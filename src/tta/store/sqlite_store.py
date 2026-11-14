"""The `Store` port on SQLite from the standard library: no ORM, one JSON document per row.

Scores on the 20% "how decisions are logged and auditable": orders, approvals and the audit trail
survive a restart, the audit table can only be appended to, an event is stored only when it follows
the last one, whichever process or connection writes it, and `atomic()` keeps an order, its approval, its
idempotency key and its audit event together: all of them are stored, or none.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from pydantic_core import to_json

from tta.config import Settings
from tta.contracts.audit import GENESIS_HASH, AuditEvent
from tta.contracts.common import ApprovalStatus, Contract, OrderStatus
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.offer import Offer
from tta.contracts.order import Approval, Order
from tta.contracts.standing import Renewal, StandingOrder
from tta.store import schema
from tta.store.errors import AuditChainConflict

IN_MEMORY = ":memory:"
STORE_UNAVAILABLE_DETAIL = "The gateway's own database could not be read or written. Nothing was changed."
STORE_BUSY_DETAIL = (
    "The gateway's own database is busy with another write. Nothing was changed; the same request can be sent again."
)
# How long a thread waits for the connection while another thread uses it or has a block open: as long as
# sqlite3 waits by default for another connection's write lock. The wait is bounded because a caller may hold a
# lock of its own while it waits here (the audit trail does), and the thread inside the block may need that lock:
# without a bound the two would wait for each other for ever.
LOCK_WAIT_SECONDS = 5.0
# The bounded audit read of review H2. Kept here: `tta.store.schema` holds the statements of the unbounded reads.
COUNT_AUDIT_EVENTS = "SELECT COUNT(*) FROM audit_events"
AUDIT_POSITION = """
SELECT seq FROM audit_events
WHERE event_id = :event_id AND (:profile_id IS NULL OR profile_id = :profile_id)
"""
AUDIT_EVENTS_PAGE = """
SELECT e.body, (SELECT p.hash FROM audit_events p WHERE p.seq < e.seq ORDER BY p.seq DESC LIMIT 1)
FROM audit_events e
WHERE (:profile_id IS NULL OR e.profile_id = :profile_id)
  AND (:offer_id IS NULL OR e.offer_id = :offer_id)
  AND (:order_id IS NULL OR e.order_id = :order_id OR (e.order_id IS NULL AND e.offer_id IN (
        SELECT o.offer_id FROM audit_events o
        WHERE o.order_id = :order_id AND o.offer_id IS NOT NULL
          AND (:profile_id IS NULL OR o.profile_id = :profile_id))))
  AND (:before IS NULL OR e.seq < :before)
ORDER BY e.seq DESC LIMIT :limit
"""
CHAIN_MOVED_DETAIL = (
    "The audit event does not follow the last event of the trail: another writer added an event first. "
    "Nothing was recorded."
)


def _encode(model: Contract) -> str:
    """The whole object as JSON. Decimals are written as strings, so no digit is lost on the way back."""
    return to_json(model.model_dump()).decode("utf-8")


class SqliteStore:
    """Offers, orders, approvals, idempotency keys, audit events and standing orders in one SQLite database.

    One connection, guarded by a lock, so the FastAPI thread pool can share it. Audit events have
    an append and two reads; there is no method that changes or removes one, and the database refuses
    an `UPDATE`, a `DELETE` or a replacing `INSERT` on them (`schema.py`).

    `atomic()` is one transaction over whatever is written inside it. While a thread has a block open, every
    other thread waits for the connection, up to `LOCK_WAIT_SECONDS`.
    """

    def __init__(self, path: Path | str = IN_MEMORY) -> None:
        self._lock = threading.RLock()
        self._depth = 0  # `atomic()` blocks open in the thread that holds the lock
        try:
            self._connection = sqlite3.connect(str(path), check_same_thread=False)
        except sqlite3.Error as error:
            raise SupplierUnavailable(STORE_UNAVAILABLE_DETAIL) from error
        try:
            # Readers do not block the writer in WAL mode. An in-memory database ignores the request.
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.executescript(schema.SCHEMA)
        except sqlite3.Error as error:
            self._connection.close()
            raise SupplierUnavailable(STORE_UNAVAILABLE_DETAIL) from error

    def close(self) -> None:
        with self._held():
            self._connection.close()

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """Everything saved or appended inside the `with` block is committed together, or not at all.

        The outermost block is one transaction that holds the database's write lock from its first statement
        (`BEGIN IMMEDIATE`), so the audit head read inside it cannot move before the append. A block inside a
        block of the same thread is a savepoint: when it fails, only its own writes are taken back. Whatever ends
        a block reaches the caller unchanged; a database failure is `SupplierUnavailable`.
        """
        with self._held():
            outermost = self._depth == 0
            self._begin(outermost)
            self._depth += 1
            try:
                yield
                self._keep(outermost)
            except BaseException:
                self._undo(outermost)
                raise
            finally:
                self._depth -= 1

    @contextmanager
    def _held(self) -> Iterator[None]:
        """The connection for this thread alone; the thread that already holds it enters at once."""
        if not self._lock.acquire(timeout=LOCK_WAIT_SECONDS):
            raise SupplierUnavailable(STORE_BUSY_DETAIL)
        try:
            yield
        finally:
            self._lock.release()

    def _begin(self, outermost: bool) -> None:
        try:
            self._connection.execute(schema.BEGIN_WRITE if outermost else schema.BEGIN_INNER)
        except sqlite3.Error as error:
            raise SupplierUnavailable(STORE_UNAVAILABLE_DETAIL) from error

    def _keep(self, outermost: bool) -> None:
        try:
            if outermost:
                self._connection.commit()
            else:
                self._connection.execute(schema.END_INNER)
        except sqlite3.Error as error:
            raise SupplierUnavailable(STORE_UNAVAILABLE_DETAIL) from error

    def _undo(self, outermost: bool) -> None:
        """Take back what a block wrote. When that fails too, it is raised with the first failure as its context."""
        try:
            if outermost:
                self._connection.rollback()
            else:
                self._connection.execute(schema.UNDO_INNER)
                self._connection.execute(schema.END_INNER)
        except sqlite3.Error as error:
            raise SupplierUnavailable(STORE_UNAVAILABLE_DETAIL) from error

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        """The connection for one method's statements. Inside an open `atomic()` block they are part of that block;
        otherwise they are committed when the method ends, and rolled back on any error."""
        with self._held():
            try:
                if self._depth:
                    yield self._connection
                else:
                    with self._connection:
                        yield self._connection
            except sqlite3.Error as error:
                raise SupplierUnavailable(STORE_UNAVAILABLE_DETAIL) from error

    def _body(self, statement: str, key: str) -> str | None:
        with self._session() as connection:
            row = connection.execute(statement, (key,)).fetchone()
        return None if row is None else row[0]

    def _bodies(self, statement: str, parameters: dict[str, str | None]) -> list[str]:
        with self._session() as connection:
            return [row[0] for row in connection.execute(statement, parameters).fetchall()]

    def save_offer(self, offer: Offer) -> None:
        with self._session() as connection:
            connection.execute(schema.SAVE_OFFER, (offer.offer_id, offer.profile_id, _encode(offer)))

    def get_offer(self, offer_id: str) -> Offer | None:
        body = self._body(schema.GET_OFFER, offer_id)
        return None if body is None else Offer.model_validate_json(body)

    def save_order(self, order: Order) -> None:
        with self._session() as connection:
            connection.execute(
                schema.SAVE_ORDER, (order.order_id, order.profile_id, order.status.value, _encode(order))
            )

    def get_order(self, order_id: str) -> Order | None:
        body = self._body(schema.GET_ORDER, order_id)
        return None if body is None else Order.model_validate_json(body)

    def list_orders(
        self, profile_id: str | None = None, statuses: Sequence[OrderStatus] | None = None
    ) -> tuple[Order, ...]:
        """In the order they were first saved. `statuses=None` means every status; an empty list, none."""
        wanted = None if statuses is None else json.dumps([status.value for status in statuses])
        bodies = self._bodies(schema.LIST_ORDERS, {"profile_id": profile_id, "statuses": wanted})
        return tuple(Order.model_validate_json(body) for body in bodies)

    def save_approval(self, approval: Approval) -> None:
        with self._session() as connection:
            connection.execute(
                schema.SAVE_APPROVAL,
                (approval.approval_id, approval.order_id, approval.profile_id, approval.status.value,
                 _encode(approval)),
            )

    def get_approval(self, approval_id: str) -> Approval | None:
        body = self._body(schema.GET_APPROVAL, approval_id)
        return None if body is None else Approval.model_validate_json(body)

    def list_approvals(
        self, profile_id: str | None = None, status: ApprovalStatus | None = None
    ) -> tuple[Approval, ...]:
        """In the order they were first saved."""
        wanted = None if status is None else status.value
        bodies = self._bodies(schema.LIST_APPROVALS, {"profile_id": profile_id, "status": wanted})
        return tuple(Approval.model_validate_json(body) for body in bodies)

    def remember_idempotency_key(self, key: str, scope: str, order_id: str) -> str:
        """Bind a key to an order id. A key already bound keeps its first order id, which is returned."""
        with self._session() as connection:
            connection.execute(schema.REMEMBER_KEY, (scope, key, order_id))
            row = connection.execute(schema.ORDER_ID_FOR_KEY, (scope, key)).fetchone()
        return row[0]

    def order_id_for_key(self, key: str, scope: str) -> str | None:
        with self._session() as connection:
            row = connection.execute(schema.ORDER_ID_FOR_KEY, (scope, key)).fetchone()
        return None if row is None else row[0]

    def append_audit_event(self, event: AuditEvent) -> None:
        """Add one event at the end, in one transaction that holds the write lock from the first read: its own,
        or the `atomic()` block it is called in.

        An id that is already stored is refused (`ValueError`): nothing is replaced. An event whose
        `previous_hash` is not the hash of the last stored event (the genesis hash in an empty trail) is
        refused with `AuditChainConflict`: another writer appended first, and storing it would fork the chain.
        """
        data = event.data
        with self.atomic(), self._session() as connection:
            if connection.execute(schema.AUDIT_EVENT_EXISTS, (event.id,)).fetchone() is not None:
                raise ValueError(f"Audit event {event.id} is already stored; the audit trail is append-only.")
            last = connection.execute(schema.LAST_AUDIT_HASH).fetchone()
            head = GENESIS_HASH if last is None else last[0]
            if data.previous_hash != head:
                raise AuditChainConflict(CHAIN_MOVED_DETAIL)
            connection.execute(
                schema.APPEND_AUDIT_EVENT,
                (event.id, event.type, event.time.isoformat(), data.profile_id, data.offer_id, data.order_id,
                 data.approval_id, data.previous_hash, data.hash, _encode(event)),
            )

    def list_audit_events(
        self, order_id: str | None = None, offer_id: str | None = None, profile_id: str | None = None
    ) -> tuple[AuditEvent, ...]:
        """In the order they were appended. Every filter given must hold; with none, every event."""
        parameters = {"order_id": order_id, "offer_id": offer_id, "profile_id": profile_id}
        bodies = self._bodies(schema.LIST_AUDIT_EVENTS, parameters)
        return tuple(AuditEvent.model_validate_json(body) for body in bodies)

    def last_audit_hash(self) -> str | None:
        with self._session() as connection:
            row = connection.execute(schema.LAST_AUDIT_HASH).fetchone()
        return None if row is None else row[0]

    def count_audit_events(self) -> int:
        """How many events the trail holds, without reading one."""
        with self._session() as connection:
            return connection.execute(COUNT_AUDIT_EVENTS).fetchone()[0]

    def audit_position(self, event_id: str, profile_id: str | None = None) -> int | None:
        """The place of an event in the trail, to read the page before it; None for an id nobody stored, or one
        that is not this buyer's when a profile is given."""
        with self._session() as connection:
            row = connection.execute(AUDIT_POSITION, {"event_id": event_id, "profile_id": profile_id}).fetchone()
        return None if row is None else row[0]

    def audit_events_page(
        self, *, limit: int, order_id: str | None = None, offer_id: str | None = None,
        profile_id: str | None = None, before: int | None = None,
    ) -> tuple[tuple[AuditEvent, str | None], ...]:
        """At most `limit` events, newest first, each with the hash of the event stored just before it in the whole
        trail (None for the first event): a bounded read (review H2). The filters are those of the audit view
        (`tta.audit.views.select`): one buyer's events; for an order, its own events and the events of its offer
        that belong to no order. `before` is a position `audit_position` gave."""
        parameters = {
            "order_id": order_id, "offer_id": offer_id, "profile_id": profile_id, "before": before, "limit": limit,
        }
        with self._session() as connection:
            rows = connection.execute(AUDIT_EVENTS_PAGE, parameters).fetchall()
        return tuple((AuditEvent.model_validate_json(body), hash_before) for body, hash_before in rows)

    def save_standing_order(self, standing: StandingOrder) -> None:
        with self._session() as connection:
            connection.execute(
                schema.SAVE_STANDING_ORDER, (standing.standing_order_id, standing.profile_id, _encode(standing))
            )

    def get_standing_order(self, standing_order_id: str) -> StandingOrder | None:
        body = self._body(schema.GET_STANDING_ORDER, standing_order_id)
        return None if body is None else StandingOrder.model_validate_json(body)

    def list_standing_orders(self, profile_id: str | None = None) -> tuple[StandingOrder, ...]:
        """In the order they were first saved, the first 100. With no profile: of every buyer."""
        bodies = self._bodies(schema.LIST_STANDING_ORDERS, {"profile_id": profile_id})
        return tuple(StandingOrder.model_validate_json(body) for body in bodies)

    def save_renewal(self, renewal: Renewal) -> None:
        with self._session() as connection:
            connection.execute(schema.SAVE_RENEWAL, (renewal.renewal_id, renewal.standing_order_id, _encode(renewal)))

    def list_renewals(self, standing_order_id: str) -> tuple[Renewal, ...]:
        """The renewals of one standing order, in the order they were first saved."""
        bodies = self._bodies(schema.LIST_RENEWALS, {"standing_order_id": standing_order_id})
        return tuple(Renewal.model_validate_json(body) for body in bodies)


def open_store(settings: Settings) -> SqliteStore:
    """The store at the path the settings name (`TTA_DB_PATH`, or `<data dir>/tta.sqlite3`)."""
    path = settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteStore(path)
