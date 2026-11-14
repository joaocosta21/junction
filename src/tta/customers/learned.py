"""What the agent learns about where the recipe (the formula) matters, per customer and product (lane LF).

Scores on the 20% "solving the problem and user need" (a buyer who uses a product as an ingredient does not have to
write "for baking" on every request) and on the 20% "autonomy and controls" (each thing learned names its source and
its evidence, a person's own decision outranks everything, and the buyer can switch the learning off).

Nothing is stored: every finding is computed again, each time, from what can be seen now.

    DECISION  what a person of this buyer decided about a substitute whose formula differed (the order book)
    WORDS     how often the buyer's past requests for the product said the formula matters (the audit trail)
    USE       the customer file's mark: INGREDIENT (it goes into something they make) or SERVED (as it is)

A decision outranks words, words outrank the use mark, and a later decision outranks an earlier one. The customer
files are synthetic, so a finding that rests on the use mark says so. What is learned only ever adds the check to a
request line (`RequestLine.keep_formula`); it never removes one the request or the profile asks for.

`learn`, `learned_for_usual` and `apply_learned` are pure. `past_of` reads a store and writes nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import Field

from tta.catalog.kinds import is_raw_type
from tta.contracts.audit import EVENT_TYPE_PREFIX, AuditEventType
from tta.contracts.common import ApprovalStatus, Contract, JsonDict, OrderStatus
from tta.contracts.customer import Customer, ProductUse, UsualProduct
from tta.contracts.errors import InvalidRequest
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.policy import BuyerProfile, FormulaMode
from tta.contracts.ports import Catalog, Store
from tta.contracts.request import ProductQuery, PurchaseRequest, RequestLine
from tta.policy.text import join_words, plain_name

ACCEPTANCES_TO_UNLEARN = 2  # ours: this many accepted formula-changing substitutes in a row show it does not matter
WORDS_MIN_REQUESTS = 2  # ours: one request that said so is a word, not a habit
WORDS_MIN_SHARE = Decimal("0.5")  # ours: at least half of the past requests for the product said so
MAX_PRODUCTS_PER_LINE = 10  # a line naming more ids is a list of alternatives: only the first ones are looked at
PARSED_TYPE = f"{EVENT_TYPE_PREFIX}{AuditEventType.REQUEST_PARSED.value}"
REQUESTED_OPTION_KEY = "requested_option_id"  # as `tta.orders.records`: the option first asked for
APPLIED_BY = "gateway"
APPLIED_FACT = "applied_by_gateway"  # the key of the "request parsed" event's facts; the buyer's own record

FROM_THE_FILE = "Learned from your customer file, which is synthetic."
SUMMARY_FROM_THE_FILE = "From your customer file, which is synthetic."
NOT_RECORDED = (
    "Why the person decided is not recorded: a rejection counts whatever its reason, and choosing another option "
    "is not told apart from leaving the product out."
)
NOTHING_LEARNED = (
    "Nothing learned yet for {label}: no decision on a substitute for it, too few requests that said the recipe "
    "matters, and no usual product of yours tells how you use it."
)
RAW_HAS_NO_RECIPE = (
    "{label} is raw {kind}, which has no recipe of its own: nothing is learned for it from how you use it, and a "
    "substitute is judged as for any product."
)
ONE_INGREDIENT = "you use it as an ingredient"
NOTHING_AT_ALL = "Nothing learned yet: no decision, request or customer file says where the recipe matters."
APPLIED_NOTE = (
    "Request line {line}: {sentence} The gateway applied this; your request did not say it. Change this in Settings."
)
# Who says the formula matters, as the offer words it (`tta.offers.candidates.REQUEST_SAYS_FORMULA`). The offer is
# built from the request with the check added, so it reads "the request says"; on a line the gateway added the
# check to, the request did not say it: what was learned did (`said_on`).
REQUEST_SAYS = "the request says the formula matters"
LEARNED_SAYS = "what the agent learned about your orders says the formula matters"


class LearnedSource(StrEnum):
    DECISION = "DECISION"
    WORDS = "WORDS"
    USE = "USE"


class SubstituteDecision(StrEnum):
    """What a person did with an option that held a substitute whose formula differed from the original's."""

    REJECTED = "REJECTED"
    CHOSE_ANOTHER = "CHOSE_ANOTHER"  # approved another option of the offer, one without such a substitute for it
    ACCEPTED = "ACCEPTED"


@dataclass(frozen=True)
class PastDecision:
    product_id: str  # the product asked for, which the substitute stood in for
    kind: SubstituteDecision
    decided_at: datetime
    approval_id: str


@dataclass(frozen=True)
class PastAsk:
    """One line of a past request of the buyer."""

    asked_at: datetime
    product_ids: tuple[str, ...]
    product_type: str | None
    said_use: bool  # the line said the formula matters (`keep_formula`), as "for baking" is read


@dataclass(frozen=True)
class Past:
    """What the order book and the audit trail show of one buyer."""

    decisions: tuple[PastDecision, ...] = ()
    asks: tuple[PastAsk, ...] = ()


class Finding(Contract):
    """Whether the recipe matters for one product of one customer, with the reason and the evidence."""

    product_id: str
    name: str | None = None
    product_type: str | None = None
    matters: bool | None = Field(description="None: there is nothing to learn from")
    source: LearnedSource | None = None
    sentence: str
    evidence: JsonDict = Field(default_factory=dict)
    synthetic: bool = Field(default=False, description="The evidence is the customer file's, which is made up")


class Applied(Contract):
    """One request line the gateway added the formula check to, and the finding it rests on."""

    line: int = Field(description="The request line, counted from 1")
    product_id: str
    finding: Finding
    note: str


@dataclass(frozen=True)
class Prepared:
    """A request as the offer is built from it, and as the buyer sent it."""

    request: PurchaseRequest
    original: PurchaseRequest
    applied: tuple[Applied, ...] = ()

    @property
    def notes(self) -> tuple[str, ...]:
        return tuple(each.note for each in self.applied)

    @property
    def facts(self) -> list[JsonDict]:
        """For the audit trail: what the gateway applied, per line, with its source. The buyer's own record."""
        return [
            {"line": each.line, "product_id": each.product_id, "keep_formula": True, "applied_by": APPLIED_BY,
             "source": each.finding.source.value if each.finding.source else None,
             "synthetic": each.finding.synthetic, "sentence": each.finding.sentence,
             "evidence": each.finding.evidence}
            for each in self.applied
        ]


# --- wording ----------------------------------------------------------------------------------------------------


def _label(product_id: str, name: str | None) -> str:
    return f"{plain_name(name)} ({product_id})" if name else f"product {product_id}"


def _day(moment: datetime) -> str:
    return f"{moment.day} {moment:%B %Y}"


# --- the three sources ------------------------------------------------------------------------------------------


def _from_decisions(product_id: str, label: str, past: Past) -> tuple[bool, str, JsonDict] | None:
    mine = (each for each in past.decisions if each.product_id == product_id)
    signals = sorted(mine, key=lambda each: each.decided_at)
    if not signals:
        return None
    against = [each for each in signals if each.kind is not SubstituteDecision.ACCEPTED]
    # By position, not by time: in replay the clock stands still, and decisions made at one instant keep the
    # order the book holds them in (the sort is stable).
    since = signals[signals.index(against[-1]) + 1:] if against else signals
    evidence: JsonDict = {
        "rejected": sum(each.kind is SubstituteDecision.REJECTED for each in signals),
        "chose_another": sum(each.kind is SubstituteDecision.CHOSE_ANOTHER for each in signals),
        "accepted": sum(each.kind is SubstituteDecision.ACCEPTED for each in signals),
        "accepted_since": len(since) if against else None,
        "last_decided_at": signals[-1].decided_at.isoformat(),
        "approval_ids": [each.approval_id for each in signals],
        "not_recorded": NOT_RECORDED,
    }
    if len(since) >= ACCEPTANCES_TO_UNLEARN:
        return False, (
            f"You accepted a substitute with different ingredients for {label} {len(since)} times, last on "
            f"{_day(since[-1].decided_at)}, so a substitute need not keep its recipe."
        ), evidence
    if not against:
        return None  # one acceptance teaches nothing yet
    last = against[-1]
    did = "rejected" if last.kind is SubstituteDecision.REJECTED else "chose another option over"
    return True, (
        f"You {did} a substitute with different ingredients for {label} on {_day(last.decided_at)}, so "
        "substitutes must keep its recipe."
    ), evidence


def _from_words(product_id: str, product_type: str | None, label: str, past: Past) -> tuple[bool, str, JsonDict] | None:
    asks = [each for each in past.asks if product_id in each.product_ids
            or (not each.product_ids and product_type is not None and each.product_type == product_type)]
    said = [each for each in asks if each.said_use]
    if len(asks) < WORDS_MIN_REQUESTS or not said or Decimal(len(said)) / len(asks) < WORDS_MIN_SHARE:
        return None
    evidence: JsonDict = {
        "requests": len(asks), "said_recipe_matters": len(said), "min_share": str(WORDS_MIN_SHARE),
        "min_requests": WORDS_MIN_REQUESTS, "last_said_at": max(each.asked_at for each in said).isoformat(),
    }
    return True, (
        f"{len(said)} of your {len(asks)} past requests for {label} said the recipe matters, so a substitute must "
        "keep its recipe."
    ), evidence


def _from_use(
    customer: Customer, product_id: str, product_type: str | None, label: str, names: Mapping[str, str]
) -> tuple[bool | None, str, JsonDict] | None:
    usual = customer.usual_product(product_id)
    raw = _raw(customer, usual, product_type, label)
    if raw is not None:
        return raw
    if usual is not None:
        evidence = _use_evidence(customer, (usual,), "PRODUCT", usual.product_type)
        if usual.use is ProductUse.INGREDIENT:
            said = f"You use {label} as an ingredient, so a substitute must keep its recipe. {FROM_THE_FILE}"
            return True, said, evidence
        return False, f"You serve {label} as it is, so a substitute need not keep its recipe. {FROM_THE_FILE}", evidence
    same_type = tuple(each for each in customer.usual if product_type is not None and each.product_type == product_type)
    if not same_type:
        return None
    ingredients = tuple(each for each in same_type if each.use is ProductUse.INGREDIENT)
    kind = str(product_type).replace("_", " ")
    if ingredients:
        listed = join_words([_label(each.product_id, names.get(each.product_id)) for each in ingredients])
        return True, (
            f"You use {kind} as an ingredient ({listed}), so a substitute for {label} must keep its recipe. "
            f"{FROM_THE_FILE}"
        ), _use_evidence(customer, ingredients, "PRODUCT_TYPE", product_type)
    return False, (
        f"You serve {kind} as it is, so a substitute for {label} need not keep its recipe. {FROM_THE_FILE}"
    ), _use_evidence(customer, same_type, "PRODUCT_TYPE", product_type)


def _raw(
    customer: Customer, usual: UsualProduct | None, product_type: str | None, label: str
) -> tuple[None, str, JsonDict] | None:
    """A learned recipe is for composed products (a cream, a blend): raw meat or fish has none to keep, so the
    use mark teaches nothing for it, whatever the customer does with it. None: the product is not raw."""
    kind = usual.product_type if usual is not None else product_type
    if not is_raw_type(kind):
        return None
    same = (usual,) if usual is not None else tuple(each for each in customer.usual if each.product_type == kind)
    if not same:
        return None
    evidence = {**_use_evidence(customer, same, "PRODUCT" if usual is not None else "PRODUCT_TYPE", kind), "raw": True}
    return None, RAW_HAS_NO_RECIPE.format(label=label, kind=str(kind).replace("_", " ")), evidence


def _use_evidence(customer: Customer, usual: Sequence[UsualProduct], basis: str, product_type: str | None) -> JsonDict:
    ids = [each.product_id for each in usual]
    return {
        "use": usual[0].use.value, "basis": basis, "product_type": product_type, "usual_product_ids": ids,
        "past_orders_with_it": sum(1 for order in customer.history if set(ids) & set(order.quantities)),
        "synthetic": customer.synthetic,
    }


# --- learning ---------------------------------------------------------------------------------------------------


def learn(
    customer: Customer | None, product_id: str, past: Past = Past(), *, product_type: str | None = None,
    name: str | None = None, names: Mapping[str, str] | None = None,
) -> Finding:
    """Whether the recipe matters for this product of this customer, from the strongest source that says anything.

    `product_type`: the product's type, for a product that is not one of the customer's usual ones. `names`: the
    names of the customer's usual products by id, for the sentence."""
    usual = customer.usual_product(product_id) if customer is not None else None
    kind = usual.product_type if usual is not None else product_type
    label = _label(product_id, name)
    found = _from_decisions(product_id, label, past)
    source = LearnedSource.DECISION
    if found is None:
        found, source = _from_words(product_id, kind, label, past), LearnedSource.WORDS
    if found is None and customer is not None:
        found, source = _from_use(customer, product_id, kind, label, names or {}), LearnedSource.USE
    if found is None:
        return Finding(product_id=product_id, name=name, product_type=kind, matters=None,
                       sentence=NOTHING_LEARNED.format(label=label))
    matters, sentence, evidence = found
    return Finding(product_id=product_id, name=name, product_type=kind, matters=matters, source=source,
                   sentence=sentence, evidence=evidence, synthetic=source is LearnedSource.USE)


def learned_for_usual(
    customer: Customer, past: Past = Past(), names: Mapping[str, str] | None = None
) -> tuple[Finding, ...]:
    """What is learned for each usual product of the customer, in the file's order."""
    names = names or {}
    return tuple(learn(customer, usual.product_id, past, name=names.get(usual.product_id), names=names)
                 for usual in customer.usual)


def summary_of(findings: Sequence[Finding]) -> str:
    """One line for the side card: the products whose recipe must be kept, by source."""
    kept = [each for each in findings if each.matters is True]
    if not kept:
        return NOTHING_AT_ALL
    reasons = {
        LearnedSource.USE: "you use them as ingredients", LearnedSource.WORDS: "your requests said so",
        LearnedSource.DECISION: "you decided so on a substitute",
    }
    parts = [
        f"{', '.join(plain_name(each.name) if each.name else f'product {each.product_id}' for each in group)} "
        f"({ONE_INGREDIENT if source is LearnedSource.USE and len(group) == 1 else why})"
        for source, why in reasons.items() if (group := [each for each in kept if each.source is source])
    ]
    synthetic = f" {SUMMARY_FROM_THE_FILE}" if any(each.synthetic for each in kept) else ""
    return f"Learned so far: {'; '.join(parts)}.{synthetic}"


# --- applying it to a request -----------------------------------------------------------------------------------

TypeOf = Callable[[str], str | None]


def _for_line(
    line: RequestLine, customer: Customer | None, past: Past, type_of: TypeOf, names: Mapping[str, str]
) -> Finding | None:
    """The finding that makes the recipe matter on this line, or None. A line naming products: the first of them
    it matters for. A line naming only a type: the customer's usual products of that type, in the line's unit
    when any is ordered in it."""
    if line.product_ids:
        findings = [
            learn(customer, product_id, past, name=names.get(product_id), names=names,
                  product_type=None if customer and customer.usual_product(product_id) else type_of(product_id))
            for product_id in line.product_ids[:MAX_PRODUCTS_PER_LINE]
        ]
    elif line.product_type is not None and customer is not None:
        of_type = [each for each in customer.usual if each.product_type == line.product_type]
        in_unit = [each for each in of_type if each.unit is line.unit] or of_type
        findings = [learn(customer, each.product_id, past, name=names.get(each.product_id), names=names)
                    for each in in_unit]
    else:
        return None
    return next((each for each in findings if each.matters is True), None)


def apply_learned(
    request: PurchaseRequest, customer: Customer | None, past: Past, *, type_of: TypeOf,
    names: Mapping[str, str] | None = None,
) -> Prepared:
    """The request with `keep_formula` on each line the recipe is learned to matter for and that does not say so
    already. `type_of` gives the product type of a product that is not one of the customer's usual ones (None:
    not known). The request given is not changed: `Prepared.original` is the same object."""
    names = names or {}
    lines: list[RequestLine] = []
    applied: list[Applied] = []
    for index, line in enumerate(request.lines):
        finding = None if line.keep_formula is True else _for_line(line, customer, past, type_of, names)
        if finding is None:
            lines.append(line)
            continue
        lines.append(line.model_copy(update={"keep_formula": True}))
        note = APPLIED_NOTE.format(line=index + 1, sentence=finding.sentence)
        applied.append(Applied(line=index + 1, product_id=finding.product_id, finding=finding, note=note))
    if not applied:
        return Prepared(request=request, original=request)
    changed = request.model_copy(update={"lines": tuple(lines)})
    return Prepared(request=changed, original=request, applied=tuple(applied))


# --- reading the past of one buyer from a store (reads only) ----------------------------------------------------


def _changing(option: OfferOption | None) -> set[str]:
    """The products asked for that the option replaces with a substitute whose formula is measured and differs.
    A substitute with no comparison says nothing: no data is unknown, never "differs"."""
    if option is None:
        return set()
    return {
        line.substitute.original_id for line in option.lines
        if line.substitute is not None and line.substitute.formula is not None
        and not line.substitute.formula.keeps_formula
    }


def _decisions(store: Store, profile_id: str) -> list[PastDecision]:
    found: list[PastDecision] = []
    for approval in store.list_approvals(profile_id=profile_id):
        if approval.status not in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED) or not approval.decisions:
            continue
        order, offer = store.get_order(approval.order_id), store.get_offer(approval.offer_id)
        if order is None or offer is None:
            continue
        asked = _changing(offer.option(str(order.extra.get(REQUESTED_OPTION_KEY) or approval.option_id)))
        at = approval.decisions[-1].decided_at
        if approval.status is ApprovalStatus.REJECTED:
            kinds = dict.fromkeys(asked, SubstituteDecision.REJECTED)
        elif order.status is OrderStatus.ORDERED:
            taken = _changing(order.option)
            kinds = {**dict.fromkeys(asked - taken, SubstituteDecision.CHOSE_ANOTHER),
                     **dict.fromkeys(taken, SubstituteDecision.ACCEPTED)}
        else:
            continue
        found.extend(PastDecision(product_id, kind, at, approval.approval_id)
                     for product_id, kind in sorted(kinds.items()))
    return found


def _asks(store: Store, profile_id: str) -> list[PastAsk]:
    found: list[PastAsk] = []
    for event in store.list_audit_events(profile_id=profile_id):
        request: Any = event.data.facts.get("request")
        lines = request.get("lines") if event.type == PARSED_TYPE and isinstance(request, dict) else None
        applied: Any = event.data.facts.get(APPLIED_FACT)
        # A line the gateway added the check to is left out: the buyer had no need to say it there, so its
        # silence is not a request that did not care (otherwise what is learned from words would unlearn itself).
        entries = applied if isinstance(applied, list) else []
        taught = {each.get("line") for each in entries if isinstance(each, dict)}
        for number, line in enumerate(lines if isinstance(lines, list) else (), start=1):
            if isinstance(line, dict) and number not in taught:
                ids = tuple(str(each) for each in line.get("product_ids") or ())
                kind = line.get("product_type")
                found.append(PastAsk(event.time, ids, kind if isinstance(kind, str) else None,
                                     line.get("keep_formula") is True))
    return found


def past_of(store: Store, profile_id: str) -> Past:
    """What the order book and the audit trail of this store show of one buyer: every decided approval whose
    option replaced a product with a formula-changing substitute, and every line of its past requests. The requests
    are the buyer's own words: a line the gateway applied learning to counts neither for nor against."""
    return Past(decisions=tuple(_decisions(store, profile_id)), asks=tuple(_asks(store, profile_id)))


# --- for the gateway: one buyer's request before its offer is built, and what the buyer may read ----------------

MODE_NOTES = {
    FormulaMode.ALWAYS: "A substitute must keep the recipe on every line: nothing needs to be learned.",
    FormulaMode.LEARN: "A substitute must keep the recipe where the past shows it matters, and where a request "
                       "says so.",
    FormulaMode.WHEN_ASKED: "A substitute must keep the recipe only where a request says so: what is learned is "
                            "shown and not applied.",
}


class LearnedView(Contract):
    """What the gateway has learned for one buyer, computed now: nothing of it is stored."""

    mode: FormulaMode
    applied: bool = Field(description="Whether what is learned is applied to requests: only in the mode LEARN")
    findings: tuple[Finding, ...] = Field(default=(), description="One per usual product of the customer file")
    summary: str
    note: str


def _names(catalog: Catalog, product_ids: Sequence[str]) -> dict[str, str]:
    found = ((product_id, catalog.get_product(product_id)) for product_id in dict.fromkeys(product_ids))
    return {product_id: product.display_name for product_id, product in found if product is not None}


def _type_finder(catalog: Catalog, customer: Customer | None) -> TypeOf:
    """The product type of a product, among the types of the customer's usual products: the only ones a use mark
    can speak for."""
    kinds = tuple(dict.fromkeys(each.product_type for each in customer.usual)) if customer is not None else ()

    def type_of(product_id: str) -> str | None:
        for kind in kinds:
            try:
                found = catalog.search(ProductQuery(product_type=kind, product_ids=(product_id,), limit=1))
            except InvalidRequest:  # a type the catalog no longer has: it speaks for nothing
                continue
            if any(product.id == product_id for product in found.products):
                return kind
        return None

    return type_of


def prepare(
    request: PurchaseRequest, *, profile: BuyerProfile, customer: Customer | None, store: Store, catalog: Catalog
) -> Prepared:
    """The request as its offer is built: in the mode LEARN, with what is learned applied; otherwise as sent."""
    if profile.formula_mode_in_force is not FormulaMode.LEARN:
        return Prepared(request=request, original=request)
    usual = [each.product_id for each in customer.usual] if customer is not None else []
    named = [product_id for line in request.lines for product_id in line.product_ids[:MAX_PRODUCTS_PER_LINE]]
    return apply_learned(
        request, customer, past_of(store, profile.profile_id), type_of=_type_finder(catalog, customer),
        names=_names(catalog, [*usual, *named]),
    )


def said_on(offer: Offer, prepared: Prepared) -> Offer:
    """The offer with the request as the buyer sent it and one note per line the gateway added the check to. The
    offer's lines keep `keep_formula`, which rule F-11 reads; the request is the buyer's own and is not rewritten.
    Where the offer's own sentences name who says the formula matters, a line the gateway added the check to names
    what was learned, never the request, which did not say it."""
    if not prepared.applied:
        return offer
    learned = {each.line for each in prepared.applied}
    notes = tuple(_who_said(note, learned) for note in offer.notes)
    # An option's headline names who said it for its first formula-changing line: reworded only when no line of
    # the request said so itself, so a request's own word is never taken from it.
    only_learned = not any(line.keep_formula is True for line in prepared.original.lines)
    options = tuple(
        option.model_copy(update={"summary": _learned_says(option.summary)}) if only_learned else option
        for option in offer.options
    )
    return offer.model_copy(
        update={"request": prepared.original, "options": options, "notes": (*notes, *prepared.notes)}
    )


def _learned_says(text: str) -> str:
    capital = REQUEST_SAYS[0].upper() + REQUEST_SAYS[1:]
    return text.replace(REQUEST_SAYS, LEARNED_SAYS).replace(capital, LEARNED_SAYS[0].upper() + LEARNED_SAYS[1:])


def _who_said(note: str, learned: set[int]) -> str:
    """A note of the offer about one request line ("Request line 2: ..."): reworded when the line is a learned one."""
    return _learned_says(note) if any(note.startswith(f"Request line {line}: ") for line in learned) else note


def learned_view(
    *, profile: BuyerProfile, customer: Customer | None, store: Store, catalog: Catalog
) -> LearnedView:
    mode = profile.formula_mode_in_force
    if customer is None:
        findings: tuple[Finding, ...] = ()
    else:
        names = _names(catalog, [each.product_id for each in customer.usual])
        findings = learned_for_usual(customer, past_of(store, profile.profile_id), names)
    return LearnedView(mode=mode, applied=mode is FormulaMode.LEARN, findings=findings,
                       summary=summary_of(findings), note=MODE_NOTES[mode])
