# FIX-11 — Rate limits for a room on one Wi-Fi

**Scores on:** 30% (the deployed demo must keep working while a room of peer reviewers uses it). From FIX-10's question (`AIMO/build/questions/FIX-10.md`) and its hand-back.
**Owns:** `src/tta/api/limits.py`, `src/tta/api/sandbox.py` (only if needed), `tests/api/test_limits.py`, `tests/api/test_visitors.py` and new test files in `tests/api/` named `test_room_*.py`. Read `src/tta/ui/` to learn the own-book cookie's name; do not edit `src/tta/ui/`. Other agents are editing `src/tta/api/routes.py`, `service.py`, `wiring.py`, `src/tta/agent/`, `src/tta/store/`, `src/tta/orders/`, `src/tta/ui/` right now: do not touch those.
**Read first:** `AIMO/build/AGENT-RULES.md`, `AIMO/build/handback/FIX-8.md`, `FIX-10.md`, `AIMO/build/tasks/FIX-10-pages-api.md` (finding 2).

## The problem
Every peer reviewer on the venue Wi-Fi reaches the deployed demo from one public address. FIX-10 keys the per-visitor windows on the address alone (20 lookups, 20 orders and decisions, 5 model runs a minute), so the whole room shares one visitor's windows: on one laptop the sixth model call of a minute was refused.

## Build (decided by the orchestrator)
- **On the pages, a visitor is a browser:** when a request carries the own-book cookie of the pages (the per-browser sandbox of FIX-10), the per-visitor windows key on that cookie (20 / 20 / 5 a minute, as now). REST and MCP keep keying on the address (and identity where FIX-10 does).
- **A cap per address above the per-browser windows**, so rotating cookies cannot take the whole app: per address, at most half of each global ceiling (60 lookups, 60 orders and decisions, 15 model runs a minute); global ceilings unchanged (120, 120, 30); live supplier looks unchanged (6 overall, 2 per visitor).
- **New own books per address:** at most 30 created per address per 10 minutes, so one address cannot push the other visitors' books out of the 300.
- Named constants; the refusal sentence says which window was full (browser, address or the whole app).

## Tests first
- Twelve browsers behind one address each run scenario 2 within a minute and all are served; a 61st lookup from that address within the minute is refused with the address sentence.
- A browser with no cookie (or REST) is counted by address, as before.
- Cookie rotation from one address cannot pass the address cap or create more than 30 books in 10 minutes.

## Rules
Usual rules (`AIMO/build/AGENT-RULES.md`); `COVERAGE_FILE` in a private scratch folder; at the end run `tests/api tests/ui tests/mcp tests/e2e`. Hand-back `AIMO/build/handback/FIX-11.md`.
