# Demo script

Seven scenarios, each one sentence a person types or one button. Every figure below was measured by running the gateway offline in replay on Sat 14 Nov 2026, last at 22:08 at code commit `e53519c` (tests: `tests/e2e/`, one file per scenario, each at both clocks). No outside service is called and no model is called.

**Quoted sentences are as measured at 21:37; products, quantities, totals and rule ids were measured again at 22:08 and had not moved.** Other lanes were still rewording the rules' and the suggestions' sentences after that (for example P-04 now reads "… says nothing about milk, which is excluded for Harbourside Hotel: Valio Aimo's data does not rule it out."). Products, quantities, totals, rule ids and who must confirm are what the tests pin; re-read the quoted words from the running app before recording.

**Where a figure comes from.** The recording `fixtures/valio/2026-11-14-demo`: price and availability of 769 products, recorded Saturday 14 Nov 2026 at 02:52 Helsinki time. Replay also answers for the 394 baking products of `2026-11-14-baking` (same Saturday, 21:12), 1,163 products in all; only scenario 7 uses the second recording. A figure here is a fact about these recordings, never about the catalog of 17,546 products.

**The clock.** The demo is shown at the **demo clock, Thursday 12 Nov 2026 14:15 Helsinki time** (`TTA_DEMO_CLOCK`, replay only). We chose it: Valio Aimo said on 14 Nov that its test data is static. Every page says which clock is in force, and the log keeps the real time. Without the setting the clock is the recording's own instant (Saturday 02:52). "By Monday" is Monday 16 Nov at both. Where the two clocks give different answers, the scenario says so.

## Before you start

```sh
rm -f var/demo.sqlite3
GEMINI_API_KEY= TTA_ENV=demo TTA_MODE=replay TTA_DEMO_CLOCK=2026-11-12T14:15:00+02:00 \
  TTA_DB_PATH=var/demo.sqlite3 .venv/bin/python -m uvicorn --factory tta.api:create_app --port 8000
```

- `http://127.0.0.1:8000/` is the first page: the examples below as buttons, in this order, each with its customer. `/shop` is the shop page, `/standing-orders` and `/menu` are used in scenarios 5 and 7, `/docs` is the interface.
- **Start from an empty order book and run each scenario once, in order.** In replay the day never ends, so the day's spend only grows. One pass in order (scenarios 1 to 6 with the hotel's renewal at 290 L) puts €2,456.69 on the hotel's day at the demo clock, under its €3,000 a day, so rule P-02 never fires (`tests/e2e/test_demo_script.py`). A second pass in the same book would meet it: use "Start again" on the page, or delete the database file for REST and MCP.
- **Nothing is ordered without a person.** Ordering alone is a buyer's setting, off in all four shipped profiles (rule F-10). See "Ordering alone" under scenario 2.
- The limits, names and histories of the four customers are ours and illustrative: the Valio Aimo mock has no customer limits and no order history. The pages say so.

| Customer | Agent token | Who signs | Limits (illustrative) |
|---|---|---|---|
| Harbourside Hotel | `demo-agent-hotel-kitchen` | Hanna (purchasing manager), Mikko (finance), Leena (dietitian) | €750 per order, €3,000 per day, at least 90% of the quantity |
| City Hospital, Ward 4 | `demo-agent-allergy-ward` | Jussi, Anna, Sari | €500 per order, €1,500 per day, 100%; no milk (AM), no gluten (AW), strict; confirmed data only |
| Kilo School | `demo-agent-school-kitchen` | Päivi, Tuomas, Riikka | €250 per order, €800 per day, 100%; no tree nuts (AN), peanuts (AP), sesame (AS), strict |
| Kallio Bakery | `demo-agent-bakery-cafe` | Marko, the owner, holds every role | €300 per order, €1,000 per day, 100%; the formula matters; no substitute without a person |

## The demo set

| # | Customer | The sentence or the button | Brief's scenario | Criterion |
|---|---|---|---|---|
| 1 | Hotel | "1,000 litres of lactose-free milk by Monday" | the brief's own flow | 30% end to end · 15% partial availability · 20% log |
| 2 | Ward | "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only" | allergen-safe ordering | 20% controls · 20% match |
| 3 | Hotel | "100 litres of Oddlygood Barista oat drink, product 473609, by Monday" | supplier stock-out | 15% exceptions |
| 4 | Hotel, then School | "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk, strict rule", then "20 litres of almond drink by Monday" | allergen-safe substitution under pressure | 20% controls · 15% exceptions |
| 5 | Hotel | "100 litres of lactose-free milk by Monday", then the button "Renew" at 290 L on `/standing-orders` | proactive selling agent · standing order drift detection | 20% match · 20% controls |
| 6 | Bakery | "40 kg of Valio crème fraîche, product 477055, by Monday, for baking", then "100 litres of whipping cream by Monday, for cakes" | substitution where the formula matters | 20% match · 15% exceptions |
| 7 | Bakery | `/menu`: "I want to make a chocolate cake for 20 people" | need → recipe → order | 30% end to end |

Reserve: "100 litres of oat drink by Monday, most reliable delivery" (hotel).

Each sentence is read by the gateway exactly as the typed request its button carries (`tests/e2e/test_page_examples.py`, both clocks). With no model key, the sentences of scenarios 1 and 2 are answered from a recording in `fixtures/agent/`, labelled as a recording; every other sentence is read by the fixed rules, and the answer says so.

---

## 1. The brief's own sentence: Harbourside Hotel

**Type:** `1,000 litres of lactose-free milk by Monday`. The brief's full sentence, "I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability.", is read as the same typed request.

**First five seconds**
- **Asked:** 1,000 L of milk with the claim lactose-free, needed by Monday 16 Nov.
- **Suggested:** confirmed stock covers **435 L of the 1,000 L** (43.5%): 384 × `469363` + 51 × `462775`, **€1,083.39** before tax; 565 L are missing.
- **Alternative: quantity not confirmed:** 1,000 × `464306`, **€1,010.00**. Valio Aimo does not confirm its stock, so it is never the suggestion.
- **Said in the headline:** "Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk."
- **Needs a person:** the purchasing manager, for both options.

**Rules, in their words**
- P-01: "The total of €1,083.39 before tax is above the €750 limit per order of Harbourside Hotel."
- P-03: "Only 43.5% of the requested quantity is covered, below the 90% minimum (covered: 435 of 1,000 L)."
- F-01 (alternative): "The quantity of 1,000 × Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free (464306) is not confirmed by Valio Aimo."

**Then:** Order → "Waiting for approval by the purchasing manager, to be decided by Sunday 15 November 2026 at 17:00". The agent's own token on the decision route answers 403 and the attempt is logged. Hanna approves → "Ordered for €1,083.39 net with approval by Demo approver Hanna (purchasing manager): rules P-01 and P-03 asked for a human and were accepted."

**The log, two readers** (10 events, the chain verifies for both)
- The buyer reads the limit, the customer's name, who approved and the note.
- Valio Aimo reads the same 10 events: "P-01, a rule the buyer set (the order is above the spend limit per order; the amount is not shown)", "confirmed by the buyer's purchasing manager", and the products left out for a reason in its own data, by id. Never a limit amount, a name or a note.

**The two clocks:** options, totals and rules are identical. Left out with a reason: 2 of 26 candidates at the demo clock (1 portion pack, 1 that cannot be delivered); 17 at the recording's clock (15 more whose cut-off has passed).

## 2. Strict allergen rule: City Hospital, Ward 4

**Type:** `200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only`

**First five seconds**
- **Asked:** 200 L of a plant drink, milk (AM) and gluten (AW) excluded, confirmed data only.
- **Suggested:** 200 × `464013` Alpro No Sugars Soya, **€402.00**. Its data states "free from" for milk and for gluten, and every statement of the line is confirmed. One option only.
- **Left out, of 51 candidates:** 18 that declare the allergen, 11 that state nothing about it (5 at the recording's clock), the rest for delivery or cut-off.
- **Needs a person:** "Prepared: confirm to order." The purchasing manager confirms (rule F-10: "The agent prepares the order, a person confirms it.").

**Then:** Jussi confirms → "Confirmed by Demo approver Jussi (purchasing manager): ordered for €402.00 net." Valio Aimo's view of the request reads "200 litres of product type plant_drink, needed by Monday 16 November 2026, confirmed data only": the excluded allergens are not shown.

**Ordering alone** (20% criterion: what the agent decides alone). On `/shop`, Ward 4, switch "ordering alone" on in the settings. The same 200 L are then ordered by the agent: "The agent placed this order alone for €402.00 net: no rule asked for a human and every statement of the offer is confirmed." With the setting on and "confirmed data only" off, the option that holds a product with unconfirmed stock still waits for a person (F-01). Both are tested through the shop's routes at both clocks.

**The two clocks:** identical option, total and rule.

## 3. Supplier stock-out: Harbourside Hotel

**Type:** `100 litres of Oddlygood Barista oat drink, product 473609, by Monday`

**Shown at the demo clock, like the rest** (decision B16): one clock for the whole demo and for the public link, so what a judge clicks is what this page says. The recording's clock gives a different and stronger answer, below; both are tested.

**First five seconds (demo clock)**
- **Asked:** 100 L of `473609`, a gluten-free barista oat drink.
- **Nothing is suggested as confirmed.** Valio Aimo reports a placeholder for its stock. Two labelled alternatives:
  - "Alternative: quantity not confirmed": 100 × `473609`, **€137.00** (F-01).
  - "Alternative: quantity not confirmed": 10 cases of `471690`, the substitute Valio itself lists, **€155.50** (F-01). What it gives up: "fat 1.5 g, not 3 g", "one sales unit holds 10 L, not 1 L", "it costs €0.19 more per L", "its name adds “Delight”, which the data does not explain".
- **Refused:** the two other substitutes Valio lists, `471881` and `464320`, add gluten (AW, contains) to a gluten-free product: "It can never be ordered as a substitute."
- **Needs a person:** the purchasing manager, for either.

**Type next:** the same sentence with `; confirmed data only`. One option, the same at both clocks: 100 × `475224` Fazer Aito Professional Barista oat drink, gluten free, **€174.00**, confirmed stock, prepared for a person (F-10). What it gives up: "it costs €0.37 more per L", "carbohydrate 7.8 g, not 6.6 g, sugars 1.6 g, not 3.5 g", "it does not carry the original's nutritional claim FREE_FROM_PRESERVATIVES", and the components its ingredient list adds (a stabiliser among them). `473609` is left out with its reason.

**At the recording's clock** the plain sentence gives: first, 100 × `475224`, €174.00, confirmed (F-10); second, `473609` as "quantity not confirmed", €137.00. `471690` is not offered: "Order cut-off passed", a delivery constraint.

## 4. A product with an allergen doubt: Harbourside Hotel, then Kilo School

### 4a. `100 litres of Elovena barista oat drink, product 469512, by Monday; no milk, strict rule`

**First five seconds**
- **Asked:** 100 L of `469512`, milk excluded, strict rule.
- **Suggested, the safe product first:** 100 × `473424` Alpro Rice drink, **€236.00**. "Its data rules out every excluded allergen; the alternative whose data does not costs €28.00 less." What it gives up: "not made for coffee, as the product asked for is", "fat 1 g, not 3 g", and the components of the two ingredient lists that differ.
- **"Alternative: allergen not ruled out":** 100 × `469512`, **€208.00**. Cheaper, and still not the suggestion.
- **Needs a person:** the dietitian, for `469512`. P-04: "Elovena 1l oat drink barista (469512) does not rule out an allergen this buyer excludes: AM (no statement)."

**Then:** pick `469512` and order. Only the dietitian can decide: the agent, the purchasing manager and finance each get 403. Leena's card shows:
- **The evidence** (a recorded page, not Valio Aimo's data): "The manufacturer's page “Elovena Kaurajuoma kahviin” on raisiofoodsolutions.fi says: contains “KAURA”; free from “Gluteeniton”, “Laktoositon”, “Maidoton”, “Kananmunaton”. Asked about milk (AM): Valio Aimo's data states nothing; the page says free from, in its words “Maidoton”. It changes no verdict: a human decides."
- **Three choices:** take the safe product (ordered: 100 × `473424`, €236.00; the log says she "chose another option of the same offer"), use it anyway (ordered: 100 × `469512`, €208.00), or leave it out (rejected, nothing ordered). Each ends in the log with her name and note; Valio Aimo's view shows rule P-04 with "which allergen and which product are not shown".

### 4b. `20 litres of almond drink by Monday` (Kilo School)

The sentence names no allergen: tree nuts, peanuts and sesame are the school's profile.

- **Nothing is suggested as safe:** "no product whose data rules out tree nuts (AN), peanuts (AP) and sesame seeds (AS) can be offered, so no option is suggested as safe: a dietitian must decide on each alternative." 3 of the 5 almond drinks declare tree nuts and are left out.
- **"Alternative: allergen not ruled out":** 20 × `465793` Alpro Barista Almond, **€47.60**. P-04: "… does not rule out an allergen this buyer excludes: AN (may contain, stated for SA)."
- **The dietitian's evidence:** "The manufacturer's page “Barista Mantelijuoma” on alpro.com says: contains “manteli” … Asked about tree nuts (AN): Valio Aimo's data does not rule it out; the page says it contains it, in its words “manteli”. The page names tree nuts (AN), which this order excludes: check the product before approving. What a page says can add a doubt and never removes one."
- **Then:** Riikka leaves it out → "Rejected by Demo approver Riikka (dietitian): nothing was ordered."

**The two clocks:** identical for 4a and 4b.

## 5. The customer's pattern, Valio Aimo's own suggestion, and the standing order: Harbourside Hotel

**Type:** `100 litres of lactose-free milk by Monday`

**First five seconds**
- **Suggested:** 100 × `469363`, the hotel's usual milk, **€248.00**, prepared for a person (F-10). Alternative, quantity not confirmed: 100 × `464306`, €101.00.
- **The forgotten item:** "In 7 of your last 8 orders with Arla Semi skimmed milkdrink 1 L UHT lactose free Suomesta (469363) you also ordered Arla Pro Cooking cream 10% 1 L UHT lactose free (463797), usually 10 L. It is not in this request. From a synthetic order history. 114 sales units are confirmed in stock for delivery on Monday 16 November. Adding it costs €33.10 before tax."
- **Valio Aimo's own suggestion** (the brief's proactive selling agent): `462775`, "a milk of the brand Arla, like the … (469363) you usually order, and in none of your 8 past orders … Suggested by Valio Aimo from its catalog, not from your orders."
- A suggestion is shown, never added.

**Accept the forgotten item:** a new request and a new offer, 100 × `469363` + 10 × `463797`, **€281.10**, judged by the same rules. Hanna confirms → "Confirmed by Demo approver Hanna (purchasing manager): ordered for €281.10 net." The first offer's log ends "suggestions.shown, suggestion.accepted". Valio Aimo reads that suggestions were shown and its own by name, not the buyer's order history.

**Then, one button** on `/standing-orders`: "Load the demo standing orders", then renew "Weekly lactose-free milk, hotel kitchen" at **290** L.
- Drift: "Standing order so_demo_hotel_milk drifts beyond the 25% tolerance: 290 L this week against a median of 100 L over the last 6 renewals. 6 renewals of the history are synthetic, made up for the demonstration".
- 290 × `469363`, **€719.20**, to the purchasing manager. P-08: "For standing order so_demo_hotel_milk, 290 L this week against a median of 100 L over the last 6 renewals, more than the 25% tolerance of Harbourside Hotel."
- Renewed as stored (100 L) it is within the tolerance: €248.00, prepared for a person (F-10).
- The same page shows the school's trend: "Your last 3 orders of Oatly Oat Drink Semi 1L (470863) have a median of 84 L against 70 L for the 3 before (+20%), each higher than the last. The standing order still says 60 L. Store 84 L?" with the button "Renew once at 84 L" (84 L is €117.60).

**The two clocks:** identical.

## 6. The formula matters: Kallio Bakery

### 6a. `40 kg of Valio crème fraîche, product 477055, by Monday, for baking`

"For baking" sets the formula mark on the line; the bakery's profile sets it too.

**First five seconds (demo clock)**
- **Asked:** 40 kg of `477055` (20 tubs of 2 kg), the formula to be kept.
- **First:** "Alternative: quantity not confirmed": 20 × `477055`, **€214.40** (F-01). Valio Aimo does not confirm its stock.
- **Last, labelled:** "Alternative: quantity not confirmed, a substitute that does not keep the formula": 27 cases of `477003` Valio Keittiön crème fraîche 150 g, **€339.66** (F-01, F-11, P-01, P-05).
- **Said:** "the request says the formula matters, and no substitute that keeps the formula can be ordered".
- **Needs a person:** the owner, for either.

**Rule F-11, in its words:** "… would replace Valio crème fraîche 2 kg lactose free (477055) where the formula matters (the request says so for this line), and the data does not show the same formula: Different contents: the ingredient list of the product asked for names 'modified maize starch', 'thickeners (pectin)', which this product's does not; 'pasteurised organic CREAM' against 'CREAM': not shown to be the same. Figures outside our tolerance: carbohydrate 2.7 g, not 3.8 g per 100 g."

**At the recording's clock** the labelled substitute is another product: 223 × `468277`, a 12% crème fraîche in 180 g pots, **€198.47** (F-01, F-11, P-05): "Figures outside our tolerance: fat 12 g, not 28 g; saturated fat 7.1 g, not 17 g per 100 g". The first option, the label and the rule are the same.

### 6b. `100 litres of whipping cream by Monday, for cakes`

- Confirmed whipping cream covers **85 of the 100 L**: 48 × `469346` + 37 × `464727`, **€549.65**, to the owner (P-01: above €300 per order; P-03: 85%, below 100%). Alternative, quantity not confirmed: 58 × `465193` (1.75 L), €338.14.
- The vegetable-fat blend `463975` is in no option: it is another product type and never tops cream up.
- **The contents decide, not only the six nutrition figures.** Asked for by id, `60 litres of Arla Pro whipping cream, product 469346, by Monday, for cakes`: first, the 48 L that are confirmed, €276.96 (P-03: 80%, below 100%). Then "Alternative: a substitute that does not keep the formula": 48 × `469346` + 12 × `464727`, **€365.40** (F-11, P-01, P-05). F-11: "… and the data does not show the same formula: Different contents: the ingredient list of the product asked for names 'lactase enzyme', which this product's does not. The six nutrition figures are within our tolerance of 15% or 1 g per nutrient (salt 0.25 g)."

**Measured with tonight's change to the formula comparison** (contents as well as figures; commit `42f51a2`). Before it, the same 12 L read "same formula within our tolerance" and F-11 stayed silent; totals and products did not move. In 6b's first option the two creams fill one request line by type, so neither is a substitute of the other and F-11 does not judge them. The tests pin the behaviour (a stand-in that does not keep the formula is labelled, never first, and goes to a person), not the comparison's answer.

## 7. Need → recipe → order: Kallio Bakery

**On `/menu`, type:** `I want to make a chocolate cake for 20 people by Monday` (or `POST /v1/menus/plan` with `{"text": "…"}` as the bakery).

Built by another lane (commit `e53519c`); its own tests are that lane's. Measured here once, at 22:08, at both clocks:

- **The recipe for 20** (ours, marked illustrative): 0.4 kg flour, 0.4 kg sugar, 0.4 kg eggs, 0.3 kg butter, 0.1 kg cocoa powder, 0.3 L milk, 0.02 kg baking powder. One typed request of 7 lines; no ingredient is reported as impossible to source.
- **First option, confirmed stock only, a partial fill: €15.19.** Flour `460856` (2 kg), cocoa `475703` (200 g), milk `463047` (1 L), baking powder `466228` (700 g). Sugar, eggs and butter have no confirmed stock in the recordings, so the option is short and goes to the owner (F-07, P-03).
- **"Alternative: quantity not confirmed", all 7 lines:** €104.65 at the demo clock (3 lines unconfirmed, with a 25 kg sack of sugar, 5 kg of liquid egg and a 4 × 5 kg case of butter), €61.02 at the recording's clock (4 lines unconfirmed, with 500 g of butter). F-01 on each unconfirmed line.
- **What it shows honestly:** the path from a sentence to a recipe to one order that waits for a person works. The order itself is small and the packs are wholesale packs: 25 kg of sugar for a cake that needs 0.4 kg. The lane that chooses packs for small needs was still changing this at 22:08; re-measure before recording.

Also measured on a recipe that was there before (`tests/e2e/test_scenario_7_menu.py`, both clocks): beef stew for 80 as the hotel needs 14.4 kg of beef chuck, 2.4 L of cream and 0.8 kg of butter; one request of 3 lines; every ingredient is in the first option or named as missing, none is dropped unsaid; beef is sold by weight, so the total is an estimate and the order goes to a person (P-06).

---

## The figures at both clocks

Recording's clock: Sat 14 Nov 2026 02:52. Demo clock: Thu 12 Nov 2026 14:15. All from the recording of 769 products, except row 7, which also reads the 394 baking products.

| # | Request | Recording's clock | Demo clock | Who confirms |
|---|---|---|---|---|
| 1 | hotel, 1,000 L lactose-free milk | 435 L, €1,083.39 (P-01, P-03); alt. 1,000 × `464306` €1,010.00 (F-01, P-01); 17 left out | the same; 2 left out | purchasing manager |
| 2 | ward, 200 L milk substitute | 200 × `464013` €402.00 (F-10) | the same | purchasing manager |
| 2 | the same, ordering alone on | ordered by the agent, €402.00 | the same | nobody |
| 3 | hotel, 100 L of `473609` | 100 × `475224` €174.00 (F-10); alt. `473609` €137.00 (F-01) | alt. `473609` €137.00 (F-01); alt. 10 × `471690` €155.50 (F-01) | purchasing manager |
| 3 | the same, confirmed data only | 100 × `475224` €174.00 (F-10) | the same | purchasing manager |
| 4a | hotel, 100 L of `469512`, no milk | 100 × `473424` €236.00 (F-10); alt. `469512` €208.00 (P-04) | the same | purchasing manager; dietitian for `469512` |
| 4b | school, 20 L almond drink | alt. 20 × `465793` €47.60 (P-04); alt. 20 × `474864` €28.80 (F-01, P-04) | the same | dietitian; with the purchasing manager for `474864` |
| 5 | hotel, 100 L lactose-free milk | 100 × `469363` €248.00 (F-10); with the cooking cream €281.10 (F-10) | the same | purchasing manager |
| 5 | hotel, standing order at 290 L | 290 × `469363` €719.20 (P-08) | the same | purchasing manager |
| 6a | bakery, 40 kg of `477055` | alt. 20 × `477055` €214.40 (F-01); alt. 223 × `468277` €198.47 (F-01, F-11, P-05) | alt. 20 × `477055` €214.40 (F-01); alt. 27 × `477003` €339.66 (F-01, F-11, P-01, P-05) | the owner |
| 6b | bakery, 100 L whipping cream | 85 L, €549.65 (P-01, P-03); alt. 58 × `465193` €338.14 (F-01, P-01) | the same | the owner |
| 6b | bakery, 60 L of `469346` | 48 L, €276.96 (P-03); alt. with 12 × `464727` €365.40 (F-11, P-01, P-05) | the same | the owner |
| 7 | bakery, chocolate cake for 20 | 4 of 7 lines confirmed, €15.19 (F-07, P-03); alt. all 7 lines €61.02 (F-01 × 4) | €15.19 (F-07, P-03); alt. €104.65 (F-01 × 3) | the owner |

## What this demo does not show

- **No model is called.** The sentences of scenarios 1 and 2 are answered from recordings in `fixtures/agent/`, labelled as recordings; the others are read by fixed rules, and the answer says "read and made by fixed rules, not by a model". A sentence the rules cannot read gets a question back, not a guess.
- **Recorded data, not the live mock.** 769 products (plus 394 baking products for the menu). A product outside the recordings has no price or stock here, and the offer says so.
- **No regular milk has confirmed stock in the recording.** A plain "milk" request is filled with a named lactose-free or low-lactose milk, said in the offer; it cannot show regular milk winning.
- **A "tomorrow" that can be met.** At the demo clock "tomorrow" is Friday 13 Nov; no last-minute request was found that the recording can fill for it, so the brief's "last-minute event" is not a scenario here. What is shown of delivery constraints is the cut-off: products past their order deadline are left out with the reason (scenario 1 at the recording's clock, scenario 3).
- **Scenario 3 at the demo clock has no confirmed option** for the plain sentence, although 130 units of `475224` are confirmed: the offer holds one substitute option and Valio's own listed substitute takes it. "Confirmed data only" brings the confirmed stand-in.
- **Suggestions exist in replay only**, from a synthetic order history, and every sentence says so. Valio Aimo's own suggestion is a related product of a brand the customer already buys; the product file has no "new" or "seasonal" mark.
- **Standing-order histories are synthetic** (8 past orders per customer, 16 for the ward). A renewal made in the demo joins the history as a real row.
- **The school's whole standing order cannot be renewed cleanly:** its usual milk `462775` and yoghurt `464517` state nothing about tree nuts, peanuts or sesame, so under the school's strict rule every option with them goes to the dietitian. The trend is shown on its oat drink only.
- **An order commits nobody.** The Valio Aimo mock has no order endpoint, by design: "ordered" is a signed record in this gateway's order book and its log.
- **Evidence pages are recordings** (`fixtures/evidence/`, 13 pages). A product with no recorded page shows no page; nothing is fetched during the demo.
- **Nobody on the team has seen every page of this script in a real browser at 390 px.** The figures are the gateway's; the layout is not checked here.

## If something goes wrong

- **A total or a rule differs from this page:** the order book was not empty, or a scenario was run twice. P-02 (the day's limit) is the usual sign. Press "Start again", or stop the app, delete `var/demo.sqlite3` and start it again.
- **The clock strip does not say Thursday 12 November 14:15:** `TTA_DEMO_CLOCK` is not set. Scenarios 3 and 6a then show their recording's-clock answers, given above.
- **A sentence gets a question back:** it is not one of the sentences above and the fixed rules could not read all of it. Use the button, or send the typed request to `POST /v1/offers`.
