"""A bounded read of the audit trail (review H2): a page of one reader's events, newest first, each with the hash
of the event stored before it, so a page can be checked without reading the whole chain.

Scores on the 15% "credible path toward production" (reading the trail costs the page, not the trail) and on the
20% "how decisions are logged and auditable" (what a page returns can still be checked against the chain).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tta.contracts.audit import GENESIS_HASH
from tta.store import SqliteStore


def _hash(number: int) -> str:
    return f"{number:064x}"


@pytest.fixture
def store(samples) -> Iterator[SqliteStore]:
    """Ten events: odd ones of the hotel, even ones of the ward; event 4 is the ward's order 2, event 2 its offer."""
    store = SqliteStore()
    for number in range(1, 11):
        hotel = number % 2 == 1
        store.append_audit_event(samples.event(
            f"evt_{number}", previous_hash=GENESIS_HASH if number == 1 else _hash(number - 1), event_hash=_hash(number),
            profile_id="hotel-kitchen" if hotel else "allergy-ward",
            offer_id="off_1" if hotel else "off_2",
            order_id=None if number in (1, 2) else ("ord_1" if hotel else "ord_2"),
        ))
    yield store
    store.close()


def test_the_trail_is_counted_without_reading_it(store: SqliteStore) -> None:
    assert store.count_audit_events() == 10
    empty = SqliteStore()
    assert empty.count_audit_events() == 0
    empty.close()


def test_a_page_is_the_newest_events_first_each_with_the_hash_stored_before_it(store: SqliteStore) -> None:
    page = store.audit_events_page(limit=3)

    assert [event.id for event, _ in page] == ["evt_10", "evt_9", "evt_8"]
    assert [before for _, before in page] == [_hash(9), _hash(8), _hash(7)]
    assert all(event.data.previous_hash == before for event, before in page)


def test_the_first_event_of_the_trail_has_no_event_before_it(store: SqliteStore) -> None:
    page = store.audit_events_page(limit=20)

    assert len(page) == 10 and page[-1][0].id == "evt_1" and page[-1][1] is None


def test_a_page_of_one_buyer_holds_its_events_only_and_the_hash_before_is_of_the_whole_chain(
    store: SqliteStore,
) -> None:
    page = store.audit_events_page(limit=2, profile_id="hotel-kitchen")

    assert [event.id for event, _ in page] == ["evt_9", "evt_7"]
    assert [before for _, before in page] == [_hash(8), _hash(6)]  # the events before them are the ward's


def test_the_next_page_starts_before_the_position_of_an_event(store: SqliteStore) -> None:
    position = store.audit_position("evt_7", profile_id="hotel-kitchen")
    assert position is not None

    page = store.audit_events_page(limit=2, profile_id="hotel-kitchen", before=position)

    assert [event.id for event, _ in page] == ["evt_5", "evt_3"]


def test_an_event_nobody_stored_or_of_another_buyer_has_no_position(store: SqliteStore) -> None:
    assert store.audit_position("evt_99") is None
    assert store.audit_position("evt_2", profile_id="hotel-kitchen") is None
    assert store.audit_position("evt_2") is not None  # the reader of every buyer's events


def test_the_trail_of_an_order_starts_with_its_offers_events_that_belong_to_no_order(store: SqliteStore) -> None:
    # As `tta.audit.views.select`: the order's own events, and the events of its offer that have no order.
    ward = store.audit_events_page(limit=20, order_id="ord_2", profile_id="allergy-ward")
    hotel = store.audit_events_page(limit=20, order_id="ord_2", profile_id="hotel-kitchen")
    by_offer = store.audit_events_page(limit=20, offer_id="off_1")

    assert [event.id for event, _ in ward] == ["evt_10", "evt_8", "evt_6", "evt_4", "evt_2"]
    assert hotel == ()
    assert [event.id for event, _ in by_offer] == ["evt_9", "evt_7", "evt_5", "evt_3", "evt_1"]
