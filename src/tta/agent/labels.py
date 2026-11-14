"""The sentences that say who read a request: a model just now, a recording of one, or a person (task FIX-9).

Scores on the 20% "decisions logged and auditable": a reading served from a recording never looks like the
model's own. The sentence travels with the reading (`tta.contracts.agent.Reading`) to the pages and the API.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tta.agent.model import AnswerSource
from tta.contracts.agent import ReadingSource

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MADE_ON = "{day} {month} {year} at {time} UTC"
READ_BY_MODEL = "Read by {model}."
A_RECORDING = "a recording of {model} made on {when}"
AN_UNDATED_RECORDING = "a recording of {model}"
BY_HAND = "an answer written by hand, not by a model"
READ_FROM = "Read from {what}"
NO_MODEL_ASKED = "; no model was asked."
GEMINI_DID_NOT_ANSWER = "Gemini did not answer; read from {what}."


def made_on(at: datetime) -> str:
    """`14 Nov 2026 at 06:14 UTC`."""
    utc = at.astimezone(UTC)
    return MADE_ON.format(day=utc.day, month=MONTHS[utc.month - 1], year=utc.year, time=f"{utc:%H:%M}")


def _what(answer: AnswerSource) -> str:
    if answer.source is ReadingSource.HAND_BUILT:
        return BY_HAND
    if answer.recorded_at is None:
        return AN_UNDATED_RECORDING.format(model=answer.model)
    return A_RECORDING.format(model=answer.model, when=made_on(answer.recorded_at))


def reading_sentence(answer: AnswerSource) -> str:
    """"Read by gemini-3.6-flash.", "Read from a recording of … made on …; no model was asked.", or
    "Read from an answer written by hand, not by a model."."""
    if answer.source is ReadingSource.MODEL:
        return READ_BY_MODEL.format(model=answer.model)
    what = READ_FROM.format(what=_what(answer))
    return f"{what}." if answer.source is ReadingSource.HAND_BUILT else what + NO_MODEL_ASKED


def fallback_sentence(answer: AnswerSource) -> str:
    """The sentence of a reading served from a recording because Gemini did not answer."""
    return GEMINI_DID_NOT_ANSWER.format(what=_what(answer))
