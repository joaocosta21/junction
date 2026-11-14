"""How much one address and one demonstration token can make the gateway store (review H2).

Scores on the 30% "working end-to-end demo" (the public link keeps working) and on the 15% "credible path toward
production": in dev and demo the words of a request are bounded, and an address and a token have a day's budget
of stored bytes, refused with the time it starts again.
"""

from __future__ import annotations

import contextvars
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

import tta.ui.examples as page_examples
from tta.api import create_app
from tta.api.budget import (
    MAX_STORED_MEGABYTES_PER_ADDRESS_PER_DAY,
    MAX_STORED_MEGABYTES_PER_TOKEN_PER_DAY,
    StorageBudget,
)
from tta.api.limits import as_client
from tta.api.service import MAX_DEMO_REQUEST_CHARACTERS
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.errors import RateLimited

Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]
Problem = Callable[..., dict[str, Any]]
THE_BRIEFS_SENTENCE = (
    "I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on "
    "price and availability."
)
ENV_TOKEN = "an-environment-token-of-forty-characters"
ENV_TOKENS = json.dumps({
    ENV_TOKEN: {"kind": "AGENT", "id": "agent:canteen", "display_name": "Canteen agent", "profile_id": "hotel-kitchen"},
})
ADDRESS_A, ADDRESS_B = "203.0.113.7", "203.0.113.8"


def _line(text: str) -> dict[str, Any]:
    return {"text": text, "product_type": "milk", "quantity": 1, "unit": "L"}


# --- (1) the words of one request ------------------------------------------------------------------------


def test_in_the_demonstration_the_words_of_a_request_have_at_most_600_characters_over_all_lines(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    assert MAX_DEMO_REQUEST_CHARACTERS == 600

    fits = client.post("/v1/offers", json={"lines": [_line("x" * 200)] * 3}, headers=auth("agent_hotel"))
    over = client.post("/v1/offers", json={"lines": [_line("x" * 200)] * 2 + [_line("x" * 201)]},
                       headers=auth("agent_hotel"))
    largest = client.post("/v1/offers", json={"lines": [_line("x" * 2000)] * 5}, headers=auth("agent_hotel"))

    assert fits.status_code == 201
    problem = assert_problem(over, "invalid-request", 422)
    assert "at most 600 characters" in problem["detail"] and "these have 601" in problem["detail"]
    assert "10,000" in assert_problem(largest, "invalid-request", 422)["detail"]


def test_a_request_refused_for_its_words_stores_nothing(client: TestClient, parts: Parts, auth: Auth) -> None:
    client.post("/v1/offers", json={"lines": [_line("x" * 601)]}, headers=auth("agent_hotel"))

    assert parts.store.count_audit_events() == 0


def test_the_briefs_sentence_and_every_example_of_the_pages_fit_several_times(
    client: TestClient, auth: Auth
) -> None:
    of_the_pages = [
        value for name, value in vars(page_examples).items() if name.endswith("_TEXT") and isinstance(value, str)
    ]
    texts = [THE_BRIEFS_SENTENCE, *of_the_pages]
    assert len(of_the_pages) >= 6

    longest = max(texts, key=len)
    assert len(longest) * 4 <= MAX_DEMO_REQUEST_CHARACTERS  # four lines of the longest example still pass
    answer = client.post("/v1/offers", json={"lines": [_line(longest)] * 4}, headers=auth("agent_hotel"))
    assert answer.status_code == 201


def test_outside_the_demonstration_the_contracts_own_limit_on_words_stands(
    tmp_path: Any, catalog: ProductCatalog
) -> None:
    settings = Settings.for_tests(tta_env="prod", tta_tokens=ENV_TOKENS, tta_data_dir=tmp_path / "var")
    app = create_app(settings, parts=build_parts(settings, catalog=catalog))

    with TestClient(app) as client:
        offer = client.post("/v1/offers", json={"lines": [_line("x" * 700)]},
                            headers={"Authorization": f"Bearer {ENV_TOKEN}"})

    assert offer.status_code == 201
    assert app.state.parts.service._deps.limiter.storage is None  # and no day's budget either


# --- (2) the day's budget of stored bytes ----------------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 14, 21, 30, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def test_the_budgets_are_100_megabytes_for_an_address_and_four_times_that_for_a_token() -> None:
    assert (MAX_STORED_MEGABYTES_PER_ADDRESS_PER_DAY, MAX_STORED_MEGABYTES_PER_TOKEN_PER_DAY) == (100, 400)


def test_an_address_that_stored_its_budget_is_refused_until_midnight_utc_and_the_refusal_says_so() -> None:
    clock = Clock()
    budget = StorageBudget(per_address_bytes=1000, per_token_bytes=10_000, now=clock)

    with as_client(ADDRESS_A):
        budget.check("agent:hotel")
        budget.charge(999)
        budget.check("agent:hotel")  # under the budget: what a call writes is never cut short
        budget.charge(500)
        with pytest.raises(RateLimited) as refused:
            budget.check("agent:hotel")
    with as_client(ADDRESS_B):
        budget.check("agent:hotel")  # another address, the same token: served

    assert "at most 0.001 MB a day" in refused.value.detail and "for one address" in refused.value.detail
    assert "starts again at 00:00 UTC, in 2 h 30 min" in refused.value.detail
    assert refused.value.extensions["retry_after_seconds"] == 2 * 3600 + 30 * 60

    clock.now += timedelta(hours=2, minutes=30)
    with as_client(ADDRESS_A):
        budget.check("agent:hotel")
    assert budget.stored("address", ADDRESS_A) == 0


def test_a_token_that_stored_its_budget_is_refused_from_every_address_and_other_tokens_are_not() -> None:
    budget = StorageBudget(per_address_bytes=1000, per_token_bytes=1500, now=Clock())
    for address in (ADDRESS_A, ADDRESS_B):
        with as_client(address):
            budget.check("agent:hotel")
            budget.charge(800)

    with as_client("203.0.113.9"), pytest.raises(RateLimited) as refused:
        budget.check("agent:hotel")
    with as_client("203.0.113.9"):
        budget.check("agent:ward")

    assert "for one demonstration token" in refused.value.detail and "00:00 UTC" in refused.value.detail


def test_what_is_written_outside_a_checked_call_is_not_counted() -> None:
    budget = StorageBudget(now=Clock())

    # The gateway's own writes at start: no call of a visitor is being served. A context of its own, as the
    # start has: the tests before this one checked calls in this thread.
    contextvars.Context().run(budget.charge, 5000)

    assert budget.stored("address", "unknown") == 0


def _stored_in(parts: Parts) -> int:
    with sqlite3.connect(parts.settings.db_path) as connection:
        events = connection.execute("SELECT COALESCE(SUM(LENGTH(CAST(body AS BLOB))), 0) FROM audit_events").fetchone()
        offers = connection.execute("SELECT COALESCE(SUM(LENGTH(CAST(body AS BLOB))), 0) FROM offers").fetchone()
    return events[0] + offers[0]


def test_what_an_offer_and_an_order_store_is_what_the_budget_counts(
    app: Any, parts: Parts, scenario_1: dict[str, Any], make_offer: Flow, place_order: Flow
) -> None:
    budget = parts.service._deps.limiter.storage
    with TestClient(app, client=(ADDRESS_A, 50000)) as client:
        offer = make_offer(client, "agent_hotel", scenario_1)
        after_the_offer = budget.stored("address", ADDRESS_A)
        # The count is of the JSON as the contract writes it; the store's own writing differs by a few bytes.
        assert after_the_offer > 10_000 and after_the_offer == pytest.approx(_stored_in(parts), rel=0.01)

        place_order(client, "agent_hotel", offer, "counted-1")
        in_the_database = _stored_in(parts)

    # An order's events are counted too; its own row is not, so the count is the events and the offer's row.
    assert budget.stored("address", ADDRESS_A) == pytest.approx(in_the_database, rel=0.01)
    assert budget.stored("address", ADDRESS_A) > after_the_offer
    assert budget.stored("token", "agent:hotel-kitchen") == budget.stored("address", ADDRESS_A)


def test_over_the_budget_an_offer_is_refused_with_429_and_reading_still_works(
    app: Any, parts: Parts, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow, assert_problem: Problem
) -> None:
    budget = parts.service._deps.limiter.storage
    budget._limits["address"] = 20_000  # one offer of scenario 1 stores about 59,000 bytes
    with TestClient(app, client=(ADDRESS_A, 50000)) as one:
        other = TestClient(app, client=(ADDRESS_B, 50000))
        offer = make_offer(one, "agent_hotel", scenario_1)
        events = parts.store.count_audit_events()

        refused = one.post("/v1/offers", json=scenario_1, headers=auth("agent_hotel"))
        other_token = one.post("/v1/offers", json=scenario_1, headers=auth("agent_ward"))
        read = one.get(f"/v1/offers/{offer['offer_id']}", headers=auth("agent_hotel"))
        trail = one.get("/v1/audit", headers=auth("agent_hotel"))
        found = one.post("/v1/products/search", json={"product_type": "milk"}, headers=auth("agent_hotel"))
        served = other.post("/v1/offers", json=scenario_1, headers=auth("agent_hotel"))
        written_for_the_other = parts.store.count_audit_events() > events

    problem = assert_problem(refused, "rate-limited", 429)
    assert "0.02 MB a day" in problem["detail"] and "for one address" in problem["detail"]
    assert "starts again at 00:00 UTC" in problem["detail"] and int(refused.headers["Retry-After"]) > 0
    assert_problem(other_token, "rate-limited", 429)  # the address is what is spent, whichever token it sends
    assert (read.status_code, trail.status_code, found.status_code) == (200, 200, 200)
    assert served.status_code == 201 and written_for_the_other


def test_the_limits_are_said_in_the_openapi_document_and_in_llms_txt(client: TestClient) -> None:
    description, text = client.get("/openapi.json").json()["info"]["description"], client.get("/llms.txt").text

    for said in (description, text):
        flat = " ".join(said.split())
        assert "600 characters" in flat and "100 MB" in flat and "400 MB" in flat and "00:00 UTC" in flat
        assert "4 name terms" in flat and "next_cursor" in flat and "at most 200" in flat
        assert "whole_chain" in flat and "returned_span" in flat
