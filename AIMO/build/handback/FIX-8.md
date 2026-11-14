# FIX-8 — done

Continuation. The first agent (05:05–05:40, stopped on a usage limit) had built all 14 findings with their tests, and the `/mcp` exact-path mount with its 401 test. Its work was checked against the task finding by finding and nothing needed redoing. This run added one test (the per-visitor window through the real MCP tools), re-ran everything and wrote this hand-back. No call to the live Valio API and no model call.

## Findings
1. **Fixed.** `FallbackGateway.look_up` answers both calls live, or both from the capture when either live call fails or the budget cannot cover two calls. `offers/deps.py` `look_up` uses the paired lookup when the gateway has one and two calls otherwise, and refuses a pair from two sources (`SupplierUnavailable`). The re-check before an order goes the same way (`revalidation.py` calls `look_up(fresh=True)`). Both reproductions are tests through the app: budget at exactly 10, and availability failing after a live price.
2. **Fixed.** The source-following clock is removed. In live mode the data clock is the live clock, also while the capture answers; a replayed answer keeps the capture's `time_now` and `source: replay`. `/healthz` `source` is the last completed look, read and written under the lock, and `null` before the first one in live mode.
3. **Fixed.** A base URL the live client refuses raises `GatewayConfigurationError` and the start stops. The address is not repeated and nothing is opened.
4. **Fixed.** `ClientKeyMiddleware` on the root app sets the client key: the peer, or the first `X-Forwarded-For` address when the peer is private or loopback. Demo identities are counted by identity plus client key, environment tokens by identity alone. Global ceilings: lookups 120, orders and decisions 120, model 30 per minute, refused as `rate-limited` with `Retry-After`. Live looks are capped at `MAX_LIVE_LOOKS_PER_MINUTE = 6`; above that the capture answers, labelled replay. A 401 is not counted. Checked through REST and, new this run, through the real MCP tools.
5. **Fixed.** `AuditTrail.head()` keeps the pair in memory and re-reads only when `store.last_audit_hash()` differs. `/healthz` no longer shows `valio_call_budget`. It has `status` `ok`/`degraded` and `reasons` (live paused, budget low, capture answering in live mode).
6. **Fixed.** The global `ValidationError` handler is removed. `invalid-request` comes from `RequestValidationError` and from `reading_caller_input()` (around the parser call in `parse_request`). Any other `ValidationError` is a 500 with a generic detail, and the trace goes to the log.
7. **Fixed.** `tta.agent` with neither factory raises `HookError`. With only one factory the start goes on and a warning names the missing one.
8. **Fixed.** `build_parts` and `create_app` close what they opened when a later step raises. `Parts.close` closes every part and raises the first failure afterwards. There are tests for both and for the live client being closed on shutdown.
9. **Fixed.** The examples are built once in the lifespan, in a worker thread. A failed scenario is logged and left out, and the document's description names it. `build_examples` never raises.
10. **Fixed.** `create_offer` writes `request.received` first, with the offer id and the lines' `text` joined by "; ". `parse_request` records it only when parsing fails, and `run_agent` only when the run made no offer. That gives one per offer.
11. **Fixed.** `_declared_length` uses `isascii() and isdigit()`. A raw ASGI test covers `²`, `¹²`, `-1`, `1e3` and an empty value.
12. **Fixed.** Outside dev and demo the start stops on any of these: a token shorter than 24 characters, a token mapped twice (seen through `object_pairs_hook`), two tokens with the same identity id, or an identity that repeats a field. Errors name positions only.
13. **Fixed.** `SecurityHeadersMiddleware` sets `nosniff` and `no-referrer` on every response and adds `Cache-Control: no-store` under `/v1`. This covers the mounted surfaces and the body-limit refusals. The 500 handler adds the headers itself.
14. **Fixed.** `/v1` (exact) belongs to the API and gets a 404 problem, never a page. `/mcp` (exact) is the MCP surface's root, with no redirect (`_McpMount`). A test checks that `POST /mcp` and `POST /mcp/` without a token both get the MCP SDK's own 401 (`invalid_token`), with pages mounted and without. It was also checked by hand with the real `tta.ui.routes` and `mcp_surface`.

## Built
- `src/tta/api/fallback.py`: paired lookup, one source per look, live data clock, `state()` for `/healthz`, 6 live looks a minute, `close()`.
- `src/tta/api/limits.py`: client key context variable and middleware, `CallLimits` (per caller or per visitor, plus global ceilings), Content-Length digit fix.
- `src/tta/api/headers.py` (new): security headers middleware, `is_api_path`.
- `src/tta/api/service.py`: limits by kind of call, `request.received` written by `create_offer`, parser call marked as caller input.
- `src/tta/api/wiring.py`: `GatewayConfigurationError`, close on a failed start, `close_each`, `Parts.close`.
- `src/tta/api/app.py`: middleware order, `_McpMount` (exact `/mcp`), `_PagesMount` keeps `/v1`, examples built in the lifespan, close on a failed `create_app`.
- `src/tta/api/errors.py`: `reading_caller_input`, other `ValidationError` goes to 500, headers on the 500.
- `src/tta/api/hooks.py`: neither factory raises `HookError`; one factory logs a warning.
- `src/tta/api/identity.py`: checks on tokens from the environment.
- `src/tta/api/docs.py`, `src/tta/api/examples.py`: `BuiltExamples`, each scenario built on its own, description names what failed, limits text updated.
- `src/tta/api/routes.py`: `/healthz` with `status`/`reasons`, nullable `source`, no budget figure.
- `src/tta/offers/deps.py`: `look_up` through `PairedLookup`, refuses two sources.
- `src/tta/audit/trail.py`: `head()` held in memory, moved on by each append.
- Tests, new files: `tests/api/test_headers.py`, `test_live_mode.py`, `test_start_and_stop.py`, `test_surfaces.py`, `test_visitors.py`, `tests/offers/test_look_up.py`, `tests/audit/test_head.py`. Existing tests extended: `tests/api/conftest.py`, `test_fallback.py`, `test_flow.py`, `test_health.py`, `test_hooks.py`, `test_identity.py`, `test_limits.py`, `test_openapi_and_schemas.py`, `test_problems.py`, `test_service.py`.
- This run: `tests/api/test_visitors.py::test_one_visitor_cannot_lock_the_others_out_through_the_mcp_tools_either`. It was checked to fail when every visitor gets the same key.

**Existing tests changed because a finding changed the intended behaviour:**
- `test_fallback.py`, finding 2: the source-following clock and `gateway.source` following the last answer are gone.
- Finding 3: "a refused address runs on the capture" became "stops the start" (now in `test_live_mode.py`). The live-without-key test moved to `test_live_mode.py` and now also asserts `degraded`.
- `test_health.py`, finding 5: `status == "ok"` became `(status, reasons) == ("ok", [])`.
- `test_hooks.py`, finding 10: a parse that succeeds now writes no event. The surface tests moved unchanged to `test_surfaces.py`.
- `test_flow.py`, finding 10: the trail now starts with `request.received`.
- `test_limits.py`, finding 4: the shared 240-a-minute limit for demo tokens is removed (60 per visitor instead).
- `test_service.py`, finding 9: `build_examples` returns `BuiltExamples`; "stops at the first failed scenario" became "leaves it out and builds the others".

## Tests
```
COVERAGE_FILE=<scratchpad>/cov/.coverage .venv/bin/python -m pytest tests/api -q --cov=tta.api --cov-report=term-missing
TOTAL                         1337     13    222      7    99%
251 passed in 30.32s

.venv/bin/python -m pytest tests/offers/test_look_up.py tests/audit/test_head.py -q --cov=tta.offers.deps --cov=tta.audit.trail
src/tta/offers/deps.py      39      0      6      0   100%
16 passed in 1.38s
(tta.audit.trail over all of tests/audit: 100%, 144 passed in 0.25s)

.venv/bin/ruff check src/tta/api tests/api src/tta/offers/deps.py tests/offers/test_look_up.py src/tta/audit/trail.py tests/audit/test_head.py
All checks passed!
```
Importers, at the end:
- `tests/ui` 159 passed. One run while the T12 agent was editing `tests/ui` (07:56) had 1 failure; the next three runs passed.
- `tests/mcp` 54 passed.
- `tests/agent` 120 passed (after T10's commit 219ed22).
- `tests/offers` 194 passed.
- `tests/orders` 157 passed.
- `tests/audit` 144 passed.

## Assumptions
- In replay mode `/healthz` `source` is `replay` from the start: that gateway has one source. "null before the first look" applies to live mode, where two sources are possible.
- In live mode, an offer that looks nothing up (no candidate ids) carries the gateway's own source (`live`) and the live clock: no data came from either source.
- The single `price()`/`availability()` calls of the port each take one of the 6 live looks a minute.
- A look sent to the capture by the 6-a-minute cap is not a supplier failure. It does not pause live looks; `/healthz` says "answers come from the recorded capture while live mode is asked for" until a live look completes.
- Under that cap, an offer made live can come back `offer-stale` at the re-check (capture prices). The fresh offer is then `replay`.
- Inside an agent run, a `ValidationError` is ours (500). Only the parser call of `parse_request` counts as caller input.
- "Demo identity" means `settings.is_demo_environment` (dev and demo), where only the demo tokens are loaded.
- A document exported with no running app builds its examples when it is asked for (on that thread).
- Live mode with no supplier key starts, serves the capture and says `degraded` (question 3).
- `/healthz` keeps `env`, `mode` and `replay_capture` beside the true/false settings (question 2).
- The client-key rule is right only if the host's proxy reaches the app from a private address (question 1).

## Contract changes needed
None. `PairedLookup` and `AuditSink.head` were already in `tta/contracts/ports.py`.

## Known and left as it is (per the task)
- The database and the audit trail grow without a cap; the ceilings bound the growth per minute.
- An idempotent retry is rate-limited before its key is looked up.
- The fresh offer built after `offer-stale` is not counted.
- 400 and 413 are described in the document's text, not per route.

## Not done
- Per-visitor counting was not run on Modal: what peer address the app sees there is unknown (question 1). Live check: deploy, set `rate_limit` to 2, send three offers with `demo-agent-allergy-ward` from two phones on different networks. Each phone should get 201, 201, 429.
- Per-visitor counting was not tested through the real pages (T12 still in progress). They call the same service under the same root middleware. REST and MCP are tested.

## Questions written
3, in `AIMO/build/questions/FIX-8.md`, all for the team (written by the first agent; none added this run):
1. The peer address on Modal.
2. What `/healthz` keeps in `settings`.
3. Live mode with no key.
