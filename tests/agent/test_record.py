"""The recorder of the live check: what the model answered becomes a fixture the recorded model serves."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from tta.agent import record
from tta.agent.model import AgentModel, ExtractCall, TurnCall
from tta.agent.parser import ModelRequestParser
from tta.agent.record import (
    PLAN,
    CallBudget,
    CallBudgetSpent,
    Recorder,
    RecordingModel,
    SecretInRecording,
    write_recording,
)
from tta.agent.recorded import RecordedModel, load_recordings
from tta.agent.runner import ModelAgentRunner
from tta.api.wiring import Parts
from tta.config import Settings
from tta.contracts.common import Identity, OrderStatus
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import Clock

TODAY = date(2026, 11, 14)
AT = datetime(2026, 11, 14, 1, 0, tzinfo=UTC)
TEXT = "200 litres of plant drink by Monday, no milk, no gluten"
WARD = "allergy-ward"
HAPPY_PATH = [[("get_authority", {})], [("create_offer", {})], [("place_order", {"option_id": "opt_1"})]]
MakeParser = Callable[..., ModelRequestParser]
Proposal = Callable[..., str]


def test_a_recorded_run_is_served_back_call_for_call(
    scripted: Any, make_parser: MakeParser, proposal: Proposal, demo_clock: Clock, parts: Parts,
    agent_ward: Identity, tmp_path: Path,
) -> None:
    answer = proposal(product_type="plant_drink", quantity=200, exclude_allergens=["AM", "AW"])
    live = RecordingModel(scripted(extracts=[answer], turns=[list(turn) for turn in HAPPY_PATH], model_id="gemini-x"))
    runner = ModelAgentRunner(model=live, parser=make_parser(live, demo_clock))
    first = runner.run_agent(TEXT, agent_ward, parts.service)

    for kind in ("parse", "run"):
        recording = live.recording(kind, TEXT, profile_id=WARD, today=TODAY, recorded_at=AT)
        write_recording(tmp_path, f"{kind}-ward", recording, secrets=("not-in-there",))
    replayed = RecordedModel(tmp_path)
    again = ModelAgentRunner(model=replayed, parser=make_parser(replayed, demo_clock)).run_agent(
        TEXT, agent_ward, parts.service
    )

    assert isinstance(live, AgentModel) and (live.model_id, live.recorded) == ("gemini-x", False)
    assert first.model == live.label_for(TEXT) == "gemini-x" and again.model == "recorded"
    assert first.order_status is OrderStatus.ORDERED
    assert [(step.tool, step.ok) for step in again.steps[:2]] == [(step.tool, step.ok) for step in first.steps[:2]]
    assert again.steps[1].arguments == first.steps[1].arguments  # the same typed request
    assert again.steps[2].tool == "place_order" and again.recorded is True
    saved = json.loads((tmp_path / "run-ward.json").read_text(encoding="utf-8"))
    assert (saved["kind"], saved["model"], saved["source"], saved["text"]) == ("run", "gemini-x", "live", TEXT)
    assert saved["profile_id"] == WARD
    assert [turn["calls"] for turn in saved["turns"]][:3] == [
        [{"name": name, "arguments": arguments} for name, arguments in turn] for turn in HAPPY_PATH
    ]
    assert saved["turns"][-1] == {"calls": [], "text": "Done."}


def test_a_recording_of_a_sentence_the_model_was_never_given_cannot_be_made(scripted: Any) -> None:
    live = RecordingModel(scripted())

    with pytest.raises(KeyError):
        live.recording("parse", "never asked", profile_id=WARD, today=TODAY, recorded_at=AT)


def test_a_recording_that_holds_a_secret_is_not_written(scripted: Any, tmp_path: Path) -> None:
    live = RecordingModel(scripted(extracts=['{"lines": [], "note": "key-123"}']))
    live.extract(ExtractCall(system="s", text=TEXT, schema={}))
    recording = live.recording("parse", TEXT, profile_id=WARD, today=TODAY, recorded_at=AT)

    with pytest.raises(SecretInRecording):
        write_recording(tmp_path, "parse-leak", recording, secrets=("key-123",))

    assert list(tmp_path.iterdir()) == []


def test_an_answer_that_is_not_a_json_object_is_recorded_as_it_came(scripted: Any) -> None:
    live = RecordingModel(scripted(extracts=["no json at all"]))
    live.extract(ExtractCall(system="s", text=TEXT, schema={}))

    recording = live.recording("parse", TEXT, profile_id=WARD, today=TODAY, recorded_at=AT)

    assert recording.proposal == {"unreadable": "no json at all"}


def test_the_call_budget_counts_every_request_and_refuses_the_one_beyond_it() -> None:
    class Transport:
        def create(self, **request: Any) -> str:
            return f"answer to {request['input']}"

    budget = CallBudget(Transport(), max_calls=2)

    answers = [budget.create(input="a"), budget.create(input="b")]
    with pytest.raises(CallBudgetSpent):
        budget.create(input="c")

    assert answers == ["answer to a", "answer to b"] and budget.calls == 2


def test_turns_are_kept_per_sentence(scripted: Any) -> None:
    live = RecordingModel(scripted(turns=[[("get_authority", {})], [("get_order", {})]]))
    live.next_turn(TurnCall(system="s", request_text="first", history=(), tools=(), turn=1))
    live.next_turn(TurnCall(system="s", request_text="second", history=(), tools=(), turn=1))

    first = live.recording("run", "first", profile_id=WARD, today=TODAY, recorded_at=AT)

    assert [[call.name for call in turn.calls] for turn in first.turns] == [["get_authority"]]


def test_the_plan_of_the_live_check_is_recorded_into_fixtures_the_recorded_model_serves(
    scripted: Any, make_parser: MakeParser, proposal: Proposal, demo_clock: Clock, parts: Parts, tmp_path: Path
) -> None:
    answers = [
        proposal(required_claims=["FREE_FROM_LACTOSE"], quantity=1000),
        proposal(product_type="plant_drink", quantity=200, exclude_allergens=["AM", "AW"], require_confirmed=True),
        proposal(quantity=None, unit=None),
    ]
    live = RecordingModel(scripted(extracts=answers, turns=[list(turn) for turn in HAPPY_PATH]))
    parser = make_parser(live, demo_clock)
    recorder = Recorder(
        live=live, parser=parser, runner=ModelAgentRunner(model=live, parser=parser), gateway=parts.service,
        directory=tmp_path / "agent", secrets=("no-such-secret",), today=TODAY,
    )

    written = [path.name for task in PLAN for path in recorder.record(task)]

    assert written == ["parse-scenario-1.json", "parse-scenario-2.json", "run-scenario-2.json",
                       "parse-no-quantity.json"]
    assert [(task.kind, task.profile_id) for task in PLAN] == [
        ("parse", "hotel-kitchen"), ("run", "allergy-ward"), ("parse", "hotel-kitchen"),
    ]
    replayed = RecordedModel(tmp_path / "agent")
    scenario_2 = PLAN[1].text
    read_again = json.loads(replayed.extract(ExtractCall(system="s", text=scenario_2, schema={}, profile_id=WARD)))
    assert read_again["require_confirmed"] is True
    first_turn = replayed.next_turn(
        TurnCall(system="s", request_text=scenario_2, history=(), tools=(), turn=1, profile_id=WARD)
    )
    assert [call.name for call in first_turn.calls] == ["get_authority"]
    no_quantity = json.loads((tmp_path / "agent" / "parse-no-quantity.json").read_text(encoding="utf-8"))
    assert no_quantity["proposal"]["lines"][0]["quantity"] is None  # the refusal is recorded as the model gave it
    assert no_quantity["today"] == "2026-11-14" and no_quantity["source"] == "live"
    assert [recording.profile_id for recording in load_recordings(tmp_path / "agent")] == [
        "hotel-kitchen", "hotel-kitchen", "allergy-ward", "allergy-ward",  # in file-name order
    ]


# --- only what validated is written (FIX-9) ---------------------------------------------------------------


def _recorder(live: RecordingModel, make_parser: MakeParser, demo_clock: Clock, parts: Parts, at: Path) -> Recorder:
    parser = make_parser(live, demo_clock)
    return Recorder(
        live=live, parser=parser, runner=ModelAgentRunner(model=live, parser=parser), gateway=parts.service,
        directory=at, secrets=("no-such-secret",), today=TODAY,
    )


def test_an_answer_that_did_not_validate_twice_is_not_recorded(
    scripted: Any, make_parser: MakeParser, proposal: Proposal, demo_clock: Clock, parts: Parts, tmp_path: Path
) -> None:
    wrong = proposal(required_claims=["FREE_FROM_LACTOSE"], quantity=10000)  # the text says 1,000
    live = RecordingModel(scripted(extracts=[wrong, wrong]))

    written = _recorder(live, make_parser, demo_clock, parts, tmp_path / "agent").record(PLAN[0])

    assert written == () and not (tmp_path / "agent").exists()


def test_a_run_that_ended_because_the_model_stopped_answering_is_not_recorded(
    scripted: Any, make_parser: MakeParser, proposal: Proposal, demo_clock: Clock, parts: Parts, tmp_path: Path
) -> None:
    answer = proposal(product_type="plant_drink", quantity=200, exclude_allergens=["AM", "AW"], require_confirmed=True)
    turns = [list(HAPPY_PATH[0]), SupplierUnavailable("The language model did not answer after 2 attempts.")]
    live = RecordingModel(scripted(extracts=[answer], turns=turns))

    written = _recorder(live, make_parser, demo_clock, parts, tmp_path / "agent").record(PLAN[1])

    assert [path.name for path in written] == ["parse-scenario-2.json"]  # the reading validated; the run is not kept
    assert live.stopped(PLAN[1].text)


def test_without_a_key_the_live_check_calls_nothing_and_says_so(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(record, "get_settings", lambda: Settings.for_tests())

    code = record.main([])

    assert code == record.EXIT_NO_KEY == 2
    assert "GEMINI_API_KEY is not set" in caplog.text


def test_the_live_check_can_give_the_model_longer_than_the_gateway_does(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    given: dict[str, Any] = {}
    monkeypatch.setattr(record, "get_settings", lambda: Settings.for_tests(gemini_api_key="test-key-0"))
    monkeypatch.setattr(record, "sdk_transport", lambda settings, **options: given.update(options) or object())
    monkeypatch.setattr(record, "_record_all", lambda settings, tasks, budget: record.EXIT_OK)

    assert record.main(["--only", "scenario-1", "--timeout", "90"]) == record.EXIT_OK
    assert given == {"timeout_seconds": 90.0}
    assert record.main(["--only", "scenario-1"]) == record.EXIT_OK
    assert given == {"timeout_seconds": record.REQUEST_TIMEOUT_SECONDS}
