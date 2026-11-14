"""When Gemini cannot be reached, a sentence that has a recording is answered from it (task T10, question 1).

Scores on the 30% "working end-to-end demo": with a key set, a time-out, a 429 or a 5xx from Gemini would
otherwise turn the demonstration sentences into `supplier-unavailable` while the same sentences work with no
key. Decided by the orchestrator on 14 Nov 2026:
- only when the model cannot be reached (`ModelUnreachable`); a refusal (400 to 404) or an answer that did
  not finish is not covered, and is answered as before;
- only for a sentence with a recording; any other sentence still answers `supplier-unavailable`;
- a run falls back only before it made its first gateway call (the runner raises only then). Once a call was
  made, what Gemini did stands under its name and the run ends as the runner reports it;
- the trace and the report say so plainly: the run's `model` names the recording, and its report starts with
  the sentence below. A request read from a recording has no trace; the log line says it.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC

from tta.agent.gemini import ModelUnreachable
from tta.agent.parser import ModelRequestParser
from tta.agent.recorded import LIVE_SOURCE, RecordedModel, Recording
from tta.agent.runner import ModelAgentRunner
from tta.contracts.agent import AgentRun
from tta.contracts.common import Identity
from tta.contracts.ports import GatewayService
from tta.contracts.request import PurchaseRequest

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
GEMINI_DID_NOT_ANSWER = "Gemini did not answer; this run was served from {source}."
READ_FROM_RECORDING = "Gemini did not answer; this request was read from {source}."
FROM_A_RECORDING = "a recording made on {day} {month} {year} at {time} UTC"
FROM_AN_UNDATED_RECORDING = "a recording of the model's earlier answers"
FROM_HAND_BUILT = "answers written by hand, not by a model"

logger = logging.getLogger(__name__)


def _source(recordings: Sequence[Recording]) -> str:
    """Where the answers came from. A sentence with any hand-written answer is said to be hand-written."""
    if any(recording.source != LIVE_SOURCE for recording in recordings):
        return FROM_HAND_BUILT
    made = [recording.recorded_at for recording in recordings if recording.recorded_at is not None]
    if not made:
        return FROM_AN_UNDATED_RECORDING
    at = max(made).astimezone(UTC)
    return FROM_A_RECORDING.format(day=at.day, month=MONTHS[at.month - 1], year=at.year, time=f"{at:%H:%M}")


def served_from(recordings: Sequence[Recording]) -> str:
    """The sentence that opens the report of a run served from recordings."""
    return GEMINI_DID_NOT_ANSWER.format(source=_source(recordings))


class FallbackParser:
    """Implements `RequestParser`: Gemini's reading, or the recorded one when Gemini cannot be reached."""

    def __init__(self, *, live: ModelRequestParser, recorded: ModelRequestParser, recordings: RecordedModel) -> None:
        self._live = live
        self._recorded = recorded
        self._recordings = recordings

    @property
    def model_id(self) -> str:
        return self._live.model_id

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        try:
            return self._live.parse_request(text, identity)
        except ModelUnreachable as unreachable:
            if not self._recordings.holds("parse", text):
                raise
            source = _source(self._recordings.recordings_of(text)[:1])  # the parse comes first
            logger.warning("%s %s", READ_FROM_RECORDING.format(source=source), unreachable.detail)
        return self._recorded.parse_request(text, identity)


class FallbackRunner:
    """Implements `AgentRunner`: a run on Gemini, or the recorded run when Gemini cannot be reached before the
    run's first gateway call. The recorded run is a whole run: its reading and its calls are both recorded."""

    def __init__(self, *, live: ModelAgentRunner, recorded: ModelAgentRunner, recordings: RecordedModel) -> None:
        self._live = live
        self._recorded = recorded
        self._recordings = recordings

    @property
    def model_id(self) -> str:
        return self._live.model_id

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        try:
            return self._live.run_agent(text, identity, tools)
        except ModelUnreachable as unreachable:
            if not (self._recordings.holds("parse", text) and self._recordings.holds("run", text)):
                raise
            opening = served_from(self._recordings.recordings_of(text))
            logger.warning("%s %s", opening, unreachable.detail)
        run = self._recorded.run_agent(text, identity, tools)
        return run.model_copy(update={"report": f"{opening} {run.report}"})
