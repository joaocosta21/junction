"""With a key set and Gemini out of reach, a sentence that has a recording is answered from it, and says so."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
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
from tta.agent.outage import OUTAGE_MEMORY_SECONDS, PROCESS_OUTAGE, Outage
from tta.agent.parser import ModelRequestParser
from tta.agent.recorded import RecordedModel
from tta.agent.rules_model import RuleModel
from tta.agent.runner import ModelAgentRunner
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.agent import ReadingSource
from tta.contracts.common import Identity, OrderStatus
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import Clock, GatewayService

KEY = "test-key-5c1e9a7f3b"  # not a real key
SERVED = "Gemini did not answer; this run was served from "
WARD_TEXT = "200 litres of plant drink by Monday, no milk, no gluten, confirmed data only"
READ_FROM_THE_RECORDING = (
    "Gemini did not answer; read from a recording of gemini-3.6-flash made on 14 Nov 2026 at 07:13 UTC."
)
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
    return httpx.Response(400, json={"error": {"code": 400, "message": "no", "status": "INVALID_ARGUMENT"}})


def _answer(part: dict[str, Any]) -> Handler:
    body = {"candidates": [{"content": {"role": "model", "parts": [part]}, "finishReason": "STOP"}]}
    return lambda request: httpx.Response(200, json=body)


def _reading(proposal: str) -> Handler:
    return _answer({"text": proposal})


def _calls(name: str) -> Handler:
    return _answer({"functionCall": {"id": "fc_1", "name": name, "args": {}}, "thoughtSignature": "c2ln"})


def _recordings(directory: Path, *, source: str = "live", run_source: str | None = None) -> RecordedModel:
    """A parse and a run of `WARD_TEXT`, as the live check writes them."""
    common = {"text": WARD_TEXT, "profile_id": "allergy-ward", "model": DEFAULT_MODEL, "today": "2026-11-14",
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


class Ticking:
    """A monotonic clock a test moves by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def ticking() -> Ticking:
    return Ticking()


@pytest.fixture
def build(
    make_parser: Callable[..., ModelRequestParser], demo_clock: Clock, recorded_model: RecordedModel, ticking: Ticking,
    product_type_keys: tuple[str, ...],
) -> Build:
    """The parser and the runner as the hooks build them with a key: Gemini first, the recordings behind it,
    and a memory of an outage on a clock the test moves. With `rules`, the fixed rules behind the recordings."""

    def make(*answers: Handler, recordings: RecordedModel = recorded_model, rules: bool = False) -> tuple[Any, ...]:
        fake = FakeGemini(*answers)
        transport = sdk_transport(Settings.for_tests(gemini_api_key=KEY),
                                  client_args={"transport": httpx.MockTransport(fake)})
        live = GeminiModel(transport, DEFAULT_MODEL, sleep=lambda seconds: None, outage=Outage(clock=ticking))
        live_parser, recorded_parser = make_parser(live, demo_clock), make_parser(recordings, demo_clock)
        rule_model = RuleModel.for_keys(product_type_keys)
        rule_parser = make_parser(rule_model, demo_clock) if rules else None
        parser = FallbackParser(live=live_parser, recorded=recorded_parser, recordings=recordings, rules=rule_parser)
        runner = FallbackRunner(
            live=ModelAgentRunner(model=live, parser=live_parser),
            recorded=ModelAgentRunner(model=recordings, parser=recorded_parser), recordings=recordings,
            rules=ModelAgentRunner(model=rule_model, parser=rule_parser) if rule_parser else None,
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
    assert len(fake.requests) == 2  # Gemini was asked, with its one retry, before the recording stood in
    assert READ_FROM_THE_RECORDING in caplog.text


def test_a_reading_from_the_recording_says_so_and_the_parser_names_what_answered(
    build: Build, proposal: Callable[..., str], agent_hotel: Identity, texts: dict[str, str], ticking: Ticking
) -> None:
    parser, _, _ = build(_busy, _busy, _reading(proposal(required_claims=["FREE_FROM_LACTOSE"], quantity=1000)))
    assert parser.model_id == DEFAULT_MODEL

    reading = parser.read(texts["scenario_1"], agent_hotel)

    assert (reading.source, reading.model) == (ReadingSource.RECORDING, "gemini-3.6-flash")
    assert reading.sentence == READ_FROM_THE_RECORDING
    assert parser.model_id == "recorded"  # the recording answered, not Gemini
    ticking.now += OUTAGE_MEMORY_SECONDS
    again = parser.read(texts["scenario_1"], agent_hotel)
    assert (again.source, again.sentence, parser.model_id) == (ReadingSource.MODEL, f"Read by {DEFAULT_MODEL}.",
                                                                 DEFAULT_MODEL)


def test_when_gemini_answers_its_own_reading_is_used(
    build: Build, proposal: Callable[..., str], agent_hotel: Identity, texts: dict[str, str]
) -> None:
    parser, _, _ = build(_reading(proposal(required_claims=["FREE_FROM_LACTOSE"], quantity=1000, pack="ANY")))

    reading = parser.read(texts["scenario_1"], agent_hotel)

    assert (reading.source, reading.model) == (ReadingSource.MODEL, DEFAULT_MODEL)
    assert reading.request.lines[0].pack == "ANY"  # not the recording's, which says nothing of the pack


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

    assert not isinstance(refused.value, ModelUnreachable) and "400" in refused.value.detail
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
    assert len(fake.requests) == 2


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
    assert len(fake.requests) == 3  # the reading, then the first turn twice


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
    assert len(gemini_down.requests) == 2  # two tries for the first sentence; the second is not sent at all
    assert PROCESS_OUTAGE.is_open()
    assert KEY not in run.model_dump_json()


def test_the_recordings_say_when_they_were_made(fixtures_agent_dir: Path) -> None:
    """A live recording carries the moment it was made, which the report repeats."""
    for path in fixtures_agent_dir.glob("*.json"):
        recording = json.loads(path.read_text(encoding="utf-8"))
        if recording["source"] == "live":
            assert datetime.fromisoformat(recording["recorded_at"]).tzinfo is not None
            assert datetime.fromisoformat(recording["recorded_at"]) <= datetime.now(UTC)


# --- an outage is remembered (FIX-9) ----------------------------------------------------------------------


def test_once_gemini_did_not_answer_a_recorded_sentence_is_answered_at_once_without_asking_it(
    build: Build, parts: Any, agent_hotel: Identity, agent_ward: Identity, texts: dict[str, str], ticking: Ticking
) -> None:
    parser, runner, fake = build(_busy)
    parser.read(texts["scenario_1"], agent_hotel)
    asked = len(fake.requests)

    ticking.now += OUTAGE_MEMORY_SECONDS - 1
    reading = parser.read(texts["scenario_1"], agent_hotel)
    run = runner.run_agent(texts["scenario_2"], agent_ward, parts.service)

    assert asked == 2 and len(fake.requests) == asked  # nothing more was sent
    assert reading.sentence == READ_FROM_THE_RECORDING
    assert run.report.startswith(SERVED) and run.order_status is OrderStatus.ORDERED


def test_once_gemini_did_not_answer_a_sentence_with_no_recording_is_refused_at_once(
    build: Build, agent_hotel: Identity, texts: dict[str, str]
) -> None:
    parser, _, fake = build(_busy)
    parser.read(texts["scenario_1"], agent_hotel)

    with pytest.raises(ModelUnreachable) as refused:
        parser.read("7 kg of cheese by Friday", agent_hotel)

    assert len(fake.requests) == 2 and "not asked again for 120 seconds" in refused.value.detail


def test_after_the_window_gemini_is_asked_again(
    build: Build, proposal: Callable[..., str], agent_hotel: Identity, texts: dict[str, str], ticking: Ticking
) -> None:
    parser, _, fake = build(_busy, _busy, _reading(proposal(required_claims=["FREE_FROM_LACTOSE"], quantity=1000)))
    parser.read(texts["scenario_1"], agent_hotel)

    ticking.now += OUTAGE_MEMORY_SECONDS
    reading = parser.read(texts["scenario_1"], agent_hotel)

    assert OUTAGE_MEMORY_SECONDS == 120
    assert reading.source is ReadingSource.MODEL and len(fake.requests) == 3


def test_a_refusal_is_not_remembered_as_an_outage(build: Build, agent_hotel: Identity, texts: dict[str, str]) -> None:
    parser, _, fake = build(_refused)

    for _ in range(2):
        with pytest.raises(SupplierUnavailable):
            parser.read(texts["scenario_1"], agent_hotel)

    assert len(fake.requests) == 2  # asked each time: a 400 is an answer, not an outage


def test_the_memory_of_an_outage_is_safe_from_several_threads() -> None:
    outage = Outage(seconds=60.0)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda number: outage.note() if number % 2 else outage.is_open(), range(200)))

    assert outage.is_open()
    outage.clear()
    assert not outage.is_open()


# --- a recording is served for its own profile only (FIX-9) -----------------------------------------------


def test_a_recording_stands_in_only_for_the_profile_it_was_recorded_for(
    build: Build, parts: Any, agent_hotel: Identity, texts: dict[str, str]
) -> None:
    parser, runner, _ = build(_busy)

    with pytest.raises(ModelUnreachable):
        parser.read(texts["scenario_2"], agent_hotel)  # recorded for the allergy ward
    with pytest.raises(ModelUnreachable):
        runner.run_agent(texts["scenario_2"], agent_hotel, parts.service)


def test_a_run_served_from_an_undated_recording_says_so(
    build: Build, parts: Any, agent_ward: Identity, tmp_path: Path
) -> None:
    recordings = _recordings(tmp_path)
    for path in tmp_path.glob("*.json"):
        undated = {key: value for key, value in json.loads(path.read_text()).items() if key != "recorded_at"}
        path.write_text(json.dumps(undated), encoding="utf-8")
    _, runner, _ = build(_busy, recordings=RecordedModel(tmp_path))

    run = runner.run_agent(WARD_TEXT, agent_ward, parts.service)

    assert recordings is not None and run.report.startswith(SERVED + "a recording of the model's earlier answers. ")


# --- the fixed rules behind the recordings (FALLBACK-1) ---------------------------------------------------

RULES_TEXT = "300 litres of oat drink by Monday, no milk, strict"


def test_when_gemini_does_not_answer_a_sentence_with_no_recording_is_read_by_the_rules_and_says_so(
    build: Build, agent_hotel: Identity, caplog: pytest.LogCaptureFixture
) -> None:
    parser, _, fake = build(_busy, rules=True)

    with caplog.at_level(logging.WARNING):
        reading = parser.read(RULES_TEXT, agent_hotel)

    assert (reading.source, reading.model, parser.model_id) == (ReadingSource.RULE_BASED, "rule-based", "rule-based")
    assert reading.sentence == "Read by fixed rules, not by a model: Gemini did not answer."
    assert reading.request.lines[0].product_type == "plant_drink" and len(fake.requests) == 2
    assert "Read by fixed rules" in caplog.text


def test_a_recorded_sentence_is_still_answered_from_its_recording_before_the_rules(
    build: Build, agent_hotel: Identity, texts: dict[str, str]
) -> None:
    parser, _, _ = build(_busy, rules=True)

    assert parser.read(texts["scenario_1"], agent_hotel).sentence == READ_FROM_THE_RECORDING


def test_a_model_that_answered_is_never_overridden_by_the_rules(
    build: Build, proposal: Callable[..., str], agent_hotel: Identity
) -> None:
    answer = proposal(product_type="plant_drink", quantity=300, exclude_allergens=["AM"], allergen_strictness="STRICT",
                      name_terms=["oat"], pack="PORTION")
    parser, _, _ = build(_reading(answer), rules=True)

    reading = parser.read(RULES_TEXT, agent_hotel)

    assert reading.source is ReadingSource.MODEL and reading.request.lines[0].pack == "PORTION"


def test_a_refusal_is_not_read_by_the_rules(build: Build, agent_hotel: Identity) -> None:
    parser, _, _ = build(_refused, rules=True)

    with pytest.raises(SupplierUnavailable) as refused:
        parser.read(RULES_TEXT, agent_hotel)

    assert "400" in refused.value.detail and "fixed rules" not in refused.value.detail


def test_a_text_neither_gemini_nor_the_rules_read_is_supplier_unavailable_naming_both(
    build: Build, agent_hotel: Identity
) -> None:
    parser, _, _ = build(_busy, rules=True)

    with pytest.raises(ModelUnreachable) as refused:
        parser.read("Some cheese for Friday", agent_hotel)

    detail = refused.value.detail
    assert detail.startswith("The language model did not answer after 2 attempts (HTTP status 503).")
    assert "The fixed rules could not read it either: cheese is named with no quantity in digits and unit." in detail
    assert detail.endswith("Send the typed request to POST /v1/offers instead.")


def test_when_gemini_does_not_answer_a_run_with_no_recording_is_made_by_the_rules(
    build: Build, parts: Any, agent_hotel: Identity
) -> None:
    _, runner, _ = build(_busy, rules=True)

    run = runner.run_agent("300 litres of oat drink by Monday", agent_hotel, parts.service)

    assert run.report.startswith("Gemini did not answer; this run was read and made by fixed rules, not by a model.")
    assert (run.model, run.recorded) == ("rule-based", False)
    assert [step.tool for step in run.steps] == ["get_authority", "create_offer", "place_order"]
    assert run.order_status in (OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL)


def test_a_run_neither_gemini_nor_the_rules_read_is_supplier_unavailable_and_records_nothing(
    build: Build, parts: Any, agent_ward: Identity
) -> None:
    _, runner, _ = build(_busy, rules=True)

    with pytest.raises(ModelUnreachable) as refused:
        runner.run_agent("Some cheese for Friday", agent_ward, parts.service)

    assert "The fixed rules could not read it either" in refused.value.detail
    assert parts.service.get_audit(agent_ward).events == ()


def test_a_refused_run_is_not_made_by_the_rules(build: Build, parts: Any, agent_hotel: Identity) -> None:
    _, runner, _ = build(_refused, rules=True)

    with pytest.raises(SupplierUnavailable) as refused:
        runner.run_agent("300 litres of oat drink by Monday", agent_hotel, parts.service)

    assert not isinstance(refused.value, ModelUnreachable)
