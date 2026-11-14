"""Every outcome of the order book is written whole or not at all (SPEC section 8).

Each write of each outcome is made to fail in turn. Afterwards the store holds nothing of that outcome, and the
same call sent again succeeds and leaves the events of exactly one outcome.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import NamedTuple

import pytest

from tta.contracts.audit import EVENT_TYPE_PREFIX, AuditEvent
from tta.contracts.common import Identity, OrderStatus
from tta.contracts.errors import NotAuthorised, OfferExpired, OfferStale, PolicyBlocked, TtaError
from tta.contracts.order import Approval, Order

KEY = "key-1"
KEY_WRITE, ORDER_WRITE, APPROVAL_WRITE, EVENT_WRITE = (
    "remember_idempotency_key", "save_order", "save_approval", "append_audit_event",
)


class People(NamedTuple):
    agent: Identity
    purchasing: Identity


class Stored(NamedTuple):
    orders: tuple[Order, ...]
    approvals: tuple[Approval, ...]
    events: tuple[AuditEvent, ...]
    order_id_of_key: str | None


@dataclass(frozen=True)
class Case:
    """One outcome: how to get to the call that produces it, the writes it makes and the events it leaves."""

    name: str
    prepare: Callable[..., Callable[[], Order]]
    writes: tuple[str, ...]
    events: tuple[str, ...]
    status: OrderStatus | None = None  # of the order the call returns
    refusal: type[TtaError] | None = None  # the call answers with this error once its event is written


def _alone(book, samples, people: People) -> Callable[[], Order]:
    offer = book.offer(samples.within_authority())
    return lambda: book.service.place_order(offer.offer_id, "opt_1", people.agent, KEY)


def _to_a_human(book, samples, people: People) -> Callable[[], Order]:
    offer = book.offer(samples.above_order_limit())
    return lambda: book.service.place_order(offer.offer_id, "opt_1", people.agent, KEY)


def _approved(book, samples, people: People) -> Callable[[], Order]:
    pending = book.waiting(people.agent, samples.above_order_limit())
    return lambda: book.service.decide(pending.approval_id, people.purchasing, samples.approve())


def _first_of_two_approvals(book, samples, people: People) -> Callable[[], Order]:
    pending = book.waiting(people.agent, samples.above_daily_limit())
    return lambda: book.service.decide(pending.approval_id, people.purchasing, samples.approve())


def _rejected(book, samples, people: People) -> Callable[[], Order]:
    pending = book.waiting(people.agent, samples.above_order_limit())
    return lambda: book.service.decide(pending.approval_id, people.purchasing, samples.reject())


def _expired_when_read(book, samples, people: People) -> Callable[[], Order]:
    pending = book.waiting(people.agent, samples.above_order_limit())
    book.clock.advance(timedelta(days=3))
    return lambda: book.service.get_order(pending.order_id, people.agent)


def _expired_when_decided(book, samples, people: People) -> Callable[[], Order]:
    pending = book.waiting(people.agent, samples.above_order_limit())
    book.clock.advance(timedelta(days=3))
    return lambda: book.service.decide(pending.approval_id, people.purchasing, samples.approve())


def _agent_refused(book, samples, people: People) -> Callable[[], Order]:
    pending = book.waiting(people.agent, samples.above_order_limit())
    return lambda: book.service.decide(pending.approval_id, people.agent, samples.approve())


def _blocked(book, samples, people: People) -> Callable[[], Order]:
    offer = book.offer(samples.adds_allergen("opt_1"))
    return lambda: book.service.place_order(offer.offer_id, "opt_1", people.agent, KEY)


def _stale(book, samples, people: People) -> Callable[[], Order]:
    offer = book.offer(samples.within_authority())
    book.revalidator.result = samples.price_changed()
    return lambda: book.service.place_order(offer.offer_id, "opt_1", people.agent, KEY)


CASES = (
    Case("within profile limits", _alone, (KEY_WRITE, ORDER_WRITE, APPROVAL_WRITE, EVENT_WRITE),
         ("approval.requested",), status=OrderStatus.PENDING_APPROVAL),
    Case("sent to a human", _to_a_human, (KEY_WRITE, ORDER_WRITE, APPROVAL_WRITE, EVENT_WRITE),
         ("approval.requested",), status=OrderStatus.PENDING_APPROVAL),
    Case("approved", _approved, (ORDER_WRITE, APPROVAL_WRITE, EVENT_WRITE, EVENT_WRITE),
         ("approval.decided", "order.confirmed"), status=OrderStatus.ORDERED),
    Case("first of two approvals", _first_of_two_approvals, (ORDER_WRITE, APPROVAL_WRITE, EVENT_WRITE),
         ("approval.decided",), status=OrderStatus.PENDING_APPROVAL),
    Case("rejected", _rejected, (ORDER_WRITE, APPROVAL_WRITE, EVENT_WRITE, EVENT_WRITE),
         ("approval.decided", "order.rejected"), status=OrderStatus.REJECTED),
    Case("expired when read", _expired_when_read, (ORDER_WRITE, APPROVAL_WRITE, EVENT_WRITE), ("order.expired",),
         status=OrderStatus.EXPIRED),
    Case("expired when decided", _expired_when_decided, (ORDER_WRITE, APPROVAL_WRITE, EVENT_WRITE),
         ("order.expired",), refusal=OfferExpired),
    Case("agent refused on an approval", _agent_refused, (EVENT_WRITE,), ("authorisation.refused",),
         refusal=NotAuthorised),
    Case("blocked by the policy", _blocked, (EVENT_WRITE,), ("order.blocked",), refusal=PolicyBlocked),
    Case("changed since the offer", _stale, (EVENT_WRITE,), ("order.not_placed",), refusal=OfferStale),
)
EVERY_WRITE_OF_EVERY_CASE = [(case, number) for case in CASES for number in range(1, len(case.writes) + 1)]


@pytest.fixture
def people(agent_hotel: Identity, approver_purchasing: Identity) -> People:
    return People(agent=agent_hotel, purchasing=approver_purchasing)


def _stored(book, people: People) -> Stored:
    return Stored(
        orders=book.store.list_orders(), approvals=book.store.list_approvals(), events=book.events(),
        order_id_of_key=book.store.order_id_for_key(KEY, people.agent.id),
    )


def _sent_again(call: Callable[[], Order], case: Case) -> Order | None:
    if case.refusal is None:
        return call()
    with pytest.raises(case.refusal):
        call()
    return None


@pytest.mark.parametrize(
    ("case", "failing"), EVERY_WRITE_OF_EVERY_CASE,
    ids=[f"{case.name}: write {number} ({case.writes[number - 1]})" for case, number in EVERY_WRITE_OF_EVERY_CASE],
)
def test_a_write_that_fails_leaves_nothing_of_the_outcome_and_the_same_call_then_succeeds(
    case: Case, failing: int, book, samples, people: People, write_fault: type[Exception]
) -> None:
    call = case.prepare(book, samples, people)
    before = _stored(book, people)
    book.store.fail_write(failing)

    with pytest.raises(write_fault):
        call()

    assert book.store.writes == list(case.writes[:failing])  # the fault hit the write this case is about
    assert _stored(book, people) == before

    result = _sent_again(call, case)

    after = _stored(book, people)
    assert book.store.writes[failing:] == list(case.writes)
    assert [event.type.removeprefix(EVENT_TYPE_PREFIX) for event in after.events[len(before.events):]] == list(
        case.events
    )
    assert book.audit.verify_chain().ok
    if result is not None:
        assert result.status is case.status and book.store.get_order(result.order_id) == result


def test_an_approval_that_could_not_be_saved_leaves_no_order_that_nobody_can_decide(
    book, samples, people: People, write_fault: type[Exception]
) -> None:
    offer = book.offer(samples.above_order_limit())
    book.store.fail_write(3)  # the key, the order, then the approval
    with pytest.raises(write_fault):
        book.service.place_order(offer.offer_id, "opt_1", people.agent, KEY)
    assert book.store.writes[-1] == APPROVAL_WRITE

    order = book.service.place_order(offer.offer_id, "opt_1", people.agent, KEY)

    assert order.status is OrderStatus.PENDING_APPROVAL and book.store.list_orders() == (order,)
    assert book.store.get_approval(order.approval_id).order_id == order.order_id
    assert book.event_types(order.order_id) == ["approval.requested"]
    decided = book.service.decide(order.approval_id, people.purchasing, samples.approve())
    assert decided.status is OrderStatus.ORDERED


def test_an_audit_event_that_cannot_be_written_stops_the_order_and_reaches_the_caller(
    book, samples, people: People, write_fault: type[Exception]
) -> None:
    offer = book.offer(samples.within_authority())
    book.store.fail_write(4)  # the key, the order, the approval, then the audit event

    with pytest.raises(write_fault):
        book.service.place_order(offer.offer_id, "opt_1", people.agent, KEY)

    assert book.store.writes[-1] == EVENT_WRITE
    assert book.store.list_orders() == () and book.events() == ()
    assert book.store.order_id_for_key(KEY, people.agent.id) is None
