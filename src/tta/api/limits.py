"""Limits on what one caller can send and how often (tasks T09, FIX-8, FIX-10 and FIX-11).

Scores on the 30% "working end-to-end demo" (the public demo keeps working under a room full of people) and
on the 15% "credible path toward production": the audit trail is append-only, the supplier's API has a call
budget and the model is paid per call, so no caller may fill the one or spend the others, and one visitor of
the demo may not lock out the rest.

Four layers, each a sliding window of one minute, in memory, for one process:
    one caller       a token from the environment; where the tokens are the public demonstration tokens, one
                     visitor, with a window per kind of call (`VISITOR_WINDOWS`), each well under its ceiling.
                     On the pages a visitor is a browser, known by the own-book cookie the pages give it; a
                     browser without one, and every REST and MCP call, is its address, whichever token it sends
    one address      the demonstration only: every browser and caller behind one address together, at most
                     a quarter of each ceiling (`ADDRESS_CAPS`). A room on one Wi-Fi shares one public address,
                     and a new cookie buys a new browser window, so this is what holds rotating cookies back
    all callers      a ceiling per kind of call (`GLOBAL_CEILINGS`): it takes four addresses at their cap to fill
                     one, so one or two callers cannot lock the demo for everybody (A3 F3)
    the supplier     live looks at price and availability, overall and per address (used by the fall-back)

The values are ours and illustrative, like the buyer profiles: the mock publishes no rate limit
(AIMO/docs/API.md section 2).
"""

from __future__ import annotations

import ipaddress
import math
import re
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from starlette.requests import cookie_parser
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from tta.api.errors import BodyTooLarge, body_too_large_problem, problem_response, status_problem
from tta.api.headers import is_api_path
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
# One visitor of the public demonstration, whichever public token it sends (task FIX-10): a browser of the pages,
# or an address. 15 readings a minute serve fast typing (A5 #3: the sixth was refused at 5) and stay under the
# offer window, so an example whose agent run is held back still makes its offer from its typed request.
MAX_LOOKUPS_PER_VISITOR_PER_MINUTE = 20
MAX_ORDERS_PER_VISITOR_PER_MINUTE = 20
MAX_MODEL_CALLS_PER_VISITOR_PER_MINUTE = 15
# Every browser and caller behind one address together (task FIX-11): a dozen reviewers on one Wi-Fi each run
# about five scenarios a minute, and rotating cookies buys no more.
MAX_LOOKUPS_PER_ADDRESS_PER_MINUTE = 60
MAX_ORDERS_PER_ADDRESS_PER_MINUTE = 60
MAX_MODEL_CALLS_PER_ADDRESS_PER_MINUTE = 60
# All callers together: four addresses at their cap, so one or two cannot lock everybody out (A3 F3). An offer
# takes about 17 ms of one core in replay (measured offline, 14 Nov), so a full ceiling is about 7% of the core.
ADDRESSES_THAT_FILL_A_CEILING = 4
MAX_OFFERS_AND_SUBSTITUTES_PER_MINUTE = ADDRESSES_THAT_FILL_A_CEILING * MAX_LOOKUPS_PER_ADDRESS_PER_MINUTE
MAX_ORDERS_AND_DECISIONS_PER_MINUTE = ADDRESSES_THAT_FILL_A_CEILING * MAX_ORDERS_PER_ADDRESS_PER_MINUTE
MAX_MODEL_CALLS_PER_MINUTE = ADDRESSES_THAT_FILL_A_CEILING * MAX_MODEL_CALLS_PER_ADDRESS_PER_MINUTE
# One look is a price call and an availability call. At this rate the default call budget of 150 lasts
# twelve minutes of a full room; above it the fall-back answers from the capture and says so.
MAX_LIVE_LOOKS_PER_MINUTE = 6
MAX_LIVE_LOOKS_PER_VISITOR_PER_MINUTE = 2

RATE_LIMITED = (
    "Too many requests that reach the supplier or write to the audit trail: at most {calls} in "
    "{window} seconds for one caller. Try again in {wait} seconds."
)
BROWSER_LIMITED = (
    "Too many {kind} from this browser: at most {calls} in {window} seconds. Try again in {wait} seconds."
)
VISITOR_LIMITED = (
    "Too many {kind} from one address: at most {calls} in {window} seconds. Try again in {wait} seconds."
)
ADDRESS_LIMITED = (
    "Too many {kind} from one address for all its browsers and callers together: at most {calls} in "
    "{window} seconds. Try again in {wait} seconds."
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
# The pages' own-book cookie: `tta.ui.security.BOOK_COOKIE`, with its `HOST_PREFIX` over HTTPS. The HTTPS name
# is read first. The key is the pages' form of `secrets.token_urlsafe(32)`; anything else is no browser.
BOOK_COOKIE_NAMES = ("__Host-tta_book", "tta_book")
BOOK_KEY = re.compile(r"^[A-Za-z0-9_-]{43}$")
COOKIE_HEADER = b"cookie"
MAX_COOKIE_BYTES = 8192  # of the Cookie header, over all its lines: more is not read
MCP_ROOT = "/mcp"  # `tta.api.app.MCP_PATH`, where the MCP surface is mounted


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
ADDRESS_CAPS: Mapping[CallKind, int] = MappingProxyType({
    CallKind.LOOKUP: MAX_LOOKUPS_PER_ADDRESS_PER_MINUTE,
    CallKind.ORDER: MAX_ORDERS_PER_ADDRESS_PER_MINUTE,
    CallKind.MODEL: MAX_MODEL_CALLS_PER_ADDRESS_PER_MINUTE,
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
_browser_key: ContextVar[str | None] = ContextVar("tta_browser_key", default=None)


def current_client_key() -> str:
    """The client key (the address) of the request being served; `UNKNOWN_CLIENT` outside a request."""
    return _client_key.get()


def current_browser_key() -> str | None:
    """The own-book cookie of the page request being served; `None` for REST, MCP and a browser without one."""
    return _browser_key.get()


@contextmanager
def as_client(key: str, *, browser: str | None = None) -> Iterator[None]:
    """Serve what runs inside the block as this client (an address) and, on a page, this browser."""
    token, browser_token = _client_key.set(key), _browser_key.set(browser)
    try:
        yield
    finally:
        _browser_key.reset(browser_token)
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


def is_page_path(path: str) -> bool:
    """True for a path the pages serve: anything outside the API (`/v1`) and the MCP surface (`/mcp`)."""
    return not is_api_path(path) and path != MCP_ROOT and not path.startswith(MCP_ROOT + "/")


def browser_key_of(scope: Scope) -> str | None:
    """The browser of a page request: the key of its own-book cookie as the pages make it, else `None`. A REST
    or MCP request is never a browser, whatever cookie it carries. Bounded before it is parsed."""
    if not is_page_path(scope.get("path", "")):
        return None
    lines = [value for name, value in scope.get("headers", ()) if name == COOKIE_HEADER]
    cookies = cookie_parser(b"; ".join(lines)[:MAX_COOKIE_BYTES].decode("latin-1"))
    return next((cookies[name] for name in BOOK_COOKIE_NAMES if BOOK_KEY.fullmatch(cookies.get(name, ""))), None)


class ClientKeyMiddleware:
    """Puts the client key of each request, and on a page its browser, into context variables, where the
    service's limits read them: the REST routes, the MCP tools and the pages are all counted per visitor
    without passing it along."""

    def __init__(self, app: ASGIApp, *, trusted_proxy_hops: int = 0) -> None:
        self._app = app
        self._hops = trusted_proxy_hops

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in KEYED_SCOPES:
            await self._app(scope, receive, send)
            return
        with as_client(client_key_of(scope, trusted_proxy_hops=self._hops), browser=browser_key_of(scope)):
            await self._app(scope, receive, send)


class CallLimits:
    """What the gateway service asks before a call that reaches the supplier, the model or the audit trail.

    One window for the caller and one ceiling per kind of call for all callers together. A token from the
    environment is one caller, counted by its identity. Where the tokens are the public demonstration tokens
    (`per_visitor`), anyone may send any of them, so the caller is the visitor: on the pages its browser, else
    its address alone, with one window per kind of call (`VISITOR_WINDOWS`). Every call of the demonstration
    is also counted for its address (`ADDRESS_CAPS`): one address with every token and any number of cookies
    cannot reach a ceiling.
    """

    def __init__(
        self,
        per_caller: RateLimit,
        *,
        per_visitor: bool,
        visitor_windows: Mapping[CallKind, RateLimit] | None = None,
        address_caps: Mapping[CallKind, int] | None = None,
        ceilings: Mapping[CallKind, int] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._per_caller = per_caller
        self._per_visitor = per_visitor
        self._visitor_windows = dict(visitor_windows if visitor_windows is not None else {
            kind: RateLimit(calls=calls, window_seconds=SECONDS_PER_MINUTE) for kind, calls in VISITOR_WINDOWS.items()
        })
        self._address_caps = dict(ADDRESS_CAPS if address_caps is None else address_caps)
        self._ceilings = dict(GLOBAL_CEILINGS if ceilings is None else ceilings)
        self._limiter = RateLimiter(per_caller, monotonic=monotonic)

    def check(self, identity: Identity, kind: CallKind) -> None:
        """Count one call, or raise `RateLimited` (with the seconds to wait) and count it nowhere. The refusal
        says which window was full: the browser's or address's own, the address's cap, or the whole app's."""
        ceiling = RateLimit(calls=self._ceilings[kind], window_seconds=SECONDS_PER_MINUTE)
        self._limiter.check_all((
            *self._callers_windows(identity, kind),
            Counted(f"all {kind.name}", ceiling, _naming(CEILING_REACHED, kind)),
        ))

    def _callers_windows(self, identity: Identity, kind: CallKind) -> tuple[Counted, ...]:
        """The caller's own window first: when two are full alike, the refusal names the caller's own."""
        if not self._per_visitor:
            return (Counted(f"caller {identity.id}", self._per_caller),)
        address, browser = current_client_key(), current_browser_key()
        cap = RateLimit(calls=self._address_caps[kind], window_seconds=SECONDS_PER_MINUTE)
        of_address = Counted(f"address {kind.name} {address}", cap, _naming(ADDRESS_LIMITED, kind))
        if browser is None:
            own = Counted(f"visitor {kind.name} {address}", self._visitor_windows[kind], _naming(VISITOR_LIMITED, kind))
        else:
            own = Counted(f"browser {kind.name} {browser}", self._visitor_windows[kind], _naming(BROWSER_LIMITED, kind))
        return own, of_address


def _naming(refusal: str, kind: CallKind) -> str:
    """The refusal with the kind of call written in; the numbers are written in when it is raised."""
    return refusal.replace("{kind}", kind.value)


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
