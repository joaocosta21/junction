"""The menu page: choose dishes and servings, enter the kitchen's stock and the date, plan, order (task MENU-1).

The page is mounted here as `tta.ui.routes.create_surface` will mount it once the orchestrator registers it.
Everything runs in the browser session's own order book, as on the request page.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tta.api.limits import RateLimit
from tta.api.sandbox import KITCHEN_IDENTITIES
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import OrderStatus
from tta.ui import menu_page, order_page
from tta.ui.routes import _install_error_pages
from tta.ui.security import BookCookie, SecurityHeaders
from tta.ui.site import Site
from tta.ui.view import words

CSRF_FIELD = re.compile(r'name="csrf" value="([A-Za-z0-9_-]+)"')
ORDER_KEY_FIELD = re.compile(r'name="order_key" value="([A-Za-z0-9_-]+)"')
OFFER_FIELD = re.compile(r'name="offer" value="([A-Za-z0-9_-]+)"')
HOTEL_AGENT = "agent:hotel-kitchen"
FEW_CALLS = 3  # a plan asks for an offer once per round of stand-ins, so the second or third plan is refused
EVENT_FORM = {
    "who": HOTEL_AGENT, "servings__beef_stew": "120", "servings__berry_quark_dessert": "120",
    "stock__butter": "3", "stock__sugar": "2", "needed_by": "2026-11-16", "require_confirmed": "yes",
}


def _client(settings: Settings, catalog: ProductCatalog, calls: int) -> Iterator[TestClient]:
    parts = build_parts(settings, catalog=catalog, rate_limit=RateLimit(calls=calls))
    identities = (*parts.tokens.identities, *KITCHEN_IDENTITIES)
    site = Site(settings=settings, sandboxes=parts.sandboxes, identities=identities)
    app = FastAPI()
    app.add_middleware(BookCookie)
    app.add_middleware(SecurityHeaders)
    _install_error_pages(app, site)
    order_page.add_routes(app, site)
    menu_page.add_routes(app, site)
    with TestClient(app) as client:
        yield client
    parts.close()


@pytest.fixture
def pages(settings: Settings, catalog: ProductCatalog) -> Iterator[TestClient]:
    yield from _client(settings, catalog, calls=1000)


@pytest.fixture
def pages_with_few_calls_a_minute(settings: Settings, catalog: ProductCatalog) -> Iterator[TestClient]:
    yield from _client(settings, catalog, calls=FEW_CALLS)


def _csrf(client: TestClient, path: str = "/menu") -> str:
    page = client.get(path)
    assert page.status_code == 200, page.text
    return CSRF_FIELD.search(page.text).group(1)  # type: ignore[union-attr]


def _plan(client: TestClient, form: dict[str, str] | None = None) -> Any:
    return client.post("/menu/plan", data={**(EVENT_FORM if form is None else form), "csrf": _csrf(client)})


def test_the_form_lists_every_dish_the_stock_and_says_the_recipes_are_illustrative(pages: TestClient) -> None:
    page = pages.get("/menu")

    assert page.status_code == 200
    for name in ("servings__beef_stew", "servings__berry_quark_dessert", "stock__cream", "needed_by"):
        assert f'name="{name}"' in page.text
    assert "illustrative" in page.text and "Hotel kitchen agent" in page.text


def test_the_example_fills_in_the_last_minute_event(pages: TestClient) -> None:
    page = pages.get("/menu?example=event")

    assert 'name="servings__beef_stew" value="120"' in page.text
    assert 'name="needed_by" value="2026-11-16"' in page.text and "checked" in page.text


def test_a_plan_shows_the_stand_in_with_its_reason_the_options_and_an_order_button(pages: TestClient) -> None:
    page = _plan(pages)

    assert page.status_code == 200, page.text
    assert "Stands in" in page.text and "yoghurt (natural)" in page.text
    assert "A thick natural yoghurt gives the same tangy base" in page.text
    assert "order cut-off passed" in page.text  # why quark cannot arrive by Monday
    assert "Needs approval" in page.text or "approval" in page.text.lower()
    assert "P-06" in page.text and 'action="/menu/order"' in page.text
    assert "In stock" in page.text


def test_the_order_button_places_the_order_through_the_normal_flow(pages: TestClient) -> None:
    page = _plan(pages)
    form = {
        "csrf": CSRF_FIELD.search(page.text).group(1), "offer": OFFER_FIELD.search(page.text).group(1),
        "option": "opt_1", "who": HOTEL_AGENT, "order_key": ORDER_KEY_FIELD.search(page.text).group(1),
    }

    answer = pages.post("/menu/order", data=form, follow_redirects=False)
    again = pages.post("/menu/order", data=form, follow_redirects=False)

    assert answer.status_code == 303 and answer.headers["location"].startswith("/orders/")
    assert again.headers["location"] == answer.headers["location"]  # the same key never orders twice
    record = pages.get(answer.headers["location"])
    assert record.status_code == 200 and words(OrderStatus.PENDING_APPROVAL) in record.text


def test_a_form_without_its_token_changes_nothing(pages: TestClient) -> None:
    answer = pages.post("/menu/plan", data={**EVENT_FORM, "csrf": "forged"})

    assert answer.status_code == 403 and "out of date" in answer.text


@pytest.mark.parametrize(
    ("change", "words"),
    [
        ({"servings__beef_stew": "0", "servings__berry_quark_dessert": ""}, "Choose at least one dish"),
        ({"servings__beef_stew": "many"}, "whole number"),
        ({"stock__butter": "-1"}, "stock"),
        ({"needed_by": "Monday"}, "date"),
        ({"who": "agent:nobody"}, "Choose who is asking"),
    ],
    ids=["no dish", "servings not a number", "negative stock", "not a date", "unknown agent"],
)
def test_a_form_that_cannot_be_read_says_why_and_keeps_what_was_typed(
    pages: TestClient, change: dict[str, str], words: str
) -> None:
    page = _plan(pages, {**EVENT_FORM, **change})

    assert page.status_code == 422 and words in page.text
    assert 'name="servings__berry_quark_dessert"' in page.text


def test_five_dishes_plan_in_one_offer(pages: TestClient) -> None:
    """A menu's offer holds the contract's 20 lines, not the five of a demonstration request (L4-2b)."""
    form = {
        "who": HOTEL_AGENT, "servings__lasagne": "50", "servings__oven_pancake": "50",
        "servings__creamy_chicken_pasta": "50", "servings__beef_stew": "50", "servings__salmon_with_rice": "50",
    }

    page = _plan(pages, form)

    assert page.status_code == 200 and "at most 5 lines" not in page.text
    assert 'action="/menu/order"' in page.text


def test_a_refusal_of_the_gateway_is_shown_on_the_page(pages_with_few_calls_a_minute: TestClient) -> None:
    """A plan past the caller's limit per minute is refused: the page says so and keeps what was typed."""
    pages = pages_with_few_calls_a_minute
    answers = [_plan(pages) for _ in range(FEW_CALLS + 1)]

    page = answers[-1]

    assert answers[0].status_code == 200, answers[0].text
    assert page.status_code == 429 and "Too many requests" in page.text
    assert 'name="servings__beef_stew" value="120"' in page.text and 'action="/menu/order"' not in page.text


def test_an_ingredient_nothing_can_supply_is_headed_cannot_be_sourced(pages: TestClient) -> None:
    """Not every such ingredient is late: eggs are not in this demo's recording at all (L4a's item M-5)."""
    page = _plan(pages, {"who": HOTEL_AGENT, "servings__oven_pancake": "50"})

    assert page.status_code == 200, page.text
    assert "<h3>Cannot be sourced</h3>" in page.text and "Cannot arrive in time" not in page.text
    assert "Cannot be sourced in this demo: eggs" in page.text
