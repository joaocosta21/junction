# T09 — API: routes, identity, errors, schemas

**Scores on:** 30% (one continuous flow) · 15% (generated OpenAPI, documented open formats) · Core 1, 2 and 3.
**Needs:** T07, T08. **Owns:** `src/tta/api/` except `mcp_surface.py` · `tests/api/`.
**Read first:** SPEC §2, §8, §11 · the contracts · the hand-backs of T07 and T08.

## Build
- **`create_app(settings)`** wiring the real implementations behind the ports; replay or live from `TTA_MODE`.
- **Routes** of SPEC §2, thin: validate, call the service, return the contract model. No business logic in a route.
- **Identity:** a dependency that maps the bearer token to an agent (bound to one profile), an approver (roles) or the supplier reader. Demo tokens in `src/tta/api/demo_tokens.yaml`, loaded only when `TTA_ENV` is `dev` or `demo`; in any other environment tokens come from the environment and the app refuses to start without them. Constant-time comparison.
- **Errors:** every typed error → RFC 9457 `application/problem+json` with the `type` of SPEC §2. No stack trace and no secret in a response.
- **`GET /v1/schemas`:** JSON Schema of every contract model.
- **OpenAPI:** title, description, tags per core requirement, the bearer security scheme, one request and response example per route taken from the scenarios.
- **Limits:** request body size, at most 1,000 product ids per request, a simple per-token rate limit on routes that reach the live API.
- **Hooks, optional imports:** mount `tta.api.mcp_surface` at `/mcp` and `tta.ui.routes` at `/` when those modules exist. `POST /v1/requests/parse` and `POST /v1/agent/run` call the `RequestParser` and `AgentRunner` ports; until T10 lands they answer `supplier-unavailable` with a clear detail.
- `GET /healthz`.

## Tests to write first (`TestClient`, replay)
- The whole flow by HTTP: authority → offer → order → approval → order → audit, for scenario 1; and scenario 2 ending `ORDERED` with no approval.
- No token → 401; an agent token on an approval route → 403 `not-authorised`; an approver token cannot place an order.
- An agent cannot name another profile: no route accepts a profile id from an agent.
- Each problem type is produced and has the right status code.
- `POST /v1/orders` without `Idempotency-Key` → `invalid-request`; the same key twice → the same order.
- `/openapi.json` lists every route of SPEC §2 and the security scheme; `/v1/schemas` returns every model.
- The supplier token sees only the supplier view of the audit trail.

## Notes from waves 1 and 2 (read every hand-back in `AIMO/build/handback/` before writing anything)
- **Wiring** (all synchronous):
  - `catalog = ProductCatalog.from_settings(settings)` (`tta.catalog.catalog`; about 1.3 s, build once)
  - replay: `gateway = ReplayGateway(settings.replay_capture_dir)`; live: `gateway = ValioClient(settings)`; the data clock is `gateway.clock`
  - `engine = RulePolicyEngine.from_files()` · `store = open_store(settings)`
  - `trail = AuditTrail(store, audit_clock, policy=engine)` — **one per process**, and `audit_clock` is the real time (a small clock that answers UTC now), never the pinned replay clock (decision T06-2)
  - `offers = OfferService(OfferDeps(catalog=catalog, gateway=gateway, policy=engine, clock=clock, day_spend=lambda profile_id: day_committed_net_eur(store, clock, profile_id)))`
  - `orders = OrderBookService(store=store, policy=engine, revalidator=offers, audit=trail, clock=clock)`
- **One service object implements the `GatewayService` port** (`tta/contracts/ports.py`), in `src/tta/api/service.py`. REST routes, the MCP tools (T11), the pages (T12) and the buyer agent (T10) all call it and nothing else. It checks what the identity may do, then delegates.
- **Offers:** `create_offer` builds the offer, stores it, and writes the audit events `request.parsed`, `lookup.performed`, `offer.created` and `policy.evaluated`, each with the offer id (the trail of an order is found through its offer). `request.received` is written by `parse_request` and `run_agent` with the pasted text. The offer builder itself stores nothing and writes no event.
- **Stale or expired at order time:** `orders.place_order` raises `OfferStale` or `OfferExpired`. Catch it, build a fresh offer from the stored offer's request, store it, and add `fresh_offer_id` to the problem's extension members before answering 409.
- **Live with a fall-back to replay.** In live mode wrap the live client and a replay gateway behind the `ValioGateway` port: when the live client raises `SupplierUnavailable`, or fewer than 10 calls remain (`ValioClient.calls_remaining`), answer from replay. Every answer already states its `source`, and an offer carries it. The data clock must follow the source of the last answer (pinned for replay, live otherwise). `/healthz` says which source is in use.
- **Identity.** Demo tokens (only when `settings.is_demo_environment`): two agents (`agent:hotel-kitchen`, `agent:allergy-ward`), six approvers whose ids are listed in the profile files (`human:hotel-purchasing`, `human:hotel-finance`, `human:hotel-dietitian`, `human:ward-dietitian`, `human:ward-purchasing`, `human:ward-finance`), and the supplier reader `supplier:valio-aimo`. Outside dev and demo: `settings.tta_tokens` holds a JSON object mapping each token to an identity; without it the app refuses to start. The demo tokens are public by design: say so in the file and in `/docs`.
- **Audit route:** a supplier token gets the supplier view only. An agent or approver gets the buyer view of its own buyer's orders and offers (check the order's or offer's `profile_id` against the identity before asking the trail), and may ask for `reader=supplier` to see what the supplier sees about its own order.
- Add `GET /v1/orders` (the caller's own buyer's orders, newest first) for the pages; `Store.list_orders` exists.
- **`/healthz`:** environment, mode, the source in use, the head of the audit chain (`trail.head()`: event count and last hash), and `settings.describe()` — never a secret, never a path.
- **Problem details:** `TtaError.to_problem()` gives the body. `AuditChainConflict` is a `SupplierUnavailable` (503, safe to retry). A Pydantic validation error is `invalid-request` and lists the fields without echoing the values. Any other exception is a 500 problem with a generic detail; the trace goes to the log only.
- **Limits, from the security review:** the request contract already bounds quantities and list sizes. Add: a body size limit, a per-token rate limit on the routes that reach the supplier (offers, substitutes, orders, agent run), and no route that reaches the supplier without a token.
- Tests use `Settings.for_tests(...)` in replay, a database under `tmp_path`, and `create_app(settings)`; nothing reads `.env`.
