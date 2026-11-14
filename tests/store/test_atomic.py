"""`SqliteStore.atomic()`: everything saved or appended inside one block is committed together, or not at all."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from tta.contracts.common import OrderStatus
from tta.contracts.errors import SupplierUnavailable
from tta.store import AuditChainConflict, SqliteStore, sqlite_store

AGENT = "agent:hotel-kitchen"
JOIN_SECONDS = 10
SHORT_WAIT_SECONDS = 0.2


class Failure(Exception):
    """Raised by a test inside a block, to stand for any failure between two writes."""


@pytest.fixture
def store() -> Iterator[SqliteStore]:
    store = SqliteStore()
    yield store
    store.close()


def _write_one_outcome(store: SqliteStore, samples) -> None:
    """The four writes of an order sent to a human: its key, the order, the approval and the audit event."""
    store.remember_idempotency_key("key-1", AGENT, "ord_1")
    store.save_order(samples.order("ord_1"))
    store.save_approval(samples.approval("apr_1"))
    store.append_audit_event(samples.event("evt_1", event_hash="1" * 64))


def _holds_nothing(store: SqliteStore) -> bool:
    return (
        store.list_orders() == () and store.list_approvals() == () and store.list_audit_events() == ()
        and store.last_audit_hash() is None and store.order_id_for_key("key-1", AGENT) is None
    )


def test_everything_written_inside_a_block_is_kept_when_the_block_ends(store: SqliteStore, samples) -> None:
    with store.atomic():
        _write_one_outcome(store, samples)

    assert store.get_order("ord_1") == samples.order("ord_1")
    assert store.get_approval("apr_1") == samples.approval("apr_1")
    assert store.order_id_for_key("key-1", AGENT) == "ord_1"
    assert [event.id for event in store.list_audit_events()] == ["evt_1"]


def test_a_failure_inside_a_block_leaves_nothing_of_it_and_reaches_the_caller(store: SqliteStore, samples) -> None:
    with pytest.raises(Failure), store.atomic():
        _write_one_outcome(store, samples)
        raise Failure

    assert _holds_nothing(store)


def test_what_was_stored_before_a_failed_block_is_untouched(store: SqliteStore, samples) -> None:
    store.save_order(samples.order("ord_1"))
    store.append_audit_event(samples.event("evt_1", event_hash="1" * 64))

    with pytest.raises(Failure), store.atomic():
        store.save_order(samples.order("ord_1", status=OrderStatus.ORDERED))
        store.append_audit_event(samples.event("evt_2", previous_hash="1" * 64, event_hash="2" * 64))
        raise Failure

    assert store.get_order("ord_1").status is OrderStatus.PENDING_APPROVAL
    assert [event.id for event in store.list_audit_events()] == ["evt_1"] and store.last_audit_hash() == "1" * 64


def test_reads_inside_a_block_see_what_the_block_wrote(store: SqliteStore, samples) -> None:
    with store.atomic():
        _write_one_outcome(store, samples)

        assert store.get_order("ord_1") is not None and store.last_audit_hash() == "1" * 64
        assert store.order_id_for_key("key-1", AGENT) == "ord_1"


def test_the_audit_head_check_holds_inside_a_block(store: SqliteStore, samples) -> None:
    store.append_audit_event(samples.event("evt_1", event_hash="1" * 64))

    with pytest.raises(AuditChainConflict), store.atomic():
        store.save_order(samples.order("ord_1"))
        store.append_audit_event(samples.event("evt_fork", event_hash="2" * 64))  # names the genesis hash again

    assert store.list_orders() == () and [event.id for event in store.list_audit_events()] == ["evt_1"]


def test_two_events_appended_in_one_block_follow_each_other(store: SqliteStore, samples) -> None:
    with store.atomic():
        store.append_audit_event(samples.event("evt_1", event_hash="1" * 64))
        store.append_audit_event(samples.event("evt_2", previous_hash="1" * 64, event_hash="2" * 64))

    assert [event.id for event in store.list_audit_events()] == ["evt_1", "evt_2"]


def test_an_event_id_already_stored_is_still_refused_inside_a_block(store: SqliteStore, samples) -> None:
    with pytest.raises(ValueError, match="append-only"), store.atomic():
        store.append_audit_event(samples.event("evt_1", event_hash="1" * 64))
        store.append_audit_event(samples.event("evt_1", previous_hash="1" * 64, event_hash="2" * 64))

    assert store.list_audit_events() == ()


def test_a_block_inside_a_block_is_committed_with_the_outer_one(store: SqliteStore, samples) -> None:
    with pytest.raises(Failure), store.atomic():
        with store.atomic():
            store.save_order(samples.order("ord_inner"))
        store.save_order(samples.order("ord_outer"))
        raise Failure

    assert store.list_orders() == ()

    with store.atomic():
        with store.atomic():
            store.save_order(samples.order("ord_inner"))
        store.save_order(samples.order("ord_outer"))

    assert [order.order_id for order in store.list_orders()] == ["ord_inner", "ord_outer"]


def test_an_inner_block_that_fails_takes_back_only_its_own_writes(store: SqliteStore, samples) -> None:
    with store.atomic():
        store.save_order(samples.order("ord_outer"))
        with pytest.raises(Failure), store.atomic():
            store.save_order(samples.order("ord_inner"))
            raise Failure
        store.save_approval(samples.approval("apr_outer"))

    assert [order.order_id for order in store.list_orders()] == ["ord_outer"]
    assert [approval.approval_id for approval in store.list_approvals()] == ["apr_outer"]


def test_the_store_works_as_before_once_a_block_has_ended(store: SqliteStore, samples) -> None:
    with pytest.raises(Failure), store.atomic():
        store.save_order(samples.order("ord_1"))
        raise Failure

    store.save_order(samples.order("ord_2"))  # outside a block: committed at once
    with store.atomic():
        store.save_order(samples.order("ord_3"))

    assert [order.order_id for order in store.list_orders()] == ["ord_2", "ord_3"]


def test_another_connection_sees_nothing_of_a_block_until_it_ends(tmp_path: Path, samples) -> None:
    path = tmp_path / "tta.sqlite3"
    writer, reader = SqliteStore(path), SqliteStore(path)

    with writer.atomic():
        _write_one_outcome(writer, samples)
        assert _holds_nothing(reader)
    assert reader.get_order("ord_1") is not None and reader.last_audit_hash() == "1" * 64

    with pytest.raises(Failure), writer.atomic():
        writer.save_order(samples.order("ord_2"))
        raise Failure
    assert reader.get_order("ord_2") is None
    writer.close()
    reader.close()


def test_another_thread_waits_for_the_block_and_then_sees_all_of_it(store: SqliteStore, samples) -> None:
    inside, seen = threading.Event(), []

    def read() -> None:
        inside.wait(timeout=JOIN_SECONDS)
        seen.append((store.get_order("ord_1"), store.get_approval("apr_1"), store.last_audit_hash()))

    reader = threading.Thread(target=read)
    reader.start()
    with store.atomic():
        store.save_order(samples.order("ord_1"))
        inside.set()
        reader.join(timeout=SHORT_WAIT_SECONDS)  # the reader cannot finish while the block is open
        assert seen == []
        store.save_approval(samples.approval("apr_1"))
        store.append_audit_event(samples.event("evt_1", event_hash="1" * 64))
    reader.join(timeout=JOIN_SECONDS)

    assert seen == [(samples.order("ord_1"), samples.approval("apr_1"), "1" * 64)]


def test_a_thread_that_waits_too_long_for_another_threads_block_gets_a_typed_error_and_the_block_goes_on(
    store: SqliteStore, samples, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The audit trail holds its own lock while it calls the store. A thread inside a block that then needs that
    lock, and a thread that holds it and needs the store, would wait for each other for ever; the wait is bounded."""
    monkeypatch.setattr(sqlite_store, "LOCK_WAIT_SECONDS", SHORT_WAIT_SECONDS)
    trail_lock, inside, outcomes = threading.Lock(), threading.Event(), []

    def record_from_another_thread() -> None:
        with trail_lock:
            inside.set()
            try:
                outcomes.append(store.last_audit_hash())
            except SupplierUnavailable as error:
                outcomes.append(error)

    other = threading.Thread(target=record_from_another_thread)
    with store.atomic():
        store.save_order(samples.order("ord_1"))
        other.start()
        inside.wait(timeout=JOIN_SECONDS)
        with trail_lock:  # free only once the other thread gave up waiting for the store
            store.append_audit_event(samples.event("evt_1", event_hash="1" * 64))
    other.join(timeout=JOIN_SECONDS)

    (outcome,) = outcomes
    assert isinstance(outcome, SupplierUnavailable) and "busy" in outcome.detail
    assert store.get_order("ord_1") is not None and store.last_audit_hash() == "1" * 64


def test_a_database_failure_inside_a_block_is_a_typed_error_and_ends_the_block(tmp_path: Path, samples) -> None:
    store = SqliteStore(tmp_path / "tta.sqlite3")

    with pytest.raises(SupplierUnavailable), store.atomic():
        store.save_order(samples.order("ord_1"))
        store.close()
        store.save_approval(samples.approval("apr_1"))  # the connection is gone

    reopened = SqliteStore(tmp_path / "tta.sqlite3")
    assert reopened.list_orders() == () and reopened.list_approvals() == ()
    reopened.close()


def test_a_block_that_cannot_be_committed_is_a_typed_error_and_stores_nothing(tmp_path: Path, samples) -> None:
    store = SqliteStore(tmp_path / "tta.sqlite3")

    with pytest.raises(SupplierUnavailable), store.atomic():
        store.save_order(samples.order("ord_1"))
        store.close()  # the last thing the block does: the commit has no connection left

    reopened = SqliteStore(tmp_path / "tta.sqlite3")
    assert reopened.list_orders() == ()
    reopened.close()


def test_a_block_cannot_be_opened_on_a_closed_database(store: SqliteStore) -> None:
    store.close()

    with pytest.raises(SupplierUnavailable), store.atomic():
        pytest.fail("the block must not start")
