"""The orders one buyer's suggestions are computed from (P15 R2, `history.py`)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from tta.contracts.common import Unit
from tta.contracts.suggestion import EvidenceSource
from tta.customers import shipped_customer
from tta.suggestions import OrderHistory, history_of


def test_a_customer_files_history_is_synthetic_oldest_first_and_knows_each_products_type_and_unit() -> None:
    hotel = shipped_customer("hotel-kitchen")
    assert hotel is not None

    history = history_of(hotel)

    assert history.customer_id == "hotel-kitchen"
    assert history.synthetic is True
    assert history.source is EvidenceSource.SYNTHETIC_HISTORY
    assert [order.delivered_on for order in history.orders] == sorted(order.delivered_on for order in history.orders)
    assert history.type_of("469363") == "milk"
    assert history.unit_of("466988") is Unit.KG
    assert history.type_of("000000") is None
    assert history.unit_of("000000") is None


def test_the_last_orders_are_the_newest_ones(make_history: Callable[..., OrderHistory]) -> None:
    history = make_history([{"469363": litres} for litres in (90, 100, 110)])

    last_two = history.last(2)

    assert [order.quantities["469363"] for order in last_two] == [100, 110]
    assert history.last(0) == ()
    assert history.last(10) == history.orders


def test_a_name_comes_from_the_names_given_else_the_product_id_is_said(
    make_history: Callable[..., OrderHistory],
) -> None:
    history = make_history([{"469363": 100}], names={"469363": "Arla milk"})

    assert history.name_of("469363") == "Arla milk"
    assert history.name_of("463797") == "product 463797"


def test_the_orders_of_one_product_are_counted_across_the_whole_history(
    make_history: Callable[..., OrderHistory],
) -> None:
    history = make_history([{"469363": 100}, {"463797": 10}, {"469363": 96, "463797": 12}])

    orders = history.orders_with("463797")

    assert [order.delivered_on for order in orders] == [date(2026, 9, 28), date(2026, 10, 5)]
