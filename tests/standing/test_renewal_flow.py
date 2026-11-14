"""A standing order renewed through the normal flow, in replay over tonight's capture (task STAND-1).

The demonstration's standing order: 100 L of 469363 a week, six synthetic past renewals with a median of 100 L,
at the capture's price of €2.48. Renewed at 100 L it is ordered alone; at 290 L rule P-08 sends it to the
purchasing manager. Before P-08, AIMO/USE-CASES.md section 6 measured 100 to 290 L all AUTO with no rule fired.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tta.contracts.audit import AuditEventType
from tta.contracts.common import (
    ApproverRole,
    AuditReader,
    DecisionKind,
    Identity,
    IdentityKind,
    OrderStatus,
    PlacedBy,
    Unit,
    Verdict,
)
from tta.contracts.errors import InvalidRequest, NotAuthorised, NotFound
from tta.contracts.order import DecisionRequest
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.contracts.standing import NewStandingOrder, RenewStandingOrder
from tta.standing.demo import DEMO_NAME, DEMO_STANDING_ORDER_ID, SYNTHETIC_WEEKS, load_demo

P08_290 = (
    "For standing order so_demo_hotel_milk, 290 L this week against a median of 100 L over the last 6 renewals, "
    "more than the 25% tolerance of profile hotel-kitchen."
)
RENEWED = f"tta.v1.{AuditEventType.STANDING_ORDER_RENEWED.value}"
CREATED = f"tta.v1.{AuditEventType.STANDING_ORDER_CREATED.value}"


def _renew(book, agent: Identity, litres: int | None = None):
    quantities = None if litres is None else (Decimal(litres),)
    return book.standing.renew(agent, DEMO_STANDING_ORDER_ID, RenewStandingOrder(quantities=quantities))


def _milk(litres: int = 100) -> PurchaseRequest:
    line = RequestLine(text=f"{litres} L of 469363", product_ids=("469363",), quantity=Decimal(litres), unit=Unit.L)
    return PurchaseRequest(lines=(line,))


def test_the_demo_standing_order_starts_with_six_synthetic_weeks_at_the_captures_price(book, agent_hotel) -> None:
    standing = load_demo(book.standing, agent_hotel, book.replay)

    detail = book.standing.get(agent_hotel, standing.standing_order_id)
    assert (standing.name, standing.profile_id, standing.cadence_days) == (DEMO_NAME, "hotel-kitchen", 7)
    assert [renewal.lines[0].quantity for renewal in detail.renewals] == list(SYNTHETIC_WEEKS)
    assert all(renewal.synthetic and renewal.order_id is None for renewal in detail.renewals)
    assert {renewal.lines[0].unit_net_price_eur for renewal in detail.renewals} == {Decimal("2.48")}
    assert load_demo(book.standing, agent_hotel, book.replay) == standing  # once only
    events = [event for event in book.store.list_audit_events() if event.type == CREATED]
    assert len(events) == 1 and "6 past renewals made up for the demonstration" in events[0].data.sentence


def test_renewed_at_the_usual_100_litres_the_order_waits_for_approval(book, agent_hotel) -> None:
    load_demo(book.standing, agent_hotel, book.replay)

    outcome = _renew(book, agent_hotel)

    order = outcome.order
    assert order is not None and order.status is OrderStatus.PENDING_APPROVAL and order.placed_by is None
    assert order.decision.verdict is Verdict.APPROVAL and order.decision.rule_ids == ("F-10",)
    assert outcome.offer.request.standing_order_id == DEMO_STANDING_ORDER_ID
    drift = outcome.drift
    assert drift is not None and drift.judged and not any(check.over_tolerance for check in drift.checks)
    assert outcome.drift.sentence.startswith(
        "Standing order so_demo_hotel_milk is within the 25% tolerance: 100 L this week against a median of 100 L "
        "over the last 6 renewals and €2.48 per ST of 469363 this week against a median of €2.48 over the last 6 "
        "renewals."
    )
    renewals = book.standing.get(agent_hotel, DEMO_STANDING_ORDER_ID).renewals
    assert renewals[-1] == outcome.renewal and not renewals[-1].synthetic and renewals[-1].order_id == order.order_id


def test_renewed_at_290_litres_p08_sends_it_to_the_purchasing_manager(book, agent_hotel) -> None:
    load_demo(book.standing, agent_hotel, book.replay)

    outcome = _renew(book, agent_hotel, 290)

    order = outcome.order
    assert order is not None and order.status is OrderStatus.PENDING_APPROVAL
    assert order.decision.rule_ids == ("P-08",) and order.decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert order.decision.fired[0].sentence == P08_290
    assert outcome.offer.options[0].decision.rule_ids == ("P-08",)  # the offer already said so
    assert outcome.sentence.startswith("Standing order so_demo_hotel_milk drifts beyond the 25% tolerance: 290 L")
    view = book.service.get_audit(agent_hotel, AuditReader.BUYER, order_id=order.order_id)
    renewed = [event for event in view.events if event.type == RENEWED]
    assert len(renewed) == 1 and renewed[0].sentence.endswith(
        f"Order {order.order_id} waits for approval by the purchasing manager."
    )


def test_the_approver_signs_the_drifting_renewal_and_p08_still_holds_at_decision_time(
    book, agent_hotel, approver_purchasing
) -> None:
    load_demo(book.standing, agent_hotel, book.replay)
    pending = _renew(book, agent_hotel, 290).order
    assert pending is not None and pending.approval_id is not None

    decided = book.service.decide_approval(
        approver_purchasing, pending.approval_id,
        DecisionRequest(decision=DecisionKind.APPROVE, note="Conference week."),
    )

    assert decided.status is OrderStatus.ORDERED and decided.placed_by is PlacedBy.HUMAN_APPROVAL
    assert decided.decision.rule_ids == ("P-08",)  # judged on the same history, without its own renewal


def test_a_rejected_renewal_leaves_the_history_it_was_judged_on(book, agent_hotel, approver_purchasing) -> None:
    load_demo(book.standing, agent_hotel, book.replay)
    pending = _renew(book, agent_hotel, 290).order
    assert pending is not None and pending.approval_id is not None
    reject = DecisionRequest(decision=DecisionKind.REJECT)
    book.service.decide_approval(approver_purchasing, pending.approval_id, reject)

    again = _renew(book, agent_hotel, 100)

    assert again.drift is not None
    quantity = again.drift.checks[0]
    assert (quantity.median, quantity.renewals) == (Decimal(100), 6)  # the rejected 290 L is not in it
    assert again.order is not None and again.order.status is OrderStatus.PENDING_APPROVAL


def test_a_new_standing_order_has_too_short_a_history_and_is_renewed_on_the_other_rules(book, agent_hotel) -> None:
    standing = book.standing.create(agent_hotel, NewStandingOrder(name="Milk for the bar", request=_milk(290)))

    outcome = book.standing.renew(agent_hotel, standing.standing_order_id, RenewStandingOrder())

    assert outcome.order is not None and outcome.order.status is OrderStatus.PENDING_APPROVAL
    assert outcome.drift is not None and outcome.drift.judged is False
    assert "has too short a history to judge drift: 0 past renewals on record" in outcome.drift.sentence
    assert book.standing.list(agent_hotel) == (standing,)


def test_an_offer_for_a_standing_order_the_buyer_does_not_have_is_an_invalid_request(
    book, agent_hotel, agent_ward
) -> None:
    load_demo(book.standing, agent_hotel, book.replay)
    unknown = _milk().model_copy(update={"standing_order_id": "so_nobody"})
    another_buyers = _milk().model_copy(update={"standing_order_id": DEMO_STANDING_ORDER_ID})

    with pytest.raises(InvalidRequest, match="No standing order so_nobody is set up for this buyer"):
        book.service.create_offer(agent_hotel, unknown)
    with pytest.raises(InvalidRequest, match="No standing order so_demo_hotel_milk"):
        book.service.create_offer(agent_ward, another_buyers)


def test_who_may_set_up_read_and_renew(book, agent_hotel, agent_ward, approver_purchasing, supplier_reader) -> None:
    load_demo(book.standing, agent_hotel, book.replay)
    body = NewStandingOrder(name="Milk", request=_milk())

    assert book.standing.list(approver_purchasing)[0].standing_order_id == DEMO_STANDING_ORDER_ID
    assert book.standing.list(agent_ward) == ()
    with pytest.raises(NotAuthorised):
        book.standing.create(approver_purchasing, body)
    with pytest.raises(NotAuthorised):
        book.standing.list(supplier_reader)
    with pytest.raises(NotFound):
        book.standing.get(agent_ward, DEMO_STANDING_ORDER_ID)
    with pytest.raises(NotFound):
        _renew(book, agent_ward)
    with pytest.raises(NotAuthorised):
        _renew(book, approver_purchasing)


def test_a_renewal_gives_one_quantity_per_request_line(book, agent_hotel) -> None:
    load_demo(book.standing, agent_hotel, book.replay)

    with pytest.raises(InvalidRequest, match="gives 1 quantities, one per line in order; this one gives 2"):
        book.standing.renew(
            agent_hotel, DEMO_STANDING_ORDER_ID, RenewStandingOrder(quantities=(Decimal(1), Decimal(2)))
        )


def test_a_standing_order_cannot_be_set_up_twice_nor_from_a_request_that_names_one(book, agent_hotel) -> None:
    standing = load_demo(book.standing, agent_hotel, book.replay)
    renewing = _milk().model_copy(update={"standing_order_id": DEMO_STANDING_ORDER_ID})

    with pytest.raises(InvalidRequest, match="already set up"):
        book.standing.set_up(agent_hotel, standing)
    with pytest.raises(InvalidRequest, match="names no standing order"):
        book.standing.create(agent_hotel, NewStandingOrder(name="Milk", request=renewing))
    other = Identity(kind=IdentityKind.AGENT, id="agent:allergy-ward", display_name="Ward", profile_id="allergy-ward")
    with pytest.raises(NotAuthorised):
        book.standing.set_up(other, standing.model_copy(update={"standing_order_id": "so_x"}))


def test_a_renewal_with_no_option_places_nothing_records_why_and_keeps_the_history(book, agent_hotel) -> None:
    line = RequestLine(text="10 L of milk with a claim no product carries", product_type="milk",
                       required_claims=("NO_SUCH_CLAIM",), quantity=Decimal(10), unit=Unit.L)
    standing = book.standing.create(
        agent_hotel, NewStandingOrder(name="Odd milk", request=PurchaseRequest(lines=(line,)))
    )

    outcome = book.standing.renew(agent_hotel, standing.standing_order_id, RenewStandingOrder())

    assert outcome.order is None and outcome.drift is None and outcome.renewal is None
    assert outcome.sentence.startswith("No order was placed: no option fits the request this time.")
    assert book.standing.get(agent_hotel, standing.standing_order_id).renewals == ()
    renewed = [event for event in book.store.list_audit_events() if event.type == RENEWED]
    assert renewed[-1].data.sentence.endswith("No order was placed.")
