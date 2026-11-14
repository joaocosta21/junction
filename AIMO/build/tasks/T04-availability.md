# T04 — Availability: the six states and what can be trusted

**Scores on:** 15% (exceptions: partial availability, delivery constraints) · the "trust protocol" the brief asks for.
**Needs:** T00. **Owns:** `src/tta/availability/`, `tests/availability/`.
**Read first:** SPEC §4 · `AIMO/FINDINGS.md` §1 · `AIMO/docs/API.md` (availability payload) · `tta/contracts/availability.py`.

## Build — pure functions, the clock is an argument
- **`classify(availability_line, now)`** → one of the six states, in the order of SPEC §4. The threshold `999_999` is a named constant. For `QUANTITY_NOT_CONFIRMED` the usable amount is `None`: nothing downstream can do arithmetic on a placeholder.
- **`is_late(line, needed_by)`** for `LATE_FOR_NEEDED_BY`.
- **`verify(line, price, product, request_line, allergen_outcome, now)`** → the status of each claim (price, quantity, delivery date, allergens, origin) per the table of SPEC §4, each with one sentence.
- A sentence for each state, written for a buyer ("Order cut-off passed on Thursday 12 Nov at 15:00, so delivery on Monday 16 Nov cannot be promised").

## Tests to write first
- One captured line per state; the order of evaluation (a blocked product with no schedule line is `BLOCKED`).
- **Regression on Friday's sample** (`fixtures/valio/2026-11-13-sample/`, clock pinned to its `timeNow`): the 1,000 products classify as 1 blocked, 203 not deliverable, 29 out of stock, 423 cut-off passed, 92 quantity not confirmed, 252 confirmed. If your counts differ, report them; do not bend the code.
- Terminal `999999` and a Stock value such as `416666666` both give `QUANTITY_NOT_CONFIRMED` with amount `None`.
- A cut-off exactly equal to now counts as passed (state the choice in the hand-back).
- Each cell of the verification table.
