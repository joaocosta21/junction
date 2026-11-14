"""Two calls at the same moment: one lock in the service, and the order and approval are read again inside it."""

from __future__ import annotations

import threading

from tta.contracts.common import ApprovalStatus, Identity, OrderStatus
from tta.contracts.order import Order

SLOW_CHECK_SECONDS = 0.05
JOIN_SECONDS = 10


def _together(*calls) -> list[Order | BaseException]:
    """Run the calls in threads that start at the same moment; a call that raises gives its exception."""
    barrier = threading.Barrier(len(calls))
    results: list[Order | BaseException | None] = [None] * len(calls)

    def run(index: int) -> None:
        barrier.wait(timeout=JOIN_SECONDS)
        try:
            results[index] = calls[index]()
        except BaseException as error:  # noqa: BLE001 - handed to the test, which asserts on it
            results[index] = error

    threads = [threading.Thread(target=run, args=(index,)) for index in range(len(calls))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=JOIN_SECONDS)
    assert not any(thread.is_alive() for thread in threads)
    return results


def test_two_approvers_deciding_at_the_same_moment_do_not_erase_each_others_decision(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity, approver_finance: Identity
) -> None:
    offer = book.offer(samples.above_daily_limit())
    pending = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")
    book.revalidator.delay_seconds = SLOW_CHECK_SECONDS  # widens the window between reading and saving

    results = _together(
        lambda: book.service.decide(pending.approval_id, approver_purchasing, samples.approve()),
        lambda: book.service.decide(pending.approval_id, approver_finance, samples.approve()),
    )

    assert sorted(result.status for result in results) == [OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL]
    approval = book.store.get_approval(pending.approval_id)
    assert approval.status is ApprovalStatus.APPROVED and approval.roles_missing == ()
    assert {decision.approver_id for decision in approval.decisions} == {approver_purchasing.id, approver_finance.id}
    assert book.store.get_order(pending.order_id).status is OrderStatus.ORDERED
    assert sorted(book.event_types(pending.order_id)) == [
        "approval.decided", "approval.decided", "approval.requested", "order.confirmed",
    ]
    assert book.audit.verify_chain().ok


def test_the_same_key_sent_twice_at_the_same_moment_places_one_order(book, samples, agent_hotel: Identity) -> None:
    offer = book.offer(samples.within_authority())
    book.revalidator.delay_seconds = SLOW_CHECK_SECONDS

    first, second = _together(
        lambda: book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1"),
        lambda: book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1"),
    )

    assert first == second and len(book.store.list_orders()) == 1
    assert len(book.revalidator.calls) == 1 and book.event_types() == ["approval.requested"]


def test_two_orders_at_the_same_moment_cannot_both_pass_under_the_daily_limit(
    book, samples, agent_hotel: Identity
) -> None:
    """Each alone stays within the day's limit of EUR 3,000; together they would not, so one of them needs finance."""
    option = samples.option("opt_1", (samples.line("463380", "250", "2.80"),))  # €700.00
    for key in ("a", "b", "c"):  # €2,100.00 committed
        offer = book.offer(option)
        order = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, key)
        assert order.status is OrderStatus.PENDING_APPROVAL
    offers = (book.offer(option), book.offer(option))
    book.revalidator.delay_seconds = SLOW_CHECK_SECONDS

    results = _together(
        lambda: book.service.place_order(offers[0].offer_id, "opt_1", agent_hotel, "d"),
        lambda: book.service.place_order(offers[1].offer_id, "opt_1", agent_hotel, "e"),
    )

    assert all(result.status is OrderStatus.PENDING_APPROVAL for result in results)
    assert {result.decision.rule_ids for result in results} == {("F-10",), ("P-02",)}
