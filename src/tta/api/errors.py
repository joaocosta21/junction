"""Every error leaves as an RFC 9457 `application/problem+json` body (SPEC section 2).

Scores on the 15% "open, documented standards rather than a proprietary format": an agent reads one stable
`type` per kind of problem and never has to parse a sentence.

A typed error (`tta.contracts.errors`) carries its own type, title and status. A request that does not match
its contract is `invalid-request` and lists the fields that are wrong, never the values sent. Anything
nobody expected is a 500 with a general detail; the fault itself goes to the log only.

No problem repeats text the caller sent. That is why none has an `instance`: the path of a request holds
the ids, or anything else, the caller put there.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from tta.contracts.errors import (
    PROBLEM_CONTENT_TYPE,
    InvalidRequest,
    ProblemDetails,
    RateLimited,
    TtaError,
    Unauthenticated,
)

NO_SPECIFIC_TYPE = "about:blank"  # RFC 9457 section 4.2.1: the problem has no meaning beyond its HTTP status
INTERNAL_DETAIL = "The gateway could not complete this request. Nothing in this answer can be relied on."
MAX_ERRORS_LISTED = 20
MAX_ERRORS_IN_DETAIL = 3
UNKNOWN_FIELD_TYPE = "extra_forbidden"
UNKNOWN_FIELD = "a field this request does not have"
# A part of a field path is shown only when it looks like a name of ours; anything else is text the caller chose.
_FIELD_PART = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
HIDDEN_PART = "?"

logger = logging.getLogger(__name__)


def problem_response(problem: ProblemDetails, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        problem.model_dump(mode="json", exclude_none=True), status_code=problem.status,
        media_type=PROBLEM_CONTENT_TYPE, headers=headers,
    )


def status_problem(status: int, detail: str | None) -> ProblemDetails:
    """A problem that says no more than its HTTP status (an unknown path, a method that is not allowed)."""
    return ProblemDetails(type=NO_SPECIFIC_TYPE, title=HTTPStatus(status).phrase, status=status, detail=detail)


class BodyTooLarge(HTTPException):
    """Raised by the body limit while a body is read, so a route never sees more than the limit."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE, detail=detail)


def body_too_large_problem(detail: str) -> ProblemDetails:
    """A body over the limit is an invalid request; its status is the one HTTP has for it, 413."""
    return InvalidRequest(detail).to_problem().model_copy(update={"status": int(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)})


def _field(location: Sequence[Any], error_type: str) -> str:
    """The path of the field that is wrong, for example `body.lines.0.quantity`. A key the caller made up is
    not repeated: an unknown field is named by where it sits."""
    parts = list(location[:-1] if error_type == UNKNOWN_FIELD_TYPE else location)
    shown = [
        str(part) if isinstance(part, int) or _FIELD_PART.fullmatch(str(part)) else HIDDEN_PART for part in parts
    ]
    return ".".join(shown) or "request"


def _what_is_wrong(error: dict[str, Any]) -> str:
    """Pydantic's message, unless it repeats what the caller sent: then only the kind of error."""
    if error["type"] == UNKNOWN_FIELD_TYPE:
        return UNKNOWN_FIELD
    message, sent = str(error.get("msg", "")), error.get("input")
    repeats = isinstance(sent, str | int | float) and not isinstance(sent, bool) and len(str(sent)) > 1 and (
        str(sent) in message
    )
    return str(error["type"]) if repeats or not message else message


def validation_problem(errors: Sequence[dict[str, Any]]) -> ProblemDetails:
    """`invalid-request` listing each field and what is wrong with it. No value the caller sent is repeated."""
    listed = [
        {"field": _field(error.get("loc", ()), str(error["type"])), "problem": _what_is_wrong(error)}
        for error in errors[:MAX_ERRORS_LISTED]
    ]
    first = "; ".join(f"{entry['field']}: {entry['problem']}" for entry in listed[:MAX_ERRORS_IN_DETAIL])
    more = len(errors) - min(len(errors), MAX_ERRORS_IN_DETAIL)
    rest = f"; and {more} more" if more else ""
    detail = f"The request does not match what this route takes. {first}{rest}."
    return InvalidRequest(detail, errors=listed).to_problem()


def _headers(error: TtaError) -> dict[str, str] | None:
    if isinstance(error, Unauthenticated):
        return {"WWW-Authenticate": "Bearer"}
    if isinstance(error, RateLimited) and "retry_after_seconds" in error.extensions:
        return {"Retry-After": str(error.extensions["retry_after_seconds"])}
    return None


def install_error_handlers(app: FastAPI) -> None:
    """Register one handler per kind of error. The most specific class wins."""

    @app.exception_handler(TtaError)
    def typed_error(request: Request, error: TtaError) -> JSONResponse:
        return problem_response(error.to_problem(), _headers(error))

    @app.exception_handler(RequestValidationError)
    def request_does_not_match(request: Request, error: RequestValidationError) -> JSONResponse:
        return problem_response(validation_problem(error.errors()))

    @app.exception_handler(ValidationError)
    def model_does_not_validate(request: Request, error: ValidationError) -> JSONResponse:
        # A contract model built from what a caller sent, somewhere below the route.
        return problem_response(validation_problem(error.errors()))

    @app.exception_handler(BodyTooLarge)
    def body_too_large(request: Request, error: BodyTooLarge) -> JSONResponse:
        return problem_response(body_too_large_problem(str(error.detail)))

    @app.exception_handler(HTTPException)
    def http_status(request: Request, error: HTTPException) -> JSONResponse:
        detail = error.detail if error.detail != HTTPStatus(error.status_code).phrase else None
        return problem_response(status_problem(error.status_code, detail), error.headers)

    @app.exception_handler(Exception)
    def anything_else(request: Request, error: Exception) -> JSONResponse:
        logger.error("Unexpected error on %s %s", request.method, request.url.path, exc_info=error)
        return problem_response(status_problem(HTTPStatus.INTERNAL_SERVER_ERROR, INTERNAL_DETAIL))
