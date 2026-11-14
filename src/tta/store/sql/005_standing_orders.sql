-- Standing orders and their renewals (task STAND-1), the same tables as the SQLite store's (src/tta/store/schema.py).
-- Idempotent. Each row keeps the whole contract object as JSON text in `body`; `seq` keeps the order in which rows
-- were first written, which is the order a standing order's history is read in.

CREATE TABLE IF NOT EXISTS standing_orders (
    seq               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    standing_order_id text NOT NULL UNIQUE,
    profile_id        text NOT NULL,
    body              text NOT NULL CHECK (body::jsonb IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS standing_orders_by_profile ON standing_orders (profile_id);

CREATE TABLE IF NOT EXISTS standing_renewals (
    seq               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    renewal_id        text NOT NULL UNIQUE,
    standing_order_id text NOT NULL,
    body              text NOT NULL CHECK (body::jsonb IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS standing_renewals_by_order ON standing_renewals (standing_order_id);
