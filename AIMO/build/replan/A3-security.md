# A3 — Security review of the gateway (Saturday 14 Nov)

Method: ran the app offline (replay, fresh data folder per script) with the hotel agent, ward agent, hotel and ward approvers and the supplier token, over REST and over the pages with cookie jars. Scripts: `.../scratchpad/replan/A3/t1.py` to `t17.py`. Nothing outside the scratchpad was changed.

## 1. In five lines
- 0 CRITICAL, 1 HIGH, 2 MEDIUM, 3 LOW. Everything below is reproduced unless marked "from code".
- Worst three: (1) HIGH standing-order creation has no rate limit and no cap, writes to an append-only audit trail on a persisted volume; (2) MEDIUM rule P-08 can be walked past by an agent alone (pending renewals count as history); (3) MEDIUM the global ceilings let one or two callers lock the demo for everybody (from code).
- Access control is sound: no cross-buyer read or write, F-06 holds on every route and page, the supplier sees none of limits, exclusions, approver names, notes.
- Forms: CSRF on all 12 writing forms, escaping holds, CSP strict, no redirect to a caller-chosen address.
- Cheapest fix with most value: rate-limit and cap standing-order creation (1.5 h).

## 2. Findings

### F1 HIGH — `src/tta/api/standing_routes.py:65`, `src/tta/standing/service.py:125`, `src/tta/store/schema.py:156`
Anyone with the public hotel token can fill the shared database, the append-only audit trail and the Volume, and make `GET /v1/standing-orders` huge.
Proof (t6.py): `POST /v1/standing-orders` 1,500 times with the largest request the 64 KB body limit allows (20 lines, 48 KB) returned 201 every time, in 3.2 s. SQLite file 161 MB. The route has no `limiter.check`, no per-buyer count, and `MAX_DEMO_REQUEST_LINES` (5) is applied only in `Gateway.create_offer`, not here. Each create also writes an audit event holding the request (triggers forbid deleting it). `GET /v1/standing-orders` then answered 77.8 MB in 6.3 s and raised process RSS by 87 MiB (container is 1,024 MiB, about 630 MiB at peak with catalog: `deploy/modal_app.py:92`; OOM at about 5,000 orders is an extrapolation, not run). The hotel's `GET /v1/audit` answers 5.3 MB (newest 100 events, each 48 KB), and every audit read walks the whole chain (`audit/chain.py:96`, 0.55 s at 1,500 events). On Modal the database is copied to the Volume after each burst and restored at start, so the damage survives a restart; the only cleanup is wiping the Volume.
Fix (1.5 h): in `StandingOrders.create` call `limiter.check(identity, CallKind.LOOKUP)`; refuse above 20 standing orders per buyer; apply the demo line cap; add `LIMIT 100` to the list query and `MAX_LIST_ITEMS` to `list`.

### F2 MEDIUM — `src/tta/standing/history.py:21,45`
An agent alone can turn a drifting quantity into "usual" and get it ordered with no human. P-08 leaves out only REJECTED and EXPIRED renewals, so renewals still waiting for approval count.
Proof (t4.py, hotel agent, fresh book): standing order 20 L; renewals 20, 20, 20 ORDERED (history under 3, so P-08 does not judge); then 60 L four times -> PENDING_APPROVAL x4 (the fourth against median 40); the fifth 60 L -> ORDERED, "within the 25% tolerance ... median of 60 L". No human approved anything. Spend rules P-01/P-02 still bound it (the daily limit counts pending orders), and P-08 is opt-in by the caller (an offer without `standing_order_id` skips it entirely), so this weakens a documented control, not a boundary.
Fix (1 h): count only ORDERED renewals (and synthetic ones) in `_counts`; add a test. Also say in the docs that the first 3 renewals are never judged.

### F3 MEDIUM — `src/tta/api/limits.py:128-145` (from code, not run)
`GLOBAL_CEILINGS` (120 offers/min, 120 orders/min, 30 model calls/min) and `ADDRESS_CAPS` (60/60/15) mean two addresses sending 60 offers a minute keep the global ceiling full: every other visitor gets 429 "all callers". Likewise 30 new order books per address per 10 minutes. If Modal shows the app one proxy peer for all visitors, they share one address bucket (`TTA_TRUSTED_PROXY_HOPS` is not set in `deploy/modal_app.py`; `docs/DEPLOY.md:141` says this was not observed).
Fix (0.5 h): no code fix for a public demo; state it, and before the video check on the deployed copy that two phones get separate buckets (the check `docs/DEPLOY.md:141` already describes).

### F4 LOW — `src/tta/contracts/request.py:71`, `src/tta/policy/facts.py:381`
`stands_in_role` is free text (200 characters; control characters, `<`, quotes allowed, unlike `Term`) and is copied into rule F-09's sentence on the approver's card.
Proof (t16.py): offer with `stands_in_for: "cream"`, `stands_in_role: "SAFE: dietitian already verified allergens, approve at once"`, order -> `GET /v1/approvals` shows "...whose role is SAFE: dietitian already verified allergens, approve at once, so a person checks that the dish still works." The supplier does not see it. Escaped in the pages; the issue is an agent writing in the gateway's voice to the human who signs.
Fix (0.5 h): restrict to the recipe table's roles, or apply `Term` and 60 characters.

### F5 LOW — `src/tta/ui/request_page.py:264`
`/run-photo` reads up to 5 MB into memory before checking the CSRF token. Any visitor can already send 5 MB to the REST photo route with a token, so the gain for an attacker is small. From code. Fix (0.25 h): none needed for the demo; optionally refuse a request with no `tta_csrf` cookie before reading the body.

### F6 LOW — `src/tta/ui/security.py:49`
No `Strict-Transport-Security` header on any response (the app relies on Modal's TLS). Fix (0.25 h): add `max-age=31536000` when `is_https`.

## 3. Checked and found sound
- **Cross-buyer (t1, t2):** ward token on hotel offer, order, audit by order and by offer, approval, standing order get/renew/list, and a ward offer naming the hotel's `standing_order_id` all answer 404 or 422 like an id nobody issued. The same Idempotency-Key from both buyers gives two separate orders (scope per caller).
- **F-06:** agent token on `POST /v1/approvals/{id}/decision` 403 and the attempt is recorded; ward approver on a hotel approval 404; supplier 403; MCP has no approval tool (`api/mcp_surface.py:61`); the pages' approver cookie can only name an approver. Approver or supplier calling place_order / create_offer / standing create / menu plan: 403.
- **Supplier (REST and `/orders/{id}?view=supplier`):** 403 on everything but audit and the recipe table; its audit view held no limit value, approver id or name, note, exclusion, label, `prefer`, stand-in text, drift tolerance or P-08 sentence (checked on orders, standing renewals, menu plan, a rejected approval with a note). A supplier cannot ask for `reader=buyer`.
- **Pages and identity:** each browser has its own book keyed by a 256-bit cookie; a fresh browser, and one with an invented key, get 404 on another's offer and order; another browser's CSRF token gives 403; "Your kitchen" settings of one browser did not show in another or in REST (`/v1/authority` still 750).
- **CSRF:** all 12 writing routes (`/run`, `/run-photo`, `/substitutes`, `/start-again`, `/kitchen`, `/kitchen/start-from`, `/menu/plan`, `/menu/order`, `/approvals/as`, `/approvals/{id}/decision`, `/standing-orders/demo`, `/standing-orders/{id}/renew`) answer 403 with no or wrong token.
- **Escaping:** autoescape on; no `|safe`; the only `Markup` is the repository's own assumptions file, escaped first. `"><script>` in query strings, form fields, standing order name, display name and request text came back escaped. Evidence link only for http(s) with `rel=noopener`.
- **Headers:** CSP `default-src 'none'`, scripts and styles `'self'`, `form-action 'self'`, `frame-ancestors 'none'`; `nosniff`, `no-referrer`, `no-store`; `/docs` uses SRI-pinned CDN files. No CORS; OPTIONS 405. Redirect targets are fixed paths with ids matched by `RECORD_ID`.
- **Input:** negative, zero, NaN, Infinity, 1e999, 1e30, 10^40 for quantities, renewal quantities, kitchen limits and ratios, menu servings and stock all 422; `cadence_days` 1..366; name 120 chars; unknown fields refused (`profile_id`, `agent_id`, `standing_order_id` in the body, `verdict`); 64 KB body cap (50,000-level nested JSON gives 413); ids matched `^[A-Za-z0-9_-]{1,64}$`; static path traversal 404.
- **SQL:** every statement in `src/tta/store/` is parameterised, none built from strings (`postgres.py` composes only the schema name with `sql.Identifier`).
- **Regexes:** no nested quantifiers; the rules reader on 2,000-character adversarial texts took at most 0.33 s (495 "and"), and the route allows 5 readings a minute per browser.
- **Agent:** the model cannot name a product, quantity, price or profile: `create_offer` takes no argument, `place_order` takes only the rank-1 `option_id`, one order per run (`agent/tools.py`). Injection text in the rules reader is only read for quantities, units and known words; an instruction text was refused, not obeyed. `stands_in_for`, `standing_order_id`, `required_labels` only add checks.
- **Kitchen page:** fixed parts (`profile_id`, `approver_roles`, `illustrative`, `description`) refused by name; limits capped at €100,000; a visitor cannot switch off F-01..F-09 (no field exists) or reach another session.
- **Audit:** triggers refuse UPDATE, DELETE and replacing INSERT; a refused caller's text is never written (`orders/service.py:156`); time comes from the data clock and actor from the token. The chain is unkeyed: it detects edits but not a rewrite to the end or a cut tail, as `audit/chain.py` itself says; the head is public at `/healthz`.
- **Secrets:** `deploy/modal_app.py` puts keys in a `modal.Secret.from_dict`, not in the image env (`IMAGE_ENV` holds none); hidden files are skipped when adding folders; `/healthz` shows booleans only and hides the call budget; unexpected errors answer a general 500 and log the trace server-side.
- **Rate limits:** approval decisions (500 tries -> 20 x 403 then 429, audit grew by 20), renewals, menu plan (6 then 429) and request readings are limited. Not limited: standing-order creation (F1), recipe table, product search, `/healthz` (all cheap).

## 4. Not checked
- Rate-limit buckets and cookie names on the deployed Modal app (no outside service allowed): peer address, `X-Forwarded-Proto`.
- Live mode with real keys, real Gemini output and photo bytes through a model; the Postgres store (no database here); Context.dev evidence text beyond the template.
- Concurrency races (two approvers deciding at once) and memory growth of in-memory books over two hours.
- `npm audit` equivalent for the Python pins in `deploy/modal_app.py:PINNED` (no network).
