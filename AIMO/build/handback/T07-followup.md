# T07 follow-up (`claims_lost`) — partly done

One test fails: rule F-08 is not in `src/tta/policy/rules.yaml` yet (0 matches when this was written), so the stand-in that drops a claim still reads `AUTO`. Everything in `src/tta/offers/` is done.

## Built
- `src/tta/offers/substitutes.py` — `claims_lost(original, other)`; `Judged.claims_lost`; `SubstituteCandidate.claims_lost` filled; one new ranking key right after "passes the allergen rules"
- `src/tta/offers/planning.py` — `SubstituteInfo.claims_lost` filled on the stand-in line of a `SUBSTITUTE` option. The stand-in is the first candidate of the same ranking that can be ordered, so it follows the new order
- `src/tta/offers/substitute_wording.py` — the `sentence` of a candidate that passes names the claims it lacks; `gives_up` reads the same field and its text is unchanged
- `tests/offers/` — 6 tests added, 4 changed (`test_checks_and_edges.py`, `test_offer_substitute.py`, `test_scenario_3_substitutes.py`)
- No signature of `OfferService`, `OfferDeps`, `build_offer`, `find_substitutes` or `revalidate` changed. The package was imported after every edit.

**What changes tonight** (replay `2026-11-14-demo`):
- **Scenario 3:** `471690` still passes and ranks first (it keeps all three claims of `473609`; cut-off passed, not orderable). `471881` and `464320` still fail with `SUBSTITUTE_ADDS_ALLERGEN`, in the same order. The best substitute that can be ordered is now **`473424` Alpro Rice drink 1 L** (109 confirmed, €2.36, +€0.99, loses no claim), no longer `475224` Fazer Aito Professional Barista Oat drink (€1.74, +€0.37): `475224` does not carry `FREE_FROM_PRESERVATIVES` and is now rank 5 with `claims_lost` set.
- 100 L of `473609` named by id, `hotel-kitchen`: option 1 `SUBSTITUTE` is now 100 × `473424` = €236.00 (`AUTO`, no claim lost); option 2 unchanged.
- Scenarios 1, 2 and the beef backup hold no substitute and are unchanged.

## Tests
`COVERAGE_FILE=/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/cov-t07/.coverage .venv/bin/python -m pytest tests/offers -q --cov=tta.offers --cov-report=term-missing`
```
src/tta/offers/substitute_wording.py      64      3     32      3    94%   28, 48, 54
src/tta/offers/substitutes.py            148      2     36      4    97%   136->135, 138, 211->216, 256
src/tta/offers/wording.py                 25      0      0      0   100%
----------------------------------------------------------------------------------
TOTAL                                   1109     14    256     18    98%
=========================== short test summary info ============================
FAILED tests/offers/test_checks_and_edges.py::test_a_stand_in_that_drops_a_claim_of_the_original_goes_to_a_human
1 failed, 148 passed in 3.12s
```
`.venv/bin/ruff check src/tta/offers tests/offers` → `All checks passed!`
- **The failing test** is the case of question 1: 100 L of `469363` by id, not deliverable, `463149` as the stand-in, `hotel-kitchen`. It passes up to the policy: the line is `463149`, `claims_lost == ("FREE_FROM_LACTOSE",)`. It fails on `verdict is APPROVAL` (got `AUTO`) and would then check `"F-08" in rule_ids`. To run it once FIX-5 is in: `.venv/bin/python -m pytest tests/offers/test_checks_and_edges.py -q -k drops_a_claim`. If F-08 reads the field under another name or fires on another id, only the last two lines of that test need to follow.
- The tests for the new behaviour were written first: 8 failed before the code, 1 after. Two more were added afterwards (failing candidates keep their order; a required claim the original itself lacks).
- 6 deliberate faults on a scratch copy (key removed, key applied to failing candidates too, either field not filled, the comparison turned round, the sentence dropped): all caught, with the F-08 test left out of the run.

## Assumptions
- `claims_lost` lists the original's `nutritional_claims` that the other product does not carry, in the original's order, each once.
- Every claim counts alike: `FREE_FROM_PRESERVATIVES` or `VEGAN` order candidates as `FREE_FROM_LACTOSE` does. That is why a rice drink now ranks before a barista oat drink in scenario 3. Counting only some claims is one function (`claims_lost` in `substitutes.py`); which ones is a decision for the team.
- The new key comes right after "passes the allergen rules" and before category distance and "listed by Valio": a listed substitute that loses a claim ranks after an unlisted one that keeps them all.
- Candidates that fail the allergen rules are not reordered by claims.
- Which category tiers are shown still depends on how many candidates can be ordered, not on how many keep every claim: a further tier is not opened to look for a product that keeps them all when the nearer tiers hold three that can be ordered.
- The `sentence` names the lost claims only for a candidate that passes the allergen rules; for one that fails, the allergen reason stays the whole sentence. `claims_lost` is filled for every candidate.
- A candidate that loses a claim still `passes` and stays orderable; in an offer it is the stand-in only when no orderable candidate before it keeps every claim.

## Not done
- F-08 could not be checked: see the failing test above.
- The three exclusion codes added in commit 6f58efe (`NOT_A_PORTION_PACK`, `QUANTITY_NOT_CONFIRMED`, `DELIVERY_DATE_NOT_CONFIRMED`) are not used by the builder: this follow-up did not ask for it. Today a `PORTION` line still excludes with `PORTION_PACK`, and products left out under confirmed-only are named in `Offer.notes`. The places are `_pack_preference` in `candidates.py` and `_pools` in `planning.py`.
