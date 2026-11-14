"""A photo of a handwritten or printed order list becomes a typed request, in two visible steps (task T18).

Scores on the Gemini award ("beyond simply adding an LLM") and the 20% "precise match": a kitchen writes its
order on paper. The model still decides nothing:
1. **Transcribe.** Gemini is shown the photo and returns the lines it reads, each word for word, held to a
   JSON Schema (`schema.TRANSCRIPTION_SCHEMA`), with no interpretation. The lines are shown to the person.
2. **Read.** The same parser and the same text check as for typed text read those lines
   (`ModelRequestParser.read`): a quantity, a unit, a day or an exclusion is taken only when the lines give it.

The image is untrusted input: it is checked by its first bytes and its size before any model is asked
(`tta.agent.images`), held in memory only, and never written to a log; neither are the lines read in it. An
instruction written in the photo is a line like any other: the transcription has no tools, and what the lines
then ask for is what the gateway's policy decides on.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError

from tta.agent.faults import MAX_ANSWERS, NOT_JSON, Fault, validation_faults
from tta.agent.images import checked_image
from tta.agent.labels import photo_sentence
from tta.agent.model import AnswerSource, ImageModel, TranscribeCall
from tta.agent.notes import notes_of
from tta.agent.prompts import TRANSCRIBE_REQUEST, TRANSCRIBER_INSTRUCTION
from tta.agent.schema import TRANSCRIPTION_SCHEMA
from tta.contracts.agent import Reading
from tta.contracts.common import Identity
from tta.contracts.errors import InvalidRequest, SupplierUnavailable

MAX_TRANSCRIPTION_LINES = 40  # a kitchen's list; a request of the demo has at most 5 lines anyway
LINE_BREAK = "\n"  # between two lines of the photo, in the text the parser reads
TRANSCRIPTION = "transcription"  # the field path faults and missing facts are named by

NO_PHOTO_READER = (
    "The model behind the request parser cannot be shown a photo. Type the request, or send the typed request to "
    "POST /v1/offers."
)
NOTHING_WRITTEN = "No writing could be read in the photo. Send a sharper photo of the list, or type the request."
NOT_TRANSCRIBED = (
    "The photo could not be transcribed: after {answers} answers of the model, {faults}. Send another photo, or "
    "type the request."
)
TOO_MANY_LINES = f"more than {MAX_TRANSCRIPTION_LINES} lines"

logger = logging.getLogger(__name__)


class _Transcription(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    lines: tuple[StrictStr, ...]  # a number where a line should be is a fault, never a line


def _under(path: str) -> str:
    """A fault's path, under the transcription: `lines[0]` is `transcription.lines[0]`."""
    return TRANSCRIPTION if path == "answer" else f"{TRANSCRIPTION}.{path}"


def _lines(answer: str) -> tuple[tuple[str, ...], tuple[Fault, ...]]:
    """The non-empty lines of the model's answer and no fault, or no line and its faults, each named by its field
    path and a fixed reason: never by the model's words."""
    try:
        data = json.loads(answer)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return (), (Fault(TRANSCRIPTION, NOT_JSON),)
    try:
        transcription = _Transcription.model_validate(data)
    except ValidationError as error:
        return (), tuple(Fault(_under(fault.path), fault.reason) for fault in validation_faults(error))
    # A line the model wrote with a break in it is two lines of the photo.
    lines = tuple(part.strip() for line in transcription.lines for part in line.splitlines() if part.strip())
    if len(lines) > MAX_TRANSCRIPTION_LINES:
        return (), (Fault(f"{TRANSCRIPTION}.lines", TOO_MANY_LINES),)
    return lines, ()


def transcribe(model: ImageModel, call: TranscribeCall) -> tuple[str, ...]:
    """The lines the photo holds. An answer that does not validate is asked for once more, then refused."""
    faults: tuple[Fault, ...] = ()
    for answer_number in range(1, MAX_ANSWERS + 1):
        lines, faults = _lines(model.transcribe(call))
        if not faults:
            if not lines:
                raise InvalidRequest(NOTHING_WRITTEN, missing=[TRANSCRIPTION])
            return lines
        logger.info("Transcription %d of the model did not validate: %s", answer_number, "; ".join(map(str, faults)))
    raise InvalidRequest(
        NOT_TRANSCRIBED.format(answers=MAX_ANSWERS, faults="; ".join(map(str, faults))),
        faults=[fault.path for fault in faults],
    )


def read_photo(
    *, model: object, image: bytes, identity: Identity, read: Callable[[str, Identity], Reading]
) -> tuple[list[str], Reading]:
    """The lines read in the photo and the typed request read from them, with who did each. Raises
    `InvalidRequest` before any model call for an upload that is not an accepted image of at most 5 MB, and as
    `read` does for the lines; `SupplierUnavailable` when the model cannot be shown a photo or does not answer."""
    photo = checked_image(image)  # the first bytes decide; the type the sender declared is not trusted
    if not isinstance(model, ImageModel):
        raise SupplierUnavailable(NO_PHOTO_READER)
    call = TranscribeCall(
        system=TRANSCRIBER_INSTRUCTION, request=TRANSCRIBE_REQUEST, image=photo.data, media_type=photo.media_type,
        schema=TRANSCRIPTION_SCHEMA, profile_id=identity.profile_id,
    )
    lines = transcribe(model, call)
    reading = read(LINE_BREAK.join(lines), identity)
    transcribed = model.transcription_source(photo.digest)
    by = AnswerSource(reading.source, reading.model, reading.recorded_at)
    sentence = photo_sentence(transcribed, by) + notes_of(reading)  # a rule read as strict, the formula, the usual
    return list(lines), reading.model_copy(update={"sentence": sentence})
