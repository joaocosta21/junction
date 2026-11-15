"""The MCP server lists exactly the tools of SPEC section 2, each with typed inputs and a description.

Scores on the 15% "open, documented standards": the same gateway, readable by any MCP host.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import pytest
from mcp.client import Client

from tta.catalog import ProductCatalog
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
        "search_products": {"query", "price_and_availability", "needed_by"},  # the flag of decision B58
        "get_product": {"product_id", "price_and_availability", "needed_by"},
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
        "needed_by", "require_confirmed", "lines", "prefer", "standing_order_id", "accepted_suggestion_id",
        "max_net_eur",  # the most the buyer wants to spend on this request: it can only add a check (rule P-01)
    }
    assert set(tools["place_order"].input_schema["required"]) == {"offer_id", "option_id", "idempotency_key"}
    assert tools["get_audit"].input_schema.get("required", []) == []
    # The flag and its date are optional: a call without them is the call of before.
    assert tools["search_products"].input_schema["required"] == ["query"]
    assert tools["get_product"].input_schema["required"] == ["product_id"]


async def test_a_request_line_lists_the_product_types_and_does_not_require_the_pack(
    connect: Connect, catalog: ProductCatalog
) -> None:
    # Review C2-7: `pack` was marked required though it has a default, and `product_type` named a table of keys
    # that nothing published. The same sentence typed with `product_type` and with `name_terms` gave two answers
    # (435 L and 1,000 L of the brief's milk), so the schema says which field carries a kind of product.
    tools = await _tools(connect)
    keys = list(catalog.product_type_keys())

    assert len(keys) == 32 and "milk" in keys and "coffee_milk" in keys
    for tool, argument in (("get_offer", "request"), ("set_up_standing_order", "standing_order")):
        line = tools[tool].input_schema["$defs"]["RequestLine"]
        assert line["required"] == ["text", "quantity", "unit"], tool
        assert "pack" in line["properties"], tool  # still an argument, with the default its description names
        assert argument in tools[tool].input_schema["required"]
    typed = (
        tools["get_offer"].input_schema["$defs"]["RequestLine"],
        tools["search_products"].input_schema["$defs"]["ProductQuery"],
    )
    for model in typed:
        product_type, name_terms = model["properties"]["product_type"], model["properties"]["name_terms"]
        [as_text] = [branch for branch in product_type["anyOf"] if branch.get("type") == "string"]
        assert as_text["enum"] == keys
        assert all(f" {key}" in product_type["description"] for key in keys)
        assert "never in `name_terms`" in product_type["description"]
        assert "Never the kind of product itself" in name_terms["description"]
        assert "A key of the product-type table" not in product_type["description"]


async def test_a_request_without_a_pack_is_taken_as_the_schema_says(connect: Connect) -> None:
    request = {"lines": [{"text": "10 litres of milk", "product_type": "milk", "quantity": 10, "unit": "L"}]}
    async with connect("agent_hotel") as client:
        offer = await client.call_tool("get_offer", {"request": request})

    assert not offer.is_error
    assert offer.structured_content["request"]["lines"][0]["pack"] == "BULK"  # the default for litres


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
