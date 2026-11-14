# FIX-3 — done

## Findings
1. **Fixed.** A member marked `UNDECLARED` (or not stated) no longer outranks its declared family: `[AN CONTAINS, SA UNDECLARED]` with `SA` excluded and `[AM CONTAINS, ML UNDECLARED]` with `ML` excluded are `MAY_CONTAIN` → `TO_HUMAN` under both strictness values. A member stated `FREE_FROM` still wins (lactose-free milk with `ML` excluded passes). 0 of 17,546 catalog products are in the fixed case today.
2. **Fixed.** A substitute that declares `CONTAINS` for a code the original declares only as `MAY_CONTAIN` fails, and the sentence says "raises 1 allergen from may contain to contains: tree nuts (AN)". Listed pairs that fail over the whole catalog: **37 of 249, unchanged**; 0 pairs raise a level. Scenario 3 holds: `471690` passes, `471881` and `464320` fail adding `AW` `CONTAINS`.
3. **Fixed.** The loader strips and upper-cases each allergen code and rejects the file, naming the product and the code, when the code is not in the code table. `check_exclusions` does the same to the statements it receives and raises `SupplierUnavailable` for a code outside the table. The real file has 45 codes, none unknown, none needing normalising.
4. **Fixed.** `get_product`, `listed_substitutes` and `same_category` no longer return a deleted product, as a product or as an anchor; `search` already did not. The catalog has 0 deleted products; tested with a hand-built file.
5. **Fixed.** `exclude_terms` on a product type (English at the start of a word, Finnish anywhere). **`milk`: 91 → 78. Lactose-free milk (`milk` + `FREE_FROM_LACTOSE`): 35 → 30.** New type `sour_milk`: 11 products, 4 of them lactose-free. The table has 30 types.

## Built
- `src/tta/allergens/statements.py` — `resolve`: the declared family counts for a member unless the member itself is stated `FREE_FROM`; `Resolution.own_relation` says what the code's own statements say.
- `src/tta/allergens/exclusion.py` — statement codes normalised and checked against the code table before the rule runs; a sentence of its own for "family declared, member marked UNDECLARED".
- `src/tta/allergens/substitution.py` — compares levels, not only codes; the sentence names added and raised allergens separately.
- `src/tta/allergens/codes.py`, `__init__.py` — `normalise_code` (strip, upper case), exported.
- `src/tta/catalog/loader.py` — allergen codes normalised; a code outside the table, or not text, rejects the file.
- `src/tta/catalog/catalog.py` — the three lookups leave out deleted products.
- `src/tta/catalog/product_types.py`, `search.py` — `ProductType.exclude_terms`, applied with the type's other conditions; a blank exclude term is rejected at load.
- `src/tta/catalog/product_types.yaml` — `milk` with `exclude_terms: [sour, piimä, coffee drink, maitokahvi, soygurt]`; new `sour_milk` (`name_terms: [sour, piimä]`).
- `tests/allergens/`, `tests/catalog/` — 313 tests, 54 more than before.
- Existing tests changed, each because a finding changes the intended behaviour:
  - `test_substitution.py::test_the_rule_is_about_codes_not_about_the_level` → `test_a_substitute_that_raises_may_contain_to_contains_fails_and_says_so` (finding 2 reverses it).
  - `test_search.py::test_lactose_free_milk_is_exactly_the_35_products_of_category_10400` → `..._the_30_milks_of_category_10400`; `test_limit_cuts_the_list_and_total_keeps_the_count` 91 → 78 (finding 5).
  - `test_integration_catalog.py::test_how_many_listed_substitutes_fail_the_substitution_rule` also counts the pairs that raise a level (0).
  - `test_loader.py::test_invalid_record_is_rejected_and_names_the_product` and `test_product_types.py::test_invalid_table_is_rejected` got more cases; none was removed.

## Tests
`COVERAGE_FILE=<scratch>/fix3/.coverage .venv/bin/python -m pytest tests/allergens tests/catalog -q --cov=tta.allergens --cov=tta.catalog --cov-report=term-missing`
```
src/tta/catalog/product_types.py       48      0     10      0   100%
src/tta/catalog/search.py             108      0     24      0   100%
src/tta/catalog/sizes.py               86      0     36      0   100%
src/tta/catalog/text.py                24      0      2      0   100%
-------------------------------------------------------------------------------
TOTAL                                 759      0    192      0   100%
313 passed in 7.36s
```
`.venv/bin/ruff check src/tta/allergens src/tta/catalog tests/allergens tests/catalog` → `All checks passed!`

Importers, not edited:
- `.venv/bin/python -m pytest tests/availability tests/policy -q` in the working tree, last run → `388 passed in 1.38s`. Earlier runs failed in `tests/policy` only (18, 65, then 3 failures) while FIX-1 was writing rule F-07 and its tests; in the two runs I searched (65 and 3) no traceback passed through `tta.allergens` or `tta.catalog`.
- The same two folders as committed at `acfbe4b`, with only these two packages replaced (a copy in the scratch folder) → `305 passed`. All committed tests outside `tests/allergens` and `tests/catalog`, those two folders among them, against the two new packages → `601 passed`.

Unchanged figures, recounted over the whole catalog: with `AM` and `AW` excluded, `STRICT` → 2,882 pass, 4,969 rejected, 9,695 to a human; `DECLARED_ONLY` → 12,078 pass, 4,969 rejected, 499 to a human.

## Assumptions
- A member's own statement beats its declared family only when it is `FREE_FROM`. A member stated both `FREE_FROM` and `UNDECLARED` counts as `UNDECLARED`, so the declared family counts.
- In the family case the finding has relation `MAY_CONTAIN` and `matched_code` = the family; the sentence says the member is marked `UNDECLARED` when it is, and "makes no statement" when it is not stated.
- A raised allergen is listed in `SubstituteAllergenCheck.added` with relation `CONTAINS`, next to the added ones, in code order. So a failing check always has a non-empty `added`, which the policy fact `line.substitute_added_allergens` reads.
- The level compared is the least safe declared level of each product: an original that states both `MAY_CONTAIN` and `CONTAINS` for a code counts as `CONTAINS`.
- The sentence of a passing substitute now reads "… declares no allergen that the original does not declare, and raises none from may contain to contains."
- Statement codes are normalised (strip, upper case); excluded codes from a request or a profile are still not normalised and an unknown one stays `InvalidRequest`.
- `check_exclusions` checks the statement codes even when nothing is excluded.
- A statement code outside the table raises `SupplierUnavailable` (503), the error the catalog already uses for a data file it cannot use.
- A deleted product id behaves like an unknown id: `get_product` → `None`, `listed_substitutes` and `same_category` → `()`, and a search by id names it as not in the catalog. A listed substitute id that is not in the file at all is still returned as before.
- `milk` leaves out by name: "sour" / "piimä" (11 sour milks: `463373` `463439` `469331` `469457` `469491` `472492` `475433` `475534` `476855` `476957` `477050`), "coffee drink" / "maitokahvi" (`469266`), "soygurt" (`472516`). All counts are from the whole catalog.
- Of the 35 products of category 10400 with `FREE_FROM_LACTOSE`, the 5 left out are 4 sour milks (`469331`, `472492`, `476957`, `477050`) and the coffee drink `469266`. The task named three sour milks; `469331` is the fourth, and `469266` carries the claim too.
- Milks for coffee stay in `milk`: `462626`, `464237`, `473142` ("coffee milk", the last one vanilla) and `463380` ("Arla Cafè milk"). `463380` supplies 565 of the 1,000 litres of tonight's best option (question Q1).
- `sour_milk` is the 11 products with "sour" or "piimä" in the name; no product outside category 10400 has "piimä" in its name.
- Demo capture (sample, 14 Nov 02:52): none of the 5 lactose-free products left out has a confirmed quantity. `477050` (€1.35) and `476957` (€1.47) carry the very large Stock value (quantity not confirmed) and are no longer candidates for a request for lactose-free milk. The confirmed `469363`, `462775`, `463380`, the portion pack `463203` and the unconfirmed `464306` are still in `milk`.

## Contract changes needed
- `SubstituteAllergenCheck`: a `raised: tuple[AllergenStatement, ...]` field, so that "raised" is told apart from "added" without reading the sentence. Today both are in `added`.
- `policy/rules.yaml`, F-05: title and message say "adds an allergen the original does not declare". For a substitute that only raises a level that sentence is wrong; the allergen sentence in `allergen_check.sentence` is right. Owner: policy.
- `errors.py`: a typed error for product data that cannot be used (T02 asked for the same). `check_exclusions` and the loader raise `SupplierUnavailable` today.
- `AllergenFinding`: no field carries the basis of a finding (T03 asked for the same); the new "member marked UNDECLARED under a declared family" case is told only by the sentence.
- Documents that say "35 lactose-free milks", not mine to edit: `AIMO/build/AGENT-RULES.md` line 27 and `AIMO/PLAN.md` lines 72, 97 and 221. Through the `milk` type it is now 30; 35 is still the count of category 10400 with the claim, as `AIMO/FINDINGS.md` §2 states it. `AIMO/SPEC.md` §3 step 2 lists "category codes, name terms and claims" and can add exclude terms. `AIMO/BOOTH-QUESTIONS.md` T02-4 is answered by this fix and says 29 types (now 30).

## Not done
- Nothing of the five findings is left out.
- `check_substitute` and `statement_for` do not normalise or check codes; the task names `check_exclusions`. In the substitution rule a misspelt code counts as an added allergen, so the rule fails rather than passes.
- `ProductCatalog.products` still returns every product of the file, deleted ones included (its docstring says so). It is not part of the `Catalog` port and the tests use it for counting.
- `name_terms` of a product type has no check for a blank term; a blank one matches every name and narrows nothing.
- `tests/catalog/test_product_types.py` allows 20 to 30 types and the table now has 30: the next type needs that bound raised.
- No live API call was made.

## Questions written
1, `AIMO/build/questions/FIX-3.md` (for the team: do milks for coffee, and the vanilla one, count as "milk"?)
