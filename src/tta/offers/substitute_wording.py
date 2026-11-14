"""Sentences about one substitute: why it passes or fails, and what the buyer gives up (SPEC section 5)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from tta.availability.wording import format_amount
from tta.contracts.common import AvailabilityState, ExclusionReason
from tta.contracts.product import PackSize
from tta.offers.candidates import price_problem
from tta.offers.wording import UNIT_WORDS, eur

if TYPE_CHECKING:
    from tta.offers.substitutes import Judged, Ranking

NOTHING_GIVEN_UP = (
    "Compared with the product asked for, nothing the data shows is given up: same category, "
    "same pack size, listed by Valio as its substitute, and not dearer."
)


def why(judged: Judged) -> str:
    """Why the candidate passes or fails, and whether it can be ordered."""
    if judged.reason is ExclusionReason.SUBSTITUTE_ADDS_ALLERGEN:
        return f"{judged.rule.sentence} It can never be ordered as a substitute."
    if judged.reason is ExclusionReason.ALLERGEN_DECLARED:
        return f"{judged.reason_sentence} It cannot be ordered for this buyer."
    lacks = ""
    if judged.claims_lost:
        lacks = f" It does not carry the original's nutritional {_claims(judged.claims_lost)}."
    if judged.reason is not None:
        return f"It adds no allergen, but it cannot be ordered now. {judged.reason_sentence}{lacks}"
    return f"{judged.rule.sentence} {judged.candidate.assessment.sentence}{lacks}"


def gives_up(judged: Judged, ranking: Ranking) -> str:
    """One sentence on what changes for the buyer who takes this product in place of the original."""
    original, product = ranking.original, judged.candidate.product
    parts: list[str] = []
    if judged.claims_lost:
        parts.append(f"it does not carry the original's nutritional {_claims(judged.claims_lost)}")
    if original.brand and product.brand and original.brand != product.brand:
        parts.append(f"the brand is {product.brand}, not {original.brand}")
    if not judged.listed:
        parts.append("Valio does not list it as a substitute")
    if judged.distance > 0:
        parts.append(f"it is from category {product.category}, not {original.category}")
    parts.extend(_pack_part(ranking.original_pack, judged.candidate.pack))
    parts.extend(_price_part(judged, ranking))
    if judged.candidate.state is AvailabilityState.QUANTITY_NOT_CONFIRMED:
        parts.append("Valio does not confirm the quantity in stock")
    if not parts:
        return NOTHING_GIVEN_UP
    return f"Compared with {original.display_name}: {'; '.join(parts)}."


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


def _price_part(judged: Judged, ranking: Ranking) -> list[str]:
    original_price, candidate = ranking.original_price, judged.candidate
    if original_price is None or original_price.catalog_price is None:
        return []
    if price_problem(candidate.price, ranking.lookup.now) is not None:
        return []
    ours, theirs = original_price.catalog_price.value, candidate.unit_price
    per = "sales unit"
    original_pack, pack = ranking.original_pack, candidate.pack
    if _comparable(original_pack, pack) and original_pack.value and pack.value and pack.unit:
        ours, theirs, per = ours / original_pack.value, theirs / pack.value, UNIT_WORDS[pack.unit]
    if theirs <= ours:
        return []
    return [f"it costs {eur(theirs - ours)} more per {per}"]
