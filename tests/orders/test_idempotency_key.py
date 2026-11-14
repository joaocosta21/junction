"""The Idempotency-Key of an order: its accepted form, and a key that another writer bound first."""

from __future__ import annotations

import pytest

from tta.contracts.common import Identity
from tta.contracts.errors import InvalidRequest, SupplierUnavailable

KEY = "key-1"


@pytest.mark.parametrize(
    "key", ["key 1", "key/1", "clé", "k" * 101, "key-1\n", "{key}", "key;1"],
    ids=["a space", "a slash", "a letter with an accent", "101 characters", "a line break", "braces", "a semicolon"],
)
def test_an_idempotency_key_outside_the_accepted_form_is_invalid(
    key: str, book, samples, agent_hotel: Identity
) -> None:
    offer = book.offer(samples.within_authority())

    with pytest.raises(InvalidRequest) as raised:
        book.service.place_order(offer.offer_id, "opt_1", agent_hotel, key)

    assert "1 to 100 characters" in raised.value.detail and key.strip() not in raised.value.detail
    assert book.store.list_orders() == () and book.revalidator.calls == [] and book.events() == ()


@pytest.mark.parametrize(
    "key", ["k", "K" * 100, "8f14e45f-ceea-467f-a2b1-9c3d5e6f7a8b", "agent:run_7.order-1"],
    ids=["one character", "100 characters", "a UUID", "every accepted sign"],
)
def test_an_idempotency_key_of_the_accepted_form_places_the_order(
    key: str, book, samples, agent_hotel: Identity
) -> None:
    offer = book.offer(samples.within_authority())

    order = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, key)

    assert order.idempotency_key == key and book.store.order_id_for_key(key, agent_hotel.id) == order.order_id


def test_a_key_that_another_writer_bound_first_is_not_given_a_second_order(
    book, samples, agent_hotel: Identity
) -> None:
    """Two gateway processes on one database: the other one bound the key after this one looked it up."""
    offer = book.offer(samples.within_authority())
    book.store.remember_idempotency_key(KEY, agent_hotel.id, "ord_of_the_other")

    with pytest.raises(SupplierUnavailable) as raised:
        book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert "Send the request again" in raised.value.detail
    assert book.store.list_orders() == () and book.events() == ()
    assert book.store.order_id_for_key(KEY, agent_hotel.id) == "ord_of_the_other"
