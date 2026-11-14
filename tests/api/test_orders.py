"""Placing and reading orders by HTTP: the idempotency key, one order per offer, the caller's own orders
(SPEC sections 2 and 8). Scores on Core 2: "moving from inquiry to commitment"."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]
Problem = Callable[..., dict[str, Any]]


def test_an_order_without_an_idempotency_key_is_an_invalid_request(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow, assert_problem: Problem
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)
    body = {"offer_id": offer["offer_id"], "option_id": "opt_1"}

    response = client.post("/v1/orders", json=body, headers=auth("agent_ward"))

    problem = assert_problem(response, "invalid-request", 422)
    assert "Idempotency-Key" in problem["detail"]
    assert client.get("/v1/orders", headers=auth("agent_ward")).json() == []


@pytest.mark.parametrize("key", ["", " ", "a key with spaces", "k" * 101, "semi;colon", "<b>"])
def test_an_idempotency_key_outside_the_allowed_form_is_an_invalid_request(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow, assert_problem: Problem, key: str
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)
    body = {"offer_id": offer["offer_id"], "option_id": "opt_1"}

    response = client.post("/v1/orders", json=body, headers=auth("agent_ward", key))

    assert_problem(response, "invalid-request", 422)
    assert client.get("/v1/orders", headers=auth("agent_ward")).json() == []


def test_the_same_key_twice_gives_the_same_order(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow, place_order: Flow
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)

    first = place_order(client, "agent_ward", offer, "retry.key:1_A-b")
    second = place_order(client, "agent_ward", offer, "retry.key:1_A-b")

    assert second == first
    listed = client.get("/v1/orders", headers=auth("agent_ward")).json()
    assert [order["order_id"] for order in listed] == [first["order_id"]]
    view = client.get("/v1/audit", params={"order_id": first["order_id"]}, headers=auth("agent_ward")).json()
    assert [event["type"] for event in view["events"]].count("tta.v1.order.placed_by_agent") == 1


def test_a_second_order_on_an_offer_that_has_one_is_refused(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow, place_order: Flow,
    assert_problem: Problem,
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)
    first = place_order(client, "agent_ward", offer, "key-1")
    body = {"offer_id": offer["offer_id"], "option_id": "opt_1"}

    response = client.post("/v1/orders", json=body, headers=auth("agent_ward", "key-2"))

    problem = assert_problem(response, "invalid-request", 422)
    assert first["order_id"] in problem["detail"]
    assert len(client.get("/v1/orders", headers=auth("agent_ward")).json()) == 1


def test_the_orders_of_the_callers_buyer_are_listed_newest_first(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], scenario_2: dict[str, Any], make_offer: Flow,
    place_order: Flow,
) -> None:
    first = place_order(client, "agent_ward", make_offer(client, "agent_ward", scenario_2), "key-1")
    second = place_order(client, "agent_ward", make_offer(client, "agent_ward", scenario_2), "key-2")
    other = place_order(client, "agent_hotel", make_offer(client, "agent_hotel", scenario_1), "key-1")

    ward = client.get("/v1/orders", headers=auth("agent_ward")).json()
    hotel = client.get("/v1/orders", headers=auth("hotel_purchasing")).json()

    assert [order["order_id"] for order in ward] == [second["order_id"], first["order_id"]]
    assert [order["order_id"] for order in hotel] == [other["order_id"]]


def test_an_approver_can_reject_and_nothing_is_ordered(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow, place_order: Flow
) -> None:
    order = place_order(client, "agent_hotel", make_offer(client, "agent_hotel", scenario_1), "key-1")

    response = client.post(
        f"/v1/approvals/{order['approval_id']}/decision",
        json={"decision": "REJECT", "note": "Too much for one delivery."},
        headers=auth("hotel_purchasing"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"
    assert client.get("/v1/approvals", params={"status": "PENDING"}, headers=auth("hotel_purchasing")).json() == []
    rejected = client.get("/v1/approvals", params={"status": "rejected"}, headers=auth("hotel_purchasing")).json()
    assert [approval["approval_id"] for approval in rejected] == [order["approval_id"]]


def test_an_approver_may_choose_another_option_of_the_same_offer(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow, place_order: Flow,
    hotel_approver_by_role: dict[str, str],
) -> None:
    offer = make_offer(client, "agent_hotel", scenario_1)
    order = place_order(client, "agent_hotel", offer, "key-1")
    other = offer["options"][1]["option_id"]

    response = client.post(
        f"/v1/approvals/{order['approval_id']}/decision", json={"decision": "APPROVE", "option_id": other},
        headers=auth("hotel_purchasing"),
    )

    assert response.status_code == 200
    decided = response.json()
    assert decided["option_id"] == other
    assert decided["status"] in ("ORDERED", "PENDING_APPROVAL")


def test_an_approval_status_nobody_knows_is_an_invalid_request(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    response = client.get("/v1/approvals", params={"status": "sideways"}, headers=auth("hotel_purchasing"))

    assert_problem(response, "invalid-request", 422)
    assert "sideways" not in response.text
