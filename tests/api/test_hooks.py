"""The hooks for the request parser and the buyer agent (T10). Without that package the gateway answers
without them and says so; a package that is there without its factories stops the start (FIX-8, finding 7).
The MCP surface and the pages: `test_surfaces.py`."""

from __future__ import annotations

import sys
import types
from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.hooks import HookError
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


def test_parse_calls_the_parser_port_and_writes_no_event_when_it_succeeds(with_agent: TestClient, auth: Auth) -> None:
    response = with_agent.post("/v1/requests/parse", json={"text": TEXT}, headers=auth("agent_ward"))

    assert response.status_code == 200
    assert PurchaseRequest.model_validate(response.json()) == TYPED
    # "Request received" is written with the offer that follows, so that an offer has exactly one (T09-1).
    assert with_agent.get("/v1/audit", headers=auth("agent_ward")).json()["events"] == []


def test_what_the_parser_refuses_leaves_as_its_typed_error_and_the_request_is_recorded_as_received(
    with_agent: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    response = with_agent.post("/v1/requests/parse", json={"text": "something"}, headers=auth("agent_ward"))

    assert assert_problem(response, "invalid-request", 422)["detail"] == "The request names no quantity."
    # No offer follows a request that could not be read: this is the only trace of it.
    events = with_agent.get("/v1/audit", headers=auth("agent_ward")).json()["events"]
    assert [event["type"] for event in events] == ["tta.v1.request.received"]
    assert '"something"' in events[0]["sentence"]
    assert events[0]["actor"]["id"] == "agent:allergy-ward"


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
    assert types_seen.count("tta.v1.request.received") == 1  # written with the offer, not a second time by the run
    assert "tta.v1.order.placed_by_agent" in types_seen
    # And it is in the trail of the order, which is found through its offer.
    trail = with_agent.get("/v1/audit", params={"order_id": run.order_id}, headers=auth("agent_ward")).json()
    assert trail["events"][0]["type"] == "tta.v1.request.received"
    assert TEXT in trail["events"][0]["facts"]["text"]


class RunnerWithoutAnOffer:
    """A run that ends before any offer: by a typed error, or with a trace that holds no offer."""

    def __init__(self, *, raises: bool) -> None:
        self._raises = raises

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        if self._raises:
            raise InvalidRequest("The request names no quantity.")
        return AgentRun(text=text, model="recorded", recorded=True, steps=(), report="Nothing was ordered.")


class RunnerThatFailsAfterItsOffer:
    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        tools.create_offer(identity, TYPED)
        raise InvalidRequest("The model named an option the offer does not have.")


@pytest.mark.parametrize("raises", [True, False])
def test_an_agent_run_that_makes_no_offer_records_the_request_as_received(
    settings: Settings, catalog: ProductCatalog, auth: Auth, raises: bool
) -> None:
    parts = build_parts(settings, catalog=catalog, agent_runner=RunnerWithoutAnOffer(raises=raises))
    with TestClient(create_app(settings, parts=parts)) as client:
        response = client.post("/v1/agent/run", json={"text": "Some milk for Monday"}, headers=auth("agent_ward"))
        events = client.get("/v1/audit", headers=auth("agent_ward")).json()["events"]

    assert response.status_code == (422 if raises else 200)
    assert [event["type"] for event in events] == ["tta.v1.request.received"]
    assert '"Some milk for Monday"' in events[0]["sentence"]


def test_an_agent_run_that_fails_after_its_offer_does_not_record_the_request_twice(
    settings: Settings, catalog: ProductCatalog, auth: Auth, assert_problem: Problem
) -> None:
    parts = build_parts(settings, catalog=catalog, agent_runner=RunnerThatFailsAfterItsOffer())
    with TestClient(create_app(settings, parts=parts)) as client:
        response = client.post("/v1/agent/run", json={"text": TEXT}, headers=auth("agent_ward"))
        events = client.get("/v1/audit", headers=auth("agent_ward")).json()["events"]
        received = parts.store.list_audit_events()[0]

    assert_problem(response, "invalid-request", 422)
    assert [event["type"] for event in events].count("tta.v1.request.received") == 1
    assert received.type == "tta.v1.request.received" and received.data.offer_id is not None


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


def test_an_agent_package_that_defines_neither_factory_stops_the_start(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A package that is there and offers nothing is a broken install, not "no agent": say so at the start.
    monkeypatch.setitem(sys.modules, "tta.agent", types.ModuleType("tta.agent"))

    with pytest.raises(HookError) as refused:
        build_parts(settings, catalog=catalog)

    assert "build_request_parser" in str(refused.value) and "build_agent_runner" in str(refused.value)
    assert not settings.db_path.exists()  # stopped before anything was opened


@pytest.mark.parametrize(
    ("defined", "missing", "expected"),
    [
        ("build_request_parser", "build_agent_runner", {"request_parser": True, "agent_runner": False}),
        ("build_agent_runner", "build_request_parser", {"request_parser": False, "agent_runner": True}),
    ],
)
def test_an_agent_package_with_one_factory_starts_and_the_missing_one_is_logged(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    defined: str, missing: str, expected: dict[str, bool],
) -> None:
    module = types.ModuleType("tta.agent")
    setattr(module, defined, lambda **given: FakeParser() if defined == "build_request_parser" else FakeRunner())
    monkeypatch.setitem(sys.modules, "tta.agent", module)

    with caplog.at_level("WARNING", logger="tta.api.hooks"):
        parts = build_parts(settings, catalog=catalog)
    with TestClient(create_app(settings, parts=parts)) as client:
        health = client.get("/healthz").json()

    assert health["agent"] == expected
    warnings = [record.getMessage() for record in caplog.records if record.levelname == "WARNING"]
    assert len(warnings) == 1
    assert missing in warnings[0] and defined not in warnings[0]


def test_parts_handed_in_are_used_without_asking_the_agent_package(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "tta.agent", types.ModuleType("tta.agent"))  # defines neither factory

    parts = build_parts(settings, catalog=catalog, request_parser=FakeParser(), agent_runner=FakeRunner())

    assert (parts.service.has_request_parser, parts.service.has_agent_runner) == (True, True)
    parts.close()
