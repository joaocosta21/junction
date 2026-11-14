# P1 — Customer types and their generated data (answers V1 and V2)

Written Saturday 14 Nov, replan round. Nothing in the repository was changed except this file. Scratch scripts: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/P1-customers/` (`count.py`, `count2.py`, `measure.py`).

How the numbers were made. "Catalog" = the whole product file (17,546 products). "Capture" = the replay recording `2026-11-14-demo` (769 products, clock pinned to Sat 14 Nov 02:52). States were counted with the app's own code (`ProductCatalog`, `ReplayGateway`, `availability.states.classify`). Offers were measured with the offline recipe of the brief (replay, no keys, fresh data folder).

## 1. In five lines
1. The product models two customers today (`hotel-kitchen`, `allergy-ward`) and one synthetic standing order. No customer has usual products, an order history of its own, or a default preference. So "per user, based on the user pattern" (V2) is not in the product yet.
2. Measured gap: the hotel asks for "100 L milk" and gets 100 × `463047` (whole milk, low lactose), though its own weekly order is `469363` (lactose-free, semi-skimmed). "The usual milk for Monday" answers 503 (measured with no model key; the model prompt also forbids estimating a quantity).
3. Recommend six documented types and four built: hotel kitchen and hospital ward (exist), **bakery-café** (V10: formula matters) and **school kitchen** (drift, volume). Lunch restaurant and catering stay documented only.
4. Data: one committed pattern file per customer (usual products, 8 synthetic weeks, standing orders, stock on hand), written once with a model (V1), checked against the catalog and the capture by a test, labelled synthetic on every screen.
5. The capture is enough for all four types on dairy, plant drinks and beef. A bakery's flour, sugar, butter and eggs (177 products) need a second recording: 2 live calls, which only the team can approve. Minimum version: 2 hours (work items C1–C3).

## 2. What exists today (verified)
- **Two buyer profiles**, limits only: `src/tta/policy/profiles/hotel-kitchen.yaml:9-29`, `src/tta/policy/profiles/allergy-ward.yaml:8-29`. Contract: `src/tta/contracts/policy.py:28-57`. A profile file with any setting the contract does not know is rejected (`src/tta/policy/profiles.py:42-48`).
- **Identities**: 2 agents, 6 approvers, 1 supplier, invented names (`src/tta/api/demo_tokens.yaml:16-73`). Who signs is `approver_roles` in each profile.
- **One standing order, one customer**: 100 L of `469363` a week for the hotel, six synthetic weeks written as a literal (`src/tta/standing/demo.py:21-28`), loaded only by a button of the page (`src/tta/ui/standing_page.py:165`). Measured: `GET /v1/standing-orders` for the hotel returns 0 at start.
- **Drift rule P-08**: median of the last 6 renewals, at least 3 needed (`src/tta/policy/drift.py:27-28`), rule at `src/tta/policy/rules.yaml:427`, tolerance per profile (`hotel-kitchen.yaml:23` 25%, `allergy-ward.yaml:23` 10%).
- **Synthetic label**: `src/tta/ui/templates/standing.html:12` and `:59` ("Synthetic: made up for the demo"); `Renewal.synthetic` in `src/tta/contracts/standing.py:88`.
- **Preference** (price, earliest, reliability, lower carbon) is per request, default price (`src/tta/contracts/request.py:99-103`, `src/tta/offers/preference.py:42-51`). The profile holds none.
- **Recipes and stock on hand**: 290-line illustrative recipe table (`src/tta/menus/recipes.yaml:23`); kitchen stock is sent with each menu request and stored nowhere (`src/tta/contracts/menu.py:89-94`).
- **Ordering alone can be switched off per profile**: `auto_order_enabled` (`hotel-kitchen.yaml:14`), rule P-00 (`rules.yaml:288`). Both profiles ship with `true`.
- **Substitution scope per profile**: `substitution_without_approval` (`hotel-kitchen.yaml:19` SAME_CATEGORY, `allergy-ward.yaml:19` NONE), rule P-05 (`rules.yaml:365`).
- **A vague request is refused.** Measured, hotel token, no model key: `POST /v1/requests/parse` with "the usual milk for Monday" → 503, "milk is named with no quantity in digits and unit" (`src/tta/agent/rules_reader.py:67`). The model prompt also forbids estimating a quantity (`src/tta/agent/prompts.py:25`).
- **A request by type takes the cheapest product, whoever asks.** Measured: hotel, typed line `product_type: milk`, 100 L, Monday → `BEST_CONFIRMED` 100 × `463047` (capture price €2.01 each), verdict AUTO. The same hotel's standing order is `469363` (€2.48).
- **A cheaper product of another formula can be ordered alone.** Measured: hotel, 60 L of whipping cream `469346` (48 confirmed) → option `SUBSTITUTE` = 48 × `469346` + 12 × `463975` "Arla Pro Ruoka 1 L 15% lactose free vegetable mix", verdict AUTO, no rule fired. A 15% vegetable-fat cooking blend stands in for whipping cream. The honest option, 48 × `469346` alone, needs a human (P-03, 80% covered); the blend option does not.
- **Replay reads one capture folder** (`src/tta/config.py:46`, `src/tta/valio/replay.py:57-73`). The customer number does not change the mock's answers (`src/tta/config.py:50`).
- The two profile ids appear in 97 test files (`grep -rln` over `tests/`). Do not rename them.

## 3. What Valio's answers change
- **V1** ("generate the data with claude, it is generic data"): customer data is ours to write. It must be labelled synthetic and must use real product ids.
- **V2** has two readings. I do not pick one; the proposal serves both.
  - (a) The agent should act per user from that user's pattern (history, usual products).
  - (b) The judges should see, per user type, every core requirement and optional direction handled.
- **V10**: how strict a substitute must be depends on the customer. A bakery uses cream as an ingredient; a lunch restaurant puts it in a sauce. Today strictness is one profile setting with three values and no notion of "ingredient".
- **V8**: a value taken from a pattern (a product, a quantity) is a suggestion. The user confirms it. (The flow is P8's.)
- **B5** ("milk is not coffee milk, be explicit"): which milk a buyer means is a per-customer fact. A café is the believable buyer of `463380` Arla Café milk; a hotel is not. (The type split is P9a's.)

## 4. Customer types

### 4.1 Facts used
- Valio Aimo's delivery-wholesale page: "our customers include restaurants, hotels, cafes, catering services, large kitchens, service stations, and kiosks." The webshop holds "your order history and order templates", and "you can now plan orders for several weeks ahead at once and confirm them as your plans become more precise." https://www.valioaimo.fi/en/become-a-customer/delivery-wholesale/
- Valio Aimo's tools page: "create standard orders", "your favorite product in the online store", "My Recipes", "review your purchase reports and the carbon footprint of your food purchases". https://www.valioaimo.fi/en/company/why-choose-valio-aimo-as-a-partner/innovative-tools-for-everyday-work/
- Both pages were read through an automatic page reader. A person should check the quotes before they go on a slide.
- From search summaries only (pages not opened; treat as leads, not facts): bakeries and industrial customers are named in https://www.vincit.com/our-work/valio-aimo ; public-sector customers came with Valio's network in https://news.cision.com/valio-oy/r/valio-to-acquire-heinon-tukku-oy---eating-away-from-home-is-a-long-term-megatrend,c3334005 ; in 2008 schools served 27% of the meals of Finnish large-scale kitchens, cafeterias 22%, restaurants and hotels 16% (https://www.cambridge.org/core/journals/public-health-nutrition/article/school-and-workplace-meals-promote-healthy-food-habits/2F8FF15391CB31DAEE8FD0D5388345AD); school menus rotate on six weeks in Vantaa and Helsinki (https://www.vantaa.fi/en/node/2073, https://palvelukeskus.hel.fi/en/food-services/school-meals); Espoo asks for a medical certificate for severe allergies (https://www.espoo.fi/en/childcare-and-education/school-catering).
- Why this matters for the pitch: order history, order templates, standard orders and favourites already exist in Valio Aimo's webshop. Our generated pattern data mirrors things their customers already have. It is not an invention.

### 4.2 The six types
Every product id below exists in the catalog and is `CONFIRMED` in the capture at the pinned clock, with the amount shown (checked by `count2.py`). Rhythm, sizes, who signs and preferences are **assumptions** of ours unless a source is given.

| # | Type (profile id) | Who orders · who signs | What they order (verified ids, confirmed amount) | Rhythm and size | Allergen rule | Substitution | Prefers | Exception that matters most |
|---|---|---|---|---|---|---|---|---|
| 1 | **Hotel kitchen** (`hotel-kitchen`, exists) | Kitchen agent for the chef · purchasing manager above €750, finance above €3,000 a day | `469363` LF semi-skimmed milk (384 ST), `463203` portion milk 100×2 cl (192 KI), `464615` greek yoghurt 1 kg (100), `463797` cooking cream 10% (114), `466988` beef chuck (109 kg, lot 3 kg, variable weight) | Weekly standing order (100 L milk) plus event peaks (the brief's 1,000 L) | None by default; per request | Same category, alone (today) | Price | Partial availability on a large order |
| 2 | **Hospital / care ward** (`allergy-ward`, exists) | Ward kitchen agent · dietitian for any allergen doubt, purchasing manager for substitutes | `464013` Alpro soya drink no sugars (478 ST, reliability 1.0), `473424` Alpro rice drink (109 ST, reliability 1.0) | Twice a week, small (200 L) | Milk and gluten excluded, STRICT | None without a human | Delivery reliability | Missing or contradicting allergen data (V5) |
| 3 | **School / municipal kitchen** (`school-kitchen`, new) | Production planner's agent · food-service manager; dietitian for special diets | `462775` LF fat-free milk (51 ST only), `463047` whole milk low lactose (132), `470863` Oatly oat drink (1,414 ST, €1.40), `464517` AIMO natural yoghurt 5 kg (242 PRK), `466988` beef chuck for the stew of `recipes.yaml`, `463254` Millac cooking blend (Heart Symbol label) | Weekly, six-week menu rotation, large and steady | No profile exclusion; a special-diet line excludes per request, STRICT | Listed by Valio only | Price, then labels (`FINNISH_HEART_SYMBOL`, `EU_ORGANIC_FARMING` on `460825`) | Drift (portion counts creeping up) and a usual product with 51 units in stock |
| 4 | **Bakery-café** (`bakery-cafe`, new) | Head baker's agent · the owner | `469346` Arla Pro whipping cream (48 ST, €5.77), `464727` Arla whipping cream ESL (37 ST, €7.37, reliability 1.0), `463380` Arla Café milk (698 ST), `469512` Elovena barista oat drink (520 ST). Quark: 0 of 49 confirmed, 11 unconfirmed. Flour, sugar, butter, eggs: not in the capture | Two or three small orders a week, very steady | None excluded; the allergens of what is sold must not change | **None alone. Formula matters (V10): same brand and formula, or a human** | Delivery reliability | A cheaper product with another formula (the measured `463975` case) |
| 5 | **Lunch restaurant** (documented) | Owner-chef orders and signs | `464762` beef knuckle (29 kg, €13.68), `466952` beef flank (38 kg, €11.76), `467297` Rama cooking 15% (940 ST), `464608` Turkish yoghurt 5 kg (1,318 PRK) | Daily or every second day, menu changes daily | Per request | Loose: by the ingredient's role in the dish (rule F-09 exists) | Price | A cut-off that has passed for tomorrow's lunch |
| 6 | **Catering / event company** (documented) | Event planner's agent · finance (large one-off sums) | `463053` Well Beef tenderloin (36 kg, €44.35, reliability 0.524), `463059` Naturkött tenderloin (129 kg, €32.56, reliability 0.354), `464152` Atria striploin (740 kg), `469346` whipping cream | Irregular, no pattern | Per event | Same category, with sign-off | Reliability, earliest date | Last-minute event; variable weight (P-06); no history, so nothing may be defaulted |

Type 6 is useful as the counter-example: a customer with no pattern gets no default, and the agent says so.

## 5. The data to generate per type

### 5.1 Where it lives and its format
- Keep limits and pattern apart. Limits stay in `src/tta/policy/profiles/<id>.yaml` (hashed into `policy_hash`, `contracts/policy.py:91`). The pattern goes in a new file per customer, `src/tta/customers/data/<profile_id>.yaml`, outside the hashed policy. Reason: a history changes every week; a policy hash must not.
- Proposed shape (names are a proposal, to be agreed before code):

```yaml
customer_id: bakery-cafe            # equals the profile id
synthetic: true                     # required; the loader rejects a file without it
who: {orders: "head baker", signs: "owner"}
prefer: RELIABILITY                 # used when a request states no preference
usual:                              # the "favourites" of Valio Aimo's webshop
  - product_type: cream
    product_id: "469346"
    use: INGREDIENT                 # INGREDIENT (formula matters, V10) or SERVED
    weekly: {quantity: 40, unit: L}
history:                            # 8 weeks, oldest first; quantity per usual product
  - {weeks_ago: 8, quantities: {"469346": 38, "463380": 60}}
standing_orders:
  - {name: "Weekly cream and coffee milk", cadence_days: 7, products: ["469346", "463380"]}
stock_on_hand:                      # only for types that cook
  - {product_type: cream, quantity: 6, unit: L}
```

- Sizes: 4 to 8 usual products per type; **8 weeks** of history (the drift window is 6 and needs 3, `policy/drift.py:27-28`; 8 fills the window and leaves two older weeks); 1 or 2 standing orders; 3 to 6 stock lines for hotel and school. Recipes: reuse the dishes of `recipes.yaml`; no new dish in the minimum version.
- History prices are read from the capture when the data is loaded, as today (`standing/demo.py:40-44`). One line may carry an explicit older price to show cost drift.

### 5.2 How it is generated
| Option | For | Against |
|---|---|---|
| **A. A file written once with a model and committed (recommended)** | It is what V1 says. The demo is the same on every run. The diff is reviewable. It is how the existing demo order is done (a literal tuple, `standing/demo.py:28`). Believable choices (which cream a baker buys) need judgement | Changing the data means editing a file |
| B. A seeded script that generates the history | Any number of weeks or customers | One more moving part; figures in the documents depend on a seed; no judge sees the difference |

Recommendation: A. **DECISION 2.**

### 5.3 How it is checked (a loader check and a test, in the style of `menus/recipes.py:68-86`)
- Each product id exists in the catalog and is not deleted (`ProductCatalog.get_product`).
- Each product is of the product type stated (catalog search by type).
- Each product has a price in the replay capture, and its state at the pinned clock is written in the test table, so the demo paths are known.
- The unit converts: `catalog.pack_size(product, price, unit).is_known`.
- The weekly quantity is a whole number of sales units after `round_to_lot` (`catalog/lots.py`); beef has lots of 3 kg (`466988`).
- The profile exists; each approver id has a token in `demo_tokens.yaml`.
- Each history line has at least 6 weeks, and its median equals `weekly.quantity`, so drift demos are predictable.
- `synthetic: true` is present.

### 5.4 How every screen labels it
- Pages: the existing tag "Synthetic: made up for the demo" (`standing.html:59`) on every usual product, history row and stock line.
- API: `synthetic: true` on the pattern object; an offer note such as "Product chosen from this buyer's usual products (synthetic history of 8 weeks)".
- Audit: the fact `synthetic_history: true` on the event, as standing orders already count `synthetic_renewals` (`standing/service.py:143`).
- `/assumptions` and `docs/ASSUMPTIONS.md`: one section "Customers and their history are ours".

## 6. How the gateway would use the pattern
| Use | State | Evidence or change |
|---|---|---|
| Limits and approvers per customer | **Exists** | Profiles and tokens (section 2). A new type is one profile file and its tokens |
| The user always confirms (V8) | **Exists as a switch** | `auto_order_enabled: false` → rule P-00 (`rules.yaml:288`). The flow is P8's |
| Substitutes only with a human | **Exists** | `substitution_without_approval: NONE` → rule P-05 (`rules.yaml:365`). The bakery profile uses it from minute one |
| Drift on a renewal (P-08) | **Exists**, for one order of one customer | `policy/drift.py:42`. **Small change:** load standing orders and history for every customer from the pattern files at start-up, not by a page button |
| Default preference per customer | **Small change** | `prefer` is per request (`contracts/request.py:99`); apply the customer's when the request states none |
| Default product for a vague line ("milk", "the usual milk") | **New** | A pure function before the offer builder (`api/service.py:170`): a line that names a type and no product gets the customer's usual product id, and a note says so. Asking by id also opens the substitute path, which type lines lack (`offers/planning.py:201`) |
| Default quantity for "the usual" | **New** | The median of the history, never a model's guess. Always a suggestion to confirm (V8). Today the reader refuses (`rules_reader.py:67`) |
| Reorder suggestions | **New** | A standing order that is due, or stock on hand below one week's use, becomes an offer shown with "Confirm". Today a renewal places the order itself (`standing/service.py:197`); under V8 that step changes (P8) |
| Cheaper suggestions that keep the formula (V10) | **New**, rules are P10's | The pattern supplies `use: INGREDIENT` per usual product; P10's rule reads it |

One rule for all of them: a pattern may pin a product or add a confirmation. It may never widen what the agent decides alone, never remove an exclusion, never weaken a fixed rule.

## 7. The capture limit
Capture `2026-11-14-demo`: 769 products. At the pinned clock: 123 CONFIRMED, 368 CUTOFF_PASSED, 145 NOT_DELIVERABLE, 112 QUANTITY_NOT_CONFIRMED, 21 OUT_OF_STOCK.

| Product type | Catalog | In capture | Confirmed | Not confirmed | Cut-off passed | Not deliverable |
|---|---|---|---|---|---|---|
| milk | 78 | 78 | 5 | 11 | 55 | 7 |
| cream | 44 | 44 | 5 | 9 | 26 | 4 |
| vegetable_cream | 9 | 9 | 6 | 1 | 2 | 0 |
| plant_drink | 51 | 51 | 24 | 5 | 12 | 10 |
| yoghurt | 150 | 150 | 5 | 37 | 90 | 18 |
| quark | 49 | 49 | 0 | 11 | 23 | 15 |
| sour_milk | 11 | 11 | 0 | 4 | 6 | 1 |
| beef | 149 | 149 | 26 | 4 | 49 | 52 (18 more out of stock) |
| beef_chuck (part of beef) | 7 | 7 | 2 | 0 | 2 | 3 |
| the other 22 product types | 2,323 | 0 | – | – | – | – |

- 52 more confirmed products of the capture belong to no product type (plant-based cooking 10406: 14; plant-based yoghurt and desserts 10413: 16; condensed milk 10404: 5; others).
- **Moving the clock back does not add confirmed stock.** With the clock before every cut-off (Thu 12 Nov 00:01), confirmed goes from 123 to 125 and unconfirmed from 112 to 478. The products past their cut-off are almost all placeholders. This is input for P5.
- **Showable today:** hotel, ward, school kitchen, lunch restaurant and catering, on dairy, plant drinks and beef. The bakery-café is showable on its dairy side only (2 whipping creams in 1 L packs, coffee milk, barista drinks; quark only unconfirmed).
- **A second recording would add:** bakery dry goods: flour (21300, 21310: 87 products), sugar (22100: 40), butter (10500: 20), eggs (10590, 10592: 30) = **177 ids → 2 calls** (1 availability, 1 price). Wider: chicken, pork, fish, minced meat 312; rice and pasta 206; cheese 295; bread 118; coffee and tea 282; juice 94; olive oil 45. All of it: 1,529 ids (+1 listed substitute) → **4 calls**. One call takes at most 1,000 ids (`AIMO/docs/API.md:80`); the existing capture cost 2 calls (`manifest.json`, `"calls": 2`).
- **Rule for choosing ids:** (1) only product types that a built customer's usual products or a recipe names; (2) every product of those types' categories, so that "cheapest that fits" and substitutes have real competition; (3) plus Valio's listed substitutes (`--with-listed-substitutes`); (4) at most 1,000 ids per call; (5) no sweep of the catalog (`API.md:76`).
- **Options. DECISION 3.**
  - A. No new recording, 0 calls. The bakery is shown on cream and coffee milk. Recommended for the minimum version.
  - B. Record the 769 again plus the 177 in one capture: 946 ids, 2 calls. One clock, no code change. Every documented figure must be re-checked. Evidence that the old figures would hold: 51 ids are in both existing captures (Fri 23:00 and Sat 02:52) and all 51 have identical availability and price; V6 calls the data static.
  - C. A second folder with the 177 ids, 2 calls, and replay reading two folders (about 1 h, `valio/replay.py:57-73`, `config.py:46`). The demo figures stay untouched. Recommended if the team wants flour and butter in the bakery story.
  - B and C make live calls: only the team can approve them.

## 8. Recommendation: what to build
| Type | Build? | Criterion | Minimum version (inside the 2 hours of C1–C3) |
|---|---|---|---|
| Hotel kitchen | Yes (exists) | 30% end-to-end; it is the brief's own example | Add its pattern file: usual `469363`, 8 weeks |
| Hospital / care ward | Yes (exists) | 20% controls; V5 | Add its pattern file: usual `464013`, 8 weeks |
| Bakery-café | **Yes (new)** | 15% exceptions and 20% match; V10 | Profile with substitutes NONE, usual `469346` and `463380`, 8 weeks |
| School kitchen | **Yes (new)** | 20% controls (P-08), 15% partial availability | Profile, usual `462775` and `470863`, a standing order with 8 weeks |
| Lunch restaurant | Documented only | 15% delivery constraints | One paragraph in the assumptions |
| Catering / event | Documented only | 15% delivery constraints | One paragraph; the "no pattern, no default" case |

**DECISION 1:** these four, or a different set.

## 9. Work items
"CS" = the computer-science member; "Bio" = a biomedical member. Minimum version first.

| Id | What | Files it would touch | Hours | Who | Criterion | Depends on |
|---|---|---|---|---|---|---|
| C1 | Two new profiles (`bakery-cafe`, `school-kitchen`), 3 tokens each, as starting points of the kitchen page | new `src/tta/policy/profiles/*.yaml`; `src/tta/api/demo_tokens.yaml`; `src/tta/api/sandbox.py:64`; tests | 0.5 | Bio | 20% controls | — |
| C2 | Pattern file for the 4 customers, its contract, loader and the catalog test of 5.3 | new `src/tta/customers/` and `data/*.yaml`; new `src/tta/contracts/customer.py`; new `tests/customers/` | 1.0 | Bio writes the data, CS the loader | 15% openness; base for 20% match | C1 |
| C3 | Standing orders and 8 synthetic weeks for every customer, loaded at start-up | `src/tta/standing/demo.py`; `src/tta/ui/standing_page.py`; `standing.html`; `tests/standing/` | 0.5 | CS | 20% controls (P-08 per customer) | C2 |
| C4 | Usual product for a line that names only a type; note on the offer; default preference | new `src/tta/customers/apply.py`; `src/tta/api/service.py:170`; `src/tta/offers/wording.py`; tests | 2.0 | CS | 20% match | C2; P9a |
| C5 | "The usual milk": quantity suggested from the median, always to confirm | `src/tta/agent/rules_reader.py`; `src/tta/agent/parser.py`; `src/tta/contracts/request.py`; tests | 1.5 | CS | 20% match, 20% controls | C4; P8 |
| C6 | Reorder suggestions (order due, or stock on hand low) as offers to confirm | new `src/tta/customers/suggest.py`; `src/tta/api/standing_routes.py`; `src/tta/ui/` | 1.5 | CS | 30% demo, 20% controls | C3; P8 |
| C7 | Customer switcher and "who this is" card with the synthetic tag | `src/tta/ui/examples.py:24-25`; `index.html`; `kitchen.html` | 1.0 | Bio | 30% demo | C1, C2; P3 |
| C8 | Second recording (177 ids, 2 live calls) and replay over two folders | run `scripts/capture_valio.py`; new `fixtures/valio/<name>/`; `src/tta/valio/replay.py`; `src/tta/config.py` | 1.5 | CS | 15% exceptions, 30% demo | team approval; P5 |
| C9 | Assumptions: customers, history, sources | `docs/ASSUMPTIONS.md`; `/assumptions` | 0.5 | Bio | 15% openness | C2 |

Minimum = C1 + C2 + C3 = 2 h. Full = 10 h. Cut first: C8, then C6, C5, C7.

## 10. What changes in the demo
Measured today; "after" lines are expected, not measured.
- **Hotel, "100 L milk".** Today: 100 × `463047` whole milk low lactose, €2.01 each, AUTO. After C4: 100 × `469363`, the milk this kitchen renews every week (€2.48 each, 384 confirmed), with "from this buyer's usual products (synthetic)" and the cheaper milk shown as the alternative.
- **"The usual milk for Monday".** Today: 503. After C5: a suggestion of 100 L of `469363`, "the median of the last 8 weeks", waiting for the user.
- **Bakery, 60 L of whipping cream `469346`.** Today, under the only profile that can run it: the agent may order alone 48 × `469346` + 12 × `463975`, a 15% vegetable-fat cooking blend. After C1: the same option goes to the owner (P-05, substitutes NONE). With P10's rule the blend is named as a formula change.
- **Standing-orders page.** Today: one order, one customer, loaded by a button. After C3: one or two per customer, each with 8 tagged weeks; the school's 51-unit milk shows drift and partial availability in one renewal.
- **A sentence for the pitch:** "Order history, order templates and favourites already exist in Valio Aimo's webshop. The agent reads the same pattern, and says when a value came from it."

## 11. Risks and what not to do
- Do not put pattern data in the profile files: the loader rejects unknown settings (`policy/profiles.py:42-48`) and the policy hash would change every week.
- Do not let a pattern decide a quantity that is then ordered alone. SPEC says a quantity is never guessed; V8 says the user confirms.
- Do not present synthetic customers as Valio's data, and do not name real organisations.
- Do not rename `hotel-kitchen` or `allergy-ward` (97 test files).
- Choose weekly quantities against the capture's stock on purpose: bakery 40 L of `469346` fits 48 confirmed; school 120 L of `462775` does not fit 51, by design.
- Avoid usual products with very large "confirmed" amounts. `464320` Oatly iKaffe reads as CONFIRMED with 39,243 units, because the placeholder threshold is exactly 999,999 (`src/tta/contracts/availability.py:24`), while B2 says a huge number means unknown. Someone owning B2 should look at it.
- A re-recording (option B) moves the clock and may move figures; decide with P5.
- The web facts in 4.1 marked "search summaries only" are leads. Do not put them on a slide unchecked.

## 12. Questions
**For the team**
- DECISION 1: build hotel, ward, bakery-café and school kitchen; document lunch restaurant and catering?
- DECISION 2: data written once with a model and committed (recommended), or a seeded script?
- DECISION 3: capture option A, B or C? B and C need the team's approval for 2 live calls.
- DECISION 4: a product or quantity taken from a pattern always needs the user's confirmation, whatever a later automatic-order setting says? (Recommended: yes.)
- DECISION 5: which reading of V2 did the mentor mean, (a) the agent acts on each user's pattern, or (b) each user type shows the scenarios? The plan covers both; the pitch should say the right one.

**For Valio (booth shape)**
- Context: your mock has no customer model, and the customer number does not change its answers. You told us to generate customer data.
- What we did: four synthetic customers (hotel kitchen, hospital ward, school kitchen, bakery-café), each with usual products, 8 weeks of weekly orders and a standing order, all labelled synthetic.
- What we got: the hotel that asks for "milk" now gets the lactose-free milk it orders every week, `469363`, instead of the cheapest milk, `463047`.
- Example: "the usual milk for Monday" becomes a suggestion of 100 L of `469363`, which the user confirms.
- The ask: is this what "per user, based on the user pattern" means? And are these four the customer types you most want to see?
- If nobody answers: we build these four, with weekly orders and 8 weeks of history.
