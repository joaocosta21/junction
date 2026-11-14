# T07 — Offers: options, ranking, combining, substitutes

**Scores on:** 20% (precise match, least manual correction) · 15% (partial availability, substitutions, delivery constraints) · Core 1 and Core 2.
**Needs:** T01, T02, T03, T04, T05. **Owns:** `src/tta/offers/`, `tests/offers/`.
**Read first:** SPEC §3, §4, §5, §6 · `AIMO/PLAN.md` §2 (the canonical request worked through) · the contracts `offer.py`, `ports.py`.

## Build
- **`build_offer(request, profile, deps)`** implementing `OfferBuilder`, following SPEC §5 step by step: candidates → one price and one availability lookup → classify → allergen check → options → constraint checks → policy verdict per option → exclusions with reason and sentence.
- **Combining:** cheapest single confirmed product that covers the quantity; otherwise cheapest first until covered; otherwise a partial fill that states what is missing.
- **`find_substitutes(product_id, profile, deps)`** per SPEC §5: candidates, re-check, ranking, a sentence on what the buyer gives up. Failures are returned with their reason and are not orderable.
- **`revalidate(option, deps)`** implementing `OfferRevalidator`: fresh price and availability for the option's lines; reports what changed.
- Totals: tax from `tax.taxRate`; `excludes_deposits` when a line carries deposits; `is_ceiling` for variable weight.

## Tests to write first (replay, capture `2026-11-14-demo`, pinned clock)
- Scenario 1: option 1 holds confirmed lines only; an unconfirmed alternative exists when a fitting product is in that state; `463203` is excluded as `PORTION_PACK`; every excluded product has a reason and a sentence; each thing the buyer asked for has a constraint check.
- Scenario 2: every product declaring `AM` or `AW` is excluded as `ALLERGEN_DECLARED`; the chosen product states `FREE_FROM` for both; one option; coverage 1.0.
- Scenario 3: `473609` → `471690` passes; `471881` and `464320` fail with `SUBSTITUTE_ADDS_ALLERGEN`.
- A request no product can meet returns an offer with no options and the reasons, not an error.
- A placeholder amount never enters a sum (construct a case where it would).
- `valid_until` is the earliest price validity and cut-off of the option's lines.
- With hand-built availability: one product covers all → single line; two needed → two lines, cheapest first; stock short → partial with the missing amount.
- `revalidate` reports a changed price and a passed cut-off.

## Note
If the capture's stock differs from Friday's numbers in the plan, the structure still has to hold. Report which products the scenarios select tonight.
