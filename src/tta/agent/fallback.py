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
- a photo (task T18) falls back only when its transcription and the reading of its lines are both recorded: it
  is then served wholly from the recordings, and its sentence opens "Read from a photo: Gemini did not answer;";
- after a failure for unreachability the Gemini model refuses at once for a while (`tta.agent.outage`), so in
  that window a recorded sentence is answered from its recording straight away.

Since the review of 14 Nov 2026 (replan A2b M1): with no key, a text the rules cannot read is no longer
`supplier-unavailable` (503, "a service cannot be reached") but `invalid-request` (422) with what was not read and
a question to the person (`tta.agent.unread.as_question`). Nothing is out of reach there; the text needs a
person's answer. With a key and Gemini out of reach it stays `supplier-unavailable`, as below.

Task FALLBACK-1 adds a third reader. When Gemini cannot be reached, or no key is set (`live` is `None`), a text is
answered from its recording if there is one, else by the rule-based reader (`tta.agent.rules_reader`), else
`supplier-unavailable` with the same sentence as before, followed by what the rules could not read. A model that
answered is never overridden. A run follows the same order: with no recorded run, the rules read the text and make
the fixed run of the hand-built recordings (`tta.agent.rules_model`), and its report opens by saying so. A photo is
not read by the rules: it needs the model.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence

from tta.agent.gemini import ModelUnreachable
from tta.agent.labels import fallback_sentence, made_on, photo_sentence, rules_sentence
from tta.agent.model import AnswerSource
from tta.agent.notes import notes_of
from tta.agent.parser import ModelRequestParser
from tta.agent.recorded import HAND_BUILT_MODEL_ID, LIVE_SOURCE, RECORDED_MODEL_ID, RecordedModel, Recording
from tta.agent.runner import ModelAgentRunner
from tta.agent.unread import NotReadByRules, as_question
from tta.contracts.agent import AgentRun, Reading, ReadingSource
from tta.contracts.common import Identity
from tta.contracts.errors import SupplierUnavailable, TtaError
from tta.contracts.ports import GatewayService
from tta.contracts.request import PurchaseRequest

GEMINI_DID_NOT_ANSWER = "Gemini did not answer; this run was served from {source}."
FROM_A_RECORDING = "a recording made on {when}"
FROM_AN_UNDATED_RECORDING = "a recording of the model's earlier answers"
FROM_HAND_BUILT = "answers written by hand, not by a model"
RULES_RAN_FOR_GEMINI = "Gemini did not answer; this run was read and made by fixed rules, not by a model."
RULES_RAN_WITHOUT_KEY = (
    "No Gemini key is set and this text has no recording; this run was read and made by fixed rules, not by a model."
)
RULES_COULD_NOT = "The fixed rules could not read it either: {why}."
SEND_THE_TYPED_REQUEST = " Send the typed request"  # how the sentences of `supplier-unavailable` end

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


def either(detail: str, why: str) -> str:
    """The sentence of `supplier-unavailable` with what the rules could not read, before its advice."""
    head, advice, rest = detail.partition(SEND_THE_TYPED_REQUEST)
    return f"{head} {RULES_COULD_NOT.format(why=why)}{advice}{rest}"


def _not_read(missed: SupplierUnavailable, unread: NotReadByRules, *, key_set: bool) -> TtaError:
    """The error the caller gets. With no key: the rules' question to the person (422). With a key: an error of
    the same kind as Gemini's, with what the rules could not read."""
    if not key_set:
        return as_question(unread)
    return type(missed)(either(missed.detail, unread.why), **missed.extensions)


def _answered_by(reading: Reading) -> str:
    """What answered, as a trace names it: the model id, "rule-based", "recorded" or "hand-built"."""
    if reading.source in (ReadingSource.MODEL, ReadingSource.RULE_BASED):
        return reading.model
    return HAND_BUILT_MODEL_ID if reading.source is ReadingSource.HAND_BUILT else RECORDED_MODEL_ID


class FallbackParser:
    """Implements `RequestParser`: Gemini's reading; when Gemini cannot be reached, or no key is set (`live` is
    `None`), the recorded one, else the rule-based one (`rules`), else `supplier-unavailable`."""

    def __init__(
        self, *, live: ModelRequestParser | None, recorded: ModelRequestParser, recordings: RecordedModel,
        rules: ModelRequestParser | None = None,
    ) -> None:
        self._live = live
        self._recorded = recorded
        self._recordings = recordings
        self._rules = rules
        self._last_answered_by = (live or recorded).model_id

    @property
    def model_id(self) -> str:
        """What answered the last reading: the Gemini model id until a recording or the rules stood in for it."""
        return self._last_answered_by

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        return self.read(text, identity).request

    def read(self, text: str, identity: Identity) -> Reading:
        try:
            reading = (self._live or self._recorded).read(text, identity)
        except SupplierUnavailable as missed:
            reading = self._instead(text, identity, missed)
        self._last_answered_by = _answered_by(reading)  # one assignment: safe from several threads
        return reading

    def _instead(self, text: str, identity: Identity, missed: SupplierUnavailable) -> Reading:
        """With a key: a recording, else the rules, only when Gemini could not be reached. With no key the recorded
        parser has no recording of this text for this profile: the rules."""
        if self._live is None:
            return self._by_rules(text, identity, missed)
        if not isinstance(missed, ModelUnreachable):
            raise missed  # a refusal is answered as before
        if self._recordings.holds("parse", text, identity.profile_id):
            reading = self._from_recording(text, identity)
        else:
            reading = self._by_rules(text, identity, missed)
        logger.warning("%s %s", reading.sentence, missed.detail)
        return reading

    def _by_rules(self, text: str, identity: Identity, missed: SupplierUnavailable) -> Reading:
        if self._rules is None:
            raise missed
        try:
            reading = self._rules.read(text, identity)
        except NotReadByRules as unread:
            raise _not_read(missed, unread, key_set=self._live is not None) from unread
        # What the sentence says after its source stays: a rule read as strict, the formula, "the usual".
        sentence = rules_sentence(key_set=self._live is not None) + notes_of(reading)
        return reading.model_copy(update={"sentence": sentence})

    def read_image(self, image: bytes, media_type: str, identity: Identity) -> tuple[list[str], Reading]:
        """Gemini's transcription and reading of a photo, or both from the recordings when Gemini cannot be
        reached and the photo has them for this profile. With no key, the recordings only."""
        if self._live is None:
            return self._recorded.read_image(image, media_type, identity)
        try:
            lines, reading = self._live.read_image(image, media_type, identity)
        except ModelUnreachable as unreachable:
            digest = hashlib.sha256(image).hexdigest()
            if not self._recordings.holds_photo(digest, identity.profile_id):
                raise
            lines, reading = self._recorded.read_image(image, media_type, identity)
            read = AnswerSource(reading.source, reading.model, reading.recorded_at)
            sentence = photo_sentence(self._recordings.transcription_source(digest), read, fallback=True)
            reading = reading.model_copy(update={"sentence": sentence})
            logger.warning("%s %s", sentence, unreachable.detail)
        self._last_answered_by = _answered_by(reading)
        return lines, reading

    def _from_recording(self, text: str, identity: Identity) -> Reading:
        reading = self._recorded.read(text, identity)
        answer = AnswerSource(reading.source, reading.model, reading.recorded_at)
        sentence = fallback_sentence(answer) + notes_of(reading)
        return reading.model_copy(update={"sentence": sentence})


class FallbackRunner:
    """Implements `AgentRunner`: a run on Gemini; when Gemini cannot be reached before the run's first gateway call,
    or no key is set (`live` is `None`), the recorded run, else the rules' run (`rules`), else
    `supplier-unavailable`. The recorded run is a whole run: its reading and its calls are both recorded."""

    def __init__(
        self, *, live: ModelAgentRunner | None, recorded: ModelAgentRunner, recordings: RecordedModel,
        rules: ModelAgentRunner | None = None,
    ) -> None:
        self._live = live
        self._recorded = recorded
        self._recordings = recordings
        self._rules = rules

    @property
    def model_id(self) -> str:
        return (self._live or self._recorded).model_id

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        try:
            return (self._live or self._recorded).run_agent(text, identity, tools)
        except SupplierUnavailable as missed:  # raised only before the run's first gateway call
            if self._live is None:
                return self._by_rules(text, identity, tools, missed)
            if not isinstance(missed, ModelUnreachable):
                raise
            held = (self._recordings.holds(kind, text, identity.profile_id) for kind in ("parse", "run"))
            if not all(held):
                return self._by_rules(text, identity, tools, missed)
            opening = served_from(self._recordings.recordings_of(text))
            logger.warning("%s %s", opening, missed.detail)
        run = self._recorded.run_agent(text, identity, tools)
        return run.model_copy(update={"report": f"{opening} {run.report}"})

    def _by_rules(
        self, text: str, identity: Identity, tools: GatewayService, missed: SupplierUnavailable
    ) -> AgentRun:
        if self._rules is None:
            raise missed
        try:
            run = self._rules.run_agent(text, identity, tools)
        except NotReadByRules as unread:
            raise _not_read(missed, unread, key_set=self._live is not None) from unread
        opening = RULES_RAN_FOR_GEMINI if self._live is not None else RULES_RAN_WITHOUT_KEY
        logger.warning("%s %s", opening, missed.detail)
        return run.model_copy(update={"report": f"{opening} {run.report}"})
