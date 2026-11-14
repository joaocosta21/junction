-- The tables of the PostgreSQL store, the same as the SQLite store's (src/tta/store/schema.py).
-- Run at every start, in one transaction, in the store's own schema (search_path): every statement is idempotent.
--
-- Each row keeps the whole contract object as JSON text in `body`. Text, not jsonb: the audit hash is computed
-- over the event as the gateway wrote it, and a jsonb round trip rewrites keys and numbers (T06 hand-back).
-- The views of 003 read `body::jsonb`. The other columns exist only to find rows; `seq` keeps the order in which
-- rows were first written.

CREATE TABLE IF NOT EXISTS offers (
    offer_id   text PRIMARY KEY,
    profile_id text NOT NULL,
    body       text NOT NULL CHECK (body::jsonb IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS orders (
    seq        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id   text NOT NULL UNIQUE,
    profile_id text NOT NULL,
    status     text NOT NULL,
    body       text NOT NULL CHECK (body::jsonb IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS orders_by_profile ON orders (profile_id, status);

CREATE TABLE IF NOT EXISTS approvals (
    seq         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    approval_id text NOT NULL UNIQUE,
    order_id    text NOT NULL,
    profile_id  text NOT NULL,
    status      text NOT NULL,
    body        text NOT NULL CHECK (body::jsonb IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS approvals_by_profile ON approvals (profile_id, status);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    scope    text NOT NULL,
    key      text NOT NULL,
    order_id text NOT NULL,
    PRIMARY KEY (scope, key)
);

-- `seq` is the event's position in the trail, 1, 2, 3 …, set by the trigger of 002 while it holds the append
-- lock: a value given by a writer is replaced, and a block that is taken back leaves no gap.
CREATE TABLE IF NOT EXISTS audit_events (
    seq           bigint PRIMARY KEY,
    event_id      text NOT NULL UNIQUE,
    type          text NOT NULL,
    time          timestamptz NOT NULL,
    profile_id    text,
    offer_id      text,
    order_id      text,
    approval_id   text,
    previous_hash text NOT NULL UNIQUE,
    hash          text NOT NULL,
    body          text NOT NULL CHECK (body::jsonb IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS audit_events_by_order ON audit_events (order_id);
CREATE INDEX IF NOT EXISTS audit_events_by_offer ON audit_events (offer_id);
CREATE INDEX IF NOT EXISTS audit_events_by_profile ON audit_events (profile_id);
