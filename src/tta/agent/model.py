"""The one interface the buyer agent has to a language model (SPEC section 11).

Two things are asked of a model and nothing else: a structured answer held to a JSON Schema (`extract`),
and the next turn of a function-calling conversation (`next_turn`). The Gemini model and the recorded
model both implement it, so the parser and the loop are the same code with and without a key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from tta.contracts.common import JsonDict


@dataclass(frozen=True)
class ExtractCall:
    """One request for a structured answer."""

    system: str  # the instruction: ours, never text from the product file, the API or the buyer
    text: str  # the buyer's words: data to read, also the key of a recorded answer
    schema: JsonDict  # the JSON Schema the answer is held to


@dataclass(frozen=True)
class TurnCall:
    """One request for the next turn of the function-calling loop."""

    system: str  # the instruction: the same on every turn of a run
    request_text: str  # the buyer's words: the key of a recorded run, not sent to a live model
    history: tuple[JsonDict, ...]  # the conversation so far, as plain steps (`tta.agent.contents`)
    tools: tuple[JsonDict, ...]  # the function declarations
    turn: int  # 1 for the first turn of the run


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

    def next_turn(self, call: TurnCall) -> ModelTurn: ...
