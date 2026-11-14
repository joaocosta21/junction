# P9b — the answers written in `AIMO/BOOTH-NOW.md` (V9), Valio's view of the log, and what is still open

Agent P9b, Saturday 14 Nov. Every "run" below is the offline recipe of the brief (replay, capture of Saturday 02:52, fresh data folder). Scratch scripts and their output: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/P9b/`. B7 is written from João's clarification of 14:51, as the coordinator asked.

## 1. In five lines
1. **Confirmed, nothing to build:** Q2, B2, B6, B11. **Confirmed with one bug found:** Q14 (a request in pieces swaps 1 for 1: 100 pieces become 100 cases). **Changed:** Q16, B13, B7.
2. **Q16:** the invoice follows the delivered weight, so "the total is a ceiling, never higher" is false in 7 code places and 14 document lines. Fix the wording now; drop the purchasing-manager sign-off for weight alone once the user's confirmation of V8 exists.
3. **B13:** Valio sees every step today (9 of 9 events) but not the decisions: no buyer rule, no reason, no role, no claim asked for, and 23 of the ward's 41 exclusions are missing. Show every rule that fired with its title, verdict and role; mask amounts and allergen codes; a role instead of a name; notes stay out. **DECISION.**
4. **B7:** claim-keeping candidates rank first, but claim-losing ones are shown as orderable beside them (241 of 573 capture products), the search stops widening at three orderable candidates whatever they lose (23 of 573: a keeper exists in a tier never searched), and a lactose-free product counts as "losing" low-lactose (180 of 1,099 losses are of this kind).
5. **Second visit:** 6 questions; first how and when they judge, then whether automatic ordering may be a buyer setting, then partial stock (after B5 it is our main scenario).

## 2. What exists today, and 3. what each answer changes

| Item | Valio's answer | What the build does today (verified by run unless said) | Verdict | Exact change |
|---|---|---|---|---|
| **Q2** (T03-1) | "take thw values as they are in the data." | `POST /v1/products/473609/substitutes`: `471881` → `passes: false`, `SUBSTITUTE_ADDS_ALLERGEN`, "adds 1 allergen … cereals containing gluten (AW, contains). It can never be ordered as a substitute." Rule F-05, `src/tta/policy/rules.yaml:201-213`; check in `src/tta/allergens/substitution.py`. `471881` carries the claim `FREE_FROM_GLUTEN` (`claims_lost: []`) and the sentence does not say that the two statements disagree. | Confirms | No code. Documents: `docs/ASSUMPTIONS.md:47`. Optional, 0.5 h, with P4: the failure sentence adds "the product file also gives it the claim FREE_FROM_GLUTEN; the two disagree and the declaration counts" (V5: flag a doubt). |
| **Q14** (T07-5) | "yes the goal is to satisfy the prompt" | `units_needed`, `src/tta/offers/candidates.py:241-245`: quantity ÷ content of one sales unit, rounded up to the lot step. In the capture `471690` is past its cut-off, so the conversion never shows. With the replay clock set to Thu 12 Nov 10:00 **in memory only**: 100 L of `473609` → 10 KI of `471690`, €155.50; 95 L → 10 KI. **But 100 UNIT of `473609` → 100 KI of `471690` (1,000 L), €1,555.00**: `_per_unit` returns one sales unit for a request in pieces (`candidates.py:299-301`), for the original and for the substitute alike. | Confirms for L and kg. Bug for pieces | `src/tta/offers/planning.py:225-227`: when the line names a product and is in `UNIT`, turn the gap into the original's content (pieces × litres or kg per piece) before `rank_substitutes`; a substitute whose content is not known is then not orderable (`PACK_SIZE_UNKNOWN`). One test. The bug appears in the demo as soon as P5 moves the clock before Thu 12 Nov 15:00. `471690` is a Terminal product: its quantity is never confirmed, so it always fires F-01. |
| **Q16** (Q9) | "what is actually delivered. like in a normal store" | 30 kg of `466988` as the hotel: €506.40, `totals.is_ceiling: true`, summary "The total is a ceiling: a product is sold by weight, so the invoice can be lower, never higher.", verdict `APPROVAL` by P-06, audit "30 KG of 466988 for at most €506.40 net". Rule `rules.yaml:385-402`; both profiles `variable_weight: APPROVAL` (`profiles/hotel-kitchen.yaml:20`, `allergy-ward.yaml:20`). | **Changes**: the delivered weight can be above the ordered one, so "ceiling", "at most" and "never higher" are false | Section 4, Q16. |
| **B2** | "yes" | Scenario 1, option 2: 1,000 × `464306`, F-01 and P-01, purchasing manager. F-01 `rules.yaml:142-155`. | Confirms | None. Under V8 F-01 still names the purchasing manager (P8). |
| **B6** | "yes" | Same run as Q2: `464320` and `471881` fail, `orderable: false`. F-05 is `BLOCK` for every buyer. | Confirms | None. |
| **B7** | "yes and only in the last case"; João 14:51: last resort, only when no product that keeps the claim can be supplied; still to a human; in doubt the safe product wins | Section 4, B7. | List confirmed (8 dietary claims, `src/tta/offers/substitutes.py:53-64`); F-08 confirmed; **"last resort" is not what the build does** | Section 4, B7. |
| **B11** | "yes" | `src/tta/agent/days.py:145` ("1 to 7: always after today"); the parser gets the data clock (`src/tta/api/wiring.py:230`). `POST /v1/requests/parse`, no key, clock Sat 14 Nov: "by Monday" → 2026-11-16, "by Sunday" → 2026-11-15, "by Saturday" → 2026-11-21. | Confirms | None. For P5: "today" is the data clock's date; a clock before Mon 9 Nov makes "by Monday" a date before every `availableDate` of the capture (2026-11-16). |
| **B13** (T06-1) | "all the steps and decisions" | Section 4, B13. | **Changes** | Section 4, B13. |

## 4. Options and recommendation

### Q16 — variable weight
What the answer settles: the price per kilo is fixed, the weight is not, and the invoice can be lower **or higher** than quantity × price. What it does not settle: how far the delivered weight may differ. We state no bound (assumption: none is in the data; not asked).

| Option | What | Cost | For / against |
|---|---|---|---|
| A, minimum | Wording only. "Estimated total: sold by weight, Valio Aimo invoices the weight delivered." P-06 keeps sending the line to the purchasing manager; its justification cites the answer instead of "an open question". The field `is_ceiling` keeps its name, with a corrected description. | 1.5 h (44 test lines pin the wording) | Makes every sentence true. Keeps a manual step that no longer protects anything: the purchasing manager cannot fix the weight either. |
| B, recommended | A, plus: the user's confirmation of V8 is the human step. The confirm screen shows the estimate and the sentence above. P-06 stays as a buyer's choice, the profile value `AUTO_WITH_CEILING` is renamed (for example `ESTIMATE`), `hotel-kitchen` uses it, `allergy-ward` keeps `APPROVAL`. Spend rules P-01 and P-02 compare the estimate and say "estimated". `is_ceiling` renamed `is_estimate`. | +1.5 h, after P8 | 20% precision (one manual step less for every meat order) and 20% controls (the rule is still there, as a setting). Touches the published contract. |
| C | B, plus a tolerance setting (for example +10%) used by P-01 and P-02. | +1.5 h | Not recommended: no data on tolerance, and the mock has no invoice to compare with. |

**DECISION D2.** Recommendation: A now, B when P8's confirmation flow is in. Cut C. Criterion: 20% autonomy and controls, 20% precision, 15% exceptions (delivery constraint).
Also true today, not run (read in `src/tta/policy/facts.py:349-353`): a product whose file does not say whether it is sold by weight (3,068 of 17,546, `AIMO/FINDINGS.md:89`) is a missing fact and goes to a human (F-03). Leave it; say so on `/assumptions`.

### B7 — a substitute that loses a dietary claim is a last resort
**What the build does** (hotel profile, capture clock):
- Ranking key, `src/tta/offers/substitutes.py:253-266`: passes the allergen rule → keeps every dietary claim → category distance → listed by Valio → pack → verification → price. Run on `473609`: ranks 1–6 keep every dietary claim, ranks 7–11 lose one (`465793` VEGAN; `468359` and `468887` FREE_FROM_GLUTEN and VEGAN; `460394`, `462322` FREE_FROM_GLUTEN), ranks 12–13 fail the allergen rule.
- The offer takes the first ranked candidate that gives a line (`src/tta/offers/planning.py:230-238`), so among the candidates shown a keeper is always taken before a loser. A loser fires F-08 → purchasing manager (`rules.yaml:255-268`; `tests/offers/test_checks_and_edges.py:260-275`, read, not run).
- A request by product type never gets a claim-losing product: the claim is a search filter and no substitute is looked for (`planning.py:201-203`).

**Three gaps against "last resort"**, counted by my script over the 573 products of the capture that carry a dietary claim (default substitutes query):
1. **Shown while a keeper is available.** The list (`POST /v1/products/{id}/substitutes`, scenario 3's page) shows claim-losing candidates with `orderable: true` beside keepers. `473609`: 5 losers shown while 3 keepers have confirmed stock (`475224`, `469512`, `473424`) and one more can be ordered unconfirmed (`468465`). Capture: 241 of 573 products by today's count of a loss (252 once the false losses of gap 3 are taken out).
2. **Not exhausted.** `_shown` (`substitutes.py:226-242`) widens to the next category tier only until three candidates can be ordered, whatever they lose. For 30 of 573 the first candidate that can be ordered loses a claim. For 23 of them a candidate that keeps every claim can be ordered in a wider tier that was never searched. But that keeper is often another kind of product: for `463299` (a cooking and whipping blend) it is `465793`, an almond drink; for `460032` (a 25 kg low-lactose milk powder) it is `468932`, a 200 g sour cream dip.
3. **False losses.** `claims_lost` compares codes one by one (`substitutes.py:217-223`): a lactose-free product "loses" `LOW_LACTOSE`, a vegan one "loses" `VEGETARIAN`. 180 of the 1,099 claim-losing orderable candidates shown are of this kind, and 14 of the 30 first-rank cases of gap 2 (`463047` low-lactose milk → `469363` lactose-free milk); 16 of the 30 are real losses. Each one is a needless F-08 approval today, and with a last-resort rule the safer product would be the one held back.

**Exact change** (one owner with P10, same file):
- `claims_lost`: `FREE_FROM_LACTOSE` keeps `LOW_LACTOSE`; `VEGAN` keeps `VEGETARIAN`. **DECISION D4**: a biomedical member confirms the two (nothing else: gluten-free does not cover wheat-free).
- `rank_substitutes` (`substitutes.py:135-151`): when at least one keeper can be ordered, claim-losing candidates leave the ranked list, with a note ("5 candidates that lack a dietary claim of the original are held back: 4 that keep it can be supplied"). The offer reads the same list, so it cannot take one. When no keeper can be ordered they are shown, labelled last resort, and F-08 still sends them to a human.
- `tests/offers/test_dietary_claims.py:45-49` expects the almond drink in the orderable list: it changes.
- **DECISION D3**: when no product of the same category keeps the claim, widen to other categories for a keeper, or offer the same-category product that loses it, to a human? Recommendation: do not widen for this until P10's "same kind" rule exists (the two examples of gap 2); the last resort stays in the same category, to a human, and says "no product of this category that keeps the claim can be supplied". Criterion: 15% exceptions, 20% precision.

### B13 — what Valio sees in the log
**Two readings** of "all the steps and decisions": (a) every step and every decision with its reason, the buyer's private values not asked for; (b) everything, the private values included. The note does not say which. The proposal below satisfies (a) fully and is one question away from (b) (section 8, question 5).

**What Valio's reader gets today** (`GET /v1/audit` with `demo-supplier-valio-aimo`; scenario 1 ordered, then approved on option 2 with a note; scenario 2 ordered alone). The supplier token is refused elsewhere: 403 on `/v1/authority`, on `/v1/orders/{id}` and on `reader=buyer` in the run (`src/tta/api/service.py:59-60, 297-300`).
- Every step: 9 of 9 events in scenario 1, 6 of 6 in scenario 2, same ids and hashes as the buyer's (`src/tta/audit/views.py:51-64`).
- **Not seen:**
  1. The buyer's words (`supplier_sentences.py:62-65`).
  2. What was asked beyond type, quantity, unit, date: claims, labels, name terms, preference (`facts.py:36-39`). Scenario 1 reads "1,000 litres of product type milk": the lactose-free claim is gone, so the log does not explain why only lactose-free milk was offered.
  3. Every buyer rule: P-00 to P-08, F-02, and **F-09** (not in `SUPPLIER_RULE_MEANINGS`, `readers.py:15-23`, although it is a fixed rule). When only such a rule fires the sentence gives no reason: "The buyer's rules were checked for option opt_1: a human at the buyer must approve this order."
  4. For every rule: its sentence, the facts it read, the role that must sign, the decision's sentence, the policy hash (`facts.py:135-144`).
  5. Exclusions for allergen reasons (`facts.py:44`): for the ward Valio's counts show 18 exclusions (12 cut-off passed, 6 not deliverable) of 41; the 18 "allergen declared" and 5 "allergen not stated" are missing, and the sentence drops the count ("1 option from 51 candidates").
  6. Constraint checks, option titles and summaries, the allergen mark of each line, the offer's notes (`facts.py:23-24, 61-75, 98`).
  7. Who approved: "A human at the buyer", no role (`readers.py:25, 32-38`); which rules the approval accepted; the option it replaced; the note.
  8. On the page (`/orders/{id}?view=supplier`) the section "The policy decision in force" is not rendered (`src/tta/ui/templates/order.html:72-90`).
- Checked in the supplier's JSON of scenario 1: 0 occurrences of the note, of "Hanna", "purchasing", "750", "P-01", "FREE_FROM_LACTOSE" and of the buyer's sentence; "F-01" 7 times.

**Proposal: every step and every decision, with the rule that fired and its outcome.** For each rule: id, title (fixed text of `rules.yaml`, it never holds a value), fixed or buyer's rule, verdict, role that must sign, product it fired on. For each exclusion reason: the count, allergen reasons included.

| Buyer's private value | Proposal | Reason |
|---|---|---|
| Limit amounts (per order, per day, minimum fill, drift tolerance), the day's spend | **Mask**: the rule and its outcome are shown ("P-01, the order is above the buyer's spend limit per order: purchasing manager"), never the amount | The decision is what Valio asked for. The amount is the buyer's position towards its supplier: a seller who knows the ceiling can pack an offer just under it. The order total is visible, so Valio learns only "the limit is below this total". |
| Allergen exclusions (codes, strictness) | **Mask**: rules F-02 and P-04 by id and title, and the two exclusion counts with plain labels ("18 declare an allergen the buyer excludes, 5 state nothing about one"); no code, no product list for these two reasons | It says something about the people the buyer feeds. The count of products that state nothing is the line Valio can act on: missing data cost it those 5 candidates (V5). |
| What was asked: claims and labels | **Show** | Closed code lists of Valio's own file, the same kind of filter as the product type. Without them the log is misleading (point 2). |
| The buyer's own words, name terms | **Leave out** | Free text can hold anything, an exclusion or a person's name. |
| Approver names and ids | **Mask to the role** ("the buyer's purchasing manager approved") | The role is part of the decision. The name is an employee's personal data and adds nothing for Valio. |
| Notes | **Leave out** | Free text. The approval form promises it: "kept in the buyer's audit trail, never shown to the supplier" (`src/tta/ui/templates/approvals.html:93`). |

**DECISION D1.** Recommendation: the table above. Minimum version (2 h): sentences and facts only, `src/tta/audit/readers.py` (`SUPPLIER_RULE_MEANINGS` gives way to the titles of the fired rules), `supplier_sentences.py`, `facts.py`, `phrases.py`, tests in `tests/audit/` (19 pinned lines). Full (+1.5 h): the supplier's page shows the decision section and, per reason about Valio's own data, the products that dropped out. Old events keep their old sentences (both are sealed in the hash), so the order book must start empty, which `docs/DEPLOY.md` already plans. Criterion: 20% "how decisions are logged and auditable"; the brief's audit trail "for buyer and Valio Aimo".

## 5. Work items

| Id | What | Files | Hours | Who | Criterion | Depends on |
|---|---|---|---|---|---|---|
| **MIN** | The 2-hour version of this topic: B13-1 without the exclusion counts (1 h), Q16-1 on the 3 strings a user sees (0.5 h), DOC-1 for those two (0.5 h) | as below | 2 | computer-science member | 20% controls | D1, D2 |
| B13-1 | Supplier view names every rule that fired (id, title, verdict, role), shows asked claims and labels, counts every exclusion reason, a role instead of "a human at the buyer" | `src/tta/audit/{readers,supplier_sentences,facts,phrases}.py`, `tests/audit/` | 2 | computer-science member | 20% controls | D1 |
| B13-2 | Supplier page: decision section, dropped products per supplier-data reason, banner text | `src/tta/ui/templates/order.html`, `src/tta/ui/order_page.py` | 1.5 | any member | 20% controls, 30% demo | B13-1 |
| Q16-1 | "Estimated total, invoiced by delivered weight" in place of ceiling wording; P-06 justification | `src/tta/offers/options.py:47`, `src/tta/audit/phrases.py:192`, `src/tta/ui/templates/order.html:67`, `_result.html:91`, `src/tta/ui/kitchen_page.py:66`, `src/tta/contracts/offer.py:107`, `src/tta/policy/rules.yaml:397-402`, tests | 1.5 | biomedical member | 15% exceptions, 15% assumptions | D2 |
| Q16-2 | Rename `is_ceiling` and `AUTO_WITH_CEILING`; hotel profile without sign-off for weight alone; P-01 and P-02 say "estimated" | `src/tta/contracts/{offer,common}.py`, `src/tta/policy/`, profiles, tests | 1.5 | computer-science member | 20% precision, 20% controls | D2, P8 |
| B7-1 | Covered claims; claim-losing candidates held back while a keeper can be ordered, with the note | `src/tta/offers/substitutes.py`, `substitute_wording.py`, `tests/offers/` | 1.5 | computer-science member (D4: biomedical member) | 15% exceptions, 20% precision | D4, P10 |
| B7-2 | Widening rule for keepers | `src/tta/offers/substitutes.py:226-242` | 1 | with P10 | 15% exceptions | D3, P10, P7 |
| Q14-1 | A request in pieces converts by content before a substitute is ranked | `src/tta/offers/planning.py`, `tests/offers/` | 1 | computer-science member | 20% precision | P5, P10 |
| DOC-1 | The lines of section 9 | documents | 1 | biomedical member | 15% assumptions | the items above |
| BOOTH-2 | Second visit, section 8 | none | 0.5 | any member | all | none |

Cut first: B13-2, then Q16-2, then B7-2, then Q14-1 (only if P5 keeps the clock after Thu 12 Nov 15:00 and no demo request is in pieces).

## 6. What changes in the demo
- **Supplier tab, scenario 1.** Today: "The request was read as: 1,000 litres of product type milk, needed by Monday 16 November 2026." and "…a human at the buyer must approve this order." After: "…of product type milk with claim FREE_FROM_LACTOSE…" and "…the buyer's purchasing manager must approve this order. Rule that applied: P-01 (the order is above the buyer's spend limit per order; the amount is not shown)."
- **Supplier tab, scenario 2.** Today: "1 option from 51 candidates." After: "…, 41 products excluded with a reason: 12 past their order deadline, 6 cannot be delivered, 18 declare an allergen the buyer excludes, 5 state nothing about one."
- **Beef backup** (30 kg of `466988`, €16.88/kg). Today: "€506.40 … The total is a ceiling … never higher", "for at most €506.40 net". After: "Estimated total €506.40: sold by weight, Valio Aimo invoices the weight delivered", "for about €506.40 net".
- **Scenario 3, substitutes list.** Today 13 candidates, 5 of them claim-losing and orderable (ranks 7–11). After: 8 candidates and the note that 5 are held back because 4 that keep every dietary claim can be ordered.
- Figures of scenarios 1 and 2 do not move because of this topic (B5 and V6 move them: P9a, P5).

## 7. Risks and what not to do
- Do not show limit amounts, allergen codes, names or notes to Valio before question 5 is answered; do not change the note's promise on the approval form.
- Do not keep "ceiling", "maximum", "at most" or "never higher" anywhere a judge can read it: Valio's own answer contradicts it.
- Do not widen the substitute search to "find a keeper" without P10's same-kind rule: the scan shows an almond drink standing in for a cooking cream.
- B13-1 and Q16-1 change sentences that tests pin (19 and 44 lines). Budget the test edits; do not delete the tests.
- A claim-losing product ordered by its own id is not a substitute for the gateway, so F-08 does not fire. The user's confirmation of V8 is the only check there (for P8 and P10).
- The B7 counts are over one capture (769 products, categories 104xx and 18720) and the hotel profile. They are not catalog figures.

## 8. Questions

### For the second booth visit (6, ranked by what the answer changes before Sunday 10:00)

`AIMO/BOOTH-ROUND-2.md` appeared at 15:07 (not mine, not edited). Its questions 1, 2, 4, 6 and 8 are my 1, 2, 3, 5 and 4. Two differences to settle when the lists are merged:
- Its question 6 says Valio's view shows "why products were left out" and hides only the private settings. Measured (section 4, B13): the view also hides **every buyer rule that fired** (no reason is given when only such a rule fires), the claims asked for, and the exclusions made for allergen reasons (23 of the ward's 41); the sentence carries no exclusion count. Ask it after B13-1 is built, with the wording of my question 5, or correct its example.
- My question 6 (what a confirmed order fixes) is not in it.

**1. How and when do you judge?** (question 23, open)
- **Context:** we can show the app at our table, in the 2-minute video, or on a deployed link. You told us the data is static and that we may choose the date.
- **Example:** on the link, every visitor shares one order book; at the table we start from an empty one and run each scenario once.
- **Ask:** "Do you judge at our table, from the video, or on the deployed link? And when?"
- **If nobody answers:** all three are prepared; the link runs on the recording.

**2. Automatic ordering as a buyer's setting** (the "question for later" of V8)
- **Context:** you said to switch automatic ordering off for now: the agent suggests, a person confirms.
- **Example:** the ward's 200 L of soya drink, €402.00, is inside every limit. Today the agent orders it alone.
- **Ask:** "May a buyer switch automatic ordering back on for orders inside its limits, as a setting that is off by default? Or should no order ever go without a person?"
- **If nobody answers:** off by default, the setting exists and is shown, never used in the main demo (P8).

**3. Stock that covers only part of an order** (question 20, open; after B5 it is our main scenario)
- **Context:** without coffee milk, confirmed lactose-free milk covers 435 of the 1,000 litres in our main request (`AIMO/BOOTH-QUESTIONS.md:441`, to be re-measured by P9a and P5).
- **Example:** 384 L of Arla semi-skimmed + 51 L of Arla fat-free = 435 L confirmed; 565 L missing.
- **Ask:** "When stock covers only part of a line, what do you do today: deliver the part, offer a substitute for the rest, or drop the line? What should the agent suggest first?"
- **If nobody answers:** the part with confirmed stock first, the full quantity with unconfirmed stock second, both for a person to confirm.

**4. Your data in our public repository** (question 26, open)
- **Context:** the submission must be a public repository under the MIT licence by Sunday 10:00.
- **Example:** it holds 4 of your data files and 18 recorded API answers; the README says they are yours and not under our licence.
- **Ask:** "May they stay in the public repository, or must we take them out?"
- **If nobody answers:** they stay, with the README note (the team decides; taking them out later means rewriting history).

**5. Your view of the log** (B13, partly answered)
- **Context:** you asked to see all the steps and decisions. We now show you every rule that fired and its outcome.
- **Example:** "P-01, the order is above the buyer's spend limit per order: sent to the buyer's purchasing manager". We do not show the limit (€750), which allergens the buyer excludes, the approver's name or her note.
- **Ask:** "Is the decision without the buyer's private values what you meant, or do you want to see those values too?"
- **If nobody answers:** masked, as in section 4.

**6. What does a confirmed order fix?** (questions 5 and B14, open)
- **Context:** a person now confirms every order. There is no order endpoint, so "ordered" means recorded in our order book.
- **Example:** Valio Eila lactose-free milk: price €1.01 valid to 31 Dec, delivery Monday if ordered by Sunday 17:00, stock unknown.
- **Ask:** "When a customer confirms an order with you, what is fixed at that moment: the price, the quantity, the delivery date?"
- **If nobody answers:** the record says which statements it relied on and that it commits nobody.

### Every question, with its status
**`AIMO/BOOTH-NOW.md`, part A**

| No | Ref | Status | By |
|---|---|---|---|
| 1 | SCOPE-1 | Partly | V2 (the three core needs and the three optional directions, per user pattern), V1 (order patterns may be generated). A field for new or seasonal products: open |
| 2 | T03-1 | Answered | V9 Q2 |
| 3 | Q1 | Answered for the demo | V6, B3 (we choose the date). Whether a passed deadline is final in production: not said |
| 4 | Q7 | Partly | V1 (generate the data), V8. No real example of a limit |
| 5 | Q4 | Open | second visit, 6 |
| 6 | DATA-1 | Partly | V5 (noisy data, flag doubts), V6 (static data). Which source wins: open |
| 7 | Q10 | Open | |
| 8 | ALMOND-1 | Answered in principle | V5 (not sure → flag to the user); what we do matches |
| 9 | T03-2 | Partly | V5, Q2. Our two readings not confirmed |
| 10 | Q5 | Answered in principle | V5 |
| 11 | Q2 | Partly | V5. GS1 meanings and who accepts "may contain": open |
| 12 | — | No such number in the file | T02-1 (lot size 0.01) was dropped from the list and was never asked |
| 13 | T02-2 | Open | |
| 14 | T07-5 | Answered | V9 Q14 |
| 15 | Q8 | Open | |
| 16 | Q9 | Answered | V9 Q16 |
| 17 | Q11 | Answered: not known | V7. Names of categories: not given |
| 18 | Q12 | Open | |
| 19 | OFFER-1 | Partly | V8 (suggest, the user confirms), V4, V10. Baskets or per product: open |
| 20 | Q6 | Open | second visit, 3 |
| 21 | Q13 | Open | matters less: V6 |
| 22 | T01-1 | Open | |
| 23 | — | Open | second visit, 1 |
| 24 | — | Partly | V6 ("the goal is to show that the program is doing this stuff") |
| 25 | — | Answered | V4 (a webshop login was given) |
| 26 | — | Open | second visit, 4 |
| 27 | S2-1 | Open | handling covered by V5 |
| 28 | S2-2 | Open | handling covered by V5 and Q2 |

**`AIMO/BOOTH-NOW.md`, part B**

| No | Status | By |
|---|---|---|
| 1 | Answered, changed | V8 |
| 2 | Answered | "yes" |
| 3 | Answered | B3, V6 (P5) |
| 4 | Open | consistent with Q2 |
| 5 | Answered, changed | "no be explicit" (P9a) |
| 6 | Answered | "yes" |
| 7 | Answered, changed | "yes and only in the last case", clarified 14:51 |
| 8 | Partly | V5 and the B7 clarification support the safer reading |
| 9 | Partly | V5 |
| 10 | Open | |
| 11 | Answered | "yes" |
| 12 | Open | |
| 13 | Answered, changed; one reading open | second visit, 5 |
| 14 | Open | second visit, 6 |

**`AIMO/BOOTH-QUESTIONS.md`, "Raised during the overnight build"**

| Group | Ids | Status |
|---|---|---|
| For Valio, answered | T03-1 (Q2), T07-5 (Q14) | Answered |
| For Valio, partly | SCOPE-1 (V2, V1), T03-2 (V5, Q2), ALMOND-1 (V5), OFFER-1 (V8, V10), DATA-1 (V5, V6), STAND-1 (V1, V2: the history is ours to generate), MENU-1 (V10: formula matters; no data offered) | Partly |
| For Valio, open | T01-1, T02-1, T02-2, S2-1, S2-2, SUST-1, SUST-2 | Open. T02-1, SUST-1 and SUST-2 are not in `BOOTH-NOW.md` and were never asked |
| For the team, settled by an answer | T06-1 (B13), T02-4 and FIX3-1 (B5), T07-1 and T07-7 (B7), T10-3 (B11), T03-3 (partly: V5, B7 clarification) | Answered |
| For the team, changed by an answer | T04-1, T12-1, T12-3, T14-2 (V8: no order without a person); T01-2, T06-2, T07-6, T13-1 (V6: the date); T05-1 (V7, V10); T05-2, T12-2 (Q16); T07-2, T07-3 (V10, Q14); FALLBACK-1 (Q2 and B7: keep the stricter reading); STAND-2 (V1) | To re-decide in the plan |
| For the team, not touched | T02-3, T07-4, T08-1 to T08-4, FIX6-1, FIX6-2, FIX7-1, FIX7-2, T09-2 to T09-4, T10-1, T11-1, FIX8-1 to FIX8-3, FALLBACK-2 | Open, ours |
| For information | T05-3, T09-1 (done: the trail starts with "request received", seen in the run), T10-2, T10-4, T10-5, T11-2, T12-4, T14-1 | Closed |

## 9. Document lines the answers make wrong or out of date
Only for the answers of this topic. `CLAUDE.md`: no line is made wrong by them (V8 and V6 touch it: P8, P5).

| Line | Now says | Corrected sentence |
|---|---|---|
| `docs/ASSUMPTIONS.md:24` | the total is a ceiling, "the invoice can be lower, never higher"; "Valio question Q9, still open" | "A variable-weight line shows an estimated total. Valio Aimo invoices the weight actually delivered ('like in a normal store', booth, 14 Nov), so the invoice can be lower or higher. A product whose file does not say is a missing fact (F-03)." |
| `docs/ASSUMPTIONS.md:125` | "…and whether a variable-weight invoice uses the ordered weight." | "Whether deposits are in the price." (the weight question is answered: delivered weight) |
| `docs/ASSUMPTIONS.md:47` | changes if "Valio corrects the data (T03-1)" | "Valio Aimo said on 14 Nov to take the values as they are in the data (T03-1)." |
| `docs/ASSUMPTIONS.md:48` | "A substitute that loses one ranks lower and always needs a human (F-08)." | "A substitute that loses one is a last resort: it is offered only when no product that keeps the claim can be supplied, and it always needs a human (F-08). Confirmed by Valio Aimo, 14 Nov." |
| `docs/ASSUMPTIONS.md:49` | changes with "Valio's answer to T07-5" | "Confirmed by Valio Aimo on 14 Nov: 'the goal is to satisfy the prompt'. A request in pieces is converted by content too." (true once Q14-1 is in) |
| `docs/ASSUMPTIONS.md:74` | the supplier's view hides "the buyer's own rules"; shows "rules F-01, F-03 to F-08" | "The supplier's view shows every step and every rule that fired, with its outcome and the role that must sign. It hides limit amounts, allergen codes, approver names, notes and the buyer's own words. Valio Aimo asked for 'all the steps and decisions' on 14 Nov." |
| `docs/ASSUMPTIONS.md:88` | "The team's answer to T10-3." | "Confirmed by Valio Aimo on 14 Nov (B11)." |
| `AIMO/FINDINGS.md:89` | "Open point: whether delivered weight equals ordered weight (booth Q9)." | "Valio Aimo answered on 14 Nov: the invoice is for the weight actually delivered." |
| `AIMO/SPEC.md:176` | "`is_ceiling` for variable weight" | "an estimate flag for variable weight: the invoice follows the delivered weight" |
| `AIMO/SPEC.md:186` | "ranks after those that keep every one, and ordering it always needs a human (F-08)" | "is held back while a product that keeps every dietary claim can be supplied, and ordering it always needs a human (F-08)" |
| `AIMO/SPEC.md:239` | "`APPROVAL` or `AUTO_WITH_CEILING`" | the new value's name (Q16-2); until then: "`AUTO_WITH_CEILING` is misnamed: the total is an estimate" |
| `AIMO/SPEC.md:287-288` | Valio does not see "The buyer's limit values, allergen exclusions, approver names and notes" | Sees: add "every rule that fired, with its outcome and the role that must sign". Does not see: "limit amounts, allergen codes, approver names, notes, the buyer's own words" |
| `AIMO/SPEC.md:336` | "the total is a ceiling; verdict `APPROVAL` (variable weight)" | "the total is an estimate (invoiced by delivered weight); verdict as decided in D2" |
| `AIMO/WALKTHROUGH.md:278, 529, 646` | "a ceiling", "the invoice can be lower, never higher" | "an estimate: Valio invoices the weight delivered" |
| `AIMO/WALKTHROUGH.md:1149-1157` | Q9 as an open question, "Built while waiting: the total is marked as a ceiling" | "Answered 14 Nov: what is actually delivered." |
| `AIMO/WALKTHROUGH.md:414-419, 895, 1279` | only fixed rules that rest on Valio's data are named; no role | as `docs/ASSUMPTIONS.md:74` above; row V13 answered: "all the steps and decisions" |
| `AIMO/PLAN.md:99` | "the order carries a spend ceiling, not an exact total" | "the order carries an estimated total: the invoice follows the delivered weight" |
| `AIMO/PLAN.md:225` | "Human approval until Valio says how they are invoiced (booth Q9)" | "Invoiced by delivered weight (Valio Aimo, 14 Nov): the total is an estimate" |
| `README.md:75` | "`reader=supplier` … which hides the buyer's limits, exclusions, approver names and notes" | "…which shows every step and decision and hides limit amounts, allergen codes, approver names and notes" |
| `docs/DEMO.md:38, 100-101, 121`, `docs/PITCH.md:31, 69` | ceiling wording; "Valio sees … without the buyer's limits or names" | estimate wording; "Valio sees every step and every decision; amounts and names stay with the buyer" |
| Code texts, same error | `src/tta/policy/rules.yaml:401-402`, `src/tta/offers/options.py:47`, `src/tta/contracts/offer.py:107`, `src/tta/ui/templates/order.html:16-19, 67`, `_result.html:91`, `src/tta/api/routes.py:249-250`, `src/tta/audit/readers.py:1` | with Q16-1 and B13-1 |
