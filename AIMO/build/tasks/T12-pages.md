# T12 — Pages: demo, approvals, order and audit

**Scores on:** 30% (the visible half of the flow) · 20% (the human approval panel, the readable audit trail). Judges give each team little time: the first screen must show what is confirmed, what is not, and what was excluded and why.
**Needs:** T09. **Owns:** `src/tta/ui/`, `tests/ui/`.
**Read first:** SPEC §12, §9 · `AIMO/PLAN.md` §3 (what the judge sees in each scenario) · the contracts `offer.py`, `order.py`, `audit.py`.

## Build — server-rendered Jinja2, plain CSS and a little plain JavaScript, no external assets (the venue network may fail)
- **`/`** — a text box with the three scenario requests as one-click examples, a "who is asking" selector (the demo agents and their profiles), Run. Result, top to bottom: the parsed request; the options side by side, each line with a mark per claim (confirmed, not confirmed, ruled out — a word and a colour, never colour alone); the constraint checks; the verdict with the rules in plain sentences; the excluded products with reasons (collapsed after the first five); then the outcome: "Ordered by the agent" or "Sent for approval".
- **`/approvals`** — pending approvals as cards: why a human is needed, the options, "order by" time, approve (with a choice of option) or reject with a note; a selector for the demo approver and role.
- **`/orders/{id}`** — the order record, the statements it relied on, and the audit trail as a timeline of sentences, switchable between the buyer's and the supplier's view; a mark showing the hash chain verifies.
- **`/assumptions`** — renders `docs/ASSUMPTIONS.md` when it exists.
- A visible "replay" label when the data is recorded. Illustrative values (profiles) are labelled as such.
- Pages call the same service functions as the API, with the demo identity chosen on the page. Every piece of dynamic text is escaped: product names are untrusted.
- Readable from two metres: large type, high contrast, no decoration.

## Tests to write first
- Each page answers 200 in replay.
- Scenario 1's result shows a confirmed option, an unconfirmed alternative and the exclusion reasons; scenario 2's shows "Ordered by the agent".
- Approving on `/approvals` changes the order to `ORDERED`.
- A product name containing `<script>` is rendered escaped.
- The supplier view shows no limit value.

## Hand-back extra
Start the app in replay and save a screenshot description (what is on each page, top to bottom) so the team can review without running it.
