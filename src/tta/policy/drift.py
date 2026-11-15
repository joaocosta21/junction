"""How far a renewal of a standing order drifts from its history (rule P-08, task STAND-1).

Valio Aimo's scenario: the agent "flags anomalies (portion counts creeping up, cost drifting) before auto-renewing".
Two things are compared with the median of the same line's last renewals:
  * the quantity asked for on each request line, with what the past renewals of that line ordered, in its unit;
  * the net price per sales unit of each product, with what the past renewals that carried it paid.
A line with fewer than `MIN_RENEWALS_TO_JUDGE` past renewals is not compared: its history is too short to judge.
A median is used rather than a mean so that one unusual week does not move what counts as usual.

Deterministic and read from data: the engine reads this through the `standing.*` facts, and the renewal shows the
same report, so what the buyer sees is what the policy judged.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from tta.contracts.common import RATIO_PLACES, Unit
from tta.contracts.offer import Coverage, OfferLine, OfferOption
from tta.contracts.standing import DriftCheck, DriftKind, DriftReport, Renewal, StandingHistory
from tta.policy.coverage import UNIT_WORDS
from tta.policy.text import format_number, format_ratio, join_words, plain_name

DRIFT_WINDOW = 6  # the last N renewals of a line that its median is taken over
MIN_RENEWALS_TO_JUDGE = 3  # fewer past renewals of a line: too short a history to judge it
WEEKLY_CADENCE_DAYS = 7
CENT = Decimal("0.01")
_RATIO_STEP = Decimal(1).scaleb(-RATIO_PLACES)


@dataclass(frozen=True)
class _Series:
    """The values of one line in its last renewals, oldest first, and which of those renewals are synthetic."""

    values: tuple[Decimal, ...]
    synthetic_ids: frozenset[str]


def assess_drift(option: OfferOption, history: StandingHistory, tolerance: Decimal | None) -> DriftReport:
    """Every comparison this renewal allows, and one sentence. `tolerance` is the profile's
    `standing_order_drift_ratio`; None when the profile sets none, so nothing is over it."""
    when = "this week" if history.cadence_days == WEEKLY_CADENCE_DAYS else "this time"
    several = len(option.coverage) > 1
    checks: list[DriftCheck] = []
    not_compared: list[str] = []
    synthetic: set[str] = set()
    for entry in option.coverage:
        series = _quantities(history.renewals, entry.request_line_index, entry.unit)
        label = f"request line {entry.request_line_index + 1}: " if several else ""
        what = f"{label}the quantity" if several else "the quantity"
        _compare(_quantity_check(entry, series, tolerance, label, when), series, what, checks, not_compared, synthetic)
    for line in _distinct_products(option.lines):
        series = _prices(history.renewals, line.product_id)
        what = f"the unit price of {line.product_id}"
        _compare(_price_check(line, series, tolerance, when), series, what, checks, not_compared, synthetic)
    return DriftReport(
        standing_order_id=history.standing_order_id, judged=bool(checks), tolerance=tolerance, checks=tuple(checks),
        not_compared=tuple(not_compared), synthetic_renewals=len(synthetic),
        sentence=_sentence(history, tuple(checks), tuple(not_compared), tolerance, len(synthetic)),
    )


def over_tolerance(report: DriftReport) -> tuple[DriftCheck, ...]:
    return tuple(check for check in report.checks if check.over_tolerance)


def largest_drift(report: DriftReport) -> Decimal:
    return max((check.drift_ratio for check in report.checks), default=Decimal(0))


# --- the series of one line --------------------------------------------------------------------------------

def _quantities(renewals: Sequence[Renewal], request_line_index: int, unit: Unit) -> _Series:
    """What each past renewal ordered of one request line, in its unit; a renewal that ordered none is left out."""
    found = [
        (renewal, sum((line.quantity for line in renewal.lines
                       if line.request_line_index == request_line_index and line.unit is unit), Decimal(0)))
        for renewal in renewals
    ]
    return _last((renewal, total) for renewal, total in found if total > 0)


def _prices(renewals: Sequence[Renewal], product_id: str) -> _Series:
    """The unit price each past renewal that carried the product paid for it."""
    found = (
        (renewal, next(line.unit_net_price_eur for line in renewal.lines if line.product_id == product_id))
        for renewal in renewals if any(line.product_id == product_id for line in renewal.lines)
    )
    return _last(found)


def _last(found: Iterable[tuple[Renewal, Decimal]]) -> _Series:
    pairs = list(found)[-DRIFT_WINDOW:]
    return _Series(
        values=tuple(value for _, value in pairs),
        synthetic_ids=frozenset(renewal.renewal_id for renewal, _ in pairs if renewal.synthetic),
    )


def _distinct_products(lines: Sequence[OfferLine]) -> list[OfferLine]:
    return list({line.product_id: line for line in reversed(lines)}.values())[::-1]


# --- one comparison ----------------------------------------------------------------------------------------

def _compare(
    check: DriftCheck | None, series: _Series, what: str, checks: list[DriftCheck], not_compared: list[str],
    synthetic: set[str],
) -> None:
    if check is None:
        renewals = _count(len(series.values), "past renewal")
        not_compared.append(f"{what} ({renewals}, at least {MIN_RENEWALS_TO_JUDGE} needed)")
        return
    checks.append(check)
    synthetic.update(series.synthetic_ids)


def _ratio(this: Decimal, middle: Decimal) -> Decimal:
    return (abs(this - middle) / middle).quantize(_RATIO_STEP, rounding=ROUND_HALF_UP)


def _judgeable(series: _Series) -> Decimal | None:
    """The median of the series, or None when the series is too short or its median is zero (no ratio)."""
    if len(series.values) < MIN_RENEWALS_TO_JUDGE:
        return None
    middle = Decimal(median(series.values))
    return middle if middle > 0 else None


def _quantity_check(
    entry: Coverage, series: _Series, tolerance: Decimal | None, label: str, when: str
) -> DriftCheck | None:
    middle = _judgeable(series)
    if middle is None:
        return None
    unit = UNIT_WORDS[entry.unit]
    ratio = _ratio(entry.requested, middle)
    sentence = (
        f"{label}{format_number(entry.requested)} {unit} {when} against a median of {format_number(middle)} {unit} "
        f"over the last {_count(len(series.values), 'renewal')}"
    )
    return DriftCheck(
        kind=DriftKind.QUANTITY, request_line_index=entry.request_line_index, this_renewal=entry.requested,
        median=middle, unit=unit, renewals=len(series.values), drift_ratio=ratio,
        over_tolerance=_over(ratio, tolerance), sentence=sentence,
    )


def _price_check(line: OfferLine, series: _Series, tolerance: Decimal | None, when: str) -> DriftCheck | None:
    middle = _judgeable(series)
    if middle is None:
        return None
    ratio = _ratio(line.unit_net_price, middle)
    sentence = (
        f"€{_price(line.unit_net_price)} per {line.sales_unit} of {line.product_id} {when} against a median of "
        f"€{_price(middle)} over the last {_count(len(series.values), 'renewal')}"
    )
    return DriftCheck(
        kind=DriftKind.UNIT_PRICE, request_line_index=line.request_line_index, product_id=line.product_id,
        this_renewal=line.unit_net_price, median=middle, unit=line.sales_unit, renewals=len(series.values),
        drift_ratio=ratio, over_tolerance=_over(ratio, tolerance), sentence=sentence,
    )


def _over(ratio: Decimal, tolerance: Decimal | None) -> bool:
    return tolerance is not None and ratio > tolerance


# --- words -------------------------------------------------------------------------------------------------

def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _price(value: Decimal) -> str:
    """€2.48, €0.4125: cents when the price has no smaller part."""
    return format(value.quantize(CENT), ",.2f") if value == value.quantize(CENT) else format_number(value)


def standing_order_said(history: StandingHistory) -> str:
    """ "standing order “Weekly lactose-free milk, hotel kitchen”": by the name the buyer gave it, never by its
    id, which is no word a person says. The name is the buyer's text: read as data, so it cannot close the
    quotation marks around it. An order with no name is said by its id."""
    name = plain_name(history.name)
    return f"standing order “{name}”" if name else f"standing order {history.standing_order_id}"


def _sentence(
    history: StandingHistory, checks: tuple[DriftCheck, ...], not_compared: tuple[str, ...],
    tolerance: Decimal | None, synthetic: int,
) -> str:
    name = f"The {standing_order_said(history)}"
    if not checks:
        on_record = _count(len(history.renewals), "past renewal")
        return (
            f"{name} has too short a history to judge drift: {on_record} on record, at least "
            f"{MIN_RENEWALS_TO_JUDGE} are needed for a line. Rule P-08 does not apply to this renewal."
        )
    over = [check.sentence for check in checks if check.over_tolerance]
    if tolerance is None:
        text = (
            f"{name}: {join_words([check.sentence for check in checks])}. The profile sets no drift tolerance, "
            "so a human decides this renewal (F-03)."
        )
    elif over:
        text = f"{name} drifts beyond the {format_ratio(tolerance)} tolerance: {join_words(over)}."
    else:
        within = join_words([check.sentence for check in checks])
        text = f"{name} is within the {format_ratio(tolerance)} tolerance: {within}."
    if not_compared:
        text += f" Not compared, too short a history: {join_words(list(not_compared))}."
    if synthetic:
        text += (
            f" {_count(synthetic, 'renewal')} of the history {'is' if synthetic == 1 else 'are'} synthetic, made up "
            "for the demonstration: the Valio Aimo mock has no order history."
        )
    return text
