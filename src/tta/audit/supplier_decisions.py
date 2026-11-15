"""The decision as Valio Aimo reads it (package S4): every rule that fired with its reason and outcome, the
logic, and the products considered and left out.

Nothing here quotes a rule's own sentence or reads its facts: both can hold a limit amount or an allergen code.
A rule is named by its id and its title, which is fixed text of `tta/policy/rules.yaml` and holds no value.
What is masked is said in the sentence (`tta.audit.readers.MASKED_BY_RULE`).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from tta.audit.phrases import HUMAN_AT_BUYER, joined, label, plain, role_name
from tta.audit.readers import (
    MASKED_BY_RULE,
    NOT_SHOWN_OR_COUNTED,
    REASONS_OF_THE_BUYER,
    RULES_ABOUT_AN_EXCLUDED_ALLERGEN,
    supplier_rule_ids,
)
from tta.contracts.common import ApproverRole, ExclusionReason, JsonDict, Verdict
from tta.contracts.offer import Exclusion, Offer
from tta.contracts.policy import FiredRule, PolicyDecision

MAX_TITLE_CHARACTERS = 160
MAX_PRODUCTS_PER_RULE = 5
# The shop page prints the sentence and no structured field, so the products left out are named in the sentence.
# The facts of the event hold every one of them.
MAX_PRODUCTS_PER_REASON = 10
FIXED_RULE = "a fixed rule"
BUYER_RULE = "a rule the buyer set"
NO_RULE_APPLIED = " No rule applied."
LOGIC = " The strictest outcome among the rules that applied decides."
BLOCKS = "the order cannot be placed"
NO_APPROVAL = "no approval is needed"
LEFT_OUT = "Left out for a reason in Valio Aimo's own data"
NONE_LEFT_OUT = "No product was left out for a reason in Valio Aimo's own data."
# F-03 fires for a fact a rule needs and does not have. When that fact is about an allergen, or only a rule
# about an excluded allergen needed it, the line it fired on would tell Valio Aimo what F-02 and P-04 hide.
MISSING_FACT_RULE = "F-03"
ALLERGEN_FACT_WORD = "allergen"
PRODUCT_NOT_SHOWN = "a product is not shown where the missing fact is about a requirement of the buyer's"
# On an order of one product the product a rule fired on is the order's own line, which other steps name: the
# sentence then claims to hide only what stays hidden (lane FIX-A1, item 10).
ALLERGEN_NOT_SHOWN = "which allergen is not shown"
REQUIREMENT_NOT_SHOWN = "the missing fact is about a requirement of the buyer's, which is not shown"
# Why a product was left out, after its count: "12 past the closing time for ordering". "Closing time" is the
# word of Valio's own webshop (AIMO/build/replan/P3-webshop.md, the mapping table).
REASON_WORDS = {
    ExclusionReason.BLOCKED: "blocked for ordering in Valio Aimo's data",
    ExclusionReason.NOT_DELIVERABLE: "that cannot be delivered",
    ExclusionReason.OUT_OF_STOCK: "out of stock",
    ExclusionReason.CUTOFF_PASSED: "past the closing time for ordering",
    ExclusionReason.LATE_FOR_NEEDED_BY: "deliverable only after the date needed",
    ExclusionReason.PORTION_PACK: "sold in portion packs, which the request does not ask for",
    ExclusionReason.NOT_A_PORTION_PACK: "not sold in portion packs, which the request asks for",
    ExclusionReason.PACK_SIZE_UNKNOWN: "with no pack size in Valio Aimo's data",
    ExclusionReason.PRICE_UNAVAILABLE: "with no price",
    ExclusionReason.SUBSTITUTE_ADDS_ALLERGEN: "that as a substitute would add an allergen the original does not "
                                              "declare",
    ExclusionReason.QUANTITY_NOT_CONFIRMED: "with a quantity that is not confirmed, when the buyer asked for "
                                            "confirmed data only",
    ExclusionReason.DELIVERY_DATE_NOT_CONFIRMED: "with a delivery date that is not confirmed, when the buyer "
                                                 "asked for confirmed data only",
    ExclusionReason.NOT_IN_RECORDING: "with no answer in the recorded copy of Valio Aimo's data",
    ExclusionReason.CLAIM_CONTRADICTED: "carrying a claim their own allergen data contradicts",
}


# One person confirms (decisions B54 and B61): whoever orders also decides a spend-limit stop, and at the hotel
# and the bakery an allergen question too. Valio Aimo read "the buyer's purchasing manager, finance and dietitian
# approved" of one person. It now reads "a person of the buyer", and a role only where the buyer has a second
# person and that role is what was asked: the dietitian of the ward and of the school. Never a name.
PERSON_OF_BUYER = "a person of the buyer"
BUYERS_DIETITIAN = "the buyer's dietitian"
DIETITIAN = ApproverRole.DIETITIAN.value


def who_is_asked(roles: Iterable[str], own_dietitian: bool | None = None) -> str:
    """a person of the buyer · the buyer's dietitian · a person of the buyer and the buyer's dietitian · a human at
    the buyer (no role is known). `roles` are the roles asked for or still missing. `own_dietitian` False: the
    person who orders holds the dietitian's role too, so no dietitian is named. None: the buyer's profile is not
    known, and the dietitian is named as she was asked."""
    asked = list(dict.fromkeys(str(role) for role in roles))
    if not asked:
        return HUMAN_AT_BUYER
    dietitian = DIETITIAN in asked and own_dietitian is not False
    person = any(role != DIETITIAN for role in asked) or not dietitian
    return joined([*([PERSON_OF_BUYER] if person else []), *([BUYERS_DIETITIAN] if dietitian else [])])


def who_signed(roles: Iterable[str], own_dietitian: bool | None = None) -> str:
    """One signer by the roles of one token: the buyer's dietitian when it holds that role alone at a buyer with a
    dietitian of its own, otherwise a person of the buyer, however many roles the token holds."""
    held = {str(role) for role in roles}
    if not held:
        return HUMAN_AT_BUYER
    return BUYERS_DIETITIAN if held == {DIETITIAN} and own_dietitian is not False else PERSON_OF_BUYER


def buyers_roles(roles: Iterable[str]) -> str:
    """the buyer's purchasing manager · the buyer's purchasing manager and dietitian · a human at the buyer. The
    roles as they are: kept for a caller that names a role itself; the sentences use `who_is_asked` and
    `who_signed`."""
    names = [role_name(role) for role in dict.fromkeys(str(role) for role in roles)]
    return f"the buyer's {joined(names)}" if names else HUMAN_AT_BUYER


def _listed(product_ids: Sequence[str], limit: int) -> str:
    shown = [label(product_id) for product_id in product_ids[:limit]]
    more = len(product_ids) - len(shown)
    return joined([*shown, f"{more} more"] if more else shown)


def _outcome(rule: FiredRule, own_dietitian: bool | None) -> str:
    if rule.verdict is Verdict.BLOCK:
        return BLOCKS
    if rule.verdict is Verdict.APPROVAL:
        return f"approval by {who_is_asked((rule.approver_role,) if rule.approver_role else (), own_dietitian)}"
    return NO_APPROVAL


def _about_an_allergen_fact(rule: FiredRule) -> bool:
    """F-03 for a missing allergen fact. Only the fact's name and the ids of the rules that needed it are read."""
    if rule.rule_id != MISSING_FACT_RULE:
        return False
    needed_by = rule.facts.get("needed_by")
    rules = needed_by if isinstance(needed_by, (list, tuple)) else ()
    return ALLERGEN_FACT_WORD in str(rule.facts.get("missing_fact", "")) or any(
        rule_id in RULES_ABOUT_AN_EXCLUDED_ALLERGEN for rule_id in rules
    )


def _hides_product(rule: FiredRule) -> bool:
    return rule.rule_id in RULES_ABOUT_AN_EXCLUDED_ALLERGEN or _about_an_allergen_fact(rule)


def _shows_product(rule: FiredRule) -> bool:
    return rule.product_id is not None and not _hides_product(rule)


def _grouped(rules: Sequence[FiredRule]) -> list[tuple[FiredRule, list[str], bool]]:
    """One entry per rule and outcome, with the products it fired on and whether one of them is hidden: a rule
    about a line fires once per line."""
    groups: dict[tuple[str, Verdict, str | None], tuple[FiredRule, list[str], list[bool]]] = {}
    for rule in rules:
        _, products, hidden = groups.setdefault((rule.rule_id, rule.verdict, rule.approver_role), (rule, [], []))
        if _shows_product(rule) and rule.product_id not in products:
            products.append(rule.product_id)
        if _about_an_allergen_fact(rule) and rule.product_id is not None:
            hidden.append(True)
    return [(rule, products, bool(hidden)) for rule, products, hidden in groups.values()]


def _masked(rule: FiredRule, hides_a_product: bool, one_line: bool) -> str | None:
    """What the line says Valio Aimo is not shown. A rule about an excluded allergen hides the allergen and the
    product it fired on; on an order of one product only the allergen, because that product is the order's line."""
    if one_line and rule.rule_id in RULES_ABOUT_AN_EXCLUDED_ALLERGEN:
        return ALLERGEN_NOT_SHOWN
    if rule.rule_id in MASKED_BY_RULE:
        return MASKED_BY_RULE[rule.rule_id]
    if hides_a_product:
        return REQUIREMENT_NOT_SHOWN if one_line else PRODUCT_NOT_SHOWN
    return None


def _rule_line(
    rule: FiredRule, products: Sequence[str], hides_a_product: bool, own_dietitian: bool | None, one_line: bool
) -> str:
    """P-01, a rule the buyer set (the order is above the spend limit per order; the amount is not shown):
    approval by a person of the buyer."""
    title = plain(rule.title, MAX_TITLE_CHARACTERS).rstrip(".")
    masked = _masked(rule, hides_a_product, one_line)
    reason = f"{title[:1].lower()}{title[1:]}{f'; {masked}' if masked else ''}"
    on = ""
    if products:
        on = f", on {'product' if len(products) == 1 else 'products'} {_listed(products, MAX_PRODUCTS_PER_RULE)}"
    outcome = _outcome(rule, own_dietitian)
    return f"{label(rule.rule_id)}, {FIXED_RULE if rule.fixed else BUYER_RULE} ({reason}){on}: {outcome}."


def rules_applied(rules: Sequence[FiredRule], own_dietitian: bool | None = None, *, one_line: bool = False) -> str:
    """ " Rules that applied: F-01, a fixed rule (…), on product 464306: approval by …. P-01, …." or nothing.
    `own_dietitian`: whether the buyer has a dietitian of its own (`who_is_asked`). `one_line`: the order holds
    one product, so a line claims to hide no product (`_masked`)."""
    groups = _grouped(rules)
    if not groups:
        return ""
    lines = " ".join(
        _rule_line(rule, products, hidden, own_dietitian, one_line) for rule, products, hidden in groups
    )
    return f" {'Rule' if len(groups) == 1 else 'Rules'} that applied: {lines}"


def decision_explained(
    decision: PolicyDecision, own_dietitian: bool | None = None, *, one_line: bool = False
) -> str:
    """Every rule that fired and how the outcome follows from them; "No rule applied." when none fired."""
    if not decision.fired:
        return NO_RULE_APPLIED
    return f"{rules_applied(decision.fired, own_dietitian, one_line=one_line)}{LOGIC}"


def _once_where_hidden(rules: Sequence[FiredRule]) -> list[FiredRule]:
    """Every firing that names its product, and one entry per rule and outcome for the firings that hide it: how
    many lines such a rule fired on is how many lines do not rule the buyer's allergen out."""
    kept: list[FiredRule] = []
    seen: set[tuple[str, Verdict, str | None]] = set()
    for rule in rules:
        key = (rule.rule_id, rule.verdict, rule.approver_role)
        if _hides_product(rule) and key in seen:
            continue
        if _hides_product(rule):
            seen.add(key)
        kept.append(rule)
    return kept


def decision_facts(decision: PolicyDecision) -> JsonDict:
    """The decision without a rule's sentence or facts, and without the product of a rule about an allergen
    (F-02, P-04, and F-03 where the missing fact is an allergen fact)."""
    return {
        "verdict": decision.verdict.value,
        "rule_ids": list(supplier_rule_ids(decision.rule_ids)),
        "rules": [
            {
                "rule_id": rule.rule_id, "title": rule.title, "fixed": rule.fixed, "verdict": rule.verdict.value,
                "approver_role": rule.approver_role.value if rule.approver_role else None,
                "product_id": rule.product_id if _shows_product(rule) else None,
            }
            for rule in _once_where_hidden(decision.fired)
        ],
        "required_roles": [role.value for role in decision.required_roles],
        "evaluated_at": decision.evaluated_at,
    }


def _by_reason(excluded: Sequence[Exclusion]) -> dict[ExclusionReason, list[str]]:
    """The reasons about Valio Aimo's own data, in the order of the code list. None of the buyer's."""
    ordered = [reason for reason in ExclusionReason if reason not in REASONS_OF_THE_BUYER]
    found = {reason: [entry.product_id for entry in excluded if _own_reason(entry) is reason] for reason in ordered}
    return {reason: product_ids for reason, product_ids in found.items() if product_ids}


def _own_reason(entry: Exclusion) -> ExclusionReason | None:
    """The reason Valio Aimo's own data gives for leaving the product out; None when only a requirement of the
    buyer's does. A product the buyer's allergen rule excluded is listed under the reason it would have been left
    out for anyway (`Exclusion.supplier_reason`): Valio Aimo knows its own data, so a product missing from its
    own list would tell it what the buyer excludes."""
    for reason in (entry.reason, entry.supplier_reason):
        if reason is not None and reason not in REASONS_OF_THE_BUYER:
            return reason
    return None


def left_out(offer: Offer) -> str:
    """ " Left out for a reason in Valio Aimo's own data: 12 past the closing time for ordering (471690, …); ….
    Products left out for a requirement of the buyer's, if any, are not shown or counted."

    No total and no count of the masked ones, and the last sentence is always there: what Valio Aimo reads is the
    same whatever the buyer excludes, and whether it excludes anything."""
    parts = [
        f"{len(product_ids):,} {REASON_WORDS[reason]} ({_listed(product_ids, MAX_PRODUCTS_PER_REASON)})"
        for reason, product_ids in _by_reason(offer.excluded).items()
    ]
    listed = f"{LEFT_OUT}: {'; '.join(parts)}." if parts else NONE_LEFT_OUT
    return f" {listed} {NOT_SHOWN_OR_COUNTED}"


def left_out_counts(offer: Offer) -> dict[str, int]:
    """How many products were left out for each reason about Valio Aimo's own data, by reason code."""
    return {reason.value: len(product_ids) for reason, product_ids in sorted(_by_reason(offer.excluded).items())}


def left_out_facts(offer: Offer) -> list[JsonDict]:
    """Each product left out for a reason about Valio Aimo's own data. None left out for a requirement of the
    buyer's."""
    return [
        {"product_id": entry.product_id, "name": entry.name, "request_line_index": entry.request_line_index,
         "reason": reason.value}
        for entry in offer.excluded
        if (reason := _own_reason(entry)) is not None
    ]
