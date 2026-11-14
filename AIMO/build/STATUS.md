# Overnight build — task board

The orchestrator is the only writer of this file. States: `todo` · `running` · `review` · `done` · `blocked` (with the reason). A task may start when everything in "needs" is `done`.

| Id | Task | Needs | State | Note |
|---|---|---|---|---|
| T00 | Foundation: branch, virtualenv, contracts, fixtures capture | — | done | orchestrator; 20 tests pass |
| T01 | Valio client, recorder, replay, clock | T00 | done | 146 tests, 100% coverage; live check passed (2 calls) |
| T02 | Catalog: loader, search, product types, pack size | T00 | done | 129 tests, 100% coverage; 29 product types; credits Sofia's litres logic |
| T03 | Allergens: codes, exclusion rule, substitution rule | T00 | done | 130 tests, 100% coverage; 37 of 249 listed substitutes fail the rule, as planned |
| T04 | Availability: six states, verification status | T00 | done | 78 tests, 100% coverage; Friday regression matches exactly |
| T05 | Policy: fixed rules, buyer profiles, engine | T00 | done | 227 tests, 99% coverage; keeps Gabriela's structure |
| T06 | Store and audit trail | T00 | done | 122 tests, 100% coverage |
| T07 | Offers: options, ranking, combining, substitutes | T01 T02 T03 T04 T05 | done | 143 tests, 98% coverage; a follow-up fills `claims_lost` |
| T08 | Orders and approvals | T05 T06 | done | 89 tests, 100% coverage; two-thread tests for approvals and idempotency |
| T09 | API: routes, identity, errors, schemas | T07 T08 | done | 149 tests, 99% coverage; the flow runs over HTTP in replay |
| T10 | Buyer agent (Gemini) | T09 | done | 148 tests; **live check passed** on `gemini-3.6-flash` (08:14–08:40): scenarios 1 and 2 and the no-quantity sentence recorded from the model; scenario 1's run stays hand-built by design |
| T11 | MCP surface | T09 | done | 54 tests, 100% coverage; scenario 2 runs over MCP; endpoint `/mcp/` |
| T12 | Pages: demo, approvals, order and audit | T09 | done | 159 tests, 99% coverage; CSP, CSRF, escaping; page-by-page description in the hand-back |
| T13 | Scenarios end to end, demo script | T09 T10 T12 | done | 16 e2e tests; live run 6 calls, identical to replay; `docs/DEMO.md` with a 90-second cut |
| S1 | Stretch: Aiven PostgreSQL for orders and audit | T13 | done | 110 tests against the real service; append-only audit guarded by triggers; buyer and supplier views; read-only supplier role; SQLite fallback. `/healthz` reason and a page notice left (routes.py, ui) |
| S2 | Stretch: web evidence for missing allergen data (Context.dev) | T13 | done | wired by the orchestrator (f3286e1): shared book and every sandbox; recordings answer without a key |
| T14 | Deployment on Modal | T13 | done | first deploy 237b37f (09:44); **redeployed** from d342dfb at 11:15 with the approved command: https://joaocostared--trusted-trade-agents.us-east.modal.run; `deploy/check.py` 7 of 7; mode live, Aiven connected (no fall-back) |
| T15 | Documents: README, assumptions, standards, award write-ups, pitch outline | T13 | done | 6 documents; 9 `<!-- check -->` marks wait on the deployment (README, AWARDS, PITCH) |
| T16 | Review and fixes | each wave | done | rounds 1–3 (FIX-1 to FIX-8), then FIX-9 to FIX-12b; T17's findings handled as listed in MORNING.md §8 |
| T18 | Gemini: a photo of a handwritten order list, and orders in Finnish | T10 FIX-9 | done | 421 agent tests; **live check blocked**: Gemini 503/504 to all 6 requests; recordings hand-written. Run `.venv/bin/python -m tta.agent.record --only finnish-1 --only finnish-2 --only photo --max-calls 10 --timeout 60` |
| T17 | Final check against the problem statement; `MORNING.md` | all | done | independent check on a clean copy of e880ad2: all SPEC §13 scenarios and guards pass; ten weak points, 3 fixed before it ended, 2 more after (8cd94c2, d447ac3), the rest in MORNING.md §8 |
| FIX-1 | Policy reads the claims; fixed rules pinned (review round 1) | T05 | done | 310 tests; rule F-07 added; all six findings fixed |
| FIX-2 | Audit and store: honest sentences, no rewrite, supplier view, chain fork | T06 | done | 165 tests; one item left for policy (product names in rule sentences) |
| FIX-3 | Allergens and catalog: least safe wins, `milk` means milk | T02 T03 | done | 313 tests; `milk` 91 → 78, lactose-free 35 → 30 |
| FIX-4 | Valio client: budget lock, clock bound, HTTPS only, bounded input | T01 | done | 221 tests; all six findings fixed |
| FIX-5 | Policy: rule F-08 (a substitute that drops a claim), wording, cleaned product names | T05 T07 | done | 378 policy tests; the orders boundary change is committed with FIX-7 |
| FIX-6 | Offers: re-check sees every change, exclusions always listed, no stock counted twice, dietary claims | T07 | done | 185 offers tests; 7 of 8 findings fixed, one as a note (question FIX6-1) |
| FIX-7 | Orders and store: atomic writes, one order per offer, daily limit by the right day | T06 T08 | done | 201 orders and store tests; all ten findings fixed |
| FIX-8 | API: one source per lookup, loud start, per-visitor limits for the public demo, request received in the trail | T09 | done | 251 API tests; all 14 findings fixed; `/mcp` and `/v1` exact paths |
| T10-F | Agent follow-up: `generateContent` instead of the Interactions API, fall-back to recordings, live check | T10 | done | 148 tests; `gemini-3.8-flash` 504 every time, `gemini-3.6-flash` answers (now the default); first real recording (scenario 1) |
| FIX-9 | Agent: proposals checked against the text, no lost order, readings labelled, outage remembered | T10 | done | 294 agent tests, 99% coverage; all nine findings fixed |
| FIX-10 | Pages and API: a private sandbox per browser, per-visitor limits by kind, honest labels, no double order | T09 T12 | done | all 14 findings fixed; whole suite 2,475 tests |
| FIX-11 | Rate limits for a room on one Wi-Fi: per browser on the pages, a cap per address | FIX-10 | done | 42 new tests; twelve browsers on one address all run scenario 2 |
| FIX-12a | Say only what the data says: not in the recording, ingredient lists, cream | T07 T03 | done | 9a1893d; 868 tests in its packages; 18 (AM+AW) and 7 (AN) declaration/ingredient conflicts over the whole catalog go to a dietitian; ALMOND-1 widened |
| FIX-12b | Coverage per line, substitutes judged like the offer, earliest date, trade-off on the approval card | T07 T12 | done | baa4e08; P-03 names the short line; substitutes route applies the buyer's own rule |
| FEAT-1 | "My kitchen": the buyer sets what its agent may decide alone (per-browser profile page) | FIX-10 | done | b91e135; 54 new tests; `/kitchen` in the menu; profile checked as a file is; in force only in that browser's book |
| DOCS-2 | Documents say what the code does | — | done | 8 documents aligned; 26 marks wait on S1, T18, FIX-12a, FIX-12b, FEAT-1 |
| DOCS-3 | Documents say what is committed: marks settled, limits checked, assumptions for price and the ceiling | DOCS-2 | done | d342dfb; 26 marks settled, 8 deploy marks settled by the orchestrator after the redeploy |
| SUST-1 | Delivery time and sustainability comparison (brief's optional direction) | 576e4cc | running | asked by the human, 11:40; hand back by 15:30 |
| STAND-1 | Standing orders with drift detection before renewal (rule P-08) | 576e4cc | running | asked by the human, 11:40; hand back by 15:30 |
| MENU-1 | Recipe logic: menu → order, substitutions by role (rule F-09) | d4ad9b7 | running | asked by the human, 11:40; hand back by 15:30 |
| FALLBACK-1 | Rule-based reader when the model cannot answer; model schema learns the new fields | 576e4cc | running | asked by the human, 11:40 (Gemini on a zero balance); hand back by 15:30 |

## Log
(one line per event: time, task, what happened)
- 02:36 loop started by the human's start line.
- 02:58 T00 done: branch `overnight-build`, `origin/bio1` and `origin/bio2` merged, `.venv` with the declared packages, contracts (59 models, 12 ports), settings, three captures in `fixtures/valio/` (tonight's: 769 products, 2 live calls), 20 tests pass, lint clean. All four optional values are set (Valio, Gemini, Aiven, Context.dev: true through `tta.config`).
- 02:58 wave 1 started: T01 T02 T03 T04 T05 T06, six agents in parallel.
- 03:13 T04 done and committed. Decision recorded in SPEC §4: which claims gate an order without a human (question T04-1 for the team).
- 03:16 T01 done and committed. Live check: 2 calls, both 200, lines equal to the capture. Questions T01-1 (Valio) and T01-2 (team) added.
- 03:19 T03 done and committed. Questions T03-1 and T03-2 (Valio), T03-3 (team) added.
- 03:26 T06 done and committed. Decision: audit events are stamped with the real time, not the pinned replay clock (question T06-2). Questions T06-1 and T06-2 (team) added.
- 03:28 T02 done and committed. Questions T02-1, T02-2 (Valio), T02-3, T02-4 (team) added. Fix candidates are kept in `fix-candidates.md`.
- 03:30 T05 done and committed. Wave 1 complete: 852 tests pass, lint clean, the six packages satisfy their ports together (smoke run). Demo approvers added for every role on both profiles. Questions T05-1 to T05-3 (team) added.
- 03:30 wave 2 started: T07 T08. T16 round 1 started on wave 1 (three reviewers, read-only), base commit 1e20827.
- 03:37 T16 round 1 back: no critical finding. High: the 60-second cache could hide a change from the order-time re-check (fixed by the orchestrator: `fresh=True` on the port, commit 2b3444c); the policy counted a missing claim as confirmed (FIX-1, new fixed rule F-07 in SPEC §7). Request bounds added to the contract. Four fix tasks started (FIX-1 to FIX-4). T07 and T08 were told what changes.
- 03:53 T08 done and committed. Questions T08-1 to T08-4 (team) added.
- 03:53 FIX-4 done and committed (no live call).
- 03:54 FIX-3 done and committed. Question FIX3-1 (team) added.
- 03:55 FIX-1 done and committed.
- 03:59 FIX-2 done and committed. `AuditSink.head()` added to the port.
- 04:14 T07 done and committed. Wave 2 complete: 1,346 tests pass; the three scenarios and the backup run through the offer service in replay (products in question T07-6). Found by T07: regular milk could stand in for lactose-free milk and be ordered by the agent alone → new fixed rule F-08 in SPEC §7, FIX-5 started, T07's builder asked to fill `claims_lost`.
- 04:14 wave 3 started: T09. T16 round 2 started on offers and orders (three reviewers, read-only), base commit e593693.
- 04:20 T16 round 2 back (offers, orders): no critical finding. High: the re-check missed a moved delivery date, sales unit and tax rate; under confirmed-only, dropped products were not listed; two request lines could take one substitute's stock twice; a failed write between order and approval left an order nobody could decide. Fix tasks FIX-6 (offers) and FIX-7 (orders and store, new port method `Store.atomic()`) started. T07's follow-up (`claims_lost`) committed. Decision: only dietary claims count for rule F-08 (question T07-7).
- 04:31 FIX-5 done and committed (policy part). The supplier view now names F-07 and F-08.
- 04:48 FIX-6 and FIX-7 done and committed, with the lock-order change in the audit trail that FIX-7 asked for. Whole suite: 1,693 tests pass (T09's tests included, still being written). Scenario 3's best orderable substitute is `475224` again.
- 04:57 T09 done and committed. Scenario 1 run over HTTP by the orchestrator: offer → `PENDING_APPROVAL` → agent refused on the approval route (403) → approved by the purchasing manager → `ORDERED`; 9 audit events, chain intact, supplier view redacted. Contracts: every stated decimal is now a JSON number; record ids bounded; `list_orders` on the port. Whole suite: 1,695 tests.
- 04:57 T10, T11, T12 started. T16 round 3 started on the API (three reviewers), base commit 89e4263.
- 05:02 T16 round 3 back (API): no critical finding; the authorisation matrix held under probing. High: an offer could mix a live price with replayed stock; live mode with a bad base URL started on the capture; `TTA_ENV` unset meant demo tokens (fixed by the orchestrator: the default is now `prod`, which fails closed); one visitor could lock out the others and spend the supplier budget through the shared demo tokens. FIX-8 started.
- 05:35 T11 done and committed. FIX-8 asked to route the exact path `/mcp` to the MCP surface. Questions T11-1 and T11-2 (team) added.
- 05:37 T11 done and committed (54 tests; scenario 2 runs over MCP).
- 05:40 T10, T12 and FIX-8 stopped on the Fable usage limit (resets 12:00); their work stayed in the tree, all tests green.
- 07:42 the human switched the session to Opus 5.5. T10 checked and committed as done with its live check blocked: Gemini answered 503 again at 07:45 (2 more requests; 4 of 20 used in all). T12 and FIX-8 restarted on Opus from the work in the tree. S1 and S2 skipped by the 06:30 rule.
- 07:50 Gemini probe: `generateContent` answers for `gemini-3.8-flash` and `gemini-3.6-flash` with the same key; only the Interactions endpoint answers 503. T10 follow-up started (switch endpoint, fall back to recordings, live check with at most 14 more model requests; 6 used tonight).
- 08:00 FIX-8 done and committed (the first agent had built every finding; the restarted one checked them and added one test). Importers green: ui 159, mcp 54, agent 120, offers 194, orders 157, audit 144.
- 08:03 T12 done and committed (restarted agent found every item built; fixed one spacing defect, added 6 tests, ran the app in replay). T13, T14 (files only) and T15 started in parallel.
- 08:15 T10 follow-up done and committed. Gemini is slow today (21.7 s for one word); `gemini-3.6-flash` read scenario 1 correctly in 29 s and is now the default. Recording scenario 2 and the no-quantity sentence (at most 7 requests; 12 used so far of 20).
- 08:17 Gemini live check passed: `gemini-3.6-flash` read scenario 2 (plant drink, 200 L, AM and AW excluded, confirmed only, by 16 Nov) and ran it (authority → offer → order of option 1 → ORDERED by the agent, €402.00). 'Some milk for Monday' refused for the missing quantity. 17 of 20 model requests used tonight.
- 08:21 T13 done and committed. Tonight's capture gives a full fill for scenario 1 (partial fill at 1,500 L, tested). T16 final round started: three reviewers on the agent, pages, MCP surface and FIX-8.
- 08:22 T15 done and committed (10 standards checked against their specification pages; 74 assumptions on the page). Flagged for the team: the four partner data files are tracked in the repository, which will be public.
- 08:33 T14 files committed: secret of three values read at deploy time, image without `.env`, SQLite on local disk with a copy on the Volume. Final review round: silent-failure report in (2 high: a second order when a run fails after placing one; a reading from a recording not labelled as such); two reports to come.
- 08:38 T16 final round back: no critical finding; 6 high (shared order book; one visitor can fill the global ceilings; spoofable forwarded address; a second order on resend after a failure; a recorded reading not labelled; the model's quantity, date and exclusions not checked against the text). Decided: a private sandbox per browser for the pages; per-visitor limits by kind; the deployed budget at 120 live calls, so the night's total stays within the 150 approved. FIX-9 (agent) and FIX-10 (pages and API) started.
- 09:13 FIX-9 done and committed.
- 09:26 The human chose (Saturday morning): build what can win a tech award when it meets the brief, otherwise the best Aimo program; redeploy at the end is approved. Plan: first deployment after FIX-10, then S1 (Aiven), S2 (Context.dev), T18 (Gemini photo and Finnish) in parallel, then a final redeploy. `psycopg[binary]` added to `pyproject.toml` and installed. Walkthrough written: `AIMO/WALKTHROUGH.md`.
- 09:44 FIX-10 done and committed; ports gained `read`, `read_request`, `order_for_offer`. **First deployment** from commit 237b37f with the approved command: https://joaocostared--trusted-trade-agents.us-east.modal.run. `deploy/check.py`: health ok (live), page 200, scenario 2 offer from live data → `AUTO` → ORDERED by the agent, 6 audit events intact, MCP 401 without a token and 8 tools with one.
- 09:45 S1 (Aiven), S2 (Context.dev), T18 (Gemini photo and Finnish) and FIX-11 (room limits) started in parallel, each with its own files.
- 09:54 The human asked for three more pieces, each with its own agent: `AIMO/OPEN-QUESTIONS.md` (the 22 open questions to Valio, each with its example), a clearer rewrite of `AIMO/WALKTHROUGH.md`, and a check of Valio's six example scenarios and our own by running the system (a main agent with one sub-agent per use case, in an isolated worktree), report in `AIMO/USE-CASES.md`.
- 10:01 FIX-11 done and committed. Docs to align at the end: `src/tta/api/docs.py` (limits text), `docs/DEMO.md`, `docs/ASSUMPTIONS.md`.
- 10:13 S2 built and committed: Context.dev evidence on the dietitian's approval card (demo: `469512` Elovena oat drink, maker's page 'Maidoton'). Wiring and deploy secret to add after S1 finishes with `wiring.py`. T18 asked for a fourth example button for this moment. `AIMO/OPEN-QUESTIONS.md` committed (23 questions, 32 examples verified); `AIMO/BOOTH-NOW.md` for the booth.
- 10:25 Use-case check report in `AIMO/USE-CASES.md`: our own scenarios all hold; Valio's six examples: allergen-safe substitution, stock-out, last-minute and recipe partly, proactive selling and standing-order drift not at all. Its top fixes started as FIX-12a and FIX-12b. Booth questions ALMOND-1 (`465793` declared free from tree nuts, ingredients say almond) and DATA-1 (the product file and the API) added.
- 10:33 Walkthrough rewritten and committed (17 sections; 25 open questions with examples; decisions split into Valio's and the team's). The human has about 1h30 and 40% of the weekly limit: FEAT-1 (profile page) and DOCS-2 (documents) started on Opus.
- 10:38 S1 done and committed (67f3b00). The orchestrator wired S2's evidence into every order book (f3286e1) and added `DATABASE_URL` and `CONTEXT_DEV_API_KEY` to the deploy secret and the evidence recordings to the image (cf6681f), both approved by the human. Left for after T18: S1's one-line `/healthz` reason in `routes.py`.
- 10:39 T18 done and committed (812de0f); S1's `/healthz` reason added. Gemini requests tonight: 17 + 1 (07:13 re-read) + 6 (T18) = 24.
- 10:48 DOCS-2 done and committed. Two untrue sentences fixed (fresh offer, standing order). T17's independent check started on a clean copy of e880ad2.

## Live API calls used
10 of 150 from this machine (T00 capture 2, T01 live check 2, T13 live run 6); the deployed app has its own budget of 120 (about 4 used by the post-deploy check)
- 10:54 FIX-12a done and committed (9a1893d); 10:53 FIX-12b (baa4e08).
- 10:58 FEAT-1 done: tests, lint, scope and the key files read; committed (b91e135). Nav link added by the orchestrator. ALMOND-1 widened in the booth files (71f13f4).
- 11:05 second booth copy of 71f13f4 on port 8001 (replay, no keys): 1,000 L milk and the almond drink checked on it.
- 11:05 T17 handed back (reviewed e880ad2). Checked on 71f13f4: points 1, 3 and half of 5 already fixed. Fixed now: the brief's own sentence without a model (8cd94c2), the summary-strip headings (d447ac3).
- 11:10 DOCS-3 handed back; netPriceFound is true on 50 of 769 price lines (it corrected the orchestrator's premise, taken from T17). Committed d342dfb.
- 11:15 **redeploy** from d342dfb with the approved command; `deploy/check.py` 7 of 7; /healthz live, no fall-back; /kitchen 200; almond drink → P-04 on the deployed app.
- 11:20 MORNING.md written; PLAN §5 and §8 updated; loop ended.
- 12:10 the human asked for A (sustainability), B (standing-order drift), C (recipes) and a rule-based fallback, plus one more redeploy when they are verified. Contracts 576e4cc and d4ad9b7 by the orchestrator; four agents launched.
