"""The hash chain: SHA-256 over the canonical JSON, and `verify_chain` names the first event that does not match."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import pytest

from tta.audit import AuditTrail
from tta.audit.chain import event_hash
from tta.contracts.audit import GENESIS_HASH, AuditContext, AuditEvent, AuditEventType
from tta.store import SqliteStore


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
    """What someone with access to the database file could do, behind the store's back."""
    with closing(sqlite3.connect(db_path)) as raw, raw:
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
