"""Limits on what one caller can send and how often (task T09; security review of the layers below).

Scores on the 15% "credible path toward production": the audit trail is append-only and the supplier's API
has a call budget, so a caller must not be able to fill the one or spend the other for free.

The values are ours and illustrative, like the buyer profiles: the mock publishes no rate limit
(AIMO/docs/API.md section 2).
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from tta.api.errors import BodyTooLarge, body_too_large_problem, problem_response, status_problem
from tta.contracts.errors import RateLimited

# A scenario request is under 1 KB and one that names 1,000 product ids about 25 KB. A request that fills
# every field of the contract to its maximum (20 lines of 2,000 characters and all their terms) is larger
# than this and is refused: no real request looks like that.
MAX_BODY_KILOBYTES = 64
MAX_BODY_BYTES = MAX_BODY_KILOBYTES * 1024
BODY_TOO_LARGE = f"The request body is larger than {MAX_BODY_KILOBYTES} KB, the most this gateway reads."
BAD_LENGTH_STATUS = 400
NOT_A_LENGTH = -1
BAD_LENGTH = "The Content-Length header is not a number."

DEFAULT_RATE_LIMIT_CALLS = 60
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60.0
# The demonstration tokens are public, so everyone trying the demo shares one token per identity: the same
# limit would turn visitors away. One run of the buyer agent counts three calls (run, offer, order).
DEMO_RATE_LIMIT_CALLS = 240
RATE_LIMITED = (
    "Too many requests that reach the supplier or write to the audit trail: at most {calls} in "
    "{window} seconds for one token. Try again in {wait} seconds."
)


@dataclass(frozen=True)
class RateLimit:
    """At most `calls` in any `window_seconds`, for one caller."""

    calls: int = DEFAULT_RATE_LIMIT_CALLS
    window_seconds: float = DEFAULT_RATE_LIMIT_WINDOW_SECONDS


def default_rate_limit(shared_demo_tokens: bool) -> RateLimit:
    """The limit for one token: wider where the tokens are the public demonstration tokens."""
    return RateLimit(calls=DEMO_RATE_LIMIT_CALLS if shared_demo_tokens else DEFAULT_RATE_LIMIT_CALLS)


class RateLimiter:
    """A sliding window per caller, in memory, for one process. A refused call is not counted."""

    def __init__(self, limit: RateLimit, *, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._limit = limit
        self._monotonic = monotonic
        self._lock = threading.Lock()  # routes run in a thread pool
        self._calls: dict[str, deque[float]] = {}

    def check(self, caller_id: str) -> None:
        """Count one call of this caller, or raise `RateLimited` saying how long to wait."""
        now = self._monotonic()
        with self._lock:
            calls = self._calls.setdefault(caller_id, deque())
            while calls and calls[0] <= now - self._limit.window_seconds:
                calls.popleft()
            if len(calls) < self._limit.calls:
                calls.append(now)
                return
            wait = max(1, math.ceil(calls[0] + self._limit.window_seconds - now)) if calls else 1
        raise RateLimited(
            RATE_LIMITED.format(calls=self._limit.calls, window=f"{self._limit.window_seconds:g}", wait=wait),
            retry_after_seconds=wait,
        )


class BodyLimitMiddleware:
    """Refuses a request body over the limit: by its declared length before anything is read, and by counting
    the bytes as they arrive when no length is declared."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        declared = _declared_length(scope)
        if declared == NOT_A_LENGTH:
            await problem_response(status_problem(BAD_LENGTH_STATUS, BAD_LENGTH))(scope, receive, send)
            return
        if declared is not None and declared > self._max_bytes:
            # Answered here, before the body is read: this middleware sits outside the error handlers.
            await problem_response(body_too_large_problem(BODY_TOO_LARGE))(scope, receive, send)
            return
        received = 0

        async def counted() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    raise BodyTooLarge(BODY_TOO_LARGE)  # raised inside the route: the error handler answers
            return message

        await self._app(scope, counted, send)


def _declared_length(scope: Scope) -> int | None:
    """The Content-Length of the request: `None` when there is none, `NOT_A_LENGTH` when it is not a number."""
    for name, value in scope.get("headers", ()):
        if name == b"content-length":
            text = value.decode("latin-1").strip()
            return int(text) if text.isdigit() else NOT_A_LENGTH
    return None
