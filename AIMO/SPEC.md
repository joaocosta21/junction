# AIMO — build specification

The contract the code follows. First written on 14 Nov for the overnight build; **brought back in line with the code on Sat 14 Nov 2026 (evening), and again on Sun 15 Nov 2026 at about 03:00 after the night's fixes**: the statements below were checked against the code, read or run offline in replay. Facts about the mock API and the data are in [FINDINGS.md](FINDINGS.md) and [docs/](docs/); this file does not repeat them.

How figures are labelled here: **catalog** = counted over the whole product file (17,546 products); **recording** = the recorded copy of Valio Aimo's answers used in replay (`fixtures/valio/2026-11-14-demo`, 769 products, recorded Sat 14 Nov 2026 at 02:52 Helsinki time; replay also answers for the 394 baking products of `2026-11-14-baking`, recorded the same Saturday at 21:12: 1,163 products in all); anything else is called a sample. Demo figures are from the recording at its own clock unless a line says otherwise.

**Rule for every line of code: name the judging criterion it scores on** ([CHALLENGE.md](CHALLENGE.md)). The weights are 30% end-to-end flow · 20% precise match to the request · 20% autonomy and controls · 15% exceptions · 15% openness and path to production.

---

## 1. What we build

A gateway between a buyer's purchasing agent and Valio Aimo's price and availability API. It is an interface for agents, not a chat: the brief says "This is not about replacing today's e-commerce UI with a chatbot."

```
buyer's agent ──► gateway ──► Valio mock API (price, availability), or its recorded copy in replay
 (any agent,       │  ├─ catalog (product file, local)
  REST or MCP)     │  ├─ response logic (six availability states, allergens, substitutes, the formula)
                   │  ├─ policy (fixed rules + buyer profile)  ──► AUTO · APPROVAL · BLOCK
                   │  ├─ order book and approvals              ──► a person confirms
                   │  ├─ audit trail (one sentence per decision, two readers)
                   │  └─ signature on every offer and order record the gateway answers
                   └─ same functions exposed as REST (OpenAPI 3.1) and as 13 MCP tools
```

**One flow, every scenario:** request + buyer identity → lookup → offer (options, a status per statement, exclusions with reasons, the policy verdict for each option) → the rules → order prepared → a person confirms (or, only where the buyer switched ordering alone on and every statement is confirmed, the agent orders) → audit record.

**A model may read a sentence; fixed rules check it, stand in for it, and decide everything else.** When a key is set (`GEMINI_API_KEY`, or an OpenAI-compatible endpoint through the `TTA_AGENT_*` settings) the model is asked first. The gateway checks every reading against the text and refuses one that does not match; it never corrects it. When no model answers, or none is configured, a recording of that sentence is served if there is one, else the fixed rules read it (`src/tta/agent/rules_reader.py`); a text they cannot read is answered with a question, never a guess (§11). Every answer says who read it. Whoever reads, no model decides what may be ordered. What reads sentences on a given deployment is reported by `GET /healthz` → `agent_reader`. The figures in this file were measured with no key set, so their sentences were read by the fixed rules or from a recording.

### Choices, each with its reason
| Choice | Reason |
|---|---|
| Python 3.13, FastAPI, Pydantic v2 | The team knows Python; FastAPI generates OpenAPI 3.1 from the typed models, so the published interface cannot drift from the code (15%) |
| Code in `src/tta/`, tests in `tests/`, virtualenv `.venv`, `pip` | A root-level `aimo/` package would collide with `AIMO/` on macOS. `tta` = Trusted Trade Agents |
| Server-rendered pages (Jinja2 and a little plain JavaScript); the shop page is static files that call `/shop/api/*` | No Node build step; one process to deploy |
| SQLite through a small repository interface | No service to provision. The shared order book and audit trail use PostgreSQL behind the same interface when `DATABASE_URL` is set (in schema `TTA_DB_SCHEMA` when that is set), and fall back to SQLite when the database cannot be reached at start, which `/healthz` then names (`docs/AIVEN.md`) |
| A fixed-rules reader for free text, which also checks a model's reading and stands in for it | It is deterministic and tested; it asks when it is not sure (Valio Aimo, 14 Nov: flag it and ask for the person's input). The typed request can always be posted directly |
| **No model decides a price, a quantity, an allergen status or a verdict** | Those come from deterministic code that can be tested and audited (20% controls). This holds whoever reads the sentence, a model included |
| Policy as data (YAML): fixed rules plus one profile per buyer; one rule (F-10) in code | The guardrails can be read and changed without touching code. F-10 fires only when nothing else asks for a person, which a `when` of the rules file cannot say |
| Audit events in a CloudEvents 1.0 envelope, hash-chained | A documented open format, and a log that shows tampering (20% controls, 15% openness) |
| Offers and order records signed by the gateway (Ed25519, detached JWS over canonical JSON) | What the gateway said can be checked later. It is the gateway's signature, with a demo key unless one is set; it is not Valio Aimo's signature (§8) |
| Errors as RFC 9457 problem details; `Idempotency-Key` on order placement | Agents retry; a retry must never place a second order |
| Replay mode with a pinned clock | The demo survives the mock being down or every cut-off having passed |
| Every port is synchronous | One style everywhere; FastAPI runs the routes in its thread pool |

RFC numbers in this file are cited from the implementers' knowledge, as the code cites them; `docs/STANDARDS.md` says how far each was checked.

### Layout
```
pyproject.toml · LICENSE (MIT) · README.md
src/tta/
  contracts/     shared Pydantic models, typed errors, ports — the interface between the packages
  config.py      settings from the environment
  valio/         client for the mock API, recorder, replay, call budget, clock
  catalog/       product file loader, search, product types (product_types.yaml), pack size, lot step,
                 flavour, use and "is a drink" read from names (kinds.py)
  allergens/     GS1 codes and families, buyer exclusion rule, ingredient list, substitution rule, claims
  availability/  the six states, verification status per statement
  policy/        rules.yaml (fixed and profile rules), profiles/*.yaml (four buyers), engine, F-10 in code
  customers/     the four demo customers (data/*.yaml, synthetic): people, usual products, past orders
  suggestions/   suggestions from a customer's history or the catalog, each checked like any product
  store/         SQLite repository; PostgreSQL repository and its SQL (sql/001…005)
  audit/         events, hash chain, sentences, the buyer's and Valio Aimo's views
  offers/        candidates → options, ranking, combining, substitutes, the formula comparison, re-check
  orders/        order states, approvals, idempotency, the day's spend
  evidence/      what a manufacturer's web page says about an allergen Valio's data leaves open (recorded pages)
  menus/         recipe table, menu needs, the menu planner (recipe logic, F-09)
  standing/      standing orders: set up, history, renewal (P-08)
  api/           FastAPI app, routes, identity, limits, MCP surface, discovery documents, signing
  agent/         the fixed-rules reader; recorded readings; the model reader (Gemini or an OpenAI-compatible endpoint), its check against the text, and the agent loop
  ui/            pages, the shop page and its back end (/shop/api/*)
deploy/          modal_app.py, check.py, evidence_batch.py, witness.py
scripts/         capture_valio.py, record_evidence.py, aiven_proof.py
fixtures/        valio/ (recorded answers of the mock), agent/ (recorded readings), evidence/ (recorded pages)
tests/
```
`AIMO/catalog_search.py` and `AIMO/policy/` were the starting point for `catalog/` and `policy/` and are kept unchanged.

---

## 2. Interface

Versioned paths are under `/v1`. Every response is JSON; every timestamp is ISO 8601 with offset; currency is ISO 4217 (`EUR`); allergens are GS1 codes; money and quantities are computed with `Decimal` and serialised as JSON numbers (money 2 decimals, quantities 3).

The list below is the generated OpenAPI document of the committed code (29 operations), nothing more.

| Method and path | Who | Purpose | Brief |
|---|---|---|---|
| `GET /v1/authority` | agent | The caller's buyer profile and every rule in plain words: what it may decide alone | Core 3 |
| `POST /v1/products/search` | agent | Search the catalog: product type, name terms, claims, labels, category, product ids. With `price_and_availability=true` (and `needed_by`) each product, at most 20 a call, also carries the fixed price and what Valio Aimo's data says is available, judged as an offer line of the same buyer would be: one lookup, one audit event. A look, not an offer | Core 1 |
| `GET /v1/products/{product_id}` | agent | One product with its allergen statements and claims; the same flag adds its price and availability | Core 1 |
| `POST /v1/products/{product_id}/substitutes` | agent | Ranked substitutes, each with pass or fail, whether it is a like-for-like replacement, and the reason | Optional: substitution |
| `POST /v1/offers` | agent | Typed request → offer from the price and availability Valio's data states now. `201` with a `Location` header | Core 1, Core 2 |
| `GET /v1/offers/{offer_id}` | agent | The stored offer | Core 2 |
| `POST /v1/orders` | agent | Order one option of an offer: it waits for a person unless the buyer allows the agent to order alone and every statement is confirmed (§7). Needs `Idempotency-Key`. `201` with `Location` | Core 2, Core 3 |
| `GET /v1/orders`, `GET /v1/orders/{order_id}` | agent, approver | The buyer's orders; one order with status, decision and approvals | Core 2 |
| `GET /v1/approvals` | approver | The approval queue of the caller's buyer | Core 3 |
| `POST /v1/approvals/{approval_id}/decision` | approver | Approve (optionally choosing another option of the same offer) or reject. An agent token is refused with 403 (F-06) | Core 3 |
| `GET /v1/audit?order_id=&reader=buyer\|supplier` | agent, approver, supplier | The audit trail as one reader sees it | Audit trail |
| `GET /v1/customers`, `GET /v1/customers/{customer_id}` | agent, approver | The caller's own customer: who orders, who holds each role, usual products, past orders, limits. All synthetic and said so. Valio Aimo's token gets 403 | 20% match |
| `POST /v1/requests/parse` | agent | Free text → typed request. Three headers say who read it and what the reader says of its reading: `TTA-Read-By`, `TTA-Reading-Source`, `TTA-Reading-Sentence`. A text that is not read is `422` with a question (§11) | 20% match |
| `POST /v1/requests/read-image` | agent | A photo of an order list → typed request. Needs a model: with no key only the one recorded demo photo is answered, from its hand-written recording | 20% match |
| `POST /v1/agent/run` | demo | Runs a buyer agent on a pasted request and returns its trace. With no key: a recorded run, or a fixed run made by the rules, and the report says which | 30% |
| `GET /v1/menus/recipes` | agent | The recipes a menu can be planned from (ours, illustrative) | Optional: substitution |
| `POST /v1/menus/plan` | agent | Dishes × servings, minus the kitchen's stock → one offer; an ingredient that cannot be had is replaced by its role's alternative (F-09) | Optional: substitution |
| `POST /v1/standing-orders`, `GET /v1/standing-orders` | agent | Set up a recurring order; list the buyer's standing orders (at most 20 per buyer) | Valio scenario "standing order drift detection" |
| `GET /v1/standing-orders/{standing_order_id}` | agent | One standing order and its renewals | same |
| `POST /v1/standing-orders/{standing_order_id}/renew` | agent | Renew with this week's quantities: an offer, the drift check (P-08), then the order through the normal order step | same |
| `GET /v1/insights` | supplier | Valio Aimo's back office of the shared order book, counted from its own view of the audit trail: demand, suggestions shown and accepted, sales not made. An agent or an approver gets 403 | Audit trail |
| `GET /v1/schemas` | anyone | JSON Schema of every contract model (98, counted from the running gateway on 15 Nov), each naming its dialect in `$schema` (2020-12) | 15% |
| `GET /openapi.json`, `/docs`, `/redoc` | anyone | Generated OpenAPI 3.1 | 15% |
| `GET /.well-known/api-catalog` (and `HEAD`) | anyone | Where the API, its description, its schemas and the MCP endpoint are (the code cites RFC 9727) | 15% |
| `GET /llms.txt` | anyone | What the gateway is and the order of calls, as plain text for a language model | 15% |
| `GET /.well-known/jwks.json` | anyone | The public key offers and orders are signed with | Trust protocol |
| `GET /healthz` | anyone | What is running: mode, the clock and its basis, the store, the audit head, whether the signing key is a demo key. It verifies the whole audit chain of the shared order book (at most once every 30 seconds) and answers `degraded`, naming the first event that does not verify | 15% |

- **MCP** (`/mcp/`): 13 tools that call the same service functions as the REST routes: `get_authority`, `search_products`, `get_product`, `find_substitutes`, `get_offer`, `place_order`, `get_order`, `get_audit`, `get_customer`, `plan_menu`, `set_up_standing_order`, `renew_standing_order`, `list_standing_orders`. **No tool lists or decides an approval.** An argument a tool does not know is refused, as REST refuses an unknown field. No logic lives in a transport. A request whose `Origin` header names an origin the server does not allow is refused with 403 (`TTA_MCP_ALLOWED_ORIGINS`); a request with no `Origin` passes.
- **Identity:** every call carries `Authorization: Bearer <token>`. A token maps to one identity: an **agent** bound to one buyer profile, an **approver** with one or more roles, or the **supplier** reader. The buyer profile is never a request field: an agent cannot choose its own authority. Demo tokens (11 identities: 4 agents, 6 approvers, the supplier; `src/tta/api/demo_tokens.yaml`) are public by design and load only when `TTA_ENV` is `dev` or `demo`. **One person confirms:** the hotel's purchasing manager and the bakery's owner hold every role of their customer; the ward and the school have one second person, the dietitian. No customer has a separate finance signer. **That an agent cannot approve holds over REST and MCP, where the token says who calls.** The demo pages (§12) have no login.
- **Errors:** RFC 9457 `application/problem+json` with a stable `type`: `invalid-request`, `not-authorised`, `unknown-product`, `not-found` (an id nobody issued, or another buyer's), `offer-expired`, `offer-stale`, `policy-blocked`, `supplier-unavailable`, `rate-limited`. Each has one typed error in `src/tta/contracts/errors.py`.
- **Idempotency:** `POST /v1/orders` requires an `Idempotency-Key` header; without it the answer is `400`. The same key returns the first result; the same key with another offer or option is refused.
- **Rate limits** (ours, illustrative, per minute, in one process's memory; `src/tta/api/limits.py`): one visitor 60 lookups (offers, substitute searches, product searches, reads of one product and of the audit trail), 20 orders and decisions, 15 request readings and agent runs; one address 60 of each; all callers together 240 of each. On REST and MCP a visitor is an address, so callers behind one Wi-Fi share its 60 lookups. Bodies up to 64 KB. The pages keep at most 1,000 order books, and one address opens at most 400 new ones in 10 minutes (`src/tta/api/sandbox.py`).

---

## 3. Request → candidates

### The typed request
| Field | Type | Meaning |
|---|---|---|
| `needed_by` | date, optional | The date the goods are needed |
| `require_confirmed` | bool, default false | Offer only options in which every statement is confirmed |
| `prefer` | `PRICE` · `EARLIEST` · `RELIABILITY` · `LOWER_CARBON`, default `PRICE` | What ranks confirmed products once every constraint is met (§5). `PRICE` is the brief's "based on price and availability" |
| `standing_order_id` | string, optional | The standing order this request renews; its history is checked (P-08). It can only add a check |
| `lines[]` | 1 to 20 (5 where `TTA_ENV` is `dev` or `demo`) | One per product asked for |
| `lines[].text` | string | The buyer's own words, kept for the audit trail |
| `lines[].product_type` | string, optional | A key of the product-type table, e.g. `milk`, `coffee_milk`, `plant_drink`, `beef_chuck` |
| `lines[].product_ids` | list, optional | Explicit products ("this product", named by id) |
| `lines[].name_terms` | list | Words that must appear in the product name (English or Finnish) |
| `lines[].required_claims` | list | `nutritionalClaim` codes that must be present, e.g. `FREE_FROM_LACTOSE` |
| `lines[].required_labels` | list | Certificate labels (`packagingMarkedLabel` codes other than the three storage temperatures, e.g. `EU_ORGANIC_FARMING`) every product must carry |
| `lines[].quantity`, `lines[].unit` | decimal, `L` · `KG` · `UNIT` | `UNIT` means sales units |
| `lines[].exclude_allergens` | list of GS1 codes | Added to the profile's exclusions; a request can add exclusions and can never remove one |
| `lines[].allergen_strictness` | `STRICT` · `DECLARED_ONLY`, optional | How the exclusions are read (§6). **With no rule here and none in the profile, an exclusion reads `STRICT`**, the safe reading, and the offer says so in a note. A request can make the rule stricter, never looser |
| `lines[].keep_formula` | bool, optional | The formula matters for this line: a substitute must keep it or it goes to a person (F-11). It can only add the check: false or absent leaves the profile's own setting (`formula_matters`) in force |
| `lines[].pack` | `ANY` · `BULK` · `PORTION` | Defaults to `BULK` for `L` and `KG`, `ANY` for `UNIT`. See the portion-pack rule |
| `lines[].stands_in_for`, `lines[].stands_in_role` | string, optional | Set by the menu planner when recipe logic chose another product type: the recipe's type this line replaces, and the job it does in the dish (F-09) |

### From a line to candidate products
1. **Explicit ids** are used as given, after a check against the local catalog (an unknown id is `unknown-product`; the availability endpoint cannot tell it from an undeliverable product).
2. **Product type:** `catalog/product_types.yaml` maps a key to category codes, name terms and claims. The table is ours: 32 types read from product names (catalog), not a complete taxonomy. A type names one kind of product: milk for coffee is `coffee_milk` (4 products), not `milk` (74) — Valio Aimo, asked on 14 Nov whether a buyer who asks for milk accepts it: "no be explicit". An offer for milk carries a note that coffee milk was left out and how to ask for it.
3. **No product type:** search product names (English, then Finnish) for every name term, and keep the categories that hold most of the matches.
4. **Claims:** every `required_claims` code must be on the product. A claim is never read as an allergen statement. A product whose own allergen data contradicts a required claim is excluded as `CLAIM_CONTRADICTED`.
5. **Pack size** in litres or kg per sales unit: `catalogPrice ÷ comparisonPrice` from the price answer, then `unitConversions` when the unit is a real volume or weight, then the product name. If none gives a value the product is excluded with `PACK_SIZE_UNKNOWN`.
6. **Portion-pack rule:** for a `BULK` line, single-serve packs are excluded with `PORTION_PACK` (an inner unit of 5 cl or 50 g or less, such as `463203`, 100 × 2 cl). A `PORTION` line keeps only those.
7. **Quantity in sales units:** round up to the product's `allowedLotSize` step with `Decimal`. Price and quantity follow the sales unit on the API line, not the one in the product file.

---

## 4. Availability and what can be trusted

### The six states
Evaluated in this order, against the `timeNow` of the answer (in replay: the recording's own instant, or the demo clock when `TTA_DEMO_CLOCK` is set, §10):

| State | Condition | Role in an offer |
|---|---|---|
| `BLOCKED` | `salesBlock` true | Excluded; triggers substitution when the product was asked for by id |
| `NOT_DELIVERABLE` | no schedule line | Same |
| `OUT_OF_STOCK` | `availableAmount` 0 | Same |
| `CUTOFF_PASSED` | `closingTime` earlier than now | Excluded from every request, dated or not, with the reason. The API gives one schedule line per product, so no later date can be promised instead |
| `QUANTITY_NOT_CONFIRMED` | `availableAmount` ≥ 999,999 (Terminal or Stock) | Never the suggestion. Offered as a labelled alternative. Ordering it always needs a person (F-01). The value is never used in arithmetic |
| `CONFIRMED` | otherwise | May be the first option |

A product with a schedule line whose `availableDate` is later than `needed_by` is excluded with `LATE_FOR_NEEDED_BY`. When nothing can arrive by the date asked, the offer answers with the earliest date as labelled alternatives ("Alternative: delivered Monday 16 Nov, 3 days later than asked"); each goes to a person, who accepts the later date (F-07), also with ordering alone on (§5).

### Verification status — our answer to the trust protocol
Every offer line states, for each of five statements, whether Valio's data confirms it:

| Statement | `CONFIRMED` | `UNKNOWN` | `RULED_OUT` |
|---|---|---|---|
| `price` | a price was returned and `validTo` is in the future | no usable price | — |
| `quantity` | state `CONFIRMED` and the amount covers the line | `QUANTITY_NOT_CONFIRMED` | out of stock, not deliverable, blocked |
| `delivery_date` | cut-off open and `availableDate` on or before `needed_by` | no `needed_by` given | cut-off passed, or later than `needed_by` |
| `allergens` | every excluded allergen has an explicit statement | any excluded allergen has `MAY_CONTAIN`, `UNDECLARED` or no statement | an excluded allergen is declared `CONTAINS` |
| `origin` | the product file states it | absent | — |

**What sends an order to a person because of a statement:** `price` and `quantity` always (the rule on an unconfirmed price or a ruled-out date, F-07, and the rule on an unconfirmed quantity, F-01); `delivery_date` when the request gives `needed_by` (F-07); `allergens` through the outcome of the allergen rule (F-02 blocks a declared allergen, P-04 sends a doubt to the dietitian). A passed cut-off is a state, not a statement: it excludes the product. `require_confirmed` (on the request or on the profile) is stricter: it keeps only lines whose statements are confirmed, the `allergens` statement included. A statement missing from a line is a missing fact (F-03).

**Ordering alone asks for more:** where the buyer has switched `auto_order_enabled` on, the agent orders alone only when no rule fires **and all five statements of every line are confirmed, origin and delivery date included** (F-10, §7; Valio Aimo, 14 Nov: "after and if you are 100% sure yes"). So a request with no date, or a product with no stated origin, is never ordered by the agent alone.

---

## 5. Building the offer

1. Candidates (§3) → one price call and one availability call for the narrowed set (up to 1,000 ids per call). A line whose confirmed stock falls short and is completed with a substitute (below) costs one more call of each: the brief's sentence makes 2 and 2.
2. Classify each candidate (§4) and run the allergen check (§6). Everything that drops out goes to `excluded[]` with a reason code and one sentence.
3. **Options, at most three (four with `CHEAPEST_CONFIRMED`), ranked by constraint fit, then verification status, then the request's preference, then price.** Four kinds (`OptionKind`); the title says what a person needs to know:

   | Kind | Title | What it is |
   |---|---|---|
   | `BEST_CONFIRMED` | "Best confirmed option", with " (partial fill)" when confirmed stock falls short; "Confirmed option ranked by delivery reliability" (or the other preference) when the preference's premium put it after the cheapest | Confirmed products only. Under `PRICE`, the cheapest single product that covers the whole quantity; if none does, the cheapest first until the quantity is covered. If confirmed stock still falls short, it says how much is missing |
   | `CHEAPEST_CONFIRMED` | "Cheapest confirmed option" | Only under a preference other than `PRICE`, when the price fill over the same confirmed stock picks other products and costs less. Both summaries say the difference in euros and what it buys |
   | `ALTERNATIVE_UNCONFIRMED` | "Alternative: quantity not confirmed" · "Alternative: allergen not ruled out" · "Alternative: quantity not confirmed, allergen not ruled out" · "Alternative: delivered <day>, <n> days later than asked" | A full structured option a person can pick. It says what is not confirmed about it. It ranks after every confirmed option; it is first only when there is no confirmed one. The later-date title is used when nothing can arrive by the date asked: the options are then for the earliest date in Valio Aimo's data |
   | `SUBSTITUTE` | "With a substitute for a product that cannot be supplied in full" · "With a substitute whose data rules out the allergen you exclude" · "Alternative: a substitute that does not keep the formula" (where the formula matters and the substitute does not keep it) · "Alternative: confirmed stock, completed with a substitute" | When the request named products by id and they cannot be supplied in full, or their data does not rule out an excluded allergen: the best substitute that passes §6. And, for a line asked by product type or by words, when confirmed stock falls short: the confirmed fill completed from confirmed stock of the nearest kind, the added product named as a substitute (`src/tta/offers/completing.py`); this option is listed after every other one. Every substitute that is not judged replaceable goes to a person (F-12) |

   - **The safe product first.** With an allergen excluded, the first option holds only products whose data rules it out; a product with a doubt is "Alternative: allergen not ruled out" and ranks after every safe option at any price, also under `DECLARED_ONLY`.
   - **A preference has a price.** An option ranked by a preference that costs more than 25% above the cheapest confirmed option comes second, and the gap is stated; a known delivery reliability under 90% ranks with an unknown one (both thresholds are ours, `src/tta/offers/preference.py`).
   - An unconfirmed product that costs no less than confirmed stock covering the line is not offered.
   - Plain "milk" fills with regular milk first; when none has confirmed stock (the case in the recording), a named lactose-free or low-lactose product is the first option and the offer says it is an alternative to regular milk.
4. Every option carries: its lines; totals (net, tax from `tax.taxRate`, gross; `excludes_deposits`); coverage (requested, covered, fill ratio); `valid_until` = the earliest price `validTo` and `closingTime` of its lines; **constraint checks** — one per thing the buyer asked for, each `MET`, `NOT_MET` or `UNVERIFIED` with a sentence; and **the policy verdict for that option** (§7), so the agent knows before ordering what happens.
   - **A total with a product sold by weight is an estimate**, written "about € …": "The total is an estimate: a product is sold by weight, and Valio Aimo invoices the weight delivered." (Valio Aimo, 14 Nov). The field is still called `totals.is_ceiling`; it means "estimate", not a ceiling.
5. The offer records where its data came from (`source`: `live` or `replay`), the `time_now` it was built against and the clock's basis (`time_basis`: `recording`, `supplier` or `demo_setting`).
6. **The comparison** (`OptionComparison`, `src/tta/offers/comparison.py`): each option states its earliest and latest delivery, the lowest delivery reliability, an estimated carbon total (amount × kg CO2e per kg, a litre counted as a kilogram), the labels every line carries, and how many lines have no value for each. A missing value is unknown, never 0. Reliability is known for 4,425 and carbon for 11,033 of the 17,546 products (catalog).
7. **`Offer.suggestions`**: a list of `Suggestion` records computed from the customer's past orders or the catalog (`src/tta/suggestions/`): at most three, one per kind, in the order forgotten item · usual product · usual quantity · cheaper product with the same formula · larger pack · quantity trend · (reorder due) · Valio Aimo's own suggestion of a related product (`FROM_SUPPLIER`, last, never more than one, and only with a stated benefit and enough confirmed stock). Each is checked like any product (allergen rule, claims, confirmed stock, formula) and carries `accept_request`, a new typed request: **a suggestion is in no option and no total and never adds itself to an order.** `POST /v1/offers` and the MCP tool `get_offer` answer the field for the four demo customers, in replay, from their synthetic order history; what was shown and what was held back is one audit event (`suggestions.shown`), and an accepted suggestion another (`suggestion.accepted`). Measured 15 Nov: the hotel's 100 L of lactose-free milk shows the forgotten cooking cream (`463797`, 10 L, €33.10) and no suggestion of Valio Aimo's; the bakery's cream request shows Valio Aimo's own (`473278`: "€1.48 a litre instead of €2.88").
8. **`Offer.proof`** (and `Order.proof`): the gateway's signature of the record (§8).

**Exclusion reason codes** (`ExclusionReason`, 16): `BLOCKED` · `NOT_DELIVERABLE` · `OUT_OF_STOCK` · `CUTOFF_PASSED` · `LATE_FOR_NEEDED_BY` · `ALLERGEN_DECLARED` · `ALLERGEN_NOT_STATED` (only under `require_confirmed`) · `CLAIM_CONTRADICTED` (the product's own allergen data contradicts a claim the request requires) · `PORTION_PACK` · `NOT_A_PORTION_PACK` (on a line that asks for portion packs) · `PACK_SIZE_UNKNOWN` · `PRICE_UNAVAILABLE` · `SUBSTITUTE_ADDS_ALLERGEN` · `QUANTITY_NOT_CONFIRMED` and `DELIVERY_DATE_NOT_CONFIRMED` (both only under `require_confirmed`) · `NOT_IN_RECORDING` (replay only: the recording has no answer for the product; never presented as Valio's statement; its price, quantity and delivery date read `UNKNOWN`. The recording holds 769 of the 17,546 products).

### Substitutes
- **Candidates:** the pairs Valio lists (249 pairs, catalog), then the products of the same 5-digit category, and nothing wider: a category number is opaque, and a shared prefix is a neighbouring shelf, not the same kind of product. Every candidate is re-checked for price and availability.
- **The order of the gates** (`src/tta/offers/substitutes.py`), first decides first:
  0. The allergen rule of §6. A candidate that fails is shown with its reason and can never be ordered (F-05).
  1. The dietary claims. A candidate that loses one is a **last resort**: held back while a candidate that keeps them all can be ordered.
  2. The same kind of product (our reading of product names, `src/tta/catalog/kinds.py`): another product type than the original, or a flavoured product for a plain one (and the reverse), is a last resort too. A pair Valio lists stays when only the type differs, after every candidate of the same type. Another use (made for coffee, whipping, cooking) and another flavour of an already flavoured product only order the candidates. Where no product type of ours says what the original is, or it is raw meat or fish, the name decides (`src/tta/catalog/kind_words.py`): a candidate whose name does not carry the original's kind words ("yolk", "brisket", "cocoa powder") is another product and leaves the ranking, so it is never an offer option (decision B65); a pair Valio lists stays, and says so.
  3. The formula (`src/tta/offers/formula.py`): the two ingredient lists compared with each other (a component one names and the other does not is a different formula), then six nutrients within 15% or 1 g (salt 0.25 g) and the same fat source; per 100 g is read with per 100 ml for drinks only. Tolerances are ours. It orders the candidates; it hides none.
  4. Listed by Valio, pack size closest, verification status, price.
- Each candidate carries one sentence that starts "Replaceable: …" or "Not a like-for-like replacement: …" with each reason (`replaceable`), the formula comparison (`formula`), `last_resort`, and what the buyer gives up (`gives_up`).
- **Dietary claims** are 8 codes (`DIETARY_CLAIMS`): `FREE_FROM_LACTOSE`, `LOW_LACTOSE`, `FREE_FROM_GLUTEN`, `FREE_FROM_WHEAT`, `FREE_FROM_EGGS`, `FREE_FROM_SOY`, `VEGAN`, `VEGETARIAN`. Losing any other claim is named in `gives_up` and fires no rule.
- **Confirmed like-for-like stock stands in before an unconfirmed product.** Where the formula matters (the request line's `keep_formula`, or the profile's `formula_matters`) and no formula-keeping substitute can be ordered, the product asked for (quantity not confirmed) is shown before a substitute that changes the formula, which is titled "Alternative: a substitute that does not keep the formula".
- A substitute sold in another sales unit is converted by content (100 cartons of 1 L become 10 cases of 10 L) and rounded up to the lot step.
- A stand-in for a product is looked for only on a line that names product ids. A product-type line gets a substitute in one case only: its confirmed stock falls short and the last option completes it from confirmed stock (above). The brief's sentence shows it: 1,000 L of lactose-free milk gets 435 L confirmed, and a third option that adds 565 L of lactose-free milk made for coffee (`463380`), named as a substitute, €2,580.64 before tax, for a person to decide (F-12, P-01).
- **The price of a substitute is bounded (rule P-05, decision B60, commit `fd4098b`):** a substitute that costs more than 25% above what the product it replaces would have cost, or whose price cannot be compared with it, goes to a person (the share is the buyer's where the profile sets one; 25% is ours). The offer line carries what the product asked for would have cost (`SubstituteInfo.original_net`). Measured at the hotel, both clocks: `475224` for `473609` costs €37.00 more (27%) and waits for a person under F-12 and P-05.
- The substitutes route judges each candidate by the buyer's own exclusion rule, confirmed-only included, as the buyer's offer does.

---

## 6. Allergen rules

Relations: `CONTAINS`, `MAY_CONTAIN`, `UNDECLARED` (group `allergen`) and `FREE_FROM` (group `nonAllergen`). `X99` is GS1's "Does not contain declaration obligatory allergens". A product with neither group has no statement; that is unknown, never safe. A `nutritionalClaim` is never an allergen statement: lactose-free milk still contains milk. Code families (for example the cereals under `AW`) are in [docs/SCHEMA-AND-CODES.md](docs/SCHEMA-AND-CODES.md).

**Buyer exclusion rule**, for each excluded allergen and its sub-codes:

| The product says | `STRICT` | `DECLARED_ONLY` |
|---|---|---|
| `FREE_FROM` | passes | passes |
| `CONTAINS` | rejected | rejected |
| `MAY_CONTAIN` | to a person (dietitian) | to a person (dietitian) |
| `UNDECLARED`, or no statement | to a person (dietitian) | passes the rule, shown as unverified, and still never the first option (§5) |

- An exclusion with no strictness on the request and none in the profile reads `STRICT` (§3).
- Conflicting statements on one product: the least safe one counts.
- **The product's own ingredient list counts as a statement.** When `keyIngredients` (English, else Finnish) names an excluded allergen or a member of its family, or says "may contain" it, while the declaration says `FREE_FROM`, `UNDECLARED` or nothing, the finding is `MAY_CONTAIN`: the product goes to a dietitian, under either strictness, with a sentence quoting both (found on `465793`, an almond drink declared free from tree nuts). A free-from wording is not a mention.
- A "no gluten" exclusion (`AW`) and a product that declares oats (`GO`): to a person, whatever else it states.
- **Evidence for the dietitian.** On an allergen doubt (P-04) the approval can carry what the manufacturer's web page says, from recorded pages in `fixtures/evidence/`, labelled as not Valio's data. A page can add a doubt and never removes one; it changes no status and no verdict (`docs/CONTEXTDEV.md`).

**Substitution rule:** a substitute must not declare (`CONTAINS` or `MAY_CONTAIN`) an allergen that the original does not declare, and must not raise an allergen from `MAY_CONTAIN` to `CONTAINS`. This holds for every buyer, with or without exclusions.

---

## 7. Policy — what the agent may decide alone

Verdicts, least to most severe: `AUTO` (the agent places the order) · `APPROVAL` (a person with the named role decides) · `BLOCK` (cannot be ordered, even with approval). Every rule that fires is listed in the decision with its sentence; the most severe verdict wins. The rules are data (`src/tta/policy/rules.yaml`), except F-10, which is code (`src/tta/policy/human_approval.py`); the policy hash covers both and is written in every audit event. `GET /v1/authority` answers every rule below in plain words for the caller's buyer.

**In all four shipped profiles the agent never orders alone**: `auto_order_enabled` is `false`, so every order is prepared by the agent and confirmed by a person (Valio Aimo, 14 Nov: "the final submition should always have the input from the user"). Ordering alone is a setting a buyer can switch on; what it then allows is F-10 below.

### Fixed rules — no profile can switch these off
The words are the rule's own sentence in `rules.yaml` (what `GET /v1/authority` answers).

| Id | The rule, in its words | Verdict |
|---|---|---|
| F-01 | "A product whose quantity Valio Aimo does not confirm always goes to the purchasing manager." | `APPROVAL` (purchasing manager) |
| F-02 | "A product that declares an allergen the buyer excludes can never be ordered, even with approval." | `BLOCK` |
| F-03 | "When a fact a rule needs is missing, a human decides. Missing data never counts as good data." | `APPROVAL` (the role the missing fact names, else the purchasing manager) |
| F-04 | "An option that has expired, whose order cut-off has passed, or whose price or availability changed since the offer cannot be ordered. A fresh offer is needed." | `BLOCK`; at order placement the answer carries a fresh offer (§8) |
| F-05 | "A substitute that declares an allergen the product asked for does not can never be ordered as a substitute, for any buyer. A person who wants that product asks for it by name." (also one that raises an allergen from may contain to contains) | `BLOCK` |
| F-06 | "An agent can never approve an order, its own included: approval routes refuse agent tokens." Enforced by the approval routes, not by the engine; listed in `rules.yaml` under `access_rules` so the policy hash covers it | refused, 403 `not-authorised` |
| F-07 | "A product whose price Valio Aimo does not confirm, or whose delivery date is ruled out, always goes to the purchasing manager. When the request gives a needed-by date, an option that does not verifiably meet it always goes to the purchasing manager." One rule judged in two places, so `rules.yaml` holds two entries with the id F-07, one for every line and one for the option as a whole; they agree on title, verdict and role, and the authority shows them as one | `APPROVAL` (purchasing manager) |
| F-08 | "A substitute that lacks a dietary claim of the product it replaces, for example lactose-free, always goes to the dietitian." It fires on the 8 dietary claims of §5. The role asked is the dietitian's wherever the profile names one, which is all four shipped profiles; at the hotel and the bakery the person who orders holds that role, and the sentence there says "the purchasing manager" | `APPROVAL` (dietitian) |
| F-09 | "A product type that recipe logic chose in place of a recipe's own ingredient always goes to the purchasing manager, who checks that the dish still works." | `APPROVAL` (purchasing manager) |
| F-11 | "Where a request line says the formula matters, a substitute whose formula differs from the original's, or cannot be compared, always goes to the purchasing manager." A profile with `formula_matters: true` (the bakery) makes it hold on every line. A profile or a request can add the check and never remove it | `APPROVAL` (purchasing manager; the dietitian where she is the buyer's second person: the ward and the school) |
| F-12 | "A substitute that is not a like-for-like replacement of the product asked for (another formula, use, flavour or product type, or one the data cannot show to be like for like) always goes to the purchasing manager, whatever <the buyer> sets." It fires on every substitute whose verdict is not "replaceable", so the agent never orders one alone, also with ordering alone on (decision B64) | `APPROVAL` (purchasing manager; the dietitian at the ward and the school) |

### F-10 — the rule the buyer's setting drives
F-10, "Every order needs human approval": "The agent prepares the order, a person confirms it." It is not marked fixed, because the profile setting `auto_order_enabled` switches it, and it is applied in two places so no path can forget it: when an option is judged and again when an order is placed.

- **Setting off** (every shipped profile): an order that no other rule sends to a person goes to the purchasing manager under F-10. The decision reads "Prepared: confirm to order. The agent prepares the order, a person confirms it (F-10): the purchasing manager confirms." When another rule already names a role, that role signs and F-10 is not added.
- **Setting on** (the buyer's own choice): the agent orders alone only when no rule fires **and** every statement of every line is confirmed: price, quantity, delivery date, allergens and origin. One statement unknown or missing, and F-10 still sends the order to the purchasing manager and names it. The fixed rules hold either way. Checked by `tests/policy/test_ordering_alone.py`. An order placed alone says why it was allowed, with the figures: "The agent placed this order alone for €402.00 net. That was allowed: ordering alone is switched on for City Hospital, Ward 4; the total of €402.00 is within the €500 limit per order; today's spend with this order is €402.00 of the €1,500 limit per day; every statement of the offer is confirmed; and no rule asked for a person."
- **Where it can be seen.** The four demo customers keep the setting off, so over REST and MCP every order of a demo token waits for a person; no demo agent orders alone there (decision B57 took its fallback). On `/shop` → Settings a visitor switches it on in the browser's own order book: at the hotel 302 L of lactose-free milk (€748.96) are then ordered by the agent and 303 L (€751.44) go to a person (P-01, the €750 limit). The switch is itself an audit event (`settings.changed`, §9), and the page's Settings lists the changes under "What changed" (`GET /shop/api/audit?event_type=settings.changed`). A demo agent that orders alone over REST and MCP is a next step.
- Rule P-00 of earlier versions is retired: it fired next to every other rule. There is no P-00.

### Buyer profile — set per buyer, one YAML file each
| Setting | Meaning | Rule when crossed, in its words |
|---|---|---|
| `auto_order_enabled` | Whether the agent may place an order alone at all. `false` in all four profiles | F-10, above |
| `max_order_net_eur` | Spend limit per order | P-01: "An order above €… before tax goes to the purchasing manager." |
| `max_daily_net_eur` | Spend limit per day, this order included; waiting orders count | P-02: "When the day's orders, this one included, pass €… before tax, the order goes to the purchasing manager." The rule's role is `finance`; in all four shipped profiles the person who orders holds it, and the sentence says so. The approval says how much is ordered and how much is waiting |
| `min_fill_ratio` | Share of the requested quantity that must be covered | P-03: "An option that covers less than …% of the requested quantity goes to the purchasing manager." |
| `excluded_allergens`, `allergen_strictness`, `allergen_strictness_by_code` | §6. The by-code map lets one allergen be `STRICT` while another is `DECLARED_ONLY`; a request can only make a rule stricter | P-04: a product that does not rule out an excluded allergen goes to the dietitian (ward: "City Hospital, Ward 4 excludes milk and cereals containing gluten, and each must be confirmed absent: a product that may contain one, leaves it undeclared or says nothing about it goes to the dietitian."). At the hotel and the bakery the person who orders holds the dietitian's role and decides it |
| `substitution_without_approval` | `NONE` · `LISTED_BY_SUPPLIER` · `SAME_CATEGORY` | P-05: `NONE` "Every substitute goes to the purchasing manager."; `LISTED_BY_SUPPLIER` "A substitute that Valio Aimo does not list for the product goes to the purchasing manager."; `SAME_CATEGORY` "A substitute that Valio Aimo does not list for the product and that is not in the same product category goes to the purchasing manager." For the last two the sentence goes on: "A substitute that costs more than 25% above what the product it replaces would have cost, or whose price cannot be compared with it, goes to the purchasing manager." (25% is ours where the profile sets no share.) |
| `variable_weight` | `APPROVAL` or `AUTO_WITH_CEILING` (the value keeps its old name; the total is an estimate, not a ceiling) | P-06: "A product sold by variable weight goes to the purchasing manager: its total is an estimate, because Valio Aimo invoices the weight delivered, which can be lower or higher than the weight ordered." |
| `deposits` | `APPROVAL` or `NOTE` (the total excludes deposits and says so) | P-07: "A product that carries a deposit goes to the purchasing manager: deposits have no published price, so the total leaves them out." (the role is `finance`, held by the person who orders in every shipped profile) |
| `require_confirmed` | Offer only fully confirmed options | applied when building the offer |
| `standing_order_drift_ratio` | Tolerance for a standing order's renewal | P-08: "A renewal of a standing order whose quantity or unit price on a line differs by more than …% from the median of that line's last 6 renewals goes to the purchasing manager. With fewer than 3 past renewals the history is too short to judge, and the renewal says so." Not set, with enough history: a missing fact (F-03) |
| `formula_matters` | The buyer's products are ingredients: the formula check holds on every line | F-11 (fixed, above) |
| `formula_mode` | `ALWAYS` · `LEARN` · `WHEN_ASKED`: whether the gateway works out, per usual product, where the recipe matters (from the customer file, past requests and decisions on substitutes) and applies it to a line that did not say so; the offer's note says when it did and where to change it | F-11, through the line's formula mark |
| `max_preference_premium_ratio` | How much more than the cheapest confirmed option a preference may cost; at most 0.25 | P-09: "An option ranked by a preference (most reliable, lowest carbon, earliest) that costs more than …% above the cheapest confirmed option goes to the purchasing manager." Not set: P-09 never fires, and the offer still ranks the cheapest first above 25% (§5) |
| `approver_roles` | Who holds `purchasing_manager`, `dietitian`, `finance`. One person may hold several: an approval is complete when the people who approved hold every role it asks for | — |

**Every value is illustrative and ours, and labelled so** (`illustrative: true` in each file). The mock has no customer model and Valio publishes no customer limits.

| Profile (customer) | Per order € | Per day € | Min fill | Allergens | Substitution | Other |
|---|---|---|---|---|---|---|
| `hotel-kitchen` (Harbourside Hotel) | 750 | 3,000 | 0.9 | none | `SAME_CATEGORY` | drift 25%; the purchasing manager holds all three roles |
| `allergy-ward` (City Hospital, Ward 4) | 500 | 1,500 | 1.0 | `AM`, `AW`, `STRICT` | `NONE` | `require_confirmed` true; drift 10%; preference premium 10%; the purchasing manager also holds finance; a dietitian is the second person |
| `school-kitchen` (Kilo School) | 250 | 800 | 1.0 | `AN`, `AP`, `AS`, `STRICT` | `LISTED_BY_SUPPLIER` | drift 25%; the purchasing manager also holds finance; a dietitian is the second person |
| `bakery-cafe` (Kallio Bakery) | 300 | 1,000 | 1.0 | none | `NONE` | `formula_matters` true (`formula_mode` `ALWAYS`); drift 25%; preference premium 10%; the owner holds all three roles |

All four: `auto_order_enabled` false, variable weight and deposits → `APPROVAL`; `formula_mode` is `LEARN` at the hotel, the ward and the school.

**Who decides (decision B54, João: several signers of one company are "a bit bureaucratic").** One person confirms. At the hotel and the bakery that person holds every role, so one confirmation completes an approval whatever rule asked. At the ward and the school the dietitian is the only second person: she decides allergen doubts (P-04), a lost dietary claim (F-08) and, since 15 Nov, a substitute whose formula differs or that is not like for like (F-11, F-12; decision B66, because we hold no nutrition standard of a school or a hospital). Where an approval names the buyer and the dietitian and she chooses the safe product of the same offer, her decision places the order within the limits: the short path, kept (decision B61). Stated plainly: at the hotel and the bakery there are no four eyes today; a second signer above a limit is a next step.

**P-04 and the ward.** `require_confirmed` is applied when the offer is built, before the policy runs: every product the allergen rule would send to a person is excluded as `ALLERGEN_NOT_STATED` (5 products for the ward's 200 L of plant drink, recording). So P-04 does not fire for `allergy-ward`. P-04 fires for a buyer with an exclusion and without confirmed-only: the hotel's request for 100 L of `469512` with milk excluded gets "Alternative: allergen not ruled out" with P-04, whose role is the dietitian's; at the hotel the person who orders holds it.

---

## 8. Order and approval

```
POST /v1/orders ─► re-check price and availability
      ├─ changed or expired ─► 409 offer-stale / offer-expired, fresh offer
      ├─ BLOCK              ─► 422 policy-blocked (audit event, no order)
      ├─ AUTO               ─► ORDERED   (only with the buyer's setting on, F-10)
      └─ APPROVAL           ─► PENDING_APPROVAL ─► approve ─► re-check ─► ORDERED
                                               ├─ reject  ─► REJECTED
                                               └─ valid_until passes ─► EXPIRED
```
- Order states (`OrderStatus`): `PENDING_APPROVAL`, `ORDERED`, `REJECTED`, `EXPIRED`. `placed_by` is `AGENT` or `HUMAN_APPROVAL`.
- **With the shipped profiles every order follows the `APPROVAL` branch.** What a person reads: "Prepared: confirm to order. Waiting for the purchasing manager to confirm, by … (rule F-10: a person confirms every order)", then "Confirmed by <name>: ordered for € … net." The role follows the name only where a second person can sign: "Confirmed by Demo approver Jussi (purchasing manager): ordered for €402.00 net." at the ward (REST, measured 15 Nov). When a rule other than F-10 asked: "Ordered for €1,083.39 net with approval by Hanna Laine, Harbourside Hotel: rules P-01 and P-03 asked for a human and were accepted." (the shop page, which signs with the customer's person by name).
- The approval names the roles it needs. It is complete when the approving people hold all of them.
- An approver may pick another option of the same offer. The policy runs again on that option: `BLOCK` still blocks.
- The daily spend counts orders in `ORDERED` and `PENDING_APPROVAL` for that profile, on the date of the data clock (§10). In replay that day never ends, so repeated demos on the shared book add up until P-02 fires.
- **At approval time** the re-check runs again. If it fails, the decision is refused (409) and the order keeps waiting: the approver can pick another option or reject, or it expires at its "order by" time (24 hours after it was created when the option has none). No fresh offer is built on this path.
- **`ORDERED` means recorded in our order book.** The mock has no order endpoint, by design. Every order's `record_note` says: "Recorded in the gateway's order book. The Valio Aimo mock has no order endpoint; this record holds everything a supplier order message would need. It commits nobody. No payment is taken here: the buyer is assumed to be a Valio Aimo credit customer, invoiced after delivery for what is delivered." There is no payment step.
- The order keeps the statements it relied on: each price with its `validTo`, each availability figure with `closingTime` and `availableDate`, the `timeNow` of the check.

### `proof` — what is signed, and what is not
Every offer and every order record that a REST route or an MCP tool answers carries `proof` (`src/tta/api/signing.py`): a detached JSON Web Signature, algorithm EdDSA over Ed25519, over the record's canonical JSON (the code cites RFC 8785) with `proof` removed. Fields: `type`, `algorithm`, `canonicalization`, `key_id`, `jws`, `jwks_path`, `demo_key`, `note`. The public key is at `/.well-known/jwks.json`.

- **It says:** this gateway answered this record; a price, quantity, verdict or name changed after the answer no longer verifies.
- **Next step (from check CK4): stored orders tied to their audit entries.** The proof is made when the record is answered. Today a stored order edited in the database is answered with the edited values and a proof that verifies, and the audit chain stays intact, because an order row is not tied to its audit events. Tying them needs a field on a hashed model.
- **It does not say:** that Valio Aimo signed or confirmed anything. It is not a Verifiable Credential and not a payment mandate.
- **The key:** `TTA_SIGNING_KEY` (the Ed25519 seed) when set; otherwise a demo key generated at start and gone at the next start. Then `demo_key` is true and the note reads "Signed with a demo key this gateway generated when it started; it is gone at the next start, so nothing is claimed about this signature beyond this run." `/healthz` says which.
- **Not signed:** audit events (they are hash-chained, §9), the pages, products, search results. The proof is added to the answer; it is not stored and not in the trail.

---

## 9. Audit trail

- **Event types** (20, each prefixed `tta.v1.`): `request.received` · `request.parsed` · `lookup.performed` · `offer.created` · `policy.evaluated` · `order.placed_by_agent` · `approval.requested` · `approval.decided` · `order.confirmed` · `order.rejected` · `order.expired` · `order.blocked` · `order.not_placed` · `authorisation.refused` · `evidence.attached` · `standing_order.created` · `standing_order.renewed` · `suggestions.shown` · `suggestion.accepted` · `settings.changed`.
- **A change of settings is an event** (`settings.changed`, decision B59): who changed what, each setting before and after ("… switched ordering alone on: the agent may order up to €750.00 an order and €3,000.00 a day without asking"). Valio Aimo reads only that a setting changed. On the shop page, at the ward and the school, the dietitian's allergen exclusions cannot be removed by the person who orders (the change is refused, 422).
- **Every event has:** who (agent, human or system, with id and role), what, why (rule ids and the facts they read), the hash of the policy and profile in force, the previous event's hash, and **one readable sentence**, built from a template, never by a model. Example (recording): "The agent cannot place this order alone: the total of €1,083.39 before tax is above the €750 limit per order of Harbourside Hotel (P-01) and only 43.5% of the requested quantity is covered, below the 90% minimum (covered: 435 of 1,000 L) (P-03). It needs the purchasing manager."
- **Envelope:** stored as CloudEvents 1.0 (`specversion`, `id`, `source`, `type`, `time`, `subject`, `data`), append-only. `time` is the real UTC time, not the data clock (§10). `GET /v1/audit` answers a reader's view of each event: `id`, `type`, `time`, `actor`, `sentence`, `rule_ids`, `facts`, `hash`. That answer is not a CloudEvents document (no `specversion`, `source`, `subject` or `data` in it), so the trail does not load into a CloudEvents tool as answered; the envelope is how it is stored. A reader also cannot recompute a hash from its view, because the view masks facts: it relies on the gateway's `chain` verdict.
- **Hash chain:** each event carries the previous event's hash and its own SHA-256 over its JSON with sorted keys. It shows a changed, removed, inserted or moved event. It does not show the newest events cut off, or a rewrite to the end by whoever can write the database, unless another party holds the head (event count and last hash, published at `/healthz`). `/healthz` verifies the whole chain of the shared order book and answers `degraded` with the first event that does not verify. A scheduled job that keeps the head elsewhere exists (`deploy/witness.py`) and has not run (`docs/AWARDS.md`), so nothing compares a head held elsewhere yet.
- **Two readers** (the brief: "a human-readable log … for both buyer and Valio Aimo"):

| | Buyer | Valio Aimo (supplier) |
|---|---|---|
| Sees | Everything about its own requests: options, exclusions and reasons, rules fired, limits, approvers and notes | Every step and decision: what was asked of their data, what was offered and ordered, **every rule that fired** by id and title, whether it is fixed or set by the buyer, its outcome and the role that must sign, the logic ("the strictest outcome decides"), and the products considered and left out by reason |
| Does not see | Other buyers | The buyer's name, limit amounts, the allergen codes and the products a rule about an excluded allergen fired on, approver names (the role stands for the name), notes and the buyer's own words. What is masked is said in the sentence ("the amount is not shown") |

Valio Aimo's token reads this view and nothing else: no order, no customer (403).

---

## 10. Live, replay and the clock

- `TTA_MODE=replay` (the default, and what every figure in this file was measured in): answers from `fixtures/valio/2026-11-14-demo` (769 products) joined with `fixtures/valio/2026-11-14-baking` (394 products, recorded the same Saturday at 21:12; Valio Aimo said its test data is static), with the clock pinned to the first recording's instant, Sat 14 Nov 2026 02:52:45 Helsinki time. The offer says `replay`, and says which of its products come from the later recording.
- **The demo clock.** `TTA_DEMO_CLOCK` (an instant with an offset) replaces the recording's instant as "now" in replay; the recorded prices and availability are not changed. It is ours: Valio Aimo said on 14 Nov that its test data is static, and at the recording's own instant many cut-offs have passed. The value used for the demo is Thu 12 Nov 2026 14:15 Helsinki time. It is honoured only in replay (in live mode it is ignored), and outside `dev` and `demo` the gateway does not start with it; `/healthz`, every offer (`time_basis: demo_setting`) and the pages say which clock is in force (`tests/e2e/test_demo_clock.py`).
- `TTA_MODE=live`: calls the mock through one client that records every response, spaces calls at least one second apart, caches for 60 seconds, and stops at a call budget. One lookup's price and availability come from one source; after a live failure, or with fewer than 10 calls left in the budget, the recording answers for 30 seconds and the offer says `replay`. The demo and the public link run in replay; the live calls made during the build are counted at the top of `AIMO/build/replan/STATUS.md`.
- **Two clocks.** The *data clock* judges cut-offs, price validity, expiry and the day of the daily spend, and stamps offers, orders and approvals. Audit events and evidence carry the *real* UTC time, so in replay an order's time and its events' times differ; the clock sentence of `/healthz` and of the pages says so ("The audit trail is stamped with the real time.").
- Tests never call the live API.
- Secrets come from the environment (`VALIO_AIMO_API_KEY`, `VALIO_AIMO_BASE_URL`, `GEMINI_API_KEY`, `DATABASE_URL`, `CONTEXT_DEV_API_KEY`, `TTA_SIGNING_KEY`, `TTA_TOKENS`). They are never logged and never written to a fixture.

## 11. Reading a request, and the buyer agent

**The typed request of §3 is the interface.** An agent posts it to `POST /v1/offers` and no text is read at all. For a person's sentence there is `POST /v1/requests/parse`.

- **The order of answering** (`src/tta/agent/fallback.py`). With a key set, the model is asked first and its reading is checked against the text (last bullet of this section). When the model does not answer, or no key is set, the order is:
  1. a **recorded reading** of exactly that sentence for that buyer profile, when `fixtures/agent/` holds one (11 recordings: 4 were recorded from `gemini-3.6-flash` on 14 Nov, 7 are written by hand and say `hand-built`; among them the brief's own sentence for the hotel). A recording is served only to the profile it was made for, so over REST and MCP the hotel's and the ward's demo sentences are answered from recordings and say so, while on `/shop`, whose order book has a profile of its own, every sentence is read by the fixed rules ("Read by fixed rules, not by a model: no Gemini key is set.");
  2. else the **fixed-rules reader** (`src/tta/agent/rules_reader.py`): quantities in digits with a unit, product types of the table, product numbers, lactose-free and gluten-free, "no milk", strictness, named days and dates, "confirmed only", preference and label words, "for whipping / for cakes / for baking" (sets `keep_formula`), "the usual milk", "a milk substitute" (read as a plant drink, and the reading says so). Asked about, not read (15 Nov): a minus ("-5 litres"), cartons, cases, boxes, crates, trays and pallets (how much one holds differs by product), an amount of money ("a price limit in the sentence is not applied yet"; the limits applied are the buyer's settings), and a Finnish or Swedish sentence ("the fixed rules read English only for now");
  3. else **a question, not a guess**: `422 invalid-request` with `question` (what to answer), `not_read` (what was not read) and `read_by` (`rule-based`). Example (run in replay): "some stuff for the weekend" → `not_read`: "it gives a deadline the rules do not read ("weekend")", `question`: "By which day are the goods needed? Name a weekday or a date, for example "by Monday" or "by 20.11."."
- **Every reading says who read it**, in the headers `TTA-Read-By` and `TTA-Reading-Source` (`rule-based`, `hand-built`, or the recorded model's name), in `TTA-Reading-Sentence` and in a sentence on the pages.
- **The rules never guess** a quantity, a unit, a date or an exclusion. `docs/READING-TABLE.md`, generated by a test, lists what is read and what is asked about: 109 sentences, 55 read, 54 asked about, 0 read wrong (15 Nov). **Next steps for the reader, none of which exists today:** a price limit read from the sentence, an origin filter ("Finnish milk" becomes a name term), "lowest carbon footprint" read from a sentence, and Finnish.
- **`POST /v1/agent/run`** with no key: a recorded run for that sentence and profile, else a fixed run made by the rules (authority → offer → order of the option ranked 1), and its report opens by saying so. The gateway, not the runner, decides whether the order goes through; with the shipped profiles it waits for a person.
- **A photo** (`POST /v1/requests/read-image`) needs a model. With no key only the recorded demo photo is answered, from hand-written recordings. The upload control is no longer on the first page; the route stays.
- **With a model.** With `GEMINI_API_KEY` set (or an OpenAI-compatible endpoint through the `TTA_AGENT_*` settings), the same parser asks the model first (structured output; a product type only from the table's keys) and checks every reading against the text (`src/tta/agent/textcheck.py`: quantity, unit, date, exclusions, confirmed-only, product ids; a disagreement is asked once more, then refused: the gateway never corrects a reading). When the model cannot be reached it falls back to the recording, then the rules. Text from the product file or the API reaches a model only as data, never as instructions. So the fixed rules are the model's check and its fallback. Measured by the build on 15 Nov with a key set, on a local server at the demo clock (not by the checks of this file): the brief's own sentence was read by `gemini-3.6-flash` into 1,000 L, product type milk, claim `FREE_FROM_LACTOSE`, Monday 16 Nov (`TTA-Read-By: gemini-3.6-flash`, `TTA-Reading-Source: model`); a loosely worded sentence whose day the model got wrong was refused ("the reading did not match the text: the text names another day"); and when the model answered HTTP 429 twice, the fixed rules read the sentence and the answer said so. Whether a deployment runs with a model is its own setting: `GET /healthz` → `agent_reader` says what reads sentences there. Whoever reads, no price, quantity, allergen status or verdict comes from a model.

## 12. Pages

Pages exist only where `TTA_ENV` is `dev` or `demo`: they act as a demo identity chosen on the page, with **no login**. Whoever opens `/shop` acts as the customer's person and can sign as any of its people, the dietitian included; the page says so ("Demo, no login: you are acting as Hanna Laine"). That an agent cannot approve is enforced over REST and MCP, not on these pages. Anywhere else no page is mounted and people decide with tokens of their own.

| Page | Shows |
|---|---|
| `/shop` | The shop page (static files over `/shop/api/*`), where everything a person does now happens: a customer, a request or a dish ("a chocolate cake for 20"), the offer with what is confirmed and what is not, one "Confirm order" button, suggestions with "Add", the reorder prompt, standing orders (each renewable at a typed quantity), the approvals that wait for someone else, Settings (limits, ordering alone, allergens; a change is logged), the log as the buyer and as Valio Aimo see it, Valio Aimo's back office, the clock strip. Not a chat. Walked in headless Chrome on 15 Nov (`AIMO/build/replan/REVIEW.md`, section BW), before the last fixes to the page |
| `/` | Paste a request, choose who is asking, run; one example per demo scenario. Then the reading, the offer (options with a mark per statement, the constraint checks, the exclusions with reasons, each option's comparison), the verdict, and "Prepared: confirm to order" |
| `/approvals` | Waiting approvals as cards: the options, why a person is needed, "order by" time, the evidence on an allergen doubt, approve (with option choice) or reject with a note |
| `/orders/{id}` | The order record and its audit trail, switchable between the buyer's and Valio Aimo's view |
| `/assumptions` | `docs/ASSUMPTIONS.md` as written |
| `/menu` | Dishes and servings, the kitchen's stock and the date; the plan per dish and ingredient (stand-ins marked), the offer's options and verdicts |
| `/standing-orders` | Load the demo standing order, see its history (synthetic rows marked), renew with this week's quantity; the drift sentence and the outcome |
| `/kitchen` | The browser's own buyer profile `my-kitchen`, set on a form and checked as a profile file is. REST and MCP never see it |

**Each browser has its own order book**: an in-memory store with its own audit trail, so one visitor's orders never count in another's daily spend. "Start again" empties it. REST and MCP keep the shared book.

## 13. Acceptance — measured in replay

Rows 1 to 5 were measured again on Sun 15 Nov 2026 between 02:26 and 02:29 through the shop's routes (`/shop/api/*`) in replay, at the demo clock (Thu 12 Nov 2026 14:15) and at the recording's own clock; row 2's sentences also over REST. All of them were measured once more at 02:51 on commit `fd4098b`, after the last change to substitute ranking and to rule P-05, at both clocks; `docs/DEMO.md` holds that measurement in full. The backup and the guards are as measured on 14 Nov, except the first guard, run again on 15 Nov. The end-to-end tests are in `tests/e2e/`.

| # | Input | What holds |
|---|---|---|
| 1 | `hotel-kitchen`: 1,000 L of lactose-free milk by Mon 16 Nov | Three options, the same at both clocks. Option 1 "Best confirmed option (partial fill)": 384 × `469363` + 51 × `462775`, 435 of 1,000 L, €1,083.39 net; to the purchasing manager (P-01 the spend limit per order, P-03 the minimum fill). Option 2 "Alternative: quantity not confirmed": 1,000 × `464306`, €1,010.00 (F-01 the quantity is not confirmed, P-01). Option 3 "Alternative: confirmed stock, completed with a substitute": option 1 plus 565 × `463380` (lactose-free milk made for coffee), €2,580.64 (F-12 not a like-for-like replacement, P-01). Of 26 candidates 2 are left out at the demo clock and 17 at the recording's (15 more past their cut-off), each with a reason; `463203` as `PORTION_PACK`. The order waits; a person approves; the trail has 11 events, a sentence for every step |
| 2 | `allergy-ward`: 200 L of plant drink by Mon 16 Nov; no milk, no gluten, strict; confirmed only | 200 × `464013`, €402.00, at both clocks. Of 51 candidates 18 are excluded as `ALLERGEN_DECLARED`, and as `ALLERGEN_NOT_STATED` 11 at the demo clock and 5 at the recording's. Verdict `APPROVAL` under F-10 alone ("Prepared: confirm to order"); after the purchasing manager's approval: `ORDERED`, "Confirmed by Demo approver Jussi (purchasing manager): ordered for €402.00 net." (REST). It is ordered by the agent alone only with the buyer's setting on, shown on `/shop` (§7; `tests/policy/test_ordering_alone.py`) |
| 3 | `hotel-kitchen`: 100 L of `473609` (quantity not confirmed) | Option 1, the confirmed substitute 100 × `475224`, €174.00, to a person (F-12: not a like-for-like replacement; P-05: it costs €37.00, 27%, more than the product asked for); option 2, the product asked for, €137.00 (F-01). **Demo clock:** the same two, then option 3, the substitute Valio lists, 10 cases of `471690`, €155.50 (F-01, F-12); at the recording's clock its cut-off has passed |
| 5 | `bakery-cafe`: 40 kg of crème fraîche `477055`, for baking | Option 1 the product asked for, quantity not confirmed, 20 × `477055`, €214.40 (F-01); option 2 "Alternative: quantity not confirmed, a substitute that does not keep the formula": at the demo clock 27 × `477003`, €339.66 (F-01, F-11 the formula, F-12, P-01, P-05 every substitute); at the recording's clock 223 × `468277`, €198.47 (F-01, F-11, F-12, P-05). To the owner |
| Backup | `hotel-kitchen`: 30 kg beef chuck | "about €506.40 before tax", the total marked as an estimate; `APPROVAL` (P-06, sold by variable weight). Measured 14 Nov, not re-measured |
| Guard | An agent token on `/v1/approvals/{id}/decision` | 403 `not-authorised` (F-06): "An agent cannot approve or reject an order (F-06). A human with the role asked for decides.", and the refusal is in the trail (`authorisation.refused`) |
| Guard | The same `Idempotency-Key` twice; no key; the same key for another option | One order; 400; 422 |
| Guard | Valio Aimo's token on `GET /v1/customers` | 403 |

Scenario 4 (suggestions from a customer's pattern) is on the offer itself (§5, point 7): the hotel's 100 L of lactose-free milk shows the forgotten cooking cream; accepted, the new offer is 100 × `469363` + 10 × `463797`, €281.10 (F-10).

## 14. Assumptions and next steps page

`docs/ASSUMPTIONS.md`, shown at `/assumptions`: every value and reading that is ours (profiles, customers and their synthetic history, product-type table, tolerances, thresholds, the demo clock, limits); what the mock does not tell us; the reason for each technical choice; what is out of scope; next steps toward production, among them a supplier order message in an open e-procurement format, real customer limits and history, and a statement signed by Valio Aimo itself in place of the gateway's own signature.
