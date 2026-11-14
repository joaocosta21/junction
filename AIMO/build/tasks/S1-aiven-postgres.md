# S1 — Stretch: Aiven PostgreSQL for the order book and the audit trail

**Scores on:** 20% ("how decisions are logged and auditable": the database itself refuses to rewrite history, and the supplier gets its own read-only view) · the Aiven award ("a meaningful part of the project, and demonstrate what it enables").
**Runs only if:** the start line approves it · `DATABASE_URL` is set (check through `tta.config`, which reports only true or false) · T13 was green before 06:30. Otherwise skip and log why.
**Owns:** `src/tta/store/postgres.py`, `src/tta/store/sql/`, `tests/store_pg/`, `docs/AIVEN.md`.
**Read first:** SPEC §8, §9 · `AIVEN-CHALLENGE.md` · the hand-back of T06 · current `psycopg` 3 documentation. The orchestrator adds `psycopg[binary]` to `pyproject.toml` before you start.

## Build
- **`PostgresStore`** behind the same `Store` port as the SQLite store. Used when `DATABASE_URL` is set. If the database cannot be reached at start-up the app falls back to SQLite and says so on `/healthz` and on the pages.
- **SQL migrations** in `src/tta/store/sql/`, applied at start-up, idempotent:
  - audit events **append-only in the database**: a trigger rejects `UPDATE` and `DELETE` on the audit table;
  - two views, `audit_buyer` and `audit_supplier`, that implement the reader split of SPEC §9 in SQL;
  - a read-only role limited to `audit_supplier`, if the service lets you create roles; if not, say so and leave the view.
- TLS as the service URI requires. The URL is never logged or printed.
- **`docs/AIVEN.md`:** which service, what it enables that SQLite on a container did not (history that survives a redeploy; history the application cannot rewrite; a supplier login that sees only its view), the queries that show it, and how to reproduce. State it plainly; do not oversell a database swap.

## Tests to write first (against the real service, in a schema `tta_test_<random>` that you create and drop)
- The store contract tests of T06 pass on Postgres.
- An `UPDATE` or `DELETE` on an audit row is refused by the database.
- `audit_supplier` exposes no limit value, no allergen exclusion, no approver name or note.
- With the database unreachable (wrong port), the app starts on SQLite and `/healthz` says so.

## Limits
Touch only objects you created. Never drop a schema or table you did not create in this task.

## Notes added on Saturday 14 Nov (the human chose to build this; the 06:30 gate of the night no longer applies)
- **Read first:** `AIMO/WALKTHROUGH.md` sections 2, 3 (steps 9 and 11) and 6; the hand-backs `T06.md`, `FIX-2.md`, `FIX-7.md` (the store grew `atomic()` transactions, audit triggers, a unique `previous_hash`, a head check inside the append).
- **The `Store` port now has `atomic()`**: everything saved or appended inside the block commits together. `PostgresStore` must implement it (one transaction; a nested block is a savepoint), and every contract test of `tests/store/` must pass on Postgres too — run the same tests against both stores (a parametrised fixture in `tests/store_pg/`), do not copy them.
- **In the database:** triggers that refuse `UPDATE` and `DELETE` on the audit table (as SQLite has now), the head check, and the two views `audit_buyer` and `audit_supplier`. The supplier view must match what `tta.audit` shows the supplier (read `src/tta/audit/readers.py` and `facts.py`: product ids and types, no buyer terms, no limit value, no allergen exclusion, no approver name or note). A read-only role limited to `audit_supplier` if the service lets you create roles.
- **Wiring:** you may edit `src/tta/api/wiring.py` (choose `PostgresStore` when `settings.has_database_url`, else SQLite; a database that cannot be reached at start-up falls back to SQLite and `/healthz` says so in its `reasons`) and the store tests of `tests/api/` that check it. The pages' per-browser sandbox (FIX-10) stays in memory: only the shared order book goes to Postgres.
- **The orchestrator has added `psycopg[binary]` to `pyproject.toml` and installed it** before you start. TLS as the service URI requires; the URI is never logged or printed; tests that need the real service are marked `live` and skipped when `DATABASE_URL` is not set, and create and drop their own schema `tta_test_<random>`.
- **Deployment:** the deployed app will receive `DATABASE_URL` as a fourth secret value (approved by the human); you may add it to `SECRET_NAMES` and `secret_values` in `deploy/modal_app.py` with its test in `tests/deploy/`, nothing else in `deploy/`.
- **`docs/AIVEN.md`:** what it enables that SQLite on a container did not (history that survives a redeploy; history the application cannot rewrite; a supplier login that sees only its view), the SQL that shows each, and how to reproduce. Plain, not oversold.
