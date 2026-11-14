"""The formula measure: does one product keep the composition of another? (AIMO/build/replan/P10-formula.md 4.2)

Valio said on 14 Nov 2026 that a substitute or a cheaper item must keep the formula where the formula matters
(a cream for whipping, a butter for baking). The product file can judge it: six nutrients per 100 g or ml and
an ingredient text. Two products have the same formula when all of this holds:

1. fat, saturated fat, protein, carbohydrate, sugars and salt are stated for both, on the same basis;
2. each differs by no more than `RELATIVE_TOLERANCE` of the original's value or `ABSOLUTE_TOLERANCE_G`,
   whichever is larger (salt: `SALT_TOLERANCE_G`);
3. the two ingredient lists agree on the fat source: both name a vegetable oil or fat, or neither does.

**The tolerances and the word list are ours, not Valio's and not law.** Energy is not compared: it follows
from the other figures and is the noisiest field. The panel does not show protein type, heat treatment or
stabiliser dose, so the wording is "the data shows no difference", never "identical". Missing data is
`NOT_KNOWN` and never read as the same (Valio, V5: not sure means ask).
"""

from __future__ import annotations

import re
from decimal import Decimal

from tta.availability.wording import format_amount
from tta.contracts.product import (
    FormulaCheck,
    FormulaOutcome,
    NutrientDifference,
    Nutrition,
    NutritionBasis,
    Product,
)

# Ours. 15% keeps whipping creams of 35, 36 and 38% fat together and separates 38 from 30 and from 15.
RELATIVE_TOLERANCE = Decimal("0.15")
# Ours. The floor stays under the 1.5 g of fat between skimmed, semi-skimmed and whole milk.
ABSOLUTE_TOLERANCE_G = Decimal("1.0")
# Ours. Separates unsalted butter (0.02 g) from salted (0.8 g and more), not creams at 0.07 and 0.19 g.
SALT_TOLERANCE_G = Decimal("0.25")

# (field of `Nutrition`, words for a sentence), in the order of a nutrition panel.
NUTRIENTS = (
    ("fat", "fat"),
    ("saturated_fat", "saturated fat"),
    ("protein", "protein"),
    ("carbohydrate", "carbohydrate"),
    ("sugars", "sugars"),
    ("salt", "salt"),
)
_WORDS = dict(NUTRIENTS)
_BASIS_WORDS = {NutritionBasis.G: "per 100 g", NutritionBasis.ML: "per 100 ml"}
# Words of an ingredient list that name a vegetable oil or fat, in English and in Finnish: the ingredient text
# is English on most products and Finnish only on others (`tta.catalog.loader`, INGREDIENT_LANGUAGES). "palm"
# must start a word and be followed by a fat word or stand alone, so "retinyl palmitate" (a vitamin) is not one.
_VEGETABLE_FAT = re.compile(
    r"\bvegetable (?:oil|fat)|\brape ?seed|\bpalm(?:\b| ?oil| ?fat| ?kernel)|\bcoconut|\bshea|\bsunflower"
    r"|\bolive oil|kasviöljy|kasvirasva|\brapsi|\brypsi|palmuöljy|palmurasva|kookos|auringonkukka|oliiviöljy",
    re.IGNORECASE,
)
_TOLERANCE_WORDS = (
    f"our tolerance of {format_amount(RELATIVE_TOLERANCE * 100)}% or {format_amount(ABSOLUTE_TOLERANCE_G)} g per "
    f"nutrient (salt {format_amount(SALT_TOLERANCE_G)} g)"
)
_CANNOT = "The formula cannot be compared:"
_NAMES_FAT = "Its ingredient list names a vegetable oil or fat; the original's does not."
_NAMES_NO_FAT = "The original's ingredient list names a vegetable oil or fat; this one's does not."


def compare_formula(original: Product, other: Product) -> FormulaCheck:
    """The formula of `other` measured against `original`'s: the outcome, the differences, and a sentence."""
    unknown = _not_comparable(original.nutrition, other.nutrition)
    if unknown is not None:
        return FormulaCheck(outcome=FormulaOutcome.NOT_KNOWN, sentence=f"{_CANNOT} {unknown}")
    assert original.nutrition is not None and other.nutrition is not None  # noqa: S101 - narrowed just above
    basis = original.nutrition.basis
    differences = _differences(original.nutrition, other.nutrition)
    outside = tuple(each for each in differences if not each.within_tolerance)
    fat_source_differs = _fat_source_differs(original, other)
    if outside or fat_source_differs:
        return FormulaCheck(
            outcome=FormulaOutcome.DIFFERENT, basis=basis, differences=differences,
            fat_source_differs=fat_source_differs, sentence=_different_sentence(outside, basis, original, other),
        )
    if fat_source_differs is None:
        whose = "this product's" if not other.key_ingredients else "the original's"
        return FormulaCheck(
            outcome=FormulaOutcome.NOT_KNOWN, basis=basis, differences=differences,
            sentence=f"{_CANNOT} the nutrition figures agree, but {whose} ingredient list is missing.",
        )
    return FormulaCheck(
        outcome=_kept_outcome(original, other, differences), basis=basis, differences=differences,
        fat_source_differs=False, sentence=_kept_sentence(original, other, differences, basis),
    )


def names_vegetable_fat(ingredients: str) -> bool:
    """Whether an ingredient list names a vegetable oil or fat. The text is data and is only searched."""
    return _VEGETABLE_FAT.search(ingredients) is not None


def _not_comparable(original: Nutrition | None, other: Nutrition | None) -> str | None:
    """Why the figures cannot be compared, as the end of a sentence; `None` when they can."""
    for nutrition, whose in ((original, "the product asked for"), (other, "this product")):
        if nutrition is None:
            return f"{whose} has no nutrition figures per 100 g or ml."
        missing = [words for field, words in NUTRIENTS if getattr(nutrition, field) is None]
        if missing:
            return f"{whose} states no figure for {', '.join(missing)} per 100 g or ml."
    assert original is not None and other is not None  # noqa: S101 - both were checked in the loop
    if original.basis is not other.basis:
        ours, theirs = _BASIS_WORDS[original.basis], _BASIS_WORDS[other.basis]
        # Grams are never converted to millilitres: the density is not in the data. The figures that stand
        # furthest apart are still said as they are stated, so a person can judge.
        apart = [each for each in _differences(original, other) if not each.within_tolerance]
        stated = "; ".join(
            f"{_WORDS[each.nutrient]} {_grams(each.other)} {theirs}, not {_grams(each.original)} {ours}"
            for each in apart
        )
        return (
            f"the figures of the product asked for are {ours} and this product's are {theirs}."
            f"{f' As stated: {stated}.' if stated else ''}"
        )
    return None


def _differences(original: Nutrition, other: Nutrition) -> tuple[NutrientDifference, ...]:
    """Every nutrient whose two figures are not equal, each marked as inside or outside the tolerance."""
    found = []
    for field, _ in NUTRIENTS:
        ours, theirs = getattr(original, field), getattr(other, field)
        if ours == theirs:
            continue
        floor = SALT_TOLERANCE_G if field == "salt" else ABSOLUTE_TOLERANCE_G
        allowed = max(ours * RELATIVE_TOLERANCE, floor)
        within = abs(theirs - ours) <= allowed
        found.append(NutrientDifference(nutrient=field, original=ours, other=theirs, within_tolerance=within))
    return tuple(found)


def _fat_source_differs(original: Product, other: Product) -> bool | None:
    """True when one ingredient list names a vegetable oil or fat and the other does not; `None` when a list
    is missing, because a missing list says nothing."""
    if not original.key_ingredients or not other.key_ingredients:
        return None
    return names_vegetable_fat(original.key_ingredients) is not names_vegetable_fat(other.key_ingredients)


def _kept_outcome(original: Product, other: Product, differences: tuple[NutrientDifference, ...]) -> FormulaOutcome:
    same_brand = bool(original.brand) and original.brand == other.brand
    if not same_brand:
        return FormulaOutcome.OTHER_BRAND  # a brand that is not stated is never read as the same brand
    return FormulaOutcome.SAME_BRAND if differences else FormulaOutcome.SAME_PRODUCT_OTHER_PACK


def _kept_sentence(
    original: Product, other: Product, differences: tuple[NutrientDifference, ...], basis: NutritionBasis
) -> str:
    if differences:
        figures = "; ".join(
            f"{_WORDS[each.nutrient]} {_grams(each.other)} against {_grams(each.original)}" for each in differences
        )
        return f"Same formula within {_TOLERANCE_WORDS}: {figures} {_BASIS_WORDS[basis]}."
    brand = "same brand, and " if original.brand and original.brand == other.brand else ""
    return f"The data shows no difference in formula: {brand}the six nutrition figures {_BASIS_WORDS[basis]} are equal."


def _different_sentence(
    outside: tuple[NutrientDifference, ...], basis: NutritionBasis, original: Product, other: Product
) -> str:
    fat_source = ""
    if _fat_source_differs(original, other):
        fat_source = f" {_NAMES_FAT if names_vegetable_fat(other.key_ingredients or '') else _NAMES_NO_FAT}"
    if not outside:
        return f"Different formula: the six nutrition figures are within {_TOLERANCE_WORDS}.{fat_source}"
    figures = "; ".join(
        f"{_WORDS[each.nutrient]} {_grams(each.other)}, not {_grams(each.original)}" for each in outside
    )
    return f"Different formula: {figures} {_BASIS_WORDS[basis]}.{fat_source}"


def _grams(value: Decimal) -> str:
    return f"{format_amount(value)} g"
