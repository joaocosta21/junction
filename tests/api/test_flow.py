"""The whole flow by HTTP in replay: authority, offer, order, approval, order, audit (SPEC sections 8 and 13).

Scores on the 30% "full request → lookup → order/approval flow … not just isolated pieces".
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]


def test_scenario_1_goes_from_authority_to_an_approved_order_with_a_sentence_for_every_step(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow, place_order: Flow,
    hotel_approver_by_role: dict[str, str],
) -> None:
    # Authority: what the agent may decide alone.
    authority = client.get("/v1/authority", headers=auth("agent_hotel"))
    assert authority.status_code == 200
    assert authority.json()["profile"]["profile_id"] == "hotel-kitchen"
    assert authority.json()["rules"]

    # Offer: live price and availability, a verdict per option.
    offer = make_offer(client, "agent_hotel", scenario_1)
    best = offer["options"][0]
    assert offer["profile_id"] == "hotel-kitchen"
    assert offer["source"] == "replay"
    assert best["kind"] == "BEST_CONFIRMED"
    assert best["decision"]["verdict"] == "APPROVAL"
    assert offer["excluded"] and all(exclusion["sentence"] for exclusion in offer["excluded"])
    assert client.get(f"/v1/offers/{offer['offer_id']}", headers=auth("agent_hotel")).json() == offer

    # Order: the agent may not place it alone, so it waits for a human.
    order = place_order(client, "agent_hotel", offer, "scenario-1")
    assert order["status"] == "PENDING_APPROVAL"
    assert order["placed_by"] is None
    assert order["approval_id"]

    # Approval: the queue names the roles, and each human asked for approves.
    queue = client.get("/v1/approvals", params={"status": "pending"}, headers=auth("hotel_purchasing"))
    assert queue.status_code == 200
    approval = next(entry for entry in queue.json() if entry["approval_id"] == order["approval_id"])
    assert approval["required_roles"] and approval["reasons"]
    decided = order
    for role in approval["required_roles"]:
        response = client.post(
            f"/v1/approvals/{approval['approval_id']}/decision",
            json={"decision": "APPROVE", "note": "Approved for the weekend."},
            headers=auth(hotel_approver_by_role[role]),
        )
        assert response.status_code == 200, response.text
        decided = response.json()
    assert decided["status"] == "ORDERED"
    assert decided["placed_by"] == "HUMAN_APPROVAL"

    # Order again: the record the agent reads.
    read = client.get(f"/v1/orders/{order['order_id']}", headers=auth("agent_hotel"))
    assert read.status_code == 200
    assert read.json()["status"] == "ORDERED"
    assert read.json()["reliance"]

    # Audit: one sentence per step, and a chain that verifies.
    audit = client.get("/v1/audit", params={"order_id": order["order_id"]}, headers=auth("agent_hotel"))
    assert audit.status_code == 200
    view = audit.json()
    types = [event["type"] for event in view["events"]]
    for step in (
        "request.parsed", "lookup.performed", "offer.created", "policy.evaluated", "approval.requested",
        "approval.decided", "order.confirmed",
    ):
        assert f"tta.v1.{step}" in types, step
    assert all(event["sentence"].strip() for event in view["events"])
    assert view["reader"] == "buyer"
    assert view["chain"]["ok"] is True


def test_scenario_2_ends_ordered_by_the_agent_with_no_approval(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow, place_order: Flow
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)
    chosen = offer["options"][0]
    assert chosen["decision"]["verdict"] == "AUTO"
    assert all(
        finding["relation"] == "FREE_FROM"
        for line in chosen["lines"]
        for finding in line["allergen_check"]["findings"]
    )

    order = place_order(client, "agent_ward", offer, "scenario-2")

    assert order["status"] == "ORDERED"
    assert order["placed_by"] == "AGENT"
    assert order["approval_id"] is None
    assert client.get("/v1/approvals", headers=auth("ward_dietitian")).json() == []
    view = client.get("/v1/audit", params={"order_id": order["order_id"]}, headers=auth("agent_ward")).json()
    placed = [event for event in view["events"] if event["type"] == "tta.v1.order.placed_by_agent"]
    assert len(placed) == 1
    assert "within its authority" in placed[0]["sentence"]
    assert not [event for event in view["events"] if event["type"].startswith("tta.v1.approval.")]


def test_every_option_of_an_offer_gets_its_own_policy_event(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow
) -> None:
    offer = make_offer(client, "agent_hotel", scenario_1)

    view = client.get("/v1/audit", params={"offer_id": offer["offer_id"]}, headers=auth("agent_hotel")).json()

    types = [event["type"] for event in view["events"]]
    assert types[:3] == ["tta.v1.request.parsed", "tta.v1.lookup.performed", "tta.v1.offer.created"]
    assert types.count("tta.v1.policy.evaluated") == len(offer["options"]) >= 2
    assert view["offer_id"] == offer["offer_id"]


def test_the_money_and_quantities_of_an_offer_are_json_numbers(
    client: TestClient, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    option = make_offer(client, "agent_ward", scenario_2)["options"][0]

    assert isinstance(option["totals"]["net"], float)
    assert isinstance(option["lines"][0]["quantity"], float)
    assert option["totals"]["currency"] == "EUR"
