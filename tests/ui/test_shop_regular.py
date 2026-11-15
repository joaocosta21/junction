"""The shop's "this is one of your regular orders" alert and the standing order set up from it, through the app.

Scores on the 30% demo (the alert sits on a real offer of the request -> offer -> order flow), on the 20% "solving the
problem and user need" (a product a standing order already holds is said before it is ordered twice) and on the 20%
"autonomy and controls" (the alert orders nothing; a standing order set up from it orders nothing; another customer's
offer is never reachable). At both clocks: the recording's instant and the demo clock (Thu 12 Nov 2026 14:15).
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
TAIL = "From a synthetic order history."
ON_STANDING = (
    "Arla Pro Whipping cream (469346) is already on your standing order “Weekly whipping cream and coffee milk, "
    f"bakery” (40 L every week, next for Tuesday 17 November). This request would be on top of it. {TAIL}"
)
REGULAR = (
    "You order this every week: Oatly iKaffe (468319), 30 L, in 8 of your last 8 orders. Make it a standing order, so "
    "each week it is one renewal you confirm instead of a new request? Setting it up orders nothing, and every "
    f"renewal goes to a person as always. {TAIL}"
)
QUANTITY = f"You usually order 30 L of Oatly iKaffe (468319); this request says 90 L. Is 90 L right? {TAIL}"
SET_UP = (
    "Set up as the standing order “Weekly Oatly iKaffe”, renewed every week (your usual delivery day is Tuesday). "
    "Nothing is ordered by this: each renewal is an offer you confirm."
)


@pytest.fixture(params=["recording", "demo"])
def shop(request: pytest.FixtureRequest, tmp_path: Path, catalog: ProductCatalog) -> Iterator[TestClient]:
    """The whole gateway in replay at each of the two clocks, with a data directory of its own."""
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_replay_capture=CAPTURE,
                                  tta_demo_clock=None if request.param == "recording" else DEMO_CLOCK)
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        yield client


def _call(client: TestClient, method: str, path: str, kitchen: str = "bakery", **kwargs: Any) -> Any:
    return client.request(method, API + path, headers={"X-Shop-Request": "1", "X-Shop-Kitchen": kitchen}, **kwargs)


def _line(product_id: str, quantity: float) -> dict[str, Any]:
    return {"text": "a line", "product_ids": [product_id], "quantity": quantity, "unit": "L"}


def _offer(client: TestClient, *lines: dict[str, Any], kitchen: str = "bakery", settings: Any = None) -> Any:
    assert _call(client, "PUT", "/kitchen", kitchen, json=settings or BAKERY).status_code == 200
    answer = _call(client, "POST", "/offers", kitchen, json={"needed_by": "2026-11-17", "lines": list(lines)})
    assert answer.status_code == 200, answer.text
    return answer.json()


def _alert(client: TestClient, offer: Any, kitchen: str = "bakery") -> Any:
    answer = _call(client, "GET", f"/regular?offer_id={offer['offer_id']}", kitchen)
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_a_product_of_the_standing_order_is_said_on_its_offer(shop: TestClient) -> None:
    offer = _offer(shop, _line("469346", 40))

    alert = _alert(shop, offer)

    assert set(alert) == {"offer_id", "finding", "sentence", "lines", "standing_order_request", "usual_request",
                          "synthetic", "note", "evidence"}
    assert (alert["offer_id"], alert["finding"], alert["synthetic"]) == (
        offer["offer_id"], "ALREADY_ON_STANDING_ORDER", True)
    assert alert["sentence"] == ON_STANDING
    assert alert["lines"] == [{
        "request_line_index": 0, "product_id": "469346", "name": "Arla Pro Whipping cream 1 L UHT lactose free",
        "quantity": 40.0, "unit": "L", "regular": True, "usual_quantity": 40.0, "comparison": "USUAL",
        "orders_matching": 8, "orders_considered": 8, "standing_order_id": "so_bakery_weekly",
        "standing_order_name": "Weekly whipping cream and coffee milk, bakery", "sentence": "your usual 40 L",
    }]
    assert alert["standing_order_request"] is None
    assert alert["evidence"]["thresholds"]["REORDER_MIN_ORDERS"] == 3
    assert alert["evidence"]["next_delivery"] == "2026-11-17"


def test_a_regular_request_carries_the_standing_order_it_could_be(shop: TestClient) -> None:
    alert = _alert(shop, _offer(shop, _line("468319", 30)))

    assert (alert["finding"], alert["sentence"]) == ("REGULAR_NOT_STANDING", REGULAR)
    body = alert["standing_order_request"]
    assert (body["name"], body["cadence_days"]) == ("Weekly Oatly iKaffe", 7)
    assert [(line["product_ids"], line["quantity"]) for line in body["request"]["lines"]] == [(["468319"], 30.0)]


def test_a_quantity_far_from_the_usual_carries_the_request_at_the_usual_one(shop: TestClient) -> None:
    alert = _alert(shop, _offer(shop, _line("468319", 90)))

    assert (alert["finding"], alert["sentence"]) == ("REGULAR_DIFFERENT_QUANTITY", QUANTITY)
    assert (alert["lines"][0]["quantity"], alert["lines"][0]["usual_quantity"]) == (90.0, 30.0)

    usual = _call(shop, "POST", "/offers", json=alert["usual_request"])  # "Use my usual 30 L"

    assert usual.status_code == 200, usual.text
    assert usual.json()["request"]["lines"][0]["quantity"] == 30.0
    assert _alert(shop, usual.json())["finding"] == "REGULAR_NOT_STANDING"


def test_a_request_for_nothing_regular_gives_no_finding(shop: TestClient) -> None:
    almond = {"text": "20 L of almond drink", "product_type": "plant_drink", "name_terms": ["almond"],
              "quantity": 20, "unit": "L"}

    alert = _alert(shop, _offer(shop, almond, kitchen="school", settings=SCHOOL), "school")

    assert (alert["finding"], alert["sentence"], alert["standing_order_request"]) == (None, "", None)
    assert alert["evidence"]["findings"] == []


def test_a_type_only_line_is_judged_on_the_product_the_offer_chose(shop: TestClient) -> None:
    line = {"text": "40 litres of whipping cream", "product_type": "cream", "name_terms": ["whipping"],
            "quantity": 40, "unit": "L"}
    offer = _offer(shop, line)
    assert offer["options"][0]["lines"][0]["product_id"] == "469346"

    alert = _alert(shop, offer)

    assert (alert["finding"], alert["sentence"]) == ("ALREADY_ON_STANDING_ORDER", ON_STANDING)
    assert alert["evidence"]["products"][0]["resolved_by"] == "OFFER"


def test_the_alert_orders_nothing(shop: TestClient) -> None:
    offer = _offer(shop, _line("469346", 40))
    _alert(shop, offer)
    _alert(shop, offer)

    assert _call(shop, "GET", "/orders").json() == []
    assert _call(shop, "GET", "/approvals").json() == []


def test_another_customers_offer_is_not_found(shop: TestClient) -> None:
    offer = _offer(shop, _line("469346", 40))

    answer = _call(shop, "GET", f"/regular?offer_id={offer['offer_id']}", "hotel")

    assert answer.status_code == 404
    assert _call(shop, "GET", "/regular?offer_id=off_nobody").status_code == 404


def test_the_route_answers_the_shop_page_only(shop: TestClient) -> None:
    offer = _offer(shop, _line("469346", 40))
    path = f"{API}/regular?offer_id={offer['offer_id']}"

    assert shop.get(path, headers={"X-Shop-Kitchen": "bakery"}).status_code == 403
    assert shop.get(path, headers={"X-Shop-Request": "1"}).status_code == 400
    assert shop.get(path, headers={"X-Shop-Request": "1", "X-Shop-Kitchen": "bakery",
                                   "Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert _call(shop, "GET", "/regular").status_code == 422  # no offer named


# --- setting the regular request up as a standing order -------------------------------------------------------------


def test_the_standing_order_is_set_up_and_orders_nothing(shop: TestClient) -> None:
    alert = _alert(shop, _offer(shop, _line("468319", 30)))

    answer = _call(shop, "POST", "/standing-orders", json=alert["standing_order_request"])

    assert answer.status_code == 201, answer.text
    made = answer.json()
    assert set(made) == {"standing_order", "sentence"}
    assert made["sentence"] == SET_UP
    assert (made["standing_order"]["name"], made["standing_order"]["cadence_days"]) == ("Weekly Oatly iKaffe", 7)
    assert made["standing_order"]["standing_order_id"].startswith("so_")
    assert _call(shop, "GET", "/orders").json() == []
    assert _call(shop, "GET", "/approvals").json() == []


def test_once_set_up_the_same_request_is_said_to_be_on_the_standing_order(shop: TestClient) -> None:
    alert = _alert(shop, _offer(shop, _line("468319", 30)))
    made = _call(shop, "POST", "/standing-orders", json=alert["standing_order_request"]).json()

    again = _alert(shop, _offer(shop, _line("468319", 30)))

    assert again["finding"] == "ALREADY_ON_STANDING_ORDER"
    assert again["sentence"] == (
        "Oatly iKaffe (468319) is already on your standing order “Weekly Oatly iKaffe” (30 L every week, next for "
        f"Tuesday 17 November). This request would be on top of it. {TAIL}"
    )
    assert again["lines"][0]["standing_order_id"] == made["standing_order"]["standing_order_id"]
    assert again["standing_order_request"] is None


def test_a_set_up_waits_for_the_customers_settings(shop: TestClient) -> None:
    body = {"name": "Weekly oat drink", "request": {"lines": [_line("468319", 30)]}}

    answer = _call(shop, "POST", "/standing-orders", json=body)

    assert answer.status_code == 409 and answer.json()["type"] == "settings-not-received"


def test_a_body_that_is_not_a_standing_order_is_refused(shop: TestClient) -> None:
    _call(shop, "PUT", "/kitchen", json=BAKERY)
    renews = {"name": "Weekly oat drink",
              "request": {"standing_order_id": "so_bakery_weekly", "lines": [_line("468319", 30)]}}

    assert _call(shop, "POST", "/standing-orders", json={"name": "No request"}).status_code == 422
    assert _call(shop, "POST", "/standing-orders", json=renews).status_code == 422
    assert shop.post(f"{API}/standing-orders", json=renews, headers={"X-Shop-Kitchen": "bakery"}).status_code == 403


def test_a_buyer_holds_at_most_twenty_standing_orders(shop: TestClient) -> None:
    _call(shop, "PUT", "/kitchen", json=BAKERY)
    body = {"name": "Weekly oat drink", "request": {"lines": [_line("468319", 30)]}}

    answers = [_call(shop, "POST", "/standing-orders", json=body) for _ in range(20)]

    assert [answer.status_code for answer in answers[:19]] == [201] * 19  # the bakery's own is the first of the 20
    assert answers[19].status_code == 422
    assert "already has 20 standing orders" in answers[19].json()["detail"]
    # A set-up is counted by the rate limit as an offer is: 60 a minute for one visitor since decision B55 (20
    # before), so the limit of 20 standing orders answers first, and the rate limit at the 61st set-up of the minute.
    more = [_call(shop, "POST", "/standing-orders", json=body) for _ in range(41)]
    assert [answer.status_code for answer in more] == [422] * 40 + [429]
    assert "at most 60 in 60 seconds" in more[40].json()["detail"]


def test_a_standing_order_takes_the_demonstrations_five_lines_at_most(shop: TestClient) -> None:
    _call(shop, "PUT", "/kitchen", json=BAKERY)
    body = {"name": "Six lines", "request": {"lines": [_line("468319", 30)] * 6}}

    refused = _call(shop, "POST", "/standing-orders", json=body)

    assert refused.status_code == 422 and "at most 5 lines" in refused.json()["detail"]


def test_a_standing_order_set_up_from_the_alert_is_listed_with_the_customers_own(shop: TestClient) -> None:
    """Lane G3: what "Make it a standing order" set up is in the Standing orders view, after the customer file's."""
    alert = _alert(shop, _offer(shop, _line("468319", 30)))
    before = [one["standing_order_id"] for one in _call(shop, "GET", "/standing-orders").json()["standing_orders"]]
    made = _call(shop, "POST", "/standing-orders", json=alert["standing_order_request"]).json()["standing_order"]

    listed = _call(shop, "GET", "/standing-orders").json()["standing_orders"]

    assert before and [one["standing_order_id"] for one in listed] == [*before, made["standing_order_id"]]
    mine = listed[-1]
    assert (mine["name"], mine["cadence_days"]) == ("Weekly Oatly iKaffe", 7)
    (line,) = mine["lines"]
    assert (line["product_id"], float(line["quantity"]), line["unit"]) == ("468319", 30, "L")
    assert line["name"].startswith("Oatly iKaffe")
    assert mine["synthetic"] is False and mine["past_orders"] == [] and mine["trend"] is None
    # The other customers' books do not see it.
    assert _call(shop, "PUT", "/kitchen", "school", json=SCHOOL).status_code == 200
    others = _call(shop, "GET", "/standing-orders", "school").json()["standing_orders"]
    assert made["standing_order_id"] not in [one["standing_order_id"] for one in others]
