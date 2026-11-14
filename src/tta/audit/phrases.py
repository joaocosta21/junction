"""Wording shared by every audit sentence: money, quantities, dates, lists, roles, what an option holds.

Plain English, no locale: the same event always gives the same sentence on every machine.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

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
MAX_PRODUCT_IDS_IN_A_SENTENCE = 5
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


def _rounded(value: Decimal, places: int) -> str:
    text = f"{value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP):,f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def number(value: Decimal) -> str:
    """1,000 · 74.9 · 0.125 — thousands separated, no trailing zeros."""
    return _rounded(value, QUANTITY_PLACES)


def money(value: Decimal) -> str:
    return f"€{round_money(value):,.2f}"


def percent(ratio: Decimal) -> str:
    return f"{_rounded(ratio * 100, PERCENT_PLACES)}%"


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


def ended(sentence: str) -> str:
    """The sentence with a full stop when it has no end mark."""
    text = " ".join(sentence.split())
    return text if text.endswith(SENTENCE_ENDS) else f"{text}."


def quoted(text: str) -> str:
    """Words typed by a person, on one line and inside quotation marks: shown as data, never as our wording."""
    return f'"{" ".join(text.split())}"'


def capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def role_name(role: str) -> str:
    return str(role).replace("_", " ")


def roles_text(roles: Sequence[str]) -> str:
    return joined(ROLES_WITH_ARTICLE.get(str(role), role_name(role)) for role in roles)


def person(name: str, roles: Sequence[str]) -> str:
    """Maija Virtanen (purchasing manager)."""
    return f"{name} ({joined(role_name(role) for role in roles)})" if roles else name


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
    lines = joined(f"{number(line.quantity)} {line.sales_unit} of {line.product_id}" for line in option.lines)
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
        shown = line.product_ids[:MAX_PRODUCT_IDS_IN_A_SENTENCE]
        more = len(line.product_ids) - len(shown)
        ids = joined([*shown, f"{more} more"] if more else shown)
        return f"{'product' if len(line.product_ids) == 1 else 'products'} {ids}"
    if line.product_type:
        return f"product type {line.product_type}"
    if line.name_terms:
        return f"products named {quoted(' '.join(line.name_terms))}"
    # The buyer's own words can name an allergen exclusion, so only the buyer reads them back.
    return quoted(line.text) if with_buyer_words else FREE_TEXT_PRODUCT


def _request_line(line: RequestLine, with_exclusions: bool) -> str:
    text = f"{amount(line.quantity, line.unit)} of {_wanted(line, with_buyer_words=with_exclusions)}"
    if line.required_claims:
        text += f" with {'claim' if len(line.required_claims) == 1 else 'claims'} {joined(line.required_claims)}"
    if with_exclusions and line.exclude_allergens:
        strictness = f" ({line.allergen_strictness.value})" if line.allergen_strictness else ""
        text += f", excluding allergens {joined(line.exclude_allergens)}{strictness}"
    return text


def request_text(request: PurchaseRequest, with_exclusions: bool) -> str:
    """What the typed request asks for. The supplier's version leaves the allergen exclusions out."""
    text = "; ".join(_request_line(line, with_exclusions) for line in request.lines)
    if request.needed_by is not None:
        text += f", needed by {day(request.needed_by)}"
    if request.require_confirmed:
        text += ", confirmed data only"
    return text
