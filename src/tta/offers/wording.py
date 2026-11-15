"""Plain-English fragments shared by the sentences of an offer. No locale: the same text on every machine."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from decimal import Decimal

from tta.availability.wording import format_amount
from tta.contracts.common import ExclusionReason, Unit, round_money
from tta.contracts.request import RequestLine

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


def eur(value: Decimal) -> str:
    """`€2,580.64`."""
    return f"{EURO_SIGN}{round_money(value):,.2f}"


def measured(value: Decimal, unit: Unit) -> str:
    """`1,000 L`, `30 kg`, `24 sales units`."""
    return f"{format_amount(value)} {UNIT_WORDS[unit]}"


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
    """`Request line 1` for index 0: how a note of the offer says which line it is about (programs read the
    number there). A sentence of an option's summary names the line by its own words instead (`line_names`)."""
    return f"Request line {index + 1}"


def line_names(asked: Sequence[RequestLine]) -> tuple[str, ...]:
    """Each request line by its own words: its product type or the words of its name; a line that names only
    product ids is `the products named on line 5`, never the list of ids. Two lines with the same words also
    say their line."""
    words = [line_words(line) if line.product_type or line.name_terms else "" for line in asked]
    names = []
    for index, (line, own) in enumerate(zip(asked, words, strict=True)):
        number = index + 1
        if not own:
            named = "the product" if len(set(line.product_ids)) == 1 else "the products"
            names.append(f"{named} named on line {number}")
        elif words.count(own) > 1:
            names.append(f"{own} (line {number})")
        else:
            names.append(own)
    return tuple(names)


def for_line(name: str) -> str:
    """`For milk`: what stands before a sentence about one line of a request of several lines, where a person
    reads it (an option's summary)."""
    return f"For {name}"


def joined(items: Sequence[str]) -> str:
    """`a`, `a and b`, `a, b and c`."""
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def line_words(line: RequestLine) -> str:
    """What a request line asked for: its product type, else its name terms, else the products it named.

    The policy names a line the same way from the subjects of its constraint checks (`tta.policy.coverage`),
    so the option summary and rule P-03 read alike.
    """
    if line.product_type:
        return line.product_type.replace("_", " ")
    terms = tuple(plain_name(term) for term in dict.fromkeys(line.name_terms))
    if terms:
        return f"{APOSTROPHE}{' '.join(terms)}{APOSTROPHE}"
    ids = tuple(dict.fromkeys(line.product_ids))
    if not ids:
        return ""
    return f"product {ids[0]}" if len(ids) == 1 else f"products {joined(ids)}"
