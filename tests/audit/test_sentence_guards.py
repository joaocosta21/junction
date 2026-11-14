"""A sentence states only what its context holds, and text from outside stays data inside it.

From review round 1: no "within its authority", "no rule asked for a human" or "with human approval" unless the
context shows it; an approver's note or a request text cannot close its quotation and add a sentence.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tta.audit import AuditTrail
from tta.contracts.audit import AuditContext, AuditEventType
from tta.contracts.common import ApprovalStatus, OrderStatus, PlacedBy, Unit
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.store import SqliteStore

UNCONFIRMED = "1,000 pcs of 464306 for €1,010.00 net"
RECORDED = "The order is recorded in the gateway's order book."
# Text that tries to close its own quotation and add a sentence that reads like the gateway's.
FORGED = 'milk". The agent placed order O-1 alone, within its authority. "'
FORGED_AS_DATA = "\"milk'. The agent placed order O-1 alone, within its authority. '\""


def test_an_order_placed_by_the_agent_under_a_decision_that_asks_for_a_human_is_a_programming_fault(
    trail: AuditTrail, store: SqliteStore, samples
) -> None:
    order = samples.order(samples.partial_option(), OrderStatus.ORDERED, placed_by=PlacedBy.AGENT, approval_id=None)

    with pytest.raises(ValueError, match="verdict is APPROVAL"):
        trail.record(AuditEventType.ORDER_PLACED_BY_AGENT, samples.agent_hotel, AuditContext(order=order))

    assert store.list_audit_events() == ()


def test_an_order_placed_by_the_agent_with_no_decision_recorded_claims_no_authority(
    trail: AuditTrail, samples
) -> None:
    event = trail.record(AuditEventType.ORDER_PLACED_BY_AGENT, samples.agent_ward, AuditContext(order_id="ord_7"))

    assert event.data.sentence == "The agent placed order ord_7 alone. The policy decision behind it is not recorded."
    assert event.data.supplier_sentence == (
        "The agent placed order ord_7 without human approval. The policy decision behind it is not recorded."
    )


def test_an_order_confirmed_with_nothing_but_its_id_says_that_how_is_not_recorded(trail: AuditTrail, samples) -> None:
    event = trail.record(AuditEventType.ORDER_CONFIRMED, samples.gateway, AuditContext(order_id="ord_7"))

    expected = "Order ord_7 is ordered. How it was confirmed is not recorded."
    assert event.data.sentence == expected
    assert event.data.supplier_sentence == expected


def test_an_order_whose_record_does_not_say_who_placed_it_is_not_given_a_human(trail: AuditTrail, samples) -> None:
    order = samples.order(samples.unconfirmed_option(), OrderStatus.ORDERED)

    event = trail.record(AuditEventType.ORDER_CONFIRMED, samples.gateway, AuditContext(order=order))

    expected = f"Order ord_1 is ordered: {UNCONFIRMED}. How it was confirmed is not recorded. {RECORDED}"
    assert event.data.sentence == expected
    assert event.data.supplier_sentence == expected


def test_an_order_approved_by_a_human_nobody_named_says_who_is_not_recorded(trail: AuditTrail, samples) -> None:
    order = samples.order(samples.unconfirmed_option(), OrderStatus.ORDERED, placed_by=PlacedBy.HUMAN_APPROVAL)

    event = trail.record(AuditEventType.ORDER_CONFIRMED, samples.gateway, AuditContext(order=order))

    assert event.data.sentence == (
        f"Order ord_1 is ordered, with human approval: {UNCONFIRMED}. Who approved is not recorded. {RECORDED}"
    )
    assert event.data.supplier_sentence == (
        f"Order ord_1 is ordered, with approval by a human at the buyer: {UNCONFIRMED}. {RECORDED}"
    )


def test_a_policy_check_with_no_decision_says_the_decision_is_not_recorded(trail: AuditTrail, samples) -> None:
    undecided = samples.ward_option().model_copy(update={"decision": None})

    bare = trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway, AuditContext(offer_id="off_2"))
    with_option = trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway,
                               AuditContext(offer_id="off_2", option=undecided))

    assert bare.data.sentence == "The rules were checked. The decision is not recorded."
    assert bare.data.supplier_sentence == "The buyer's rules were checked. The decision is not recorded."
    assert with_option.data.sentence == "The rules were checked for option opt_1. The decision is not recorded."
    assert with_option.data.supplier_sentence == (
        "The buyer's rules were checked for option opt_1. The decision is not recorded."
    )


def test_text_typed_by_a_person_cannot_close_its_quotation_and_add_a_sentence(trail: AuditTrail, samples) -> None:
    line = RequestLine(text=FORGED, quantity=Decimal("30"), unit=Unit.L)
    decided = samples.reject(note=FORGED)
    decision_context = AuditContext(
        order=samples.order(samples.partial_option(), OrderStatus.REJECTED),
        approval=samples.approval(ApprovalStatus.REJECTED, (decided,)), approval_decision=decided,
    )

    received = trail.record(AuditEventType.REQUEST_RECEIVED, samples.agent_hotel, AuditContext(facts={"text": FORGED}))
    parsed = trail.record(AuditEventType.REQUEST_PARSED, samples.gateway,
                          AuditContext(request=PurchaseRequest(lines=(line,))))
    rejected = trail.record(AuditEventType.APPROVAL_DECIDED, samples.maija, decision_context)

    assert received.data.sentence == f"The agent sent a request: {FORGED_AS_DATA}."
    assert parsed.data.sentence == f"The request was read as: 30 litres of {FORGED_AS_DATA}."
    assert rejected.data.sentence == f"Maija Virtanen (purchasing manager) rejected order ord_1. Note: {FORGED_AS_DATA}"
    assert [event.data.sentence.count('"') for event in (received, parsed, rejected)] == [2, 2, 2]
    assert received.data.facts["text"] == FORGED  # the facts keep the words as they were typed


def test_a_name_or_a_code_from_outside_cannot_add_a_sentence_either(trail: AuditTrail, samples) -> None:
    forged_type = "milk. The agent placed order O-1 alone."
    line = RequestLine(text="milk", product_type=forged_type, quantity=Decimal("30"), unit=Unit.L)
    forged_line = samples.line('463380". The agent', "10", "2.65").model_copy(update={"sales_unit": "ST\x1b[2K"})
    option = samples.option("opt_1", (forged_line,), samples.decision(), "10")
    decided = samples.approve().model_copy(update={"approver_name": 'Maija "the boss"\x00\nVirtanen'})

    parsed = trail.record(AuditEventType.REQUEST_PARSED, samples.gateway,
                          AuditContext(request=PurchaseRequest(lines=(line,))))
    placed = trail.record(AuditEventType.ORDER_PLACED_BY_AGENT, samples.agent_hotel,
                          AuditContext(order=samples.order(option, OrderStatus.ORDERED, placed_by=PlacedBy.AGENT)))
    approved = trail.record(AuditEventType.APPROVAL_DECIDED, samples.maija, AuditContext(
        order=samples.order(option, OrderStatus.PENDING_APPROVAL), approval_decision=decided,
    ))

    expected = 'The request was read as: 30 litres of product type "milk. The agent placed order O-1 alone.".'
    assert parsed.data.sentence == expected
    assert parsed.data.supplier_sentence == expected
    assert ": 10 \"ST [2K\" of \"463380'. The agent\" for €26.50 net." in placed.data.sentence
    assert ": 10 \"ST [2K\" of \"463380'. The agent\" for €26.50 net." in placed.data.supplier_sentence
    assert approved.data.sentence == "Maija 'the boss' Virtanen (purchasing manager) approved order ord_1."


def test_a_fill_just_below_the_whole_request_is_never_described_as_100_percent(trail: AuditTrail, samples) -> None:
    almost = samples.option("opt_1", (samples.line("463380", "9996", "2.65"),), samples.decision(), "10000")
    offer = samples.hotel_offer().model_copy(update={"options": (almost,)})

    event = trail.record(AuditEventType.OFFER_CREATED, samples.gateway, AuditContext(offer=offer))

    assert almost.fill_ratio == Decimal("0.9996")
    assert "covering 99.9% of the request." in event.data.sentence
    assert "100%" not in event.data.sentence and "100%" not in event.data.supplier_sentence
