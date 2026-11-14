# Tonight's build — board and log

The orchestrator is the only writer of this file. Procedure: [RUNBOOK.md](RUNBOOK.md) part 2. States: `todo`, `running`, `done`, `blocked` (with the reason).

Branch: `replan-build` (exists; it holds the merges of `origin/frontend-shop` at `f292acd` and `origin/codex/mandatory-human-approval` at `5673ef2`). Outside calls made in this run: 0 (none are approved).

## Board

| Wave | Task | What | Needs | State |
|---|---|---|---|---|
| 0 | B0 | Baseline, on top of the two merged branches: the buyer's setting back and off by default, where F-10 lives, coffee milk its own type, standing-order history, the demo-clock setting, pinned figures refreshed | — | running |
| 1 | L1 | Reader: asks instead of guessing, exclusions never dropped, numbers, units, "coffee milk" | B0 | todo |
| 1 | L2a | Substitutes and formula: no category tiers, nutrition, the measure, the ranking, claim-keepers first | B0 | todo |
| 1 | L2b | Options and safety: safe product first, the preference's gap, no dearer unconfirmed alternative | B0 | todo |
| 1 | L3 | Rules and log: wording, "confirmed by", two new profiles, Valio's view in full | B0 | todo |
| 1 | L4 | Gateway: standing-order limits, recipes, the day's spend, limits, `Origin`, discovery | B0 | todo |
| 1 | L5 | Customers and suggestions: pattern files, loader, the pure functions | B0 | done |
| 2 | L2a-2 | Formula on the request, the cheaper same-formula line, pieces converted, claims against allergen data | L2a, L2b, L5 | todo |
| 2 | L3-2 | The formula rule (F-11) and its settings; the rule for a preference's premium | L2a, L2b | todo |
| 2 | L4-2 | Suggestions wired, customers loaded at start, the public link's settings, signed offers, the Context.dev cap and evidence | L3, L5 | todo |
| 2 | L1-2 | "Formula matters" and "the usual …" wired into the reading; Gemini's schema and prompt; the reading table | L5, L2a-2 | todo |
| 3 | E1 | The demo set re-measured at both clocks, end-to-end tests, the demo script | wave 2 | todo |
| 3 | E2 | Documents made true | E1 | todo |
| 3 | E3 | Review of the whole diff, at high effort | wave 2 | todo |
| 4 | X | The "later" list, one at a time, with Modal's scheduled witness | wave 3 | todo |

## Demo figures (measured offline; the orchestrator fills this in)

| Scenario | Default clock (Sat 14 Nov 02:52) | Demo clock (Thu 12 Nov 14:15) |
|---|---|---|
| 1. 1,000 L of lactose-free milk, hotel | before the baseline: €2,580.64 with 565 L of coffee milk | — |
| 2. 200 L of a milk substitute, ward | before the baseline: €402.00, ordered alone | — |
| 3. Oat-drink substitute | — | — |
| 4. The customer's pattern | — | — |
| 5. The formula, bakery-café | — | — |

## Log
- sáb 14 nov 17:23 — **L5 done** (Opus). New paths only, checked with `git status`. Own tests: `137 passed, 2 skipped` (the two skips wait for L3's school and bakery profile files); linter clean on its paths. The whole suite was not run for it: B0 is still changing the rest of the tree, and L5 touched no existing file. Measured offline, the same at both clocks: every usual product of the four customers has confirmed stock; larger pack 60 L of `464320` €106.80 against 40 × `473278` €88.80. Carried forward: L3 (approver roles of the two new profiles must be among the customer's people; display names must agree with the customer files), L4-2 (`Offer.suggestions`, standing orders built from the customer files, the guard on every suggestion: the school's forgotten yoghurt `464517` has no nut or sesame statement and must be dropped), E2 (thresholds on the assumptions page). Defaults taken: a suggestion is shown, never applied; forgotten-item silence refined so the ward's rice drink still speaks beside its soya drink; ward and bakery prefer RELIABILITY. Questions for the hand-over: the school's strict rule sends every confirmed bulk milk and yoghurt to the dietitian.
- sáb 14 nov 16:55 — **L5 started early, beside B0**, on João's instruction in the session to run as much in parallel as possible. It creates only new paths (`src/tta/customers`, `src/tta/suggestions`, two new contract files, their tests); B0 was told to ignore them in its suite run. The other wave-1 lanes edit files B0 is changing, so they wait for B0. Models from here: Opus for the simpler lanes, Fable for the harder lanes and every review.
- sáb 14 nov 16:53 — **B0 started** (one agent, alone in the tree, high effort). Loop run begins from a clean `replan-build` at `bb0d551`; `AIMO/BOOTH-NOW.md` was already modified and is left untouched.
- Sat 14 Nov 16:50 — **the merged base holds.** `replan-build` = `overnight-build` + `origin/frontend-shop` (`f292acd`) + `origin/codex/mandatory-human-approval` (`5673ef2`), one conflict resolved in `src/tta/api/sandbox.py`, then the commit "fix: the merged base holds". Whole suite: `3281 passed, 67 skipped, 1 deselected`; linter clean. Not yet the end state: every order needs a person through F-10 in code, whatever the profile says, and the path on which the agent orders alone is deleted. B0 starts with C1's X2 (RUNBOOK, "The baseline").
- Sat 14 Nov 16:20 — `C2-frontend-branch.md` is in: build on top of Gabriela's shop page after fixes. Merge it first, then Sofia's commit. B0 starts with C2's F2 (the shop stops sending `auto_order_enabled: true`; three tests). The runbook names the shop files the build may edit and the fields the page already prints.
- Sat 14 Nov 16:10 — `C1-human-approval-branch.md` is in: take Sofia's commit with fixes X1 to X4 (3 tests red on it; the buyer's setting must come back, off by default; her rule holds the id F-10, so the formula rule is F-11). `C2-frontend-branch.md` still running.
- Sat 14 Nov 16:05 — the baseline now depends on two reviews: `C1-human-approval-branch.md` (Sofia's commit) and `C2-frontend-branch.md` (Gabriela's shop page). Both were still running. The four tech awards have their offline part in L1, L3, L4-2, E2 and wave 4.
- Sat 14 Nov 15:55 — board written by the planning session. Nothing built yet. The review of `origin/codex/mandatory-human-approval` (file `C1-human-approval-branch.md`) was still running.
