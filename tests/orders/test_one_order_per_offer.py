"""An offer answers one request: while an order of it waits or is ORDERED, it cannot be ordered a second time."""

from __future__ import annotations

from datetime import timedelta

import pytest

from tta.contracts.common import Identity, OrderStatus
from tta.contracts.errors import InvalidRequest


@pytest.mark.parametrize(
    ("build", "state"), [("within_authority", "ordered"), ("above_order_limit", "waiting for approval")],
    ids=["an order that is ORDERED", "an order that waits for a human"],
)
def test_an_offer_that_already_has_an_order_cannot_be_ordered_again_under_another_key(
    build: str, state: str, book, samples, agent_hotel: Identity
) -> None:
    offer = book.offer(getattr(samples, build)("opt_1"), samples.unconfirmed("opt_2"))
    first = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")

    for option_id in ("opt_1", "opt_2"):
        with pytest.raises(InvalidRequest) as raised:
            book.service.place_order(offer.offer_id, option_id, agent_hotel, "key-2")
        assert raised.value.detail.startswith(
            f"Offer {offer.offer_id} already has an order: {first.order_id}, which is {state}."
        )
        assert raised.value.extensions == {"offer_id": offer.offer_id, "order_id": first.order_id}

    assert book.store.list_orders() == (first,) and len(book.revalidator.calls) == 1
    assert len(book.events()) == 1 and book.store.order_id_for_key("key-2", agent_hotel.id) is None


def test_an_offer_can_be_ordered_again_after_its_order_was_rejected(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    offer = book.offer(samples.above_order_limit("opt_1"), samples.within_authority("opt_2"))
    first = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")
    book.service.decide(first.approval_id, approver_purchasing, samples.reject())

    second = book.service.place_order(offer.offer_id, "opt_2", agent_hotel, "key-2")

    assert second.status is OrderStatus.ORDERED and second.order_id != first.order_id
    assert book.store.get_order(first.order_id).status is OrderStatus.REJECTED


def test_an_offer_can_be_ordered_again_once_its_waiting_order_is_past_its_time(
    book, samples, agent_hotel: Identity
) -> None:
    soon = samples.now + timedelta(hours=1)
    offer = book.offer(samples.above_order_limit("opt_1", valid_until=soon), samples.within_authority("opt_2"))
    first = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")
    book.clock.advance(timedelta(hours=2))  # nobody has read the first order since: it is still stored as waiting

    second = book.service.place_order(offer.offer_id, "opt_2", agent_hotel, "key-2")

    assert second.status is OrderStatus.ORDERED
    assert book.store.get_order(first.order_id).status is OrderStatus.EXPIRED
    assert book.event_types() == ["approval.requested", "order.expired", "order.placed_by_agent"]


def test_an_order_of_another_offer_does_not_stand_in_the_way(book, samples, agent_hotel: Identity) -> None:
    other = book.offer(samples.above_order_limit())
    book.service.place_order(other.offer_id, "opt_1", agent_hotel, "key-1")
    offer = book.offer(samples.within_authority())

    assert book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-2").status is OrderStatus.ORDERED
