"""Who read a request is said; a run of the buyer agent never hides an order; an order is found by its offer.

Task FIX-10, findings 5, 4 and 11. Scores on the 20% "solving the problem" (the reader of a request is named,
a recording is never passed off as the model), the 20% "decisions logged and auditable" and the 30% demo
(no order is lost behind an error).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app, service
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.agent import AgentRun, Reading, ReadingSource
from tta.contracts.common import DecisionKind, Identity, OrderStatus, Unit
from tta.contracts.errors import InvalidRequest, NotFound, SupplierUnavailable
from tta.contracts.order import DecisionRequest
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
SECRET_LOOKING = "sdk-said-something-with-a-key-AIza0123456789"


class OldParser:
    """A parser with the port as it was: `parse_request` and a model id, no `read`."""

    model_id = "gemini-3.6-flash"

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        return TYPED


class ReadingParser:
    """A parser that says who read the text (task FIX-9): here, a recording served while Gemini was down."""

    def __init__(self, model: str = "gemini-3.6-flash", source: ReadingSource = ReadingSource.RECORDING) -> None:
        self.reading = Reading(
            request=TYPED, source=source, model=model, recorded_at=datetime(2026, 11, 14, 6, 14, tzinfo=UTC),
            sentence="Gemini did not answer; read from a recording of gemini-3.6-flash made on 14 Nov 2026.",
        )
        self.reads = 0

    def read(self, text: str, identity: Identity) -> Reading:
        self.reads += 1
        return self.reading

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        raise AssertionError("the gateway asks `read` when the parser has it")


class DownParser:
    def read(self, text: str, identity: Identity) -> Reading:
        raise SupplierUnavailable("The language model cannot be reached.")

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        raise SupplierUnavailable("The language model cannot be reached.")


class RunnerThatBreaksAfterItsOrder:
    """Places the order through the gateway, then fails with an error of its own (an SDK fault, a bug)."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        offer = tools.create_offer(identity, TYPED)
        tools.place_order(identity, offer.offer_id, offer.options[0].option_id, "agent-run-1")
        raise self._error


class RunnerThatBreaksBeforeAnyOrder:
    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        tools.create_offer(identity, TYPED)
        raise RuntimeError(SECRET_LOOKING)


def _client(settings: Settings, catalog: ProductCatalog, **parts: Any) -> TestClient:
    return TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog, **parts)),
                      raise_server_exceptions=False)


# --- finding 5: who read the request ----------------------------------------------------------------------


def test_a_parser_that_says_who_read_the_text_is_asked_for_its_reading(
    settings: Settings, catalog: ProductCatalog, agent_ward: Identity
) -> None:
    parser = ReadingParser()
    parts = build_parts(settings, catalog=catalog, request_parser=parser)

    reading = parts.service.read_request(agent_ward, TEXT)

    assert reading == parser.reading and parser.reads == 1
    assert parts.service.parse_request(agent_ward, TEXT) == TYPED  # the old function gives the reading's request
    parts.close()


def test_a_parser_of_the_old_port_is_named_by_its_model_id_as_the_model_that_read_it(
    settings: Settings, catalog: ProductCatalog, agent_ward: Identity
) -> None:
    parts = build_parts(settings, catalog=catalog, request_parser=OldParser())

    reading = parts.service.read_request(agent_ward, TEXT)

    assert (reading.request, reading.source, reading.model) == (TYPED, ReadingSource.MODEL, "gemini-3.6-flash")
    assert reading.recorded_at is None and reading.sentence == "Read by gemini-3.6-flash."
    parts.close()


@pytest.mark.parametrize(
    ("parser", "read_by", "source"),
    [
        (OldParser(), "gemini-3.6-flash", "model"),
        (ReadingParser(), "gemini-3.6-flash", "recording"),
        (ReadingParser(model="hand-built", source=ReadingSource.HAND_BUILT), "hand-built", "hand-built"),
        (ReadingParser(model="a model\r\nX-Injected: yes"), "unknown", "recording"),
    ],
)
def test_the_parse_route_keeps_its_body_and_names_the_reader_in_two_headers(
    settings: Settings, catalog: ProductCatalog, auth: Auth, parser: Any, read_by: str, source: str
) -> None:
    with _client(settings, catalog, request_parser=parser) as client:
        response = client.post("/v1/requests/parse", json={"text": TEXT}, headers=auth("agent_ward"))

    assert response.status_code == 200
    assert PurchaseRequest.model_validate(response.json()) == TYPED
    assert (response.headers["tta-read-by"], response.headers["tta-reading-source"]) == (read_by, source)
    assert "x-injected" not in response.headers


def test_a_reading_that_fails_is_its_typed_error_and_the_request_is_recorded_as_received(
    settings: Settings, catalog: ProductCatalog, auth: Auth, assert_problem: Problem
) -> None:
    with _client(settings, catalog, request_parser=DownParser()) as client:
        response = client.post("/v1/requests/parse", json={"text": TEXT}, headers=auth("agent_ward"))
        events = client.get("/v1/audit", headers=auth("agent_ward")).json()["events"]

    assert_problem(response, "supplier-unavailable", 503)
    assert "tta-read-by" not in response.headers
    assert [event["type"] for event in events] == ["tta.v1.request.received"]


# --- finding 4: a run never hides an order ----------------------------------------------------------------


@pytest.mark.parametrize("error", [RuntimeError(SECRET_LOOKING), InvalidRequest(SECRET_LOOKING)])
def test_a_run_that_breaks_after_its_order_is_answered_with_the_order_never_a_500(
    settings: Settings, catalog: ProductCatalog, auth: Auth, error: Exception
) -> None:
    with _client(settings, catalog, agent_runner=RunnerThatBreaksAfterItsOrder(error)) as client:
        response = client.post("/v1/agent/run", json={"text": TEXT}, headers=auth("agent_ward"))
        orders = client.get("/v1/orders", headers=auth("agent_ward")).json()

    assert response.status_code == 200, response.text
    run = AgentRun.model_validate(response.json())
    assert [order["order_id"] for order in orders] == [run.order_id]
    assert run.order_status is OrderStatus.ORDERED and run.offer_id == orders[0]["offer_id"]
    assert run.report.startswith("The buyer agent stopped on an error")
    assert type(error).__name__ in run.report and run.order_id in run.report
    assert SECRET_LOOKING not in response.text


def test_a_run_that_breaks_before_any_order_is_its_error_as_before(
    settings: Settings, catalog: ProductCatalog, auth: Auth
) -> None:
    with _client(settings, catalog, agent_runner=RunnerThatBreaksBeforeAnyOrder()) as client:
        response = client.post("/v1/agent/run", json={"text": TEXT}, headers=auth("agent_ward"))

    assert response.status_code == 500
    assert SECRET_LOOKING not in response.text


# --- finding 11: the order of an offer, read through the store ---------------------------------------------


def test_the_order_of_an_offer_is_found_beyond_the_newest_hundred(
    settings: Settings, catalog: ProductCatalog, agent_ward: Identity, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "MAX_LIST_ITEMS", 2)  # stands for the 100 of a list
    parts = build_parts(settings, catalog=catalog)
    gateway = parts.service
    small = TYPED.model_copy(update={"lines": (TYPED.lines[0].model_copy(update={"quantity": Decimal(1)}),)})
    offers = [gateway.create_offer(agent_ward, small) for _ in range(3)]
    orders = [gateway.place_order(agent_ward, offer.offer_id, offer.options[0].option_id, f"k-{number}")
              for number, offer in enumerate(offers)]
    unordered = gateway.create_offer(agent_ward, small)

    assert offers[0].offer_id not in {order.offer_id for order in gateway.list_orders(agent_ward)}
    assert gateway.order_for_offer(agent_ward, offers[0].offer_id) == orders[0]
    assert gateway.order_for_offer(agent_ward, unordered.offer_id) is None
    parts.close()


def test_the_order_of_an_offer_is_its_newest_and_another_buyer_reads_no_offer(
    settings: Settings, catalog: ProductCatalog, agent_hotel: Identity, agent_ward: Identity,
    approver_purchasing: Identity,
) -> None:
    parts = build_parts(settings, catalog=catalog)
    gateway = parts.service
    milk = PurchaseRequest(needed_by=date(2026, 11, 16), lines=(RequestLine(
        text="milk", product_type="milk", required_claims=("FREE_FROM_LACTOSE",), quantity=Decimal(1000),
        unit=Unit.L,
    ),))
    offer = gateway.create_offer(agent_hotel, milk)
    first = gateway.place_order(agent_hotel, offer.offer_id, offer.options[0].option_id, "k-1")
    gateway.decide_approval(approver_purchasing, first.approval_id, DecisionRequest(decision=DecisionKind.REJECT))
    second = gateway.place_order(agent_hotel, offer.offer_id, offer.options[0].option_id, "k-2")

    assert gateway.order_for_offer(agent_hotel, offer.offer_id).order_id == second.order_id
    with pytest.raises(NotFound):
        gateway.order_for_offer(agent_ward, offer.offer_id)
    parts.close()
