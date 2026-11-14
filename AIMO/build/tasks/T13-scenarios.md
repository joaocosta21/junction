# T13 — Scenarios end to end, and the demo script

**Scores on:** 30% ("a full request → lookup → order/approval flow … not just isolated pieces") · 15% (exceptions).
**Needs:** T09, T10, T12 (T11 if it landed). **Owns:** `tests/e2e/`, `docs/DEMO.md`.
**Read first:** SPEC §13 · `AIMO/PLAN.md` §2, §3 · all hand-backs.

## Build
- **End-to-end tests over HTTP in replay** for every row of SPEC §13, starting from the pasted sentence (recorded model) and ending at the audit trail.
- **One live run** (at most 6 calls to the Valio API): the three scenarios against the live mock. Report, per scenario, what differs from the replay capture.
- **`docs/DEMO.md`:** the demo click by click for the three scenarios and the backup — what to paste, who is asking, what appears, the exact sentences on screen, and one line on which criterion each moment scores. Include a 90-second cut. State which mode to demo in and how to switch to replay.
- **Scenario facts:** if tonight's capture no longer supports a scenario as planned (for example the soy drink is no longer confirmed, or a single milk now covers 1,000 litres), find the product or request that restores the intended demonstration, and say so at the top of the hand-back.

## You do not fix other packages
A failure outside `tests/e2e/` is reported with the failing test, the response body and your reading of the cause. The orchestrator sends it to the owner.
