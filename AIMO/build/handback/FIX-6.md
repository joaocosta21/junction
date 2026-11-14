# FIX-6 — partly done

Seven findings fixed. Finding 2 is partly fixed: every product that drops out is now an `Exclusion`, but the sum "options' products + exclusions = `candidates_considered`" cannot hold as worded, because a product that fits and is not needed has no reason code (see "Contract changes needed").

## Findings
1. **Re-check — fixed.** `available_date` (later, or stated on one side only), `sales_unit` and `tax_rate` are compared; new `field` values `delivery_date`, `sales_unit`, `tax_rate`. An earlier date and a price validity that moved later are not changes; a validity that moved earlier is.
2. **Exclusions under confirmed-only — partly fixed.** A candidate with an unconfirmed quantity or delivery date gets `QUANTITY_NOT_CONFIRMED` or `DELIVERY_DATE_NOT_CONFIRMED` with a sentence; a `PORTION` line excludes with `NOT_A_PORTION_PACK`. Left: a product that fits and is in no option is named in a note, not in `excluded[]`. The sum that holds and is tested on five replay requests: in an option + excluded + named as not needed. Tonight: scenario 1 30 = 4 + 19 + 7; scenario 2 51 = 1 + 41 + 9; beef 7 = 1 + 5 + 1; `473609` by id 1 = 1 + 0 + 0.
3. **Substitute stock taken twice — fixed.** Stock taken by the stand-ins of earlier request lines is counted. The reproduction now gives 100 × `462775` for line 1, nothing for line 2, verdict `APPROVAL`, and the re-check of that option is `ok`.
4. **`valid_until` — fixed.** `None` when any line has no cut-off. With a cut-off on every line the 9999-12-31 sentinel is never the earliest moment. Checked with the real policy: at order time such an option gets `APPROVAL` by F-03.
5. **Checks MET for missing lines — fixed.** `NEEDED_BY` and `CONFIRMED_ONLY` are `NOT_MET` when a request line has nothing offered; the sentence names the line or lines.
6. **Untrusted text — fixed.** `plain_name` in `wording.py`, used in option summaries, the product-id check, `gives_up`, the "no substitute" note and all 12 re-check sentences. `UnknownProduct` no longer carries `product_id`.
7. **Rank — fixed as specified, without effect today.** The net total is the last key. An offer holds at most one option per kind, so the kind always decides first (question 2).
8. **Dietary claims — fixed.** `DIETARY_CLAIMS` holds the eight codes; `claims_lost` (field, ranking key, F-08) counts only those; `gives_up` names every claim not carried.

**Scenario 3 afterwards** (replay `2026-11-14-demo`): `471690` still ranks first and cannot be ordered (cut-off passed). The best substitute that can be ordered is **`475224` Fazer Aito Professional Barista Oat drink** (€1.74, +€0.37, `claims_lost` empty, `gives_up` names `FREE_FROM_PRESERVATIVES`). `473424` Alpro Rice drink is rank 4. 100 L of `473609` by id, `hotel-kitchen`: option 1 `SUBSTITUTE` 100 × `475224` = €174.00 `AUTO`; option 2 `ALTERNATIVE_UNCONFIRMED` 100 × `473609` = €137.00 `APPROVAL` (F-01).

**The F-08 test passes**: rule F-08 is in `rules.yaml` (commit 39b51dd). `463149` in place of `469363` still gives `claims_lost == ("FREE_FROM_LACTOSE",)`, verdict `APPROVAL`.

**Other scenarios:** options, totals and verdicts of scenarios 1, 2 and the beef backup are unchanged. Each gains one note ("N products fit the request and are in no option …").

## Built
- `src/tta/offers/revalidation.py` — tax rate, delivery date and sales unit compared; price validity only when it ends sooner
- `src/tta/offers/candidates.py` — `_not_confirmed`, the last exclusion check (confirmed-only); `NOT_A_PORTION_PACK`; `UnknownProduct` without the id
- `src/tta/offers/planning.py` — stand-in stock tracked across request lines; the confirmed-only filter moved to the exclusion checks, its notes built from the exclusions; two branches of `_line_from` that became unreachable removed
- `src/tta/offers/builder.py` — `_unused_notes`: products that fit and are in no option
- `src/tta/offers/lines.py` — `valid_until_of`
- `src/tta/offers/checks.py` — `_empty_lines`, `_lines_label`; `NEEDED_BY` and `CONFIRMED_ONLY`
- `src/tta/offers/options.py` — net total in `_rank_key`; names cleaned in summaries
- `src/tta/offers/substitutes.py` — `DIETARY_CLAIMS`, `claims_not_carried`, `claims_lost`; `Judged.claims_not_carried`
- `src/tta/offers/substitute_wording.py` — `gives_up` names every claim not carried; names and brands cleaned
- `src/tta/offers/wording.py` — `plain_name`
- `tests/offers/test_accounting.py`, `test_dietary_claims.py`, `test_untrusted_names.py` — new; 36 tests added in all (149 → 185)
- No signature of `OfferService`, `OfferDeps`, `build_offer`, `find_substitutes` or `revalidate` changed.

**Existing tests changed, each because its finding changes the behaviour:**
- `test_checks_and_edges.py::test_a_delivery_valio_gives_no_cut_off_for_is_unverified_for_a_dated_request` — `valid_until is None` (4)
- `test_exclusions_and_requests.py::test_a_portion_request_keeps_only_portion_packs` — `NOT_A_PORTION_PACK` (2)
- `test_exclusions_and_requests.py::test_confirmed_only_leaves_the_unconfirmed_product_out_and_says_so` — the product is in `excluded` (2)
- `test_offer_substitute.py::test_tonight_an_unconfirmed_named_product_gets_a_confirmed_substitute_ranked_first` — stand-in `475224` (8)
- `test_offer_substitute.py::test_the_ward_may_not_take_a_substitute_without_a_human` — `claims_lost == ()` (8)
- `test_scenario_3_substitutes.py::test_tonight_the_best_orderable_substitute_keeps_every_claim_of_the_original` — rewritten and renamed for `475224` (8)

## Tests
`COVERAGE_FILE=/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/cov-fix6/.coverage .venv/bin/python -m pytest tests/offers -q --cov=tta.offers --cov-report=term-missing`
```
src/tta/offers/planning.py               162      2     40      3    98%   120, 226, 242->245
src/tta/offers/revalidation.py           127      0     28      0   100%
src/tta/offers/service.py                 25      0      2      0   100%
src/tta/offers/substitute_wording.py      64      3     32      3    94%   28, 49, 55
src/tta/offers/substitutes.py            152      2     36      3    97%   153->152, 155, 280
src/tta/offers/wording.py                 41      0      4      0   100%
----------------------------------------------------------------------------------
TOTAL                                   1208     13    282     16    98%
185 passed in 3.38s
```
- `.venv/bin/ruff check src/tta/offers tests/offers` → `All checks passed!`
- Importers, not edited: `.venv/bin/python -m pytest tests/orders tests/api -q` → `304 passed in 9.64s` (both folders were being edited by other agents during the run).
- The tests of each finding were written first and failed before the code. Exception: `test_an_earlier_delivery_date_is_not_a_change` passed from the start; it guards against over-correcting.
- 41 deliberate faults on a scratch copy of the package: 40 caught on the first run, the last after one assertion was added (`sentence` names dietary claims only). No live call was made.

## Assumptions
- Re-check: a delivery date stated on one side only is a change; only an earlier date is not.
- Re-check: a later price validity is never a change of its own. A changed price is reported as a price change whatever the validity.
- Re-check: when the sales unit changed, stock is not compared with the quantity, because it is stated in another unit. Only the unit change is reported.
- Re-check: when the state changed or the cut-off passed, that change is reported alone, as before; date, unit and stock are not compared. A moved cut-off is still a change in either direction.
- Under confirmed-only the reason is the first unconfirmed claim in the order price, quantity, allergens, delivery date, and it comes after every other exclusion check.
- The same check applies to stand-ins inside an offer. A stand-in whose quantity is not confirmed no longer counts as orderable there, so the search widens to the next category tier to find three that are.
- The two notes about confirmed-only stay, next to the exclusions.
- "In no option" is judged across the whole offer: for a request with several lines, a product used for another line is not named.
- The reason given in the "not needed" note is the selection rule (the cheapest products that cover the quantity). It does not tell apart a product whose stock is below one lot step or was taken by an earlier request line.
- `valid_until` is `None` whenever one line has no cut-off, also when a price validity is known.
- A request line with nothing offered is named before any other reason in `NEEDED_BY` and `CONFIRMED_ONLY`.
- `plain_name` follows `tta.policy.text.plain_name`: eight quotation marks become an apostrophe, every character of Unicode category C becomes a space, runs of spaces become one, 120 characters with "…" at the cut.
- A brand is cleaned like a name. The fields `name` and `original_name` keep the text of the product file.
- Whole catalog (17,546 products): 29 names hold a double quotation mark, 9 a control or format character, 13 are longer than 120 characters.
- `sentence` of a substitute names the dietary claims lost; `gives_up` names every claim not carried, in the original's order.
- Stand-in stock goes to request lines in their order.

## Contract changes needed
- `ExclusionReason`: a code for a product that fits and is not needed, so finding 2's sum holds without a note (question 1).
- `RevalidationChange.field` comment: add `delivery_date`, `sales_unit`, `tax_rate`. The policy already words them through its fallback ("the delivery date").
- `SubstituteInfo.claims_lost` and `SubstituteCandidate.claims_lost` comments, SPEC section 5 and the note of `line.substitute_claims_lost` in `rules.yaml`: say "dietary claims".
- `plain_name` exists twice with the same rule (`tta.policy.text`, `tta.offers.wording`). One copy in `tta.contracts` would serve both.

## Not done
- Finding 2's sum as worded: see above.
- Category codes (product file) and sales units (API) enter sentences as they are: `gives_up`, the re-check sentences, and the availability sentences owned by `tta.availability`.
- `OfferLine.name`, `Exclusion.name`, `SubstituteCandidate.name` and `original_name` hold the raw name. T10 (prompt) and T12 (pages) must treat them as data.
- Seen while fixing finding 3, not changed: substitutes are ranked before the stock other lines took is known. A later line can get a partial stand-in from the first-ranked product when a lower-ranked one could cover it whole. `test_a_second_stand_in_takes_what_the_first_left_and_the_next_product_after_that` pins it.
- Seen, not changed: a re-check sentence prints an open-ended validity as "31 Dec 9999 at 00:00".
- No review agent was run on this change.

## Questions written
2, `AIMO/build/questions/FIX-6.md` (both for the team: a reason code for a product that fits and is not needed; whether the price should come before the kind in the option ranking)
