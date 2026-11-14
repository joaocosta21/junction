"""The gateway service itself, without HTTP: the one object every transport calls (SPEC section 2).

Scores on the 20% "autonomy and controls": what an identity may do is decided here, so it cannot differ
between the REST routes, the MCP tools, the pages and the buyer agent.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.examples import build_examples, scenario_requests
from tta.api.service import Gateway
from tta.api.wiring import Parts, build_parts
from tta.audit import AuditTrail
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import AuditReader, DecisionKind, Identity, OrderStatus, Unit
from tta.contracts.errors import InvalidRequest, NotAuthorised, NotFound, SupplierUnavailable
from tta.contracts.offer import SubstituteQuery
from tta.contracts.order import DecisionRequest
from tta.contracts.ports import GatewayService
from tta.contracts.request import ProductQuery, PurchaseRequest, RequestLine
from tta.store import SqliteStore
from tta.valio import ReplayGateway


@pytest.fixture
def service(parts: Parts) -> Gateway:
    return parts.service


@pytest.fixture
def ward_request(parts: Parts) -> PurchaseRequest:
    return scenario_requests(parts.replay.time_now.date())[1]


def test_the_service_is_the_gateway_port_and_the_wiring_is_the_real_one(parts: Parts) -> None:
    assert isinstance(parts.service, GatewayService)
    assert isinstance(parts.catalog, ProductCatalog)
    assert isinstance(parts.gateway, ReplayGateway)
    assert isinstance(parts.store, SqliteStore)
    assert isinstance(parts.audit, AuditTrail)
    assert parts.clock.now() == parts.replay.time_now


def test_create_app_alone_builds_everything_from_the_settings(
    settings: Settings, auth: Any, scenario_2: dict[str, Any]
) -> None:
    app = create_app(settings)

    with TestClient(app) as client:
        offer = client.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))

    assert offer.status_code == 201
    assert offer.json()["options"][0]["decision"]["verdict"] == "AUTO"
    assert settings.db_path.exists()
    assert len(app.state.parts.catalog.products) > 17_000


def test_the_app_closes_the_database_and_the_live_client_when_it_stops(
    tmp_path: Any, catalog: ProductCatalog
) -> None:
    settings = Settings.for_tests(tta_mode="live", tta_data_dir=tmp_path / "var")  # no key: no call is sent
    parts = build_parts(settings, catalog=catalog)

    with TestClient(create_app(settings, parts=parts)) as client:
        assert client.get("/healthz").status_code == 200

    with pytest.raises(SupplierUnavailable):  # the store reports a closed database as its typed error
        parts.store.list_orders()
    parts.close()  # closing twice is harmless


def test_the_supplier_may_call_nothing_but_the_audit_view(
    service: Gateway, supplier_reader: Identity, ward_request: PurchaseRequest
) -> None:
    refused = (
        lambda: service.get_authority(supplier_reader),
        lambda: service.search_products(supplier_reader, ProductQuery(product_type="milk")),
        lambda: service.get_product(supplier_reader, "464013"),
        lambda: service.find_substitutes(supplier_reader, "473609", SubstituteQuery()),
        lambda: service.create_offer(supplier_reader, ward_request),
        lambda: service.get_offer(supplier_reader, "off_any"),
        lambda: service.place_order(supplier_reader, "off_any", "opt_1", "key-1"),
        lambda: service.get_order(supplier_reader, "ord_any"),
        lambda: service.list_orders(supplier_reader),
        lambda: service.list_approvals(supplier_reader),
        lambda: service.decide_approval(supplier_reader, "apr_any", DecisionRequest(decision=DecisionKind.REJECT)),
        lambda: service.parse_request(supplier_reader, "milk"),
        lambda: service.run_agent(supplier_reader, "milk"),
        lambda: service.get_audit(supplier_reader, AuditReader.BUYER),
    )

    for call in refused:
        with pytest.raises(NotAuthorised):
            call()
    assert service.get_audit(supplier_reader).reader is AuditReader.SUPPLIER
    assert service.get_audit(supplier_reader).events == ()


def test_an_approver_reads_and_decides_but_never_asks_or_orders(
    service: Gateway, approver_dietitian: Identity, agent_ward: Identity, ward_request: PurchaseRequest
) -> None:
    offer = service.create_offer(agent_ward, ward_request)

    assert service.get_authority(approver_dietitian).profile.profile_id == "allergy-ward"
    assert service.get_offer(approver_dietitian, offer.offer_id) == offer
    assert service.get_product(approver_dietitian, "464013").id == "464013"
    assert service.list_approvals(approver_dietitian) == ()
    assert service.list_orders(approver_dietitian) == ()
    for call in (
        lambda: service.create_offer(approver_dietitian, ward_request),
        lambda: service.find_substitutes(approver_dietitian, "473609", SubstituteQuery()),
        lambda: service.place_order(approver_dietitian, offer.offer_id, "opt_1", "key-1"),
        lambda: service.parse_request(approver_dietitian, "milk"),
        lambda: service.run_agent(approver_dietitian, "milk"),
    ):
        with pytest.raises(NotAuthorised):
            call()


def test_an_agent_reads_only_its_own_buyers_offers(
    service: Gateway, agent_ward: Identity, agent_hotel: Identity, ward_request: PurchaseRequest
) -> None:
    offer = service.create_offer(agent_ward, ward_request)

    with pytest.raises(NotFound) as other_buyer:
        service.get_offer(agent_hotel, offer.offer_id)
    with pytest.raises(NotFound) as nobody:
        service.get_offer(agent_hotel, "off_nobody")
    with pytest.raises(NotFound):
        service.get_audit(agent_hotel, offer_id=offer.offer_id)

    assert other_buyer.value.detail == nobody.value.detail
    assert offer.offer_id not in other_buyer.value.detail


def test_the_agent_is_refused_on_the_approval_queue(service: Gateway, agent_hotel: Identity) -> None:
    with pytest.raises(NotAuthorised, match="F-06"):
        service.list_approvals(agent_hotel)


def test_a_request_over_1000_product_ids_is_refused_before_any_lookup(
    service: Gateway, agent_hotel: Identity
) -> None:
    ids = tuple(str(400000 + number) for number in range(600))
    line = RequestLine(text="these", product_ids=ids, quantity=Decimal(1), unit=Unit.UNIT)

    with pytest.raises(InvalidRequest, match="1,200"):
        service.create_offer(agent_hotel, PurchaseRequest(lines=(line, line)))


def test_a_listed_waiting_order_is_read_through_the_order_book(
    service: Gateway, parts: Parts, agent_hotel: Identity
) -> None:
    request = scenario_requests(parts.replay.time_now.date())[0]
    offer = service.create_offer(agent_hotel, request)
    order = service.place_order(agent_hotel, offer.offer_id, offer.options[0].option_id, "key-1")

    listed = service.list_orders(agent_hotel)

    assert order.status is OrderStatus.PENDING_APPROVAL
    assert listed == (order,)


# --- the examples of /openapi.json ----------------------------------------------------------------------


def test_the_examples_are_built_in_a_private_store_and_leave_the_real_one_empty(parts: Parts) -> None:
    requests, answers = build_examples(parts)

    assert {"create_offer", "place_order", "decide_approval", "search_products", "find_substitutes"} <= set(requests)
    assert {"get_authority", "get_offer", "get_order", "list_orders", "list_approvals", "get_audit"} <= set(answers)
    assert parts.store.list_orders() == ()
    assert parts.audit.head()[0] == 0


def test_examples_from_a_capture_that_holds_no_scenario_product_are_fewer_not_wrong(
    tmp_path: Any, catalog: ProductCatalog
) -> None:
    # Friday's 37 probe ids: no scenario of the demonstration can be filled from them.
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_replay_capture="2026-11-13-extras")
    parts = build_parts(settings, catalog=catalog)

    requests, answers = build_examples(parts)

    assert "create_offer" in answers
    for example in answers["create_offer"].values():
        assert example["value"]["source"] == "replay"
    with TestClient(create_app(settings, parts=parts)) as client:
        assert client.get("/openapi.json").status_code == 200


def test_examples_stop_at_the_first_scenario_that_cannot_be_run(
    parts: Parts, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def down(product_ids: Any, *, fresh: bool = False) -> Any:
        raise SupplierUnavailable("The replay capture cannot be used.")

    monkeypatch.setattr(parts.replay, "availability", down)

    with caplog.at_level(logging.WARNING, logger="tta.api.examples"):
        requests, answers = build_examples(parts)

    assert "get_authority" in answers and "search_products" in answers
    assert "create_offer" not in answers
    assert "supplier-unavailable" in caplog.text
