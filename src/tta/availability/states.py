"""The six availability states of SPEC section 4. Pure functions: the clock is an argument.

Scores on the 15% for exception handling (partial availability, delivery constraints): every
product gets exactly one state and one sentence a buyer can read.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from tta.availability.wording import format_amount, format_day, format_moment
from tta.contracts.availability import (
    QUANTITY_NOT_CONFIRMED_THRESHOLD,
    AvailabilityAssessment,
    AvailabilityLine,
)
from tta.contracts.common import AvailabilityState

BLOCKED_SENTENCE = "Valio has blocked sales of this product, so it cannot be ordered now."
NOT_DELIVERABLE_SENTENCE = "Valio cannot currently deliver this product on any date."


def classify(line: AvailabilityLine, now: datetime) -> AvailabilityAssessment:
    """One of the six states, checked in the order of SPEC section 4, against the clock given."""
    schedule = line.schedule_line
    # salesBlock true at either level means "cannot be ordered currently" (AIMO/docs/API.md section 8.3).
    if line.sales_block or (schedule is not None and schedule.sales_block):
        return _assess(line, AvailabilityState.BLOCKED, BLOCKED_SENTENCE)
    # No schedule line: "cannot currently be delivered on any date" (AIMO/docs/API.md section 8.4).
    if schedule is None:
        return _assess(line, AvailabilityState.NOT_DELIVERABLE, NOT_DELIVERABLE_SENTENCE)
    stated = f"{format_amount(schedule.available_amount)} {schedule.sales_unit}"
    # A schedule line with amount 0 is a third unavailable shape (AIMO/docs/API.md section 8.2).
    if schedule.available_amount <= 0:
        return _assess(line, AvailabilityState.OUT_OF_STOCK, f"Out of stock: Valio shows {stated} available.")
    # "Order by closingTime at the latest": a cut-off equal to now has passed (AIMO/docs/API.md section 8.7).
    if line.closing_time is not None and line.closing_time <= now:
        sentence = _cutoff_passed(line.closing_time, schedule.available_date)
        return _assess(line, AvailabilityState.CUTOFF_PASSED, sentence)
    # Terminal 999999 and the very large Stock values both mean the stock is not known (AIMO/FINDINGS.md section 1).
    if schedule.available_amount >= QUANTITY_NOT_CONFIRMED_THRESHOLD:
        sentence = f"Quantity not confirmed: Valio reports {stated}, a placeholder that means the stock is not known."
        return _assess(line, AvailabilityState.QUANTITY_NOT_CONFIRMED, sentence)
    sentence = f"{stated} confirmed in stock{_delivery_terms(schedule.available_date, line.closing_time)}."
    return _assess(line, AvailabilityState.CONFIRMED, sentence, usable_amount=schedule.available_amount)


def is_late(line: AvailabilityLine, needed_by: date | None) -> bool:
    """True when the line's `availableDate` is later than `needed_by` (exclusion `LATE_FOR_NEEDED_BY`)."""
    schedule = line.schedule_line
    if needed_by is None or schedule is None or schedule.available_date is None:
        return False
    return schedule.available_date > needed_by


def late_sentence(available_date: date, needed_by: date) -> str:
    """The sentence for a product excluded as `LATE_FOR_NEEDED_BY`."""
    return f"Delivery is on {format_day(available_date)}, later than the needed-by date {format_day(needed_by)}."


def _assess(
    line: AvailabilityLine, state: AvailabilityState, sentence: str, usable_amount: Decimal | None = None
) -> AvailabilityAssessment:
    """What Valio stated, with our state. `usable_amount` stays `None` unless the quantity is confirmed."""
    schedule = line.schedule_line
    return AvailabilityAssessment(
        product_id=line.product_id,
        state=state,
        usable_amount=usable_amount,
        sales_unit=schedule.sales_unit if schedule is not None else None,
        available_date=schedule.available_date if schedule is not None else None,
        closing_time=line.closing_time,
        logistic_model=line.logistic_model,
        sentence=sentence,
    )


def _cutoff_passed(closing_time: datetime, available_date: date | None) -> str:
    delivery = f"delivery on {format_day(available_date)}" if available_date is not None else "delivery"
    return f"Order cut-off passed on {format_moment(closing_time)}, so {delivery} cannot be promised."


def _delivery_terms(available_date: date | None, closing_time: datetime | None) -> str:
    """The end of the confirmed sentence: the delivery date and the cut-off, or which of them Valio left out."""
    if available_date is not None and closing_time is not None:
        return f", for delivery on {format_day(available_date)} if ordered by {format_moment(closing_time)}"
    if available_date is not None:
        return f", for delivery on {format_day(available_date)}; Valio gave no order cut-off"
    if closing_time is not None:
        return f"; Valio gave no delivery date (order cut-off {format_moment(closing_time)})"
    return "; Valio gave no delivery date and no order cut-off"
