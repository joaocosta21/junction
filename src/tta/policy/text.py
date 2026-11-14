"""Plain-text formatting shared by the facts and the sentences. No policy logic lives here."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from tta.contracts.common import round_money

PERCENT = Decimal(100)
PERCENT_STEP = Decimal("0.1")  # a ratio prints with at most one decimal: 74.9%


def format_number(value: Decimal) -> str:
    """1000 -> "1,000", 12.50 -> "12.5"."""
    return format(value.normalize(), ",f")


def format_money(value: Decimal) -> str:
    """Always two decimals: 1980.77 -> "1,980.77", 428 -> "428.00"."""
    return format(round_money(value), ",.2f")


def format_limit(value: Decimal) -> str:
    """A limit prints as it is set: 750 -> "750", 750.5 -> "750.50"."""
    rounded = round_money(value)
    return format(rounded, ",.0f") if rounded == rounded.to_integral_value() else format(rounded, ",.2f")


def format_ratio(value: Decimal) -> str:
    """0.749 -> "74.9%", 0.9 -> "90%", 1 -> "100%". Rounded down, never up: 0.9996 -> "99.9%".

    A share that falls short of a minimum must not print as that minimum, and a ratio below 1 must not
    print as 100%.
    """
    percent = (value * PERCENT).quantize(PERCENT_STEP, rounding=ROUND_DOWN)
    return f"{format_number(percent)}%"


def format_datetime(value: datetime) -> str:
    """ISO 8601 to the minute, with its offset: "2026-11-15 17:00+02:00"."""
    return value.isoformat(sep=" ", timespec="minutes")


def join_words(items: Sequence[str]) -> str:
    """["a"] -> "a", ["a", "b"] -> "a and b", ["a", "b", "c"] -> "a, b and c"."""
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def as_sentence(clause: str) -> str:
    """A clause becomes a sentence: first letter upper case, a full stop at the end."""
    stripped = clause.strip()
    if not stripped:
        return stripped
    ending = "" if stripped.endswith((".", "!", "?")) else "."
    return stripped[0].upper() + stripped[1:] + ending


def unique(items: Sequence[str]) -> tuple[str, ...]:
    """The items in their first-seen order, each once."""
    return tuple(dict.fromkeys(items))
