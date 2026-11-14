"""GET /v1/menus/recipes and POST /v1/menus/plan: the same identity, problems and limits as every other route."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app, hooks
from tta.api.limits import RateLimit
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.errors import PROBLEM_CONTENT_TYPE, PROBLEM_TYPE_BASE

# The demonstration tokens of src/tta/api/demo_tokens.yaml. They are public by design.
AGENT = {"Authorization": "Bearer demo-agent-hotel-kitchen"}
APPROVER = {"Authorization": "Bearer demo-approver-hotel-purchasing"}
SUPPLIER = {"Authorization": "Bearer demo-supplier-valio-aimo"}
NOT_SHOWN = (hooks.AGENT_MODULE, hooks.MCP_MODULE, hooks.PAGES_MODULE)


@pytest.fixture
def make_api(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[..., TestClient]]:
    """The gateway's API with the menu routes included, as `api/app.py` will include them."""
    real = hooks.optional_module
    monkeypatch.setattr(hooks, "optional_module", lambda name: None if name in NOT_SHOWN else real(name))
    opened: list[TestClient] = []

    def make(calls: int = 1000) -> TestClient:
        app = create_app(settings, parts=build_parts(settings, catalog=catalog, rate_limit=RateLimit(calls=calls)))
        client = TestClient(app)
        client.__enter__()
        opened.append(client)
        return client

    yield make
    for client in opened:
        client.__exit__(None, None, None)


@pytest.fixture
def api(make_api: Callable[..., TestClient]) -> TestClient:
    return make_api()


def _problem(response: Any, status: int, slug: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    body = response.json()
    assert body["type"] == f"{PROBLEM_TYPE_BASE}{slug}"
    return body


def test_the_recipes_are_listed_and_labelled_illustrative(api: TestClient) -> None:
    response = api.get("/v1/menus/recipes", headers=AGENT)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["illustrative"] is True and "illustrative" in body["note"]
    dishes = {recipe["dish_id"]: recipe for recipe in body["recipes"]}
    assert "berry_quark_dessert" in dishes and len(dishes) >= 8
    quark = dishes["berry_quark_dessert"]["ingredients"][0]
    assert quark["role"] and quark["alternatives"][0]["product_type"] == "yoghurt"


def test_a_menu_plan_returns_the_plan_and_its_final_offer(
    api: TestClient, menu: Callable[..., Any]
) -> None:
    response = api.post("/v1/menus/plan", headers=AGENT, json=menu().model_dump(mode="json"))

    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["illustrative"] is True and len(plan["offers_asked"]) == 3
    offer = api.get(f"/v1/offers/{plan['offer_id']}", headers=AGENT)
    assert offer.status_code == 200
    assert [line.get("stands_in_for") for line in offer.json()["request"]["lines"]] == [None, None, None, "quark"]


def test_an_unknown_dish_is_an_invalid_request_problem(api: TestClient) -> None:
    body = {"dishes": [{"dish_id": "pizza", "servings": 10}]}

    problem = _problem(api.post("/v1/menus/plan", headers=AGENT, json=body), 422, "invalid-request")

    assert "No recipe has the id 'pizza'" in problem["detail"]


def test_a_body_that_breaks_the_contract_is_an_invalid_request_problem(api: TestClient) -> None:
    body = {"dishes": [{"dish_id": "lasagne", "servings": 0}]}

    _problem(api.post("/v1/menus/plan", headers=AGENT, json=body), 422, "invalid-request")


def test_no_token_is_unauthenticated_and_an_approver_cannot_plan(api: TestClient, menu: Callable[..., Any]) -> None:
    body = menu().model_dump(mode="json")

    _problem(api.get("/v1/menus/recipes"), 401, "not-authorised")
    _problem(api.post("/v1/menus/plan", json=body), 401, "not-authorised")
    _problem(api.post("/v1/menus/plan", headers=APPROVER, json=body), 403, "not-authorised")
    _problem(api.post("/v1/menus/plan", headers=SUPPLIER, json=body), 403, "not-authorised")


def test_the_rate_limit_counts_every_offer_of_a_plan(make_api: Callable[..., TestClient], menu: Callable) -> None:
    api = make_api(calls=4)  # one plan of the demo case asks for 3 offers
    body = menu().model_dump(mode="json")

    assert api.post("/v1/menus/plan", headers=AGENT, json=body).status_code == 200
    _problem(api.post("/v1/menus/plan", headers=AGENT, json=body), 429, "rate-limited")


def test_the_routes_are_in_the_openapi_document(api: TestClient) -> None:
    paths = api.get("/openapi.json").json()["paths"]

    assert paths["/v1/menus/recipes"]["get"]["operationId"] == "list_recipes"
    assert paths["/v1/menus/plan"]["post"]["operationId"] == "plan_menu"
