"""Limits for a room on one Wi-Fi, through the real pages (task FIX-11).

Scores on the 30% "working end-to-end demo": twelve peer reviewers on the venue Wi-Fi, one public address, each
click scenario 2 within a minute, and the buyer agent runs for every one of them. Above the windows of each
browser the address has its cap, and opens at most 30 new books in 10 minutes. REST stays counted by address.
The windows themselves are tested in `test_room_limits.py`.
"""

from __future__ import annotations

import html
import re
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.limits import ADDRESS_CAPS, BOOK_COOKIE_NAMES, VISITOR_WINDOWS, CallKind, as_client
from tta.api.sandbox import MAX_NEW_BOOKS_PER_ADDRESS
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.agent import AgentRun, AgentStep
from tta.contracts.common import Identity
from tta.contracts.ports import GatewayService
from tta.contracts.request import PurchaseRequest
from tta.ui import security

Auth = Callable[..., dict[str, str]]
Problem = Callable[..., dict[str, Any]]
# Public addresses: the documentation ranges of RFC 5737 would not do, Python counts them as private.
ROOM, ELSEWHERE = "93.184.216.40", "93.184.216.41"
ROOM_SIZE = 12
CSRF_FIELD = re.compile(r'name="csrf" value="([A-Za-z0-9_-]+)"')
RUN_KEY_FIELD = re.compile(r'name="run_key" value="([A-Za-z0-9_-]+)"')
# What each refusal says, by the window that was full.
FROM_THIS_BROWSER = "from this browser:"
FROM_ONE_ADDRESS = "from one address:"
FOR_THE_WHOLE_ADDRESS = "from one address for all its browsers and callers together:"
TOO_MANY_BOOKS = "Too many new demo order books from one address"
AGENT_COULD_NOT_RUN = "The buyer agent could not run"


class ScenarioTwoRunner:
    """Runs scenario 2 the way the buyer agent does, only through the gateway's own functions, with no model."""

    def __init__(self, request: PurchaseRequest) -> None:
        self._request = request
        self.runs = 0

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        self.runs += 1
        offer = tools.create_offer(identity, self._request)
        order = tools.place_order(identity, offer.offer_id, offer.options[0].option_id, f"room-{self.runs}")
        steps = (
            AgentStep(index=1, tool="create_offer", ok=True, result={"offer_id": offer.offer_id}),
            AgentStep(index=2, tool="place_order", ok=True, sentence=order.status_sentence),
        )
        return AgentRun(
            text=text, model="fake-model-1", recorded=True, steps=steps, offer_id=offer.offer_id,
            order_id=order.order_id, order_status=order.status, report=order.status_sentence,
        )


@dataclass(frozen=True)
class Room:
    app: FastAPI
    parts: Parts
    runner: ScenarioTwoRunner

    def browser(self, address: str = ROOM, base_url: str = "http://testserver") -> TestClient:
        return TestClient(self.app, client=(address, 50000), base_url=base_url)


@pytest.fixture
def ward_request(scenario_2: dict[str, Any]) -> PurchaseRequest:
    return PurchaseRequest.model_validate(scenario_2)


@pytest.fixture
def room(
    settings: Settings, catalog: ProductCatalog, ward_request: PurchaseRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Room]:
    """The gateway with the real pages, the default limits and a buyer agent that runs scenario 2."""
    monkeypatch.delitem(sys.modules, "tta.ui.routes")  # the other tests of this folder see the pages as absent
    runner = ScenarioTwoRunner(ward_request)
    parts = build_parts(settings, catalog=catalog, agent_runner=runner)
    app = create_app(settings, parts=parts)
    with TestClient(app):
        assert app.state.surfaces["pages"] is True
        yield Room(app=app, parts=parts, runner=runner)


def _book_key(browser: TestClient) -> str:
    return next(browser.cookies[name] for name in BOOK_COOKIE_NAMES if browser.cookies.get(name))


def _run_scenario_2(browser: TestClient, *, without_book_cookie: bool = False) -> Any:
    """Open the first page and click scenario 2, as a reviewer does."""
    page = browser.get("/")
    assert page.status_code == 200, page.text
    form = {
        "csrf": CSRF_FIELD.search(page.text).group(1),  # type: ignore[union-attr]
        "run_key": RUN_KEY_FIELD.search(page.text).group(1),  # type: ignore[union-attr]
        "example": "scenario-2",
    }
    if without_book_cookie:
        for name in BOOK_COOKIE_NAMES:
            browser.cookies.delete(name)
    return browser.post("/run", data=form)


def _text(response: Any) -> str:
    return html.unescape(response.text)


def test_twelve_browsers_behind_one_address_run_scenario_2_within_a_minute_and_the_61st_lookup_is_refused(
    room: Room, agent_ward: Identity, ward_request: PurchaseRequest, auth: Auth, scenario_2: dict[str, Any],
    assert_problem: Problem,
) -> None:
    browsers = [room.browser() for _ in range(ROOM_SIZE)]

    pages = [_run_scenario_2(browser) for browser in browsers]

    assert [page.status_code for page in pages] == [200] * ROOM_SIZE
    assert room.runner.runs == ROOM_SIZE  # the buyer agent ran for every one of them
    assert not any(AGENT_COULD_NOT_RUN in _text(page) for page in pages)
    books = [room.parts.sandboxes.find(_book_key(browser)) for browser in browsers]
    assert len({id(book) for book in books}) == ROOM_SIZE
    assert all(len(book.service.list_orders(agent_ward)) == 1 for book in books)

    # One lookup per run so far. The same browsers search more, as their pages do, up to the address's 60.
    cap = ADDRESS_CAPS[CallKind.LOOKUP]
    for browser, book in zip(browsers, books, strict=True):
        with as_client(ROOM, browser=_book_key(browser)):
            for _ in range((cap - ROOM_SIZE) // ROOM_SIZE):
                book.service.create_offer(agent_ward, ward_request)

    newcomer = _run_scenario_2(room.browser())  # its own browser window is empty: the address's is full
    by_rest = room.browser().post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))
    elsewhere = _run_scenario_2(room.browser(ELSEWHERE))

    assert newcomer.status_code == 429
    assert FOR_THE_WHOLE_ADDRESS in _text(newcomer) and f"at most {cap} in 60 seconds" in _text(newcomer)
    assert FOR_THE_WHOLE_ADDRESS in assert_problem(by_rest, "rate-limited", 429)["detail"]
    assert elsewhere.status_code == 200 and AGENT_COULD_NOT_RUN not in _text(elsewhere)


def test_a_browser_over_https_has_its_own_model_window_and_its_neighbour_keeps_its_own(room: Room) -> None:
    one, neighbour = room.browser(base_url="https://testserver"), room.browser(base_url="https://testserver")
    window = VISITOR_WINDOWS[CallKind.MODEL]

    pages = [_run_scenario_2(one) for _ in range(window + 1)]
    served = _run_scenario_2(neighbour)

    assert one.cookies.get(security.HOST_PREFIX + security.BOOK_COOKIE)
    assert [AGENT_COULD_NOT_RUN in _text(page) for page in pages] == [False] * window + [True]
    assert FROM_THIS_BROWSER in _text(pages[-1])  # the example still ran, from its typed request
    assert pages[-1].status_code == 200
    assert AGENT_COULD_NOT_RUN not in _text(served) and room.runner.runs == window + 1


def test_a_browser_with_no_book_cookie_is_counted_by_its_address_as_before(room: Room) -> None:
    browser = room.browser()
    window = VISITOR_WINDOWS[CallKind.MODEL]

    pages = [_run_scenario_2(browser, without_book_cookie=True) for _ in range(window + 1)]
    cookied = _run_scenario_2(room.browser())  # a browser with its cookie still has its own window

    assert [AGENT_COULD_NOT_RUN in _text(page) for page in pages] == [False] * window + [True]
    refused = _text(pages[-1])
    assert FROM_ONE_ADDRESS in refused and FOR_THE_WHOLE_ADDRESS not in refused
    assert AGENT_COULD_NOT_RUN not in _text(cookied) and room.runner.runs == window + 1


def test_rest_is_counted_by_address_even_with_the_pages_cookie(
    room: Room, auth: Auth, scenario_2: dict[str, Any], assert_problem: Problem
) -> None:
    window = VISITOR_WINDOWS[CallKind.LOOKUP]

    def offer() -> Any:
        rotating = room.browser()
        rotating.cookies.set(security.BOOK_COOKIE, security.new_token())
        return rotating.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))

    statuses = [offer().status_code for _ in range(window)]
    refused = offer()

    assert statuses == [201] * window
    detail = assert_problem(refused, "rate-limited", 429)["detail"]
    assert FROM_ONE_ADDRESS in detail and f"at most {window} in 60 seconds" in detail


def test_cookie_rotation_through_the_pages_opens_at_most_30_books_from_one_address(room: Room) -> None:
    pages = [_run_scenario_2(room.browser()) for _ in range(MAX_NEW_BOOKS_PER_ADDRESS + 1)]
    elsewhere = _run_scenario_2(room.browser(ELSEWHERE))

    assert [page.status_code for page in pages] == [200] * MAX_NEW_BOOKS_PER_ADDRESS + [429]
    assert TOO_MANY_BOOKS in _text(pages[-1]) and "at most 30 in 10 minutes" in _text(pages[-1])
    assert elsewhere.status_code == 200
    assert len(room.parts.sandboxes) == MAX_NEW_BOOKS_PER_ADDRESS + 1
