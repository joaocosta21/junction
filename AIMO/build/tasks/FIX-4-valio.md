# FIX-4 — Valio client: a budget that counts, a clock that cannot be steered, bounded input

**Scores on:** 15% (credible path to production) · 30% (the flow must not fall over on a strange answer). From review round 1 (Python reviewer finding 5; security findings 7, 8, 11).
**Owns:** `src/tta/valio/`, `tests/valio/`. **Builder's hand-back:** `AIMO/build/handback/T01.md`. **Read:** SPEC §10.
**Importers to re-run:** none exist yet (T07 is being written now and uses `ValioClient`, `ReplayGateway`, their `.clock`, `price(ids, *, fresh=False)` and `availability(ids, *, fresh=False)`: do not change these).

## Findings to fix
1. **MEDIUM — the call budget loses counts with more than one writer.** `budget.py` (`spend`, `_write`): a read-modify-write with no file lock and one shared temp-file name. Eight threads with their own `CallBudget` on one file made 800 spends and recorded 131. Use an exclusive file lock (`fcntl.flock` on a lock file next to the count) around read-modify-write and a unique temp name, so two clients, two processes, or a script next to the app count correctly. Test with threads that each build their own `CallBudget`.
2. **MEDIUM — the upstream `timeNow` is trusted without a bound.** `clock.py` (`LiveClock.observe`): any offset-aware value is accepted, also one years in the past or one that moves backwards, and that clock decides cut-offs and expiry. Refuse (as `SupplierUnavailable`, answer not used) a `timeNow` more than 12 hours away from this machine's UTC time, and never let the clock move backwards. Named constants.
3. **MEDIUM — the key can travel in clear text.** `client.py`: `valio_aimo_base_url` accepts `http://`. Refuse at construction any base URL that is not `https://`, except a loopback host (for tests); the error does not echo the URL.
4. **LOW — unbounded numbers and bodies.** `parsing.py`: accept a price only in the range 0 to 1,000,000 and an amount only from 0 to 100,000,000,000 (the largest placeholder is 9,999,999,999); anything else refuses the answer as `SupplierUnavailable`. `client.py`: refuse a response body over 20 MB before parsing or recording it.
5. **LOW — messages to callers name our configuration.** The `SupplierUnavailable` details for a spent budget and a missing key name environment variables and counts; these become the `detail` of a public problem response. Keep the caller's message general ("the supplier cannot be asked right now") and put the specifics in a log record at warning level, never the key.
6. **For the public demo — a floor under the budget.** Add a settings-free way to learn what is left: `CallBudget.remaining() -> int` and `ValioClient.calls_remaining`, so the API can fall back to replay before the budget is spent.

## Not to change
The cache, the spacing, the retries, the recorder format, the replay gateway's behaviour for an unknown id.

## Rules for this fix
- Read `AIMO/build/AGENT-RULES.md` first. Then the hand-back of the package's builder (named below) and the files named in each finding.
- Other agents are working in the same tree right now: T07 writes `src/tta/offers/`, T08 writes `src/tta/orders/`, and other fix agents edit other packages. Touch only the paths this task owns. Keep every file importable after each edit: make one coherent edit per file rather than leaving it half-changed while you run something.
- For each finding: write the failing test first, see it fail, fix, see it pass. Keep the existing tests passing; change an existing test only when the finding changes the intended behaviour, and say which in the hand-back.
- Run your package's tests and the linter, with `COVERAGE_FILE` set to a file in your scratch directory. Then run the tests of the packages that import yours (named below) and report their result; do not edit them.
- Hand-back in `AIMO/build/handback/<this task id>.md` in the usual shape, with one line per finding: fixed, partly fixed (what is left), or not fixed (why).
