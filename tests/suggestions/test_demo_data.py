"""The shipped customer files meet each threshold a demo moment needs (P15 R1 and section 4.6).

So that a demo moment cannot go quiet after an edit of the data: the hotel's cream with its milk, the yoghurt that
stays silent, the ward's rice drink with its soya drink, the usual products and quantities, the school's rising oat
drink, the bakery's whipping cream. Every figure comes from a synthetic history written for the demonstration.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import Unit
from tta.contracts.request import PurchaseRequest
from tta.customers import shipped_customer, shipped_customers
from tta.suggestions import (
    OrderHistory,
    forgotten_items,
    history_of,
    quantity_trend,
    usual_product,
    usual_product_question,
    usual_quantity,
)
from tta.suggestions.thresholds import USUAL_QUANTITY_WINDOW

# The drift tolerance the shop page sends for every kitchen (BASE_SETTINGS in kitchens.js): ours, until the school's
# profile file states its own (P1 C1, another lane).
SCHOOL_TOLERANCE = Decimal("0.25")
# The one standing-order line whose stored quantity is not the median of its history, on purpose (P15 section 4.6,
# item 4): the school stores 60 L of oat drink under a rising series.
RISING_LINE = ("school-kitchen", "470863")


def _history(customer_id: str) -> OrderHistory:
    customer = shipped_customer(customer_id)
    assert customer is not None
    return history_of(customer)


def _request(product_id: str, quantity: int, unit: str = "L") -> PurchaseRequest:
    line: dict[str, Any] = {"text": f"{quantity} {unit} of {product_id}", "product_ids": [product_id],
                            "quantity": quantity, "unit": unit}
    return PurchaseRequest.model_validate({"needed_by": "2026-11-16", "lines": [line]})


def test_the_hotel_asking_for_its_milk_is_reminded_of_10_litres_of_cooking_cream_in_7_of_8_orders() -> None:
    suggestions = forgotten_items(_history("hotel-kitchen"), _request("469363", 100))

    assert [(found.product_id, found.quantity, found.unit) for found in suggestions] == [("463797", 10, Unit.L)]
    evidence = suggestions[0].evidence
    assert (evidence.orders_matching, evidence.orders_considered, evidence.synthetic) == (7, 8, True)


def test_the_hotels_yoghurt_in_3_of_8_orders_stays_silent() -> None:
    history = _history("hotel-kitchen")
    with_yoghurt = [order for order in history.last(8) if "464615" in order.quantities]

    assert len(with_yoghurt) == 3
    assert "464615" not in [found.product_id for found in forgotten_items(history, _request("469363", 100))]


def test_the_ward_asking_for_its_soya_drink_is_reminded_of_20_litres_of_rice_drink_in_7_of_8_orders() -> None:
    suggestions = forgotten_items(_history("allergy-ward"), _request("464013", 200))

    assert [(found.product_id, found.quantity) for found in suggestions] == [("473424", 20)]
    assert (suggestions[0].evidence.orders_matching, suggestions[0].evidence.orders_considered) == (7, 8)


@pytest.mark.parametrize(
    ("customer_id", "product_type", "product_id", "quantity"),
    [
        ("hotel-kitchen", "milk", "469363", 100),
        ("hotel-kitchen", "cream", "463797", 10),
        ("allergy-ward", "plant_drink", "464013", 200),
        ("school-kitchen", "milk", "462775", 120),
        ("school-kitchen", "yoghurt", "464517", 20),
        ("bakery-cafe", "cream", "469346", 40),
        ("bakery-cafe", "coffee_milk", "463380", 60),
        ("bakery-cafe", "plant_drink", "468319", 30),
    ],
)
def test_each_customers_usual_product_and_quantity(customer_id: str, product_type: str, product_id: str,
                                                   quantity: int) -> None:
    history = _history(customer_id)

    found = usual_product(history, product_type)
    usual = usual_quantity(history, product_id)

    assert found is not None and found.product_id == product_id
    assert usual is not None and usual.quantity == Decimal(quantity)
    assert usual_product_question(history, product_type) is None


def test_the_schools_oat_drink_has_grown_by_a_fifth_over_its_stored_60_litres() -> None:
    customer = shipped_customer("school-kitchen")
    assert customer is not None
    standing = customer.standing_orders[0]
    stored = next(line.quantity for line in standing.lines if line.product_id == "470863")

    found = quantity_trend(history_of(customer), "470863", standing_order_id=standing.standing_order_id,
                           stored_quantity=stored, tolerance=SCHOOL_TOLERANCE)

    assert stored == Decimal(60)
    assert found is not None
    assert found.quantity == Decimal(84)
    assert "are growing: about 84 L in your last 3 orders, 70 L in the 3 before." in found.sentence


def test_no_other_usual_product_shows_a_trend() -> None:
    for customer in shipped_customers().values():
        history = history_of(customer)
        for usual in customer.usual:
            if (customer.customer_id, usual.product_id) == RISING_LINE:
                continue
            found = quantity_trend(history, usual.product_id, standing_order_id="so_any",
                                   stored_quantity=Decimal(1), tolerance=None)
            assert found is None, (customer.customer_id, usual.product_id)


def test_each_standing_order_stores_the_median_of_its_lines_history_but_the_schools_rising_oat_drink() -> None:
    for customer in shipped_customers().values():
        history = history_of(customer)
        for standing in customer.standing_orders:
            for line in standing.lines:
                usual = usual_quantity(history, line.product_id)
                assert usual is not None
                assert len(usual.evidence.values) == USUAL_QUANTITY_WINDOW
                if (customer.customer_id, line.product_id) == RISING_LINE:
                    assert line.quantity < usual.quantity
                else:
                    assert line.quantity == usual.quantity, (customer.customer_id, line.product_id)


def test_the_hotels_standing_order_is_the_demonstrations_weekly_milk() -> None:
    hotel = shipped_customer("hotel-kitchen")
    assert hotel is not None

    standing = hotel.standing_orders[0]

    assert (standing.standing_order_id, standing.cadence_days) == ("so_demo_hotel_milk", 7)
    assert [(line.product_id, line.quantity) for line in standing.lines] == [("469363", Decimal(100))]
