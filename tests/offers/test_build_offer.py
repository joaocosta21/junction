"""The offer builder over hand-built price and availability (SPEC sections 3, 4 and 5)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from tta.contracts.availability import QUANTITY_NOT_CONFIRMED_THRESHOLD
from tta.contracts.common import (
    CheckResult,
    ConstraintKind,
    ExclusionReason,
    OptionKind,
    Unit,
)
from tta.contracts.offer import Offer
from tta.contracts.request import PurchaseRequest, RequestLine

# Three lactose-free milks of category 10400, each a 1-litre carton sold by the piece (ST).
A, B, C = "469363", "462775", "463380"
UNCONFIRMED = "464306"
PLACEHOLDER = 999_999

Build = Callable[..., Offer]


# --- combining ---------------------------------------------------------------------------------------------

def test_one_product_that_covers_all_gives_a_single_line(build: Build, price: Any, stock: Any, best: Any) -> None:
    offer = build([price(A, "2.48"), price(B, "2.57")], [stock(A, 1500), stock(B, 51)])

    option = best(offer)
    assert [(line.product_id, line.quantity, line.covers) for line in option.lines] == [(A, 1000, 1000)]
    assert option.totals.net == Decimal("2480.00")
    assert option.fill_ratio == 1
    assert option.is_partial is False


def test_two_products_are_combined_cheapest_first(build: Build, price: Any, stock: Any, best: Any) -> None:
    offer = build([price(A, "2.65"), price(B, "2.48")], [stock(A, 800), stock(B, 384)])

    option = best(offer)
    assert [(line.product_id, line.quantity, line.covers) for line in option.lines] == [(B, 384, 384), (A, 616, 616)]
    assert option.totals.net == Decimal("952.32") + Decimal("1632.40")
    assert option.fill_ratio == 1


def test_short_stock_gives_a_partial_fill_with_the_missing_amount(
    build: Build, price: Any, stock: Any, best: Any
) -> None:
    offer = build([price(C, "2.65"), price(B, "2.57")], [stock(C, 698), stock(B, 51)])

    option = best(offer)
    assert [(line.product_id, line.quantity) for line in option.lines] == [(B, 51), (C, 698)]
    assert option.totals.net == Decimal("1980.77")
    assert option.is_partial is True
    assert option.fill_ratio == Decimal("0.749")
    coverage = option.coverage[0]
    assert (coverage.requested, coverage.covered, coverage.missing, coverage.unit) == (1000, 749, 251, Unit.L)
    assert "251" in option.summary
    quantity = next(check for check in option.constraint_checks if check.kind is ConstraintKind.QUANTITY)
    assert quantity.result is CheckResult.NOT_MET
    assert "251" in quantity.sentence
    assert option.decision is not None
    assert {"P-01", "P-03"} <= set(option.decision.rule_ids)  # above 750 EUR and below the 0.9 minimum fill


def test_a_placeholder_amount_never_enters_a_sum(build: Build, price: Any, stock: Any, best: Any) -> None:
    # The cheapest product reports the placeholder 999999; confirmed stock is 80 litres short.
    offer = build(
        [price(UNCONFIRMED, "1.01"), price(A, "2.48"), price(B, "2.57")],
        [stock(UNCONFIRMED, PLACEHOLDER), stock(A, 400), stock(B, 520)],
    )

    option = best(offer)
    assert [(line.product_id, line.quantity) for line in option.lines] == [(A, 400), (B, 520)]
    assert option.coverage[0].covered == 920
    assert option.coverage[0].missing == 80
    assert option.totals.net == Decimal("992.00") + Decimal("1336.40")
    alternative = next(option for option in offer.options if option.kind is OptionKind.ALTERNATIVE_UNCONFIRMED)
    line = alternative.lines[0]
    assert (line.product_id, line.quantity, line.covers) == (UNCONFIRMED, 1000, 1000)
    assert line.availability.usable_amount is None
    assert alternative.totals.net == Decimal("1010.00")
    for every in offer.options:
        assert all(each.quantity < QUANTITY_NOT_CONFIRMED_THRESHOLD for each in every.lines)
        assert every.coverage[0].covered <= 1000
    assert [option.kind for option in offer.options] == [OptionKind.BEST_CONFIRMED, OptionKind.ALTERNATIVE_UNCONFIRMED]


def test_a_very_large_stock_value_is_not_a_quantity_either(build: Build, price: Any, stock: Any) -> None:
    offer = build([price(A, "2.48")], [stock(A, "9999999999")])

    assert [option.kind for option in offer.options] == [OptionKind.ALTERNATIVE_UNCONFIRMED]
    assert offer.options[0].lines[0].quantity == 1000
    quantity = next(check for check in offer.options[0].constraint_checks if check.kind is ConstraintKind.QUANTITY)
    assert quantity.result is CheckResult.UNVERIFIED


def test_the_unconfirmed_alternative_is_ranked_after_a_partial_confirmed_option(
    build: Build, price: Any, stock: Any
) -> None:
    offer = build([price(UNCONFIRMED, "1.01"), price(A, "2.48")], [stock(UNCONFIRMED, PLACEHOLDER), stock(A, 10)])

    assert [(option.option_id, option.kind) for option in offer.options] == [
        ("opt_1", OptionKind.BEST_CONFIRMED), ("opt_2", OptionKind.ALTERNATIVE_UNCONFIRMED),
    ]


# --- validity ----------------------------------------------------------------------------------------------

def test_valid_until_is_the_cut_off_when_it_comes_before_the_price_validity(
    build: Build, price: Any, stock: Any, open_cutoff: datetime, best: Any
) -> None:
    end_of_year = datetime.fromisoformat("2026-12-31T00:00:00+02:00")
    offer = build([price(A, "2.48", valid_to=end_of_year)], [stock(A, 1500)])

    assert best(offer).valid_until == open_cutoff
    assert best(offer).lines[0].price_valid_to == end_of_year


def test_valid_until_is_the_price_validity_when_it_comes_first(build: Build, price: Any, stock: Any, best: Any) -> None:
    sunday_noon = datetime.fromisoformat("2026-11-15T12:00:00+02:00")
    early_cutoff = datetime.fromisoformat("2026-11-15T09:00:00+02:00")
    offer = build(
        [price(A, "2.48", valid_to=sunday_noon), price(B, "2.57")],
        [stock(A, 600), stock(B, 600)],
    )

    assert best(offer).valid_until == sunday_noon

    earlier = build(
        [price(A, "2.48", valid_to=sunday_noon), price(B, "2.57")],
        [stock(A, 600), stock(B, 600, closing_time=early_cutoff)],
    )
    assert best(earlier).valid_until == early_cutoff


# --- nothing fits ------------------------------------------------------------------------------------------

def test_a_request_no_product_can_meet_returns_no_options_and_the_reasons(
    build: Build, price: Any, stock: Any, reasons: Any
) -> None:
    passed = datetime.fromisoformat("2026-11-12T15:00:00+02:00")
    offer = build([price(A, "2.48"), price(B, "2.57")], [stock(A, 500, closing_time=passed), stock(B, 0)])

    assert offer.options == ()
    assert reasons(offer)[A] is ExclusionReason.CUTOFF_PASSED
    assert reasons(offer)[B] is ExclusionReason.OUT_OF_STOCK
    assert offer.candidates_considered >= 2
    assert all(exclusion.sentence.strip() for exclusion in offer.excluded)
    assert any("no option" in note.lower() for note in offer.notes)


def test_words_no_product_name_holds_give_an_offer_with_the_reason_not_an_error(build: Build) -> None:
    request = PurchaseRequest(
        lines=(RequestLine(text="unobtainium", name_terms=("zzqqxx",), quantity=Decimal(5), unit=Unit.UNIT),)
    )

    offer = build([], [], request)

    assert offer.options == ()
    assert offer.excluded == ()
    assert offer.candidates_considered == 0
    assert any("zzqqxx" in note for note in offer.notes)
