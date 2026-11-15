# Use cases — how well the gateway serves them

Checked on Saturday 14 Nov 2026, 10:00–11:00, against the six "example scenarios to spark ideas" in Valio Aimo's brief (`AIMO/CHALLENGE.md`) and our own acceptance scenarios (SPEC §13).

**Which code.** The code checked is commit `84d9407` (branch `overnight-build`), the latest commit. The isolated worktree was created from `main`, which holds no code, so that commit was exported with `git archive` into a scratch folder and run there. Nothing in the repository was changed except this file. Changes other agents made to the main tree after `84d9407` are not covered.

**How.** Everything ran in replay mode with capture `2026-11-14-demo` (clock pinned to Sat 14 Nov 02:52, 769 products), no Gemini key and no supplier calls. Each use case had its own server and an empty database. One sub-agent per use case ran the requests. The claims that carry the verdicts were then run again by hand; those are marked **(re-checked)**. Each figure says whether it covers the whole catalog (17,546 products) or the capture only.

The six brief scenarios are optional: the brief calls them ideas, not requirements. On Saturday morning the team had cut recipe → order, proactive selling and standing-order drift on purpose (`AIMO/PLAN.md:106`); all three were built later that day, in part or in full. A "not at all" in the Saturday sections is a fact about scope at that commit.

---

## What holds now (Sunday 15 Nov 2026, about 03:00)

Everything below this section is the check of Saturday morning against commit `84d9407`, kept as it was written: it is the record of what was missing then and why the day's work was chosen. Much of it has since been built. This section says what is true of the code now (commit `94b21a5`, with one lane's uncommitted change to substitute ranking), from the independent check of the six scenarios on Sunday at 00:52 (`AIMO/build/replan/REVIEW.md`, section CK3, on commit `016cc08`), the fixes that followed, and runs through `/shop/api/*` in replay on Sunday between 02:26 and 02:29. Figures are from the recordings (1,163 products: 769 and 394 baking products), never the whole catalog of 17,546. The item-by-item account with the proof for each is `AIMO/COVERAGE.md`; the figures of the demo at both clocks are `docs/DEMO.md`.

| # | Use case | Verdict on Saturday morning | Verdict now | What changed, and the next step (which does not exist today) |
|---|---|---|---|---|
| 1 | Need → recipe → order | Partly | **Partly** | Built: ten illustrative recipes of ours, a menu planner (`POST /v1/menus/plan`, MCP `plan_menu`, the shop's request box), the kitchen's stock taken off (beef stew for 80 with 10 kg in stock: 4.4 kg to order), one offer and one order for a person. A sentence that names a dish is planned ("A chocolate cake for 20 by Monday": 7 lines; 4 from confirmed stock, €15.19; all 7 for €23.44 with five quantities not confirmed; measured at 02:26 and still moving); one that names an ingredient gets the dishes that use it. Coverage is said per line ("4 of the 7 ingredients are covered in full …"). **Next step: recipes chosen around a seasonal ingredient.** Today there is no notion of season |
| 2 | Last-minute event | Partly | **Partly** | Built: a stand-in by its role in the dish, always for a person (F-09); and since Sunday a date that cannot be met is answered with the earliest date as a labelled alternative that a person accepts ("delivered Monday 16 Nov, 3 days later than asked", F-07). Still true: no request for "tomorrow" can be filled from the recording; the role alternatives are a fixed list per recipe, written by us |
| 3 | Supplier stock-out | Partly | **Partly** | Built: substitutes ranked by kind, use and formula (ingredient lists and six nutrients), the trade-off in numbers on the page and in the rule's sentence the person reads, and every substitute not judged replaceable goes to a person (F-12). **Next step: a check that runs before the kitchen asks.** Today nothing runs without a request, and a stock-out while an order waits for approval still ends in a refusal with no fresh offer |
| 4 | Proactive selling agent | Not at all | **Partly** | Built: Valio Aimo's own suggestion of a related product on the offer, with its benefit in euros ("€1.48 a litre instead of €2.88 … €42.00 less", at the bakery), never added unless accepted; Valio Aimo's back office counts what was shown and accepted. It stays silent when it has nothing fit: on the hotel's 100 L of lactose-free milk none is shown. **Next step: new and seasonal products marked in the data** (it has no such mark today); nothing is pushed before the buyer asks |
| 5 | Allergen-safe substitution | Partly | **Works for allergens; partly for nutrition** | The four gaps of Saturday are closed: nutrition values and ingredient lists are compared; the substitute list is judged by the buyer's own rule; the almond drink `465793` goes to the dietitian with the manufacturer's page beside it; and at the ward and the school a substitute whose formula differs or that is not like for like is the dietitian's to decide. The check of Sunday could not get an unsafe product past the rules. **Next step: a nutrition standard for schools and hospitals** (none is encoded today). There is no urgency field, so pressure relaxes nothing |
| 6 | Standing-order drift | Not at all | **Works** | Built: standing orders, their history, a renewal judged against the median of the last 6 renewals (P-08), a trend prompt. On `/shop` the hotel's renewal at 290 L is €719.20 and goes to a person: "290 L this week against a median of 100 L over the last 6 renewals, more than the 25% tolerance". **Next step: a scheduler**; today a renewal is asked for by a person or an agent. The shipped histories are synthetic and say so; fixed prices never trigger the price side |
| 7 | Our own scenarios | All hold | **Re-measured** | The brief's sentence now has three options (435 L confirmed €1,083.39; 1,000 × `464306` €1,010.00 with the quantity not confirmed; all 1,000 L from confirmed stock with 565 × `463380`, milk made for coffee, as a named substitute, €2,580.64). No order is placed without a person in the four shipped profiles; ordering alone is a buyer's setting, shown on `/shop` (hotel: 302 L, €748.96, by the agent; 303 L, €751.44, to a person) |

**Of the cross-cutting findings below:** 1 is fixed (a product outside the recordings reads `NOT_IN_RECORDING`, never Valio's statement); 2 is fixed for the menu's sentences (coverage is said per item; the log's "covering 0%" wording for a menu was still reported on Sunday); 3 is fixed (kind, use and formula are read); 4 is fixed on the shop page; 5 is changed: a product-type line gets a substitute in one case, when its confirmed stock falls short and confirmed stock of the nearest kind can complete it, as a last option for a person.

**Assumptions, in one place** (what in the demo is ours and says so): the data is a recording read at a clock we chose · the customers and their histories are synthetic · the limit values are illustrative · the signature is the gateway's, with a demo key · the demo pages have no login (an agent cannot approve over REST and MCP; whoever opens `/shop` acts as the customer's person) · the order step is ours by design, because the mock has no order endpoint.

**Next steps, in one place** (what a pilot would add; none exists today, and `AIMO/COVERAGE.md` says for each what it would stand on): Valio Aimo signing its own statements · people signing in with their own accounts · an order message Valio Aimo's systems can take · stored orders tied to their audit entries (today an order edited in the database still gets a valid proof) · a nutrition standard for schools and hospitals · new and seasonal products marked in the data · recipes around a seasonal ingredient · a scheduler for standing orders and a check that runs before the kitchen asks · an origin filter · Finnish · a demo agent that orders alone over REST and MCP (today it is shown on the page). A substitute dearer than 25% above the product asked for already goes to a person (rule P-05, commit `fd4098b`).

**People, now:** one person confirms. Hanna Laine at the hotel and Marko Heikkinen at the bakery hold every role; at the ward Jussi Nieminen orders and the dietitian Sari Lehto is the only second person, at the school Päivi Korhonen and the dietitian Riikka Mäkelä. The approver names and the three-signer flow in the sections below are Saturday morning's.

---

## Summary of the check of Saturday morning (commit `84d9407`; the section above wins where they differ)

| # | Use case | Verdict | Evidence in one line | Smallest change and cost | Criterion |
|---|---|---|---|---|---|
| 1 | Need → recipe → order | **Partly** | Several ingredients go into one offer, one order and one approval. 15 kg beef chuck + 10 L cream + 20 L milk → €319.20, P-06; Hanna approves; ORDERED; 9 audit events **(re-checked)**. There is no seasonal marker, no recipe and no kitchen stock | A fourth page example that sends a multi-line "menu" request built from captured ingredients, and keep vegetable-fat blends out of `cream`: about 2 h. A full recipe planner is 6–8 h and not advised | 30% demo, 20% match |
| 2 | Last-minute event | **Partly** | "Tomorrow" is read and checked, and each line says why it cannot arrive in time (5 lines, 159 exclusions, each with a reason). There is no recipe logic; substitutes are a product swap. In replay nothing can arrive tomorrow: all 603 delivery dates in the capture are Mon 16 Nov **(re-checked)** | When every product is late, a note naming the earliest date Valio states: about 1 h. Substitutes that respect an ingredient's role: 3–5 h | 15% delivery constraints, 20% match |
| 3 | Supplier stock-out | **Partly** | An out-of-stock product asked for by id gets a ranked substitute and a sentence on what is given up: `469316` → 11 × `460394`, €152.68 **(re-checked)**. A stock-out between offer and order gives 409 and a fresh offer. Nothing runs proactively, and a stock-out while an order waits for approval is a dead end: 409 and no fresh offer **(re-checked in code)** | A fresh offer when the approval re-check fails: 2–3 h. Show the trade-off on the approval card: 1–2 h | 15% robustness, 20% controls |
| 4 | Proactive selling agent | **Not at all** | The supplier token reads its own audit view and nothing else (403 everywhere else). No field marks a product as new or seasonal; 13 catalog names say "seasonal". Valio has no channel to the buyer's agent | Do not build it. Add one line to the next steps: 0.1 h | 15% openness |
| 5 | Allergen-safe substitution | **Partly** | The allergen side is strict. Scenario 2 goes AUTO only with FREE_FROM milk and gluten, substitutes that add gluten are blocked, and every ward substitute goes to a human. Four gaps: no nutrition value is read anywhere **(re-checked)**; ward substitutes go to the purchasing manager, never the dietitian **(re-checked)**; the ward's substitute list says "passes · can be ordered" for oat drinks its own rule sends to a dietitian **(re-checked)**; an almond drink declared free from tree nuts is ordered alone under a nut exclusion **(re-checked)** | Judge the substitute list with the buyer's own rule: 0.5–1 h. Ward substitutes to the dietitian: 1 h, and a team decision. Claims a substitute must keep, set per profile: 1 h. A nutrition rule: 4–6 h | 20% controls, 20% match |
| 6 | Standing-order drift | **Not at all** | No standing order, no comparison with history, no renewal. `GET /v1/orders` lists past orders, and P-02 is a fixed same-day sum. Seven orders growing from 100 to 290 L all went through alone | A drift rule modelled on P-02: 3–5 h. Not advised before the deadline | 20% controls |
| 7 | Our own scenarios | **All hold** | S1, S2, S3, the backup, both guards and the 1,500 L partial fill hold on REST. S1–S3 hold on the pages and S2 over MCP **(S1, S2, S2-over-MCP and both guards re-checked)**. The numbers match DEMO.md, and the e2e tests give 16 passed | Doc wording only: about 0.5 h | 15% openness |

---

## Findings that cut across the use cases

These show up in several of the sections below and decide the ranking at the end.

1. **Replay states something false about products it never recorded (re-checked).**
   - A product outside the capture is excluded as `NOT_DELIVERABLE` with "Valio cannot currently deliver this product on any date." Nothing on the offer says the product is simply not in the recording.
   - The capture holds 769 of the 17,546 catalog products (category prefixes 104 and 18720, plus five ids), so most of the catalog is affected. Examples: all 20 butters, all chanterelles, the seasonal glögg `477051`.
   - This contradicts the docstring in `valio/replay.py` ("An id outside the capture reads as unknown") and our own rule that no data means unknown.
   - A judge who asks for anything other than milk or plant drinks sees it. That holds on the replay app and on the deployed app when it falls back to replay.
   - The demo scenarios are not affected: their NOT_DELIVERABLE products (1 in S1, 6 in S2) are all in the capture **(re-checked)**.
2. **Multi-line offers word coverage wrongly (re-checked).**
   - Request: 100 L lactose-free milk + 10 kg butter, needed Monday.
   - Option 1 reads "1 confirmed product covers the 2 request lines, the least covered at 0.0%", and P-03 reads "Only 0% of the requested quantity is covered".
   - In fact line 1 is covered in full and line 2 not at all. The ratio used is the lowest line's (`offers/options.py:137`, `policy/rules.yaml:314`).
3. **Substitutes are chosen by category and price, never by how the product is used.**
   - The ranking is: passes the allergen rule → keeps dietary claims → category distance → listed by Valio → pack size → confirmation → price (`offers/substitutes.py`).
   - Examples: a 35% whipping cream gets 15% cooking creams ranked above a 38% whipping cream; a barista oat drink gets a rice drink (#4 for the hotel, and the chosen substitute for the ward); beef tenderloin gets flank.
   - The nutrient data that could tell these apart (fat, protein, sugar per 100 g) is filled on 12,251 catalog products. The code never reads it **(re-checked: grep finds no hit in `src/tta`)**.
4. **The human who signs a substitute does not see the trade-off.**
   - `gives_up` appears on REST, on MCP and on the request page.
   - It does not appear on the approval card, the order page, the audit sentences, or what the Gemini agent is shown.
5. **Substitutes exist only for lines that name product ids** (`offers/planning.py:176`). A product-type line, which is what a recipe line would be, never gets one.

---

## 1. Need → recipe → order — partly

> "a chef plans next week's menu around a seasonal ingredient. The agent suggests recipes, works out what's missing from stock, and places the order."

| Part | Today | Evidence |
|---|---|---|
| Seasonal ingredient | No | No season field in the product schema or the API. 13 catalog names say "seasonal" (glögg, mousse and yoghurt flavours), and none is a fresh ingredient. `POST /v1/products/search {"name_terms":["seasonal"]}` → `total: 6`, with "6 in 6 other categories were left out" |
| Suggests recipes | No | There is no recipe code. The parser is told never to estimate a quantity (`agent/prompts.py`), and the quantity must appear in the text (`agent/parser.py`). This is by design: the model never decides a quantity (SPEC §1) |
| Missing from the kitchen's stock | No | No field holds the kitchen's stock. A line with `"on_hand":5` → 422 "a field this request does not have" |
| Missing from Valio's stock | Yes, per line | Coverage, a quantity check and notes for each line. Stock used by one line is not offered again to the next (`offers/planning.py:131-140`) |
| Places the order, several ingredients at once | Yes | **(re-checked)** `POST /v1/offers` with 3 lines (15 kg `beef_chuck`, 10 L `cream`, 20 L `milk`, needed Monday) → "3 confirmed products cover all 3 request lines in full, for €319.20 before tax. The total is a ceiling…", APPROVAL [P-06]. `POST /v1/orders` → PENDING_APPROVAL. Hanna's decision → "Ordered for €319.20 net with approval by Demo approver Hanna (purchasing manager): rule P-06 asked for a human and was accepted." Audit: 9 events, `chain.ok: true`. A request takes up to 20 lines. Over MCP, a 3-line `get_offer` then `place_order` → ORDERED by the agent |

**Gaps.**
- No season data, no recipes, no kitchen stock.
- **Ingredient precision (re-checked):** "10 L cream" picks `463975` "Arla Pro Ruoka 1 L 15% lactose free vegetable mix", a vegetable-fat blend.
- With several lines, the unconfirmed alternative swaps every line that has an unconfirmed product (`planning.py`). "Confirmed cream + confirmed milk + unconfirmed quark" is never offered.
- The 0% coverage wording (cross-cutting finding 2).
- The three page examples have one line each, so a multi-line request reaches the pages only through Gemini.

**Smallest change.**
- **Minimal, about 2 h:**
  - a fourth example in `src/tta/ui/examples.py`, sending a multi-line typed request built only from captured ingredients (beef chuck, cream, milk, quark);
  - `exclude_terms` for vegetable-fat blends under `cream` in `catalog/product_types.yaml`;
  - one e2e test.

  This covers part (d) only; the chef names the ingredient.
- **Fuller, 6–8 h plus a new capture:** an illustrative recipe table (servings × amount per serving − kitchen stock → typed request), `POST /v1/menus/plan` and a page form. Not advised before Sunday.
- **A pitch line that costs nothing:** recipes and kitchen stock belong to the buyer's agent; the gateway takes the multi-line request it produces, over REST or MCP. The MCP run above shows this working today.

---

## 2. Last-minute event — partly

> "an unexpected booking for tomorrow. The agent identifies what the recipes require, flags what can't be sourced in time, and proposes substitutions through recipe logic rather than a simple SKU swap."

| Part | Today | Evidence |
|---|---|---|
| A need date of tomorrow | Yes | `agent/days.py` reads "tomorrow" (and the Finnish "huomen…") from the data clock; in replay that is Sun 15 Nov. 100 L lactose-free milk with `needed_by 2026-11-15` → no option: "17 cutoff passed, 11 late for needed by, 1 portion pack, 1 not deliverable". A late product reads "Delivery is on Monday 16 Nov, later than the needed-by date Sunday 15 Nov." With `needed_by 2026-11-16` → €248.00, AUTO |
| What the recipes require | No | No recipe, dish, menu or servings concept anywhere in `src/tta`. "Portion" only means single-serve packs |
| Flags what can't be sourced in time | Yes, per line | 5 lines needed tomorrow (cream, lactose-free milk, quark, beef chuck, butter) → no option, one note per line, all 159 exclusions with a reason, recorded in the audit. The same 5 lines needed Monday → option 1 covers 3 lines; "Nothing is offered for request lines 3 and 5…" → APPROVAL [F-07, P-03, P-06] |
| Substitutes by recipe logic | No: product swap only | Cross-cutting finding 3. Substitutes are offered only for lines that name ids (finding 5) |

**Gaps.**
- When every product is late, the offer is empty. It never says "the earliest date Valio states is Mon 16 Nov", and it offers no later-delivery option that a human could accept.
- In replay, "tomorrow" can never be met: **all 603 delivery dates in the capture are 2026-11-16 (re-checked)**.
- Without a Gemini key, the free text "…for tomorrow" answers 503, and the page examples are fixed to Monday.
- Butter and most other event ingredients read "Valio cannot currently deliver…" in replay (finding 1).

**Smallest change.**
- **Earliest-date note, about 1 h:** in `offers/planning.py`, when a line's products drop out only for being late, add "the earliest delivery Valio states is Mon 16 Nov (11 products)".
- **Later-delivery option, 3–4 h:** offer the best option at the earliest date. F-07 already sends it to a human.
- **Role check on substitutes, 3–5 h:** load fat and ingredients and demote candidates that miss the role, for example "15% fat, cannot be whipped".

**Also seen, not re-checked:**
- `POST /v1/offers` accepts a needed-by date in the past (`2026-11-13`, HTTP 201), although the parser refuses one.
- SPEC §4 says `CUTOFF_PASSED` is excluded "for a dated request". The code excludes it for undated requests too.

---

## 3. Supplier stock-out — partly

> "a key product runs out mid-week. The agent proposes a recipe-compatible substitute before the kitchen notices the gap, and explains the trade-off."

| Part | Today | Evidence |
|---|---|---|
| Runs out at offer time | Yes | **(re-checked)** Hotel, `product_ids:["469316"]`, 30 L → excluded: "Out of stock: Valio shows 0 ST available." Option 1 is a substitute: 11 × `460394` Spice Up! Coconut milk 2900 ml, €152.68. What is given up: "the brand is Spice Up!, not Urtekram; Valio does not list it as a substitute; one sales unit holds 2.9 L, not 3 L." The capture holds 21 out-of-stock products |
| Runs out between offer and order | Yes | Simulated over a modified copy of the capture (`usecases/3/sim.py`): `475224` set to 0 after the scenario 3 offer → `POST /v1/orders` answers 409 `offer-stale` with a `fresh_offer_id`. The fresh offer's top option, 100 × `469512` for €208, was ordered |
| Runs out while waiting for approval | No | **(re-checked in code)** `place_order` builds a fresh offer when the offer is stale or expired (`api/service.py` `_fresh_offer`); `decide_approval` does not. In the simulation, Hanna's approval → 409 with no `fresh_offer_id`, and the order stays PENDING_APPROVAL. The audit sentence says "A fresh offer is needed.", but none is made |
| Before the kitchen notices | No | No scheduler, webhook or subscription, and no re-check without a request. The app's lifespan runs only the MCP session manager. `GET /v1/orders/{id}` never re-checks stock |
| Recipe-compatible substitute | Partly: by category | Finding 3. For the ward, `473609` → Alpro Rice drink |
| Explains the trade-off | Partly | `gives_up` names lost claims, brand, "not listed by Valio", category, pack, a higher price and unconfirmed stock. It never states a lower price or a change of product. Tenderloin → flank reads only "the brand is Well Beef…; Valio does not list it…" |

**Smallest change.**
- **Fresh offer on approval, 2–3 h:** reuse `_fresh_offer` in `decide_approval` and show it on the card.
- **Trade-off where the decision is made, 2–3 h:** show the trade-off on the approval card and the order page, and have `substitute_wording.py` state a change of product and a lower price.
- **Proactive re-check, at least 5–6 h:** `POST /v1/orders/{id}/recheck`, plus a demo-only switch that simulates a stock-out. Not advised.

---

## 4. Proactive selling agent — not at all

> "Valio Aimo's own agent spots a new or seasonal product and proactively suggests it to the buyer's agent."

| Part | Today | Evidence |
|---|---|---|
| A Valio-side agent | No | `demo-supplier-valio-aimo` gets 403 on every route except `GET /v1/audit`: "The supplier reads its view of the audit trail (GET /v1/audit) and nothing else". Over MCP it sees the 8 buyer tools, but only `get_audit` works. MCP has no resources or prompts, and `subscribe:false` |
| Spots new or seasonal | No field | Whole catalog, schema and data: no new, seasonal or launch field. The only date fields are `synkkaData.lastUpdated` (latest 2025-10-05) and `mediasLastUpdated`. 13 names say "seasonal"; the 12 names containing "new" are all brand names. 4 of the 13 are in the capture, and none can be ordered (2 not deliverable, 2 with the cut-off passed) |
| Suggests to the buyer's agent | No channel | The closest thing is `Offer.notes`, free text written by the gateway. There is no push, no webhook and no suggestion option kind |
| Controls | Nothing to control | The existing gates would hold: the supplier cannot create offers, and the agent may order only the top option. A risk for any future version: a suggestion modelled as a `SUBSTITUTE` would go through alone under the hotel's P-05 |

**Fit with the brief: weak.** The brief frames the problem as a wholesaler being "safely and openly readable by autonomous agents". The four "problems we'd love to see tackled" are all on the buyer's side.

**Recommendation:** do not build it; add one line to the next steps. A fuller version is 8–12 h: `POST /v1/suggestions` for the supplier, and a new fixed rule that sends anything the buyer did not ask for to a human.

---

## 5. Allergen-safe substitution under pressure — partly

> "in a school or hospital kitchen, a substitution must still satisfy strict allergen and nutrition rules."

| Part | Today | Evidence |
|---|---|---|
| Strict allergen rules on a substitute | Yes, with two holes (next two rows) | Ward, `product_ids:["473609"]` → 473609 is excluded as `ALLERGEN_NOT_STATED` (no statement about milk; oats need a dietitian). Substitute `473424` Alpro Rice drink, FREE_FROM AM and AW. Substitutes `471881` and `464320` → `SUBSTITUTE_ADDS_ALLERGEN` (AW). A sweep over the capture: all 646 ward substitutes passed both rules |
| Hole 1: the declaration is trusted against the product's own ingredients | — | **(re-checked)** Ward, `product_ids:["465793"]`, `exclude_allergens:["AN"]` → AUTO, €47.60, "Every product offered states that it is free from AN". 465793 is Alpro Barista Almond drink. Its `keyIngredients` say "Water, ALMOND (2.5%) … MAY CONTAIN REMAINS FROM NUTS", while its `nonAllergen` says AN FREE_FROM. Almond (`SA`) is in the AN family (`allergens/codes.py:89`). 2 such products in the whole catalog (465793, 461449) |
| Hole 2: losing a FREE_FROM passes | — | The substitution rule compares only CONTAINS and MAY_CONTAIN, so a substitute that drops a FREE_FROM statement of the original passes. This happened to 16 of the 80 ward-safe originals in the sweep. It does not affect the ward's own AM and AW |
| Nutrition rules | No | **(re-checked)** No nutrient field is read anywhere in `src/tta`, although `nutritionalContent` is filled on 12,251 catalog products. Examples: a no-added-sugar drink (0.0 g) → a 2.5 g substitute, losing `LOW_SODIUM_SALT` and `NO_ADDED_SUGARS` with only P-05 firing; coconut milk at 18 g fat → rice drink at 1 g. F-08 counts only 8 dietary claims. A `required_claims` in the request is honoured for substitutes |
| Under pressure: to a human, who can approve | Yes, but the wrong role | Ward substitutes → PENDING_APPROVAL by P-05; the ward's purchasing manager approves → ORDERED. The dietitian, finance and the agent get 403, the hotel approver 404. **(re-checked)** P-05's `approver_role` is `purchasing_manager`. P-04 (dietitian) cannot fire for the ward: its confirmed-only setting first excludes every product the allergen rule would send to a dietitian. So sentences say "a dietitian must decide", but no dietitian is ever asked |
| The substitute list says something the ward's offer does not | — | **(re-checked)** `POST /v1/products/473609/substitutes` as the ward: `475224` has "passes: true, orderable: true", while its own allergens claim reads "The product data does not confirm that it is free from an excluded allergen (AM, AW)". The ward's offer for 475224 excludes it as `ALLERGEN_NOT_STATED`. Here "passes" only means "adds no allergen compared with the original" |
| A claim is not an allergen statement; no data means unknown | Yes | The ward asking for lactose-free milk → 0 options, 30 × `ALLERGEN_DECLARED` "contains milk (AM)". Products named "gluten free" that declare AW fail. Under STRICT, X99 goes to a human |
| School kitchen | No profile | Only `hotel-kitchen` and `allergy-ward` exist. A school profile is data only: one YAML file plus tokens |

**Smallest change: the minimal set is about 3.5–4 h.**
- Judge the substitute list with the buyer's own allergen rule under confirmed-only, saying "needs a dietitian" where that applies (`offers/substitutes.py`): 0.5–1 h.
- Send ward substitutes to the dietitian, through a profile setting for P-05's role: 1 h. This is a team decision, since ASSUMPTIONS chose the purchasing manager.
- A per-profile list of claims a substitute must keep, feeding F-08: 1 h.
- The allergen findings and "gives up" on the approval card: 1 h.

**Fuller options:**
- A nutrition rule: load `nutritionalContent`, and send a substitute that changes a nutrient beyond the profile's tolerance to the dietitian: 4–6 h.
- A check for conflicts between the ingredients or name and the declaration: 1.5–2 h.
- The almond drink is also worth a booth question: 0.25 h.

---

## 6. Standing-order drift detection — not at all

> "the agent learns a kitchen's recurring weekly order and flags anomalies (portion counts creeping up, cost drifting) before auto-renewing it."

| Part | Today | Evidence |
|---|---|---|
| A standing order | No | 16 OpenAPI paths and 8 MCP tools, none for this. The store has 5 tables: offers, orders, approvals, idempotency keys, audit events |
| Learns from history | Partly: stored, not read | `GET /v1/orders` returned all 8 orders placed, newest first, with quantity, total and `created_at` (at most 100, no filters). `GET /v1/offers/{id}` keeps the typed request. MCP has no tool to list orders. In replay every `created_at` is 02:52:45 |
| Flags quantity or cost drift | No | P-02 sums today's orders against a fixed €3,000. Test on `469363`: quantities 100 → 110 → 120 → 140 → 180 → 250 → 290 L were all AUTO with no rule fired. The eighth order, back to 100 L, was held by P-02. So the normal order was flagged and the creep was not, and only because the pinned clock puts every "week" on the same day |
| Auto-renews after a check | No | There is no scheduler. Ordering the same offer again → 422 "already has an order". An agent can renew by hand (post the stored request again, then order), and every fixed and profile rule applies, but no rule compares the order with history |

**Smallest change.**
- A rule P-08, quantity or unit price against the median of the last N orders → APPROVAL, wired exactly like P-02's day spend (the `orders/spend.py` pattern, `PolicyContext`, `policy/facts.py`): 3–5 h.
- A standing-order resource with a renew call: 10–14 h.

Neither is advised before the deadline.

**Wording slips, 0.1 h:** SPEC.md:105 says `product_ids` covers "a standing order", and the OpenAPI example note for `decide_approval` reads "Checked against the standing order." (`api/examples.py:49`). Neither feature exists.

---

## 7. Our own scenarios — all hold

The server ran in replay on empty books. "Re-checked" marks what was run a second time, by hand, on a separate server. The pages column comes from the sub-agent's saved page text (`usecases/7/pages/`); the e2e count comes from its log.

| Scenario or guard | Surface | Holds | Numbers seen (all match DEMO.md) |
|---|---|---|---|
| S1 hotel, 1,000 L lactose-free milk by Monday | REST, typed **(re-checked)** | Yes | opt_1 384 × 469363 + 51 × 462775 + 565 × 463380 = **€2,580.64**, APPROVAL [P-01]. opt_2 1,000 × 464306 = **€1,010.00**, [F-01, P-01]. **19 excluded**: 17 CUTOFF_PASSED, 1 PORTION_PACK (463203), 1 NOT_DELIVERABLE. An agent token on the decision route → 403 |
| S1 | REST, pasted sentence | Yes | `/v1/requests/parse` headers: `TTA-Read-By: gemini-3.6-flash`, `TTA-Reading-Source: recording`. `/v1/agent/run`: get_authority → create_offer → place_order → PENDING_APPROVAL. After Hanna approves: ORDERED, **9 events**, chain ok. The run is `model: "hand-built"`, as DEMO.md says |
| S1 | Pages (example button and paste) | Yes | Summary strip: "3 confirmed products cover the 1,000 L asked for, for €2,580.64…", "? Sent for approval". Hanna's card → "✓ Ordered with human approval", 9 events. The supplier tab shows no Hanna, no €750 and no note |
| S2 ward, 200 L milk substitute, no milk, no gluten, confirmed only | REST, typed **(re-checked)** | Yes | 200 × 464013 = **€402.00**, AUTO, no rule fired. **41 excluded**: 18 ALLERGEN_DECLARED, 12 CUTOFF_PASSED, 6 NOT_DELIVERABLE, 5 ALLERGEN_NOT_STATED. Order → ORDERED, placed by AGENT: "The agent placed this order alone for €402.00 net: no rule of profile allergy-ward asked for a human." |
| S2 | REST, pasted sentence | Yes | Reading from the recording, run `model: "recorded"`, ORDERED by the agent for €402.00 |
| S2 | Pages | Yes | "✓ Ordered by the agent", the same counts, "Run from a recording of the model's earlier answers" |
| S2 | MCP **(re-checked)** | Yes | `initialize` and `tools/list` (8 tools). `get_offer` → 200 × 464013, €402.00, AUTO, 41 excluded with the same split. `place_order` → ORDERED, placed by AGENT. Without a token → 401; GET → 405 |
| S3 substitutes of 473609 | REST | Yes | 471690 passes the allergen rule but cannot be ordered (cut-off passed). 464320 and 471881 → SUBSTITUTE_ADDS_ALLERGEN (AW, contains) and cannot be ordered. Offer: opt_1 100 × 475224 = **€174.00**, AUTO; opt_2 473609, €137.00 [F-01] |
| S3 | Pages | Yes | Ranks 1, 12 and 13 as in DEMO.md; 468465 "? Can be ordered, needs approval"; "✓ Ordered by the agent" |
| Backup, 30 kg beef chuck | REST | Yes | 30 × 466988 = **€506.40**, a ceiling, APPROVAL [P-06]. 31 kg → 33 kg, **€557.04**. After S1 and S3 on the same book: [P-02, P-06], €3,261.04, "purchasing manager and finance" |
| Guard A: agent token on an approval | REST **(re-checked)** | Yes | 403 `application/problem+json`, type `…/not-authorised`: "An agent cannot approve or reject an order (F-06)…". `authorisation.refused` is in the audit |
| Guard B: the same Idempotency-Key twice | REST **(re-checked)**, pages, MCP | Yes | The second answer is the first order (`ord_1a1cc532801d` both times). A new key on the same offer → 422 "already has an order" |
| Partial fill, 1,500 L | REST | Yes, on an empty book | 384 + 51 + 698 = **1,133 L**, **€2,933.09**, fill 0.7553, quantity NOT_MET, [P-01, P-03]. opt_2 1,500 × 464306 = €1,515.00 |
| e2e tests | pytest | 16 passed, 0 failed | backup 3, demo script 2, guards 2, S1 4, S2 3, S3 2 |

**Notes. None of these fails a scenario.**
- WALKTHROUGH Step 1 says `fixtures/agent/` "holds Gemini's own answers for scenarios 1 and 2". That is true of the readings only: the S1 run is hand-built. DEMO.md and the page both say so correctly.
- The order shows 02:52:45 (the pinned clock), while the audit events carry real time (WALKTHROUGH decision 7). The order page does not explain this next to the trail.
- The 1,500 L verdict is [P-01, P-03] only on an empty book; after the backup order, P-02 fires as well. DEMO.md's "Extra moments" does not say so.
- SPEC §13 row 3 says "471690 passes". It passes the allergen rule but cannot be ordered tonight. DEMO.md explains this; SPEC does not.
- Not reproduced, because live calls were not allowed: DEMO.md's live check at 08:12, and the behaviour with a Gemini key set.

---

## Other places where the code and our docs disagree

| Doc says | Code does | Checked by |
|---|---|---|
| `valio/replay.py`: "An id outside the capture reads as unknown" | `NOT_DELIVERABLE`, with "Valio cannot currently deliver this product on any date" | Re-checked |
| `/v1/authority` (ward), F-08: "a substitute that lacks a nutritional claim … always to a human" | Only 8 dietary claims count; losing `LOW_SODIUM_SALT` fires nothing but P-05 | Sub-agent |
| WALKTHROUGH §4: P-04 for the ward → dietitian | P-04 never fires for the ward: confirmed-only excludes those products first | Re-checked (rules); sub-agent (sweep) |
| WALKTHROUGH decision 3 and ASSUMPTIONS: the dietary-claims list was chosen so that a rice drink would not stand in for a barista oat drink | It still does: it is the ward's substitute for 473609, and #4 for the hotel | Re-checked (rank 2 in the ward's list) |
| Audit sentence on an approval-time refusal: "A fresh offer is needed." | No fresh offer is built on that path | Re-checked (code) |
| SPEC §5: each substitute "says in one sentence what the buyer gives up" | A lower price and a change of product are never stated | Sub-agent |

---

## Changes worth making before Sunday 10:00, by score gained per hour

This ranking is a judgement: the hours are estimates, and score gained cannot be measured. It puts first what a judge is likely to meet in the first minutes of pointing an agent at the gateway.

| Rank | Change | Hours | Criterion | Why |
|---|---|---|---|---|
| 1 | **Replay: a product outside the capture reads "not in the recorded copy of Valio's data", never "Valio cannot deliver".** Where: `valio/replay.py`, the reason codes and their wording | 1–2 | 15% openness and the trust protocol; protects the 30% demo | It puts a false statement in Valio's name for most of the catalog, against our own rule that no data means unknown. Any judge who asks for butter, cheese or eggs on the replay or fallback app sees it. Tonight's demo numbers do not change (re-checked) |
| 2 | **One pass over the doc wording**: WALKTHROUGH Step 1 (the S1 run is hand-built), SPEC §13 row 3, "on an empty book" in DEMO.md for 1,500 L, SPEC.md:105 and the OpenAPI note on "standing order", the `/v1/authority` F-08 sentence, WALKTHROUGH §4 (P-04 for the ward), SPEC §4 (cut-off on undated requests), and one line on the order page about the two clocks | 0.5–1 | 15% openness | Judges who read `/docs` and the walkthrough meet claims the code does not back |
| 3 | **Coverage per line in multi-line offers** ("3 of 5 lines covered; lines 3 and 5 missing"), in the option summary and the P-03 sentence (`offers/options.py:137`, `rules.yaml:314`) | ~1 | 20% match, 20% controls | A judge's first request with several ingredients shows "covered at 0.0%" for an option that covers a line in full, and the approver reads "only 0%" |
| 4 | **Judge the substitute list with the buyer's own allergen rule**, so the ward never reads "✓ passes · can be ordered" for a product its own offer sends to a dietitian (`offers/substitutes.py`) | 0.5–1 | 20% controls | It contradicts the allergen story exactly where a Valio judge would look: scenario 3 asked as the ward |
| 5 | **A note with the earliest date** when every product of a line arrives after the needed-by date (`offers/planning.py`) | ~1 | 15% delivery constraints | It turns "nothing in time" into "earliest Mon 16 Nov", the answer the last-minute-event scenario needs |
| 6 | **The trade-off and the allergen basis on the approval card** (`ui/approvals_page.py` and its template) | 1–2 | 20% controls | The human who signs a substitute sees what is given up; today only the request page shows it |
| 7 | **A booth question on 465793**, the almond drink declared free from tree nuts. Optionally, a check that sends a conflict between the ingredients or name and the declaration to the dietitian | 0.25 (question) or 1.5–2 (check) | 20% controls, the trust protocol | A strong, concrete example for the trust-protocol pitch. It affects 2 catalog products |
| 8 | **A page example with several ingredients**, built from captured ingredients, plus keeping vegetable-fat blends out of `cream`. Do it after rank 3 | ~2 | 30% demo, 20% match | It answers the ordering half of scenarios 1 and 2, and backs the pitch line "recipes belong to the buyer's agent; the gateway takes its multi-line request" |
| 9 | **Ward substitutes to the dietitian** (P-05's role set by the profile) | ~1 | 20% controls | It fits "allergen-safe substitution" better, but ASSUMPTIONS chose the purchasing manager, so decide first |
| 10 | **A fresh offer when an approval's re-check fails** (`api/service.py` `decide_approval`) | 2–3 | 15% robustness | It fixes a real dead end, but the case cannot appear in a replay demo, where stock never moves |

**Not before the deadline:**
- a recipe planner (6–8 h);
- a drift rule (3–5 h), or standing orders (10–14 h);
- proactive re-checks or notifications (at least 5–6 h);
- a nutrition rule (4–6 h);
- a seller-side agent (8–12 h).

For each of these, one line under the next steps on `/assumptions` scores on 15% openness instead.

Ranks 1 to 6 together take about 5–8 h. Ranks 1, 3 and 4 touch code that the e2e tests cover, so run the suite after each.

---

The evidence files (requests, answers, page text, scripts) are under `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/usecases/<n>/`: `0/` holds the re-checks, and `1/` to `7/` hold the use cases. The scratchpad is not kept after this session.
