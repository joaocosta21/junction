"""How values are written on a page: money, quantities, times, and a word for every code."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

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
    Unit,
    Verdict,
)
from tta.contracts.offer import Exclusion
from tta.ui import view

HELSINKI = timezone(timedelta(hours=2))


@pytest.mark.parametrize(("amount", "written"), [
    ("2580.64", "€2,580.64"), ("1010", "€1,010.00"), ("0.5", "€0.50"), ("2.005", "€2.01"),
    ("1234567.891", "€1,234,567.89"),
])
def test_money_is_written_in_euros_with_two_decimals(amount: str, written: str) -> None:
    assert view.money(Decimal(amount)) == written


@pytest.mark.parametrize(("amount", "written"), [
    ("1000.000", "1,000"), ("0.5", "0.5"), ("2.500", "2.5"), ("384", "384"), ("0.020", "0.02"), ("1E+3", "1,000"),
])
def test_a_quantity_is_written_without_trailing_zeros(amount: str, written: str) -> None:
    assert view.quantity(Decimal(amount)) == written


def test_a_unit_price_keeps_the_decimals_valio_states() -> None:
    assert view.unit_price(Decimal("2.48")) == "€2.48"
    assert view.unit_price(Decimal("0.0125")) == "€0.0125"


def test_a_ratio_is_written_as_a_percentage() -> None:
    assert view.percent(Decimal("0.749")) == "74.9%"
    assert view.percent(Decimal(1)) == "100%"


def test_a_time_is_written_with_its_weekday_and_its_own_offset() -> None:
    assert view.moment(datetime(2026, 11, 15, 17, 0, tzinfo=HELSINKI)) == "Sunday 15 Nov 2026 at 17:00 (UTC+02:00)"
    assert view.moment(datetime(2026, 11, 14, 2, 59, 33, tzinfo=UTC)) == "Saturday 14 Nov 2026 at 02:59 (UTC)"
    assert view.clock_time(datetime(2026, 11, 14, 2, 59, 33, tzinfo=UTC)) == "14 Nov 02:59:33 UTC"
    assert view.day(date(2026, 11, 16)) == "Monday 16 Nov 2026"


def test_nothing_missing_is_written_as_a_value() -> None:
    assert view.moment(None) == "not stated"
    assert view.day(None) == "not stated"
    assert view.quantity(None) == "not stated"


def test_a_price_valid_to_the_end_of_time_has_no_end_date() -> None:
    assert view.valid_to(datetime(9999, 12, 31, tzinfo=HELSINKI)) == "no end date"
    assert view.valid_to(datetime(2026, 12, 31, tzinfo=HELSINKI)) == "Thursday 31 Dec 2026 at 00:00 (UTC+02:00)"
    assert view.valid_to(None) == "not stated"


@pytest.mark.parametrize("codes", [
    ExclusionReason, ClaimName, ClaimStatus, CheckResult, Verdict, OrderStatus, ApproverRole, OptionKind,
    AvailabilityState, ConstraintKind, Unit,
])
def test_every_code_has_its_own_words(codes: type) -> None:
    for code in codes:
        assert code.value in view.WORDS[codes], code  # written by hand, not derived from the code
        assert view.words(code) == view.WORDS[codes][code.value]


def test_two_codes_with_the_same_spelling_keep_their_own_words() -> None:
    # A StrEnum member equals its string, so CONFIRMED of a claim and CONFIRMED of availability are "equal".
    assert view.words(ClaimStatus.CONFIRMED) == "confirmed"
    assert view.words(AvailabilityState.CONFIRMED) == "Confirmed in stock"
    assert view.words(ExclusionReason.QUANTITY_NOT_CONFIRMED) == "Quantity not confirmed"
    assert view.tone(AvailabilityState.QUANTITY_NOT_CONFIRMED) == "warn"
    assert view.tone(ExclusionReason.QUANTITY_NOT_CONFIRMED) == "plain"


def test_a_code_nobody_wrote_words_for_is_still_readable() -> None:
    assert view.words("SOMETHING_NEW") == "Something new"
    assert view.words(None) == "not stated"


def test_a_mark_is_a_word_and_a_tone_never_a_colour_alone() -> None:
    assert view.tone(ClaimStatus.CONFIRMED) == "ok"
    assert view.tone(ClaimStatus.UNKNOWN) == "warn"
    assert view.tone(ClaimStatus.RULED_OUT) == "bad"
    assert [view.tone(code) for code in (CheckResult.MET, CheckResult.UNVERIFIED, CheckResult.NOT_MET)] == [
        "ok", "warn", "bad",
    ]
    assert [view.tone(code) for code in (Verdict.AUTO, Verdict.APPROVAL, Verdict.BLOCK)] == ["ok", "warn", "bad"]
    assert [view.tone(code) for code in OrderStatus] == ["warn", "ok", "bad", "bad"]
    assert view.tone("SOMETHING_NEW") == "plain"
    for tone in ("ok", "warn", "bad", "plain"):
        assert view.GLYPHS[tone]


def _excluded(product_id: str, reason: ExclusionReason) -> Exclusion:
    return Exclusion(product_id=product_id, name=f"Product {product_id}", request_line_index=0, reason=reason,
                     sentence="Because.")


def test_the_first_exclusions_shown_cover_every_reason() -> None:
    cut, late, pack = ExclusionReason.CUTOFF_PASSED, ExclusionReason.NOT_DELIVERABLE, ExclusionReason.PORTION_PACK
    reasons = (cut, cut, cut, cut, late, pack, cut)
    excluded = tuple(_excluded(str(number), reason) for number, reason in enumerate(reasons))

    ordered = view.spread_by_reason(excluded)

    assert [entry.product_id for entry in ordered] == ["0", "4", "5", "1", "2", "3", "6"]
    assert sorted(ordered, key=lambda entry: entry.product_id) == list(excluded)  # nothing lost, nothing added
    assert view.spread_by_reason(()) == ()


def test_exclusions_are_counted_by_reason_most_frequent_first() -> None:
    cut, pack = ExclusionReason.CUTOFF_PASSED, ExclusionReason.PORTION_PACK
    excluded = tuple(_excluded(str(number), reason) for number, reason in enumerate((pack, cut, cut)))

    assert view.reason_counts(excluded) == ((cut, 2), (pack, 1))
