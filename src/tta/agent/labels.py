"""The sentences that say who read a request: a model just now, a recording of one, a person, or fixed rules
(tasks FIX-9 and FALLBACK-1).

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
READ_BY_RULES = "Read by fixed rules, not by a model."
BY_RULES = "fixed rules, not a model"
RULES_FOR_GEMINI = "Read by fixed rules, not by a model: Gemini did not answer."
RULES_WITHOUT_KEY = "Read by fixed rules, not by a model: no Gemini key is set."


def made_on(at: datetime) -> str:
    """`14 Nov 2026 at 06:14 UTC`."""
    utc = at.astimezone(UTC)
    return MADE_ON.format(day=utc.day, month=MONTHS[utc.month - 1], year=utc.year, time=f"{utc:%H:%M}")


def _what(answer: AnswerSource) -> str:
    if answer.source is ReadingSource.HAND_BUILT:
        return BY_HAND
    if answer.source is ReadingSource.RULE_BASED:
        return BY_RULES
    if answer.recorded_at is None:
        return AN_UNDATED_RECORDING.format(model=answer.model)
    return A_RECORDING.format(model=answer.model, when=made_on(answer.recorded_at))


def reading_sentence(answer: AnswerSource) -> str:
    """"Read by gemini-3.6-flash.", "Read from a recording of … made on …; no model was asked.", or
    "Read from an answer written by hand, not by a model."."""
    if answer.source is ReadingSource.MODEL:
        return READ_BY_MODEL.format(model=answer.model)
    if answer.source is ReadingSource.RULE_BASED:
        return READ_BY_RULES
    what = READ_FROM.format(what=_what(answer))
    return f"{what}." if answer.source is ReadingSource.HAND_BUILT else what + NO_MODEL_ASKED


def fallback_sentence(answer: AnswerSource) -> str:
    """The sentence of a reading served from a recording because Gemini did not answer."""
    return GEMINI_DID_NOT_ANSWER.format(what=_what(answer))


def rules_sentence(*, key_set: bool) -> str:
    """The sentence of a reading made by the rule-based reader (`tta.agent.rules_reader`): because Gemini did not
    answer, or because no key is set and the text has no recording."""
    return RULES_FOR_GEMINI if key_set else RULES_WITHOUT_KEY


# --- a photo: who transcribed it, then who read the lines (task T18) ---------------------------------------

READ_FROM_A_PHOTO = "Read from a photo: {did_not_answer}{transcribed}, then {read}{ending}"
TRANSCRIBED_BY_MODEL = "transcribed by {model}"
TRANSCRIBED_FROM = "transcribed from {what}"
TRANSCRIBED_BY_HAND = "transcribed by hand, not by a model"
READ_BY = "read by {model}"
READ_FROM_WHAT = "read from {what}"
DID_NOT_ANSWER = "Gemini did not answer; "


def _transcribed(answer: AnswerSource) -> str:
    if answer.source is ReadingSource.MODEL:
        return TRANSCRIBED_BY_MODEL.format(model=answer.model)
    if answer.source is ReadingSource.HAND_BUILT:
        return TRANSCRIBED_BY_HAND
    return TRANSCRIBED_FROM.format(what=_what(answer))


def _read(answer: AnswerSource) -> str:
    if answer.source is ReadingSource.MODEL:
        return READ_BY.format(model=answer.model)
    return READ_FROM_WHAT.format(what=_what(answer))


def photo_sentence(transcribed: AnswerSource, read: AnswerSource, *, fallback: bool = False) -> str:
    """"Read from a photo: transcribed by gemini-3.6-flash, then read by gemini-3.6-flash.", or with recordings
    "… transcribed from a recording of … made on …, then read from a recording of …; no model was asked.", or,
    when Gemini did not answer, "Read from a photo: Gemini did not answer; transcribed from a recording …"."""
    asked = ReadingSource.MODEL in (transcribed.source, read.source)
    ending = "." if asked or fallback else NO_MODEL_ASKED
    return READ_FROM_A_PHOTO.format(
        did_not_answer=DID_NOT_ANSWER if fallback else "", transcribed=_transcribed(transcribed), read=_read(read),
        ending=ending,
    )
