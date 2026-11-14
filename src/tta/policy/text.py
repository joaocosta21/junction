"""Plain-text formatting shared by the facts and the sentences. No policy logic lives here."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from tta.contracts.common import round_money

PERCENT = Decimal(100)
PERCENT_STEP = Decimal("0.1")  # a ratio prints with at most one decimal: 74.9%
NAME_MAX_CHARACTERS = 120  # of a product name inside a rule sentence
CUT_MARK = "…"
# Every mark a reader could take for the end of a quotation: each becomes an apostrophe.
DOUBLE_QUOTES = '"“”„‟«»＂'
_TO_APOSTROPHE = str.maketrans(dict.fromkeys(DOUBLE_QUOTES, "'"))
_NOT_SHOWN = "C"  # Unicode categories Cc (control) and Cf (format: bidirectional overrides, zero width), Cs, Co, Cn


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


def plain_name(name: str) -> str:
    """A name from the supplier's product file as it may stand in a rule sentence: data, never a statement.

    A double quotation mark, ASCII or typographic, becomes an apostrophe, so a name cannot close a quotation.
    A control or format character (a line break, a bidirectional override, a zero-width character) becomes a
    space, so a name stays on one line and hides nothing. At most `NAME_MAX_CHARACTERS` characters; a longer
    name ends in "…". The audit trail quotes rule sentences as written, so this is done where a name is read.
    """
    shown = "".join(
        " " if unicodedata.category(character).startswith(_NOT_SHOWN) else character
        for character in name.translate(_TO_APOSTROPHE)
    )
    one_line = " ".join(shown.split())
    if len(one_line) <= NAME_MAX_CHARACTERS:
        return one_line
    return one_line[: NAME_MAX_CHARACTERS - len(CUT_MARK)].rstrip() + CUT_MARK


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
