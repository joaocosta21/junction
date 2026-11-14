"""The SQLite store: round trips, idempotency keys, the append-only audit table, files and threads."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import closing
from decimal import Decimal
from pathlib import Path

import pytest

from tta.config import Settings
from tta.contracts.common import ApprovalStatus, OrderStatus
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import Store
from tta.store import SqliteStore, open_store


@pytest.fixture
def store() -> Iterator[SqliteStore]:
    store = SqliteStore()
    yield store
    store.close()


def test_the_store_implements_the_store_port(store: SqliteStore) -> None:
    assert isinstance(store, Store)


def test_an_offer_comes_back_as_it_was_saved(store: SqliteStore, samples) -> None:
    offer = samples.offer()

    store.save_offer(offer)

    assert store.get_offer("off_1") == offer
    assert store.get_offer("off_unknown") is None


def test_saving_an_offer_again_replaces_it(store: SqliteStore, samples) -> None:
    offer = samples.offer()
    store.save_offer(offer)

    store.save_offer(offer.model_copy(update={"notes": ("Rebuilt.",)}))

    assert store.get_offer("off_1").notes == ("Rebuilt.",)


def test_an_order_comes_back_as_it_was_saved(store: SqliteStore, samples) -> None:
    order = samples.order()

    store.save_order(order)

    assert store.get_order("ord_1") == order
    assert store.get_order("ord_unknown") is None


def test_decimals_keep_every_digit_through_the_store(store: SqliteStore, samples) -> None:
    order = samples.order()
    precise = order.model_copy(update={"option": order.option.model_copy(update={"fill_ratio": Decimal("0.69833333")})})

    store.save_order(precise)

    loaded = store.get_order("ord_1")
    assert loaded.option.fill_ratio == Decimal("0.69833333")
    assert loaded.option.totals.net == Decimal("1849.70")
    assert isinstance(loaded.reliance[0].available_amount, Decimal)


def test_saving_an_order_again_replaces_it_and_keeps_its_place(store: SqliteStore, samples) -> None:
    store.save_order(samples.order("ord_1"))
    store.save_order(samples.order("ord_2"))

    store.save_order(samples.order("ord_1", status=OrderStatus.ORDERED))

    assert store.get_order("ord_1").status is OrderStatus.ORDERED
    assert [order.order_id for order in store.list_orders()] == ["ord_1", "ord_2"]


def test_orders_are_listed_by_profile_and_status(store: SqliteStore, samples) -> None:
    store.save_order(samples.order("ord_1", status=OrderStatus.ORDERED))
    store.save_order(samples.order("ord_2", status=OrderStatus.PENDING_APPROVAL))
    store.save_order(samples.order("ord_3", status=OrderStatus.REJECTED))
    store.save_order(samples.order("ord_4", profile_id="allergy-ward", status=OrderStatus.ORDERED))

    committed = store.list_orders("hotel-kitchen", (OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL))

    assert [order.order_id for order in committed] == ["ord_1", "ord_2"]
    assert [order.order_id for order in store.list_orders("allergy-ward")] == ["ord_4"]
    assert [order.order_id for order in store.list_orders(statuses=(OrderStatus.ORDERED,))] == ["ord_1", "ord_4"]
    assert store.list_orders("hotel-kitchen", ()) == ()
    assert len(store.list_orders()) == 4


def test_an_approval_comes_back_as_it_was_saved(store: SqliteStore, samples) -> None:
    pending = samples.approval()
    store.save_approval(pending)
    assert store.get_approval("apr_1") == pending

    approved = samples.approval(status=ApprovalStatus.APPROVED)
    store.save_approval(approved)

    assert store.get_approval("apr_1") == approved
    assert store.get_approval("apr_1").decisions[0].note == "Weekly volume, OK."
    assert store.get_approval("apr_unknown") is None


def test_approvals_are_listed_by_profile_and_status(store: SqliteStore, samples) -> None:
    store.save_approval(samples.approval("apr_1"))
    store.save_approval(samples.approval("apr_2", status=ApprovalStatus.APPROVED))
    store.save_approval(samples.approval("apr_3", profile_id="allergy-ward"))

    assert [a.approval_id for a in store.list_approvals(status=ApprovalStatus.PENDING)] == ["apr_1", "apr_3"]
    assert [a.approval_id for a in store.list_approvals("hotel-kitchen")] == ["apr_1", "apr_2"]
    assert [a.approval_id for a in store.list_approvals("hotel-kitchen", ApprovalStatus.APPROVED)] == ["apr_2"]
    assert len(store.list_approvals()) == 3


def test_an_idempotency_key_stored_twice_returns_the_first_order(store: SqliteStore) -> None:
    first = store.remember_idempotency_key("key-1", "agent:hotel-kitchen", "ord_1")
    second = store.remember_idempotency_key("key-1", "agent:hotel-kitchen", "ord_2")

    assert first == "ord_1"
    assert second == "ord_1"
    assert store.order_id_for_key("key-1", "agent:hotel-kitchen") == "ord_1"


def test_an_idempotency_key_belongs_to_its_scope(store: SqliteStore) -> None:
    store.remember_idempotency_key("key-1", "agent:hotel-kitchen", "ord_1")

    assert store.order_id_for_key("key-1", "agent:allergy-ward") is None
    assert store.remember_idempotency_key("key-1", "agent:allergy-ward", "ord_9") == "ord_9"
    assert store.order_id_for_key("key-unknown", "agent:hotel-kitchen") is None


def test_audit_events_come_back_in_the_order_they_were_appended(store: SqliteStore, samples) -> None:
    first = samples.event("evt_1", event_hash="1" * 64)
    second = samples.event("evt_2", previous_hash="1" * 64, event_hash="2" * 64)
    assert store.last_audit_hash() is None

    store.append_audit_event(first)
    store.append_audit_event(second)

    assert store.list_audit_events() == (first, second)
    assert store.last_audit_hash() == "2" * 64


def test_audit_events_are_filtered_by_order_offer_and_profile(store: SqliteStore, samples) -> None:
    store.append_audit_event(samples.event("evt_1", order_id=None))
    store.append_audit_event(samples.event("evt_2"))
    store.append_audit_event(samples.event("evt_3", order_id="ord_2", offer_id="off_2", profile_id="allergy-ward"))

    assert [e.id for e in store.list_audit_events(order_id="ord_1")] == ["evt_2"]
    assert [e.id for e in store.list_audit_events(offer_id="off_1")] == ["evt_1", "evt_2"]
    assert [e.id for e in store.list_audit_events(profile_id="allergy-ward")] == ["evt_3"]
    assert [e.id for e in store.list_audit_events(order_id="ord_2", profile_id="hotel-kitchen")] == []


def test_an_audit_event_cannot_be_appended_twice(store: SqliteStore, samples) -> None:
    original = samples.event("evt_1")
    store.append_audit_event(original)
    changed = original.model_copy(update={"subject": "order/ord_other"})

    with pytest.raises(ValueError, match="append-only"):
        store.append_audit_event(changed)

    assert store.list_audit_events() == (original,)


def test_the_store_offers_no_way_to_change_or_remove_an_audit_event(store: SqliteStore) -> None:
    audit_methods = [name for name in dir(store) if "audit" in name and not name.startswith("_")]

    assert sorted(audit_methods) == ["append_audit_event", "last_audit_hash", "list_audit_events"]


def test_a_file_database_uses_wal_and_keeps_its_data_when_reopened(tmp_path: Path, samples) -> None:
    path = tmp_path / "tta.sqlite3"
    store = SqliteStore(path)
    store.save_offer(samples.offer())
    store.append_audit_event(samples.event("evt_1"))
    store.close()

    with closing(sqlite3.connect(path)) as raw:
        assert raw.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    reopened = SqliteStore(path)

    assert reopened.get_offer("off_1") == samples.offer()
    assert [event.id for event in reopened.list_audit_events()] == ["evt_1"]
    reopened.close()


def test_open_store_takes_the_path_from_the_settings(settings: Settings, samples) -> None:
    store = open_store(settings)
    store.save_offer(samples.offer())
    store.close()

    assert settings.db_path.is_file()
    assert settings.db_path.parent == settings.tta_data_dir


def test_the_store_can_be_used_from_another_thread(store: SqliteStore, samples) -> None:
    errors: list[Exception] = []

    def save() -> None:
        try:
            store.save_order(samples.order("ord_thread"))
        except Exception as error:  # the test reports whatever the thread raised
            errors.append(error)

    thread = threading.Thread(target=save)
    thread.start()
    thread.join()

    assert errors == []
    assert store.get_order("ord_thread") is not None


def test_a_database_that_cannot_be_opened_is_reported_as_a_typed_error(tmp_path: Path) -> None:
    not_a_database = tmp_path / "notes.txt"
    not_a_database.write_bytes(b"These bytes are not an SQLite database, whatever the file is called." * 20)

    with pytest.raises(SupplierUnavailable):
        SqliteStore(tmp_path)  # a directory, not a file
    with pytest.raises(SupplierUnavailable):
        SqliteStore(not_a_database)


def test_a_database_failure_is_reported_as_a_typed_error(store: SqliteStore) -> None:
    store.close()

    with pytest.raises(SupplierUnavailable) as raised:
        store.get_offer("off_1")

    assert "database" in raised.value.detail
