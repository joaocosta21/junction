"""The web evidence of an approval is looked up with the order book's lock released (review finding P5).

A lookup can take up to 40 seconds. Held inside the lock, it stalled every read and every decision of the shared
book. Now: check, release, look up, take the lock again and make sure nothing the order rests on changed, write.
"""

from __future__ import annotations

import threading
from datetime import timedelta

import pytest

from tta.audit import AuditTrail
from tta.contracts.common import Identity, OrderStatus
from tta.contracts.errors import InvalidRequest, OfferExpired
from tta.contracts.order import Evidence
from tta.orders import OrderBookService

WAIT_SECONDS = 5


class SlowFinder:
    """An evidence finder that does not answer until the test lets it."""

    def __init__(self) -> None:
        self.asked = threading.Event()
        self.answer = threading.Event()
        self.calls = 0
        self.meanwhile = None  # run once, during the first lookup, by the thread that waits for the evidence

    def for_approval(self, option, decision) -> tuple[Evidence, ...]:
        self.calls += 1
        self.asked.set()
        if self.meanwhile is not None:
            meanwhile, self.meanwhile = self.meanwhile, None
            meanwhile()
        assert self.answer.wait(WAIT_SECONDS)
        product_id = option.lines[0].product_id
        return (Evidence(product_id=product_id, found=True, sentence=f"A page about {product_id} [{self.calls}]."),)


@pytest.fixture
def finder() -> SlowFinder:
    return SlowFinder()


@pytest.fixture
def slow_book(book, finder: SlowFinder):
    """The book of the other order tests, its service given a slow evidence finder."""
    book.service = OrderBookService(
        store=book.store, policy=book.policy, revalidator=book.revalidator,
        audit=AuditTrail(book.store, book.clock, policy=book.policy), clock=book.clock, evidence=finder,
    )
    return book


def _in_thread(call) -> tuple[threading.Thread, list]:
    result: list = []

    def run() -> None:
        try:
            result.append(call())
        except BaseException as error:  # noqa: BLE001 - handed to the test, which asserts on it
            result.append(error)

    thread = threading.Thread(target=run)
    thread.start()
    return thread, result


def test_a_slow_evidence_lookup_does_not_block_a_concurrent_get_order(
    slow_book, finder: SlowFinder, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    finder.answer.set()
    earlier = slow_book.waiting(agent_hotel, samples.above_order_limit())
    finder.answer.clear()
    finder.asked.clear()
    offer = slow_book.offer(samples.above_order_limit())
    placing, placed = _in_thread(lambda: slow_book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-2"))
    assert finder.asked.wait(WAIT_SECONDS)  # the lookup is under way and has not answered

    reading, read = _in_thread(lambda: slow_book.service.get_order(earlier.order_id, agent_hotel))
    reading.join(timeout=WAIT_SECONDS)
    listing, listed = _in_thread(lambda: slow_book.service.list_approvals(approver_purchasing))
    listing.join(timeout=WAIT_SECONDS)
    read_while_looking_up = not reading.is_alive() and not listing.is_alive() and placing.is_alive()

    finder.answer.set()
    placing.join(timeout=WAIT_SECONDS)
    reading.join(timeout=WAIT_SECONDS)
    listing.join(timeout=WAIT_SECONDS)
    assert read_while_looking_up
    assert read[0].order_id == earlier.order_id and len(listed[0]) == 1
    order = placed[0]
    assert order.status is OrderStatus.PENDING_APPROVAL
    approval = slow_book.store.get_approval(order.approval_id)
    assert [item.sentence for item in approval.evidence] == ["A page about 463380 [2]."]
    assert len(slow_book.revalidator.calls) == 2  # one check per order: nothing changed during the lookup


def test_an_order_placed_on_the_same_offer_during_the_lookup_refuses_the_one_that_waited(
    slow_book, finder: SlowFinder, samples, agent_hotel: Identity
) -> None:
    offer = slow_book.offer(samples.above_order_limit())
    other = OrderBookService(
        store=slow_book.store, policy=slow_book.policy, revalidator=slow_book.revalidator,
        audit=slow_book.audit, clock=slow_book.clock,
    )
    finder.meanwhile = lambda: other.place_order(offer.offer_id, "opt_1", agent_hotel, "key-other")
    finder.answer.set()

    with pytest.raises(InvalidRequest, match="already has an order"):
        slow_book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")

    assert len(slow_book.store.list_orders()) == 1


def test_the_same_key_used_during_the_lookup_gives_that_keys_order_and_places_no_second(
    slow_book, finder: SlowFinder, samples, agent_hotel: Identity
) -> None:
    offer = slow_book.offer(samples.above_order_limit())
    other = OrderBookService(
        store=slow_book.store, policy=slow_book.policy, revalidator=slow_book.revalidator,
        audit=slow_book.audit, clock=slow_book.clock,
    )
    finder.meanwhile = lambda: other.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")
    finder.answer.set()

    order = slow_book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")

    assert [stored.order_id for stored in slow_book.store.list_orders()] == [order.order_id]
    assert slow_book.store.get_approval(order.approval_id).evidence == ()  # the other writer's order, as it wrote it


def test_spend_that_changed_during_the_lookup_has_the_check_run_again(
    slow_book, finder: SlowFinder, samples, agent_hotel: Identity
) -> None:
    """€700.00 on a day with €2,100.00 committed stays under €3,000; a further €700.00 placed during the lookup
    takes the day over the limit, so the order is judged again and waits for finance too (P-02)."""
    small = samples.option("opt_1", (samples.line("463380", "250", "2.80"),))
    other = OrderBookService(
        store=slow_book.store, policy=slow_book.policy, revalidator=slow_book.revalidator,
        audit=slow_book.audit, clock=slow_book.clock,
    )
    for key in ("a", "b", "c"):
        other.place_order(slow_book.offer(small).offer_id, "opt_1", agent_hotel, key)
    extra, offer = slow_book.offer(small), slow_book.offer(small)
    finder.meanwhile = lambda: other.place_order(extra.offer_id, "opt_1", agent_hotel, "d")
    finder.answer.set()
    checks_before = len(slow_book.revalidator.calls)

    order = slow_book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")

    assert order.status is OrderStatus.PENDING_APPROVAL and "P-02" in order.decision.rule_ids
    assert len(slow_book.revalidator.calls) - checks_before == 3  # the other order's check, this one's, and again
    approval = slow_book.store.get_approval(order.approval_id)
    assert "€2,800.00 before tax" in " ".join(approval.reasons)
    assert len(approval.evidence) == 1 and finder.calls == 2  # looked up again for the decision that was written


def test_an_order_by_time_that_passed_during_the_lookup_has_the_check_run_again(
    slow_book, finder: SlowFinder, samples, agent_hotel: Identity
) -> None:
    offer = slow_book.offer(samples.above_order_limit())

    def time_passes() -> None:
        slow_book.clock.advance(timedelta(days=3))
        slow_book.revalidator.result = samples.cutoff_passed(slow_book.clock.now())

    finder.meanwhile = time_passes
    finder.answer.set()

    with pytest.raises(OfferExpired):
        slow_book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")

    assert slow_book.store.list_orders() == () and slow_book.event_types() == ["order.not_placed"]
