"""Tables and statements of the SQLite store. Every statement is a constant: no SQL is built from input.

Each row keeps the whole contract object as JSON in `body`; the other columns exist only to find rows.
`seq` keeps the order in which rows were first written.
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
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT NOT NULL UNIQUE,
    type        TEXT NOT NULL,
    time        TEXT NOT NULL,
    profile_id  TEXT,
    offer_id    TEXT,
    order_id    TEXT,
    approval_id TEXT,
    hash        TEXT NOT NULL,
    body        TEXT NOT NULL CHECK (json_valid(body))
);
CREATE INDEX IF NOT EXISTS audit_events_by_order ON audit_events (order_id);
CREATE INDEX IF NOT EXISTS audit_events_by_offer ON audit_events (offer_id);
CREATE INDEX IF NOT EXISTS audit_events_by_profile ON audit_events (profile_id);
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

AUDIT_EVENT_EXISTS = "SELECT 1 FROM audit_events WHERE event_id = ?"
APPEND_AUDIT_EVENT = """
INSERT INTO audit_events (event_id, type, time, profile_id, offer_id, order_id, approval_id, hash, body)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
LIST_AUDIT_EVENTS = """
SELECT body FROM audit_events
WHERE (:order_id IS NULL OR order_id = :order_id)
  AND (:offer_id IS NULL OR offer_id = :offer_id)
  AND (:profile_id IS NULL OR profile_id = :profile_id)
ORDER BY seq
"""
LAST_AUDIT_HASH = "SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1"
