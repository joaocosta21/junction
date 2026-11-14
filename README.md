# Trusted Trade Agents

- **What it is.** A gateway that makes a food-service wholesaler, Valio Aimo, readable by a buyer's purchasing agent: the agent looks up products, gets an offer at fixed prices, and prepares an order that a person confirms.
- **Not a chatbot.** Valio's brief: "This is not about replacing today's e-commerce UI with a chatbot. It is about defining how a European food-service wholesaler can be safely and openly readable by autonomous agents". The product is a typed interface (REST with OpenAPI 3.1, and the Model Context Protocol) with rules, not a conversation.
- **What an agent can trust.** Every offer line says, statement by statement (price, quantity, delivery date, allergens, origin), whether Valio's data confirms it; every product left out says why; every offer and order record is signed by the gateway.
- **Who decides.** Fixed rules no buyer can switch off, plus each buyer's own limits. By default every order waits for a person; ordering alone is a buyer setting, off in all four demo customers.
- **What is logged.** Every step goes to a hash-chained audit trail, in plain sentences, with one view for the buyer and one for Valio Aimo.

Built at Junction 2026 for Valio Aimo's challenge "Trusted Trade Agents", against Valio Aimo's mock API. Where each judging criterion is answered, with the proof for each: [AIMO/COVERAGE.md](AIMO/COVERAGE.md).

This page describes commit `c2106fe` (Sat 14 Nov 2026, evening), run locally in replay. The public link, https://joaocostared--trusted-trade-agents.us-east.modal.run, was last deployed from an earlier commit (`8163d5d`, by the build log) and **has not been redeployed with tonight's code**; it was not called for this page ([docs/DEPLOY.md](docs/DEPLOY.md)).

## The flow

```
request ──► lookup ──► offer ──► rules ──► order prepared ──► a person confirms
(typed, or   (catalog +  (options, a    (fixed rules   (recorded, waiting,   (or rejects; an agent's
 a sentence   price and   status per     F-01 to F-12   signed by the          token cannot)
 read by      stock)      statement,     + the buyer's  gateway)
 fixed rules)             every          rules P-01
                          exclusion      to P-09)          every step ──► audit trail (buyer's view, Valio Aimo's view)
                          with a reason)
```

One run, measured offline on this commit, in replay of the recording (769 products, recorded Sat 14 Nov 2026 02:52 Helsinki), at the recording's clock:

- **Harbourside Hotel, the brief's own sentence: "I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability."**
  - Option 1, "Best confirmed option (partial fill)": two confirmed milks cover 435 L of the 1,000 L, €1,083.39 before tax. It goes to the purchasing manager under two of the hotel's rules: P-01 (an order above the hotel's €750 limit) and P-03 (an option that covers less than 90% of the quantity).
  - Option 2, "Alternative: quantity not confirmed": one milk for the whole 1,000 L, €1,010.00, whose stock Valio does not confirm. Fixed rule F-01 sends it to the purchasing manager: a product whose quantity Valio Aimo does not confirm always goes to a person.
  - The offer says that coffee milk was left out and how to ask for it. Valio Aimo, asked on 14 Nov whether a buyer who asks for milk accepts milk for coffee, answered "no be explicit".
  - Placing option 1 answers `201` with the order in state `PENDING_APPROVAL`. Nothing is ordered until a person confirms.
- In the recording no more lactose-free milk has confirmed stock, so 1,000 L cannot be covered with confirmed products. That is the scenario, not a fault: the agent offers what is confirmed, names the unconfirmed product as an alternative, and asks a person.

The other demo scenarios (the allergy ward, a substitute, the customer's pattern, the formula, the dietitian) are in [AIMO/COVERAGE.md](AIMO/COVERAGE.md) and [AIMO/WALKTHROUGH.md](AIMO/WALKTHROUGH.md), each with how it was checked.

## Who reads a request

- A request arrives **typed** (`POST /v1/offers`, the MCP tool `get_offer`) or as a **sentence** (`POST /v1/requests/parse`, the pages).
- A sentence is read by **fixed rules** (`src/tta/agent/rules_reader.py`): quantity and unit, product type or product number, claims such as lactose-free, excluded allergens, the day, "confirmed only", a preference. What the rules cannot read is not guessed: the answer is a question for the person (status 422, with `question`, `not_read`, `read_by`).
- With no model key, a sentence the repository holds a recording for (11 files in `fixtures/agent/`, some recorded from a model on 14 Nov, some written by hand) is answered from that recording, and the answer says so. The brief's sentence above is one: its reading says `hand-built`.
- The code also holds a reader that calls Google's Gemini. It runs only when the operator sets `GEMINI_API_KEY`. **No model was called in tonight's build or tests, and we do not enter Google's award.** To run with no model, start with `GEMINI_API_KEY=` empty. Note for whoever deploys: `deploy/modal_app.py` passes the key to the public link when the deploying machine has one.
- Whoever reads, deterministic code decides every price, quantity, allergen status and verdict.

## The four customers

All four are ours and **synthetic**: names, people, limits and eight weeks of order history are made up for the demonstration and marked `synthetic` (`src/tta/customers/data/`, `src/tta/policy/profiles/`). The mock has no customers, limits or order history.

| Customer | Limit per order / per day (before tax) | Its own rules | Who signs |
|---|---|---|---|
| Harbourside Hotel (`hotel-kitchen`) | €750 / €3,000 | 90% of the quantity covered; a substitute from the same category needs no extra approval | Hanna Laine (purchasing), Mikko Saari (finance), Leena Koski (dietitian) |
| City Hospital, Ward 4 (`allergy-ward`) | €500 / €1,500 | No milk, no gluten, strict; confirmed data only; every substitute to a person | Jussi Nieminen, Anna Virta, Sari Lehto |
| Kilo School (`school-kitchen`) | €250 / €800 | No tree nuts, peanuts or sesame, strict; only substitutes Valio Aimo lists | Päivi Korhonen, Tuomas Aho, Riikka Mäkelä |
| Kallio Bakery (`bakery-cafe`) | €300 / €1,000 | The formula matters on every line; every substitute to a person | Marko Heikkinen, the owner, holds every role |

## The rules, in short

`GET /v1/authority` returns every rule in words for the caller's customer. The contract is [AIMO/SPEC.md](AIMO/SPEC.md).

- **Fixed rules F-01 to F-12** hold whatever a buyer sets. Examples: F-01, a product whose quantity Valio Aimo does not confirm always goes to the purchasing manager; F-02, a product that declares an allergen the buyer excludes can never be ordered, even with approval; F-06, an agent can never approve an order, its own included; F-11, where the formula matters, a substitute whose formula differs or cannot be compared goes to the purchasing manager; F-12, a substitute that is a last resort goes to the purchasing manager.
- **F-10, the agent prepares the order and a person confirms it**, is driven by the buyer's setting `auto_order_enabled`, off in all four profiles. Switched on, the agent orders alone only when no rule asks for a person and every statement of every line is confirmed. Valio Aimo, 14 Nov: "for now deactivate automatic order", and of ordering alone as a setting, "after and if you are 100% sure yes".
- **The buyer's rules P-01 to P-09**: spend per order and per day, minimum cover, allergens to the dietitian, substitutes, products sold by weight, deposits, standing-order drift, and what a preference may cost.

## Run it locally, in replay

Python 3.13 is required. From the repository root:

```bash
python3.13 -m venv .venv && .venv/bin/pip install -e ".[dev]"
GEMINI_API_KEY= TTA_ENV=demo TTA_MODE=replay .venv/bin/python -m uvicorn --factory tta.api:create_app
# then open http://127.0.0.1:8000/shop
```

- **`TTA_ENV` must be `dev` or `demo`.** Unset means `prod`: no demonstration token, no page, and no start without `TTA_TOKENS`.
- **Replay makes no outside call.** Prices and stock come from `fixtures/valio/2026-11-14-demo/`, and the clock is pinned to the recording's instant. `TTA_DEMO_CLOCK=2026-11-12T14:15:00+02:00` sets the demo clock instead (replay only; an instant we chose, since Valio's test data is static). `GET /healthz` says which clock is in force; the audit trail always keeps the real time.
- **Two kinds of order book.** On the pages each browser has its own book in memory. REST and MCP share one book in `var/tta.sqlite3`, where the day's spend adds up across runs; set `TTA_DB_PATH` to a new file to start empty. With `DATABASE_URL` set the shared book uses PostgreSQL ([docs/AIVEN.md](docs/AIVEN.md)).
- **Signing.** With no `TTA_SIGNING_KEY`, offers and orders are signed with a demo key generated at start, and every `proof` says so.

A first call, with a demonstration token (public by design, listed in `src/tta/api/demo_tokens.yaml`; 15 identities):

```bash
curl -s http://127.0.0.1:8000/.well-known/api-catalog
curl -s -H "Authorization: Bearer demo-agent-allergy-ward" http://127.0.0.1:8000/v1/authority
```

What is served:

| Path | What | Who |
|---|---|---|
| `/.well-known/api-catalog`, `/llms.txt` | Every way in, for an agent that knows only the address | Anyone |
| `/openapi.json`, `/docs`, `/redoc` | Generated OpenAPI 3.1 | Anyone |
| `/v1/schemas` | JSON Schema 2020-12 of 96 contract models | Anyone |
| `/.well-known/jwks.json` | The public key behind every `proof` | Anyone |
| `/healthz` | Mode, the clock in force, the store, the signing key, the head of the audit chain | Anyone |
| `/v1/...` | REST: authority, product search, substitutes, offers, orders, approvals, audit, customers, menus, standing orders, reading a sentence | Bearer token |
| `/mcp/` | The same service as 13 MCP tools; none approves an order | Bearer token |
| `/shop`, `/`, `/approvals`, `/kitchen`, `/menu`, `/standing-orders`, `/assumptions` | Demonstration pages, an order book per browser | `dev` and `demo` only |

The flow over REST: `GET /v1/authority` → `POST /v1/offers` → `POST /v1/orders` with an `Idempotency-Key` header → `GET /v1/orders/{id}` and `GET /v1/audit`. A person decides at `POST /v1/approvals/{id}/decision` with a person's token.

## Run the tests

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```

The tests call no outside service: they run on the recordings and on fakes. One package at a time: `.venv/bin/python -m pytest tests/offers -q`. The whole suite was last run in one piece by the build on commit `db4c035` (earlier this evening); on this commit each lane ran its own folders (`AIMO/build/replan/STATUS.md`).

## Limits, and what is synthetic

- **"Ordered" means recorded in this gateway's order book.** The mock has no order endpoint, by design; no order reaches Valio and the record commits nobody. No payment is taken.
- **Synthetic, ours:** the four customers, their people, limits and order history; the recipe table; every threshold. Each is listed with its value in [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md).
- **Valio Aimo's, not ours:** the product file (17,546 products), the reliability and carbon files, and the recorded price and availability answers. Replay holds 769 of the 17,546 products: a product outside the recording is excluded as "not in the recording", never as unavailable in Valio's name.
- **Signed by the gateway, not by Valio Aimo.** A supplier's own signature on price, stock and origin is a next step ([docs/STANDARDS.md](docs/STANDARDS.md)).
- **Limits per minute on the demonstration** (ours): one visitor 20 offers, 20 orders and 15 readings; one address 60 of each; all callers 240 of each. A buyer holds at most 20 standing orders, and nothing deletes one.
- **Suggestions.** The functions that suggest a forgotten item, a trend, a cheaper product of the same formula and Valio Aimo's own related product are built and tested (`src/tta/suggestions/`); on this commit the offer route does not fill `Offer.suggestions` yet.
- **Not run by anyone:** the pages in a real browser; a redeploy with tonight's code; the new SQL view for Valio against PostgreSQL; the Modal jobs; a third-party MCP host ([docs/AWARDS.md](docs/AWARDS.md), [docs/DEPLOY.md](docs/DEPLOY.md)).

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
| [AIMO/WALKTHROUGH.md](AIMO/WALKTHROUGH.md) | What the gateway does, step by step, re-measured on this commit |
| [docs/AWARDS.md](docs/AWARDS.md), [docs/CONTEXTDEV.md](docs/CONTEXTDEV.md), [docs/AIVEN.md](docs/AIVEN.md), [docs/DEPLOY.md](docs/DEPLOY.md) | The technology awards: what ran and what did not; deploying |
| [docs/DEMO.md](docs/DEMO.md), [docs/PITCH.md](docs/PITCH.md) | The demo script and the pitch (rewritten after the scenarios are re-measured) |
| [AIMO/CHALLENGE.md](AIMO/CHALLENGE.md) | The challenge and its judging criteria, verbatim |
| [AIMO/FINDINGS.md](AIMO/FINDINGS.md) | Facts about the mock API and the data, from the first days |

## Licence

MIT, see [LICENSE](LICENSE). The Valio Aimo datasets and recorded API answers are not ours and are not covered by it.

---

## Hackathon notes

The original README of this repository, kept as it was:

# junction
