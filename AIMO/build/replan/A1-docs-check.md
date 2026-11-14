# A1 — Do the documents say what the code does?

Checked on Saturday 14 Nov, 14:45–15:10, at commit `7f09ce7`, offline (replay, capture `2026-11-14-demo`, no key, no outside call). Scripts and page dumps: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/A1/` (`run1.py`…`run5.py`, `count.py`, `paths.py`, `out/`).

## 1. In five lines

1. About 600 statements checked (counts are approximate): about 260 sentences and figures of `docs/DEMO.md` run through the test client; about 60 REST, MCP and docs-page statements; 16 catalog and capture figures recounted from the raw files; 22 commit ids and every backticked file path of the ten documents by script; about 60 constants, rule ids, routes and settings read in the code.
2. **26 are wrong.** None is a wrong demo figure: every price, total, quantity, count and rule id in the demo paths matched. All 26 are sentences left over from before the afternoon's four parts, or from the morning.
3. **Worst 1:** `docs/ASSUMPTIONS.md` lines 148, 150, 153, 166, 168 still say recipe logic, ranking by reliability and standing orders are **not built**. The app serves these lines at `/assumptions` (checked: status 200, both sentences on the page), next to rows that say they are built.
4. **Worst 2:** four documents still say the fixed rules are F-01 to F-08 and the kitchen settings P-00 to P-07 (`docs/ASSUMPTIONS.md`:60, :111 · `docs/DEMO.md`:145 · `AIMO/WALKTHROUGH.md`:764). The page shows F-09 and P-08.
5. **Worst 3:** `AIMO/build/MORNING.md`:3 says "local only: nothing was pushed". The local ref `origin/overnight-build` is at `7f09ce7`, the same as HEAD, so the branch was pushed, with Valio's four data files tracked in it. Also `docs/DEMO.md`:151, `MORNING.md`:44 and `WALKTHROUGH.md`:766 describe a "could not run" message for My kitchen that the page no longer shows.

**Not covered:** `AIMO/WALKTHROUGH.md` sections 1–11, 13–15 and 17, and `AIMO/SPEC.md` sections 1, 3, 4, 6, 8, 9, 10 were only searched for the afternoon's terms, not read line by line. The full test suite did not finish (section 3).

### Wrong statements per document

| Document | Wrong | Lines |
|---|---|---|
| `docs/ASSUMPTIONS.md` | 8 | 27, 60, 111, 148, 150, 153, 166, 168 |
| `AIMO/WALKTHROUGH.md` | 6 | 764, 766, 1002, 1066, 1168, 1179 |
| `AIMO/build/MORNING.md` | 5 | 3, 12, 15, 44, 92 |
| `docs/DEMO.md` | 3 | 136, 145, 151 |
| `README.md` | 2 | 29, 44 (both small) |
| `docs/AWARDS.md` | 1 | 65 |
| `docs/PITCH.md` | 1 | 87 (small) |
| `AIMO/SPEC.md`, `docs/ARCHITECTURE.md`, `docs/STANDARDS.md` | 0 | in the parts checked |

## 2. Wrong

"Run" means run offline through `fastapi.testclient` with the brief's recipe, each path from an empty book.

| # | Document and line | What it says | What is true | How I checked | Corrected sentence |
|---|---|---|---|---|---|
| 1 | `docs/ASSUMPTIONS.md`:148 (Out of scope) | "Recipe to order and proactive selling: every input would be invented." | Recipe to order is built: `/menu`, `POST /v1/menus/plan`, rule F-09. The same file says so at line 100. Proactive selling is not built. | Run: `/menu?example=event` → €476.48, F-09 + P-06. `GET /assumptions` holds the old sentence. | "Proactive selling (a selling agent of Valio's own): not built. Recipe to order is built with a recipe table that is ours and illustrative (row "Recipes")." |
| 2 | `docs/ASSUMPTIONS.md`:150 | "Ranking by delivery reliability or carbon: the values are loaded but not used." | `prefer` = `RELIABILITY` or `LOWER_CARBON` ranks confirmed products (`src/tta/offers/preference.py`; line 96 of the same file). | Run: example 5 gives `470863` at €140.00 over `472145` at €133.00. | Delete the line, or: "A profile limit on how much more a preference may cost before a human decides: not built." |
| 3 | `docs/ASSUMPTIONS.md`:153 | "Standing orders: no order is renewed and none is compared with the buyer's history. … A next step below." | Built: `/standing-orders`, four REST routes, rule P-08 (line 99 of the same file). | Run: renew 100 L → ordered alone, €248.00; 290 L → P-08. | Delete the line, or: "A customer's real order history: the demo history is synthetic (row "Standing orders")." |
| 4 | `docs/ASSUMPTIONS.md`:166 (next step 9) | "Delivery reliability and sustainability in the comparison." | Built (`docs/STANDARDS.md`:141 says "Built"). | As row 2. | "9. A profile limit on how much more a preference may cost before a human decides; Valio's word on the carbon unit." |
| 5 | `docs/ASSUMPTIONS.md`:168 (next step 11) | "Standing orders: a renewal the agent can ask for, and a rule like P-02 …" | Built (`docs/STANDARDS.md`:143 says "Built"). | As row 3. | "11. Standing orders on the customer's real order history; a separate tolerance for price." |
| 6 | `docs/ASSUMPTIONS.md`:27 | Delivery reliability "is not used in ranking yet." | It ranks when the request prefers reliability. | As row 2. | "It ranks confirmed products only when the request says `prefer: RELIABILITY` (row "Preference")." |
| 7 | `docs/ASSUMPTIONS.md`:60 | "Fixed rules F-01 to F-08 cannot be switched off by a profile." | Nine fixed rules: F-09 exists (`src/tta/policy/rules.yaml`:273). | Read the file; F-09 fired in the menu run. | "Fixed rules F-01 to F-09 cannot be switched off by a profile." |
| 8 | `docs/ASSUMPTIONS.md`:111 | "The fixed rules F-01 to F-08 apply whatever is set." The settings listed leave out the drift tolerance. | `/kitchen` lists F-01 to F-09 and has the field `standing_order_drift_ratio` (P-08). | Run: `GET /kitchen`. | "…(spend limits, minimum fill, allergen rule, substitutes, standing-order tolerance)… The fixed rules F-01 to F-09 apply whatever is set." |
| 9 | `docs/DEMO.md`:145 | "Each setting shows the rule it drives (P-00 to P-07) … below the form are the fixed rules F-01 to F-08" | The page shows P-00 to P-08 and F-01 to F-09. | Run: `GET /kitchen`, each id found once. | "…the rule it drives (P-00 to P-08) … the fixed rules F-01 to F-09, under "Always, whatever you set"." |
| 10 | `docs/DEMO.md`:151 | Without a key the result page says "The buyer agent could not run: This sentence was recorded for another buyer profile …" and "Read from the typed request of this example". | Neither sentence is on the page. The rule-based reader reads the pasted sentence. The page says: "No Gemini key is set, so this run was read and made by fixed rules, not by a model." The verdicts are as written. | Run: kitchen path steps 2–4. | "**Without a Gemini key** the result page says "No Gemini key is set, so this run was read and made by fixed rules, not by a model.": the recordings are for `hotel-kitchen` and `allergy-ward`, so the fixed rules read the sentence. The verdicts above are the same." |
| 11 | `docs/DEMO.md`:136 | ""Too many requests" on a page: this address used its minute (20 offers, 20 orders, 5 agent runs)." | 20, 20 and 5 are the windows of one browser on the pages. One address has 60, 60 and 15 (`src/tta/api/limits.py`:65–72; line 33 of the same file). | Read the constants. | "…this browser used its minute (20 offers, 20 orders, 5 agent runs), or the address its 60, 60 and 15." |
| 12 | `AIMO/WALKTHROUGH.md`:764 | "(P-00 to P-07) … the fixed rules F-01 to F-08" | As row 9. | As row 9. | "(P-00 to P-08) … the fixed rules F-01 to F-09" |
| 13 | `AIMO/WALKTHROUGH.md`:766 | "Known gap: without a working Gemini model, a run as My kitchen agent first says the recorded sentence was made for another profile, then uses the example's typed request." | As row 10. The gap is closed by the rule-based reader. | As row 10. | "Without a working Gemini model, a run as My kitchen agent is read by the fixed rules and says so. The verdicts are the same." |
| 14 | `AIMO/WALKTHROUGH.md`:1002 (question SCOPE-1) | "plus two of the six scenarios … The buyer limits live in two profile files, and no page can edit them yet." | `/kitchen` edits them. Standing-order drift and recipe to order are built too. | Run: kitchen, standing-order and menu paths. | "…plus four of the six scenarios: the two above, standing-order drift (P-08) and recipe to order (F-09). The buyer sets its limits on `/kitchen`." |
| 15 | `AIMO/WALKTHROUGH.md`:1066 (question OFFER-1) | "at most three whole-order options (best confirmed, quantity not confirmed, substitute)" | A fourth kind exists: `CHEAPEST_CONFIRMED` is added under a preference, and `AIMO/SPEC.md`:171 gives four options as the most. | Run: 10 L cream, `prefer: RELIABILITY` → three options at once, `BEST_CONFIRMED`, `CHEAPEST_CONFIRMED`, `ALTERNATIVE_UNCONFIRMED`. Four at once was not produced. | "at most three whole-order options, four when a preference adds the cheapest confirmed one" |
| 16 | `AIMO/WALKTHROUGH.md`:1168 (question Q11) | "We also wrote 30 product types of our own" | 31 keys in `src/tta/catalog/product_types.yaml` (`docs/AWARDS.md`:22 and `docs/ASSUMPTIONS.md`:50 say 31). | Counted the keys of the YAML file. | "We also wrote 31 product types of our own" |
| 17 | `AIMO/WALKTHROUGH.md`:1179 (question Q12) | "The value does not change the ranking yet." | It does under `prefer: RELIABILITY`. | As row 2. | "The value ranks products only when the request prefers reliability; a product with no value ranks last." |
| 18 | `AIMO/build/MORNING.md`:3 | "Branch `overnight-build`, local only: nothing was pushed. To share it: `git push -u origin overnight-build`." | `origin/overnight-build` is at `7f09ce7` = HEAD; `git status -sb` shows no commit ahead. A remote-tracking ref moves only on a push or fetch. I did not contact GitHub. | `git rev-parse --short origin/overnight-build`, `git status -sb`. | "Branch `overnight-build`, pushed to `origin` (at `7f09ce7`)." |
| 19 | `AIMO/build/MORNING.md`:12 | "run example 1 as "My kitchen agent": `ORDERED`, `AUTO`" | The example button brings its own agent: pressed with My kitchen chosen, it runs as the hotel kitchen and waits for approval. Pasting the sentence as My kitchen agent gives `ORDERED`. | Run: both ways. | "choose My kitchen agent, paste example 1's sentence, press Run: `ORDERED`, `AUTO`" (as `docs/DEMO.md`:147 says) |
| 20 | `AIMO/build/MORNING.md`:15 | "`/v1/openapi.json` (OpenAPI 3.1, generated)" | `GET /v1/openapi.json` answers 404. The document is at `/openapi.json`. | Run. | "`/openapi.json` (OpenAPI 3.1, generated)" |
| 21 | `AIMO/build/MORNING.md`:44 | A run as My kitchen agent "first says "This sentence was recorded for another buyer profile", then uses the example's typed request." | As row 10. | As row 10. | Remove the row from "What is blocked", or: "read by the fixed rules; a recording for `my-kitchen` is still missing." |
| 22 | `AIMO/build/MORNING.md`:92 (point 10) | "Reliability and carbon loaded but unused … **Open.** Shown on `GET /v1/products/{id}` only." | Built this afternoon; section 1b of the same file says so. | As row 2. | "**Fixed** (`fa07e39`): shown on every offer line; `prefer` ranks by them." |
| 23 | `docs/AWARDS.md`:65 | "the per-browser limits of the pages (FIX-11) … are not deployed yet." | FIX-11 is commit `289a3c7`, an ancestor of `d342dfb` and `8163d5d`, which line 60 and `README.md`:5 say are deployed. | `git merge-base --is-ancestor 289a3c7 8163d5d`. The deployed app itself was not called. | "…the per-browser limits of the pages (FIX-11) do not, and they are on the deployed app since the redeploy of `d342dfb`." |
| 24 | `README.md`:29 | the page says "Read by fixed rules, not by a model" | The result page of a run says: "No Gemini key is set, so this run was read and made by fixed rules, not by a model." The quoted label is in `src/tta/agent/labels.py`:24–27 for a reading; I did not find it on a result page. Small. | Run: example 5 and the kitchen path. | the page says "No Gemini key is set, so this run was read and made by fixed rules, not by a model." |
| 25 | `README.md`:44 | "a time-out can hold a sentence for about 90 s" | The code waits 30 s, twice: about 60 s (`src/tta/agent/gemini.py`:63–65). `docs/AWARDS.md`:48 and `docs/STANDARDS.md`:142 say 60 s. Not timed against Gemini. | Read the constants. | "…for about 60 s before the recording answers." |
| 26 | `docs/PITCH.md`:87 | "returns an offer with up to three options" | Up to four by `AIMO/SPEC.md`:171 (row 15). Small; a draft. | As row 15. | "…with up to three options, and the cheapest confirmed one beside them when the buyer states a preference." |

## 3. Could not be checked

| Document and line | Why |
|---|---|
| `README.md`:5, :140 · `docs/AWARDS.md`:54, :60, :71, :96 · `WALKTHROUGH.md`:744, :772 · `MORNING.md`:16, :18 | What runs on the deployed app, and the 7 checks of `deploy/check.py` against it: no outside call allowed. (`deploy/check.py` does hold 7 checks.) |
| `docs/DEMO.md`:13 · `docs/PITCH.md`:3, :51 | The live check at 08:12 (6 calls): no outside call. |
| `MORNING.md`:9 ("3,009 passed, 63 skipped at `71f13f4`") | An earlier commit. At `7f09ce7` I started the full suite and stopped it at 23% after 12 minutes (load average 16, about 18 agents); no failure up to there. `pytest tests/e2e -q`: **16 passed** in 17 s. `ruff check src tests`: all checks passed. |
| `MORNING.md`:27, :36 | Which commits the booth copies on ports 8000, 8001 and 8002 run. Line 36 calls `284fee8` on port 8001 "current code"; HEAD is `7f09ce7`, so that sentence is at least out of date. |
| `MORNING.md`:68–70 · `AWARDS.md`:21, :23, :48, :90, :103–104 | Call counts, Gemini and Aiven timings, the one live Gemini check: history of outside services. |
| `AWARDS.md`:31 ("294 tests in `tests/agent/` after FIX-9") | A count at an earlier commit; not recounted. |
| `WALKTHROUGH.md`:760, :1059 · `MORNING.md`:57 ("18 products for milk/gluten, 7 for tree nuts", whole catalog) | Needs the gateway's ingredient matcher over the catalog; not recounted in the time. |
| `README.md`:41 · `ARCHITECTURE.md`:121 (unset `TTA_ENV` means `prod` and no start without `TTA_TOKENS`) | Not run. |
| `README.md`:137 · `docs/DEMO.md`:194 ("`EARLIEST` and `LOWER_CARBON` change no choice in tonight's capture") | True for the demo's categories (one carbon value each, section below); not run for every request. |
| `docs/DEMO.md`:33 (the "Too many requests" wording), :112 (two tabs, two approvers) | Not run. The limit numbers were read in the code and match. |
| `docs/STANDARDS.md`, the quotes from the specifications | My topic allows no web reading. Library versions match: FastAPI 0.162.7, `mcp` 2.3.0, `google-genai` 3.3.0, psycopg 3.3.9. |

## 4. Contradictions between documents

1. **Built or not built.** `docs/ASSUMPTIONS.md`:148, :150, :153, :166, :168 against `README.md`:26–28, `docs/STANDARDS.md`:141 and :143, `docs/PITCH.md`:54, `AIMO/SPEC.md`:342, and rows 96–100 of `ASSUMPTIONS.md` itself.
2. **Fixed rules.** "F-01 to F-08" (`ASSUMPTIONS.md`:60, :111 · `DEMO.md`:145 · `WALKTHROUGH.md`:764) against F-09 in `SPEC.md`:228, `ARCHITECTURE.md`:32, `README.md`:28.
3. **Reliability in the ranking.** "Not used yet" (`ASSUMPTIONS.md`:27 · `WALKTHROUGH.md`:1179 · `MORNING.md`:92) against `ASSUMPTIONS.md`:96, `SPEC.md`:172.
4. **How many options.** "Up to three" (`PITCH.md`:87 · `WALKTHROUGH.md`:1066) against "four with `CHEAPEST_CONFIRMED`" (`SPEC.md`:171 · `ARCHITECTURE.md`:55).
5. **Product types.** 30 (`WALKTHROUGH.md`:1168) against 31 (`AWARDS.md`:22 · `ASSUMPTIONS.md`:50). The file has 31.
6. **Wait on a Gemini time-out.** About 90 s (`README.md`:44) against about 60 s (`AWARDS.md`:48 · `STANDARDS.md`:142).
7. **My kitchen without a key.** "Could not run … typed request" (`DEMO.md`:151 · `MORNING.md`:44 · `WALKTHROUGH.md`:766) against the rule-based reader (`README.md`:29 · `WALKTHROUGH.md`:798–804).
8. **The deployed commit.** `MORNING.md`:16 "redeployed from `d342dfb` at 11:15" reads as current; `MORNING.md`:18, `README.md`:5 and `WALKTHROUGH.md`:744 say `8163d5d` at about 13:00.
9. **Per-browser limits deployed.** `AWARDS.md`:65 "not deployed yet" against `README.md`:5.
10. **Pushed or not.** `MORNING.md`:3 and the brief, section 3 ("nothing pushed") against the local ref `origin/overnight-build`.
11. **Aiven.** `CLAUDE.md` says "Aiven was dropped on 14 Nov"; `AWARDS.md`:94–104, `PITCH.md`:93 and `README.md`:121 present it as built and deployed (`MORNING.md`:48 already asks the team).
12. **Friday sample.** "1,000 random products" (`WALKTHROUGH.md`:940, the brief) against `product_count` 1001 in `fixtures/valio/2026-11-13-sample/manifest.json`.
13. **Two lists called V.** `WALKTHROUGH.md` section 17 numbers our decisions V1–V14; the brief numbers Valio's answers V1–V10. They are not the same items.

## 5. Made out of date by Valio's answers

Ids are the brief's (section 2). The booth sheet's "Q2", "Q14" and "Q16" are the walkthrough's `T03-1`, `T07-5` and `Q9`.

| Document and line | Which answer | What is now out of date |
|---|---|---|
| `README.md`:3, :10, :20, :26, :27 · `docs/DEMO.md`:10, :65–70, :79–80, :122, :147, :177, :189–192 · `docs/PITCH.md`:11, :13, :29, :41, :42, :70, :84, :89 · `docs/AWARDS.md`:27 · `AIMO/SPEC.md`:215, :254 · `WALKTHROUGH.md`:441, :779, :787 · `MORNING.md`:12, :23–25 | **V8** "for now deactivate automatic order … the final submition should always have the input from the user" | Every "the agent orders alone" outcome: scenario 2, scenario 3, the 100 L renewal, example 5, My kitchen at €3,000. |
| `README.md`:19 · `docs/DEMO.md`:9, :44, :50, :54–56, :119–121, :147 · `docs/PITCH.md`:27, :28, :66, :68 · `MORNING.md`:11, :51 · `WALKTHROUGH.md` section 3 and :1271 | **B5** "no be explicit" (coffee milk is not milk) | Option 1 of scenario 1: 565 of the 1,000 L are `463380` Arla Café milk. Without it the two other confirmed milks give 384 + 51 = 435 L, about €1,083.39 (my arithmetic on the page's prices, not run). €2,580.64 and "three confirmed milks" then change everywhere. |
| `docs/DEMO.md`:38, :77–80 · `MORNING.md`:50 · `docs/ASSUMPTIONS.md`:26, :48, :57 · `AIMO/SPEC.md`:182–190, :251 · `docs/PITCH.md`:89 | **V10** same brand or formula for a substitute or a cheaper item | Scenario 3 orders `475224` (Fazer Aito) alone in place of Oddlygood `473609`; the page itself says "the brand is Fazer Aito, not Oddlygood®". |
| `README.md`:26, :28 · `docs/DEMO.md`:165–167, :185–192 · `WALKTHROUGH.md`:779, :795 | **V10** (the formula matters for cakes and the like) | Yoghurt standing in for quark in a dessert (it does go to a human by F-09), and example 5 choosing another oat drink than the cheapest. To be judged by the agents who plan V10. |
| `README.md`:19 · `docs/DEMO.md`:11, :46, :52, :64, :82, :188 · `docs/PITCH.md`:27, :29, :67 · `docs/ASSUMPTIONS.md`:17 · `docs/ARCHITECTURE.md`:118 · `WALKTHROUGH.md`:1015–1024, :1269 | **V6** and **B3** "this is all static data so we can chose the date"; "go back a few days" | The clock pinned at the capture's `timeNow`, and every count that rests on it ("17 × Cut-off passed", "19 excluded", "41 excluded", "20 excluded"). A moved date changes every replay figure. |
| `docs/DEMO.md`:100 · `docs/ASSUMPTIONS.md`:24 ("Q9, still open") · `MORNING.md`:90 · `WALKTHROUGH.md`:1149–1157 | **Q16** "what is actually delivered. like in a normal store" | "The invoice can be lower, never higher" is no longer an open question: the invoice follows the delivered weight, which the answer does not cap. |
| `README.md`:75 · `docs/DEMO.md`:57 · `docs/PITCH.md`:31, :69 · `docs/AWARDS.md`:81 · `WALKTHROUGH.md`:1279 | **B13** "all the steps and decisions" | The supplier view shows all nine steps but hides limits, exclusions, approver names and notes. The answer reads two ways: (a) our list is confirmed; (b) Valio wants the decisions with their limits too. João must say which. |
| `WALKTHROUGH.md`:1273 · `docs/ASSUMPTIONS.md`:48 | **B7** "yes and only in the last case" | Ambiguous; the list of dietary claims stays "to confirm" until João says what was meant. |
| `WALKTHROUGH.md`:926 (title "still without an answer"), :1004–1013 (`T03-1`), :1130–1138 (`T07-5`), :1149–1157 (`Q9`) | **Q2**, **Q14**, **Q16** | Three of the 25 questions now have an answer; Q2 and Q14 confirm what is built. |
| `WALKTHROUGH.md`:1268, :1272, :1277 | **B2**, **B6**, **B11** "yes" | Decisions listed as "to confirm" are confirmed. |
| `docs/ASSUMPTIONS.md`:26 · `WALKTHROUGH.md`:1159–1168 | **V7** "sap code semi random?? he doesnt know" | Tiers by the first 4 and first 3 digits of the category rest on a reading nobody confirmed; "Valio explains the code hierarchy (Q11)" will not come. |
| `docs/PITCH.md`:48 · `docs/STANDARDS.md`:134 · `AIMO/SPEC.md`:245 · `WALKTHROUGH.md`:1026–1033 | **V1** customer data is to be generated | "We asked Valio what real customers set (Q7)" has its answer: there is none to get; profiles are generated. |
| `WALKTHROUGH.md`:991–1002 | **V2** per customer type, all three optional directions | SCOPE-1 is answered: cover them all. |

## 6. Demo paths (`docs/DEMO.md`)

| Path | Result |
|---|---|
| Scenario 1, steps 1–10 (lines 43–57) | **Works as written.** Every quoted sentence and figure found: €2,580.64, 384 + 51 + 565, `464306` €1,010.00, 19 excluded (17 + 1 + 1), 30 looked up, P-01, F-01, the approval, 9 events, the supplier view at `/orders/{id}?view=supplier` with no limit, name or note. |
| Scenario 2 (61–70) | **Works as written.** €402.00, 200 × `464013`, 478 in stock, 41 excluded (18 + 12 + 6 + 5), ordered by the agent, the audit sentence. |
| Scenario 3 (72–86) | **Works as written.** `475224` €174.00, `473609` €137.00, €2,754.64 of the day, ranks 1, 12 and 13, `468465`. The page adds one sentence the script does not quote: "The fixed rules could not read it either: 473609 is named with no quantity in digits and unit." |
| Backup, 30 kg beef chuck (88–102) | **Works as written.** `rule-based`, `beef_chuck`, 30 kg; €506.40; 31 kg → 33 kg, €557.04; P-06 on an empty book; after scenarios 1 and 3 over REST, P-02 as well, €3,261.04, "the purchasing manager and finance". |
| Extra moments (104–112) | **Work as written:** partial fill (1,133 L, €2,933.09, `NOT_MET`, P-01 + P-03 on an empty book, 1,500 × `464306`); almond `465793` → P-04, the finding quotes the ingredient list and the declaration; cream `463797` €33.10 alone, 9 `vegetable_cream` products in category 10401; agent on the decision route → 403, the exact sentence, `authorisation.refused` in the trail; same `Idempotency-Key` → the same order; headers `gemini-3.6-flash` and `recording`. "Two tabs" **not run**. |
| For a judge (125–131) | **Works as written.** Eight MCP tools with those names, 401 without a token, 405 with `Allow: POST` on GET and DELETE, Swagger UI 5.32.15 and ReDoc 2.5.4 with integrity hashes and a policy that allows jsDelivr only. |
| If something goes wrong (133–139) | Line 136 **differs** (row 11). The fourth scenario 2 goes to finance, as line 20 says. |
| Your kitchen (141–152) | Steps 2–5 **work as written** (€3,000 → `ORDERED` alone, profile `my-kitchen`, the policy hash changes and is on the order record; €750 → P-01 and P-02, "Demo approver Hanna, My kitchen"; Start again → €750). **Differs:** line 145 (row 9) and line 151 (row 10). |
| A menu becomes one order (158–170) | **Works as written.** 4 lines, 21.6 kg, 3.6 L, 12 kg, the quark sentence (6 + 4 of 10), €476.48 and €540.81, the four line totals, F-09 + P-06, the approval; `POST /v1/menus/plan` gives the same, with 3 offers asked. |
| A standing order that drifts (172–179) | **Works as written.** Six synthetic weeks (100, 96, 104, 100, 98, 102 at €2.48), 100 L → €248.00 alone, 290 L → P-08, "5 renewals of the history are synthetic", two real rows. |
| A preference changes the choice (181–194) | **Works as written.** €140.00 and €133.00, €7.00, `468465` €117.00, 20 excluded (11 + 8 + 1), 38 looked up, 0.435 kg CO2e per kg, 43.5 kg, both options within the limits. |

### Figures recounted (all match the documents)

Whole catalog, from `valio_aimo_junction26_product_data.json` and the two CSV files (`count.py`): 17,546 products · 8,110 with no allergen statement, 46.2%, and 30.6% of food products · 45 allergen codes · reliability for 4,425 (25.2%) · carbon for 11,033 (62.9%) · 89 of 279 categories with more than one carbon value · all 91 products of category 10400 at 1.1; cream 1.81; beef 26.195 · 16 label codes; `EU_ORGANIC_FARMING` 456; `MARINE_STEWARDSHIP_COUNCIL_LABEL` 104 · 230 of 250 listed substitution pairs in the same 5-digit category · 21 claim codes. Capture `2026-11-14-demo`: 769 products (620 in 104xx, 149 in 18720), `time_now` 2026-11-14T02:52:45+0200, 2 calls. Files: 11 agent recordings (4 from the model, 7 hand-built), 9 recipes, 31 product types, 9 problem types, 21 OpenAPI paths, 61 schemas.
