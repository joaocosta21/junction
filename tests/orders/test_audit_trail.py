"""Every step of an order is in the audit trail, in order, and no status changes without an event (SPEC section 9)."""

from __future__ import annotations

from datetime import timedelta
from itertools import pairwise

from tta.contracts.audit import GENESIS_HASH
from tta.contracts.common import AuditReader, Identity, OrderStatus


def test_the_audit_events_of_one_order_in_order_form_a_valid_chain(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity, approver_finance: Identity
) -> None:
    offer = book.offer(samples.above_daily_limit())
    pending = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")
    book.service.decide(pending.approval_id, approver_purchasing, samples.approve())
    book.service.decide(pending.approval_id, approver_finance, samples.approve(note="Within the month's budget."))

    events = book.events(pending.order_id)

    assert book.event_types(pending.order_id) == [
        "approval.requested", "approval.decided", "approval.decided", "order.confirmed",
    ]
    assert events[0].data.previous_hash == GENESIS_HASH
    assert all(later.data.previous_hash == earlier.data.hash for earlier, later in pairwise(events))
    assert all(event.data.order_id == pending.order_id and event.data.offer_id == offer.offer_id for event in events)
    assert all(event.data.policy_hash == pending.decision.policy_hash for event in events)
    assert all(event.data.sentence and event.data.supplier_sentence for event in events)
    verification = book.audit.verify_chain()
    assert verification.ok and verification.checked == 4
    view = book.audit.view(AuditReader.BUYER, order_id=pending.order_id)
    assert view.chain.ok and [event.id for event in view.events] == [event.id for event in events]


def test_who_acted_is_on_every_event(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    offer = book.offer(samples.above_order_limit())
    pending = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")
    book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    requested, decided, confirmed = book.events(pending.order_id)

    assert (requested.data.actor.kind, requested.data.actor.id) == ("agent", agent_hotel.id)
    assert (decided.data.actor.kind, decided.data.actor.id) == ("human", approver_purchasing.id)
    assert decided.data.actor.role == "purchasing_manager"
    assert confirmed.data.actor.kind == "system"
    assert requested.data.rule_ids == decided.data.rule_ids == confirmed.data.rule_ids == ("P-01",)
    assert confirmed.data.facts["revalidation"]["ok"] is True
    assert len(confirmed.data.facts["order"]["reliance"]) == 1


def test_no_status_changes_without_an_audit_event_in_the_same_call(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity, approver_finance: Identity
) -> None:
    """Walks every status change of SPEC section 8 and counts the events each call adds."""
    seen: dict[str, OrderStatus | None] = {}
    walked: list[tuple[OrderStatus | None, OrderStatus, list[str]]] = []

    def step(call) -> None:
        before = len(book.events())
        order = call()
        added = book.event_types()[before:]
        previous = seen.get(order.order_id)
        if previous is not order.status:
            walked.append((previous, order.status, added))
        seen[order.order_id] = order.status

    def place(option, key: str):
        offer = book.offer(option)
        return book.service.place_order(offer.offer_id, option.option_id, agent_hotel, key)

    step(lambda: place(samples.within_authority(), "within-limits"))
    step(lambda: place(samples.above_order_limit(), "approve"))
    approved = book.store.list_orders()[-1]
    step(lambda: book.service.decide(approved.approval_id, approver_purchasing, samples.approve()))
    step(lambda: place(samples.unconfirmed("opt_1"), "reject"))
    rejected = book.store.list_orders()[-1]
    step(lambda: book.service.decide(rejected.approval_id, approver_purchasing, samples.reject()))
    step(lambda: place(samples.unconfirmed("opt_1"), "expire"))
    expiring = book.store.list_orders()[-1]
    book.clock.advance(timedelta(days=3))
    step(lambda: book.service.get_order(expiring.order_id, agent_hotel))

    pending, ordered, rejected_, expired = (
        OrderStatus.PENDING_APPROVAL, OrderStatus.ORDERED, OrderStatus.REJECTED, OrderStatus.EXPIRED,
    )
    assert walked == [
        (None, pending, ["approval.requested"]),
        (None, pending, ["approval.requested"]),
        (pending, ordered, ["approval.decided", "order.confirmed"]),
        (None, pending, ["approval.requested"]),
        (pending, rejected_, ["approval.decided", "order.rejected"]),
        (None, pending, ["approval.requested"]),
        (pending, expired, ["order.expired"]),
    ]
    assert {after for _, after, _ in walked} == set(OrderStatus)
    assert book.audit.verify_chain().ok
