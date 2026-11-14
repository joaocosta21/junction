"""Why a suggestion was dropped, in a few words for a list or a log line ("its data does not rule out tree nuts (AN)").

The guard keeps the full sentence of each check in `DroppedSuggestion.sentence`; the summary is the reason the
buyer's audit sentence and a page show beside the product's name. Lower case, no full stop.
"""

from __future__ import annotations

from tta.allergens.codes import describe
from tta.contracts.allergen import AllergenCheck
from tta.contracts.common import AllergenOutcome, ExclusionReason

# The offer's own checks, as a suggestion meets them. "Closing time" is the word of Valio's own webshop
# (AIMO/build/replan/P3-webshop.md, the mapping table).
EXCLUSION_SUMMARIES = {
    ExclusionReason.BLOCKED: "it is blocked for ordering in Valio Aimo's data",
    ExclusionReason.NOT_DELIVERABLE: "it cannot be delivered",
    ExclusionReason.OUT_OF_STOCK: "it is out of stock",
    ExclusionReason.CUTOFF_PASSED: "its closing time for ordering has passed",
    ExclusionReason.LATE_FOR_NEEDED_BY: "it can be delivered only after the date needed",
    ExclusionReason.PORTION_PACK: "it is sold in portion packs, which the request does not ask for",
    ExclusionReason.NOT_A_PORTION_PACK: "it is not sold in portion packs, which the request asks for",
    ExclusionReason.PACK_SIZE_UNKNOWN: "its pack size is not in Valio Aimo's data",
    ExclusionReason.PRICE_UNAVAILABLE: "it has no price",
    ExclusionReason.SUBSTITUTE_ADDS_ALLERGEN: "it would add an allergen the product it replaces does not declare",
    ExclusionReason.QUANTITY_NOT_CONFIRMED: "its quantity is not confirmed",
    ExclusionReason.DELIVERY_DATE_NOT_CONFIRMED: "its delivery date is not confirmed",
    ExclusionReason.NOT_IN_RECORDING: "the recorded copy of Valio Aimo's data holds no answer for it",
}
UNKNOWN_PRODUCT = "it is not in the catalog"
ALREADY_ORDERED = "it is already in an order placed or waiting for the same delivery date"
STOCK_NOT_CONFIRMED = "its stock is not confirmed for the date"
FORMULA_NOT_KEPT = "it does not keep the formula of {product_id}"
ADDS_ALLERGEN = "it would add an allergen to {product_id}"
CLAIM_NOT_CARRIED = "it does not carry {claims}"
CLAIM_LOST = "it does not carry {claims}, which {product_id} carries"
ALLERGEN_NOT_RULED_OUT = "its data does not rule out {allergens}"
ALLERGEN_DECLARED = "it declares {allergens}"
ALLERGEN_DOUBT = "its data leaves an allergen you exclude open"
# The offer's own check gives ALLERGEN_DECLARED, with no finding, to a claim the line requires that the product's
# own allergen statements contradict (review P4, item F4, `tta.offers.candidates._claim_contradicted`).
CLAIM_CONTRADICTED = "its own allergen data contradicts a claim the request requires"


def exclusion_summary(reason: ExclusionReason, allergen_check: AllergenCheck | None) -> str:
    """The offer's own reason for leaving the product out, in a few words."""
    if reason in (ExclusionReason.ALLERGEN_DECLARED, ExclusionReason.ALLERGEN_NOT_STATED):
        if _open(allergen_check):
            return allergen_summary(allergen_check)
        return CLAIM_CONTRADICTED if reason is ExclusionReason.ALLERGEN_DECLARED else ALLERGEN_DOUBT
    if reason is ExclusionReason.CLAIM_CONTRADICTED:
        return CLAIM_CONTRADICTED
    return EXCLUSION_SUMMARIES.get(reason, f"it does not pass the check {reason.value}")


def _open(allergen_check: AllergenCheck | None) -> bool:
    return allergen_check is not None and any(
        finding.outcome is not AllergenOutcome.PASS for finding in allergen_check.findings
    )


def allergen_summary(allergen_check: AllergenCheck | None) -> str:
    """ "it declares milk (AM)" when the data declares an excluded allergen, else "its data does not rule out tree
    nuts (AN), peanuts (AP) and sesame seeds (AS)": the allergens the buyer excludes, in the buyer's own view."""
    if allergen_check is None:
        return ALLERGEN_DOUBT
    open_ = [finding for finding in allergen_check.findings if finding.outcome is not AllergenOutcome.PASS]
    declared = [finding.excluded_code for finding in open_ if finding.outcome is AllergenOutcome.REJECT]
    if declared:
        return ALLERGEN_DECLARED.format(allergens=_allergens(declared))
    if not open_:
        return ALLERGEN_DOUBT
    return ALLERGEN_NOT_RULED_OUT.format(allergens=_allergens([finding.excluded_code for finding in open_]))


def _allergens(codes: list[str]) -> str:
    named = [describe(code) for code in dict.fromkeys(codes)]
    return named[0] if len(named) == 1 else f"{', '.join(named[:-1])} and {named[-1]}"
