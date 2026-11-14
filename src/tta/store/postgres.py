"""The `Store` port on PostgreSQL (the Aiven service), with psycopg 3: the tables and JSON documents of the SQLite
store, in a schema of its own (`tta` for the deployed gateway, `tta_dev` for a local run).

Scores on the 20% "how decisions are logged and auditable": the order book and the audit trail live in a managed
database that outlives a redeploy; the database itself refuses to change or remove an audit event, lets an event in
only when it follows the last one, whichever program connects, and gives the supplier a view and a role of its own
(`sql/`).

One connection, guarded by a lock, as in the SQLite store. The connection is in autocommit, so a method's statement
outside a block is committed at once; `atomic()` is one transaction, and a block inside a block a savepoint. The
commands that open and release blocks are not sent on their own: they wait for the block's next statement and go
with it in one pipeline (one round trip to the service instead of one per command), and a block that ran no
statement sends none. An offer with two options needed 40 round trips sent one by one: 2.1 s or more at 39 ms
a round trip, 0.7 s pipelined (docs/AIVEN.md).

The URL is a secret. It is read from its `SecretStr` only where the connection is opened. No message, log line or
error chain carries it: libpq's own message on a refused connection names the server, and on a malformed URL it can
repeat the password, so a failed connection is reported by the class of its error only. TLS is what the URL asks
for (`sslmode`); the Aiven service URL asks for `require`.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus
from psycopg.rows import TupleRow
from pydantic import SecretStr
from pydantic_core import to_json

from tta.config import Settings
from tta.contracts.audit import AuditEvent
from tta.contracts.common import ApprovalStatus, Contract, OrderStatus
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.offer import Offer
from tta.contracts.order import Approval, Order
from tta.store import sql as statements
from tta.store.errors import AuditChainConflict
from tta.store.sqlite_store import CHAIN_MOVED_DETAIL, STORE_BUSY_DETAIL, STORE_UNAVAILABLE_DETAIL

logger = logging.getLogger(__name__)

Connection = psycopg.Connection[TupleRow]
Cursor = psycopg.Cursor[TupleRow]

DEFAULT_SCHEMA = "tta"
# A local run (TTA_ENV=dev) with the same DATABASE_URL never writes into the deployed demo's order book, whose
# audit trail cannot be cleaned afterwards.
SCHEMA_BY_ENVIRONMENT = {"dev": "tta_dev"}
SCHEMA_NAME = re.compile(r"[a-z_][a-z0-9_]{0,40}")  # leaves room for the "_supplier" of the role's name
SUPPLIER_ROLE_SUFFIX = "_supplier"
# How long a thread waits for the connection while another thread uses it or has a block open, and how long a
# statement waits for a lock another connection holds (an appender of another process): as the SQLite store.
LOCK_WAIT_SECONDS = 5.0
CONNECT_TIMEOUT_SECONDS = 5
# TCP keepalives, so a connection the network dropped is noticed instead of waited on for ever.
CONNECTION_OPTIONS: dict[str, Any] = {
    "application_name": "tta-gateway",
    "connect_timeout": CONNECT_TIMEOUT_SECONDS,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}
UNREACHABLE_LOG = "The PostgreSQL database could not be reached (%s)."
LOST_LOG = "The connection to the PostgreSQL database was lost; a new one is opened."
NO_SUPPLIER_ROLE_LOG = "The supplier role %s does not exist: the service did not let this login create it."
NO_PIPELINE_LOG = "The PostgreSQL client library has no pipeline mode (libpq 14 or later is needed)."


def _encode(model: Contract) -> str:
    """The whole object as JSON, exactly as the SQLite store writes it: Decimals as strings, no digit lost."""
    return to_json(model.model_dump()).decode("utf-8")


def _unavailable(error: psycopg.Error) -> SupplierUnavailable:
    busy = error.sqlstate == statements.LOCK_NOT_AVAILABLE
    return SupplierUnavailable(STORE_BUSY_DETAIL if busy else STORE_UNAVAILABLE_DETAIL)


def _refusal(error: psycopg.Error, event_id: str) -> Exception:
    """What the database's refusal of an audit event means to the caller (`sql/002`)."""
    constraint = error.diag.constraint_name
    if error.sqlstate == statements.EVENT_ALREADY_STORED or constraint == statements.EVENT_ID_TAKEN:
        return ValueError(f"Audit event {event_id} is already stored; the audit trail is append-only.")
    if error.sqlstate == statements.NOT_AFTER_THE_HEAD or constraint == statements.PREVIOUS_HASH_TAKEN:
        return AuditChainConflict(CHAIN_MOVED_DETAIL)
    return _unavailable(error)


class PostgresStore:
    """Offers, orders, approvals, idempotency keys and audit events in one PostgreSQL schema.

    Opening the store connects, creates the schema if needed and runs the migrations of `sql/` in one transaction.
    Audit events have an append and two reads; no method changes or removes one, and the database refuses an
    `UPDATE`, a `DELETE` or a `TRUNCATE` of them from any connection.

    A connection lost between two calls (a restart of the service, a network cut) fails the call that finds it, as
    `SupplierUnavailable`, and the next call opens a new one; inside an open block the block fails instead.
    """

    def __init__(self, url: SecretStr, schema: str = DEFAULT_SCHEMA) -> None:
        if not SCHEMA_NAME.fullmatch(schema):
            raise ValueError("The store's schema must be a plain lower-case identifier of at most 41 characters.")
        self._url = url
        self._schema = schema
        self._lock = threading.RLock()
        # Per `atomic()` block open in the thread that holds the lock, the place of its opening command in
        # `_pending`, or None once that command was sent.
        self._opened: list[int | None] = []
        self._pending: list[str] = []  # commands that go with the next statement
        self._closed = False
        if not psycopg.Pipeline.is_supported():
            logger.warning(NO_PIPELINE_LOG)
            raise SupplierUnavailable(STORE_UNAVAILABLE_DETAIL)
        self._connection = self._connect()
        try:
            self._migrate()
        except BaseException:
            self._connection.close()
            raise

    def close(self) -> None:
        with self._held():
            self._closed = True
            self._connection.close()

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """Everything saved or appended inside the `with` block is committed together, or not at all.

        The outermost block is one transaction. A block inside a block of the same thread is a savepoint: when it
        fails, only its own writes are taken back. Whatever ends a block reaches the caller unchanged; a database
        failure is `SupplierUnavailable`. A commit the database turns into a rollback is a failure too.
        """
        with self._held():
            outermost = not self._opened
            self._usable()
            self._opened.append(len(self._pending))
            self._pending.append(statements.BEGIN if outermost else statements.BEGIN_INNER)
            try:
                yield
            except BaseException:
                self._end(outermost, keep=False)
                raise
            self._end(outermost, keep=True)

    def _connect(self) -> Connection:
        try:
            connection = psycopg.connect(self._url.get_secret_value(), autocommit=True, **CONNECTION_OPTIONS)
        except psycopg.Error as error:
            logger.warning(UNREACHABLE_LOG, type(error).__name__)
            raise SupplierUnavailable(STORE_UNAVAILABLE_DETAIL) from None  # libpq's text names the server
        try:
            connection.execute(sql.SQL(statements.SET_SEARCH_PATH).format(schema=sql.Identifier(self._schema)))
            connection.execute(statements.SET_LOCK_TIMEOUT, (f"{round(LOCK_WAIT_SECONDS * 1000)}ms",))
        except psycopg.Error as error:
            connection.close()
            raise _unavailable(error) from error
        return connection

    def _migrate(self) -> None:
        """Create the schema and run every migration, in one transaction that one process at a time may hold."""
        connection = self._connection
        try:
            connection.execute(statements.BEGIN)
            connection.execute(statements.MIGRATION_LOCK, (self._schema,))
            connection.execute(sql.SQL(statements.CREATE_SCHEMA).format(schema=sql.Identifier(self._schema)))
            for _name, script in statements.migrations():
                connection.execute(script)  # a constant file of this package, run as it is
            connection.execute(statements.COMMIT)
            role = self._schema + SUPPLIER_ROLE_SUFFIX
            if connection.execute(statements.ROLE_EXISTS, (role,)).fetchone() is None:
                logger.warning(NO_SUPPLIER_ROLE_LOG, role)
        except psycopg.Error as error:
            raise _unavailable(error) from error

    @contextmanager
    def _held(self) -> Iterator[None]:
        """The connection for this thread alone; the thread that already holds it enters at once."""
        if not self._lock.acquire(timeout=LOCK_WAIT_SECONDS):
            raise SupplierUnavailable(STORE_BUSY_DETAIL)
        try:
            yield
        finally:
            self._lock.release()

    def _usable(self) -> None:
        """Make the connection ready for this thread's next statement.

        A connection that was lost is opened again, unless a block was open on it. Outside a block, a transaction a
        failed commit or rollback left open is rolled back first, so nothing later joins it.
        """
        if self._closed:
            raise SupplierUnavailable(STORE_UNAVAILABLE_DETAIL)
        if self._connection.closed:
            if self._opened:
                raise SupplierUnavailable(STORE_UNAVAILABLE_DETAIL)  # the block's transaction went with it
            logger.warning(LOST_LOG)
            self._connection = self._connect()
            return
        if not self._opened and self._connection.info.transaction_status is not TransactionStatus.IDLE:
            try:
                self._connection.execute(statements.ROLLBACK)
            except psycopg.Error as error:
                raise _unavailable(error) from error

    def _execute(self, statement: str, parameters: Sequence[object] | dict[str, object] | None = None) -> Cursor:
        """One statement, with the commands waiting before it in the same round trip. Raises psycopg's error."""
        commands, self._pending = self._pending, []
        self._opened = [None] * len(self._opened)  # every opening command waiting is sent now
        if not commands:
            return self._connection.execute(statement, parameters)
        with self._connection.pipeline():
            for command in commands:
                self._connection.execute(command)
            return self._connection.execute(statement, parameters)  # the block's end waits for every answer

    def _end(self, outermost: bool, keep: bool) -> None:
        """Release, commit or take back the innermost block. A commit the database answers with a rollback (a
        statement of the block had failed) is a failure. When taking back fails too, that failure is raised,
        with the first one as its context."""
        start = self._opened.pop()
        if start is not None:  # it ran no statement: the database never saw it open
            del self._pending[start:]
            return
        if outermost:
            last = statements.COMMIT if keep else statements.ROLLBACK
        elif keep:
            self._pending.append(statements.END_INNER)  # goes with the next statement, or the commit
            return
        else:
            self._pending.append(statements.UNDO_INNER)
            last = statements.END_INNER
        try:
            status = self._execute(last).statusmessage
        except psycopg.Error as error:
            raise _unavailable(error) from error
        if keep and status != statements.COMMITTED:
            raise SupplierUnavailable(STORE_UNAVAILABLE_DETAIL)

    def _rows(self, statement: str, parameters: Sequence[object] | dict[str, object]) -> list[TupleRow]:
        """The rows of one method's statement: part of the open block, or committed at once."""
        with self._held():
            self._usable()
            try:
                cursor = self._execute(statement, parameters)
                return cursor.fetchall() if cursor.description is not None else []
            except psycopg.Error as error:
                raise _unavailable(error) from error

    def _value(self, statement: str, parameters: Sequence[object]) -> Any:
        rows = self._rows(statement, parameters)
        return rows[0][0] if rows else None

    def _values(self, statement: str, parameters: dict[str, object]) -> list[Any]:
        return [row[0] for row in self._rows(statement, parameters)]

    def _write(self, statement: str, parameters: Sequence[object]) -> None:
        self._rows(statement, parameters)

    def save_offer(self, offer: Offer) -> None:
        self._write(statements.SAVE_OFFER, (offer.offer_id, offer.profile_id, _encode(offer)))

    def get_offer(self, offer_id: str) -> Offer | None:
        body = self._value(statements.GET_OFFER, (offer_id,))
        return None if body is None else Offer.model_validate_json(body)

    def save_order(self, order: Order) -> None:
        self._write(statements.SAVE_ORDER, (order.order_id, order.profile_id, order.status.value, _encode(order)))

    def get_order(self, order_id: str) -> Order | None:
        body = self._value(statements.GET_ORDER, (order_id,))
        return None if body is None else Order.model_validate_json(body)

    def list_orders(
        self, profile_id: str | None = None, statuses: Sequence[OrderStatus] | None = None
    ) -> tuple[Order, ...]:
        """In the order they were first saved. `statuses=None` means every status; an empty list, none."""
        wanted = None if statuses is None else [status.value for status in statuses]
        bodies = self._values(statements.LIST_ORDERS, {"profile_id": profile_id, "statuses": wanted})
        return tuple(Order.model_validate_json(body) for body in bodies)

    def save_approval(self, approval: Approval) -> None:
        self._write(
            statements.SAVE_APPROVAL,
            (approval.approval_id, approval.order_id, approval.profile_id, approval.status.value, _encode(approval)),
        )

    def get_approval(self, approval_id: str) -> Approval | None:
        body = self._value(statements.GET_APPROVAL, (approval_id,))
        return None if body is None else Approval.model_validate_json(body)

    def list_approvals(
        self, profile_id: str | None = None, status: ApprovalStatus | None = None
    ) -> tuple[Approval, ...]:
        """In the order they were first saved."""
        wanted = None if status is None else status.value
        bodies = self._values(statements.LIST_APPROVALS, {"profile_id": profile_id, "status": wanted})
        return tuple(Approval.model_validate_json(body) for body in bodies)

    def remember_idempotency_key(self, key: str, scope: str, order_id: str) -> str:
        """Bind a key to an order id. A key already bound keeps its first order id, which is returned."""
        self._write(statements.REMEMBER_KEY, (scope, key, order_id))
        return self._value(statements.ORDER_ID_FOR_KEY, (scope, key))

    def order_id_for_key(self, key: str, scope: str) -> str | None:
        return self._value(statements.ORDER_ID_FOR_KEY, (scope, key))

    def append_audit_event(self, event: AuditEvent) -> None:
        """Add one event at the end, in a savepoint of its own: a refusal takes back nothing else of the block.

        The database decides (`sql/002`): an id that is already stored is refused (`ValueError`); an event whose
        `previous_hash` is not the hash of the last stored event (the genesis hash in an empty trail) is refused
        with `AuditChainConflict`: another writer appended first, and storing it would fork the chain.
        """
        data = event.data
        parameters = (
            event.id, event.type, event.time, data.profile_id, data.offer_id, data.order_id, data.approval_id,
            data.previous_hash, data.hash, _encode(event),
        )
        with self.atomic():
            try:
                self._execute(statements.APPEND_AUDIT_EVENT, parameters)
            except psycopg.Error as error:
                raise _refusal(error, event.id) from error

    def list_audit_events(
        self, order_id: str | None = None, offer_id: str | None = None, profile_id: str | None = None
    ) -> tuple[AuditEvent, ...]:
        """In the order they were appended. Every filter given must hold; with none, every event."""
        parameters = {"order_id": order_id, "offer_id": offer_id, "profile_id": profile_id}
        bodies = self._values(statements.LIST_AUDIT_EVENTS, parameters)
        return tuple(AuditEvent.model_validate_json(body) for body in bodies)

    def last_audit_hash(self) -> str | None:
        return self._value(statements.LAST_AUDIT_HASH, ())


def schema_for(settings: Settings) -> str:
    """`tta` for the deployed gateway (demo, prod), `tta_dev` for a local run."""
    return SCHEMA_BY_ENVIRONMENT.get(settings.tta_env, DEFAULT_SCHEMA)


def open_postgres_store(settings: Settings) -> PostgresStore:
    """The store on the database `DATABASE_URL` names, in the schema of the environment (`schema_for`). Raises
    `SupplierUnavailable` when it cannot be reached or prepared; the URL is not repeated."""
    if settings.database_url is None:
        raise SupplierUnavailable(STORE_UNAVAILABLE_DETAIL)
    return PostgresStore(settings.database_url, schema=schema_for(settings))
