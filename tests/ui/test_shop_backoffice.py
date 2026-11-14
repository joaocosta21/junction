"""The shop's "Valio Aimo back office" route: Valio Aimo's figures of this browser's demo order books (lane BO).

Scores on the 30% demo (the figures come from the same request -> offer -> order flow the visitor just ran), on the
20% "autonomy and controls" (it reads Valio Aimo's view of the log and nothing of a customer's own) and on the 15%
"visibility of assumptions" (an empty book says so instead of showing zeros). Measured at the demo clock,
Thursday 12 Nov 2026 14:15 Helsinki.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings

API = "/shop/api"
CAPTURE = "2026-11-14-demo"
DEMO_CLOCK = "2026-11-12T14:15:00+02:00"
CUSTOMER_IDS = {"hotel": "hotel-kitchen", "bakery": "bakery-cafe"}
HOTEL_MILK = {"needed_by": "2026-11-16", "lines": [
    {"text": "100 L of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}]}
BAKERY_OAT = {"needed_by": "2026-11-17", "lines": [
    {"text": "30 L oat drink 468319", "product_ids": ["468319"], "quantity": 30, "unit": "L"}]}
NOTHING_YET = "Nothing has been ordered in this demonstration yet. Make a request as a customer, then come back."
DEMAND = (
    "3 requests came in through the agent channel and 3 offers went out. 2 orders were prepared: 1 confirmed by a "
    "person (€248.00 before tax), 0 placed by the agent alone, 1 waiting for a person (€44.40), 0 rejected and "
    "0 expired."
)


@pytest.fixture
def shop(tmp_path: Path, catalog: ProductCatalog) -> Iterator[TestClient]:
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_replay_capture=CAPTURE,
                                  tta_demo_clock=DEMO_CLOCK)
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        yield client


def _call(client: TestClient, method: str, path: str, kitchen: str = "hotel", **kwargs: Any) -> Any:
    return client.request(method, API + path, headers={"X-Shop-Request": "1", "X-Shop-Kitchen": kitchen}, **kwargs)


def _json(client: TestClient, method: str, path: str, kitchen: str, **kwargs: Any) -> Any:
    answer = _call(client, method, path, kitchen, **kwargs)
    assert answer.status_code == 200, answer.text
    return answer.json()


def _fill(client: TestClient, settings: dict[str, dict[str, Any]]) -> None:
    """As the hotel: 100 L of milk, ordered and confirmed by its purchasing manager. As the bakery: 30 L of oat
    drink, the cheaper product with the same formula switched to, ordered and left waiting."""
    for kitchen, customer_id in CUSTOMER_IDS.items():
        _json(client, "PUT", "/kitchen", kitchen, json=settings[customer_id])
    milk = _json(client, "POST", "/offers", "hotel", json=HOTEL_MILK)
    order = _json(client, "POST", "/orders", "hotel", json={
        "offer_id": milk["offer_id"], "option_id": milk["options"][0]["option_id"], "key": "bo-hotel"})
    _json(client, "POST", f"/approvals/{order['approval_id']}/decision", "hotel", json={
        "role": "purchasing_manager", "decision": {"decision": "APPROVE"}})
    oat = _json(client, "POST", "/offers", "bakery", json=BAKERY_OAT)
    cheaper = next(each for each in oat["suggestions"] if each["kind"] == "CHEAPER_SAME_FORMULA")
    switched = _json(client, "POST", "/offers", "bakery", json=cheaper["accept_request"])
    _json(client, "POST", "/orders", "bakery", json={
        "offer_id": switched["offer_id"], "option_id": switched["options"][0]["option_id"], "key": "bo-bakery"})


def test_a_browser_that_ordered_nothing_gets_the_empty_state_and_no_book_is_opened(shop: TestClient) -> None:
    books = len(shop.app.state.parts.sandboxes)  # type: ignore[attr-defined]

    found = _json(shop, "GET", "/backoffice", "hotel")

    assert found["empty"] is True and found["empty_sentence"] == NOTHING_YET
    assert len(shop.app.state.parts.sandboxes) == books  # type: ignore[attr-defined]


def test_the_figures_are_of_every_customer_of_this_browser_together_whichever_is_selected(
    shop: TestClient, shop_profile_settings: dict[str, dict[str, Any]],
) -> None:
    _fill(shop, shop_profile_settings)

    as_hotel = _json(shop, "GET", "/backoffice", "hotel")
    as_bakery = _json(shop, "GET", "/backoffice?period=all", "bakery")

    assert as_hotel["empty"] is False and as_hotel["demand"]["sentence"] == DEMAND
    assert (as_hotel["demand"]["confirmed_net_eur"], as_hotel["demand"]["waiting_net_eur"]) == (248.0, 44.4)
    found = as_hotel["suggestions"]
    assert (found["accepted"], found["ordered"], found["added_net_eur"], found["saved_net_eur"]) == (1, 0, 0.0, 42.0)
    assert as_hotel["missed"]["shortfalls"] == [] and "covered by confirmed stock" in as_hotel["missed"]["sentence"]
    assert all(as_bakery[block] == as_hotel[block] for block in ("demand", "suggestions", "missed"))


def test_nothing_of_a_customers_own_is_in_the_answer(
    shop: TestClient, shop_profile_settings: dict[str, dict[str, Any]],
) -> None:
    _fill(shop, shop_profile_settings)

    text = _call(shop, "GET", "/backoffice?period=all").text

    hotel = shop_profile_settings["hotel-kitchen"]
    for private in (hotel["display_name"], "max_order_net_eur", "excluded_allergens", "my-kitchen", "Demo approver",
                    HOTEL_MILK["lines"][0]["text"], BAKERY_OAT["lines"][0]["text"]):  # type: ignore[index]
        assert str(private) not in text, private


def test_another_browser_sees_nothing_of_it_and_the_route_answers_the_shop_page_only(
    shop: TestClient, shop_profile_settings: dict[str, dict[str, Any]],
) -> None:
    _fill(shop, shop_profile_settings)

    with TestClient(shop.app) as other:
        assert _json(other, "GET", "/backoffice", "hotel")["empty"] is True
    assert shop.get(API + "/backoffice").status_code == 403  # no X-Shop-Request header
    assert _call(shop, "GET", "/backoffice?period=yesterday").status_code == 422
