"""The amended request a suggestion carries in `accept_request`: a new request, never a change to the one given.

Every field the buyer set is kept (`exclude_unset`), so a request that stated no preference still states none.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from tta.contracts.request import PurchaseRequest, RequestLine


def with_lines(request: PurchaseRequest, lines: Sequence[RequestLine]) -> PurchaseRequest:
    """The request with these lines in place of its own, validated again."""
    data = request.model_dump(exclude_unset=True)
    data["lines"] = [line.model_dump(exclude_unset=True) for line in lines]
    return PurchaseRequest.model_validate(data)


def with_line_added(request: PurchaseRequest, line: RequestLine) -> PurchaseRequest:
    return with_lines(request, (*request.lines, line))


def with_line_changed(request: PurchaseRequest, index: int, **changes: Any) -> PurchaseRequest:
    """The request with one line's fields changed; the other lines as they are."""
    changed = RequestLine.model_validate({**request.lines[index].model_dump(exclude_unset=True), **changes})
    return with_lines(request, (*request.lines[:index], changed, *request.lines[index + 1:]))
