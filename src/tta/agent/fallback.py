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
  the sentence below. A request read from a recording says so in its `Reading` (task FIX-9): "Gemini did not
  answer; read from a recording of gemini-3.6-flash made on 14 Nov 2026 at 06:14 UTC.";
- a recording is served only for the buyer profile it was recorded for;
- after a failure for unreachability the Gemini model refuses at once for a while (`tta.agent.outage`), so in
  that window a recorded sentence is answered from its recording straight away.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from tta.agent.gemini import ModelUnreachable
from tta.agent.labels import fallback_sentence, made_on
from tta.agent.model import AnswerSource
from tta.agent.parser import ModelRequestParser
from tta.agent.recorded import HAND_BUILT_MODEL_ID, LIVE_SOURCE, RECORDED_MODEL_ID, RecordedModel, Recording
from tta.agent.runner import ModelAgentRunner
from tta.contracts.agent import AgentRun, Reading, ReadingSource
from tta.contracts.common import Identity
from tta.contracts.ports import GatewayService
from tta.contracts.request import PurchaseRequest

GEMINI_DID_NOT_ANSWER = "Gemini did not answer; this run was served from {source}."
FROM_A_RECORDING = "a recording made on {when}"
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
    return FROM_A_RECORDING.format(when=made_on(max(made)))


def served_from(recordings: Sequence[Recording]) -> str:
    """The sentence that opens the report of a run served from recordings."""
    return GEMINI_DID_NOT_ANSWER.format(source=_source(recordings))


def _answered_by(reading: Reading) -> str:
    """What answered, as a trace names it: the model id, "recorded" or "hand-built"."""
    if reading.source is ReadingSource.MODEL:
        return reading.model
    return HAND_BUILT_MODEL_ID if reading.source is ReadingSource.HAND_BUILT else RECORDED_MODEL_ID


class FallbackParser:
    """Implements `RequestParser`: Gemini's reading, or the recorded one when Gemini cannot be reached."""

    def __init__(self, *, live: ModelRequestParser, recorded: ModelRequestParser, recordings: RecordedModel) -> None:
        self._live = live
        self._recorded = recorded
        self._recordings = recordings
        self._last_answered_by = live.model_id

    @property
    def model_id(self) -> str:
        """What answered the last reading: the Gemini model id until a recording stood in for it."""
        return self._last_answered_by

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        return self.read(text, identity).request

    def read(self, text: str, identity: Identity) -> Reading:
        try:
            reading = self._live.read(text, identity)
        except ModelUnreachable as unreachable:
            if not self._recordings.holds("parse", text, identity.profile_id):
                raise
            reading = self._from_recording(text, identity)
            logger.warning("%s %s", reading.sentence, unreachable.detail)
        self._last_answered_by = _answered_by(reading)  # one assignment: safe from several threads
        return reading

    def _from_recording(self, text: str, identity: Identity) -> Reading:
        reading = self._recorded.read(text, identity)
        answer = AnswerSource(reading.source, reading.model, reading.recorded_at)
        return reading.model_copy(update={"sentence": fallback_sentence(answer)})


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
            held = (self._recordings.holds(kind, text, identity.profile_id) for kind in ("parse", "run"))
            if not all(held):
                raise
            opening = served_from(self._recordings.recordings_of(text))
            logger.warning("%s %s", opening, unreachable.detail)
        run = self._recorded.run_agent(text, identity, tools)
        return run.model_copy(update={"report": f"{opening} {run.report}"})
