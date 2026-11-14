# Coverage — how the build answers Valio Aimo's brief

First written Saturday 14 Nov 2026 at about 18:00 against commit `51e9b03`; refreshed the same evening, at about 20:30, against commit `c2106fe` on branch `replan-build` (the two commits after it change documents only). It says, item by item, what the committed code does, what is in the working tree and not committed, and what is not built.

**How to read the states.**
- **Works** — in commit `c2106fe`, with tests. For this refresh each item was checked in one of two ways, and the text says which: *run* = asked of the gateway through its own routes, offline, on a clean copy of the commit; *test* = a named test file, run on the same copy (list and result under "How each step is checked").
- **Not committed** — work of a lane still running when this was written (`L4-2d`: suggestions on the offer; `L1-3`: brand words in a sentence). It is described as not part of the build.
- **Not built** — no code.
- **Not run** — built, and never executed against the real thing. These are listed once, under "What was not run".

**Where figures come from.** "Whole catalog" = Valio's product file, 17,546 products. "Recording" = the recorded answers of Valio's mock API used in replay, `fixtures/valio/2026-11-14-demo`: 769 products, recorded Saturday 14 Nov 2026 02:52 Helsinki time. Every figure of an offer below comes from the recording and names its clock: the **default clock** is the recording's own instant; the **demo clock** is Thursday 12 Nov 2026 14:15 Helsinki, a setting of ours (`TTA_DEMO_CLOCK`) that Valio allowed ("this is all static data so we can chose the date"). Every limit value, recipe, customer and customer history is ours and illustrative; the mock has no customer model.

**No model is called.** Sentences are read by fixed rules (`src/tta/agent/rules_reader.py`). The code keeps a client for a language model that a deployer may switch on with a key; no key is set in any run described here, and nothing below depends on one.

---

## Summary

### The pipeline

One Python process (FastAPI), the "gateway", between a buyer's agent and Valio's mock API. REST (`/v1/*`) and MCP (`/mcp/`, 13 tools) call the same service object (`src/tta/api/service.py`); the pages are a front end to the same functions.

1. **Request.** A typed request (`POST /v1/offers`, MCP `get_offer`): lines with a product type or product ids, quantity, unit, needed-by date, required claims and labels, allergen exclusions, whether the formula matters (`keep_formula`), a preference. Or a sentence (`POST /v1/requests/parse`, `POST /v1/agent/run`, the shop page).
2. **Reading.** A sentence is read by fixed rules and never guessed: what the rules cannot read comes back as a question (status 422 with the question), not as an offer for something else. *Run:* "some stuff for the weekend please" → 422, "By which day are the goods needed?"; "1,000 litres of lactose-free milk by Monday" → read, header `TTA-Read-By: rule-based`. The result is the same typed request as in step 1.
3. **Candidates.** Product types (32, ours), name terms, claims, pack size and lot step from the product file (`src/tta/catalog/`). No call to Valio yet.
4. **Lookup.** One price call and one availability call for the narrowed set (`src/tta/valio/`), from the mock or from the recording, never one of each. Every run described here used the recording.
5. **Offer.** Each product gets one of six availability states and a status per statement (price, quantity, delivery date, allergens, origin); the buyer's allergen exclusions are applied; at most three options are built, four under a preference (`src/tta/offers/options.py`). Everything left out is listed with a reason. The offer is signed by the gateway (item 13).
6. **Rules.** Each option is judged by rules kept as data (`src/tta/policy/rules.yaml`) with the buyer's own limits (`src/tta/policy/profiles/*.yaml`, four customers). The outcome is: the agent may order (`AUTO`), a named role must sign (`APPROVAL`), or it cannot be ordered (`BLOCK`).
7. **Order prepared.** `POST /v1/orders` with an `Idempotency-Key` (without one: 400). Price and availability are asked again; the rules run again. The order waits (`PENDING_APPROVAL`).
8. **A person confirms** (`POST /v1/approvals/{id}/decision`, page `/approvals`, the shop page). The check runs once more, then the order is `ORDERED`. An agent's token on this route is refused (403). **The agent orders alone** only when the buyer switched that setting on, no rule fired and every statement of every line is confirmed. The setting is off in all four shipped profiles, so in the build as shipped no order is placed without a person.
9. **Log.** Every step writes one event with one sentence built from a template, chained by SHA-256 hashes (`src/tta/audit/`). The buyer and Valio Aimo each read their own view (`GET /v1/audit?reader=buyer|supplier`).

"Ordered" means recorded in our order book. The mock has no order endpoint; the order step, its approval and its record are ours to define. Every order record says so, and says that no payment is taken.

### The 16 items

| # | Item of the brief | Our answer in one line | State at `c2106fe` | Not built |
|---|---|---|---|---|
| 1 | Core: lookup | Search, product and offer over REST and MCP, typed, with a status per statement; a discovery document | Works | — |
| 2 | Core: inquiry → order | Offer at Valio's fixed price → order with a re-check and an idempotency key; both signed by the gateway | Works | An order message to Valio's systems |
| 3 | Core: permission and approval | Rules as data, a buyer profile, named roles, an agent can never approve; ordering alone is a buyer setting, off by default | Works | — |
| 4 | Optional: delivery and sustainability | Reliability, carbon and labels per line; a preference with its price gap stated and capped | Works | Carbon as a category range |
| 5 | Optional: substitution, exceptions | Ranked substitutes, partial fill, unconfirmed alternative, a reason for every exclusion | Works | — |
| 6 | Optional: traceability | One sentence per step, rule ids with their facts, two views | Works | — |
| 7 | Scenario: need → recipe → order | Dishes × servings − kitchen stock → one offer → order | Works in part | Seasonal ingredient; recipe suggestion |
| 8 | Scenario: last-minute event | What cannot arrive in time is named; a stand-in by its role in the dish goes to a person | Works in part | A date of "tomorrow" that can be met in the recording |
| 9 | Scenario: supplier stock-out | Out-of-stock product → a substitute checked for allergens, claims and formula; stale offer → fresh offer | Works in part | Anything that runs before the kitchen asks |
| 10 | Scenario: proactive selling agent | Valio Aimo's own suggestion of a related product, as a tested function | Works in part: the function exists, no route or page serves it at this commit | A "new" or "seasonal" product: Valio's data marks neither |
| 11 | Scenario: allergen-safe substitution | A substitute never adds an allergen; the safe product first; formula compared; dietitian for doubt | Works | A nutrition standard for schools or hospitals |
| 12 | Scenario: standing-order drift | A renewal is compared with the median of its history before it is ordered | Works | — |
| 13 | Problem: trust protocol | A status per statement; a re-check before commitment; a hash-chained log; offers and orders signed by the gateway | Works | Statements signed by Valio |
| 14 | Problem: guardrails model | Eleven fixed rules no buyer can switch off, nine buyer limits, one "agent may order alone" setting | Works | — |
| 15 | Problem: response logic | Confirmed first, the safe product first, unconfirmed as a named alternative, substitutes ranked, partial fill stated | Works | — |
| 16 | Problem: audit trail | CloudEvents, append-only, hash chain, buyer view and supplier view with every rule that fired | Works | — |

Count: **12 work, 4 work in part** (items 7, 8, 9, 10), **0 not built**. At 18:00 the count was 11, 4 and 1.

---

## Core — the solution must enable

### 1. Product, price & availability lookup

> "Product, price & availability lookup: a structured way for an external agent to search for and retrieve what's available and at what price."

| | |
|---|---|
| **What we do** | Three typed calls. Search the catalog by product type, name terms (English or Finnish), claims, category, ids; read one product with its allergen statements (GS1 codes) and claims; ask for an offer, which adds Valio's price and availability. Each offer line carries one of six availability states (blocked · not deliverable · out of stock · order cut-off passed · quantity not confirmed · confirmed) and a status per statement. Valio is asked only for the candidates of one request (*run:* the log of the brief's request says "looked up price and availability of 26 products"), as Valio's slide asks ("Query the APIs only when needed, never for all product"). An agent that knows only the address finds the rest: `/.well-known/api-catalog` lists the REST base, the OpenAPI document, the schemas and the MCP endpoint, and `/llms.txt` says the flow in plain text. |
| **Where** | `POST /v1/products/search`, `GET /v1/products/{id}`, `POST /v1/offers`, `GET /v1/offers/{id}`; MCP `search_products`, `get_product`, `get_offer`. Schemas: `GET /openapi.json` (OpenAPI 3.1, generated from the models), `GET /v1/schemas` (JSON Schema, each naming its dialect). Code: `src/tta/catalog/search.py`, `src/tta/catalog/product_types.yaml`, `src/tta/valio/client.py`, `src/tta/valio/replay.py`, `src/tta/availability/states.py`, `src/tta/availability/claims.py`, `src/tta/api/discovery.py`. |
| **How we know it is right** | *Test:* `tests/mcp/test_tools.py`, `tests/api/test_discovery.py`. *Run:* the three calls, the two discovery documents and `/healthz`. Not re-run for this refresh, named for the reader: `tests/catalog/`, `tests/availability/`, `tests/valio/`, `tests/api/test_openapi_and_schemas.py`. Invariants: a stock figure of 999,999 or more is "quantity not confirmed" and is never used in arithmetic (Valio confirmed on 14 Nov that a very large value means the stock is not known); an absent field is unknown, never 0; a product the recording does not hold is `NOT_IN_RECORDING`, never presented as Valio's statement. |
| **State** | **Works.** Milk for coffee is a product type of its own, so "milk" holds 74 products (whole catalog, counted from `product_types.yaml`; Valio, asked whether a buyer who asks for milk accepts coffee milk: "no be explicit"). The offer for milk says coffee milk was left out and how to ask for it (*run*). |

### 2. Requesting price & availability, then placing an order

> "Requesting price & availability, then placing an order: a defined interaction for moving from inquiry to commitment, based on fixed prices rather than a negotiated quote."

| | |
|---|---|
| **What we do** | Inquiry: `POST /v1/offers` returns options at the price Valio's price call returned, each with `valid_until` (the earliest price validity and order cut-off of its lines). No field lets either side propose another price. Commitment: `POST /v1/orders` names one offer and one option. Before anything is recorded, price and availability are asked again and the rules run again. If something changed or expired, the answer is `409` with a new offer id and nothing is ordered (rule F-04: "An option that has expired, whose order cut-off has passed, or whose price or availability changed since the offer cannot be ordered. A fresh offer is needed."). The same `Idempotency-Key` returns the first result, so a retry never places a second order; a missing key is refused (400). A new order answers 201 with its address in `Location`. The order record keeps each price with its validity, each stock and delivery statement, and the time of the check. A total that holds a product sold by weight is called an estimate ("Valio Aimo invoices the weight delivered"). |
| **Where** | `POST /v1/offers` → `POST /v1/orders` → `GET /v1/orders/{id}`; MCP `get_offer`, `place_order`, `get_order`. Code: `src/tta/offers/revalidation.py`, `src/tta/orders/checking.py`, `src/tta/orders/service.py`, `src/tta/orders/records.py`, `src/tta/api/signing.py`. |
| **How we know it is right** | *Run:* offer → order (201, `PENDING_APPROVAL`, `Location: /v1/orders/…`) → the purchasing manager's decision (200, `ORDERED`); the same order call without a key → 400. *Test:* `tests/e2e/test_guards.py` (the same key twice places one order), `tests/api/test_signing.py`. Not re-run, named: `tests/orders/` (17 files), `tests/offers/test_revalidate.py`, `tests/api/test_flow.py`, `tests/mcp/test_flow.py`. |
| **State** | **Works**, with a person confirming every order in every shipped profile. Offers and orders carry a `proof`: a signature by the gateway (item 13). **Not built:** a message Valio's systems take. The mock has no order endpoint, by design; "ordered" is a record in our book, and the record says "It commits nobody. No payment is taken here". Mapping that record to an open ordering format is a written next step (`docs/STANDARDS.md`), not code. |

### 3. Permission & human-approval management

> "Permission & human-approval management: what the agent may decide on its own, and what must go to a human for sign-off."

| | |
|---|---|
| **What we do** | The agent's authority comes from its bearer token, which is bound to one customer's profile; it is never a field of the request, so an agent cannot choose its own limits. `GET /v1/authority` returns the profile and every rule as a sentence with that profile's values. **The agent decides alone:** reading the request or asking about it, leaving products out, combining products, choosing a substitute, the re-check, preparing the order, naming who must sign. **A person decides:** placing the order. Valio's answer on 14 Nov: "the final submition should always have the input from the user". **Ordering alone is a buyer setting** (`auto_order_enabled`), off in all four shipped profiles. Switched on, the agent orders alone only when no rule fires and all five statements of every line are confirmed: price, quantity, delivery date, allergens and origin (Valio, second visit: "after and if you are 100% sure yes"). Rule F-10 says which case applies: "The agent prepares the order, a person confirms it." An approval names the roles it needs (purchasing manager, finance, dietitian) and is complete when people holding all of them have signed; the approver may pick another option of the same offer, and the rules run again on it. |
| **Where** | `GET /v1/authority`, `GET /v1/approvals`, `POST /v1/approvals/{id}/decision`; page `/approvals`; shop page `/shop`; MCP `get_authority` (none of the 13 MCP tools approves). Code: `src/tta/policy/rules.yaml`, `src/tta/policy/engine.py`, `src/tta/policy/human_approval.py`, `src/tta/policy/profiles/`, `src/tta/orders/access.py`, `src/tta/api/identity.py`. |
| **How we know it is right** | *Run:* the hotel agent's token on the decision route → 403; the ward's 200 L at both clocks fires F-10 and nothing else. *Test:* `tests/e2e/test_no_order_without_a_person.py` (REST, agent run, standing-order renewal, menu plan: each waits for a person), `tests/api/test_ordering_alone.py` (setting on: the ward's 200 L, €402.00, ordered alone; an unconfirmed quantity still goes to a person), `tests/policy/test_four_customers.py` (no shipped profile lets the agent order alone; every role a profile names is a person of the customer file), `tests/mcp/test_approval.py`, `tests/e2e/test_guards.py`. Not re-run, named: the rest of `tests/policy/` (26 files; `test_rulebook.py`, `test_profiles.py`), `tests/orders/test_decide.py`, `test_access.py`. |
| **State** | **Works**, both sides of the brief's sentence: what goes to a person (the default, and always under the fixed rules) and what the agent may do alone (a setting the buyer turns on, bounded by the same rules). The autonomous path is narrow on purpose: a request with no needed-by date has no confirmed delivery date, so it is never ordered alone (`tests/policy/test_ordering_alone.py`, not re-run). |

---

## Optional – open directions

### 4. Delivery time & sustainability comparison

> "Delivery time & sustainability comparison: not just price, but delivery reliability and the certificates/sustainability labels already shown in the webshop. (Category-level carbon-footprint ranges are a stretch goal.)"

| | |
|---|---|
| **What we do** | Each offer line shows its delivery reliability, carbon figure and certificate labels from Valio's files. Each option states its earliest and latest delivery, lowest reliability, an estimated carbon total and the labels every line carries. A request may set `prefer` to `EARLIEST`, `RELIABILITY` or `LOWER_CARBON`, and may require labels (for example `EU_ORGANIC_FARMING`). Under a preference the offer adds the cheapest confirmed option and says the difference in euros and what it buys. A preference that costs more than 25% above the cheapest confirmed option comes second, not first, and a known reliability under 90% ranks with an unknown one (both thresholds are ours and are named as ours). A profile may set a lower share (ward and bakery: 10%) above which a person decides: rule P-09, "An option ranked by a preference (most reliable, lowest carbon, earliest) that costs more than … above the cheapest confirmed option goes to the purchasing manager." A missing value is unknown, never 0 and never imputed. |
| **Where** | Fields `prefer`, `lines[].required_labels` on `POST /v1/offers`; option kind `CHEAPEST_CONFIRMED`. Code: `src/tta/offers/preference.py`, `src/tta/offers/comparison.py`, `src/tta/policy/premium_facts.py`, `src/tta/catalog/loader.py`. |
| **How we know it is right** | *Run, hotel, 100 L of plant drink, `prefer: RELIABILITY`, both clocks:* first `470863` at €140.00, "€7.00 more than the cheapest confirmed option, for a delivery reliability of at least 100% instead of unknown, a premium of 5.3%"; then the cheapest confirmed, `472145` at €133.00; then the unconfirmed alternative. *Test:* `tests/offers/test_preference_guard.py`, `tests/policy/test_preference_premium.py`. Not re-run, named: `tests/offers/test_preference_offer.py`, `test_required_labels.py`, `tests/catalog/test_labels.py`. |
| **State** | **Works.** Coverage of Valio's data, whole catalog (pinned by `tests/catalog/test_loader.py`): reliability on 4,425 products, carbon on 11,033. **Limit:** an earlier measurement over 18 offers of the recording (`AIMO/build/replan/P2-scenarios.md`; not re-measured for this refresh) found that "earliest" and "lower carbon" changed no first option; we show the preference on the oat-drink case above and claim no more. **Not built:** carbon as a category range; we show Valio's figure per product. |

### 5. Substitution and other exception handling

> "Substitution and other exception handling: what happens when the exact request can't be met. (Last year's Zero-Fail Logistics challenge covered failed deliveries in depth, so this isn't scored as core.)"

| | |
|---|---|
| **What we do** | Each condition of the mock has one defined answer, and the offer says which applied. A substitute comes from the pairs Valio lists and from the same 5-digit category, nothing wider (Valio could not confirm that the digits of a category are levels). It passes four gates in order: it adds no allergen; it keeps the dietary claims; it is the same kind of product (same product type, not flavoured where the original is plain); its formula is compared. A candidate that fails the second or third gate is a last resort: held back while a like-for-like candidate can be ordered, and always sent to a person when shown. Each candidate carries one sentence that starts "Replaceable: …" or "Not a like-for-like replacement: …". |
| **Where** | `POST /v1/products/{id}/substitutes`, MCP `find_substitutes`; options of `POST /v1/offers`. Code: `src/tta/offers/combining.py`, `options.py`, `planning.py`, `substitutes.py`, `stand_ins.py`, `formula.py`, `substitute_wording.py`, `src/tta/catalog/kinds.py`, `src/tta/allergens/substitution.py`. |

| Condition | What the agent does | Rule that sends it to a person |
|---|---|---|
| Confirmed stock covers part of the quantity | Combines confirmed products cheapest first; says how much is missing | P-03: "An option that covers less than [the profile's share] of the requested quantity goes to the purchasing manager." |
| Quantity not confirmed | Never the suggestion; offered as "Alternative: quantity not confirmed"; not offered at all when it costs no less than confirmed stock that covers the line | F-01: "A product whose quantity Valio Aimo does not confirm always goes to the purchasing manager." |
| Order cut-off passed | Left out, with the reason; `closingTime` is read literally | — |
| Delivery later than needed | Left out; the note names the earliest date Valio states | F-07: "When the request gives a needed-by date, an option that does not verifiably meet it always goes to the purchasing manager." |
| A named product cannot be supplied in full | Confirmed like-for-like stock stands in first; the named product stays as the unconfirmed alternative | F-05 blocks a substitute that adds an allergen · F-08: "A substitute that lacks a nutritional claim of the product it replaces, for example lactose-free, always goes to the purchasing manager." · F-12: "A substitute that is a last resort (it lacks a dietary claim of the product asked for, is flavoured where that product is not, or is another product type) always goes to the purchasing manager." · P-05: a substitute outside what the profile accepts |
| The formula matters (the request line or the profile says so) and the substitute's formula differs or cannot be compared | Shown as "Alternative: a substitute that does not keep the formula", after the product asked for | F-11: "Where a request line says the formula matters, a substitute whose formula differs from the original's, or cannot be compared, always goes to the purchasing manager." |
| Price or stock changed between offer and order | Nothing ordered; a fresh offer id is returned | F-04 (a block) |
| Sold by variable weight | Total marked as an estimate ("about € …") | P-06: "A product sold by variable weight goes to the purchasing manager: its total is an estimate, because Valio Aimo invoices the weight delivered, which can be lower or higher than the weight ordered." |
| No allergen data | Unknown, not safe (item 11) | P-04: a product that does not rule out an excluded allergen goes to the dietitian |

| | |
|---|---|
| **How we know it is right** | *Run, hotel, 100 L of the barista oat drink `473609` (quantity not confirmed in the recording).* Default clock: first a substitute, 100 × `475224` (another barista oat drink), €174.00, F-10 only; then the product itself, €137.00, quantity not confirmed (F-01). Demo clock: first the product itself, €137.00 (F-01); then the product Valio lists as its substitute, 10 cases of `471690`, €155.50, which also fires F-01 at that clock. *Test:* `tests/e2e/test_scenario_3_substitutes.py`, `tests/offers/test_substitutes_replaceable.py`, `test_substitutes_formula.py`, `test_profile_formula.py` (bakery, 40 kg of crème fraîche `477055`: the product itself unconfirmed €214.40, then tzatziki `470260` €240.40 as "a substitute that does not keep the formula"), `tests/policy/test_last_resort.py`, `tests/policy/test_formula_rule.py`. Not re-run, named: `tests/offers/test_combining.py`, `test_offer_substitute.py`, `tests/allergens/test_substitution.py`, `tests/e2e/test_backup_beef.py`. |
| **State** | **Works.** The formula measure is ours: six nutrients within 15% or 1 g, salt within 0.25 g, the same fat source (`src/tta/offers/formula.py`); the tolerances wait for a biomedical team member's signature. 11,511 of 17,546 products state all six nutrients (whole catalog, pinned by `tests/catalog/test_nutrition.py`); a substitute that cannot be compared counts as not keeping the formula. **Limit:** the answer for scenario 3 differs between the two clocks, and both are shown above. |

### 6. Traceability and explainability

> "Traceability and explainability: a human-readable record of what the agent did and why."

| | |
|---|---|
| **What we do** | One event per step: request received, request read, lookup performed, offer created, rules evaluated, approval requested, approval decided, order confirmed, rejected, expired, blocked or not placed, authorisation refused, evidence attached, standing order created or renewed. Each event has who acted, the rule ids with the facts they read, the hash of the rules and profile in force, and one sentence written from a template. Example (*run*, the brief's request for the hotel): "The agent cannot place this order alone: the total of €1,083.39 before tax is above the €750 limit per order of Harbourside Hotel (P-01) and only 43.5% of the requested quantity is covered, below the 90% minimum (covered: 435 of 1,000 L) (P-03). It needs the purchasing manager." Every excluded product keeps its reason code and sentence on the offer. |
| **Where** | `GET /v1/audit?order_id=&offer_id=&reader=`, MCP `get_audit`, page `/orders/{id}`, the shop page. Code: `src/tta/audit/trail.py`, `sentences.py`, `supplier_sentences.py`, `supplier_decisions.py`, `chain.py`. |
| **How we know it is right** | *Run:* one order from request to a person's confirmation wrote nine events, in the order above. *Test:* `tests/audit/test_supplier_decisions.py`, `test_pinned_hashes.py`. Not re-run, named: `tests/audit/test_sentences.py`, `test_sentence_guards.py`, `test_envelope.py`, `test_chain.py`, `test_log_wording.py`, `tests/orders/test_audit_trail.py`, `tests/api/test_audit.py`. |
| **State** | **Works.** Sentences name the customer ("of Harbourside Hotel"), never a profile id. Two event types for suggestions (`suggestions.shown`, `suggestion.accepted`) are defined with their sentences; nothing writes them at this commit (item 10). |

---

## Example scenarios

The brief calls these "example scenarios to spark ideas". Two are covered in full (11, 12), four in part.

### 7. Need → recipe → order

> "Need → recipe → order: a chef plans next week's menu around a seasonal ingredient. The agent suggests recipes, works out what's missing from stock, and places the order."

| | |
|---|---|
| **What we do** | The buyer picks dishes and servings and states what the kitchen holds. The planner expands the recipes, takes the stock off dish by dish, adds up per product type, and asks for one offer; the order goes through the normal flow and waits for a person. A menu of two dishes and seven lines is planned. An ingredient that cannot be sourced stays in the offer with nothing offered, so the rules judge the whole menu and not only what could be found. |
| **Where** | `GET /v1/menus/recipes`, `POST /v1/menus/plan`, MCP `plan_menu`, page `/menu`. Code: `src/tta/menus/needs.py`, `planner.py`, `recipes.yaml` (ours and illustrative: Valio publishes no recipes). |
| **How we know it is right** | *Test:* `tests/menus/test_planner.py` (beef stew and a quark dessert: four lines, €476.48 for the first option, the quark replaced by its role), `tests/api/test_menu_offers_and_locations.py` (two dishes, seven lines), `tests/mcp/test_more_tools.py` (the same plan over MCP, ordered like any other offer). Not re-run, named: `tests/menus/test_needs.py`, `test_recipes.py`, `test_routes.py`, `test_review_a2a.py`. |
| **State** | **Works in part.** **Not built:** the seasonal ingredient and the suggestion of recipes around it. The product file has no season or "new" field. The buyer chooses the dishes. The recording holds dairy, plant drinks and fresh beef, so a dish that needs flour, eggs or sugar is planned with those ingredients listed as not sourced, and waits for a person. |

### 8. Last-minute event

> "Last-minute event: an unexpected booking for tomorrow. The agent identifies what the recipes require, flags what can't be sourced in time, and proposes substitutions through recipe logic rather than a simple SKU swap."

| | |
|---|---|
| **What we do** | Same planner. For each ingredient that cannot arrive by the date, the plan says why and tries the alternatives the recipe lists for that ingredient's role in the dish, best first, each with one sentence on what changes in the dish. A stand-in names the allergens it adds to the dish. A line that stands in for the recipe's own ingredient always goes to a person: rule F-09, "A product type that recipe logic chose in place of a recipe's own ingredient always goes to the purchasing manager, who checks that the dish still works." No buyer can switch it off. An ingredient with no working alternative is listed as "Cannot be sourced". |
| **Where** | `POST /v1/menus/plan`; `/menu?example=event`. Code: `src/tta/menus/planner.py`, `plan.py`, `allergens.py`, `wording.py`; fields `stands_in_for`, `stands_in_role` on the request line. |
| **How we know it is right** | *Test:* `tests/menus/test_planner.py`. Not re-run, named: `tests/menus/test_review_a2a.py` (a stand-in names the allergens it declares), `tests/policy/test_stands_in_for.py`. |
| **State** | **Works in part.** **Limits, stated plainly:** the role alternatives are written by us in the recipe file, not derived from product data. The example asks for Monday, not for "tomorrow": by an earlier count (`AIMO/USE-CASES.md`; not re-counted for this refresh) every dated delivery in the recording is Monday 16 Nov, so a request for the day after the clock gets no option and the earliest date instead. |

### 9. Supplier stock-out

> "Supplier stock-out: a key product runs out mid-week. The agent proposes a recipe-compatible substitute before the kitchen notices the gap, and explains the trade-off."

| | |
|---|---|
| **What we do** | A product asked for by id that cannot be supplied in full gets a stand-in, and the offer says what is given up in numbers (formula, pack, price, claims). "Recipe-compatible" has a measure: the formula comparison of item 5, and rule F-11 sends a formula-changing substitute to a person where the formula matters. A product that runs out between offer and order gives `409` and a fresh offer. |
| **Where** | `POST /v1/offers` with `product_ids`; `POST /v1/products/{id}/substitutes`. Code: `src/tta/offers/substitutes.py`, `stand_ins.py`, `formula.py`, `src/tta/api/service.py` (`_fresh_offer`). |
| **How we know it is right** | *Run and test:* as item 5. *Test:* `tests/offers/test_substitutes_formula.py` (bakery cream: 37 L of `464727`, confirmed and of the same formula, stands in before 52 L of an unconfirmed product; €549.65 for 85 of 100 L). |
| **State** | **Works in part.** **Not built:** "before the kitchen notices". Nothing runs without a request: no scheduler, no subscription. The fresh offer is built on the order call only; a stock-out while an order waits for approval refuses the approval and leaves the order waiting. |

### 10. Proactive selling agent

> "Proactive selling agent: Valio Aimo's own agent spots a new or seasonal product and proactively suggests it to the buyer's agent."

| | |
|---|---|
| **What we do** | **Valio Aimo's own suggestion of a related product.** It is a product of the same product type and the same brand as one the customer usually orders, that is in none of the customer's past orders and not in the request, with confirmed stock (at least two sales units). It is checked like any product: the customer's allergen rule, required claims, stock for the date, formula. It is labelled as serving the supplier (`serves: SUPPLIER`, sentence "Valio Aimo suggests …"), comes last and apart from the buyer's own suggestions, and there is never more than one. It stays silent when only another kind of pack passes (a portion milk for a school's bulk order). It is shown, never applied: accepting it builds a new offer under every rule. Beside it, from the customer's own history: the forgotten item, the usual product and quantity, a cheaper product of the same formula, a larger pack, a quantity trend; at most one per kind and three in all. |
| **Its limit** | It is **"related", not "new" or "seasonal"**. The product file marks neither: of its fields only `synkkaData.lastUpdated` is a date, and it says when the record changed, not when the product was launched (`src/tta/suggestions/supplier.py`; question D4 for Valio). The customers' histories it compares with are synthetic and labelled so. Nothing is pushed: the suggestion is computed when the buyer asks for an offer. |
| **Where** | `src/tta/suggestions/supplier.py`, `service.py` (`suggestions_for`), `guard.py`, `thresholds.py` (every threshold named, ours); `src/tta/customers/data/*.yaml`; the contract field `Offer.suggestions`; the log's events `suggestions.shown` and `suggestion.accepted` (`src/tta/audit/suggestion_sentences.py`). |
| **How we know it is right** | *Test:* `tests/suggestions/test_supplier_and_standing_trend.py` (every related product is of the same type and brand as a usual one and was never ordered), `test_service.py` (hotel, 100 L of `469363`: the forgotten cooking cream `463797`, +€33.10), `test_guard.py` (the school's suggestions that state nothing on nuts or sesame are dropped). *Run:* three offers through `POST /v1/offers` at both clocks each came back with `suggestions: []`. |
| **State** | **Works in part.** At commit `c2106fe` the suggestions are tested functions and a field of the offer that **the gateway does not fill**: no route, tool or page shows one. **Not committed:** the wiring (lane `L4-2d`: `src/tta/api/suggesting.py`, the suggestions on every offer, `GET /shop/api/suggestions`, the two events written) was in the working tree and unfinished when this was written. Until it is committed and re-measured, a demo cannot show this item on screen. |

### 11. Allergen-safe substitution under pressure

> "Allergen-safe substitution under pressure: in a school or hospital kitchen, a substitution must still satisfy strict allergen and nutrition rules."

| | |
|---|---|
| **What we do** | **Allergens.** Exclusions are GS1 allergen codes on the profile or the request; a request can add one and never remove one; an exclusion with no rule named is read as strict. Under the strict rule: "free from" passes; "contains" is rejected and can never be ordered (rule F-02: "A product that declares an allergen the buyer excludes can never be ordered, even with approval."); "may contain", "undeclared" or no statement goes to the dietitian (rule P-04). **The safe product is first:** with an allergen excluded, the first option holds only products whose data rules it out; a doubtful one is "Alternative: allergen not ruled out" and ranks after every safe option at any price. A nutritional claim is never an allergen statement (lactose-free milk still declares milk), and a product whose own allergen data contradicts a claim the request requires is left out with a reason of its own. A substitute may never declare an allergen the original does not, for any buyer (rule F-05, a block). **Two customers show it:** the hospital ward (no milk, no gluten, strict, confirmed data only, every substitute to a person) and the school (no tree nuts, peanuts or sesame, strict). When the dietitian is asked about a missing statement, what a recorded manufacturer's page says is shown beside it, labelled as not Valio data; it can add a doubt and never removes one. **Nutrition.** A substitute's six nutrients and fat source are compared with the original's (item 5). |
| **Where** | `src/tta/allergens/codes.py`, `exclusion.py`, `ingredients.py`, `substitution.py`, `claims.py`; `src/tta/offers/safety.py`; `src/tta/policy/profiles/allergy-ward.yaml`, `school-kitchen.yaml`; `src/tta/evidence/`. |
| **How we know it is right** | *Run, ward, 200 L of a plant drink, no milk, no gluten, confirmed only, both clocks:* 200 × `464013`, €402.00, 41 products left out with a reason each, F-10 only. *Test:* `tests/e2e/test_scenario_2_allergy_ward.py`, `tests/offers/test_safe_first.py` (hotel, plant drink without gluten: €20.10 safe first, €17.40 not ruled out second), `tests/policy/test_four_customers.py` (a school product that says nothing about nuts goes to the dietitian), `tests/evidence/test_recordings.py` (13 recorded pages: 9 kept as evidence, 4 dropped), `test_every_doubt.py`. Not re-run, named: `tests/allergens/` (9 files). |
| **State** | **Works**, with two limits. The "nutrition rules" are a comparison of a substitute with the product it replaces, not a school or hospital diet standard: none is encoded. And the school's strict rule sends every confirmed bulk milk and yoghurt to the dietitian, because those products state nothing about tree nuts, peanuts or sesame; that is the rule working, and it means the school's demo always ends with the dietitian. |

### 12. Standing order drift detection

> "Standing order drift detection: the agent learns a kitchen's recurring weekly order and flags anomalies (portion counts creeping up, cost drifting) before auto-renewing it."

| | |
|---|---|
| **What we do** | A standing order is renewed through the normal offer and order. Before the order, each line's quantity and each product's unit price are compared with the median of its last 6 renewals (at least 3 are needed to judge). Beyond the buyer's tolerance (ward 10%, the other three 25%; ours) the renewal goes to a person: rule P-08, "A renewal of a standing order whose quantity or unit price on a line differs by more than [the tolerance] from the median of that line's last 6 renewals goes to the purchasing manager. With fewer than 3 past renewals the history is too short to judge, and the renewal says so." Only ordered renewals count as history. Each of the four customers has a standing order built from its customer file, whose past orders are synthetic and marked so. A buyer holds at most 20 standing orders. |
| **Where** | `POST /v1/standing-orders`, `GET /v1/standing-orders`, `GET /v1/standing-orders/{id}`, `POST /v1/standing-orders/{id}/renew`; MCP `set_up_standing_order`, `renew_standing_order`, `list_standing_orders`; page `/standing-orders`. Code: `src/tta/standing/service.py`, `history.py`, `src/tta/policy/drift.py`, `standing_facts.py`. |
| **How we know it is right** | *Test:* `tests/standing/test_history_counts_ordered.py`, `test_set_up_limits.py`, `tests/mcp/test_more_tools.py` (a standing order set up over MCP is the one REST lists, and its renewal waits for a person), `tests/suggestions/test_supplier_and_standing_trend.py` (the school's oat drink shows a trend and no other line does). Not re-run, named: `tests/standing/test_renewal_flow.py`, `test_customer_standing_orders.py`, `tests/policy/test_standing_drift.py`. |
| **State** | **Works.** "Learns" is a median over a window, by choice: the buyer can recompute it. "Creeping up" below the tolerance is the trend function (`src/tta/suggestions/trend.py`), which is tested and, at this commit, shown on no page (it is part of the uncommitted wiring of item 10). |

---

## Problems they would love tackled

### 13. Trust protocol

> "Trust protocol: the minimum data/verification standard for an external agent to trust Valio Aimo's claims on stock, price and origin without a manual check."

| | |
|---|---|
| **What we do** | Our proposal for the minimum standard has five parts. (1) **A status per statement, per line**: `CONFIRMED`, `UNKNOWN` or `RULED_OUT`, with one sentence. (2) **A re-check before commitment**: the supplier is asked again at order time and at approval time. (3) **A record of what was relied on**: the order keeps each statement with its validity. (4) **A log neither side can change unseen**: a SHA-256 hash chain whose head `/healthz` publishes. (5) **A signature on every offer and order**: Ed25519, a detached JSON Web Signature over the record's canonical JSON, with the public key at `/.well-known/jwks.json`, so a buyer can show later exactly what it was offered. |
| **Where** | `claims[]` on every offer line; `proof` on every offer and order; `src/tta/availability/claims.py`; `src/tta/offers/revalidation.py`; `src/tta/audit/chain.py`; `src/tta/api/signing.py`, `keys.py`. |

| Statement | Confirmed when | Unknown when | Ruled out when |
|---|---|---|---|
| Price | a price was returned and its validity is in the future | no usable price | — |
| Quantity (stock) | the stock figure is a real number and covers the line | the figure is a placeholder (999,999 or more) | out of stock, not deliverable, blocked |
| Delivery date | the cut-off is open and the delivery date is on or before the needed-by date | the request gives no date | cut-off passed, or later than needed |
| Allergens | every excluded allergen has an explicit statement | "may contain", "undeclared" or no statement | an excluded allergen is declared |
| Origin | the product file states it | absent | — |

| | |
|---|---|
| **How we know it is right** | *Run:* an offer and its order each carry `proof` (`algorithm: EdDSA`, `canonicalization: RFC 8785`, `demo_key: true`); `/.well-known/jwks.json` serves one Ed25519 key; `/healthz` names the key and the log's head. *Test:* `tests/api/test_signing.py` (an offer verifies with the published key and fails on a changed price; what is stored and what the log holds carry no proof), `tests/audit/test_pinned_hashes.py`. Not re-run, named: `tests/availability/test_claims.py`, `tests/offers/test_revalidate.py`, `tests/audit/test_chain.py`, `test_head.py`. |
| **State** | **Works**, and says what it is not. **The signature is the gateway's, not Valio's.** With no `TTA_SIGNING_KEY` set, the key is a demo key generated at start and gone at the next start, and every proof says so ("nothing is claimed about this signature beyond this run"). "Confirmed" still means "Valio's API said so at this time". The chain shows a changed, removed or inserted event; it does not show the newest events cut off, or a rewrite by whoever owns the database, unless another party holds the head. A scheduled witness of the head exists as code (`deploy/witness.py`) and has never run. Origin gates one thing only: with ordering alone switched on, an unknown origin sends the order to a person. **Not built, and outside our reach:** Valio signing its own statements. |

### 14. Guardrails model

> "Guardrails model: which decisions require human sign-off (spend threshold, substitutions outside stated preferences) vs. fully autonomous."

Rules are data (`src/tta/policy/rules.yaml`), evaluated by one deterministic engine; the most severe outcome of the rules that fire wins. A profile file that names a fixed rule, or carries a setting not listed, is rejected when it loads. F-10 is the one rule kept in code (`src/tta/policy/human_approval.py`), because it fires only when no other rule asks for a person; its texts are part of the policy hash.

| Rule | In words | Outcome | Who signs |
|---|---|---|---|
| **Fixed: no buyer can switch these off** | | | |
| F-01 | A product's quantity is not confirmed by Valio Aimo | Person | Purchasing manager |
| F-02 | A product declares an allergen the buyer excludes | Blocked | — |
| F-03 | A fact a rule needs is missing: missing data never counts as good data | Person | The role the fact names |
| F-04 | The option expired, its cut-off passed, or its price or availability changed since the offer | Blocked; fresh offer | — |
| F-05 | A substitute declares an allergen the original does not | Blocked | — |
| F-06 | An agent can never approve an order, its own included | Refused | — |
| F-07 | A price is not confirmed, a delivery date is ruled out, or a needed-by date is not verifiably met | Person | Purchasing manager |
| F-08 | A substitute lacks a nutritional claim of the product it replaces, for example lactose-free | Person | Purchasing manager |
| F-09 | A product type that recipe logic chose in place of a recipe's own ingredient | Person | Purchasing manager |
| F-11 | The formula matters and a substitute's formula differs or cannot be compared | Person | Purchasing manager |
| F-12 | A substitute is a last resort: it lacks a dietary claim, is flavoured where the original is not, or is another product type | Person | Purchasing manager |
| **Set by the buyer (values are ours, illustrative)** | | | |
| F-10 | The agent prepares the order, a person confirms it (the setting "agent may order alone" is off, or it is on and a statement is not confirmed) | Person | Purchasing manager |
| P-01 | The order is above the spend limit per order (hotel €750, ward €500, school €250, bakery €300) | Person | Purchasing manager |
| P-02 | The day's orders, this one included, pass the limit per day (hotel €3,000, ward €1,500, school €800, bakery €1,000); orders waiting for a person count | Person | Finance |
| P-03 | The option covers too little of the quantity (hotel 90%, the other three 100%) | Person | Purchasing manager |
| P-04 | A product does not rule out an excluded allergen | Person | Dietitian |
| P-05 | A substitute is outside what the profile accepts (hotel: same category or listed; school: listed by Valio; ward and bakery: none) | Person | Purchasing manager |
| P-06 | A product is sold by variable weight, so the total is an estimate | Person | Purchasing manager |
| P-07 | A product carries a deposit the total leaves out | Person | Finance |
| P-08 | A standing order's renewal drifts from its history (ward 10%, the others 25%) | Person | Purchasing manager |
| P-09 | A preference costs more than the profile's share above the cheapest confirmed option (ward and bakery 10%; hotel and school set none) | Person | Purchasing manager |

| | |
|---|---|
| **Where** | `GET /v1/authority` (the rules in sentences with the caller's values and the hash of the rules in force); `GET /v1/customers` (the caller's own customer: people, usual products, limits; Valio's token is refused, 403); pages `/kitchen` and the shop's settings, where a visitor sets a profile of their own. |
| **How we know it is right** | *Run:* the rules fired in every case above. *Test:* `tests/policy/test_last_resort.py` (a rules file that weakens or drops F-12 does not load; no profile setting lets a last resort through), `test_formula_rule.py`, `test_preference_premium.py`, `test_four_customers.py`, `tests/api/test_customers.py`. Not re-run, named: `tests/policy/test_rules.py`, `test_rulebook.py`, `test_authority.py`, `test_missing_facts.py`, `test_custom_profile.py`, `test_hash.py`, `test_day_spend_parts.py`, `tests/orders/test_spend.py`. Invariants: the rules run when the option is built, again when the order is placed, again when a person decides; a missing fact asks for a person, it never passes. |
| **State** | **Works.** F-12 closed a hole found during the build: with ordering alone switched on, a flavoured or other-type substitute fired no rule of its own. Rule P-00 is retired. |

### 15. Response logic

> "Response logic: how an agent handles partial availability and substitution ranking ("good-better-best") within Valio Aimo's own assortment."

| | |
|---|---|
| **What we do** | **Options, in this order:** (1) confirmed stock only — the cheapest product that covers the quantity, else a combination cheapest first, else a partial fill that says how much is missing; (2) labelled alternatives a person can pick: "Alternative: quantity not confirmed", "Alternative: allergen not ruled out", "Alternative: a substitute that does not keep the formula"; (3) a substitute, when a named product cannot be supplied. An option that holds an unconfirmed quantity or a doubt is never the suggestion while a safe, confirmed one exists. **Substitutes** come only from Valio's assortment: the pairs Valio lists and the same 5-digit category. They are ranked: passes the allergen rule → keeps every dietary claim → same kind of product → formula → listed by Valio → closest pack → confirmed → price. One that fails the allergen rule is still shown, with its reason, and can never be ordered. |
| **Where** | `src/tta/offers/options.py`, `combining.py`, `planning.py`, `safety.py`, `substitutes.py`; `POST /v1/products/{id}/substitutes`. |
| **How we know it is right** | *Run, the brief's own request, hotel, both clocks:* "Best confirmed option (partial fill)": 384 × `469363` + 51 × `462775`, 435 of 1,000 L, €1,083.39, to the purchasing manager (P-01, P-03); "Alternative: quantity not confirmed": 1,000 × `464306`, €1,010.00 (F-01, P-01); a note says coffee milk was left out. 17 products left out with reasons at the default clock, 2 at the demo clock. *Test:* `tests/e2e/test_scenario_1_milk.py`, `tests/offers/test_safe_first.py`. Not re-run, named: `tests/offers/test_scenario_1_milk.py`, `test_combining.py`, `test_plain_milk.py`, `test_dearer_unconfirmed.py`, `test_coffee_milk.py`. |
| **State** | **Works.** The brief's own request ends in a partial fill in the recording: confirmed lactose-free milk covers 435 of 1,000 litres. That is the mock's condition, and the offer says it in its first line and gives the person both choices. |

### 16. Audit trail

> "Audit trail: a usable, human-readable log of an agent's purchasing decisions, for both buyer and Valio Aimo."

| | |
|---|---|
| **What we do** | One log, two views. **The buyer** sees everything about its own requests: options, exclusions with reasons, rules fired, limits, approvers and their notes; never another buyer's events. **Valio Aimo** sees what was asked of its data, what was offered and ordered, the statements each order relied on, the agent's identity, whether a person approved, **every rule that fired** with its reason, and the products left out by reason. Valio asked for "all the steps and decisions" and "the logic behind it and product considered". What stays the buyer's: limit amounts, allergens and the products they concern, the approver's name (the role is shown) and notes. Example of Valio's view (*run*): "Rules that applied: P-01, a rule the buyer set (the order is above the spend limit per order; the amount is not shown): approval by the buyer's purchasing manager." Events are CloudEvents 1.0, stored append-only; database triggers refuse an update or a delete. Audit times are real UTC time even when the offers run on the recording's clock. |
| **Where** | `GET /v1/audit?reader=buyer|supplier`, MCP `get_audit`, page `/orders/{id}`, `GET /shop/api/audit`. Code: `src/tta/audit/views.py`, `readers.py`, `supplier_decisions.py`, `trail.py`; `src/tta/store/schema.py`, `src/tta/store/sql/`. |
| **How we know it is right** | *Run:* Valio's token read the log of the brief's request: seven events up to the approval request, each rule with its reason and no amount. *Test:* `tests/audit/test_supplier_decisions.py`, `test_sql_view.py` (the SQL view and the reader list the same fields; compared as text, not executed), `test_pinned_hashes.py` (17 stored rows and a chain head still hash the same, so the log already stored stays valid). Not re-run, named: `tests/audit/test_views.py`, `test_phrases.py`, `tests/store/`, `tests/api/test_audit.py`. |
| **State** | **Works** on SQLite, which every run here used. **Not run:** the PostgreSQL form of Valio's view (`src/tta/store/sql/003_reader_views.sql`) was rewritten tonight and has not been executed against a database; `tests/store_pg/` needs one and is skipped offline. |

---

## Does this make sense? Gaps and weak spots

Ranked by what each costs against the judging criteria. "Smallest change" is the least work that closes it. Of the 16 gaps listed at 18:00, ten are closed (the reader's wrong readings, substitutes that ignored use and formula, a doubtful product ranked first, Valio's view hiding the buyer's rules, nothing signed, the `Origin` check and discovery document, menus and standing orders as MCP tools, the missing school and bakery profiles, the partial fill unexplained, coffee milk in the brief's own answer). What remains:

| # | Gap | Costs on | Smallest change |
|---|---|---|---|
| 1 | **The public link runs an older build.** Nothing of tonight is deployed; a redeploy is a person's action. The older build answers the brief's own request with coffee milk in it. | 30% demo | One redeploy in replay with the demo clock, then `deploy/check.py` against it. |
| 2 | **The demo set has not been re-measured as a whole** (task `E1`). The figures in this document were measured for this refresh or are pinned by the tests named; `docs/DEMO.md` and `docs/PITCH.md` are written after `E1` and may still carry older figures. | 30% demo | Run `E1` at both clocks; `tests/e2e/test_demo_script.py` then pins the script. |
| 3 | **Suggestions reach no screen at this commit** (item 10): tested functions, an empty field on the offer. | 20% precision; the brief's scenario | Commit lane `L4-2d` and measure one offer with a suggestion and Valio's own. |
| 4 | **The shop page has not been seen in a real browser** (layout, phone width, keyboard). It was checked by driving its code against a local gateway. | 30% demo | Open `/shop` once before the video. |
| 5 | **The reader asks more than it reads.** Of the 68 sentences of `docs/READING-TABLE.md`, the fixed rules read 37 and ask about 31; one is read wrong ("24 litres of Arla lactose-free whipping cream": the brand is dropped without a word). Asking is the safe failure, and it is the only reader a judge meets. | 20% precision | Lane `L1-3` (not committed) keeps a brand word; the table is regenerated by its test. |
| 6 | **Scenario 3 gives a different answer at each clock** (a €174.00 substitute first at the default clock; the unconfirmed original first and Valio's listed substitute second at the demo clock). Both are defensible; a presenter must know which clock is on. | 30% demo | `E1` fixes the clock per scenario. |
| 7 | **Stock-out (item 9) is reactive.** Nothing checks an open or waiting order; a stock-out during approval ends in a refusal with no fresh offer. | 15% exceptions | Reuse `_fresh_offer` on the approval path. Not started. |
| 8 | **Recipes (items 7, 8) are a fixed table of ours;** no seasonal ingredient; the recording holds few of the ingredients; the role alternatives are hand-written. | 15% exceptions | Say so on the page (it does); recipe data from the buyer is a next step. |
| 9 | **The signature is ours, with a demo key.** It proves what this gateway offered during one run. It does not prove Valio said it. | 15% openness | A fixed key as a deployment secret (`TTA_SIGNING_KEY`); Valio signing its own statements is the real next step. |
| 10 | **PostgreSQL and the award services are code that has not run tonight:** the new supplier view, the Aiven proof script, the Modal fan-out of the evidence batch, the scheduled witness. | 15% openness | Each is one command for a person with the keys; listed below. |
| 11 | **The formula tolerances and the list of manufacturer hosts are ours and unsigned** by anyone with the domain knowledge. | 15% openness | A biomedical team member reads `src/tta/offers/formula.py`; the host list is on the assumptions page. |
| 12 | **"Nutrition rules" (item 11) compare a substitute with the original, not with a diet standard.** | 15% exceptions | Stated here and on the assumptions page. |
| 13 | **`CLAUDE.md` still names Gemini as the agent's model and says Aiven was dropped.** It is the team's file to change. | 15% openness | One edit by its owner. |

### What was not run

- The shop page in a real browser.
- The new supplier view against PostgreSQL (`tests/store_pg/`), and any test that needs a live service.
- A redeploy; `deploy/check.py` against the public link.
- The evidence batch as a Modal fan-out (`deploy/evidence_batch.py`) and the hourly witness of the log's head (`deploy/witness.py`).
- The Aiven proof script against a database (`scripts/aiven_proof.py`; only its dry run).
- Any call to Valio's live mock, and any model.
- The whole test suite at this commit. Its last full run was on commit `db4c035`, earlier in the evening: 4,049 passed, 6 failed (pins since fixed by their lanes), 68 skipped (`AIMO/build/replan/STATUS.md`).

---

## How each step is checked

**How the build was checked** (from `AIMO/build/replan/RUNBOOK.md` and the log in `STATUS.md`). One orchestrating session coordinates; agents build.

1. **Lanes.** Each task owns its files. Two agents never own the same file at the same time. Shared models (`src/tta/contracts/`) may only gain fields with a default, and each addition is reported.
2. **Tests first.** Each defect in the proposals comes with a reproduction; the agent turns it into a test that fails before the change. An agent runs only the test folders it owns.
3. **Offline.** Build agents run in replay from the recording: no call to Valio's mock, a model, Modal, Aiven or Context.dev; `.env` is never read. The orchestrator alone made the outside calls of the evening: one `git fetch` and 8 Context.dev requests, each counted in the log.
4. **The orchestrator does not take an agent's word.** On every hand-back it runs the agent's tests itself and checks that only owned paths changed.
5. **The whole suite once per wave**, not per lane, because lanes change the same tree at once. A pinned figure that moves is re-measured offline and replaced by the lane that owns the test.
6. **Hashes of the stored log are pinned** (`tests/audit/test_pinned_hashes.py`), so a change that would invalidate the log already stored fails a test.
7. **Still to come when this was written:** the demo set re-measured at both clocks (`E1`), the review of the whole diff (`E3`), the whole suite and the linter once more.

**How this document was checked.** On a clean copy of commit `c2106fe`, offline, replay, no key of any kind:

- *Run:* the gateway built in the `demo` environment and asked through its own routes at the default clock and at the demo clock: the brief's request, the ward's, the oat drink, a preference, an order, a person's decision, an agent's attempt to decide, both views of the log, the reader with and without a readable sentence, `/healthz`, the discovery documents, the key set, the customers route, MCP with a foreign `Origin` (403).
- *Test:* 36 test files, named in the items above, run together on the same copy. Result: see the line below.
- *Counted from the files:* 13 MCP tool names in `src/tta/api/mcp_surface.py`; 32 product types in `product_types.yaml`; the rules and their words from `rules.yaml` and `human_approval.py`; the four profiles' values from `src/tta/policy/profiles/`.
- Tests named "not re-run" exist at this commit and were not executed for this refresh.

Result of the 36 files, with the copy's own code on the path: `388 passed in 154.74s`.

One later commit, `da6a96b` (fixes to the order book's lock, to who completes an approval that only F-10 holds, and to which renewals count as history), landed after these checks and is not covered by them. The wiring of suggestions (item 10) was still not committed at that point.
