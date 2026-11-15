# Aiven for PostgreSQL: the order book and the audit trail

The gateway keeps its shared order book and its audit trail in an Aiven for PostgreSQL service when `DATABASE_URL` is set. Without it, they stay in SQLite, as before. The store behind both is the same `Store` port (`src/tta/contracts/ports.py`), so no other package changed.

This is a database swap with three consequences the SQLite file could not give. Each one has SQL below that shows it.

## What ran, and what did not

Checked against the code at commit `c2106fe`, offline, and brought up to date on Sun 15 Nov 2026 from the code at commit `94b21a5` and the run's log (`AIMO/build/replan/STATUS.md`). No call to the Aiven service was made for this page. One was made by mistake during the night: see the third point.

- **Ran against the Aiven service, on the morning of Saturday 14 Nov** (commit `67f3b00`, by the earlier log; not repeated since): the store, the migrations, the triggers, the two views and the supplier role, through the tests of `tests/store_pg`; the figures of "The service and the connection" and "What it costs" come from that morning.
- **Changed on 14 Nov, offline:** Valio Aimo's view (`sql/003_reader_views.sql`) now shows every rule that fired and names a person by role. It is dropped and created again at every start. A setting, `TTA_DB_SCHEMA`, chooses the schema.
- **Ran by mistake, on 14 Nov at 21:22** (from the log): a local server was started with the team's settings, which carry `DATABASE_URL`, and used this service for about four minutes. At its start the schema statements ran, the rewritten view of Valio Aimo among them, without error: the first time that SQL ran on a database. The server stored the four customers' demo standing orders with their synthetic past orders, and one offer (the bakery, 10 kg of flour); nothing was ordered. An audit event cannot be removed, so those rows are in the trail of schema `tta`. A redeploy with `DATABASE_URL` must therefore run the same code line, or start a new trail in a new schema (`TTA_DB_SCHEMA`).
- **Checked offline:** `tests/audit/test_sql_view.py` (9 tests) compares the SQL file with the Python reader as text: the columns, the roles, the words. `tests/audit/test_pinned_hashes.py` (20 tests) pins the hashes of stored events, so a change to what is hashed fails a test before it can make the trail already in the database unverifiable.
- **Not run: the view's SQL as it stands now.** It changed after the run of 21:22 (the product of an `evidence.attached` event is masked), and the tests that execute it have not been run since the view was rewritten: they are the live ones of `tests/store_pg` (117 tests in the folder; the live ones are skipped unless the run selects `-m live`). They must pass against the service before any deploy with `DATABASE_URL`: a view that fails to create fails the whole start-up, and the gateway then runs on SQLite with the reason in `/healthz`.
- **Not run: the proof script against a database** (section 4). Only its dry run, which sends nothing.
- **Not created: the supplier's login.** The role exists without a login; "Valio Aimo reads its own view" has been shown by a test login only.
- **Not run: the witness** (section 5).

## The service and the connection

| | |
|---|---|
| Service | Aiven for PostgreSQL, server 18.7 (`SHOW server_version`, read on the morning of 14 Nov) |
| Driver | psycopg 3.3.9 with its binary wheel, which bundles libpq 18. No system library is needed. |
| TLS | As the service URI asks: Aiven's URI carries `sslmode=require`. A test checks that the store's session is encrypted (`pg_stat_ssl`); a probe of the service saw TLS 1.3. `require` encrypts the traffic but does not check the server's certificate. |
| Schema | The one `TTA_DB_SCHEMA` names, when it is set (a plain lower-case name of at most 41 characters; any other value is refused and the gateway falls back to SQLite, saying so). Otherwise `tta` for the deployed gateway (`TTA_ENV=demo` or `prod`) and `tta_dev` for a local run (`TTA_ENV=dev`), so a laptop with the same URL never writes into the demo's trail, which cannot be cleaned afterwards. An audit event cannot be removed, so a build that can no longer read an old trail starts a new one in a new schema and the old one stays as it is. Tests use their own schemas `tta_test_<random>_<n>`, dropped after each test. |
| Secret | The URL is read through `tta.config` only, where the connection is opened. libpq's own error text names the server, and for a malformed URL it repeats the password. So a failed connection is logged by its error class alone and is not chained to the raised error (`tests/store_pg/test_unreachable.py`). |
| Start-up | The store connects, creates its schema and runs the migrations of `src/tta/store/sql/` in one transaction under a lock, so two containers starting together take turns. Every migration is idempotent and runs at every start. |
| Fallback | If the database cannot be reached or prepared at start-up, the gateway starts on SQLite, logs a warning and lists the reason in `/healthz`. It does not switch back by itself: that takes a restart. |
| Which store is in use | `/healthz` says it in `store`: `kind` is `postgresql` or `sqlite`, with the reason. Never the address, the database name or a path. |

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

**Assumption, and the next step.** The table's owner can drop or disable a trigger first. Today the gateway connects with the service's admin login, which owns the tables. The hash chain still shows a changed or removed event when someone does that (`src/tta/audit/chain.py`). Closing this gap takes a second login for the gateway that does not own the tables (see "Next steps").

## 3. A supplier login that sees only its view

The two readers of SPEC §9 are views (`sql/003_reader_views.sql`):

- **`audit_buyer`**: every field, with the buyer profile, so a buyer's query names its own profile. The gateway keeps one buyer from another: it checks who is asking.
- **`audit_supplier`**: what Valio Aimo may see. It has no buyer profile, and it uses the supplier's sentence and facts, which the audit package builds from an allow-list: the buyer's limit amounts, its allergen exclusions and the products they concern are masked there. It shows every rule that fired, each id once, in the order they fired. It shows an agent by kind and id only, and a person by the approver roles they hold ("The buyer's purchasing manager"; "The buyer's purchasing manager, finance, dietitian" at the hotel and the bakery, where one person holds every role), never by name or id; a person who holds no approver role reads "A human at the buyer". The view is dropped and created again at every start, because PostgreSQL refuses to replace a view whose columns changed; `sql/004` gives the grant again right after.

Both views must show exactly what `tta.audit` shows the same reader. Offline, `tests/audit/test_sql_view.py` compares the SQL text with the reader. On a database (live only, not run since the view changed on 14 Nov), `tests/store_pg/test_reader_views.py` records the audit package's own two flows (`tests/audit/conftest.py`: the hotel order sent to a human, the ward order placed by the agent) through `AuditTrail` on PostgreSQL. It then compares every row of each view with `AuditTrail.view(...)`. It also runs the audit package's own redaction check on the supplier view: no limit value, no allergen exclusion, no approver name or note.

`sql/004_supplier_role.sql` creates the role `<schema>_supplier` (`tta_supplier` for the schema `tta`). It cannot log in, and it holds one privilege: `SELECT` on `tta.audit_supplier`. A view reads its tables with its owner's rights, so the role reads the projection and never the rows behind it. The supplier's own login is made a member of the role. **This login has not been created on the service yet:**

```sql
-- As the admin login, once:
CREATE ROLE valio_aimo LOGIN PASSWORD '<a strong password>' IN ROLE tta_supplier;

-- As valio_aimo:
SELECT seq, type, time, actor, sentence, rule_ids, facts FROM tta.audit_supplier ORDER BY seq;   -- rows
SELECT * FROM tta.audit_events;   -- ERROR: permission denied for table audit_events
SELECT * FROM tta.audit_buyer;    -- ERROR: permission denied for view audit_buyer
SELECT * FROM tta.orders;         -- ERROR: permission denied for table orders
```

The live test does exactly this with a login it creates and drops. It also checks that the role holds no grant but `SELECT` on `audit_supplier`.

Both readers on one order:

```sql
SELECT seq, sentence FROM tta.audit_buyer    WHERE order_id = '<order id>' ORDER BY seq;
SELECT seq, sentence FROM tta.audit_supplier WHERE order_id = '<order id>' ORDER BY seq;
```

## 4. The proof in one command (built, not run against a database)

`scripts/aiven_proof.py` connects with the supplier's own login, read from `SUPPLIER_DATABASE_URL`, and prints each statement before its result. `--dry-run` lists the statements and sends nothing; `--schema` names another schema than `tta`. The dry run, run offline on 14 Nov, lists 8 statements:

| # | Statement | The database must |
|---|---|---|
| 1 | `SELECT current_user` | answer |
| 2 | `SELECT seq, type, sentence FROM tta.audit_supplier ORDER BY seq DESC LIMIT 5` | answer |
| 3 | `SELECT seq FROM tta.audit_events LIMIT 1` | refuse it |
| 4 | `SELECT seq FROM tta.audit_buyer LIMIT 1` | refuse it |
| 5 | `UPDATE tta.audit_events SET hash = hash WHERE false` | refuse it |
| 6 | `DELETE FROM tta.audit_events WHERE false` | refuse it |
| 7 | `SELECT count(*) AS events, max(seq) AS last_seq FROM tta.audit_supplier` | answer |
| 8 | `SELECT seq, hash FROM tta.audit_supplier ORDER BY seq DESC LIMIT 1` | answer |

Statements 5 and 6 are written `WHERE false`, so a database that did not refuse them would still change nothing. With the supplier's login the refusals are "permission denied"; the append-only triggers are what refuse the gateway's own login (section 2), and the script does not show that case. The script exits 0 when every statement did what the table says, 1 when one did not, 2 when nothing could be sent. It has 13 offline tests with a stand-in connection (`tests/store/test_aiven_proof.py`). The script does not create the supplier's login: that is the `CREATE ROLE` statement of section 3, run by hand. The commands are in `docs/DEPLOY.md`, "To run".

## 5. A witness of the trail's head (built, not run)

The hash chain shows a changed event in the middle. A trail cut at its end, or rewritten whole, still verifies by itself unless another party holds an earlier head. `deploy/witness.py` is that other party, in the supplier's seat: with the supplier's read-only login it reads the count, the last position and the last hash from `audit_supplier`, notes them, and at its next run checks that the head it noted is still in place. Its findings are: first run, same head, grown, shortened, rewritten. `deploy/modal_app.py` schedules it hourly on Modal only when `SUPPLIER_DATABASE_URL` is set on the deploying machine. That value has never been set, so the witness has never run.

## What it costs

Measured on the morning of 14 Nov from the development machine; not re-measured since.

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

Steps 2 and 3 send SQL to the service. Neither was run on purpose since the morning of 14 Nov. Start a local gateway with `--no-proxy-headers` when it should not believe a forwarded address (`docs/ASSUMPTIONS.md`, row "Rate limits").

## Assumptions and next steps

- **The pages do not use it.** Every page, the shop included, keeps each browser's order book in memory. Only REST and MCP callers write to the shared book, and so to Aiven. Next: a page that shows Valio Aimo's log of the shared book; the shop page shows Valio Aimo's view of an order of the browser's own book today.
- **A stored order is not tied to its audit event.** The triggers protect the audit table. An order or an offer row can still be changed by whoever can write the database, and the gateway then answers the changed row with a signature that verifies. Next: a reference from each record to its event, checked when the record is read.
- **The gateway's login owns the tables** (above). Next: a gateway login with `INSERT` and `SELECT` on `audit_events` and no ownership. The admin login would then only run migrations. That needs a second URL in the settings.
- **The server certificate is not checked** (`sslmode=require`). Next: `sslmode=verify-full` with the project's CA certificate from the Aiven console.
- **Buyers are kept apart by the gateway, not by the database.** Next: a login per buyer, with row-level security on `audit_buyer` keyed on its profile.
- **One connection per process**, as with SQLite: requests take turns on it. That is enough for one container. More containers would each hold their own connection, and the trail stays linear across them (section 2).
- **No migration version table.** Each migration is idempotent and runs at every start. A change that cannot be written that way would need versioned migrations.
- **The hash cannot be recomputed in SQL.** It is computed over the canonical JSON the gateway writes (`src/tta/audit/chain.py`). That is why `body` is stored as text, exactly as written, and not as `jsonb`.
