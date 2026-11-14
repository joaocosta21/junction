"""Plain-English fragments shared by the sentences of an offer. No locale: the same text on every machine."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from tta.availability.wording import format_amount
from tta.contracts.common import ExclusionReason, Unit, round_money

EURO_SIGN = "€"
UNIT_WORDS = {Unit.L: "L", Unit.KG: "kg", Unit.UNIT: "sales units"}
MAX_IDS_IN_A_NOTE = 10
_TENTH_OF_A_PERCENT = Decimal("0.1")


def eur(value: Decimal) -> str:
    """`€2,580.64`."""
    return f"{EURO_SIGN}{round_money(value):,.2f}"


def measured(value: Decimal, unit: Unit) -> str:
    """`1,000 L`, `30 kg`, `24 sales units`."""
    return f"{format_amount(value)} {UNIT_WORDS[unit]}"


def percent(ratio: Decimal) -> str:
    """`74.9%`."""
    return f"{(ratio * 100).quantize(_TENTH_OF_A_PERCENT, rounding=ROUND_HALF_UP)}%"


def counted(count: int, noun: str) -> str:
    """`1 product`, `3 products`."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def reason_words(reason: ExclusionReason) -> str:
    """`cutoff passed` for `CUTOFF_PASSED`."""
    return reason.value.replace("_", " ").lower()


def listed(ids: Sequence[str]) -> str:
    """Up to ten ids, and how many more there are."""
    shown = ", ".join(ids[:MAX_IDS_IN_A_NOTE])
    more = len(ids) - MAX_IDS_IN_A_NOTE
    return f"{shown} and {more} more" if more > 0 else shown


def line_label(index: int) -> str:
    """`Request line 1` for index 0."""
    return f"Request line {index + 1}"
