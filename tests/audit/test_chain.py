"""The hash chain: SHA-256 over the canonical JSON, and `verify_chain` names the first event that does not match.

Also what a view may say about the chain, several writers on one database file, and the head another party keeps.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

from tta.audit import AuditTrail
from tta.audit.chain import event_hash
from tta.audit.trail import MAX_APPEND_ATTEMPTS
from tta.contracts.audit import GENESIS_HASH, AuditContext, AuditEvent, AuditEventType
from tta.contracts.common import AuditReader
from tta.store import AuditChainConflict, SqliteStore

HOTEL = "hotel-kitchen"
WARD = "allergy-ward"
DROP_THE_GUARDS = (
    "DROP TRIGGER IF EXISTS audit_events_no_update; DROP TRIGGER IF EXISTS audit_events_no_delete;"
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "audit.sqlite3"


@pytest.fixture
def events(db_path: Path, samples, demo_clock) -> tuple[AuditEvent, ...]:
    """Five events written to a database file, so a test can change the file behind the store's back."""
    store = SqliteStore(db_path)
    trail = AuditTrail(store, demo_clock)
    for number in range(5):
        trail.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway,
                     AuditContext(facts={"products_looked_up": number}))
    written = store.list_audit_events()
    store.close()
    return written


def _verify(db_path: Path, demo_clock):
    store = SqliteStore(db_path)
    try:
        return AuditTrail(store, demo_clock).verify_chain()
    finally:
        store.close()


def _change_file(db_path: Path, statement: str, parameters: tuple[str, ...]) -> None:
    """What someone who can write the database file could do, behind the store's back: drop the two triggers
    that refuse a rewrite, then change a row."""
    with closing(sqlite3.connect(db_path)) as raw:
        raw.executescript(DROP_THE_GUARDS)
        with raw:
            raw.execute(statement, parameters)


def _rewrite(db_path: Path, event: AuditEvent) -> None:
    _change_file(db_path, "UPDATE audit_events SET body = ?, hash = ? WHERE event_id = ?",
                 (event.model_dump_json(), event.data.hash, event.id))


def _remove(db_path: Path, event: AuditEvent) -> None:
    _change_file(db_path, "DELETE FROM audit_events WHERE event_id = ?", (event.id,))


def _with_sentence(event: AuditEvent, sentence: str) -> AuditEvent:
    return event.model_copy(update={"data": event.data.model_copy(update={"sentence": sentence})})


def test_the_hash_is_sha256_over_the_canonical_json_without_the_hash(events: tuple[AuditEvent, ...]) -> None:
    event = events[2]
    payload = event.model_dump(mode="json")
    del payload["data"]["hash"]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    assert event.data.hash == hashlib.sha256(canonical).hexdigest()
    assert event_hash(event) == event.data.hash


def test_an_empty_trail_verifies(trail: AuditTrail) -> None:
    result = trail.verify_chain()

    assert (result.ok, result.checked, result.first_bad_event_id) == (True, 0, None)
    assert result.sentence == "The audit trail is empty."


def test_a_trail_of_one_event_verifies(trail: AuditTrail, samples) -> None:
    trail.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext())

    result = trail.verify_chain()

    assert (result.ok, result.checked) == (True, 1)
    assert result.sentence == "The audit trail is intact: its only event matches its hash."


def test_an_untouched_trail_verifies(db_path: Path, events: tuple[AuditEvent, ...], demo_clock) -> None:
    result = _verify(db_path, demo_clock)

    assert (result.ok, result.checked, result.first_bad_event_id) == (True, 5, None)
    assert result.sentence == (
        "The audit trail is intact: each of its 5 events matches its hash and follows the one before."
    )
    assert events[0].data.previous_hash == GENESIS_HASH
    assert [event.data.previous_hash for event in events[1:]] == [event.data.hash for event in events[:-1]]


def test_changing_one_stored_event_makes_verify_chain_name_it(
    db_path: Path, events: tuple[AuditEvent, ...], demo_clock
) -> None:
    _rewrite(db_path, _with_sentence(events[2], "The gateway looked up nothing."))

    result = _verify(db_path, demo_clock)

    assert result.ok is False
    assert result.first_bad_event_id == events[2].id
    assert result.checked == 3
    assert result.sentence == (
        f"The audit trail does not verify: event {events[2].id} (number 3 of 5) was changed after it was "
        "written. It and every later event cannot be trusted."
    )


def test_changing_an_event_and_its_hash_breaks_the_link_from_the_next_event(
    db_path: Path, events: tuple[AuditEvent, ...], demo_clock
) -> None:
    changed = _with_sentence(events[2], "The gateway looked up nothing.")
    rehashed = changed.model_copy(update={"data": changed.data.model_copy(update={"hash": event_hash(changed)})})
    _rewrite(db_path, rehashed)

    result = _verify(db_path, demo_clock)

    assert result.ok is False
    assert result.first_bad_event_id == events[3].id
    assert result.sentence == (
        f"The audit trail does not verify: event {events[3].id} (number 4 of 5) does not follow the event "
        "before it; an event was changed, removed or inserted. It and every later event cannot be trusted."
    )


def test_removing_an_event_makes_verify_chain_name_the_one_after_it(
    db_path: Path, events: tuple[AuditEvent, ...], demo_clock
) -> None:
    _remove(db_path, events[1])

    result = _verify(db_path, demo_clock)

    assert (result.ok, result.first_bad_event_id, result.checked) == (False, events[2].id, 2)


def test_removing_the_first_event_is_noticed(db_path: Path, events: tuple[AuditEvent, ...], demo_clock) -> None:
    _remove(db_path, events[0])

    assert _verify(db_path, demo_clock).first_bad_event_id == events[1].id


def test_events_recorded_from_several_threads_still_form_one_chain(trail: AuditTrail, samples) -> None:
    def record_ten() -> None:
        for _ in range(10):
            trail.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext())

    threads = [threading.Thread(target=record_ten) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    result = trail.verify_chain()
    assert (result.ok, result.checked) == (True, 80)


@pytest.fixture
def two_buyers(db_path: Path, samples, demo_clock) -> tuple[AuditEvent, ...]:
    """Five events in one chain: hotel, ward, hotel, ward, hotel."""
    store = SqliteStore(db_path)
    trail = AuditTrail(store, demo_clock)
    for profile_id in (HOTEL, WARD, HOTEL, WARD, HOTEL):
        trail.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext(profile_id=profile_id))
    written = store.list_audit_events()
    store.close()
    return written


def _view(db_path: Path, demo_clock, profile_id: str):
    store = SqliteStore(db_path)
    try:
        return AuditTrail(store, demo_clock).view(AuditReader.BUYER, profile_id=profile_id)
    finally:
        store.close()


def test_a_view_counts_only_the_events_it_shows(db_path: Path, two_buyers: tuple[AuditEvent, ...], demo_clock) -> None:
    hotel = _view(db_path, demo_clock, HOTEL).chain
    ward = _view(db_path, demo_clock, WARD).chain

    assert (hotel.ok, hotel.checked, hotel.first_bad_event_id) == (True, 3, None)
    assert hotel.sentence == (
        "The audit trail is intact: each of the 3 events shown here matches its hash, and the chain they belong "
        "to verifies."
    )
    assert (ward.ok, ward.checked) == (True, 2)
    assert "5" not in hotel.sentence and "5" not in ward.sentence


def test_a_view_of_one_event_and_a_view_of_none_say_so_without_counting_other_events(
    db_path: Path, two_buyers: tuple[AuditEvent, ...], trail: AuditTrail, samples, demo_clock
) -> None:
    none_of_none = trail.view(AuditReader.BUYER, profile_id="nobody").chain
    trail.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext(profile_id=HOTEL))

    one = trail.view(AuditReader.BUYER, profile_id=HOTEL).chain
    none_of_five = _view(db_path, demo_clock, "nobody").chain
    none_of_one = trail.view(AuditReader.BUYER, profile_id="nobody").chain

    assert (one.ok, one.checked) == (True, 1)
    assert one.sentence == (
        "The audit trail is intact: the event shown here matches its hash, and the chain it belongs to verifies."
    )
    assert (none_of_five.ok, none_of_five.checked) == (True, 0)
    assert none_of_five.sentence == "No event is shown here; the chain of the audit trail verifies."
    assert none_of_none == none_of_one == none_of_five  # an empty view never says how long the trail is


def test_a_break_at_another_buyer_s_event_is_reported_without_naming_it(
    db_path: Path, two_buyers: tuple[AuditEvent, ...], demo_clock
) -> None:
    ward_event = two_buyers[1]
    _rewrite(db_path, _with_sentence(ward_event, "The gateway looked up nothing."))

    hotel = _view(db_path, demo_clock, HOTEL).chain
    whole = _verify(db_path, demo_clock)

    assert (hotel.ok, hotel.checked, hotel.first_bad_event_id) == (False, 3, None)
    assert hotel.sentence == (
        "The audit trail does not verify: it is broken at an event outside this view. "
        "Events shown here that were written after it cannot be trusted: 2 of 3."
    )
    assert ward_event.id not in hotel.sentence
    assert (whole.first_bad_event_id, whole.checked) == (ward_event.id, 2)
    assert "(number 2 of 5)" in whole.sentence


def test_a_break_at_an_event_of_the_view_names_it_by_its_place_in_the_view(
    db_path: Path, two_buyers: tuple[AuditEvent, ...], demo_clock
) -> None:
    hotel_event = two_buyers[2]
    _rewrite(db_path, _with_sentence(hotel_event, "The gateway looked up nothing."))

    hotel = _view(db_path, demo_clock, HOTEL).chain
    ward = _view(db_path, demo_clock, WARD).chain

    assert (hotel.ok, hotel.checked, hotel.first_bad_event_id) == (False, 3, hotel_event.id)
    assert hotel.sentence == (
        f"The audit trail does not verify: event {hotel_event.id} (number 2 of the 3 shown here) was changed "
        "after it was written. It and every later event cannot be trusted."
    )
    assert (ward.ok, ward.checked, ward.first_bad_event_id) == (False, 2, None)
    assert ward.sentence.endswith("Events shown here that were written after it cannot be trusted: 1 of 2.")
    assert hotel_event.id not in ward.sentence


class OvertakenStore:
    """A store whose reader is overtaken: after each of its first `times` reads of the head, a rival trail on
    the same database file appends an event, so the head just read is already old."""

    def __init__(self, store: SqliteStore, rival: AuditTrail, samples, times: int) -> None:
        self._store = store
        self._rival = rival
        self._samples = samples
        self._times = times

    def last_audit_hash(self) -> str | None:
        head = self._store.last_audit_hash()
        if self._times > 0:
            self._times -= 1
            self._rival.record(AuditEventType.LOOKUP_PERFORMED, self._samples.gateway, AuditContext())
        return head

    def __getattr__(self, name: str):
        return getattr(self._store, name)


@pytest.fixture
def two_stores(db_path: Path) -> Iterator[tuple[SqliteStore, SqliteStore]]:
    stores = (SqliteStore(db_path), SqliteStore(db_path))
    yield stores
    for store in stores:
        store.close()


def test_two_trails_on_one_database_file_write_one_chain(
    two_stores: tuple[SqliteStore, SqliteStore], samples, demo_clock
) -> None:
    one, other = (AuditTrail(store, demo_clock) for store in two_stores)

    written = [
        (one if number % 2 == 0 else other).record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext())
        for number in range(6)
    ]

    result = one.verify_chain()
    assert (result.ok, result.checked) == (True, 6)
    assert one.head() == other.head() == (6, written[-1].data.hash)


def test_a_trail_that_another_writer_overtakes_reads_the_head_again(
    two_stores: tuple[SqliteStore, SqliteStore], samples, demo_clock
) -> None:
    rival = AuditTrail(two_stores[0], demo_clock)
    overtaken = AuditTrail(OvertakenStore(two_stores[1], rival, samples, times=1), demo_clock)

    event = overtaken.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext())

    stored = two_stores[0].list_audit_events()
    assert [entry.id for entry in stored][-1] == event.id and len(stored) == 2
    assert event.data.previous_hash == stored[0].data.hash
    assert rival.verify_chain().ok is True


def test_a_trail_that_is_overtaken_every_time_gives_up_and_stores_nothing(
    two_stores: tuple[SqliteStore, SqliteStore], samples, demo_clock
) -> None:
    rival = AuditTrail(two_stores[0], demo_clock)
    overtaken = AuditTrail(OvertakenStore(two_stores[1], rival, samples, times=99), demo_clock)

    with pytest.raises(AuditChainConflict, match=f"{MAX_APPEND_ATTEMPTS} attempts"):
        overtaken.record(AuditEventType.APPROVAL_REQUESTED, samples.agent_hotel, AuditContext())

    result = rival.verify_chain()
    assert (result.ok, result.checked) == (True, MAX_APPEND_ATTEMPTS)
    assert all(entry.type == "tta.v1.lookup.performed" for entry in two_stores[0].list_audit_events())


def test_the_head_is_the_number_of_events_and_the_hash_of_the_last_one(trail: AuditTrail, samples) -> None:
    assert trail.head() == (0, GENESIS_HASH)

    written = [trail.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext()) for _ in range(3)]

    assert trail.head() == (3, written[-1].data.hash)


def test_cutting_off_the_end_still_verifies_and_only_a_head_kept_elsewhere_shows_it(
    db_path: Path, events: tuple[AuditEvent, ...], demo_clock
) -> None:
    kept_by_another_party = (5, events[-1].data.hash)
    _remove(db_path, events[4])
    _remove(db_path, events[3])

    store = SqliteStore(db_path)
    trail = AuditTrail(store, demo_clock)
    result, head = trail.verify_chain(), trail.head()
    store.close()

    assert (result.ok, result.checked) == (True, 3)  # the limit: a chain cut at the end is a shorter valid chain
    assert head == (3, events[2].data.hash)
    assert head != kept_by_another_party
