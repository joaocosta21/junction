"""Valio Aimo's own related product (P15 R11) before the guard, and the trend of a standing order's lines (P15 R7)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.contracts.suggestion import EvidenceSource, Serves, SuggestionKind
from tta.customers import shipped_customer, shipped_customers
from tta.suggestions import history_of, standing_order_trends
from tta.suggestions.supplier import related_products
from tta.suggestions.thresholds import SUPPLIER_MAX_POOL
from tta.suggestions.trend import RENEWS_ONCE

SCHOOL = "school-kitchen"


def test_every_related_product_is_of_the_same_type_and_brand_as_a_usual_one_and_was_never_ordered(
    world_now: Any,
) -> None:
    for customer in shipped_customers().values():
        request = world_now.request({"text": "x", "product_ids": [customer.usual[0].product_id], "quantity": 1,
                                     "unit": customer.usual[0].unit.value})
        known = {usual.product_id for usual in customer.usual}

        found = related_products(customer, history_of(customer), request, known, world_now.catalog)

        assert 0 < len(found) <= SUPPLIER_MAX_POOL, customer.customer_id
        for each in found:
            product = world_now.catalog.get_product(each.suggestion.product_id)
            anchor = world_now.catalog.get_product(each.anchor_id)
            assert product.id not in known and product.brand == anchor.brand and product.brand
            assert (each.suggestion.kind, each.suggestion.serves, each.suggestion.evidence.source) == (
                SuggestionKind.FROM_SUPPLIER, Serves.SUPPLIER, EvidenceSource.SUPPLIER,
            )
            assert each.suggestion.evidence.orders_matching == 0
            assert each.suggestion.accept_request.lines[-1].product_ids == (product.id,)


def test_the_product_of_the_request_is_the_first_anchor(world_now: Any) -> None:
    school = shipped_customer(SCHOOL)
    request = world_now.request({"text": "oat", "product_ids": ["470863"], "quantity": 60, "unit": "L"})

    found = related_products(school, history_of(school), request, ("470863",), world_now.catalog)

    assert found[0].anchor_id == "470863"
    assert world_now.catalog.get_product(found[0].suggestion.product_id).brand == "Oatly"


def test_a_full_request_gets_no_related_product(world_now: Any) -> None:
    hotel = shipped_customer("hotel-kitchen")
    line = {"text": "milk", "product_ids": ["469363"], "quantity": 1, "unit": "L"}
    request = world_now.request(*[line] * 20)

    assert related_products(hotel, history_of(hotel), request, ("469363",), world_now.catalog) == ()


def test_the_schools_standing_order_shows_the_oat_drinks_trend_and_no_other_line(world_now: Any) -> None:
    school = shipped_customer(SCHOOL)
    (standing,) = world_now.standing_orders(SCHOOL)
    tolerance = world_now.profile(SCHOOL).standing_order_drift_ratio

    (trend,) = standing_order_trends(history_of(school), standing, tolerance=tolerance)

    assert (trend.product_id, trend.quantity, trend.standing_order_id, trend.request_line_index) == (
        "470863", Decimal(84), "so_school_weekly", 1,
    )
    assert "a median of 84 L against 70 L" in trend.sentence and "The standing order still says 60 L." in trend.sentence
    assert trend.checks == (RENEWS_ONCE,)
    renewal = trend.accept_request
    assert renewal.standing_order_id == "so_school_weekly"
    assert [line.quantity for line in renewal.lines] == [Decimal(120), Decimal(84), Decimal(20)]
    assert standing.request.lines[1].quantity == Decimal(60)  # the stored quantity is not changed


def test_no_other_customers_standing_order_shows_a_trend(world_now: Any) -> None:
    for customer in shipped_customers().values():
        if customer.customer_id == SCHOOL:
            continue
        for standing in world_now.standing_orders(customer.customer_id):
            tolerance = world_now.profile(customer.customer_id).standing_order_drift_ratio
            assert standing_order_trends(history_of(customer), standing, tolerance=tolerance) == ()
