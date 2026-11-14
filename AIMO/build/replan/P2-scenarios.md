# P2 — Scenario catalogue (answer V2)

Measured on 14 Nov, 14:45–15:05, commit `7f09ce7`, offline replay of capture `2026-11-14-demo` (769 products, clock pinned to Saturday 14 Nov 02:52), no keys, a fresh data folder per series. Scripts and raw outputs: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/P2/` (`s1.py` … `s8.py`, `*.out`). Every figure below is from those runs unless a line says "from DEMO.md, not re-run" or "arithmetic".

## 1. In five lines
1. The build shows all six directions of the brief today: 29 scenarios are listed below (28 run in this round, 1 quoted from `docs/DEMO.md`), each with its request, profile, verdict, rules and sentences.
2. Recommended demo set, five scenarios: (1) the brief's own sentence through approval and audit, (2) the allergy ward, (3) the substitute with its trade-off, (4) the reliability preference, (5) the standing order that drifts. Opener: the brief's sentence.
3. Valio's answers change every headline figure. B5 alone turns scenario 1 into a partial fill: 435 of 1,000 L confirmed (arithmetic on today's stock). V8 turns the seven scenarios that end `AUTO` today (S3, S4, S8, S9, S12, S16, S21) into suggestions. V6 can remove the recipe stand-in. Record nothing before those land and are re-measured.
4. The build cannot show today: a deposit line (0 of the 769 captured products carry one), a lower-carbon or earliest-delivery preference that changes a choice (0 of 18 offers), a price drift, an expired offer, and 7 of the 9 recipes (1 run, 6 read from the recipe file).
5. Eleven things fail or look wrong (section 2.5). The three worth fixing: the menu planner refuses two dishes with "at most 5 lines"; an unconfirmed alternative is offered at a higher price than the confirmed option; the reliability preference pays €931.35 instead of €246.96.

## 2. What exists today

### 2.1 Where the scenarios live
- Five example buttons on `/`: `src/tta/ui/examples.py:59-130` (`scenario-1` … `scenario-5`). Read from the page: "Scenario 1 · hotel kitchen", "Scenario 2 · allergy ward", "Scenario 3 · substitutes", "Dietitian: oat drink with no milk statement", "Preference · most reliable delivery".
- OpenAPI examples built from scenarios 1 to 3 at start-up: `src/tta/api/examples.py:45-47`.
- Demo script: `docs/DEMO.md:41` (scenario 1), `:59` (2), `:72` (3), `:88` (beef backup), `:104` (extra moments), `:114` (90-second cut), `:158` (menu), `:172` (standing order), `:181` (preference). Every DEMO.md figure I re-ran matched.
- End-to-end tests pin today's figures: `tests/e2e/test_scenario_1_milk.py:39` (2580.64), `test_scenario_2_allergy_ward.py:44` (402.00), `test_scenario_3_substitutes.py:68` (174.00), `test_demo_script.py:45-46`.
- Rules: `src/tta/policy/rules.yaml` (F-01 `:142`, F-03 `:172`, F-08 `:255`, F-09 `:273`, P-05 `:365`, P-07 `:404`, P-08 `:427`, F-06 `:449`). Profiles: `src/tta/policy/profiles/hotel-kitchen.yaml`, `allergy-ward.yaml`.
- The capture holds 15 categories (14 of 104xx, and 18720). Counted with `POST /v1/products/search` over its 769 ids: 0 products with a deposit, 111 sold by variable weight, 43 with no variable-weight statement, 23 with substitutes listed by Valio, 26 with `EU_ORGANIC_FARMING`. Nine product types answer in replay: milk, sour_milk, cream, vegetable_cream, plant_drink, yoghurt, quark, beef, beef_chuck. The other 22 types map to categories outside the capture (read from `src/tta/catalog/product_types.yaml`; `src/tta/menus/recipes.yaml:17-21` says the same). The 8 of them I ran (butter, cheese, minced_meat, coffee, chicken, pork, pasta, rice) answered "not in recording".
- The capture was recorded for one delivery date: `fixtures/valio/2026-11-14-demo/manifest.json`, `requested_date: 2026-11-16`.

### 2.2 The catalogue
All offers are `POST /v1/offers` with `"needed_by": "2026-11-16"` unless said. "hotel" = token `demo-agent-hotel-kitchen`, "ward" = `demo-agent-allergy-ward`. Only `lines[0]` is shown.

**Core 1 — lookup of product, price and availability**
| id | Request | Profile | Result |
|---|---|---|---|
| S1 | `{"text":"1,000 litres of lactose-free milk by Monday","product_type":"milk","required_claims":["FREE_FROM_LACTOSE"],"quantity":1000,"unit":"L"}` (OpenAPI `scenario_1`) | hotel | 30 products looked up. Option 1 `BEST_CONFIRMED` €2,580.64 = 384 × `469363` + 51 × `462775` + 565 × `463380`. Option 2 `ALTERNATIVE_UNCONFIRMED` €1,010.00 = 1,000 × `464306`. 19 excluded: 17 cut-off passed, 1 portion pack, 1 not deliverable. Each line states price, state, amount, date and cut-off: "698 ST confirmed in stock, for delivery on Monday 16 Nov if ordered by Sunday 15 Nov at 17:00." |
| S23 | `POST /v1/products/search {"product_type":"plant_drink","limit":100}`; `POST /v1/products/473609/substitutes {"quantity":100,"unit":"L","needed_by":"2026-11-16"}` | hotel | Search: 51 plant drinks (milk 78, cream 44, yoghurt 150, quark 49, beef 149). Substitutes: 13 ranked candidates, "619 candidates checked for price, availability and allergens", 9 can be ordered, 3 are listed by Valio. |
| S21 | `{"text":"portion milk","product_type":"milk","quantity":5,"unit":"L","pack":"PORTION"}` | hotel | 3 × `463203` Arla Portion milk 100x2 cl, €45.27, `AUTO`. 77 excluded as "not a portion pack". |
| S24 | `POST /v1/requests/parse {"text": …}` with no key | hotel | Read by fixed rules (`TTA-Reading-Source: rule-based`): "30 kg beef chuck"; "100 litres of oat drink by Monday, most reliable delivery" (`prefer: RELIABILITY`); "50 litres of organic milk by Monday" (`required_labels: ["EU_ORGANIC_FARMING"]`); "20 kg of natural yoghurt by Monday, lowest carbon footprint"; "10 litres of cream and 5 kg of quark by Monday" (two lines). The brief's full sentence answers `hand-built`. |

**Core 2 — price and availability, then an order**
| id | Request | Profile | Result |
|---|---|---|---|
| S4 | `{"text":"200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only","product_type":"plant_drink","quantity":200,"unit":"L","exclude_allergens":["AM","AW"]}`, `"require_confirmed": true` (OpenAPI `scenario_2`), then `POST /v1/orders` | ward | 200 × `464013` Alpro No Sugars Soya, €402.00, `AUTO`, no rule fired. Order `ORDERED`, placed by the agent: "The agent placed this order alone for €402.00 net: no rule of profile allergy-ward asked for a human." 41 excluded: 18 declare an excluded allergen, 12 cut-off passed, 6 not deliverable, 5 allergen not stated. |
| S3 | LF milk as S1 with `"quantity":300`, then `310` | hotel | 300 L: 300 × `469363`, €744.00, `AUTO`. 310 L: €768.80, `APPROVAL`, P-01. Ten litres move the verdict across the €750 limit. |
| S20 | Three lines: LF milk 300 L, `{"product_type":"cream","quantity":20,"unit":"L"}`, `{"product_type":"beef_chuck","quantity":12,"unit":"KG"}` | hotel | €1,012.76 = 300 × `469363` + 20 × `463797` + 12 × `466988`. `APPROVAL`, P-01 and P-06. "3 confirmed products cover all 3 request lines in full … The total is a ceiling". |
| S1b | `POST /v1/agent/run {"text":"I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability."}` | hotel | Steps `get_authority`, `create_offer`, `place_order`; order `PENDING_APPROVAL`. Model `hand-built`, recorded. |

**Core 3 — permission and human approval**
| id | Request | Profile | Result |
|---|---|---|---|
| S1c | Order option 1 of S1, then `POST /v1/approvals/{id}/decision {"decision":"APPROVE","note":"Checked with the kitchen."}` as `demo-approver-hotel-purchasing` | hotel | "Waiting for approval by the purchasing manager, to be decided by Sunday 15 November 2026 at 17:00 (UTC+02:00): rule P-01 asks for a human." Then "Ordered for €2,580.64 net with approval by Demo approver Hanna (purchasing manager): rule P-01 asked for a human and was accepted." A second `POST /v1/orders` with the same `Idempotency-Key` returns the same order id. |
| S2 | Same order, decision `{"decision":"APPROVE","option_id":"opt_2"}` | hotel | `ORDERED`, €1,010.00: "rules F-01 and P-01 asked for a human and were accepted." Trail: "… approved order … and chose another option of the same offer: opt_2 (1,000 ST of 464306 for €1,010.00 net) instead of opt_1." |
| S5 | `{"text":"100 litres of Elovena barista oat drink, product 469512, by Monday; no milk, strict rule","product_ids":["469512"],"quantity":100,"unit":"L","exclude_allergens":["AM"],"allergen_strictness":"STRICT"}` (button `scenario-4`) | hotel | 100 × `469512`, €208.00, `APPROVAL`, P-04, role dietitian: "The product makes no statement about milk (AM): a dietitian must decide." The purchasing manager is refused (403). Web evidence from a local recording is attached (`src/tta/evidence/finder.py:127-128`: no key, nobody is asked) and "changes no verdict". Dietitian rejects: "Rejected by Demo approver Leena (dietitian): nothing was ordered." |
| S6 | S1 again in the same data folder after S1c | hotel | P-01 and P-02: roles purchasing manager and finance. |
| S7 | Decision with the agent's token; with finance; with a ward approver; an offer with no token, the supplier's token, an approver's token | any | 403 "An agent cannot approve or reject an order (F-06). A human with the role asked for decides." · 403 "The approval still needs the purchasing manager; this approver counts for finance" · 404 · 401 · 403 · 403. The first two are written to the audit trail. |
| S25 | `/kitchen`: spend limit 3000, then 750 (from DEMO.md `:141-152`, not re-run) | my-kitchen | Same request, another setting, another verdict. |

**Optional 1 — delivery time and sustainability comparison**
| id | Request | Profile | Result |
|---|---|---|---|
| S8 | `"prefer":"RELIABILITY"`, `{"text":"100 litres of oat drink","product_type":"plant_drink","name_terms":["oat"],"quantity":100,"unit":"L"}` (button `scenario-5`) | hotel | Option 1: 100 × `470863` Oatly Semi, €140.00, reliability 100%. Option 2 `CHEAPEST_CONFIRMED`: 100 × `472145`, €133.00, reliability unknown. Both `AUTO`. "€7.00 more than the cheapest confirmed option, for a delivery reliability of at least 100% instead of unknown." Each option carries a comparison sentence; option 1's is: "Delivery on Monday 16 Nov. Lowest delivery reliability 100%. Carbon footprint about 43.5 kg CO2e, a litre counted as a kilogram. No certificate label stated." |
| S9 | `{"product_type":"plant_drink","required_labels":["EU_ORGANIC_FARMING"],"quantity":50,"unit":"L"}`; the same with `"product_type":"milk"` | hotel | Plant drink: 50 × `460825` Oatly Oat Drink Organic, €87.00, `AUTO`. Milk: no option, "11 candidates checked: 11 cutoff passed". |
| S10 | `{"product_type":"milk","required_claims":["FREE_FROM_LACTOSE"],"required_labels":["FINNISH_HEART_SYMBOL"],"quantity":100,"unit":"L"}` | hotel | Option 1: 51 × `462775`, €131.07, 51% covered, `APPROVAL` P-03. Option 2: 100 × `464401` unconfirmed, €110.00, F-01. A label requirement and a partial fill in one request. |
| S18 | S1 with `"needed_by":"2026-11-15"` and 100 L | hotel | No option: "nothing can arrive by Sunday 15 Nov. The earliest delivery date in Valio's data for a product that otherwise fits is Monday 16 Nov, for 11 products". |

**Optional 2 — substitution and other exceptions**
| id | Request | Profile | Result |
|---|---|---|---|
| S11 | S1 with `"quantity":1500` | hotel | 384 + 51 + 698 = 1,133 L, €2,933.09, 75.5% covered. `APPROVAL`, P-01 and P-03: "only 75.5% of the requested quantity is covered, below the 90% minimum (covered: 1,133 of 1,500 L)". Option 2: 1,500 × `464306`, €1,515.00, F-01 and P-01. |
| S12 | `{"text":"100 litres of Oddlygood Barista oat drink, product 473609, by Monday","product_ids":["473609"],"quantity":100,"unit":"L"}` (button `scenario-3`) | hotel | Option 1 `SUBSTITUTE`: 100 × `475224` Fazer Aito Barista, €174.00, `AUTO`. Trade-off: "it does not carry the original's nutritional claim FREE_FROM_PRESERVATIVES; the brand is Fazer Aito, not Oddlygood®; Valio does not list it as a substitute; it costs €0.37 more per L." Option 2: `473609` itself, €137.00, F-01. Of Valio's 3 listed substitutes, `471690` has its cut-off passed and `464320`, `471881` add gluten: "It can never be ordered as a substitute." |
| S13 | Same body | ward | 100 × `473424` Alpro Rice drink, €236.00, `APPROVAL`, P-05: "a substitute that profile allergy-ward does not accept without a human". |
| S14 | `{"text":"30 kg beef chuck","product_type":"beef_chuck","quantity":30,"unit":"KG"}`; then 31 | hotel | 30 × `466988`, €506.40, `APPROVAL` P-06: "sold by variable weight, so its final price is not fixed in advance". "The total is a ceiling: … the invoice can be lower, never higher." 31 kg is sold as 33 kg, €557.04 (lot step 3 kg). |
| S15 | `POST /v1/menus/plan {"dishes":[{"dish_id":"beef_stew","servings":120},{"dish_id":"berry_quark_dessert","servings":120}],"stock":[{"product_type":"butter","quantity":3,"unit":"KG"},{"product_type":"sugar","quantity":2,"unit":"KG"}],"needed_by":"2026-11-16","require_confirmed":true}` | hotel | 4 lines, €476.48: 24 × `466988`, 4 × `463797`, 4 × `469346`, 12 × `464615`. "Yoghurt (natural) stands in for quark (maitorahka) … none of 10 products can be offered by Mon 16 Nov 2026 (6 order cut-off passed, 4 quantity not confirmed …)". `APPROVAL`, F-09 and P-06. The order waits for the purchasing manager. |
| S16 | `POST /v1/standing-orders` (100 L of `469363`), then `/renew {"quantities":[100]}` three times, then `[290]` | hotel | Renewals 1 to 3: `ORDERED` alone, €248.00, "too short a history to judge drift … at least 3 are needed". Renewal 4: `PENDING_APPROVAL`, P-08: "drifts beyond the 25% tolerance: 290 L this week against a median of 100 L over the last 3 renewals." On the page (`/standing-orders`, demo order with six synthetic weeks) the first 290 L renewal is flagged. |
| S17 | `{"product_type":"yoghurt","quantity":20,"unit":"KG"}` | hotel | 4 × `464517` AIMO natural yogurt 5 kg, €48.56, `APPROVAL` F-03: "the variable-weight statement … is missing …, so rule P-06 cannot be checked". Noisy data goes to a person (V5). |
| S19 | `"product_type":"unicorn"`; an exclusion with no strictness; text "100 litres of oat drink by Monday, no gluten" | hotel | 422 "Unknown product type. The product types are: …" · 422 "allergen_strictness is required when an allergen is excluded" · 422 "… does not say how strictly … The strictness is never guessed." |
| S26 | `{"product_type":"coffee","quantity":10,"unit":"KG"}`; ward with `{"product_type":"milk","quantity":50,"unit":"L"}` | hotel, ward | No option: "153 candidates checked: 153 not in recording". Ward: no option, "78 allergen declared". |

**Optional 3 — traceability and explainability**
| id | Request | Profile | Result |
|---|---|---|---|
| S22 | `GET /v1/audit?order_id=…&reader=buyer` and `reader=supplier` after S1c and S7 | hotel, supplier | 11 events each, one sentence each. "The audit trail is intact: each of the 11 events shown here matches its hash, and the chain they belong to verifies." Buyer: "P-01: The total of €2,580.64 before tax is above the €750 limit per order of profile hotel-kitchen." Supplier: "The agent could not place order … alone under the buyer's rules." `/healthz` gives the chain head. |
| S27 | The `excluded` list of any offer; the `decision.fired` list of any option | any | Every dropped product has a reason and a sentence. Every option carries its verdict, rule ids, roles and policy hash before anything is ordered. |

### 2.3 The matrix
C1 lookup · C2 inquiry to order · C3 permission and approval · O1 delivery and sustainability · O2 substitution and exceptions · O3 traceability · 30 end-to-end · 20m match · 20c controls · 15x exceptions · 15o openness.

| id | Scenario | Profile | C1 | C2 | C3 | O1 | O2 | O3 | 30 | 20m | 20c | 15x | 15o |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1, S1b, S1c | Brief's sentence to approval and order | hotel | x | x | x | | | x | x | x | x | x | |
| S2 | Approver picks the other option | hotel | | x | x | | | x | | | x | | |
| S3 | 300 L against 310 L | hotel | x | x | x | | | | | x | x | | |
| S4 | Ward, no milk, no gluten | ward | x | x | x | | | x | x | x | x | x | |
| S5 | Dietitian, no milk statement | hotel | | | x | | x | x | | x | x | x | |
| S6 | Second order of the day, finance | hotel | | | x | | | | | | x | | |
| S7 | Callers that are refused | any | | | x | | | x | | | x | | x |
| S8 | Most reliable delivery | hotel | x | | | x | | | | x | | | |
| S9 | Organic label | hotel | x | | | x | x | | | x | | x | |
| S10 | Heart symbol, 51% covered | hotel | x | | x | x | x | | | x | x | x | |
| S11 | 1,500 L, 75.5% covered | hotel | x | | x | | x | | | | x | x | |
| S12 | Substitute with trade-off | hotel | x | x | x | | x | x | x | x | x | x | |
| S13 | Substitute needs a human | ward | | | x | | x | | | | x | x | |
| S14 | Variable weight, lot step | hotel | x | | x | | x | | | x | x | x | |
| S15 | Recipe stand-in | hotel | x | x | x | | x | x | x | x | x | x | |
| S16 | Standing order drifts | hotel | | x | x | | x | x | x | | x | x | |
| S17 | Missing fact | hotel | | | x | | x | | | | x | x | |
| S18 | Cannot arrive in time | hotel | x | | | x | x | | | x | | x | |
| S19, S26 | Requests refused or empty | both | | | | | x | | | x | | x | x |
| S20 | Three lines, one order | hotel | x | x | x | | x | | x | x | x | | |
| S21 | Portion packs | hotel | x | | | | | | | x | | | |
| S22, S27 | Two audit views, hash chain | both | | | | | | x | | | x | | x |
| S23, S24 | Typed lookup, text to typed request | hotel | x | | | | | | | x | | | x |
| S25 | Buyer changes its own limit | my-kitchen | | | x | | | | | | x | | |

### 2.4 What the build cannot show today
- **A deposit line (P-07).** 0 of the 769 captured products carry a deposit. In the catalog, deposits sit on mineral water (63 of 63) and soft drinks (91 of the first 100 of 157), which the capture does not hold.
- **A lower-carbon or earliest-delivery preference that changes the choice.** 9 product types × 2 preferences = 18 offers, 0 changed option 1 (quark and sour milk have no confirmed option at all). Carbon is close to one value per category (`docs/DEMO.md:194`), and the capture has one delivery date. The figures are shown per option; they decide nothing.
- **A price drift on a standing order.** Replay prices never move; only the quantity can drift.
- **An offer that expires (F-04).** Inference from the pinned clock, not run.
- **Seven of the nine recipes.** `creamy_chicken_pasta` was run: chicken, pasta and cheese "cannot be sourced … not in the recorded capture". The other six each name a type outside the capture (read from `recipes.yaml`, not run).
- **The unit conversion of Q14 (100 cartons become 10 cases).** The listed substitute sold in 10 L cases, `471690`, has its cut-off passed.
- **Free text outside the 7 recordings and the rule shapes.** With no key the answer is 503.
- **"Suggest, then the user confirms" (V8)** and **"same brand or formula" (V10).** Neither state nor rule exists.

### 2.5 Scenarios that fail or look wrong today
1. **The menu planner refuses two dishes.** `POST /v1/menus/plan`, hotel, `{"dishes":[{"dish_id":"beef_stew","servings":120},{"dish_id":"berry_quark_dessert","servings":120}],"needed_by":"2026-11-16"}` → 422 "In this demonstration a request has at most 5 lines; this one has 6. Send the others as another request." The caller sent dishes, not lines. Limit: `src/tta/api/service.py:55`. The page example works only because butter and sugar are typed as kitchen stock (`src/tta/ui/menu_page.py:39-44`). The published schema allows 20 lines (`src/tta/contracts/request.py:15`), so a typed request with 6 lines is refused too (run: six cream lines → 422).
2. **An unconfirmed alternative that costs more.** Hotel, `{"text":"20 kg beef","product_type":"beef","quantity":20,"unit":"KG"}` → option 1 confirmed €246.96 (21 × `466952`), option 2 "quantity not confirmed" €382.20 (20 × `467014`). It gives the approver nothing. `src/tta/offers/planning.py:5`, `:74-75`.
3. **The reliability preference at any price.** Same body with `"prefer":"RELIABILITY"` → option 1 is 21 × `463053` Tenderloin, €931.35: "€684.39 more than the cheapest confirmed option, for a delivery reliability of at least 52.4% instead of unknown." A known 52.4% beats an unknown, a tenderloin replaces a flank, and P-01 now fires. Cream, 20 L: whipping cream `464727` at €147.40 against cooking cream `463797` at €66.20. A product with no figure ranks after every product with one (`src/tta/offers/preference.py:4`).
4. **The menu sentence changes its count.** S15 body without `require_confirmed`: "none of 6 products can be offered … (6 order cut-off passed)". With it: "none of 10 products". The 4 unconfirmed quarks (`465165`, `467156`, `477044`, `477086`) vanish from the sentence and yoghurt stands in. A typed request for the same line, `{"product_type":"quark","name_terms":["maitorahka"],"quantity":12,"unit":"KG"}`, offers the recipe's own ingredient to a person: 3 × `477044`, €48.09, F-01. So the planner swaps the ingredient where the original could be approved.
5. **The audit trail of a substitute order does not say what was given up.** Order option 1 of S12. Last sentence: "The agent placed order … alone, within its authority under profile hotel-kitchen: 100 ST of 475224 for €174.00 net. No rule asked for a human." No event names the brand change, the claim lost or the €0.37 per L. The trade-off is in the offer only.
6. **`price_difference` compares a case with a carton.** `POST /v1/products/473609/substitutes` → `471690`: `price_difference` 14.18, sentence "it costs €0.19 more per L". `471881`: 11.13 against "€1.13 more per L". The sentence is right; the typed field misleads a machine reader. `src/tta/contracts/offer.py:230`.
7. **"Coffee milk" cannot be read.** `POST /v1/requests/parse {"text":"200 litres of coffee milk by Monday"}`, no key → 503 `supplier-unavailable`: "line 1 names more than one product type (coffee, milk)". After B5 a judge will type this sentence.
8. **Product types mix what a cook keeps apart.** 20 kg yoghurt → option 2 is `462849` peach-passion yoghurt. 200 L cream → 114 × cooking cream `463797` + 48 × whipping cream `469346` + 37 × `464727`, 199 of 200 L, €926.99. Same family as B5.
9. **One product is preferred to a cheaper mix, and no sentence says so.** 430 L of LF milk → 430 × `463380`, €1,139.50. 384 × `469363` + 46 × `462775` would be €1,070.54 (arithmetic). Rule: `src/tta/offers/combining.py:3-5`.
10. **The supplier's view drops the claim asked for.** Buyer: "read as: 1,000 litres of product type milk with claim FREE_FROM_LACTOSE". Supplier: "read as: 1,000 litres of product type milk". Valio's answer B13 is "all the steps and decisions".
11. **Small ones.** A date in the past (`"needed_by":"2026-11-13"`) is answered as "nothing can arrive by Friday 13 Nov"; it does not say the date has passed. Ward, 600 L of plant drink → a line of 1 × `460509` next to 478 × `464013`: its confirmed stock is 1, so the fill is right and looks odd. My own series hit 429 at the 21st offer in a minute from one address (`src/tta/api/limits.py`); judges on one Wi-Fi share an address.

## 3. What Valio's answers change
In words only. Nothing was re-measured under a new clock.

| Scenario | V6 clock moves back | B5 coffee milk leaves "milk" | V8 no order without the user | V10 same brand or formula |
|---|---|---|---|---|
| S1, S1c, S2, S22 | 17 of the 19 exclusions are passed cut-offs. Some become candidates, so products, total and counts change. | `463380` supplies 565 L and drops out. Left: 384 + 51 = 435 L, 43.5%, €1,083.39 (arithmetic). P-03 joins P-01. The opener becomes a partial fill. | No change: it already goes to a human. | The fill mixes three milks. "Normal milk is fine", so no change expected. |
| S11 | Likely more confirmed stock, so the 75.5% moves. | 698 L drop out: 435 of 1,500 L, 29% (arithmetic). | None. | None. |
| S3 | Other products may become cheaper candidates. | None: `469363` only. | 300 L is no longer ordered alone: suggested, the user confirms. The 300/310 pair then shows "your confirmation is enough" against "the purchasing manager must sign". | None. |
| S4 | 12 exclusions are passed cut-offs; the choice may change. | None. | "Ordered by the agent" becomes "suggested". This is the scenario that proves the autonomous path, so automatic ordering must stay visible as a setting. | None. |
| S5 | `469512` must stay confirmed. | None. | None: the dietitian decides. | None. |
| S8, S9 | Organic milk: all 11 candidates are passed cut-offs, so an option may appear. | None. | Both `AUTO` outcomes become suggestions. | None. |
| S10 | 4 of 6 candidates are passed cut-offs; the 51% may become 100%. | None seen. | None. | None. |
| S12, S13 | `471690`, same brand, listed by Valio, sold in 10 L cases, has a passed cut-off. It may become the substitute, and then Q14 is shown. | None. | The `AUTO` substitute becomes a suggestion. | Largest change. Fazer for Oddlygood is another brand and is ordered alone today. A rice drink for a barista oat drink is another base. Both must go to a person or rank below a same-brand product. |
| S14, S20 | 2 beef chuck cut-offs passed; price may change. | None. | None: P-06 or P-01 already ask. | None. |
| S15 | Highest risk. The stand-in exists because 6 quarks have a passed cut-off. With an earlier clock quark may be orderable and F-09 never fires. | None. | None: F-09 asks. | Consistent: a recipe is exactly "things that require the formula". Offer the recipe's own ingredient with unconfirmed stock to a person before another ingredient (item 4 of 2.5). |
| S16 | The synthetic history is dated from the clock; no change expected. | None. | The usual renewal (100 L) is no longer ordered alone unless the buyer switched automatic ordering on. "Auto-renew" is in Valio's own example, so this is the natural place for that switch. | None. |
| S17, S18, S19, S21, S23–S27 | S18 depends on what "today" is. | S24: "coffee milk" becomes a sentence to read. | S21 becomes a suggestion. | None. |

Note for P5: the capture answers for one date, 16 Nov. "By Monday" is the first Monday after today (B11). If the clock moves before Monday 9 Nov, "Monday" becomes 9 Nov and no captured product can meet it.

V2 can be read two ways: (a) customer types, each with its own rules and data (P1), or (b) the agent learning one customer's ordering pattern. Today only S16 uses a customer's history.

## 4. Options and recommendation

**The demo set, in order (2:00 video; the 3:00 pitch uses the same order with the reserve for questions).**
| # | Time | Scenario | Covers | What a judge sees in the first 5 seconds |
|---|---|---|---|---|
| 1 | 0:00–0:45 | S1 + S1c + S22: the brief's sentence, the approval, the order record, the two audit views | C1, C2, C3, O3 (and O2 once B5 makes it a partial fill) · 30%, 20m, 20c | Valio's own sentence in the box, then three boxes: green "confirmed products cover … L", yellow "cheaper, stock not confirmed, a human must approve", red "19 products excluded, each with its reason". |
| 2 | 0:45–1:03 | S4: the allergy ward | C3 (what needs no sign-off), V5 · 20c, 20m | "No milk, no gluten, confirmed data only" and a green outcome, next to "18 declare an excluded allergen, 5 make no statement". |
| 3 | 1:03–1:22 | S12: the substitute | O2 · 15x, 20c | A ranked list where two substitutes Valio lists itself are red: "adds … gluten. It can never be ordered as a substitute." |
| 4 | 1:22–1:38 | S8: most reliable delivery | O1 · 20m | Two options side by side: "ranked by delivery reliability", "€7.00 more", and reliability, carbon and labels on each. |
| 5 | 1:38–1:53 | S16: the standing order that drifts | V2 "user pattern", C3, O3 · 20c | Six weeks near 100 L, then "290 L this week against a median of 100 L": waiting for approval. |
| close | 1:53–2:00 | `/docs`, the MCP tool list, `/assumptions` | 15o | The OpenAPI page with a real example. |

**Opener: S1, typed as the brief writes it.** Three reasons. Judges recognise their own sentence at once. It is one continuous flow from request to order, which is the 30% criterion. After B5 the same screen also shows partial availability and good-better-best.

**Reserve for questions:** S15 (recipe), S5 (dietitian with web evidence), S14 (variable weight), S3 (the €750 boundary), S7 (an agent cannot approve), S25 (the buyer's own limit).

- **DECISION 1 — the five and the opener.** Recommendation as above.
- **DECISION 2 — slot 5: standing order (S16) or recipe (S15).** S16: fits V2's "user pattern", does not depend on cut-offs, 15 seconds on screen. S15: Valio's "need → recipe → order" example and the richest sentence, but V6 can remove its stand-in and it breaks at 6 lines. Recommendation: S16 in the video, S15 in the reserve.
- **DECISION 3 — keep 1,000 L after B5.** The opener then covers 43.5% on today's clock and asks for two rules. Recommendation: keep it; partial availability is 15% and it is the brief's number. Re-measure after P5.
- **DECISION 4 — the reliability preference.** Keep "unknown ranks last" and demo oat drinks only, or count an unknown as neutral. Recommendation: keep it for the demo, never show beef or cream, and fix the ranking so a low known figure (52.4%) does not beat an unknown one at four times the price.
- **DECISION 5 — what V2 means.** João says which reading the mentor meant (section 8).

## 5. Work items
Minimum version first: W1 and W2, 2 hours together. Cut W7 first, then W6, then W5.

| id | What | Files | Hours | Who | Criterion | Depends on |
|---|---|---|---|---|---|---|
| W1 | Re-measure the five demo scenarios and the reserve after the clock, coffee-milk, confirmation and formula changes land; rewrite the demo script and the 2:00 cut with the new figures | `docs/DEMO.md`, `tests/e2e/test_scenario_*.py`, `tests/e2e/test_demo_script.py` | 1.5 | biomedical member | 30% | P5, P8, P9a, P10 |
| W2 | One button per demo scenario on `/`, in demo order, with a link to the standing-order page | `src/tta/ui/examples.py`, `src/tta/ui/templates/index.html` | 0.5 | computer-science member | 30% | DECISION 1, 2 |
| W3 | A menu plan is not refused at 6 lines: lift the limit for plans, or say which dishes to send apart | `src/tta/api/service.py:55`, `src/tta/menus/plan.py:23`, tests | 0.5 | computer-science member | 30%, 15x | — |
| W4 | Do not offer an unconfirmed alternative that costs more than the confirmed option | `src/tta/offers/planning.py:74-75`, tests | 0.5 | any | 20m | — |
| W5 | The audit trail of a substitute order names the original and what is given up | `src/tta/audit/sentences.py:142`, tests | 0.5 | any | 20c, O3 | P10 |
| W6 | Reliability preference: a known low figure must not outrank an unknown one at any price; state the premium as a share | `src/tta/offers/preference.py`, `src/tta/offers/wording.py` | 0.5 | biomedical member | 20m | DECISION 4 |
| W7 | `price_difference` per requested unit next to the per-sales-unit field | `src/tta/contracts/offer.py:230`, `src/tta/offers/substitutes.py` | 0.25 | any | 15o | — |

Not proposed: a new capture with deposits or a second delivery date. It needs calls to the mock, and P-07 and "earliest" score on no criterion that the five scenarios leave open.

## 6. What changes in the demo
- Scenario 1 keeps its sentence. Its green box changes from "3 confirmed products cover the 1,000 L asked for, for €2,580.64" to a partial fill once coffee milk is out: 435 L and €1,083.39 on today's clock (arithmetic; the clock change moves it again).
- Scenario 2's outcome changes from "✓ Ordered by the agent" to a suggestion the user confirms. The video must still show one order placed alone with the setting switched on, or the 20% criterion loses its autonomous half.
- Scenario 3's substitute stops being ordered alone. The trade-off sentence already names brand, claim and price, so it becomes the reason shown to the person.
- New in the cut: the reliability preference (16 seconds) and the standing order (15 seconds). Out of the cut: nothing; the 90-second cut of `docs/DEMO.md:114` had no slot for optional direction 1.

## 7. Risks and what not to do
- Do not record the video before the changes of section 3 are merged and W1 is done: every figure moves.
- Do not show the recipe stand-in until P5's clock is fixed and quark is checked under it.
- Do not demo the reliability preference on beef or cream (item 3 of 2.5).
- Do not let a judge type a product outside the nine captured types in replay: the answer is "not in recording". Say which types the recording holds.
- Empty the order book between takes: a second scenario 1 in the same day adds finance (S6).
- One address gets 20 offers a minute. Rehearse the five scenarios inside that.
- Do not claim a deposit, a carbon-ranked choice or an earliest-date choice: the capture cannot show them.

## 8. Questions
**For the team (João):** in V2, "see per user based on the user pattern", did the mentor mean customer types with their own rules, or the agent learning one customer's orders over time? The demo's fifth slot follows the answer.

**For Valio, if the booth is still open:**
- Context: you said the goal is "to see per user based on the user pattern".
- What we did: two buyer profiles with their own limits and allergen rules, and a standing order whose renewal is checked against that buyer's last six weeks.
- What we got: a renewal of 290 L against a median of 100 L goes to a person; 100 L does not.
- Example: "Weekly lactose-free milk, hotel kitchen", product `469363`, weeks of 100, 96, 104, 100, 98 and 102 L (synthetic).
- The ask: is that the pattern you meant, or did you mean different customer types?
- If nobody answers: we keep both, the customer types of P1 and the standing order as scenario 5.
