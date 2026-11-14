"""The standing-order routes and the page, over the whole gateway in replay (task STAND-1).

The gateway as it is wired (`tta.api.wiring`, `tta.api.app`, `tta.ui.routes`). The buyer agent and MCP are not
loaded.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app, hooks, wiring
from tta.config import Settings
from tta.contracts.errors import PROBLEM_TYPE_BASE

CAPTURE = "2026-11-14-demo"
AGENT = {"Authorization": "Bearer demo-agent-hotel-kitchen"}
WARD = {"Authorization": "Bearer demo-agent-allergy-ward"}
PURCHASING = {"Authorization": "Bearer demo-approver-hotel-purchasing"}
SUPPLIER = {"Authorization": "Bearer demo-supplier-valio-aimo"}
CSRF = re.compile(r'name="csrf" value="([A-Za-z0-9_-]+)"')
P08 = "290 L this week against a median of 100 L over the last 6 renewals, more than the 25% tolerance"


@pytest.fixture
def client(tmp_path: Path, catalog: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    real_module, hidden = hooks.optional_module, (hooks.AGENT_MODULE, hooks.MCP_MODULE)
    monkeypatch.setattr(hooks, "optional_module", lambda name: None if name in hidden else real_module(name))
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_env="demo", tta_replay_capture=CAPTURE)
    app = create_app(settings, parts=wiring.build_parts(settings, catalog=catalog))  # the gateway as it runs
    with TestClient(app) as test_client:
        yield test_client


def _milk(litres: int) -> dict[str, Any]:
    return {"lines": [{"text": f"{litres} L of milk 469363", "product_ids": ["469363"], "quantity": litres,
                       "unit": "L"}]}


def test_the_rest_routes_set_up_list_read_and_renew_a_standing_order(client: TestClient) -> None:
    created = client.post("/v1/standing-orders", json={"name": "Milk for the bar", "request": _milk(100)},
                          headers=AGENT)
    assert created.status_code == 201, created.text
    standing_id = created.json()["standing_order_id"]

    assert [one["standing_order_id"] for one in client.get("/v1/standing-orders", headers=PURCHASING).json()] == [
        standing_id
    ]
    renewed = client.post(f"/v1/standing-orders/{standing_id}/renew", json={"quantities": [290]}, headers=AGENT)
    assert renewed.status_code == 201, renewed.text
    body = renewed.json()
    assert body["order"]["status"] == "PENDING_APPROVAL" and body["drift"]["judged"] is False
    assert body["offer"]["request"]["standing_order_id"] == standing_id
    detail = client.get(f"/v1/standing-orders/{standing_id}", headers=AGENT).json()
    assert [renewal["order_id"] for renewal in detail["renewals"]] == [body["order"]["order_id"]]


def test_the_rest_routes_answer_problems_as_the_other_routes_do(client: TestClient) -> None:
    unknown = client.get("/v1/standing-orders/so_nobody", headers=AGENT)
    approver = client.post("/v1/standing-orders", json={"name": "Milk", "request": _milk(100)}, headers=PURCHASING)
    supplier = client.get("/v1/standing-orders", headers=SUPPLIER)
    offer = client.post("/v1/offers", json={**_milk(100), "standing_order_id": "so_nobody"}, headers=AGENT)

    assert unknown.status_code == 404 and unknown.json()["type"] == PROBLEM_TYPE_BASE + "not-found"
    assert approver.status_code == 403 and supplier.status_code == 403
    assert client.get("/v1/standing-orders").status_code == 401
    assert offer.status_code == 422 and offer.json()["type"] == PROBLEM_TYPE_BASE + "invalid-request"
    assert "No standing order so_nobody is set up for this buyer" in offer.json()["detail"]
    assert client.post("/v1/standing-orders/so_x/renew", json={"quantities": [0]}, headers=AGENT).status_code == 422
    assert "/v1/standing-orders/{standing_order_id}/renew" in client.get("/openapi.json").json()["paths"]


def _csrf(client: TestClient) -> str:
    page = client.get("/standing-orders")
    assert page.status_code == 200, page.text
    return CSRF.search(page.text).group(1)  # type: ignore[union-attr]


def test_the_page_loads_the_demo_renews_it_and_shows_the_drift_and_the_outcome(client: TestClient) -> None:
    empty = client.get("/standing-orders").text
    assert "No standing order in your order book yet." in empty and "Load the demo standing order" in empty

    loaded = client.post("/standing-orders/demo", data={"csrf": _csrf(client)}, follow_redirects=False)
    page = client.get("/standing-orders").text
    assert loaded.status_code == 303
    assert "Weekly lactose-free milk, hotel kitchen" in page
    assert page.count("Synthetic: made up for the demo") == 78  # all four customers' past orders, each labelled
    assert "more than 25% from the median" in page  # P-08 with the hotel kitchen's tolerance

    usual = client.post("/standing-orders/so_demo_hotel_milk/renew",
                        data={"csrf": _csrf(client), "quantity_0": "100"}, follow_redirects=False)
    page = client.get("/standing-orders").text
    assert usual.status_code == 303 and "is within the 25% tolerance" in page and "Waiting for approval" in page

    drift = client.post("/standing-orders/so_demo_hotel_milk/renew",
                        data={"csrf": _csrf(client), "quantity_0": "290"}, follow_redirects=False)
    page = client.get("/standing-orders").text
    assert drift.status_code == 303 and P08 in page and 'href="/approvals"' in page
    approvals = client.get("/approvals").text
    assert P08 in approvals  # the purchasing manager's card states the drift


def test_the_page_refuses_a_form_without_its_token_or_with_a_quantity_that_is_no_number(client: TestClient) -> None:
    client.post("/standing-orders/demo", data={"csrf": _csrf(client)})

    no_token = client.post("/standing-orders/so_demo_hotel_milk/renew", data={"quantity_0": "100"})
    not_a_number = client.post("/standing-orders/so_demo_hotel_milk/renew",
                               data={"csrf": _csrf(client), "quantity_0": "a lot"})
    zero = client.post("/standing-orders/so_demo_hotel_milk/renew", data={"csrf": _csrf(client), "quantity_0": "0"})
    unknown = client.post("/standing-orders/so_nobody/renew", data={"csrf": _csrf(client), "quantity_0": "1"})

    assert no_token.status_code == 403
    assert not_a_number.status_code == 422 and "Not a quantity" in not_a_number.text
    assert zero.status_code == 422
    assert unknown.status_code == 404
