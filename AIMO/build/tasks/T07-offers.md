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

## Notes from wave 1 (read the hand-backs in `AIMO/build/handback/` for T01 to T05)
- **Entry points:** `ProductCatalog.from_settings(settings)` (`tta.catalog.catalog`, about 1.3 s: build it once per test session in your own `tests/offers/conftest.py`) · `ReplayGateway(settings.replay_capture_dir)` and its pinned `.clock` (`tta.valio`) · `classify`, `is_late`, `late_sentence`, `verify` (`tta.availability`) · `check_exclusions`, `check_substitute`, `is_known_code` (`tta.allergens`; they take allergen statements, not products) · `RulePolicyEngine.from_files()` (`tta.policy`).
- `verify(line, price, product, *, quantity, needed_by, allergen_outcome, now)`: `quantity` is the line's quantity in sales units.
- **The day's spend.** `PolicyEngine.evaluate` needs `PolicyContext(now=..., day_committed_net_eur=...)`; with `None` every option reads `APPROVAL` by F-03. Your builder takes a dependency `day_spend: Callable[[str], Decimal]` (profile id → net EUR committed today). T09 wires it to the order book; your tests pass a function.
- **Allergens and the policy.** For a buyer or request with exclusions every line needs an `AllergenCheck` with one finding per excluded code and the strictness set, or F-03 fires. Exclusions are the profile's plus the request line's. A request line with exclusions, no strictness, and a profile that sets none is `InvalidRequest`.
- Pass `Product.variable_weight` through to `OfferLine.variable_weight` as it is (`None` included: it is a missing fact for the policy).
- **Pack size and units:** `catalog.pack_size(product, price_line, unit)`. When the API line's sales unit differs from the product file's (7 of 797 lines in Friday's sample) and the source is not `PRICE_RATIO`, treat the pack size as unknown (`PACK_SIZE_UNKNOWN`). Lot rounding: `catalog.round_to_lot(product, quantity)`.
- **Which claims gate** (SPEC §4): `require_confirmed` keeps only options whose every line satisfies `OfferLine.confirmed_for_order(dated=request.needed_by is not None)`. A product that fails only this is excluded with the matching reason (`ALLERGEN_NOT_STATED` for an unsettled allergen claim).
- **A cut-off that has passed** excludes a product (`CUTOFF_PASSED`) whether or not the request has a date: the delivery Valio states can no longer be ordered (T04's reading).
- **The builder stores nothing and records no audit event.** T09's service stores the offer and writes the events. Ids: `off_` + 12 hex characters; options `opt_1`, `opt_2`, `opt_3` in rank order.
- A request for 1,000 litres tonight: the three confirmed milks cover it together (384 + 51 + 565 of `463380`), net about €2,580.64, so the verdict is `APPROVAL` by P-01 for `hotel-kitchen`. `472492` drops out with `PACK_SIZE_UNKNOWN` (priced per kg).
- Coverage runs: set `COVERAGE_FILE` to a file in your scratch directory; agents running in parallel share `.coverage` in the repository root.
