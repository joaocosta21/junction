"""The recorded model: the same interface as the Gemini model, served from `fixtures/agent/`."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tta.agent.model import AgentModel, ExtractCall, TurnCall
from tta.agent.recorded import (
    HAND_BUILT_MODEL_ID,
    RECORDED_MODEL_ID,
    RecordedModel,
    RecordingError,
    load_recordings,
    text_key,
)
from tta.contracts.agent import ReadingSource
from tta.contracts.errors import SupplierUnavailable

PROFILE = "hotel-kitchen"
PARSE = {
    "kind": "parse", "text": "5 kg of butter", "profile_id": PROFILE, "model": "gemini-3.8-flash", "source": "live",
    "recorded_at": "2026-11-14T03:00:00+02:00", "today": "2026-11-14",
    "proposal": {"needed_by": None, "require_confirmed": False, "lines": []},
}
RUN = {
    "kind": "run", "text": "5 kg of butter", "profile_id": PROFILE, "model": "gemini-3.8-flash", "source": "hand-built",
    "turns": [
        {"calls": [{"name": "get_authority", "arguments": {}}]},
        {"calls": [{"name": "place_order", "arguments": {"option_id": "opt_1"}}]},
        {"calls": [], "text": "Placed."},
    ],
}


def _write(directory: Path, **files: Any) -> Path:
    for name, content in files.items():
        text = content if isinstance(content, str) else json.dumps(content)
        (directory / f"{name}.json").write_text(text, encoding="utf-8")
    return directory


def _extract(text: str, profile_id: str | None = PROFILE, today: date | None = None) -> ExtractCall:
    return ExtractCall(system="s", text=text, schema={}, profile_id=profile_id, today=today)


def _turn(text: str, turn: int, profile_id: str | None = PROFILE) -> TurnCall:
    return TurnCall(system="s", request_text=text, history=(), tools=(), turn=turn, profile_id=profile_id)


def test_a_recorded_sentence_is_found_whatever_its_case_spacing_or_final_full_stop() -> None:
    assert text_key("  5 KG of   butter. ") == text_key("5 kg of butter")
    assert text_key("5 kg of butter") != text_key("6 kg of butter")


def test_extract_serves_the_recorded_proposal(tmp_path: Path) -> None:
    model = RecordedModel(_write(tmp_path, parse=PARSE))

    answer = model.extract(_extract("5 kg of BUTTER."))

    assert isinstance(model, AgentModel)
    assert (model.model_id, model.recorded) == (RECORDED_MODEL_ID, True) and RECORDED_MODEL_ID == "recorded"
    assert json.loads(answer) == PARSE["proposal"]


def test_next_turn_serves_the_recorded_calls_in_order_then_ends(tmp_path: Path) -> None:
    model = RecordedModel(_write(tmp_path, parse=PARSE, run=RUN))

    turns = [model.next_turn(_turn("5 kg of butter", number)) for number in (1, 2, 3, 4)]

    assert [[(call.name, call.arguments) for call in turn.calls] for turn in turns] == [
        [("get_authority", {})], [("place_order", {"option_id": "opt_1"})], [], [],
    ]
    assert turns[2].text == "Placed." and turns[3].calls == ()
    assert len({call.id for turn in turns for call in turn.calls}) == 2  # every call has its own id
    assert turns[1].steps == ({"type": "function_call", "id": turns[1].calls[0].id, "name": "place_order",
                               "arguments": {"option_id": "opt_1"}},)


def test_a_trace_credits_a_model_only_with_answers_a_model_gave(tmp_path: Path) -> None:
    live_run = {**RUN, "source": "live"}
    by_hand = RecordedModel(_write(tmp_path, parse=PARSE, run=RUN))  # the run was written by a person
    (tmp_path / "live").mkdir()
    all_live = RecordedModel(_write(tmp_path / "live", parse=PARSE, run=live_run))

    assert by_hand.label_for("5 kg of butter.") == HAND_BUILT_MODEL_ID == "hand-built"
    assert all_live.label_for("5 KG of butter") == RECORDED_MODEL_ID
    assert all_live.label_for("a sentence with no recording") == RECORDED_MODEL_ID


@pytest.mark.parametrize("ask", ["extract", "next_turn"])
def test_a_sentence_that_was_never_recorded_is_supplier_unavailable(tmp_path: Path, ask: str) -> None:
    model = RecordedModel(_write(tmp_path, parse=PARSE, run=RUN))

    with pytest.raises(SupplierUnavailable) as refused:
        if ask == "extract":
            model.extract(_extract("7 kg of cheese"))
        else:
            model.next_turn(_turn("7 kg of cheese", 1))

    assert "GEMINI_API_KEY" in refused.value.detail and "POST /v1/offers" in refused.value.detail
    assert "cheese" not in refused.value.detail


@pytest.mark.parametrize(
    "files",
    [
        {"broken": "{not json"},
        {"extra": {**PARSE, "surprise": 1}},
        {"no_proposal": {key: value for key, value in PARSE.items() if key != "proposal"}},
        {"no_turns": {key: value for key, value in RUN.items() if key != "turns"}},
        {"no_profile": {key: value for key, value in PARSE.items() if key != "profile_id"}},
        {"one": PARSE, "two": {**PARSE, "text": "5 KG of butter."}},  # the same sentence twice
        {"a_list": [PARSE]},
    ],
)
def test_a_fixture_that_cannot_be_trusted_stops_the_start(tmp_path: Path, files: dict[str, Any]) -> None:
    with pytest.raises(RecordingError) as refused:
        RecordedModel(_write(tmp_path, **files))

    assert ".json" in str(refused.value)  # the file is named


def test_a_folder_with_no_recordings_serves_nothing(tmp_path: Path) -> None:
    model = RecordedModel(tmp_path / "missing")

    with pytest.raises(SupplierUnavailable):
        model.extract(_extract("5 kg of butter"))


def test_the_fixtures_of_the_repository_hold_the_demonstration_sentences_and_no_secret(
    fixtures_agent_dir: Path, texts: dict[str, str]
) -> None:
    recordings = load_recordings(fixtures_agent_dir)

    parsed = {text_key(recording.text) for recording in recordings if recording.kind == "parse"}
    run = {text_key(recording.text) for recording in recordings if recording.kind == "run"}
    assert {text_key(text) for text in texts.values()} <= parsed
    assert {text_key(texts["scenario_1"]), text_key(texts["scenario_2"])} <= run
    for path in fixtures_agent_dir.glob("*.json"):
        content = path.read_text(encoding="utf-8").lower()
        assert not any(word in content for word in ("x-goog-api-key", "authorization", "bearer ", "aiza"))


def test_the_model_says_which_sentences_it_holds_and_what_it_holds_for_them(tmp_path: Path) -> None:
    model = RecordedModel(_write(tmp_path, parse=PARSE, run=RUN))
    (tmp_path / "parse-only").mkdir()
    parse_only = RecordedModel(_write(tmp_path / "parse-only", parse=PARSE))

    held = model.recordings_of("5 KG of butter.")

    assert [(recording.kind, recording.source) for recording in held] == [("parse", "live"), ("run", "hand-built")]
    assert model.holds("parse", "5 kg of butter", PROFILE) and model.holds("run", "5 kg of butter", PROFILE)
    assert parse_only.holds("parse", "5 kg of butter", PROFILE)
    assert not parse_only.holds("run", "5 kg of butter", PROFILE)
    assert model.recordings_of("7 kg of cheese") == () and not model.holds("parse", "7 kg of cheese", PROFILE)


# --- a recording is served for its own profile and its own day (FIX-9) ------------------------------------


def test_a_recording_is_served_only_for_the_profile_it_was_recorded_for(tmp_path: Path) -> None:
    model = RecordedModel(_write(tmp_path, parse=PARSE, run=RUN))

    for ask in (lambda: model.extract(_extract("5 kg of butter", "allergy-ward")),
                lambda: model.next_turn(_turn("5 kg of butter", 1, "allergy-ward")),
                lambda: model.extract(_extract("5 kg of butter", None))):
        with pytest.raises(SupplierUnavailable) as refused:
            ask()
        assert "another buyer profile" in refused.value.detail
    assert not model.holds("parse", "5 kg of butter", "allergy-ward")
    assert not model.holds("run", "5 kg of butter", None)


@pytest.mark.parametrize(
    ("today", "needed_by"),
    [(None, "2026-11-16"), (date(2026, 11, 14), "2026-11-16"), (date(2026, 11, 15), "2026-11-16"),
     (date(2026, 11, 16), "2026-11-23")],
)
def test_a_recorded_needed_by_is_read_again_by_the_calendar_rule_on_another_day(
    tmp_path: Path, today: date | None, needed_by: str
) -> None:
    by_monday = {**PARSE, "text": "5 kg of butter by Monday",
                 "proposal": {**PARSE["proposal"], "needed_by": "2026-11-16"}}
    model = RecordedModel(_write(tmp_path, parse=by_monday))

    answer = json.loads(model.extract(_extract("5 kg of butter by Monday", today=today)))

    assert answer["needed_by"] == needed_by
    assert {key: value for key, value in answer.items() if key != "needed_by"} == {
        key: value for key, value in by_monday["proposal"].items() if key != "needed_by"
    }


def test_a_recorded_answer_with_no_date_or_on_a_text_with_two_days_is_served_as_it_was(tmp_path: Path) -> None:
    two_days = {**PARSE, "text": "5 kg of butter on Monday or Tuesday",
                "proposal": {**PARSE["proposal"], "needed_by": "2026-11-16"}}
    model = RecordedModel(_write(tmp_path, parse=PARSE, two=two_days))

    later = date(2026, 11, 20)
    assert json.loads(model.extract(_extract("5 kg of butter", today=later)))["needed_by"] is None
    assert json.loads(model.extract(_extract("5 kg of butter on Monday or Tuesday", today=later)))["needed_by"] == (
        "2026-11-16"
    )


# The brief's own sentence (AIMO/CHALLENGE.md), recorded by hand so the demo reads it without a model.
BRIEF_SENTENCE = (
    "I need 1,000 litres of lactose-free milk by Monday. "
    "Find an option that meets our requirements based on price and availability."
)


def test_the_recordings_of_the_repository_name_the_profile_they_were_recorded_for(
    fixtures_agent_dir: Path, texts: dict[str, str], demo_photo_lines: tuple[str, ...]
) -> None:
    profiles = {(recording.kind, text_key(recording.text)): recording.profile_id
                for recording in load_recordings(fixtures_agent_dir)}

    one, two, none = (text_key(texts[name]) for name in ("scenario_1", "scenario_2", "no_quantity"))
    finnish_1, finnish_2 = (text_key(texts[name]) for name in ("finnish_1", "finnish_2"))
    photo = text_key("\n".join(demo_photo_lines))
    brief = text_key(BRIEF_SENTENCE)
    assert profiles == {
        ("parse", brief): "hotel-kitchen", ("run", brief): "hotel-kitchen",
        ("parse", one): "hotel-kitchen", ("run", one): "hotel-kitchen", ("parse", none): "hotel-kitchen",
        ("parse", two): "allergy-ward", ("run", two): "allergy-ward",
        ("parse", finnish_1): "hotel-kitchen", ("parse", finnish_2): "allergy-ward",
        ("transcribe", photo): "hotel-kitchen", ("parse", photo): "hotel-kitchen",
    }


def test_the_source_of_a_recorded_answer_is_the_recording(tmp_path: Path) -> None:
    by_hand = {**PARSE, "text": "6 kg of butter", "source": "hand-built", "model": "hand-built"}
    model = RecordedModel(_write(tmp_path, parse=PARSE, by_hand=by_hand))

    live, written = model.answer_source("5 kg of butter"), model.answer_source("6 kg of butter")

    assert (live.source, live.model) == (ReadingSource.RECORDING, "gemini-3.8-flash")
    assert live.recorded_at is not None
    assert (written.source, written.model) == (ReadingSource.HAND_BUILT, HAND_BUILT_MODEL_ID)
