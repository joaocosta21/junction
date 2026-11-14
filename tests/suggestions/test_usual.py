"""The usual product for a product type, and the usual quantity of a product (P1 C4 and C5, kinds USUAL_PRODUCT
and USUAL_QUANTITY of P15 section 4.1).

The usual product: the product in the largest share of the last 8 orders that hold the type, from 3 such orders
and a share of 60%. Two products that alternate: no usual product, and the question which one. The usual quantity:
the median of the product's last 6 orders, from 3 orders. Both are suggestions: a person confirms them.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from tta.contracts.common import Unit
from tta.contracts.request import PurchaseRequest
from tta.contracts.suggestion import SuggestionKind
from tta.suggestions import (
    OrderHistory,
    usual_product,
    usual_product_question,
    usual_products_for_request,
    usual_quantity,
)

HOTEL_MILK = (100, 96, 104, 100, 98, 102, 100, 100)  # the hotel's 8 synthetic weeks, oldest first


def test_the_milk_in_every_one_of_the_last_8_milk_orders_is_the_usual_milk_at_its_median_quantity(
    make_history: Callable[..., OrderHistory],
) -> None:
    history = make_history([{"469363": litres} for litres in HOTEL_MILK])

    found = usual_product(history, "milk")

    assert found is not None
    assert (found.kind, found.product_id, found.quantity, found.unit) == (
        SuggestionKind.USUAL_PRODUCT, "469363", Decimal(100), Unit.L,
    )
    assert found.sentence == (
        "Your usual milk is Arla milk (469363): it is in 8 of your last 8 orders of milk. Confirm it before it is "
        "ordered. From a synthetic order history."
    )
    assert (found.evidence.orders_considered, found.evidence.orders_matching) == (8, 8)
    assert found.evidence.thresholds == {"USUAL_PRODUCT_MIN_ORDERS": 3, "USUAL_PRODUCT_MIN_SHARE": Decimal("0.6")}
    assert found.accept_request is None
    assert usual_product_question(history, "milk") is None


def test_two_milks_that_alternate_give_no_usual_milk_but_a_question(make_history: Callable[..., OrderHistory]) -> None:
    history = make_history([{"469363": 100}, {"463047": 100}] * 4)

    assert usual_product(history, "milk") is None
    assert usual_product_question(history, "milk") == (
        "Your last 8 orders of milk hold Arla milk (469363) 4 times and Arla whole milk (463047) 4 times. "
        "Which one do you mean?"
    )


def test_a_share_below_60_percent_is_no_usual_product(make_history: Callable[..., OrderHistory]) -> None:
    history = make_history([{"469363": 100}] * 4 + [{"463047": 100}] * 3)  # 4 of 7: 57%

    assert usual_product(history, "milk") is None
    assert usual_product_question(history, "milk") is not None


def test_exactly_60_percent_is_a_usual_product(make_history: Callable[..., OrderHistory]) -> None:
    history = make_history([{"463047": 100}] * 2 + [{"469363": 100}] * 3)  # 3 of 5

    found = usual_product(history, "milk")

    assert found is not None and found.product_id == "469363"


def test_fewer_than_3_orders_of_the_type_give_neither_a_usual_product_nor_a_question(
    make_history: Callable[..., OrderHistory],
) -> None:
    history = make_history([{"469363": 100}, {"469363": 100}, {"463797": 10}])

    assert usual_product(history, "milk") is None
    assert usual_product_question(history, "milk") is None
    assert usual_product(history, "plant_drink") is None


def test_a_type_only_line_is_offered_the_usual_product_and_accepting_pins_it(
    make_history: Callable[..., OrderHistory],
) -> None:
    history = make_history([{"469363": litres, "463797": 10} for litres in HOTEL_MILK])
    request = PurchaseRequest.model_validate({"needed_by": "2026-11-16", "lines": [
        {"text": "100 litres of lactose-free milk", "product_type": "milk", "required_claims": ["FREE_FROM_LACTOSE"],
         "quantity": 100, "unit": "L"},
        {"text": "10 litres of cream 463797", "product_ids": ["463797"], "quantity": 10, "unit": "L"},
    ]})

    suggestions = usual_products_for_request(history, request)

    assert len(suggestions) == 1
    found = suggestions[0]
    assert (found.request_line_index, found.product_id, found.quantity, found.unit) == (0, "469363", 100, Unit.L)
    assert found.sentence == (
        "This line names milk and no product. Your usual milk is Arla milk (469363): it is in 8 of your last 8 "
        "orders of milk. Confirm it before it is ordered. From a synthetic order history."
    )
    assert found.accept_request is not None
    pinned = found.accept_request.lines[0]
    assert pinned.product_ids == ("469363",)
    assert (pinned.product_type, pinned.required_claims) == ("milk", ("FREE_FROM_LACTOSE",))  # nothing widened
    assert found.accept_request.lines[1] == request.lines[1]


def test_a_type_only_line_with_no_usual_product_gets_no_suggestion(make_history: Callable[..., OrderHistory]) -> None:
    history = make_history([{"469363": 100}, {"463047": 100}] * 4)
    request = PurchaseRequest.model_validate(
        {"lines": [{"text": "100 litres of milk", "product_type": "milk", "quantity": 100, "unit": "L"}]}
    )

    assert usual_products_for_request(history, request) == ()


def test_the_usual_quantity_is_the_median_of_the_last_6_orders_with_their_range(
    make_history: Callable[..., OrderHistory],
) -> None:
    history = make_history([{"469363": litres} for litres in HOTEL_MILK])

    found = usual_quantity(history, "469363")

    assert found is not None
    assert (found.kind, found.product_id, found.quantity, found.unit) == (
        SuggestionKind.USUAL_QUANTITY, "469363", Decimal(100), Unit.L,
    )
    assert found.evidence.values == (104, 100, 98, 102, 100, 100)
    assert found.evidence.orders_considered == 6
    assert found.sentence == (
        "You usually order 100 L of Arla milk (469363): the median of your last 6 orders, which ranged from 98 to "
        "104 L. Confirm the quantity before it is ordered. From a synthetic order history."
    )


def test_three_orders_are_enough_for_a_usual_quantity_and_two_are_not(
    make_history: Callable[..., OrderHistory],
) -> None:
    assert usual_quantity(make_history([{"469363": 100}, {"469363": 96}]), "469363") is None
    found = usual_quantity(make_history([{"469363": 100}, {"469363": 96}, {"469363": 90}]), "469363")
    assert found is not None and found.quantity == Decimal(96)


def test_an_even_number_of_orders_takes_the_middle_two_and_rounds_to_three_decimals(
    make_history: Callable[..., OrderHistory],
) -> None:
    orders: list[dict[str, Any]] = [{"466988": kilos} for kilos in ("9.001", "9.002", "12", "6")]
    found = usual_quantity(make_history(orders), "466988")

    assert found is not None
    assert found.quantity == Decimal("9.002")  # 9.0015, half up
    assert found.unit is Unit.KG


def test_a_product_of_one_order_only_has_no_usual_quantity(make_history: Callable[..., OrderHistory]) -> None:
    assert usual_quantity(make_history([{"469363": 100}]), "463797") is None
