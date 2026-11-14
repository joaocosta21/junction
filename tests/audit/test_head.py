"""`AuditTrail.head()` is cheap: it reads the whole trail once, then only the last hash (task FIX-8, finding 5).

`/healthz` is public and calls it on every request. The head must still be right after an event this trail
writes, after another writer's event, after a block that was taken back, and after the end was cut off.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from tta.audit import AuditTrail
from tta.contracts.audit import GENESIS_HASH, AuditContext, AuditEvent, AuditEventType
from tta.store import SqliteStore

DROP_THE_GUARD = "DROP TRIGGER IF EXISTS audit_events_no_delete;"


class CountingStore:
    """A store that counts how often the whole trail is read."""

    def __init__(self, store: SqliteStore) -> None:
        self._store = store
        self.whole_trail_reads = 0

    def list_audit_events(self, *args: Any, **kwargs: Any) -> tuple[AuditEvent, ...]:
        self.whole_trail_reads += 1
        return self._store.list_audit_events(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "audit.sqlite3"


@pytest.fixture
def counting(db_path: Path) -> Any:
    store = SqliteStore(db_path)
    yield CountingStore(store)
    store.close()


def _record(trail: AuditTrail, samples: Any) -> AuditEvent:
    return trail.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext())


def test_the_whole_trail_is_read_once_however_often_the_head_is_asked(
    counting: CountingStore, samples: Any, demo_clock: Any
) -> None:
    writer = AuditTrail(counting, demo_clock)
    written = [_record(writer, samples) for _ in range(3)]
    reader = AuditTrail(counting, demo_clock)  # a trail that has written nothing: its first head is a read

    heads = [reader.head() for _ in range(20)]

    assert set(heads) == {(3, written[-1].data.hash)}
    assert counting.whole_trail_reads == 1


def test_an_empty_trail_is_remembered_too(counting: CountingStore, demo_clock: Any) -> None:
    trail = AuditTrail(counting, demo_clock)

    assert [trail.head() for _ in range(5)] == [(0, GENESIS_HASH)] * 5
    assert counting.whole_trail_reads == 1


def test_the_head_follows_each_event_the_trail_writes_without_reading_the_trail_again(
    counting: CountingStore, samples: Any, demo_clock: Any
) -> None:
    trail = AuditTrail(counting, demo_clock)
    assert trail.head() == (0, GENESIS_HASH)

    for number in range(1, 6):
        event = _record(trail, samples)
        assert trail.head() == (number, event.data.hash)

    assert counting.whole_trail_reads == 1


def test_an_event_of_another_writer_makes_the_head_read_the_trail_again(
    counting: CountingStore, db_path: Path, samples: Any, demo_clock: Any
) -> None:
    trail = AuditTrail(counting, demo_clock)
    _record(trail, samples)
    assert trail.head()[0] == 1
    other_store = SqliteStore(db_path)
    theirs = _record(AuditTrail(other_store, demo_clock), samples)
    other_store.close()

    assert trail.head() == (2, theirs.data.hash)
    assert trail.head() == (2, theirs.data.hash)
    assert counting.whole_trail_reads == 2

    ours = _record(trail, samples)  # and the count goes on from what was read
    assert trail.head() == (3, ours.data.hash)
    assert counting.whole_trail_reads == 2


def test_an_event_written_before_the_first_head_is_not_counted_from_nothing(
    counting: CountingStore, db_path: Path, samples: Any, demo_clock: Any
) -> None:
    earlier_store = SqliteStore(db_path)
    earlier = AuditTrail(earlier_store, demo_clock)
    for _ in range(4):
        _record(earlier, samples)
    earlier_store.close()
    trail = AuditTrail(counting, demo_clock)

    event = _record(trail, samples)  # the trail has never read the head: it must not answer (1, …)

    assert trail.head() == (5, event.data.hash)


def test_an_event_taken_back_with_its_block_is_not_in_the_head(
    counting: CountingStore, samples: Any, demo_clock: Any
) -> None:
    trail = AuditTrail(counting, demo_clock)
    kept = _record(trail, samples)
    assert trail.head() == (1, kept.data.hash)

    with pytest.raises(RuntimeError, match="after the event"), counting.atomic():
        _record(trail, samples)
        raise RuntimeError("a write after the event failed")

    assert trail.head() == (1, kept.data.hash)
    assert len(counting.list_audit_events()) == 1


def test_a_trail_cut_off_at_the_end_shows_in_the_head_of_a_trail_that_had_read_it(
    counting: CountingStore, db_path: Path, samples: Any, demo_clock: Any
) -> None:
    trail = AuditTrail(counting, demo_clock)
    written = [_record(trail, samples) for _ in range(5)]
    kept_by_another_party = trail.head()

    with closing(sqlite3.connect(db_path)) as connection:  # behind the store's back
        connection.executescript(DROP_THE_GUARD)
        connection.execute("DELETE FROM audit_events WHERE event_id IN (?, ?)", (written[3].id, written[4].id))
        connection.commit()

    assert kept_by_another_party == (5, written[4].data.hash)
    assert trail.head() == (3, written[2].data.hash)
