"""The menu page: choose dishes and servings, enter the kitchen's stock and the date, plan, order (task MENU-1).

The page is mounted here as `tta.ui.routes.create_surface` will mount it once the orchestrator registers it.
Everything runs in the browser session's own order book, as on the request page.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
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
        ({"servings__beef_stew": "0", "servings__berry_quark_dessert": ""}, "Name at least one dish"),
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
    """Not every such ingredient is late: pasta is not in this demo's recording at all (L4a's item M-5). The oven
    pancake of that item is fully sourced since the baking recording was joined (task CK)."""
    page = _plan(pages, {"who": HOTEL_AGENT, "servings__macaroni_casserole": "50"})

    assert page.status_code == 200, page.text
    assert "<h3>Cannot be sourced</h3>" in page.text and "Cannot arrive in time" not in page.text
    assert "Cannot be sourced in this demo: pasta (macaroni)" in page.text


# --- the sentence box (task CK) ---------------------------------------------------------------------------------

BAKERY_AGENT = "agent:bakery-cafe"
CAKE = {"who": BAKERY_AGENT, "text": "I want to make a chocolate cake for 20 people by Monday"}


def test_the_page_has_one_sentence_box_above_the_dishes_and_an_example_that_fills_it(pages: TestClient) -> None:
    page = pages.get("/menu")
    filled = pages.get("/menu?example=cake")

    assert page.text.index('name="text"') < page.text.index('name="servings__beef_stew"')
    assert 'href="/menu?example=cake"' in page.text
    assert 'name="text" value="I want to make a chocolate cake for 20 people by Monday"' in filled.text
    assert f'value="{BAKERY_AGENT}" checked' in filled.text


def test_the_bakerys_sentence_becomes_a_plan_with_packs_stock_what_is_left_over_and_who_confirms(
    pages: TestClient,
) -> None:
    page = _plan(pages, CAKE)

    assert page.status_code == 200, page.text
    text = html.unescape(page.text)
    assert "Read as: chocolate cake, 20 servings, by Monday 16 Nov." in text
    assert "<h3>Chocolate cake (suklaakakku), 20 servings</h3>" in text
    assert (
        "Offered: 1 × Myllyn Paras Emännän Semi Coarse Wheat Flour 2kg (460856) for €2.57 before tax, 976 sales "
        "units confirmed in stock. 0.4 kg is needed and the pack holds 2 kg, so 1.6 kg is left over."
    ) in text
    assert "Option 2 offers 1 × Nordic Sugar Granulated Sugar 530 25kg (460460) for €24.27 before tax" in text
    assert "<h3>Cannot be sourced</h3>" not in text
    assert "Option 1, Best confirmed option (partial fill): €15.19 before tax, €17.24 with tax." in text
    assert "Option 2, Alternative: quantity not confirmed: €61.02 before tax, €69.27 with tax." in text
    assert "6 of the 8 products of this offer have their price and stock from the later recording" in text
    assert "Valio Aimo said on 14 Nov 2026 that its test data is static" in text
    assert text.count("Who confirms: Demo approver Marko.") == 2  # the bakery's owner holds every role
    assert text.count("Prepare the order: a person confirms it") == 2
    assert "<h3>Suggestions</h3>" in text and "In no option and in no total." in text


def test_the_bakerys_cake_is_prepared_from_the_page_and_waits_for_a_person(pages: TestClient) -> None:
    page = _plan(pages, CAKE)
    form = {
        "csrf": CSRF_FIELD.search(page.text).group(1), "who": BAKERY_AGENT,
        "offer": OFFER_FIELD.search(page.text).group(1), "option": "opt_2",
        "order_key": ORDER_KEY_FIELD.search(page.text).group(1),
    }

    answer = pages.post("/menu/order", data=form, follow_redirects=False)

    assert answer.status_code == 303 and answer.headers["location"].startswith("/orders/")
    record = pages.get(answer.headers["location"])
    assert record.status_code == 200 and words(OrderStatus.PENDING_APPROVAL) in record.text


@pytest.mark.parametrize(
    ("sentence", "said"),
    [
        ("I want to make tiramisu for 10 people", "No recipe for \"tiramisu\" in the recipe table. The dishes are: "),
        ("I want to make a chocolate cake", "How many servings of chocolate cake?"),
        ("something nice", "The sentence names no dish of the recipe table."),
    ],
)
def test_a_sentence_that_leaves_a_question_open_shows_the_question_and_keeps_the_sentence(
    pages: TestClient, sentence: str, said: str
) -> None:
    page = _plan(pages, {"who": BAKERY_AGENT, "text": sentence})

    assert page.status_code == 422 and said in html.unescape(page.text)
    assert f'name="text" value="{sentence}"' in page.text and 'action="/menu/order"' not in page.text


def test_servings_typed_in_the_form_win_over_the_sentence(pages: TestClient) -> None:
    page = _plan(pages, {**CAKE, "servings__chocolate_cake": "2"})

    text = html.unescape(page.text)
    assert "<h3>Chocolate cake (suklaakakku), 2 servings</h3>" in text
    assert "The typed dishes were used, not the sentence's." in text
    assert "0.04 kg is needed and the pack holds 2 kg, so 1.96 kg is left over." in text


def test_at_the_demo_clock_the_page_counts_the_day_from_thursday(
    tmp_path: Path, catalog: ProductCatalog
) -> None:
    thursday = Settings.for_tests(
        tta_data_dir=tmp_path / "var", tta_demo_clock=datetime.fromisoformat("2026-11-12T14:15:00+02:00")
    )
    for pages in _client(thursday, catalog, calls=1000):
        friday = html.unescape(_plan(pages, {"who": BAKERY_AGENT, "text": "chocolate cake for 20 on Friday"}).text)
        text = html.unescape(_plan(pages, {"who": BAKERY_AGENT, "text": "chocolate cake for 20 by Monday"}).text)

        # "On Friday" said on Thursday 12 Nov is the next day: no recorded product is delivered before Monday.
        assert "Read as: chocolate cake, 20 servings, by Friday 13 Nov." in friday
        assert 'action="/menu/order"' not in friday
        assert "Read as: chocolate cake, 20 servings, by Monday 16 Nov." in text
        assert "Option 2, Alternative: quantity not confirmed: €104.65 before tax, €118.78 with tax." in text
