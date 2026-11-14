"""A pending order past its "order by" time becomes EXPIRED when it is next read or listed (SPEC section 8)."""

from __future__ import annotations

from datetime import timedelta

from tta.contracts.common import ApprovalStatus, Identity, OrderStatus
from tta.contracts.order import Order
from tta.orders.records import is_past_order_by

AFTER_ORDER_BY = timedelta(days=3)


def _pending(book, samples, agent: Identity, key: str = "key-1") -> Order:
    offer = book.offer(samples.above_order_limit())
    return book.service.place_order(offer.offer_id, "opt_1", agent, key)


def test_a_pending_order_read_after_its_order_by_time_is_expired(book, samples, agent_hotel: Identity) -> None:
    pending = _pending(book, samples, agent_hotel)
    book.clock.advance(AFTER_ORDER_BY)

    order = book.service.get_order(pending.order_id, agent_hotel)

    assert order.status is OrderStatus.EXPIRED and order.placed_by is None
    assert order.updated_at == book.clock.now() and order.created_at == pending.created_at
    assert order.status_sentence == (
        "Expired on Sunday 15 November 2026 at 17:00 (UTC+02:00) without approval by the purchasing manager: "
        "nothing was ordered."
    )
    assert book.store.get_order(pending.order_id) == order
    assert book.store.get_approval(pending.approval_id).status is ApprovalStatus.EXPIRED
    assert book.event_types(order.order_id) == ["approval.requested", "order.expired"]
    assert book.events(order.order_id)[-1].data.actor.kind == "system"


def test_reading_an_expired_order_again_records_nothing_more(book, samples, agent_hotel: Identity) -> None:
    pending = _pending(book, samples, agent_hotel)
    book.clock.advance(AFTER_ORDER_BY)
    first = book.service.get_order(pending.order_id, agent_hotel)

    second = book.service.get_order(pending.order_id, agent_hotel)

    assert second == first and book.event_types().count("order.expired") == 1


def test_an_order_is_pending_until_its_order_by_time_and_expired_at_that_very_instant(
    book, samples, agent_hotel: Identity
) -> None:
    """A time equal to the clock has passed, as for the policy (F-04), availability and the offer re-check."""
    pending = _pending(book, samples, agent_hotel)
    book.clock.advance(samples.order_by - samples.now - timedelta(seconds=1))

    assert book.service.get_order(pending.order_id, agent_hotel).status is OrderStatus.PENDING_APPROVAL

    book.clock.advance(timedelta(seconds=1))

    assert book.clock.now() == pending.option.valid_until == samples.order_by
    assert not is_past_order_by(pending, samples.order_by - timedelta(microseconds=1))
    assert is_past_order_by(pending, samples.order_by)
    assert book.service.get_order(pending.order_id, agent_hotel).status is OrderStatus.EXPIRED


def test_listing_the_approvals_expires_the_ones_past_their_time(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)
    book.clock.advance(AFTER_ORDER_BY)

    assert book.service.list_approvals(approver_purchasing, ApprovalStatus.PENDING) == ()

    (expired,) = book.service.list_approvals(approver_purchasing, ApprovalStatus.EXPIRED)
    assert expired.approval_id == pending.approval_id
    assert book.store.get_order(pending.order_id).status is OrderStatus.EXPIRED
    assert book.event_types().count("order.expired") == 1


def test_reading_an_approval_past_its_time_expires_it(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)
    book.clock.advance(AFTER_ORDER_BY)

    approval = book.service.get_approval(pending.approval_id, approver_purchasing)

    assert approval.status is ApprovalStatus.EXPIRED
    assert book.store.get_order(pending.order_id).status is OrderStatus.EXPIRED


def test_an_order_that_was_placed_never_expires(book, samples, agent_hotel: Identity) -> None:
    offer = book.offer(samples.within_authority())
    ordered = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")
    book.clock.advance(AFTER_ORDER_BY)

    assert book.service.get_order(ordered.order_id, agent_hotel) == ordered
    assert book.event_types() == ["order.placed_by_agent"]


def test_a_retry_with_the_same_key_after_the_time_passed_returns_the_expired_order(
    book, samples, agent_hotel: Identity
) -> None:
    offer = book.offer(samples.above_order_limit())
    pending = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")
    book.clock.advance(AFTER_ORDER_BY)

    again = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")

    assert again.order_id == pending.order_id and again.status is OrderStatus.EXPIRED
    assert len(book.store.list_orders()) == 1


def test_a_pending_order_whose_approval_record_is_missing_still_expires(book, samples, agent_hotel: Identity) -> None:
    pending = _pending(book, samples, agent_hotel)
    book.store.save_order(pending.model_copy(update={"approval_id": "apr_gone00000000"}))
    book.clock.advance(AFTER_ORDER_BY)

    order = book.service.get_order(pending.order_id, agent_hotel)

    assert order.status is OrderStatus.EXPIRED and book.event_types().count("order.expired") == 1
