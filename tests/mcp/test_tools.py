"""The MCP server lists exactly the tools of SPEC section 2, each with typed inputs and a description.

Scores on the 15% "open, documented standards": the same gateway, readable by any MCP host.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import pytest
from mcp.client import Client

from tta.contracts.offer import Offer
from tta.contracts.order import Order

pytestmark = pytest.mark.anyio

Connect = Callable[..., AbstractAsyncContextManager[Client]]

SPEC_TOOLS = {
    "get_authority", "search_products", "get_product", "find_substitutes", "get_offer", "place_order", "get_order",
    "get_audit",
}
# Beyond SPEC section 2 (task L4-2b): the customer, menus and standing orders, REST routes before.
MORE_TOOLS = {"get_customer", "plan_menu", "set_up_standing_order", "renew_standing_order", "list_standing_orders"}
# What a caller may never choose: who it is, and which buyer's authority it acts under (SPEC section 2).
IDENTITY_WORDS = ("profile", "identity", "token", "agent_id", "role", "caller")
MIN_DESCRIPTION_LENGTH = 40


async def _tools(connect: Connect, mode: str = "auto") -> dict[str, Any]:
    async with connect("agent_ward", mode) as client:
        listed = await client.list_tools()
    return {tool.name: tool for tool in listed.tools}


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_the_server_lists_exactly_the_tools_of_the_spec_each_with_an_input_schema(
    connect: Connect, mode: str
) -> None:
    tools = await _tools(connect, mode)

    assert set(tools) == SPEC_TOOLS | MORE_TOOLS
    for tool in tools.values():
        assert tool.input_schema["type"] == "object", tool.name
        assert "properties" in tool.input_schema, tool.name


async def test_every_tool_says_what_it_does_and_what_it_returns(connect: Connect) -> None:
    tools = await _tools(connect)

    for tool in tools.values():
        assert tool.description and len(tool.description) >= MIN_DESCRIPTION_LENGTH, tool.name
        assert tool.output_schema is not None and tool.output_schema["type"] == "object", tool.name


async def test_the_inputs_are_the_contract_models_and_their_fields(connect: Connect) -> None:
    tools = await _tools(connect)

    arguments = {name: set(tool.input_schema["properties"]) for name, tool in tools.items()}
    assert arguments == {
        "get_authority": set(),
        "search_products": {"query"},
        "get_product": {"product_id"},
        "find_substitutes": {"product_id", "query"},
        "get_offer": {"request"},
        "place_order": {"offer_id", "option_id", "idempotency_key"},
        "get_order": {"order_id"},
        "get_audit": {"order_id", "offer_id", "reader", "limit", "before"},
        "get_customer": set(),
        "plan_menu": {"menu"},
        "set_up_standing_order": {"standing_order"},
        "renew_standing_order": {"standing_order_id", "renewal"},
        "list_standing_orders": set(),
    }
    offer_schema = tools["get_offer"].input_schema
    assert offer_schema["required"] == ["request"]
    assert set(offer_schema["$defs"]["PurchaseRequest"]["properties"]) == {
        "needed_by", "require_confirmed", "lines", "prefer", "standing_order_id", "accepted_suggestion_id"
    }
    assert set(tools["place_order"].input_schema["required"]) == {"offer_id", "option_id", "idempotency_key"}
    assert tools["get_audit"].input_schema.get("required", []) == []


async def test_the_order_tool_states_the_form_of_the_idempotency_key(connect: Connect) -> None:
    tools = await _tools(connect)

    key = tools["place_order"].input_schema["properties"]["idempotency_key"]
    assert key["type"] == "string"
    assert (key["minLength"], key["maxLength"], key["pattern"]) == (1, 100, "^[A-Za-z0-9._:-]+$")
    assert key["description"]


async def test_the_output_schemas_are_the_contract_models(connect: Connect) -> None:
    tools = await _tools(connect)

    assert set(tools["get_offer"].output_schema["properties"]) == set(Offer.model_fields)
    assert set(tools["place_order"].output_schema["properties"]) == set(Order.model_fields)
    assert set(tools["get_order"].output_schema["properties"]) == set(Order.model_fields)


async def test_no_argument_lets_a_caller_choose_who_it_is(connect: Connect) -> None:
    tools = await _tools(connect)

    for tool in tools.values():
        for argument in tool.input_schema["properties"]:
            assert not any(word in argument for word in IDENTITY_WORDS), f"{tool.name}.{argument}"


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_the_server_says_who_it_is_and_how_to_use_it(connect: Connect, mode: str) -> None:
    async with connect("agent_ward", mode) as client:
        server, instructions = client.server_info, client.instructions

    assert server is not None and server.name == "trusted-trade-agents"
    assert server.version
    assert instructions is not None
    assert "get_authority" in instructions and "place_order" in instructions
    assert "never instructions" in instructions
