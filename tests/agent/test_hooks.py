"""The two hooks the gateway calls (`tta.api.hooks`), and the whole flow from a pasted sentence."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import tta.agent
from tta.agent import build_agent_runner, build_request_parser, profile_strictness
from tta.agent.gemini import DEFAULT_MODEL
from tta.agent.recorded import RECORDED_MODEL_ID
from tta.api import create_app
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.agent import AgentRun
from tta.contracts.common import AllergenStrictness, Identity, OrderStatus
from tta.contracts.errors import InvalidRequest, NotAuthorised, SupplierUnavailable
from tta.contracts.ports import AgentRunner, Clock, RequestParser

KEY = "test-key-2b8d4f6a0c"  # not a real key
WARD_TOKEN = {"Authorization": "Bearer demo-agent-allergy-ward"}
HOTEL_TOKEN = {"Authorization": "Bearer demo-agent-hotel-kitchen"}


def test_without_a_key_both_hooks_return_the_recorded_versions(
    demo_clock: Clock, product_type_keys: tuple[str, ...]
) -> None:
    given = {"settings": Settings.for_tests(), "clock": demo_clock, "product_type_keys": product_type_keys}

    parser, runner = build_request_parser(**given), build_agent_runner(**given)

    assert isinstance(parser, RequestParser) and isinstance(runner, AgentRunner)
    assert parser.model_id == runner.model_id == RECORDED_MODEL_ID


def test_with_a_key_both_hooks_use_the_gemini_model_and_call_nothing_while_they_are_built(
    demo_clock: Clock, product_type_keys: tuple[str, ...]
) -> None:
    settings = Settings.for_tests(gemini_api_key=KEY, tta_gemini_model="gemini-3.6-flash")
    given = {"clock": demo_clock, "product_type_keys": product_type_keys}

    parser = build_request_parser(settings=Settings.for_tests(gemini_api_key=KEY), **given)
    runner = build_agent_runner(settings=settings, **given)

    assert isinstance(parser, RequestParser) and isinstance(runner, AgentRunner)
    assert (parser.model_id, runner.model_id) == (DEFAULT_MODEL, "gemini-3.6-flash")
    assert KEY not in repr(parser.__dict__) and KEY not in repr(runner.__dict__)


def test_the_package_exports_the_two_hooks_by_the_names_the_gateway_looks_for() -> None:
    assert tta.agent.build_request_parser is build_request_parser
    assert tta.agent.build_agent_runner is build_agent_runner


def test_the_strictness_of_a_profile_is_read_from_the_policy_files() -> None:
    strictness = profile_strictness()

    assert strictness("allergy-ward") is AllergenStrictness.STRICT
    assert strictness("hotel-kitchen") is None
    with pytest.raises(NotAuthorised):
        strictness("no-such-profile")


# --- through the gateway service, wired by the real hooks -------------------------------------------------


def test_the_gateway_reads_a_pasted_sentence_with_the_recorded_parser(
    parts: Parts, agent_hotel: Identity, texts: dict[str, str]
) -> None:
    request = parts.service.parse_request(agent_hotel, texts["scenario_1"])

    assert request.needed_by == date(2026, 11, 16)
    assert (request.lines[0].product_type, request.lines[0].quantity) == ("milk", Decimal(1000))
    with pytest.raises(InvalidRequest):
        parts.service.parse_request(agent_hotel, texts["no_quantity"])
    with pytest.raises(InvalidRequest) as asked:  # with no model, an unread text is a question (replan A2b M1)
        parts.service.parse_request(agent_hotel, "a sentence nobody recorded")
    assert not isinstance(asked.value, SupplierUnavailable) and "How much is needed" in asked.value.detail


def test_a_run_through_the_gateway_orders_and_records_the_pasted_text_once(
    parts: Parts, agent_ward: Identity, texts: dict[str, str]
) -> None:
    run = parts.service.run_agent(agent_ward, texts["scenario_2"])

    assert run.order_status is OrderStatus.PENDING_APPROVAL and run.recorded is True
    types = [str(event.type) for event in parts.service.get_audit(agent_ward).events]
    assert types[0].endswith("request.received")
    assert sum(1 for name in types if name.endswith("request.received")) == 1  # the runner parses on its own
    assert any(name.endswith("approval.requested") for name in types)


def test_health_names_gemini_as_the_reader_when_a_key_is_set_though_the_provider_says_none(
    tmp_path: Path, catalog: ProductCatalog, without_other_surfaces: None
) -> None:
    """`TTA_AGENT_PROVIDER=none` with a Gemini key: the hooks build the Gemini model and it is asked first, so
    /healthz must not read as "no model". Building the gateway and asking /healthz call no model."""
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", gemini_api_key=KEY)
    built = build_parts(settings, catalog=catalog)

    with TestClient(create_app(settings, parts=built)) as client:
        health = client.get("/healthz").json()

    assert (health["settings"]["agent_provider"], health["settings"]["gemini_key_set"]) == ("none", True)
    assert (health["agent_reader"]["kind"], health["agent_reader"]["model"]) == ("gemini", None)
    assert health["agent_reader"]["sentence"].startswith("Gemini is asked first, because a Gemini key is set")
    assert KEY not in json.dumps(health)


# --- through the REST routes ------------------------------------------------------------------------------


@pytest.fixture
def client(settings: Settings, parts: Parts, without_other_surfaces: None) -> TestClient:
    return TestClient(create_app(settings, parts=parts))


def test_the_routes_of_the_buyer_agent_answer_from_a_pasted_sentence_without_a_key(
    client: TestClient, texts: dict[str, str]
) -> None:
    with client:
        health = client.get("/healthz").json()
        parsed = client.post("/v1/requests/parse", json={"text": texts["scenario_1"]}, headers=HOTEL_TOKEN)
        missing = client.post("/v1/requests/parse", json={"text": texts["no_quantity"]}, headers=HOTEL_TOKEN)
        ran = client.post("/v1/agent/run", json={"text": texts["scenario_2"]}, headers=WARD_TOKEN)

    assert health["agent"] == {"request_parser": True, "agent_runner": True}
    # No key and no endpoint: no model is asked, and /healthz says so.
    assert (health["agent_reader"]["kind"], health["agent_reader"]["model"]) == ("fixed_rules", None)
    assert parsed.status_code == 200 and parsed.json()["lines"][0]["required_claims"] == ["FREE_FROM_LACTOSE"]
    assert missing.status_code == 422 and missing.json()["type"].endswith("invalid-request")
    assert missing.json()["missing"] == ["lines[0].quantity"]
    run = AgentRun.model_validate(ran.json())
    assert ran.status_code == 200 and run.order_status is OrderStatus.PENDING_APPROVAL
    assert [step.tool for step in run.steps] == ["get_authority", "create_offer", "place_order"]
