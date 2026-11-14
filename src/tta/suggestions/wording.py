"""Numbers and words shared by the suggestions' sentences. Plain English, with the number and the reason."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from tta.contracts.common import QUANTITY_PLACES, Unit, round_money

UNIT_WORDS = {Unit.L: "L", Unit.KG: "kg", Unit.UNIT: "units"}
MEASURE_WORDS = {Unit.L: "litre", Unit.KG: "kg"}
SYNTHETIC_TAIL = "From a synthetic order history."
CONFIRM_IT = "Confirm it before it is ordered."
CONFIRM_THE_QUANTITY = "Confirm the quantity before it is ordered."
_QUANTUM = Decimal(1).scaleb(-QUANTITY_PLACES)
_PERCENT = Decimal(100)


def middle(values: Sequence[Decimal]) -> Decimal:
    """The median, rounded half up to the three decimals a request line takes."""
    return Decimal(median(values)).quantize(_QUANTUM, rounding=ROUND_HALF_UP)


def number(value: Decimal) -> str:
    """100, 1.5, 1,000: no trailing zeros, no exponent."""
    return f"{value.normalize():,f}"


def amount(value: Decimal, unit: Unit) -> str:
    """"10 L", "9 kg", "1 unit"."""
    word = "unit" if unit is Unit.UNIT and value == 1 else UNIT_WORDS[unit]
    return f"{number(value)} {word}"


def euros(value: Decimal) -> str:
    return f"€{round_money(abs(value)):,.2f}"


def percent(ratio: Decimal) -> str:
    """+20%, -17%."""
    whole = (ratio * _PERCENT).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return f"{'+' if whole > 0 else ''}{whole}%"


def day(value: date) -> str:
    """Monday 16 November."""
    return f"{value:%A} {value.day} {value:%B}"


def type_words(product_type: str) -> str:
    """plant_drink: "plant drink"."""
    return product_type.replace("_", " ")


def sentence(*parts: str) -> str:
    """The parts that say something, one space apart."""
    return " ".join(part for part in parts if part)


def tail(synthetic: bool) -> str:
    return SYNTHETIC_TAIL if synthetic else ""
