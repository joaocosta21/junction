"""Filling with a preference (task SUST-1): confirmed products by the buyer's key first, then by price.

Pure arithmetic. A `tier` is the rank of a product's value for the key, 0 the best; a product with no value has
the last tier. Under price every product has tier 0 and the fill is the one SPEC section 5 describes.
"""

from __future__ import annotations

from decimal import Decimal

from tta.offers.combining import Supply, fill


def supply(product_id: str, price: str, usable: str, tier: int = 0) -> Supply:
    return Supply(
        product_id=product_id, per_unit=Decimal(1), unit_price=Decimal(price), usable=Decimal(usable),
        lot_step=Decimal(1), tier=tier,
    )


def picks(result: object) -> list[tuple[str, Decimal]]:
    return [(pick.product_id, pick.units) for pick in result.picks]  # type: ignore[attr-defined]


def test_the_best_tier_wins_over_a_cheaper_product_that_covers_alone() -> None:
    result = fill(Decimal(100), [supply("CHEAP", "1.33", "131", tier=1), supply("RELIABLE", "1.40", "1414")])

    assert picks(result) == [("RELIABLE", 100)]


def test_within_a_tier_the_cheapest_that_covers_alone_wins() -> None:
    result = fill(
        Decimal(100), [supply("B", "2.00", "500"), supply("A", "1.50", "500"), supply("WORSE", "1.00", "500", tier=1)]
    )

    assert picks(result) == [("A", 100)]


def test_products_of_the_best_tiers_are_combined_before_a_worse_product_covers_alone() -> None:
    result = fill(
        Decimal(100),
        [supply("BEST_1", "2.00", "60"), supply("BEST_2", "2.10", "60"), supply("WORSE", "1.00", "500", tier=1)],
    )

    assert picks(result) == [("BEST_1", 60), ("BEST_2", 40)]


def test_a_worse_tier_is_used_only_when_the_better_ones_cannot_cover() -> None:
    result = fill(Decimal(100), [supply("BEST", "2.00", "30"), supply("SECOND", "3.00", "200", tier=1)])

    assert picks(result) == [("SECOND", 100)]


def test_combining_keeps_the_order_of_the_key_then_the_price() -> None:
    result = fill(
        Decimal(100),
        [supply("BEST", "3.00", "30"), supply("SECOND", "2.00", "30", tier=1), supply("LAST", "1.00", "60", tier=2)],
    )

    assert picks(result) == [("BEST", 30), ("SECOND", 30), ("LAST", 40)]


def test_a_partial_fill_takes_every_tier_in_order() -> None:
    result = fill(Decimal(100), [supply("LAST", "1.00", "20", tier=1), supply("BEST", "5.00", "10")])

    assert picks(result) == [("BEST", 10), ("LAST", 20)]
    assert result.missing == 70


def test_one_tier_is_the_price_fill() -> None:
    supplies = [supply("A", "2.00", "60"), supply("B", "1.00", "60")]

    result = fill(Decimal(100), supplies)

    assert picks(result) == [("B", 60), ("A", 40)]


def test_no_supply_is_an_empty_fill() -> None:
    result = fill(Decimal(30), [])

    assert result.picks == ()
    assert result.missing == 30
