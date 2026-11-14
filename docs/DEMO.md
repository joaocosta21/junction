# Demo script

The demo of the Trusted Trade Agents gateway, click by click: three scenarios and a backup. Every number below was checked on 14 Nov 2026 against tonight's replay capture (`fixtures/valio/2026-11-14-demo`, Valio's server time Saturday 14 Nov 02:52). The end-to-end tests in `tests/e2e/` check them on every run.

## How tonight's data changes the plan

| Plan (Friday's data) | Tonight's capture | What the demo shows instead |
|---|---|---|
| Scenario 1: confirmed stock covers 749 L, so option 1 is a partial fill | Three confirmed milks cover the full 1,000 L for €2,580.64 (`469363` 384, `462775` 51, `463380` 565) | A combined full fill. It still goes to a human: €2,580.64 is above the hotel's €750 limit per order (P-01). For a partial fill, ask for **1,500 litres**: confirmed stock is 1,133 L, so 75.5% is covered, which is below the 90% minimum (P-03). See "Extra moments". |
| Scenario 2: `464056` Alpro Barista Soya, €2.14, €428.00 | `464013` Alpro No Sugars Soya, €2.01, 200 × = €402.00 | The same story. It states `FREE_FROM` milk and gluten, every claim is confirmed, and €402.00 is within the ward's €500 limit, so the baseline approval rule F-10 sends it to the purchasing manager. |
| Scenario 3: `471690` passes | `471690` passes the allergen rule, but its cut-off has passed (Thursday 12 Nov 15:00) | It passes and still cannot be ordered, and the page shows the reason. `471881` and `464320` add gluten (`AW`, contains) and can never be ordered. The best substitute that can be ordered is `475224`. |

**Live check, 14 Nov at 08:12 Valio time (6 calls):** the live mock gave the same result as the capture for all three scenarios: the same products, quantities, prices, stock figures, cut-offs, exclusions, verdicts and rules. Every answer was labelled `live`, and `/healthz` read `ok · live · live`.

## Before you start

**Mode: demo in replay**, with the scenarios run once each in the order 1, 2, 3, from a browser whose own order book is empty.
- **Replay** answers from tonight's capture with the clock pinned to Saturday 02:52. The outcomes below are then certain. They do not depend on the mock being up or on stock moving, and no supplier calls are spent. Every page says so in a yellow box: "Replay: recorded Valio Aimo data, clock pinned to the recording".
- **Each browser has its own demo order book.** Every page says, in one line under the header: "Your own demo order book: nothing you do here is seen by other visitors, and it commits nobody." Each browser session of the pages gets its own in-memory order book (orders, approvals, audit trail), so one visitor's orders never count in another's day and never appear on another's approvals page. A new browser (or a private window) starts empty. The **Start again** button next to that line empties this browser's book and no other. The book lives in memory: a restart empties every book. At most 300 books are kept, and a book idle for 2 hours is dropped.
- **Why an empty book matters:** the daily spend limit (P-02) counts the buyer's orders of the data clock's date. In replay that date never ends, so a second run in the same book changes the outcome: the fourth scenario 2 goes to finance, a second scenario 1 needs finance as well, and scenario 3 can also need finance once the hotel's daily spend exceeds €3,000. If an outcome differs from this script, press **Start again**. `tests/e2e/test_demo_script.py` shows the same on the shared book of the REST API.
- **The REST API and MCP keep one shared order book**, the one of their tokens, in the database file. The pages do not show it, and it does not see the pages' books. To start that book from empty, delete the database file and restart (below).
- **No Gemini key** (`GEMINI_API_KEY=` empty): scenarios 1 and 2 are then read and run from the recordings in `fixtures/agent/`. Both readings and scenario 2's run were recorded from `gemini-3.6-flash` on 14 Nov; scenario 1's run is still written by hand. So are, labelled `hand-built`, the reading and the run of the brief's own sentence ("I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability.", hotel kitchen), the readings of the two Finnish sentences, and the transcription and reading of the demo photo (Gemini answered 503 and 504 when those were to be recorded, task T18). The page names where the answers came from: "Run from answers written by hand, not by a model: no live model call." for scenario 1 and "Run from a recording of the model's earlier answers: no live model call." for scenario 2. With a key set, a run served from a recording because Gemini did not answer says "Gemini did not answer, so this run was served from …". With a key set, the buyer agent calls Gemini, and a slow model holds the page. If Gemini cannot be reached, a recorded sentence is answered from its recording, and the run's report says so.

```sh
rm -f var/demo.sqlite3
GEMINI_API_KEY= TTA_ENV=demo TTA_MODE=replay TTA_DB_PATH=var/demo.sqlite3 \
  .venv/bin/python -m uvicorn --factory tta.api:create_app --port 8000
```
Open `http://127.0.0.1:8000/`. `TTA_ENV=demo` is required: without it the app runs as `prod`, which has no demo tokens and does not start. Deleting `var/demo.sqlite3` empties the shared book of the REST API and MCP; the pages' books are in memory and start empty anyway.

**Live mode** is `TTA_MODE=live` (the Valio key and base URL come from the environment). Every offer then says `live` or `replay`. If the mock cannot answer, the call budget runs low, or more than 6 looks a minute are asked for (2 from one address), the capture answers and the page shows the replay label.

**Limits**, per minute (`src/tta/api/limits.py`, illustrative): for one browser on the pages (by its own-book cookie), or one address on REST and MCP, 20 offers and substitute searches, 20 orders and approval decisions, 5 request readings and agent runs; for one address, all its browsers and callers together, 60, 60 and 15; for the whole app, 120, 120 and 30. At most 30 new own order books per address in 10 minutes. Above a limit the answer is "Too many requests" with the time to wait. An example button still runs when the agent is held back by the limit on model calls: it says "The buyer agent could not run: Too many request readings and agent runs from one visitor…" and goes on with its typed request. Everyone behind one network address (the venue Wi-Fi, one laptop) shares the per-address windows; each browser still has its own. To switch back to replay, restart with `TTA_MODE=replay` (on Modal, set the same variable; see `docs/DEPLOY.md`).

**Who is asking.** Both buyer profiles are illustrative and ours. The page says so, and the mock has no customer limits.
| Agent | Per-order / daily review limits | Also |
|---|---|---|
| Hotel kitchen agent (demo), profile `hotel-kitchen` | €750 per order, €3,000 per day, at least 90% of the quantity covered | Substitutes of the same category allowed; variable weight goes to a human |
| Allergy ward agent (demo), profile `allergy-ward` | €500 per order, €1,500 per day, 100% covered | Excludes `AM` milk and `AW` gluten (strict), confirmed data only, no substitute without a human |

## Scenario 1: hotel kitchen, "1,000 litres of lactose-free milk by Monday"

1. **Click** "Scenario 1 · hotel kitchen". The example brings its own agent, the hotel kitchen. The browser opens at the summary strip.
   - Green **Every claim confirmed**: "3 confirmed products cover the 1,000 L asked for, for €2,580.64 before tax."
   - Yellow **A claim not confirmed**: "… (464306) for the 1,000 L asked for, €1,010.00 before tax. Valio does not confirm the quantity in stock, so a human must approve this option."
   - Red **Excluded**: "19 products, each with its reason: 17 × Cut-off passed, 1 × Portion pack, 1 × Not deliverable."
   - **Outcome**: "? Sent for approval".
   *Scores on:* 30% (one flow from request to approval) · 15% (unknown stock and passed cut-offs are handled, not hidden).
2. **Scroll to "The request, as the gateway read it"**: "read as 1,000 L of product type milk, with claim FREE_FROM_LACTOSE, pack: bulk." · "Needed by: Monday 16 Nov 2026" · "Products looked up: 30" · "The text was read and run by the buyer agent". *Scores on:* 20% (a precise match to what was asked).
3. **Options, side by side.** Option 1 "✓ Confirmed stock": 384 × `469363`, 51 × `462775`, 565 × `463380`, each with "✓ Price / Quantity / Delivery date / Allergens / Origin: confirmed". It says "Covers 1,000 of 1,000 L (100%). Order by Sunday 15 Nov 2026 at 17:00 (UTC+02:00)." Option 2 "? Quantity not confirmed", `464306` at €1.01: "Quantity not confirmed: Valio reports 9,999,999,999 ST, a placeholder that means the stock is not known." Under each option, "What the buyer asked for" shows five checks, among them "Every product offered carries the nutritional claim FREE_FROM_LACTOSE. A claim is not an allergen statement." *Scores on:* trust protocol (a status for every claim) · 20% (good-better-best, ready for the approver to pick).
4. **"What the agent may do"** on option 1: "? A human must approve. The agent cannot place this order alone: the total of €2,580.64 before tax is above the €750 limit per order of profile hotel-kitchen (P-01). It needs the purchasing manager." Option 2 adds **F-01**, tagged "fixed rule: no profile can switch it off". *Scores on:* 20% controls (the verdict is known before ordering, with each rule named).
5. **Excluded products:** "✕ Portion pack Arla Portion milk 100x2 cl … (463203) This is a pack of single-serve portions: one sales unit holds 100 portions of 0.02 L. The request is for bulk packs." and "✕ Cut-off passed … Order cut-off passed on Thursday 12 Nov at 15:00, so delivery on Monday 16 Nov cannot be promised." *Scores on:* 15% (every exclusion has a reason).
6. **"What the buyer agent did"**: `✓ get_authority`, `✓ create_offer`, `✓ place_order`, then "The model chooses which function to call; the gateway decides every price, quantity and verdict." *Scores on:* 20% controls (the model never decides a price, a quantity or a verdict).
7. **Click** "Decide as Demo approver Hanna (purchasing manager)", in the same browser: the approval is in this browser's own book. The approval card says "? Waiting for approval · Order by Sunday 15 Nov 2026 at 17:00 (UTC+02:00): after that the order expires." Under "Why a human is needed": "The total of €2,580.64 before tax is above the €750 limit per order of profile hotel-kitchen." · "Needs: purchasing manager". Option 1 is checked and tagged "proposed by the agent". The cheaper option 2 can be picked instead. Point at the lead text: "An agent can never approve: the gateway refuses agent tokens here (rule F-06)."
8. **Type a note** ("Checked with the kitchen.") and **click** "Approve the chosen option". The order record opens: "✓ Ordered with human approval · Ordered for €2,580.64 net with approval by Demo approver Hanna (purchasing manager): rule P-01 asked for a human and was accepted." Below it: "Recorded in the gateway's order book. The Valio Aimo mock has no order endpoint; this record holds everything a supplier order message would need. It commits nobody." *Scores on:* Core 3 · 30%.
9. **Scroll the order record.** "The statements this order relied on" lists price, stock stated (384, 51, 698), delivery date, order by and the time Valio stated it, for each product. "Audit trail: the buyer's view" begins with "✓ The hash chain verifies · The audit trail is intact: each of the 9 events shown here matches its hash …", then "The head of your order book's whole chain now: 9 events, last hash …" (`/healthz` shows the head of the shared book of the REST API and MCP, not this one). The trail has nine sentences, from "The agent sent a request for profile hotel-kitchen: …" to "Order ord_… is ordered, with approval by Demo approver Hanna (purchasing manager): … Price and availability were checked again and had not changed." *Scores on:* 20% (decisions logged and auditable).
10. **Click** the tab "Valio Aimo's view (supplier)". The same nine events appear in the supplier's words: "The buyer's agent sent a purchase request." · "a human at the buyer must approve this order" · "A human at the buyer approved order …". They hold no limit value, no approver name and no note. *Scores on:* audit trail for "both buyer and Valio Aimo" · 15% (a CloudEvents envelope with a hash chain).

## Scenario 2: allergy ward, "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"

1. **Go back to Request, click** "Scenario 2 · allergy ward". The example brings the allergy ward agent.
   - **Every claim confirmed**: "1 confirmed product covers the 200 L asked for, for €402.00 before tax."
   - **A claim not confirmed**: "Nothing unconfirmed is offered."
   - **Excluded**: "41 products, each with its reason: 18 × Declares an excluded allergen, 12 × Cut-off passed, 6 × Not deliverable, 5 × Allergen not stated."
   - **Outcome**: "? Sent for approval".
   *Scores on:* 20% controls (approval even within limits).
2. **The request as read**: "read as 200 L of product type plant_drink, excluding allergens AM, AW, pack: bulk." · "Confirmed data only: yes". *Scores on:* 20% (no milk, no gluten and confirmed only are all kept).
3. **The option**: 200 × Alpro No Sugars Soya drink 1L (`464013`), €2.01, "478 ST confirmed in stock". It shows "The product states it is free from milk (AM)." and "The product states it is free from cereals containing gluten (AW)." All seven checks are met, the last being "✓ Confirmed data only: met". F-10 still sends it to the purchasing manager.
4. **Excluded**: "✕ Declares an excluded allergen Oatly Oat Drink Organic 1L (460825) The product declares that it contains cereals containing gluten (AW), which the buyer excludes." Under the strict rule, a product that makes no statement about milk, or that declares oats when gluten is excluded, goes to a dietitian, so with confirmed data only it is excluded: "✕ Allergen not stated … Confirmed data only was asked for. The product makes no statement about milk (AM): a dietitian must decide." *Scores on:* trust protocol (no data means unknown, not safe; a claim is never an allergen statement).
5. **Approve or reject.** On Approvals, act as the ward purchasing manager. Confirm the proposed option and check that the order record logs the human decision.

## Scenario 3: substitutes, "100 litres of Oddlygood Barista oat drink, product 473609, by Monday"

Asked by the hotel kitchen agent. The sentence has no recording, so the page uses the example's typed request and says so: "The buyer agent could not run: No GEMINI_API_KEY is set, so the gateway can read only the 7 recorded demonstration requests, and this is not one of them." · "Read from the typed request of this example, not from a model's reading." The substitutes are looked up once, when the request runs; reloading the result looks nothing up again.

1. **Click** "Scenario 3 · substitutes".
   - **Every claim confirmed**: "Fazer Aito Professional Barista Oat drink, gluten-free 1L UHT (475224) in place of Oddlygood® Barista oat drink 1 l UHT gluten free (473609): the 100 L asked for, for €174.00 before tax."
   - **A claim not confirmed**: `473609` itself, €137.00, which needs a human (F-01).
   - **Outcome**: "? Sent for approval".
2. **Option 1 "? Substitute"** says what the buyer gives up: "it does not carry the original's nutritional claim FREE_FROM_PRESERVATIVES; the brand is Fazer Aito, not Oddlygood®; Valio does not list it as a substitute; it costs €0.37 more per L". The check reads "✕ Product asked for: not met". The option waits for human approval.
3. **"Substitutes, ranked"** under "Listed by Valio Aimo as substitutes: 3":
   - "1. Oddlygood® Barista oat drink 1 L Delight UHT gluten free (471690) · ✓ Passes the allergen rule · ✕ Cannot be ordered: Cut-off passed · It adds no allergen, but it cannot be ordered now. Order cut-off passed on Thursday 12 Nov at 15:00 …"
   - "12. Oatly iKaffe Oat drink 1L (464320) · ✕ Fails the allergen rule · ✕ Cannot be ordered: Substitute adds an allergen · The substitute adds 1 allergen that the original does not declare: cereals containing gluten (AW, contains). It can never be ordered as a substitute."
   - "13. Oddlygood® Barista oat drink 0,5 l UHT gluten free (471881)", with the same failure. It is the same brand and carries the `FREE_FROM_GLUTEN` claim, yet it declares gluten cereals: a claim is not an allergen statement.
   - Under "Other products of the same category", `468465` reads "? Can be ordered, needs approval": its quantity is not confirmed, so a human must approve it (F-01).
   *Scores on:* 15% (a substitute Valio itself lists fails the buyer's rule) · 20% (it can never be ordered, for any buyer).

## Backup: hotel kitchen, "30 kg beef chuck"

Use this if a scenario breaks. It has no button and no recording: with no key, pasted as text, it is read by the fixed rules (`POST /v1/requests/parse` answers `TTA-Reading-Source: rule-based`, product type `beef_chuck`, 30 kg). Or send the typed request through `/docs` ("Try it out" on `POST /v1/offers`, token `demo-agent-hotel-kitchen`) or with curl:
```sh
curl -s -X POST http://127.0.0.1:8000/v1/offers -H "Authorization: Bearer demo-agent-hotel-kitchen" \
  -H "Content-Type: application/json" \
  -d '{"lines":[{"text":"30 kg beef chuck","product_type":"beef_chuck","quantity":30,"unit":"KG"}]}'
curl -s -X POST http://127.0.0.1:8000/v1/orders -H "Authorization: Bearer demo-agent-hotel-kitchen" \
  -H "Idempotency-Key: backup-1" -H "Content-Type: application/json" \
  -d '{"offer_id":"<offer_id from the first answer>","option_id":"opt_1"}'
```
The REST answers are the record: the order is `PENDING_APPROVAL`. The pages do not show it, because the REST API keeps its own shared order book and the pages show only the browser's own. Approve it with an approver's token (`POST /v1/approvals/<approval_id>/decision`, `Authorization: Bearer demo-approver-hotel-purchasing`, body `{"decision": "APPROVE"}`) and show `GET /v1/audit?order_id=<order_id>`.
- **What appears:** 30 × Well Beef chuck roll (`466988`), €16.88 per kg, €506.40 before tax: "1 confirmed product covers the 30 kg asked for, for €506.40 before tax. The total is a ceiling: a product is sold by weight, so the invoice can be lower, never higher." The lot step is 3 kg: 31 kg is sold as 33 kg (€557.04).
- **Verdict on an empty shared book:** `APPROVAL` by P-06 (variable weight), sent to the purchasing manager. **After scenarios 1 and 3 through REST on the same book** the hotel's day would reach €3,261.04, so P-02 fires as well and finance must also approve: "It needs the purchasing manager and finance." Scenarios run on the pages do not count here: they are in the browser's own book.
- *Scores on:* 20% (lot step and quantity) · 15% (variable weight as a delivery constraint).

## Extra moments for the Q&A (typed requests, `/docs` or curl)

- **Partial fill:** scenario 1 with `"quantity": 1500`. Option 1 is 384 + 51 + 698 = 1,133 L for €2,933.09: "3 confirmed products cover 1,133 L of the 1,500 L asked for (367 L missing)". The quantity check shows "NOT_MET", and P-01 and P-03 fire (75.5%, below the 90% minimum). The unconfirmed alternative is 1,500 × `464306`. *Scores on:* 15% (partial availability).
- **The ingredient list is read:** the hotel kitchen asks for `465793` (Alpro Barista Almond drink) with tree nuts `AN` excluded, strict. The product declares tree nuts free from, but its ingredient list names almond, so it goes to the dietitian (P-04) with a sentence quoting both (task FIX-12a; question ALMOND-1).
- **Cream is dairy cream:** as the hotel kitchen, a typed request for 10 L of product type `cream` picks `463797` Arla Pro Cooking cream 10%, €33.10, submitted for approval. The 9 vegetable-fat blends of category 10401 are type `vegetable_cream` and are not offered for `cream` (task FIX-12a).
- **An agent cannot approve:** `POST /v1/approvals/<approval_id>/decision` with `Authorization: Bearer demo-agent-hotel-kitchen` answers 403 `application/problem+json`, type `…/not-authorised`: "An agent cannot approve or reject an order (F-06). A human with the role asked for decides." The attempt is written to the audit trail (`authorisation.refused`).
- **A retry places one order:** send the same `POST /v1/orders` twice with the same `Idempotency-Key`. The second answer is the first order. On the pages, a form sent twice (or re-sent after an error page) shows its first result: each form submission orders with one key of its own.
- **Who read the text:** `POST /v1/requests/parse` answers the typed request with two headers, `TTA-Read-By` and `TTA-Reading-Source`. With no key, scenario 1's sentence answers `gemini-3.6-flash` and `recording`.
- **Two tabs, two approvers:** a card's form says whom it was shown to. If another tab switched the approver in between, the decision is refused: "The approver was changed in another tab … Nothing was changed."

## The 90-second cut

| Time | Screen | Say | Criterion |
|---|---|---|---|
| 0:00–0:10 | `/`, the two agents | "A buyer's agent asks the wholesaler. Its authority is a profile: €750 an order for the hotel." | 20% controls |
| 0:10–0:35 | Scenario 1, summary strip, then the two options | "Three confirmed milks cover the 1,000 litres. The cheaper one has no confirmed stock, so it is offered, but only a human can pick it. Nineteen products are excluded, each with its reason." | 30% · 20% match · 15% |
| 0:35–0:50 | Approval card, then Approve | "€2,580 is above the agent's limit: P-01, purchasing manager. The agent cannot approve its own order." | 20% controls · Core 3 |
| 0:50–1:05 | Order record, audit trail, then the supplier tab | "Nine steps, one sentence each, hash-chained. Valio sees the same steps without the buyer's limits or names." | 20% audit · 15% open standards |
| 1:05–1:20 | Scenario 2 | "The allergy ward: even with confirmed data and €402 within its limits, the proposed order waits for human approval." | 20% controls |
| 1:20–1:30 | Scenario 3, the ranked substitutes | "Two substitutes Valio itself lists add gluten. The gateway shows them and never lets them be ordered." | 15% robustness |

## For a judge who wants to point an agent at it

- **MCP:** `POST <demo address>/mcp/` (Streamable HTTP, no session, JSON answers) with the header `Authorization: Bearer demo-agent-allergy-ward` or `Authorization: Bearer demo-agent-hotel-kitchen`. It has eight tools: `get_authority`, `search_products`, `get_product`, `find_substitutes`, `get_offer` (takes the typed request and makes an offer), `place_order`, `get_order`, `get_audit`. No tool approves: approvals are REST routes for approver tokens only. Without a token the answer is 401. Checked by hand today: `initialize` and `tools/list` answer 200 with the token.
- **REST:** OpenAPI at `<demo address>/openapi.json` and `/docs`, JSON Schemas at `/v1/schemas`, health at `/healthz`. The demo tokens are in `src/tta/api/demo_tokens.yaml`. They are public by design and are loaded only when `TTA_ENV` is `dev` or `demo`.
- **Orders commit nobody.** `ORDERED` means recorded in this gateway's order book; the Valio Aimo mock has no order endpoint. Every page says so.
- **MCP takes POST only.** `GET` and `DELETE` on `/mcp` and `/mcp/` answer 405 with `Allow: POST`: there is no event stream and no session.
- **`/docs` and `/redoc`** load Swagger UI 5.32.15 and ReDoc 2.5.4 from jsDelivr, each file checked by its hash, under a Content-Security-Policy that allows that CDN only and no framing. They need the venue network to reach jsDelivr; `/openapi.json` needs nothing.

## If something goes wrong

- **An outcome differs from this script:** this browser's book was not empty, or a scenario was run twice in it. Press **Start again** (next to the "Your own demo order book" line) and run the scenarios once each, in the order 1, 2, 3. For the REST API's shared book: stop the app, delete the database file and start it again.
- **"Too many requests" on a page:** this address used its minute (20 offers, 20 orders, 5 agent runs). Wait the seconds it names. An example button still runs from its typed request when only the agent runs are used up.
- **Free text answers 503:** with no Gemini key, only the recorded sentences and the shapes the fixed rules know can be read; the answer names what the rules could not read. Use the example buttons, or send the typed request.
- **The page waits on the model:** a Gemini key is set and Gemini is slow. Restart with `GEMINI_API_KEY=` empty.
- **The mock is down in live mode:** offers come from the capture and say `replay`; `/healthz` shows `degraded` and the reason. Nothing else changes.

## Your kitchen: the buyer sets its review limits (task FEAT-1)

*Scores on:* 20% autonomy and controls (the buyer sets review limits; every order needs human approval) · Core 3 of the brief · 30% demo.

1. Open "Your kitchen" in the menu (`/kitchen`). It starts as a copy of `hotel-kitchen` under the id `my-kitchen`. Each setting shows the rule it drives (P-01 to P-08) with its values, and below the form are the fixed rules including F-10, under "Always, whatever you set".
2. Set **Spend limit per order** to `3000` and press **Save my kitchen**. The policy hash on the page changes.
3. On `/`, choose **My kitchen agent**, paste `1,000 litres of lactose-free milk by Monday`, press **Run**. Option 1 (384 × `469363` + 51 × `462775` + 565 × `463380`, **€2,580.64**) is `PENDING_APPROVAL` under F-10, profile `my-kitchen`. The order record shows the policy hash in force, and its audit trail names profile `my-kitchen`.
4. Back on `/kitchen`, set the limit to `750` and save. Run the same sentence as My kitchen agent: the order waits for the purchasing manager (P-01). Finance is asked as well (P-02), because the €2,580.64 of step 3 already counts in today's €3,000. Decide it on `/approvals` as "Demo approver Hanna, My kitchen".
5. Say: "Same request, same data, a different setting, a different reason for approval. The buyer sets the limits; nothing it sets can switch off a fixed rule. A form that tries is refused, with the field named."

- **Without a Gemini key** the result page says "The buyer agent could not run: This sentence was recorded for another buyer profile …" and "Read from the typed request of this example": the recordings are for `hotel-kitchen` and `allergy-ward`, so the page uses the example's typed request. The verdicts above are the same.
- The kitchen is in this browser's own order book only. Another visitor, the REST API, MCP and the profile files never see it. **Start again** brings back the copy of `hotel-kitchen` at €750.

## Added on Saturday afternoon: three more moments

Checked on 14 Nov 2026 by running the pages in replay, in-process, with no Gemini key (capture `2026-11-14-demo`, Saturday 02:52), each from an empty book. Each moment is independent of the scenarios above; run it after **Start again** if the scenarios were run first, because the hotel's day spend counts (P-02).

### A menu becomes one order (`/menu`, task MENU-1)

*Scores on:* 15% (substitution through recipe logic, a delivery constraint) · 20% controls (a stand-in always goes to a human) · 30% demo.

1. **Open** "Menu" in the menu bar and **click** "Fill in the last-minute event" (or open `/menu?example=event`). The form fills in: Beef stew 120 servings, Berry quark dessert (marjarahka) 120 servings, the kitchen holds butter 3 kg and sugar 2 kg, needed by 2026-11-16, "Confirmed stock, price and date only" ticked. "Hotel kitchen agent (demo)" is chosen. The page says: "The recipes and their amounts per serving are ours and illustrative, not Valio Aimo's."
2. **Click** "Plan the menu". "The final offer has 4 lines for Beef stew (120 servings) and Berry quark dessert (marjarahka) (120 servings)."
   - Beef stew: beef chuck 21.6 kg (line 1), cream 3.6 L (line 2), butter 1.2 kg "✓ In stock".
   - Berry quark dessert: quark 12 kg "? Stands in as yoghurt (line 4)": "Yoghurt (natural) stands in for quark (maitorahka), the thick, tangy base of the dessert. Quark (maitorahka): none of 10 products can be offered by Mon 16 Nov 2026 (6 order cut-off passed, 4 quantity not confirmed (confirmed data only was asked for)). A thick natural yoghurt gives the same tangy base; the dessert is runnier and has less protein." Whipping cream 3.6 L (line 3); sugar 1.2 kg in stock.
3. **The offer, option 1** "✓ Confirmed stock": "4 confirmed products cover all 4 request lines in full, for €476.48 before tax." · "€476.48 before tax · €540.81 with tax". Lines: 24 × `466988` beef chuck €405.12, 4 × `463797` cooking cream €13.24, 4 × `469346` whipping cream €23.08, 12 × `464615` Valio A+ greek natural yoghurt €35.04.
4. **"? A human must approve"**: "The agent cannot place this order alone: Valio A+™ greek natural yoghurt 1 kg lactose free (464615) stands in for an ingredient of a recipe: yoghurt in place of the recipe's quark, whose role is the thick, tangy base of the dessert, so a person checks that the dish still works (F-09) and Well Beef Beef Chuck roll n 3 kg (466988) is sold by variable weight, so its final price is not fixed in advance (P-06). It needs the purchasing manager." F-09 is a fixed rule: no profile can switch it off.
5. **Click** "Send this option for approval": the order goes through the normal flow and waits for the purchasing manager on `/approvals` (`tests/menus/test_menu_page.py`).

The same plan over REST: `POST /v1/menus/plan` with the hotel's token gives the same offer, €476.48, `APPROVAL` with F-09 and P-06.

### A standing order that drifts (`/standing-orders`, task STAND-1)

*Scores on:* 20% controls (each renewal requires approval and unusual quantities are flagged) · 20% audit (the drift is stated in the trail) · Valio's example scenario "standing order drift detection".

1. **Open** "Standing orders" and **click** "Load the demo standing order". It is "Weekly lactose-free milk, hotel kitchen" (`so_demo_hotel_milk`): 100 L of `469363` every 7 days, hotel-kitchen profile. The history shows six weeks, 3 Oct to 7 Nov: 100, 96, 104, 100, 98 and 102 L at €2.48, each marked "Synthetic: made up for the demo". Say it: the Valio Aimo mock has no order history, and the page says so.
2. **Type** `100` and **click** "Renew". "? Waiting for approval · €248.00 net, rule F-10." The drift sentence: "Standing order so_demo_hotel_milk is within the 25% tolerance: 100 L this week against a median of 100 L over the last 6 renewals and €2.48 per ST of 469363 this week against a median of €2.48 over the last 6 renewals. 6 renewals of the history are synthetic, …"
3. **Type** `290` and **click** "Renew". 290 × €2.48 = €719.20 is under the €750 limit per order, and P-08 explains why the renewal needs scrutiny. "? Waiting for approval · … rule P-08 asks for a human." P-08: "For standing order so_demo_hotel_milk, 290 L this week against a median of 100 L over the last 6 renewals, more than the 25% tolerance of profile hotel-kitchen." The history now has two real rows, each with its order id; "5 renewals of the history are synthetic".
4. **Click** through to the approvals page and decide as the purchasing manager. The 25% tolerance is ours and illustrative; it is set on "Your kitchen" for My kitchen.

### A preference changes the choice (example 5 on `/`, task SUST-1)

*Scores on:* the brief's optional direction "delivery time & sustainability comparison" · 20% match (the buyer's own ranking) · 20% controls (the cheaper option stays on the table with the difference in euros).

1. **Click** "Preference · most reliable delivery" ("100 litres of oat drink by Monday, most reliable delivery", hotel kitchen).
   - **Every claim confirmed**: "1 confirmed product covers the 100 L asked for, for €140.00 before tax. €7.00 more than the cheapest confirmed option, for a delivery reliability of at least 100% instead of unknown." and "The cheapest confirmed option: 1 confirmed product covers the 100 L asked for, for €133.00 before tax. €7.00 less than the option ranked by delivery reliability."
   - **A claim not confirmed**: `468465` Oddlygood oat drink, €117.00, to a human.
   - **Excluded**: "20 products, each with its reason: 11 × Cut-off passed, 8 × Not deliverable, 1 × Portion pack."
   - **Outcome**: "? Sent for approval".
2. **The request as read**: "read as 100 L of product type plant_drink, name contains oat, pack: bulk." · "Ranked by: delivery reliability, then price" · "Products looked up: 38". With no key: "No Gemini key is set, so this run was read and made by fixed rules, not by a model." (With a key, Gemini reads it; that was not checked for this sentence.)
3. **Option 1** "Best confirmed option, ranked by delivery reliability": 100 × Oatly Oat Drink Semi 1L (`470863`), €1.40, "Delivery reliability: 100% · Carbon footprint: 0.435 kg CO2e per kg · Certificate labels: none stated". "Compared with the other options: Delivery on Monday 16 Nov. Lowest delivery reliability 100%. Carbon footprint about 43.5 kg CO2e, a litre counted as a kilogram. No certificate label stated."
4. **Option 2** "Cheapest confirmed option": 100 × Oatly No Sugars Oat Drink (`472145`), €1.33, "Delivery reliability: unknown". Both options are within the hotel's limits. The agent submitted option 1 for approval.

Under price alone (the default, every other figure on this page) the same request gives `472145` at €133.00. "Earliest" and "lower carbon" change no choice in tonight's capture: every confirmed product arrives on Monday 16 Nov, and carbon is close to one value per category (`docs/ASSUMPTIONS.md`).
