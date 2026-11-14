# FIX-10 — done

Every finding has a test that was written first and seen failing (on import, an assertion or a time-out) before its fix. No call to Gemini or to the Valio API was made. The app was run by hand in replay (`GEMINI_API_KEY=` empty, `TTA_DB_PATH` and `TTA_DATA_DIR` in the scratch folder, port 8791) and walked as two browsers. The log has no error and the app shut down cleanly. `/docs` and `/redoc` were rendered in a headless Chromium with a throw-away profile.

## Findings
1. **Fixed.** A private sandbox per browser session (`tta.api.sandbox`). Each sandbox has its own in-memory SQLite store, audit trail, offer service and order book. It shares the catalog, the supplier gateway (with its fall-back and budget), the policy, the limits, the parser and the runner. At most 300 are kept, the one used least recently is dropped first, and one idle for 2 hours is dropped. A dropped sandbox is closed. Each sandbox has a cookie key (`tta_book`, `__Host-` over HTTPS, HttpOnly, SameSite=Lax) that is never written into a page. A book is built on the first POST; GETs read an empty shared "blank" book, so crawlers open nothing. "Start again" is a POST with CSRF. Every page shows the agreed sentence. The order page shows the head of its own book's chain, server-side. REST and MCP keep the shared book. `docs/DEMO.md` is updated.
2. **Fixed.** Per-visitor windows per kind, keyed by address alone: lookups 20, orders and decisions 20, model 5 a minute. The global ceilings are unchanged (120/120/30). Live looks: 6 a minute overall, 2 per visitor; above that the capture answers, labelled replay. All values are named constants. Tests show that one address using both agent tokens and an approver token stops at the visitor window, under the ceiling, and that a second address is still served. The same is shown through the app with the reviewer's `ceiling.py` case: 20 accepted, not 120.
3. **Fixed.** New setting `TTA_TRUSTED_PROXY_HOPS` (default 0: no forwarded header is believed, the peer is the visitor). With N, the visitor is the N-th entry from the right, read over all header lines. Fewer entries than N, or an entry that is not an address, gives the peer. IPv6 is keyed on its /64, and IPv4-mapped IPv6 as IPv4. Test added in `tests/test_foundation.py`.
4. **Fixed.**
   - The pages order with `page-<sha256(run key)[:32]>`, one key per form submission.
   - A run key is released only on a typed refusal, which never hides an order (see next point). Any other fault keeps the key, and a resend shows "stopped on an unexpected fault… not run again".
   - `Gateway.run_agent` traces the offers and orders made in the run. A runner that raises after an order is answered with an `AgentRun` that holds the order and a report opening "The buyer agent stopped on an error (<class>) after the gateway placed order …". The error text is never shown.
   - Even if the run log forgets a form, the order book refuses a second order on the same key.
5. **Fixed.**
   - `Gateway.read_request(identity, text) -> Reading`: uses `parser.read` when the parser has it, else `parse_request` with source MODEL and the parser's `model_id`.
   - `POST /v1/requests/parse` keeps its body and adds `TTA-Read-By` and `TTA-Reading-Source`. A model id that is not a plain id is sent as `unknown`, so a line break cannot add a header.
   - The pages show the reading's sentence. Hand-checked with no key: `gemini-3.6-flash`, `recording`.
6. **Fixed.** The decision form carries `shown_to`. If it differs from the cookie's approver (or is missing), the page refuses with 409 "The approver was changed in another tab … Nothing was changed."
7. **Fixed.** Once the agent was asked, the parser is never asked again for the same submission. For free text, the agent's refusal is the answer; an example goes on with its typed request. One reading per submission.
8. **Fixed.** Substitutes are looked up once, at run time, and kept with the run. Re-check: 1 lookup for 1 run and 60 views, where the reviewer measured 61. A view without its run (or whose lookup was refused) shows a "Look up substitutes" button (POST, CSRF). Its result is kept for the views that follow.
9. **Fixed.** `GET` and `DELETE` on `/mcp` and `/mcp/` answer 405 `Allow: POST` (problem+json) before the SDK. The test asserts the answer comes within 2 s. The reviewer's `mcp_get.py`: 0 of 200 GETs still open, where all 200 had been.
10. **Fixed.**
    - In dev and demo a request has at most 5 lines (`MAX_DEMO_REQUEST_LINES`; above that `invalid-request`). Outside dev and demo the contract's 20 still apply (tested).
    - The `offer.created` context lists each excluded product once. For 3 identical lines the count goes from 189 to 63; the sentence and `excluded_by_reason` follow.
    - Measured per offer, offer row plus audit events: the worst case was **708,910 B** (20 lines × 2,000 characters: 434,645 + 274,265). It is now **187,236 B** (5 lines: 110,017 + 77,219). A 1-line offer is unchanged (21,624 + 20,475).
    - Script: `<scratch>/fix10/measure.py`.
11. **Fixed.**
    - `Gateway.order_for_offer(identity, offer_id) -> Order | None` reads through the store, takes the newest order, and reads it through the order book so that expiry applies. Another buyer's offer gives `not-found`.
    - The result page uses it.
    - A result whose run is no longer in memory says "How this was read is no longer known …".
12. **Fixed.**
    - "No model was asked" appears only when there is neither an agent nor a parser. Otherwise the page says "Read from the typed request of this example, not from a model's reading."
    - The agent card says "Run from answers written by hand, not by a model", "Run from a recording of the model's earlier answers", "Gemini did not answer, so this run was served from …" (recorded while a key is set) or "Run live by <model>".
    - A substitute whose quantity is not confirmed shows "? Can be ordered, needs approval" (seen on `468465`).
13. **Fixed.**
    - Pinned versions: Swagger UI 5.32.15 (published 4 Sep 2026) and ReDoc 2.5.4 (10 Sep 2026), from jsDelivr.
    - Integrity: SHA-384 subresource integrity, computed from the files jsDelivr served. Their SHA-256 matches jsDelivr's own index.
    - Policy: a Content-Security-Policy that allows only that CDN, with `frame-ancestors 'none'` and `base-uri 'none'`.
    - Docs page: its one inline script is allowed by its hash, and no validator or favicon is fetched from another host.
    - In headless Chromium both pages render. The only request the policy blocks is ReDoc's own "powered by" logo from `cdn.redoc.ly`.
14. **Fixed.** A document over 512 KiB says "docs/ASSUMPTIONS.md is larger than 512 KiB, the most this page shows, so it is not shown here."

## Built
- `src/tta/api/sandbox.py` (new): `Sandbox`, `Sandboxes`.
- `src/tta/api/agent_calls.py` (new): `read_with`, `header_value`, `traced`/`note_offer`/`note_order` (the run trace), `run_that_stopped`.
- `src/tta/api/docs_pages.py` (new): `/docs`, `/redoc`.
- `src/tta/api/service.py`: line cap, one exclusion per product in the trail, `read_request`, `order_for_offer`, a run never hides an order.
- `src/tta/api/limits.py`: `client_key_of(…, trusted_proxy_hops)`, `ClientKeyMiddleware(trusted_proxy_hops)`, `VISITOR_WINDOWS`, `CallLimits(visitor_windows=…)`, `call_limits`, `RateLimiter.full_window`.
- `src/tta/api/fallback.py`: 2 live looks per visitor.
- `src/tta/api/wiring.py`: `Parts.sandboxes`, the parts shared by every book, the line cap.
- `src/tta/api/app.py`: hop count to the middleware, own docs pages, sandboxes in the surface context.
- `src/tta/api/hooks.py`: `SurfaceContext.sandboxes`.
- `src/tta/api/routes.py`: reading headers on the parse route.
- `src/tta/api/mcp_surface.py`: `PostOnly`.
- `src/tta/api/docs.py`: limits text.
- `src/tta/config.py`: `tta_trusted_proxy_hops`, the one field allowed.
- `src/tta/ui/`:
  - `security.py`: `BookCookie`, `book_key`.
  - `site.py`: `book`, `own_book`, `runs`, the sentence.
  - `run.py`: reading, `order_key`, `Substitutes`, `look_up_substitutes`, `broken_run`, `RunLog` per book, `RunLogs`.
  - `request_page.py`: run once per form, substitutes at run time, `POST /substitutes`, `order_for_offer`.
  - `approvals_page.py`: `shown_to`.
  - `order_page.py`: the head of its own chain.
  - `routes.py`: `BookCookie`, `POST /start-again`, `Document`.
  - `view.py`: `run_label`, `can_be_ordered`.
  - Templates: `base`, `_result`, `_agent`, `_candidate`, `approvals`, `order`, `assumptions`.
  - `static/app.css`; `static/app.js`: the `/healthz` head script is removed.
- New test files:
  - `tests/api/`: `test_sandbox.py`, `test_readings_and_runs.py`, `test_growth.py`, `test_docs_pages.py`.
  - `tests/mcp/test_methods.py`.
  - `tests/ui/`: `test_own_book.py`, `test_resend.py`, `test_result_page.py`.
- `docs/DEMO.md`: own books and Start again, limits per visitor, new wording, the backup through REST only, MCP POST-only, pinned docs.
- `AIMO/build/questions/FIX-10.md`.

**Existing tests changed, because a finding changed the intended behaviour:**
- **Finding 3**
  - `tests/api/test_visitors.py`: client-key cases, the middleware test, and the proxy test now set hops=1 (plus a test that hops 0 ignores the header).
  - `tests/mcp/conftest.py`: a visitor is its peer address, not a header.
- **Finding 2**
  - `test_visitors.py`: windows per kind, and the ceiling refusal test.
  - `tests/api/test_limits.py`: another token from the same address is now refused.
  - `tests/api/test_fallback.py`: the six looks are spread over visitors.
- **Finding 1**
  - `tests/ui/conftest.py`: `book`, `own_book`, `orders`; `only_order` reads the browser's book; `decide` sends `shown_to` (also finding 6).
  - `test_approvals`, `test_order`, `test_edges` and `test_security` read or patch the browser's book. `test_security` also expects two cookies, and `test_order` no longer expects `data-audit-head`.
- **Finding 7**
  - `test_run.py`: free text that the agent cannot run is no longer sent to the parser.
  - `test_run_unit.py`: the same, and the stub has `read_request`.
- **Finding 4**: `test_edges.py`: a broken run no longer frees its form.
- **Finding 14**: `test_edges.py`: wording for a document that is too large.
- **Finding 12**: `test_run_unit.py`: wording.
- **On the orchestrator's note**: my fake parser's sentence in `test_result_page.py` is now plainly a fake. `test_with_the_agent_package.py` builds the real recording's sentence from the fixture's `recorded_at` through `tta.agent.labels.made_on`.

## Tests
`COVERAGE_FILE=<scratch>/fix10/.coverage`, `<scratch>` = `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad`
```
.venv/bin/python -m pytest <folder> -q -p no:cacheprovider
tests/agent: 294 passed in 6.94s
tests/ui: 192 passed in 16.78s
tests/api: 300 passed in 28.60s
tests/mcp: 59 passed in 11.55s
tests/e2e: 16 passed in 4.44s
tests/test_foundation.py tests/deploy: 60 passed in 5.39s

.venv/bin/python -m pytest tests/api tests/mcp -q -p no:cacheprovider --cov=tta.api --cov-report=term-missing
TOTAL                         1621      6    266      7    99%
359 passed in 60.99s (0:01:00)
.venv/bin/python -m pytest tests/ui -q -p no:cacheprovider --cov=tta.ui
TOTAL                           1074      0    202      3    99%

.venv/bin/ruff check src/tta/api src/tta/ui tests/api tests/ui tests/mcp tests/e2e src/tta/config.py tests/test_foundation.py
All checks passed!
```
The reviewers' reproductions were re-run. `ceiling.py`, `xff_repro.py`, `limits_repro.py`, `rev/limits.py`, `growth.py` and `spend.py` ran as they are. `rev/lost.py`, `rev/getpage.py` and `flood.py` were adapted to read the browser's book: `<scratch>/fix10/recheck.py`.
- `rev/lost.py`: 1 order after two sends; REST answers 200 with the order.
- `rev/getpage.py`: 1 lookup for 60 views.
- `flood.py`: 0 spam cards on a judge's approvals page.
- `rev/limits.py`: a written `X-Forwarded-For` gives the peer.

## Assumptions
- **The browser session's book.** A browser session is a session cookie of its own (`tta_book`), separate from the CSRF token, so that the key never appears in HTML.
- **When a book is built.** A book is built on the first POST of a browser (run, decision, lookup). GETs read one shared, empty "blank" book that the pages never write to: reads of the order book write nothing (checked in `tta.orders`).
- **Closing a dropped book.** A dropped book is closed at once. A request of the same visitor still running in it at that moment fails.
- **The run log.** It is per book (50 runs, `RUNS_PER_VISITOR`), held in a `WeakKeyDictionary`, so a dropped book takes its runs with it.
- **Free text.** Once the agent is asked, a free text it cannot run is answered with the agent's refusal, never by the parser. This replaces T12's "an unreachable model hands over to the parser".
- **The address alone.** The per-visitor windows are keyed by address alone in dev and demo. A token from the environment is still counted by identity (60 a minute) outside dev and demo.
- **Shared addresses.** "Unknown" clients (no IP peer) share one window, as before, also for the 2 live looks a minute.
- **The `rate_limit` argument.** `build_parts(rate_limit=…)`, used by tests, replaces the window of one caller for every kind of call.
- **Counting refused requests.** A request refused for its lines (or its product ids) is counted in the lookup window, because the limiter runs first, as before.
- **The hop setting.** `TTA_TRUSTED_PROXY_HOPS` is capped at 10. With hops set, the N-th entry from the right is believed whatever the peer's address (no private-peer test).
- **Run label.** A "fall-back run" on the agent card is a run with `recorded` true while a Gemini key is set. `AgentRun` has no field that says so.
- **A run that broke.** The `AgentRun` that the gateway builds for a runner that broke after its order has `model` = the runner's `model_id` and `recorded` = the runner's `recorded` attribute (false when it has none), and no steps.
- **Cosmetic.** ReDoc's "powered by" logo is left blocked by the policy.

## Contract changes needed
- `GatewayService`: `read_request(identity, text) -> Reading` and `order_for_offer(identity, offer_id) -> Order | None`. `RequestParser`: `read(text, identity) -> Reading`. The orchestrator adds these, as planned. The page calls `read_request` and `order_for_offer` on its `Gateway`.
- `AgentRun`: a field for "served from a recording because the live model did not answer". The page infers it from `recorded` and the key.
- `tta.api.hooks.SurfaceContext.sandboxes` is new. It is in my package; the T11/T12 notes about the context should name it.

## Not done
- **No click-through in a real browser.** The pages were walked over HTTP (texts saved in `<scratch>/fix10/run/pages/`). `/docs` and `/redoc` were checked headless only.
- **Opening many books.** Opening books is not limited per address beyond what limits the POSTs. An address can push the 300 least recently used books out by sending forms with fresh cookies. A per-address cap on new books would close this.
- **Files I do not own.**
  - `docs/DEPLOY.md`: per-visitor limit and `X-Forwarded-For` wording; on Modal nothing needs setting, hops stay 0.
  - `docs/ASSUMPTIONS.md`: the sandbox, the limits by kind and the 5-line cap.
- **The venue NAT question.** One public address shares the 5 agent runs a minute (question 1). Live check, which spends no call: from two phones on different networks, open the deployed `/`, run scenario 2 on each, then check that each sees only its own approvals.

## Questions written
1, for the team: `AIMO/build/questions/FIX-10.md` (the room behind one NAT shares the per-visitor windows).
