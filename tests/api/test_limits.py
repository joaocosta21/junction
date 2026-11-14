"""Limits on what a caller can send and how often (task T09, security review).

Scores on the 15% "credible path toward production": a caller cannot fill the append-only trail or spend
the supplier budget for free.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.limits import MAX_BODY_BYTES, BodyLimitMiddleware, RateLimit, RateLimiter
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.errors import RateLimited

Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]
Problem = Callable[..., dict[str, Any]]


class FakeTime:
    def __init__(self) -> None:
        self.seconds = 1000.0

    def __call__(self) -> float:
        return self.seconds


# --- request body ---------------------------------------------------------------------------------------


def test_the_body_limit_is_64_kilobytes() -> None:
    assert MAX_BODY_BYTES == 64 * 1024


def test_a_body_over_the_limit_is_refused_before_it_is_read(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], assert_problem: Problem
) -> None:
    line = {**scenario_1["lines"][0], "text": "x" * 1900}
    body = {"lines": [line] * 40}  # about 80 KB

    response = client.post("/v1/offers", json=body, headers=auth("agent_hotel"))

    problem = assert_problem(response, "invalid-request", 413)
    assert "64 KB" in problem["detail"]


def test_a_declared_length_over_the_limit_is_answered_without_reading_a_byte() -> None:
    sent: list[dict[str, Any]] = []

    async def never_reached(scope: Any, receive: Any, send: Any) -> None:
        raise AssertionError("the application must not be called")

    async def receive() -> dict[str, Any]:
        raise AssertionError("the body must not be read")

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {"type": "http", "path": "/v1/offers", "headers": [(b"content-length", str(MAX_BODY_BYTES + 1).encode())]}

    asyncio.run(BodyLimitMiddleware(never_reached)(scope, receive, send))

    assert sent[0]["status"] == 413
    assert (b"content-type", b"application/problem+json") in sent[0]["headers"]


def test_a_message_that_is_not_part_of_the_body_passes_uncounted() -> None:
    seen: list[dict[str, Any]] = []

    async def application(scope: Any, receive: Any, send: Any) -> None:
        seen.append(await receive())

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    asyncio.run(BodyLimitMiddleware(application)({"type": "http", "path": "/v1/offers", "headers": []}, receive, None))

    assert seen == [{"type": "http.disconnect"}]


def test_a_body_sent_in_pieces_with_no_length_is_cut_off_at_the_limit(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    def pieces() -> Iterator[bytes]:
        yield b'{"lines": [{"text": "'
        for _ in range(80):
            yield b"x" * 1024
        yield b'"}]}'

    headers = {**auth("agent_hotel"), "Content-Type": "application/json"}

    response = client.post("/v1/offers", content=pieces(), headers=headers)

    assert_problem(response, "invalid-request", 413)


def test_a_length_that_is_not_a_number_is_refused(client: TestClient, auth: Auth) -> None:
    headers = {**auth("agent_hotel"), "Content-Type": "application/json", "Content-Length": "many"}

    response = client.post("/v1/offers", content=b"{}", headers=headers)

    assert response.status_code in (400, 413)


@pytest.mark.parametrize("length", [b"\xb2", b"\xb9\xb2", b"-1", b"1e3", b""])
def test_a_length_python_calls_a_digit_but_cannot_read_is_refused_too(length: bytes) -> None:
    # "\xb2" is the superscript two in latin-1: `str.isdigit` is true for it and `int` raises on it.
    sent: list[dict[str, Any]] = []

    async def never_reached(scope: Any, receive: Any, send: Any) -> None:
        raise AssertionError("the application must not be called")

    async def receive() -> dict[str, Any]:
        raise AssertionError("the body must not be read")

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {"type": "http", "path": "/v1/offers", "headers": [(b"content-length", length)]}

    asyncio.run(BodyLimitMiddleware(never_reached)(scope, receive, send))

    assert sent[0]["status"] == 400
    assert (b"content-type", b"application/problem+json") in sent[0]["headers"]


def test_a_body_at_the_size_of_a_real_request_passes(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any]
) -> None:
    # 3 lines of 190 characters: under the demonstration's 600 characters of words for one request (review H2;
    # this test sent 3 lines of 1,900 before that limit).
    line = {**scenario_1["lines"][0], "text": "x" * 190}

    response = client.post("/v1/offers", json={"lines": [line] * 3}, headers=auth("agent_hotel"))

    assert response.status_code == 201


# --- product ids ----------------------------------------------------------------------------------------


def test_a_request_names_at_most_1000_product_ids_over_all_its_lines(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    ids = [str(400000 + number) for number in range(501)]
    line = {"text": "these", "product_ids": ids, "quantity": 1, "unit": "UNIT"}

    response = client.post("/v1/offers", json={"lines": [line, line]}, headers=auth("agent_hotel"))

    problem = assert_problem(response, "invalid-request", 422)
    assert "1,000" in problem["detail"]


def test_a_line_with_more_than_1000_product_ids_is_refused_by_the_contract(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    ids = [str(400000 + number) for number in range(1001)]
    query = client.post("/v1/products/search", json={"product_ids": ids}, headers=auth("agent_hotel"))

    assert_problem(query, "invalid-request", 422)


# --- lists ----------------------------------------------------------------------------------------------


def test_a_search_returns_at_most_100_products_and_says_how_many_there_are(
    client: TestClient, auth: Auth
) -> None:
    response = client.post(
        "/v1/products/search", json={"category_prefix": "1", "limit": 500}, headers=auth("agent_hotel")
    )

    assert response.status_code == 200
    assert len(response.json()["products"]) == 100
    assert response.json()["total"] > 100


def test_order_and_approval_lists_are_cut_to_the_newest(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow, place_order: Flow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tta.api.service.MAX_LIST_ITEMS", 2)
    monkeypatch.setattr("tta.api.audit_pages.AUDIT_PAGE_DEFAULT", 2)  # the audit trail's own page (review H2)
    orders = [
        place_order(client, "agent_hotel", make_offer(client, "agent_hotel", scenario_1), f"key-{number}")
        for number in range(3)
    ]

    listed = client.get("/v1/orders", headers=auth("agent_hotel")).json()
    approvals = client.get("/v1/approvals", headers=auth("hotel_purchasing")).json()
    events = client.get("/v1/audit", headers=auth("agent_hotel")).json()["events"]

    assert [order["order_id"] for order in listed] == [orders[2]["order_id"], orders[1]["order_id"]]
    assert [approval["order_id"] for approval in approvals] == [orders[1]["order_id"], orders[2]["order_id"]]
    # The newest two events of the buyer's trail: what the last offer suggested (written after its policy
    # checks) and the request for approval of its order.
    assert [event["type"] for event in events] == ["tta.v1.suggestions.shown", "tta.v1.approval.requested"]
    assert orders[2]["order_id"] in events[1]["sentence"]


# --- rate limit -----------------------------------------------------------------------------------------


def test_the_limiter_counts_per_caller_and_forgets_after_the_window() -> None:
    time = FakeTime()
    limiter = RateLimiter(RateLimit(calls=2, window_seconds=60), monotonic=time)

    limiter.check("agent:a")
    limiter.check("agent:a")
    limiter.check("agent:b")
    with pytest.raises(RateLimited) as refused:
        limiter.check("agent:a")
    time.seconds += 59
    with pytest.raises(RateLimited):
        limiter.check("agent:a")
    time.seconds += 2
    limiter.check("agent:a")

    assert refused.value.extensions["retry_after_seconds"] == 60
    assert "agent:a" not in refused.value.detail


def test_a_call_leaves_the_window_one_window_after_it_was_made_and_the_later_ones_stay() -> None:
    time = FakeTime()
    limiter = RateLimiter(RateLimit(calls=2, window_seconds=60), monotonic=time)
    limiter.check("agent:a")
    time.seconds += 30
    limiter.check("agent:a")

    time.seconds += 31  # the first call is 61 seconds old, the second 31
    limiter.check("agent:a")
    with pytest.raises(RateLimited) as refused:
        limiter.check("agent:a")

    assert refused.value.extensions["retry_after_seconds"] == 29


def test_a_refused_call_does_not_extend_the_wait() -> None:
    time = FakeTime()
    limiter = RateLimiter(RateLimit(calls=1, window_seconds=60), monotonic=time)
    limiter.check("agent:a")

    for _ in range(5):
        time.seconds += 10
        with pytest.raises(RateLimited):
            limiter.check("agent:a")
    time.seconds += 11

    limiter.check("agent:a")


def test_one_caller_gets_60_calls_a_minute_by_default() -> None:
    assert RateLimit() == RateLimit(calls=60, window_seconds=60)


def test_the_limiter_forgets_a_caller_whose_window_has_passed() -> None:
    # A caller can be made up (a forged forwarding header), so a window nobody uses any more must not be kept.
    time = FakeTime()
    limiter = RateLimiter(RateLimit(calls=2, window_seconds=60), monotonic=time)
    for number in range(50):
        limiter.check(f"made-up-{number}")
    assert len(limiter) == 50

    time.seconds += 61
    limiter.check("agent:a")

    assert len(limiter) == 1


def test_a_refused_caller_is_not_remembered() -> None:
    limiter = RateLimiter(RateLimit(calls=0, window_seconds=60), monotonic=FakeTime())

    with pytest.raises(RateLimited):
        limiter.check("made-up")

    assert len(limiter) == 0


@pytest.fixture
def limited(settings: Settings, catalog: ProductCatalog) -> Iterator[TestClient]:
    parts = build_parts(settings, catalog=catalog, rate_limit=RateLimit(calls=2, window_seconds=60))
    with TestClient(create_app(settings, parts=parts)) as test_client:
        yield test_client


def test_too_many_offers_from_one_visitor_are_rate_limited_whichever_demo_token_it_uses(
    limited: TestClient, auth: Auth, scenario_1: dict[str, Any], scenario_2: dict[str, Any], assert_problem: Problem
) -> None:
    # The demonstration tokens are public: a visitor is its address, not the token it sends (task FIX-10).
    for _ in range(2):
        assert limited.post("/v1/offers", json=scenario_2, headers=auth("agent_ward")).status_code == 201

    refused = limited.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))
    other_token = limited.post("/v1/offers", json=scenario_1, headers=auth("agent_hotel"))
    elsewhere = TestClient(limited.app, client=("93.184.216.34", 50000))
    other_visitor = elsewhere.post("/v1/offers", json=scenario_1, headers=auth("agent_hotel"))

    problem = assert_problem(refused, "rate-limited", 429)
    assert int(refused.headers["retry-after"]) == problem["retry_after_seconds"] > 0
    assert_problem(other_token, "rate-limited", 429)
    assert other_visitor.status_code == 201


@pytest.mark.parametrize(
    ("who", "method", "path", "body"),
    [
        ("agent_hotel", "POST", "/v1/products/473609/substitutes", {}),
        ("agent_hotel", "POST", "/v1/orders", {"offer_id": "off_nobody", "option_id": "opt_1"}),
        ("hotel_purchasing", "POST", "/v1/approvals/apr_nobody/decision", {"decision": "REJECT"}),
        ("agent_hotel", "POST", "/v1/requests/parse", {"text": "milk"}),
        ("agent_hotel", "POST", "/v1/agent/run", {"text": "milk"}),
    ],
)
def test_every_route_that_reaches_the_supplier_or_writes_the_trail_is_rate_limited(
    limited: TestClient, auth: Auth, assert_problem: Problem, who: str, method: str, path: str, body: Any
) -> None:
    for _ in range(2):
        assert limited.request(method, path, json=body, headers=auth(who, "key-1")).status_code != 429

    refused = limited.request(method, path, json=body, headers=auth(who, "key-1"))

    assert_problem(refused, "rate-limited", 429)


def test_reads_are_not_rate_limited(limited: TestClient, auth: Auth) -> None:
    for _ in range(5):
        assert limited.get("/v1/authority", headers=auth("agent_hotel")).status_code == 200
        assert limited.get("/v1/orders", headers=auth("agent_hotel")).status_code == 200
