"""A standing order's history counts only renewals that were ordered (review A2a, finding S-1).

Before: a renewal that still waited for approval counted, so three unapproved renewals at 150 L moved the median
from 100 L to 125 L and the fourth 150 L was "within the 25% tolerance". Nobody had approved anything.
Now a waiting renewal moves nothing: the baseline is what the kitchen actually ordered.
In replay over tonight's capture, at the recording's own clock; the demo standing order is 100 L of 469363 a week.
"""

from __future__ import annotations

from decimal import Decimal

from tta.contracts.common import DecisionKind, Identity, OrderStatus
from tta.contracts.order import DecisionRequest, Order
from tta.contracts.standing import RenewStandingOrder
from tta.standing.demo import DEMO_STANDING_ORDER_ID, SYNTHETIC_WEEKS, load_demo
from tta.standing.history import standing_history

HOTEL = "hotel-kitchen"
APPROVE = DecisionRequest(decision=DecisionKind.APPROVE)


def _renew(book, agent: Identity, litres: int):
    return book.standing.renew(agent, DEMO_STANDING_ORDER_ID, RenewStandingOrder(quantities=(Decimal(litres),)))


def _history_litres(book) -> list[Decimal]:
    history = standing_history(book.store, HOTEL, DEMO_STANDING_ORDER_ID)
    return [renewal.lines[0].quantity for renewal in history.renewals]


def test_three_renewals_that_still_wait_do_not_move_the_baseline(book, agent_hotel: Identity) -> None:
    load_demo(book.standing, agent_hotel, book.replay)
    waiting = [_renew(book, agent_hotel, 150) for _ in range(3)]

    fourth = _renew(book, agent_hotel, 150)

    assert all(outcome.order.status is OrderStatus.PENDING_APPROVAL for outcome in waiting)
    assert all(outcome.order.decision.rule_ids == ("P-08",) for outcome in [*waiting, fourth])
    assert fourth.order.status is OrderStatus.PENDING_APPROVAL
    assert fourth.drift.sentence.startswith(
        "The standing order “Weekly lactose-free milk, hotel kitchen” drifts beyond the 25% tolerance: 150 L this week "
        "against a median of 100 L over the last 6 renewals"
    )
    assert _history_litres(book) == list(SYNTHETIC_WEEKS)  # the six weeks it started with; nothing that waits


def test_a_renewal_counts_once_a_person_approved_it(book, agent_hotel: Identity, approver_purchasing) -> None:
    load_demo(book.standing, agent_hotel, book.replay)
    for _ in range(3):
        pending: Order = _renew(book, agent_hotel, 150).order
        decided = book.service.decide_approval(approver_purchasing, pending.approval_id, APPROVE)
        assert decided.status is OrderStatus.ORDERED

    fourth = _renew(book, agent_hotel, 150)

    assert _history_litres(book)[-3:] == [Decimal(150)] * 3
    assert fourth.order.decision.rule_ids == ("F-10",)  # no drift: 150 L against a median of 126 L
    assert "150 L this week against a median of 126 L over the last 6 renewals" in fourth.drift.sentence


def test_a_waiting_renewal_is_judged_at_decision_time_on_the_history_without_the_others_that_wait(
    book, agent_hotel: Identity, approver_purchasing
) -> None:
    load_demo(book.standing, agent_hotel, book.replay)
    first, second = _renew(book, agent_hotel, 150).order, _renew(book, agent_hotel, 150).order

    decided = book.service.decide_approval(approver_purchasing, first.approval_id, APPROVE)

    assert second.status is OrderStatus.PENDING_APPROVAL
    assert decided.status is OrderStatus.ORDERED and decided.decision.rule_ids == ("P-08",)
