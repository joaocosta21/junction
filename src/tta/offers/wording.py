"""Plain-English fragments shared by the sentences of an offer. No locale: the same text on every machine."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from tta.availability.wording import format_amount
from tta.contracts.common import ExclusionReason, Unit, round_money

EURO_SIGN = "€"
UNIT_WORDS = {Unit.L: "L", Unit.KG: "kg", Unit.UNIT: "sales units"}
MAX_IDS_IN_A_NOTE = 10
MAX_NAME_LENGTH = 120  # of a product name inside a sentence
CUT_MARK = "…"
# Every mark a reader could take for the end of a quotation, ASCII and typographic.
DOUBLE_QUOTES = '"\u201c\u201d\u201e\u201f\u00ab\u00bb\uff02'
APOSTROPHE = "'"
# Unicode categories Cc (control: line breaks, tabs) and Cf (format: bidirectional overrides, zero width),
# and the rest of the "other" group (surrogates, private use, unassigned).
_NOT_SHOWN = "C"
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


def plain_name(name: str) -> str:
    """A name from the product file as it may stand in a sentence: data, never a statement.

    The product file is untrusted input, and a sentence of an offer is read by people, by the audit trail
    and by a language model. A double quotation mark becomes an apostrophe, so a name cannot close a
    quotation; a control or format character becomes a space, so a name stays on one line and hides
    nothing; a name longer than `MAX_NAME_LENGTH` is cut and ends in "…". The policy applies the same
    rule to the names in its rule sentences (`tta.policy.text.plain_name`).
    """
    shown = "".join(_plain_character(character) for character in name)
    one_line = " ".join(shown.split())
    if len(one_line) <= MAX_NAME_LENGTH:
        return one_line
    return one_line[: MAX_NAME_LENGTH - len(CUT_MARK)].rstrip() + CUT_MARK


def _plain_character(character: str) -> str:
    if character in DOUBLE_QUOTES:
        return APOSTROPHE
    return " " if unicodedata.category(character).startswith(_NOT_SHOWN) else character


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
