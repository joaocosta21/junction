# Tonight's build — board and log

The orchestrator is the only writer of this file. Procedure: [RUNBOOK.md](RUNBOOK.md) part 2. States: `todo`, `running`, `done`, `blocked` (with the reason).

Branch: `replan-build`, to be created from `overnight-build`. Outside calls made in this run: 0 (none are approved).

## Board

| Wave | Task | What | Needs | State |
|---|---|---|---|---|
| 0 | B0 | Baseline: ordering alone off, coffee milk its own type, standing-order history, the demo-clock setting, pinned figures refreshed | — | todo |
| 1 | L1 | Reader: asks instead of guessing, exclusions never dropped, numbers, units, "coffee milk" | B0 | todo |
| 1 | L2a | Substitutes and formula: no category tiers, nutrition, the measure, the ranking, claim-keepers first | B0 | todo |
| 1 | L2b | Options and safety: safe product first, the preference's gap, no dearer unconfirmed alternative | B0 | todo |
| 1 | L3 | Rules and log: wording, "confirmed by", two new profiles, Valio's view in full | B0 | todo |
| 1 | L4 | Gateway: standing-order limits, recipes, the day's spend, limits, `Origin`, discovery | B0 | todo |
| 1 | L5 | Customers and suggestions: pattern files, loader, the pure functions | B0 | todo |
| 2 | L2a-2 | Formula on the request, the cheaper same-formula line, pieces converted, claims against allergen data | L2a, L2b, L5 | todo |
| 2 | L3-2 | Rule F-10 and its settings; the rule for a preference's premium | L2a, L2b | todo |
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
- Sat 14 Nov 16:05 — the baseline now depends on two reviews: `C1-human-approval-branch.md` (Sofia's commit) and `C2-frontend-branch.md` (Gabriela's shop page). Both were still running. The four tech awards have their offline part in L1, L3, L4-2, E2 and wave 4.
- Sat 14 Nov 15:55 — board written by the planning session. Nothing built yet. The review of `origin/codex/mandatory-human-approval` (file `C1-human-approval-branch.md`) was still running.
