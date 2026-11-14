"""Sentences about one substitute: why it passes or fails, and what the buyer gives up (SPEC section 5)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING

from tta.availability.wording import format_amount
from tta.catalog.kinds import FLAVOURED, flavour_words, type_words, use_words
from tta.contracts.common import AllergenOutcome, AvailabilityState, ExclusionReason, Unit
from tta.contracts.product import FormulaCheck, FormulaOutcome, PackSize, ReplaceCheck, ReplaceVerdict
from tta.offers.candidates import price_problem
from tta.offers.wording import UNIT_WORDS, eur, plain_name

# The formula outcomes under which "nothing the data shows is given up" may still be said.
_NO_DIFFERENCE_SHOWN = frozenset({FormulaOutcome.SAME_PRODUCT_OTHER_PACK, FormulaOutcome.SAME_BRAND})

if TYPE_CHECKING:
    from tta.offers.substitutes import Judged, Ranking

# Reasons that come from the buyer's own rules, not from the product or the supplier (SPEC section 5): the
# offer of this buyer excludes the product for the same reason.
BUYER_RULE_REASONS = frozenset(
    {
        ExclusionReason.ALLERGEN_NOT_STATED,
        ExclusionReason.QUANTITY_NOT_CONFIRMED,
        ExclusionReason.DELIVERY_DATE_NOT_CONFIRMED,
    }
)
NOTHING_GIVEN_UP = (
    "Compared with the product asked for, nothing the data shows is given up: same category, "
    "same pack size, listed by Valio as its substitute, and not dearer."
)


LAST_RESORT = (
    "Last resort: no candidate that keeps every dietary claim of the original can be ordered, so a person "
    "decides whether this one will do."
)


# For a candidate that is another kind of product (another product type, or flavoured against plain).
LAST_RESORT_OTHER_KIND = (
    "Last resort: no candidate of the same kind as the original can be ordered, so a person decides whether "
    "this one will do."
)
# Said wherever the original is of none of our product types (14,685 of the 17,546 products, whole catalog).
NO_PRODUCT_TYPE = "the product asked for has no product type of ours, so only its category was compared"
NO_KNOWN_FLAVOUR = "names no flavour our lists know"
# For a variant of the original's product line whose name differs in a word the data does not explain.
UNEXPLAINED_VARIANT = (
    "It cannot be shown to be like for like with the product asked for, so a person decides whether this one "
    "will do."
)
_NUTRIENT_WORDS = {"saturated_fat": "saturated fat"}
# A price difference under half a cent reads "€0.00 more": it is not said.
_LEAST_SAID = Decimal("0.005")


def replace_reasons(
    check: ReplaceCheck, formula: FormulaCheck, claims_lost: Sequence[str], *, listed: bool
) -> tuple[str, ...]:
    """Each reason the candidate is not a like-for-like replacement, in plain words; empty when there is none.

    Flavours, uses and product types are words of our own lists (`tta.catalog.kinds`), never text of the
    product file.
    """
    reasons: list[str] = []
    if check.other_type:
        mine = type_words(check.types) if check.types else "of no product type we know"
        pair = "; Valio lists the pair" if listed else ""
        reasons.append(f"another product type ({mine}, not {type_words(check.original_types)}{pair})")
    if check.plain_against_flavoured:
        reasons.append(_plain_against_flavoured(check))
    elif check.other_flavour:
        reasons.append(
            f"another flavour ({flavour_words(check.flavours)}, not {flavour_words(check.original_flavours)})"
        )
    if check.other_use:
        reasons.append(_use_reason(check))
    if claims_lost:
        reasons.append(f"it does not carry the {_claims(claims_lost)}")
    if formula.outcome is FormulaOutcome.DIFFERENT:
        figures = ", ".join(
            f"{_NUTRIENT_WORDS.get(each.nutrient, each.nutrient)} {format_amount(each.other)} g, not "
            f"{format_amount(each.original)} g"
            for each in formula.differences if not each.within_tolerance
        )
        reasons.append(f"a different formula ({figures})" if figures else "another fat source")
    if check.name_difference:
        reasons.append(f"it cannot be shown to be like for like: {_name_difference(check)}")
    if check.no_shared_word:
        reasons.append(
            "it cannot be shown to be the same kind of product: its name shares no product word with the name of "
            f"the product asked for, and {NO_PRODUCT_TYPE}"
        )
    return tuple(reasons)


def _plain_against_flavoured(check: ReplaceCheck) -> str:
    """Flavoured against plain. Where the side that reads plain has a word in its name that no list explains,
    "not flavoured" is not claimed for it (review finding S11)."""
    if check.flavours:
        plain = NO_KNOWN_FLAVOUR if check.original_name_words else "is not flavoured"
        return f"{_flavoured(check.flavours)}; the product asked for {plain}"
    mine = "it names no flavour our lists know" if check.name_words else "not flavoured"
    return f"{mine}; the product asked for is {_flavoured(check.original_flavours)}"


def _quoted(words: Sequence[str]) -> str:
    """Words of a product name inside a sentence: text of the product file, entered like a name."""
    return f"“{plain_name(' '.join(words))}”"


def _name_difference(check: ReplaceCheck) -> str:
    if check.original_name_words and check.name_words:
        said = f"the names differ in {_quoted(check.original_name_words)} against {_quoted(check.name_words)}"
    elif check.name_words:
        said = f"its name adds {_quoted(check.name_words)}"
    else:
        said = f"its name lacks {_quoted(check.original_name_words)}"
    return f"{said}, which the data does not explain"


def _flavoured(flavours: Sequence[str]) -> str:
    return "flavoured" if tuple(flavours) == (FLAVOURED,) else f"flavoured with {flavour_words(tuple(flavours))}"


def _use_reason(check: ReplaceCheck) -> str:
    if check.uses and check.original_uses:
        return f"{use_words(check.uses)}; the product asked for is {use_words(check.original_uses)}"
    if check.uses:
        return f"{use_words(check.uses)}; the product asked for is not"
    return f"not {use_words(check.original_uses)}, as the product asked for is"


def replace_sentence(
    check: ReplaceCheck, verdict: ReplaceVerdict, reasons: Sequence[str], *, same_category: bool,
    formula_known: bool = True,
) -> str:
    """The answer to "can this replace the product asked for?", in one sentence."""
    if verdict is ReplaceVerdict.NOT_LIKE_FOR_LIKE:
        return f"Not a like-for-like replacement: {'; '.join(reasons)}."
    kind = "same type" if check.original_types else ("same category" if same_category else "another category")
    flavour = "same flavour" if check.flavours else "no flavour named"
    same = ", ".join((kind, "same use", flavour))
    if verdict is ReplaceVerdict.NOT_SHOWN:
        not_shown = "; ".join(
            part for part in (
                NO_PRODUCT_TYPE if check.type_not_judged else "",
                "" if formula_known else "the formula cannot be compared",
            ) if part
        )
        return f"Replaceable as far as the data shows: {same}; {not_shown}."
    return f"Replaceable: {same}, same formula within tolerance."


def why(judged: Judged) -> str:
    """Why the candidate passes or fails, and whether it can be ordered."""
    if judged.reason is ExclusionReason.SUBSTITUTE_ADDS_ALLERGEN:
        return f"{judged.rule.sentence} It can never be ordered as a substitute."
    if judged.reason in (ExclusionReason.ALLERGEN_DECLARED, ExclusionReason.CLAIM_CONTRADICTED):
        return f"{judged.reason_sentence} It cannot be ordered for this buyer."
    lacks = ""
    if judged.claims_lost:  # dietary claims only: the ones that change the rank and the verdict
        lacks = f" It does not carry the original's nutritional {_claims(judged.claims_lost)}."
    if judged.last_resort:
        lacks += f" {_last_resort_sentence(judged)}"
    if judged.reason in BUYER_RULE_REASONS:
        return f"It adds no allergen, but this buyer's rules exclude it. {judged.reason_sentence}{lacks}"
    if judged.reason is not None:
        return f"It adds no allergen, but it cannot be ordered now. {judged.reason_sentence}{lacks}"
    return f"{judged.rule.sentence} {judged.candidate.assessment.sentence}{_to_a_human(judged)}{lacks}"


def _last_resort_sentence(judged: Judged) -> str:
    if judged.claims_lost:
        return LAST_RESORT
    return LAST_RESORT_OTHER_KIND if judged.other_kind else UNEXPLAINED_VARIANT


def _to_a_human(judged: Judged) -> str:
    """The findings of the buyer's allergen rule that send the candidate to a dietitian, as the offer would."""
    check = judged.candidate.allergen_check
    if check is None:
        return ""
    sentences = [finding.sentence for finding in check.findings if finding.outcome is AllergenOutcome.TO_HUMAN]
    return "".join(f" {sentence}" for sentence in sentences)


def gives_up(judged: Judged, ranking: Ranking) -> str:
    """Whether it replaces the original like for like, then what changes for the buyer who takes it, the
    formula in numbers."""
    return f"{judged.replaceable.sentence} {_differences(judged, ranking)}"


def _differences(judged: Judged, ranking: Ranking) -> str:
    original, product = ranking.original, judged.candidate.product
    parts: list[str] = []
    if judged.claims_not_carried:  # every claim, dietary or not: all of them are given up
        parts.append(f"it does not carry the original's nutritional {_claims(judged.claims_not_carried)}")
    if original.brand and product.brand and original.brand != product.brand:
        # A brand is text of the product file like a name, and enters the sentence the same way.
        parts.append(f"the brand is {plain_name(product.brand)}, not {plain_name(original.brand)}")
    if not judged.listed:
        parts.append("Valio does not list it as a substitute")
    if judged.distance > 0:
        parts.append(f"it is from category {product.category}, not {original.category}")
    parts.extend(_pack_part(ranking.original_pack, judged.candidate.pack))
    parts.extend(_price_part(judged, ranking))
    if judged.candidate.state is AvailabilityState.QUANTITY_NOT_CONFIRMED:
        parts.append("Valio does not confirm the quantity in stock")
    # The formula sentence is built from numbers and fixed words only (`tta.offers.formula`).
    formula = judged.formula.sentence
    if parts:
        return f"Compared with {plain_name(original.display_name)}: {'; '.join(parts)}. {formula}"
    if judged.formula.outcome in _NO_DIFFERENCE_SHOWN:
        return f"{NOTHING_GIVEN_UP} {formula}"
    return f"Compared with {plain_name(original.display_name)}: {formula}"


def _claims(codes: Sequence[str]) -> str:
    return f"claim {codes[0]}" if len(codes) == 1 else f"claims {', '.join(codes)}"


def _size(pack: PackSize) -> str:
    return f"{format_amount(pack.value)} {UNIT_WORDS[pack.unit]}" if pack.value is not None and pack.unit else ""


def _comparable(original: PackSize, other: PackSize) -> bool:
    return original.is_known and other.is_known and original.unit is other.unit


def _pack_part(original: PackSize, other: PackSize) -> list[str]:
    if not _comparable(original, other):
        return ["the pack sizes cannot be compared"] if original.is_known or other.is_known else []
    if original.value == other.value:
        return []
    return [f"one sales unit holds {_size(other)}, not {_size(original)}"]


def per_measure_difference(
    ours: Decimal, original: PackSize, theirs: Decimal, other: PackSize
) -> tuple[Decimal, Unit] | None:
    """Substitute minus original, per litre or kilogram: each price divided by what one sales unit holds, so
    a case is never compared with a carton (review P2, item W7). `None` when either pack size is not known
    or the two are not in the same measure."""
    if not (_comparable(original, other) and original.value and other.value and other.unit):
        return None
    return theirs / other.value - ours / original.value, other.unit


def _price_part(judged: Judged, ranking: Ranking) -> list[str]:
    original_price, candidate = ranking.original_price, judged.candidate
    if original_price is None or original_price.catalog_price is None:
        return []
    if price_problem(candidate.price, ranking.lookup.now) is not None:
        return []
    more, per = candidate.unit_price - original_price.catalog_price.value, "sales unit"
    gap = per_measure_difference(
        original_price.catalog_price.value, ranking.original_pack, candidate.unit_price, candidate.pack
    )
    if gap is not None:
        more, per = gap[0], UNIT_WORDS[gap[1]]
    if more < _LEAST_SAID:
        return []
    return [f"it costs {eur(more)} more per {per}"]
