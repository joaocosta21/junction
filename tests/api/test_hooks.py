"""The hooks for what other tasks add: the request parser and the buyer agent (T10), the MCP surface (T11)
and the pages (T12). Until they land, the gateway answers without them and says so."""

from __future__ import annotations

import sys
import types
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from tta.api import create_app
from tta.api.hooks import SurfaceContext
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.agent import AgentRun, AgentStep
from tta.contracts.common import Identity, Unit
from tta.contracts.errors import InvalidRequest
from tta.contracts.ports import GatewayService
from tta.contracts.request import PurchaseRequest, RequestLine

Auth = Callable[..., dict[str, str]]
Problem = Callable[..., dict[str, Any]]
TEXT = "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"
TYPED = PurchaseRequest(
    needed_by=date(2026, 11, 16), require_confirmed=True,
    lines=(RequestLine(text=TEXT, product_type="plant_drink", quantity=Decimal(200), unit=Unit.L,
                       exclude_allergens=("AM", "AW")),),
)


class FakeParser:
    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        if "milk" not in text:
            raise InvalidRequest("The request names no quantity.")
        return TYPED


class FakeRunner:
    """Runs the flow the way the buyer agent will: only through the gateway's own functions."""

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        authority = tools.get_authority(identity)
        offer = tools.create_offer(identity, TYPED)
        order = tools.place_order(identity, offer.offer_id, offer.options[0].option_id, "agent-run-1")
        steps = (
            AgentStep(index=1, tool="get_authority", ok=True, result={"profile_id": authority.profile.profile_id}),
            AgentStep(index=2, tool="create_offer", ok=True, result={"offer_id": offer.offer_id}),
            AgentStep(index=3, tool="place_order", ok=True, sentence=order.status_sentence),
        )
        return AgentRun(
            text=text, model="recorded", recorded=True, steps=steps, offer_id=offer.offer_id,
            order_id=order.order_id, order_status=order.status, report=order.status_sentence,
        )


@pytest.fixture
def with_agent(settings: Settings, catalog: ProductCatalog) -> Iterator[TestClient]:
    parts = build_parts(settings, catalog=catalog, request_parser=FakeParser(), agent_runner=FakeRunner())
    with TestClient(create_app(settings, parts=parts)) as client:
        yield client


# --- T10: request parser and buyer agent ----------------------------------------------------------------


@pytest.mark.parametrize("path", ["/v1/requests/parse", "/v1/agent/run"])
def test_until_the_agent_package_lands_both_routes_answer_supplier_unavailable(
    client: TestClient, auth: Auth, assert_problem: Problem, path: str
) -> None:
    response = client.post(path, json={"text": TEXT}, headers=auth("agent_ward"))

    problem = assert_problem(response, "supplier-unavailable", 503)
    assert "POST /v1/offers" in problem["detail"]
    assert client.get("/v1/audit", headers=auth("agent_ward")).json()["events"] == []


@pytest.mark.parametrize("path", ["/v1/requests/parse", "/v1/agent/run"])
def test_a_text_that_is_empty_or_too_long_is_an_invalid_request(
    client: TestClient, auth: Auth, assert_problem: Problem, path: str
) -> None:
    assert_problem(client.post(path, json={"text": ""}, headers=auth("agent_ward")), "invalid-request", 422)
    assert_problem(client.post(path, json={"text": "x" * 2001}, headers=auth("agent_ward")), "invalid-request", 422)


def test_parse_calls_the_parser_port_and_records_the_pasted_text(with_agent: TestClient, auth: Auth) -> None:
    response = with_agent.post("/v1/requests/parse", json={"text": TEXT}, headers=auth("agent_ward"))

    assert response.status_code == 200
    assert PurchaseRequest.model_validate(response.json()) == TYPED
    events = with_agent.get("/v1/audit", headers=auth("agent_ward")).json()["events"]
    assert [event["type"] for event in events] == ["tta.v1.request.received"]
    assert TEXT in events[0]["sentence"]
    assert events[0]["actor"]["id"] == "agent:allergy-ward"


def test_what_the_parser_refuses_leaves_as_its_typed_error(
    with_agent: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    response = with_agent.post("/v1/requests/parse", json={"text": "something"}, headers=auth("agent_ward"))

    assert assert_problem(response, "invalid-request", 422)["detail"] == "The request names no quantity."


def test_agent_run_gives_the_runner_the_gateway_itself_and_returns_its_trace(
    with_agent: TestClient, auth: Auth
) -> None:
    response = with_agent.post("/v1/agent/run", json={"text": TEXT}, headers=auth("agent_ward"))

    assert response.status_code == 200
    run = AgentRun.model_validate(response.json())
    assert [step.tool for step in run.steps] == ["get_authority", "create_offer", "place_order"]
    assert run.order_status is not None and run.order_status.value == "ORDERED"
    order = with_agent.get(f"/v1/orders/{run.order_id}", headers=auth("agent_ward")).json()
    assert order["status"] == "ORDERED"
    types_seen = [event["type"] for event in with_agent.get("/v1/audit", headers=auth("agent_ward")).json()["events"]]
    assert types_seen[0] == "tta.v1.request.received"
    assert "tta.v1.order.placed_by_agent" in types_seen


def test_only_an_agent_may_paste_a_request(with_agent: TestClient, auth: Auth, assert_problem: Problem) -> None:
    for path in ("/v1/requests/parse", "/v1/agent/run"):
        response = with_agent.post(path, json={"text": TEXT}, headers=auth("ward_dietitian"))
        assert_problem(response, "not-authorised", 403)


def test_the_agent_package_is_wired_through_its_two_factories(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def build_request_parser(**given: Any) -> FakeParser:
        seen["parser"] = given
        return FakeParser()

    def build_agent_runner(**given: Any) -> FakeRunner:
        seen["runner"] = given
        return FakeRunner()

    module = types.ModuleType("tta.agent")
    module.build_request_parser = build_request_parser  # type: ignore[attr-defined]
    module.build_agent_runner = build_agent_runner  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tta.agent", module)

    parts = build_parts(settings, catalog=catalog)
    with TestClient(create_app(settings, parts=parts)) as client:
        health = client.get("/healthz").json()

    assert health["agent"] == {"request_parser": True, "agent_runner": True}
    for given in (seen["parser"], seen["runner"]):
        assert set(given) == {"settings", "clock", "product_type_keys"}
        assert given["settings"] is settings
        assert "milk" in given["product_type_keys"]


def test_a_factory_that_returns_something_else_stops_the_start(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = types.ModuleType("tta.agent")
    module.build_request_parser = lambda **given: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tta.agent", module)

    with pytest.raises(RuntimeError, match="build_request_parser"):
        build_parts(settings, catalog=catalog)


# --- T11 and T12: the MCP surface and the pages ---------------------------------------------------------


def _surface(name: str, started: list[str], contexts: list[SurfaceContext]) -> types.ModuleType:
    def create_surface(context: SurfaceContext) -> Starlette:
        contexts.append(context)

        @asynccontextmanager
        async def lifespan(app: Starlette) -> AsyncIterator[None]:
            started.append(f"{name} started")
            yield
            started.append(f"{name} stopped")

        async def page(request: Request) -> PlainTextResponse:
            return PlainTextResponse(f"{name} at {request.url.path}")

        return Starlette(routes=[Route("/", page), Route("/{rest:path}", page)], lifespan=lifespan)

    module = types.ModuleType(name)
    module.create_surface = create_surface  # type: ignore[attr-defined]
    return module


def test_without_the_optional_modules_nothing_is_mounted(client: TestClient) -> None:
    assert client.get("/mcp/").status_code == 404
    assert client.get("/").status_code == 404
    assert client.get("/healthz").json()["surfaces"] == {"mcp": False, "pages": False}


def test_the_mcp_surface_and_the_pages_are_mounted_when_their_modules_exist(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch, auth: Auth
) -> None:
    started: list[str] = []
    contexts: list[SurfaceContext] = []
    monkeypatch.setitem(sys.modules, "tta.api.mcp_surface", _surface("mcp", started, contexts))
    monkeypatch.setitem(sys.modules, "tta.ui.routes", _surface("pages", started, contexts))
    parts = build_parts(settings, catalog=catalog)

    with TestClient(create_app(settings, parts=parts)) as client:
        assert client.get("/mcp/").text == "mcp at /mcp/"
        assert client.get("/").text == "pages at /"
        assert client.get("/approvals").text == "pages at /approvals"
        # The API keeps its own paths, also for a path or a method it does not have.
        assert client.get("/healthz").json()["surfaces"] == {"mcp": True, "pages": True}
        assert client.get("/v1/schemas").status_code == 200
        assert client.get("/v1/authority", headers=auth("agent_hotel")).status_code == 200
        assert client.get("/openapi.json").status_code == 200
        for response, status in ((client.get("/v1/no-such-thing"), 404), (client.delete("/v1/orders"), 405)):
            assert response.status_code == status
            assert response.headers["content-type"] == "application/problem+json"
        assert started == ["mcp started", "pages started"]
    assert started[2:] == ["pages stopped", "mcp stopped"]

    assert len(contexts) == 2
    for context in contexts:
        assert context.service is parts.service
        assert context.settings is settings
        assert context.identify("demo-agent-hotel-kitchen") == parts.tokens.identify("demo-agent-hotel-kitchen")
        assert context.identify("nobody") is None
        assert len(context.demo_identities) == 9


def test_outside_dev_and_demo_the_pages_are_not_mounted_and_no_demo_identity_is_handed_out(
    tmp_path: Any, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    contexts: list[SurfaceContext] = []
    monkeypatch.setitem(sys.modules, "tta.api.mcp_surface", _surface("mcp", [], contexts))
    monkeypatch.setitem(sys.modules, "tta.ui.routes", _surface("pages", [], contexts))
    tokens = '{"a-token-from-the-environment": {"kind": "SUPPLIER", "id": "supplier:x", "display_name": "X"}}'
    settings = Settings.for_tests(tta_env="prod", tta_tokens=tokens, tta_data_dir=tmp_path / "var")

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        assert client.get("/").status_code == 404
        assert client.get("/mcp/").status_code == 200
        assert client.get("/healthz").json()["surfaces"] == {"mcp": True, "pages": False}

    assert [context.demo_identities for context in contexts] == [()]


def test_an_optional_module_without_its_hook_stops_the_start(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "tta.ui.routes", types.ModuleType("tta.ui.routes"))

    with pytest.raises(RuntimeError, match="create_surface"):
        create_app(settings, parts=build_parts(settings, catalog=catalog))


def test_a_surface_that_is_a_bare_asgi_callable_is_mounted_too(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def bare(scope: Any, receive: Any, send: Any) -> None:
        await PlainTextResponse("bare")(scope, receive, send)

    module = types.ModuleType("tta.api.mcp_surface")
    module.create_surface = lambda context: bare  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tta.api.mcp_surface", module)

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        assert client.get("/mcp/").text == "bare"


def test_an_optional_module_that_exists_but_cannot_be_imported_stops_the_start(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    from tta.api import hooks

    def broken(name: str) -> Any:
        raise ModuleNotFoundError("No module named 'something_it_needs'", name="something_it_needs")

    monkeypatch.setattr(hooks.importlib, "import_module", broken)

    with pytest.raises(ModuleNotFoundError, match="something_it_needs"):
        hooks.optional_module("tta.ui.routes")
