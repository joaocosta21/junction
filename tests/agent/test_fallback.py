"""With a key set and Gemini out of reach, a sentence that has a recording is answered from it, and says so."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

import tta.agent
from tta.agent import gemini as gemini_module
from tta.agent.fallback import FallbackParser, FallbackRunner
from tta.agent.gemini import DEFAULT_MODEL, GeminiModel, ModelUnreachable, sdk_transport
from tta.agent.parser import ModelRequestParser
from tta.agent.recorded import RecordedModel
from tta.agent.runner import ModelAgentRunner
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import Identity, OrderStatus
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import Clock, GatewayService

KEY = "test-key-5c1e9a7f3b"  # not a real key
SERVED = "Gemini did not answer; this run was served from "
WARD_TEXT = "200 litres of plant drink, no milk, no gluten"
HAPPY_PATH = [[("get_authority", {})], [("create_offer", {})], [("place_order", {"option_id": "opt_1"})]]
Handler = Callable[[httpx.Request], httpx.Response]
Build = Callable[..., tuple[FallbackParser, FallbackRunner, "FakeGemini"]]


class FakeGemini:
    """Answers like `generateContent`; the last answer repeats."""

    def __init__(self, *answers: Handler) -> None:
        self._answers = list(answers)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return (self._answers.pop(0) if len(self._answers) > 1 else self._answers[0])(request)


def _busy(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503, json={"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}})


def _refused(request: httpx.Request) -> httpx.Response:
    return httpx.Response(403, json={"error": {"code": 403, "message": "no", "status": "PERMISSION_DENIED"}})


def _answer(part: dict[str, Any]) -> Handler:
    body = {"candidates": [{"content": {"role": "model", "parts": [part]}, "finishReason": "STOP"}]}
    return lambda request: httpx.Response(200, json=body)


def _reading(proposal: str) -> Handler:
    return _answer({"text": proposal})


def _calls(name: str) -> Handler:
    return _answer({"functionCall": {"id": "fc_1", "name": name, "args": {}}, "thoughtSignature": "c2ln"})


def _recordings(directory: Path, *, source: str = "live", run_source: str | None = None) -> RecordedModel:
    """A parse and a run of `WARD_TEXT`, as the live check writes them."""
    common = {"text": WARD_TEXT, "model": DEFAULT_MODEL, "today": "2026-11-14",
              "recorded_at": "2026-11-14T08:05:00+00:00"}
    line = {"product_type": "plant_drink", "product_ids": [], "name_terms": [], "required_claims": [],
            "quantity": 200, "unit": "L", "exclude_allergens": ["AM", "AW"], "allergen_strictness": None, "pack": None}
    parse = {**common, "kind": "parse", "source": source,
             "proposal": {"needed_by": "2026-11-16", "require_confirmed": True, "lines": [line]}}
    turns = [{"calls": [{"name": name, "arguments": arguments} for name, arguments in turn]} for turn in HAPPY_PATH]
    run = {**common, "kind": "run", "source": run_source or source, "turns": turns}
    for name, recording in (("parse-ward", parse), ("run-ward", run)):
        (directory / f"{name}.json").write_text(json.dumps(recording), encoding="utf-8")
    return RecordedModel(directory)


@pytest.fixture
def build(make_parser: Callable[..., ModelRequestParser], demo_clock: Clock, recorded_model: RecordedModel) -> Build:
    """The parser and the runner as the hooks build them with a key: Gemini first, the recordings behind it."""

    def make(*answers: Handler, recordings: RecordedModel = recorded_model) -> tuple[Any, ...]:
        fake = FakeGemini(*answers)
        transport = sdk_transport(Settings.for_tests(gemini_api_key=KEY),
                                  client_args={"transport": httpx.MockTransport(fake)})
        live = GeminiModel(transport, DEFAULT_MODEL, sleep=lambda seconds: None)
        live_parser, recorded_parser = make_parser(live, demo_clock), make_parser(recordings, demo_clock)
        parser = FallbackParser(live=live_parser, recorded=recorded_parser, recordings=recordings)
        runner = FallbackRunner(
            live=ModelAgentRunner(model=live, parser=live_parser),
            recorded=ModelAgentRunner(model=recordings, parser=recorded_parser), recordings=recordings,
        )
        return parser, runner, fake

    return make


# --- the parser -------------------------------------------------------------------------------------------


def test_when_gemini_does_not_answer_a_recorded_sentence_is_read_from_its_recording(
    build: Build, make_parser: Callable[..., ModelRequestParser], recorded_model: RecordedModel, demo_clock: Clock,
    agent_hotel: Identity, texts: dict[str, str], caplog: pytest.LogCaptureFixture,
) -> None:
    parser, _, fake = build(_busy)

    with caplog.at_level(logging.WARNING):
        request = parser.parse_request(texts["scenario_1"], agent_hotel)

    assert request == make_parser(recorded_model, demo_clock).parse_request(texts["scenario_1"], agent_hotel)
    assert parser.model_id == DEFAULT_MODEL
    assert len(fake.requests) == 3  # Gemini was asked, with its two retries, before the recording stood in
    assert "Gemini did not answer; this request was read from " in caplog.text


def test_when_gemini_answers_its_own_reading_is_used(
    build: Build, proposal: Callable[..., str], agent_hotel: Identity, texts: dict[str, str]
) -> None:
    parser, _, _ = build(_reading(proposal(required_claims=["FREE_FROM_LACTOSE"], quantity=900)))

    request = parser.parse_request(texts["scenario_1"], agent_hotel)

    assert request.lines[0].quantity == 900  # not the recording's 1,000


@pytest.mark.parametrize("failure", [_busy, _refused])
def test_a_sentence_with_no_recording_is_still_supplier_unavailable(
    build: Build, agent_hotel: Identity, failure: Handler
) -> None:
    parser, _, _ = build(failure)

    with pytest.raises(SupplierUnavailable) as refused:
        parser.parse_request("7 kg of cheese by Friday", agent_hotel)

    assert "did not answer" in refused.value.detail or "refused" in refused.value.detail


def test_a_refusal_is_not_covered_by_a_recording(build: Build, agent_hotel: Identity, texts: dict[str, str]) -> None:
    parser, _, fake = build(_refused)

    with pytest.raises(SupplierUnavailable) as refused:
        parser.parse_request(texts["scenario_1"], agent_hotel)

    assert not isinstance(refused.value, ModelUnreachable) and "403" in refused.value.detail
    assert len(fake.requests) == 1


# --- the runner -------------------------------------------------------------------------------------------


def test_when_gemini_does_not_answer_a_recorded_run_is_served_from_its_recording_and_says_so(
    build: Build, parts: Any, agent_ward: Identity, texts: dict[str, str], shown_as: Callable[[str], str]
) -> None:
    _, runner, fake = build(_busy)

    run = runner.run_agent(texts["scenario_2"], agent_ward, parts.service)

    order = parts.service.get_order(agent_ward, run.order_id)
    assert run.order_status is OrderStatus.ORDERED
    assert (run.model, run.recorded) == (shown_as(texts["scenario_2"]), True)  # the trace names the recording
    assert run.report.startswith(SERVED)
    assert order.status_sentence in run.report
    assert runner.model_id == DEFAULT_MODEL
    assert len(fake.requests) == 3


def test_the_report_names_when_the_recording_was_made(
    build: Build, parts: Any, agent_ward: Identity, tmp_path: Path
) -> None:
    _, runner, _ = build(_busy, recordings=_recordings(tmp_path))

    run = runner.run_agent(WARD_TEXT, agent_ward, parts.service)

    assert run.report.startswith(SERVED + "a recording made on 14 Nov 2026 at 08:05 UTC. ")
    assert (run.model, run.order_status) == ("recorded", OrderStatus.ORDERED)


def test_a_run_whose_answers_a_person_wrote_is_said_to_be_so(
    build: Build, parts: Any, agent_ward: Identity, tmp_path: Path
) -> None:
    _, runner, _ = build(_busy, recordings=_recordings(tmp_path, run_source="hand-built"))

    run = runner.run_agent(WARD_TEXT, agent_ward, parts.service)

    assert run.report.startswith(SERVED + "answers written by hand, not by a model. ")
    assert run.model == "hand-built"


def test_a_run_whose_first_turn_fails_is_served_whole_from_the_recording(
    build: Build, ward_answer: str, parts: Any, agent_ward: Identity, tmp_path: Path
) -> None:
    _, runner, fake = build(_reading(ward_answer), _busy, recordings=_recordings(tmp_path))

    run = runner.run_agent(WARD_TEXT, agent_ward, parts.service)

    assert run.recorded is True and run.report.startswith(SERVED)
    assert [step.tool for step in run.steps] == ["get_authority", "create_offer", "place_order"]
    assert len(fake.requests) == 4  # the reading, then the first turn three times


def test_a_model_that_stops_after_a_step_is_not_replaced_by_the_recording(
    build: Build, ward_answer: str, parts: Any, agent_ward: Identity, tmp_path: Path
) -> None:
    _, runner, _ = build(_reading(ward_answer), _calls("get_authority"), _busy, recordings=_recordings(tmp_path))

    run = runner.run_agent(WARD_TEXT, agent_ward, parts.service)

    assert (run.model, run.recorded) == (DEFAULT_MODEL, False)  # what Gemini did stands, under its name
    assert [step.tool for step in run.steps] == ["get_authority"]
    assert "stopped answering" in run.report and SERVED not in run.report


@pytest.mark.parametrize("failure", [_busy, _refused])
def test_a_run_with_no_recording_is_still_supplier_unavailable(
    build: Build, parts: Any, agent_ward: Identity, failure: Handler
) -> None:
    _, runner, _ = build(failure)

    with pytest.raises(SupplierUnavailable):
        runner.run_agent("7 kg of cheese by Friday", agent_ward, parts.service)

    assert parts.service.get_audit(agent_ward).events == ()


def test_a_refused_run_is_not_served_from_its_recording(
    build: Build, parts: Any, agent_ward: Identity, texts: dict[str, str]
) -> None:
    _, runner, _ = build(_refused)

    with pytest.raises(SupplierUnavailable) as refused:
        runner.run_agent(texts["scenario_2"], agent_ward, parts.service)

    assert not isinstance(refused.value, ModelUnreachable)


# --- through the gateway, wired by the real hooks ---------------------------------------------------------


@pytest.fixture
def gemini_down(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGemini]:
    """Every request the hooks' Gemini model sends answers 503, at once and without waiting between tries."""
    fake = FakeGemini(_busy)
    real = gemini_module.sdk_transport
    monkeypatch.setattr(tta.agent, "sdk_transport",
                        lambda settings: real(settings, client_args={"transport": httpx.MockTransport(fake)}))
    monkeypatch.setattr(gemini_module, "RETRY_WAIT_SECONDS", 0.0)
    yield fake


def test_with_a_key_set_and_gemini_down_the_gateway_serves_the_demonstration_from_the_recordings(
    settings: Settings, catalog: ProductCatalog, gemini_down: FakeGemini, agent_hotel: Identity,
    agent_ward: Identity, texts: dict[str, str],
) -> None:
    keyed = settings.model_copy(update={"gemini_api_key": SecretStr(KEY)})
    parts = build_parts(keyed, catalog=catalog)
    try:
        service: GatewayService = parts.service
        request = service.parse_request(agent_hotel, texts["scenario_1"])
        run = service.run_agent(agent_ward, texts["scenario_2"])
        events = [str(event.type) for event in service.get_audit(agent_ward).events]
    finally:
        parts.close()

    assert (request.lines[0].product_type, request.lines[0].quantity) == ("milk", 1000)
    assert run.order_status is OrderStatus.ORDERED and run.report.startswith(SERVED)
    assert sum(1 for name in events if name.endswith("request.received")) == 1
    assert len(gemini_down.requests) == 6  # three tries for the reading of each sentence
    assert KEY not in run.model_dump_json()


def test_the_recordings_say_when_they_were_made(fixtures_agent_dir: Path) -> None:
    """A live recording carries the moment it was made, which the report repeats."""
    for path in fixtures_agent_dir.glob("*.json"):
        recording = json.loads(path.read_text(encoding="utf-8"))
        if recording["source"] == "live":
            assert datetime.fromisoformat(recording["recorded_at"]).tzinfo is not None
            assert datetime.fromisoformat(recording["recorded_at"]) <= datetime.now(UTC)
