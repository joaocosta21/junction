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
