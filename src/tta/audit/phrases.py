"""Wording shared by every audit sentence: money, quantities, dates, lists, roles, what an option holds.

Plain English, no locale: the same event always gives the same sentence on every machine.

Text that comes from outside (a buyer's words, an approver's note, a name, an id or a code from a request or
from Valio Aimo's data) goes into a sentence only through `quoted`, `plain` or `label`, so it reads as data
and cannot close a quotation or start a sentence that looks like the gateway's own.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from tta.contracts.audit import Actor, ActorKind
from tta.contracts.common import (
    QUANTITY_PLACES,
    ApproverRole,
    DataSource,
    OptionKind,
    Unit,
    round_money,
)
from tta.contracts.offer import OfferOption
from tta.contracts.policy import FiredRule
from tta.contracts.request import PurchaseRequest, RequestLine

PERCENT_PLACES = 1
WHOLE = Decimal(1)
MAX_PRODUCT_IDS_IN_A_SENTENCE = 5
# The facts of the event keep the full text; a sentence shows this much of it.
MAX_QUOTED_CHARACTERS = 200
MAX_NAME_CHARACTERS = 80
CUT_MARK = "…"
# Every mark a reader could take for the end of a quotation: each becomes a single quote inside quoted text.
DOUBLE_QUOTES = '"“”„‟«»＂'
TO_SINGLE_QUOTES = str.maketrans(dict.fromkeys(DOUBLE_QUOTES, "'"))
UNICODE_CONTROL_CATEGORIES = "C"  # Cc control, Cf format (bidi overrides, zero width), Cs, Co, Cn
# What an id, a sales unit, a product type or a claim code looks like. Anything else is shown as quoted text.
CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,39}")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
UNIT_WORDS = {Unit.L: ("litre", "litres"), Unit.KG: ("kg", "kg"), Unit.UNIT: ("unit", "units")}
ROLES_WITH_ARTICLE = {
    ApproverRole.PURCHASING_MANAGER.value: "the purchasing manager",
    ApproverRole.DIETITIAN.value: "the dietitian",
    ApproverRole.FINANCE.value: "finance",
}
OPTION_KINDS = {
    OptionKind.BEST_CONFIRMED: "best confirmed",
    OptionKind.ALTERNATIVE_UNCONFIRMED: "alternative, quantity not confirmed",
    OptionKind.SUBSTITUTE: "substitute",
}
SOURCES = {
    DataSource.LIVE: "Valio Aimo's live data",
    DataSource.REPLAY: "a recorded copy of Valio Aimo's data (replay)",
}
UNKNOWN_SOURCE = "Valio Aimo's data"
RECORDED = "The order is recorded in the gateway's order book."
RECHECKED = "Price and availability were checked again and had not changed."
NOTHING_ORDERED = "Nothing was ordered."
HUMAN_AT_BUYER = "a human at the buyer"
FREE_TEXT_PRODUCT = "a product described in free text"
SENTENCE_ENDS = (".", "!", "?")


def _rounded(value: Decimal, places: int, rounding: str = ROUND_HALF_UP) -> str:
    text = f"{value.quantize(Decimal(1).scaleb(-places), rounding=rounding):,f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def number(value: Decimal) -> str:
    """1,000 · 74.9 · 0.125 — thousands separated, no trailing zeros."""
    return _rounded(value, QUANTITY_PLACES)


def money(value: Decimal) -> str:
    return f"€{round_money(value):,.2f}"


def percent(ratio: Decimal) -> str:
    """74.9% — one decimal, rounded half up. A ratio below 1 is never shown as 100%: 0.9996 reads 99.9%."""
    shown = _rounded(ratio * 100, PERCENT_PLACES)
    if ratio < WHOLE and shown == _rounded(WHOLE * 100, PERCENT_PLACES):
        shown = _rounded(ratio * 100, PERCENT_PLACES, ROUND_DOWN)
    return f"{shown}%"


def amount(value: Decimal, unit: Unit) -> str:
    singular, plural = UNIT_WORDS[unit]
    return f"{number(value)} {singular if value == 1 else plural}"


def count(value: int, singular: str, plural: str | None = None) -> str:
    return f"{value:,} {singular if value == 1 else plural or singular + 's'}"


def day(value: date) -> str:
    return f"{WEEKDAYS[value.weekday()]} {value.day} {MONTHS[value.month - 1]} {value.year}"


def moment(value: datetime) -> str:
    """Sunday 15 November 2026 at 17:00 (UTC+02:00): the clock time as stated, with its offset."""
    offset = value.strftime("%z")
    zone = f" (UTC{offset[:3]}:{offset[3:5]})" if offset else ""
    return f"{day(value.date())} at {value:%H:%M}{zone}"


def joined(items: Iterable[str]) -> str:
    """a · a and b · a, b and c."""
    parts = list(items)
    if len(parts) <= 1:
        return "".join(parts)
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def _one_line(text: str) -> str:
    """The text on one line, each control or format character replaced by a space."""
    visible = "".join(
        " " if unicodedata.category(character).startswith(UNICODE_CONTROL_CATEGORIES) else character
        for character in text
    )
    return " ".join(visible.split())


def ended(sentence: str) -> str:
    """A sentence another package wrote, on one line, with a full stop when it has no end mark."""
    text = _one_line(sentence)
    return text if text.endswith(SENTENCE_ENDS) else f"{text}."


def plain(text: str, limit: int) -> str:
    """Text from outside, fit for a sentence: one line, no control character, no double quotation mark,
    and at most `limit` characters (a longer text ends in "…")."""
    cleaned = _one_line(text.translate(TO_SINGLE_QUOTES))
    return cleaned if len(cleaned) <= limit else f"{cleaned[:limit].rstrip()}{CUT_MARK}"


def quoted(text: str) -> str:
    """Words typed by a person, inside quotation marks they cannot close: shown as data, never as our wording."""
    return f'"{plain(text, MAX_QUOTED_CHARACTERS)}"'


def label(code: str) -> str:
    """An id or a code from outside: as it is when it looks like one, otherwise as quoted text."""
    return code if CODE.fullmatch(code) else quoted(code)


def capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def role_name(role: str) -> str:
    return str(role).replace("_", " ")


def roles_text(roles: Sequence[str]) -> str:
    return joined(ROLES_WITH_ARTICLE.get(str(role), role_name(role)) for role in roles)


def person(name: str, roles: Sequence[str]) -> str:
    """Maija Virtanen (purchasing manager)."""
    shown = plain(name, MAX_NAME_CHARACTERS)
    return f"{shown} ({joined(role_name(role) for role in roles)})" if roles else shown


def actor_text(actor: Actor) -> str:
    if actor.kind is ActorKind.AGENT:
        return "The agent"
    if actor.kind is ActorKind.SYSTEM:
        return "The gateway"
    return person(actor.display_name or actor.id, (actor.role,) if actor.role else ())


def source_text(source: DataSource | None) -> str:
    return SOURCES.get(source, UNKNOWN_SOURCE)


def option_text(option: OfferOption) -> str:
    """698 ST of 463380 and 51 ST of 462775 for €1,980.77 net.

    Quantities are in sales units and prices exclude tax (AIMO/policy/LOG-FORMAT.md, rules 4 and 5).
    """
    lines = joined(
        f"{number(line.quantity)} {label(line.sales_unit)} of {label(line.product_id)}" for line in option.lines
    )
    ceiling = "at most " if option.totals.is_ceiling else ""
    deposits = ", deposits not included" if option.totals.excludes_deposits else ""
    return f"{lines} for {ceiling}{money(option.totals.net)} net{deposits}"


def coverage_text(option: OfferOption) -> str:
    if option.is_partial:
        return f"covering {percent(option.fill_ratio)} of the request"
    return "covering the full quantity"


def rule_lines(rules: Sequence[FiredRule]) -> str:
    """P-01: its sentence. P-03: its sentence. The sentences come from the policy engine's templates."""
    return " ".join(f"{rule.rule_id}: {ended(rule.sentence)}" for rule in rules)


def _wanted(line: RequestLine, with_buyer_words: bool) -> str:
    if line.product_ids:
        shown = [label(product_id) for product_id in line.product_ids[:MAX_PRODUCT_IDS_IN_A_SENTENCE]]
        more = len(line.product_ids) - len(shown)
        ids = joined([*shown, f"{more} more"] if more else shown)
        return f"{'product' if len(line.product_ids) == 1 else 'products'} {ids}"
    if line.product_type:
        return f"product type {label(line.product_type)}"
    # Name terms and the buyer's own words can name an exclusion ("without peanuts"): only the buyer reads them.
    if not with_buyer_words:
        return FREE_TEXT_PRODUCT
    if line.name_terms:
        return f"products named {quoted(' '.join(line.name_terms))}"
    return quoted(line.text)


def _request_line(line: RequestLine, with_exclusions: bool) -> str:
    text = f"{amount(line.quantity, line.unit)} of {_wanted(line, with_buyer_words=with_exclusions)}"
    if not with_exclusions:
        return text
    if line.required_claims:
        claims = joined(label(claim) for claim in line.required_claims)
        text += f" with {'claim' if len(line.required_claims) == 1 else 'claims'} {claims}"
    if line.exclude_allergens:
        strictness = f" ({line.allergen_strictness.value})" if line.allergen_strictness else ""
        text += f", excluding allergens {joined(label(code) for code in line.exclude_allergens)}{strictness}"
    return text


def request_text(request: PurchaseRequest, with_exclusions: bool) -> str:
    """What the typed request asks for. The supplier's version (`with_exclusions=False`) names product ids and
    product types only: no name term, no claim, no allergen exclusion and none of the buyer's own words."""
    text = "; ".join(_request_line(line, with_exclusions) for line in request.lines)
    if request.needed_by is not None:
        text += f", needed by {day(request.needed_by)}"
    if request.require_confirmed:
        text += ", confirmed data only"
    return text
