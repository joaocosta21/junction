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

from tta.allergens.codes import ALLERGEN_CODES
from tta.contracts.audit import Actor, ActorKind
from tta.contracts.common import (
    QUANTITY_PLACES,
    AllergenStrictness,
    ApproverRole,
    AvailabilityState,
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
# What a claim or label code of Valio Aimo's product file looks like (FREE_FROM_LACTOSE, EU_ORGANIC_FARMING).
# The supplier reads a required claim or label only in this form: anything else may be the buyer's own words.
LIST_CODE = re.compile(r"[A-Z0-9][A-Z0-9_]{0,39}")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
UNIT_WORDS = {Unit.L: ("litre", "litres"), Unit.KG: ("kg", "kg"), Unit.UNIT: ("unit", "units")}
# Valio Aimo's sales-unit codes in the words of its own webshop ("384 pcs", "1 crt = 20 pcs":
# AIMO/build/replan/P3-webshop.md). A code that is not listed is shown as it is.
SALES_UNIT_WORDS = {"ST": "pcs", "KPL": "pcs", "KI": "crt", "KG": "kg", "L": "L"}
ROLES_WITH_ARTICLE = {
    ApproverRole.PURCHASING_MANAGER.value: "the purchasing manager",
    ApproverRole.DIETITIAN.value: "the dietitian",
    ApproverRole.FINANCE.value: "finance",
}
OPTION_KINDS = {
    OptionKind.BEST_CONFIRMED: "best confirmed",
    OptionKind.ALTERNATIVE_UNCONFIRMED: "alternative",
    OptionKind.CHEAPEST_CONFIRMED: "cheapest confirmed",
    OptionKind.SUBSTITUTE: "substitute",
}
# The kind ALTERNATIVE_UNCONFIRMED holds two alternatives: one whose quantity is not confirmed and one whose
# data does not rule out an excluded allergen, with a confirmed quantity. The offer says which in the title
# (`tta.offers.options`: "Alternative: allergen not ruled out (partial fill)"); a test checks the two texts agree.
ALTERNATIVE_TITLE = "Alternative: "
PARTIAL_TITLE_SUFFIX = " (partial fill)"  # the sentence states the coverage itself
QUANTITY_NOT_CONFIRMED = "quantity not confirmed"
MAX_TITLE_CHARACTERS = 80
SOURCES = {
    DataSource.LIVE: "Valio Aimo's live data",
    DataSource.REPLAY: "a recorded copy of Valio Aimo's data",
}
UNKNOWN_SOURCE = "Valio Aimo's data"
RECORDED = "The order is recorded in the gateway's order book."
RECHECKED = "Price and availability were checked again and had not changed."
NOTHING_ORDERED = "Nothing was ordered."
HUMAN_AT_BUYER = "a human at the buyer"
FREE_TEXT_PRODUCT = "a product described in free text"
# `totals.is_ceiling` keeps its name in the contract; what it means is "an estimate" (P9b-booth-answers.md, Q16).
BY_WEIGHT = "an estimate: sold by weight, Valio Aimo invoices the weight delivered"
SENTENCE_ENDS = (".", "!", "?")
# The two allergen rules in the words of the shop page ("Strict", "Declared only"): a person reads no code.
ALLERGEN_RULE_WORDS = {AllergenStrictness.STRICT: "strict", AllergenStrictness.DECLARED_ONLY: "declared only"}


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


def allergen_name(code: str) -> str:
    """milk for AM, cereals containing gluten for AW: the name a person reads, from the table of allergen codes
    (`tta.allergens.codes`). A code the table does not hold is shown as it is, as data."""
    entry = ALLERGEN_CODES.get(code)
    return entry.label if entry is not None else label(code)


def allergen_names(codes: Iterable[str]) -> str:
    """milk and cereals containing gluten."""
    return joined(allergen_name(code) for code in codes)


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


def sales_unit(code: str) -> str:
    """pcs for ST, kg for KG, L for L: the webshop's word for a sales-unit code, else the code as data."""
    return SALES_UNIT_WORDS.get(code) or label(code)


def option_kind_text(option: OfferOption, for_buyer: bool) -> str:
    """best confirmed · alternative, allergen not ruled out · alternative, quantity not confirmed.

    An alternative is phrased from its title, which says what is not confirmed about it; with no such title,
    from its lines. The supplier is never told that an allergen is in doubt: next to the products of the
    option and its own allergen data, that would point to what the buyer excludes.
    """
    kind = OPTION_KINDS[option.kind]
    if option.kind is not OptionKind.ALTERNATIVE_UNCONFIRMED:
        return kind
    quantity_open = any(line.availability.state is not AvailabilityState.CONFIRMED for line in option.lines)
    stated = option.title.removesuffix(PARTIAL_TITLE_SUFFIX)
    if for_buyer and stated.startswith(ALTERNATIVE_TITLE) and stated != ALTERNATIVE_TITLE:
        return f"{kind}, {plain(stated.removeprefix(ALTERNATIVE_TITLE), MAX_TITLE_CHARACTERS)}"
    return f"{kind}, {QUANTITY_NOT_CONFIRMED}" if quantity_open else kind


def option_text(option: OfferOption) -> str:
    """698 pcs of 463380 and 51 pcs of 462775 for €1,980.77 net.

    A total that holds a product sold by weight is an estimate, and the sentence says why: Valio Aimo invoices
    the weight delivered, which can be below or above the weight ordered (Valio's answer of 14 Nov, Q16).

    Quantities are in sales units and prices exclude tax (AIMO/policy/LOG-FORMAT.md, rules 4 and 5).
    """
    lines = joined(
        f"{number(line.quantity)} {sales_unit(line.sales_unit)} of {label(line.product_id)}" for line in option.lines
    )
    estimate = "about " if option.totals.is_ceiling else ""
    weight = f" ({BY_WEIGHT})" if option.totals.is_ceiling else ""
    deposits = ", deposits not included" if option.totals.excludes_deposits else ""
    return f"{lines} for {estimate}{money(option.totals.net)} net{weight}{deposits}"


def coverage_text(option: OfferOption) -> str:
    """covering the full quantity · covering 74.9% of the request · covering 4 of the 7 items asked for in full.
    An option of several request lines (a menu) has no one share to state: its fill ratio is that of its least
    covered line, so an order with one line missing read "covering 0% of the request"."""
    if not option.is_partial:
        return "covering the full quantity"
    if len(option.coverage) > 1:
        # The count and the words of rule P-03's own sentence (`tta.policy.coverage.coverage_said`).
        in_full = sum(1 for part in option.coverage if part.fill_ratio >= WHOLE)
        return f"covering {in_full} of the {len(option.coverage)} items asked for in full"
    return f"covering {percent(option.fill_ratio)} of the request"


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


def code_shaped(codes: Sequence[str]) -> tuple[str, ...]:
    """The claims or labels that are codes of Valio Aimo's lists; the rest may be the buyer's own words."""
    return tuple(code for code in codes if LIST_CODE.fullmatch(code))


def _required(codes: Sequence[str], with_buyer_words: bool, lead: str, singular: str, plural: str) -> str:
    """ " with claim FREE_FROM_LACTOSE"; for the supplier, what is not a code is counted and not shown."""
    shown = list(codes) if with_buyer_words else list(code_shaped(codes))
    hidden = len(codes) - len(shown)
    text = f" {lead} {singular if len(shown) == 1 else plural} {joined(label(code) for code in shown)}" if shown else ""
    if hidden:
        requirement = count(hidden, "more requirement is", "more requirements are")
        text += f" ({requirement} in the buyer's own words and {'is' if hidden == 1 else 'are'} not shown)"
    return text


def _request_line(line: RequestLine, with_exclusions: bool) -> str:
    text = f"{amount(line.quantity, line.unit)} of {_wanted(line, with_buyer_words=with_exclusions)}"
    text += _required(line.required_claims, with_exclusions, "with", "claim", "claims")
    text += _required(line.required_labels, with_exclusions, "carrying", "label", "labels")
    if with_exclusions and line.exclude_allergens:
        # Names and words, never codes: "excluding allergens milk and cereals containing gluten (strict rule)".
        rule = f" ({ALLERGEN_RULE_WORDS[line.allergen_strictness]} rule)" if line.allergen_strictness else ""
        text += f", excluding allergens {allergen_names(line.exclude_allergens)}{rule}"
    return text


def request_text(request: PurchaseRequest, with_exclusions: bool) -> str:
    """What the typed request asks for. The supplier's version (`with_exclusions=False`) names product ids,
    product types and the claim and label codes asked for: no name term, no allergen exclusion and none of the
    buyer's own words."""
    text = "; ".join(_request_line(line, with_exclusions) for line in request.lines)
    if request.needed_by is not None:
        text += f", needed by {day(request.needed_by)}"
    if request.require_confirmed:
        text += ", confirmed data only"
    return text
