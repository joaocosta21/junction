"""Verification status per claim (SPEC section 4): price, quantity and delivery date.

Covers every cell of the table for these three claims, and the cells the table leaves open.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from tta.availability import verify
from tta.contracts.common import ClaimName, ClaimStatus

NOW = datetime.fromisoformat("2026-11-14T02:52:45+02:00")  # timeNow of tonight's capture
NEEDED_BY = date(2026, 11, 16)
YEAR_END = datetime.fromisoformat("2026-12-31T00:00:00+02:00")

CONFIRMED_ID = "469363"  # 384 ST, 2.48 EUR, open-ended price
PLACEHOLDER_ID = "464306"  # Stock placeholder 9999999999, 1.01 EUR valid to 2026-12-31
CUTOFF_PASSED_ID = "464119"  # Terminal, closed Thursday 12 Nov 15:00
NOT_DELIVERABLE_ID = "471881"
OUT_OF_STOCK_ID = "470193"
BLOCKED_ID = "470094"  # Friday's sample
MADE_UP_ID = "459999"  # not in the catalog: /api/price answers error true


def test_verify_returns_one_check_per_claim_in_a_fixed_order(build_line, build_product, build_price) -> None:
    checks = verify(build_line(), build_price(), build_product(), quantity=Decimal(10), needed_by=NEEDED_BY,
                    allergen_outcome=None, now=NOW)

    assert [check.claim for check in checks] == [
        ClaimName.PRICE, ClaimName.QUANTITY, ClaimName.DELIVERY_DATE, ClaimName.ALLERGENS, ClaimName.ORIGIN,
    ]
    assert all(check.status is ClaimStatus.CONFIRMED for check in checks)
    assert all(check.sentence.endswith(".") for check in checks)


def test_a_recorded_confirmed_product_has_every_claim_confirmed(capture_demo, to_line, to_price,
                                                               build_product) -> None:
    line = to_line(capture_demo.lines("availability")[CONFIRMED_ID])
    price = to_price(capture_demo.lines("price")[CONFIRMED_ID])

    checks = verify(line, price, build_product(id=CONFIRMED_ID), quantity=Decimal(384), needed_by=NEEDED_BY,
                    allergen_outcome=None, now=capture_demo.time_now)

    assert {check.claim: check.status for check in checks} == dict.fromkeys(ClaimName, ClaimStatus.CONFIRMED)


# --- price -------------------------------------------------------------------------------------


def test_price_is_confirmed_when_a_price_was_returned_and_has_no_end_date(capture_demo, to_line, to_price,
                                                                         claim_of) -> None:
    line = to_line(capture_demo.lines("availability")[CONFIRMED_ID])
    price = to_price(capture_demo.lines("price")[CONFIRMED_ID])

    check = claim_of(ClaimName.PRICE, line, price=price)

    assert check.status is ClaimStatus.CONFIRMED
    assert check.sentence == "Valio's price is €2.48 per ST before tax, with no end date."


def test_price_is_confirmed_while_valid_to_is_in_the_future(capture_demo, to_line, to_price, claim_of) -> None:
    line = to_line(capture_demo.lines("availability")[PLACEHOLDER_ID])
    price = to_price(capture_demo.lines("price")[PLACEHOLDER_ID])

    check = claim_of(ClaimName.PRICE, line, price=price)

    assert check.status is ClaimStatus.CONFIRMED
    assert check.sentence == "Valio's price is €1.01 per ST before tax, valid until 31 Dec 2026 at 00:00."


def test_price_names_no_unit_when_the_api_gave_no_schedule_line(build_line, claim_of, build_price) -> None:
    check = claim_of(ClaimName.PRICE, build_line(None), price=build_price("1240.5"))

    assert check.status is ClaimStatus.CONFIRMED
    assert check.sentence == "Valio's price is €1,240.50 per sales unit before tax, with no end date."


def test_price_in_another_currency_is_written_with_its_code(build_line, claim_of, build_price) -> None:
    check = claim_of(ClaimName.PRICE, build_line(), price=build_price("2.485", currency="SEK"))

    assert check.sentence == "Valio's price is 2.485 SEK per ST before tax, with no end date."


def test_price_is_unknown_when_no_price_line_came_back(build_line, claim_of) -> None:
    check = claim_of(ClaimName.PRICE, build_line(), price=None)

    assert check.status is ClaimStatus.UNKNOWN
    assert check.sentence == "Valio returned no price for this product."


def test_price_is_unknown_for_a_recorded_error_line(capture_sample, to_price, build_line, claim_of) -> None:
    price = to_price(capture_sample.lines("price")[MADE_UP_ID])

    assert price.error
    assert claim_of(ClaimName.PRICE, build_line(), price=price).status is ClaimStatus.UNKNOWN


def test_price_is_unknown_when_the_line_says_error_even_if_it_carries_a_price(build_line, build_price,
                                                                               claim_of) -> None:
    price = build_price().model_copy(update={"error": True})  # "error true: no price could be found"

    assert claim_of(ClaimName.PRICE, build_line(), price=price).status is ClaimStatus.UNKNOWN


def test_price_is_unknown_once_valid_to_has_passed_or_is_exactly_now(build_line, claim_of, build_price) -> None:
    line, price = build_line(), build_price("1.01", YEAR_END)

    expired = claim_of(ClaimName.PRICE, line, price=price, now=YEAR_END + timedelta(days=1))
    at_the_instant = claim_of(ClaimName.PRICE, line, price=price, now=YEAR_END)
    a_second_before = claim_of(ClaimName.PRICE, line, price=price, now=YEAR_END - timedelta(seconds=1))

    assert expired.status is ClaimStatus.UNKNOWN
    assert expired.sentence == "Valio's price of €1.01 was valid until 31 Dec 2026 at 00:00, which has passed."
    assert at_the_instant.status is ClaimStatus.UNKNOWN
    assert a_second_before.status is ClaimStatus.CONFIRMED


# --- quantity ----------------------------------------------------------------------------------


def test_quantity_is_confirmed_when_confirmed_stock_covers_the_line(capture_demo, to_line, claim_of) -> None:
    line = to_line(capture_demo.lines("availability")[CONFIRMED_ID])

    covered = claim_of(ClaimName.QUANTITY, line, quantity=Decimal(380))
    exactly = claim_of(ClaimName.QUANTITY, line, quantity=Decimal(384))

    assert covered.status is ClaimStatus.CONFIRMED
    assert covered.sentence == "Valio shows 384 ST in stock, enough for the 380 ST of this line."
    assert exactly.status is ClaimStatus.CONFIRMED


def test_quantity_is_confirmed_when_no_quantity_was_asked(capture_demo, to_line, claim_of) -> None:
    check = claim_of(ClaimName.QUANTITY, to_line(capture_demo.lines("availability")[CONFIRMED_ID]), quantity=None)

    assert check.status is ClaimStatus.CONFIRMED
    assert check.sentence == "Valio shows 384 ST in stock."


def test_quantity_is_ruled_out_when_confirmed_stock_is_short_of_the_line(capture_demo, to_line, claim_of) -> None:
    check = claim_of(ClaimName.QUANTITY, to_line(capture_demo.lines("availability")[CONFIRMED_ID]),
                     quantity=Decimal(385))

    assert check.status is ClaimStatus.RULED_OUT
    assert check.sentence == "Valio shows 384 ST in stock, fewer than the 385 ST of this line."


def test_quantity_is_unknown_when_the_quantity_is_not_confirmed(capture_demo, to_line, claim_of) -> None:
    check = claim_of(ClaimName.QUANTITY, to_line(capture_demo.lines("availability")[PLACEHOLDER_ID]),
                     quantity=Decimal(1))

    assert check.status is ClaimStatus.UNKNOWN
    assert check.sentence == (
        "Quantity not confirmed: Valio reports 9,999,999,999 ST, a placeholder that means the stock is not known."
    )


def test_quantity_is_unknown_when_the_cutoff_has_passed(capture_demo, to_line, claim_of) -> None:
    check = claim_of(ClaimName.QUANTITY, to_line(capture_demo.lines("availability")[CUTOFF_PASSED_ID]),
                     quantity=Decimal(1))

    assert check.status is ClaimStatus.UNKNOWN
    assert check.sentence == "The order cut-off has passed, so no quantity is confirmed for a later delivery."


@pytest.mark.parametrize(
    ("capture_name", "product_id", "sentence"),
    [
        ("2026-11-14-demo", OUT_OF_STOCK_ID, "Out of stock: Valio shows 0 KG available."),
        ("2026-11-14-demo", NOT_DELIVERABLE_ID, "Valio cannot currently deliver this product on any date."),
        ("2026-11-13-sample", BLOCKED_ID, "Valio has blocked sales of this product, so it cannot be ordered now."),
    ],
)
def test_quantity_and_delivery_date_are_ruled_out_for_out_of_stock_not_deliverable_and_blocked(
    load_capture, to_line, claim_of, capture_name: str, product_id: str, sentence: str
) -> None:
    capture = load_capture(capture_name)
    line = to_line(capture.lines("availability")[product_id])

    quantity = claim_of(ClaimName.QUANTITY, line, quantity=Decimal(1), now=capture.time_now)
    delivery = claim_of(ClaimName.DELIVERY_DATE, line, needed_by=date(2026, 12, 31), now=capture.time_now)

    assert (quantity.status, quantity.sentence) == (ClaimStatus.RULED_OUT, sentence)
    assert (delivery.status, delivery.sentence) == (ClaimStatus.RULED_OUT, sentence)


# --- delivery date -----------------------------------------------------------------------------


def test_delivery_date_is_confirmed_with_an_open_cutoff_and_a_date_on_or_before_needed_by(capture_demo, to_line,
                                                                                         claim_of) -> None:
    line = to_line(capture_demo.lines("availability")[CONFIRMED_ID])

    on_the_day = claim_of(ClaimName.DELIVERY_DATE, line, needed_by=NEEDED_BY)
    a_day_early = claim_of(ClaimName.DELIVERY_DATE, line, needed_by=NEEDED_BY + timedelta(days=1))

    assert on_the_day.status is ClaimStatus.CONFIRMED
    assert on_the_day.sentence == (
        "Delivery on Monday 16 Nov meets the needed-by date Monday 16 Nov if ordered by Sunday 15 Nov at 17:00."
    )
    assert a_day_early.status is ClaimStatus.CONFIRMED


def test_delivery_date_is_confirmed_for_an_unconfirmed_quantity_too(capture_demo, to_line, claim_of) -> None:
    check = claim_of(ClaimName.DELIVERY_DATE, to_line(capture_demo.lines("availability")[PLACEHOLDER_ID]),
                     needed_by=NEEDED_BY)

    assert check.status is ClaimStatus.CONFIRMED


def test_delivery_date_is_unknown_when_no_needed_by_was_given(capture_demo, to_line, claim_of) -> None:
    check = claim_of(ClaimName.DELIVERY_DATE, to_line(capture_demo.lines("availability")[CONFIRMED_ID]),
                     needed_by=None)

    assert check.status is ClaimStatus.UNKNOWN
    assert check.sentence == (
        "No needed-by date was given; Valio shows delivery on Monday 16 Nov if ordered by Sunday 15 Nov at 17:00."
    )


def test_delivery_date_is_ruled_out_when_the_cutoff_has_passed(capture_demo, to_line, claim_of) -> None:
    line = to_line(capture_demo.lines("availability")[CUTOFF_PASSED_ID])
    sentence = "Order cut-off passed on Thursday 12 Nov at 15:00, so delivery on Monday 16 Nov cannot be promised."

    dated = claim_of(ClaimName.DELIVERY_DATE, line, needed_by=NEEDED_BY)
    undated = claim_of(ClaimName.DELIVERY_DATE, line, needed_by=None)

    assert (dated.status, dated.sentence) == (ClaimStatus.RULED_OUT, sentence)
    assert (undated.status, undated.sentence) == (ClaimStatus.RULED_OUT, sentence)


def test_delivery_date_is_ruled_out_when_later_than_needed_by(build_line, claim_of) -> None:
    check = claim_of(ClaimName.DELIVERY_DATE, build_line(available_date=date(2026, 12, 30)), needed_by=NEEDED_BY)

    assert check.status is ClaimStatus.RULED_OUT
    assert check.sentence == "Delivery is on Wednesday 30 Dec, later than the needed-by date Monday 16 Nov."


def test_delivery_date_is_unknown_when_valio_gave_no_cutoff_or_no_date(build_line, claim_of) -> None:
    no_cutoff = claim_of(ClaimName.DELIVERY_DATE, build_line(closing_time=None), needed_by=NEEDED_BY)
    no_date = claim_of(ClaimName.DELIVERY_DATE, build_line(available_date=None), needed_by=NEEDED_BY)

    assert no_cutoff.status is ClaimStatus.UNKNOWN
    assert no_cutoff.sentence == "Valio gave no order cut-off, so delivery on Monday 16 Nov cannot be confirmed."
    assert no_date.status is ClaimStatus.UNKNOWN
    assert no_date.sentence == "Valio gave no delivery date for this product."


def test_a_late_delivery_is_ruled_out_even_without_a_cutoff(build_line, claim_of) -> None:
    check = claim_of(ClaimName.DELIVERY_DATE, build_line(closing_time=None, available_date=date(2026, 12, 30)),
                     needed_by=NEEDED_BY)

    assert check.status is ClaimStatus.RULED_OUT
