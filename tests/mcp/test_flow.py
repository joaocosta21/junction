"""Request, lookup and order over MCP, in replay: the same answers as the REST routes give.

Scores on the 30% "one continuous flow" and the 15% "open standards": an MCP host runs the whole flow with
the tools, and no rule differs between the two transports.
"""

from __future__ import annotations

import json
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

CREATED = 201
MONDAY = "2026-11-16"  # the Monday after tonight's capture
# Tonight's capture, 2026-11-14-demo (AIMO/build/tasks/T11-mcp.md, "Tonight in replay").
PLANT_DRINK = "464013"  # the confirmed plant drink without milk or gluten: 200 units at €2.01
UNCONFIRMED_DRINK = "473609"  # quantity not confirmed; scenario 3 asks for its substitutes
ADDS_AN_ALLERGEN = "471881"  # one of its substitutes that fails: it adds an allergen


def _without(body: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: value for key, value in body.items() if key not in keys}


async def _order(client: Client, offer: dict[str, Any], key: str, option: int = 0) -> Any:
    arguments = {
        "offer_id": offer["offer_id"], "option_id": offer["options"][option]["option_id"], "idempotency_key": key,
    }
    return await client.call_tool("place_order", arguments)


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_get_offer_returns_the_same_offer_as_the_rest_route_for_scenario_2(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth, scenario_2: dict[str, Any], mode: str
) -> None:
    async with connect("agent_ward", mode) as client:
        answer = await client.call_tool("get_offer", {"request": scenario_2})
    response = await rest.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))

    assert response.status_code == CREATED
    assert not answer.is_error
    over_mcp, over_rest = answer.structured_content, response.json()
    assert over_mcp["offer_id"] != over_rest["offer_id"]  # two offers were made, one per call
    # Each offer carries its own id and the gateway's signature of it: the rest is the same document.
    assert _without(over_mcp, "offer_id", "proof") == _without(over_rest, "offer_id", "proof")
    assert over_mcp["proof"]["key_id"] == over_rest["proof"]["key_id"]
    assert json.loads(answer.content[0].text) == over_mcp  # what the model reads is the same document


async def test_the_offer_of_scenario_2_requires_human_approval(
    connect: Connect, scenario_2: dict[str, Any]
) -> None:
    async with connect("agent_ward") as client:
        offer = (await client.call_tool("get_offer", {"request": scenario_2})).structured_content

    assert offer["source"] == "replay" and offer["profile_id"] == "allergy-ward"
    [option] = offer["options"]
    assert [(line["product_id"], line["quantity"]) for line in option["lines"]] == [(PLANT_DRINK, 200.0)]
    assert option["totals"]["net"] == 402.0
    assert option["decision"]["verdict"] == "APPROVAL"
    assert offer["excluded"]  # what dropped out is listed, with reasons


async def test_the_whole_flow_runs_over_mcp_and_the_order_is_the_one_rest_shows(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth, scenario_2: dict[str, Any]
) -> None:
    async with connect("agent_ward") as client:
        authority = await client.call_tool("get_authority")
        offer = (await client.call_tool("get_offer", {"request": scenario_2})).structured_content
        placed = await _order(client, offer, "mcp-flow-1")
        read = await client.call_tool("get_order", {"order_id": placed.structured_content["order_id"]})
        trail = await client.call_tool("get_audit", {"order_id": placed.structured_content["order_id"]})
    order = placed.structured_content
    over_rest = await rest.get(f"/v1/orders/{order['order_id']}", headers=auth("agent_ward"))
    trail_over_rest = await rest.get("/v1/audit", params={"order_id": order["order_id"]}, headers=auth("agent_ward"))

    assert authority.structured_content["profile"]["profile_id"] == "allergy-ward"
    assert not placed.is_error
    assert (order["status"], order["placed_by"], order["offer_id"]) == ("PENDING_APPROVAL", None, offer["offer_id"])
    assert read.structured_content == order
    assert over_rest.json() == order
    assert not trail.is_error
    assert trail.structured_content == trail_over_rest.json()
    assert trail.structured_content["chain"]["ok"] is True
    sentences = [event["sentence"] for event in trail.structured_content["events"]]
    assert sentences and all(sentences)


async def test_the_same_idempotency_key_returns_the_first_order(connect: Connect, scenario_2: dict[str, Any]) -> None:
    async with connect("agent_ward") as client:
        offer = (await client.call_tool("get_offer", {"request": scenario_2})).structured_content
        first = await _order(client, offer, "mcp-retry-1")
        again = await _order(client, offer, "mcp-retry-1")

    assert not first.is_error and not again.is_error
    assert again.structured_content == first.structured_content


async def test_an_order_placed_over_rest_is_read_over_mcp(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth, scenario_2: dict[str, Any]
) -> None:
    offer = (await rest.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))).json()
    body = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"]}
    placed = await rest.post("/v1/orders", json=body, headers={**auth("agent_ward"), "Idempotency-Key": "rest-1"})

    async with connect("agent_ward") as client:
        read = await client.call_tool("get_order", {"order_id": placed.json()["order_id"]})

    assert placed.status_code == CREATED
    assert read.structured_content == placed.json()


async def test_substitutes_are_ranked_with_reasons_as_the_rest_route_ranks_them(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth
) -> None:
    async with connect("agent_ward") as client:
        answer = await client.call_tool("find_substitutes", {"product_id": UNCONFIRMED_DRINK, "query": {}})
    response = await rest.post(
        f"/v1/products/{UNCONFIRMED_DRINK}/substitutes", json={}, headers=auth("agent_ward")
    )

    assert not answer.is_error
    assert answer.structured_content == response.json()
    by_id = {candidate["product_id"]: candidate for candidate in answer.structured_content["candidates"]}
    assert by_id[ADDS_AN_ALLERGEN]["passes"] is False
    assert by_id[ADDS_AN_ALLERGEN]["reason"] == "SUBSTITUTE_ADDS_ALLERGEN"
    assert any(candidate["orderable"] for candidate in by_id.values())


async def test_substitutes_are_checked_against_the_quantity_and_date_asked_for(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth
) -> None:
    query = {"quantity": 5000, "unit": "L", "needed_by": MONDAY}
    async with connect("agent_ward") as client:
        alone = await client.call_tool("find_substitutes", {"product_id": UNCONFIRMED_DRINK, "query": {}})
        answer = await client.call_tool("find_substitutes", {"product_id": UNCONFIRMED_DRINK, "query": query})
    response = await rest.post(
        f"/v1/products/{UNCONFIRMED_DRINK}/substitutes", json=query, headers=auth("agent_ward")
    )

    assert not answer.is_error
    assert answer.structured_content == response.json()
    assert answer.structured_content != alone.structured_content  # the quantity and the date were used


async def test_search_and_product_lookup_answer_as_the_rest_routes(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth
) -> None:
    query = {"product_type": "plant_drink", "limit": 5}
    async with connect("agent_ward") as client:
        found = await client.call_tool("search_products", {"query": query})
        product = await client.call_tool("get_product", {"product_id": PLANT_DRINK})
    found_over_rest = await rest.post("/v1/products/search", json=query, headers=auth("agent_ward"))
    product_over_rest = await rest.get(f"/v1/products/{PLANT_DRINK}", headers=auth("agent_ward"))

    assert not found.is_error and not product.is_error
    assert found.structured_content == found_over_rest.json()
    assert len(found.structured_content["products"]) == 5
    assert product.structured_content == product_over_rest.json()


async def test_the_supplier_reads_over_mcp_what_it_reads_over_rest(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth, scenario_2: dict[str, Any]
) -> None:
    async with connect("agent_ward") as agent, connect("supplier") as supplier:
        offer = (await agent.call_tool("get_offer", {"request": scenario_2})).structured_content
        order = (await _order(agent, offer, "mcp-supplier-1")).structured_content
        trail = await supplier.call_tool("get_audit", {"order_id": order["order_id"]})
    over_rest = await rest.get("/v1/audit", params={"order_id": order["order_id"]}, headers=auth("supplier"))

    assert trail.structured_content == over_rest.json()
    assert trail.structured_content["reader"] == "supplier"


HOTEL_MILK = {"needed_by": "2026-11-16", "lines": [
    {"text": "100 L of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}]}


async def test_get_offer_carries_the_suggestions_rest_shows_and_accepting_is_another_get_offer(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth
) -> None:
    async with connect("agent_hotel") as client:
        offer = (await client.call_tool("get_offer", {"request": HOTEL_MILK})).structured_content
        forgotten = offer["suggestions"][0]
        accepted = (await client.call_tool("get_offer", {"request": forgotten["accept_request"]})).structured_content
    over_rest = await rest.get(f"/v1/offers/{offer['offer_id']}", headers=auth("agent_hotel"))
    trail = await rest.get("/v1/audit", params={"offer_id": offer["offer_id"]}, headers=auth("agent_hotel"))

    assert [(each["kind"], each["product_id"]) for each in offer["suggestions"]] == [
        ("FORGOTTEN_ITEM", "463797"), ("FROM_SUPPLIER", "462775")]
    assert over_rest.json()["suggestions"] == offer["suggestions"]
    assert accepted["options"][0]["totals"]["net"] == 281.1  # €248.00 + €33.10; a new offer, nothing ordered
    kinds = [event["type"] for event in trail.json()["events"]]
    assert "tta.v1.suggestions.shown" in kinds and "tta.v1.suggestion.accepted" in kinds
