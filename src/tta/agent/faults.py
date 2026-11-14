"""What is wrong with a model's structured answer, named by field path and a fixed reason (task T10; moved for T18).

Used by the parser of a request and by the transcription of a photo: a fault never repeats the model's words.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

MAX_ANSWERS = 2  # the first answer, and one more when it does not validate

NOT_JSON = "not a JSON object"
UNKNOWN_FIELD = "a field the typed request does not have"
NOT_IN_ANSWER = "missing from the answer"
NOT_VALID = "not a valid value ({code})"


@dataclass(frozen=True)
class Fault:
    """Something wrong with the model's answer. It names a field and a fixed reason, never the model's words."""

    path: str
    reason: str

    def __str__(self) -> str:
        return f"{self.path}: {self.reason}"


def _path(location: Sequence[Any]) -> str:
    """`("lines", 0, "quantity")` as `lines[0].quantity`."""
    path = ""
    for part in location:
        path += f"[{part}]" if isinstance(part, int) else f".{part}" if path else str(part)
    return path or "answer"


def validation_faults(error: ValidationError) -> tuple[Fault, ...]:
    """One fault per error, named by where it sits and by pydantic's error code: never by the input."""
    faults = []
    for item in error.errors(include_input=False, include_url=False):
        location, code = item["loc"], item["type"]
        if code == "extra_forbidden":
            faults.append(Fault(_path(location[:-1]), UNKNOWN_FIELD))  # a made-up key is not repeated
        elif code == "missing":
            faults.append(Fault(_path(location), NOT_IN_ANSWER))
        else:
            faults.append(Fault(_path(location), NOT_VALID.format(code=code)))
    return tuple(faults)
