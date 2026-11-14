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
