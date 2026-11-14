# Aiven for PostgreSQL: the order book and the audit trail

The gateway keeps its shared order book and its audit trail in an Aiven for PostgreSQL service when `DATABASE_URL` is set. Without it, they stay in SQLite, as before. The store behind both is the same `Store` port (`src/tta/contracts/ports.py`), so no other package changed.

This is a database swap with three consequences the SQLite file could not give. Each one has SQL below that shows it.

## The service and the connection

| | |
|---|---|
| Service | Aiven for PostgreSQL, server 18.7 (`SHOW server_version`) |
| Driver | psycopg 3.3.9 with its binary wheel, which bundles libpq 18. No system library is needed. |
| TLS | As the service URI asks: Aiven's URI carries `sslmode=require`. A test checks that the store's session is encrypted (`pg_stat_ssl`); a probe of the service saw TLS 1.3. `require` encrypts the traffic but does not check the server's certificate. |
| Schema | `tta` for the deployed gateway (`TTA_ENV=demo` or `prod`), `tta_dev` for a local run (`TTA_ENV=dev`). A laptop with the same URL never writes into the demo's trail, which cannot be cleaned afterwards. Tests use their own schemas `tta_test_<random>_<n>`, dropped after each test. |
| Secret | The URL is read through `tta.config` only, where the connection is opened. libpq's own error text names the server, and for a malformed URL it repeats the password. So a failed connection is logged by its error class alone and is not chained to the raised error (`tests/store_pg/test_unreachable.py`). |
| Start-up | The store connects, creates its schema and runs the migrations of `src/tta/store/sql/` in one transaction under a lock, so two containers starting together take turns. Every migration is idempotent and runs at every start. |
| Fallback | If the database cannot be reached or prepared at start-up, the gateway starts on SQLite, logs a warning and lists the reason in `/healthz`. It does not switch back by itself: that takes a restart. |

Code: `src/tta/store/postgres.py` (the store), `src/tta/store/sql/` (statements and migrations), `src/tta/api/wiring.py` (`_order_book`: which store, and the fallback).

## 1. History that survives a redeploy

**Before.** On Modal, SQLite runs on the container's own disk. A copy goes to a Volume after each request and is restored when a container starts (`docs/DEPLOY.md`). A crash loses the last second. Writes between the old container's last copy and the new container's start can be lost.

**Now.** An order or an event is in the managed database once its transaction commits. A new container reads it at once. `tests/store_pg/test_flow_on_postgres.py` runs the full flow over HTTP: an offer, an order, an approval, then the order. It then starts a second gateway on the same database. That gateway finds the order as `ORDERED`, the chain intact, and the same audit head in `/healthz`.

```sql
-- Before and after `modal deploy`: the same numbers, and the same head as /healthz → audit_head.
SELECT count(*) AS events, max(seq) AS last_position, max(time) AS last_event FROM tta.audit_events;
SELECT hash FROM tta.audit_events ORDER BY seq DESC LIMIT 1;
SELECT order_id, profile_id, status FROM tta.orders ORDER BY seq DESC LIMIT 5;
```

## 2. History the gateway cannot rewrite

The gateway's code has no statement that changes or removes an event. The database refuses one too, from the gateway's own connection as from any other. Triggers of `sql/002_audit_append_only.sql`:

| Attempt | The database answers |
|---|---|
| `UPDATE tta.audit_events SET body = '{}' WHERE seq = 1` | `TA001 audit_events is append-only: UPDATE is refused, an event cannot be changed or removed` |
| `DELETE FROM tta.audit_events WHERE seq = 1` | `TA001 … DELETE is refused …` |
| `TRUNCATE tta.audit_events` | `TA001 … TRUNCATE is refused …` |
| `INSERT … ON CONFLICT DO UPDATE` | refused as an `UPDATE` |
| An event whose `previous_hash` is not the last event's hash | `TA003 audit_events is append-only: event e2 does not follow the last stored event` |
| An event id already stored | `TA002 audit_events is append-only: event e1 is already stored` |
| Two events with the same `previous_hash`, with that trigger disabled | the `UNIQUE` constraint on `previous_hash` |
| The same `DELETE` after `SET session_replication_role = replica`, which this service's admin login may set and which skips ordinary triggers | still refused: both triggers are `ENABLE ALWAYS` |

The insert trigger takes a lock that is held until the writer's transaction ends. Writers on several connections therefore take turns on one trail (tested with two stores on one schema). A writer that waited finds the head moved and is refused, so the chain cannot fork. The same trigger gives each event its position, `seq` = 1, 2, 3 …, with no gaps.

```sql
SELECT tgname, tgenabled FROM pg_trigger
WHERE tgrelid = 'tta.audit_events'::regclass AND NOT tgisinternal;   -- 'A' = fires always
-- audit_events_append_only | A
-- audit_events_follow_head | A
```

**What this does not stop.** The table's owner can drop or disable a trigger first. Today the gateway connects with the service's admin login, which owns the tables. The hash chain still shows a changed or removed event when someone does that (`src/tta/audit/chain.py`). Closing this gap takes a second login for the gateway that does not own the tables (see "Next steps").

## 3. A supplier login that sees only its view

The two readers of SPEC §9 are views (`sql/003_reader_views.sql`):

- **`audit_buyer`**: every field, with the buyer profile, so a buyer's query names its own profile. The gateway keeps one buyer from another: it checks who is asking.
- **`audit_supplier`**: what Valio Aimo may see. It has no buyer profile, and it uses the supplier's sentence and facts, which the audit package builds from an allow-list. It shows an agent by kind and id only, and a human only as "A human at the buyer". It keeps only the rules about the supplier's own data or the caller's identity (F-01, F-03 to F-08).

Both views must show exactly what `tta.audit` shows the same reader. `tests/store_pg/test_reader_views.py` records the audit package's own two flows (`tests/audit/conftest.py`: the hotel order sent to a human, the ward order placed by the agent) through `AuditTrail` on PostgreSQL. It then compares every row of each view with `AuditTrail.view(...)`. It also runs the audit package's own redaction check on the supplier view: no limit value, no allergen exclusion, no approver name or note.

`sql/004_supplier_role.sql` creates the role `tta_supplier`. It cannot log in, and it holds one privilege: `SELECT` on `tta.audit_supplier`. A view reads its tables with its owner's rights, so the role reads the projection and never the rows behind it. The supplier's own login is made a member of the role:

```sql
-- As the admin login, once:
CREATE ROLE valio_aimo LOGIN PASSWORD '<a strong password>' IN ROLE tta_supplier;

-- As valio_aimo:
SELECT seq, type, time, actor, sentence, rule_ids, facts FROM tta.audit_supplier ORDER BY seq;   -- rows
SELECT * FROM tta.audit_events;   -- ERROR: permission denied for table audit_events
SELECT * FROM tta.audit_buyer;    -- ERROR: permission denied for view audit_buyer
SELECT * FROM tta.orders;         -- ERROR: permission denied for table orders
```

The test does exactly this with a login it creates and drops. It also checks that the role holds no grant but `SELECT` on `audit_supplier`.

Both readers on one order:

```sql
SELECT seq, sentence FROM tta.audit_buyer    WHERE order_id = '<order id>' ORDER BY seq;
SELECT seq, sentence FROM tta.audit_supplier WHERE order_id = '<order id>' ORDER BY seq;
```

## What it costs

Each statement is a round trip to the service. From the development machine that is 39 ms (median of 10 `SELECT 1`). Sent one by one, an offer with two options took 40 statements, 24 of them savepoint bookkeeping. To cut the waiting, the store holds back the commands that open and release blocks and sends them with the block's next statement in one pipeline. A block that runs no statement sends none. Two runs each, from the development machine, over HTTP in-process (`TestClient`):

| | SQLite | PostgreSQL, one by one | PostgreSQL, pipelined |
|---|---|---|---|
| `POST /v1/offers` (2 options) | 0.02–0.03 s | 2.1–2.9 s | 0.65–0.72 s |
| `POST /v1/orders` | < 0.01 s | 0.8–1.75 s | 0.56–0.69 s |
| `POST /v1/approvals/{id}/decision` | < 0.01 s | 1.0–1.3 s | 0.56–0.68 s |

From a container far from the service, each round trip costs more.

## Reproduce

1. Put the service URI from the Aiven console (Service → Connection information) in `.env` as `DATABASE_URL`.
2. Run the tests against the service: `.venv/bin/python -m pytest tests/store_pg -q -m live`. Each test creates its own schema and drops it, with its roles. The tests that need no service run without `-m live`: `.venv/bin/python -m pytest tests/store_pg tests/api/test_store_choice.py -q`.
3. Run the gateway locally: `TTA_ENV=dev .venv/bin/uvicorn --factory tta.api:create_app`. It writes schema `tta_dev`. Run the queries above with `psql "$DATABASE_URL"`, with `tta_dev` in place of `tta`.

## Limits and next steps

- **The gateway's login owns the tables** (above). Next: a gateway login with `INSERT` and `SELECT` on `audit_events` and no ownership. The admin login would then only run migrations. That needs a second URL in the settings.
- **The server certificate is not checked** (`sslmode=require`). Next: `sslmode=verify-full` with the project's CA certificate from the Aiven console.
- **Buyers are kept apart by the gateway, not by the database.** Next: a login per buyer, with row-level security on `audit_buyer` keyed on its profile.
- **One connection per process**, as with SQLite: requests take turns on it. That is enough for one container. More containers would each hold their own connection, and the trail stays linear across them (section 2).
- **No migration version table.** Each migration is idempotent and runs at every start. A change that cannot be written that way would need versioned migrations.
- **The hash cannot be recomputed in SQL.** It is computed over the canonical JSON the gateway writes (`src/tta/audit/chain.py`). That is why `body` is stored as text, exactly as written, and not as `jsonb`.
