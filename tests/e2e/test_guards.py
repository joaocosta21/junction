"""The two guards of SPEC section 13: an agent cannot approve, and a retried order is placed once."""

from __future__ import annotations

from typing import Any

from tta.contracts.common import OrderStatus


def test_guard_an_agent_token_on_the_decision_route_is_not_authorised_and_the_attempt_is_recorded(
    demo: Any, texts: Any, assert_problem: Any, event_types: Any
) -> None:
    run = demo.run_agent("hotel", texts.scenario_1)  # from the pasted sentence: waits for a human
    order = demo.get_order("hotel", run["order_id"])

    for decision in ("APPROVE", "REJECT"):
        assert_problem(demo.decide("hotel", order["approval_id"], decision), "not-authorised", 403)

    assert demo.get_order("hotel", order["order_id"])["status"] == OrderStatus.PENDING_APPROVAL
    assert [approval["approval_id"] for approval in demo.pending("hotel:purchasing_manager")] == [order["approval_id"]]
    trail = demo.audit("hotel", order["order_id"])
    assert event_types(trail)[-2:] == ["authorisation.refused", "authorisation.refused"]
    assert all(event["sentence"].strip() for event in trail["events"])


def test_guard_the_same_idempotency_key_twice_places_one_order(demo: Any, texts: Any, event_types: Any) -> None:
    offer = demo.offer("ward", texts.scenario_2_request)

    first = demo.order("ward", offer, key="retry-of-one-order")
    second = demo.order("ward", offer, key="retry-of-one-order")

    assert first["order_id"] == second["order_id"]
    assert first["status"] == second["status"] == OrderStatus.ORDERED
    assert [order["order_id"] for order in demo.orders("ward")] == [first["order_id"]]
    assert event_types(demo.audit("ward", first["order_id"])).count("order.placed_by_agent") == 1

