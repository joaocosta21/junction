"""The two standing-order events (task STAND-1): set up, and renewed with the drift found, for both readers."""

from __future__ import annotations

from decimal import Decimal

from tta.audit import AuditTrail
from tta.contracts.audit import AuditContext, AuditEventType
from tta.contracts.common import AuditReader, OrderStatus, PlacedBy, Unit
from tta.contracts.request import PurchaseRequest, RequestLine

DRIFT = (
    "Standing order so_milk drifts beyond the 25% tolerance: 290 L this week against a median of 100 L over the last "
    "6 renewals. 6 renewals of the history are synthetic, made up for the demonstration: the Valio Aimo mock has no "
    "order history."
)
NAME = "Weekly lactose-free milk, hotel kitchen"


def _request() -> PurchaseRequest:
    line = RequestLine(text="100 L of lactose-free milk 469363", product_ids=("469363",), quantity=Decimal(100),
                       unit=Unit.L)
    return PurchaseRequest(lines=(line,))


def _renewed_facts() -> dict:
    return {"standing_order_id": "so_milk", "standing_order_name": NAME, "drift_sentence": DRIFT,
            "drift": {"judged": True, "tolerance": 0.25}, "renewal_id": "ren_7"}


def test_setting_up_a_standing_order_says_what_it_renews_and_that_its_history_is_synthetic(
    trail: AuditTrail, samples
) -> None:
    facts = {"standing_order_id": "so_milk", "standing_order_name": NAME, "cadence_days": 7, "synthetic_renewals": 6}

    event = trail.record(
        AuditEventType.STANDING_ORDER_CREATED, samples.agent_hotel,
        AuditContext(profile_id="hotel-kitchen", request=_request(), facts=facts),
    )

    assert event.type == "tta.v1.standing_order.created"
    assert event.subject == "standing_order/so_milk"
    assert event.data.sentence == (
        f'The agent set up standing order so_milk, "{NAME}", renewed every 7 days: 100 litres of product 469363. '
        "It starts with 6 past renewals made up for the demonstration, marked synthetic: the Valio Aimo mock has no "
        "order history."
    )
    assert event.data.supplier_sentence == "The buyer's agent set up a standing order."
    assert "standing_order_name" not in event.data.supplier_facts


def test_a_renewal_sent_to_a_human_states_the_drift_and_who_must_approve(trail: AuditTrail, samples) -> None:
    rule = samples.rule("P-08", "For standing order so_milk, 290 L this week against a median of 100 L.")
    option = samples.option("opt_1", (samples.line("469363", "290", "2.48"),), samples.decision(rule), "290")
    order = samples.order(option, OrderStatus.PENDING_APPROVAL, order_id="ord_7", offer_id="off_7")

    event = trail.record(
        AuditEventType.STANDING_ORDER_RENEWED, samples.agent_hotel,
        AuditContext(offer_id="off_7", order=order, facts=_renewed_facts()),
    )

    assert event.subject == "standing_order/so_milk"
    assert event.data.sentence == (
        f'The agent renewed standing order so_milk, "{NAME}", as offer off_7. {DRIFT} Order ord_7 waits for approval '
        "by the purchasing manager."
    )
    assert event.data.rule_ids == ("P-08",)
    assert event.data.supplier_sentence == (
        "The buyer's agent renewed a standing order as offer off_7. Order ord_7 is pending approval. "
        "Rule that applied: P-08, a rule the buyer set (rule P-08; the buyer's tolerance is not shown): "
        "approval by a person of the buyer."
    )
    assert "25%" not in event.data.supplier_sentence and "drift" not in event.data.supplier_facts
    found = trail.view(AuditReader.BUYER, order_id="ord_7").events
    assert [view.type for view in found] == ["tta.v1.standing_order.renewed"]


def test_a_renewal_placed_alone_says_so(trail: AuditTrail, samples) -> None:
    option = samples.option("opt_1", (samples.line("469363", "100", "2.48"),), samples.decision(), "100")
    order = samples.order(option, OrderStatus.ORDERED, order_id="ord_8", placed_by=PlacedBy.AGENT, approval_id=None)

    event = trail.record(
        AuditEventType.STANDING_ORDER_RENEWED, samples.agent_hotel,
        AuditContext(offer_id="off_1", order=order, facts=_renewed_facts()),
    )

    assert event.data.sentence.endswith("Order ord_8 was placed by the agent within its authority.")


def test_a_renewal_without_an_order_says_nothing_was_placed(trail: AuditTrail, samples) -> None:
    event = trail.record(
        AuditEventType.STANDING_ORDER_RENEWED, samples.agent_hotel,
        AuditContext(profile_id="hotel-kitchen", offer_id="off_9", facts={"standing_order_id": "so_milk"}),
    )

    assert event.data.sentence == "The agent renewed standing order so_milk as offer off_9. No order was placed."
    assert event.data.supplier_sentence == (
        "The buyer's agent renewed a standing order as offer off_9. No order was placed."
    )


def test_a_standing_order_id_that_is_not_an_id_is_never_a_subject(trail: AuditTrail, samples) -> None:
    event = trail.record(
        AuditEventType.STANDING_ORDER_CREATED, samples.agent_hotel,
        AuditContext(profile_id="hotel-kitchen", facts={"standing_order_id": "so x"}),
    )

    assert event.subject is None
    assert event.data.sentence == 'The agent set up standing order "so x".'
