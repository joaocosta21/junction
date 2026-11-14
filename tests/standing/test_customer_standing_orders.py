"""The demonstration's standing orders built from the customer files (P1 C3): all four customers, stable ids, a
renewal per past order, the recording's price where a past order states none."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import Identity, IdentityKind, Unit
from tta.contracts.customer import Customer
from tta.contracts.errors import NotAuthorised, SupplierUnavailable
from tta.contracts.standing import RenewStandingOrder
from tta.customers import shipped_customer, shipped_customers
from tta.standing import standing_history
from tta.standing.demo import (
    DEMO_LITRES,
    DEMO_NAME,
    DEMO_PRODUCT_ID,
    DEMO_STANDING_ORDER_ID,
    SYNTHETIC_WEEKS,
    demo_request,
    load_customer_standing_orders,
    load_demo,
    past_renewals,
    standing_request,
)

NOW = datetime.fromisoformat("2026-11-14T02:52:00+02:00")
# customer: (standing order id, lines as (product, quantity, unit), past renewals)
EXPECTED = {
    "hotel-kitchen": ("so_demo_hotel_milk", [("469363", 100, Unit.L)], 8),
    "allergy-ward": ("so_ward_plant_drinks", [("464013", 200, Unit.L), ("473424", 20, Unit.L)], 16),
    "school-kitchen": ("so_school_weekly", [("462775", 120, Unit.L), ("470863", 60, Unit.L),
                                            ("464517", 20, Unit.KG)], 8),
    "bakery-cafe": ("so_bakery_weekly", [("469346", 40, Unit.L), ("463380", 60, Unit.L)], 8),
}


def _agent(customer_id: str) -> Identity:
    return Identity(kind=IdentityKind.AGENT, id=f"agent:{customer_id}", display_name="Test agent",
                    profile_id=customer_id)


@pytest.mark.parametrize("customer_id", sorted(EXPECTED))
def test_each_customers_standing_order_is_set_up_from_its_file_with_its_past_orders_as_renewals(
    customer_id: str, book: Any,
) -> None:
    standing_order_id, lines, renewals = EXPECTED[customer_id]
    agent, customer = _agent(customer_id), shipped_customer(customer_id)

    (standing,) = load_customer_standing_orders(book.standing, agent, book.replay)

    assert (standing.standing_order_id, standing.profile_id, standing.name) == (
        standing_order_id, customer_id, customer.standing_orders[0].name,
    )
    assert [(line.product_ids, line.quantity, line.unit) for line in standing.request.lines] == [
        ((product_id,), Decimal(quantity), unit) for product_id, quantity, unit in lines
    ]
    detail = book.standing.get(agent, standing_order_id)
    assert len(detail.renewals) == renewals
    assert all(renewal.synthetic and renewal.order_id is None for renewal in detail.renewals)
    assert [renewal.renewed_at.date() for renewal in detail.renewals] == [
        order.delivered_on for order in customer.history
    ]
    assert load_customer_standing_orders(book.standing, agent, book.replay) == (standing,)  # once only


def test_a_renewal_holds_only_the_stored_products_the_past_order_held(book: Any) -> None:
    agent = _agent("allergy-ward")
    load_customer_standing_orders(book.standing, agent, book.replay)

    renewals = book.standing.get(agent, "so_ward_plant_drinks").renewals

    without_rice = [renewal for renewal in renewals if len(renewal.lines) == 1]
    assert len(without_rice) == 2  # 28 September and 22 October hold no rice drink
    assert all(renewal.lines[0].product_id == "464013" for renewal in without_rice)
    assert {(line.request_line_index, line.product_id) for renewal in renewals for line in renewal.lines} == {
        (0, "464013"), (1, "473424"),
    }


def test_the_hotels_order_keeps_its_id_and_its_median_of_100_litres(book: Any, agent_hotel: Identity) -> None:
    standing = load_demo(book.standing, agent_hotel, book.replay)

    assert (standing.standing_order_id, standing.name) == (DEMO_STANDING_ORDER_ID, DEMO_NAME)
    constants = (DEMO_STANDING_ORDER_ID, DEMO_PRODUCT_ID, DEMO_LITRES)
    assert constants == ("so_demo_hotel_milk", "469363", Decimal(100))
    weeks = list(SYNTHETIC_WEEKS)
    assert weeks == [Decimal(litres) for litres in (100, 96, 104, 100, 98, 102, 100, 100)]
    assert standing.request == demo_request()
    history = standing_history(book.store, "hotel-kitchen", DEMO_STANDING_ORDER_ID)
    assert [renewal.lines[0].quantity for renewal in history.renewals] == list(SYNTHETIC_WEEKS)
    usual = book.standing.renew(agent_hotel, DEMO_STANDING_ORDER_ID, RenewStandingOrder())
    assert "against a median of 100 L over the last 6 renewals" in usual.sentence


def test_a_past_order_without_a_price_takes_the_recordings_and_one_with_a_price_keeps_its_own() -> None:
    """The bakery paid €6.90 for 464727 in four older weeks; the two newest orders state no price."""
    bakery = shipped_customer("bakery-cafe")
    with_the_cream = Customer.model_validate({
        **bakery.model_dump(),
        "standing_orders": [{"standing_order_id": "so_test_cream", "name": "Whipping cream",
                             "lines": [{"product_id": "464727", "quantity": 10}]}],
    })

    renewals = past_renewals(with_the_cream, with_the_cream.standing_orders[0], {"464727": Decimal("7.37")}, NOW)

    assert [(renewal.renewed_at.date(), renewal.lines[0].unit_net_price_eur) for renewal in renewals] == [
        (date(2026, 9, 22), Decimal("6.90")), (date(2026, 9, 29), Decimal("6.90")),
        (date(2026, 10, 6), Decimal("6.90")), (date(2026, 10, 20), Decimal("6.90")),
        (date(2026, 11, 3), Decimal("7.37")), (date(2026, 11, 10), Decimal("7.37")),
    ]
    assert [renewal.renewal_id for renewal in renewals] == [f"ren_test_cream_{number}" for number in range(1, 7)]


def test_an_order_delivered_after_the_clock_is_not_a_past_renewal() -> None:
    hotel = shipped_customer("hotel-kitchen")
    early = datetime.fromisoformat("2026-10-20T09:00:00+03:00")

    renewals = past_renewals(hotel, hotel.standing_orders[0], {"469363": Decimal("2.48")}, early)

    assert [renewal.renewed_at.date() for renewal in renewals] == [
        date(2026, 9, 21), date(2026, 9, 28), date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 19),
    ]


def test_the_request_of_a_standing_order_says_each_line_in_plain_words() -> None:
    ward = shipped_customer("allergy-ward")

    request = standing_request(ward, ward.standing_orders[0])

    assert [line.text for line in request.lines] == [
        "200 litres of product 464013, every 3 days", "20 litres of product 473424, every 3 days",
    ]
    assert request.standing_order_id is None


def test_a_buyer_without_a_customer_file_gets_no_standing_order_and_another_buyers_agent_is_refused(
    book: Any, agent_hotel: Identity,
) -> None:
    nobody = Identity(kind=IdentityKind.AGENT, id="agent:x", display_name="x", profile_id="no-such-customer")

    assert load_customer_standing_orders(book.standing, nobody, book.replay) == ()
    with pytest.raises(NotAuthorised):
        load_customer_standing_orders(book.standing, agent_hotel, book.replay, shipped_customer("allergy-ward"))


def test_a_recording_without_the_products_price_sets_nothing_up(book: Any, agent_hotel: Identity) -> None:
    class NoPrices:
        def price(self, product_ids: Any, *, fresh: bool = False) -> Any:
            return book.replay.price(["0000000"])

    with pytest.raises(SupplierUnavailable, match="holds no price for product 469363"):
        load_demo(book.standing, agent_hotel, NoPrices())
    assert book.standing.list(agent_hotel) == ()


def test_every_shipped_customer_has_a_standing_order_in_its_file() -> None:
    assert {customer_id: [each.standing_order_id for each in customer.standing_orders]
            for customer_id, customer in shipped_customers().items()} == {
        customer_id: [expected[0]] for customer_id, expected in EXPECTED.items()
    }
