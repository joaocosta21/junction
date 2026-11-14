"""The one interface the buyer agent has to a language model (SPEC section 11).

Two things are asked of a model and nothing else: a structured answer held to a JSON Schema (`extract`),
and the next turn of a function-calling conversation (`next_turn`). The Gemini model and the recorded
model both implement it, so the parser and the loop are the same code with and without a key.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol, runtime_checkable

from tta.contracts.agent import ReadingSource
from tta.contracts.common import JsonDict
from tta.contracts.errors import SupplierUnavailable


class ModelUnreachable(SupplierUnavailable):
    """The model gave no answer after the retries (a time-out, a connection failure, 408, 429 or a 5xx), or it is
    not available to this gateway at all (401, 402 or 403, at once). Raised by every model client alike.
    Answered as `supplier-unavailable` like its parent; a recording or the fixed rules may stand in for it
    (`tta.agent.fallback`)."""


@dataclass(frozen=True)
class ExtractCall:
    """One request for a structured answer."""

    system: str  # the instruction: ours, never text from the product file, the API or the buyer
    text: str  # the buyer's words: data to read, also the key of a recorded answer
    schema: JsonDict  # the JSON Schema the answer is held to
    # Never sent to a live model. A recording is served only for the profile it was recorded for, and its
    # `needed_by` is read again by the calendar rule when it was recorded on another day than `today`.
    profile_id: str | None = None
    today: date | None = None  # the date in Helsinki the request is read on
    # The corrective turn (task AG): the answer that failed the checks and what failed, each fault as its field
    # path and a fixed reason of ours. A client that holds no conversation (a recording, the fixed rules) ignores
    # both and answers as it did.
    previous_answer: str | None = None
    faults: tuple[str, ...] = ()


@dataclass(frozen=True)
class TranscribeCall:
    """One request to write down the lines a photo holds (task T18). The image is data, never an instruction."""

    system: str  # the instruction: ours, never text from the photo
    request: str  # the words that ask for the transcription, sent after the image
    image: bytes = field(repr=False)  # checked by its first bytes (`tta.agent.images`); never shown in a repr
    media_type: str  # the type the first bytes gave
    schema: JsonDict  # the JSON Schema the answer is held to
    profile_id: str | None = None  # never sent to a live model: a recording is served for its own profile only

    @property
    def digest(self) -> str:
        """The SHA-256 of the image: the key of a recorded transcription."""
        return hashlib.sha256(self.image).hexdigest()


@dataclass(frozen=True)
class TurnCall:
    """One request for the next turn of the function-calling loop."""

    system: str  # the instruction: the same on every turn of a run
    request_text: str  # the buyer's words: the key of a recorded run, not sent to a live model
    history: tuple[JsonDict, ...]  # the conversation so far, as plain steps (`tta.agent.contents`)
    tools: tuple[JsonDict, ...]  # the function declarations
    turn: int  # 1 for the first turn of the run
    profile_id: str | None = None  # the caller's buyer profile: a recorded run is served only for its own


@dataclass(frozen=True)
class FunctionCall:
    """A function the model asks for. Its arguments are a proposal: the runner validates them."""

    id: str
    name: str
    arguments: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class ModelTurn:
    """What the model returned for one turn."""

    steps: tuple[JsonDict, ...] = ()  # as received, to send back unchanged on the next turn
    calls: tuple[FunctionCall, ...] = ()
    text: str | None = None  # the model's own words; never used as the report


@dataclass(frozen=True)
class AnswerSource:
    """Who gave the structured answer for a sentence: a model just now, a recording of one, or a person."""

    source: ReadingSource
    model: str  # the model id; for a recording, the model it was recorded from; "hand-built" for a person
    recorded_at: datetime | None = None  # when the recording was made
    host: str | None = None  # where a model of ours is served ("Modal"), when the reading's sentence says so
    checked: bool = False  # the reading passed the checks of `tta.agent.held`, and its sentence says so


@runtime_checkable
class AgentModel(Protocol):
    """Raises `SupplierUnavailable` when no answer can be had."""

    @property
    def model_id(self) -> str:
        """The model id, or "recorded" when the answers are served from recorded outputs."""
        ...

    @property
    def recorded(self) -> bool: ...

    def label_for(self, request_text: str) -> str:
        """What a trace shows as the model for this sentence: the model id; "recorded" for answers saved
        from a model; "hand-built" when a person wrote the fixture. A trace never credits a model with
        an answer it did not give."""
        ...

    def extract(self, call: ExtractCall) -> str:
        """The JSON text of a structured answer. It is a proposal: the caller validates it."""
        ...

    def answer_source(self, request_text: str) -> AnswerSource:
        """Who gave the structured answer `extract` serves for this sentence."""
        ...

    def next_turn(self, call: TurnCall) -> ModelTurn: ...


@runtime_checkable
class ImageModel(Protocol):
    """A model that can be shown a photo (task T18). Raises `SupplierUnavailable` when no answer can be had."""

    def transcribe(self, call: TranscribeCall) -> str:
        """The JSON text of the lines the photo holds. It is a proposal: the caller validates it."""
        ...

    def transcription_source(self, digest: str) -> AnswerSource:
        """Who wrote down the lines `transcribe` serves for the photo with this SHA-256."""
        ...
