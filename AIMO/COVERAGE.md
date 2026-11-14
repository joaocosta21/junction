# Coverage — how the build answers Valio Aimo's brief

Written Saturday 14 Nov 2026, about 18:00, while tonight's build runs (task D1 of the board, `AIMO/build/replan/STATUS.md`). It describes the code on branch `replan-build` and says, item by item, what is in the last commit and what is still being built.

**How to read the states.**
- **Works in the committed base** — in commit `51e9b03`, with tests. The suite on the merged base: 3,281 passed, 67 skipped (they need live services), 1 timing test left out (`STATUS.md`, log of 16:50).
- **Being built tonight (task)** — a task of the board. The task's state at the time of writing is given once, here: `B0` baseline: handed back (`AIMO/build/handback/B0.md`), not yet re-run and committed by the orchestrator · `L5` customers and suggestions: committed · `U1` shop page: running · `L1`, `L2a`, `L2b`, `L3`, `L4`, and the second-wave tasks `L1-2`, `L2a-2`, `L3-2`, `L4-2`, then `E1`, `E2`, `E3`, `X`: not started. Where this document relies on a plan and not on code, it says "planned".
- **Not built** — no code and no task.

**Where figures come from.** "Whole catalog" = Valio's product file, 17,546 products. "Recording" = the recorded answers of Valio's mock API used in replay, `fixtures/valio/2026-11-14-demo`: 769 products (milk, cream, plant drinks, yoghurt, quark, fresh beef), recorded Saturday 14 Nov 02:52 Helsinki time. "Sample" = a named smaller set. Every limit value, recipe and customer history is ours and illustrative; the mock has no customer model.

---

## Summary

### The pipeline

One Python process (FastAPI), the "gateway", between a buyer's agent and Valio's mock API. REST (`/v1/*`) and MCP (`/mcp/`) call the same service object (`src/tta/api/service.py`); the pages are a front end to the same routes.

1. **Request.** A typed request (`POST /v1/offers`, MCP `get_offer`): lines with product type or product ids, quantity, unit, needed-by date, required claims and labels, allergen exclusions, a preference. Or a sentence (`POST /v1/requests/parse`, `POST /v1/agent/run`, the shop page).
2. **Reading.** A sentence is read by fixed rules (`src/tta/agent/rules_reader.py`), never guessed: no model is called in tonight's build (the Gemini key has no credits; João dropped the model work at 17:33). A recorded model answer is served only for the exact sentence and customer it was recorded for. The result is the same typed request as in step 1.
3. **Candidates.** Product types, name terms, claims, pack size and lot step from the product file (`src/tta/catalog/`). No call to Valio yet.
4. **Lookup.** One price call and one availability call for the narrowed set (`src/tta/valio/`), from the mock or from the recording, never one of each.
5. **Offer.** Each product gets one of six availability states and a status per statement (price, quantity, delivery date, allergens, origin); the buyer's allergen exclusions are applied; at most three options are built, four under a preference (`src/tta/availability/`, `src/tta/allergens/`, `src/tta/offers/`). Everything left out is listed with a reason.
6. **Rules.** Each option is judged by rules kept as data (`src/tta/policy/rules.yaml`) with the buyer's own limits (`src/tta/policy/profiles/*.yaml`). The outcome is: the agent may order (`AUTO`), a named role must sign (`APPROVAL`), or it cannot be ordered (`BLOCK`). No model takes part.
7. **Order prepared.** `POST /v1/orders` with an `Idempotency-Key`. Price and availability are asked again; the rules run again. The order waits (`PENDING_APPROVAL`).
8. **A person confirms** (`POST /v1/approvals/{id}/decision`, page `/approvals`, the shop page). The check runs once more, then the order is `ORDERED`. An agent's token on this route is refused. **Or the agent orders alone**, only when the buyer switched that setting on, no rule fired and every statement of every line is confirmed (being built tonight, `B0`; off in every shipped profile).
9. **Log.** Every step writes one event with one sentence built from a template, chained by SHA-256 hashes (`src/tta/audit/`). The buyer and Valio Aimo each read their own view (`GET /v1/audit?reader=buyer|supplier`).

"Ordered" means recorded in our order book. The mock has no order endpoint; the order step, its approval and its record are ours to define.

### The 16 items

| # | Item of the brief | Our answer in one line | Committed base | Tonight | Not built |
|---|---|---|---|---|---|
| 1 | Core: lookup | Search, product and offer over REST and MCP, typed, with a status per statement | Works | Reader repaired (`L1`); discovery document (`L4`) | — |
| 2 | Core: inquiry → order | Offer at Valio's fixed price → order with a re-check and an idempotency key | Works | Agent-orders-alone path (`B0`); signed offers (`L4-2`) | An order message to Valio's systems |
| 3 | Core: permission and approval | Rules as data, a buyer profile, named roles, an agent can never approve | Works: a person on every order | The buyer's "agent may order alone" setting, off by default (`B0`) | — |
| 4 | Optional: delivery and sustainability | Reliability, carbon and labels per line; a preference; required labels | Works | A preference's price gap stated (`L2b`) | Carbon as a category range |
| 5 | Optional: substitution, exceptions | Ranked substitutes, partial fill, unconfirmed alternative, reasons for every exclusion | Works | Four gates incl. formula (`L2a`, `L2b`, `L3-2`) | — |
| 6 | Optional: traceability | One sentence per step, rule ids with their facts, two views | Works | Valio's view in full (`L3`) | — |
| 7 | Scenario: need → recipe → order | Dishes × servings − kitchen stock → one offer → order | Works in part | Two-dish menus accepted (`L4`) | Seasonal ingredient; recipe suggestion |
| 8 | Scenario: last-minute event | What cannot arrive in time is named; a stand-in by its role in the dish goes to a person | Works in part | Stand-in's added allergens named (`L4`) | A date of "tomorrow" that can be met in the recording |
| 9 | Scenario: supplier stock-out | Out-of-stock product → ranked substitute with what is given up; stale offer → fresh offer | Works in part | Substitute keeps the formula (`L2a`) | Anything that runs before the kitchen asks |
| 10 | Scenario: proactive selling agent | Suggestions from the buyer's own history only | — | Buyer-side suggestions wired (`L4-2`) | A Valio-side agent that proposes a product |
| 11 | Scenario: allergen-safe substitution | A substitute never adds an allergen; strict exclusion rule; dietitian for doubt | Works for allergens | Nutrition and formula (`L2a`, `L3-2`); school profile (`L3`) | — |
| 12 | Scenario: standing-order drift | A renewal is compared with the median of its history before it is ordered | Works | History counts ordered renewals only (`B0`); limits (`L4`) | — |
| 13 | Problem: trust protocol | A status per statement; a re-check before commitment; a hash-chained log | Works | Signed offers and audit head (`L4-2`, `X`) | Statements signed by Valio |
| 14 | Problem: guardrails model | Nine fixed rules no buyer can switch off, eight buyer limits, one "person on every order" setting | Works | The setting (`B0`); formula rule and preference premium (`L3-2`) | — |
| 15 | Problem: response logic | Confirmed first, unconfirmed as a named alternative, substitutes ranked, partial fill stated | Works | Safe product first, claim-keepers first, no category tiers (`L2a`, `L2b`) | — |
| 16 | Problem: audit trail | CloudEvents, append-only, hash chain, buyer view and supplier view | Works | Valio sees every rule that fired and the products considered (`L3`) | — |

---

## Core — the solution must enable

### 1. Product, price & availability lookup

> "Product, price & availability lookup: a structured way for an external agent to search for and retrieve what's available and at what price."

| | |
|---|---|
| **What we do** | Three typed calls. Search the catalog by product type, name terms (English or Finnish), claims, category, ids; read one product with its allergen statements (GS1 codes) and claims; ask for an offer, which adds Valio's price and availability. Each offer line carries one of six availability states (blocked · not deliverable · out of stock · order cut-off passed · quantity not confirmed · confirmed) and a status per statement. Valio is asked only for the candidates of one request, in two calls, as Valio's slide asks ("Query the APIs only when needed, never for all product"). |
| **Where** | `POST /v1/products/search`, `GET /v1/products/{id}`, `POST /v1/offers`, `GET /v1/offers/{id}`; MCP `search_products`, `get_product`, `get_offer`. Schemas: `GET /openapi.json` (OpenAPI 3.1, generated from the models), `GET /v1/schemas` (JSON Schema). Code: `src/tta/catalog/search.py`, `src/tta/catalog/product_types.yaml`, `src/tta/valio/client.py`, `src/tta/valio/replay.py`, `src/tta/availability/states.py`, `src/tta/availability/claims.py`. |
| **How we know it is right** | `tests/catalog/`, `tests/availability/test_states.py`, `tests/availability/test_claims.py`, `tests/valio/` (client, replay, call budget, no secret in a log), `tests/api/test_openapi_and_schemas.py`, `tests/mcp/test_tools.py`. Invariants: a stock figure of 999,999 or more is "quantity not confirmed" and is never used in arithmetic (Valio confirmed on 14 Nov that a very large value means the stock is not known); an absent field is unknown, never 0; a product the recording does not hold is `NOT_IN_RECORDING`, never presented as Valio's statement. |
| **State** | **Works in the committed base.** Being built tonight: coffee milk as its own product type, so "milk" holds 74 products instead of 78 (whole catalog; `B0`); the sentence reader's repair (`L1`); a discovery document at `/.well-known/api-catalog` and `/llms.txt` (`L4`, planned). |

### 2. Requesting price & availability, then placing an order

> "Requesting price & availability, then placing an order: a defined interaction for moving from inquiry to commitment, based on fixed prices rather than a negotiated quote."

| | |
|---|---|
| **What we do** | Inquiry: `POST /v1/offers` returns options at the net price Valio's price call returned, each with `valid_until` (the earliest price validity and order cut-off of its lines). No field lets either side propose another price. Commitment: `POST /v1/orders` names one offer and one option. Before anything is recorded, price and availability are asked again and the rules run again. If something changed or expired, the answer is `409` with a new offer id and nothing is ordered (rule F-04, "the option expired or changed before the order"). The same `Idempotency-Key` returns the first result, so a retry never places a second order. The order record keeps each price with its validity, each stock and delivery statement, and the time of the check. |
| **Where** | `POST /v1/offers` → `POST /v1/orders` → `GET /v1/orders/{id}`; MCP `get_offer`, `place_order`, `get_order`. Code: `src/tta/offers/revalidation.py`, `src/tta/orders/checking.py`, `src/tta/orders/service.py`, `src/tta/orders/records.py`. |
| **How we know it is right** | `tests/orders/test_place_order.py`, `test_idempotency_key.py`, `test_one_order_per_offer.py`, `test_expiry.py`, `test_concurrency.py`, `test_atomic_outcomes.py`, `tests/offers/test_revalidate.py`, `tests/e2e/test_guards.py` (the same key twice places one order), `tests/api/test_flow.py`, `tests/mcp/test_flow.py`. |
| **State** | **Works in the committed base**, with a person confirming every order. Being built tonight: the path on which the agent's own call ends in `ORDERED` (`B0`); offers and orders signed with a published key (`L4-2`, planned). **Not built:** a message Valio's systems take. The mock has no order endpoint, by design; "ordered" is a record in our book. Mapping that record to Peppol BIS Ordering is a written next step (`docs/STANDARDS.md`), not code. |

### 3. Permission & human-approval management

> "Permission & human-approval management: what the agent may decide on its own, and what must go to a human for sign-off."

| | |
|---|---|
| **What we do** | The agent's authority comes from its bearer token, which is bound to one buyer profile; it is never a field of the request, so an agent cannot choose its own limits. `GET /v1/authority` returns the profile and every rule as a sentence with that profile's values. **The agent decides alone:** reading the request, leaving products out, combining products, choosing a substitute inside the buyer's allowed scope, the re-check, preparing the order, naming who must sign. **A person decides:** placing the order. Valio's answer on 14 Nov: "the final submition should always have the input from the user". An approval names the roles it needs (purchasing manager, finance, dietitian) and is complete when people holding all of them have signed; the approver may pick another option of the same offer, and the rules run again on it. |
| **Where** | `GET /v1/authority`, `GET /v1/approvals`, `POST /v1/approvals/{id}/decision`; page `/approvals`; shop page `/shop`; MCP `get_authority` (no MCP tool approves). Code: `src/tta/policy/rules.yaml`, `src/tta/policy/engine.py`, `src/tta/policy/human_approval.py`, `src/tta/policy/profiles/`, `src/tta/orders/access.py`, `src/tta/api/identity.py`. |
| **How we know it is right** | `tests/policy/` (19 files; `test_rulebook.py`: the shipped rules are exactly the specified ones, no fixed rule reads a buyer setting, a broken rules file does not load; `test_profiles.py`: a profile that touches a fixed rule is rejected at load), `tests/orders/test_decide.py`, `test_access.py`, `test_decide_other_buyer.py`, `tests/mcp/test_approval.py`, `tests/e2e/test_guards.py` (an agent's token on the decision route is refused and the attempt is logged). The security review of the earlier build found: no buyer reads another's data, an agent cannot approve its own order by any route (`AIMO/PLAN.md` section 3). |
| **State** | **Works in the committed base** in its strict form: rule F-10 ("every order needs human approval") is applied in code on every path, whatever the profile says. **Being built tonight (`B0`):** F-10 becomes the rule a buyer setting drives. `auto_order_enabled` is off in every shipped profile; switched on, the agent orders alone only when no rule fires and all five statements of every line are confirmed (Valio, second visit: "after and if you are 100% sure yes"). Proof written by `B0`: `tests/e2e/test_no_order_without_a_person.py` (REST, agent run, standing-order renewal, menu plan: each waits for a person), `tests/api/test_ordering_alone.py` (setting on: the ward's 200 L, €402.00, ordered alone; an unconfirmed quantity still goes to a person). Figures from the recording. |

---

## Optional – open directions

### 4. Delivery time & sustainability comparison

> "Delivery time & sustainability comparison: not just price, but delivery reliability and the certificates/sustainability labels already shown in the webshop. (Category-level carbon-footprint ranges are a stretch goal.)"

| | |
|---|---|
| **What we do** | Each offer line shows its delivery reliability, carbon figure (kg CO2e per kg) and certificate labels from Valio's files. Each option states its earliest and latest delivery, lowest reliability, an estimated carbon total and the labels every line carries, and how many lines have no value. A request may set `prefer` to `EARLIEST`, `RELIABILITY` or `LOWER_CARBON`, and may require labels (for example `EU_ORGANIC_FARMING`). Under a preference the offer adds the cheapest confirmed option and says the difference in euros and what it buys. A preference never outranks availability or the rules. A missing value is unknown, never 0 and never imputed. |
| **Where** | Fields `prefer`, `lines[].required_labels` on `POST /v1/offers`; option kind `CHEAPEST_CONFIRMED`. Code: `src/tta/offers/preference.py`, `src/tta/offers/comparison.py`, `src/tta/catalog/loader.py`. |
| **How we know it is right** | `tests/offers/test_preference_offer.py`, `test_preference_fill.py`, `test_required_labels.py`, `tests/catalog/test_labels.py`, `tests/ui/test_sustainability_page.py`. |
| **State** | **Works in the committed base.** Coverage of Valio's data, whole catalog: reliability on 4,425 products (25.2%), carbon on 11,033 (62.9%). In the recording, across 18 offers (9 product types × 2 preferences) "earliest" and "lower carbon" changed no first option (`P2-scenarios.md`); "most reliable" changes one, oat drink, at €7.00 more. Being built tonight (`L2b`): the gap is stated and a known low reliability no longer beats an unknown one at any price (found: €73.70 of cream chosen over €33.10). **Not built:** carbon as a category range; we show Valio's figure per product. |

### 5. Substitution and other exception handling

> "Substitution and other exception handling: what happens when the exact request can't be met. (Last year's Zero-Fail Logistics challenge covered failed deliveries in depth, so this isn't scored as core.)"

| | |
|---|---|
| **What we do** | Each condition of the mock has one defined answer, and the offer says which applied. |
| **Where** | `POST /v1/products/{id}/substitutes`, MCP `find_substitutes`; options of `POST /v1/offers`. Code: `src/tta/offers/combining.py`, `options.py`, `planning.py`, `substitutes.py`, `substitute_wording.py`, `src/tta/allergens/substitution.py`. |

| Condition | What the agent does | Rule that sends it to a person |
|---|---|---|
| Confirmed stock covers part of the quantity | Combines confirmed products cheapest first; says how much is missing | P-03, "the option covers too little of the requested quantity" (below the buyer's minimum fill) |
| Quantity not confirmed | Never the suggestion; offered as a separate, complete option | F-01, "a line's quantity is not confirmed": always a person |
| Order cut-off passed | Left out, with the reason; `closingTime` is read literally | — |
| Delivery later than needed | Left out; the note names the earliest date Valio states and the products that make it | F-07, "a needed-by date is not verifiably met", when such a line is ordered |
| A named product cannot be supplied | Ranked substitutes; each says whether it passes the allergen rule, whether it can be ordered now and what the buyer gives up | F-05 blocks one that adds an allergen · F-08, "a substitute lacks a dietary claim the original carries" · P-05, "a substitute is outside what the profile accepts" |
| Price or stock changed between offer and order | Nothing ordered; a fresh offer id is returned | F-04 |
| Sold by variable weight | Total marked as an estimate | P-06, "a line is sold by variable weight" |
| No allergen data | Unknown, not safe (item 11) | P-04, "a line does not rule out an excluded allergen": the dietitian |

| | |
|---|---|
| **How we know it is right** | `tests/offers/test_combining.py`, `test_offer_substitute.py`, `test_substitutes_buyer_rule.py`, `test_dietary_claims.py`, `test_exclusions_and_requests.py`, `test_checks_and_edges.py`, `tests/allergens/test_substitution.py`, `tests/e2e/test_scenario_1_milk.py`, `test_scenario_3_substitutes.py`, `test_backup_beef.py`. |
| **State** | **Works in the committed base.** Being built tonight: substitutes pass four gates in order — adds no allergen; keeps the dietary claims, or is a last resort; keeps the formula where the formula matters; then Valio's listing, pack and price (`L2a`, `L2a-2`, `L3-2`); candidates only from Valio's listed pairs and the same 5-digit category, because Valio could not confirm that the digits are levels (`L2a`). Today the code still widens to the first 4 and 3 digits and does not read nutrition. |

### 6. Traceability and explainability

> "Traceability and explainability: a human-readable record of what the agent did and why."

| | |
|---|---|
| **What we do** | One event per step: request received, request read, lookup performed, offer created, rules evaluated, approval requested, approval decided, order confirmed, rejected, expired or blocked, standing order created or renewed. Each event has who acted, the rule ids with the facts they read, the hash of the rules and profile in force, and one sentence written from a template, never by a model. Example (from `AIMO/SPEC.md`): "The agent could not place this order alone: the total of €1,980.77 is above the €750 limit of profile hotel-kitchen (P-01) and only 74.9% of the 1,000 litres is covered (P-03). Sent to the purchasing manager." Every excluded product keeps its reason code and sentence on the offer. |
| **Where** | `GET /v1/audit?order_id=&offer_id=&reader=`, MCP `get_audit`, page `/orders/{id}`. Code: `src/tta/audit/trail.py`, `sentences.py`, `supplier_sentences.py`, `chain.py`. |
| **How we know it is right** | `tests/audit/test_sentences.py`, `test_sentence_guards.py`, `test_envelope.py`, `test_chain.py`, `tests/orders/test_audit_trail.py`, `tests/api/test_audit.py`. |
| **State** | **Works in the committed base.** Being built tonight (`L3`): sentences say who confirmed; Valio's view shows every rule that fired and the products considered (item 16). |

---

## Example scenarios

The brief calls these "example scenarios to spark ideas". Four are covered in part, one in full, one not at all.

### 7. Need → recipe → order

> "Need → recipe → order: a chef plans next week's menu around a seasonal ingredient. The agent suggests recipes, works out what's missing from stock, and places the order."

| | |
|---|---|
| **What we do** | The buyer picks dishes and servings and states what the kitchen holds. The planner expands the recipes, takes the stock off dish by dish, adds up per product type, and asks for one offer; the order goes through the normal flow. It asks at most three offers per plan. |
| **Where** | `GET /v1/menus/recipes`, `POST /v1/menus/plan`, page `/menu`. Not on MCP. Code: `src/tta/menus/needs.py`, `planner.py`, `recipes.yaml` (9 dishes, ours and illustrative: Valio publishes no recipes). |
| **How we know it is right** | `tests/menus/test_needs.py`, `test_planner.py`, `test_recipes.py`, `test_routes.py`, `test_menu_page.py`. Measured in the recording (`docs/DEMO.md`): beef stew and berry quark dessert for 120 servings → 4 lines, €476.48, to the purchasing manager. |
| **State** | **Works in the committed base, in part.** Being built tonight (`L4`): two-dish menus accepted (30 of 36 two-dish menus were refused with "at most 5 lines", `AIMO/PLAN.md` section 3). **Not built:** the seasonal ingredient and the suggestion of recipes around it. The product file has no season or "new" field; 13 product names say "seasonal" (whole catalog, `AIMO/USE-CASES.md`). The buyer chooses the dishes. In replay 7 of the 9 dishes cannot be ordered in full: the recording holds dairy and fresh beef only. |

### 8. Last-minute event

> "Last-minute event: an unexpected booking for tomorrow. The agent identifies what the recipes require, flags what can't be sourced in time, and proposes substitutions through recipe logic rather than a simple SKU swap."

| | |
|---|---|
| **What we do** | Same planner. For each ingredient that cannot arrive by the date, the plan says why (cut-off passed, quantity not confirmed, late) and tries the alternatives the recipe lists for that ingredient's role in the dish, best first, each with one sentence on what changes ("A thick natural yoghurt gives the same tangy base; the dessert is runnier and has less protein."). A line that stands in for the recipe's own ingredient always goes to a person: rule F-09, "a line stands in for a recipe's own ingredient", which no buyer can switch off. An ingredient with no working alternative is listed as not sourced. |
| **Where** | `POST /v1/menus/plan`; `/menu?example=event`. Code: `src/tta/menus/planner.py`, `plan.py`, `wording.py`; fields `stands_in_for`, `stands_in_role` on the request line. |
| **How we know it is right** | `tests/menus/test_planner.py` (the event replaces quark by its role and keeps the rest; an ingredient without an alternative says why), `tests/policy/test_stands_in_for.py`. |
| **State** | **Works in the committed base, in part.** Being built tonight (`L4`): the allergens a stand-in adds are named; a false "none can be offered" sentence is fixed. **Limits, stated plainly:** the role alternatives are written by us in the recipe file, not derived from product data. Every delivery date in the recording is Monday 16 Nov (603 dated lines, `AIMO/USE-CASES.md`), so a request for "tomorrow" gets no option and the earliest date; the example therefore uses Monday. |

### 9. Supplier stock-out

> "Supplier stock-out: a key product runs out mid-week. The agent proposes a recipe-compatible substitute before the kitchen notices the gap, and explains the trade-off."

| | |
|---|---|
| **What we do** | A product asked for by id that is out of stock is left out with "Out of stock" and the offer's substitute option names the best replacement and what is given up (another brand, not listed by Valio, another pack size, a lost claim, a higher price, stock not confirmed). A product that runs out between offer and order gives `409` and a fresh offer. |
| **Where** | `POST /v1/offers` with `product_ids`; `POST /v1/products/{id}/substitutes`. Code: `src/tta/offers/substitutes.py`, `substitute_wording.py`, `src/tta/api/service.py` (`_fresh_offer`). |
| **How we know it is right** | `tests/offers/test_offer_substitute.py`, `tests/e2e/test_scenario_3_substitutes.py` (two substitutes Valio itself lists are refused because they add gluten). |
| **State** | **Works in the committed base, in part.** Being built tonight (`L2a`): "recipe-compatible" as a measure — the six nutrients per 100 g within 15% or 1 g, salt within 0.25 g, the same fat source (tolerances are ours, `P10-formula.md`). **Not built:** "before the kitchen notices". Nothing runs without a request: no scheduler, no subscription. A stock-out while an order waits for approval refuses the approval and builds no fresh offer. |

### 10. Proactive selling agent

> "Proactive selling agent: Valio Aimo's own agent spots a new or seasonal product and proactively suggests it to the buyer's agent."

| | |
|---|---|
| **What we do** | Nothing on Valio's side. Valio's token reads its view of the log and nothing else. What exists is the buyer's side of suggesting: from a customer's past orders, the forgotten item ("you usually order 10 L of cooking cream with this"), the usual product and quantity, a larger pack of the same product, a quantity trend. A suggestion never adds itself to an order; accepting it builds a new offer under every rule. |
| **Where** | `src/tta/suggestions/` (pure functions), `src/tta/customers/data/*.yaml` (four customers with synthetic histories, labelled), `src/tta/contracts/suggestion.py`. No route yet. |
| **How we know it is right** | `tests/suggestions/` (7 files), `tests/customers/test_against_catalog.py` (every product of a customer file exists and has confirmed stock in the recording). `L5`'s own run: 137 passed, 2 skipped. |
| **State** | **Not built** as the brief describes it. The buyer-side functions are **in the committed base** but reach no offer or page; wiring them is **being built tonight** (`L4-2`: the list on an offer, the guard against the buyer's exclusions, `GET /shop/api/suggestions`; planned). A supplier-originated suggestion (proposal `P15-recommendations.md`, item R11: a profile setting, off by default) is in no task. Reason: the product file marks nothing as new or seasonal, and a seller's push into a buyer's order needs the buyer's consent model first. |

### 11. Allergen-safe substitution under pressure

> "Allergen-safe substitution under pressure: in a school or hospital kitchen, a substitution must still satisfy strict allergen and nutrition rules."

| | |
|---|---|
| **What we do** | **Allergens.** Exclusions are GS1 allergen codes on the profile or the request; a request can add one and never remove one. Under the strict rule: "free from" passes; "contains" is rejected and can never be ordered (rule F-02, "a line declares an excluded allergen"); "may contain", "undeclared" or no statement goes to the dietitian (rule P-04). A nutritional claim is never an allergen statement: all 35 lactose-free milks of category 10400 declare milk (whole catalog). The ingredient list counts as a statement when it contradicts a "free from". Each allergen can carry its own rule. A substitute may never declare an allergen the original does not, for any buyer (rule F-05, a block). For the hospital ward every substitute goes to a person. When the dietitian is asked about a missing statement, what the manufacturer's page says is shown beside it (from stored or recorded lookups; no lookup is made tonight), labelled as not Valio data; it changes no outcome. **Nutrition.** Nothing today: the build does not load nutrient values. |
| **Where** | `src/tta/allergens/codes.py`, `exclusion.py`, `ingredients.py`, `substitution.py`; `src/tta/policy/profiles/allergy-ward.yaml`; `src/tta/evidence/`. |
| **How we know it is right** | `tests/allergens/` (8 files, among them `test_rule_per_allergen.py`, `test_ingredient_rule.py`, `test_integration_catalog.py` over the whole catalog), `tests/offers/test_scenario_2_ward.py`, `tests/e2e/test_scenario_2_allergy_ward.py` (every product declaring milk or gluten is left out; the chosen product states free from both), `tests/evidence/`. |
| **State** | **Allergen half works in the committed base.** Being built tonight: nutrition loaded and the "same formula" measure (`L2a`; six nutrients are present on 11,538 of 17,546 products, whole catalog, `P10-formula.md`), a formula rule with id F-11 (`L3-2`, planned), a school-kitchen profile that keeps tree nuts, peanuts and sesame out under the strict rule (`L3`), the safe product always first and a doubtful one only as a labelled alternative (`L2b`). No nutrition standard for schools or hospitals is encoded or planned; the formula measure compares a substitute with the original, not with a diet. |

### 12. Standing order drift detection

> "Standing order drift detection: the agent learns a kitchen's recurring weekly order and flags anomalies (portion counts creeping up, cost drifting) before auto-renewing it."

| | |
|---|---|
| **What we do** | A standing order is renewed through the normal offer and order. Before the order, each line's quantity and each product's unit price are compared with the median of its last 6 renewals (at least 3 are needed to judge). Beyond the buyer's tolerance (hotel 25%, ward 10%; ours) the renewal goes to the purchasing manager: rule P-08, "a standing order's renewal drifts from its history". The sentence gives the numbers: "290 L this week against a median of 100 L over the last 6 renewals, more than the 25% tolerance". The demo history is six synthetic weeks, each marked as such. |
| **Where** | `POST /v1/standing-orders`, `GET /v1/standing-orders`, `GET /v1/standing-orders/{id}`, `POST /v1/standing-orders/{id}/renew`; page `/standing-orders`. Not on MCP. Code: `src/tta/standing/service.py`, `history.py`, `src/tta/policy/drift.py`, `standing_facts.py`. |
| **How we know it is right** | `tests/standing/test_renewal_flow.py`, `tests/policy/test_standing_drift.py`, `tests/orders/test_standing_history_at_order_time.py`, `tests/audit/test_standing_events.py`. |
| **State** | **Works in the committed base**, with one known defect: renewals still waiting for approval count as history, so three unapproved renewals move the baseline. **Being built tonight:** only ordered renewals count (`B0`, `tests/standing/test_history_counts_ordered.py`); at most 20 standing orders per buyer and a rate limit (`L4`). The trend function ("your order has grown") is committed (`src/tta/suggestions/trend.py`) but shown nowhere yet. "Learns" is a median over a window, by choice: the buyer can recompute it. |

---

## Problems they would love tackled

### 13. Trust protocol

> "Trust protocol: the minimum data/verification standard for an external agent to trust Valio Aimo's claims on stock, price and origin without a manual check."

| | |
|---|---|
| **What we do** | Our proposal for the minimum standard has four parts. (1) **A status per statement, per line**: `CONFIRMED`, `UNKNOWN` or `RULED_OUT`, with one sentence. (2) **A re-check before commitment**: the supplier is asked again at order time and at approval time. (3) **A record of what was relied on**: the order keeps each statement with its validity. (4) **A log neither side can change unseen**: a SHA-256 hash chain whose head `/healthz` publishes. |
| **Where** | `claims[]` on every offer line; `src/tta/availability/claims.py`; `src/tta/offers/revalidation.py`; `src/tta/audit/chain.py`. |

| Statement | Confirmed when | Unknown when | Ruled out when |
|---|---|---|---|
| Price | a net price was returned and its validity is in the future | no net price | — |
| Quantity (stock) | the stock figure is a real number and covers the line | the figure is a placeholder (999,999 or more) | out of stock, not deliverable, blocked |
| Delivery date | the cut-off is open and the delivery date is on or before the needed-by date | the request gives no date | cut-off passed, or later than needed |
| Allergens | every excluded allergen has an explicit statement | "may contain", "undeclared" or no statement | an excluded allergen is declared |
| Origin | the product file states it | absent | — |

| | |
|---|---|
| **How we know it is right** | `tests/availability/test_claims.py`, `test_claims_allergens_origin.py`, `tests/offers/test_revalidate.py`, `tests/audit/test_chain.py`, `test_head.py`. |
| **State** | **Works in the committed base.** Being built tonight: offers and orders signed with Ed25519 and a published key, with a check script (`L4-2`, planned); a scheduled witness of the log's head on Modal (`X`, planned, live only after a redeploy). **Not built, and outside our reach:** Valio signing its own statements. Today "confirmed" means "Valio's API said so at this time", not "Valio signed it". The chain shows a changed, removed or inserted event; it does not show the newest events cut off, or a rewrite by whoever owns the database, unless another party holds the head (`src/tta/audit/chain.py` says so). Origin is shown and, in the committed base, gates nothing. |

### 14. Guardrails model

> "Guardrails model: which decisions require human sign-off (spend threshold, substitutions outside stated preferences) vs. fully autonomous."

Rules are data (`src/tta/policy/rules.yaml`), evaluated by one deterministic engine; the most severe outcome of the rules that fire wins. A profile file that names a fixed rule, or carries a setting not listed, is rejected when it loads (stated in the profile files and tested for fixed rules).

| Rule | In words | Outcome | Who signs |
|---|---|---|---|
| **Fixed: no buyer can switch these off** | | | |
| F-01 | A line's quantity is not confirmed | Person | Purchasing manager |
| F-02 | A line declares an excluded allergen | Blocked | — |
| F-03 | A fact a rule needs is missing | Person | The role the fact names |
| F-04 | The option expired or changed before the order | Blocked; fresh offer | — |
| F-05 | A substitute adds an allergen the original does not declare, or raises "may contain" to "contains" | Blocked | — |
| F-06 | An agent cannot approve an order | Refused | — |
| F-07 | A price is not confirmed, a delivery date is ruled out, or a needed-by date is not verifiably met | Person | Purchasing manager |
| F-08 | A substitute lacks a dietary claim the original carries | Person | Purchasing manager |
| F-09 | A line stands in for a recipe's own ingredient | Person | Purchasing manager |
| **Set by the buyer (values are ours, illustrative)** | | | |
| F-10 | Every order needs human approval (the setting "agent may order alone" is off) | Person | Purchasing manager |
| P-01 | The order is above the spend limit per order (hotel €750, ward €500) | Person | Purchasing manager |
| P-02 | The day's spend would pass the limit per day (hotel €3,000, ward €1,500) | Person | Finance |
| P-03 | The option covers too little of the quantity (hotel 90%, ward 100%) | Person | Purchasing manager |
| P-04 | A line does not rule out an excluded allergen | Person | Dietitian |
| P-05 | A substitute is outside what the profile accepts (hotel: same category; ward: none) | Person | Purchasing manager |
| P-06 | A line is sold by variable weight | Person | Purchasing manager |
| P-07 | A line carries a deposit the total leaves out | Person | Finance |
| P-08 | A standing order's renewal drifts from its history | Person | Purchasing manager |

| | |
|---|---|
| **Where** | `GET /v1/authority` (the rules in sentences with the caller's values and the hash of the rules in force); pages `/kitchen` and the shop's settings, where a visitor sets a profile of their own. |
| **How we know it is right** | `tests/policy/test_rules.py`, `test_rulebook.py`, `test_authority.py`, `test_missing_facts.py`, `test_custom_profile.py`, `test_hash.py`, `test_order_time.py`, `tests/orders/test_spend.py`, `test_decide_at_order_time.py`. Invariants: the rules run when the option is built, again when the order is placed, again when a person decides; a missing fact asks for a person, it never passes. |
| **State** | **Works in the committed base** with F-10 always on. **Being built tonight:** F-10 driven by the buyer's setting, and the "fully autonomous" side of the brief's sentence with it (`B0`; F-10 stays in code because it fires only when no other rule asks for a person, and `rules.yaml` says where it lives); a formula rule F-11 and a rule for how much more a preference may cost (`L3-2`, planned); two more profiles, school and bakery-café (`L3`). |

### 15. Response logic

> "Response logic: how an agent handles partial availability and substitution ranking ("good-better-best") within Valio Aimo's own assortment."

| | |
|---|---|
| **What we do** | **Options, in this order:** (1) confirmed stock only — the cheapest product that covers the quantity, else a combination cheapest first, else a partial fill that says how much is missing; (2) the cheapest product whose quantity is not confirmed, as a complete alternative a person can pick; (3) a substitute, when a named product cannot be supplied. Ranking is by fit to what was asked, then by what is confirmed, then by the buyer's preference, then by price. **Substitutes** come only from Valio's assortment: the pairs Valio lists first (249 pairs on 189 products, whole catalog), then the same category. They are ranked: passes the allergen rule → keeps every dietary claim → category distance → listed by Valio → closest pack → confirmed → price. One that fails is still shown, with its reason, and can never be ordered. |
| **Where** | `src/tta/offers/options.py`, `combining.py`, `planning.py`, `substitutes.py`; `POST /v1/products/{id}/substitutes`. |
| **How we know it is right** | `tests/offers/test_scenario_1_milk.py`, `test_combining.py`, `test_accounting.py`, `test_offer_wording.py`, `tests/catalog/test_substitutes.py`, `tests/e2e/test_scenario_1_milk.py`, `test_scenario_3_substitutes.py`. |
| **State** | **Works in the committed base.** The brief's own request, in the recording, hotel kitchen, as `B0` measured it at both clocks (being built tonight): confirmed stock covers 435 of 1,000 litres of lactose-free milk (384 × `469363` + 51 × `462775`) for €1,083.39; the alternative is 1,000 × `464306` for €1,010.00 with the quantity not confirmed; both go to a person; the offer says coffee milk was left out. In the committed base the same request is filled to 1,000 L for €2,580.64 with 565 L of coffee milk, which Valio told us a buyer asking for milk does not accept ("no be explicit"). Also being built tonight: no 4- or 3-digit category tiers, claim-keeping substitutes first, formula (`L2a`); the safe product first and no unconfirmed alternative dearer than the confirmed option (`L2b`). |

### 16. Audit trail

> "Audit trail: a usable, human-readable log of an agent's purchasing decisions, for both buyer and Valio Aimo."

| | |
|---|---|
| **What we do** | One log, two views. **The buyer** sees everything about its own requests: options, exclusions with reasons, rules fired, limits, approvers and their notes; never another buyer's events. **Valio Aimo** sees what was asked of its data, what was offered and ordered, the statements each order relied on, the agent's identity, and whether it acted alone or with human approval; not the buyer's limit values, allergen exclusions, approver names or notes. Events are CloudEvents 1.0, stored append-only; database triggers refuse an update or a delete (SQLite locally; PostgreSQL on Aiven when a database URL is set). Audit times are real UTC time even when the offers run on the recording's clock. |
| **Where** | `GET /v1/audit?reader=buyer|supplier`, MCP `get_audit`, page `/orders/{id}` (switch between the two views), `GET /shop/api/audit`. Code: `src/tta/audit/views.py`, `readers.py`, `trail.py`; `src/tta/store/schema.py`, `src/tta/store/sql/`. |
| **How we know it is right** | `tests/audit/test_views.py`, `test_phrases.py`, `tests/store/`, `tests/api/test_audit.py`; `tests/store_pg/test_reader_views.py` needs the live database and is among the 67 tests skipped offline. |
| **State** | **Works in the committed base**, thinner than Valio asked for: Valio's view lists only the fixed rules F-01 and F-03 to F-08 and hides every buyer rule that fired. Valio's answer on 14 Nov: "all the steps and decisions", and "the logic behind it and product considered". **Being built tonight (`L3`):** every rule that fired with its reason, and the products considered and left out; limit amounts and allergen codes masked; the role in place of the approver's name; notes left out; the SQL view changed to match, with a test that both list the same fields. |

---

## Does this make sense? Gaps and weak spots

Ranked by what each costs against the judging criteria. "Smallest change" is the least work that closes it.

| # | Gap | Costs on | Smallest change |
|---|---|---|---|
| 1 | **The end state exists only as uncommitted or unstarted work, and the public link runs an older build.** The committed base fills the brief's own request with 565 L of coffee milk; the corrected answer is `B0`'s, not yet verified. `docs/DEMO.md`, `docs/PITCH.md` and `README.md` still carry €2,580.64. A redeploy is a person's action; the run never deploys. | 30% demo | Verify and commit `B0`; run `E1` (figures at both clocks) before any other second-wave work; one redeploy in replay with the demo clock. |
| 2 | **The sentence reader can return a wrong request.** Reproduced before tonight (`A2b-review-preference-reader.md`): "must not contain gluten" dropped; "0.100 l" read as 100 L; "10 kg of milk chocolate" read as milk; 20 of 40 hard sentences wrong (a sample of 40). With a person on every order nothing is ordered unseen, but the offer shown is for the wrong thing. It is also the only reader a judge meets: no model is called. | 20% precision; safety | `L1` at its minimum: every exclusion in the text must be in the typed request, "0.100 l" is not 100 L, a number that belongs elsewhere is not the quantity, an unreadable text gets a question. |
| 3 | **Substitutes ignore how a product is used.** 100 L of 36% whipping cream is topped up with 52 L of a 15% vegetable-fat blend; a rice drink stands in for a barista oat drink. Valio called formula "a VERY IMPORTANT thing". Nutrition is not loaded. | 15% exceptions; 20% precision | `L2a`, first two steps only: drop the 4- and 3-digit category tiers; load the six nutrients and refuse a different fat source where formula matters. |
| 4 | **A doubtful product can rank above a safe one.** Hotel, plant drink, no gluten: €17.40 with the allergen not ruled out is option 1 over €20.10 that rules it out. Valio: when unsure, flag it; João: the safe product wins. | 20% controls | `L2b`, item P4 M1: option 1 holds only products whose data rules the allergen out. |
| 5 | **Valio's view of the log hides the buyer's rules**, against Valio's own answer. A judge from Valio opening the supplier view sees less than they asked for. | 20% controls | `L3`, item B13-1: list every fired rule with its title and outcome; mask values. |
| 6 | **Proactive selling (item 10) is not built and no task holds it.** Suggestions from history are functions with no route. | 20% precision; the brief's scenario | `L4-2` minimum: the forgotten item on the offer with "Add". For the scenario itself: one suggestion kind marked as serving the supplier, off by default (`P15` R11, estimated 0.75 h), or one line under next steps. |
| 7 | **Stock-out (item 9) is reactive.** Nothing checks an open or waiting order; a stock-out during approval ends in a refusal with no fresh offer. | 15% exceptions | Reuse `_fresh_offer` on the approval path (estimated 2–3 h in `AIMO/USE-CASES.md`); in no task tonight. |
| 8 | **The brief's own request ends in a partial fill** (435 of 1,000 L confirmed, recording). It is the mock's condition, not a fault, but a judge must read that in one line. | 30% demo | The headline of option 1 says both choices and that coffee milk was left out (`L2b`; the note exists, the headline does not mention it). |
| 9 | **Recipes (items 7, 8) are a fixed table of ours;** no seasonal ingredient; most dishes cannot be ordered in the recording; the role alternatives are hand-written. | 15% exceptions | `L4` S5; else take "Menu" out of the navigation, as the plan allows. |
| 10 | **Nothing is signed.** "Confirmed" is Valio's API answer at a time. The log's owner can rewrite it unless someone else holds the head. | 15% openness | `L4-2` signed offers; else one paragraph that says so (it is in `docs/STANDARDS.md`). |
| 11 | **Openness details.** `/mcp/` does not check the `Origin` header, which the MCP specification requires; no discovery document; 26 document lines out of date (`A1-docs-check.md`); `CLAUDE.md` still names Gemini as the agent's model and says Aiven was dropped. Menus and standing orders are not MCP tools. | 15% openness | `L4` (Origin, discovery), `E2` (documents). |
| 12 | **Autonomy is narrow once switched on.** `B0` reads "every statement confirmed" literally: origin and delivery date included, so an undated request never orders alone. Open question for the team (`B0.md`). | 20% controls | Decide; one line in `human_approval.py` either way. |
| 13 | **Four customers, two profiles.** School and bakery-café have customer files but no profile yet; the school's strict nut rule sends every confirmed bulk milk and yoghurt to the dietitian, because those products state nothing about nuts. | 30% demo | `L3` profiles; choose the school's demo product from those with a statement. |
| 14 | **Scenario 3 moves with the clock.** At the demo clock (Thursday 12 Nov 14:15) the substitute `475224` is no longer offered (`B0.md`). | 30% demo | `E1` picks the clock per scenario or another example. |
| 15 | **"Nutrition rules" (item 11)** will be a comparison with the original product, not a school or hospital standard. | 15% exceptions | Say so on the assumptions page. |
| 16 | **Delivery comparison rarely changes a choice in the recording** (0 of 18 offers for earliest and lower carbon). | optional direction | Show it on oat drink, the one case it does; claim no more. |

---

## How each step is checked

From `AIMO/build/replan/RUNBOOK.md`, part 2. One orchestrating session coordinates; agents build.

1. **Lanes.** Each task owns its folders (the reader · substitutes and formula · options and safety · rules and log · the gateway · customers and suggestions · the shop page). Two agents never own the same file at the same time. Shared models (`src/tta/contracts/`) may only gain fields with a default, and each addition is reported.
2. **Tests first.** Each defect in the proposals comes with a reproduction; the agent turns it into a test that fails before the change. An agent runs only the test folders it owns.
3. **No outside call.** Everything runs in replay from the recording: no call to Valio's mock, a model, Modal, Aiven or Context.dev; no push, fetch, merge or deployment; `.env` is never read.
4. **The orchestrator does not take an agent's word.** On every hand-back it runs the agent's tests itself, checks with `git status --short` that only owned paths changed, and reads the files that carry the logic against the proposal and the plan's rules (`AIMO/PLAN.md` section 2).
5. **The whole suite before each commit** (about 3.5 minutes; one timing test left out). If a test outside the agent's folders fails only because a pinned figure moved, the new value is measured offline and replaced in a commit named `pins: <task>`. Any other failure sends the change back once; a second failure marks the task blocked and the run continues without it.
6. **Demo figures at two clocks.** After each task that can move them, the demo set (`AIMO/PLAN.md` section 5) is re-measured offline at the default clock (the recording's instant, Saturday 14 Nov 02:52) and at the demo clock (Thursday 12 Nov 14:15, a replay-only setting) and written into the board.
7. **Commits** hold only that task's paths.
8. **Review of the whole diff** (`E3`): three reviewers (Python, security, silent failures) read `overnight-build..HEAD`. They get the diff range, the plan's rules and the question "what is wrong with this", never a conclusion to confirm. Each finding returns to the lane that owns the file.
9. **Ending.** Whole suite and linter once more, the demo set at the demo clock, and a hand-over that lists what works with the command that proves it, what is blocked, every default the run took, and the questions for Valio and the team.
