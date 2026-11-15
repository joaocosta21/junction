# Trusted Trade Agents

A gateway that makes a food-service wholesaler, Valio Aimo, readable by a buyer's purchasing agent: the agent looks up products, prices and availability, gets an offer at fixed prices, and prepares an order that a person confirms. It is a typed interface with rules (REST with OpenAPI 3.1, and the Model Context Protocol), not a chatbot: fixed rules no buyer can switch off, each buyer's own limits on top, and an agent's token can never approve an order. Every offer line says, statement by statement, whether Valio Aimo's data confirms it; every offer and order record is signed; every step goes to a hash-chained audit trail with one view for the buyer and one for Valio Aimo.

Built at Junction 2026 for Valio Aimo's challenge "Trusted Trade Agents", against Valio Aimo's mock API. MIT licence. The brief and its judging criteria, verbatim: [AIMO/CHALLENGE.md](AIMO/CHALLENGE.md). Where each criterion is answered, with the proof for each: [AIMO/COVERAGE.md](AIMO/COVERAGE.md).

## The brief's request, and the answer

> "I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability."

Sent as Harbourside Hotel's agent, the gateway answers with three options in structured form:

| Option | What it covers | Before tax | Rules that send it to a person |
|---|---|---|---|
| 1. Best confirmed option (partial fill) | 435 L of the 1,000 L, from two milks whose stock Valio Aimo confirms | €1,083.39 | P-01, above the hotel's €750 limit per order; P-03, less than 90% of the quantity covered |
| 2. Alternative: quantity not confirmed | 1,000 L of one milk whose stock Valio Aimo does not confirm | €1,010.00 | F-01, a fixed rule: a quantity Valio Aimo does not confirm always goes to a person; P-01 |
| 3. Alternative: confirmed stock, completed with a substitute | 1,000 L, all from confirmed stock: the same 435 L, and 565 L of a lactose-free milk made for coffee (`463380`), named as a substitute | €2,580.64 | F-12, a fixed rule: a substitute that is not like for like goes to a person; P-01 |

- **Request → lookup → order → approval.** Placing an option answers with the order in state `PENDING_APPROVAL`. Nothing is ordered until a person confirms: "Ordered for €1,083.39 net with approval by Hanna Laine, Harbourside Hotel: rules P-01 and P-03 asked for a human and were accepted." An agent's token gets 403 at the approval route, and the attempt is logged.
- **Why 435 L.** In the recording only two plain lactose-free milks have a confirmed stock figure. That is the scenario, not a fault: the agent offers what is confirmed, names the alternatives, and asks a person. Valio Aimo, asked on 14 Nov whether a buyer who asks for milk accepts milk for coffee, answered "no be explicit", so coffee milk never fills a milk request silently.
- **The agent ordering alone** is a buyer's setting, off by default. Switched on for the hotel: 302 L, €748.96, is ordered by the agent; 303 L, €751.44, goes to a person because of the €750 limit.

These figures were measured on Sunday 15 Nov 2026 in replay of the recording (769 products, recorded Sat 14 Nov 2026 02:52 Helsinki), with no key set. The three options, their totals and their rules were measured again over REST at commit `d617d5c`: they are the same at the recording's clock and at the demo clock (Thu 12 Nov 2026 14:15). Six more scenarios (the allergy ward, a stock-out, an allergen doubt, the customer's pattern, the formula, a recipe): [docs/DEMO.md](docs/DEMO.md).

## Run it

Python 3.13. No key and no account; once installed, replay makes no outside call. From the repository root:

```bash
python3.13 -m venv .venv && .venv/bin/pip install -e ".[dev]" && GEMINI_API_KEY= TTA_ENV=demo TTA_MODE=replay .venv/bin/python -m uvicorn --factory tta.api:create_app --no-proxy-headers
```

- **As a person:** open http://127.0.0.1:8000/shop, type `1,000 litres of lactose-free milk by Monday`, press "Check price and stock", then "Confirm order". Open the order under "Orders" to read the log, in the buyer's view and in "What Valio Aimo sees". The first start takes about ten seconds while the product file loads.
- **As an agent:** start at http://127.0.0.1:8000/.well-known/api-catalog or `/llms.txt`; the interface is at `/docs`. Demonstration tokens are public by design, for example `curl -s -H "Authorization: Bearer demo-agent-hotel-kitchen" http://127.0.0.1:8000/v1/authority`.
- **Without installing:** https://joaocostared--trusted-trade-agents.us-east.modal.run. The team's build log says which commit it runs and how it was checked (`AIMO/build/replan/STATUS.md`, on branch `replan-build`); the link was not called for this page.

## Open, documented standards

Nothing proprietary to learn: an agent that knows only the address finds every way in, and each format below is a published one. Each row's departures from its standard are in [docs/STANDARDS.md](docs/STANDARDS.md).

| Standard | Where to see it |
|---|---|
| OpenAPI 3.1 | `GET /openapi.json`, `/docs`, `/redoc`: generated from the typed models, 27 paths |
| JSON Schema 2020-12 | `GET /v1/schemas`: 98 contract models, each with its `$schema` |
| Model Context Protocol | `/mcp/`: the same service as 13 tools; none approves an order (`src/tta/api/mcp_surface.py`) |
| RFC 9457 problem details | Every error, over REST and inside MCP tool errors (`application/problem+json`) |
| RFC 9727 API catalog | `GET /.well-known/api-catalog`, with no token |
| `llms.txt` (a community proposal) | `GET /llms.txt` |
| Ed25519 signatures as a detached JSON Web Signature, with a published JSON Web Key set | `proof` on every offer and order record; `GET /.well-known/jwks.json` (`src/tta/api/signing.py`) |
| CloudEvents 1.0 | The envelope every audit event is stored in (`src/tta/contracts/audit.py`); `GET /v1/audit` answers a reader's view of each event |
| GS1 allergen code lists | Allergen codes and what each means (`src/tta/allergens/codes.py`) |
| Bearer tokens (RFC 6750), the `Idempotency-Key` header, RFC 3339 times, ISO 4217 currency | Identity, a retry that never orders twice, every timestamp and amount |

Nothing is published for a protocol we do not implement.

## Assumptions

What in this demonstration is ours, stated as such. Every value, with where it lives: [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md), also served at `/assumptions`.

- **The order step is ours, by design.** Valio Aimo's mock has no order endpoint. "Ordered" means recorded and signed in this gateway's order book: no order reaches Valio Aimo, the record commits nobody, no payment is taken and no stock is reserved. Price and availability are checked again when an order is placed and when it is approved.
- **The data is a recording, and the clock is chosen.** Replay answers from two recordings of Valio Aimo's mock made on Sat 14 Nov 2026: 1,163 of the catalog's 17,546 products. A product outside them is left out as "not in the recording", never as unavailable in Valio's name. The demo clock (Thu 12 Nov 2026 14:15) is ours; Valio Aimo said on 14 Nov that its test data is static.
- **The customers are synthetic.** The four customers, their people, their order history and the recipe table are made up for the demonstration and say so wherever they show. Suggestions come from that history, and each says so; a suggestion is shown, never added.
- **The limit values are illustrative.** Spend per order and per day, minimum cover, the drift tolerance, the rates per minute and every other threshold are ours; the mock has no customer limits.
- **One person confirms.** Our choice for the demonstration (see "The four customers").
- **The signature is the gateway's, with a demo key.** The `proof` says this gateway answered this record; the key is generated at start and marked as a demo key inside the signature. It is not Valio Aimo's signature.
- **The demonstration pages have no login.** On `/shop` whoever opens the page acts as the selected customer's person, the dietitian included, and the page says who. That an agent cannot approve is enforced over REST and MCP, where the token says who calls. The pages are mounted only in `dev` and `demo`.
- **A model reader exists and is off.** The public link and every figure on this page use the fixed rules and the recordings (see "Who reads a request").
- **What is Valio Aimo's, not ours:** the product file (17,546 products), the reliability and carbon files, and the recorded price and availability answers.

## Technical choices, and why

| Choice | The alternative we did not take | Why |
|---|---|---|
| Fixed rules decide; a model, when one is configured, only reads the sentence | A model that picks products, prices or verdicts | Every price, quantity, allergen status and verdict can be tested, repeated and audited. A reading is checked against the text, and what cannot be read becomes a question for the person, not a guess |
| Rules as data in YAML: fixed rules, plus one profile per buyer (`src/tta/policy/`) | Rules written into code or into a prompt | The guardrails can be read and changed without touching code, and the policy hash in every decision says which version applied |
| A hash-chained audit trail with two views | An application log, or one view for everyone | A changed, inserted or removed event is detected and named, and `/healthz` reports it. Valio Aimo reads the same events as the buyer, without the buyer's private facts (a limit amount, a name) |
| Replay from a recording at a fixed clock | A demonstration that calls the mock live | The same answer at any hour, with no key, whatever the mock does. Live mode asks Valio Aimo's API per request through the same code |
| A person confirms every order by default | The agent orders alone by default | Valio Aimo, 14 Nov: "for now deactivate automatic order". Ordering alone is a buyer's setting inside the fixed rules, and the order says why it was allowed |
| REST and MCP over one service object | One surface only, or two implementations | Any agent can use the gateway, and the rules live in one place |
| The interface generated from typed models (FastAPI, Pydantic) | A specification written by hand | The published OpenAPI and JSON Schema cannot drift from the code |
| SQLite by default; PostgreSQL behind the same interface when `DATABASE_URL` is set | A database service required to start | A clone runs with nothing else installed. In PostgreSQL the database itself refuses changes to audit events ([docs/AIVEN.md](docs/AIVEN.md)) |

The packages and the ports: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Next steps

What a pilot would add, each on something that exists today.

- **Valio Aimo signs its own statements.** Today the gateway signs every offer and order record, with the key published at `/.well-known/jwks.json`. The same check works with a supplier's key on price, stock and origin ([docs/STANDARDS.md](docs/STANDARDS.md)).
- **An order message Valio Aimo's systems can take.** Today an order is a signed record in our order book. Next: the same record sent in an open e-procurement format, once Valio Aimo names the one it accepts.
- **People sign in with their own accounts.** Over REST and MCP a token already says who calls, and an agent's token is refused at the approval route. Next: the same for people on a page, so that only the dietitian can answer the dietitian's question there; and a second signer above a spend limit.
- **Stored orders tied to their audit entries.** Today a changed, inserted or removed audit event is detected and named. A stored order is not yet bound to its event: whoever can write to the database can change an order and the gateway signs what it reads, and a cut tail of the trail is caught only by someone who kept the head. Next: the order's hash carried in its event, and the head of the chain kept by someone outside the database.
- **The audit trail as CloudEvents at the interface.** Events are stored in a CloudEvents 1.0 envelope; `GET /v1/audit` answers a reader's view of each (no `specversion`). Next: a route that serves the envelope itself, so the trail loads into a CloudEvents tool.
- **A demo agent that orders alone over REST and MCP.** Today ordering alone is off in the four profiles and is shown on the shop page (Settings). Next: one demo identity whose buyer has it on.
- **A scheduler for standing orders.** Today a stock-out, a suggestion or a drift is found when a request or a renewal arrives, and a person presses renew. The drift rule and the renewal exist; a scheduler calls them on the cadence the standing order stores.
- **A nutrition standard for schools and hospitals.** Today the allergen rules are fixed, and a substitute whose formula or nutrients differ goes to the dietitian where a customer has one. Next: her standard written as rules, so that she is asked less.
- **An origin filter, a price per unit, and Finnish.** Today the reader asks about a price per unit ("under €2 a litre") and about a sentence in Finnish or Swedish, and does not read a word such as "Finnish" as a filter; it asks rather than guesses. The typed request is where each new field goes.
- **Substitutes for more products.** Today a product with no product type of ours often gets no substitute, and the answer says so: of the 1,163 recorded products 872 have a substitute that can be ordered (measured by the lane that built the rule, `AIMO/build/replan/STATUS.md`). Next: product types for more of the catalog.
- **New and seasonal products marked in the data.** Today the product file has no such mark, and the recipes are ten illustrative ones of ours. With a mark in Valio Aimo's data, its own suggestion and the recipe choice can use it.
- **A finer count of sales not made in Valio Aimo's back office.** Today a request that the buyer's own requirements emptied is not counted as a sale Valio Aimo could not make; a request that has an option and is short partly for a buyer's rule is still counted whole. Next: split that quantity by reason.

---

The rest of this page is reference.

## The flow

```
request ──► lookup ──► offer ──► rules ──► order prepared ──► a person confirms
(typed, or   (catalog +  (options, a    (fixed rules   (recorded, waiting,   (or rejects; an agent's
 a sentence   price and   status per     F-01 to F-12   signed by the          token cannot)
 read and     stock)      statement,     + the buyer's  gateway)
 checked)                 every          rules P-01
                          exclusion      to P-09)          every step ──► audit trail (buyer's view, Valio Aimo's view)
                          with a reason)
```

Over REST: `GET /v1/authority` → `POST /v1/offers` → `POST /v1/orders` with an `Idempotency-Key` header → `GET /v1/orders/{id}` and `GET /v1/audit`. A person decides at `POST /v1/approvals/{id}/decision` with a person's token; an agent's token gets 403 there.

## Who reads a request

- A request arrives **typed** (`POST /v1/offers`, the MCP tool `get_offer`) or as a **sentence** (`POST /v1/requests/parse`, the shop page).
- **Fixed rules read the sentence** (`src/tta/agent/rules_reader.py`): quantity and unit, product type or product number, claims such as lactose-free, excluded allergens, the day, "confirmed only", a preference. Over REST and MCP a sentence the repository holds a recording for (11 files in `fixtures/agent/`, some recorded from a model on 14 Nov, some written by hand) is answered from that recording first, for the demo customer it was recorded for.
- **What the fixed rules cannot read is not guessed:** the answer is a question for the person (status 422, with `question`, `not_read`, `read_by`). They ask about a minus sign, about cartons, cases and pallets (they do not know what one holds), about a price per unit ("under €2 a litre"), and about a sentence in Finnish or Swedish (they read English only). [docs/READING-TABLE.md](docs/READING-TABLE.md), generated from the fixed rules alone: 126 sentences, 67 read, 59 asked about, 0 read wrong.
- **An amount named for the whole request is read** ("under €400", "max 1000 euros", "a budget of €1,000") into `max_net_eur`, euros before tax, and applied by rule P-01 as a spend limit for that one request, the lower of it and the buyer's own limit per order: it can only tighten. Measured at the demo clock, hotel: "200 litres of lactose-free milk by Monday, under €400" → 200 × `469363` is €496.00 and waits for a person, "The total of €496.00 before tax is above the €400 you named for this request."
- **A model may read the sentence instead, when one is configured** (a key, or an OpenAI-compatible endpoint with the `TTA_AGENT_*` settings). It is off by default, off on the public link, and off for every figure on this page and in [docs/DEMO.md](docs/DEMO.md). Measured by the build on 15 Nov on a local server with a key set: the brief's own sentence was read into 1,000 L, product type milk, claim lactose-free, Monday 16 Nov. The gateway checks every reading against the text and refuses one that does not match ("the reading did not match the text: the text names another day"); it does not repair a reading itself. When the model answered HTTP 429, the fixed rules read the sentence and the answer said so; after a first 429 the model is not asked again for 120 seconds, and a sentence neither can read is answered 503 with the rules' own reason.
- **Every answer says who read it:** the headers `TTA-Read-By`, `TTA-Reading-Source` and `TTA-Reading-Sentence` over REST, a line on the shop page. `GET /healthz` → `agent_reader` says what reads sentences on a given deployment, the public link included.
- **Whoever reads, fixed rules decide what may be ordered:** deterministic code decides every price, quantity, allergen status and verdict.
- A dish is read too, by fixed rules: "A chocolate cake for 20 by Monday" becomes a recipe plan and one offer (`POST /v1/menus/plan`), from ten illustrative recipes of ours; a sentence that names an ingredient is answered with the dishes that use it.

## The four customers

All four are ours and **synthetic**: names, people, limits and eight weeks of order history are made up for the demonstration and marked `synthetic` (`src/tta/customers/data/`, `src/tta/policy/profiles/`). The mock has no customers, limits or order history.

| Customer | Limit per order / per day (before tax) | Its own rules | Who confirms |
|---|---|---|---|
| Harbourside Hotel (`hotel-kitchen`) | €750 / €3,000 | 90% of the quantity covered; a substitute from the same category needs no extra approval | Hanna Laine, purchasing manager, holds every role |
| City Hospital, Ward 4 (`allergy-ward`) | €500 / €1,500 | No milk, no gluten, strict; confirmed data only; every substitute to a person | Jussi Nieminen, purchasing manager; Sari Lehto, dietitian |
| Kilo School (`school-kitchen`) | €250 / €800 | No tree nuts, peanuts or sesame, strict; only substitutes Valio Aimo lists | Päivi Korhonen, purchasing manager; Riikka Mäkelä, dietitian |
| Kallio Bakery (`bakery-cafe`) | €300 / €1,000 | The formula matters on every line; every substitute to a person | Marko Heikkinen, the owner, holds every role |

**One person confirms.** At the hotel and the bakery the person who orders holds every role, so one confirmation completes an approval whatever rule asked. The ward and the school have one second person, the dietitian: she decides allergen and dietary-claim questions (P-04, F-08) and a substitute whose formula differs or that is not like for like (F-11, F-12). No customer has a separate finance signer. This is our choice for the demonstration: one token therefore holds every role at the hotel and the bakery, and a second signer above a limit is a next step.

## The rules, in short

`GET /v1/authority` returns every rule in words for the caller's customer. The contract is [AIMO/SPEC.md](AIMO/SPEC.md).

- **Fixed rules F-01 to F-12** hold whatever a buyer sets. Examples: F-01, a product whose quantity Valio Aimo does not confirm always goes to a person; F-02, a product that declares an allergen the buyer excludes can never be ordered, even with approval; F-06, an agent can never approve an order, its own included (over REST and MCP: the approval routes refuse an agent's token and log the attempt, and no MCP tool approves); F-11, where the formula matters, a substitute whose formula differs or cannot be compared goes to a person; F-12, a substitute that is not a like-for-like replacement (another formula, use, flavour or product type, or one the data cannot show to be like for like) goes to a person. At the ward and the school the person for F-11 and F-12 is the dietitian.
- **F-10, the agent prepares the order and a person confirms it**, is driven by the buyer's setting `auto_order_enabled`, off in all four profiles. Switched on, the agent orders alone only when no rule asks for a person and every statement of every line is confirmed, and the order says why it was allowed. In the demonstration the switch is on the shop page only, and every change of settings made there is an event in the audit trail: the buyer reads who changed what ("Hanna Laine switched ordering alone on: the agent may order up to €750.00 an order and €3,000.00 a day without asking."), Valio Aimo reads only that a setting changed. Valio Aimo, 14 Nov, of ordering alone as a setting: "after and if you are 100% sure yes".
- **The buyer's rules P-01 to P-09**: spend per order and per day, minimum cover, allergens to the dietitian, substitutes, products sold by weight, deposits, standing-order drift, and what a preference may cost. The substitute rule P-05 also bounds the price: a substitute that costs more than 25% above what the product it replaces would have cost, or whose price cannot be compared with it, goes to a person (the share is the buyer's where the profile sets one; 25% is ours). Measured at the hotel: the confirmed substitute for an oat drink whose stock is not confirmed costs €37.00 more (27%), so it waits for a person under F-12 and P-05.

## Running it, in detail

- **`--no-proxy-headers` matters.** Without it a local uvicorn believes an `X-Forwarded-For` header sent from the machine itself, so a caller could choose the address the rate limits count. The gateway itself reads that header only when `TTA_TRUSTED_PROXY_HOPS` is set.
- **`TTA_ENV` must be `dev` or `demo`.** Unset means `prod`: no demonstration token, no page, no start without `TTA_TOKENS`.
- **`GEMINI_API_KEY=` empty** keeps the model reader off even where the shell or a local `.env` holds a key.
- **Replay makes no outside call.** Prices and stock come from `fixtures/valio/2026-11-14-demo/` (769 products), joined with `2026-11-14-baking` (394 baking products of the same Saturday): 1,163 of the catalog's 17,546 products. The clock is pinned to the recording's instant. `TTA_DEMO_CLOCK=2026-11-12T14:15:00+02:00` sets the demo clock instead (replay only). `GET /healthz` says which clock is in force; the audit trail always keeps the real time.
- **Two kinds of order book.** On the pages each browser has its own book per customer, in memory. REST and MCP share one book in `var/tta.sqlite3`, where the day's spend adds up across runs; set `TTA_DB_PATH` to a new file to start empty. With `DATABASE_URL` set the shared book uses PostgreSQL ([docs/AIVEN.md](docs/AIVEN.md)).
- **Signing.** With no `TTA_SIGNING_KEY` the demo key is generated at start: a restart makes a new key, so a record signed before it no longer verifies.
- **The rates of the demonstration are ours.** Per minute: one visitor 60 lookups (offers, searches, reads), 20 orders and decisions, and 15 readings; one address 60 of each; all callers together 240 of each. One address may open 400 new order books of the pages in 10 minutes, and 1,000 books are kept. A buyer holds at most 20 standing orders.
- **The public link** is one container kept running, with 4,096 MiB ([docs/DEPLOY.md](docs/DEPLOY.md)). The deploy sends it no model key unless the deploying shell sets `TTA_DEPLOY_WITH_MODEL=1` (`deploy/modal_app.py`).
- **Demonstration tokens:** `src/tta/api/demo_tokens.yaml`, 11 identities (4 agents, 6 people, Valio Aimo's reader).

What is served, besides the open documents listed under "Open, documented standards" (which need no token):

| Path | What | Who |
|---|---|---|
| `/healthz` | Mode, the clock in force, the store, the signing key, the head of the audit chain; it walks the chain and says `degraded` with the first bad event | Anyone |
| `/v1/...` | REST, 27 paths in the OpenAPI document: authority, product search (with `price_and_availability=true`: the fixed price and what is available, for at most 20 products a call), substitutes, offers, orders, approvals, audit, customers, menus, standing orders, reading a sentence | Bearer token |
| `/mcp/` | The same service as 13 MCP tools; none approves an order; an argument a tool does not know is refused | Bearer token |
| `/shop` | The shop page: everything a person does (request, confirm, standing orders, settings, the log, Valio Aimo's back office), an order book per browser and customer, no login | `dev` and `demo` only |
| `/`, `/approvals`, `/kitchen`, `/menu`, `/standing-orders`, `/assumptions` | Older demonstration pages, still served | `dev` and `demo` only |

## Run the tests

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```

The tests call no outside service. One package at a time: `.venv/bin/python -m pytest tests/offers -q`. The whole suite was last run in one piece on commit `b567e5f`: 6,213 passed, 69 skipped, 1 deselected.

## Datasets, and how to refresh them

| What | Where | Refresh |
|---|---|---|
| Valio Aimo product file (17,546 products) and its JSON Schema | `valio_aimo_junction26_product_data.json`, `valio_aimo_junction26_product_data_schema.json` | Download from Valio Aimo's challenge API with the key from the Junction challenge page |
| Delivery reliability and carbon footprint | `valio_aimo_junction26_delivery_reliability.csv`, `valio_aimo_junction26_carbon_footprint.csv` | The same |
| Recorded price and availability answers of the mock | `fixtures/valio/<capture>/` (`manifest.json` holds the server's `timeNow`) | `scripts/capture_valio.py` (calls the mock) |
| Recorded web-page answers for allergen doubts (Context.dev) | `fixtures/evidence/` (92 recorded answers, one per product; 30 are shown as evidence, 39 are rejected with a reason, 23 found no page) | `scripts/record_evidence.py` ([docs/CONTEXTDEV.md](docs/CONTEXTDEV.md)) |
| The four demo customers: their people, usual products, eight weeks of order history and standing orders | `src/tta/customers/data/*.yaml` | Ours, synthetic, written for the demonstration; edit the file |
| The buyer profiles (spend limits, allergen rule, substitution scope, who approves) and the ten recipes of the menu planner | `src/tta/policy/profiles/*.yaml`, `src/tta/menus/recipes.yaml` | Ours, illustrative, written for the demonstration; edit the file |

To use a new recording, give it a new name and start with `TTA_REPLAY_CAPTURE=<name>`: the tests read the committed recordings by name.

## Read more

| Document | What it holds |
|---|---|
| [AIMO/SPEC.md](AIMO/SPEC.md) | The contract: interface, data shapes, states, rules |
| [AIMO/WALKTHROUGH.md](AIMO/WALKTHROUGH.md) | What the gateway does, step by step |
| [docs/AWARDS.md](docs/AWARDS.md), [docs/CONTEXTDEV.md](docs/CONTEXTDEV.md), [docs/AIVEN.md](docs/AIVEN.md), [docs/DEPLOY.md](docs/DEPLOY.md) | The technology awards: what ran and what did not; deploying |
| [docs/DEMO.md](docs/DEMO.md) | The demo script on `/shop`, with every scenario's figures at both clocks |
| [AIMO/FINDINGS.md](AIMO/FINDINGS.md) | Facts about the mock API and the data, from the first days |
| [AIMO/README.md](AIMO/README.md) | The index of `AIMO/`: the brief, the contract, and the references for Valio Aimo's API and data |

**This branch holds the delivery:** the code, the tests, the data and the documents above. The team's working notes of the weekend (the plan, the build log, the review findings, the questions asked at Valio Aimo's booth) are not on it. Some documents cite one of those notes as the source of a figure, a check or a decision, by a path such as `AIMO/build/replan/STATUS.md` or `AIMO/PLAN.md`. Those files are on the branch `replan-build`, at the same paths.

## Licence

MIT, see [LICENSE](LICENSE). The Valio Aimo datasets and recorded API answers are synthetic data of Valio Aimo's, not ours and not covered by it; whether they may stay in a public repository is a question for Valio.
