"""The `Store` port on SQLite from the standard library: no ORM, one JSON document per row.

Scores on the 20% "how decisions are logged and auditable": orders, approvals and the audit trail
survive a restart, the audit table can only be appended to, and an event is stored only when it follows
the last one, whichever process or connection writes it.
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
from tta.store import schema
from tta.store.errors import AuditChainConflict

IN_MEMORY = ":memory:"
STORE_UNAVAILABLE_DETAIL = "The gateway's own database could not be read or written. Nothing was changed."
CHAIN_MOVED_DETAIL = (
    "The audit event does not follow the last event of the trail: another writer added an event first. "
    "Nothing was recorded."
)


def _encode(model: Contract) -> str:
    """The whole object as JSON. Decimals are written as strings, so no digit is lost on the way back."""
    return to_json(model.model_dump()).decode("utf-8")


class SqliteStore:
    """Offers, orders, approvals, idempotency keys and audit events in one SQLite database.

    One connection, guarded by a lock, so the FastAPI thread pool can share it. Audit events have
    an append and two reads; there is no method that changes or removes one, and the database refuses
    an `UPDATE`, a `DELETE` or a replacing `INSERT` on them (`schema.py`).
    """

    def __init__(self, path: Path | str = IN_MEMORY) -> None:
        self._lock = threading.RLock()
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
        with self._lock:
            self._connection.close()

    @contextmanager
    def _session(self, begin: str | None = None) -> Iterator[sqlite3.Connection]:
        """One unit of work: committed at the end, rolled back on any error.

        `begin` opens the transaction at once with that statement; without it SQLite opens one at the first write.
        """
        with self._lock:
            try:
                with self._connection:
                    if begin is not None:
                        self._connection.execute(begin)
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
        """Add one event at the end, in one transaction that holds the write lock from the first read.

        An id that is already stored is refused (`ValueError`): nothing is replaced. An event whose
        `previous_hash` is not the hash of the last stored event (the genesis hash in an empty trail) is
        refused with `AuditChainConflict`: another writer appended first, and storing it would fork the chain.
        """
        data = event.data
        with self._session(schema.BEGIN_WRITE) as connection:
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


def open_store(settings: Settings) -> SqliteStore:
    """The store at the path the settings name (`TTA_DB_PATH`, or `<data dir>/tta.sqlite3`)."""
    path = settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteStore(path)
