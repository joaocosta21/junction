"""The decision as Valio Aimo reads it (package S4): every rule that fired with its reason and outcome, the
logic, and the products considered and left out.

Nothing here quotes a rule's own sentence or reads its facts: both can hold a limit amount or an allergen code.
A rule is named by its id and its title, which is fixed text of `tta/policy/rules.yaml` and holds no value.
What is masked is said in the sentence (`tta.audit.readers.MASKED_BY_RULE`).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from tta.audit.phrases import HUMAN_AT_BUYER, count, joined, label, plain, role_name
from tta.audit.readers import MASKED_BY_RULE, RULES_ABOUT_AN_EXCLUDED_ALLERGEN, supplier_rule_ids
from tta.contracts.common import ExclusionReason, JsonDict, Verdict
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
ALLERGEN_REASONS = (ExclusionReason.ALLERGEN_DECLARED, ExclusionReason.ALLERGEN_NOT_STATED)
PRODUCTS_NOT_SHOWN = "which allergen and which products are not shown"
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
    ExclusionReason.ALLERGEN_DECLARED: "declaring an allergen the buyer excludes",
    ExclusionReason.ALLERGEN_NOT_STATED: "stating nothing about an allergen the buyer excludes",
    ExclusionReason.CLAIM_CONTRADICTED: "carrying a claim their own allergen data contradicts",
}


def buyers_roles(roles: Iterable[str]) -> str:
    """the buyer's purchasing manager · the buyer's purchasing manager and dietitian · a human at the buyer."""
    names = [role_name(role) for role in dict.fromkeys(str(role) for role in roles)]
    return f"the buyer's {joined(names)}" if names else HUMAN_AT_BUYER


def _listed(product_ids: Sequence[str], limit: int) -> str:
    shown = [label(product_id) for product_id in product_ids[:limit]]
    more = len(product_ids) - len(shown)
    return joined([*shown, f"{more} more"] if more else shown)


def _outcome(rule: FiredRule) -> str:
    if rule.verdict is Verdict.BLOCK:
        return BLOCKS
    if rule.verdict is Verdict.APPROVAL:
        return f"approval by {buyers_roles((rule.approver_role,) if rule.approver_role else ())}"
    return NO_APPROVAL


def _shows_product(rule: FiredRule) -> bool:
    return rule.product_id is not None and rule.rule_id not in RULES_ABOUT_AN_EXCLUDED_ALLERGEN


def _grouped(rules: Sequence[FiredRule]) -> list[tuple[FiredRule, list[str]]]:
    """One entry per rule and outcome, with the products it fired on: a rule about a line fires once per line."""
    groups: dict[tuple[str, Verdict, str | None], tuple[FiredRule, list[str]]] = {}
    for rule in rules:
        _, products = groups.setdefault((rule.rule_id, rule.verdict, rule.approver_role), (rule, []))
        if _shows_product(rule) and rule.product_id not in products:
            products.append(rule.product_id)
    return list(groups.values())


def _rule_line(rule: FiredRule, products: Sequence[str]) -> str:
    """P-01, a rule the buyer set (the order is above the spend limit per order; the amount is not shown):
    approval by the buyer's purchasing manager."""
    title = plain(rule.title, MAX_TITLE_CHARACTERS).rstrip(".")
    masked = MASKED_BY_RULE.get(rule.rule_id)
    reason = f"{title[:1].lower()}{title[1:]}{f'; {masked}' if masked else ''}"
    on = ""
    if products:
        on = f", on {'product' if len(products) == 1 else 'products'} {_listed(products, MAX_PRODUCTS_PER_RULE)}"
    return f"{label(rule.rule_id)}, {FIXED_RULE if rule.fixed else BUYER_RULE} ({reason}){on}: {_outcome(rule)}."


def rules_applied(rules: Sequence[FiredRule]) -> str:
    """ " Rules that applied: F-01, a fixed rule (…), on product 464306: approval by …. P-01, …." or nothing."""
    groups = _grouped(rules)
    if not groups:
        return ""
    lines = " ".join(_rule_line(rule, products) for rule, products in groups)
    return f" {'Rule' if len(groups) == 1 else 'Rules'} that applied: {lines}"


def decision_explained(decision: PolicyDecision) -> str:
    """Every rule that fired and how the outcome follows from them; "No rule applied." when none fired."""
    if not decision.fired:
        return NO_RULE_APPLIED
    return f"{rules_applied(decision.fired)}{LOGIC}"


def decision_facts(decision: PolicyDecision) -> JsonDict:
    """The decision without a rule's sentence or facts, and without the product of a rule about an allergen."""
    return {
        "verdict": decision.verdict.value,
        "rule_ids": list(supplier_rule_ids(decision.rule_ids)),
        "rules": [
            {
                "rule_id": rule.rule_id, "title": rule.title, "fixed": rule.fixed, "verdict": rule.verdict.value,
                "approver_role": rule.approver_role.value if rule.approver_role else None,
                "product_id": rule.product_id if _shows_product(rule) else None,
            }
            for rule in decision.fired
        ],
        "required_roles": [role.value for role in decision.required_roles],
        "evaluated_at": decision.evaluated_at,
    }


def _by_reason(excluded: Sequence[Exclusion]) -> dict[ExclusionReason, list[str]]:
    """Reasons about Valio Aimo's own data first, in the order of the code list; the two allergen reasons last."""
    ordered = [reason for reason in ExclusionReason if reason not in ALLERGEN_REASONS] + list(ALLERGEN_REASONS)
    found = {reason: [entry.product_id for entry in excluded if entry.reason is reason] for reason in ordered}
    return {reason: product_ids for reason, product_ids in found.items() if product_ids}


def left_out(offer: Offer) -> str:
    """ " 41 products were considered and left out: 12 past the closing time for ordering (471690, …); …" """
    if not offer.excluded:
        return ""
    parts = []
    for reason, product_ids in _by_reason(offer.excluded).items():
        shown = PRODUCTS_NOT_SHOWN if reason in ALLERGEN_REASONS else _listed(product_ids, MAX_PRODUCTS_PER_REASON)
        parts.append(f"{len(product_ids):,} {REASON_WORDS[reason]} ({shown})")
    total = len(offer.excluded)
    products = count(total, "product was", "products were")
    return f" {products} considered and left out: {'; '.join(parts)}."


def left_out_facts(offer: Offer) -> list[JsonDict]:
    """Each product left out for a reason about Valio Aimo's own data. None left out for an allergen."""
    return [
        {"product_id": entry.product_id, "name": entry.name, "request_line_index": entry.request_line_index,
         "reason": entry.reason.value}
        for entry in offer.excluded
        if entry.reason not in ALLERGEN_REASONS
    ]
