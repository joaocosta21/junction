# Architecture

Trusted Trade Agents is one Python process. It sits between a buyer's purchasing agent and Valio Aimo's price and availability API. It answers lookups, builds offers at fixed prices, prepares orders that a person confirms (or, only where a buyer has switched ordering alone on and every statement is confirmed, places them), and writes an audit trail that the buyer and Valio Aimo each read in their own view. It is an interface for agents, not a chat.

The build contract is [`AIMO/SPEC.md`](../AIMO/SPEC.md). This page describes what is built, checked against the committed code on Sat 14 Nov 2026 (evening) and again on Sun 15 Nov 2026 at commit `94b21a5`, offline in replay. **A model may read a sentence; it never decides.** When a model is configured it reads free text first and the gateway checks its reading against the text; when none is configured or none answers, a labelled recording or the fixed rules read it (`GET /healthz` → `agent_reader` says which on a given gateway). Every price, quantity, allergen status and verdict is deterministic code. Figures come from the recordings used in replay (1,163 products: 769 recorded Sat 14 Nov 2026 at 02:52 Helsinki time, which gives the clock, and 394 baking products recorded the same day at 21:12) or, where said, from the whole catalog (17,546 products).

## The picture

```
  buyer's agent                      a person at the buyer          Valio Aimo
  (any agent: REST or MCP)           (the person who orders;        (supplier reader)
        │                             a dietitian at ward and school)     │
        │ REST /v1/*  ·  MCP /mcp/         │ pages /shop, /approvals     │ GET /v1/audit?reader=supplier
        │ (bearer token)                   │ or POST /v1/approvals/…     │ (bearer token; nothing else)
        ▼                                  ▼                             ▼
  ┌───────────────────────────────────────────────────────────────────────────────┐
  │ api/   FastAPI app: identity, rate limits, body limit, RFC 9457 errors,        │
  │        generated OpenAPI 3.1, /healthz, /.well-known/api-catalog, /llms.txt,   │
  │        /.well-known/jwks.json. Surfaces: routes.py (REST), mcp_surface.py      │
  │        (13 MCP tools, none approves), ui/ (pages, only in dev and demo)        │
  │        signing.py: a signature on every offer and order record answered        │
  │                                                                               │
  │        service.Gateway  ── the one service object behind every surface ──      │
  └──────┬──────────────┬───────────────┬──────────────────┬──────────────────────┘
         │              │               │                  │
         ▼              ▼               ▼                  ▼
     offers/         orders/         audit/             agent/
     options,        order-time      CloudEvents in     free text → typed request:
     ranking,        check,          store, hash chain, a model if one is set, its
     combining,      approvals,      the buyer's and    reading checked against the
     substitutes,    idempotency,    Valio Aimo's       text; else a recording, else
     formula,        day's spend     views              fixed rules, else a question
     re-check            │              ▼
      │  │  │  │         │
      │  │  │  └─────────┴──────► policy/   rules.yaml (fixed rules F-01…F-12, profile rules P-01…P-09)
      │  │  │                              + human_approval.py (F-10: a person confirms every order
      │  │  │                                unless the buyer switched ordering alone on)
      │  │  │                              + profiles/*.yaml (four buyer profiles)
      │  │  │                              → AUTO · APPROVAL · BLOCK
      │  │  └──► availability/  six states, a status per statement
      │  └─────► allergens/     GS1 codes, exclusion rule, ingredient list, substitution rule
      ▼
   catalog/     product file, search, product types, pack size, lot step, flavour and use from names
   valio/       live client · recorder · replay · call budget · clock ──► Valio mock API, or its recording
   store/       SQLite, or PostgreSQL when DATABASE_URL is set (schema TTA_DB_SCHEMA): offers, orders,
                approvals, idempotency keys, standing orders, append-only audit events
   customers/   the four demo customers (synthetic): people, usual products, past orders
   suggestions/ suggestions from a customer's history or the catalog, each checked like any product
   evidence/    what a manufacturer's page says about an allergen Valio's data leaves open
                (recorded pages; a lookup only with a Context.dev key) ──► approval card
```

`contracts/` holds the shared Pydantic models and the ports. Every package depends on ports, not on another package's classes. `api/wiring.py` is the one place that builds the real parts and connects them.

**Two kinds of order book.** REST and MCP share one order book and audit trail in the database. On the pages, each browser gets its own book (`api/sandbox.py`): an in-memory store with its own audit trail and order service, sharing the catalog, the supplier gateway, the policy, the limits and the agent. At most 1,000 are kept; one idle for 2 hours is dropped. The pages take no credential: a page acts as the customer's person it shows.

## One request, step by step

1. **Request.** The agent sends a typed request (`POST /v1/offers`). A person's sentence goes through `POST /v1/requests/parse`: a model when one is configured, its reading checked against the text and refused when it does not match; when none answers or none is configured, a recorded reading of that exact sentence for that buyer if there is one, else the fixed-rules reader; a text the rules cannot read is never guessed: with no model configured it is answered `422` with a question, and when a configured model did not answer, `503` with the rules' own reason in it (after a failure the model is not asked again for 120 seconds). Every reading says who read it. The buyer profile comes from the bearer token, never from the request.
2. **Candidates.** `catalog/` finds products by product type, name terms, claims, explicit ids and pack rule. Pack size and lot step come from the product file and the live price.
3. **Lookup.** `valio/` asks for price and availability of the narrowed set: one price call and one availability call, and a second pair when substitutes have to be looked up (the 1,000 L example makes two of each). Both answers come from one source, the mock (live mode) or the recording (replay, the default), never one of each.
4. **Classify.** `availability/` gives each product one of six states and a status per claim: price, quantity, delivery date, allergens, origin. `allergens/` applies the buyer's exclusions.
5. **Offer.** `offers/` builds at most three options: best confirmed, a labelled alternative ("Alternative: quantity not confirmed", "Alternative: allergen not ruled out", "Alternative: a substitute that does not keep the formula"), a substitute; under a preference other than price, a fourth, the cheapest confirmed, when it differs. When confirmed stock of the product asked for covers only part of the quantity, one option fills all of it from confirmed stock with a named substitute ("Alternative: confirmed stock, completed with a substitute"). When nothing can arrive by the date asked, the options are for the earliest date in Valio's data and say how many days later that is. Both go to a person. With an allergen excluded, only products whose data rules it out are in the first option. Every option carries its totals ("about € …" when a product is sold by weight: an estimate), its constraint checks and its policy verdict. Every product that drops out is listed with a reason.
6. **Policy.** `policy/` evaluates each option. The most severe verdict of the rules that fire wins.
7. **Order.** `orders/` re-checks price and availability with a fresh lookup, runs the policy again at order time, and then opens an approval (`APPROVAL`: the order is prepared and waits for a person, which is every order under the four shipped profiles, rule F-10), refuses (`BLOCK`), or places the order (`AUTO`, only where the buyer switched ordering alone on and every statement is confirmed). Nothing is sent to Valio Aimo and no payment is taken: `ORDERED` means recorded in our order book.
8. **Approval.** A person with the named role approves or rejects, on the pages or over REST. One person confirms: at the hotel and the bakery the person who orders holds every role; at the ward and the school a dietitian is the second person, for allergen and dietary-claim questions and for a substitute whose formula differs or that is not like for like. The order-time check runs again before the order is placed. Over REST an agent token on an approval route is refused (F-06) and the attempt is logged, and no MCP tool approves; the demonstration pages have no login, so there the guarantee rests on who opens the page. When rule P-04 sends a product to the dietitian because an excluded allergen is not ruled out, `evidence/` attaches what the product's web page says, labelled as not Valio data and called the manufacturer's page only on a host we list for the brand; a page can add a doubt and never removes one, and it changes no verdict.
9. **Audit.** Every step writes one event with one readable sentence, stored in a CloudEvents envelope and chained by SHA-256 hashes. `GET /v1/audit` answers a reader's view of each event, not the envelope. The buyer and the supplier each read their own view: Valio Aimo sees every rule that fired and the products left out, with the buyer's name, limit amounts and allergens masked. A change of a buyer's settings is an event too.
10. **Proof.** The offer and the order record answered over REST or MCP carry `proof`: the gateway's own Ed25519 signature (a detached JWS over the record's canonical JSON), with a demo key unless `TTA_SIGNING_KEY` is set. It is not Valio Aimo's signature.

## Packages

| Package | What it does | Implements | Uses |
|---|---|---|---|
| `contracts/` | Shared Pydantic models, typed errors, ports, JSON Schema export; `menu.py`, `standing.py`, `customer.py`, `suggestion.py` | — | — |
| `config.py` | Settings from the environment and `.env`; secrets as `SecretStr` | — | — |
| `valio/` | HTTPS client for the mock, recorder, replay of a capture, call budget, live and pinned clocks | `ValioGateway`, `Clock` | — |
| `catalog/` | Loads the product file and the two CSV files; search; product-type table (`product_types.yaml`, 32 types, ours); pack size; portion packs; lot rounding; flavour, use and "is a drink" read from product names (`kinds.py`, ours) | `Catalog` | — |
| `allergens/` | GS1 code table and families; buyer exclusion rule (an exclusion with no rule reads strict); the ingredient list as a statement; substitution rule; claims against allergen data | functions | — |
| `availability/` | The six states; the status of each claim; sentences | functions | — |
| `policy/` | Rules file, four buyer profiles, deterministic engine, policy hash; `human_approval.py` (F-10, the one rule in code); `drift.py` and `standing_facts.py` (P-08, a renewal's drift); `formula_facts.py` (F-11), `last_resort_facts.py` (F-12), `premium_facts.py` (P-09) | `PolicyEngine` | — |
| `offers/` | Candidates → options; ranking; combining; substitutes (same 5-digit category or listed by Valio); `formula.py` (six nutrients and the fat source against the original's); `safety.py` (the safe product first); `completing.py` (a partial confirmed fill completed with a named substitute); `later.py` (the earliest date as an alternative when the date asked cannot be met); re-check before an order; `preference.py` and `comparison.py` | `OfferBuilder`, `OfferRevalidator` | `Catalog`, `ValioGateway`, `PolicyEngine`, `Clock` |
| `store/` | SQLite repository (the default); PostgreSQL repository, used when `DATABASE_URL` is set, in the schema `TTA_DB_SCHEMA` names: database triggers that refuse changes to audit events, buyer and supplier views (the supplier view is dropped and re-created at start), a read-only supplier role (`sql/001`…`005`); SQLite when the database cannot be reached at start, and `/healthz` names the store and the reason. The live PostgreSQL tests (`tests/store_pg`) are skipped offline and were not run against a database in the evening build | `Store` | — |
| `evidence/` | What a product's web page says about an excluded allergen, for the dietitian. Recorded pages in `fixtures/evidence/` (13) answer without a key; a page is shown only when its variant marks (fat percentage, lactose-free, UHT, flavour, pack) agree with the product; a host not on our brand-owner list reads "a web page whose owner was not checked". A new lookup (Context.dev Answers) happens only with `CONTEXT_DEV_API_KEY` set, and the request count is kept on disk | `EvidenceFinder` (a protocol in `orders/service.py`) | `Catalog` |
| `customers/` | The four demo customers from `data/*.yaml`: people and roles, usual products, past orders (8 each for the hotel, the school and the bakery, 16 for the ward), standing orders. All synthetic and marked so | functions | — |
| `suggestions/` | `suggestions_for`: at most three suggestions, one per kind (forgotten item, usual product or quantity, cheaper product with the same formula, larger pack, trend, Valio Aimo's own suggestion of a related product, last), each checked like any product; a suggestion never adds itself to an order. Thresholds in `thresholds.py`, ours. Every offer made in replay carries them (`Offer.suggestions`), over REST, MCP and `/shop`; there are none with live data | functions | `Catalog`, `ValioGateway`, `Clock` |
| `audit/` | Events, hash chain, sentences from templates (never from a model), the buyer's view and Valio Aimo's view (`readers.py`, `supplier_decisions.py`: every rule that fired, the buyer's values masked) | `AuditSink` | `Store` |
| `standing/` | Standing orders: set up, list, read, renew through the normal offer and order; the history of past renewals; at most 20 per buyer; the demo standing orders with their synthetic weeks. No scheduler: a person or an agent asks for each renewal | `StandingOrders` | `Store`, `AuditSink`, `GatewayService`, `Clock` |
| `menus/` | The recipe table (`recipes.yaml`, ours and illustrative), servings minus stock to request lines, the menu planner that tries a role's alternatives and asks at most 3 offers (task MENU-1) | `plan_menu` | `GatewayService` |
| `orders/` | Order-time check, approvals, expiry, idempotency, the day's spend, evidence on an approval | `OrderService` | `OfferRevalidator`, `PolicyEngine`, `Store`, `AuditSink`, `Clock`, `EvidenceFinder` |
| `api/` | FastAPI app, REST routes (`menu_routes.py`, `standing_routes.py`, `customer_routes.py` among them), identity, limits (per visitor, per address, overall), problem details, OpenAPI, the MCP surface with its `Origin` check (`mcp_origin.py`), discovery documents (`discovery.py`), schema export (`schema_export.py`), signing (`signing.py`, `keys.py`), fall-back from live to replay, one order book per browser (`sandbox.py`) | `GatewayService` (`service.Gateway`) | all of the above |
| `agent/` | Free text → typed request, by three readers in order. A model when one is configured (`GEMINI_API_KEY`, or an OpenAI-compatible endpoint by the `TTA_AGENT_*` settings): the parser with a check of every reading against the text, and a tool-calling loop (`gemini.py`, `parser.py`, `runner.py`). When none answers or none is configured (`fallback.py`): recorded readings (`recorded.py`, 11 in `fixtures/agent/`, 7 of them written by hand and labelled so), then the fixed-rules reader (`rules_reader.py`); what the rules cannot read becomes a question (`unread.py`, `asking.py`). A photo of an order list needs the model | `RequestParser`, `AgentRunner` | `GatewayService` |
| `ui/` | The shop page (`static/shop/`, static files over `/shop/api/*`, `shop_api.py`) and the server-rendered pages: request, approvals (with the evidence card), order and audit trail, assumptions, `/kitchen`, `/menu`, `/standing-orders`. Everything a person does in the demo is on `/shop`: requests, recipe plans, confirming, standing orders and their renewal, settings, the log in both views, Valio Aimo's back office. The shop page was walked by a script in headless Chrome on 15 Nov (`AIMO/build/replan/REVIEW.md`, section BW), before the last changes to it | — | `GatewayService` |

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
| `Store` | Save and read offers, orders, approvals, idempotency keys, standing orders and their renewals; append audit events; `atomic()` block | `store.sqlite_store.SqliteStore`, `store.postgres.PostgresStore` |
| `AuditSink` | Record one event per step; reader views; chain check; head (count and last hash) | `audit.trail.AuditTrail` |
| `OrderService` | Place, decide, read orders and approvals; the day's committed spend | `orders.service.OrderBookService` |
| `RequestParser` | Free text → typed request; names what is missing, never guesses | `agent.fallback.FallbackParser` (`agent.parser.ModelRequestParser` first when a model is configured; then a recording, then fixed rules) |
| `GatewayService` | Every function a surface offers, each taking the caller's identity first | `api.service.Gateway` |
| `AgentRunner` | A run over `GatewayService`: authority, offer, order | `agent.fallback.FallbackRunner` (`agent.runner.ModelAgentRunner` first when a model is configured; then a recorded run, else a fixed run made by the rules) |

## Where each part of the brief lives

| Brief ([`AIMO/CHALLENGE.md`](../AIMO/CHALLENGE.md)) | Interface | Code |
|---|---|---|
| Core 1 — "a structured way for an external agent to search for and retrieve what's available and at what price" | `POST /v1/products/search` and `GET /v1/products/{id}`, with `price_and_availability=true` for the price and what is available on each product (at most 20 a call); `POST /v1/offers`; MCP `search_products`, `get_product`, `get_offer` | `catalog/search.py`, `offers/builder.py`, `valio/client.py`, `availability/states.py`, `availability/claims.py` |
| Core 2 — "a defined interaction for moving from inquiry to commitment, based on fixed prices" | `POST /v1/offers` → `POST /v1/orders` with `Idempotency-Key`; `GET /v1/orders/{id}`; MCP `place_order`, `get_order` | `offers/revalidation.py`, `orders/checking.py`, `orders/service.py` |
| Core 3 — "what the agent may decide on its own, and what must go to a human for sign-off" | `GET /v1/authority`; `GET /v1/approvals`; `POST /v1/approvals/{id}/decision`; pages `/shop`, `/approvals`; MCP `get_authority` (no MCP tool approves) | `policy/rules.yaml`, `policy/human_approval.py`, `policy/profiles/*.yaml`, `policy/engine.py`, `orders/access.py` |
| Trust protocol — what an agent can trust about stock, price and origin | A status per statement on every offer line: `CONFIRMED`, `UNKNOWN` or `RULED_OUT`; `proof` on every offer and order record (the gateway's signature, not Valio Aimo's); `/.well-known/jwks.json` | `availability/claims.py`, `api/signing.py` |
| Response logic — partial availability, good-better-best substitutes | Options of an offer; `POST /v1/products/{id}/substitutes`; MCP `find_substitutes` | `offers/combining.py`, `offers/options.py`, `offers/substitutes.py`, `allergens/substitution.py` |
| Audit trail — "for both buyer and Valio Aimo" | `GET /v1/audit?reader=buyer\|supplier`; pages `/shop`, `/orders/{id}`; MCP `get_audit` | `audit/trail.py`, `audit/chain.py`, `audit/readers.py`, `audit/supplier_decisions.py`, `store/schema.py` |
| Optional — delivery time and sustainability comparison | Each line's reliability, carbon and labels; each option's comparison; `prefer` and `required_labels` on the request; the `CHEAPEST_CONFIRMED` option (task SUST-1) | `offers/preference.py`, `offers/comparison.py`, `catalog/loader.py`, `catalog/search.py` |
| Optional — proactive selling agent | Valio Aimo's own suggestion of a related product (`FROM_SUPPLIER`), shown last, only with a stated benefit, and never applied; the product file has no "new" or "seasonal" mark, so "related" is all it can be. It answers a request: nothing runs before the kitchen asks | `suggestions/supplier.py` |
| Open standards (15%) | `GET /openapi.json`, `GET /v1/schemas` (98 models, each with `$schema`), `/.well-known/api-catalog`, `/llms.txt`, MCP at `/mcp/`; see [STANDARDS.md](STANDARDS.md) | `api/docs.py`, `api/schema_export.py`, `api/discovery.py`, `api/mcp_surface.py` |

## Modes and the clock

- `TTA_MODE=replay` (the default): answers come from `fixtures/valio/<capture>/`, and the clock is pinned to that capture's `timeNow`. The default capture is `2026-11-14-demo` (Saturday 14 Nov 2026, 02:52 Helsinki time, 769 products); replay also answers for the 394 baking products of `2026-11-14-baking` (the same Saturday, 21:12), 1,163 in all, and an offer that holds one of those says so.
- **The demo clock.** `TTA_DEMO_CLOCK` replaces the recording's instant as "now" in replay; the recorded data is not changed. It is ours (Valio Aimo said its test data is static); the demo uses Thu 12 Nov 2026 14:15 Helsinki time. Ignored in live mode; outside `dev` and `demo` the gateway does not start with it. `/healthz`, each offer (`time_basis`) and the pages say which clock is in force.
- `TTA_MODE=live`: calls the mock through the client: at least one second between calls, a 60-second cache, a call budget kept in `var/valio_call_budget.json`. When the mock cannot be reached, or fewer than 10 calls are left, the capture answers and the offer says `replay`.
- **Two clocks.** The data clock (pinned in replay; in live the later of this machine's time and Valio's last `timeNow`) judges cut-offs, price validity, expiry and the day of the daily spend, and stamps offers, orders and approvals. Audit events carry the real UTC time (`api/wiring.py`, `UtcClock`). In replay at the recording's clock an order reads 02:52:45 while its events carry the real time.
- `TTA_ENV` decides who can call. `dev` and `demo` load the public demo tokens of `src/tta/api/demo_tokens.yaml` (11 identities: 4 agents, 6 approvers, the supplier) and mount the pages. Unset means `prod`: no demo token, no pages, and the app does not start without `TTA_TOKENS`.

## Assumptions of the design, and the next step for each

From the build's hand-backs in `AIMO/build/handback/` and the checks of 15 Nov (`AIMO/build/replan/REVIEW.md`), both on branch `replan-build`. The whole list of next steps is in [ASSUMPTIONS.md](ASSUMPTIONS.md).
- **One process.** The order book's lock, the rate limiter, the agent-run log of the pages and the cached audit head live in memory. Two gateway processes on one database are not protected against each other. Next: a lock, a limiter and a budget shared between processes.
- **SQLite.** The audit table refuses update and delete through triggers, but whoever can write the database file can drop them. On PostgreSQL the triggers are in the database, but the gateway connects as the login that owns the tables (`docs/AIVEN.md`). The chain shows a changed, removed or inserted event; it does not show the last events cut off unless another party holds the head (`/healthz` publishes it, and verifies the whole chain for its answer: a broken chain reads `degraded` with the first bad event). `deploy/witness.py` defines an hourly check that notes the head and compares the next one with it; it is written and tested offline and has never run on Modal. Next: run it, and a gateway login that does not own the tables.
- **The signature is the gateway's own.** `proof` shows that this gateway answered a record. With no `TTA_SIGNING_KEY` the key is a demo key that changes at every start. Nothing is signed by Valio Aimo; a statement signed by the supplier itself (for example as a Verifiable Credential) is a next step.
- **Everything about a customer is synthetic.** Names, people, past orders and limits are ours; the mock has no customer model. Next: real customers, their limits, people and order history.
- **A stored order is not tied to its audit events.** Whoever can write the database can change a stored order or offer; the gateway then answers the changed record with a signature that verifies, and the chain stays intact. Next: a reference from each record to its event, which needs a field on a hashed model.
- **No login on the pages.** They act as the customer's person shown on the page and take no credential, so whoever opens `/shop` can confirm as any of that customer's people, the dietitian included. "An agent cannot approve" is enforced over REST and MCP, where a token says who calls. The pages exist only in `dev` and `demo`. Next: people sign in with their own accounts; outside `dev` and `demo` no page is mounted today and a person decides with a token of their own.
- **One person holds every role at the hotel and the bakery.** A choice for the demonstration (one confirmation, no second signer). Next: a second signer above an amount.
- **The pages' books are in memory.** A restart empties every browser's book; only the shared REST and MCP book is kept in the database. Next: the pages on the shared book, once people sign in.
