"""A public demo that one visitor cannot exhaust (task FIX-8, finding 4).

Scores on the 30% "working end-to-end demo" (the demo link keeps working under a room full of people) and
on the 20% "controls": the demonstration tokens are public and shared, so a caller is counted per visitor,
and every kind of call that reaches the supplier, the model or the audit trail has a ceiling for all callers.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.limits import (
    GLOBAL_CEILINGS,
    UNKNOWN_CLIENT,
    CallKind,
    CallLimits,
    ClientKeyMiddleware,
    RateLimit,
    as_client,
    client_key_of,
    current_client_key,
)
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import Identity
from tta.contracts.errors import RateLimited

Auth = Callable[..., dict[str, str]]
Problem = Callable[..., dict[str, Any]]
# Two public addresses. The documentation ranges of RFC 5737 would not do: Python counts them as private.
VISITOR_A, VISITOR_B = "93.184.216.34", "93.184.216.35"
PROXY = "10.0.0.9"
FORWARDED = b"x-forwarded-for"


class FakeTime:
    def __init__(self) -> None:
        self.seconds = 1000.0

    def __call__(self) -> float:
        return self.seconds


def _scope(peer: Any, forwarded: bytes | None = None) -> dict[str, Any]:
    headers = [] if forwarded is None else [(FORWARDED, forwarded)]
    return {"type": "http", "path": "/v1/offers", "client": peer, "headers": headers}


# --- who is at the other end ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("peer", "forwarded", "expected"),
    [
        ((VISITOR_A, 4711), None, VISITOR_A),
        # A public peer speaks for itself: the header is the caller's own text and is not believed.
        ((VISITOR_A, 4711), VISITOR_B.encode(), VISITOR_A),
        # Behind a proxy of ours (a private or loopback peer) the first forwarded address is the visitor.
        ((PROXY, 4711), VISITOR_B.encode(), VISITOR_B),
        (("127.0.0.1", 4711), f"{VISITOR_A}, {PROXY}".encode(), VISITOR_A),
        (("::1", 4711), b" 2001:db8::7 ,10.0.0.1", "2001:db8::7"),
        ((PROXY, 4711), None, PROXY),
        ((PROXY, 4711), b"", PROXY),
        ((PROXY, 4711), b"not an address, 93.184.216.34", PROXY),
        ((PROXY, 4711), b"<script>" + b"x" * 5000, PROXY),
        ((PROXY, 4711), b"\xff\xfe", PROXY),
        (None, VISITOR_A.encode(), UNKNOWN_CLIENT),
        (("testclient", 50000), VISITOR_A.encode(), UNKNOWN_CLIENT),
    ],
)
def test_the_client_key_is_the_peer_or_behind_our_own_proxy_the_first_forwarded_address(
    peer: Any, forwarded: bytes | None, expected: str
) -> None:
    assert client_key_of(_scope(peer, forwarded)) == expected


def test_the_middleware_sets_the_client_key_for_the_request_and_takes_it_back() -> None:
    seen: list[str] = []

    async def application(scope: Any, receive: Any, send: Any) -> None:
        seen.append(current_client_key())

    async def run() -> None:
        await ClientKeyMiddleware(application)(_scope((PROXY, 1), VISITOR_B.encode()), None, None)
        await ClientKeyMiddleware(application)({"type": "lifespan"}, None, None)
        seen.append(current_client_key())

    asyncio.run(run())

    assert seen == [VISITOR_B, UNKNOWN_CLIENT, UNKNOWN_CLIENT]


# --- one window per visitor, one ceiling for everybody --------------------------------------------------


def _limits(time: FakeTime, *, per_visitor: bool, calls: int = 2, **ceilings: int) -> CallLimits:
    chosen = {**GLOBAL_CEILINGS, **{CallKind[name.upper()]: ceiling for name, ceiling in ceilings.items()}}
    return CallLimits(RateLimit(calls=calls), per_visitor=per_visitor, ceilings=chosen, monotonic=time)


def test_the_ceilings_are_120_lookups_120_orders_and_30_model_calls_a_minute() -> None:
    assert GLOBAL_CEILINGS == {CallKind.LOOKUP: 120, CallKind.ORDER: 120, CallKind.MODEL: 30}


def test_with_shared_demo_tokens_each_visitor_has_its_own_window(agent_hotel: Identity) -> None:
    limits = _limits(FakeTime(), per_visitor=True)

    with as_client(VISITOR_A):
        limits.check(agent_hotel, CallKind.LOOKUP)
        limits.check(agent_hotel, CallKind.ORDER)
        with pytest.raises(RateLimited) as refused:
            limits.check(agent_hotel, CallKind.LOOKUP)
    with as_client(VISITOR_B):
        limits.check(agent_hotel, CallKind.LOOKUP)  # the same token, another visitor: not locked out

    assert refused.value.extensions["retry_after_seconds"] == 60
    assert "2 in 60 seconds" in refused.value.detail
    assert VISITOR_A not in refused.value.detail and agent_hotel.id not in refused.value.detail


def test_a_token_from_the_environment_is_counted_by_identity_wherever_it_calls_from(agent_hotel: Identity) -> None:
    limits = _limits(FakeTime(), per_visitor=False)

    with as_client(VISITOR_A):
        limits.check(agent_hotel, CallKind.LOOKUP)
        limits.check(agent_hotel, CallKind.LOOKUP)
    with as_client(VISITOR_B), pytest.raises(RateLimited):
        limits.check(agent_hotel, CallKind.LOOKUP)


@pytest.mark.parametrize("kind", list(CallKind))
def test_a_ceiling_holds_for_all_callers_together_and_says_when_to_come_back(
    agent_hotel: Identity, agent_ward: Identity, kind: CallKind
) -> None:
    time = FakeTime()
    limits = _limits(time, per_visitor=True, calls=10, **{kind.name.lower(): 3})

    for visitor, identity in ((VISITOR_A, agent_hotel), (VISITOR_B, agent_ward), (PROXY, agent_hotel)):
        with as_client(visitor):
            limits.check(identity, kind)
        time.seconds += 10
    with as_client("192.0.2.1"), pytest.raises(RateLimited) as refused:
        limits.check(agent_ward, kind)

    assert refused.value.extensions["retry_after_seconds"] == 30  # the first of the three leaves the window then
    assert "3" in refused.value.detail and "all callers together" in refused.value.detail
    other = next(each for each in CallKind if each is not kind)
    with as_client("192.0.2.1"):
        limits.check(agent_ward, other)  # the other kinds of call are not held back


def test_a_call_refused_by_a_ceiling_is_not_counted_against_the_caller(agent_hotel: Identity) -> None:
    time = FakeTime()
    limits = _limits(time, per_visitor=True, calls=2, model=1)

    with as_client(VISITOR_A):
        limits.check(agent_hotel, CallKind.MODEL)
        for _ in range(5):
            with pytest.raises(RateLimited):
                limits.check(agent_hotel, CallKind.MODEL)
        limits.check(agent_hotel, CallKind.LOOKUP)  # the second call of the visitor's two: the refusals took none
        with pytest.raises(RateLimited) as refused:
            limits.check(agent_hotel, CallKind.LOOKUP)

    assert "all callers together" not in refused.value.detail


def test_a_call_refused_for_the_caller_is_not_counted_against_the_ceiling(
    agent_hotel: Identity, agent_ward: Identity
) -> None:
    limits = _limits(FakeTime(), per_visitor=True, calls=1, lookup=2)

    with as_client(VISITOR_A):
        limits.check(agent_hotel, CallKind.LOOKUP)
        for _ in range(5):
            with pytest.raises(RateLimited):
                limits.check(agent_hotel, CallKind.LOOKUP)
    with as_client(VISITOR_B):
        limits.check(agent_ward, CallKind.LOOKUP)  # the second of the two the ceiling allows


# --- through the application ----------------------------------------------------------------------------


@pytest.fixture
def limited_app(settings: Settings, catalog: ProductCatalog) -> Iterator[Any]:
    parts = build_parts(settings, catalog=catalog, rate_limit=RateLimit(calls=2, window_seconds=60))
    app = create_app(settings, parts=parts)
    with TestClient(app):  # runs the lifespan; each test opens its own clients on the same app
        yield app


def test_one_visitor_cannot_lock_the_others_out_of_a_shared_demo_token(
    limited_app: Any, auth: Auth, scenario_2: dict[str, Any], assert_problem: Problem
) -> None:
    one = TestClient(limited_app, client=(VISITOR_A, 50000))
    other = TestClient(limited_app, client=(VISITOR_B, 50000))
    for _ in range(2):
        assert one.post("/v1/offers", json=scenario_2, headers=auth("agent_ward")).status_code == 201

    refused = one.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))
    served = other.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))

    assert_problem(refused, "rate-limited", 429)
    assert served.status_code == 201


def test_behind_our_proxy_visitors_are_told_apart_by_the_forwarded_address(
    limited_app: Any, auth: Auth, scenario_2: dict[str, Any], assert_problem: Problem
) -> None:
    proxied = TestClient(limited_app, client=(PROXY, 50000))

    def offer(visitor: str) -> Any:
        headers = {**auth("agent_ward"), "X-Forwarded-For": f"{visitor}, {PROXY}"}
        return proxied.post("/v1/offers", json=scenario_2, headers=headers)

    assert [offer(VISITOR_A).status_code for _ in range(2)] == [201, 201]
    assert_problem(offer(VISITOR_A), "rate-limited", 429)
    assert offer(VISITOR_B).status_code == 201


def test_a_forwarded_address_from_a_public_peer_buys_no_second_window(
    limited_app: Any, auth: Auth, scenario_2: dict[str, Any], assert_problem: Problem
) -> None:
    direct = TestClient(limited_app, client=(VISITOR_A, 50000))

    def offer(claimed: str) -> Any:
        return direct.post("/v1/offers", json=scenario_2, headers={**auth("agent_ward"), "X-Forwarded-For": claimed})

    assert [offer(f"192.0.2.{number}").status_code for number in range(2)] == [201, 201]
    assert_problem(offer("192.0.2.99"), "rate-limited", 429)


MCP_SUBSTITUTES = {
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {"name": "find_substitutes", "arguments": {"product_id": "473609", "query": {}}},
}


def test_one_visitor_cannot_lock_the_others_out_through_the_mcp_tools_either(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The real MCP surface (task T11): its tools run where the SDK puts them, and must still be counted for
    # the visitor whose request they serve. The other tests of this folder see the module as not installed.
    monkeypatch.delitem(sys.modules, "tta.api.mcp_surface")
    parts = build_parts(settings, catalog=catalog, rate_limit=RateLimit(calls=2, window_seconds=60))
    app = create_app(settings, parts=parts)
    headers = {"Accept": "application/json, text/event-stream", "Authorization": "Bearer demo-agent-hotel-kitchen"}

    def refused(client: TestClient) -> bool:
        response = client.post("/mcp", json=MCP_SUBSTITUTES, headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        return bool(result.get("isError")) and result["structuredContent"]["status"] == 429

    with TestClient(app):
        one = TestClient(app, client=(VISITOR_A, 50000))
        other = TestClient(app, client=(VISITOR_B, 50000))
        assert app.state.surfaces["mcp"] is True
        assert [refused(one) for _ in range(3)] == [False, False, True]
        assert refused(other) is False


def test_requests_without_a_token_are_not_counted(
    limited_app: Any, auth: Auth, scenario_2: dict[str, Any], assert_problem: Problem
) -> None:
    client = TestClient(limited_app, client=(VISITOR_A, 50000))
    for _ in range(10):
        assert_problem(client.post("/v1/offers", json=scenario_2), "not-authorised", 401)
        unknown = client.post("/v1/offers", json=scenario_2, headers={"Authorization": "Bearer nobody-issued-this"})
        assert_problem(unknown, "not-authorised", 401)

    assert [
        client.post("/v1/offers", json=scenario_2, headers=auth("agent_ward")).status_code for _ in range(2)
    ] == [201, 201]


NOBODYS_ORDER = {"offer_id": "off_nobody", "option_id": "opt_1"}
TWO_ROUTES_PER_CEILING = [
    (CallKind.LOOKUP, [
        ("agent_ward", "/v1/offers", "scenario"),
        ("agent_hotel", "/v1/products/473609/substitutes", {}),
    ]),
    (CallKind.ORDER, [
        ("agent_ward", "/v1/orders", NOBODYS_ORDER),
        ("hotel_purchasing", "/v1/approvals/apr_nobody/decision", {"decision": "REJECT"}),
    ]),
    (CallKind.MODEL, [
        ("agent_ward", "/v1/requests/parse", {"text": "milk"}),
        ("agent_hotel", "/v1/agent/run", {"text": "milk"}),
    ]),
]


@pytest.mark.parametrize(("kind", "calls"), TWO_ROUTES_PER_CEILING)
def test_above_a_ceiling_the_answer_is_rate_limited_with_retry_after_whoever_calls(
    settings: Settings, catalog: ProductCatalog, auth: Auth, scenario_2: dict[str, Any], assert_problem: Problem,
    monkeypatch: pytest.MonkeyPatch, kind: CallKind, calls: list[tuple[str, str, Any]],
) -> None:
    # Two routes share each ceiling; with a ceiling of two, a third call from a third visitor is refused.
    monkeypatch.setattr("tta.api.limits.GLOBAL_CEILINGS", {**GLOBAL_CEILINGS, kind: 2})
    app = create_app(settings, parts=build_parts(settings, catalog=catalog))

    def call(visitor: str, who: str, path: str, body: Any) -> Any:
        client = TestClient(app, client=(visitor, 50000), raise_server_exceptions=False)
        return client.post(path, json=scenario_2 if body == "scenario" else body, headers=auth(who, "key-1"))

    with TestClient(app):
        for visitor, (who, path, body) in zip((VISITOR_A, VISITOR_B), calls, strict=True):
            assert call(visitor, who, path, body).status_code != 429
        refused = call("192.0.2.1", *calls[0])
        read = TestClient(app, client=("192.0.2.1", 50000)).get("/v1/authority", headers=auth("agent_ward"))

    problem = assert_problem(refused, "rate-limited", 429)
    assert int(refused.headers["retry-after"]) == problem["retry_after_seconds"] > 0
    assert "all callers together" in problem["detail"]
    assert read.status_code == 200  # reads have no ceiling
