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
| T07 | Offers: options, ranking, combining, substitutes | T01 T02 T03 T04 T05 | running | |
| T08 | Orders and approvals | T05 T06 | running | |
| T09 | API: routes, identity, errors, schemas | T07 T08 | todo | |
| T10 | Buyer agent (Gemini) | T09 | todo | needs `GEMINI_API_KEY` for the live check only |
| T11 | MCP surface | T09 | todo | first cut if behind |
| T12 | Pages: demo, approvals, order and audit | T09 | todo | |
| T13 | Scenarios end to end, demo script | T09 T10 T12 | todo | |
| S1 | Stretch: Aiven PostgreSQL for orders and audit | T13 | todo | only if approved, `DATABASE_URL` set, T13 green before 06:30 |
| S2 | Stretch: web evidence for missing allergen data (Context.dev) | T13 | todo | only if approved, `CONTEXT_DEV_API_KEY` set, T13 green before 06:30 |
| T14 | Deployment on Modal | T13 | todo | needs a Modal token |
| T15 | Documents: README, assumptions, standards, award write-ups, pitch outline | T13 | todo | |
| T16 | Review and fixes | each wave | running | round 1 (wave 1) running; rounds after waves 2, 3 and at the end to come |
| T17 | Final check against the problem statement; `MORNING.md` | all | todo | |

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

## Live API calls used
4 of 150 (T00 capture 2, T01 live check 2)
