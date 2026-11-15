"""The published texts say what the gateway does since B0: ordering alone is a buyer setting, off by default.

Scores on the 20% "what the agent can decide alone, what needs human sign-off" and the 15% "clear visibility of
assumptions". After B0 the OpenAPI description still said every verdict is `APPROVAL` or `BLOCK` and every
order waits for a person; with the setting on, `AUTO` and `ORDERED` come back (`tests/api/test_ordering_alone.py`).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings

UNTRUE_SINCE_B0 = ("(`APPROVAL` or `BLOCK`)", "Every eligible order waits", "for human approval")


@pytest.fixture(scope="module")
def document(catalog: ProductCatalog, tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    settings = Settings.for_tests(tta_data_dir=tmp_path_factory.mktemp("texts") / "var")
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        yield client.get("/openapi.json").json()


def test_the_description_names_the_three_verdicts_and_the_setting_that_allows_the_first(
    document: dict[str, Any],
) -> None:
    description = " ".join(document["info"]["description"].split())  # the text as read, without line breaks

    for phrase in ("`AUTO`", "`APPROVAL`", "`BLOCK`", "auto_order_enabled", "off by default", "F-10",
                   "every statement", "`placed_by: AGENT`", "`PENDING_APPROVAL`"):
        assert phrase in description, phrase
    for untrue in UNTRUE_SINCE_B0:
        assert untrue not in description, untrue


def test_placing_an_order_says_when_it_is_ordered_alone_and_when_it_waits(document: dict[str, Any]) -> None:
    operation = document["paths"]["/v1/orders"]["post"]
    text = " ".join(f"{operation['summary']} {operation['description']}".split())

    for phrase in ("`AUTO`", "`ORDERED`", "`PENDING_APPROVAL`", "`BLOCK`", "off in every shipped profile"):
        assert phrase in text, phrase
    for untrue in UNTRUE_SINCE_B0:
        assert untrue not in text, untrue


def test_the_two_orders_the_texts_quote_are_what_the_hotel_gets_with_ordering_alone_on(
    catalog: ProductCatalog, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Decision B57, its fallback: `/llms.txt` and the OpenAPI description say where ordering alone is shown, with
    302 and 303 litres at Harbourside Hotel. Measured here at the recording's clock and, on 15 Nov, at the demo
    clock (Thu 12 Nov 2026 14:15): the same two answers."""
    from decimal import Decimal

    from tta.api import discovery
    from tta.api.sandbox import KITCHEN_AGENT, KITCHEN_SETTINGS, file_profile
    from tta.contracts.common import OrderStatus, PlacedBy
    from tta.contracts.request import PurchaseRequest

    settings = Settings.for_tests(tta_data_dir=tmp_path_factory.mktemp("alone") / "var")
    parts = build_parts(settings, catalog=catalog)
    hotel = file_profile("hotel-kitchen").model_dump(include=set(KITCHEN_SETTINGS))
    found = []
    try:
        for litres in (discovery.ALONE_LITRES, discovery.TO_A_PERSON_LITRES):
            book = parts.sandboxes.open(f"browser-{litres}.hotel-kitchen")
            book.customer.name("hotel-kitchen")
            book.kitchen.set_up({**hotel, "auto_order_enabled": True})
            offer = book.service.create_offer(KITCHEN_AGENT, PurchaseRequest.model_validate({
                "needed_by": "2026-11-16",
                "lines": [{"text": f"{litres} litres of lactose-free milk by Monday", "product_type": "milk",
                           "required_claims": ["FREE_FROM_LACTOSE"], "quantity": litres, "unit": "L"}],
            }))
            order = book.service.place_order(KITCHEN_AGENT, offer.offer_id, offer.options[0].option_id, "k-1")
            found.append((order.option.totals.net, order.status, order.placed_by, order.decision.rule_ids))
    finally:
        parts.close()

    assert found == [
        (Decimal(discovery.ALONE_NET), OrderStatus.ORDERED, PlacedBy.AGENT, ()),
        (Decimal(discovery.TO_A_PERSON_NET), OrderStatus.PENDING_APPROVAL, None, ("P-01",)),
    ]
    assert (discovery.ALONE_LITRES, discovery.ALONE_NET) == (302, "748.96")
    assert (discovery.TO_A_PERSON_LITRES, discovery.TO_A_PERSON_NET) == (303, "751.44")
    assert file_profile("hotel-kitchen").max_order_net_eur == Decimal(discovery.HOTEL_ORDER_LIMIT)
