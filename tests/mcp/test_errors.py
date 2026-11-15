"""A typed error of the gateway leaves a tool as an error result that carries the problem document
(RFC 9457: `type`, `title`, `status`, `detail` and any extension member), never a trace.

Scores on the 15% "open, documented standards" and the 15% "robustness": an agent reads one stable `type`
per kind of problem over MCP exactly as over REST.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from decimal import Decimal
from typing import Any

import httpx
import pytest
from mcp.client import Client
from mcp.types import CallToolResult

from tta.api.limits import RateLimit
from tta.api.wiring import Parts
from tta.contracts.errors import PROBLEM_TYPE_BASE

pytestmark = pytest.mark.anyio

Connect = Callable[..., AbstractAsyncContextManager[Client]]
Headers = dict[str, str]
Auth = Callable[[str], Headers]

NO_SUCH_PRODUCT = "459999"  # made up: no product of the catalog has this id
ONE_CALL = RateLimit(calls=1, window_seconds=60.0)


def _problem(answer: CallToolResult, slug: str, status: int) -> dict[str, Any]:
    """Check that a tool answer is an error carrying a problem of one type and status; hand back the problem."""
    assert answer.is_error is True
    problem = answer.structured_content
    assert problem is not None
    assert problem["type"] == PROBLEM_TYPE_BASE + slug
    assert problem["status"] == status
    assert problem["title"] and problem["detail"]
    [block] = answer.content
    assert json.loads(block.text) == problem  # the model reads the same document a program reads
    assert "Traceback" not in block.text
    return problem


async def _order(client: Client, offer: dict[str, Any], key: str) -> CallToolResult:
    arguments = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"], "idempotency_key": key}
    return await client.call_tool("place_order", arguments)


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_an_unknown_product_is_a_tool_error_with_the_problem_of_the_rest_route(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth, mode: str
) -> None:
    async with connect("agent_ward", mode) as client:
        answer = await client.call_tool("get_product", {"product_id": NO_SUCH_PRODUCT})
    over_rest = await rest.get(f"/v1/products/{NO_SUCH_PRODUCT}", headers=auth("agent_ward"))

    problem = _problem(answer, "unknown-product", 404)
    assert problem == over_rest.json()


async def test_an_order_id_nobody_issued_is_not_found(connect: Connect) -> None:
    async with connect("agent_ward") as client:
        answer = await client.call_tool("get_order", {"order_id": "ord_nobody_issued_this"})

    _problem(answer, "not-found", 404)


async def test_a_second_order_on_one_offer_is_refused_as_over_rest(
    connect: Connect, scenario_2: dict[str, Any]
) -> None:
    async with connect("agent_ward") as client:
        offer = (await client.call_tool("get_offer", {"request": scenario_2})).structured_content
        first = await _order(client, offer, "mcp-second-1")
        second = await _order(client, offer, "mcp-second-2")

    assert not first.is_error
    _problem(second, "invalid-request", 422)


async def test_a_changed_price_is_offer_stale_and_names_the_fresh_offer(
    connect: Connect, changing: Any, parts: Parts, scenario_2: dict[str, Any]
) -> None:
    async with connect("agent_ward") as client:
        offer = (await client.call_tool("get_offer", {"request": scenario_2})).structured_content
        changing.price_rise = Decimal("0.10")
        answer = await _order(client, offer, "mcp-stale-1")

    problem = _problem(answer, "offer-stale", 409)
    assert problem["fresh_offer_id"] not in (None, offer["offer_id"])
    assert parts.store.get_offer(problem["fresh_offer_id"]) is not None
    assert parts.store.list_orders() == ()


@pytest.mark.parametrize("rate_limit", [ONE_CALL])
async def test_the_rate_limit_of_the_service_holds_over_mcp(
    connect: Connect, scenario_2: dict[str, Any], rate_limit: RateLimit
) -> None:
    async with connect("agent_ward") as client:
        first = await client.call_tool("get_offer", {"request": scenario_2})
        second = await client.call_tool("get_offer", {"request": scenario_2})

    assert not first.is_error
    problem = _problem(second, "rate-limited", 429)
    assert problem["retry_after_seconds"] >= 1


@pytest.mark.parametrize("rate_limit", [ONE_CALL])
async def test_each_visitor_of_the_public_demonstration_tokens_has_its_own_limit_over_mcp(
    connect: Connect, scenario_2: dict[str, Any], rate_limit: RateLimit
) -> None:
    # The demonstration tokens are shared, so the service counts a caller per visitor (`tta.api.limits`).
    # 203.0.113.0/24 is reserved for documentation (RFC 5737).
    async with (
        connect("agent_ward", visitor="203.0.113.7") as one,
        connect("agent_ward", visitor="203.0.113.8") as other,
    ):
        first = await one.call_tool("get_offer", {"request": scenario_2})
        second = await one.call_tool("get_offer", {"request": scenario_2})
        elsewhere = await other.call_tool("get_offer", {"request": scenario_2})

    assert not first.is_error
    _problem(second, "rate-limited", 429)
    assert not elsewhere.is_error  # one visitor at its limit does not lock out the next


async def test_arguments_that_do_not_match_the_schema_are_refused_before_the_tool_runs(
    connect: Connect, parts: Parts
) -> None:
    no_quantity = {"lines": [{"text": "some milk", "unit": "L"}]}
    async with connect("agent_ward") as client:
        answer = await client.call_tool("get_offer", {"request": no_quantity})
        unknown_field = await client.call_tool("get_product", {"product_id": "464013", "profile_id": "hotel-kitchen"})

    assert "quantity" in _problem(answer, "invalid-request", 422)["detail"]
    assert parts.audit.head()[0] == 0  # nothing was built or recorded
    # An argument the tool does not have is not a way to choose a buyer: it is refused, as REST refuses a field
    # a request does not have (review C1-7; `test_strict_arguments.py` holds the reproductions).
    refused = _problem(unknown_field, "invalid-request", 422)
    assert refused["errors"] == [{"field": "arguments", "problem": "a field this request does not have"}]
    assert "hotel-kitchen" not in unknown_field.content[0].text


async def test_an_unexpected_fault_says_nothing_about_itself(
    connect: Connect, changing: Any, scenario_2: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    changing.broken = True
    async with connect("agent_ward") as client:
        answer = await client.call_tool("get_offer", {"request": scenario_2})

    assert answer.is_error is True
    [block] = answer.content
    assert "do-not-show-this-to-a-caller" not in block.text
    assert "Traceback" not in block.text and "RuntimeError" not in block.text
    assert answer.structured_content is None
    assert "do-not-show-this-to-a-caller" in caplog.text  # the fault itself goes to the server's log only
