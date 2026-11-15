# Aiven for PostgreSQL: the order book and the audit trail

The gateway keeps its shared order book and its audit trail in an Aiven for PostgreSQL service when `DATABASE_URL` is set. Without it, they stay in SQLite, as before. The store behind both is the same `Store` port (`src/tta/contracts/ports.py`), so no other package changed.

Three things the SQLite file could not give, each with SQL below that shows it: history that survives a redeploy, an audit trail the database itself refuses to change, and a role for Valio Aimo that reads one view and nothing else. The proof on the deployed trail is in section 4.

## What ran, and what did not

Brought up to date on Sun 15 Nov 2026 at 04:00 Helsinki, after the runs of that night against the Aiven service. Times are Helsinki.

- **Ran on 15 Nov, 03:45 to 03:47: the 68 live tests of `tests/store_pg`, against the service, with tonight's SQL. 68 passed, 0 failed** (`test_reader_views.py` 6 in 13 s, `test_postgres_store.py` 25 in 38 s, `test_flow_on_postgres.py` 1 in 11 s, `test_store_contract.py` 36 in 46 s; one file at a time). Each test made its own schema `tta_test_<random>_<n>` with its roles and dropped them; afterwards the database held the schema `tta` and the role `tta_supplier` and nothing else of ours. This is the first time Valio Aimo's view as it stands now (`sql/003_reader_views.sql`) was compared row by row on a database with what `tta.audit` shows the same reader.
- **Ran on 15 Nov, 03:47: the proof on the deployed schema `tta`** (section 4, with its whole output): the database refused an `UPDATE` and a `DELETE` of the audit table from the gateway's own login with `TA001`; with the rights of the supplier's role, the view answered 33 events and every table behind it, the buyer's view and both changes were refused with `42501`.
- **The public link runs on this service** since the deploy of 15 Nov at 03:35: `/healthz` says `store.kind: postgresql`, and its audit head (33 events, last hash `c5cfc61f…a813e3`) is the one the database answers. 26 of the 33 events are older than the container that serves the link: they were written on 14 Nov by earlier containers and by the mistake below, so the trail has outlived its redeploys.
- **Ran by mistake, on 14 Nov at 21:22** (from the log): a local server was started with the team's settings, which carry `DATABASE_URL`, and used this service for about four minutes. It stored the four customers' demo standing orders with their synthetic past orders, and one offer (the bakery, 10 kg of flour); nothing was ordered. An audit event cannot be removed, so those rows are in the trail of schema `tta` (the 9 events of 14 Nov, 21:00 to 22:00).
- **Ran on the morning of 14 Nov** (commit `67f3b00`, by the earlier log): the store, the migrations, the triggers, the two views and the supplier role; the figures of "The service and the connection" and "What it costs" come from that morning.
- **Checked offline:** `tests/audit/test_sql_view.py` (9 tests) compares the SQL file with the Python reader as text. `tests/audit/test_pinned_hashes.py` (20 tests) pins the hashes of stored events, so a change to what is hashed fails a test before it can make the trail already in the database unverifiable.
- **Not created: the supplier's own login.** The role `tta_supplier` exists and cannot log in. What it may read was shown twice: by a login the live test creates and drops in its own schema, and on the deployed schema by the gateway's login taking the role's rights for one transaction (`SET LOCAL ROLE`). A login that Valio Aimo itself would hold does not exist.
- **Not run: `scripts/aiven_proof.py` against a database.** It needs that login (`SUPPLIER_DATABASE_URL`). Section 4 shows the same statements, and more, sent another way.
- **Not run on Modal: the witness** (section 5). Its code ran once by hand on the team's machine against the deployed view.

## The service and the connection

| | |
|---|---|
| Service | Aiven for PostgreSQL, server 18.7 (read again on 15 Nov at 03:47) |
| Driver | psycopg 3.3.9 with its binary wheel, which bundles libpq 18. No system library is needed. |
| TLS | As the service URI asks: Aiven's URI carries `sslmode=require`. A test checks that the store's session is encrypted (`pg_stat_ssl`); the proof of 15 Nov read TLS 1.3 for its own session. `require` encrypts the traffic but does not check the server's certificate. |
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

Both views must show exactly what `tta.audit` shows the same reader. Offline, `tests/audit/test_sql_view.py` compares the SQL text with the reader. On a database (live only; run on 15 Nov at 03:45 against the service, 6 of 6 passed), `tests/store_pg/test_reader_views.py` records the audit package's own two flows (`tests/audit/conftest.py`: the hotel order sent to a human, the ward order placed by the agent) through `AuditTrail` on PostgreSQL. It then compares every row of each view with `AuditTrail.view(...)`. It also runs the audit package's own redaction check on the supplier view: no limit value, no allergen exclusion, no approver name or note.

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

## 4. The proof (ran on 15 Nov on the deployed schema; the one-command script still waits for the supplier's login)

**What ran.** On Sun 15 Nov 2026 at 03:47 Helsinki, against the schema `tta` that the public link writes to, with the gateway's own login read through `tta.config`. Every statement ran in a transaction that was rolled back. The only changes attempted were an `UPDATE` and a `DELETE` written `WHERE false`: they match no row, so a database that did not refuse them would still have changed nothing. No `TRUNCATE`, no `INSERT`, nothing created. The supplier's seat was taken with `SET LOCAL ROLE tta_supplier` inside such a transaction: the statements then run with the role's rights and nothing else. The statements were sent by a short script kept outside the repository; they are all below, so anyone with the login can send them again. The whole output:

```
Run at 2026-11-15T01:47:30+00:00

-- server
SELECT split_part(version(), ' on ', 1), current_setting('server_version');
   -> PostgreSQL 18.7 | 18.7

-- TLS of this session
SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid();
   -> True | TLSv1.3

-- schemas whose name starts with tta
SELECT nspname FROM pg_namespace WHERE starts_with(nspname, 'tta') ORDER BY 1;
   -> tta

-- roles whose name starts with tta or valio
SELECT rolname, rolcanlogin FROM pg_roles WHERE starts_with(rolname, 'tta') OR starts_with(rolname, 'valio') ORDER BY 1;
   -> tta_supplier | False

-- the triggers on the audit table ('A' = fires always)
SELECT tgname, tgenabled FROM pg_trigger WHERE tgrelid = 'tta.audit_events'::regclass AND NOT tgisinternal ORDER BY 1;
   -> audit_events_append_only | A
   -> audit_events_follow_head | A

-- the head of the trail (compare with /healthz audit_head)
SELECT count(*) AS events, max(seq) AS last_seq, min(time) AS first_event, max(time) AS last_event FROM tta.audit_events;
   -> 33 | 33 | 2026-11-14 09:15:58.166751+00:00 | 2026-11-15 01:35:28.606903+00:00

-- the last hash
SELECT seq, hash FROM tta.audit_events ORDER BY seq DESC LIMIT 1;
   -> 33 | c5cfc61f3895365357b81aeb07b082e6ad7d2b5ea0257a3cb8eee65a04a813e3

-- event types in the trail
SELECT type, count(*) FROM tta.audit_events GROUP BY type ORDER BY 2 DESC, 1;
   -> tta.v1.lookup.performed | 5
   -> tta.v1.offer.created | 5
   -> tta.v1.policy.evaluated | 5
   -> tta.v1.request.parsed | 5
   -> tta.v1.request.received | 5
   -> tta.v1.standing_order.created | 4
   -> tta.v1.order.placed_by_agent | 2
   -> tta.v1.approval.requested | 1
   -> tta.v1.suggestions.shown | 1

-- orders in the shared book by status
SELECT status, count(*) FROM tta.orders GROUP BY status ORDER BY 1;
   -> ORDERED | 2
   -> PENDING_APPROVAL | 1

-- what the supplier role holds
SELECT table_schema, table_name, privilege_type FROM information_schema.role_table_grants WHERE grantee = 'tta_supplier';
   -> tta | audit_supplier | SELECT

-- the supplier view's columns
SELECT column_name FROM information_schema.columns WHERE table_schema = 'tta' AND table_name = 'audit_supplier' ORDER BY ordinal_position;
   -> seq
   -> offer_id
   -> order_id
   -> approval_id
   -> id
   -> type
   -> time
   -> actor
   -> sentence
   -> rule_ids
   -> facts
   -> hash

== The gateway's own login (the table's owner) tries to change the trail ==

-- an UPDATE of the audit table
UPDATE tta.audit_events SET hash = hash WHERE false;
   -> refused: SQLSTATE TA001, audit_events is append-only: UPDATE is refused, an event cannot be changed or removed

-- a DELETE on the audit table
DELETE FROM tta.audit_events WHERE false;
   -> refused: SQLSTATE TA001, audit_events is append-only: DELETE is refused, an event cannot be changed or removed

== With the rights of the supplier's role (SET LOCAL ROLE, rolled back) ==

-- who
SELECT current_user;   [as role tta_supplier]
   -> tta_supplier

-- the supplier reads its view
SELECT count(*), max(seq) FROM tta.audit_supplier;   [as role tta_supplier]
   -> 33 | 33

-- the last three sentences of its view
SELECT seq, type, sentence FROM tta.audit_supplier ORDER BY seq DESC LIMIT 3;   [as role tta_supplier]
   -> 33 | tta.v1.approval.requested | The agent could not place order ord_cdb1800d43fe alone under the buyer's rules. The order (200 pcs of 464013 for €402.00 net) was sent to a person of the buyer for approval. Rule that applied: F-10, a rule the buyer set (every order needs human approval): approval by a person of the buyer.
   -> 32 | tta.v1.suggestions.shown | 1 suggestion was shown to the buyer with offer off_72e0f68fe2e8: a forgotten item. 1 was not shown: 1 with too little confirmed stock for the quantity.
   -> 31 | tta.v1.policy.evaluated | The buyer's rules were checked for option opt_1: a person of the buyer must approve this order. Rule that applied: F-10, a rule the buyer set (every order needs human approval): approval by a person of the buyer. The strictest outcome among the rules that applied decides.

-- the supplier role reads audit_events
SELECT 1 FROM tta.audit_events LIMIT 1;   [as role tta_supplier]
   -> refused: SQLSTATE 42501, permission denied for table audit_events

-- the supplier role reads audit_buyer
SELECT 1 FROM tta.audit_buyer LIMIT 1;   [as role tta_supplier]
   -> refused: SQLSTATE 42501, permission denied for view audit_buyer

-- the supplier role reads orders
SELECT 1 FROM tta.orders LIMIT 1;   [as role tta_supplier]
   -> refused: SQLSTATE 42501, permission denied for table orders

-- the supplier role reads offers
SELECT 1 FROM tta.offers LIMIT 1;   [as role tta_supplier]
   -> refused: SQLSTATE 42501, permission denied for table offers

-- the supplier role reads approvals
SELECT 1 FROM tta.approvals LIMIT 1;   [as role tta_supplier]
   -> refused: SQLSTATE 42501, permission denied for table approvals

-- the supplier role tries an UPDATE
UPDATE tta.audit_events SET hash = hash WHERE false;   [as role tta_supplier]
   -> refused: SQLSTATE 42501, permission denied for table audit_events

-- the supplier role tries a DELETE
DELETE FROM tta.audit_events WHERE false;   [as role tta_supplier]
   -> refused: SQLSTATE 42501, permission denied for table audit_events
```

What it shows:
- **The database refuses, not the application.** The gateway's login owns the table, and its `UPDATE` and `DELETE` are still refused, by the trigger, with our own SQLSTATE `TA001`. Both triggers are `A`: they fire always.
- **Valio Aimo's role reads its view and nothing behind it.** 33 events through `audit_supplier`; `permission denied` (`42501`) for `audit_events`, `audit_buyer`, `orders`, `offers` and `approvals`, and for both changes. The role holds one grant, `SELECT` on `tta.audit_supplier`, and cannot log in.
- **The head is the link's.** 33 events and the hash `/healthz` shows as `audit_head`.
- **Not shown here:** a `TRUNCATE`, and a change after `SET session_replication_role = replica`. Both are refused in the live tests, in a schema of their own (`tests/store_pg/test_postgres_store.py`); on the deployed trail they were not tried, because a database that failed to refuse them would have lost the trail.

**What did not run: `scripts/aiven_proof.py`.** It connects with the supplier's own login, read from `SUPPLIER_DATABASE_URL`, and prints each statement before its result. `--dry-run` lists the statements and sends nothing; `--schema` names another schema than `tta`. Its 8 statements:

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

With the supplier's login the refusals are "permission denied", as in the output above. The script exits 0 when every statement did what the table says, 1 when one did not, 2 when nothing could be sent. It has 13 offline tests with a stand-in connection (`tests/store/test_aiven_proof.py`). It does not create the supplier's login: that is the `CREATE ROLE` statement of section 3, run once by a person who then holds the password. With the login's URL in the environment as `SUPPLIER_DATABASE_URL`: `.venv/bin/python scripts/aiven_proof.py`.

## 5. A witness of the trail's head (its code ran once by hand; not scheduled on Modal)

The hash chain shows a changed event in the middle. A trail cut at its end, or rewritten whole, still verifies by itself unless another party holds an earlier head. `deploy/witness.py` is that other party, in the supplier's seat: with the supplier's read-only login it reads the count, the last position and the last hash from `audit_supplier`, notes them, and at its next run checks that the head it noted is still in place. Its findings are: first run, same head, the same head for six hours or longer, grown, shortened, rewritten. `deploy/modal_app.py` schedules it hourly on Modal only when `SUPPLIER_DATABASE_URL` is set in the shell that deploys. That value has never been set, so no such function exists on Modal.

**Ran once by hand, on 15 Nov at 03:57, on the team's machine:** the module's own `witness_once`, twice, over a connection that had taken the supplier role's rights (`SET ROLE tta_supplier`, read only), with its notes in a plain dict where Modal would keep a `modal.Dict`. The last two lines are the pure function alone, with no database:

```
connected as: tta_supplier | session user is the gateway's login
run 1 at 2026-11-15T01:57:07+00:00: FIRST: First run: the head was noted (33 events, last number 33, hash c5cfc61f3895…).
run 2 at 2026-11-15T01:57:07+00:00: SAME: The head is the one noted last time (33 events, last number 33, hash c5cfc61f3895…).
note kept: {'count': 33, 'seq': 33, 'hash': 'c5cfc61f3895365357b81aeb07b082e6ad7d2b5ea0257a3cb8eee65a04a813e3', 'noted_at': '2026-11-15T01:57:07.673004+00:00', 'moved_at': '2026-11-15T01:57:07.590974+00:00', 'finding': 'SAME'}
if the trail lost its last event: The audit trail was shortened: 33 events were noted (last number 33), and it holds 32 now (last number 32). The earlier note is kept.
if the noted event were rewritten: The audit trail was rewritten: event number 33 was noted with hash c5cfc61f3895…, and that place holds ffffffffffff… now. The earlier note is kept.
```

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
2. Run the tests against the service: `.venv/bin/python -m pytest tests/store_pg -q -m live` (68 tests; run on 15 Nov, one file at a time, in under two minutes). Each test creates its own schema and drops it, with its roles. The tests that need no service run without `-m live`: `.venv/bin/python -m pytest tests/store_pg tests/api/test_store_choice.py -q`.
3. Run the gateway locally: `TTA_ENV=dev .venv/bin/uvicorn --factory tta.api:create_app`. It writes schema `tta_dev`. Run the queries above with `psql "$DATABASE_URL"`, with `tta_dev` in place of `tta`.

Steps 2 and 3 send SQL to the service. Step 2 ran on 15 Nov; step 3 was not run on purpose since the morning of 14 Nov. Start a local gateway with `--no-proxy-headers` when it should not believe a forwarded address (`docs/ASSUMPTIONS.md`, row "Rate limits").

## Assumptions and next steps

- **The pages do not use it.** Every page, the shop included, keeps each browser's order book in memory. Only REST and MCP callers write to the shared book, and so to Aiven. Next: a page that shows Valio Aimo's log of the shared book; the shop page shows Valio Aimo's view of an order of the browser's own book today.
- **A stored order is not tied to its audit event.** The triggers protect the audit table. An order or an offer row can still be changed by whoever can write the database, and the gateway then answers the changed row with a signature that verifies. Next: a reference from each record to its event, checked when the record is read.
- **The gateway's login owns the tables** (above). Next: a gateway login with `INSERT` and `SELECT` on `audit_events` and no ownership. The admin login would then only run migrations. That needs a second URL in the settings.
- **The server certificate is not checked** (`sslmode=require`). Next: `sslmode=verify-full` with the project's CA certificate from the Aiven console.
- **Buyers are kept apart by the gateway, not by the database.** Next: a login per buyer, with row-level security on `audit_buyer` keyed on its profile.
- **One connection per process**, as with SQLite: requests take turns on it. That is enough for one container. More containers would each hold their own connection, and the trail stays linear across them (section 2).
- **No migration version table.** Each migration is idempotent and runs at every start. A change that cannot be written that way would need versioned migrations.
- **The hash cannot be recomputed in SQL.** It is computed over the canonical JSON the gateway writes (`src/tta/audit/chain.py`). That is why `body` is stored as text, exactly as written, and not as `jsonb`.
