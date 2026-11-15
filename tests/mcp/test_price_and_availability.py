"""`search_products` and `get_product` carry price and availability when asked, as the REST routes do (decision
B58, review C1-2).

Scores on the 30% and the 20%: the brief's first core item, "a structured way for an external agent to search for
and retrieve what's available and at what price", over the open protocol an agent's host speaks. The flag is the
same over both transports because both call `tta.api.product_lookup`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import httpx
import pytest
from mcp.client import Client

from tta.api.wiring import Parts

pytestmark = pytest.mark.anyio

Connect = Callable[..., AbstractAsyncContextManager[Client]]
Headers = dict[str, str]
Auth = Callable[[str], Headers]

PROBLEMS = "https://tta.example/problems/"
MONDAY = "2026-11-16"
PLANT_DRINKS = {"product_type": "plant_drink", "limit": 3}
PLANT_DRINK = "464013"  # the confirmed plant drink of scenario 2: €2.01 a piece
ASKED = {"price_and_availability": True, "needed_by": MONDAY}
AS_QUERY = {"price_and_availability": "true", "needed_by": MONDAY}


async def test_a_search_with_the_flag_answers_as_the_rest_route_does(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth
) -> None:
    async with connect("agent_hotel") as client:
        found = await client.call_tool("search_products", {"query": PLANT_DRINKS, **ASKED})
    over_rest = await rest.post("/v1/products/search", params=AS_QUERY, json=PLANT_DRINKS, headers=auth("agent_hotel"))

    assert not found.is_error, found.content
    assert over_rest.status_code == 200
    assert found.structured_content == over_rest.json()
    assert json.loads(found.content[0].text) == found.structured_content  # the model reads the same document
    stated = [product["price_and_availability"] for product in found.structured_content["products"]]
    assert [each["unit_net_price"] for each in stated] == [3.03, 2.43, 2.01]
    assert all(each["availability"]["state"] == "CONFIRMED" and each["needed_by"] == MONDAY for each in stated)
    assert all(each["source"] == "replay" and each["time_now"] for each in stated)


async def test_one_product_with_the_flag_answers_as_the_rest_route_does(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth
) -> None:
    async with connect("agent_ward") as client:
        read = await client.call_tool("get_product", {"product_id": PLANT_DRINK, **ASKED})
    over_rest = await rest.get(f"/v1/products/{PLANT_DRINK}", params=AS_QUERY, headers=auth("agent_ward"))

    assert not read.is_error, read.content
    assert read.structured_content == over_rest.json()
    stated = read.structured_content["price_and_availability"]
    assert (stated["unit_net_price"], stated["currency"], stated["orderable"]) == (2.01, "EUR", True)
    delivery = next(claim for claim in stated["claims"] if claim["claim"] == "delivery_date")
    assert delivery["status"] == "CONFIRMED" and "meets the needed-by date Monday 16 Nov" in delivery["sentence"]


async def test_without_the_flag_both_tools_answer_the_product_file_alone_and_write_nothing(
    connect: Connect, parts: Parts
) -> None:
    async with connect("agent_hotel") as client:
        found = await client.call_tool("search_products", {"query": PLANT_DRINKS})
        switched_off = await client.call_tool(
            "search_products", {"query": PLANT_DRINKS, "price_and_availability": False}
        )
        read = await client.call_tool("get_product", {"product_id": PLANT_DRINK})

    assert found.structured_content == switched_off.structured_content
    assert all(product["price_and_availability"] is None for product in found.structured_content["products"])
    assert read.structured_content["price_and_availability"] is None
    assert parts.audit.head()[0] == 0


async def test_one_call_with_the_flag_writes_one_audit_event(connect: Connect, parts: Parts) -> None:
    async with connect("agent_hotel") as client:
        await client.call_tool("search_products", {"query": PLANT_DRINKS, "price_and_availability": True})
        trail = (await client.call_tool("get_audit")).structured_content

    assert parts.audit.head()[0] == 1
    [event] = trail["events"]
    assert event["type"] == "tta.v1.lookup.performed"
    assert event["facts"]["products_looked_up"] == 3


async def test_a_date_without_the_flag_is_refused_over_mcp_as_over_rest(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth
) -> None:
    async with connect("agent_hotel") as client:
        refused = await client.call_tool("get_product", {"product_id": PLANT_DRINK, "needed_by": MONDAY})
    over_rest = await rest.get(f"/v1/products/{PLANT_DRINK}", params={"needed_by": MONDAY}, headers=auth("agent_hotel"))

    assert refused.is_error
    assert refused.structured_content == over_rest.json()
    assert (refused.structured_content["type"], refused.structured_content["status"]) == (
        PROBLEMS + "invalid-request", 422
    )


async def test_the_two_tools_say_what_the_flag_gives_and_what_it_costs(connect: Connect) -> None:
    async with connect("agent_hotel") as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    for name in ("search_products", "get_product"):
        tool = tools[name]
        flag = tool.input_schema["properties"]["price_and_availability"]
        date = tool.input_schema["properties"]["needed_by"]
        assert (flag["type"], flag["default"]) == ("boolean", False)
        assert "price" in flag["description"] and "20" in flag["description"]
        assert "price_and_availability" in date["description"]
        assert "price_and_availability" in " ".join(tool.description.split())
        product = tool.output_schema.get("$defs", {}).get("Product", tool.output_schema)  # the answer, or in it
        assert "price_and_availability" in product["properties"]
    assert "has no price and no availability" not in " ".join(tools["search_products"].description.split())
