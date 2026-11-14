# Architecture

Trusted Trade Agents is one Python process. It sits between a buyer's purchasing agent and Valio Aimo's price and availability API. It answers lookups, builds offers at fixed prices, places orders within the agent's authority or sends them to a human, and writes an audit trail that the buyer and Valio Aimo each read in their own view.

The build contract is [`AIMO/SPEC.md`](../AIMO/SPEC.md). This page describes what is built.

## The picture

```
  buyer's agent                      human approver                 Valio Aimo
  (Gemini loop, or any agent)        (purchasing, finance,          (supplier reader)
        │                             dietitian)                          │
        │ REST /v1/*  ·  MCP /mcp/         │ pages /approvals            │ GET /v1/audit?reader=supplier
        │ (bearer token)                   │ or POST /v1/approvals/…     │ (bearer token)
        ▼                                  ▼                             ▼
  ┌───────────────────────────────────────────────────────────────────────────────┐
  │ api/   FastAPI app: identity, rate limits, body limit, RFC 9457 errors,        │
  │        generated OpenAPI 3.1, /healthz.  Surfaces: routes.py (REST),           │
  │        mcp_surface.py (MCP), ui/ (pages, only when TTA_ENV is dev or demo)     │
  │                                                                               │
  │        service.Gateway  ── the one service object behind every surface ──      │
  └──────┬──────────────┬───────────────┬──────────────────┬──────────────────────┘
         │              │               │                  │
         ▼              ▼               ▼                  ▼
     offers/         orders/         audit/             agent/
     options,        order-time      CloudEvents,       Gemini: read the text,
     ranking,        check,          hash chain,        then a function-calling
     combining,      approvals,      two reader         loop over the same
     substitutes,    idempotency,    views              service (or recorded
     re-check        day's spend        │               answers)
      │  │  │  │         │              ▼
      │  │  │  └─────────┴──────► policy/   rules.yaml (fixed rules F-01…F-08)
      │  │  │                              + profiles/*.yaml (buyer profiles)
      │  │  │                              → AUTO · APPROVAL · BLOCK
      │  │  └──► availability/  six states, a status per claim
      │  └─────► allergens/     GS1 codes, exclusion rule, substitution rule
      ▼
   catalog/  product file, search, product types, pack size, lot step
   valio/    live client · recorder · replay · call budget · clock ──► Valio mock API
   store/    SQLite: offers, orders, approvals, idempotency keys, append-only audit events
```

`contracts/` holds the shared Pydantic models and the ports. Every package depends on ports, not on another package's classes. `api/wiring.py` is the one place that builds the real parts and connects them.

## One request, step by step

1. **Request.** The agent sends a typed request (`POST /v1/offers`), or the demo sends pasted text that the Gemini parser turns into one (`POST /v1/requests/parse`, `POST /v1/agent/run`). The buyer profile comes from the bearer token, never from the request.
2. **Candidates.** `catalog/` finds products by product type, name terms, claims, explicit ids and pack rule. Pack size and lot step come from the product file and the live price.
3. **Lookup.** `valio/` asks the mock for price and availability of the narrowed set: one price call and one availability call. Both answers come from one source, live or the recorded capture, never one of each.
4. **Classify.** `availability/` gives each product one of six states and a status per claim: price, quantity, delivery date, allergens, origin. `allergens/` applies the buyer's exclusions.
5. **Offer.** `offers/` builds at most three options: best confirmed, unconfirmed alternative, substitute. Every option carries its totals, its constraint checks and its policy verdict. Every product that drops out is listed with a reason.
6. **Policy.** `policy/` evaluates each option. The most severe verdict of the rules that fire wins.
7. **Order.** `orders/` re-checks price and availability with a fresh call, runs the policy again at order time, and then places the order (`AUTO`), opens an approval (`APPROVAL`) or refuses (`BLOCK`).
8. **Approval.** A human with the named role approves or rejects, on the pages or over REST. The order-time check runs again before the order is placed. An agent token on an approval route is refused.
9. **Audit.** Every step writes one CloudEvents event with one readable sentence, chained by SHA-256 hashes. The buyer and the supplier each read their own view.

## Packages

| Package | What it does | Implements | Uses |
|---|---|---|---|
| `contracts/` | Shared Pydantic models, typed errors, ports, JSON Schema export | — | — |
| `config.py` | Settings from the environment and `.env`; secrets as `SecretStr` | — | — |
| `valio/` | HTTPS client for the mock, recorder, replay of a capture, call budget, live and pinned clocks | `ValioGateway`, `Clock` | — |
| `catalog/` | Loads the product file and the two CSV files; search; product-type table (`product_types.yaml`); pack size; portion packs; lot rounding | `Catalog` | — |
| `allergens/` | GS1 code table and families; buyer exclusion rule; substitution rule | functions | — |
| `availability/` | The six states; the status of each claim; sentences | functions | — |
| `policy/` | Rules file, buyer profiles, deterministic engine, policy hash | `PolicyEngine` | — |
| `offers/` | Candidates → options; ranking; combining; substitutes; re-check before an order | `OfferBuilder`, `OfferRevalidator` | `Catalog`, `ValioGateway`, `PolicyEngine`, `Clock` |
| `store/` | SQLite repository; audit table that refuses update and delete | `Store` | — |
| `audit/` | Events, hash chain, sentences from templates, buyer and supplier views | `AuditSink` | `Store` |
| `orders/` | Order-time check, approvals, expiry, idempotency, the day's spend | `OrderService` | `OfferRevalidator`, `PolicyEngine`, `Store`, `AuditSink`, `Clock` |
| `api/` | FastAPI app, REST routes, identity, limits, problem details, OpenAPI, MCP surface, fall-back from live to replay | `GatewayService` (`service.Gateway`) | all of the above |
| `agent/` | Gemini: request parser and buyer-agent loop; recorded answers when there is no key | `RequestParser`, `AgentRunner` | `GatewayService` |
| `ui/` | Server-rendered pages: request, approvals, order and audit trail, assumptions | — | `GatewayService` |

## Ports

Defined in `src/tta/contracts/ports.py`. Every port is synchronous.

| Port | Promise | Implemented by |
|---|---|---|
| `Clock` | Timezone-aware "now". Replay: pinned to the capture's `timeNow`. Live: the server's time carried forward, never backwards | `valio.clock.PinnedClock`, `valio.clock.LiveClock` |
| `ValioGateway` | Price and availability; `fresh=True` skips the cache for the order-time re-check | `valio.client.ValioClient`, `valio.replay.ReplayGateway`, `api.fallback.FallbackGateway` |
| `PairedLookup` | Price and availability for the same ids from the same source | `api.fallback.FallbackGateway` |
| `Catalog` | Products, search, product types, listed substitutes, category neighbours, pack size, portion packs, lot rounding | `catalog.catalog.ProductCatalog` |
| `PolicyEngine` | Profiles, verdicts, the authority text, the policy hash. No model takes part | `policy.engine.RulePolicyEngine` |
| `OfferBuilder` | An offer for a typed request; "nothing fits" is an offer with no options and the reasons | `offers.service.OfferService` |
| `OfferRevalidator` | A fresh look at an option's lines and what changed | `offers.service.OfferService` |
| `Store` | Save and read offers, orders, approvals, idempotency keys; append audit events; `atomic()` block | `store.sqlite_store.SqliteStore` |
| `AuditSink` | Record one event per step; reader views; chain check; head (count and last hash) | `audit.trail.AuditTrail` |
| `OrderService` | Place, decide, read orders and approvals; the day's committed spend | `orders.service.OrderBookService` |
| `RequestParser` | Free text → typed request; names what is missing, never guesses | `agent.parser.ModelRequestParser` |
| `GatewayService` | Every function a surface offers, each taking the caller's identity first | `api.service.Gateway` |
| `AgentRunner` | A function-calling loop over `GatewayService`, at most 8 steps | `agent.runner.ModelAgentRunner` |

## Where each part of the brief lives

| Brief ([`AIMO/CHALLENGE.md`](../AIMO/CHALLENGE.md)) | Interface | Code |
|---|---|---|
| Core 1 — "a structured way for an external agent to search for and retrieve what's available and at what price" | `POST /v1/products/search`, `GET /v1/products/{id}`, `POST /v1/offers`; MCP `search_products`, `get_product`, `get_offer` | `catalog/search.py`, `offers/builder.py`, `valio/client.py`, `availability/states.py`, `availability/claims.py` |
| Core 2 — "a defined interaction for moving from inquiry to commitment, based on fixed prices" | `POST /v1/offers` → `POST /v1/orders` with `Idempotency-Key`; `GET /v1/orders/{id}`; MCP `place_order`, `get_order` | `offers/revalidation.py`, `orders/checking.py`, `orders/service.py` |
| Core 3 — "what the agent may decide on its own, and what must go to a human for sign-off" | `GET /v1/authority`; `GET /v1/approvals`; `POST /v1/approvals/{id}/decision`; page `/approvals`; MCP `get_authority` (no MCP tool approves) | `policy/rules.yaml`, `policy/profiles/*.yaml`, `policy/engine.py`, `orders/access.py` |
| Trust protocol — what an agent can trust about stock, price and origin | A status per claim on every offer line: `CONFIRMED`, `UNKNOWN` or `RULED_OUT` | `availability/claims.py` |
| Response logic — partial availability, good-better-best substitutes | Options of an offer; `POST /v1/products/{id}/substitutes`; MCP `find_substitutes` | `offers/combining.py`, `offers/options.py`, `offers/substitutes.py`, `allergens/substitution.py` |
| Audit trail — "for both buyer and Valio Aimo" | `GET /v1/audit?reader=buyer\|supplier`; page `/orders/{id}`; MCP `get_audit` | `audit/trail.py`, `audit/chain.py`, `audit/readers.py`, `store/schema.py` |
| Optional — delivery time and sustainability comparison | **Not built.** Delivery reliability and carbon values are loaded onto each product (`GET /v1/products/{id}`) and used nowhere else | `catalog/loader.py` |
| Open standards (15%) | `GET /openapi.json`, `GET /v1/schemas`, MCP at `/mcp/`; see [STANDARDS.md](STANDARDS.md) | `api/docs.py`, `contracts/schemas.py`, `api/mcp_surface.py` |

## Modes and the clock

- `TTA_MODE=replay` (the default): answers come from `fixtures/valio/<capture>/`, and the clock is pinned to that capture's `timeNow`. The default capture is `2026-11-14-demo` (Saturday 14 Nov 2026, 02:52 server time, 769 products of categories `104xx` and `18720`).
- `TTA_MODE=live`: calls the mock through the client: at least one second between calls, a 60-second cache, a call budget kept in `var/valio_call_budget.json`. When the mock cannot be reached, or fewer than 10 calls are left, the capture answers and the offer says `replay`.
- `TTA_ENV` decides who can call. `dev` and `demo` load the public demo tokens of `src/tta/api/demo_tokens.yaml` and mount the pages. Unset means `prod`: no demo token, no pages, and the app does not start without `TTA_TOKENS`.

## Known limits of the design

From the hand-backs in `AIMO/build/handback/`:
- **One process.** The order book's lock, the rate limiter, the agent-run log of the pages and the cached audit head live in memory. Two gateway processes on one database are not protected against each other.
- **SQLite.** The audit table refuses update and delete through triggers, but whoever can write the database file can drop them. The chain shows a changed, removed or inserted event; it does not show the last events cut off unless another party holds the head (`/healthz` publishes it; nothing compares it yet).
- **No login on the pages.** They act as a demo identity chosen on the page, so they exist only in `dev` and `demo`.
