"""The formula measure: does one product keep the composition of another? (AIMO/build/replan/P10-formula.md 4.2)

Valio said on 14 Nov 2026 that a substitute or a cheaper item must keep the formula where the formula matters
(a cream for whipping, a butter for baking), and that the figures alone do not show it: a milk with an added
component is chemically another product even when its six figures agree. So the contents decide first and the
figures second. Two products have the same formula when all of this holds:

1. their two ingredient lists, compared component by component in one language, show no component that only
   one of them has (`tta.offers.composition`: computed from the two lists, no list of words decides);
2. fat, saturated fat, protein, carbohydrate, sugars and salt are stated for both, on the same basis;
3. each differs by no more than `RELATIVE_TOLERANCE` of the original's value or `ABSOLUTE_TOLERANCE_G`,
   whichever is larger (salt: `SALT_TOLERANCE_G`).

A component only one list has makes the outcome `DIFFERENT`, whatever the figures say. Lists that cannot be
compared (one is missing, or the two share no language) make it `NOT_KNOWN` even when the figures agree.

**The tolerances are ours, not Valio's and not law.** Energy is not compared: it follows from the other
figures and is the noisiest field. A list does not show protein type, heat treatment or the dose of a
stabiliser, so the wording is "the data shows no difference", never "identical". Missing data is `NOT_KNOWN`
and never read as the same (Valio, V5: not sure means ask).

**The one word list left, and why.** `names_vegetable_fat` no longer decides between two lists that can be
compared: there the components themselves say it. It is kept for two things the comparison cannot carry: two
lists with no language in common (an English-only list against a Finnish-only one), where the words of both
languages still show that one names a vegetable oil or fat and the other does not; and the field
`FormulaCheck.fat_source_differs`, which the policy facts and the mixed-order sentence still read.

**Per 100 g against per 100 ml (our rule, decided by the team on 14 Nov 2026).** For a drink the two are read
as they stand: a litre of milk weighs 1.03 kg, so a figure per 100 ml is about 3% above the same figure per
100 g, well inside the tolerance. A product is a drink when its file says a litre of it weighs between 0.97
and 1.06 kg, or, where the file states no weight for a volume, when its product type is one of the drink
types (`tta.catalog.kinds.drink_evidence`). For anything else grams are never read as millilitres: the
outcome stays `NOT_KNOWN`.
"""

from __future__ import annotations

import re
from decimal import Decimal

from tta.availability.wording import format_amount
from tta.catalog.kinds import drink_evidence
from tta.contracts.product import (
    FormulaCheck,
    FormulaOutcome,
    NutrientDifference,
    Nutrition,
    NutritionBasis,
    Product,
)
from tta.offers.composition import ContentsCheck, compare_contents
from tta.offers.wording import plain_name

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
# Words of an ingredient list that name a vegetable oil or fat, in English and in Finnish. Kept only for two
# lists with no language in common and for `FormulaCheck.fat_source_differs` (see the module's note). "palm"
# must start a word and be followed by a fat word or stand alone, so "retinyl palmitate" (a vitamin) is not one.
_VEGETABLE_FAT = re.compile(
    r"\bvegetable (?:oil|fat)|\brape ?seed|\bpalm(?:\b| ?oil| ?fat| ?kernel)|\bcoconut|\bshea|\bsunflower"
    r"|\bolive oil|kasviöljy|kasvirasva|\brapsi|\brypsi|palmuöljy|palmurasva|kookos|auringonkukka|oliiviöljy",
    re.IGNORECASE,
)
# A lecithin is an emulsifier, a fraction of a gram, and not a fat source: "emulsifier (rapeseed lecitin)" in a
# milk powder (465028), "sunflower lecithin" in a chocolate. Taken out before the search. Ours.
_LECITHIN = re.compile(
    r"(?:rape ?seed|sunflower|rapsi|rypsi|auringonkukka)[ -]?le[cs]it\w+"
    r"|le[cs]it\w+ \((?:from )?(?:rape ?seed|sunflower|rapsi|rypsi|auringonkukka)\w*\)?",
    re.IGNORECASE,
)
_TOLERANCE_WORDS = (
    f"our tolerance of {format_amount(RELATIVE_TOLERANCE * 100)}% or {format_amount(ABSOLUTE_TOLERANCE_G)} g per "
    f"nutrient (salt {format_amount(SALT_TOLERANCE_G)} g)"
)
_MIXED_BASIS = (
    "Figures per 100 g compared with per 100 ml as they stand: for a drink the two are about 3% apart (our rule)."
)
_CANNOT = "The formula cannot be compared:"
_NAMES_FAT = "Its ingredient list names a vegetable oil or fat; the original's does not."
_NAMES_NO_FAT = "The original's ingredient list names a vegetable oil or fat; this one's does not."
_SAME_CONTENTS = "The two ingredient lists name the same components."
_WITHIN = f"The six nutrition figures are within {_TOLERANCE_WORDS}."
COMPONENTS_SAID = 3  # of each side, in a sentence; the fields of the check carry every one


def compare_formula(original: Product, other: Product) -> FormulaCheck:
    """The formula of `other` measured against `original`'s: the outcome, the differences, and a sentence.

    The contents decide first: a component only one ingredient list has is a different formula whatever the
    figures say, and the sentence names the components before the figures."""
    contents = compare_contents(original, other)
    check = _compare(original, other, contents)
    return check.model_copy(
        update={
            "contents_compared": contents.compared,
            "only_in_original": contents.only_in_original,
            "only_in_other": contents.only_in_other,
        }
    )


def _compare(original: Product, other: Product, contents: ContentsCheck) -> FormulaCheck:
    mixed = _mixed_basis_of_two_drinks(original, other)
    unknown = _not_comparable(original.nutrition, other.nutrition, mixed)
    fat_source_differs = _fat_source_differs(original, other)
    if unknown is not None:
        if contents.differs:
            return FormulaCheck(
                outcome=FormulaOutcome.DIFFERENT, fat_source_differs=fat_source_differs,
                sentence=f"{_contents_sentence(contents)} The nutrition figures cannot be compared: {unknown}",
            )
        return FormulaCheck(outcome=FormulaOutcome.NOT_KNOWN, sentence=f"{_CANNOT} {unknown}")
    assert original.nutrition is not None and other.nutrition is not None  # noqa: S101 - narrowed just above
    basis = None if mixed else original.nutrition.basis
    per = _per(original.nutrition, other.nutrition)
    note = f" {_MIXED_BASIS}" if mixed else ""
    differences = _differences(original.nutrition, other.nutrition)
    outside = tuple(each for each in differences if not each.within_tolerance)
    # Two lists with no language in common: the words of both languages can still show another fat source.
    by_words_only = bool(fat_source_differs) and not contents.compared
    if contents.differs or outside or by_words_only:
        return FormulaCheck(
            outcome=FormulaOutcome.DIFFERENT, basis=basis, differences=differences, mixed_basis=mixed,
            fat_source_differs=fat_source_differs,
            sentence=f"{_different_sentence(outside, per, original, other, contents)}{note}",
        )
    if not contents.compared:
        return FormulaCheck(
            outcome=FormulaOutcome.NOT_KNOWN, basis=basis, differences=differences, mixed_basis=mixed,
            sentence=(
                f"{_CANNOT} the figures agree within {_TOLERANCE_WORDS}, but the ingredient lists cannot be "
                f"compared ({contents.why_not}), so the formula is not shown to be the same.{note}"
            ),
        )
    return FormulaCheck(
        outcome=_kept_outcome(original, other, differences, mixed), basis=basis, differences=differences,
        mixed_basis=mixed, fat_source_differs=False,
        sentence=f"{_kept_sentence(original, other, differences, per, mixed)} {_SAME_CONTENTS}{note}",
    )


def _contents_sentence(contents: ContentsCheck) -> str:
    """The components only one list has, in the labels' own words, then the pairs not shown to be the same."""
    unsure_ours = {mine for mine, _ in contents.not_shown_same}
    unsure_theirs = {yours for _, yours in contents.not_shown_same}
    parts = [
        f"{whose} names {_quoted(found)}, which {other} does not"
        for whose, other, found in (
            ("this product's ingredient list", "the list of the product asked for",
             [each for each in contents.only_in_other if each not in unsure_theirs]),
            ("the ingredient list of the product asked for", "this product's",
             [each for each in contents.only_in_original if each not in unsure_ours]),
        ) if found
    ]
    pairs = contents.not_shown_same[:COMPONENTS_SAID]
    parts.extend(f"{_quote(yours)} against {_quote(mine)}: not shown to be the same" for mine, yours in pairs)
    more = len(contents.not_shown_same) - len(pairs)
    if more:
        parts.append(f"{more} more such {'pair' if more == 1 else 'pairs'}")
    said = "; ".join(parts)
    return f"Different contents: {said}."


def _quote(words: str) -> str:
    """Words of a label inside a sentence: text of the product file, entered like a name (`plain_name`), with
    no quotation mark around it: no sentence of an offer carries one, so that no file text can close one."""
    return plain_name(words)


def _quoted(components: list[str]) -> str:
    """ "CREAM", "CREAM and salt", "CREAM, salt and water", "CREAM, salt, water and 2 more"."""
    said = [_quote(each) for each in components[:COMPONENTS_SAID]]
    more = len(components) - COMPONENTS_SAID
    if more > 0:
        return f"{', '.join(said)} and {more} more"
    return said[0] if len(said) == 1 else f"{', '.join(said[:-1])} and {said[-1]}"


def _mixed_basis_of_two_drinks(original: Product, other: Product) -> bool:
    """One states its figures per 100 g, the other per 100 ml, and both are drinks: compared as they stand."""
    if original.nutrition is None or other.nutrition is None or original.nutrition.basis is other.nutrition.basis:
        return False
    return drink_evidence(original) is not None and drink_evidence(other) is not None


def _per(original: Nutrition, other: Nutrition) -> str:
    """ "per 100 g", or "per 100 g against per 100 ml" (this product's against the original's) when they differ."""
    if original.basis is other.basis:
        return _BASIS_WORDS[original.basis]
    return f"{_BASIS_WORDS[other.basis]} against {_BASIS_WORDS[original.basis]}"


def names_vegetable_fat(ingredients: str) -> bool:
    """Whether an ingredient list names a vegetable oil or fat. The text is data and is only searched."""
    return _VEGETABLE_FAT.search(_LECITHIN.sub(" ", ingredients)) is not None


def _not_comparable(original: Nutrition | None, other: Nutrition | None, mixed: bool = False) -> str | None:
    """Why the figures cannot be compared, as the end of a sentence; `None` when they can."""
    for nutrition, whose in ((original, "the product asked for"), (other, "this product")):
        if nutrition is None:
            return f"{whose} has no nutrition figures per 100 g or ml."
        missing = [words for field, words in NUTRIENTS if getattr(nutrition, field) is None]
        if missing:
            return f"{whose} states no figure for {', '.join(missing)} per 100 g or ml."
    assert original is not None and other is not None  # noqa: S101 - both were checked in the loop
    if original.basis is not other.basis and not mixed:
        ours, theirs = _BASIS_WORDS[original.basis], _BASIS_WORDS[other.basis]
        # Not two drinks: grams are never read as millilitres. The figures that stand furthest apart are
        # still said as they are stated, so a person can judge.
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
    is missing, because a missing list says nothing. It decides an outcome only for two lists that share no
    language; otherwise the components compared say it."""
    if not original.key_ingredients or not other.key_ingredients:
        return None
    return names_vegetable_fat(original.key_ingredients) is not names_vegetable_fat(other.key_ingredients)


def _kept_outcome(
    original: Product, other: Product, differences: tuple[NutrientDifference, ...], mixed: bool = False
) -> FormulaOutcome:
    same_brand = bool(original.brand) and original.brand == other.brand
    if not same_brand:
        return FormulaOutcome.OTHER_BRAND  # a brand that is not stated is never read as the same brand
    # Equal figures on two bases are about 3% apart, so they are never read as the same product.
    return FormulaOutcome.SAME_BRAND if differences or mixed else FormulaOutcome.SAME_PRODUCT_OTHER_PACK


def _kept_sentence(
    original: Product, other: Product, differences: tuple[NutrientDifference, ...], per: str, mixed: bool = False
) -> str:
    if differences:
        figures = "; ".join(
            f"{_WORDS[each.nutrient]} {_grams(each.other)} against {_grams(each.original)}" for each in differences
        )
        return f"Same formula within {_TOLERANCE_WORDS}: {figures}{_per_words(per, mixed)}."
    if mixed:
        return f"Same formula within {_TOLERANCE_WORDS}: the six nutrition figures are equal as stated, {per}."
    brand = "same brand, and " if original.brand and original.brand == other.brand else ""
    return f"The data shows no difference in formula: {brand}the six nutrition figures {per} are equal."


def _per_words(per: str, mixed: bool) -> str:
    """The basis at the end of a list of figures: " per 100 g", or ", per 100 g against per 100 ml"."""
    return f", {per}" if mixed else f" {per}"


def _different_sentence(
    outside: tuple[NutrientDifference, ...], per: str, original: Product, other: Product, contents: ContentsCheck
) -> str:
    """The components first, the figures after. Where the two lists could not be compared, the fat source the
    words of both languages show."""
    if outside:
        stated = "; ".join(
            f"{_WORDS[each.nutrient]} {_grams(each.other)}, not {_grams(each.original)}" for each in outside
        )
        figures = f"{stated}{_per_words(per, ' against ' in per)}."
    else:
        figures = ""
    if contents.differs:
        after = f"Figures outside our tolerance: {figures}" if figures else _WITHIN
        return f"{_contents_sentence(contents)} {after}"
    fat_source = ""
    if not contents.compared and _fat_source_differs(original, other):
        fat_source = f" {_NAMES_FAT if names_vegetable_fat(other.key_ingredients or '') else _NAMES_NO_FAT}"
    if not outside:
        return f"Different formula: the six nutrition figures are within {_TOLERANCE_WORDS}.{fat_source}"
    same = f" {_SAME_CONTENTS}" if contents.compared else ""
    return f"Different formula: {figures}{fat_source}{same}"


def _grams(value: Decimal) -> str:
    return f"{format_amount(value)} g"
