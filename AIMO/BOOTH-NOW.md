# At the Valio Aimo booth — everything to ask and confirm (Saturday 14 Nov)

Part A: the questions still without an answer (23). Part B: decisions we took last night on our own about Valio's data or business — confirm each or tell us what is right (14).
The full wording, with a worked example for each, is in `AIMO/OPEN-QUESTIONS.md` and `AIMO/BOOTH-QUESTIONS.md` (same ids). Demo to show: https://joaocostared--trusted-trade-agents.us-east.modal.run

## A. Open questions

**First**
1. **SCOPE-1** — Of the six example scenarios in your brief, which would you most like to see an agent do on top of what we built: the buyer setting its agent's limits, standing-order drift, recipe to order, or your own selling agent? *(Follow-ups: do customers set their own limits and approvers today? May we define a standing order ourselves? How would your agent know a product is new or seasonal — no such field, no recipes in the data?)*
2. **T03-1** — `471881`, Oddlygood Barista oat drink 0.5 l, is named "gluten free" and has the gluten-free claim, but declares cereals containing gluten (`AW`); the 1 l packs do not. Is that expected? *(It is in our demo: we reject it.)*
3. **Q1** — We read `closingTime` literally: once it has passed, the product cannot arrive on `availableDate`. Right? *(It excludes 17 of the 30 lactose-free milks tonight.)*
4. **Q7** — What limits do real customers set: a euro cap per order, an approved product list, approver roles? One example is enough.
5. **Q4** — When you accept an order today, what is committed at that moment: the price, the quantity, the delivery date?

**Reading the data**
5b. **ALMOND-1 — ask this one** — `465793` Alpro Barista Almond drink 1L declares tree nuts (`AN`) as *free from*, but its own ingredient list says "Water, ALMOND (2.5%), Sugar, Fructose, Acidity regulators (Potassium phosphates), Calcium…". Which is right? *(Today our gateway trusts the declaration, so a no-nuts buyer's agent would order it alone.)*
6. **Q2** — Do `X99` ("no declarable allergens") and `UNDECLARED` have their GS1 meanings in your data?
7. **T03-2** — 176 products say a family is "free from" while declaring one of its members (a gluten-free loaf with wheat; Toblerone "free from tree nuts" with almonds). Gluten-free wheat starch, and a data error?
8. **Q5** — 46% of the catalog has no allergen statement. Does no data mean "declared nothing", so an agent must treat it as unknown?
9. **T02-1** — `allowedLotSize` is 0.01 on nearly every countable product (cases, cartons). Does 0.01 mean "no step"?
10. **T02-2** — Is `comparisonPrice` the catalog price divided by the content of one sales unit (drained weight where there is one)?
11. **Q10** — The API's sales unit differs from the product file's on some lines. Which unit do the price and the amount refer to?
12. **T07-5** — Is a listed substitute meant across sales units? `473609` is sold by the piece, its listed substitute `471690` by the 10-litre case.
13. **Q8** — Is a deposit inside `catalogPrice` or charged on top, and at what value per code?
14. **Q9** — Is a variable-weight product invoiced at the weight ordered or the weight delivered?
15. **Q11** — Is the category code a hierarchy (which digits are levels)? Can we have the category names?
16. **Q12** — What does delivery reliability measure, and does a missing value mean no history?

**The mock and the judging**
17. **Q6** — When stock covers only part of an order line, what happens today: partial delivery, a substitute, or the line is dropped?
18. **Q13** — Is our call volume fine during judging? One offer is 2 calls; the deployed demo makes at most 6 live looks a minute and 120 in all.
19. **T01-1** — Python's default User-Agent got 403 from Cloudflare; a named one got 200. Is a named User-Agent the rule for agents?
20. How and when do you judge — at our table, the video, or the deployed link? Will the mock stay up unchanged until then?
21. Do exception cases have to run live in the demo, or does a documented, tested rule count?
22. The brief mentions webshop test accounts. Are they available?
23. The repository must be public under MIT. May the datasets and a few recorded mock answers stay in it?

## B. Decisions we took — confirm or correct

1. **What the agent may order alone:** only when price, quantity and allergens are confirmed, the delivery date is met if the buyer gave one, the quantity is covered, the spend is within the buyer's limits, and no substitute is outside what the buyer allows. Anything else goes to a named human. Is that the right line?
2. **Very large stock (≥ 999,999, Terminal or Stock) = quantity not known:** always to a human, never the suggestion. *(You told us this on Friday — just confirm it still holds.)*
3. **A cut-off exactly at "now" counts as passed.**
4. **A nutritional claim is never an allergen statement:** lactose-free milk still "contains milk".
5. **"Milk" leaves out sour milk, the coffee drink and soy yoghurt, but keeps coffee milks** (`463380` Arla Café milk supplies 565 of the 1,000 litres in our demo). Would a buyer asking for milk accept coffee milk?
6. **A substitute may never add an allergen the original does not declare, or raise "may contain" to "contains"** — blocked for every buyer.
7. **A substitute that drops a dietary claim (lactose-free → regular, gluten-free → regular) always goes to a human.** We count as dietary: lactose-free, low-lactose, gluten-free, wheat-free, egg-free, soy-free, vegan, vegetarian. Others (no preservatives, no added sugar …) are only mentioned. Right list?
8. **Oats under a "no gluten" request go to a dietitian; gluten-free wheat starch is rejected.**
9. **A product carrying only `X99` goes to a dietitian for a strict buyer.**
10. **Single-serve packs (5 cl or 50 g or less) are left out of a bulk request** (`463203`, 100 × 2 cl milk, is excluded from "1,000 litres of milk").
11. **"By Monday" means the first Monday after today**; we send today's date as `requestedDate` (the mock ignores it) and compare `availableDate` ourselves.
12. **Before an order we look again:** any price change, a new cut-off or a later delivery date cancels the offer and builds a fresh one; stock that moved but still covers the order does not.
13. **What Valio sees in its view of the audit trail:** what was asked of your data, what was offered and ordered, the figures each order relied on, the agent's identity, and whether it acted alone or with a human — but not the buyer's limits, allergen exclusions, approver names or notes. Is that what you would want to see?
14. **"Ordered" means recorded in our order book; it commits nobody**, because the mock has no order endpoint. Is that how you want it described?
