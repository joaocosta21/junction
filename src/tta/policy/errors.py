"""The error raised when a rules file or a profile file cannot be used."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ValidationError

MAX_SHOWN_INPUT_LENGTH = 80


class PolicyLoadError(ValueError):
    """A rules file or a buyer profile is broken. The gateway must not start with it.

    Not one of the errors of `tta.contracts.errors`: those are answers to a caller of the API, and
    this one is raised before any call is served.
    """

    def __init__(self, source: str, problems: Sequence[str]) -> None:
        self.source = source
        self.problems = tuple(problems)
        super().__init__(f"{source}: " + "; ".join(self.problems))


def validation_problems(error: ValidationError) -> list[str]:
    """One line per schema error: where it is, what is wrong and, for a plain value, what was given."""
    problems: list[str] = []
    for item in error.errors(include_url=False):
        where = ".".join(str(part) for part in item["loc"]) or "the file"
        given = item.get("input")
        is_plain = isinstance(given, str | int | float | bool) and len(repr(given)) <= MAX_SHOWN_INPUT_LENGTH
        shown = f" (got {given!r})" if is_plain else ""
        problems.append(f"{where}: {item['msg']}{shown}")
    return problems
