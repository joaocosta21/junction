# A2a — review of the recipe logic and the standing orders (14 Nov, 15:05)

Scope: commit `fa07e39` and the fixes after it, at `7f09ce7`. All runs are offline (replay, capture `2026-11-14-demo`, clock pinned to 2026-11-14 02:52, fresh data folder per script, rate limit raised in the test client only). "Reproduced" means a script ran it; "proved" means read from the code. Scripts: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/A2a/` (`m1.py`–`m4.py` menus, `s1.py`–`s5.py` standing orders, `h.py` and `run.sh` to run them).

## 1. In five lines
- 16 findings: 1 CRITICAL, 4 HIGH, 5 MEDIUM, 6 LOW. No 500 was found; no wrong arithmetic was found.
- Worst 1 (CRITICAL, standing orders): renewals that wait for approval count as history. After three unapproved renewals at 150 L, the fourth 150 L renewal is ordered by the agent alone. Reproduced on the API, and on the page with the demo standing order.
- Worst 2 (HIGH, menus): 30 of the 36 two-dish menus need more than 5 request lines, and the gateway refuses them ("at most 5 lines"). Lasagne plus oven pancake fails on the page.
- Worst 3 (HIGH, menus): a stand-in can add an allergen and nobody is told. Rice porridge for 5,000 gets 1,500 L of an oat drink that declares gluten and oats in place of milk; neither the plan nor F-09 says so.
- Also HIGH: ingredients that cannot be sourced drop out and the agent may order the rest alone; and without "confirmed only" the plan says no quark can be offered while the first offer holds one.

## 2. Findings

### CRITICAL
**S-1 · `src/tta/standing/history.py:21` and `:45-51` · A renewal whose order still waits for approval counts as history, so the agent's own unapproved requests move the median that P-08 judges against.**
- Reproduced (`s1.py`, `s2.py`, API, hotel agent): standing order of 100 L of `469363`; three renewals at 100 L (ORDERED); then four at 150 L. Results: PENDING_APPROVAL (P-08, median 100 over 3), PENDING (median 100 over 4), PENDING (median 100 over 5), then **ORDERED, AUTO, no rule fired**: "is within the 25% tolerance: 150 L this week against a median of 125 L over the last 6 renewals". Nobody approved anything.
- Reproduced on the page (`s4.py`): load the demo, renew at 150 L four times. The page shows medians 100, 101, 103, then "within the 25% tolerance ... median of 126 L" and "✓ Ordered ... The agent placed this order alone".
- Side effect, reproduced (`s2.py`): when the approver then approves the first waiting renewal, its stored decision reads AUTO, "The agent may place this order alone", on an order placed with human approval.
- Smallest fix: in `_counts`, keep a real renewal only when its order is ORDERED (synthetic ones stay). One line plus one test and the hand-back's assumption line. 0.5 h. Optional: refuse a renewal while another of the same standing order waits (0.5 h).

### HIGH
**M-1 · `src/tta/menus/planner.py:101` with `src/tta/api/service.py:55` · A menu whose recipes need more than 5 product types is refused, and that is most menus.**
- Counted (`m3.py`, over the shipped `recipes.yaml`, no kitchen stock): 30 of 36 pairs of dishes need 6 lines or more; lasagne alone needs 5.
- Reproduced (API and page): lasagne 50 + oven pancake 50 → HTTP 422, "In this demonstration a request has at most 5 lines; this one has 7. Send the others as another request." The page gives no way to do that.
- Smallest fix: let the planner's offers use the contract's limit (20) instead of the demo limit, or raise `MAX_DEMO_REQUEST_LINES`. 0.5 h, plus a latency check (five large plans took over 120 s in one of my runs; I did not time a 7-line plan).

**M-2 · `src/tta/menus/planner.py:59-82`, `src/tta/policy/rules.yaml:273-282` · A recipe stand-in is never compared for allergens, and no sentence names what it adds.**
- Reproduced (`m2.py` case A, `m3.py`): rice porridge, 5,000 servings, confirmed only, by 2026-11-16. Milk covers 84%, so `plant_drink` stands in: 1,500 × `464320` Oatly iKaffe Oat drink. `GET /v1/products/464320` declares `AW` and `GO` CONTAINS; the milks declare `AM`. Verdict APPROVAL by F-09 and P-01. F-09 says only "so a person checks that the dish still works"; the plan says "it is not dairy and the porridge is less rich".
- For a product substitute the same case is blocked (Valio's B6: yes). For a recipe stand-in the approver is not told.
- Smallest fix: name the stand-in product's declared allergens in the plan sentence and in F-09's fact (1 h). Full: compare with the recipe type's products and send to the dietitian or block (3 h).

**M-3 · `src/tta/menus/planner.py:76-79` and `:112-114` · Ingredients that cannot be sourced leave the final offer, and nothing tells the policy: the agent may order the rest alone.**
- Reproduced (`m2.py` case E, `m4.py` page): oven pancake, 50 servings, by 2026-11-16. Eggs, flour and sugar are "cannot be sourced"; the final offer is 8 × `463047` milk, €16.08, verdict **AUTO**, button "Order this option".
- In replay this is the normal case: `recipes.yaml:18-21` says only 104xx and 18720 are in the capture, so every dish has an ingredient outside it unless the kitchen's stock covers it.
- Smallest fix: a request flag set by the planner when anything is unsourced, read by a fixed rule that asks the purchasing manager (1.5 h). Page-only version: replace the order button by a warning when `cannot_be_sourced` is not empty (0.5 h; the API verdict stays AUTO). If V8 switches automatic orders off, this drops to MEDIUM.

**M-4 · `src/tta/menus/plan.py:40-44`, `src/tta/menus/wording.py:85-90` · Without "confirmed only", the plan says no quark can be offered, although the first offer offers one, and swaps the recipe's own ingredient for another type.**
- Reproduced (`m3.py`): the demo menu without `require_confirmed`. First offer, option 2 (ALTERNATIVE_UNCONFIRMED): 3 × `477044` Valio quark 5 kg, fill 1.0. The plan: "Quark (maitorahka): none of 6 products can be offered by Mon 16 Nov 2026 (6 order cut-off passed)" and yoghurt stands in. The final offer has no quark line, so none of its options can hold quark.
- Cause: `fill_of` reads only `options[0]`. Both routes end with a human (F-01 or F-09), but the buyer never sees that the real ingredient can be had. This is the opposite of V10 (keep the formula).
- Smallest fix: a line fails only when no option of the first offer covers it; otherwise keep the recipe's type and say "quantity not confirmed". 1 h. The demo (confirmed only) is not affected.

### MEDIUM
**M-5 · `src/tta/ui/menu_page.py:49`, `src/tta/ui/templates/menu.html:92` · Every unsourced ingredient is labelled "Cannot arrive in time", whatever the reason.** Reproduced on the page: eggs "✕ Cannot arrive in time ... (30 not in the recorded capture)". With `AM` excluded the API sentence was reproduced, "cream: none of 44 products ... (44 declares an excluded allergen)", and the same status gets the same label (proved from `menu_page.py:49`). The label is false in both cases. Fix: label "Cannot be sourced"; say "not in this demo's recording" when that is the only reason. 0.25 h.

**M-6 · `src/tta/menus/planner.py:80-81` (hand-back assumption) · A stand-in replaces the whole amount, not the missing part.** Reproduced: 84% of the milk can be offered, and the plan orders 1,500 L of oat drink and no milk. Against V10 this is the wrong default. Fix: order what the recipe's type covers and stand in for the rest. 2 h; or state it on the page, 0.25 h.

**S-2 · `src/tta/standing/service.py:185-204`, `src/tta/policy/drift.py:45` · Nothing checks the cadence.** Reproduced: a weekly standing order renewed seven times at the same pinned instant, the first three at 100 L each ORDERED, AUTO (`s1.py`); on the page the demo standing order renewed three times at 100 L, each "within the 25% tolerance: 100 L this week against a median of 100 L" (`s5.py`). Repeating a renewal triples the week's quantity and P-08 sees no drift: `cadence_days` is stored and never read by a check. Fix: a fact "renewed again within `cadence_days`" that fires P-08 (1 h). Note: the clock is pinned in replay, so a strict check would also stop the demo's second renewal; say so on the page or exempt replay.

**S-3 · `src/tta/contracts/request.py:104-106`, `src/tta/offers/deps.py:45-51` · P-08 binds only an agent that names the standing order.** Reproduced (`s3.py`): with a history of 100 L, `POST /v1/offers` for 290 L naming the standing order → APPROVAL (P-08); the same request without `standing_order_id` → AUTO, and `POST /v1/orders` → 201 ORDERED. It is stated as design ("it can only add a check"), but a judge of "autonomy and controls" will ask. Fix: say it in `docs/ASSUMPTIONS.md` (0.25 h); matching a request to a standing order by product is 2 h.

**S-4 · `src/tta/policy/drift.py:86-92` · Cost drift is compared per product id, so a renewal filled by a different, dearer product is "not compared".** Proved from the code; `tests/policy/test_standing_drift.py:171` pins it as intended. A standing order by product type can change product and price with no P-08. Not reproduced: replay prices are fixed. Fix: also compare net per unit of each request line. 1 h.

### LOW
- **S-5 · `src/tta/policy/drift.py:121-122`, `:168-169` · The ratio is rounded to 4 places before the comparison.** Reproduced: 125.004 L against a median of 100 L → `drift_ratio` 0.25, "is within the 25% tolerance". Fix: compare the unrounded ratio. 0.25 h.
- **S-6 · `src/tta/standing/service.py:80-87` · The template keeps an absolute `needed_by`.** Reproduced: a standing order created with `needed_by` 2026-11-10 is accepted (201); its renewal answers "No order was placed ... nothing can arrive by Tuesday 10 Nov". With a live clock any dated weekly order works once. Fix: refuse `needed_by` in a standing order's request. 0.5 h.
- **S-7 · `src/tta/standing/service.py:125-132` · A standing order for a product that is not in the catalog is created.** Reproduced: 201 for product `999999`; the renewal then answers 404 `unknown-product`. Fix: check the ids in `create`. 0.25 h.
- **S-8 · `src/tta/standing/service.py:96` against `src/tta/policy/drift.py:140` · The history keeps what was covered, the check compares what is requested.** Proved from the code: after partly filled renewals, the same request reads as a drift ("100 L this week against a median of 60 L"). Not reproduced. Fix: keep the requested quantity on `RenewalLine`. 0.5 h.
- **M-7 · `src/tta/menus/needs.py:95`, `:107` · Kitchen stock is per product type, not per name term.** Reproduced: 3 L of "cream" in stock → "In stock: the kitchen holds the 3 L of cream (whipping)". Cooking cream counts as whipping cream. Fix: say "cream of any kind" on the form, or one field per term. 0.25 h.
- **M-8 · `src/tta/menus/plan.py:186` · The note names dishes that have no line.** Reproduced (`AM` excluded): "The final offer has 1 line for Beef stew (120 servings) and Berry quark dessert (marjarahka) (120 servings)"; the one line is the stew's beef. Also "(1 servings)". Fix: take the dishes from the final lines. 0.25 h.

## 3. Checked and found right
- Arithmetic: every amount per serving is a `Decimal`; servings × amounts are exact for all ingredients at 1, 3, 7, 10, 33, 120, 333, 999 and 5,000 servings. Rounding up to whole L or kg with a minimum of 1 (0.18 kg → 1, 21.6 → 22, 3.6 → 4). Stock is taken in menu order and never beyond the need; stock above the need gives no offer and "nothing is ordered".
- The demo: €476.48, 12 × `464615`, three offers, F-09 and P-06 fire, on the API and the page. F-09 fires in the running system (the hand-back's open gap is closed).
- Menu input: empty menu, 0 or 5,001 servings, a dish twice, an unknown dish, stock in the wrong unit, an approver's token → 422 or 403 problems. Page: bad servings, stock or date → 422 page with the reason. The order button twice with one key → the same order.
- Menu exclusions (`AM`, STRICT) remove every dairy line and alternative; the plan lists them; no error.
- Two request lines for one product share its stock (300 + 84 of 384): no double allocation.
- Standing orders, access: another buyer's id → 404 on the routes, 422 on an offer naming it; approver cannot renew (403) but can list; supplier 403.
- Standing orders, input: 0, 2 or bad quantities, zero, negative, text, too large, unknown id, a template naming a standing order, empty name, cadence 0 → 422 or 404. Page: bad quantities → 422 page.
- Drift: no history and 1 or 2 renewals → "too short", P-08 silent; exactly 25% → not over; 26% below → fires (the profile says above or below); medians over an even count are exact (125, 126); a rejected renewal leaves the history (reproduced: median 125 over 6 after one rejection); the renewal being decided is left out of its own history (proved from `orders/checking.py:100-102`, not separated by my runs); a renewal with no option places nothing, says why, and records the event.

## 4. Not checked
- PostgreSQL (`postgres.py`, `005_standing_orders.sql`): needs the outside service. I only read the SQL.
- Live mode: the machine clock, `renewed_at` order with real times.
- Unit-price drift end to end, a zero median, standing orders with several lines or by product type: replay prices are fixed and time ran out. Read only.
- A final offer that grows past 5 lines after stand-ins split a line (`planner.py:71-82`): possible from the code, not built.
- A `TtaError` raised inside the page's renewal (`standing_page.py:191`: rate limit, stale offer): not triggered.
- Two renewals truly in parallel; the supplier's view of the standing events; `standing.html` line by line.
- The tests were read by name and four bodies; I did not run pytest (machine load). Gaps seen: no test with a waiting renewal in the history, none with more than 5 menu lines, and the demo menu is only tested with `require_confirmed: true` (`tests/menus/conftest.py:31`).
