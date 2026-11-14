"""What the PostgreSQL store adds, on the real service: the database itself guards the audit trail, against any
connection; two stores on one schema cannot fork the chain; what is written survives a new store; the connection
is encrypted; a lost connection is opened again. The counterparts of the SQLite tests that need a file or a second
connection (`tests/store/`) are here too.
"""

from __future__ import annotations

import importlib.util
import threading
from collections.abc import Callable
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from pydantic import SecretStr

from tta.contracts.common import OrderStatus
from tta.contracts.errors import SupplierUnavailable
from tta.store import AuditChainConflict
from tta.store import postgres as postgres_module
from tta.store.postgres import PostgresStore

pytestmark = pytest.mark.live

Open = Callable[[], PostgresStore]
JOIN_SECONDS = 20
SHORT_WAIT_SECONDS = 0.2
AGENT = "agent:hotel-kitchen"


class Failure(Exception):
    """Raised by a test inside a block, to stand for any failure between two writes."""


def _load_samples() -> object:
    """The hand-built objects of `tests/store/conftest.py`, loaded from its file."""
    path = Path(__file__).resolve().parents[1] / "store" / "conftest.py"
    spec = importlib.util.spec_from_file_location("tta_reused_store_conftest_pg", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Samples()


samples = _load_samples()


def _in(schema: str, statement: str) -> sql.Composed:
    """A statement on the audit table of a test schema, as another program would send it."""
    return sql.SQL(statement).format(table=sql.Identifier(schema, "audit_events"))


# --- the database guards the audit trail -------------------------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    ["UPDATE {table} SET body = '{{}}', hash = 'x'",
     "DELETE FROM {table}",
     "TRUNCATE {table}",
     "INSERT INTO {table} (event_id, type, time, previous_hash, hash, body) "
     "SELECT event_id, type, time, 'p', 'h', body FROM {table} "
     "ON CONFLICT (event_id) DO UPDATE SET body = '{{}}'"],
)
def test_the_database_itself_refuses_to_change_or_remove_an_audit_event(
    pg_store: PostgresStore, admin: psycopg.Connection, pg_schema: str, statement: str
) -> None:
    original = samples.event("evt_1")
    pg_store.append_audit_event(original)

    with pytest.raises(psycopg.Error, match="append-only") as raised:
        admin.execute(_in(pg_schema, statement))  # another program on the same service, not this class

    assert raised.value.sqlstate == "TA001"
    assert pg_store.list_audit_events() == (original,)


def test_the_guard_holds_also_where_the_session_turns_ordinary_triggers_off(
    pg_store: PostgresStore, admin: psycopg.Connection, pg_schema: str
) -> None:
    """The service's admin user may set session_replication_role = replica, which skips ordinary triggers."""
    pg_store.append_audit_event(samples.event("evt_1"))

    admin.execute("SET session_replication_role = replica")
    try:
        with pytest.raises(psycopg.Error, match="append-only"):
            admin.execute(_in(pg_schema, "DELETE FROM {table}"))
    finally:
        admin.execute("RESET session_replication_role")

    assert [event.id for event in pg_store.list_audit_events()] == ["evt_1"]


def test_the_database_refuses_an_event_that_does_not_follow_the_last_one_from_any_connection(
    pg_store: PostgresStore, admin: psycopg.Connection, pg_schema: str
) -> None:
    pg_store.append_audit_event(samples.event("evt_1", event_hash="1" * 64))
    fork = (
        "INSERT INTO {table} (event_id, type, time, previous_hash, hash, body) "
        "SELECT 'evt_fork', type, time, repeat('0', 64), 'f', body FROM {table}"
    )

    with pytest.raises(psycopg.Error, match="does not follow") as raised:
        admin.execute(_in(pg_schema, fork))

    assert raised.value.sqlstate == "TA003"
    assert [event.id for event in pg_store.list_audit_events()] == ["evt_1"]


def test_two_events_can_never_follow_the_same_event_even_without_the_trigger(
    pg_store: PostgresStore, admin: psycopg.Connection, pg_schema: str
) -> None:
    pg_store.append_audit_event(samples.event("evt_1"))
    copy_with_another_id = (  # with its own position: without the trigger nothing sets it
        "INSERT INTO {table} (seq, event_id, type, time, previous_hash, hash, body) "
        "SELECT seq + 1, 'evt_fork', type, time, previous_hash, hash, body FROM {table}"
    )

    admin.execute("BEGIN")
    try:
        admin.execute(_in(pg_schema, "ALTER TABLE {table} DISABLE TRIGGER audit_events_follow_head"))  # the owner can
        with pytest.raises(psycopg.errors.UniqueViolation, match="previous_hash"):
            admin.execute(_in(pg_schema, copy_with_another_id))
    finally:
        admin.execute("ROLLBACK")  # the trigger is back as it was

    assert [event.id for event in pg_store.list_audit_events()] == ["evt_1"]


def test_an_events_position_is_given_by_the_database_without_gaps(
    pg_store: PostgresStore, admin: psycopg.Connection, pg_schema: str
) -> None:
    pg_store.append_audit_event(samples.event("evt_1", event_hash="1" * 64))
    with pytest.raises(Failure), pg_store.atomic():
        pg_store.append_audit_event(samples.event("evt_2", previous_hash="1" * 64, event_hash="2" * 64))
        raise Failure
    pg_store.append_audit_event(samples.event("evt_3", previous_hash="1" * 64, event_hash="3" * 64))

    rows = admin.execute(_in(pg_schema, "SELECT seq, event_id FROM {table} ORDER BY seq")).fetchall()

    assert rows == [(1, "evt_1"), (2, "evt_3")]


# --- two stores, one schema ---------------------------------------------------------------------------------


def test_two_stores_on_one_schema_cannot_fork_the_chain(open_pg: Open) -> None:
    one, other = open_pg(), open_pg()
    one.append_audit_event(samples.event("evt_1", event_hash="1" * 64))

    with pytest.raises(AuditChainConflict):
        other.append_audit_event(samples.event("evt_2", event_hash="2" * 64))  # read the head before evt_1 landed
    other.append_audit_event(samples.event("evt_3", previous_hash="1" * 64, event_hash="3" * 64))

    assert [event.id for event in one.list_audit_events()] == ["evt_1", "evt_3"]
    assert one.last_audit_hash() == other.last_audit_hash() == "3" * 64


def test_another_store_sees_nothing_of_a_block_until_it_ends(open_pg: Open) -> None:
    writer, reader = open_pg(), open_pg()

    with writer.atomic():
        writer.remember_idempotency_key("key-1", AGENT, "ord_1")
        writer.save_order(samples.order("ord_1"))
        writer.append_audit_event(samples.event("evt_1", event_hash="1" * 64))
        assert reader.get_order("ord_1") is None and reader.last_audit_hash() is None
        assert reader.order_id_for_key("key-1", AGENT) is None
    assert reader.get_order("ord_1") is not None and reader.last_audit_hash() == "1" * 64

    with pytest.raises(Failure), writer.atomic():
        writer.save_order(samples.order("ord_2"))
        raise Failure
    assert reader.get_order("ord_2") is None


def test_a_second_appender_waits_for_the_first_block_and_then_finds_the_head_moved(open_pg: Open) -> None:
    first, second = open_pg(), open_pg()
    outcomes: list[object] = []

    def append_from_another_store() -> None:
        try:
            second.append_audit_event(samples.event("evt_late", event_hash="9" * 64))  # names the genesis hash
            outcomes.append("stored")
        except AuditChainConflict as conflict:
            outcomes.append(conflict)

    other = threading.Thread(target=append_from_another_store)
    with first.atomic():
        first.append_audit_event(samples.event("evt_1", event_hash="1" * 64))  # holds the append lock from here
        other.start()
        other.join(timeout=SHORT_WAIT_SECONDS * 5)
        assert outcomes == []  # still waiting for this block
    other.join(timeout=JOIN_SECONDS)

    (outcome,) = outcomes
    assert isinstance(outcome, AuditChainConflict)
    assert [event.id for event in first.list_audit_events()] == ["evt_1"]


def test_an_appender_that_waits_too_long_for_another_store_gets_a_typed_busy_error(
    open_pg: Open, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(postgres_module, "LOCK_WAIT_SECONDS", 0.5)
    first, second = open_pg(), open_pg()  # the second waits half a second for a database lock

    with first.atomic():
        first.append_audit_event(samples.event("evt_1", event_hash="1" * 64))
        with pytest.raises(SupplierUnavailable, match="busy"):
            second.append_audit_event(samples.event("evt_2", previous_hash="1" * 64, event_hash="2" * 64))

    second.append_audit_event(samples.event("evt_2", previous_hash="1" * 64, event_hash="2" * 64))
    assert [event.id for event in second.list_audit_events()] == ["evt_1", "evt_2"]


def test_a_thread_that_waits_too_long_for_another_threads_block_gets_a_typed_error_and_the_block_goes_on(
    pg_store: PostgresStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(postgres_module, "LOCK_WAIT_SECONDS", SHORT_WAIT_SECONDS)
    outcomes: list[object] = []

    def read_from_another_thread() -> None:
        try:
            outcomes.append(pg_store.last_audit_hash())
        except SupplierUnavailable as error:
            outcomes.append(error)

    other = threading.Thread(target=read_from_another_thread)
    with pg_store.atomic():
        pg_store.save_order(samples.order("ord_1"))
        other.start()
        other.join(timeout=JOIN_SECONDS)  # it gives up while this block holds the connection
        pg_store.append_audit_event(samples.event("evt_1", event_hash="1" * 64))

    (outcome,) = outcomes
    assert isinstance(outcome, SupplierUnavailable) and "busy" in outcome.detail
    assert pg_store.get_order("ord_1") is not None and pg_store.last_audit_hash() == "1" * 64


# --- failures ---------------------------------------------------------------------------------------------


def test_a_database_failure_inside_a_block_is_a_typed_error_and_stores_nothing(open_pg: Open) -> None:
    store, reader = open_pg(), open_pg()

    with pytest.raises(SupplierUnavailable), store.atomic():
        store.save_order(samples.order("ord_1"))
        store.close()
        store.save_approval(samples.approval("apr_1"))  # the connection is gone

    assert reader.list_orders() == () and reader.list_approvals() == ()


def test_a_block_that_cannot_be_committed_is_a_typed_error_and_stores_nothing(open_pg: Open) -> None:
    store, reader = open_pg(), open_pg()

    with pytest.raises(SupplierUnavailable), store.atomic():
        store.save_order(samples.order("ord_1"))
        store.close()  # the last thing the block does: the commit has no connection left

    assert reader.list_orders() == ()


def test_a_lost_connection_fails_one_call_and_is_opened_again_for_the_next(
    pg_store: PostgresStore, admin: psycopg.Connection
) -> None:
    pg_store.save_order(samples.order("ord_1"))
    backend = pg_store._connection.info.backend_pid  # the server process behind the store's connection

    admin.execute("SELECT pg_terminate_backend(%s)", (backend,))  # as a restart or a network cut would

    with pytest.raises(SupplierUnavailable):
        pg_store.get_order("ord_1")
    assert pg_store.get_order("ord_1") == samples.order("ord_1")
    assert pg_store._connection.info.backend_pid != backend


# --- what a database service gives ------------------------------------------------------------------------


def test_what_was_written_is_there_for_a_store_opened_later(open_pg: Open) -> None:
    first = open_pg()
    first.save_offer(samples.offer())
    first.save_order(samples.order("ord_1", status=OrderStatus.ORDERED))
    first.append_audit_event(samples.event("evt_1", event_hash="1" * 64))
    first.close()  # as when the container stops for a redeploy

    later = open_pg()  # the migrations run again on the same schema and change nothing

    assert later.get_offer("off_1") == samples.offer()
    assert later.get_order("ord_1").status is OrderStatus.ORDERED
    assert [event.id for event in later.list_audit_events()] == ["evt_1"] and later.last_audit_hash() == "1" * 64


def test_the_connection_is_encrypted(pg_store: PostgresStore) -> None:
    rows = pg_store._rows("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()", ())

    assert rows == [(True,)]


def test_the_store_works_only_in_its_own_schema(
    pg_store: PostgresStore, admin: psycopg.Connection, pg_schema: str
) -> None:
    tables = admin.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = %s ORDER BY table_name", (pg_schema,)
    ).fetchall()

    assert [name for (name,) in tables] == [
        "approvals", "audit_buyer", "audit_events", "audit_supplier", "idempotency_keys", "offers", "orders",
    ]


# --- blocks the caller did not end cleanly ------------------------------------------------------------------

DIVIDE_BY_ZERO = "SELECT 1 / 0"  # a statement the database refuses, standing for any failed write


def _swallow_a_failed_statement(store: PostgresStore) -> None:
    """A caller that catches the store's error inside a block and goes on: the block's transaction is aborted."""
    with pytest.raises(SupplierUnavailable):
        store._rows(DIVIDE_BY_ZERO, ())


def test_a_block_whose_statement_failed_is_not_committed_even_when_the_caller_went_on(open_pg: Open) -> None:
    store, reader = open_pg(), open_pg()

    with pytest.raises(SupplierUnavailable), store.atomic():
        store.save_order(samples.order("ord_1"))
        _swallow_a_failed_statement(store)
        # PostgreSQL answers this block's COMMIT with ROLLBACK; the store reports it instead of returning quietly

    assert reader.list_orders() == ()
    store.save_order(samples.order("ord_2"))
    assert [order.order_id for order in reader.list_orders()] == ["ord_2"]


def test_a_transaction_a_failed_commit_left_open_is_rolled_back_before_the_next_call(open_pg: Open) -> None:
    store, reader = open_pg(), open_pg()

    with pytest.raises(SupplierUnavailable), store.atomic():
        store.save_order(samples.order("ord_1"))
        with store.atomic():
            _swallow_a_failed_statement(store)
        # the inner block's release goes with the commit, fails, and the commit is never run

    store.save_order(samples.order("ord_2"))  # not part of the abandoned transaction
    assert [order.order_id for order in reader.list_orders()] == ["ord_2"]


def test_a_block_that_runs_no_statement_sends_nothing_and_changes_nothing(pg_store: PostgresStore) -> None:
    with pg_store.atomic():
        pass
    with pg_store.atomic():
        pg_store.save_order(samples.order("ord_1"))
        with pg_store.atomic(), pg_store.atomic():
            pass
        pg_store.save_approval(samples.approval("apr_1"))

    assert [order.order_id for order in pg_store.list_orders()] == ["ord_1"]
    assert [approval.approval_id for approval in pg_store.list_approvals()] == ["apr_1"]
    assert pg_store._pending == [] and pg_store._opened == []


def test_a_connection_lost_inside_a_block_fails_the_block_and_the_next_call_opens_a_new_one(
    pg_store: PostgresStore, admin: psycopg.Connection
) -> None:
    with pytest.raises(SupplierUnavailable), pg_store.atomic():
        pg_store.save_order(samples.order("ord_1"))
        admin.execute("SELECT pg_terminate_backend(%s)", (pg_store._connection.info.backend_pid,))
        with pytest.raises(SupplierUnavailable):
            pg_store.save_approval(samples.approval("apr_1"))  # finds the connection gone
        pg_store.save_approval(samples.approval("apr_2"))  # the block cannot go on without its transaction

    assert pg_store.list_orders() == () and pg_store.list_approvals() == ()


# --- opening the store ------------------------------------------------------------------------------------


def test_a_migration_that_fails_leaves_no_schema_and_no_connection_behind(
    database_url: SecretStr, pg_schema: str, admin: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    genuine = postgres_module.statements.migrations()
    monkeypatch.setattr(postgres_module.statements, "migrations", lambda: (*genuine, ("999_broken.sql", "SELEC 1")))
    opened: list[psycopg.Connection] = []
    genuine_connect = psycopg.connect

    def remembering(*given: object, **options: object) -> psycopg.Connection:
        opened.append(genuine_connect(*given, **options))
        return opened[-1]

    monkeypatch.setattr(psycopg, "connect", remembering)

    with pytest.raises(SupplierUnavailable):
        PostgresStore(database_url, schema=pg_schema)

    assert opened and opened[0].closed
    found = admin.execute("SELECT count(*) FROM pg_namespace WHERE nspname = %s", (pg_schema,)).fetchone()
    assert found == (0,)  # the schema was created in the same transaction, and went with it


def test_a_missing_supplier_role_is_logged(
    open_pg: Open, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(postgres_module.statements, "ROLE_EXISTS", "SELECT 1 WHERE %s::text IS NULL")  # finds no role

    open_pg()

    assert "supplier role" in caplog.text and "does not exist" in caplog.text
