# FIX-6 — questions

## 1. For the team — a product that fits and is not needed: an exclusion, or a note?
**Context:** FIX-6 finding 2 asks that `candidates_considered` equal the options' products plus the exclusions for a single-line request. A candidate can pass every check and still be in no option, because a cheaper product covers the quantity or a cheaper unconfirmed product is the alternative. It has not dropped out, and `ExclusionReason` has no code for it.
**We did:** every product that drops out now gets an `Exclusion` (also under confirmed-only). A product that fits and is in no option is named in one note per request line, not in `excluded[]`.
**We got:** the candidates add up as "in an option + excluded + named as not needed", and a test says so on every scenario. The sum without the third term does not hold.
**Example to show:** scenario 1 tonight (replay `2026-11-14-demo`): 30 candidates = 4 in the two options + 19 excluded + 7 named as not needed (`463335`, `463779`, `464073`, `464201`, `464237`, `464398`, `464401`). Scenario 2: 51 = 1 + 41 + 9. Beef backup: 7 = 1 + 5 + 1 (`464744`).
**Ask:** "Should a product that fits and is not needed be listed in `excluded[]` under a new reason code such as `NOT_NEEDED`, so the sum holds without the note; is the note what you expected, or did we get something wrong?"
**If no answer, we build:** the note stays. With a new code in `ExclusionReason` the change is one function (`_unused_notes` in `src/tta/offers/builder.py`).

## 2. For the team — where the price stands in the option ranking
**Context:** FIX-6 finding 7 asks for the net total as the last key of the option ranking. SPEC section 5 says "constraint fit, then verification status, then price".
**We did:** the key is: holds an unconfirmed quantity, `NOT_MET` count, `UNVERIFIED` count, kind (`BEST_CONFIRMED`, `ALTERNATIVE_UNCONFIRMED`, `SUBSTITUTE`), net total.
**We got:** an offer holds at most one option of each kind, so the kind always decides before the net total is read. The price orders nothing today; no scenario changed.
**Example to show:** `469363` named by id for 100 L with 40 in stock: `BEST_CONFIRMED` (40 L, €99.20) and `SUBSTITUTE` (40 L + 60 L of `462775`, €253.40) tie on one `NOT_MET` each; the kind puts the first before the second, and the price would too.
**Ask:** "Should the net total come before the kind, so the cheaper of two options that fit alike is first whatever its kind; is the key as built what you expected, or did we get something wrong?"
**If no answer, we build:** as the finding says, the net total last.
