# AIMO — build specification

The contract the code follows. Written 14 Nov for the overnight build; it closes the "to specify before coding" list of [PLAN.md](PLAN.md) §9. Facts about the mock API and the data are in [FINDINGS.md](FINDINGS.md) and [docs/](docs/); this file does not repeat them.

**Rule for every line of code: name the judging criterion it scores on** ([CHALLENGE.md](CHALLENGE.md)). The weights are 30% end-to-end flow · 20% precise match to the request · 20% autonomy and controls · 15% exceptions · 15% openness and path to production.

---

## 1. What we build

A gateway between a buyer's purchasing agent and Valio Aimo's price and availability API.

```
buyer's agent ──► gateway ──► Valio mock API (price, availability)
   (Gemini)        │  ├─ catalog (product file, local)
                   │  ├─ response logic (six availability states, allergens, substitutes)
                   │  ├─ policy (fixed rules + buyer profile)  ──► AUTO · APPROVAL · BLOCK
                   │  ├─ order book and approvals              ──► human approval panel
                   │  └─ audit trail (one sentence per decision, two readers)
                   └─ same functions exposed as REST (OpenAPI) and as MCP tools
```

**One flow, every scenario:** request + buyer identity → search → offer (options, a status per claim, exclusions with reasons, the policy verdict for each option) → order → placed by the agent or sent to a human → audit record.

### Choices, each with its reason
| Choice | Reason |
|---|---|
| Python 3.13, FastAPI, Pydantic v2 | The team knows Python; FastAPI generates OpenAPI 3.1 from the typed models, so the published interface cannot drift from the code (15%) |
| Code in `src/tta/`, tests in `tests/`, virtualenv `.venv`, `pip` | A root-level `aimo/` package would collide with `AIMO/` on macOS. `tta` = Trusted Trade Agents |
| Server-rendered pages (Jinja2 and a little plain JavaScript) | No Node build step; one process to deploy |
| SQLite through a small repository interface | No service to provision overnight. Postgres can be added behind the same interface if `DATABASE_URL` is set |
| Gemini through the official SDK | Structured output turns the pasted request into the typed request; function calling drives the buyer agent |
| **The model never decides a price, a quantity, an allergen status or a verdict** | Those come from deterministic code that can be tested and audited (20% controls) |
| Policy as data (YAML): fixed rules plus one profile per buyer | The guardrails can be read and changed without touching code |
| Audit events in a CloudEvents 1.0 envelope, hash-chained | A documented open format, and a log that shows tampering (20% controls, 15% openness) |
| Errors as RFC 9457 problem details; `Idempotency-Key` on order placement | Agents retry; a retry must never place a second order |
| Replay mode with a pinned clock | The demo survives the mock being down or every cut-off having passed |
| Every port is synchronous | One style everywhere; FastAPI runs the routes in its thread pool; SQLite, `httpx` and the Gemini SDK all have synchronous clients |

### Layout
```
pyproject.toml · LICENSE (MIT) · README.md
src/tta/
  contracts/     shared Pydantic models — the interface. Only the orchestrator edits these.
  config.py      settings from the environment
  valio/         client for the mock API, recorder, replay, call budget, clock
  catalog/       product file loader, search, product types, pack size
  allergens/     GS1 codes and families, buyer exclusion rule, substitution rule
  availability/  the six states, verification status per claim
  policy/        fixed rules, buyer profiles, engine
  store/         SQLite repository
  audit/         events, hash chain, sentences, reader views
  offers/        candidates → options, ranking, combining, substitutes
  orders/        order states, approvals, idempotency
  api/           FastAPI app, routes, authentication, MCP surface
  agent/         Gemini: request parsing and the buyer agent loop
  ui/            templates and static files
deploy/modal_app.py
fixtures/valio/  recorded responses of the mock API
tests/
```
`AIMO/catalog_search.py` (Sofia, `bio1`) and `AIMO/policy/` (Gabriela, `bio2`) are merged into the build branch unchanged and are the starting point for `catalog/` and `policy/`.

---

## 2. Interface

All paths are under `/v1`. Every response is JSON; every timestamp is ISO 8601 with offset; currency is ISO 4217 (`EUR`); allergens are GS1 codes; money and quantities are computed with `Decimal` and serialised as JSON numbers (money 2 decimals, quantities 3).

| Method and path | Who | Purpose | Brief |
|---|---|---|---|
| `GET /v1/authority` | agent | The caller's buyer profile: what it may decide alone | Core 3 |
| `POST /v1/products/search` | agent | Search the catalog: product type, name terms, claims, category, pack size | Core 1 |
| `GET /v1/products/{id}` | agent | One product with its allergen statements and claims | Core 1 |
| `POST /v1/products/{id}/substitutes` | agent | Ranked substitutes, each with pass or fail and the reason | Optional: substitution |
| `POST /v1/offers` | agent | Typed request → offer with live price and availability | Core 1, Core 2 |
| `GET /v1/offers/{id}` | agent | The stored offer | Core 2 |
| `POST /v1/orders` | agent | Commit one option of an offer | Core 2, Core 3 |
| `GET /v1/orders/{id}` | agent, approver | Order with status, decision and approvals | Core 2 |
| `GET /v1/approvals?status=pending` | approver | The approval queue | Core 3 |
| `POST /v1/approvals/{id}/decision` | approver | Approve (optionally choosing another option of the same offer) or reject | Core 3 |
| `GET /v1/audit?order_id=&reader=buyer\|supplier` | agent, approver, supplier | The audit trail as one reader sees it | Audit trail |
| `POST /v1/requests/parse` | agent | Free text → typed request (Gemini structured output) | 20% match |
| `POST /v1/agent/run` | demo | Runs the buyer agent on a pasted request and returns its tool-call trace | 30% |
| `GET /v1/schemas` | anyone | JSON Schema of every model | 15% |
| `GET /openapi.json`, `/docs` | anyone | Generated OpenAPI | 15% |

- **MCP:** the tools `get_authority`, `search_products`, `get_product`, `find_substitutes`, `get_offer`, `place_order`, `get_order`, `get_audit` call the same service functions as the REST routes. No logic lives in a transport.
- **Identity:** every call carries `Authorization: Bearer <token>`. A token maps to one identity: an **agent** bound to one buyer profile, an **approver** with one or more roles, or the **supplier** reader. The buyer profile is never a request field: an agent cannot choose its own authority. Approval routes reject agent tokens: **an agent cannot approve its own order.** Demo tokens are loaded only when `TTA_ENV` is `dev` or `demo`.
- **Errors:** RFC 9457 `application/problem+json` with a stable `type`: `offer-expired`, `offer-stale`, `policy-blocked`, `not-authorised`, `unknown-product`, `invalid-request`, `supplier-unavailable`, `not-found` (an offer, order or approval id nobody issued), `rate-limited`. Each has one typed error in `tta/contracts/errors.py`.
- **Idempotency:** `POST /v1/orders` requires an `Idempotency-Key` header. The same key returns the first result.

---

## 3. Request → candidates

### The typed request
| Field | Type | Meaning |
|---|---|---|
| `needed_by` | date, optional | The date the goods are needed |
| `require_confirmed` | bool, default false | Offer only options in which every claim is confirmed |
| `lines[]` | 1 or more | One per product asked for |
| `lines[].text` | string | The buyer's own words, kept for the audit trail |
| `lines[].product_type` | string, optional | A key of the product-type table, e.g. `milk`, `plant_drink`, `beef_chuck` |
| `lines[].product_ids` | list, optional | Explicit products (a standing order, or "this product") |
| `lines[].name_terms` | list | Words that must appear in the product name (English or Finnish) |
| `lines[].required_claims` | list | `nutritionalClaim` codes that must be present, e.g. `FREE_FROM_LACTOSE` |
| `lines[].quantity`, `lines[].unit` | decimal, `L` · `KG` · `UNIT` | `UNIT` means sales units |
| `lines[].exclude_allergens` | list of GS1 codes | Added to the profile's exclusions; a request can add exclusions and can never remove one |
| `lines[].allergen_strictness` | `STRICT` · `DECLARED_ONLY`, optional | Required when there is any exclusion and the profile sets none. There is no default: a missing value is `invalid-request` |
| `lines[].pack` | `ANY` · `BULK` · `PORTION`, default `BULK` for `L` and `KG` | See the portion-pack rule |

### From a line to candidate products
1. **Explicit ids** are used as given, after a check against the local catalog (an unknown id is `unknown-product`; the availability endpoint cannot tell it from an undeliverable product).
2. **Product type:** `catalog/product_types.yaml` maps a key to category codes, name terms and claims. It is a short table we maintain and document as an assumption. It must cover the demo scenarios and the commonest food-service types found in the catalog.
3. **No product type:** search product names (English, then Finnish) for every name term, and keep the categories that hold most of the matches.
4. **Claims:** every `required_claims` code must be on the product. A claim is never read as an allergen statement.
5. **Pack size** in litres or kg per sales unit: `catalogPrice ÷ comparisonPrice` from the live price, then `unitConversions` when the unit is a real volume or weight, then the product name. If none gives a value the product is excluded with `PACK_SIZE_UNKNOWN`.
6. **Portion-pack rule:** for a `BULK` line, single-serve packs are excluded with `PORTION_PACK` (an inner unit of 5 cl or 50 g or less, such as `463203`, 100 × 2 cl). A `PORTION` line keeps only those.
7. **Quantity in sales units:** round up to the product's `allowedLotSize` step with `Decimal`. Price and quantity follow the sales unit on the API line, not the one in the product file.

---

## 4. Availability and what can be trusted

### The six states
Evaluated in this order, against the `timeNow` of the response (or the pinned clock in replay):

| State | Condition | Role in an offer |
|---|---|---|
| `BLOCKED` | `salesBlock` true | Excluded; triggers substitution when the product was asked for by id |
| `NOT_DELIVERABLE` | no schedule line | Same |
| `OUT_OF_STOCK` | `availableAmount` 0 | Same |
| `CUTOFF_PASSED` | `closingTime` earlier than now | Excluded for a dated request, with the reason |
| `QUANTITY_NOT_CONFIRMED` | `availableAmount` ≥ 999,999 (Terminal or Stock) | Never the suggestion. Offered as a separate option. Ordering it always needs a human. The value is never used in arithmetic |
| `CONFIRMED` | otherwise | May be suggested and, within authority, ordered by the agent |

A product with a schedule line whose `availableDate` is later than `needed_by` is excluded with `LATE_FOR_NEEDED_BY`.

### Verification status — our answer to the trust protocol
Every offer line states, for each claim, whether Valio's data confirms it:

| Claim | `CONFIRMED` | `UNKNOWN` | `RULED_OUT` |
|---|---|---|---|
| `price` | a net price was returned and `validTo` is in the future | no net price | — |
| `quantity` | state `CONFIRMED` and the amount covers the line | `QUANTITY_NOT_CONFIRMED` | out of stock, not deliverable, blocked |
| `delivery_date` | cut-off open and `availableDate` on or before `needed_by` | no `needed_by` given | cut-off passed, or later than `needed_by` |
| `allergens` | every excluded allergen has an explicit statement | any excluded allergen has `MAY_CONTAIN`, `UNDECLARED` or no statement | an excluded allergen is declared `CONTAINS` |
| `origin` | the product file states it | absent | — |

**Which claims gate an order without a human** (decided 14 Nov, after the availability hand-back and review round 1): `price` and `quantity` always (rules F-07 and F-01); `delivery_date` when the request gives `needed_by` (F-07, through the needed-by constraint check); `allergens` through the outcome of the allergen rule (F-02, P-04) — under `DECLARED_ONLY` a product with no statement passes and is shown as unverified, because that buyer chose so; `origin` never (it is shown, the buyer did not ask for it). A request with no date is not sent to a human for that reason alone. `require_confirmed` (on the request or on the profile) is stricter: it keeps only lines for which `OfferLine.confirmed_for_order(dated=...)` holds, which asks for the `allergens` claim itself to be confirmed. A claim that is missing from a line is a missing fact (F-03).

---

## 5. Building the offer

1. Candidates (§3) → one price call and one availability call for the narrowed set (up to 1,000 ids per call).
2. Classify each candidate (§4) and run the allergen check (§6). Everything that drops out goes to `excluded[]` with a reason code and one sentence.
3. **Options, at most three, ranked by constraint fit, then verification status, then price:**
   - `BEST_CONFIRMED` — confirmed products only. The cheapest single product that covers the whole quantity; if none does, combine the cheapest first until the quantity is covered. If confirmed stock still falls short, the option is a partial fill and says how much is missing.
   - `ALTERNATIVE_UNCONFIRMED` — the cheapest product in state `QUANTITY_NOT_CONFIRMED` that otherwise fits. A full structured option the approver can pick, not a footnote.
   - `SUBSTITUTE` — only when the request named products by id and they cannot be supplied in full: the best substitute that passes §6.
4. Every option carries: its lines; totals (net, tax from `tax.taxRate`, gross; `excludes_deposits`; `is_ceiling` for variable weight); coverage (requested, covered, fill ratio); `valid_until` = the earliest price `validTo` and `closingTime` of its lines; **constraint checks** — one per thing the buyer asked for (product type, quantity, needed-by date, each claim, each allergen exclusion, pack), each `MET`, `NOT_MET` or `UNVERIFIED` with a sentence; and **the policy verdict for that option** (§7), so the agent knows before ordering what it may do alone.
5. The offer records where its data came from (`live` or `replay`) and the `timeNow` it was built against.

**Exclusion reason codes:** `BLOCKED` · `NOT_DELIVERABLE` · `OUT_OF_STOCK` · `CUTOFF_PASSED` · `LATE_FOR_NEEDED_BY` · `ALLERGEN_DECLARED` · `ALLERGEN_NOT_STATED` (only under `require_confirmed`) · `PORTION_PACK` · `NOT_A_PORTION_PACK` (on a line that asks for portion packs) · `PACK_SIZE_UNKNOWN` · `PRICE_UNAVAILABLE` · `SUBSTITUTE_ADDS_ALLERGEN` · `QUANTITY_NOT_CONFIRMED` and `DELIVERY_DATE_NOT_CONFIRMED` (both only under `require_confirmed`).

### Substitutes
- **Candidates:** the pairs Valio lists (250 pairs on 189 products) as a seed, then the same 5-digit category, then the same first 4 digits, then the same first 3. Every candidate is re-checked for price and availability.
- **Ranking (good, better, best):** passes §6 (a failure is shown, with the reason, and can never be ordered) → category distance → listed by Valio → pack size closest to the original → verification status → price difference.
- Each result says in one sentence what the buyer gives up.
- A substitute that lacks a nutritional claim of the original (`claims_lost`) ranks after those that keep every claim, and ordering it always needs a human (F-08).

---

## 6. Allergen rules

Relations: `CONTAINS`, `MAY_CONTAIN`, `UNDECLARED` (group `allergen`) and `FREE_FROM` (group `nonAllergen`). `X99` is GS1's "Does not contain declaration obligatory allergens". A product with neither group has no statement; that is unknown, never safe. Code families (for example the cereals under `AW`) are in [docs/SCHEMA-AND-CODES.md](docs/SCHEMA-AND-CODES.md).

**Buyer exclusion rule**, for each excluded allergen and its sub-codes:

| The product says | `STRICT` | `DECLARED_ONLY` |
|---|---|---|
| `FREE_FROM` | passes | passes |
| `CONTAINS` | rejected | rejected |
| `MAY_CONTAIN` | to a human (dietitian) | to a human (dietitian) |
| `UNDECLARED`, or no statement | to a human (dietitian) | passes, shown as unverified |

- Conflicting statements on one product: the least safe one counts.
- A "no gluten" exclusion (`AW`) and a product that declares oats (`GO`): to a human, whatever else it states.

**Substitution rule:** a substitute must not declare (`CONTAINS` or `MAY_CONTAIN`) an allergen that the original does not declare, and must not raise an allergen from `MAY_CONTAIN` to `CONTAINS`. This holds for every buyer, with or without exclusions.

---

## 7. Policy — what the agent may decide alone

Verdicts, least to most severe: `AUTO` (the agent places the order) · `APPROVAL` (a human with the named role decides) · `BLOCK` (cannot be ordered, even with approval). Every rule that fires is listed in the decision with its sentence; the most severe verdict wins. Structure, fact declarations and the policy hash come from Gabriela's `AIMO/policy/policy.yaml`.

### Fixed rules — no profile can switch these off
| Id | Rule | Verdict |
|---|---|---|
| F-01 | A line's quantity is not confirmed | `APPROVAL` (purchasing manager) |
| F-02 | A line declares an excluded allergen | `BLOCK` |
| F-03 | A fact a rule needs is missing | `APPROVAL` |
| F-04 | At order time the option has expired, a cut-off has passed, or price or availability changed | `BLOCK`, with a fresh offer |
| F-05 | A substitute adds an allergen the original does not declare, or raises one from may contain to contains | `BLOCK` |
| F-06 | The caller is an agent on an approval route | refused (`not-authorised`) |
| F-07 | A line's price is not confirmed, its delivery date is ruled out, or a needed-by date is not verifiably met | `APPROVAL` (purchasing manager) |
| F-08 | A substitute lacks a nutritional claim the original carries (for example lactose-free) | `APPROVAL` (purchasing manager) |

### Buyer profile — set per buyer, one YAML file each
| Setting | Meaning | Rule when crossed |
|---|---|---|
| `auto_order_enabled` | Whether the agent may place any order alone | P-00 `APPROVAL` |
| `max_order_net_eur` | Spend limit per order without a human | P-01 `APPROVAL` (purchasing manager) |
| `max_daily_net_eur` | Spend limit per day, this order included | P-02 `APPROVAL` (finance) |
| `min_fill_ratio` | Share of the requested quantity that must be covered | P-03 `APPROVAL` (purchasing manager) |
| `excluded_allergens`, `allergen_strictness` | §6 | P-04 `APPROVAL` (dietitian) for "to a human" cases |
| `substitution_without_approval` | `NONE` · `LISTED_BY_SUPPLIER` · `SAME_CATEGORY` | P-05 `APPROVAL` when a substitute is outside it |
| `variable_weight` | `APPROVAL` or `AUTO_WITH_CEILING` | P-06 |
| `deposits` | `APPROVAL` or `NOTE` (the total excludes deposits and says so) | P-07 (finance) |
| `require_confirmed` | Offer only fully confirmed options | applied when building the offer |
| `approver_roles` | Who holds `purchasing_manager`, `dietitian`, `finance` | — |

**The values are illustrative and labelled as ours.** The mock has no customer model and Valio publishes no customer limits (booth Q7).

| Profile | `max_order_net_eur` | `max_daily_net_eur` | `min_fill_ratio` | Allergens | Substitution | Other |
|---|---|---|---|---|---|---|
| `hotel-kitchen` | 750 | 3,000 | 0.9 | none | `SAME_CATEGORY` | variable weight and deposits → `APPROVAL` |
| `allergy-ward` | 500 | 1,500 | 1.0 | `AM`, `AW`, `STRICT` | `NONE` | `require_confirmed` true |

**An order goes ahead without a human only when** no fixed rule fires and every profile limit holds: every claim confirmed, the quantity covered, no substitute outside the profile, spend within both limits.

---

## 8. Order and approval

```
POST /v1/orders ─► re-check price and availability
      ├─ changed or expired ─► 409 offer-stale / offer-expired, fresh offer
      ├─ BLOCK              ─► 422 policy-blocked (audit event, no order)
      ├─ AUTO               ─► ORDERED
      └─ APPROVAL           ─► PENDING_APPROVAL ─► approve ─► re-check ─► ORDERED
                                               ├─ reject  ─► REJECTED
                                               └─ valid_until passes ─► EXPIRED
```
- The approval names the roles it needs. It is complete when the approving humans hold all of them.
- An approver may pick another option of the same offer. The policy runs again on that option: `BLOCK` still blocks.
- The daily spend counts orders in `ORDERED` and `PENDING_APPROVAL` for that profile.
- **`ORDERED` means recorded in our order book.** The mock has no order endpoint; the record holds everything a supplier order message would need, and says so. What an order commits Valio to is booth Q4.
- The order keeps the statements it relied on: each price with its `validTo`, each availability figure with `closingTime` and `availableDate`, the `timeNow` of the check.

---

## 9. Audit trail

- **One event per step:** request received · request parsed · lookup performed · offer created · policy evaluated · order placed by agent · approval requested · approval decided · order confirmed, rejected, expired or blocked.
- **Every event has:** who (agent, human or system, with id and role), what, why (rule ids and the facts they read), the hash of the policy and profile in force, the previous event's hash, and **one readable sentence**, built from a template, never by a model. Example: "The agent could not place this order alone: the total of €1,980.77 is above the €750 limit of profile hotel-kitchen (P-01) and only 74.9% of the 1,000 litres is covered (P-03). Sent to the purchasing manager."
- **Envelope:** CloudEvents 1.0 (`specversion`, `id`, `source`, `type`, `time`, `subject`, `data`). Stored append-only.
- **Two readers** (the brief: "a human-readable log … for both buyer and Valio Aimo"):

| | Buyer | Valio Aimo (supplier) |
|---|---|---|
| Sees | Everything about its own requests: options, exclusions and reasons, rules fired, limits, approvers and notes | What was asked of their data, what was offered and ordered, the statements each order relied on, the agent's identity and whether it acted within its authority or with human approval |
| Does not see | Other buyers | The buyer's limit values, allergen exclusions, approver names and notes |

---

## 10. Live, replay and the clock

- `TTA_MODE=live`: calls the mock through one client that records every response, spaces calls at least one second apart, caches for 60 seconds, and stops at a call budget.
- `TTA_MODE=replay`: answers from `fixtures/valio/` with the clock pinned to the capture's `timeNow`. The offer shows that it is a replay.
- Tests never call the live API.
- Secrets come from the environment (`VALIO_AIMO_API_KEY`, `VALIO_AIMO_BASE_URL`, `GEMINI_API_KEY`). They are never logged, never written to a fixture, never sent to the model.

## 11. The buyer agent (Gemini)

- **Parse:** free text → the typed request of §3, using structured output with the request's JSON Schema. The parser may choose a `product_type` only from the table's keys.
- **Run:** a function-calling loop over the gateway's own tools: read authority → get offer → pick the top option → place the order → report what happened and why. The gateway, not the model, decides whether the order goes through.
- **Without a key:** the same loop runs on recorded model outputs for the demo scenarios, and the typed request can be posted directly.
- Text from the product file or the API reaches the model only as data, never as instructions.

## 12. Pages

| Page | Shows |
|---|---|
| `/` | Paste a request, choose who is asking, run. Then: the parsed request, the offer (options with a mark per claim, the constraint checks, the exclusions with reasons), the verdict, and the order or "sent for approval" |
| `/approvals` | Pending approvals as cards: the options, why a human is needed, "order by" time, approve (with option choice) or reject with a note |
| `/orders/{id}` | The order record and its audit trail, switchable between the buyer's and the supplier's view |
| `/assumptions` | The assumptions and next steps page |

The first screen must show at a glance what is confirmed, what is not, and what was excluded and why.

## 13. Acceptance — the scenarios of PLAN §3

Run in replay from the capture taken at the start of the build. Product ids are Friday's; if the capture differs, the scenario test picks the equivalent product and the difference is reported.

| # | Input | Must hold |
|---|---|---|
| 1 | `hotel-kitchen`: "1,000 litres of lactose-free milk by Monday" | Option 1 has confirmed lines only. A `QUANTITY_NOT_CONFIRMED` option exists when such a product fits. `463203` is excluded as `PORTION_PACK`. Every exclusion has a reason. Verdict `APPROVAL` with the rules named. A human approves, the order becomes `ORDERED`, the audit trail has a sentence for every step |
| 2 | `allergy-ward`: "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only" | Every product declaring milk or gluten is excluded as `ALLERGEN_DECLARED`. The chosen product states `FREE_FROM` for `AM` and `AW`. Verdict `AUTO`. The order is `ORDERED` with no approval, and the audit sentence says the agent acted within its authority |
| 3 | Substitutes of `473609` | `471690` passes. `471881` and `464320` fail with `SUBSTITUTE_ADDS_ALLERGEN` (`AW`), and cannot be ordered |
| Backup | `hotel-kitchen`: "30 kg beef chuck" | Lot step 3 kg respected; the total is a ceiling; verdict `APPROVAL` (variable weight) |
| Guard | An agent token on `/v1/approvals/{id}/decision` | `not-authorised` |
| Guard | The same `Idempotency-Key` twice | One order |

## 14. Assumptions and next steps page

`docs/ASSUMPTIONS.md`, shown at `/assumptions`: every "if no answer, we build" line of [BOOTH-QUESTIONS.md](BOOTH-QUESTIONS.md); every illustrative value (profiles, product-type table, portion-pack threshold); what the mock does not tell us; the reason for each technical choice; what is out of scope; next steps toward production, among them a supplier order message in an open e-procurement format and real customer limits.
