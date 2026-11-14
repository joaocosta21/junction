"""The sentences of a menu plan: short, plain English, each with the number and the reason."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from tta.availability.wording import format_amount
from tta.contracts.common import ExclusionReason, Unit
from tta.contracts.offer import Exclusion

if TYPE_CHECKING:
    from tta.menus.needs import Use
    from tta.menus.recipes import Choice

UNIT_WORDS: Mapping[Unit, str] = {Unit.L: "L", Unit.KG: "kg", Unit.UNIT: "sales units"}
AMOUNT_PLACES = Decimal("0.001")
REASON_WORDS: Mapping[ExclusionReason, str] = {
    ExclusionReason.BLOCKED: "blocked",
    ExclusionReason.NOT_DELIVERABLE: "not deliverable",
    ExclusionReason.OUT_OF_STOCK: "out of stock",
    ExclusionReason.CUTOFF_PASSED: "order cut-off passed",
    ExclusionReason.LATE_FOR_NEEDED_BY: "delivered too late",
    ExclusionReason.ALLERGEN_DECLARED: "declares an excluded allergen",
    ExclusionReason.ALLERGEN_NOT_STATED: "no allergen statement",
    ExclusionReason.CLAIM_CONTRADICTED: "carries a claim its allergen data contradicts",
    ExclusionReason.PORTION_PACK: "portion pack",
    ExclusionReason.NOT_A_PORTION_PACK: "not a portion pack",
    ExclusionReason.PACK_SIZE_UNKNOWN: "pack size unknown",
    ExclusionReason.PRICE_UNAVAILABLE: "no price",
    ExclusionReason.SUBSTITUTE_ADDS_ALLERGEN: "adds an allergen",
    ExclusionReason.QUANTITY_NOT_CONFIRMED: "quantity not confirmed (confirmed data only was asked for)",
    ExclusionReason.DELIVERY_DATE_NOT_CONFIRMED: "delivery date not confirmed (confirmed data only was asked for)",
    ExclusionReason.NOT_IN_RECORDING: "not in this demo's recording",
}
# The reasons that mean "it cannot be here by the date", named first in a sentence.
LATE_REASONS = (ExclusionReason.CUTOFF_PASSED, ExclusionReason.NOT_DELIVERABLE, ExclusionReason.LATE_FOR_NEEDED_BY)


def amount_words(value: Decimal, unit: Unit) -> str:
    """`24 kg`, `3.6 L`."""
    return f"{format_amount(value.quantize(AMOUNT_PLACES).normalize())} {UNIT_WORDS[unit]}"


def type_words(product_type: str) -> str:
    return product_type.replace("_", " ")


def choice_words(choice: Choice) -> str:
    """`beef chuck`, `yoghurt (natural)`."""
    terms = f" ({' '.join(choice.name_terms)})" if choice.name_terms else ""
    return f"{type_words(choice.product_type)}{terms}"


def dish_words(uses: Iterable[Use]) -> str:
    """`Beef stew (120 servings) and Berry quark dessert (80 servings)`."""
    dishes = dict.fromkeys(f"{use.recipe.name} ({use.servings:,} servings)" for use in uses)
    return joined(list(dishes))


def joined(items: Sequence[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def date_words(needed_by: date | None) -> str:
    return f"by {needed_by:%a %d %b %Y}" if needed_by is not None else "now"


def only_missing_from_recording(excluded: Sequence[Exclusion]) -> bool:
    """Every product of the line is outside the recorded data: the date has nothing to do with it (review A2a,
    finding M-5). In replay the recording holds categories 104xx and 18720 only (`recipes.yaml`, header)."""
    return bool(excluded) and all(item.reason is ExclusionReason.NOT_IN_RECORDING for item in excluded)


def exclusion_words(excluded: Sequence[Exclusion]) -> str:
    """`23 order cut-off passed, 15 not deliverable, 11 quantity not confirmed`: the late reasons first."""
    counts = Counter(exclusion.reason for exclusion in excluded)
    order = [*LATE_REASONS, *(reason for reason in ExclusionReason if reason not in LATE_REASONS)]
    return ", ".join(f"{counts[reason]:,} {REASON_WORDS[reason]}" for reason in order if counts[reason])


def found_words(choice: Choice, excluded: Sequence[Exclusion], fill: Decimal, needed_by: date | None) -> str:
    """What one offer found for one line: `quark (maitorahka): none of 49 products can be offered by ...`."""
    when = date_words(needed_by)
    if fill > 0:
        return f"{choice_words(choice)}: only {fill:.0%} of it can be offered {when}"
    if not excluded:
        return f"{choice_words(choice)}: no product of this type can be offered {when}"
    if only_missing_from_recording(excluded):
        count = len(excluded)
        products = "its one product is not" if count == 1 else f"none of its {count:,} products is"
        return (
            f"{choice_words(choice)}: {products} in this demo's recording of Valio Aimo's data, so no price or "
            "stock is known for it"
        )
    return (
        f"{choice_words(choice)}: none of {len(excluded):,} products can be offered {when} "
        f"({exclusion_words(excluded)})"
    )
