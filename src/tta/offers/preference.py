"""What ranks confirmed products once every constraint is met: price, or the buyer's preference (task SUST-1).

The keys are earliest `availableDate`, highest delivery reliability and lowest carbon footprint per kg. A product
with no value for the key ranks after every product with one: a missing value is unknown, never good or bad
(AIMO/FINDINGS.md section 6). Reliability is known for 4,425 products and carbon for 11,033 of 17,546; carbon
is close to category-level, so `LOWER_CARBON` mostly separates products of different categories.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal

from tta.contracts.common import Preference
from tta.contracts.offer import OfferLine
from tta.offers.candidates import Candidate
from tta.offers.wording import counted

PRICE_TIER = 0
TITLE_SUFFIXES: Mapping[Preference, str] = {
    Preference.EARLIEST: ", ranked by earliest delivery",
    Preference.RELIABILITY: ", ranked by delivery reliability",
    Preference.LOWER_CARBON: ", ranked by lowest carbon footprint",
}
KEY_WORDS: Mapping[Preference, str] = {
    Preference.PRICE: "price",
    Preference.EARLIEST: "earliest delivery date",
    Preference.RELIABILITY: "delivery reliability",
    Preference.LOWER_CARBON: "carbon footprint",
}
# What Valio Aimo's data lacks for a line, as the sentence of an option names it.
MISSING_WORDS: Mapping[Preference, str] = {
    Preference.EARLIEST: "delivery date",
    Preference.RELIABILITY: "delivery reliability",
    Preference.LOWER_CARBON: "carbon footprint",
}

Value = Decimal | date


def candidate_value(candidate: Candidate, prefer: Preference) -> Value | None:
    """The candidate's value for the key, lower is better; `None` when the data has none (or under price)."""
    if prefer is Preference.EARLIEST:
        return candidate.assessment.available_date
    if prefer is Preference.RELIABILITY:
        reliability = candidate.product.delivery_reliability
        return None if reliability is None else -reliability
    if prefer is Preference.LOWER_CARBON:
        return candidate.product.carbon_kg_co2e_per_kg
    return None


def line_value(line: OfferLine, prefer: Preference) -> Value | None:
    """The same value as the line carries it."""
    if prefer is Preference.EARLIEST:
        return line.availability.available_date
    if prefer is Preference.RELIABILITY:
        return None if line.delivery_reliability is None else -line.delivery_reliability
    if prefer is Preference.LOWER_CARBON:
        return line.carbon_kg_co2e_per_kg
    return None


def tiers(candidates: Iterable[Candidate], prefer: Preference) -> dict[str, int]:
    """Product id to tier: 0 for the best value, one more per worse value, the last for no value.

    Under price every product has tier 0, so the fill is the price fill of SPEC section 5.
    """
    listed = tuple(candidates)
    if prefer is Preference.PRICE:
        return dict.fromkeys((each.product.id for each in listed), PRICE_TIER)
    values = {each.product.id: candidate_value(each, prefer) for each in listed}
    ranked: list[Value] = sorted({value for value in values.values() if value is not None})  # type: ignore[type-var]
    position = {value: index for index, value in enumerate(ranked)}
    return {
        product_id: len(ranked) if value is None else position[value] for product_id, value in values.items()
    }


def title_suffix(prefer: Preference) -> str:
    return TITLE_SUFFIXES.get(prefer, "")


def missing_sentence(lines: Sequence[OfferLine], prefer: Preference) -> str:
    """` No delivery reliability in Valio Aimo's data for 1 of the 3 lines; …`, or nothing when every line has
    a value or the key is price."""
    if prefer is Preference.PRICE:
        return ""
    missing = sum(line_value(line, prefer) is None for line in lines)
    if not missing:
        return ""
    what = MISSING_WORDS[prefer]
    if len(lines) == 1:
        return f" No {what} in Valio Aimo's data for this product; it ranks after every product that has one."
    those = "it ranks" if missing == 1 else "they rank"
    return (
        f" No {what} in Valio Aimo's data for {missing} of the {counted(len(lines), 'line')}; {those} after every "
        f"product that has one."
    )
