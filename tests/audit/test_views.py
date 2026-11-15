"""The two readers of SPEC section 9: the buyer sees everything about its own requests, the supplier a subset."""

from __future__ import annotations

import json
import re
from decimal import Decimal

import pytest

from tta.audit import AuditTrail
from tta.contracts.audit import ActorKind, AuditContext, AuditEventType, AuditView
from tta.contracts.common import AuditReader, OrderStatus, PlacedBy, Unit
from tta.contracts.errors import InvalidRequest
from tta.contracts.request import PurchaseRequest, RequestLine

LIMIT_VALUES = ("750", "3000", "3,000", "90%", "min_fill_ratio", "max_order_net_eur", "max_daily_net_eur")
ALLERGEN_EXCLUSIONS = re.compile(r"\b(AM|AW|STRICT)\b|exclude_allergens|excluded_allergens|allergen_strictness")
# The role is shown since S4 (Valio, 14 Nov: "all the steps and decisions"); the name, the id and the note are not.
APPROVER_DETAILS = ("Maija", "Virtanen", "human:maija", "Weekly volume")


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
    assert "excluding allergens milk and cereals containing gluten (strict rule)" in ward
    assert '"exclude_allergens": ["AM", "AW"]' in ward
    assert '"ALLERGEN_DECLARED": 2' in ward


def test_the_supplier_sees_what_was_ordered_and_the_statements_it_relied_on(hotel_flow: AuditTrail) -> None:
    confirmed = hotel_flow.view(AuditReader.SUPPLIER, order_id="ord_1").events[-1]

    order = confirmed.facts["order"]
    assert confirmed.sentence == (
        "Order ord_1 is ordered, with approval by a person of the buyer: "
        "1,000 pcs of 464306 for €1,010.00 net. "
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


def test_the_supplier_sees_which_role_decided_but_not_who(hotel_flow: AuditTrail) -> None:
    buyer = hotel_flow.view(AuditReader.BUYER, order_id="ord_1").events[6]
    supplier = hotel_flow.view(AuditReader.SUPPLIER, order_id="ord_1").events[6]

    assert buyer.type == supplier.type == "tta.v1.approval.decided"
    assert (buyer.actor.id, buyer.actor.role, buyer.actor.display_name) == (
        "human:maija", "purchasing_manager", "Maija Virtanen",
    )
    assert supplier.actor.kind is ActorKind.HUMAN
    assert (supplier.actor.id, supplier.actor.role, supplier.actor.display_name) == (
        "buyer-human", "purchasing_manager", "The buyer's purchasing manager",
    )
    assert supplier.facts["approval_decision"] == {
        "decision": "APPROVE", "roles": ["purchasing_manager"], "option_id": "opt_2",
        "decided_at": "2026-11-14T02:52:00+02:00",
    }
    assert supplier.hash == buyer.hash and supplier.id == buyer.id


def test_the_supplier_sees_the_agent_and_every_rule_that_fired(hotel_flow: AuditTrail) -> None:
    buyer = hotel_flow.view(AuditReader.BUYER, order_id="ord_1").events[6]
    supplier = hotel_flow.view(AuditReader.SUPPLIER, order_id="ord_1").events
    requested = supplier[5]

    assert buyer.rule_ids == ("F-01", "P-01")
    assert supplier[6].rule_ids == buyer.rule_ids
    assert requested.rule_ids == ("P-01", "P-03")
    assert requested.actor.model_dump(exclude_none=True) == {"kind": ActorKind.AGENT, "id": "agent:hotel-kitchen"}
    decision = supplier[4].facts["decision"]
    assert (decision["verdict"], decision["rule_ids"], decision["required_roles"]) == (
        "APPROVAL", ["P-01", "P-03"], ["purchasing_manager"],
    )
    assert [sorted(rule) for rule in decision["rules"]] == [
        ["approver_role", "fixed", "product_id", "rule_id", "title", "verdict"],
    ] * 2  # never a rule's sentence or the facts it read: both hold the limit


def test_a_supplier_rule_is_explained_without_the_buyer_s_wording(trail: AuditTrail, samples) -> None:
    option = samples.unconfirmed_option()

    trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway, AuditContext(offer_id="off_1", option=option))

    assert trail.view(AuditReader.SUPPLIER).events[0].sentence == (
        "The buyer's rules were checked for option opt_2: a person of the buyer must approve this order. "
        "Rules that applied: F-01, a fixed rule (rule F-01), on product 464306: approval by a person of the buyer. "
        "P-01, a rule the buyer set (rule P-01; the amount is not shown): approval by a person of the buyer. "
        "The strictest outcome among the rules that applied decides."
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
    within_authority = samples.option("opt_3", (samples.line("464056", "200", "2.14"),), samples.decision(), "200")
    other = samples.order(within_authority, OrderStatus.ORDERED, order_id="ord_9", placed_by=PlacedBy.AGENT,
                          approval_id=None)
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


def test_a_view_says_whether_the_chain_verifies_and_counts_only_its_own_events(
    hotel_flow: AuditTrail, ward_flow: AuditTrail
) -> None:
    view = hotel_flow.view(AuditReader.BUYER, order_id="ord_1")
    everything = hotel_flow.view(AuditReader.SUPPLIER)

    assert (view.chain.ok, view.chain.checked, view.chain.first_bad_event_id) == (True, 8, None)
    assert view.chain.sentence == (
        "The audit trail is intact: each of the 8 events shown here matches its hash, and the chain they belong "
        "to verifies."
    )
    assert everything.chain.checked == len(everything.events) == hotel_flow.verify_chain().checked == 12


def test_a_buyer_view_over_every_buyer_is_refused(hotel_flow: AuditTrail) -> None:
    with pytest.raises(InvalidRequest, match="never sees another buyer"):
        hotel_flow.view(AuditReader.BUYER)


def test_a_reader_given_as_text_gets_its_own_view_and_an_unknown_reader_gets_none(hotel_flow: AuditTrail) -> None:
    as_text = hotel_flow.view("supplier", order_id="ord_1")

    assert as_text.reader is AuditReader.SUPPLIER
    assert as_text.events == hotel_flow.view(AuditReader.SUPPLIER, order_id="ord_1").events
    with pytest.raises(InvalidRequest, match="two readers"):
        hotel_flow.view("auditor", order_id="ord_1")


def test_the_supplier_reads_the_claim_codes_asked_for_and_never_the_buyer_s_own_terms(
    trail: AuditTrail, samples
) -> None:
    by_name = RequestLine(text="20 kg of biscuits without peanuts", name_terms=("biscuits", "without", "peanuts"),
                          required_claims=("FREE_FROM_PEANUTS",), quantity=Decimal("20"), unit=Unit.KG)
    by_type = RequestLine(text="5 l of oat drink, gluten free", product_type="oat_drink", product_ids=("468319",),
                          required_claims=("FREE_FROM_GLUTEN",), quantity=Decimal("5"), unit=Unit.L)
    context = AuditContext(profile_id="allergy-ward", offer_id="off_3",
                           request=PurchaseRequest(lines=(by_name, by_type)))

    trail.record(AuditEventType.REQUEST_RECEIVED, samples.agent_ward, context)
    trail.record(AuditEventType.REQUEST_PARSED, samples.gateway, context)
    buyer = trail.view(AuditReader.BUYER, offer_id="off_3")
    supplier = trail.view(AuditReader.SUPPLIER, offer_id="off_3")

    assert supplier.events[1].sentence == (
        "The request was read as: 20 kg of a product described in free text with claim FREE_FROM_PEANUTS; "
        "5 litres of product 468319 with claim FREE_FROM_GLUTEN."
    )
    assert supplier.events[1].facts["request"]["lines"] == [
        {"product_type": None, "product_ids": [], "quantity": 20.0, "unit": "KG", "pack": "BULK",
         "required_claims": ["FREE_FROM_PEANUTS"], "required_labels": []},
        {"product_type": "oat_drink", "product_ids": ["468319"], "quantity": 5.0, "unit": "L", "pack": "BULK",
         "required_claims": ["FREE_FROM_GLUTEN"], "required_labels": []},
    ]
    shown = _readable(supplier)
    assert [word for word in ("peanuts", "biscuit", "gluten", "name_terms", "without") if word in shown] == []
    assert 'products named "biscuits without peanuts" with claim FREE_FROM_PEANUTS' in buyer.events[1].sentence
    assert buyer.events[1].facts["request"]["lines"][0]["name_terms"] == ["biscuits", "without", "peanuts"]


def test_the_supplier_sees_an_agent_by_id_and_kind_only_and_no_name_of_a_human(hotel_flow: AuditTrail) -> None:
    actors = [event.actor.model_dump(exclude_none=True) for event in hotel_flow.view(AuditReader.SUPPLIER).events]

    assert {"kind": ActorKind.AGENT, "id": "agent:hotel-kitchen"} in actors
    assert {"kind": ActorKind.HUMAN, "id": "buyer-human", "role": "purchasing_manager",
            "display_name": "The buyer's purchasing manager"} in actors
    assert [actor for actor in actors if "Hotel kitchen agent" in actor.values()] == []
    assert [actor for actor in actors if actor["kind"] is ActorKind.HUMAN and actor["id"] != "buyer-human"] == []


def test_an_event_recorded_with_only_an_id_is_found_by_the_profile_view_when_what_it_names_is_stored(
    trail: AuditTrail, store, samples
) -> None:
    store.save_order(samples.order(samples.ward_option(), OrderStatus.ORDERED, order_id="ord_2",
                                   profile_id="allergy-ward", offer_id="off_2", placed_by=PlacedBy.AGENT,
                                   approval_id=None))
    store.save_offer(samples.hotel_offer())
    store.save_approval(samples.approval())

    by_order = trail.record(AuditEventType.ORDER_CONFIRMED, samples.gateway, AuditContext(order_id="ord_2"))
    by_offer = trail.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext(offer_id="off_1"))
    by_approval = trail.record(AuditEventType.EVIDENCE_ATTACHED, samples.gateway, AuditContext(approval_id="apr_1"))
    unknown = trail.record(AuditEventType.ORDER_CONFIRMED, samples.gateway, AuditContext(order_id="ord_unknown"))
    stated = trail.record(AuditEventType.ORDER_CONFIRMED, samples.gateway,
                          AuditContext(order_id="ord_2", profile_id="hotel-kitchen"))

    assert [event.data.profile_id for event in (by_order, by_offer, by_approval, unknown, stated)] == [
        "allergy-ward", "hotel-kitchen", "hotel-kitchen", None, "hotel-kitchen",
    ]
    assert [event.id for event in trail.view(AuditReader.BUYER, profile_id="allergy-ward").events] == [by_order.id]
    assert [event.id for event in trail.view(AuditReader.BUYER, profile_id="hotel-kitchen").events] == [
        by_offer.id, by_approval.id, stated.id,
    ]
    assert [event.id for event in trail.view(AuditReader.BUYER, order_id="ord_unknown").events] == [unknown.id]
