"""Combining confirmed products into one fill (SPEC section 5, BEST_CONFIRMED). Pure arithmetic in Decimal."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tta.catalog import ProductCatalog
from tta.offers.combining import Supply, ceil_to_step, fill, floor_to_step, units_for

ONE = Decimal(1)


def supply(product_id: str, price: str, usable: str, per_unit: str = "1", step: str = "1") -> Supply:
    return Supply(
        product_id=product_id, per_unit=Decimal(per_unit), unit_price=Decimal(price), usable=Decimal(usable),
        lot_step=Decimal(step),
    )


def test_one_product_that_covers_everything_gives_a_single_pick() -> None:
    result = fill(Decimal(100), [supply("A", "2.00", "500"), supply("B", "1.00", "40")])

    assert [(pick.product_id, pick.units, pick.covers) for pick in result.picks] == [("A", 100, 100)]
    assert result.covered == 100
    assert result.missing == 0


def test_the_cheapest_of_the_products_that_cover_alone_is_chosen() -> None:
    result = fill(Decimal(100), [supply("A", "2.00", "500"), supply("B", "1.50", "100"), supply("C", "1.00", "99")])

    assert [pick.product_id for pick in result.picks] == ["B"]


def test_a_single_product_is_compared_on_what_the_whole_quantity_costs() -> None:
    # 100 L: 10 cases of 10 L at 14.00 (140.00) beat 100 cartons of 1 L at 1.50 (150.00).
    result = fill(Decimal(100), [supply("CARTON", "1.50", "500"), supply("CASE", "14.00", "50", per_unit="10")])

    assert [(pick.product_id, pick.units) for pick in result.picks] == [("CASE", 10)]


def test_when_no_product_covers_alone_the_cheapest_are_combined_first() -> None:
    result = fill(Decimal(100), [supply("DEAR", "3.00", "80"), supply("CHEAP", "1.00", "60")])

    picks = [(pick.product_id, pick.units, pick.covers) for pick in result.picks]
    assert picks == [("CHEAP", 60, 60), ("DEAR", 40, 40)]
    assert result.missing == 0


def test_combining_ranks_by_the_price_of_a_litre_not_of_a_sales_unit() -> None:
    # The 10 L case at 12.00 is 1.20 a litre; the 1 L carton at 1.50 is dearer per litre.
    result = fill(Decimal(100), [supply("CARTON", "1.50", "70"), supply("CASE", "12.00", "5", per_unit="10")])

    picks = [(pick.product_id, pick.units, pick.covers) for pick in result.picks]
    assert picks == [("CASE", 5, 50), ("CARTON", 50, 50)]


def test_short_stock_gives_a_partial_fill_that_states_what_is_missing() -> None:
    result = fill(Decimal(1000), [supply("A", "2.65", "698"), supply("B", "2.57", "51")])

    assert [(pick.product_id, pick.units) for pick in result.picks] == [("B", 51), ("A", 698)]
    assert result.covered == 749
    assert result.missing == 251
    assert result.requested == 1000


def test_no_supply_gives_an_empty_fill_with_everything_missing() -> None:
    result = fill(Decimal(30), [])

    assert result.picks == ()
    assert result.covered == 0
    assert result.missing == 30


def test_a_quantity_is_rounded_up_to_the_lot_step_and_the_cover_never_exceeds_the_request() -> None:
    # 1,000 L in cases of 3.75 L: 267 cases hold 1,001.25 L, and cover the 1,000 L asked for.
    result = fill(Decimal(1000), [supply("CASE", "10.71", "400", per_unit="3.75")])

    assert [(pick.units, pick.covers) for pick in result.picks] == [(267, 1000)]
    assert result.covered == 1000


def test_stock_off_the_lot_step_is_used_down_to_the_step() -> None:
    # 10 kg in stock with a 3 kg step: 9 kg can be ordered; the rest comes from the next product.
    result = fill(Decimal(30), [supply("A", "15.00", "10", step="3"), supply("B", "16.88", "20", step="3")])

    assert [(pick.product_id, pick.units, pick.covers) for pick in result.picks] == [("A", 9, 9), ("B", 18, 18)]
    assert result.missing == 3


def test_a_product_with_less_stock_than_one_lot_step_is_skipped() -> None:
    result = fill(Decimal(30), [supply("A", "15.00", "2", step="3"), supply("B", "16.88", "9", step="3")])

    assert [pick.product_id for pick in result.picks] == ["B"]
    assert result.missing == 21


def test_equal_prices_are_ordered_by_product_id() -> None:
    result = fill(Decimal(10), [supply("B", "1.00", "5"), supply("A", "1.00", "5")])

    assert [pick.product_id for pick in result.picks] == ["A", "B"]


@pytest.mark.parametrize(
    ("quantity", "step", "up", "down"),
    [("30", "3", "30", "30"), ("10", "3", "12", "9"), ("0.5", "1", "1", "0"), ("2.25", "0.01", "2.25", "2.25"),
     ("266.6667", "1", "267", "266"), ("4", "1.5", "4.5", "3.0")],
)
def test_rounding_to_a_step(quantity: str, step: str, up: str, down: str) -> None:
    assert ceil_to_step(Decimal(quantity), Decimal(step)) == Decimal(up)
    assert floor_to_step(Decimal(quantity), Decimal(step)) == Decimal(down)


def test_units_for_a_quantity_follow_the_pack_size_and_the_step() -> None:
    assert units_for(Decimal(200), supply("A", "1", "0", per_unit="0.5")) == 400
    assert units_for(Decimal(1000), supply("A", "1", "0", per_unit="3.75")) == 267
    assert units_for(Decimal(10), supply("A", "1", "0", step="3")) == 12


@pytest.mark.parametrize("product_id", ["469363", "464744", "466988", "463203"])
def test_rounding_up_agrees_with_the_catalog_rule(catalog: ProductCatalog, product_id: str) -> None:
    """The step is read from the catalog port; rounding with it must give what the port gives."""
    product = catalog.get_product(product_id)
    step = catalog.round_to_lot(product, Decimal("0.001"))

    for quantity in (Decimal("0.4"), Decimal(7), Decimal("29.5"), Decimal(30), Decimal("1000.01")):
        assert ceil_to_step(quantity, step) == catalog.round_to_lot(product, quantity)


def test_stock_that_equals_the_need_exactly_covers_alone() -> None:
    result = fill(Decimal(100), [supply("EXACT", "2.00", "100"), supply("CHEAP", "1.00", "99")])

    assert [(pick.product_id, pick.units) for pick in result.picks] == [("EXACT", 100)]


def test_the_last_product_of_a_combination_covers_no_more_than_what_was_still_missing() -> None:
    # 375 L from the cheap cases; the other 625 L need 167 cases of 3.75 L, which hold 626.25 L.
    result = fill(
        Decimal(1000),
        [supply("CHEAP", "9.00", "100", per_unit="3.75"), supply("DEAR", "10.71", "200", per_unit="3.75")],
    )

    assert [(pick.product_id, pick.units, pick.covers) for pick in result.picks] == [
        ("CHEAP", 100, 375), ("DEAR", 167, 625),
    ]
    assert result.covered == 1000
    assert result.missing == 0
