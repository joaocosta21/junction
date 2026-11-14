"""The two readers of SPEC section 9: the buyer sees everything about its own requests, the supplier a subset."""

from __future__ import annotations

import json
import re

import pytest

from tta.audit import AuditTrail
from tta.contracts.audit import ActorKind, AuditContext, AuditEventType, AuditView
from tta.contracts.common import AuditReader, OrderStatus, PlacedBy
from tta.contracts.errors import InvalidRequest

LIMIT_VALUES = ("750", "3000", "3,000", "90%", "min_fill_ratio", "max_order_net_eur", "max_daily_net_eur")
ALLERGEN_EXCLUSIONS = re.compile(r"\b(AM|AW|STRICT)\b|exclude_allergens|excluded_allergens|allergen_strictness")
APPROVER_DETAILS = ("Maija", "Virtanen", "human:maija", "Weekly volume", "purchasing")


def _readable(view: AuditView) -> str:
    """What a reader is shown, as text: ids and hashes are left out because they are random."""
    shown = [
        {"actor": event.actor.model_dump(mode="json"), "sentence": event.sentence, "rule_ids": event.rule_ids,
         "facts": event.facts}
        for event in view.events
    ]
    return json.dumps(shown, ensure_ascii=False)


def test_the_supplier_view_has_no_limit_no_allergen_exclusion_no_approver_name_or_note(
    hotel_flow: AuditTrail, ward_flow: AuditTrail
) -> None:
    view = hotel_flow.view(AuditReader.SUPPLIER)

    shown = _readable(view)

    assert len(view.events) == 12
    assert [value for value in LIMIT_VALUES if value in shown] == []
    assert ALLERGEN_EXCLUSIONS.search(shown) is None
    assert [value for value in APPROVER_DETAILS if value in shown] == []


def test_the_buyer_view_has_the_limits_the_exclusions_the_approver_and_the_note(
    hotel_flow: AuditTrail, ward_flow: AuditTrail
) -> None:
    hotel = _readable(hotel_flow.view(AuditReader.BUYER, order_id="ord_1"))
    ward = _readable(ward_flow.view(AuditReader.BUYER, profile_id="allergy-ward"))

    assert "€750.00 limit" in hotel
    assert '"max_order_net_eur": 750.0' in hotel and '"max_daily_net_eur": 3000.0' in hotel
    assert "Maija Virtanen (purchasing manager)" in hotel and "Weekly volume, OK." in hotel
    assert "excluding allergens AM and AW (STRICT)" in ward
    assert '"exclude_allergens": ["AM", "AW"]' in ward
    assert '"ALLERGEN_DECLARED": 2' in ward


def test_the_supplier_sees_what_was_ordered_and_the_statements_it_relied_on(hotel_flow: AuditTrail) -> None:
    confirmed = hotel_flow.view(AuditReader.SUPPLIER, order_id="ord_1").events[-1]

    order = confirmed.facts["order"]
    assert confirmed.sentence == (
        "Order ord_1 is ordered, with approval by a human at the buyer: 1,000 ST of 464306 for €1,010.00 net. "
        "Price and availability were checked again and had not changed. "
        "The order is recorded in the gateway's order book."
    )
    assert (order["agent_id"], order["placed_by"], order["status"]) == (
        "agent:hotel-kitchen", "HUMAN_APPROVAL", "ORDERED",
    )
    assert order["option"]["lines"][0]["product_id"] == "464306"
    assert order["option"]["totals"]["net"] == 1010.0
    assert order["reliance"][0]["availability_state"] == "QUANTITY_NOT_CONFIRMED"
    assert order["reliance"][0]["time_now"] == "2026-11-14T02:52:00+02:00"
    assert "status_sentence" not in order and "decision" not in order


def test_the_supplier_sees_that_a_human_decided_but_not_who(hotel_flow: AuditTrail) -> None:
    buyer = hotel_flow.view(AuditReader.BUYER, order_id="ord_1").events[6]
    supplier = hotel_flow.view(AuditReader.SUPPLIER, order_id="ord_1").events[6]

    assert buyer.type == supplier.type == "tta.v1.approval.decided"
    assert (buyer.actor.id, buyer.actor.role, buyer.actor.display_name) == (
        "human:maija", "purchasing_manager", "Maija Virtanen",
    )
    assert supplier.actor.kind is ActorKind.HUMAN
    assert (supplier.actor.id, supplier.actor.role, supplier.actor.display_name) == (
        "buyer-human", None, "A human at the buyer",
    )
    assert supplier.facts["approval_decision"] == {
        "decision": "APPROVE", "option_id": "opt_2", "decided_at": "2026-11-14T02:52:00+02:00",
    }
    assert supplier.hash == buyer.hash and supplier.id == buyer.id


def test_the_supplier_sees_the_agent_and_only_the_rules_about_its_own_data(hotel_flow: AuditTrail) -> None:
    buyer = hotel_flow.view(AuditReader.BUYER, order_id="ord_1").events[6]
    supplier = hotel_flow.view(AuditReader.SUPPLIER, order_id="ord_1").events
    requested = supplier[5]

    assert buyer.rule_ids == ("F-01", "P-01")
    assert supplier[6].rule_ids == ("F-01",)
    assert requested.rule_ids == ()
    assert requested.actor.id == "agent:hotel-kitchen" and requested.actor.display_name == "Hotel kitchen agent"
    assert supplier[4].facts["decision"] == {
        "verdict": "APPROVAL", "rule_ids": [], "evaluated_at": "2026-11-14T02:52:00+02:00",
    }


def test_a_supplier_rule_is_explained_without_the_buyer_s_wording(trail: AuditTrail, samples) -> None:
    option = samples.unconfirmed_option()

    trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway, AuditContext(offer_id="off_1", option=option))

    assert trail.view(AuditReader.SUPPLIER).events[0].sentence == (
        "The buyer's rules were checked for option opt_2: a human at the buyer must approve this order. "
        "Fixed rule that applied: F-01 (a line's quantity is not confirmed)."
    )


def test_the_trail_of_an_order_includes_the_steps_before_the_order_existed(
    hotel_flow: AuditTrail, ward_flow: AuditTrail
) -> None:
    view = hotel_flow.view(AuditReader.BUYER, order_id="ord_1")

    assert (view.reader, view.order_id, view.offer_id) == (AuditReader.BUYER, "ord_1", None)
    assert [event.type.removeprefix("tta.v1.") for event in view.events] == [
        "request.received", "request.parsed", "lookup.performed", "offer.created", "policy.evaluated",
        "approval.requested", "approval.decided", "order.confirmed",
    ]


def test_the_trail_of_an_order_leaves_out_other_orders_of_the_same_offer(hotel_flow: AuditTrail, samples) -> None:
    other = samples.order(samples.partial_option(), OrderStatus.ORDERED, order_id="ord_9",
                          placed_by=PlacedBy.AGENT, approval_id=None)
    hotel_flow.record(AuditEventType.ORDER_PLACED_BY_AGENT, samples.agent_hotel, AuditContext(order=other))

    first = hotel_flow.view(AuditReader.BUYER, order_id="ord_1")
    second = hotel_flow.view(AuditReader.BUYER, order_id="ord_9")

    assert len(first.events) == 8
    assert [event.type.removeprefix("tta.v1.") for event in second.events][-2:] == [
        "policy.evaluated", "order.placed_by_agent",
    ]


def test_a_buyer_does_not_see_another_buyer(hotel_flow: AuditTrail, ward_flow: AuditTrail) -> None:
    hotel = hotel_flow.view(AuditReader.BUYER, profile_id="hotel-kitchen")
    ward = hotel_flow.view(AuditReader.BUYER, profile_id="allergy-ward")
    wrong = hotel_flow.view(AuditReader.BUYER, order_id="ord_2", profile_id="hotel-kitchen")

    assert (len(hotel.events), len(ward.events), len(wrong.events)) == (8, 4, 0)
    assert "allergy-ward" not in _readable(hotel) and "hotel-kitchen" not in _readable(ward)


def test_events_can_be_read_by_offer(hotel_flow: AuditTrail, ward_flow: AuditTrail) -> None:
    view = hotel_flow.view(AuditReader.SUPPLIER, offer_id="off_2")

    assert (view.order_id, view.offer_id) == (None, "off_2")
    assert [event.type.removeprefix("tta.v1.") for event in view.events] == [
        "request.parsed", "offer.created", "policy.evaluated", "order.placed_by_agent",
    ]


def test_a_view_says_whether_the_whole_chain_verifies(hotel_flow: AuditTrail) -> None:
    view = hotel_flow.view(AuditReader.BUYER, order_id="ord_1")

    assert (view.chain.ok, view.chain.checked, view.chain.first_bad_event_id) == (True, 8, None)
    assert view.chain.sentence == hotel_flow.verify_chain().sentence


def test_a_buyer_view_over_every_buyer_is_refused(hotel_flow: AuditTrail) -> None:
    with pytest.raises(InvalidRequest, match="never sees another buyer"):
        hotel_flow.view(AuditReader.BUYER)


def test_a_reader_given_as_text_gets_its_own_view_and_an_unknown_reader_gets_none(hotel_flow: AuditTrail) -> None:
    as_text = hotel_flow.view("supplier", order_id="ord_1")

    assert as_text.reader is AuditReader.SUPPLIER
    assert as_text.events == hotel_flow.view(AuditReader.SUPPLIER, order_id="ord_1").events
    with pytest.raises(InvalidRequest, match="two readers"):
        hotel_flow.view("auditor", order_id="ord_1")
