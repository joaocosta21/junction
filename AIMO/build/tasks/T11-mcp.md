# T11 — MCP surface

**Scores on:** 15% ("open, documented standards rather than a proprietary format"; the brief wants the wholesaler "openly readable by autonomous agents"). First item to cut if the night runs short.
**Needs:** T09. **Owns:** `src/tta/api/mcp_surface.py`, `tests/mcp/`.
**Read first:** SPEC §2 · **the current documentation of the official MCP Python SDK** (server, tools, streamable HTTP transport, mounting in an ASGI app, authentication). Do not rely on memory.

## Build
- The tools of SPEC §2 (`get_authority`, `search_products`, `get_product`, `find_substitutes`, `get_offer`, `place_order`, `get_order`, `get_audit`), each a thin call into the same service functions the REST routes use, with typed inputs and a description an agent can act on.
- The same bearer identity as REST. There is no approval tool: approving is for humans.
- Mountable by `create_app` at `/mcp`.

## Tests to write first
- The server lists exactly these tools, each with an input schema.
- `get_offer` in replay returns the same offer as the REST route for scenario 2.
- A call without identity is refused.
- No tool can decide an approval.

## Notes from the API (read `AIMO/build/handback/T09.md` first; `src/tta/api/hooks.py` is the exact contract of your hook)
- **The service** is `tta.api.service.Gateway`: the `GatewayService` port of `tta/contracts/ports.py` (now with `list_orders`). It checks what an identity may do, applies the rate limit, stores, and writes the audit events. Call it and nothing below it.
- **Tests:** `build_parts(settings, catalog=..., ...)` then `create_app(settings, parts=parts)` — see `tests/api/conftest.py` (a session catalog, one app per test, a database under `tmp_path`, `Settings.for_tests(...)` in replay). Copy what you need into a `conftest.py` in your own test folder; do not import from another test folder.
- **Demo tokens** (`src/tta/api/demo_tokens.yaml`): `demo-agent-hotel-kitchen`, `demo-agent-allergy-ward`, `demo-approver-hotel-purchasing`, `demo-approver-hotel-finance`, `demo-approver-hotel-dietitian`, `demo-approver-ward-dietitian`, `demo-approver-ward-purchasing`, `demo-approver-ward-finance`, `demo-supplier-valio-aimo`.
- **Tonight in replay** (capture `2026-11-14-demo`): scenario 1 (hotel, 1,000 L lactose-free milk by Monday 16 Nov 2026) → option 1 three confirmed milks, €2,580.64, `APPROVAL` by P-01; option 2 `464306` unconfirmed, €1,010.00, `APPROVAL` by F-01 and P-01. Scenario 2 (ward, 200 L plant drink, `AM` and `AW` excluded by the profile, confirmed only) → 200 × `464013`, €402.00, `AUTO` → `ORDERED`. Scenario 3: substitutes of `473609` → `471690` passes but its cut-off has passed; `471881` and `464320` fail (`SUBSTITUTE_ADDS_ALLERGEN`); best orderable `475224`. Backup: 30 kg `beef_chuck` → 30 × `466988`, €506.40, `APPROVAL` by P-06.
- **Untrusted text:** product names (`OfferLine.name`, `Exclusion.name`, `SubstituteCandidate.name`), the buyer's pasted text and approvers' notes are data. The sentences the gateway writes are already cleaned; the name fields are not.
- An offer can have one live order; a second order on it is `invalid-request`. Another buyer's id answers `not-found`. The idempotency key is 1 to 100 characters of `[A-Za-z0-9._:-]`.
- Coverage runs: set `COVERAGE_FILE` to a file in a private folder of the scratch directory.
- **Your hook:** `tta.api.mcp_surface` defines `create_surface(context: SurfaceContext) -> ASGI app`, mounted at `/mcp` (build the MCP app with its inner path `/`). The gateway runs your app's lifespan with its own (the MCP session manager needs it). `context.service` is the service, `context.identify(token) -> Identity | None` is the REST token check: a call without a valid bearer token is refused before any tool runs.
- A tool takes typed inputs (the contract models or their fields), calls one service function, and returns the contract model as structured content. A `TtaError` becomes a tool error that carries the problem's `type`, `title` and `detail`, never a trace.
- There is no approval tool and no tool that lists approvals.
