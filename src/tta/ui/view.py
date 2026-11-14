"""How values are written on a page: money, quantities, times, and a word for every code.

Scores on the 20% "how decisions are logged and auditable" and on the 30% demo: a judge reads the page from
two metres, so a state is a word with a mark, never a colour alone, and never a raw code.
Nothing here decides anything: it only writes what the gateway answered.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from tta.contracts.agent import AgentRun
from tta.contracts.common import (
    ApproverRole,
    AvailabilityState,
    CheckResult,
    ClaimName,
    ClaimStatus,
    ConstraintKind,
    ExclusionReason,
    OptionKind,
    OrderStatus,
    PlacedBy,
    Preference,
    Unit,
    Verdict,
)
from tta.contracts.offer import Exclusion, SubstituteCandidate

NOT_STATED = "not stated"
NO_END_DATE = "no end date"
# Valio writes a price with no end as 31 Dec 9999 (AIMO/docs/API.md, price validity).
NO_END_YEAR = 9999
CENTS = Decimal("0.01")
HUNDRED = Decimal(100)
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# How a run of the buyer agent was served (task FIX-10, finding 12). The agent package labels a run written by
# hand "hand-built" and one replayed from a model's recording "recorded" (`tta.agent.recorded`).
HAND_BUILT_MODEL = "hand-built"
RULE_BASED_MODEL = "rule-based"  # a run read and made by fixed rules (task FALLBACK-1)
RUN_BY_RULES_FOR_GEMINI = "Gemini did not answer, so this run was read and made by fixed rules, not by a model."
RUN_BY_RULES_WITHOUT_KEY = "No Gemini key is set, so this run was read and made by fixed rules, not by a model."
RECORDED_MODEL = "recorded"
BY_HAND = "answers written by hand, not by a model"
FROM_A_RECORDING = "a recording of the model's earlier answers"
FROM_A_RECORDING_OF = "a recording of {model}'s earlier answers"
RUN_FROM = "Run from {what}: no live model call."
RUN_FALLBACK = "Gemini did not answer, so this run was served from {what}."
RUN_LIVE = "Run live by {model}."
CAN_BE_ORDERED = "Can be ordered"
NEEDS_APPROVAL = "Can be ordered, needs approval"  # its quantity is not confirmed: a human decides (rule F-01)
CANNOT_BE_ORDERED = "Cannot be ordered"

OK, WARN, BAD, PLAIN = "ok", "warn", "bad", "plain"
GLYPHS = {OK: "✓", WARN: "?", BAD: "✕", PLAIN: "•"}

# Words and tones are kept per kind of code: a `StrEnum` member equals its string, so `CONFIRMED` of a claim
# and `CONFIRMED` of availability would be one key in a table shared by every kind.
WORDS: dict[type[Enum], dict[str, str]] = {
    ClaimName: {
        "price": "Price", "quantity": "Quantity", "delivery_date": "Delivery date", "allergens": "Allergens",
        "origin": "Origin",
    },
    ClaimStatus: {"CONFIRMED": "confirmed", "UNKNOWN": "not confirmed", "RULED_OUT": "ruled out"},
    CheckResult: {"MET": "met", "NOT_MET": "not met", "UNVERIFIED": "not verified"},
    ConstraintKind: {
        "PRODUCT_TYPE": "Product type", "PRODUCT_ID": "Product asked for", "NAME_TERM": "Name",
        "QUANTITY": "Quantity", "NEEDED_BY": "Needed by", "CLAIM": "Claim", "LABEL": "Certificate label",
        "ALLERGEN": "Allergen", "PACK": "Pack", "CONFIRMED_ONLY": "Confirmed data only",
    },
    Verdict: {
        "AUTO": "The agent may order alone", "APPROVAL": "A human must approve",
        "BLOCK": "Cannot be ordered, even with approval",
    },
    OrderStatus: {
        "PENDING_APPROVAL": "Waiting for approval", "ORDERED": "Ordered", "REJECTED": "Rejected", "EXPIRED": "Expired",
    },
    PlacedBy: {"AGENT": "by the agent", "HUMAN_APPROVAL": "with human approval"},
    ApproverRole: {"purchasing_manager": "purchasing manager", "dietitian": "dietitian", "finance": "finance"},
    OptionKind: {
        "BEST_CONFIRMED": "Confirmed stock", "ALTERNATIVE_UNCONFIRMED": "Quantity not confirmed",
        "SUBSTITUTE": "Substitute", "CHEAPEST_CONFIRMED": "Cheapest confirmed",
    },
    AvailabilityState: {
        "BLOCKED": "Blocked by Valio Aimo", "NOT_DELIVERABLE": "Not deliverable", "OUT_OF_STOCK": "Out of stock",
        "CUTOFF_PASSED": "Cut-off passed", "QUANTITY_NOT_CONFIRMED": "Quantity not confirmed",
        "CONFIRMED": "Confirmed in stock",
    },
    ExclusionReason: {
        "BLOCKED": "Blocked by Valio Aimo", "NOT_DELIVERABLE": "Not deliverable", "OUT_OF_STOCK": "Out of stock",
        "CUTOFF_PASSED": "Cut-off passed", "LATE_FOR_NEEDED_BY": "Too late for the needed-by date",
        "ALLERGEN_DECLARED": "Declares an excluded allergen", "ALLERGEN_NOT_STATED": "Allergen not stated",
        "PORTION_PACK": "Portion pack", "NOT_A_PORTION_PACK": "Not a portion pack",
        "NOT_IN_RECORDING": "Not in the recorded copy",
        "PACK_SIZE_UNKNOWN": "Pack size unknown", "PRICE_UNAVAILABLE": "No price",
        "SUBSTITUTE_ADDS_ALLERGEN": "Substitute adds an allergen", "QUANTITY_NOT_CONFIRMED": "Quantity not confirmed",
        "DELIVERY_DATE_NOT_CONFIRMED": "Delivery date not confirmed",
    },
    Unit: {"L": "litres", "KG": "kilograms", "UNIT": "sales units"},
    Preference: {
        "PRICE": "price", "EARLIEST": "earliest delivery, then price",
        "RELIABILITY": "delivery reliability, then price", "LOWER_CARBON": "lowest carbon footprint, then price",
    },
}

_TONES: dict[type[Enum], dict[str, str]] = {
    ClaimStatus: {"CONFIRMED": OK, "UNKNOWN": WARN, "RULED_OUT": BAD},
    CheckResult: {"MET": OK, "UNVERIFIED": WARN, "NOT_MET": BAD},
    Verdict: {"AUTO": OK, "APPROVAL": WARN, "BLOCK": BAD},
    OrderStatus: {"ORDERED": OK, "PENDING_APPROVAL": WARN, "REJECTED": BAD, "EXPIRED": BAD},
    OptionKind: {"BEST_CONFIRMED": OK, "ALTERNATIVE_UNCONFIRMED": WARN, "SUBSTITUTE": WARN, "CHEAPEST_CONFIRMED": OK},
    AvailabilityState: {"CONFIRMED": OK, "QUANTITY_NOT_CONFIRMED": WARN},
}


def plain(code: str) -> str:
    """A code nobody wrote words for, made readable: `SOMETHING_NEW` becomes "Something new"."""
    return code.replace("_", " ").replace("-", " ").strip().capitalize()


def words(code: Enum | str | None) -> str:
    """The words for a code of the contracts. A code added later still reads as words, not as a code."""
    if code is None:
        return NOT_STATED
    if isinstance(code, Enum):
        return WORDS.get(type(code), {}).get(str(code.value)) or plain(str(code.value))
    return plain(code)


def tone(code: Enum | str | None) -> str:
    """`ok`, `warn`, `bad` or `plain`: picks the mark's glyph and colour. The word is always written too."""
    if not isinstance(code, Enum):
        return PLAIN
    return _TONES.get(type(code), {}).get(str(code.value), PLAIN)


def _grouped(value: Decimal, places: int) -> str:
    return f"{value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP):,.{places}f}"


def money(value: Decimal | None) -> str:
    """Euros with two decimals, rounded half up like every total of the gateway."""
    return NOT_STATED if value is None else f"€{_grouped(value, 2)}"


def unit_price(value: Decimal | None) -> str:
    """A price per sales unit: two decimals, or as many as Valio states when it states more (four at most)."""
    if value is None:
        return NOT_STATED
    places = 2 if value == value.quantize(CENTS) else 4
    return f"€{_grouped(value, places)}"


def quantity(value: Decimal | None) -> str:
    """A quantity with thousands separators and no trailing zeros."""
    if value is None:
        return NOT_STATED
    written = f"{value:,.3f}".rstrip("0").rstrip(".")
    return written or "0"


def percent(ratio: Decimal | None) -> str:
    if ratio is None:
        return NOT_STATED
    return f"{quantity((ratio * HUNDRED).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))}%"


def day(value: date | None) -> str:
    if value is None:
        return NOT_STATED
    return f"{WEEKDAYS[value.weekday()]} {value.day} {MONTHS[value.month - 1]} {value.year}"


def _offset(value: datetime) -> str:
    offset = value.utcoffset()
    if offset is None:
        return "no time zone stated"
    if offset == timedelta(0):
        return "UTC"
    sign = "-" if offset < timedelta(0) else "+"
    minutes = abs(int(offset.total_seconds())) // 60
    return f"UTC{sign}{minutes // 60:02d}:{minutes % 60:02d}"


def moment(value: datetime | None) -> str:
    """A time in the offset it was stated in (Valio states Helsinki time), with its weekday."""
    if value is None:
        return NOT_STATED
    return f"{day(value.date())} at {value:%H:%M} ({_offset(value)})"


def clock_time(value: datetime | None) -> str:
    """A short time stamp for the audit timeline."""
    if value is None:
        return NOT_STATED
    return f"{value.day} {MONTHS[value.month - 1]} {value:%H:%M:%S} {_offset(value)}"


def valid_to(value: datetime | None) -> str:
    if value is None:
        return NOT_STATED
    return NO_END_DATE if value.year >= NO_END_YEAR else moment(value)


def spread_by_reason(excluded: tuple[Exclusion, ...]) -> tuple[Exclusion, ...]:
    """The same exclusions, ordered so that the first ones shown cover every reason.

    One product per reason first (in the order the reasons first appear), then the rest in the gateway's
    order. A page that shows five rows before "show the others" then shows every reason, not five times one.
    """
    first_of_reason: dict[ExclusionReason, Exclusion] = {}
    for entry in excluded:
        first_of_reason.setdefault(entry.reason, entry)
    leading = tuple(first_of_reason.values())
    shown = {id(entry) for entry in leading}
    return leading + tuple(entry for entry in excluded if id(entry) not in shown)


def reason_counts(excluded: tuple[Exclusion, ...]) -> tuple[tuple[ExclusionReason, int], ...]:
    """How many products each reason excluded, the most frequent first."""
    return tuple(Counter(entry.reason for entry in excluded).most_common())


def run_label(run: AgentRun, live_model: bool) -> str:
    """What served a run of the buyer agent, in a sentence: a live model, a recording or answers written by
    hand, and whether the recording stood in for Gemini (`live_model`: a Gemini key is set)."""
    if run.model == RULE_BASED_MODEL:
        return RUN_BY_RULES_FOR_GEMINI if live_model else RUN_BY_RULES_WITHOUT_KEY
    if not run.recorded:
        return RUN_LIVE.format(model=run.model)
    if run.model == HAND_BUILT_MODEL:
        what = BY_HAND
    else:
        what = FROM_A_RECORDING if run.model == RECORDED_MODEL else FROM_A_RECORDING_OF.format(model=run.model)
    return RUN_FALLBACK.format(what=what) if live_model else RUN_FROM.format(what=what)


def can_be_ordered(candidate: SubstituteCandidate) -> tuple[str, str]:
    """The tone and words of a substitute's "can it be ordered" mark. One whose quantity is not confirmed can
    be ordered only with a human's approval, as every such line can."""
    if not candidate.orderable:
        reason = f": {words(candidate.reason)}" if candidate.reason else ""
        return BAD, CANNOT_BE_ORDERED + reason
    state = candidate.availability.state if candidate.availability else None
    if state is AvailabilityState.QUANTITY_NOT_CONFIRMED:
        return WARN, NEEDS_APPROVAL
    return OK, CAN_BE_ORDERED
