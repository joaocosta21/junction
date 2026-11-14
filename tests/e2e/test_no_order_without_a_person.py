"""With the shipped profiles no path places an order without a person.

Valio Aimo, 14 Nov 2026: "for now deactivate automatic order but you can suggest orders the final submition should
always have the input from the user." Ordering alone is a buyer setting that every shipped profile leaves off
(rule F-10). This test walks the paths that can place an order in the demo app, each with a request that is
within every limit and fully confirmed, where the agent would order alone if the setting were on:
REST, the agent run, a standing-order renewal and a menu plan. The MCP path is `tests/mcp/test_flow.py`.
Replay over tonight's capture, at the recording's own clock.
"""

from __future__ import annotations

from typing import Any

MENU = {"dishes": [{"dish_id": "oven_pancake", "servings": 50}], "needed_by": "2026-11-16"}
WEEKLY_MILK = {
    "name": "Milk for breakfast",
    "request": {"lines": [{"text": "100 L of 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}]},
}


def _waits_for_a_person(order: dict[str, Any]) -> None:
    assert (order["status"], order["placed_by"]) == ("PENDING_APPROVAL", None), order["status_sentence"]
    assert order["approval_id"] and order["decision"]["verdict"] == "APPROVAL"
    assert order["decision"]["required_roles"]


def test_rest_agent_run_renewal_and_menu_plan_each_leave_the_order_waiting_for_a_person(
    demo: Any, texts: Any, fired: Any, event_types: Any
) -> None:
    client = demo.client

    # REST: scenario 2, €402.00, every statement confirmed, within the ward's limits.
    rest = demo.order("ward", demo.offer("ward", texts.scenario_2_request))
    _waits_for_a_person(rest)
    assert {rule["rule_id"] for rule in rest["decision"]["fired"]} == {"F-10"}

    # The agent run on the pasted sentence of the same scenario.
    run = demo.run_agent("ward", texts.scenario_2)
    assert run["order_status"] == "PENDING_APPROVAL"

    # A standing order renewed at its usual quantity.
    hotel = demo.headers("hotel")
    created = client.post("/v1/standing-orders", json=WEEKLY_MILK, headers=hotel)
    assert created.status_code == 201, created.text
    renewed = client.post(
        f"/v1/standing-orders/{created.json()['standing_order_id']}/renew", json={}, headers=hotel
    )
    assert renewed.status_code == 201, renewed.text
    _waits_for_a_person(renewed.json()["order"])

    # A menu plan: the plan orders nothing, and the order of its offer waits like any other.
    planned = client.post("/v1/menus/plan", json=MENU, headers=hotel)
    assert planned.status_code == 200, planned.text
    plan = planned.json()
    assert plan["offer_id"] is not None
    _waits_for_a_person(demo.order("hotel", demo.get_offer("hotel", plan["offer_id"])))

    # Nothing in either buyer's book was placed by the agent, and no event says so.
    for who in ("ward", "hotel"):
        orders = demo.orders(who)
        assert orders and all(order["placed_by"] is None for order in orders)
        assert all(order["status"] == "PENDING_APPROVAL" for order in orders)
        for order in orders:
            assert "order.placed_by_agent" not in event_types(demo.audit(who, order["order_id"]))
