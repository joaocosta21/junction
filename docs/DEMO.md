# Demo script

Seven scenarios on one page, `/shop`: each is one sentence a person types, or one button. Every figure below was measured on Sunday 15 Nov 2026 between 02:26 and 02:55, in replay, through the routes the page itself calls (`/shop/api/*`), once at each clock; the last full run, of every scenario at both clocks, was at 02:54 on commit `dbb8e13`, and gave the same answers as the run at 02:51 on `fd4098b`. No outside service was called, and no model: the server ran with no model key (see "Who reads the sentence").

**What was checked and what was not.** Products, quantities, totals, rule ids, who confirms and the quoted sentences are the gateway's answers to the page's own calls. The names of buttons and labels were checked against the page's source at 02:54 (commit `dbb8e13`). The person who wrote this script did not click through it in a browser: the page was walked in headless Chrome by another check (`AIMO/build/replan/REVIEW.md`, section BW) before the last changes.

**Where a figure comes from.** The recording `fixtures/valio/2026-11-14-demo`: price and availability of 769 products, recorded Saturday 14 Nov 2026 at 02:52 Helsinki time. Replay also answers for the 394 baking products of `2026-11-14-baking` (the same Saturday, 21:12): 1,163 products in all, and only scenario 7 needs the second recording. A figure here is a fact about these recordings, never about the catalog of 17,546 products.

**The clock.** The demo is shown at the **demo clock, Thursday 12 Nov 2026 14:15 Helsinki time** (`TTA_DEMO_CLOCK`, replay only). We chose it: Valio Aimo said on 14 Nov that its test data is static. The strip at the top of the page says which clock is in force, and the log keeps the real time. Without the setting the clock is the recording's own instant (Saturday 14 Nov, 02:52). "By Monday" is Monday 16 Nov at both. Where the two clocks answer differently, the scenario says so.

## Before you start

```sh
rm -f var/demo.sqlite3
GEMINI_API_KEY= TTA_ENV=demo TTA_MODE=replay TTA_DEMO_CLOCK=2026-11-12T14:15:00+02:00 \
  TTA_DB_PATH=var/demo.sqlite3 .venv/bin/python -m uvicorn --factory tta.api:create_app --port 8000 --no-proxy-headers
```

Open `http://127.0.0.1:8000/shop`. Everything a person does in this script happens there. `/docs` is the interface for an agent. The older pages (`/`, `/approvals`, `/kitchen`, `/menu`, `/standing-orders`) are still served and are not used.

- **Who you are.** The page has no login. The menu at the top right switches between the four customers and says who you act as ("Demo, no login: you are acting as Hanna Laine, Harbourside Hotel."). Each customer has its own order book in this browser.
- **One person confirms.** At the hotel and the bakery the person who orders holds every role, so "Confirm order" on the answer is the whole decision. The ward and the school have one second person, the dietitian: what is hers waits under "Waiting for someone else", where the button "Decide as …, dietitian (demonstration)" lets one visitor walk the whole flow.
- **Run each scenario once, in order, from an empty book.** In replay the day never ends, so a customer's spend of the day only grows. One pass in the order below, each scenario ordered once, puts €2,493.69 on the hotel's day (limit €3,000), €402.00 on the ward's and €779.24 on the bakery's (limit €1,000) at the demo clock, so the rule for the day's limit (P-02) never fires. To start again: Settings → "Reset this customer's demo", per customer. The file `var/demo.sqlite3` holds the book of REST and MCP only.
- **Nothing is ordered without a person.** Ordering alone is a buyer's setting, off for all four customers (rule F-10). See "Ordering alone" under scenario 2.
- The limits, names and order histories of the four customers are ours and illustrative: Valio Aimo's mock has no customer limits and no order history. The page says so.

| Customer | You act as | The second person | Limits (illustrative) |
|---|---|---|---|
| Harbourside Hotel | Hanna Laine, purchasing manager; holds every role | none | €750 per order, €3,000 per day, at least 90% of the quantity |
| City Hospital, Ward 4 | Jussi Nieminen, purchasing manager | Sari Lehto, dietitian | €500 per order, €1,500 per day, 100%; no milk, no gluten, strict; confirmed data only |
| Kilo School | Päivi Korhonen, purchasing manager | Riikka Mäkelä, dietitian | €250 per order, €800 per day, 100%; no tree nuts, peanuts or sesame, strict |
| Kallio Bakery | Marko Heikkinen, the owner; holds every role | none | €300 per order, €1,000 per day, 100%; the formula matters; no substitute without a person |

Over REST and MCP the same four customers have public demo tokens (`demo-agent-hotel-kitchen`, `demo-agent-allergy-ward`, `demo-agent-school-kitchen`, `demo-agent-bakery-cafe`, six people's tokens and Valio Aimo's reader: 11 identities, listed in `/llms.txt` and `/docs`). There an agent's token cannot approve: the decision route answers 403 and logs the attempt, and no MCP tool approves.

## The demo set

| # | Customer | The sentence or the button | Brief's scenario | Criterion |
|---|---|---|---|---|
| 1 | Hotel | "1,000 litres of lactose-free milk by Monday" | the brief's own flow | 30% end to end · 15% partial availability · 20% log |
| 2 | Ward | "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only" | allergen-safe ordering | 20% controls · 20% match |
| 3 | Hotel | "100 litres of Oddlygood Barista oat drink, product 473609, by Monday" | supplier stock-out | 15% exceptions |
| 4 | Hotel, then School | "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk, strict rule", then "20 litres of almond drink by Monday" | allergen-safe substitution under pressure | 20% controls · 15% exceptions |
| 5 | Hotel, then Bakery | "100 litres of lactose-free milk by Monday"; "10 litres of whipping cream by Monday" (bakery); Standing orders → renew once at 290 L (hotel) | proactive selling agent · standing order drift detection | 20% match · 20% controls |
| 6 | Bakery | "40 kg of Valio crème fraîche, product 477055, by Monday, for baking"; "60 litres of Arla Pro whipping cream, product 469346, by Monday, for cakes" (look); "100 litres of whipping cream by Monday, for cakes" | substitution where the formula matters | 20% match · 15% exceptions |
| 7 | Bakery | "A chocolate cake for 20 by Monday" | need → recipe → order | 30% end to end |

Reserve: "100 litres of lactose-free milk by tomorrow" (hotel): a date that cannot be met, answered with the earliest date (see "Next steps, and how the demo answers today").

**Who reads the sentence.** This script was measured with no model key set (`GEMINI_API_KEY=` empty, as in the command above). On `/shop` every sentence above is then read by the fixed rules, and the answer says so: "Read by fixed rules, not by a model: no Gemini key is set." With a key set a model is asked first; the gateway checks its reading against the text and refuses one that does not match, and when the model does not answer the fixed rules read the sentence (one they cannot read is then answered with the rules' own reason). The answer always says who read it, and `/healthz` → `agent_reader` says what reads sentences on the server in front of you. Whoever reads, the options, totals and rules below are made by fixed rules from the typed request: the same typed request gives the same answer. A sentence the fixed rules cannot read gets a question back, not a guess. The demo sentences name no price. An amount named for the whole request is read and applied as a spend limit for that request, tighter than the buyer's own (hotel: `200 litres of lactose-free milk by Monday, under €400` → €496.00 waits for a person, "The total of €496.00 before tax is above the €400 you named for this request."); a price per unit is asked about. Quantities are said in litres or kilograms, not cartons (the reader asks what a carton holds).

---

## 1. The brief's own sentence: Harbourside Hotel

**Type:** `1,000 litres of lactose-free milk by Monday`, then "Check price and stock". The brief's full sentence, "I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability.", gives the same answer.

**The answer, three options**
- **Suggested:** confirmed stock covers **435 L of the 1,000 L** (43.5%): 384 × `469363` + 51 × `462775`, **€1,083.39** before tax. "2 confirmed products cover 435 L of the 1,000 L asked for (565 L missing), for €1,083.39 before tax."
- **"Alternative: quantity not confirmed":** 1,000 × `464306`, **€1,010.00**. "Valio does not confirm the quantity in stock, so a human must approve this option." It is never the suggestion.
- **"Alternative: confirmed stock, completed with a substitute":** 384 × `469363` + 51 × `462775` + 565 × `463380`, **€2,580.64** before tax (€2,929.02 with tax). "All 1,000 L from confirmed stock, if 565 L may be Arla Cafè milk 1 L UHT lactose free (463380) at €2.65 per L". The coffee milk is named as a substitute and "Not a like-for-like replacement: another product type (coffee milk, not milk); made for coffee; the product asked for is not; a different formula".
- **Said in a note:** "21 products fit the request and are in no option because Valio does not confirm their quantity … The cheapest product whose quantity is not confirmed, 464306, is the alternative shown."
- **A suggestion, shown and not added:** "With this milk you usually also order Arla Pro Cooking cream 10% (463797): it was in 7 of your last 8 orders, 10 L each time, and it is not in this request. Adding 10 L costs €33.10. 114 L confirmed for Monday 16 November. From a synthetic order history."
- **Needs a person:** Hanna Laine, for each of the three.

**Rules, in their words**
- P-01: "The total of €1,083.39 before tax is above the €750 limit per order of Harbourside Hotel."
- P-03: "Only 43.5% of the requested quantity is covered, below the 90% minimum (covered: 435 of 1,000 L)."
- F-01 (option 2): "The quantity of 1,000 × Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free (464306) is not confirmed by Valio Aimo."
- F-12 (option 3, with P-01): "Arla Cafè milk 1 L UHT lactose free (463380) would replace Arla Semi skimmed milkdrink 1 L UHT lactose free Suomesta (469363) and is not a like-for-like replacement: … A person decides whether it will do."

**Then:** "Confirm order" on the suggested option → "Ordered for €1,083.39 net with approval by Hanna Laine, Harbourside Hotel: rules P-01 and P-03 asked for a human and were accepted."

**The log, two readers** (11 events for this path; the chain verifies for both). Open the order under "Orders".
- The buyer reads the limit, the customer's name, who approved, and the suggestion shown with the two that were not and why.
- "What Valio Aimo sees" holds the same 11 events: "P-01, a rule the buyer set (the order is above the spend limit per order; the amount is not shown): approval by a person of the buyer", "F-12, a fixed rule (a substitute is not a like-for-like replacement), on product 463380", "A person of the buyer approved order …", and the products left out for a reason in its own data, by id ("1 that cannot be delivered (464440); 1 sold in portion packs, which the request does not ask for (463203)"). Never a limit amount, a name or a note.

**The two clocks:** the three options, their totals and their rules are identical. Left out with a reason: 2 of 26 candidates at the demo clock (1 portion pack, 1 that cannot be delivered); 17 at the recording's clock (15 more whose order cut-off has passed).

## 2. Strict allergen rule: City Hospital, Ward 4

Switch to City Hospital, Ward 4 (you act as Jussi Nieminen).

**Type:** `200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only`

**The answer, one option**
- **Read as:** 200 L of a plant drink, milk and gluten excluded, confirmed data only. "A milk substitute is read as a plant drink (oat, soya and other plant-based drinks): a product type, not a product."
- **Suggested:** 200 × `464013` Alpro No Sugars Soya drink, **€402.00**. Its data states "free from" for milk and for gluten, and every statement of the line is confirmed.
- **Left out, of 51 candidates:** 41. At the demo clock: 18 that declare an excluded allergen, 11 that state nothing about one, 6 that cannot be delivered, 6 past their cut-off. At the recording's clock: 18, 5, 6 and 12.
- **Needs a person:** "Prepared: confirm to order. The agent prepares the order, a person confirms it (F-10): the purchasing manager confirms."

**Then:** "Confirm order" → "Confirmed by Jussi Nieminen, City Hospital, Ward 4 (purchasing manager): ordered for €402.00 net." Valio Aimo's view of the request reads "200 litres of product type plant_drink, needed by Monday 16 November 2026, confirmed data only": the excluded allergens are not shown. It does read "11 with a quantity that is not confirmed, when the buyer asked for confirmed data only", so the ward's "confirmed data only" setting is visible to Valio Aimo as a count.

**Ordering alone** (20% criterion: what the agent decides alone). Settings → "What the agent may do alone" → "Let the agent place orders alone", then the same sentence: the 200 L are ordered by the agent. "The agent placed this order alone for €402.00 net. That was allowed: ordering alone is switched on for City Hospital, Ward 4; the total of €402.00 is within the €500 limit per order; today's spend with this order is €402.00 of the €1,500 limit per day; every statement of the offer is confirmed; and no rule asked for a person." The switch is an event of the book's audit trail, shown on the Settings page under "What changed"; at the hotel it reads "Hanna Laine switched ordering alone on: the agent may order up to €750.00 an order and €3,000.00 a day without asking." Valio Aimo reads only "The buyer changed a setting of its agent. Which setting and its values are the buyer's own and are not shown." On the same Settings page the ward's allergen exclusions are locked: "Set by Sari Lehto, the dietitian: … This cannot be removed or made less strict here." (at the school the route refuses it: "The allergen exclusions of Kilo School are set by its dietitian and cannot be removed here: tree nuts, peanuts and sesame seeds must stay excluded").

The limit can be shown at the hotel with the same switch on: `302 litres of lactose-free milk by Monday` is €748.96 and is ordered by the agent; `303 litres …` is €751.44 and waits for Hanna Laine (P-01, the €750 limit per order). Over REST and MCP no demo agent orders alone: ordering alone is off in the four profiles and no route sets it; it is shown on the page only.

**The two clocks:** identical option, total and rule.

## 3. Supplier stock-out: Harbourside Hotel

**Type:** `100 litres of Oddlygood Barista oat drink, product 473609, by Monday`

**The answer at the demo clock, three options**
- **Asked:** 100 L of `473609`, a gluten-free barista oat drink. Valio Aimo reports a placeholder for its stock, so its quantity is not confirmed.
- **Suggested, "With a substitute for a product that cannot be supplied in full":** 100 × `475224` Fazer Aito Professional Barista Oat drink, gluten-free, **€174.00**, from confirmed stock. The line says what it gives up: "Not a like-for-like replacement: a different formula. Compared with Oddlygood® Barista oat drink 1 l UHT gluten free: it costs €0.37 more per L; it does not carry the claim FREE_FROM_PRESERVATIVES; the brand is Fazer Aito, not Oddlygood®; Valio does not list it as a substitute. … Figures outside our tolerance: carbohydrate 7.8 g, not 6.6 g; sugars 1.6 g, not 3.5 g per 100 ml."
- **"Alternative: quantity not confirmed":** 100 × `473609` itself, **€137.00** (F-01).
- **"Alternative: quantity not confirmed":** 10 cases of `471690`, the substitute Valio itself lists, **€155.50** (F-01, F-12): "a different formula (fat 1.5 g, not 3 g); it cannot be shown to be like for like: its name adds Delight, which the data does not explain", "one sales unit holds 10 L, not 1 L".
- **Never offered:** the two other substitutes Valio lists, `471881` and `464320`, add gluten to a gluten-free product: "The substitute adds 1 allergen that the original does not declare: cereals containing gluten (AW, contains). It can never be ordered as a substitute." (`POST /v1/products/473609/substitutes` lists them with that reason.)
- **Needs a person:** Hanna Laine, for each. Two rules on the suggested option. F-12: "Fazer Aito Professional Barista Oat drink, gluten-free 1L UHT (475224) would replace Oddlygood® Barista oat drink 1 l UHT gluten free (473609) and is not a like-for-like replacement: a different formula (…). A person decides whether it will do." P-05, the price: "Fazer Aito Professional Barista Oat drink, gluten-free 1L UHT (475224) replaces Oddlygood® Barista oat drink 1 l UHT gluten free (473609), and the substitute costs €37.00 more than the product you asked for (27% more): a person decides." Both hold with ordering alone switched on: the agent never orders alone a substitute that is not judged replaceable, nor one that costs more than 25% above the product asked for (25% is our value where the buyer sets none).

**Then:** "Confirm order" → "Ordered for €174.00 net with approval by Hanna Laine, Harbourside Hotel: rules F-12 and P-05 asked for a human and were accepted."

**With `; confirmed data only` added** the answer is the first option alone, the same at both clocks: 100 × `475224`, €174.00 (F-12, P-05), and the note "1 product whose quantity Valio does not confirm was left out, because confirmed data only was asked for: 473609."

**At the recording's clock** the plain sentence gives two options: 100 × `475224`, €174.00 (F-12, P-05), and `473609` as "quantity not confirmed", €137.00 (F-01). `471690` is not offered there: "Order cut-off passed on Thursday 12 Nov at 15:00, so delivery on Monday 16 Nov cannot be promised", a delivery constraint.

## 4. A product with an allergen doubt: Harbourside Hotel, then Kilo School

### 4a. `100 litres of Elovena barista oat drink, product 469512, by Monday; no milk, strict rule` (hotel)

The hotel's profile excludes no allergen; the sentence does ("no milk, strict rule").

**The answer, three options**
- **Suggested, the safe product first, "With a substitute whose data rules out the allergen you exclude":** 100 × `473424` Alpro Rice drink, **€236.00**. "Elovena 1l oat drink barista (469512) states nothing about milk (AM), which is excluded; Alpro Rice drink 1L (473424) is free from it. Its data rules out every excluded allergen; the alternative whose data does not costs €28.00 less." It is a substitute that is not like for like ("not made for coffee, as the product asked for is; a different formula … fat 1 g, not 3 g"), so F-12 asks for a person.
- **"Alternative: allergen not ruled out":** 100 × `469512`, the product asked for, **€208.00**. Cheaper, and still not the suggestion. P-04: "Elovena 1l oat drink barista (469512) says nothing about milk, which is excluded for Harbourside Hotel: Valio Aimo's data does not rule it out."
- **"Alternative: quantity not confirmed, allergen not ruled out":** 100 × `473609`, **€137.00** (F-01, F-12, P-04).
- **Needs a person:** Hanna Laine for each. The hotel has no dietitian, so the allergen question is hers too.

**The question, on the result.** "Choose" on the `469512` alternative: "Needs your decision: the agent is not sure about Elovena 1l oat drink barista (469512)", with the evidence, which is a recorded page and not Valio Aimo's data: "The manufacturer's page “Elovena Kaurajuoma kahviin” on raisiofoodsolutions.fi says: contains “KAURA”; free from “Gluteeniton”, “Laktoositon”, “Maidoton”, “Kananmunaton”. Asked about milk (AM): Valio Aimo's data states nothing; the page says free from, in its words “Maidoton”. It changes no verdict: a human decides." Three choices:
- **"Take the safe product":** ordered, 100 × `473424`, "Ordered for €236.00 net with approval by Hanna Laine, Harbourside Hotel: rule F-12 asked for a human and was accepted."
- **"Use it anyway":** ordered, 100 × `469512`, "Ordered for €208.00 net with approval by Hanna Laine, Harbourside Hotel: rule P-04 asked for a human and was accepted."
- **"Leave it out":** "Rejected by Hanna Laine, Harbourside Hotel: nothing was ordered."

Each ends in the log with her name and note. Valio Aimo's view shows rule P-04 as "a line does not rule out an excluded allergen; which allergen is not shown", and the evidence step without the product: "Evidence from outside Valio Aimo's data was attached to an approval (the product is not named in this step)."

**The two clocks:** identical.

### 4b. `20 litres of almond drink by Monday` (Kilo School)

Switch to Kilo School (you act as Päivi Korhonen). The sentence names no allergen: tree nuts, peanuts and sesame are the school's profile.

- **Nothing is suggested as safe:** "no product whose data rules out tree nuts (AN), peanuts (AP) and sesame seeds (AS) can be offered, so no option is suggested as safe: a dietitian must decide on each alternative." 3 of the 5 almond drinks declare tree nuts and are left out.
- **"Alternative: allergen not ruled out":** 20 × `465793` Alpro Barista Almond drink, **€47.60**. P-04: "Alpro Barista Almond drink 1L (465793) may contain almonds (counted under tree nuts), which is excluded for Kilo School: Valio Aimo's data does not rule it out."
- **"Alternative: quantity not confirmed, allergen not ruled out":** 20 × `474864`, **€28.80** (F-01 and P-04: it needs Päivi Korhonen and the dietitian).
- **A suggestion:** "You asked for plant drink without naming one. You usually buy Oatly Oat Drink Semi (470863): it was in 8 of your last 8 plant drink orders. Use it? For 20 L: €28.00. 1,414 L confirmed for Monday 16 November. From a synthetic order history."
- **Order the first alternative:** "Waiting for approval by the dietitian, to be decided by Sunday 15 November 2026 at 17:00". Päivi Korhonen cannot decide it: the route answers 403, "The approval still needs the dietitian".
- **Under "Waiting for someone else"**, the dietitian's card carries the evidence, which is a recorded page and not Valio Aimo's data: "The manufacturer's page “Barista Mantelijuoma” on alpro.com says: contains “manteli”; may contain “pähkinöistä (ei maapähkinästä)”; free from “laktoositon”, “Maidoton”, “Gluteeniton”. Asked about tree nuts (AN): Valio Aimo's data does not rule it out; the page says it contains it, in its words “manteli”. The page names tree nuts (AN), which this order excludes: check the product before approving. What a page says can add a doubt and never removes one. It changes no verdict: a human decides."
- **Then:** "Decide as Riikka Mäkelä, dietitian (demonstration)" → "Leave it out" → "Rejected by Riikka Mäkelä, Kilo School (dietitian): nothing was ordered." Valio Aimo reads "Order … was rejected by the buyer's dietitian. Nothing was ordered." and of the rule "which allergen is not shown".

**The two clocks:** identical.

## 5. The customer's pattern, Valio Aimo's own suggestion, and the standing order

### 5a. The forgotten item: Harbourside Hotel

**Type:** `100 litres of lactose-free milk by Monday`

- **Suggested:** 100 × `469363`, the hotel's usual milk, **€248.00**, prepared for a person (F-10). Alternative, quantity not confirmed: 100 × `464306`, €101.00 (F-01).
- **The forgotten item:** "With this milk you usually also order Arla Pro Cooking cream 10% (463797): it was in 7 of your last 8 orders, 10 L each time, and it is not in this request. Adding 10 L costs €33.10. 114 L confirmed for Monday 16 November. From a synthetic order history."
- **Valio Aimo's own suggestion does not show here**, and the log says why: its candidate `462775` has 51 packs confirmed and 100 are needed, and `463047` does not carry the lactose-free claim.
- **"Add":** a new request and a new offer, 100 × `469363` + 10 × `463797`, **€281.10**, judged by the same rules; the first card says it was replaced and has no button. "Confirm order" → "Confirmed by Hanna Laine, Harbourside Hotel: ordered for €281.10 net."

### 5b. Valio Aimo's own suggestion (the brief's proactive selling agent): Kallio Bakery

Switch to Kallio Bakery (you act as Marko Heikkinen). **Type:** `10 litres of whipping cream by Monday`. Look, do not order (the bakery's day is needed for scenarios 6 and 7).

- **Suggested:** 10 × `469346` Arla Pro Whipping cream, **€57.70**, prepared for a person (F-10). Alternative, quantity not confirmed: 6 × `465193` (1.75 L), €34.98.
- **Valio Aimo's suggestion:** "Because you buy Oatly iKaffe 0.5 L (468319), Valio Aimo suggests Oatly iKaffe Oat drink 1.5 L (473278): the same kind of plant drink, with the same formula, €1.48 a litre instead of €2.88. For your usual 30 L: €44.40, €42.00 less. 234 L confirmed for Monday 16 November. Suggested by Valio Aimo, not from your orders."
- **The buyer's own:** "With this cream you usually also order Arla Cafè milk (463380): it was in 8 of your last 8 orders, about 60 L each time, and it is not in this request. Adding 60 L costs €159.00. 698 L confirmed for Monday 16 November. From a synthetic order history."
- A suggestion is shown, never added: "Add" makes a new offer that a person confirms; "Not now" puts it away.

### 5c. The standing order that drifts: Harbourside Hotel

Switch back to the hotel. **Standing orders** → "Weekly lactose-free milk, hotel kitchen" (100 L of `469363` every week) → type **290** in "This week's quantity" → "Renew once at 290 L".

- 290 × `469363`, **€719.20**. "Needs your decision". P-08: "For the standing order “Weekly lactose-free milk, hotel kitchen”, 290 L this week against a median of 100 L over the last 6 renewals, more than the 25% tolerance of Harbourside Hotel."
- "Confirm order" → "Ordered for €719.20 net with approval by Hanna Laine, Harbourside Hotel: rule P-08 asked for a human and was accepted."
- Renewed at the stored 100 L it is within the tolerance: €248.00, prepared for a person (F-10).
- The same view at Kilo School shows a trend: "Your orders of Oatly Oat Drink Semi (470863) are growing: about 84 L in your last 3 orders, 70 L in the 3 before. Your standing order still says 60 L. Renew once at 84 L? From a synthetic order history." Do not order it in the demo: see "Next steps, and how the demo answers today".

**The two clocks:** identical for 5a, 5b and 5c.

## 6. The formula matters: Kallio Bakery

### 6a. `40 kg of Valio crème fraîche, product 477055, by Monday, for baking`

"For baking" sets the formula mark on the line ("Formula matters: the request says "for baking"."); the bakery's profile sets it too.

**The answer at the demo clock, two alternatives and nothing suggested as confirmed**
- **Asked:** 40 kg of `477055` (20 tubs of 2 kg), the formula to be kept. Valio Aimo does not confirm its stock.
- **First, "Alternative: quantity not confirmed":** 20 × `477055`, **€214.40** (F-01).
- **Last, "Alternative: quantity not confirmed, a substitute that does not keep the formula":** 27 cases of `477003` Valio Keittiön crème fraîche 150 g, organic, **€339.66** (F-01, F-11, F-12, P-01, P-05).
- **Said in a note:** "the request says the formula matters, and no substitute that keeps the formula can be ordered for Valio crème fraîche 2 kg lactose free (477055). Valio Keittiön crème fraîche 150 g lactose free, organic (477003) does not keep it and is offered only as a labelled alternative for a person to decide."
- **Needs a person:** Marko Heikkinen, for either.

**Rule F-11, in its words:** "Valio Keittiön crème fraîche 150 g lactose free, organic (477003) would replace Valio crème fraîche 2 kg lactose free (477055) where the formula matters (the request says so for this line), and the data does not show the same formula: it lacks CREAM, modified maize starch and thickeners (pectin), which the product asked for contains; contains pasteurised organic CREAM, which the product asked for does not; figures outside our tolerance: carbohydrate 2.7 g, not 3.8 g."

**Then:** "Confirm order" on the first → "Ordered for €214.40 net with approval by Marko Heikkinen, Kallio Bakery: rule F-01 asked for a human and was accepted."

**At the recording's clock** the labelled substitute is another product: 223 × `468277`, a 12% crème fraîche in 180 g pots, **€198.47** (F-01, F-11, F-12, P-05). The first option, the label and the note are the same.

### 6b. `60 litres of Arla Pro whipping cream, product 469346, by Monday, for cakes`, then `100 litres of whipping cream by Monday, for cakes`

**First the 60 L by product number: look, do not order.** The contents decide, not only the six nutrition figures.
- **Suggested:** the 48 L that are confirmed, **€276.96** (P-03: "Only 80% of the requested quantity is covered, below the 100% minimum (covered: 48 of 60 L)."). "No substitute that keeps the formula can be ordered: 48 L are offered and the rest is left for a person."
- **"Alternative: a substitute that does not keep the formula":** 48 × `469346` + 12 × `464727`, **€365.40** (F-11, P-01, P-05). F-11: "Arla Whipping cream 1 L ESL lactose free (464727) would replace Arla Pro Whipping cream 1 L UHT lactose free (469346) where the formula matters (the request says so for this line), and the data does not show the same formula: it lacks lactase enzyme, which the product asked for contains." P-05: "… a substitute that Kallio Bakery does not accept without a human."
- **A suggestion asks about the quantity:** "You usually order about 40 L of Arla Pro Whipping cream (469346): between 38 and 42 L in your last 6 orders. This request says 60 L. Order 40 L instead? For 40 L: €230.80. 48 L confirmed for Monday 16 November. From a synthetic order history."

**Then the 100 L by type: order it.**
- **Suggested:** confirmed whipping cream covers **85 of the 100 L**: 48 × `469346` + 37 × `464727`, **€549.65**. It needs Marko Heikkinen (P-01: "The total of €549.65 before tax is above the €300 limit per order of Kallio Bakery."; P-03: "Only 85% of the requested quantity is covered, below the 100% minimum (covered: 85 of 100 L)."). Here the two creams fill one request line by type, so neither is a substitute of the other; the summary still says they differ: "Arla Whipping cream 1 L ESL lactose free (464727) differs in formula from Arla Pro Whipping cream 1 L UHT lactose free (469346), which fills the same request line: lacks lactase enzyme."
- **"Alternative: quantity not confirmed":** 58 × `465193` (1.75 L), €338.14 (F-01, P-01).
- "Confirm order" → "Ordered for €549.65 net with approval by Marko Heikkinen, Kallio Bakery: rules P-01 and P-03 asked for a human and were accepted."

**Why this order.** With 6a and the 100 L ordered, the bakery's day stands at €764.05 of its €1,000. The 60 L request asked after that is answered with the day's rule as well (P-02 on both options), which is correct and not what this scenario is about.

**The two clocks:** identical for 6b.

## 7. Need → recipe → order: Kallio Bakery

**Type:** `A chocolate cake for 20 by Monday` in the same request box. The reader does not read it as a product request, so the page sends it to the recipe planner (`POST /v1/menus/plan` over REST, the tool `plan_menu` over MCP).

- **Read as:** "chocolate cake, 20 servings, by Monday 16 Nov." "The recipes and their amounts per serving are ours and illustrative, not Valio Aimo's."
- **The recipe for 20:** 0.4 kg flour, 0.4 kg sugar, 0.4 kg eggs, 0.3 kg butter, 0.1 kg cocoa powder, 0.3 L milk, 0.02 kg baking powder. One request of 7 lines, one offer; no ingredient is reported as impossible to source. Each ingredient says what is left over: "0.4 kg is needed and the pack holds 2 kg, so 1.6 kg is left over."
- **Suggested, confirmed stock only, a partial fill: €15.19** (€17.24 with tax). Flour `460856` (2 kg), cocoa `475703` (200 g), milk `463047` (1 L, low lactose, named as such), baking powder `466228` (700 g). "4 of the 7 ingredients are covered in full: flour, cocoa powder, milk and baking powder. Sugar, eggs and butter have no confirmed stock, so they are not in this option; option 2 offers them with a quantity Valio Aimo has not confirmed. What this option holds arrives by Monday 16 Nov. An order that is not complete goes to a person."
- **"Alternative: quantity not confirmed", all 7 lines: €23.44** (€26.60 with tax): sugar `468569` (1 kg), whole egg `468269` (1 kg), butter `464411` (500 g), and for milk and baking powder the cheaper unconfirmed `469477` and `476689`. F-01 on each of the five unconfirmed lines.
- **Needs a person:** Marko Heikkinen. F-07: "Nothing is offered for sugar, eggs and butter; what is offered arrives by Monday 16 Nov." P-03: "4 of the 7 items asked for are covered in full; nothing is offered for sugar, eggs and butter; Kallio Bakery asks for every item in full."
- **Then:** "Confirm order" → "Ordered for €15.19 net with approval by Marko Heikkinen, Kallio Bakery: rules F-07 and P-03 asked for a human and were accepted."
- **What it shows honestly:** the path from a sentence to a recipe to one order that waits for a person. The order is small and the packs are wholesale packs. 7 of the 9 products of the offer have their price and stock from the later recording, and the offer says so.

**The two clocks:** identical.

Also measured: `Beef stew for 80 by Monday` as the hotel needs 14.4 kg of beef chuck, 2.4 L of cream and 0.8 kg of butter; one request of 3 lines; first option 15 × `466988` + 3 × `463797` + 4 × `476740`, €272.89. Beef is sold by weight, so the total is an estimate and the order goes to a person (P-06). `Beef stew for 80 for tomorrow` names the earliest day: "Beef chuck, cream and butter cannot arrive by Friday 13 Nov: the offer holds them for Monday 16 Nov, and a person must accept the later date." A sentence that names an ingredient and no dish gets the dishes that use it: "With cream we have: beef stew, creamy chicken pasta, salmon with rice and berry quark dessert."

---

## The figures at both clocks

Demo clock: Thu 12 Nov 2026 14:15. Recording's clock: Sat 14 Nov 2026 02:52. All from the recording of 769 products, except row 7, which also reads the 394 baking products. Measured through `/shop/api/*` on Sun 15 Nov 2026; every row measured again in one run at 02:54–02:55 on commit `dbb8e13`.

| # | Request | Demo clock | Recording's clock | Who confirms |
|---|---|---|---|---|
| 1 | hotel, 1,000 L lactose-free milk | 435 L, €1,083.39 (P-01, P-03); alt. 1,000 × `464306` €1,010.00 (F-01, P-01); alt. 435 L + 565 × `463380` €2,580.64 (F-12, P-01); 2 of 26 left out | the same three options; 17 left out | Hanna Laine |
| 2 | ward, 200 L milk substitute | 200 × `464013` €402.00 (F-10) | the same | Jussi Nieminen |
| 2 | the same, ordering alone on | ordered by the agent, €402.00 | the same | nobody |
| 2 | hotel, ordering alone on, 302 L / 303 L | 302 × `469363` €748.96 ordered by the agent; 303 × `469363` €751.44 (P-01) | the same | nobody / Hanna Laine |
| 3 | hotel, 100 L of `473609` | 100 × `475224` €174.00 (F-12, P-05); alt. `473609` €137.00 (F-01); alt. 10 × `471690` €155.50 (F-01, F-12) | 100 × `475224` €174.00 (F-12, P-05); alt. `473609` €137.00 (F-01) | Hanna Laine |
| 3 | the same, confirmed data only | 100 × `475224` €174.00 (F-12, P-05) | the same | Hanna Laine |
| 4a | hotel, 100 L of `469512`, no milk | 100 × `473424` €236.00 (F-12); alt. `469512` €208.00 (P-04); alt. `473609` €137.00 (F-01, F-12, P-04) | the same | Hanna Laine |
| 4b | school, 20 L almond drink | alt. 20 × `465793` €47.60 (P-04); alt. 20 × `474864` €28.80 (F-01, P-04) | the same | Riikka Mäkelä, dietitian; with Päivi Korhonen for `474864` |
| 5a | hotel, 100 L lactose-free milk | 100 × `469363` €248.00 (F-10); alt. 100 × `464306` €101.00 (F-01); with the cooking cream €281.10 (F-10) | the same | Hanna Laine |
| 5b | bakery, 10 L whipping cream | 10 × `469346` €57.70 (F-10); alt. 6 × `465193` €34.98 (F-01); Valio Aimo suggests `473278` | the same | Marko Heikkinen |
| 5c | hotel, standing order at 290 L | 290 × `469363` €719.20 (P-08) | the same | Hanna Laine |
| 6a | bakery, 40 kg of `477055` | alt. 20 × `477055` €214.40 (F-01); alt. 27 × `477003` €339.66 (F-01, F-11, F-12, P-01, P-05) | alt. 20 × `477055` €214.40 (F-01); alt. 223 × `468277` €198.47 (F-01, F-11, F-12, P-05) | Marko Heikkinen |
| 6b | bakery, 60 L of `469346` | 48 L, €276.96 (P-03); alt. with 12 × `464727` €365.40 (F-11, P-01, P-05) | the same | Marko Heikkinen |
| 6b | bakery, 100 L whipping cream | 85 L, €549.65 (P-01, P-03); alt. 58 × `465193` €338.14 (F-01, P-01) | the same | Marko Heikkinen |
| 7 | bakery, chocolate cake for 20 | 4 of 7 lines confirmed, €15.19 (F-07, P-03); alt. all 7 lines €23.44 (F-01 × 5) | the same | Marko Heikkinen |
| reserve | hotel, 100 L lactose-free milk by tomorrow | "delivered Monday 16 Nov, 3 days later than asked": 100 × `469363` €248.00 (F-07); 100 × `464306` €101.00 (F-01, F-07) | "1 day later than asked", the same products and rules | Hanna Laine |

One pass in this order, each scenario ordered once at the demo clock (the first option each time; 4b rejected; 5b and the 60 L of 6b looked at only): hotel €2,493.69, ward €402.00, bakery €779.24, school nothing. Valio Aimo's back office then reads: "13 requests came in through the agent channel and 13 offers went out. 10 orders were prepared: 9 confirmed by a person (€3,674.93 before tax), 0 placed by the agent alone, 0 waiting for a person (€0.00), 1 rejected and 0 expired."

## Assumptions of this demo

What is ours in what you just saw, stated as such.

- **Who read the sentences here.** The script was measured with no model key: on `/shop` the fixed rules read every sentence. Over REST with the demo tokens and no key, the sentences of scenarios 1 and 2 are answered from a recording in `fixtures/agent/` and say so ("Read from a recording of gemini-3.6-flash made on 14 Nov 2026 …; no model was asked.", or "Read from an answer written by hand, not by a model." for the brief's full sentence). With a key a model reads first and the fixed rules are its check and its fallback (see "Who reads the sentence"); a model never decides what may be ordered.
- **Recorded data, and a clock we chose.** 769 products, plus 394 baking products. A product outside the recordings has no price or stock here, and the offer says so. No regular milk has confirmed stock in the recording: a plain "milk" request is filled with a named lactose-free or low-lactose milk, said in the offer (the cake's milk line shows it).
- **Synthetic customers and illustrative limits.** Names, people, limits and order histories are ours (8 past orders per customer, 16 for the ward), and every suggestion says "From a synthetic order history". A renewal made on `/shop` does not join that history.
- **No login on the page.** Whoever opens `/shop` acts as the customer's person, the dietitian included. That an agent cannot approve is enforced over REST and MCP, where the token says who calls. The pages are served only in the `dev` and `demo` environments.
- **The order step is ours.** The Valio Aimo mock has no order endpoint, by design: "ordered" is a signed record in this gateway's order book and its log, and commits nobody. The signature is the gateway's, with a demo key generated at start; it is not Valio Aimo's.
- **Evidence pages are recordings** (`fixtures/evidence/`: 92 recorded answers, of which 30 are shown as evidence). A product with no recorded page shows no page; nothing is fetched during the demo.
- **The recipes are ours:** ten illustrative ones; the buyer names the dish.

## Next steps, and how the demo answers today

None of these exists yet; each line says what the demo does instead.

- **A demo agent that orders alone over REST and MCP.** Today it is shown on the page, with the switch in Settings (scenario 2).
- **A last-minute order that arrives in time.** At the demo clock "tomorrow" is Friday 13 Nov, and nothing in the recording can arrive by then. `100 litres of lactose-free milk by tomorrow` (hotel) is answered with the earliest date as an alternative a person accepts: "Alternative: delivered Monday 16 Nov, 3 days later than asked", 100 × `469363`, €248.00 (F-07: "The needed-by date 2026-11-13 is not met for this option: … arrives on Monday 16 Nov."), and the same for the unconfirmed 100 × `464306`, €101.00 (F-01, F-07). At the recording's clock tomorrow is Sunday 15 Nov and the label reads "1 day later than asked".
- **A scheduler for standing orders, and checks before the kitchen asks.** Today a stock-out, a suggestion and a drift are found when a request or a renewal comes in, and a person presses "Renew once".
- **New and seasonal products, and recipes around a seasonal ingredient.** The product file has no mark for "new" or "seasonal", so today Valio Aimo's own suggestion is a related product of something the customer already buys.
- **A nutrition standard for schools and hospitals.** Today, at the ward and the school a substitute whose formula or nutrients differ goes to the dietitian (F-11, F-12); she decides.
- **Renewing the school's whole standing order in one step.** "Renew once at 84 L" renews all three lines: its usual milk `462775` and yoghurt `464517` state nothing about tree nuts, peanuts or sesame, so today only the oat drink (84 × `470863`, €117.60) is in the first option and every fuller option goes to the dietitian. Do not order it in the demo.
- **Valio Aimo's own signature, people signing in with their own accounts, an order message Valio Aimo's systems can take:** see "Next steps" in the [README](../README.md).

## If something goes wrong

- **A total or a rule differs from this page:** the customer's book was not empty, or a scenario was ordered twice. A sentence about the day's limit is the usual sign. Settings → "Reset this customer's demo".
- **The clock strip does not say Thursday 12 November 14:15:** `TTA_DEMO_CLOCK` is not set. The answers are then the recording's-clock ones, given with each scenario and in the table.
- **A sentence gets a question back:** it is not one of the sentences above and the reader could not read all of it, or a model's reading did not match the text. Type it as written here.
- **"Too many requests":** the limits per minute are per browser and per address (60 lookups a minute for one address). Wait for the seconds the message names.
