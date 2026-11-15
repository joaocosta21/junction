# Trusted Trade Agents

- **What it is.** A gateway that makes a food-service wholesaler, Valio Aimo, readable by a buyer's purchasing agent: the agent looks up products, gets an offer at fixed prices, and prepares an order that a person confirms.
- **Not a chatbot.** Valio's brief: "This is not about replacing today's e-commerce UI with a chatbot. It is about defining how a European food-service wholesaler can be safely and openly readable by autonomous agents". The product is a typed interface (REST with OpenAPI 3.1, and the Model Context Protocol) with rules, not a conversation.
- **What an agent can trust.** Every offer line says, statement by statement (price, quantity, delivery date, allergens, origin), whether Valio's data confirms it; every product left out says why; every offer and order record is signed by the gateway.
- **Who decides.** Fixed rules no buyer can switch off, plus each buyer's own limits. By default every order waits for a person; ordering alone is a buyer setting, off in all four demo customers. Over REST and MCP an agent's token cannot approve an order, its own included.
- **What is logged.** Every step goes to a hash-chained audit trail, in plain sentences, with one view for the buyer and one for Valio Aimo.
- **What is ours and assumed, and what comes next,** is said in two sections below: "Assumptions" and "Next steps".

Built at Junction 2026 for Valio Aimo's challenge "Trusted Trade Agents", against Valio Aimo's mock API. Where each judging criterion is answered, with the proof for each: [AIMO/COVERAGE.md](AIMO/COVERAGE.md).

This page describes the code of Sunday 15 Nov 2026, early morning (commit `dbb8e13`), run locally in replay. Its figures were measured then, through the shop page's own routes. The public link is https://joaocostared--trusted-trade-agents.us-east.modal.run; whether it runs this code is said in [docs/DEPLOY.md](docs/DEPLOY.md), and the link was not called for this page.

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

One run, measured in replay of the recording (769 products, recorded Sat 14 Nov 2026 02:52 Helsinki). The options, totals and rules are the same at the recording's clock and at the demo clock (Thu 12 Nov 2026 14:15):

- **Harbourside Hotel, the brief's own sentence: "I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability."**
  - Option 1, "Best confirmed option (partial fill)": two confirmed milks cover 435 L of the 1,000 L, €1,083.39 before tax. It goes to a person under two of the hotel's rules: P-01 (an order above the hotel's €750 limit) and P-03 (an option that covers less than 90% of the quantity).
  - Option 2, "Alternative: quantity not confirmed": one milk for the whole 1,000 L, €1,010.00, whose stock Valio does not confirm. Fixed rule F-01 sends it to a person: a product whose quantity Valio Aimo does not confirm always does.
  - Option 3, "Alternative: confirmed stock, completed with a substitute": the same 435 L and 565 L of a lactose-free milk made for coffee (`463380`), all from confirmed stock, €2,580.64. The coffee milk is named as a substitute that is not like for like, so fixed rule F-12 sends it to a person, with P-01.
  - Valio Aimo, asked on 14 Nov whether a buyer who asks for milk accepts milk for coffee, answered "no be explicit". So coffee milk never fills a milk request silently: it appears only as the named substitute of option 3.
  - Placing an option answers with the order in state `PENDING_APPROVAL`. Nothing is ordered until a person confirms; at the hotel that is Hanna Laine, and her confirmation reads "Ordered for €1,083.39 net with approval by Hanna Laine, Harbourside Hotel: rules P-01 and P-03 asked for a human and were accepted."
- In the recording only two plain lactose-free milks have a confirmed stock figure, so 1,000 L of the product asked for cannot be covered with confirmed stock. That is the scenario, not a fault: the agent offers what is confirmed, names the unconfirmed product and the substitute as alternatives, and asks a person.
- **With ordering alone switched on for the hotel** (the shop page, Settings): 302 L of lactose-free milk, €748.96, is ordered by the agent; 303 L, €751.44, goes to a person because of the €750 limit. The order the agent places says why it was allowed.

The seven demo scenarios (the allergy ward, a substitute, an allergen doubt for the dietitian, the customer's pattern and Valio Aimo's own suggestion, a standing order that drifts, the formula, a recipe) are in [docs/DEMO.md](docs/DEMO.md), with the figures at both clocks. [AIMO/COVERAGE.md](AIMO/COVERAGE.md) says how each part of the brief is answered and checked.

## Who reads a request

- A request arrives **typed** (`POST /v1/offers`, the MCP tool `get_offer`) or as a **sentence** (`POST /v1/requests/parse`, the shop page).
- **A model may read the sentence.** It is asked first when a key is set: `GEMINI_API_KEY` for Google's Gemini, or an OpenAI-compatible endpoint with the `TTA_AGENT_*` settings. Measured by the build on 15 Nov on a local server with a key set: the brief's own sentence was read by `gemini-3.6-flash` into 1,000 L, product type milk, claim lactose-free, Monday 16 Nov (`TTA-Read-By: gemini-3.6-flash`, `TTA-Reading-Source: model`).
- **The gateway checks every reading against the text, and refuses one that does not match.** It does not repair a reading itself. Measured in the same run: a loosely worded sentence whose day the model got wrong was refused with "the reading did not match the text: the text names another day".
- **When no model answers, or none is configured, the fixed rules read the sentence** (`src/tta/agent/rules_reader.py`): quantity and unit, product type or product number, claims such as lactose-free, excluded allergens, the day, "confirmed only", a preference. Measured in the same run: when the model answered HTTP 429 twice, the fixed rules read the sentence and the answer said so. Over REST and MCP a sentence the repository holds a recording for (11 files in `fixtures/agent/`, some recorded from a model on 14 Nov, some written by hand) is answered from that recording first, for the demo customer it was recorded for.
- **What the fixed rules cannot read is not guessed:** the answer is a question for the person (status 422, with `question`, `not_read`, `read_by`). They ask about a minus sign, about cartons, cases and pallets (they do not know what one holds), and about a sentence in Finnish or Swedish (they read English only); a money limit in a sentence is refused with the reason: limits are the buyer's settings. [docs/READING-TABLE.md](docs/READING-TABLE.md), generated from the fixed rules alone, with no model: 109 sentences, 55 read, 54 asked about, 0 read wrong.
- **Every answer says who read it:** the headers `TTA-Read-By`, `TTA-Reading-Source` and `TTA-Reading-Sentence` over REST, a line on the shop page. `GET /healthz` → `agent_reader` says what reads sentences on a given deployment, the public link included.
- **Whoever reads, fixed rules decide what may be ordered.** Deterministic code decides every price, quantity, allergen status and verdict. A model never decides. So the fixed rules are the model's check and its fallback.
- The figures on this page and in [docs/DEMO.md](docs/DEMO.md) were measured with no key set (`GEMINI_API_KEY=` empty, as in the run command below): there the fixed rules read every sentence on the shop page. We do not enter Google's award. Note for whoever deploys: `deploy/modal_app.py` passes the key to the public link when the deploying machine has one.
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

- **Fixed rules F-01 to F-12** hold whatever a buyer sets. Examples: F-01, a product whose quantity Valio Aimo does not confirm always goes to a person; F-02, a product that declares an allergen the buyer excludes can never be ordered, even with approval; F-06, an agent can never approve an order, its own included (over REST and MCP: the approval routes refuse an agent's token and log the attempt, and no MCP tool approves); F-11, where the formula matters, a substitute whose formula differs or cannot be compared goes to a person; F-12, a substitute that is not a like-for-like replacement (another formula, use, flavour or product type, or one the data cannot show to be like for like) goes to a person. So the agent never orders alone a substitute that is not judged replaceable. At the ward and the school the person for F-11 and F-12 is the dietitian.
- **F-10, the agent prepares the order and a person confirms it**, is driven by the buyer's setting `auto_order_enabled`, off in all four profiles. Switched on, the agent orders alone only when no rule asks for a person and every statement of every line is confirmed, and the order says why it was allowed. In the demonstration the switch is on the shop page only (over REST and MCP no demo agent orders alone), and every change of settings made there is an event in the audit trail: the buyer reads who changed what ("Hanna Laine switched ordering alone on: the agent may order up to €750.00 an order and €3,000.00 a day without asking."), Valio Aimo reads only that a setting changed. Valio Aimo, 14 Nov: "for now deactivate automatic order", and of ordering alone as a setting, "after and if you are 100% sure yes".
- **The buyer's rules P-01 to P-09**: spend per order and per day, minimum cover, allergens to the dietitian, substitutes, products sold by weight, deposits, standing-order drift, and what a preference may cost. The substitute rule P-05 also bounds the price: a substitute that costs more than 25% above what the product it replaces would have cost, or whose price cannot be compared with it, goes to a person (the share is the buyer's where the profile sets one; 25% is ours). Measured at the hotel: the confirmed substitute for an oat drink whose stock is not confirmed costs €37.00 more (27%), so it waits for a person under F-12 and P-05.

## Run it locally, in replay

Python 3.13 is required. From the repository root:

```bash
python3.13 -m venv .venv && .venv/bin/pip install -e ".[dev]"
GEMINI_API_KEY= TTA_ENV=demo TTA_MODE=replay .venv/bin/python -m uvicorn --factory tta.api:create_app --no-proxy-headers
# then open http://127.0.0.1:8000/shop
```

- **`--no-proxy-headers` matters.** Without it a local uvicorn believes an `X-Forwarded-For` header sent from the machine itself, so a caller could choose the address the rate limits count. The gateway itself reads that header only when `TTA_TRUSTED_PROXY_HOPS` is set.
- **`TTA_ENV` must be `dev` or `demo`.** Unset means `prod`: no demonstration token, no page, and no start without `TTA_TOKENS`.
- **Replay makes no outside call.** Prices and stock come from `fixtures/valio/2026-11-14-demo/` (769 products), joined with `2026-11-14-baking` (394 baking products of the same Saturday): 1,163 of the catalog's 17,546 products. The clock is pinned to the recording's instant. `TTA_DEMO_CLOCK=2026-11-12T14:15:00+02:00` sets the demo clock instead (replay only; an instant we chose, since Valio's test data is static). `GET /healthz` says which clock is in force; the audit trail always keeps the real time.
- **Two kinds of order book.** On the pages each browser has its own book per customer, in memory. REST and MCP share one book in `var/tta.sqlite3`, where the day's spend adds up across runs; set `TTA_DB_PATH` to a new file to start empty. With `DATABASE_URL` set the shared book uses PostgreSQL ([docs/AIVEN.md](docs/AIVEN.md)).
- **Signing.** With no `TTA_SIGNING_KEY`, offers and orders are signed with a demo key generated at start, and every `proof` says so. A restart makes a new key, so a record signed before it no longer verifies.
- **The pages have no login.** Whoever opens `/shop` acts as the selected customer's person; the page says who. The pages exist only in `dev` and `demo`.

A first call, with a demonstration token (public by design, listed in `src/tta/api/demo_tokens.yaml`; 11 identities: 4 agents, 6 people, Valio Aimo's reader):

```bash
curl -s http://127.0.0.1:8000/.well-known/api-catalog
curl -s -H "Authorization: Bearer demo-agent-allergy-ward" http://127.0.0.1:8000/v1/authority
```

What is served:

| Path | What | Who |
|---|---|---|
| `/.well-known/api-catalog`, `/llms.txt` | Every way in, for an agent that knows only the address | Anyone |
| `/openapi.json`, `/docs`, `/redoc` | Generated OpenAPI 3.1 | Anyone |
| `/v1/schemas` | JSON Schema 2020-12 of 98 contract models | Anyone |
| `/.well-known/jwks.json` | The public key behind every `proof` | Anyone |
| `/healthz` | Mode, the clock in force, the store, the signing key, the head of the audit chain; it walks the chain and says `degraded` with the first bad event | Anyone |
| `/v1/...` | REST, 27 paths in the OpenAPI document: authority, product search (with `price_and_availability=true`: the fixed price and what is available, for at most 20 products a call), substitutes, offers, orders, approvals, audit, customers, menus, standing orders, reading a sentence | Bearer token |
| `/mcp/` | The same service as 13 MCP tools; none approves an order; an argument a tool does not know is refused | Bearer token |
| `/shop` | The shop page: everything a person does (request, confirm, standing orders, settings, the log, Valio Aimo's back office), an order book per browser and customer, no login | `dev` and `demo` only |
| `/`, `/approvals`, `/kitchen`, `/menu`, `/standing-orders`, `/assumptions` | Older demonstration pages, still served | `dev` and `demo` only |

The flow over REST: `GET /v1/authority` → `POST /v1/offers` → `POST /v1/orders` with an `Idempotency-Key` header → `GET /v1/orders/{id}` and `GET /v1/audit`. A person decides at `POST /v1/approvals/{id}/decision` with a person's token; an agent's token gets 403 there.

## Run the tests

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```

The tests call no outside service: they run on the recordings and on fakes. One package at a time: `.venv/bin/python -m pytest tests/offers -q`. When the whole suite was last run in one piece, and on which commit, is in the build log (`AIMO/build/replan/STATUS.md`).

## Assumptions

What in this demonstration is ours, stated as such. Every value, with where it lives, is in [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md).

- **The order step is ours, by design.** Valio Aimo's mock has no order endpoint. "Ordered" means recorded and signed in this gateway's order book: no order reaches Valio Aimo, the record commits nobody, no payment is taken and no stock is reserved. Price and availability are checked again when an order is placed and when it is approved.
- **The data is a recording, and the clock is chosen.** Replay answers from two recordings of Valio Aimo's mock made on Sat 14 Nov 2026: 1,163 of the catalog's 17,546 products. A product outside them is left out as "not in the recording", never as unavailable in Valio's name. The demo clock (Thu 12 Nov 2026 14:15) is ours; Valio Aimo said on 14 Nov that its test data is static.
- **The customers are synthetic.** The four customers, their people, their order history and the recipe table are made up for the demonstration and say so wherever they show.
- **The limit values are illustrative.** Spend per order and per day, minimum cover, the drift tolerance and every other threshold are ours; the mock has no customer limits.
- **One person confirms.** Our choice for the demonstration (see "The four customers").
- **The signature is the gateway's, with a demo key.** The `proof` says this gateway answered this record; the key is generated at start and marked as a demo key inside the signature. It is not Valio Aimo's signature.
- **The demonstration pages have no login.** On `/shop` whoever opens the page acts as the selected customer's person, the dietitian included, and the page says who. That an agent cannot approve is enforced over REST and MCP, where the token says who calls. The pages are mounted only in `dev` and `demo`.
- **The rates of the demonstration are ours.** Per minute: one visitor 60 lookups (offers, searches, reads), 20 orders and decisions, and 15 readings; one address 60 of each; all callers together 240 of each. One address may open 400 new order books of the pages in 10 minutes, and 1,000 books are kept. A buyer holds at most 20 standing orders.
- **The public link** runs as one container that is kept running, with 4,096 MiB; its order books and its demo signing key live in memory ([docs/DEPLOY.md](docs/DEPLOY.md)).
- **Suggestions come from a synthetic order history,** and each says so: a forgotten item, a usual product or quantity, a trend, a cheaper product of the same formula, and Valio Aimo's own related product. A suggestion is shown, never added; Valio Aimo's own shows only when it has a stated benefit and enough confirmed stock.
- **What is Valio Aimo's, not ours:** the product file (17,546 products), the reliability and carbon files, and the recorded price and availability answers.

## Next steps

What a pilot would add. None of these exists today; each says what it builds on.

- **Valio Aimo signs its own statements.** Today the gateway signs every offer and order record (a detached JSON Web Signature, the key published at `/.well-known/jwks.json`). The same check works with a supplier's key on price, stock and origin ([docs/STANDARDS.md](docs/STANDARDS.md)).
- **People sign in with their own accounts.** Over REST and MCP a token already says who calls, and an agent's token is refused at the approval route. Next: the same for people on a page, so that only the dietitian can answer the dietitian's question there; and a second signer above a spend limit.
- **An order message Valio Aimo's systems can take.** Today an order is a signed record in our order book. Next: the same record sent in an open e-procurement format, once Valio Aimo names the one it accepts.
- **Stored orders tied to their audit entries.** Today a changed, inserted or removed audit event is detected and named, and `/healthz` reports it. A stored order is not yet bound to its event: whoever can write to the database can change an order and the gateway signs what it reads, and a cut tail of the trail is caught only by someone who kept the head. Next: the order's hash carried in its event, and the head of the chain kept by someone outside the database.
- **The audit trail as CloudEvents at the interface.** Events are stored in a CloudEvents 1.0 envelope; `GET /v1/audit` answers a reader's view of each (no `specversion`). Next: a route that serves the envelope itself, so the trail loads into a CloudEvents tool.
- **A nutrition standard for schools and hospitals.** Today the allergen rules are fixed, and a substitute whose formula or nutrients differ goes to the dietitian where a customer has one. Next: her standard written as rules, so that she is asked less.
- **New and seasonal products marked in the data, and recipes around a seasonal ingredient.** Today the product file has no such mark; the recipes are ten illustrative ones of ours, found by dish or by ingredient. With a mark in Valio Aimo's data, its own suggestion and the recipe choice can use it.
- **A scheduler for standing orders, and checks that run before the kitchen asks.** Today a stock-out, a suggestion or a drift is found when a request or a renewal arrives, and a person presses renew. The drift rule and the renewal already exist; a scheduler calls them on the cadence the standing order stores.
- **A price limit read from the sentence, an origin filter, and Finnish.** Today the reader refuses a money limit with the reason (limits are the buyer's settings), does not read a word such as "Finnish" as a filter, and says it reads English only; it asks rather than guesses. The typed request is where each new field goes.
- **A demo agent that orders alone over REST and MCP.** Today ordering alone is off in the four profiles and is shown on the shop page (Settings). Next: one demo identity whose buyer has it on.
- **Substitutes for more products.** Today a candidate whose name says it is another kind of product is never offered, so a product with no product type of ours often gets no substitute, and the answer says so: of the 1,163 recorded products 872 have a substitute that can be ordered (measured by the lane that built the rule, `AIMO/build/replan/STATUS.md`). Next: product types for more of the catalog.
- **What ran and what did not** for the hosting, the database and the manufacturer pages (Modal, Aiven, Context.dev) is in [docs/AWARDS.md](docs/AWARDS.md) and [docs/DEPLOY.md](docs/DEPLOY.md).

## Datasets, and how to refresh them

| What | Where | Refresh |
|---|---|---|
| Valio Aimo product file (17,546 products) and its JSON Schema | `valio_aimo_junction26_product_data.json`, `valio_aimo_junction26_product_data_schema.json` | Download from Valio Aimo's challenge API with the key from the Junction challenge page |
| Delivery reliability and carbon footprint | `valio_aimo_junction26_delivery_reliability.csv`, `valio_aimo_junction26_carbon_footprint.csv` | The same |
| Recorded price and availability answers of the mock | `fixtures/valio/<capture>/` (`manifest.json` holds the server's `timeNow`) | `scripts/capture_valio.py` (calls the mock; not run tonight) |
| Recorded manufacturer pages for allergen doubts | `fixtures/evidence/` (13 pages) | `scripts/record_evidence.py` ([docs/CONTEXTDEV.md](docs/CONTEXTDEV.md)) |

To use a new recording, give it a new name and start with `TTA_REPLAY_CAPTURE=<name>`: the tests read the committed recordings by name.

The datasets and recorded answers are Valio Aimo's synthetic data, not covered by this repository's licence. Whether they may stay in a public repository is a question for Valio.

## Read more

| Document | What it holds |
|---|---|
| [AIMO/COVERAGE.md](AIMO/COVERAGE.md) | The brief's items and the judging criteria, each with what answers it and how it is checked |
| [AIMO/SPEC.md](AIMO/SPEC.md) | The contract: interface, data shapes, states, rules |
| [docs/STANDARDS.md](docs/STANDARDS.md) | Each open standard we use, where we depart from it, and the next steps toward production |
| [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) | Every assumption and threshold, labelled ours, with its value and where it lives (also served at `/assumptions`) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The packages and the ports |
| [AIMO/WALKTHROUGH.md](AIMO/WALKTHROUGH.md) | What the gateway does, step by step |
| [docs/AWARDS.md](docs/AWARDS.md), [docs/CONTEXTDEV.md](docs/CONTEXTDEV.md), [docs/AIVEN.md](docs/AIVEN.md), [docs/DEPLOY.md](docs/DEPLOY.md) | The technology awards: what ran and what did not; deploying |
| [docs/DEMO.md](docs/DEMO.md), [docs/PITCH.md](docs/PITCH.md) | The demo script on `/shop`, with every scenario's figures at both clocks; the pitch |
| [AIMO/CHALLENGE.md](AIMO/CHALLENGE.md) | The challenge and its judging criteria, verbatim |
| [AIMO/FINDINGS.md](AIMO/FINDINGS.md) | Facts about the mock API and the data, from the first days |

## Licence

MIT, see [LICENSE](LICENSE). The Valio Aimo datasets and recorded API answers are not ours and are not covered by it.

---

## Hackathon notes

The original README of this repository, kept as it was:

# junction
