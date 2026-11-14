"""An approval for an option with no "order by" time gets 24 hours, so every waiting order ends (SPEC section 8)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from tta.contracts.common import ApprovalStatus, Identity, OrderStatus
from tta.contracts.errors import OfferExpired
from tta.contracts.order import Order

A_DAY = timedelta(hours=24)


def _waiting_with_no_order_by(book, samples, agent: Identity) -> Order:
    return book.waiting(agent, samples.above_order_limit(valid_until=None))


def test_an_approval_for_an_option_with_no_order_by_time_must_be_decided_within_24_hours(
    book, samples, agent_hotel: Identity
) -> None:
    pending = _waiting_with_no_order_by(book, samples, agent_hotel)

    approval = book.store.get_approval(pending.approval_id)
    assert pending.option.valid_until is None and approval.valid_until == samples.now + A_DAY
    assert pending.status_sentence.startswith(
        "Waiting for approval by the purchasing manager, to be decided by Sunday 15 November 2026 at 02:52 (UTC+02:00):"
    )


def test_such_an_order_waits_until_that_time_and_expires_at_it(book, samples, agent_hotel: Identity) -> None:
    pending = _waiting_with_no_order_by(book, samples, agent_hotel)
    book.clock.advance(A_DAY - timedelta(seconds=1))

    assert book.service.get_order(pending.order_id, agent_hotel).status is OrderStatus.PENDING_APPROVAL

    book.clock.advance(timedelta(seconds=1))
    order = book.service.get_order(pending.order_id, agent_hotel)

    assert order.status is OrderStatus.EXPIRED
    assert order.status_sentence == (
        "Expired on Sunday 15 November 2026 at 02:52 (UTC+02:00) without approval by the purchasing manager: "
        "nothing was ordered."
    )
    assert book.store.get_approval(pending.approval_id).status is ApprovalStatus.EXPIRED
    assert book.event_types(pending.order_id) == ["approval.requested", "order.expired"]
    assert "Sunday 15 November 2026 at 02:52" in book.events(pending.order_id)[-1].data.sentence


def test_such_an_order_is_listed_as_expired_once_its_24_hours_are_over(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _waiting_with_no_order_by(book, samples, agent_hotel)
    book.clock.advance(A_DAY + timedelta(hours=1))

    (expired,) = book.service.list_approvals(approver_purchasing, ApprovalStatus.EXPIRED)

    assert expired.approval_id == pending.approval_id and book.service.list_approvals(
        approver_purchasing, ApprovalStatus.PENDING
    ) == ()


def test_deciding_it_too_late_answers_offer_expired_with_that_time(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _waiting_with_no_order_by(book, samples, agent_hotel)
    book.clock.advance(A_DAY + timedelta(hours=1))

    with pytest.raises(OfferExpired) as raised:
        book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    assert raised.value.extensions["valid_until"] == (samples.now + A_DAY).isoformat()
    assert "it had to be decided by Sunday 15 November 2026 at 02:52 (UTC+02:00)" in raised.value.detail
    assert book.store.get_order(pending.order_id).status is OrderStatus.EXPIRED


def test_a_first_approval_does_not_move_the_time_the_order_waits_until(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    two_roles = samples.option("opt_1", (samples.line("463380", "1200", "2.65"),), valid_until=None)
    pending = book.waiting(agent_hotel, two_roles)
    book.clock.advance(timedelta(hours=3))

    still_waiting = book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    assert still_waiting.status is OrderStatus.PENDING_APPROVAL
    assert book.store.get_approval(pending.approval_id).valid_until == samples.now + A_DAY
    assert "to be decided by Sunday 15 November 2026 at 02:52 (UTC+02:00)" in still_waiting.status_sentence


def test_an_option_with_an_order_by_time_keeps_it(book, samples, agent_hotel: Identity) -> None:
    pending = book.waiting(agent_hotel, samples.above_order_limit())

    assert book.store.get_approval(pending.approval_id).valid_until == samples.order_by
