# FIX-4 — done

All six findings are fixed as written. Two residuals are listed under "Not done": the 20 MB limit is checked after httpx has downloaded the body, and other caller-facing details outside finding 5's two still name internals.

**Read first if you build on `ValioClient`:**
- A test that feeds a recorded capture through `ValioClient` must pass `clock=LiveClock(utc_now=...)` set near the capture's time, as `tests/valio/conftest.py` does. With the real machine clock, an availability answer from the demo capture is refused from Sat 14 Nov 14:52 Helsinki on (12 hours after its `timeNow`). `ReplayGateway` is not affected.
- `ValioClient(settings)` now raises `SupplierUnavailable` at construction for a base URL that is not `https://` (`http://` passes for `localhost` or a loopback IP only).
- `CallBudget.remaining` was a property and is now a method, as the task gives it. No code outside `tests/valio` used it.
- Wiring for the floor (T09): `client.calls_remaining` (an `int`, a file read, no call sent). `ReplayGateway` has no such attribute.

## Findings
1. **Budget loses counts — fixed.** `spend` holds `fcntl.flock` on `<count file>.lock` around read-modify-write; the new count goes to a `mkstemp` name and is put in place with `os.replace`. 8 threads, each with its own `CallBudget`, 100 spends each: 800 recorded (132 with the lock switched off, by hand). 4 processes × 200 spends, by hand: 800.
2. **`timeNow` trusted without a bound — fixed.** `LiveClock.observe` refuses a `timeNow` more than 12 hours from this machine's UTC time as `SupplierUnavailable`; the client then neither records, caches nor returns that answer. The clock never reads earlier than it did.
3. **Key in clear text — fixed.** Checked in `ValioClient.__init__` before the HTTP client is built. Neither the error nor the log repeats the address.
4. **Unbounded numbers and bodies — fixed.** Prices 0 to 1,000,000 and amounts 0 to 100,000,000,000, both ends included; a 200 body over 20 MB is refused before it is decoded, parsed or recorded. Residual under "Not done".
5. **Messages name our configuration — fixed for the two named.** Spent budget and missing key both say "The supplier cannot be asked right now, so no call was made."; the count, the limit and the variable name go to a warning record (`tta.valio.budget`, `tta.valio.client`). The key is never logged.
6. **Floor under the budget — fixed.** `CallBudget.remaining() -> int` and `ValioClient.calls_remaining`.

## Built
- `src/tta/valio/budget.py` — lock file, unique temporary file, `remaining()`, `SUPPLIER_NOT_ASKED`, spent-budget warning.
- `src/tta/valio/clock.py` — `MAX_SERVER_TIME_DIFFERENCE` (12 h), refusal of a far `timeNow`, forward-only clock.
- `src/tta/valio/client.py` — `_checked_base_url`, `MAX_BODY_BYTES` (20 × 1024 × 1024), `calls_remaining`, general missing-key message with a warning record.
- `src/tta/valio/parsing.py` — `HIGHEST_PRICE`, `HIGHEST_AMOUNT`; `_number` takes its upper bound.
- `src/tta/valio/__init__.py` — one docstring line on `calls_remaining`.
- `tests/valio/test_client_guards.py` — new: base URL, body size, far and older `timeNow` through the client, `calls_remaining`.
- `tests/valio/test_budget.py`, `test_clock.py`, `test_parsing.py` — new tests for findings 1, 2, 4, 5, 6.
- Existing tests changed, each because a finding changes the intended behaviour:
  - `test_budget.py`: `remaining` → `remaining()` in three tests (finding 6); `test_a_spent_budget_raises_and_counts_no_further` no longer expects "1 of 1" in the detail (finding 5; the count is asserted on the log record in a new test).
  - `test_client.py`: `test_the_budget_stops_the_next_call_with_the_typed_error` and `test_without_a_key_no_call_is_made_and_no_budget_is_spent` expect the general detail and the specifics in a warning record (finding 5); the second now also runs for a blank key.

## Tests
`COVERAGE_FILE=<scratch>/.coverage.fix4 .venv/bin/python -m pytest tests/valio -q -p no:cacheprovider --cov=tta.valio --cov-report=term-missing`
```
Name                        Stmts   Miss Branch BrPart  Cover   Missing
-----------------------------------------------------------------------
src/tta/valio/__init__.py       7      0      0      0   100%
src/tta/valio/budget.py        86      0      8      0   100%
src/tta/valio/client.py       190      0     42      0   100%
src/tta/valio/clock.py         41      0      4      0   100%
src/tta/valio/ids.py            6      0      2      0   100%
src/tta/valio/parsing.py      113      0     34      0   100%
src/tta/valio/recorder.py      46      0      0      0   100%
src/tta/valio/replay.py        83      0     12      0   100%
-----------------------------------------------------------------------
TOTAL                         572      0    102      0   100%
221 passed in 1.45s
```
`.venv/bin/ruff check src/tta/valio tests/valio` → `All checks passed!`
Before the change: 147 passed. Every new test was seen failing first. The folder was run six times in a row: 221 passed each time.
**Importers:** the task names none. `tests/offers/conftest.py` (T07, being written) now imports `ReplayGateway`; `pytest tests/offers` could not be collected: `ImportError: cannot import name 'OfferDeps' from 'tta.offers'`. That is T07's unfinished package; nothing in the trace is in `tta.valio`. Not edited. No live call was made; `var/` is untouched.

## Assumptions
- **The clock rule covers the first answer too.** The live clock reads this machine's UTC time plus the largest lead any answer has stated (0 to 12 hours), in the offset of the last answer. So it is the later of this machine's time and the server's. With both clocks right the difference is the network delay. If the team wants the first answer to set the clock even when it is behind this machine's time, it is a two-line change in `LiveClock.observe` (take the first lead as it is instead of the larger of it and zero); the clock could then step back once per process, by up to 12 hours.
- A forward step stays until the process restarts: an answer that puts the server 11 hours ahead keeps the clock there. That errs towards "cut-off passed" and "expired", never the other way.
- A `timeNow` earlier than the clock reads does not refuse the answer: that is the normal case (the server stamps before the answer travels). Only a difference over 12 hours refuses it.
- The 12 hours are measured against this machine's UTC time. A machine clock more than 12 hours wrong stops live availability (price calls do not carry a time). The mock's `timeNow` was real time in the one live call T01 recorded: recording started 01:13:04 UTC, `timeNow` 03:13:04+02:00.
- The lock is `fcntl.flock`, so POSIX only (macOS, Linux). The lock file stays next to the count. The count file is now written with mode 0600 (`mkstemp`).
- Reading the count (`used`, `remaining()`, `calls_remaining`) takes no lock: the file is replaced in one step, so a reader sees the old count or the new one.
- `remaining()` answers 0 and logs a warning when the count file cannot be read, rather than raising: no call can be made then, and the caller can turn to replay. It does not look at whether a key is set.
- A refused base URL is `SupplierUnavailable`, like every other failure of this package. The URL is read with httpx, the library that sends the request. `localhost` is trusted to be this machine.
- 20 MB is 20 × 1024 × 1024 bytes of the decoded body of a 200 answer. The largest recorded body is 0.5 MB, for 769 ids (demo capture).
- The tax rate and the tax value of a price entry are held to the price range (0 to 1,000,000); the task names prices and amounts only. The bounds also apply in replay (same parser); the three captures pass (prices 0.3 to 541.5, tax rate 13.5 or 25.5, amounts up to 9,999,999,999 in those captures).
- The new details I wrote (12 hours, 20 MB, not https) say the reason and name no setting, file, address or value of ours.

## Contract changes needed
- `Clock.now` docstring in `ports.py` ("the server's `timeNow` as last told, carried forward"): add "never earlier than it read before, and not behind this machine's time". Docstring only.
- `ValioGateway` has no `calls_remaining`: to use the floor the API must hold the `ValioClient` itself. Add it to the port only if the API wants to ask through the port (replay would need an answer too).

## Not done
- **The 20 MB limit does not stop the download.** httpx reads and decompresses the whole body before `_body_text` measures it. Stopping earlier needs a streamed read with a cap in `_send`, which sits in the retry path the task says not to change.
- **Other details that reach callers still name internals** (not in finding 5): budget file unreadable or unsaveable (file name, OS error text, "Correct or delete the file"), recording failed (OS error text), an HTTP refusal (status and the Cloudflare/User-Agent hint), an unusable replay capture (folder and file name). Same treatment: about ten lines and four test assertions.
- **`AvailabilityResponse.time_now` stays as the server stated it.** Code that judges a cut-off with that field instead of `clock.now()` can still be told a time up to 12 hours back. For T07/T03 to check.
- No test with separate processes in the suite (the task asks for threads); checked by hand as above.
- Still open from T01: `scripts/capture_valio.py` does not count against the budget.

## Questions written
0.
