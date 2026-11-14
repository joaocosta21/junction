# T01 — Valio client, recorder, replay, clock

**Scores on:** 30% (the flow runs in the mocked environment and survives it being down) · 15% (production path: budget, cache, retries).
**Needs:** T00. **Owns:** `src/tta/valio/`, `tests/valio/`.
**Read first:** SPEC §4, §10 · `AIMO/docs/API.md` · `AIMO/docs/FIELD-DICTIONARY.md` (API payloads) · `tta/contracts/availability.py`, `ports.py`.

## Build
- `ValioClient` implementing the `ValioGateway` port: `price(ids)` and `availability(ids)` over `httpx`, header `X-API-Key`, body `{customer, requestedDate, products}`.
- **Always send an explicit `User-Agent` and `Accept: application/json`.** The API sits behind Cloudflare. Friday's working calls sent `User-Agent: retest-client/1.0`; on 14 Nov the same key got 403 on `/ping` with Python's default user agent and 200 with an explicit one (FINDINGS §1). A 403 is reported as `SupplierUnavailable` with that hint, never retried in a loop.
- Chunks of at most 1,000 ids; at least one second between calls; a 60-second cache keyed by endpoint and sorted ids; a call budget persisted in `var/` that raises `SupplierUnavailable` when spent; two retries with back-off on time-outs and 5xx only.
- Parsing into the contract models: optional fields are omitted, never `null`; the sales unit comes from the API line; `/api/price` marks unknown ids with `error: true`, `/api/availability` does not.
- **Recorder:** every live response body is written to `var/recordings/` with the id list and `timeNow`. The key and request headers are never written.
- **`ReplayGateway`:** same port, reads a capture folder of `fixtures/valio/`; an id not in the capture behaves as the live API does for an unknown id.
- **Clocks:** `LiveClock` (the `timeNow` of the last response, else UTC now) and `PinnedClock`.

## Tests to write first
- A captured body parses into models; a product with no schedule line, one with amount 0, one Terminal `999999`, one Stock placeholder each keep their raw values.
- 2,300 ids → three calls; a repeated call inside 60 seconds makes no request; the budget stops the next call with the typed error.
- The key never appears in a recording, a log record or an exception message (assert on a sentinel key).
- Replay returns objects equal to parsing the same bodies live (via `httpx.MockTransport`).
- Time-out → retried twice → `SupplierUnavailable`.

## Limits
- No test calls the live API. You may make **at most 2 live calls** at the very end to confirm the client against the real endpoints; report them in the hand-back.
