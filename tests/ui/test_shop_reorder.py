"""The shop's "you usually order this: order again?" prompt and its standing orders, through the app.

Scores on the 30% demo (the prompt's request runs request -> offer -> order -> approval like any other), on the 20%
"solving the problem and user need" (the regular order is ready-made from the customer's own history) and on the
20% "autonomy and controls" (the prompt orders nothing, never repeats a standing order's product or one already
ordered, and another customer's is never reachable). At both clocks: the recording's instant (Sat 14 Nov 2026
02:52) and the demo clock (Thu 12 Nov 2026 14:15).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.customers import shipped_customers

API = "/shop/api"
CAPTURE = "2026-11-14-demo"
DEMO_CLOCK = "2026-11-12T14:15:00+02:00"
_BASE = {"auto_order_enabled": False, "variable_weight": "APPROVAL", "deposits": "APPROVAL",
         "standing_order_drift_ratio": 0.25, "formula_matters": False, "max_preference_premium_ratio": None}
BAKERY = {**_BASE, "display_name": "Kallio Bakery", "max_order_net_eur": 300, "max_daily_net_eur": 1000,
          "min_fill_ratio": 1, "excluded_allergens": [], "allergen_strictness": None,
          "allergen_strictness_by_code": {}, "substitution_without_approval": "NONE", "require_confirmed": False,
          "formula_matters": True, "max_preference_premium_ratio": 0.1}
SCHOOL = {**_BASE, "display_name": "Kilo School", "max_order_net_eur": 250, "max_daily_net_eur": 800,
          "min_fill_ratio": 1, "excluded_allergens": ["AN", "AP", "AS"], "allergen_strictness": "STRICT",
          "allergen_strictness_by_code": {"AN": "STRICT", "AP": "STRICT", "AS": "STRICT"},
          "substitution_without_approval": "LISTED_BY_SUPPLIER", "require_confirmed": False}
BAKERY_SENTENCE = (
    "You ordered Oatly iKaffe 0,5L (468319), 30 L, in 4 of your last 4 weekly orders (8 of the last 8), and Arla "
    "Whipping cream 1 L ESL lactose free (464727), 10 L, in 3 of 4 (6 of 8), most recently on Tuesday 10 November. "
    "Order the same again for Tuesday 17 November? About €160.10 before tax at today's prices. Arla Pro Whipping "
    "cream 1 L UHT lactose free (469346) and Arla Cafè milk 1 L UHT lactose free (463380) are on your standing "
    "order, so they are not repeated here. From a synthetic order history."
)
Call = Callable[..., Any]


@pytest.fixture(params=["recording", "demo"])
def shop(request: pytest.FixtureRequest, tmp_path: Path, catalog: ProductCatalog) -> Iterator[TestClient]:
    """The whole gateway in replay at each of the two clocks, with a data directory of its own."""
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_replay_capture=CAPTURE,
                                  tta_demo_clock=None if request.param == "recording" else DEMO_CLOCK)
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        yield client


def _call(client: TestClient, method: str, path: str, kitchen: str = "bakery", **kwargs: Any) -> Any:
    return client.request(method, API + path, headers={"X-Shop-Request": "1", "X-Shop-Kitchen": kitchen}, **kwargs)


def test_the_bakerys_prompt_answers_before_the_page_sent_its_settings(shop: TestClient) -> None:
    answer = _call(shop, "GET", "/reorder")

    assert answer.status_code == 200
    prompt = answer.json()
    assert set(prompt) == {"customer_id", "lines", "sentence", "request", "needed_by", "total_net_eur", "synthetic",
                           "note", "why_not", "evidence"}
    assert prompt["customer_id"] == "bakery-cafe" and prompt["synthetic"] is True
    assert prompt["lines"] == [
        {"product_id": "468319", "name": "Oatly iKaffe 0,5L", "quantity": 30.0, "unit": "L", "orders_matching": 4,
         "orders_considered": 4, "last_ordered_on": "2026-11-10"},
        {"product_id": "464727", "name": "Arla Whipping cream 1 L ESL lactose free", "quantity": 10.0, "unit": "L",
         "orders_matching": 3, "orders_considered": 4, "last_ordered_on": "2026-11-10"},
    ]
    assert prompt["sentence"] == BAKERY_SENTENCE
    assert (prompt["needed_by"], prompt["total_net_eur"]) == ("2026-11-17", 160.1)
    assert len(prompt["why_not"]) == 2 and all("standing order" in why for why in prompt["why_not"])
    assert prompt["evidence"]["checked"] is True and prompt["evidence"]["prices_from"] == "replay"
    assert prompt["evidence"]["thresholds"]["REORDER_MIN_ORDERS"] == 3


def test_asking_for_the_prompt_orders_nothing(shop: TestClient) -> None:
    _call(shop, "GET", "/reorder")
    _call(shop, "GET", "/reorder")

    assert _call(shop, "GET", "/orders").json() == []
    assert _call(shop, "GET", "/approvals").json() == []


def test_the_ready_made_request_becomes_an_offer_a_person_confirms(shop: TestClient) -> None:
    prompt = _call(shop, "GET", "/reorder").json()
    assert _call(shop, "PUT", "/kitchen", json=BAKERY).status_code == 200

    answer = _call(shop, "POST", "/offers", json=prompt["request"])

    assert answer.status_code == 200, answer.text
    offer = answer.json()
    assert len(offer["options"]) == 1
    first = offer["options"][0]
    assert sorted(line["product_id"] for line in first["lines"]) == ["464727", "468319"]
    assert first["totals"]["net"] == prompt["total_net_eur"] == 160.1  # the prompt's total is the offer's
    assert [rule["rule_id"] for rule in first["decision"]["fired"]] == ["F-10"]  # under the €300 limit per order
    assert first["decision"]["required_roles"] == ["purchasing_manager"]
    assert not [note for note in offer["notes"] if "accepted" in note]  # the request names no suggestion


def test_a_limit_below_the_total_is_said_by_the_offer_not_by_the_prompt(shop: TestClient) -> None:
    prompt = _call(shop, "GET", "/reorder").json()
    _call(shop, "PUT", "/kitchen", json={**BAKERY, "max_order_net_eur": 100})

    first = _call(shop, "POST", "/offers", json=prompt["request"]).json()["options"][0]

    assert "P-01" in [rule["rule_id"] for rule in first["decision"]["fired"]]
    assert "limit" not in _call(shop, "GET", "/reorder").json()["sentence"]


def test_once_ordered_the_same_products_are_not_offered_again_for_that_date(shop: TestClient) -> None:
    prompt = _call(shop, "GET", "/reorder").json()
    _call(shop, "PUT", "/kitchen", json=BAKERY)
    offer = _call(shop, "POST", "/offers", json=prompt["request"]).json()
    order = _call(shop, "POST", "/orders", json={
        "offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"], "key": "test.reorder.1"}).json()
    assert order["status"] == "PENDING_APPROVAL"

    again = _call(shop, "GET", "/reorder").json()

    assert again["lines"] == [] and again["request"] is None and again["total_net_eur"] is None
    assert sum("already in an order placed or waiting for Tuesday 17 November" in why
               for why in again["why_not"]) == 2


@pytest.mark.parametrize(("kitchen", "lines", "needed_by", "total"), [
    ("hotel", [("463797", 10.0)], "2026-11-16", 33.1),
    ("school", [], None, None),
    ("ward", [], None, None),
])
def test_the_other_customers_prompts(shop: TestClient, kitchen: str, lines: list[Any], needed_by: str | None,
                                     total: float | None) -> None:
    prompt = _call(shop, "GET", "/reorder", kitchen).json()

    assert [(line["product_id"], line["quantity"]) for line in prompt["lines"]] == lines
    assert (prompt["needed_by"], prompt["total_net_eur"]) == (needed_by, total)
    assert (prompt["request"] is None) == (not lines)
    assert "on your standing order" in prompt["sentence"] and prompt["sentence"].endswith(
        "From a synthetic order history.")
    if not lines:
        assert prompt["sentence"].startswith("No order is suggested: every product you order regularly is on a "
                                             "standing order already.")


def test_a_customers_prompt_follows_the_settings_the_shop_sent(shop: TestClient) -> None:
    """The hotel's cooking cream holds milk: under settings that exclude milk it stays out, and the reason is said."""
    hotel = {**_BASE, "display_name": "Harbourside Hotel", "max_order_net_eur": 750, "max_daily_net_eur": 3000,
             "min_fill_ratio": 0.9, "excluded_allergens": ["AM"], "allergen_strictness": "STRICT",
             "allergen_strictness_by_code": {"AM": "STRICT"}, "substitution_without_approval": "SAME_CATEGORY",
             "require_confirmed": False}
    assert _call(shop, "PUT", "/kitchen", "hotel", json=hotel).status_code == 200

    prompt = _call(shop, "GET", "/reorder", "hotel").json()

    assert prompt["lines"] == [] and prompt["request"] is None
    why = next(each for each in prompt["why_not"] if "(463797)" in each)
    assert ", 10 L: " in why and why.endswith("So it is not in the ready-made request.")


def test_both_routes_are_behind_the_shops_guards(shop: TestClient) -> None:
    for path in ("/reorder", "/standing-orders"):
        assert shop.get(API + path, headers={"X-Shop-Kitchen": "bakery"}).status_code == 403, path
        cross = {"X-Shop-Request": "1", "X-Shop-Kitchen": "bakery", "Sec-Fetch-Site": "cross-site"}
        assert shop.get(API + path, headers=cross).status_code == 403, path
        assert shop.get(API + path, headers={"X-Shop-Request": "1"}).status_code == 400, path
        unknown = {"X-Shop-Request": "1", "X-Shop-Kitchen": "someone-else"}
        assert shop.get(API + path, headers=unknown).status_code == 400, path  # no other customer is reachable
        assert shop.get(API + path + "?customer_id=hotel-kitchen",
                        headers={"X-Shop-Request": "1", "X-Shop-Kitchen": "bakery"}).json()["customer_id"] == (
            "bakery-cafe"), path


def test_the_standing_orders_are_the_customer_files_with_synthetic_past_orders(shop: TestClient) -> None:
    for kitchen, customer_id in (("school", "school-kitchen"), ("ward", "allergy-ward"), ("hotel", "hotel-kitchen"),
                                 ("bakery", "bakery-cafe")):
        answer = _call(shop, "GET", "/standing-orders", kitchen)

        assert answer.status_code == 200, answer.text
        body, customer = answer.json(), shipped_customers()[customer_id]
        assert body["customer_id"] == customer_id and body["synthetic"] is True
        assert [(one["standing_order_id"], one["name"], one["cadence_days"]) for one in body["standing_orders"]] == [
            (entry.standing_order_id, entry.name, entry.cadence_days) for entry in customer.standing_orders]
        for one in body["standing_orders"]:
            assert one["past_orders"] and all(past["synthetic"] is True for past in one["past_orders"])
            assert all(line["name"] and line["unit"] in ("L", "KG", "UNIT") for line in one["lines"])


def test_the_schools_oat_drink_has_a_trend_and_the_others_have_none(shop: TestClient) -> None:
    school = _call(shop, "GET", "/standing-orders", "school").json()["standing_orders"][0]

    trend = school["trend"]
    assert set(trend) == {"product_id", "sentence", "suggested_quantity", "unit", "accept_request"}
    assert (trend["product_id"], trend["suggested_quantity"], trend["unit"]) == ("470863", 84.0, "L")
    assert "a median of 84 L against 70 L for the 3 before (+20%)" in trend["sentence"]
    assert "The standing order still says 60 L." in trend["sentence"]
    assert [line["quantity"] for line in trend["accept_request"]["lines"]] == [120.0, 84.0, 20.0]
    for kitchen in ("ward", "hotel", "bakery"):
        orders = _call(shop, "GET", "/standing-orders", kitchen).json()["standing_orders"]
        assert [one["trend"] for one in orders] == [None], kitchen


def test_renew_once_at_the_trends_quantity_is_an_offer_prepared_and_judged_like_any_renewal(shop: TestClient) -> None:
    trend = _call(shop, "GET", "/standing-orders", "school").json()["standing_orders"][0]["trend"]
    assert trend["accept_request"]["standing_order_id"] == "so_school_weekly"
    assert _call(shop, "PUT", "/kitchen", "school", json=SCHOOL).status_code == 200

    answer = _call(shop, "POST", "/offers", "school", json=trend["accept_request"])

    assert answer.status_code == 200, answer.text
    options = answer.json()["options"]
    assert options and all(option["decision"]["verdict"] == "APPROVAL" for option in options)  # a person confirms
    fired = [rule["rule_id"] for option in options for rule in option["decision"]["fired"]]
    assert "P-08" not in fired  # 84 L of oat drink against a median of 77 L: within the school's 25%
    assert ("470863", 84.0) in [(line["product_id"], line["quantity"]) for line in options[0]["lines"]]
    assert _call(shop, "GET", "/orders", "school").json() == []  # an offer, never an order


def test_a_renewal_far_from_its_history_is_flagged_in_the_shops_book(shop: TestClient) -> None:
    """The book holds the customer's past renewals, so rule P-08 judges a renewal sent from the shop."""
    trend = _call(shop, "GET", "/standing-orders", "school").json()["standing_orders"][0]["trend"]
    _call(shop, "PUT", "/kitchen", "school", json=SCHOOL)
    lines = [{**line, "quantity": 300} if line["product_ids"] == ["470863"] else line
             for line in trend["accept_request"]["lines"]]

    answer = _call(shop, "POST", "/offers", "school", json={**trend["accept_request"], "lines": lines})

    assert answer.status_code == 200, answer.text
    assert "P-08" in [rule["rule_id"] for rule in answer.json()["options"][0]["decision"]["fired"]]


def test_each_shop_book_holds_its_own_customers_standing_orders_once(shop: TestClient) -> None:
    for _ in range(2):
        assert _call(shop, "GET", "/standing-orders", "school").status_code == 200
        assert _call(shop, "GET", "/standing-orders", "bakery").status_code == 200
    bakery = {**BAKERY, "max_order_net_eur": 1000}
    _call(shop, "PUT", "/kitchen", "bakery", json=bakery)
    renewal = {"standing_order_id": "so_bakery_weekly", "lines": [
        {"text": "40 L", "product_ids": ["469346"], "quantity": 40, "unit": "L"},
        {"text": "60 L", "product_ids": ["463380"], "quantity": 60, "unit": "L"}]}

    assert _call(shop, "POST", "/offers", "bakery", json=renewal).status_code == 200
    other = _call(shop, "POST", "/offers", "bakery", json={**renewal, "standing_order_id": "so_school_weekly"})
    assert other.status_code == 422  # another customer's standing order is not in this book


def test_the_customer_view_names_each_usual_product(shop: TestClient) -> None:
    view = _call(shop, "GET", "/customer", "bakery").json()

    assert {usual["product_id"]: usual["name"] for usual in view["customer"]["usual"]} == {
        "469346": "Arla Pro Whipping cream 1 L UHT lactose free", "464727": "Arla Whipping cream 1 L ESL lactose free",
        "463380": "Arla Cafè milk 1 L UHT lactose free", "468319": "Oatly iKaffe 0,5L"}
    assert view["limits"]["max_order_net_eur"] == 300 and view["synthetic"] is True
