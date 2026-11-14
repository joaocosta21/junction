# Overnight build — task board

The orchestrator is the only writer of this file. States: `todo` · `running` · `review` · `done` · `blocked` (with the reason). A task may start when everything in "needs" is `done`.

| Id | Task | Needs | State | Note |
|---|---|---|---|---|
| T00 | Foundation: branch, virtualenv, contracts, fixtures capture | — | todo | orchestrator |
| T01 | Valio client, recorder, replay, clock | T00 | todo | |
| T02 | Catalog: loader, search, product types, pack size | T00 | todo | starts from `bio1` |
| T03 | Allergens: codes, exclusion rule, substitution rule | T00 | todo | |
| T04 | Availability: six states, verification status | T00 | todo | |
| T05 | Policy: fixed rules, buyer profiles, engine | T00 | todo | starts from `bio2` |
| T06 | Store and audit trail | T00 | todo | starts from `bio2` log format |
| T07 | Offers: options, ranking, combining, substitutes | T01 T02 T03 T04 T05 | todo | |
| T08 | Orders and approvals | T05 T06 | todo | |
| T09 | API: routes, identity, errors, schemas | T07 T08 | todo | |
| T10 | Buyer agent (Gemini) | T09 | todo | needs `GEMINI_API_KEY` for the live check only |
| T11 | MCP surface | T09 | todo | first cut if behind |
| T12 | Pages: demo, approvals, order and audit | T09 | todo | |
| T13 | Scenarios end to end, demo script | T09 T10 T12 | todo | |
| S1 | Stretch: Aiven PostgreSQL for orders and audit | T13 | todo | only if approved, `DATABASE_URL` set, T13 green before 06:30 |
| S2 | Stretch: web evidence for missing allergen data (Context.dev) | T13 | todo | only if approved, `CONTEXT_DEV_API_KEY` set, T13 green before 06:30 |
| T14 | Deployment on Modal | T13 | todo | needs a Modal token |
| T15 | Documents: README, assumptions, standards, award write-ups, pitch outline | T13 | todo | |
| T16 | Review and fixes | each wave | todo | runs after waves 1, 2, 3 and at the end |
| T17 | Final check against the problem statement; `MORNING.md` | all | todo | |

## Log
(one line per event: time, task, what happened)

## Live API calls used
0 of 150
