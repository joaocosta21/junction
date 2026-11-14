# A5 — The build scored against Valio Aimo's criteria (Saturday 14 Nov, commit `7f09ce7`)

Scored as a strict Valio Aimo judge who also gave the booth answers. Everything below was run by me offline (replay capture `2026-11-14-demo`, clock pinned to Sat 14 Nov 02:52, no keys, fresh data folder per script). Figures are from that capture, not catalog facts.

**Not run, so not judged:** the deployed app, Gemini (free text was read by the recordings or the rule-based reader), photo reading, live mode, the test suite (2,102 test functions in 185 files exist; counted with `grep`, not executed). Pages were fetched as HTML, not seen in a browser. Gains and hours in section 5 are my estimates.

## 1. In five lines
- **Weighted total: 70.5 / 100** (demo 8 · precision 5 · autonomy and controls 7 · exceptions 7 · openness 8).
- **Weakest criterion: precision (20%), 5/10.** Of 15 varied free-text requests, 4 came back as a buyer would want with no correction, 2 were correct refusals with nothing offered instead, 9 needed a correction or were not read.
- The flow is complete on the REST routes; the pages carry it from the sentence to the approval queue; the MCP surface lists its 8 tools (I did not call them). "Works" is not the problem; **what the main scenario returns** is: 565 of its 1,000 litres are coffee milk (Valio, B5: "no be explicit").
- **Most valuable change:** one re-baseline of the main scenario: take coffee milk out of "milk" (B5) and choose a date at which order cut-offs have not passed (V6). It lifts precision and the demo together (estimate +8 weighted points, about 5 hours, highest risk).
- **Cheapest change:** turn automatic ordering off in both profiles (V8). Rule P-00 and the `/kitchen` switch already exist; estimate +3 points for about 1.25 hours.

## 2. Scores
| Criterion | Weight | Score | Evidence (what I ran and saw) | What holds it down |
|---|---|---|---|---|
| Working end-to-end demo | 30% | **8** | `scenario_1` end to end: `GET /v1/authority` → `POST /v1/offers` (201, 2 options, 19 exclusions each with a reason) → `POST /v1/orders` (PENDING_APPROVAL, P-01) → `POST /v1/approvals/{id}/decision` (ORDERED, `placed_by` HUMAN_APPROVAL) → `GET /v1/audit` (11 events, chain verifies). Through the pages: `/` → `POST /run` → `/orders/{id}` → `/approvals` shows the order waiting with its options (I did not submit the decision form). `/mcp/` answers `initialize` and `tools/list` (8 tools; 401 without a token); I did not call the tools. `/v1/agent/run` does it from one sentence. Menu plan, standing orders and substitutes routes all answered. | (1) The main scenario's "best" answer is a patchwork of 3 products with 565 L of coffee milk for €2,580.64. (2) With the clock at capture time most candidates are gone: cut-off passed for 17 of 30 (lactose-free milk), 55 of 78 (milk), 79 of 122 (milk and cream). (3) Free text outside the recordings depends on Gemini; offline, 4 of my 15 sentences were not read at all. (4) Typed free text is limited to 5 readings a minute per visitor: my own run was refused (429) from the 6th request. The one-click scenarios carry their typed request (`ui/request_page.py:57`); whether they count toward this limit was not checked. (5) Replay holds only categories 104xx and 18720 (brief, section 3): "20 kg of chicken breast" gives 97 × NOT_IN_RECORDING. (6) `POST /v1/products/search` returns no price and no availability; those come only with an offer. |
| Solving the problem and user need (precision) | 20% | **5** | 15 free-text requests, section 6. **4 right without correction** (R02, R03, R07, R13). **2 correct refusals** with the reason but no orderable way forward (R08, R11). **9 not as wanted**: coffee milk (R01); 200 "portions" became 200 tubs of 500 g for €530, orderable alone (R09); "10 cases" became 10 single cartons (R10); "gluten-free" and "no gluten" stopped with a 422 asking STRICT or DECLARED_ONLY (R04, R15); "the usual milk" refused (R06); 3 not read by the offline reader (R05, R12, R14). The engine never guesses and says why; each exclusion carries a sentence. | The criterion is "least manual correction"; the build prefers to refuse or ask. No use of the buyer's own pattern (V2). Unit words other than litres and kilograms are read silently as sales units. `pack: PORTION` found nothing: "112 not a portion pack", including a 150 g cup. Brand is not a field; R13 kept "Arla" by price luck. Plain "200 litres of milk" returns a lactose-free UHT drink at €2.48 while the €0.88 milk is unconfirmed. Best case if Gemini reads the 3 unread ones correctly: about 7 of 15 (typed equivalents T05, T12 run; not measured with Gemini). |
| Autonomy and controls | 20% | **7** | `rules.yaml`: 9 fixed rules, 9 profile rules, data only, most severe verdict wins, missing fact goes to a human, policy hash on every decision. Tested and refused: agent approving its own order (403, F-06, logged), wrong role (403, logged), other buyer's approver (404), supplier (403), approver placing an order (403), `profile_id` in the body (422), second order on one offer (422), deciding twice (422). Ward agent sending `DECLARED_ONLY` and `require_confirmed: false` did not weaken its profile. Two roles needed when two rules name them; after the purchasing manager switched to option 1, finance was needed again although it had approved option 2. Audit: readable sentences, rule ids, facts, hash chain, buyer and supplier views. | (1) **V8 not applied:** both profiles order alone; 8 of my test orders were placed with no person (4 split orders, 4 standing-order renewals). (2) **Splitting works:** 4 × 250 L at €620 each were all ordered alone (€2,480) where one 1,000 L order needs a human; P-02 stops only the 5th. (3) **The gateway does not count its own orders against stock:** those 4 orders took 1,000 units of `469363` against 384 confirmed, and the next offer still said "384 confirmed". (4) Supplier view hides which profile rule fired and why; Valio (B13) asked for "all the steps and decisions". (5) Event `time` is the machine's clock (12:46Z) while offers carry the pinned clock (02:52+02:00): one trail, two clocks. |
| Robustness to exceptions | 15% | **7** | Partial: 5,000 L asked, 1,133 L confirmed, fill 22.7%, P-03, "3,867 L missing". Unknown stock: named as alternative, always to a human (F-01). Delivery: "for tomorrow" and "today" give no option plus the earliest possible date and the products that could make it. Substitution: named product past its cut-off gives a SUBSTITUTE option with an allergen check and a "gives up" sentence; `/substitutes` ranks 10 of 619 checked. Variable weight: ceiling total, P-06. Allergen unknown: dietitian (P-04). Recipe stand-in: yoghurt for quark, F-09. Standing order: 290 L against a median of 100 L goes to a human (P-08). | (1) **Substitute ranking:** for 1 L organic lactose-free milk `462921` the first substitute is a case of 2.5 dl cartons at €2.86/L (€10.71 per 3.75 L case); the 1 L same-brand `464306` at €1.01/L ranks second. The lost organic label is not mentioned. (2) One substitute per offer; no good-better-best tiers there. (3) V10 (same brand or formula; recipes that depend on the formula) is not modelled; the hotel profile accepts any same-category substitute alone. (4) When the date cannot be met no option is offered for the earliest date; the buyer must ask again. (5) No option that tops up confirmed stock with unconfirmed stock. (6) Preferences rarely change anything in this capture: RELIABILITY, LOWER_CARBON and EARLIEST gave the same answer; reliability is known for 18 of 78 milk products; carbon is one value per category. |
| Openness and path to production | 15% | **8** | OpenAPI 3.1 generated from the models; JSON Schema at `/v1/schemas`; RFC 9457 problem bodies on every error I provoked; MCP surface; GS1 allergen codes; bearer tokens; `Idempotency-Key` required on orders; CloudEvents envelope claimed in `docs/STANDARDS.md` (the API view shows `id`, `type`, `time`). `/assumptions` page served by the app; every limit labelled illustrative; `docs/STANDARDS.md` states its own gaps and 11 next steps (order message, OAuth, signed statements as W3C credentials, Peppol named). MIT licence. | (1) The offer and order shapes are our own format, documented but not mapped to a trade standard (Peppol is named as a next step only). (2) The "trust protocol" is unsigned: per-claim CONFIRMED / UNKNOWN is our statement about Valio's data, and the gateway verifies its own chain. (3) No discovery document for an arriving agent beyond `/openapi.json` and MCP. (4) The product-type table is hand-made: 32 types for 349 categories. (5) Volume of documents: a judge with minutes will not find the three sentences that matter. |

Weighted: 0.30×8 + 0.20×5 + 0.20×7 + 0.15×7 + 0.15×8 = **70.5**.

**What a 10 looks like, per criterion**
- Demo: the brief's own sentence returns one answer a Valio salesperson would nod at, in under 10 seconds, on the deployed address, three times in a row, and any dairy, meat or dry-goods sentence a judge types gets a sensible offer.
- Precision: 13 or more of 15 varied requests right first time, units and pack sizes honoured, "the usual" resolved from the buyer's history, and each reading shown for one-click confirmation instead of a refusal.
- Autonomy: the agent proposes, a person confirms (V8), the switch for ordering alone is visible but off; no path where repetition beats a limit; both parties read every step.
- Exceptions: every "cannot" comes with the next best orderable thing, ranked good-better-best with the trade-off in one line, same brand and pack first.
- Openness: a standard order message, statements a third party can verify, and one page a judge can read in a minute.

## 3. Distance from Valio's answers
Cost is in points of the criterion (0–10 scale) and, in brackets, weighted points out of 100. Estimates.

| Answer | Today | Distance | Cost |
|---|---|---|---|
| **V8** deactivate automatic ordering; the agent suggests, the user decides | `auto_order_enabled: true` in both profiles; scenario 2 is "the agent orders alone"; renewals are placed alone | Large in what the judge sees, small in code: P-00 and the `/kitchen` switch exist | Autonomy −1.5 (−3) |
| **V6 / B3** choose the date so the data makes sense | Clock = capture time (Sat 02:52); Thursday cut-offs are passed | Large: 17/30, 55/78, 79/122 candidates gone in my runs | Precision −1.5, demo −0.5 (−4.5) |
| **B5** coffee milk is not milk | `milk` excludes "coffee drink", not "Cafè milk" or "coffee milk"; 565 of 1,000 L in scenario 1, 698 L in the 5,000 L case | Large, in the first thing a judge sees | Precision −1, demo −0.5 (−3.5) |
| **V10** substitutes: same brand or formula; formula matters for cakes | No brand or formula in the ranking or the rules; first substitute differs in pack and loses a label unmentioned | Large | Exceptions −1.5, precision −0.5 (−3.25) |
| **V2 / V1** per user, from the user's pattern; data can be generated | Two fixed profiles and an editable "My kitchen"; no order history behind a request; "the usual milk" refused | Medium | Precision −1 (−2) |
| **B13** Valio sees all the steps and decisions | Supplier view: steps yes; profile rule ids, reasons, claims asked for, names and notes hidden | Medium. **DECISION:** what stays hidden (limit values, names) | Autonomy −0.5 (−1) |
| **V5** noisy data: be robust, flag when unsure | Missing data goes to a human (F-03, P-04); exclusions explained | Small. Gap: unit words ("cases", "portions") are assumed, not flagged | Precision −0.5 (−1) |
| **V7** category digits are not confirmed levels | Policy uses the exact 5-digit category (`SAME_CATEGORY_DISTANCE = 0`). Not checked by me: whether substitute tiers beyond 0 read digits as levels (`offers/substitutes.py`) | Unknown | 0 to −0.25 exceptions |
| **Q2** take allergen values as in the data | Done: the "gluten free" oat drink goes to the dietitian because the data says oats | None | 0 |
| **Q14** convert units to satisfy the request | Done for volume: 27 cases of 3.75 L offered for 100 L | None | 0 |
| **Q16** variable weight: invoiced for what is delivered | "The total is a ceiling: lower, never higher" | Small: "never higher" is our assumption | 0 |
| **B2, B6, B11** | Done (F-01, F-05, first Monday) | None | 0 |
| **B7** ("yes and only in the last case") | F-08 sends a lost dietary claim to a human | Ambiguous note; João must say what was meant | Not costed |
| **V4** webshop | Not looked at (agent P3 only) | Not judged | Not costed |

Sum of the costed distances: about 18 weighted points. Closing all would put the build near 88.

## 4. Against the field
Reasoned from the brief, not observed. 105 teams, most with a language model, the mock API and 40 hours.

**What the strongest teams probably show**
- A chat-style agent over an MCP wrapper of the mock that completes the milk sentence with a spend threshold and an approve button. It always answers, so it feels precise even when it is wrong.
- The brief's scenarios played as stories: recipe → order, last-minute event, stock-out with a recipe-compatible substitute, a selling agent that proposes a seasonal product.
- The brief's "preferred tech" by name: verifiable credentials or a trust layer, agentic payment standards (x402, Nevermined), agent-to-agent protocols. None of these is in `src/` (grep: 0 files).
- A polished single screen and a tight two-minute story.

**What this build has that they probably lack**
- Policy as data with fixed rules no profile can switch off, a policy hash on each decision, roles, two-person sign-off, and refusals that are themselves logged.
- A per-claim statement of what Valio's data confirms (price, quantity, delivery date, allergens, origin): a real answer to "trust protocol".
- An audit trail with a buyer view and a supplier view, hash-chained, in sentences.
- Honest handling of unknown stock, passed cut-offs and missing allergen data, each with a reason, where others will show them as stock.
- Allergen logic on GS1 codes ("may contain", not stated, oats and gluten), a dietitian role.
- Offline replay, recordings when the model is down, 2,102 tests, a standards document that states its own gaps.

**What they probably have that this build lacks**
- An answer for every sentence. Here 9 of 15 needed a correction.
- Use of the buyer's history ("the usual"), and a proactive supplier-side suggestion.
- A named trust or payment standard in the demo, even if thin.
- One memorable screen. Here the proof is spread over six pages and long documents.

## 5. The ten changes, ranked by weighted points per hour
Estimates. "Risk" is the risk to what already works. Items 2 and 4 change every figure of scenario 1 and must be one re-baseline, done first or not at all.

| # | Change | Criterion | Gain (weighted) | Hours | Risk |
|---|---|---|---|---|---|
| 1 | **Automatic ordering off by default (V8).** `auto_order_enabled: false` in both profiles; scenario 2 becomes "the agent proposes, the dietitian or buyer confirms in one click"; keep the AUTO verdict visible as "could be placed alone if the setting were on"; `/kitchen` switch shown as the later setting. | Autonomy 20% | +3 | 1.25 | Medium-low: tests and recordings that expect ORDERED by the agent (scenario 2, renewals) change |
| 2 | **Coffee milk out of "milk" (B5).** Exclude terms for café and coffee milk in `catalog/product_types.yaml`. Scenario 1 then has 435 L confirmed of 1,000 (from my run: 1,133 L confirmed with 698 L of coffee milk), so the brief's own sentence becomes the partial-availability case. | Precision 20%, demo 30% | +3.5 | 1.5 | Medium: every figure of scenario 1 in tests, recordings, DEMO and PITCH |
| 3 | **Rate limit for typed requests at the booth.** 5 readings a minute per visitor refused my 6th request; raise it for the review hours (`MAX_MODEL_CALLS_PER_VISITOR_PER_MINUTE`, `api/limits.py`). | Demo 30% | +0.75 | 0.5 | Low |
| 4 | **Choose the date (V6, B3).** One "as of" date for replay and live at which Thursday cut-offs have not passed. Not measured: my scratch override of `PinnedClock.now` did not change the offers (they kept the recording's `time_now`), so the effect on figures is unknown until built. | Precision 20%, demo 30%, exceptions | +4.5 | 3.5 | High: all figures; do with item 2 |
| 5 | **Unit words.** "cases" → the product's `KI` unit (sizes are in the data: 6, 12, 20); "portions" → small packs; otherwise a visible "read as sales units" check that goes to a person. Minimum (1 h): the check only. | Precision 20% | +2 | 1.5 | Low-medium |
| 6 | **Supplier view shows every step and decision (B13):** rule ids and titles of all rules fired, no limit values, names or notes. | Autonomy 20% | +1 | 1 | Low |
| 7 | **Substitute ranking (V10):** same brand and same pack size first, every lost label and claim named (organic was not), three tiers in the offer, substitutes never accepted alone for the hotel. Minimum (1.5 h): tie-break, label sentence, profile setting. | Exceptions 15%, precision | +3.25 | 3.5 | Medium: scenario 3 figures |
| 8 | **Count the gateway's own orders against confirmed stock,** at offer time and at order time. Closes 1,000 units ordered on 384. | Autonomy 20%, exceptions 15% | +1.75 | 2 | Medium: offer builder and re-check |
| 9 | **"The usual" from a generated history per profile (V1, V2),** labelled synthetic, shown as a reading the person confirms. Minimum (2 h): one history file per profile and the lookup. | Precision 20% | +2 | 3 | Low-medium: new path |
| 10 | **An orderable way forward when the date cannot be met:** the earliest-date option (F-07 already sends it to a human) and a top-up of confirmed with unconfirmed stock. Minimum (1 h): a one-click "ask again for Monday" on the page. | Exceptions 15% | +1.5 | 2.5 | Medium: a new option kind touches the contract |

Sum: about 20 hours for an estimated +23 if nothing overlapped; expect +12 to +15. Just outside the ten: price and availability on `POST /v1/products/search` (+0.75, 1.5 h).

**Three things to stop**
1. **New scenarios and optional-direction polish.** Menu planning, photo reading, standing orders, delivery and carbon preferences already exist and score. The preferences gave one answer three times in this capture. None of them moves the weakest criterion.
2. **Hardening and more tests.** Rate-limit layers, fall-backs, MCP edge cases, 2,102 tests: openness is at 8 and a judge does not see the difference in three minutes.
3. **More documents.** The assumptions page is 56 KB and the walkthrough 1,302 lines. Spend the time on the one screen and the three sentences a judge hears.

## 6. What I ran
Recipe of the brief, section 5; scripts in `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/A5/` (`flow.py`, `precision2.py`, `typed.py`, `exc.py`, `guard.py`, `opt.py`, `pages.py`). One client address per request in `precision2.py`, because of the 5-a-minute limit.

**Core flow (`flow.py`):** `GET /healthz` · `GET /v1/authority` (hotel; 401 without token) · `POST /v1/offers` `scenario_1` → 201 · `POST /v1/orders` without `Idempotency-Key` → 422; with it → 201 PENDING_APPROVAL; same key again → same order; new key → 422 "already has an order" · decision as agent 403, finance 403, ward purchasing 404, supplier 403, hotel purchasing 200 ORDERED; again → 422 · `GET /v1/audit?order_id=` as agent, approver, supplier: 11 events each, chain ok.

**Precision, free text → `POST /v1/requests/parse` → `POST /v1/offers` (`precision2.py`), hotel agent:**
| # | Request | Result | Verdict |
|---|---|---|---|
| R01 | 1,000 litres of lactose-free milk by Monday | 384 + 51 + 565 (Arla Cafè milk), €2,580.64; alternative 1,000 × `464306` unconfirmed €1,010 | No: coffee milk |
| R02 | 50 litres of whole milk by Tuesday | 50 × Arla whole milk (low lactose) €100.50, alone | Yes |
| R03 | 10 kg of quark by Monday | 2 × Valio quark 5 kg, unconfirmed, to a human | Yes |
| R04 | 200 litres of gluten-free oat drink by Monday | 422: asks STRICT or DECLARED_ONLY | No: correction |
| R05 | 30 cartons of Valio Eila lactose free milk 1 l | 503 offline ("more than one quantity"). Typed (T05): 30 × `464306`, to a human | No offline |
| R06 | the usual milk | 503 offline ("no quantity") | No |
| R07 | 100 litres of milk and 20 litres of cream by Monday | 100 × whole milk + 20 × cooking cream 10%, €267.20, alone | Yes |
| R08 | 5 kg of beef chuck for tomorrow | No option; "earliest Monday 16 Nov, 2 products" | Half |
| R09 | 200 portions of lactose-free yoghurt by Monday | 200 × Salakis Turkish yoghurt 500 g, €530, alone; the 150 g cup only as unconfirmed alternative. Typed with `pack: PORTION` (T09): no option | No |
| R10 | 10 cases of oat drink by Monday | 10 × 1 L Oatly, €13.30 | No |
| R11 | 100 litres of organic milk by Monday | No option: 11 of 11 cut-off passed; nothing else proposed | Half |
| R12 | 120 litres of skimmed milk in 10 litre boxes by Monday | 503 offline. Typed (T12): no option, 5 of 5 cut-off passed | No offline |
| R13 | 24 litres of Arla lactose-free whipping cream by Wednesday | 24 × Arla Pro whipping cream, €138.48, alone ("Arla" was not read) | Yes |
| R14 | 200 litraa laktoositonta maitoa maanantaiksi | 503 offline (recordings of other Finnish sentences exist) | No offline |
| R15 | 200 litres of oat drink by Monday, no gluten, no nuts | 422: asks strictness | No: correction |
Also run: by product number (right, alone), "by 18 November" (300 × `469363`, €744, alone), chicken (not in recording), tomatoes (not read), ward scenario (200 × Alpro soya, €402, alone), plain "200 litres of milk" typed (200 × lactose-free UHT at €2.48, alone; €0.88 milk unconfirmed).

**Exceptions (`exc.py`):** 5,000 L lactose-free, confirmed only → fill 22.7%, P-01 + P-03 · same, unconfirmed allowed → alternative €5,050 with F-01, P-01, P-02 · `product_ids: ["462921"]`, 100 L → SUBSTITUTE 27 × `463779` €289.17, F-01 · `POST /v1/products/462921/substitutes` → 10 ranked of 619 · needed today, needed in the past → no option, earliest date named · no date → offer, date not asked · `prefer` RELIABILITY, LOWER_CARBON, EARLIEST on 300 L of milk → same answer three times · 30 kg of beef → P-06, ceiling total.

**Guardrails (`guard.py`):** 5 × (offer 250 L lactose-free milk, order) → 4 ORDERED by the agent, 5th PENDING (P-02); availability of `469363` still 384 · ward agent with `allergen_strictness: DECLARED_ONLY`, `require_confirmed: false` → profile still enforced (18 declared, 4 not stated, excluded) · ward agent asks `469363` → excluded, rice-drink substitute to a human (P-05) · `profile_id` in a body → 422 · unconfirmed option ordered → roles purchasing manager and finance; finance approves → still pending; purchasing switches to option 1 → still pending, finance needed again.

**Optional directions (`opt.py`, `pages.py`):** `POST /v1/menus/plan` `last_minute_event` → 6 ingredients, yoghurt stands in for quark · standing order: 4 renewals placed alone, 290 L → PENDING (P-08) · `/mcp/` `tools/list`: `get_authority`, `search_products`, `get_product`, `find_substitutes`, `get_offer`, `place_order`, `get_order`, `get_audit` · pages `/`, `/approvals`, `/kitchen`, `/menu`, `/standing-orders`, `/assumptions` → 200; `POST /run` with `example=scenario-1` → result page, order page with the buyer's audit trail, approvals page with the approver switch.
