"""Limits for a room on one Wi-Fi (task FIX-11): who the visitor is, the windows, the new books.

Scores on the 30% "working end-to-end demo": every peer reviewer on the venue Wi-Fi reaches the deployed demo
from one public address, and with the windows of FIX-10 keyed on that address the whole room shared one
visitor's five model calls a minute. On the pages a visitor is now a browser (its own-book cookie), with the
same windows; above them one address may make at most a quarter of each ceiling (A3 F3) and open at most 400
new books in 10 minutes, so rotating cookies cannot take the whole app or push the other visitors' books out.
REST and MCP keep counting by address. The same through the real pages: `test_room_pages.py`.

The review day (decision B55, FIX-A1): a room of reviewers behind the venue's one address opens a book on every
page load and customer switch, so the new books are 400 in 10 minutes (were 30); and REST and MCP callers behind
one address share 60 lookups a minute (were 20), which is the address's whole cap for lookups.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tta.api import app as gateway_app
from tta.api.limits import (
    ADDRESS_CAPS,
    BOOK_COOKIE_NAMES,
    GLOBAL_CEILINGS,
    MCP_ROOT,
    VISITOR_WINDOWS,
    CallKind,
    CallLimits,
    ClientKeyMiddleware,
    RateLimit,
    as_client,
    browser_key_of,
    current_browser_key,
    current_client_key,
)
from tta.api.sandbox import MAX_NEW_BOOKS_PER_ADDRESS, MAX_SANDBOXES, NEW_BOOKS_WINDOW_SECONDS, Sandboxes
from tta.contracts.common import Identity
from tta.contracts.errors import RateLimited
from tta.ui import security

# Public addresses: the documentation ranges of RFC 5737 would not do, Python counts them as private.
ROOM, ELSEWHERE = "93.184.216.40", "93.184.216.41"
BOOK = security.new_token  # a key in the form the pages make
ROOM_SIZE = 12
SCENARIOS_PER_REVIEWER_PER_MINUTE = 5
# What each refusal says, by the window that was full.
FROM_THIS_BROWSER = "from this browser:"
FROM_ONE_ADDRESS = "from one address:"
FOR_THE_WHOLE_ADDRESS = "from one address for all its browsers and callers together:"
FOR_THE_WHOLE_APP = "from all callers together"
TOO_MANY_BOOKS = "Too many new demo order books from one address"


class FakeTime:
    def __init__(self) -> None:
        self.seconds = 1000.0

    def __call__(self) -> float:
        return self.seconds


def _scope(path: str, *cookies: bytes, client: Any = (ROOM, 4711)) -> dict[str, Any]:
    return {"type": "http", "path": path, "client": client, "headers": [(b"cookie", value) for value in cookies]}


# --- who is the visitor ---------------------------------------------------------------------------------


def test_the_limits_read_the_cookie_the_pages_write_and_know_the_mcp_path() -> None:
    assert BOOK_COOKIE_NAMES == (security.HOST_PREFIX + security.BOOK_COOKIE, security.BOOK_COOKIE)
    assert MCP_ROOT == gateway_app.MCP_PATH


@pytest.mark.parametrize("path", ["/", "/run", "/approvals", "/approvals/apr_1/decision", "/start-again", "/v1x"])
@pytest.mark.parametrize("name", BOOK_COOKIE_NAMES)
def test_on_a_page_the_browser_is_its_own_book_cookie(path: str, name: str) -> None:
    key = BOOK()

    assert browser_key_of(_scope(path, f"tta_csrf={BOOK()}; {name}={key}".encode())) == key


@pytest.mark.parametrize("path", ["/v1", "/v1/offers", "/v1/agent/run", "/mcp", "/mcp/", "/mcp/messages"])
def test_rest_and_mcp_are_never_keyed_on_the_cookie(path: str) -> None:
    assert browser_key_of(_scope(path, f"tta_book={BOOK()}".encode())) is None


@pytest.mark.parametrize(
    "cookie",
    [
        b"",
        b"tta_csrf=" + BOOK().encode(),  # another cookie of the pages
        b"tta_book=short",
        b"tta_book=" + b"!" * 43,
        b"tta_book=" + BOOK().encode() + b"x",  # 44 characters
        b"tta_book=" + b"a" * 9000,
        b"\xff\xfe=\xff",
    ],
)
def test_a_cookie_the_pages_did_not_make_is_no_browser(cookie: bytes) -> None:
    assert browser_key_of(_scope("/run", cookie)) is None


def test_with_both_names_the_https_cookie_is_the_browser() -> None:
    secure, plain = BOOK(), BOOK()

    assert browser_key_of(_scope("/run", f"tta_book={plain}; __Host-tta_book={secure}".encode())) == secure


def test_cookies_sent_on_several_header_lines_are_read_together() -> None:
    key = BOOK()

    assert browser_key_of(_scope("/run", f"tta_csrf={BOOK()}".encode(), f"tta_book={key}".encode())) == key


def test_the_middleware_sets_the_address_and_the_browser_for_the_request_and_takes_both_back() -> None:
    seen: list[tuple[str, str | None]] = []
    key = BOOK()

    async def application(scope: Any, receive: Any, send: Any) -> None:
        seen.append((current_client_key(), current_browser_key()))

    async def run() -> None:
        middleware = ClientKeyMiddleware(application)
        await middleware(_scope("/run", f"tta_book={key}".encode()), None, None)
        await middleware(_scope("/v1/offers", f"tta_book={key}".encode()), None, None)
        await middleware(_scope("/run"), None, None)
        seen.append((current_client_key(), current_browser_key()))

    asyncio.run(run())

    assert seen == [(ROOM, key), (ROOM, None), (ROOM, None), ("unknown", None)]


# --- a window per browser, a cap per address, a ceiling for everybody ------------------------------------


def test_one_address_may_make_60_of_each_kind_of_call_a_minute_a_quarter_of_each_ceiling() -> None:
    assert ADDRESS_CAPS == {CallKind.LOOKUP: 60, CallKind.ORDER: 60, CallKind.MODEL: 60}
    for kind, cap in ADDRESS_CAPS.items():
        assert cap * 4 == GLOBAL_CEILINGS[kind], kind
        assert VISITOR_WINDOWS[kind] <= cap, kind
    # Orders and model calls: one visitor stays under its address's cap. Lookups since B55: one visitor (on REST
    # and MCP, every caller behind one address together) may use the address's whole cap.
    assert VISITOR_WINDOWS[CallKind.ORDER] < ADDRESS_CAPS[CallKind.ORDER]
    assert VISITOR_WINDOWS[CallKind.MODEL] < ADDRESS_CAPS[CallKind.MODEL]
    assert VISITOR_WINDOWS[CallKind.LOOKUP] == ADDRESS_CAPS[CallKind.LOOKUP] == 60
    # A room of a dozen reviewers on one Wi-Fi: each can run five scenarios with the agent in a minute.
    assert ADDRESS_CAPS[CallKind.MODEL] >= ROOM_SIZE * SCENARIOS_PER_REVIEWER_PER_MINUTE


def test_browsers_behind_one_address_each_have_their_own_window(agent_ward: Identity) -> None:
    limits = CallLimits(RateLimit(), per_visitor=True, monotonic=FakeTime())
    one, other = BOOK(), BOOK()

    with as_client(ROOM, browser=one):
        for _ in range(VISITOR_WINDOWS[CallKind.MODEL]):
            limits.check(agent_ward, CallKind.MODEL)
        with pytest.raises(RateLimited) as refused:
            limits.check(agent_ward, CallKind.MODEL)
    with as_client(ROOM, browser=other):
        limits.check(agent_ward, CallKind.MODEL)  # the same address, another browser: its own window

    window = VISITOR_WINDOWS[CallKind.MODEL]
    assert FROM_THIS_BROWSER in refused.value.detail and f"at most {window} in 60 seconds" in refused.value.detail
    assert one not in refused.value.detail and ROOM not in refused.value.detail


@pytest.mark.parametrize("kind", list(CallKind))
def test_cookie_rotation_from_one_address_cannot_pass_the_address_cap(agent_ward: Identity, kind: CallKind) -> None:
    limits = CallLimits(RateLimit(), per_visitor=True, monotonic=FakeTime())
    accepted = 0

    with pytest.raises(RateLimited) as refused:
        while True:  # a new cookie for every call
            with as_client(ROOM, browser=BOOK()):
                limits.check(agent_ward, kind)
            accepted += 1
    with as_client(ROOM), pytest.raises(RateLimited) as without_cookie:
        limits.check(agent_ward, kind)
    with as_client(ELSEWHERE, browser=BOOK()):
        limits.check(agent_ward, kind)  # another address is still served
    with as_client(ELSEWHERE):
        limits.check(agent_ward, kind)

    assert accepted == ADDRESS_CAPS[kind] < GLOBAL_CEILINGS[kind]
    for detail in (refused.value.detail, without_cookie.value.detail):
        assert FOR_THE_WHOLE_ADDRESS in detail and f"at most {ADDRESS_CAPS[kind]} in 60 seconds" in detail
    assert refused.value.extensions["retry_after_seconds"] == 60


def test_without_a_cookie_a_visitor_is_its_address_and_counts_in_the_address_cap(agent_ward: Identity) -> None:
    limits = CallLimits(RateLimit(), per_visitor=True, monotonic=FakeTime())
    window, cap = VISITOR_WINDOWS[CallKind.LOOKUP], ADDRESS_CAPS[CallKind.LOOKUP]

    with as_client(ROOM):
        for _ in range(window):
            limits.check(agent_ward, CallKind.LOOKUP)
        with pytest.raises(RateLimited) as refused:
            limits.check(agent_ward, CallKind.LOOKUP)
    browsers = [BOOK() for _ in range((cap - window) // window + 1)]
    accepted = 0
    with pytest.raises(RateLimited) as capped:
        for browser in browsers:
            for _ in range(window):
                with as_client(ROOM, browser=browser):
                    limits.check(agent_ward, CallKind.LOOKUP)
                accepted += 1

    assert FROM_ONE_ADDRESS in refused.value.detail and f"at most {window} in 60 seconds" in refused.value.detail
    assert accepted == cap - window  # the calls without a cookie took their part of the address's cap
    assert FOR_THE_WHOLE_ADDRESS in capped.value.detail


def test_the_ceiling_still_holds_for_all_addresses_together(agent_ward: Identity) -> None:
    limits = CallLimits(RateLimit(), per_visitor=True, monotonic=FakeTime())
    for address in (ROOM, ELSEWHERE, "93.184.216.43", "93.184.216.44"):  # four addresses at their cap
        for _ in range(ADDRESS_CAPS[CallKind.MODEL]):
            with as_client(address, browser=BOOK()):
                limits.check(agent_ward, CallKind.MODEL)

    with as_client("93.184.216.42", browser=BOOK()), pytest.raises(RateLimited) as refused:
        limits.check(agent_ward, CallKind.MODEL)

    ceiling = GLOBAL_CEILINGS[CallKind.MODEL]
    assert FOR_THE_WHOLE_APP in refused.value.detail and f"at most {ceiling} " in refused.value.detail


def test_a_token_from_the_environment_is_counted_by_identity_whatever_cookie_it_sends(agent_hotel: Identity) -> None:
    limits = CallLimits(RateLimit(calls=2), per_visitor=False, monotonic=FakeTime())
    with as_client(ROOM, browser=BOOK()):
        limits.check(agent_hotel, CallKind.LOOKUP)
    with as_client(ELSEWHERE, browser=BOOK()):
        limits.check(agent_hotel, CallKind.LOOKUP)

    with as_client(ROOM, browser=BOOK()), pytest.raises(RateLimited) as refused:
        limits.check(agent_hotel, CallKind.LOOKUP)

    assert "for one caller" in refused.value.detail


# --- new books per address ------------------------------------------------------------------------------


def _books(time: FakeTime, capacity: int = MAX_SANDBOXES) -> tuple[Sandboxes, list[Any]]:
    built: list[Any] = []

    class Book:
        def __init__(self) -> None:
            self.closed = False
            built.append(self)

        def close(self) -> None:
            self.closed = True

    return Sandboxes(Book, capacity=capacity, monotonic=time), built  # type: ignore[arg-type]


def test_one_address_opens_at_most_400_new_books_in_10_minutes() -> None:
    # 8 reviewers behind the venue's address clicking through the 4 customers reached the 30 of before (C2-1).
    assert (MAX_NEW_BOOKS_PER_ADDRESS, NEW_BOOKS_WINDOW_SECONDS) == (400, 10 * 60)
    time = FakeTime()
    sandboxes, built = _books(time)
    keys = [BOOK() for _ in range(MAX_NEW_BOOKS_PER_ADDRESS)]
    with as_client(ROOM):
        opened = [sandboxes.open(key) for key in keys]
        with pytest.raises(RateLimited) as refused:
            sandboxes.open(BOOK())  # a rotated cookie

        assert sandboxes.open(keys[0]) is opened[0]  # a book that exists is no new book
    with as_client(ELSEWHERE):
        sandboxes.open(BOOK())  # another address is not held back

    assert len(built) == len(sandboxes) == MAX_NEW_BOOKS_PER_ADDRESS + 1
    assert not any(book.closed for book in built)
    detail = refused.value.detail
    assert TOO_MANY_BOOKS in detail and "at most 400 in 10 minutes" in detail and ROOM not in detail
    assert refused.value.extensions["retry_after_seconds"] == NEW_BOOKS_WINDOW_SECONDS


def test_the_new_books_of_one_address_in_one_window_leave_room_for_the_books_of_others() -> None:
    assert 2 * MAX_NEW_BOOKS_PER_ADDRESS <= MAX_SANDBOXES  # two full rooms in one window push nobody out


def test_an_address_opens_new_books_again_once_its_10_minutes_have_passed() -> None:
    time = FakeTime()
    sandboxes, _ = _books(time)
    with as_client(ROOM):
        for _ in range(MAX_NEW_BOOKS_PER_ADDRESS):
            sandboxes.open(BOOK())
        time.seconds += NEW_BOOKS_WINDOW_SECONDS - 1
        with pytest.raises(RateLimited) as refused:
            sandboxes.open(BOOK())
        time.seconds += 1
        sandboxes.open(BOOK())

    assert refused.value.extensions["retry_after_seconds"] == 1


def test_one_address_cannot_push_the_other_visitors_books_out() -> None:
    time = FakeTime()
    sandboxes, built = _books(time, capacity=MAX_NEW_BOOKS_PER_ADDRESS + 5)
    others = [BOOK() for _ in range(5)]
    with as_client(ELSEWHERE):
        for key in others:
            sandboxes.open(key)
    time.seconds += 1

    refused = 0
    with as_client(ROOM):
        for _ in range(MAX_NEW_BOOKS_PER_ADDRESS * 2):
            try:
                sandboxes.open(BOOK())
            except RateLimited:
                refused += 1

    assert refused == MAX_NEW_BOOKS_PER_ADDRESS
    assert all(sandboxes.find(key) is not None for key in others)
    assert len(built) == MAX_NEW_BOOKS_PER_ADDRESS + len(others)
