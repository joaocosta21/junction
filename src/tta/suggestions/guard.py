"""The guard: every suggestion is checked like any product before it leaves the gateway (P15 section 4.3, R3).

A suggestion is judged as the line it would become: the line of its `accept_request` goes through the offer
package's own judgement (`need_for`, `evaluate`, `exclusion_for` of `tta.offers.candidates`, read-only), so the
buyer's allergen exclusions under the profile's rule, the pack preference, the availability state, the needed-by
date and the price are the same checks an offer line meets. On top of them a suggestion must hold what an offer
line may leave to a person:

* an excluded allergen the data does not rule out is never suggested (under STRICT, no data means not suggested);
* a dietary claim the line requires, or that the product it replaces or resembles carries, must be carried;
* a suggestion that replaces a product adds no allergen to it (rule F-05) and keeps its formula where the formula
  matters: always for the cheaper line, and for every replacing kind when the profile says `formula_matters`;
* only confirmed stock that covers the whole quantity for the needed date is suggested.

A suggestion that fails is dropped, and the reason is kept for the log (`DroppedSuggestion`). One that passes
leaves complete: availability, confirmed stock, what it adds in money, and the sentences of each check.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from tta.allergens import check_substitute
from tta.contracts.common import AllergenOutcome, AllergenRelation, AvailabilityState, Contract, round_money
from tta.contracts.errors import InvalidRequest
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import Catalog
from tta.contracts.product import Product
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.contracts.suggestion import Suggestion, SuggestionEffect, SuggestionKind
from tta.offers.candidates import Candidate, Need, evaluate, exclusion_for, need_for, units_needed
from tta.offers.deps import Lookup
from tta.offers.formula import compare_formula
from tta.offers.safety import ruled_out
from tta.offers.substitutes import COVERED_BY, claims_lost
from tta.suggestions import reasons
from tta.suggestions.wording import amount, confirmed_words, euros, last_tail, number, packs, sentence, stock_amount

# The kinds whose product is a line the request did not have: accepting adds its cost to the order.
ADDS_A_LINE = frozenset({SuggestionKind.FORGOTTEN_ITEM, SuggestionKind.FROM_SUPPLIER})
# The kinds that always keep the formula of what they replace, whatever the profile says (P10 F6).
ALWAYS_KEEPS_FORMULA = frozenset({SuggestionKind.CHEAPER_SAME_FORMULA, SuggestionKind.LARGER_PACK})


class DropReason(StrEnum):
    """Why the guard dropped a suggestion. A reason of the offer's own checks keeps its `ExclusionReason` code
    (ALLERGEN_DECLARED, CUTOFF_PASSED, LATE_FOR_NEEDED_BY, ...); these are the guard's own."""

    UNKNOWN_PRODUCT = "UNKNOWN_PRODUCT"
    ALREADY_ORDERED = "ALREADY_ORDERED"
    ALLERGEN_NOT_RULED_OUT = "ALLERGEN_NOT_RULED_OUT"
    DIETARY_CLAIM_MISSING = "DIETARY_CLAIM_MISSING"
    ADDS_ALLERGEN = "ADDS_ALLERGEN"
    FORMULA_NOT_KEPT = "FORMULA_NOT_KEPT"
    STOCK_NOT_CONFIRMED = "STOCK_NOT_CONFIRMED"
    STOCK_TOO_LOW = "STOCK_TOO_LOW"
    # Valio Aimo's own suggestion only (decision B32): it passed every check above and still stays silent.
    OTHER_PACK_KIND = "OTHER_PACK_KIND"  # a portion pack for a usual bulk product, or the other way round
    ONE_UNIT_IN_STOCK = "ONE_UNIT_IN_STOCK"  # one sales unit confirmed in stock is not a suggestion
    NO_STATED_BENEFIT = "NO_STATED_BENEFIT"  # it passed every check and has no benefit it can state (lane SG)


class DroppedSuggestion(Contract):
    """A suggestion the guard did not let through, with the reason, for the audit trail. Never shown as an offer."""

    suggestion_id: str
    kind: SuggestionKind
    product_id: str
    name: str
    reason: str  # a `DropReason`, or the `ExclusionReason` of the offer's own check
    sentence: str
    summary: str = ""  # the reason in a few words for a list or a log line (`tta.suggestions.reasons`)


@dataclass(frozen=True)
class Failure:
    """The first check a suggestion fails: the reason code, the check's sentence, the reason in a few words."""

    reason: str
    sentence: str
    summary: str


@dataclass(frozen=True)
class Proposal:
    """A suggestion before the guard. `like_product_id`: the product whose dietary claims it must keep without
    replacing it (the product a supplier's related suggestion resembles); a replaced product is always kept to."""

    suggestion: Suggestion
    like_product_id: str | None = None


@dataclass(frozen=True)
class GuardContext:
    """What the guard reads: the request the suggestion amends, the buyer's profile, one look at price and
    availability, the catalog, and the products already in an order placed or waiting for the same date."""

    request: PurchaseRequest
    profile: BuyerProfile
    lookup: Lookup
    catalog: Catalog
    already_ordered: Collection[str] = ()


def check(proposal: Proposal, context: GuardContext) -> Suggestion | DroppedSuggestion:
    """The suggestion, complete, or why it is dropped. Never raises for a product that fails a check."""
    suggestion = proposal.suggestion
    product = _product(context.catalog, suggestion.product_id)
    if product is None:
        return dropped(suggestion, Failure(DropReason.UNKNOWN_PRODUCT, "The product is not in the catalog.",
                                           reasons.UNKNOWN_PRODUCT))
    if suggestion.kind in ADDS_A_LINE and suggestion.product_id in context.already_ordered:
        said = "The product is already in an order placed or waiting for the same delivery date."
        return dropped(suggestion, Failure(DropReason.ALREADY_ORDERED, said, reasons.ALREADY_ORDERED))
    index, line, accept = _line_to_judge(suggestion, context.request)
    try:
        need = need_for(index, line, accept, context.profile)
    except InvalidRequest as error:
        return dropped(suggestion, Failure(DropReason.ALLERGEN_NOT_RULED_OUT, str(error), reasons.ALLERGEN_DOUBT))
    candidate = evaluate(product, need, context.lookup, context.catalog)
    failed = _first_failure(proposal, candidate, need, line, context)
    if failed is not None:
        return dropped(suggestion, failed)
    return _complete(suggestion, candidate, need, context)


def _product(catalog: Catalog, product_id: str) -> Product | None:
    product = catalog.get_product(product_id)
    return None if product is None or product.deleted else product


def _line_to_judge(suggestion: Suggestion, request: PurchaseRequest) -> tuple[int, RequestLine, PurchaseRequest]:
    """The line the suggestion would become, with its index and the request that holds it. A suggestion without
    an `accept_request` is judged as a line of its product and quantity added to the request."""
    accept = suggestion.accept_request
    if accept is not None:
        holding = [index for index, line in enumerate(accept.lines) if line.product_ids == (suggestion.product_id,)]
        if suggestion.request_line_index in holding:
            return suggestion.request_line_index, accept.lines[suggestion.request_line_index], accept
        if holding:
            return holding[-1], accept.lines[holding[-1]], accept
    line = RequestLine(text=suggestion.name, product_ids=(suggestion.product_id,), quantity=suggestion.quantity,
                       unit=suggestion.unit)
    return len(request.lines), line, request


def _first_failure(proposal: Proposal, candidate: Candidate, need: Need, line: RequestLine,
                   context: GuardContext) -> Failure | None:
    """The first check the product fails; None when it passes them all."""
    excluded = exclusion_for(candidate, need, context.lookup.now)
    if excluded is not None:
        summary = reasons.exclusion_summary(excluded[0], candidate.allergen_check)
        return Failure(excluded[0].value, excluded[1], summary)
    return (
        _allergen_doubt(candidate)
        or _claims(proposal, candidate.product, line, context.catalog)
        or _replacement(proposal.suggestion, candidate.product, context)
        or _stock(candidate, need)
    )


def _allergen_doubt(candidate: Candidate) -> Failure | None:
    """The offer's own test (`tta.offers.safety.ruled_out`), under either allergen rule: a product is suggested
    only when its data states it is free from every excluded allergen. Under the declared-only rule a product
    with no statement passes the rule and is still not ruled out; the offer labels it "allergen not ruled
    out", so a suggestion for it is dropped (Python review, item P3)."""
    check_ = candidate.allergen_check
    if check_ is None or ruled_out(check_):
        return None
    doubts = [finding.sentence for finding in check_.findings
              if finding.outcome is not AllergenOutcome.PASS or finding.relation is not AllergenRelation.FREE_FROM]
    said = sentence(*doubts, "A product whose data does not rule out an excluded allergen is not suggested.")
    return Failure(DropReason.ALLERGEN_NOT_RULED_OUT.value, said, reasons.allergen_summary(check_))


def _claims(proposal: Proposal, product: Product, line: RequestLine, catalog: Catalog) -> Failure | None:
    """The claims the line requires, and the dietary claims of the product it replaces or resembles."""
    carried = frozenset(product.nutritional_claims)
    missing = [claim for claim in line.required_claims
               if claim not in carried and not COVERED_BY.get(claim, frozenset()) & carried]
    if missing:
        said = f"The request line requires {', '.join(missing)}, which this product does not carry."
        summary = reasons.CLAIM_NOT_CARRIED.format(claims=", ".join(missing))
        return Failure(DropReason.DIETARY_CLAIM_MISSING.value, said, summary)
    other_id = proposal.suggestion.replaces_product_id or proposal.like_product_id
    other = _product(catalog, other_id) if other_id is not None else None
    lost = claims_lost(other, product) if other is not None else ()
    if lost:
        said = f"Product {other_id} carries {', '.join(lost)}, which this product does not."
        summary = reasons.CLAIM_LOST.format(claims=", ".join(lost), product_id=other_id)
        return Failure(DropReason.DIETARY_CLAIM_MISSING.value, said, summary)
    return None


def _replacement(suggestion: Suggestion, product: Product, context: GuardContext) -> Failure | None:
    """A suggestion that replaces a product adds no allergen to it and, where the formula matters, keeps it."""
    if suggestion.replaces_product_id is None:
        return None
    original = _product(context.catalog, suggestion.replaces_product_id)
    replaced = suggestion.replaces_product_id
    if original is None:
        said = "The product it would replace is not in the catalog."
        return Failure(DropReason.UNKNOWN_PRODUCT.value, said, f"{replaced}, which it would replace, is not in the "
                                                                "catalog")
    added = check_substitute(original.allergen_statements, product.allergen_statements)
    if not added.passes:
        summary = reasons.ADDS_ALLERGEN.format(product_id=replaced)
        return Failure(DropReason.ADDS_ALLERGEN.value, added.sentence, summary)
    if suggestion.kind not in ALWAYS_KEEPS_FORMULA and not context.profile.formula_matters:
        return None
    formula = compare_formula(original, product)
    if formula.keeps_formula:
        return None
    summary = reasons.FORMULA_NOT_KEPT.format(product_id=replaced)
    return Failure(DropReason.FORMULA_NOT_KEPT.value, formula.sentence, summary)


def _stock(candidate: Candidate, need: Need) -> Failure | None:
    """Only confirmed stock that covers the whole quantity is suggested (P15 section 4.3, rules 6 and 7)."""
    if candidate.state is not AvailabilityState.CONFIRMED:
        said = candidate.assessment.sentence
        return Failure(DropReason.STOCK_NOT_CONFIRMED.value, said, reasons.STOCK_NOT_CONFIRMED)
    units, usable = _units(candidate, need), candidate.assessment.usable_amount or Decimal(0)
    if usable < units:
        stock = f"{_sales_units(usable)} confirmed in stock and {number(units)} are needed"
        said = f"{stock} for {amount(need.quantity or Decimal(0), need.unit)}."
        return Failure(DropReason.STOCK_TOO_LOW.value, said, stock)
    return None


def _sales_units(count: Decimal, *, verb: bool = True) -> str:
    """ "1 pack is", "114 packs are"; without the verb for a cost. "pack" for the sales unit, whose codes are not
    documented (`wording.PACKS`)."""
    one = count == 1
    words = packs(count)
    return f"{words} {'is' if one else 'are'}" if verb else words


def _units(candidate: Candidate, need: Need) -> Decimal:
    return units_needed(candidate, need.quantity or Decimal(0))


def _complete(suggestion: Suggestion, candidate: Candidate, need: Need, context: GuardContext) -> Suggestion:
    """The suggestion with what the guard read: availability, confirmed stock, the cost, each check's sentence.
    A suggestion that came without its effect gets the price for its quantity, then the stock, said after the
    kind's own reason ("Adding 10 L costs €33.10. 114 L confirmed for Monday 16 November."); "From a synthetic
    order history." stays the last sentence. Prices are before tax, as Valio Aimo's webshop shows them first."""
    units = _units(candidate, need)
    net = round_money(units * candidate.unit_price)
    assessment = candidate.assessment
    usable = assessment.usable_amount or Decimal(0)
    stock = confirmed_words(stock_amount(usable, candidate.per_unit, need.unit), assessment.available_date)
    quantity = amount(suggestion.quantity, suggestion.unit)
    update: dict[str, object] = {
        "availability": assessment, "stock_confirmed": True,
        "checks": (*suggestion.checks, *_check_sentences(suggestion, candidate, context), stock),
    }
    if suggestion.effect is None and suggestion.kind in ADDS_A_LINE:
        update["effect"] = SuggestionEffect(net_change_eur=net)
        update["sentence"] = last_tail(suggestion.sentence, f"Adding {quantity} costs {euros(net)}.", stock)
    elif suggestion.effect is None:
        update["sentence"] = last_tail(suggestion.sentence, f"For {quantity}: {euros(net)}.", stock)
    return suggestion.model_copy(update=update)


def _check_sentences(suggestion: Suggestion, candidate: Candidate, context: GuardContext) -> tuple[str, ...]:
    said: list[str] = []
    if candidate.allergen_check is not None:
        said.extend(finding.sentence for finding in candidate.allergen_check.findings)
    original = _product(context.catalog, suggestion.replaces_product_id or "")
    if original is not None:
        said.append(check_substitute(original.allergen_statements, candidate.product.allergen_statements).sentence)
        said.append("It carries every dietary claim of the product it replaces.")
        said.append(compare_formula(original, candidate.product).sentence)
    return tuple(said)


def dropped(suggestion: Suggestion, failure: Failure) -> DroppedSuggestion:
    """The suggestion as the log keeps it once a check stopped it."""
    return DroppedSuggestion(suggestion_id=suggestion.suggestion_id, kind=suggestion.kind,
                             product_id=suggestion.product_id, name=suggestion.name, reason=str(failure.reason),
                             sentence=failure.sentence, summary=failure.summary)
