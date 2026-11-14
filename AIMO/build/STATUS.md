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
| T09 | API: routes, identity, errors, schemas | T07 T08 | running | |
| T10 | Buyer agent (Gemini) | T09 | todo | needs `GEMINI_API_KEY` for the live check only |
| T11 | MCP surface | T09 | todo | first cut if behind |
| T12 | Pages: demo, approvals, order and audit | T09 | todo | |
| T13 | Scenarios end to end, demo script | T09 T10 T12 | todo | |
| S1 | Stretch: Aiven PostgreSQL for orders and audit | T13 | todo | only if approved, `DATABASE_URL` set, T13 green before 06:30 |
| S2 | Stretch: web evidence for missing allergen data (Context.dev) | T13 | todo | only if approved, `CONTEXT_DEV_API_KEY` set, T13 green before 06:30 |
| T14 | Deployment on Modal | T13 | todo | needs a Modal token |
| T15 | Documents: README, assumptions, standards, award write-ups, pitch outline | T13 | todo | |
| T16 | Review and fixes | each wave | running | round 1 done (FIX-1 to FIX-4 in); round 2 (offers, orders) running; rounds after wave 3 and at the end to come |
| T17 | Final check against the problem statement; `MORNING.md` | all | todo | |
| FIX-1 | Policy reads the claims; fixed rules pinned (review round 1) | T05 | done | 310 tests; rule F-07 added; all six findings fixed |
| FIX-2 | Audit and store: honest sentences, no rewrite, supplier view, chain fork | T06 | done | 165 tests; one item left for policy (product names in rule sentences) |
| FIX-3 | Allergens and catalog: least safe wins, `milk` means milk | T02 T03 | done | 313 tests; `milk` 91 → 78, lactose-free 35 → 30 |
| FIX-4 | Valio client: budget lock, clock bound, HTTPS only, bounded input | T01 | done | 221 tests; all six findings fixed |
| FIX-5 | Policy: rule F-08 (a substitute that drops a claim), wording, cleaned product names | T05 T07 | done | 378 policy tests; the orders boundary change is committed with FIX-7 |
| FIX-6 | Offers: re-check sees every change, exclusions always listed, no stock counted twice, dietary claims | T07 | done | 185 offers tests; 7 of 8 findings fixed, one as a note (question FIX6-1) |
| FIX-7 | Orders and store: atomic writes, one order per offer, daily limit by the right day | T06 T08 | done | 201 orders and store tests; all ten findings fixed |

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

## Live API calls used
4 of 150 (T00 capture 2, T01 live check 2)
