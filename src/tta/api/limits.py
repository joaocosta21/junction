"""Limits on what one caller can send and how often (tasks T09 and FIX-8; security review of the layers below).

Scores on the 30% "working end-to-end demo" (the public demo keeps working under a room full of people) and
on the 15% "credible path toward production": the audit trail is append-only, the supplier's API has a call
budget and the model is paid per call, so no caller may fill the one or spend the others, and one visitor of
the demo may not lock out the rest.

Three layers, each a sliding window of one minute, in memory, for one process:
    one caller       a token from the environment; where the tokens are the public demonstration tokens, one
                     visitor (its address, whichever token it sends), with a window per kind of call
                     (`VISITOR_WINDOWS`), each well under its ceiling
    all callers      a ceiling per kind of call (`GLOBAL_CEILINGS`)
    the supplier     live looks at price and availability, overall and per visitor (used by the fall-back)

The values are ours and illustrative, like the buyer profiles: the mock publishes no rate limit
(AIMO/docs/API.md section 2).
"""

from __future__ import annotations

import ipaddress
import math
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from tta.api.errors import BodyTooLarge, body_too_large_problem, problem_response, status_problem
from tta.contracts.common import Identity
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

SECONDS_PER_MINUTE = 60.0
DEFAULT_RATE_LIMIT_CALLS = 60
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = SECONDS_PER_MINUTE
# For all callers together, per minute. One run of the buyer agent is one model call, one lookup and one order.
MAX_OFFERS_AND_SUBSTITUTES_PER_MINUTE = 120
MAX_ORDERS_AND_DECISIONS_PER_MINUTE = 120
MAX_MODEL_CALLS_PER_MINUTE = 30
# One visitor of the public demonstration, whichever of the public tokens it sends (task FIX-10). Each is at
# most a quarter of its ceiling, so one address cannot lock the others out.
MAX_LOOKUPS_PER_VISITOR_PER_MINUTE = 20
MAX_ORDERS_PER_VISITOR_PER_MINUTE = 20
MAX_MODEL_CALLS_PER_VISITOR_PER_MINUTE = 5
# One look is a price call and an availability call. At this rate the default call budget of 150 lasts
# twelve minutes of a full room; above it the fall-back answers from the capture and says so.
MAX_LIVE_LOOKS_PER_MINUTE = 6
MAX_LIVE_LOOKS_PER_VISITOR_PER_MINUTE = 2

RATE_LIMITED = (
    "Too many requests that reach the supplier or write to the audit trail: at most {calls} in "
    "{window} seconds for one caller. Try again in {wait} seconds."
)
VISITOR_LIMITED = (
    "Too many {kind} from one visitor: at most {calls} in {window} seconds. Try again in {wait} seconds."
)
CEILING_REACHED = (
    "This gateway takes at most {calls} {kind} in {window} seconds from all callers together, and that "
    "many were made. Try again in {wait} seconds."
)

UNKNOWN_CLIENT = "unknown"  # no peer address, or one that is not an address: such callers share one window
FORWARDED_HEADER = b"x-forwarded-for"
MAX_ADDRESS_CHARACTERS = 64  # the longest text read as an address; an IPv6 address has at most 45
MAX_FORWARDED_BYTES = 4096  # of X-Forwarded-For, over all its lines: more is not read
IPV6_VISITOR_PREFIX = 64
KEYED_SCOPES = ("http", "websocket")


@dataclass(frozen=True)
class RateLimit:
    """At most `calls` in any `window_seconds`."""

    calls: int = DEFAULT_RATE_LIMIT_CALLS
    window_seconds: float = DEFAULT_RATE_LIMIT_WINDOW_SECONDS


class CallKind(StrEnum):
    """The kinds of call that are counted. The value is how a refusal names them."""

    LOOKUP = "offers and substitute searches"
    ORDER = "orders and approval decisions"
    MODEL = "request readings and agent runs"


GLOBAL_CEILINGS: Mapping[CallKind, int] = MappingProxyType({
    CallKind.LOOKUP: MAX_OFFERS_AND_SUBSTITUTES_PER_MINUTE,
    CallKind.ORDER: MAX_ORDERS_AND_DECISIONS_PER_MINUTE,
    CallKind.MODEL: MAX_MODEL_CALLS_PER_MINUTE,
})
VISITOR_WINDOWS: Mapping[CallKind, int] = MappingProxyType({
    CallKind.LOOKUP: MAX_LOOKUPS_PER_VISITOR_PER_MINUTE,
    CallKind.ORDER: MAX_ORDERS_PER_VISITOR_PER_MINUTE,
    CallKind.MODEL: MAX_MODEL_CALLS_PER_VISITOR_PER_MINUTE,
})


@dataclass(frozen=True)
class Counted:
    """One window a call is counted in: its key, its limit and the sentence for when it is full."""

    key: str
    limit: RateLimit
    refusal: str = RATE_LIMITED


class RateLimiter:
    """Sliding windows by key, in memory, for one process. A call is counted in every window it names or in
    none: a refused call is not counted. A window nobody has used for its whole length is forgotten."""

    def __init__(self, limit: RateLimit, *, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._limit = limit
        self._monotonic = monotonic
        self._lock = threading.Lock()  # routes run in a thread pool
        self._calls: dict[str, deque[float]] = {}
        self._longest_window = limit.window_seconds
        self._swept_at = monotonic()

    def __len__(self) -> int:
        """How many windows are held."""
        with self._lock:
            return len(self._calls)

    def check(self, caller_id: str) -> None:
        """Count one call of this caller, or raise `RateLimited` saying how long to wait."""
        self.check_all((Counted(caller_id, self._limit),))

    def allows(self, caller_id: str) -> bool:
        """Count one call of this caller and answer true, or answer false when its window is full."""
        return self.full_window((Counted(caller_id, self._limit),)) is None

    def full_window(self, counted: Sequence[Counted]) -> Counted | None:
        """Count one call in every window named and answer `None`, or answer the fullest and count it in none."""
        wait, full = self._take(counted)
        return full if wait else None

    def check_all(self, counted: Sequence[Counted]) -> None:
        """Count one call in every window named, or raise `RateLimited` for the fullest and count it in none."""
        wait, full = self._take(counted)
        if wait:
            raise RateLimited(
                full.refusal.format(calls=full.limit.calls, window=f"{full.limit.window_seconds:g}", wait=wait),
                retry_after_seconds=wait,
            )

    def _take(self, counted: Sequence[Counted]) -> tuple[int, Counted]:
        """(0, …) after counting the call in every window; else (seconds to wait, the window to wait for)."""
        now = self._monotonic()
        with self._lock:
            self._forget_idle(now, counted)
            wait, full = max(((self._wait(each, now), each) for each in counted), key=lambda found: found[0])
            if wait == 0:
                for each in counted:
                    self._calls.setdefault(each.key, deque()).append(now)
            return wait, full

    def _wait(self, counted: Counted, now: float) -> int:
        """Seconds until a call fits this window: zero when one fits now. Drops the calls that have left it."""
        calls, limit = self._calls.get(counted.key), counted.limit
        while calls and calls[0] <= now - limit.window_seconds:
            calls.popleft()
        if len(calls or ()) < limit.calls:
            return 0
        return max(1, math.ceil(calls[0] + limit.window_seconds - now)) if calls else 1

    def _forget_idle(self, now: float, counted: Sequence[Counted]) -> None:
        """Once per window length, drop every window whose last call is older than the longest window."""
        self._longest_window = max(self._longest_window, *(each.limit.window_seconds for each in counted))
        if now - self._swept_at < self._longest_window:
            return
        self._swept_at = now
        idle = [key for key, calls in self._calls.items() if not calls or calls[-1] <= now - self._longest_window]
        for key in idle:
            del self._calls[key]


# --- who is at the other end ----------------------------------------------------------------------------

_client_key: ContextVar[str] = ContextVar("tta_client_key", default=UNKNOWN_CLIENT)


def current_client_key() -> str:
    """The client key of the request being served; `UNKNOWN_CLIENT` outside a request."""
    return _client_key.get()


@contextmanager
def as_client(key: str) -> Iterator[None]:
    """Serve what runs inside the block as this client."""
    token = _client_key.set(key)
    try:
        yield
    finally:
        _client_key.reset(token)


def _address(text: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not text or len(text) > MAX_ADDRESS_CHARACTERS:
        return None
    try:
        return ipaddress.ip_address(text.strip())
    except ValueError:
        return None


def _forwarded(scope: Scope) -> list[str]:
    """Every entry of `X-Forwarded-For`, in order, over all the header's lines. Bounded before it is split."""
    lines = [value for name, value in scope.get("headers", ()) if name == FORWARDED_HEADER]
    joined = b",".join(lines)[:MAX_FORWARDED_BYTES].decode("latin-1")
    return [entry.strip() for entry in joined.split(",")]


def _visitor(scope: Scope, trusted_proxy_hops: int) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """The peer, or with N trusted proxies the N-th forwarded entry from the right: the address our outermost
    proxy saw. What a caller wrote into the header itself stands left of that and is never read. A header
    with fewer entries, or an entry that is not an address, leaves the peer: never a guess."""
    client = scope.get("client")
    peer = _address(client[0] if client else None)
    if trusted_proxy_hops == 0 or peer is None:
        return peer
    entries = _forwarded(scope)
    if len(entries) < trusted_proxy_hops:
        return peer
    return _address(entries[-trusted_proxy_hops]) or peer


def client_key_of(scope: Scope, *, trusted_proxy_hops: int = 0) -> str:
    """The key that stands for the visitor: its address, an IPv6 address by its /64 (one network hands its
    hosts many addresses). `X-Forwarded-For` is believed only as far as `TTA_TRUSTED_PROXY_HOPS` says."""
    address = _visitor(scope, trusted_proxy_hops)
    if address is None:
        return UNKNOWN_CLIENT
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return str(address.ipv4_mapped)
    if isinstance(address, ipaddress.IPv6Address):
        return str(ipaddress.IPv6Network((address, IPV6_VISITOR_PREFIX), strict=False))
    return str(address)


class ClientKeyMiddleware:
    """Puts the client key of each request into a context variable, where the service's limits read it:
    the REST routes, the MCP tools and the pages are all counted per visitor without passing it along."""

    def __init__(self, app: ASGIApp, *, trusted_proxy_hops: int = 0) -> None:
        self._app = app
        self._hops = trusted_proxy_hops

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in KEYED_SCOPES:
            await self._app(scope, receive, send)
            return
        with as_client(client_key_of(scope, trusted_proxy_hops=self._hops)):
            await self._app(scope, receive, send)


class CallLimits:
    """What the gateway service asks before a call that reaches the supplier, the model or the audit trail.

    One window for the caller and one ceiling per kind of call for all callers together. A token from the
    environment is one caller, counted by its identity. Where the tokens are the public demonstration tokens
    (`per_visitor`), anyone may send any of them, so the caller is the visitor's address alone, with one
    window per kind of call (`VISITOR_WINDOWS`): one address with every token cannot reach a ceiling.
    """

    def __init__(
        self,
        per_caller: RateLimit,
        *,
        per_visitor: bool,
        visitor_windows: Mapping[CallKind, RateLimit] | None = None,
        ceilings: Mapping[CallKind, int] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._per_caller = per_caller
        self._per_visitor = per_visitor
        self._visitor_windows = dict(visitor_windows if visitor_windows is not None else {
            kind: RateLimit(calls=calls, window_seconds=SECONDS_PER_MINUTE) for kind, calls in VISITOR_WINDOWS.items()
        })
        self._ceilings = dict(GLOBAL_CEILINGS if ceilings is None else ceilings)
        self._limiter = RateLimiter(per_caller, monotonic=monotonic)

    def check(self, identity: Identity, kind: CallKind) -> None:
        """Count one call, or raise `RateLimited` (with the seconds to wait) and count it nowhere."""
        ceiling = RateLimit(calls=self._ceilings[kind], window_seconds=SECONDS_PER_MINUTE)
        self._limiter.check_all((
            self._callers_window(identity, kind),
            Counted(f"all {kind.name}", ceiling, CEILING_REACHED.replace("{kind}", kind.value)),
        ))

    def _callers_window(self, identity: Identity, kind: CallKind) -> Counted:
        if not self._per_visitor:
            return Counted(f"caller {identity.id}", self._per_caller)
        refusal = VISITOR_LIMITED.replace("{kind}", kind.value)
        return Counted(f"visitor {kind.name} {current_client_key()}", self._visitor_windows[kind], refusal)


def call_limits(per_visitor: bool, rate_limit: RateLimit | None = None) -> CallLimits:
    """The limits of the gateway. `rate_limit`, for a test, replaces the window of one caller for every kind
    of call: of a token from the environment, or of one visitor of the demonstration tokens."""
    if rate_limit is None:
        return CallLimits(RateLimit(), per_visitor=per_visitor)
    return CallLimits(rate_limit, per_visitor=per_visitor, visitor_windows=dict.fromkeys(CallKind, rate_limit))


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
            # `str.isdigit` is also true for digits `int` cannot read, such as the superscript two.
            return int(text) if text.isascii() and text.isdigit() else NOT_A_LENGTH
    return None
