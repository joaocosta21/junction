"""The six availability states: one recorded line per state, the order of evaluation, and the regression counts."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from tta.availability import classify, is_late, late_sentence
from tta.contracts.availability import QUANTITY_NOT_CONFIRMED_THRESHOLD, AvailabilityAssessment
from tta.contracts.common import AvailabilityState

BLOCKED_ID = "470094"  # Terminal, 999999, cut-off passed, availableDate 2026-12-30 (Friday's sample)
NOT_DELIVERABLE_ID = "465854"
OUT_OF_STOCK_ID = "470193"
OUT_OF_STOCK_AFTER_CUTOFF_ID = "474311"  # amount 0 and a cut-off that has passed
CUTOFF_PASSED_ID = "460315"  # Terminal, 999999, closed Thursday 12 Nov 15:00
CUTOFF_PASSED_REAL_STOCK_ID = "476965"  # Stock, 3 units, closed Friday 13 Nov 13:00
STOCK_PLACEHOLDER_ID = "462152"  # Stock, 9999999999
STOCK_PLACEHOLDER_416M_ID = "477367"  # Stock, 416666666
CONFIRMED_ID = "469363"  # Stock, 384 units (tonight's capture)

NEEDED_BY = date(2026, 11, 16)
CUTOFF = datetime.fromisoformat("2026-11-15T17:00:00+02:00")

SAMPLE_COUNTS = {
    AvailabilityState.BLOCKED: 1,
    AvailabilityState.NOT_DELIVERABLE: 203,
    AvailabilityState.OUT_OF_STOCK: 29,
    AvailabilityState.CUTOFF_PASSED: 423,
    AvailabilityState.QUANTITY_NOT_CONFIRMED: 92,
    AvailabilityState.CONFIRMED: 252,
}
DEMO_COUNTS = {
    AvailabilityState.NOT_DELIVERABLE: 145,
    AvailabilityState.OUT_OF_STOCK: 21,
    AvailabilityState.CUTOFF_PASSED: 368,
    AvailabilityState.QUANTITY_NOT_CONFIRMED: 112,
    AvailabilityState.CONFIRMED: 123,
}


def _count_states(capture, to_line, now: datetime) -> dict[AvailabilityState, int]:
    made_up = set(capture.manifest.get("non_catalog_ids", ()))
    lines = capture.lines("availability")
    return dict(Counter(classify(to_line(lines[pid]), now).state for pid in capture.ids if pid not in made_up))


@pytest.mark.parametrize(
    ("product_id", "state"),
    [
        (BLOCKED_ID, AvailabilityState.BLOCKED),
        (NOT_DELIVERABLE_ID, AvailabilityState.NOT_DELIVERABLE),
        (OUT_OF_STOCK_ID, AvailabilityState.OUT_OF_STOCK),
        (CUTOFF_PASSED_ID, AvailabilityState.CUTOFF_PASSED),
        (STOCK_PLACEHOLDER_ID, AvailabilityState.QUANTITY_NOT_CONFIRMED),
    ],
)
def test_a_recorded_line_of_fridays_sample_gets_its_state(
    capture_sample, sample_clock, to_line, product_id: str, state: AvailabilityState
) -> None:
    line = to_line(capture_sample.lines("availability")[product_id])

    assessment = classify(line, sample_clock.now())

    assert isinstance(assessment, AvailabilityAssessment)
    assert assessment.product_id == product_id
    assert assessment.state is state
    assert assessment.usable_amount is None  # only a confirmed quantity can be used in arithmetic


def test_a_recorded_confirmed_line_keeps_its_amount_and_what_valio_stated(capture_demo, demo_clock, to_line) -> None:
    line = to_line(capture_demo.lines("availability")[CONFIRMED_ID])

    assessment = classify(line, demo_clock.now())

    assert assessment.state is AvailabilityState.CONFIRMED
    assert assessment.usable_amount == Decimal(384)
    assert assessment.sales_unit == "ST"
    assert assessment.available_date == date(2026, 11, 16)
    assert assessment.closing_time == CUTOFF
    assert assessment.logistic_model == "Stock"
    assert assessment.is_orderable_state


def test_a_line_with_no_schedule_line_carries_no_unit_date_or_cutoff(capture_sample, sample_clock, to_line) -> None:
    assessment = classify(to_line(capture_sample.lines("availability")[NOT_DELIVERABLE_ID]), sample_clock.now())

    assert (assessment.sales_unit, assessment.available_date, assessment.closing_time) == (None, None, None)
    assert assessment.logistic_model is None
    assert not assessment.is_orderable_state


def test_fridays_sample_classifies_as_the_findings_say(capture_sample, sample_clock, to_line) -> None:
    assert _count_states(capture_sample, to_line, sample_clock.now()) == SAMPLE_COUNTS


def test_tonights_capture_classifies_as_the_foundation_reported(capture_demo, demo_clock, to_line) -> None:
    assert _count_states(capture_demo, to_line, demo_clock.now()) == DEMO_COUNTS


def test_a_blocked_product_with_no_schedule_line_is_blocked(build_line) -> None:
    line = build_line(None, sales_block=True, closing_time=None, logistic_model=None)

    assert classify(line, CUTOFF).state is AvailabilityState.BLOCKED


def test_a_block_on_the_schedule_line_alone_is_blocked(build_line) -> None:
    assert classify(build_line(50, line_block=True), CUTOFF - timedelta(hours=1)).state is AvailabilityState.BLOCKED


def test_blocked_comes_before_out_of_stock_cutoff_and_placeholder(build_line, capture_sample, sample_clock,
                                                                 to_line) -> None:
    recorded = to_line(capture_sample.lines("availability")[BLOCKED_ID])  # blocked, cut-off passed, 999999
    blocked_and_empty = build_line(0, sales_block=True, line_block=True)

    assert classify(recorded, sample_clock.now()).state is AvailabilityState.BLOCKED
    assert classify(blocked_and_empty, CUTOFF + timedelta(days=1)).state is AvailabilityState.BLOCKED


def test_an_amount_below_zero_is_read_as_out_of_stock(build_line) -> None:
    assessment = classify(build_line(-5), CUTOFF - timedelta(hours=1))

    assert assessment.state is AvailabilityState.OUT_OF_STOCK
    assert assessment.usable_amount is None


def test_out_of_stock_comes_before_cutoff_passed(capture_sample, sample_clock, to_line) -> None:
    line = to_line(capture_sample.lines("availability")[OUT_OF_STOCK_AFTER_CUTOFF_ID])

    assert line.closing_time is not None and line.closing_time < sample_clock.now()
    assert classify(line, sample_clock.now()).state is AvailabilityState.OUT_OF_STOCK


def test_cutoff_passed_comes_before_the_quantity_states(capture_sample, sample_clock, to_line) -> None:
    lines = capture_sample.lines("availability")
    placeholder = classify(to_line(lines[CUTOFF_PASSED_ID]), sample_clock.now())
    real_stock = classify(to_line(lines[CUTOFF_PASSED_REAL_STOCK_ID]), sample_clock.now())

    assert placeholder.state is AvailabilityState.CUTOFF_PASSED
    assert real_stock.state is AvailabilityState.CUTOFF_PASSED
    assert real_stock.usable_amount is None  # 3 units are stated, but they can no longer be ordered for that date


def test_terminal_999999_is_quantity_not_confirmed_while_its_cutoff_is_open(capture_sample, to_line) -> None:
    line = to_line(capture_sample.lines("availability")[CUTOFF_PASSED_ID])
    before_cutoff = line.closing_time - timedelta(hours=1)

    assessment = classify(line, before_cutoff)

    assert line.logistic_model == "Terminal" and line.schedule_line.available_amount == Decimal(999_999)
    assert assessment.state is AvailabilityState.QUANTITY_NOT_CONFIRMED
    assert assessment.usable_amount is None


def test_a_stock_placeholder_such_as_416666666_is_quantity_not_confirmed(capture_sample, sample_clock,
                                                                         to_line) -> None:
    line = to_line(capture_sample.lines("availability")[STOCK_PLACEHOLDER_416M_ID])

    assessment = classify(line, sample_clock.now())

    assert line.logistic_model == "Stock" and line.schedule_line.available_amount == Decimal(416_666_666)
    assert assessment.state is AvailabilityState.QUANTITY_NOT_CONFIRMED
    assert assessment.usable_amount is None
    assert assessment.is_orderable_state


def test_the_threshold_is_the_contracts_999999_and_the_value_below_it_is_a_quantity(build_line) -> None:
    now = CUTOFF - timedelta(hours=1)
    at_threshold = classify(build_line(999_999), now)
    below = classify(build_line(999_998), now)

    assert Decimal(999_999) == QUANTITY_NOT_CONFIRMED_THRESHOLD
    assert at_threshold.state is AvailabilityState.QUANTITY_NOT_CONFIRMED and at_threshold.usable_amount is None
    assert below.state is AvailabilityState.CONFIRMED and below.usable_amount == Decimal(999_998)


def test_a_cutoff_exactly_equal_to_now_counts_as_passed(build_line) -> None:
    line = build_line(50, closing_time=CUTOFF)

    assert classify(line, CUTOFF).state is AvailabilityState.CUTOFF_PASSED
    assert classify(line, CUTOFF - timedelta(seconds=1)).state is AvailabilityState.CONFIRMED


def test_the_cutoff_is_compared_as_an_instant_whatever_the_clocks_offset(build_line) -> None:
    line = build_line(50, closing_time=CUTOFF)  # 17:00 +02:00 is 15:00 UTC

    assert classify(line, datetime(2026, 11, 15, 15, 0, tzinfo=UTC)).state is AvailabilityState.CUTOFF_PASSED
    assert classify(line, datetime(2026, 11, 15, 14, 59, 59, tzinfo=UTC)).state is AvailabilityState.CONFIRMED


def test_a_line_with_stock_and_no_cutoff_is_not_called_cutoff_passed(build_line) -> None:
    assessment = classify(build_line(50, closing_time=None), CUTOFF)

    assert assessment.state is AvailabilityState.CONFIRMED
    assert assessment.sentence == (
        "50 ST confirmed in stock, for delivery on Monday 16 Nov; Valio gave no order cut-off."
    )


def test_classify_returns_the_same_answer_twice_and_leaves_the_line_alone(capture_demo, demo_clock, to_line) -> None:
    line = to_line(capture_demo.lines("availability")[CONFIRMED_ID])
    before = line.model_dump()

    assert classify(line, demo_clock.now()) == classify(line, demo_clock.now())
    assert line.model_dump() == before


# --- sentences ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("product_id", "sentence"),
    [
        (BLOCKED_ID, "Valio has blocked sales of this product, so it cannot be ordered now."),
        (NOT_DELIVERABLE_ID, "Valio cannot currently deliver this product on any date."),
        (OUT_OF_STOCK_ID, "Out of stock: Valio shows 0 KG available."),
        (CUTOFF_PASSED_ID,
         "Order cut-off passed on Thursday 12 Nov at 15:00, so delivery on Monday 16 Nov cannot be promised."),
        (STOCK_PLACEHOLDER_ID,
         "Quantity not confirmed: Valio reports 9,999,999,999 BAG, a placeholder that means the stock is not known."),
    ],
)
def test_each_state_has_a_sentence_for_a_buyer(capture_sample, sample_clock, to_line, product_id: str,
                                               sentence: str) -> None:
    line = to_line(capture_sample.lines("availability")[product_id])

    assert classify(line, sample_clock.now()).sentence == sentence


def test_the_confirmed_sentence_says_the_amount_the_date_and_the_cutoff(capture_demo, demo_clock, to_line) -> None:
    line = to_line(capture_demo.lines("availability")[CONFIRMED_ID])

    assert classify(line, demo_clock.now()).sentence == (
        "384 ST confirmed in stock, for delivery on Monday 16 Nov if ordered by Sunday 15 Nov at 17:00."
    )


def test_sentences_hold_when_valio_leaves_the_date_or_the_cutoff_out(build_line) -> None:
    now = CUTOFF - timedelta(hours=1)

    no_date = classify(build_line(50, available_date=None), now)
    neither = classify(build_line("12.5", available_date=None, closing_time=None, sales_unit="KG"), now)
    passed_no_date = classify(build_line(50, available_date=None), CUTOFF)

    assert no_date.sentence == (
        "50 ST confirmed in stock; Valio gave no delivery date (order cut-off Sunday 15 Nov at 17:00)."
    )
    assert neither.sentence == "12.5 KG confirmed in stock; Valio gave no delivery date and no order cut-off."
    assert passed_no_date.sentence == "Order cut-off passed on Sunday 15 Nov at 17:00, so delivery cannot be promised."


# --- late for the needed-by date ------------------------------------------------------------------


def test_a_recorded_line_dated_after_needed_by_is_late(capture_sample, to_line) -> None:
    line = to_line(capture_sample.lines("availability")[BLOCKED_ID])  # availableDate 2026-12-30

    assert is_late(line, NEEDED_BY)
    assert late_sentence(line.schedule_line.available_date, NEEDED_BY) == (
        "Delivery is on Wednesday 30 Dec, later than the needed-by date Monday 16 Nov."
    )


def test_delivery_on_or_before_needed_by_is_not_late(build_line) -> None:
    assert not is_late(build_line(available_date=NEEDED_BY), NEEDED_BY)
    assert not is_late(build_line(available_date=NEEDED_BY - timedelta(days=1)), NEEDED_BY)
    assert is_late(build_line(available_date=NEEDED_BY + timedelta(days=1)), NEEDED_BY)


def test_nothing_is_late_without_a_needed_by_date_or_without_a_delivery_date(build_line) -> None:
    assert not is_late(build_line(available_date=date(2026, 12, 30)), None)
    assert not is_late(build_line(None), NEEDED_BY)  # no schedule line: NOT_DELIVERABLE, not late
    assert not is_late(build_line(0, available_date=None), NEEDED_BY)  # out of stock lines carry no date
