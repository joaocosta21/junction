"""A private order book per browser session of the pages (task FIX-10, finding 1).

Scores on the 30% "working end-to-end demo" and the 20% "what the agent can decide alone": on one shared
order book, the day's spend of every visitor added up, so three visitors used up the autonomous scenario
for everybody. Each browser of the pages now gets its own book over the shared catalog, supplier gateway,
policy and limits; the REST API and MCP keep the shared book of their tokens.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.limits import VISITOR_WINDOWS, CallKind, as_client
from tta.api.sandbox import MAX_SANDBOXES, SANDBOX_IDLE_SECONDS, Sandboxes
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import Identity, OrderStatus, Verdict
from tta.contracts.errors import NotFound, RateLimited, SupplierUnavailable
from tta.contracts.request import PurchaseRequest

Auth = Callable[..., dict[str, str]]


class FakeTime:
    def __init__(self) -> None:
        self.seconds = 1000.0

    def __call__(self) -> float:
        return self.seconds


@pytest.fixture
def ward_request(scenario_2: dict[str, Any]) -> PurchaseRequest:
    return PurchaseRequest.model_validate({**scenario_2, "lines": [
        {**scenario_2["lines"][0], "allergen_strictness": "STRICT"},
    ]})


def _order_scenario_2(book: Any, agent: Identity, request: PurchaseRequest, key: str) -> Any:
    offer = book.service.create_offer(agent, request)
    return book.service.place_order(agent, offer.offer_id, offer.options[0].option_id, key)


def test_the_sandboxes_exist_in_dev_and_demo_and_are_capped_at_1000_for_two_idle_hours(parts: Parts) -> None:
    assert parts.sandboxes is not None
    assert (MAX_SANDBOXES, SANDBOX_IDLE_SECONDS) == (1000, 2 * 60 * 60)  # 300 before the review day (B55)


def test_outside_dev_and_demo_there_is_no_sandbox(tmp_path: Any, catalog: ProductCatalog) -> None:
    token = {"an-environment-token-of-forty-characters": {
        "kind": "AGENT", "id": "agent:canteen", "display_name": "Canteen agent", "profile_id": "hotel-kitchen",
    }}
    settings = Settings.for_tests(tta_env="prod", tta_tokens=json.dumps(token), tta_data_dir=tmp_path / "var")
    parts = build_parts(settings, catalog=catalog)

    assert parts.sandboxes is None
    parts.close()


def test_each_sandbox_has_its_own_orders_and_its_own_day_of_spend(
    parts: Parts, agent_ward: Identity, ward_request: PurchaseRequest
) -> None:
    one, other = parts.sandboxes.open("visitor-one"), parts.sandboxes.open("visitor-two")

    rules = [_order_scenario_2(one, agent_ward, ward_request, f"k-{n}").decision.rule_ids for n in range(4)]
    elsewhere = _order_scenario_2(other, agent_ward, ward_request, "k-0")

    # Four times €402 is above the ward's illustrative €1,500 a day: the fourth goes to a human, in one book.
    assert rules == [("F-10",)] * 3 + [("P-02",)]
    assert (elsewhere.decision.verdict, elsewhere.status) == (Verdict.APPROVAL, OrderStatus.PENDING_APPROVAL)
    assert len(one.service.list_orders(agent_ward)) == 4 and len(other.service.list_orders(agent_ward)) == 1
    with pytest.raises(NotFound):
        other.service.get_order(agent_ward, one.service.list_orders(agent_ward)[0].order_id)
    assert parts.service.list_orders(agent_ward) == ()  # nothing reached the shared book of the tokens
    assert parts.store.list_audit_events() == ()


def test_a_sandbox_is_found_again_by_its_key_and_an_unknown_key_finds_none(parts: Parts) -> None:
    book = parts.sandboxes.open("visitor-one")

    assert parts.sandboxes.open("visitor-one") is book and parts.sandboxes.find("visitor-one") is book
    assert parts.sandboxes.find("nobody") is None and parts.sandboxes.find(None) is None


def test_the_blank_book_is_empty_shared_and_not_counted(parts: Parts, agent_ward: Identity) -> None:
    blank = parts.sandboxes.blank()

    assert parts.sandboxes.blank() is blank and len(parts.sandboxes) == 0
    assert blank.service.list_orders(agent_ward) == () and blank.audit.head()[0] == 0


def test_the_sandboxes_share_the_limits_of_one_visitor_with_the_rest_of_the_gateway(
    parts: Parts, agent_ward: Identity, ward_request: PurchaseRequest
) -> None:
    books = [parts.sandboxes.open(f"browser-{number}") for number in range(3)]

    with as_client("93.184.216.34"), pytest.raises(RateLimited):
        for number in range(VISITOR_WINDOWS[CallKind.LOOKUP] + 1):  # a new browser does not buy a new window
            books[number % len(books)].service.create_offer(agent_ward, ward_request)


def test_starting_again_empties_the_visitors_book_and_closes_the_old_one(
    parts: Parts, agent_ward: Identity, ward_request: PurchaseRequest
) -> None:
    book = parts.sandboxes.open("visitor-one")
    _order_scenario_2(book, agent_ward, ward_request, "k-1")

    parts.sandboxes.drop("visitor-one")
    again = parts.sandboxes.open("visitor-one")

    assert again is not book and again.service.list_orders(agent_ward) == ()
    with pytest.raises(SupplierUnavailable):  # the store's own word for a closed database
        book.store.list_orders()


def _registry(time: FakeTime, capacity: int = 3, idle_seconds: float = 60) -> tuple[Sandboxes, list[Any]]:
    built: list[Any] = []

    class Book:
        def __init__(self) -> None:
            self.closed = False
            built.append(self)

        def close(self) -> None:
            self.closed = True

    return Sandboxes(Book, capacity=capacity, idle_seconds=idle_seconds, monotonic=time), built  # type: ignore[arg-type]


def test_above_the_cap_the_book_used_least_recently_is_dropped() -> None:
    time = FakeTime()
    sandboxes, built = _registry(time)
    for key in ("a", "b", "c"):
        sandboxes.open(key)
        time.seconds += 1
    sandboxes.find("a")  # "a" is used again: "b" is now the one used least recently

    sandboxes.open("d")

    assert len(sandboxes) == 3
    assert sandboxes.find("b") is None and built[1].closed
    assert all(sandboxes.find(key) is not None for key in ("a", "c", "d"))


def test_a_book_idle_for_longer_than_the_limit_is_dropped() -> None:
    time = FakeTime()
    sandboxes, built = _registry(time, idle_seconds=60)
    sandboxes.open("a")
    time.seconds += 30
    sandboxes.open("b")
    time.seconds += 31

    assert sandboxes.find("a") is None and built[0].closed
    assert sandboxes.find("b") is built[1]
    time.seconds += 61
    sandboxes.open("c")
    assert len(sandboxes) == 1 and built[1].closed


def test_closing_closes_every_book(parts: Parts) -> None:
    one, other = parts.sandboxes.open("a"), parts.sandboxes.open("b")
    blank = parts.sandboxes.blank()

    parts.sandboxes.close()

    for book in (one, other, blank):
        with pytest.raises(SupplierUnavailable):
            book.store.list_orders()
    assert len(parts.sandboxes) == 0


def test_the_rest_api_keeps_the_shared_book_of_its_tokens(
    settings: Settings, parts: Parts, auth: Auth, scenario_2: dict[str, Any], agent_ward: Identity
) -> None:
    with TestClient(create_app(settings, parts=parts)) as client:  # the app closes the parts when it stops
        offer = client.post("/v1/offers", json=scenario_2, headers=auth("agent_ward")).json()
        shared = parts.service.get_offer(agent_ward, offer["offer_id"])
        with pytest.raises(NotFound):
            parts.sandboxes.open("visitor-one").service.get_offer(agent_ward, offer["offer_id"])

    assert shared.offer_id == offer["offer_id"]
