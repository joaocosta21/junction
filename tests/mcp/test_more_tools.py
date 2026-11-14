"""The customer, menus and standing orders as MCP tools: the same service calls, limits and refusals as REST.

Scores on the 15% "open, documented standards" (an MCP host reaches everything a REST client does) and the 20%
"autonomy and controls" (no tool approves; a renewal waits for a person as any order does).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import httpx
import pytest
from mcp.client import Client

from tta.api.hooks import SurfaceContext
from tta.api.mcp_surface import NO_STANDING_ORDERS, GatewayTools
from tta.api.signing import JWKS_PATH, verifies
from tta.api.wiring import Parts
from tta.contracts.errors import SupplierUnavailable
from tta.standing.service import MAX_STANDING_ORDERS_PER_BUYER

pytestmark = pytest.mark.anyio

Connect = Callable[..., AbstractAsyncContextManager[Client]]
Auth = Callable[[str], dict[str, str]]
PROBLEMS = "https://tta.example/problems/"
WEEKLY = {
    "name": "Weekly lactose-free milk", "cadence_days": 7,
    "request": {"lines": [{"text": "100 litres of lactose-free milk 469363", "product_ids": ["469363"],
                           "quantity": 100, "unit": "L"}]},
}
TWO_DISHES = {"dishes": [{"dish_id": "lasagne", "servings": 50}, {"dish_id": "oven_pancake", "servings": 50}]}


def _six_lines() -> dict[str, Any]:
    line = WEEKLY["request"]["lines"][0]
    return {**WEEKLY, "request": {"lines": [line] * 6}}


async def test_get_customer_answers_what_the_rest_route_answers(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth
) -> None:
    async with connect("agent_ward") as client:
        answer = await client.call_tool("get_customer", {})
    over_rest = await rest.get("/v1/customers/allergy-ward", headers=auth("agent_ward"))

    assert not answer.is_error
    assert answer.structured_content == over_rest.json()
    assert answer.structured_content["customer"]["synthetic"] is True


async def test_the_supplier_reads_no_customer_over_mcp(connect: Connect) -> None:
    async with connect("supplier") as client:
        answer = await client.call_tool("get_customer", {})

    assert answer.is_error and answer.structured_content["type"] == PROBLEMS + "not-authorised"


async def test_plan_menu_plans_two_dishes_and_its_offer_is_ordered_like_any_other(connect: Connect) -> None:
    async with connect("agent_hotel") as client:
        plan = (await client.call_tool("plan_menu", {"menu": TWO_DISHES})).structured_content
        offer_id = plan["offer_id"]
        audit = (await client.call_tool("get_audit", {"offer_id": offer_id})).structured_content

    assert len(plan["lines"]) == 7 and plan["illustrative"] is True
    assert any(event["type"].endswith("offer.created") for event in audit["events"])


async def test_an_approver_cannot_plan_a_menu_or_set_up_or_renew_a_standing_order(connect: Connect) -> None:
    async with connect("hotel_purchasing") as client:
        answers = [
            await client.call_tool("plan_menu", {"menu": TWO_DISHES}),
            await client.call_tool("set_up_standing_order", {"standing_order": WEEKLY}),
            await client.call_tool("renew_standing_order", {"standing_order_id": "so_nobody", "renewal": {}}),
        ]

    for answer in answers:
        assert answer.is_error and answer.structured_content["type"] == PROBLEMS + "not-authorised"


async def test_a_standing_order_set_up_over_mcp_is_the_one_rest_lists_and_a_renewal_waits_for_a_person(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth
) -> None:
    async with connect("agent_hotel") as client:
        standing = (await client.call_tool("set_up_standing_order", {"standing_order": WEEKLY})).structured_content
        listed = (await client.call_tool("list_standing_orders", {})).structured_content
        renewed = await client.call_tool(
            "renew_standing_order", {"standing_order_id": standing["standing_order_id"], "renewal": {}}
        )
    over_rest = await rest.get("/v1/standing-orders", headers=auth("agent_hotel"))
    keys = (await rest.get(JWKS_PATH)).json()

    assert listed["standing_orders"] == over_rest.json() == [standing]
    assert not renewed.is_error
    outcome = renewed.structured_content
    # Ordering alone is off: the renewal is an order like any other and waits for a person. No tool approves it.
    assert outcome["order"]["status"] == "PENDING_APPROVAL" and outcome["order"]["placed_by"] is None
    assert verifies(outcome["order"], keys) and verifies(outcome["offer"], keys)
    order = await rest.get(f"/v1/orders/{outcome['order']['order_id']}", headers=auth("agent_hotel"))
    assert order.json()["status"] == "PENDING_APPROVAL"


async def test_the_limits_of_a_set_up_are_those_of_rest_and_are_shared_with_it(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth
) -> None:
    # Another address than the REST client's: one address makes at most 20 such calls a minute, over both ways in.
    async with connect("agent_ward", visitor="203.0.113.7") as client:
        too_long = await client.call_tool("set_up_standing_order", {"standing_order": _six_lines()})
        for _ in range(MAX_STANDING_ORDERS_PER_BUYER // 2):
            assert not (await client.call_tool("set_up_standing_order", {"standing_order": WEEKLY})).is_error
        for _ in range(MAX_STANDING_ORDERS_PER_BUYER // 2):
            created = await rest.post("/v1/standing-orders", json=WEEKLY, headers=auth("agent_ward"))
            assert created.status_code == 201, created.text
        one_more = await client.call_tool("set_up_standing_order", {"standing_order": WEEKLY})
    over_rest = await rest.post("/v1/standing-orders", json=WEEKLY, headers=auth("agent_ward"))

    assert too_long.is_error and "at most 5 lines; this one has 6" in too_long.structured_content["detail"]
    assert one_more.is_error and one_more.structured_content["type"] == PROBLEMS + "invalid-request"
    assert one_more.structured_content["detail"] == over_rest.json()["detail"]  # the twenty-first, either way
    assert "already has 20 standing orders" in one_more.structured_content["detail"]


async def test_another_buyers_standing_order_reads_as_one_nobody_set_up(connect: Connect) -> None:
    async with connect("agent_hotel") as hotel, connect("agent_ward") as ward:
        standing = (await hotel.call_tool("set_up_standing_order", {"standing_order": WEEKLY})).structured_content
        renewal = {"standing_order_id": standing["standing_order_id"], "renewal": {}}
        answer = await ward.call_tool("renew_standing_order", renewal)
        listed = (await ward.call_tool("list_standing_orders", {})).structured_content

    assert answer.is_error and answer.structured_content["type"] == PROBLEMS + "not-found"
    assert listed["standing_orders"] == []


def test_a_surface_built_without_the_standing_orders_refuses_those_tools(parts: Parts) -> None:
    context = SurfaceContext(settings=parts.settings, service=parts.service, identify=parts.tokens.identify)
    tools = GatewayTools(context.service, context.identify, context.standing, context.signer)

    assert context.standing is None and context.signer is None
    with pytest.raises(SupplierUnavailable, match="no standing orders"):
        tools._standing_orders()
    assert NO_STANDING_ORDERS.startswith("This gateway serves no standing orders here")
