"""Who may read orders and approvals: an agent or approver of the same buyer; the supplier reads none here."""

from __future__ import annotations

import pytest

from tta.contracts.common import ApprovalStatus, Identity
from tta.contracts.errors import NotAuthorised, NotFound
from tta.contracts.order import Order


def _pending(book, samples, agent: Identity, key: str = "key-1") -> Order:
    offer = book.offer(samples.above_order_limit())
    return book.service.place_order(offer.offer_id, "opt_1", agent, key)


@pytest.mark.parametrize("reader", ["agent_hotel", "approver_purchasing", "approver_hotel_buyer"])
def test_the_agent_and_the_approvers_of_a_buyer_read_its_orders_and_approvals(
    reader: str, book, samples, agent_hotel: Identity, request: pytest.FixtureRequest
) -> None:
    identity = request.getfixturevalue(reader)
    pending = _pending(book, samples, agent_hotel)

    assert book.service.get_order(pending.order_id, identity) == pending
    assert book.service.get_approval(pending.approval_id, identity).order_id == pending.order_id
    assert [approval.approval_id for approval in book.service.list_approvals(identity)] == [pending.approval_id]


@pytest.mark.parametrize("reader", ["agent_ward", "approver_dietitian"])
def test_an_order_or_approval_of_another_buyer_is_answered_like_one_nobody_issued(
    reader: str, book, samples, agent_hotel: Identity, request: pytest.FixtureRequest
) -> None:
    identity = request.getfixturevalue(reader)
    pending = _pending(book, samples, agent_hotel)

    with pytest.raises(NotFound) as order_of_another_buyer:
        book.service.get_order(pending.order_id, identity)
    with pytest.raises(NotFound) as unknown_order:
        book.service.get_order("ord_000000000bad", identity)
    with pytest.raises(NotFound) as approval_of_another_buyer:
        book.service.get_approval(pending.approval_id, identity)
    with pytest.raises(NotFound) as unknown_approval:
        book.service.get_approval("apr_000000000bad", identity)

    assert order_of_another_buyer.value.to_problem() == unknown_order.value.to_problem()
    assert approval_of_another_buyer.value.to_problem() == unknown_approval.value.to_problem()
    assert book.event_types() == ["approval.requested"]


def test_the_supplier_reads_no_order_and_no_approval_whether_it_exists_or_not(
    book, samples, agent_hotel: Identity, supplier_reader: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)

    for order_id in (pending.order_id, "ord_000000000bad"):
        with pytest.raises(NotAuthorised):
            book.service.get_order(order_id, supplier_reader)
    for approval_id in (pending.approval_id, "apr_000000000bad"):
        with pytest.raises(NotAuthorised):
            book.service.get_approval(approval_id, supplier_reader)


def test_a_buyer_lists_only_its_own_approvals(
    book, samples, agent_hotel: Identity, approver_dietitian: Identity, supplier_reader: Identity
) -> None:
    _pending(book, samples, agent_hotel)

    assert book.service.list_approvals(approver_dietitian) == ()
    with pytest.raises(NotAuthorised):
        book.service.list_approvals(supplier_reader)


def test_the_queue_can_be_listed_by_status(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    waiting = _pending(book, samples, agent_hotel, "key-1")
    decided = _pending(book, samples, agent_hotel, "key-2")
    book.service.decide(decided.approval_id, approver_purchasing, samples.reject())

    pending = book.service.list_approvals(approver_purchasing, ApprovalStatus.PENDING)
    rejected = book.service.list_approvals(approver_purchasing, ApprovalStatus.REJECTED)

    assert [approval.approval_id for approval in pending] == [waiting.approval_id]
    assert [approval.approval_id for approval in rejected] == [decided.approval_id]
    assert len(book.service.list_approvals(approver_purchasing)) == 2


def test_an_order_or_approval_nobody_issued_is_not_found(book, agent_hotel: Identity) -> None:
    with pytest.raises(NotFound):
        book.service.get_order("ord_000000000bad", agent_hotel)
    with pytest.raises(NotFound):
        book.service.get_approval("apr_000000000bad", agent_hotel)


def test_an_approval_whose_order_is_not_in_the_book_cannot_be_read(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)
    approval = book.store.get_approval(pending.approval_id)
    book.store.save_approval(approval.model_copy(update={"approval_id": "apr_orphan000000", "order_id": "ord_gone"}))

    with pytest.raises(NotFound):
        book.service.get_approval("apr_orphan000000", approver_purchasing)
