"""Statements and migrations of the PostgreSQL store (`tta.store.postgres`).

Every statement is a constant, and every value is a parameter: no SQL is built from input. The one name put into
SQL is the store's schema, which the store checks against a plain-identifier pattern and quotes as an identifier.
The migrations are the `NNN_*.sql` files of this folder, run in the order of their names at every start; each is
idempotent.
"""

from __future__ import annotations

from importlib.resources import files

MIGRATION_SUFFIX = ".sql"

# Two-key form: its keys never meet the one-key locks the audit trigger takes (sql/002).
MIGRATION_LOCK = "SELECT pg_advisory_xact_lock(hashtext('tta.store.migrate'), hashtext(%s))"
CREATE_SCHEMA = "CREATE SCHEMA IF NOT EXISTS {schema}"
SET_SEARCH_PATH = "SET search_path TO {schema}"
SET_LOCK_TIMEOUT = "SELECT set_config('lock_timeout', %s, false)"
ROLE_EXISTS = "SELECT 1 FROM pg_roles WHERE rolname = %s"

BEGIN = "BEGIN"
COMMIT = "COMMIT"
ROLLBACK = "ROLLBACK"
COMMITTED = "COMMIT"  # the status PostgreSQL answers a COMMIT that kept the work; an aborted one answers ROLLBACK
# A block opened inside another block of the same thread. PostgreSQL matches the newest savepoint of a name,
# so one name serves every depth.
BEGIN_INNER = "SAVEPOINT tta_atomic"
END_INNER = "RELEASE SAVEPOINT tta_atomic"
UNDO_INNER = "ROLLBACK TO SAVEPOINT tta_atomic"  # followed by END_INNER

SAVE_OFFER = """
INSERT INTO offers (offer_id, profile_id, body) VALUES (%s, %s, %s)
ON CONFLICT (offer_id) DO UPDATE SET profile_id = excluded.profile_id, body = excluded.body
"""
GET_OFFER = "SELECT body FROM offers WHERE offer_id = %s"

SAVE_ORDER = """
INSERT INTO orders (order_id, profile_id, status, body) VALUES (%s, %s, %s, %s)
ON CONFLICT (order_id) DO UPDATE
SET profile_id = excluded.profile_id, status = excluded.status, body = excluded.body
"""
GET_ORDER = "SELECT body FROM orders WHERE order_id = %s"
# %(statuses)s is a list of status names, or NULL for every status.
LIST_ORDERS = """
SELECT body FROM orders
WHERE (%(profile_id)s::text IS NULL OR profile_id = %(profile_id)s::text)
  AND (%(statuses)s::text[] IS NULL OR status = ANY (%(statuses)s::text[]))
ORDER BY seq
"""

SAVE_APPROVAL = """
INSERT INTO approvals (approval_id, order_id, profile_id, status, body) VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (approval_id) DO UPDATE
SET order_id = excluded.order_id, profile_id = excluded.profile_id, status = excluded.status, body = excluded.body
"""
GET_APPROVAL = "SELECT body FROM approvals WHERE approval_id = %s"
LIST_APPROVALS = """
SELECT body FROM approvals
WHERE (%(profile_id)s::text IS NULL OR profile_id = %(profile_id)s::text)
  AND (%(status)s::text IS NULL OR status = %(status)s::text)
ORDER BY seq
"""

REMEMBER_KEY = "INSERT INTO idempotency_keys (scope, key, order_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING"
ORDER_ID_FOR_KEY = "SELECT order_id FROM idempotency_keys WHERE scope = %s AND key = %s"

# The trigger of sql/002 checks the id and the head, and sets `seq`.
APPEND_AUDIT_EVENT = """
INSERT INTO audit_events
    (event_id, type, time, profile_id, offer_id, order_id, approval_id, previous_hash, hash, body)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
LIST_AUDIT_EVENTS = """
SELECT body FROM audit_events
WHERE (%(order_id)s::text IS NULL OR order_id = %(order_id)s::text)
  AND (%(offer_id)s::text IS NULL OR offer_id = %(offer_id)s::text)
  AND (%(profile_id)s::text IS NULL OR profile_id = %(profile_id)s::text)
ORDER BY seq
"""
LAST_AUDIT_HASH = "SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1"

# Standing orders and their renewals (task STAND-1, sql/005).
SAVE_STANDING_ORDER = """
INSERT INTO standing_orders (standing_order_id, profile_id, body) VALUES (%s, %s, %s)
ON CONFLICT (standing_order_id) DO UPDATE SET profile_id = excluded.profile_id, body = excluded.body
"""
GET_STANDING_ORDER = "SELECT body FROM standing_orders WHERE standing_order_id = %s"
# The first 100, as in `tta.store.schema` (review A3, finding F1).
LIST_STANDING_ORDERS = """
SELECT body FROM standing_orders
WHERE (%(profile_id)s::text IS NULL OR profile_id = %(profile_id)s::text)
ORDER BY seq
LIMIT 100
"""
SAVE_RENEWAL = """
INSERT INTO standing_renewals (renewal_id, standing_order_id, body) VALUES (%s, %s, %s)
ON CONFLICT (renewal_id) DO UPDATE SET standing_order_id = excluded.standing_order_id, body = excluded.body
"""
LIST_RENEWALS = "SELECT body FROM standing_renewals WHERE standing_order_id = %(standing_order_id)s ORDER BY seq"

# What the audit triggers raise (sql/002), and the constraint behind them (sql/001).
EVENT_ALREADY_STORED = "TA002"
NOT_AFTER_THE_HEAD = "TA003"
EVENT_ID_TAKEN = "audit_events_event_id_key"
PREVIOUS_HASH_TAKEN = "audit_events_previous_hash_key"
LOCK_NOT_AVAILABLE = "55P03"


def migrations() -> tuple[tuple[str, str], ...]:
    """The name and text of each migration of this folder, in the order of their names."""
    found = (entry for entry in files(__name__).iterdir() if entry.name.endswith(MIGRATION_SUFFIX))
    return tuple(sorted((entry.name, entry.read_text(encoding="utf-8")) for entry in found))
