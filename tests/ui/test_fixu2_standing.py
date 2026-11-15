"""FIX-U2, item 1: every standing order of the shop can be renewed from `/shop`, at its usual quantity or at one a
person types, through the route the school's trend button uses (`POST /shop/api/offers`).

Scores on the 30% demo (scenario 5: the hotel renews its weekly milk at 290 L on the page and a person confirms),
on the 20% "autonomy and controls" (the renewal is judged against the past renewals, rule P-08, and nothing is
ordered by the click) and on the 15% robustness (a quantity far from the usual one is flagged, not refused).
Measured at the demo clock, Thu 12 Nov 2026 14:15 Helsinki, in replay.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import tta.ui
from tta.api import create_app
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings

API = "/shop/api"
CAPTURE = "2026-11-14-demo"
DEMO_CLOCK = "2026-11-12T14:15:00+02:00"
SHOP_JS = Path(tta.ui.__file__).parent / "static" / "shop" / "js"
HOTEL_ORDER = "so_demo_hotel_milk"
MILK = "469363"
MIN_NODE = 22  # a page script is read as a module by its own syntax from this version on


@pytest.fixture
def shop(tmp_path: Path, catalog: ProductCatalog) -> Iterator[TestClient]:
    """The whole gateway in replay at the demo clock, with a data directory of its own."""
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_replay_capture=CAPTURE,
                                  tta_demo_clock=DEMO_CLOCK)
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        yield client


def _call(client: TestClient, method: str, path: str, kitchen: str = "hotel", **kwargs: Any) -> Any:
    return client.request(method, API + path, headers={"X-Shop-Request": "1", "X-Shop-Kitchen": kitchen}, **kwargs)


def _settings(client: TestClient, kitchen: str, settings: dict[str, dict[str, Any]]) -> None:
    customer_id = {"hotel": "hotel-kitchen", "school": "school-kitchen", "bakery": "bakery-cafe"}[kitchen]
    saved = _call(client, "PUT", "/kitchen", kitchen, json=settings[customer_id])
    assert saved.status_code == 200, saved.text


def _renewal(client: TestClient, standing_order_id: str, kitchen: str = "hotel", **body: Any) -> Any:
    return _call(client, "POST", f"/standing-orders/{standing_order_id}/renewal", kitchen, json=body)


# --- the route: one renewal as a request, written by the gateway ------------------------------------------------


def test_the_hotels_renewal_at_290_litres_is_a_request_that_names_the_standing_order(shop: TestClient) -> None:
    answer = _renewal(shop, HOTEL_ORDER, quantities=[290])

    assert answer.status_code == 200, answer.text
    request = answer.json()
    assert request["standing_order_id"] == HOTEL_ORDER
    (line,) = request["lines"]
    assert (line["product_ids"], float(line["quantity"]), line["unit"]) == ([MILK], 290.0, "L")
    # The log's first step quotes the line's words: they say this week's quantity, not the stored 100.
    assert "290" in line["text"] and "100" not in line["text"]
    assert _call(shop, "GET", "/orders").json() == []  # a request, never an order


def test_a_renewal_without_quantities_is_the_usual_one(shop: TestClient) -> None:
    request = _renewal(shop, HOTEL_ORDER).json()

    assert request["standing_order_id"] == HOTEL_ORDER
    assert [(line["product_ids"], float(line["quantity"])) for line in request["lines"]] == [([MILK], 100.0)]


def test_at_290_litres_the_offer_is_flagged_against_the_past_renewals_and_a_person_confirms(
    shop: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _settings(shop, "hotel", shop_profile_settings)
    request = _renewal(shop, HOTEL_ORDER, quantities=[290]).json()

    offered = _call(shop, "POST", "/offers", json=request)

    assert offered.status_code == 200, offered.text
    first = offered.json()["options"][0]
    assert [(line["product_id"], line["quantity"]) for line in first["lines"]] == [(MILK, 290.0)]
    assert first["totals"]["net"] == 719.2  # 290 x EUR 2.48
    assert first["decision"]["verdict"] == "APPROVAL"
    assert "P-08" in [rule["rule_id"] for rule in first["decision"]["fired"]]  # 290 L against a median of 100 L
    assert _call(shop, "GET", "/orders").json() == []


def test_at_the_usual_100_litres_no_drift_is_flagged_and_a_person_still_confirms(
    shop: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _settings(shop, "hotel", shop_profile_settings)

    first = _call(shop, "POST", "/offers", json=_renewal(shop, HOTEL_ORDER).json()).json()["options"][0]

    assert first["totals"]["net"] == 248.0 and first["decision"]["verdict"] == "APPROVAL"
    assert "P-08" not in [rule["rule_id"] for rule in first["decision"]["fired"]]


def test_the_confirmed_renewal_is_an_order_like_any_other_in_orders_and_in_the_back_office(
    shop: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _settings(shop, "hotel", shop_profile_settings)
    offer = _call(shop, "POST", "/offers", json=_renewal(shop, HOTEL_ORDER, quantities=[290]).json()).json()
    body = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"], "key": "fixu2.hotel.290"}
    waiting = _call(shop, "POST", "/orders", json=body).json()
    assert waiting["status"] == "PENDING_APPROVAL"

    decided = _call(shop, "POST", f"/approvals/{waiting['approval_id']}/decision",
                    json={"role": "purchasing_manager", "decision": {"decision": "APPROVE"}})

    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "ORDERED"
    listed = _call(shop, "GET", "/orders").json()
    assert [(order["order_id"], order["status"], order["option"]["totals"]["net"]) for order in listed] == [
        (waiting["order_id"], "ORDERED", 719.2)]
    demand = _call(shop, "GET", "/backoffice?period=all").json()["demand"]
    assert (demand["confirmed_by_person"], demand["confirmed_net_eur"]) == (1, 719.2)


def test_a_standing_order_with_several_lines_takes_one_quantity_per_line(shop: TestClient) -> None:
    answer = _renewal(shop, "so_school_weekly", "school", quantities=[120, 90, 20])

    assert answer.status_code == 200, answer.text
    assert [float(line["quantity"]) for line in answer.json()["lines"]] == [120.0, 90.0, 20.0]
    short = _renewal(shop, "so_school_weekly", "school", quantities=[90])
    assert short.status_code == 422 and "3 quantities" in short.json()["detail"]


def test_a_quantity_that_is_no_quantity_and_another_customers_standing_order_are_refused(shop: TestClient) -> None:
    for wrong in ([0], [-5], ["a lot"]):
        assert _renewal(shop, HOTEL_ORDER, quantities=wrong).status_code == 422, wrong
    assert _renewal(shop, "so_school_weekly", quantities=[60]).status_code == 404  # not in the hotel's book
    assert _renewal(shop, "so_nobody", quantities=[60]).status_code == 404
    path = f"{API}/standing-orders/{HOTEL_ORDER}/renewal"
    assert shop.post(path, json={"quantities": [290]}, headers={"X-Shop-Kitchen": "hotel"}).status_code == 403
    assert _call(shop, "GET", "/orders").json() == []


def test_a_standing_order_set_up_on_the_page_can_be_renewed_too(
    shop: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _settings(shop, "bakery", shop_profile_settings)
    line = {"text": "30 L of oat drink 468319", "product_ids": ["468319"], "quantity": 30, "unit": "L"}
    made = _call(shop, "POST", "/standing-orders", "bakery", json={"name": "Weekly oat drink", "request": {
        "lines": [line]}}).json()["standing_order"]

    request = _renewal(shop, made["standing_order_id"], "bakery", quantities=[45]).json()

    assert request["standing_order_id"] == made["standing_order_id"]
    assert [(each["product_ids"], float(each["quantity"])) for each in request["lines"]] == [(["468319"], 45.0)]
    assert _call(shop, "POST", "/offers", "bakery", json=request).status_code == 200


# --- the page: every card has its renewal, whether or not a trend exists --------------------------------------------

VIEW = """
const store = new Map();
globalThis.localStorage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k) };
const answers = %(answers)s;
globalThis.fetch = async (url) => {
  const path = String(url).replace(/^.*\\/shop\\/api/, "");
  const body = answers[path];
  return { ok: body !== undefined, status: body === undefined ? 404 : 200, json: async () => body ?? {} };
};
const { memory } = await import(%(store)s);
memory.active = %(kitchen)s;
const core = await import(%(core)s);
core.setRenderer(() => {});
const standing = await import(%(view)s);
standing.enter();
await new Promise((done) => setTimeout(done, 50));
console.log(JSON.stringify(String(standing.view())));
"""


def _drawn(kitchen: str, standing_orders: dict[str, Any]) -> str:
    """The standing-orders view as the page's own script draws it for one answer of the route, run by node."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30, check=False)  # noqa: S603
    if int(version.stdout.strip().lstrip("v").split(".")[0]) < MIN_NODE:
        pytest.skip(f"node {version.stdout.strip()} does not read the page's scripts as modules")
    script = VIEW % {
        "answers": json.dumps({"/standing-orders": standing_orders}), "kitchen": json.dumps(kitchen),
        "store": json.dumps((SHOP_JS / "store.js").as_uri()), "core": json.dumps((SHOP_JS / "core.js").as_uri()),
        "view": json.dumps((SHOP_JS / "views" / "standing.js").as_uri()),
    }
    # The script is this file's own text around the page's source: nothing from outside is run.
    done = subprocess.run([node, "--input-type=module", "-e", script], capture_output=True, text=True,  # noqa: S603
                          timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    drawn: str = json.loads(done.stdout.strip().splitlines()[-1])
    return drawn


def test_the_hotels_card_can_be_renewed_at_its_usual_quantity_or_at_one_typed(shop: TestClient) -> None:
    listed = _call(shop, "GET", "/standing-orders").json()
    assert [one["trend"] for one in listed["standing_orders"]] == [None]  # no trend: the card had no button

    page = _drawn("hotel", listed)

    assert f'data-act="standing-renew-at" data-id="{HOTEL_ORDER}"' in page
    assert 'value="100"' in page  # the usual quantity, ready to be typed over
    assert "Renew once at 100 L" in page


def test_the_schools_card_keeps_its_trend_button_and_gains_the_renewal_of_every_line(shop: TestClient) -> None:
    listed = _call(shop, "GET", "/standing-orders", "school").json()

    page = _drawn("school", listed)

    assert 'data-act="standing-renew"' in page and "Renew once at 84 L" in page  # the trend's own button
    assert 'data-act="standing-renew-at" data-id="so_school_weekly"' in page
    assert page.count('data-input="standing-quantity"') == 3  # one field per line of the standing order
