"""No MCP tool can decide an approval: approving is for a human, on the approval routes.

Scores on the 20% "autonomy and controls": what needs human sign-off cannot be signed off by an agent's
host, whatever token it holds.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import httpx
import pytest
from mcp.client import Client

pytestmark = pytest.mark.anyio

Connect = Callable[..., AbstractAsyncContextManager[Client]]
Headers = dict[str, str]
Auth = Callable[[str], Headers]

APPROVAL_WORDS = ("approv", "decide", "decision", "reject", "sign")
APPROVAL_FUNCTIONS = ("decide_approval", "list_approvals", "get_approval", "approve_order")


async def _waiting_order(client: Client, scenario_1: dict[str, Any], key: str) -> dict[str, Any]:
    """Scenario 1: 1,000 litres for the hotel is above its limit per order, so the order waits for a human."""
    offer = (await client.call_tool("get_offer", {"request": scenario_1})).structured_content
    arguments = {
        "offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"], "idempotency_key": key,
    }
    placed = await client.call_tool("place_order", arguments)
    assert not placed.is_error
    return placed.structured_content


@pytest.mark.parametrize("who", ["agent_hotel", "hotel_purchasing", "supplier"])
async def test_no_tool_decides_or_lists_an_approval_whoever_asks(connect: Connect, who: str) -> None:
    async with connect(who) as client:
        tools = (await client.list_tools()).tools

    assert len(tools) == 13  # the customer, menus and standing orders included: none of them approves
    for tool in tools:
        assert not any(word in tool.name for word in APPROVAL_WORDS), tool.name
        assert "decision" not in tool.input_schema["properties"], tool.name
        assert "approval_id" not in tool.input_schema["properties"], tool.name


@pytest.mark.parametrize("who", ["agent_hotel", "hotel_purchasing"])
async def test_calling_an_approval_function_by_name_reaches_nothing(
    connect: Connect, scenario_1: dict[str, Any], who: str
) -> None:
    async with connect("agent_hotel") as agent, connect(who) as caller:
        order = await _waiting_order(agent, scenario_1, "mcp-approval-1")
        answers = [
            await caller.call_tool(name, {"approval_id": order["approval_id"], "decision": {"decision": "APPROVE"}})
            for name in APPROVAL_FUNCTIONS
        ]
        after = (await agent.call_tool("get_order", {"order_id": order["order_id"]})).structured_content

    assert order["status"] == "PENDING_APPROVAL"
    assert all(answer.is_error for answer in answers)
    assert after["status"] == "PENDING_APPROVAL"


async def test_an_order_that_needs_a_human_waits_until_a_human_approves_it_outside_mcp(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth, scenario_1: dict[str, Any]
) -> None:
    async with connect("agent_hotel") as agent:
        order = await _waiting_order(agent, scenario_1, "mcp-approval-2")
        before = (await agent.call_tool("get_order", {"order_id": order["order_id"]})).structured_content
        decided = await rest.post(
            f"/v1/approvals/{order['approval_id']}/decision", json={"decision": "APPROVE"},
            headers=auth("hotel_purchasing"),
        )
        after = (await agent.call_tool("get_order", {"order_id": order["order_id"]})).structured_content

    assert order["decision"]["verdict"] == "APPROVAL"
    assert order["decision"]["required_roles"] == ["purchasing_manager"]
    assert before["status"] == "PENDING_APPROVAL" and before["placed_by"] is None
    assert decided.status_code == 200
    assert (after["status"], after["placed_by"]) == ("ORDERED", "HUMAN_APPROVAL")
