"""Tables and statements of the SQLite store. Every statement is a constant: no SQL is built from input.

Each row keeps the whole contract object as JSON in `body`; the other columns exist only to find rows.
`seq` keeps the order in which rows were first written.

The audit table is guarded by the database as well as by the code. Three triggers refuse, from any connection,
an `UPDATE`, a `DELETE`, and an `INSERT` that names a stored event's id or previous hash (with `OR REPLACE`
such an insert would remove the stored row without running the trigger on `DELETE`). `previous_hash` is also
unique, so two events can never follow the same event.
Limit: whoever can write the database file can drop a trigger first. What the hash chain still shows then,
and what it does not, is stated in `tta.audit.chain`.
"""

from __future__ import annotations

SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    offer_id   TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    body       TEXT NOT NULL CHECK (json_valid(body))
);
CREATE TABLE IF NOT EXISTS orders (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   TEXT NOT NULL UNIQUE,
    profile_id TEXT NOT NULL,
    status     TEXT NOT NULL,
    body       TEXT NOT NULL CHECK (json_valid(body))
);
CREATE INDEX IF NOT EXISTS orders_by_profile ON orders (profile_id, status);
CREATE TABLE IF NOT EXISTS approvals (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    approval_id TEXT NOT NULL UNIQUE,
    order_id    TEXT NOT NULL,
    profile_id  TEXT NOT NULL,
    status      TEXT NOT NULL,
    body        TEXT NOT NULL CHECK (json_valid(body))
);
CREATE INDEX IF NOT EXISTS approvals_by_profile ON approvals (profile_id, status);
CREATE TABLE IF NOT EXISTS idempotency_keys (
    scope    TEXT NOT NULL,
    key      TEXT NOT NULL,
    order_id TEXT NOT NULL,
    PRIMARY KEY (scope, key)
);
CREATE TABLE IF NOT EXISTS audit_events (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      TEXT NOT NULL UNIQUE,
    type          TEXT NOT NULL,
    time          TEXT NOT NULL,
    profile_id    TEXT,
    offer_id      TEXT,
    order_id      TEXT,
    approval_id   TEXT,
    previous_hash TEXT NOT NULL UNIQUE,
    hash          TEXT NOT NULL,
    body          TEXT NOT NULL CHECK (json_valid(body))
);
CREATE INDEX IF NOT EXISTS audit_events_by_order ON audit_events (order_id);
CREATE INDEX IF NOT EXISTS audit_events_by_offer ON audit_events (offer_id);
CREATE INDEX IF NOT EXISTS audit_events_by_profile ON audit_events (profile_id);
CREATE TABLE IF NOT EXISTS standing_orders (
    seq               INTEGER PRIMARY KEY AUTOINCREMENT,
    standing_order_id TEXT NOT NULL UNIQUE,
    profile_id        TEXT NOT NULL,
    body              TEXT NOT NULL CHECK (json_valid(body))
);
CREATE INDEX IF NOT EXISTS standing_orders_by_profile ON standing_orders (profile_id);
CREATE TABLE IF NOT EXISTS standing_renewals (
    seq               INTEGER PRIMARY KEY AUTOINCREMENT,
    renewal_id        TEXT NOT NULL UNIQUE,
    standing_order_id TEXT NOT NULL,
    body              TEXT NOT NULL CHECK (json_valid(body))
);
CREATE INDEX IF NOT EXISTS standing_renewals_by_order ON standing_renewals (standing_order_id);
CREATE TRIGGER IF NOT EXISTS audit_events_no_update BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only: an event cannot be changed');
END;
CREATE TRIGGER IF NOT EXISTS audit_events_no_delete BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only: an event cannot be removed');
END;
CREATE TRIGGER IF NOT EXISTS audit_events_no_replace BEFORE INSERT ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events is append-only: an event cannot be replaced')
    WHERE EXISTS (
        SELECT 1 FROM audit_events WHERE event_id = NEW.event_id OR previous_hash = NEW.previous_hash
    );
END;
"""

SAVE_OFFER = """
INSERT INTO offers (offer_id, profile_id, body) VALUES (?, ?, ?)
ON CONFLICT (offer_id) DO UPDATE SET profile_id = excluded.profile_id, body = excluded.body
"""
GET_OFFER = "SELECT body FROM offers WHERE offer_id = ?"

SAVE_ORDER = """
INSERT INTO orders (order_id, profile_id, status, body) VALUES (?, ?, ?, ?)
ON CONFLICT (order_id) DO UPDATE
SET profile_id = excluded.profile_id, status = excluded.status, body = excluded.body
"""
GET_ORDER = "SELECT body FROM orders WHERE order_id = ?"
# :statuses is a JSON array of status names, or NULL for every status.
LIST_ORDERS = """
SELECT body FROM orders
WHERE (:profile_id IS NULL OR profile_id = :profile_id)
  AND (:statuses IS NULL OR status IN (SELECT value FROM json_each(:statuses)))
ORDER BY seq
"""

SAVE_APPROVAL = """
INSERT INTO approvals (approval_id, order_id, profile_id, status, body) VALUES (?, ?, ?, ?, ?)
ON CONFLICT (approval_id) DO UPDATE
SET order_id = excluded.order_id, profile_id = excluded.profile_id, status = excluded.status, body = excluded.body
"""
GET_APPROVAL = "SELECT body FROM approvals WHERE approval_id = ?"
LIST_APPROVALS = """
SELECT body FROM approvals
WHERE (:profile_id IS NULL OR profile_id = :profile_id)
  AND (:status IS NULL OR status = :status)
ORDER BY seq
"""

REMEMBER_KEY = "INSERT OR IGNORE INTO idempotency_keys (scope, key, order_id) VALUES (?, ?, ?)"
ORDER_ID_FOR_KEY = "SELECT order_id FROM idempotency_keys WHERE scope = ? AND key = ?"

# Takes the write lock before the head is read, so no other connection can append between the check and the insert.
BEGIN_WRITE = "BEGIN IMMEDIATE"
# A block opened inside another block of the same thread. SQLite matches the innermost savepoint of that name,
# so one name serves every depth.
BEGIN_INNER = "SAVEPOINT tta_atomic"
END_INNER = "RELEASE tta_atomic"
UNDO_INNER = "ROLLBACK TO tta_atomic"
AUDIT_EVENT_EXISTS = "SELECT 1 FROM audit_events WHERE event_id = ?"
APPEND_AUDIT_EVENT = """
INSERT INTO audit_events
    (event_id, type, time, profile_id, offer_id, order_id, approval_id, previous_hash, hash, body)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
LIST_AUDIT_EVENTS = """
SELECT body FROM audit_events
WHERE (:order_id IS NULL OR order_id = :order_id)
  AND (:offer_id IS NULL OR offer_id = :offer_id)
  AND (:profile_id IS NULL OR profile_id = :profile_id)
ORDER BY seq
"""
LAST_AUDIT_HASH = "SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1"

# Standing orders and their renewals (task STAND-1). Saving again replaces the body and keeps the row's place.
SAVE_STANDING_ORDER = """
INSERT INTO standing_orders (standing_order_id, profile_id, body) VALUES (?, ?, ?)
ON CONFLICT (standing_order_id) DO UPDATE SET profile_id = excluded.profile_id, body = excluded.body
"""
GET_STANDING_ORDER = "SELECT body FROM standing_orders WHERE standing_order_id = ?"
LIST_STANDING_ORDERS = """
SELECT body FROM standing_orders WHERE (:profile_id IS NULL OR profile_id = :profile_id) ORDER BY seq
"""
SAVE_RENEWAL = """
INSERT INTO standing_renewals (renewal_id, standing_order_id, body) VALUES (?, ?, ?)
ON CONFLICT (renewal_id) DO UPDATE SET standing_order_id = excluded.standing_order_id, body = excluded.body
"""
LIST_RENEWALS = "SELECT body FROM standing_renewals WHERE standing_order_id = :standing_order_id ORDER BY seq"
