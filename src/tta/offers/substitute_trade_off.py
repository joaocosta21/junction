"""What the buyer gives up with one substitute, each fact once (review finding C3-F9).

Before, the sentence said the formula twice (in full as a reason of the verdict, then as the formula sentence)
and the dietary claims twice (as a reason, then among all the claims). Now: the verdict with its reasons, the
formula named there in three words; then what a cook decides on, price first, then pack, the other claims, brand
and what Valio says of it; then the formula sentence, once, with the contents and the figures.
The formula sentence is `tta.offers.formula`'s own and stands whole, because the shop page looks for it in this
text before it adds it (`ui/static/shop/js/views/parts.js`).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING

from tta.availability.wording import format_amount
from tta.contracts.common import AvailabilityState
from tta.contracts.product import FormulaOutcome, PackSize, ReplaceVerdict
from tta.offers.candidates import price_problem
from tta.offers.substitute_wording import NOTHING_GIVEN_UP, per_measure_difference
from tta.offers.wording import UNIT_WORDS, eur, plain_name

if TYPE_CHECKING:
    from tta.offers.substitutes import Judged, Ranking

# How `tta.offers.substitute_wording.replace_reasons` starts the reason that spells the formula out. The
# verdict here names it in three words and the formula sentence says the rest. A test builds the reasons and
# fails when this no longer matches them.
FORMULA_REASON_PREFIX = "a different formula ("
FORMULA_IN_SHORT = "a different formula"
NOT_LIKE_FOR_LIKE = "Not a like-for-like replacement"
# The formula outcomes under which "nothing the data shows is given up" may still be said.
_NO_DIFFERENCE_SHOWN = frozenset({FormulaOutcome.SAME_PRODUCT_OTHER_PACK, FormulaOutcome.SAME_BRAND})
_LEAST_SAID = Decimal("0.005")  # a price difference under half a cent reads "€0.00 more": it is not said


def gives_up(judged: Judged, ranking: Ranking) -> str:
    """Whether it replaces the original like for like, then what changes for the buyer who takes it."""
    original = plain_name(ranking.original.display_name)
    formula = judged.formula.sentence
    parts = _parts(judged, ranking)
    if parts:
        return f"{_verdict(judged)} Compared with {original}: {'; '.join(parts)}. {formula}"
    if judged.formula.outcome in _NO_DIFFERENCE_SHOWN:
        return f"{_verdict(judged)} {NOTHING_GIVEN_UP} {formula}"
    return f"{_verdict(judged)} Compared with {original}: {formula}"


def _verdict(judged: Judged) -> str:
    """The verdict sentence. For a candidate that is not like for like, each reason as the check words it,
    but the formula in short: the formula sentence, further on, says the contents and the figures."""
    check = judged.replaceable
    if check.verdict is not ReplaceVerdict.NOT_LIKE_FOR_LIKE or not check.reasons:
        return check.sentence
    reasons = [FORMULA_IN_SHORT if reason.startswith(FORMULA_REASON_PREFIX) else reason for reason in check.reasons]
    return f"{NOT_LIKE_FOR_LIKE}: {'; '.join(reasons)}."


def _parts(judged: Judged, ranking: Ranking) -> list[str]:
    original, product = ranking.original, judged.candidate.product
    parts = [*_price_part(judged, ranking), *_pack_part(ranking.original_pack, judged.candidate.pack)]
    # The dietary claims it lacks are a reason of the verdict; the other claims it lacks are given up too.
    others = [claim for claim in judged.claims_not_carried if claim not in judged.claims_lost]
    if others:
        parts.append(f"it does not carry the {_claims(others)}")
    if original.brand and product.brand and original.brand != product.brand:
        # A brand is text of the product file like a name, and enters the sentence the same way.
        parts.append(f"the brand is {plain_name(product.brand)}, not {plain_name(original.brand)}")
    if not judged.listed:
        parts.append("Valio does not list it as a substitute")
    if judged.distance > 0:
        parts.append(f"it is from category {product.category}, not {original.category}")
    if judged.candidate.state is AvailabilityState.QUANTITY_NOT_CONFIRMED:
        parts.append("Valio does not confirm the quantity in stock")
    return parts


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
    ours = original_price.catalog_price.value
    more, per = candidate.unit_price - ours, "sales unit"
    gap = per_measure_difference(ours, ranking.original_pack, candidate.unit_price, candidate.pack)
    if gap is not None:
        more, per = gap[0], UNIT_WORDS[gap[1]]
    if more < _LEAST_SAID:
        return []
    return [f"it costs {eur(more)} more per {per}"]
