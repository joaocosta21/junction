"""The recorded model: the `AgentModel` interface served from `fixtures/agent/` (SPEC section 11).

Without a Gemini key the parser and the loop run on these recordings, so the demonstration scenarios work
with no key and in tests. A recording holds what the model answered for one sentence: its structured answer
(`parse`) or the function calls of each turn of a run (`run`). The gateway still decides everything: a
recorded call that no longer fits what the gateway answers is refused like any other call.

A fixture file is input like any other: it is validated when it is loaded, and one that does not validate
stops the start rather than being skipped.

A recording names the buyer profile it was recorded for and is served only for that profile (task FIX-9). Its
`needed_by` was resolved on the day it was recorded: on another day it is read again by the parser's calendar
rule (`tta.agent.days`), so "by Monday" recorded on Saturday 14 Nov still means 16 Nov on Sunday 15 Nov and
means 23 Nov on Monday 16 Nov.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from tta.agent.days import named_dates
from tta.agent.model import AnswerSource, ExtractCall, FunctionCall, ModelTurn, TurnCall
from tta.config import Settings
from tta.contracts.agent import ReadingSource
from tta.contracts.common import JsonDict
from tta.contracts.errors import SupplierUnavailable

RECORDED_MODEL_ID = "recorded"
HAND_BUILT_MODEL_ID = "hand-built"  # shown instead, for a sentence whose fixture a person wrote
LIVE_SOURCE = "live"
AGENT_FIXTURES_FOLDER = "agent"
_IGNORED_AT_THE_END = " .!"

NOT_RECORDED = (
    "No GEMINI_API_KEY is set, so the gateway can read only the {count} recorded demonstration requests, "
    "and this is not one of them. Send the typed request to POST /v1/offers instead."
)
RUN_NOT_RECORDED = (
    "No GEMINI_API_KEY is set, so the buyer agent can act only on the {count} recorded demonstration runs, "
    "and this request is not one of them. Send the typed request to POST /v1/offers and the chosen option "
    "to POST /v1/orders instead."
)
OTHER_PROFILE = (
    "This sentence was recorded for another buyer profile, and a recording is served only for the profile it "
    "was recorded for. Send the typed request to POST /v1/offers instead."
)
NEEDED_BY = "needed_by"


class RecordingError(ValueError):
    """A file of `fixtures/agent/` cannot be used. The message names the file."""


class _Recorded(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RecordedCall(_Recorded):
    name: str
    arguments: JsonDict = {}


class RecordedTurn(_Recorded):
    calls: tuple[RecordedCall, ...] = ()
    text: str | None = None


class Recording(_Recorded):
    """What a model answered for one sentence."""

    kind: Literal["parse", "run"]
    text: str  # the buyer's sentence
    profile_id: str  # the buyer profile it was recorded for: it is served for that profile only
    model: str  # the model that answered
    source: Literal["live", "hand-built"]  # "live": saved from a call to the model
    recorded_at: datetime | None = None
    today: date | None = None  # the date of the data clock when the answer was given ("by Monday")
    note: str | None = None
    proposal: JsonDict | None = None  # kind "parse": the structured answer
    turns: tuple[RecordedTurn, ...] | None = None  # kind "run": the calls of each turn

    @model_validator(mode="after")
    def _holds_what_its_kind_needs(self) -> Recording:
        if self.kind == "parse" and (self.proposal is None or self.turns is not None):
            raise ValueError("a parse recording holds a proposal and no turns")
        if self.kind == "run" and (self.turns is None or self.proposal is not None):
            raise ValueError("a run recording holds turns and no proposal")
        return self


def text_key(text: str) -> str:
    """A sentence as it is looked up: case, spacing and a final full stop do not matter."""
    return " ".join(text.casefold().split()).rstrip(_IGNORED_AT_THE_END)


def _read(path: Path) -> Recording:
    try:
        return Recording.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:  # not readable, not JSON, or not a recording (a ValidationError)
        problems = error.error_count() if isinstance(error, ValidationError) else 1
        raise RecordingError(f"{path.name} is not a usable recording ({problems} problem(s)).") from error


def _served_for(recording: Recording | None, profile_id: str | None) -> Recording | None:
    return recording if recording is not None and recording.profile_id == profile_id else None


def _on(proposal: JsonDict, recording: Recording, today: date | None) -> JsonDict:
    """The recorded answer for `today`: its `needed_by` read again by the calendar rule when it was recorded on
    another day and the text names one day. Any other answer is served as it was recorded."""
    if today is None or recording.today == today or proposal.get(NEEDED_BY) is None:
        return proposal
    dates = named_dates(recording.text, today)
    return {**proposal, NEEDED_BY: dates[0].isoformat()} if len(dates) == 1 else proposal


def load_recordings(directory: Path) -> tuple[Recording, ...]:
    """Every recording of the folder, in file-name order. A missing folder holds none."""
    if not directory.is_dir():
        return ()
    return tuple(_read(path) for path in sorted(directory.glob("*.json")))


def _by_sentence(recordings: Iterable[Recording], kind: str, directory: Path) -> dict[str, Recording]:
    found: dict[str, Recording] = {}
    for recording in recordings:
        if recording.kind != kind:
            continue
        key = text_key(recording.text)
        if key in found:
            raise RecordingError(f"Two {kind} recordings (.json files) of {directory.name}/ hold the same sentence.")
        found[key] = recording
    return found


class RecordedModel:
    """Implements `AgentModel` from recordings. It never calls anything."""

    def __init__(self, directory: Path) -> None:
        recordings = load_recordings(directory)
        self._parses = _by_sentence(recordings, "parse", directory)
        self._runs = _by_sentence(recordings, "run", directory)

    @classmethod
    def from_settings(cls, settings: Settings) -> RecordedModel:
        return cls(settings.tta_fixtures_dir / AGENT_FIXTURES_FOLDER)

    @property
    def model_id(self) -> str:
        return RECORDED_MODEL_ID

    @property
    def recorded(self) -> bool:
        return True

    def recordings_of(self, request_text: str) -> tuple[Recording, ...]:
        """What is held for this sentence: its parse, then its run, each when there is one."""
        key = text_key(request_text)
        return tuple(found[key] for found in (self._parses, self._runs) if key in found)

    def holds(self, kind: Literal["parse", "run"], request_text: str, profile_id: str | None) -> bool:
        """True when this sentence has a recording of this kind for this buyer profile."""
        found = self._parses if kind == "parse" else self._runs
        return _served_for(found.get(text_key(request_text)), profile_id) is not None

    def label_for(self, request_text: str) -> str:
        """"recorded" when every recording of this sentence was saved from a model; else "hand-built"."""
        by_hand = any(recording.source != LIVE_SOURCE for recording in self.recordings_of(request_text))
        return HAND_BUILT_MODEL_ID if by_hand else RECORDED_MODEL_ID

    def answer_source(self, request_text: str) -> AnswerSource:
        """The recording `extract` serves for this sentence. Raises `KeyError` when there is none."""
        recording = self._parses[text_key(request_text)]
        if recording.source != LIVE_SOURCE:
            return AnswerSource(ReadingSource.HAND_BUILT, HAND_BUILT_MODEL_ID, recording.recorded_at)
        return AnswerSource(ReadingSource.RECORDING, recording.model, recording.recorded_at)

    def extract(self, call: ExtractCall) -> str:
        recording = self._parses.get(text_key(call.text))
        if recording is None:
            raise SupplierUnavailable(NOT_RECORDED.format(count=len(self._parses)))
        if _served_for(recording, call.profile_id) is None:
            raise SupplierUnavailable(OTHER_PROFILE)
        return json.dumps(_on(recording.proposal or {}, recording, call.today))

    def next_turn(self, call: TurnCall) -> ModelTurn:
        """The recorded calls of this turn; past the last recorded turn, a turn with no call."""
        recording = self._runs.get(text_key(call.request_text))
        if recording is None or recording.turns is None:
            raise SupplierUnavailable(RUN_NOT_RECORDED.format(count=len(self._runs)))
        if _served_for(recording, call.profile_id) is None:
            raise SupplierUnavailable(OTHER_PROFILE)
        if call.turn > len(recording.turns):
            return ModelTurn()
        turn = recording.turns[call.turn - 1]
        calls = tuple(
            FunctionCall(id=f"recorded-{call.turn}-{number}", name=one.name, arguments=dict(one.arguments))
            for number, one in enumerate(turn.calls, start=1)
        )
        steps = tuple(
            {"type": "function_call", "id": one.id, "name": one.name, "arguments": one.arguments} for one in calls
        )
        return ModelTurn(steps=steps, calls=calls, text=turn.text)
