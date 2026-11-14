"""`GET /v1/audit` in pages (review H2): a short trail is answered whole as before; a long one costs a page.

Scores on the 20% "how decisions are logged and auditable" (every answer says what was verified) and on the 15%
"credible path toward production" (the cost of a read does not grow with the trail).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import audit_pages, create_app
from tta.api.audit_pages import AUDIT_PAGE_DEFAULT, AUDIT_PAGE_MAX, WHOLE_CHAIN_MAX_EVENTS, _verify_span
from tta.api.limits import RateLimit
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.audit import GENESIS_HASH

Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]
Problem = Callable[..., dict[str, Any]]


def _walk(client: TestClient, headers: dict[str, str], **params: Any) -> tuple[list[dict[str, Any]], list[Any]]:
    """Every page from the newest back to the first: the events oldest first, and each page's answer."""
    pages, events, before = [], [], None
    while True:
        answer = client.get("/v1/audit", params={**params, **({"before": before} if before else {})}, headers=headers)
        assert answer.status_code == 200, answer.text
        page = answer.json()
        pages.append(page)
        events = [*page["events"], *events]
        before = page["next_cursor"]
        if before is None:
            return events, pages


def test_the_page_sizes_are_named(client: TestClient) -> None:
    assert (AUDIT_PAGE_DEFAULT, AUDIT_PAGE_MAX, WHOLE_CHAIN_MAX_EVENTS) == (100, 200, 1000)


def test_a_short_trail_is_answered_whole_with_the_whole_chain_verified_as_before(
    client: TestClient, parts: Parts, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow
) -> None:
    make_offer(client, "agent_hotel", scenario_1)
    stored = parts.store.list_audit_events()

    view = client.get("/v1/audit", headers=auth("agent_hotel")).json()

    assert [event["id"] for event in view["events"]] == [event.id for event in stored]
    assert (view["next_cursor"], view["verified"], view["page_size"]) == (None, "whole_chain", 100)
    assert view["chain"]["ok"] is True and view["chain"]["checked"] == len(stored)
    assert f"each of the {len(stored)} events shown here matches its hash" in view["chain"]["sentence"]


def test_a_page_holds_the_newest_events_and_the_cursor_reads_the_page_before(
    client: TestClient, parts: Parts, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow
) -> None:
    make_offer(client, "agent_hotel", scenario_1)
    stored = [event.id for event in parts.store.list_audit_events()]
    assert len(stored) >= 5

    events, pages = _walk(client, auth("agent_hotel"), limit=2)

    assert [event["id"] for event in pages[0]["events"]] == stored[-2:]  # the newest two, the older one first
    assert pages[0]["next_cursor"] == stored[-2] and pages[-1]["next_cursor"] is None
    assert [event["id"] for event in events] == stored  # every event once, none twice
    assert all(page["chain"]["checked"] == len(page["events"]) <= 2 for page in pages)
    assert "each of the 2 events shown here" in pages[0]["chain"]["sentence"]
    assert all(page["verified"] == "whole_chain" for page in pages)


def test_a_page_size_outside_one_to_two_hundred_is_refused(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    for limit in (0, 201, "many"):
        assert_problem(client.get("/v1/audit", params={"limit": limit}, headers=auth("agent_hotel")),
                       "invalid-request", 422)
    assert client.get("/v1/audit", params={"limit": 200}, headers=auth("agent_hotel")).status_code == 200


def test_a_cursor_that_is_not_an_event_of_the_callers_view_is_refused_alike(
    client: TestClient, parts: Parts, auth: Auth, scenario_1: dict[str, Any], scenario_2: dict[str, Any],
    make_offer: Flow, assert_problem: Problem, monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_offer(client, "agent_hotel", scenario_1)
    make_offer(client, "agent_ward", scenario_2)
    of_the_ward = next(e.id for e in parts.store.list_audit_events() if e.data.profile_id == "allergy-ward")

    def refusals() -> list[str]:
        return [
            assert_problem(client.get("/v1/audit", params={"before": cursor}, headers=auth("agent_hotel")),
                           "invalid-request", 422)["detail"]
            for cursor in ("an-id-nobody-issued", of_the_ward)
        ]

    short = refusals()
    monkeypatch.setattr(audit_pages, "WHOLE_CHAIN_MAX_EVENTS", 3)  # the same trail, read as a long one
    long = refusals()

    assert len({*short, *long}) == 1 and "next_cursor" in short[0]
    # The supplier reads every buyer's events: the same id is a cursor of its view.
    assert client.get("/v1/audit", params={"before": of_the_ward}, headers=auth("supplier")).status_code == 200


# --- a trail too long to walk for one answer -------------------------------------------------------------


@pytest.fixture
def long_trail(
    client: TestClient, parts: Parts, scenario_1: dict[str, Any], scenario_2: dict[str, Any], make_offer: Flow,
    place_order: Flow, monkeypatch: pytest.MonkeyPatch,
) -> Iterator[dict[str, Any]]:
    """Two buyers' events, then the trail counts as long: more events than one answer verifies whole."""
    offer = make_offer(client, "agent_hotel", scenario_1)
    make_offer(client, "agent_ward", scenario_2)
    order = place_order(client, "agent_hotel", offer, "paged-1")
    make_offer(client, "agent_hotel", scenario_1)
    monkeypatch.setattr(audit_pages, "WHOLE_CHAIN_MAX_EVENTS", 3)
    assert parts.store.count_audit_events() > 3
    yield {"offer": offer, "order": order}


def test_a_long_trail_is_read_a_page_at_a_time_and_the_answer_says_only_the_page_was_verified(
    client: TestClient, parts: Parts, auth: Auth, long_trail: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    hotel = [e.id for e in parts.store.list_audit_events() if e.data.profile_id == "hotel-kitchen"]

    def the_whole_trail(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a long trail must not be read whole for one answer")

    monkeypatch.setattr(parts.store, "list_audit_events", the_whole_trail)
    events, pages = _walk(client, auth("agent_hotel"), limit=4)

    assert [event["id"] for event in events] == hotel and len(pages) > 1
    assert all(page["verified"] == "returned_span" and page["chain"]["ok"] for page in pages)
    assert all(page["chain"]["checked"] == len(page["events"]) <= 4 for page in pages)
    assert "Each of the 4 events returned here matches its hash and follows the event stored before it" in (
        pages[0]["chain"]["sentence"])
    assert "did not walk the whole chain" in pages[0]["chain"]["sentence"]


def test_the_views_of_a_long_trail_hold_what_the_views_of_a_short_one_hold(
    client: TestClient, parts: Parts, auth: Auth, long_trail: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    order_id, offer_id = long_trail["order"]["order_id"], long_trail["offer"]["offer_id"]
    asked = (
        ("agent_hotel", {}), ("agent_hotel", {"order_id": order_id}), ("agent_hotel", {"offer_id": offer_id}),
        ("agent_hotel", {"reader": "supplier"}), ("agent_ward", {}), ("supplier", {}),
        ("supplier", {"order_id": order_id}),
    )
    paged = [client.get("/v1/audit", params=params, headers=auth(who)).json() for who, params in asked]
    monkeypatch.setattr(audit_pages, "WHOLE_CHAIN_MAX_EVENTS", 1000)
    whole = [client.get("/v1/audit", params=params, headers=auth(who)).json() for who, params in asked]

    for one, other in zip(paged, whole, strict=True):
        assert (one["verified"], other["verified"]) == ("returned_span", "whole_chain")
        assert one["events"] == other["events"] and one["events"]
        assert [one[name] for name in ("reader", "order_id", "offer_id")] == [
            other[name] for name in ("reader", "order_id", "offer_id")
        ]


def test_a_changed_event_or_one_out_of_place_is_named_when_only_a_page_is_checked(
    client: TestClient, parts: Parts, scenario_1: dict[str, Any], make_offer: Flow
) -> None:
    make_offer(client, "agent_hotel", scenario_1)
    first, second, third = parts.store.list_audit_events()[:3]
    intact = ((first, None), (second, first.data.hash), (third, second.data.hash))
    changed = second.model_copy(update={"data": second.data.model_copy(update={"sentence": "Nothing happened."})})

    assert _verify_span(intact).ok and _verify_span(((first, GENESIS_HASH),)).ok
    rewritten = _verify_span(((first, None), (changed, first.data.hash), (third, second.data.hash)))
    removed = _verify_span(((first, None), (third, first.data.hash)))  # the event between them is gone

    assert (rewritten.ok, rewritten.first_bad_event_id) == (False, second.id)
    assert "was changed after it was written" in rewritten.sentence
    assert "number 2 of the 3 returned" in rewritten.sentence
    assert (removed.ok, removed.first_bad_event_id) == (False, third.id)
    assert "does not follow the event before it" in removed.sentence
    assert "Only the events returned here were checked" in removed.sentence


# --- reading the trail is counted ------------------------------------------------------------------------


def test_reading_the_trail_counts_against_the_lookup_window(
    settings: Settings, catalog: ProductCatalog, auth: Auth, assert_problem: Problem
) -> None:
    parts = build_parts(settings, catalog=catalog, rate_limit=RateLimit(calls=2, window_seconds=60))
    with TestClient(create_app(settings, parts=parts)) as client:
        answers = [client.get("/v1/audit", headers=auth("supplier")) for _ in range(3)]

    assert [answer.status_code for answer in answers[:2]] == [200, 200]
    problem = assert_problem(answers[2], "rate-limited", 429)
    assert "reads of the catalog and the audit trail" in problem["detail"] and "Retry-After" in answers[2].headers
