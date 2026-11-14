# P15 — Suggestions from a customer's past orders (the brief's "recommendation logic", V2, V8, V10)

Agent P15, Saturday 14 Nov, replan round. Nothing in the repository was changed except this file. Scratch scripts and outputs: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/P15/` (`dump.py`, `analyse.py`, `run.py`, `run2.py`, `run3.py`, `run*.txt`).

How the figures were made. "Measured" = run offline with the brief's recipe (replay, capture `2026-11-14-demo`, clock pinned to Sat 14 Nov 02:52, fresh data folder per script). "Capture" = the 769 products of that recording, classified with the app's own code. Nutrition figures are per 100 ml or 100 g and come from P10's extract of the whole product file (`.../replan/P10/extract.jsonl`). Every history, count such as "7 of 8" and threshold below is a **proposal**: no customer history exists yet.

## 1. In five lines
1. Today nothing suggests anything. Past orders are read only for the day's spend and for rule P-08. An offer has no place for a suggestion (measured: its keys are `options`, `excluded`, `notes` and ids).
2. Recommend one small list, `suggestions`, on every offer: at most 3, each with a kind, a product, a quantity, one sentence with its numbers, the evidence behind it, and whose interest it serves. Computed by the gateway with medians and counts. No model decides one.
3. A suggestion never changes an order. Accepting it builds a new offer, which goes through the same rules and the user's confirmation (V8). The buyer's allergen exclusions, the dietary claims (B7), the formula (V10) and "stock not confirmed" apply to a suggestion exactly as to an offer line.
4. Minimum (2.75 h; a 2.0 h floor needs no other agent's work): "you usually order this with it, did you forget it?" Measured demo: the hotel asks for 100 L of milk `469363` (€248.00); the gateway suggests 10 L of cooking cream `463797`; one click gives €281.10. The next 0.75 h adds "Not now", remembered, and the accepted and dismissed audit events.
5. Full (+7.25 h): larger pack of the same drink (measured: €106.80 → €88.80 for 60 L of Oatly iKaffe), a quantity trend on a standing order, a remembered substitute decision, and P1's and P10's suggestions in the same shape. An upsell that serves Valio is documented, labelled and off by default.

## 2. What exists today (verified)
- **No suggestion code.** `grep -rn "suggest" src/tta` over `*.py`, `*.yaml`, `*.html` finds 1 line, a comment (`src/tta/offers/options.py:149`).
- **Who reads past orders.** The day's spend (`src/tta/orders/spend.py:30-41`, `orders/service.py:122`), the order list (`api/service.py:255-262`) and the standing-order history for P-08 (`standing/history.py:36`). Nothing else.
- **P-08** compares a renewal with the median of the last 6 renewals and needs 3 (`src/tta/policy/drift.py:27-28`). It compares the quantity per line and the unit price per product. A past renewal line already stores its price (`contracts/standing.py:69-76`, `unit_net_price_eur`).
- **One history, one customer:** six synthetic weeks of `469363` (`standing/demo.py:28`). `GET /v1/standing-orders` for the hotel returns `[]` at start (measured).
- **A standing order cannot be changed.** The service has create, set up, list, find, get, renew (`standing/service.py:125-185`). A renewal may carry this week's quantities (`contracts/standing.py:145-151`); the stored quantity stays.
- **The offer** (`src/tta/contracts/offer.py:186-197`): free-text `notes`, no structured hint. Measured on 10 requests: `notes` was `[]` every time. The page prints notes at `ui/templates/_result.html:225-226`.
- **The substitute ranking** (`offers/substitutes.py:253-266`) has no memory. Measured: for 40 L of Arla whipping cream `464727` (37 confirmed) the offer fills the 3 L missing with `463975`, a 15% vegetable mix, verdict AUTO. The other whipping cream, `469346`, is rank 6 of the candidates.
- **Audit events** are an enum of 17 types (`contracts/audit.py:25-44`); each event has `type`, `actor`, `sentence`, `facts`, `rule_ids`, `hash` (measured). The supplier reads its own sentences (`audit/supplier_sentences.py`): for the buyer's "within the €750 limit per order" Valio reads "the agent may place this order within its authority" (measured).
- **MCP** returns the same `Offer` object (`api/mcp_surface.py:218`), so a field added to the offer reaches MCP with no extra tool.
- **The guards a suggestion needs exist:** `allergens/exclusion.py:70` (`check_exclusions`), `allergens/substitution.py:25` (`check_substitute`: adds no allergen), the dietary claims of `offers/substitutes.py:53-64`, the availability states, rule F-01. Measured: the ward asking for the cheaper oat drink `470863` gets it excluded, "The product declares that it contains cereals containing gluten (AW), which the buyer excludes." The hotel asking for 40 L of `465193` (quantity not confirmed) gets verdict APPROVAL, fired F-01.
- **Not in the data:** a "new since" or seasonal mark on a product. A grep of `AIMO/docs/*.md` for created, launch, seasonal, validFrom finds only the price validity. I did not scan the product file for it. So "new product" cannot be computed today: assumption until someone checks the file.

## 3. What Valio's answers change
- **V2** ("per user based on the user pattern"): a pattern must change what the gateway answers. P1 covers the usual product and quantity. This proposal covers what the pattern lets the gateway *say* beyond the request.
- **V8**: every suggestion is a proposal to a person. Nothing is added to an order without a click, and the order still needs the user's confirmation (P8).
- **V10**: a cheaper or larger item is suggested only when it keeps the formula (P10's measure). Without that measure no replacing suggestion ships.
- **V5**: below a threshold the gateway stays silent or asks. It does not guess.
- **B7**: a product that loses a dietary claim is never a suggestion. It stays a last resort of the substitute path, with a human.
- **B13** ("all the steps and decisions"): suggestions and what the customer did with them are events both readers can see.
- **The mentor's goal** (attract customers): a suggestion with its evidence is a reason for a buyer's agent to prefer this wholesaler. A sales push without evidence is the opposite.

## 4. Options and recommendation

### 4.1 The signals
One window for all: the customer's last **8 orders** (P1 generates 8 weeks). Named values are proposals. "Order" = one past order with its date and lines; an order a human rejected or that expired is left out, as P-08 does (`standing/history.py:20-21`).

| Kind (`kind`) | Computed how | May speak from | Stays silent when | Serves | Who builds it |
|---|---|---|---|---|---|
| `USUAL_PRODUCT` | For a product type: the product in the largest share of the orders that hold the type. | 3 orders of the type and a share of 60% or more (`USUAL_PRODUCT_MIN_SHARE`) | No product reaches the share (two milks alternate): then the gateway asks which one (V5). The usual product fails a guard of 4.3. | Buyer | P1's C4; same shape |
| `USUAL_QUANTITY` | Median quantity of the product over its last 6 orders (the window of P-08). The sentence gives the range. | 3 orders (`MIN_RENEWALS_TO_JUDGE`, `drift.py:28`) | Fewer than 3. Never ordered alone on a median: always confirmed. | Buyer | P1's C5 |
| `REORDER_DUE` | Gaps in days between deliveries of the product. Regular when 75% of the gaps are within 1 day of the median gap. The weekday is the most frequent one. Due when last delivery + median gap falls within the next 3 days and no order, placed or waiting, holds the product for that date. | 4 orders (3 gaps) | Irregular gaps (the catering type). An order already exists. Dismissed for this cycle. | Buyer | P1's C6; rule added here (R8) |
| **`FORGOTTEN_ITEM`** | For a product A of the request and a product B not in it: support = past orders holding both; confidence = support ÷ past orders holding A. Quantity = median of B in those orders. | support 4 or more and confidence 0.75 or more (`COMPANION_MIN_SUPPORT`, `COMPANION_MIN_CONFIDENCE`) | B, or another product of B's type, is in the request (the buyer chose). B is in an order placed or waiting for the same delivery date. B fails a guard. Dismissed. | Buyer | **R1–R4 (minimum)** |
| `QUANTITY_TREND` | Last 6 orders of a product: median of the last 3 against the median of the 3 before. | 6 orders; change of 15% or more (`TREND_MIN_CHANGE`) and 4 of the 5 steps in one direction | Mixed direction. The stored standing quantity is already within the profile's drift tolerance of the recent median. | Buyer | R7 |
| `PRICE_CHANGE` | Today's price against the median price paid in the last 6 orders (P-08's price check, `drift.py`). | 3 priced orders; rise of 5% or more | A fall (not said in the minimum). No history price. | Buyer | R6 |
| `CHEAPER_SAME_FORMULA` | P10's four conditions: adds no allergen, loses no dietary claim, keeps the formula, saves 5% or more per litre or kg. Shown at most once, the largest saving. | 0 orders (a catalog fact). With history the sentence adds "on your usual 40 L a week". | The formula differs or cannot be compared. The line matters by formula and the brand differs (P10's decision 3). | Buyer | P10's F6; same shape |
| `LARGER_PACK` | Same product in another pack (P10's outcome "same product in another pack"): larger pack, 5% or more cheaper per litre or kg, the quantity is a whole number of packs with at most 10% over, confirmed stock covers it. | 0 orders | The request asks for portion packs (`pack`, `contracts/request.py:79`). Dismissed ("opened cartons do not keep"). | Buyer | R5 |
| `SUBSTITUTE_REMEMBERED` | When a line needs a substitute: a candidate this customer accepted or refused for the same original before. Refused: never the suggested one, shown with "you refused this on …". Accepted: named, and it wins a tie only after allergens, claims and formula. | 1 decision | It never removes a sign-off (P-05, F-08, P10's F-10). | Buyer | R9 |
| `FROM_SUPPLIER` | A product the supplier wants seen: the organic or labelled version of what the customer buys, or a new product once the data marks one. | — | Off unless the buyer's profile switches it on. Never first, at most 1. | **Supplier** | R11, documented only tonight |

Why confidence and not lift for the forgotten item: an item in every order has lift 1 and is exactly the item a kitchen must not forget. Lift belongs to finding related products across customers, which needs many customers (4.4).

### 4.2 Whose interest, and how a suggestion earns trust
- Every suggestion has `serves: BUYER` or `SUPPLIER`. Nine kinds serve the buyer: a complete order, a saving, less retyping. One serves the seller, and the brief asks for it as an example ("Proactive selling agent", `AIMO/CHALLENGE.md:44`).
- The reason is a sentence with its numbers and its source: "In 7 of your last 8 weekly orders with this milk you also ordered Arla Pro Cooking cream 10% (463797), usually 10 L. It is not in this request. 114 are confirmed for Monday 16 November; 10 L adds €33.10. Synthetic history."
- The evidence is in the answer, so an outside agent can check it: the orders counted, the orders matching, the dates of the window, the values the median was taken from, the threshold names and values.
- A suggestion that costs more says so first ("€0.34 more per litre").
- The customer can dismiss it. The dismissal is an audit event, and the audit trail is the memory: the gateway reads it back (`Store.list_audit_events`, `contracts/ports.py:181`) and stays silent for the same buyer, kind and product for 28 days (`DISMISSAL_DAYS`). No new table.
- At most 3 per offer, buyer kinds first, the supplier kind last and apart, under "Suggested by Valio Aimo, not from your orders".
- **What Valio may see** (B13: "all the steps and decisions"). Proposal: Valio's view shows that a suggestion was made, its kind, product, quantity, the counts, and whether it was accepted or dismissed. It does not show the dismissal note, the stock on hand, the recipes or the limits (already hidden today). Reason: the counts come from orders placed with Valio, which Valio already holds (its webshop has "your order history and order templates": quoted from P1 section 4.1, not checked by me). Each suggestion records its `evidence.source`; evidence from another supplier's orders would never go to Valio. No customer's history is used for another customer tonight. **DECISION 3.**

### 4.3 The rules a suggestion can never break
One guard function runs on every suggestion before it leaves the gateway. A suggestion that fails is dropped, and the drop is a fact of the audit event.
1. **It never changes an order.** A suggestion is not a line of any option and is in no total. Accepting it builds a new offer from an amended request. That offer meets every rule again and waits for the user's confirmation (V8, rule P-00).
2. **It never widens authority.** Accepting is not an approval. No limit, exclusion or fixed rule moves.
3. **Allergens.** The product passes the request's and the profile's exclusions with the same check as an offer line (`check_exclusions`). Under STRICT, no data means not suggested. A replacing suggestion adds no allergen to what it replaces (`check_substitute`, rule F-05).
4. **Dietary claims (B7).** A replacing suggestion keeps every dietary claim of what it replaces and every claim the request requires. Otherwise it is not a suggestion.
5. **Formula (V10).** A replacing suggestion keeps the formula by P10's measure. "Different" and "not known" are never suggested unasked.
6. **Stock not confirmed.** Suggested only with that said in the sentence and `stock_confirmed: false`, and never ahead of a confirmed one. Ordering it needs a human (F-01, measured).
7. **It can be ordered.** Cut-off passed, not deliverable, out of stock or blocked: not suggested. For a usual item the gateway says so as a note instead.
8. **A doubt means ask (V5).** Below a threshold: silence, or one question when the request depends on it. A quantity is a median of 3 or more orders, never a guess.
9. **Synthetic history is said**, in the sentence, in `evidence.synthetic` and in the audit facts.
10. **A model never picks, ranks or changes a suggestion.**

### 4.4 Method
- **Deterministic, in the gateway:** counts, shares, medians, support and confidence (association rules, the textbook market-basket method), a two-window trend.
- Why here:
  - The data is 4 synthetic customers × 8 weeks. A trained model would learn our own generator. A judge could not tell it from a lookup table, and we could not defend it.
  - Every suggestion can be recomputed from its evidence. That is the 20% "logged and auditable" and the brief's trust protocol.
  - A wrong suggestion in a ward is a safety matter (V5). Rules compose with the guards; a score does not.
  - Thresholds are named values on `/assumptions`. That is the 15% "clear visibility of assumptions".
- **The model's part:** none in the minimum; the sentence is a template. In the full version a model may reword it, and the gateway keeps its own sentence unless every number and product id of the reworded one is in the evidence (the idea of `src/tta/agent/textcheck.py`).
- **What a learned model adds later, with real histories of thousands of customers:** suggestions for a new customer from kitchens of the same type (collaborative filtering); seasons and holidays in the reorder date (demand forecasting); lift against the population for related products. Each still passes the guards of 4.3 and still shows its evidence. This is a next step for the 15% criterion, not a build item.

### 4.5 Where it shows
- **Contract** (new `src/tta/contracts/suggestion.py`; `Offer.suggestions: tuple[Suggestion, ...] = ()` next to `notes`):
  - `suggestion_id` (stable for buyer + kind + product, so a dismissal is found again) · `kind` · `serves`
  - `request_line_index` (none for a new line) · `product_id` · `name` · `quantity` · `unit` · `replaces_product_id`
  - `sentence`
  - `evidence`: `source` (SYNTHETIC_HISTORY · ORDER_BOOK · CATALOG · SUPPLIER), `synthetic`, `orders_considered`, `orders_matching`, `first_order`, `last_order`, `values`, `thresholds`
  - `effect`: `net_change_eur`, `price_per_litre_or_kg`, `saving_ratio`
  - `availability` (the state, the confirmed amount, the date) · `stock_confirmed`
  - `checks`: the allergen, claim and formula sentences
  - `accept_request`: the full amended request. An outside agent accepts by posting it to `POST /v1/offers`. No new route is needed to accept.
- **Modules** (new `src/tta/suggestions/`): `history.py` (the orders of one buyer, from P1's pattern file and later the order book) · `signals.py` (pure functions) · `guard.py` (4.3) · `wording.py` · `service.py` (builds the list for an offer, remembers dismissals) · `thresholds.py`.
- **REST:** `suggestions` on `POST /v1/offers` and `GET /v1/offers/{id}`. Full version: `POST /v1/suggestions/{id}/decision` with `DISMISS` or `ACCEPT` and a note, and `GET /v1/suggestions` for the kinds without a request (reorder due, trend).
- **MCP:** nothing new in the minimum (`get_offer` returns the offer). Full: a tool `decide_suggestion`.
- **Page:** one block under the suggested option in `_result.html` (near line 225), titled "From your order history" with the synthetic tag. At most 3 rows; each is the sentence, a button "Add to the request" or "Switch", and "Not now". The evidence opens under "Why?". The block is absent when the list is empty.
- **Audit:** three event types, `suggestion.made`, `suggestion.accepted` (with the new offer id and who clicked), `suggestion.dismissed` (with the note, buyer view only). Sentences for both readers in `audit/sentences.py` and `audit/supplier_sentences.py`.

**DECISION 1:** the list on the offer (recommended: one answer, MCP for free) or a separate route (no change to the `Offer` schema; 7 test files name its keys, by `grep -rln candidates_considered tests`).
**DECISION 2:** the thresholds of 4.1 (support 4, confidence 0.75, share 60%, trend 15%, saving 5%, 28 days).
**DECISION 4:** the supplier's suggestion: documented only tonight (recommended), or built and off by default.
**DECISION 5:** P10's cheaper line (F6) and P1's usual product, usual quantity and reorder (C4–C6) use this one shape, one page block and one set of audit events (recommended).

### 4.6 What the generated history must contain (additions to P1's C2; P1 owns the format)
P1's entry is `{weeks_ago, quantities}`. The signals need four more things:
1. **A date per order** (days before the pinned clock, or a delivery date). A rhythm needs dates; the ward orders twice a week.
2. **A price per product in at least one customer**, older and lower, for the price change.
3. **Substitute decisions:** original, substitute, accepted or refused, date, note.
4. **A relaxed check for one line.** P1's test asks that each median equals `weekly.quantity` (P1 section 5.3). The rising series below breaks it on purpose; mark that line.

| Customer | History to write (real ids, all `CONFIRMED` in the capture) | Shows |
|---|---|---|
| Hotel kitchen | Mondays, 8 weeks. `469363` milk 100, 96, 104, 100, 98, 102, 100, 100 L. `463797` cooking cream in 7 of the 8 weeks, 10 L (one week none). `464615` greek yoghurt in 3 of 8. | Rhythm; forgotten item (7/8 = 0.875); the silent case (3/8 is below 0.75) |
| Hospital ward | Mondays and Thursdays. `464013` soya drink 200 L every order. `473424` rice drink 20 L in 14 of 16. | Forgotten item under exclusions; a cheaper drink that is never suggested (`470863` contains gluten cereals) |
| Bakery-café | `468319` Oatly iKaffe 0.5 L, 30 L a week (or `464320`, the 1 L pack, 60 L: see 6). `464727` whipping cream 40 L against 37 confirmed, on purpose: it opens the substitute path. Paid €6.90 in the 6 older weeks and €7.37 in the last 2. One decision: refused `463975` for `464727`; one: accepted `469346`. P1 lists `469346` as this bakery's usual cream: to agree with P1. | Larger pack; price change (+6.8%); remembered substitute |
| School kitchen | `470863` oat drink 60, 62, 66, 70, 74, 80, 84, 90 L; the standing order stores 60 L. | Trend: median 84 against 70, +20%, five steps up |
| Catering (documented) | No history. | The gateway says "no pattern, no suggestion" |

A test asserts that each behaviour's threshold is met by the data, so a demo moment cannot go quiet after an edit. Every screen and every sentence says "synthetic".

## 5. Work items
"CS" = the computer-science member; "Bio" = a biomedical member. Minimum first.

| Id | What | Files it would touch | Hours | Who | Criterion | Depends on |
|---|---|---|---|---|---|---|
| R1 | The history lines of 4.6 for the hotel and the ward in P1's files; the test "each threshold is met" | P1's `src/tta/customers/data/*.yaml`; new `tests/suggestions/test_demo_data.py` | 0.5 | Bio | 15% visible assumptions | P1 C2 |
| R2 | `Suggestion` contract; `history.py`; the forgotten-item function (support, confidence, median) with named thresholds; unit tests | new `src/tta/contracts/suggestion.py`, `src/tta/suggestions/` | 1.0 | CS | brief's "recommendation logic"; 20% least correction | P1 C2 |
| R3 | The guard (exclusions, availability state, already in the request or in an order) and the list on the offer; the sentence | `src/tta/suggestions/guard.py`, `wording.py`, `service.py`; `src/tta/contracts/offer.py:197`; `src/tta/api/service.py:170-190`, `api/wiring.py` | 0.75 | CS | 20% controls; 30% demo | R2 |
| R4a | Page block with "Add to the request" (posts `accept_request`), 0.25 h; the event `suggestion.made` for both readers, 0.25 h | `src/tta/ui/templates/_result.html`, `ui/request_page.py`; `contracts/audit.py`; `audit/sentences.py`, `supplier_sentences.py` | 0.5 | Bio | 30% demo; 20% logged | R3 |
| **—** | **Minimum: R1–R4a = 2.75 h. Floor of 2.0 h: R2 + R3 + the page row, with the hotel's 8 weeks as a labelled literal in the style of `standing/demo.py:28` (no dependency on P1), no event** | | | | | |
| R4b | "Not now", remembered by reading the audit trail back (no new table); events `suggestion.accepted` and `suggestion.dismissed` | `suggestions/service.py`, `ui/request_page.py`, `contracts/audit.py`, `audit/sentences.py`, `supplier_sentences.py` | 0.75 | CS | 20% controls and audit | R4a |
| R5 | `LARGER_PACK` | `suggestions/signals.py`; uses P10's `offers/formula.py` | 1.0 | CS | 20% match; Valio's goal | P10 F1–F2 |
| R6 | `PRICE_CHANGE` as the trigger of P10's cheaper line, in this shape | `suggestions/signals.py`; `policy/drift.py` (reuse) | 0.5 | CS | 20% match | P10 F6; P1 C2 |
| R7 | `QUANTITY_TREND` on the standing page, and a new operation "change the stored quantity", confirmed by the user | `suggestions/signals.py`; `standing/service.py`; `api/standing_routes.py`; `ui/templates/standing.html` | 1.5 | CS | 20% controls; the brief's drift scenario (`CHALLENGE.md:46`) | P1 C3; P8 |
| R8 | The rhythm rule and `GET /v1/suggestions` for P1's reorder item | `suggestions/signals.py`; `api/routes.py` | 0.5 | CS | 30% demo | P1 C6 |
| R9 | `SUBSTITUTE_REMEMBERED`: decisions read from the pattern file and from approval decisions; tie-break and sentence | `offers/substitutes.py`, `substitute_wording.py`; `suggestions/history.py` | 1.0 | CS | 15% exceptions; 20% least correction | P10 F3; P1 C2 |
| R10 | `POST /v1/suggestions/{id}/decision` and the MCP tool `decide_suggestion` | `api/routes.py`, `api/mcp_surface.py`, `/docs` examples | 0.75 | CS | 15% open interface | R4b |
| R11 | `FROM_SUPPLIER`: profile setting, off; the organic version of a usual product | `contracts/policy.py`, profiles, `suggestions/` | 0.75 | Bio | Valio's goal; `CHALLENGE.md:44` | R3 |
| R12 | Thresholds, the guard rules and the governance paragraph on `/assumptions`, `docs/ASSUMPTIONS.md`, `AIMO/SPEC.md` | those files | 0.5 | Bio | 15% openness | R3 |
| R13 | A model rewords the sentence, with the number check | `src/tta/agent/` | 0.5 | CS | none that a template does not already score | R3 |

Minimum = R1 + R2 + R3 + R4a = 2.75 h. Full = +7.25 h (R4b, R5–R12). **Drop R13**: it scores on no criterion. Cut order, first to go: R11, R10, R9, R8, R6, R7, R5. Keep R4b and R12: they are the dismissal, the audit events and the visible assumptions.

Check against the criteria. 20% least manual correction: the forgotten item saves a second order; the trend saves retyping a quantity every week. 30% demo: one visible step inside the request → lookup → order flow. 20% controls: suggest is not decide; three logged events; guards as fixed rules. 15% exceptions: R9 only. 15% openness: a documented method, named thresholds, evidence in the answer. Brief's "recommendation logic" (`CHALLENGE.md:54`): R2.

## 6. What changes in the demo
All figures measured in replay with the hotel or ward token; the suggestion itself is not built, so its sentence is the proposed one.

**Moment 1 — "Did you forget the cream?" (minimum).**
- Request, hotel: "100 litres of lactose-free milk 469363 by Monday". Today: 100 × `469363`, €248.00, nothing else.
- Suggested: 10 L of `463797` Arla Pro Cooking cream 10% (114 confirmed, €3.31, delivery Monday 16 Nov).
- Sentence: the one in 4.2.
- Click "Add to the request": new offer, 100 × `469363` + 10 × `463797`, **€281.10** (measured). Then the user confirms (P8).
- Second take (R4b): click "Not now". The audit reads "dismissed by …"; the same request shows no suggestion.

**Moment 2 — the rule that keeps a suggestion silent (minimum, the ward's lines of R1).**
- Request, ward: "200 litres of soya drink 464013". Today: €402.00.
- Suggested: 20 L of `473424` Alpro rice drink (109 confirmed, no declared allergen, gluten-free claim). Accepted: **€449.20** (measured), inside the ward's €500 limit per order.
- Under "Why?": "A cheaper drink was not suggested: 470863 contains cereals containing gluten, which this profile excludes." The exclusion sentence is the app's own (measured).

**Moment 3 — "Same drink, larger carton" (full, R5).**
- Request: "60 litres of Oatly iKaffe 464320". Today: 60 × `464320`, **€106.80**.
- Suggested: `473278` Oatly iKaffe 1.5 L, 156 confirmed. Same allergens (AW, GO) and claims (`FREE_FROM_SOY`, `VEGAN`). Fat 3.0 against 3.0 g, protein 1.0 against 1.1 g, sugars 3.3 against 3.4 g per 100 ml.
- Sentence: "Oatly iKaffe 1.5 L (473278) is the same drink at €1.48 per litre against €1.78. 40 cartons cover the 60 L for €88.80: €18.00 less. 156 cartons are confirmed for Monday."
- Click "Switch": new offer, 40 × `473278`, **€88.80** (measured).
- P1 warns that `464320` shows 39,243 units as confirmed. The same moment with the 0.5 L carton `468319` (3,003 confirmed): 30 L costs €86.40; 20 × `473278` cost €44.40 (both measured): €42.00 less.

**Moment 4 — "Your order has grown" (full, R7).** School kitchen, standing order of `470863`, 60 L stored, last renewals 66, 70, 74, 80, 84, 90 L. "Your last 3 weekly orders have a median of 84 L against 70 L for the 3 before (+20%), each higher than the last. The standing order still says 60 L. Store 84 L?" 84 L costs €117.60 (measured with the hotel token; the school profile is P1's C1).

**Remembered substitute (full, R9).** 40 L of `464727`: today 37 × `464727` + 3 × `463975` (vegetable mix), €280.43, AUTO. With the two decisions of 4.6: 37 × `464727` + 3 × `469346`, €290.00 (arithmetic on capture prices), and "you accepted 469346 for this cream on 27 October; you refused 463975 on 3 November".

## 7. Risks and what not to do
- **Do not let "Add" write into an existing offer or order.** Accepting builds a new offer. Otherwise the audit chain and the policy verdict no longer describe what is ordered.
- **Do not ship a replacing suggestion (cheaper, larger pack) before P10's measure exists.** A name match is not a formula. If P10 slips, ship only the forgotten item.
- **Do not show more than 3.** A page of offers is the shop UI the brief says this is not.
- **Do not present counts as real.** "7 of your last 8" comes from a file we wrote. The word synthetic stays in the sentence.
- **Do not learn across customers.** Four invented customers prove nothing, and it opens a data question we cannot answer tonight.
- **A companion with a low base is noise.** Keep both thresholds; the yoghurt in 3 of 8 weeks must stay silent, and a test says so.
- **`Offer` gains a field.** Additive with a default, but the OpenAPI examples and the 7 test files that name the offer's keys must be re-run. The store keeps offers in two back ends (`store/sqlite_store.py`, `store/postgres.py`); I did not check how an offer is serialised there.
- **The trend must not launder drift.** Changing the stored quantity is a user action with its own event. P-08 keeps its window, its median and its tolerance.
- **P1's caution on `464320`** (39,243 units read as confirmed) applies to moment 3. Use `468319` if the team treats large numbers as unknown.
- **The pages and REST keep different order books** (P8, risk list). "Already in an order for that date" is checked per book.

## 8. Questions
**For the team**
- DECISION 1 to 5 above.
- DECISION 6: history source in the minimum is P1's pattern file only. Add the app's own order book in the full version (recommended), so an order placed in the demo counts in the next suggestion?
- For P1: the four additions of 4.6 to the pattern format.
- For P10: emit the cheaper line as a `Suggestion` (kind `CHEAPER_SAME_FORMULA`).

**For Valio (booth shape)**
1. *What you see of a suggestion.* Context: you said you want to see all the steps and decisions. What we did: when a customer's history shows an item it usually orders together with the request, the agent suggests it, and the customer adds or dismisses it. What we got: both the suggestion and the customer's answer are in the log you read. Example: a hotel asks for 100 L of milk `469363`; the agent suggests 10 L of cooking cream `463797`, "in 7 of the last 8 weekly orders"; the customer says "not now". The ask: may you see that dismissal and the counts behind it, or only the orders placed? If nobody answers: you see the suggestion, the counts and the outcome, not the customer's note.
2. *Your own suggestions.* Context: your brief names a selling agent that proposes a new or seasonal product. What we did: we kept one labelled place for a supplier's suggestion, apart from the ones computed from the customer's orders, off unless the customer switches it on. What we got: nothing to fill it with, because we found no "new" or "seasonal" mark in the product data. Example: the organic version `460825` (label `EU_ORGANIC_FARMING`, 177 confirmed, €1.74) of the oat drink `470863` a kitchen buys (€1.40): €0.34 more per litre, same declared allergens. The ask: is there such a mark, and would you want that suggestion made by default? If nobody answers: documented only, off by default.
