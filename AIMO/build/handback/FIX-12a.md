# FIX-12a — done

## Built
- `src/tta/valio/replay.py`: an id the capture does not hold gets price and availability lines marked `not_in_recording=True` (`not_recorded_price_line`, `not_recorded_availability_line`). Recorded lines are never marked, including Valio's own answer for an unknown id (`459999`).
- `src/tta/offers/candidates.py`: new check `_not_in_recording` → `NOT_IN_RECORDING`, "Not in the recorded copy of Valio's data used for this demo; a live lookup would answer." It runs after the product-file checks (allergen declared, portion pack) and before pack size, state, date and price. `evaluate` passes `key_ingredients` to the allergen rule. For an unrecorded line the assessment sentence is replaced. `claims_of` gives price, quantity and delivery date as `UNKNOWN` with the same sentence, so the substitute list says nothing in Valio's name either. 399 lines.
- `src/tta/catalog/loader.py`: `Product.key_ingredients` holds the English list, else the Finnish one. A value with no letter (`-`, `.`) counts as absent. A malformed entry rejects the file and names the product.
- `src/tta/allergens/ingredients.py` (new): `ingredient_mentions(text)` → `IngredientMention(code, words, may_contain)`.
  - Matching: English words as whole words in any case, longest first (so "pine nuts" is `PN`). Finnish forms at the start of a word.
  - Not mentions: free-from wordings ("X-free", "free from X and Y", "does not contain X, Y or Z", "without", "contains no", Finnish "-ton/-tön" and "ei sisällä").
  - A "may contain …" phrase is quoted up to the end of its sentence, on one line, at most 80 characters.
  - Exceptions: plant milks ("coconut milk"), milk-caps, and the Finnish words for lactic acid, Kalamata/Kalamon olives, calamari and fishing.
- `src/tta/allergens/exclusion.py`: `check_exclusions(..., *, ingredients=None)`.
  - When the list names an excluded allergen (or a member of its family; or its family, unless the member itself is stated FREE_FROM) while the declaration says FREE_FROM, UNDECLARED or nothing, the finding is `MAY_CONTAIN` → `TO_HUMAN`.
  - The sentence quotes both: `The ingredient list names "ALMOND" and says "MAY CONTAIN REMAINS FROM NUTS (NOT PEANUTS)", while the product states it is free from tree nuts (AN): a dietitian must decide.`
  - CONTAINS stays REJECT and a declared MAY_CONTAIN is unchanged. Without `ingredients` the result is exactly what it was before.
- `src/tta/allergens/__init__.py`: exports `IngredientMention` and `ingredient_mentions`.
- `src/tta/catalog/product_types.yaml`:
  - `cream` gets `exclude_terms: ["vegetable", "kasvirasva", "alternative", "rama professional"]` and goes from 53 to 44 products.
  - New type `vegetable_cream` (9 products, category 10401): 462703, 463254, 463299, 463975 ("vegetable"/"kasvirasva"); 469160, 469162 ("cooking cream alternative"); 467142, 467173, 467297 (Rama Professional, whose Finnish ingredient lists name vegetable oils or fats).
  - "10 L cream" now picks `463797` Arla Pro Cooking cream 10% (€33.10, AUTO); before, it picked `463975`.
- Tests:
  - `tests/allergens/test_ingredients.py` and `tests/allergens/test_ingredient_rule.py` (new).
  - `tests/allergens/test_integration_catalog.py`: 465793, the direction of every catalog-wide change, 465793 and 461449 both found.
  - `tests/catalog/test_loader.py`: key ingredients.
  - `tests/catalog/test_product_types.py`: cream and blends, bound raised to 31 types.
  - `tests/valio/test_replay.py`: flag marked, never on recorded lines, butter.
  - `tests/offers/test_data_truth_recording.py`, `test_data_truth_ingredients.py`, `test_data_truth_cream.py` (new).
- `AIMO/build/questions/FIX-12a.md`: 1 question.

## Tests
```
tests/offers: 227 passed in 3.72s
tests/policy: 396 passed in 1.98s
tests/allergens: 239 passed in 7.55s
tests/catalog: 161 passed in 3.85s
tests/valio: 225 passed in 1.34s
tests/availability: 78 passed in 0.08s
tests/ui: 231 passed in 32.36s
tests/e2e: 16 passed in 7.44s
ruff check (my paths): All checks passed!
coverage (tests/allergens tests/catalog tests/valio tests/offers): tta.allergens 100%, tta.catalog 100%, tta.valio.replay 100%, tta.offers.candidates 98% (3 earlier lines: 118, 169, 240)
```
- **Demo numbers: unchanged.** Asserted in `test_data_truth_recording.py`; `tests/e2e` passes.
  - S1: 17 cut-off passed, 1 portion pack, 1 not deliverable; €2,580.64.
  - S2: 18 declared, 12 cut-off passed, 6 not deliverable, 5 not stated; 200 × 464013, €402.00, AUTO.
  - S3: substitute 475224, €174.00; no `NOT_IN_RECORDING` in the offer or the substitute list.
  - Backup: `tests/e2e/test_backup_beef.py` passes.
  - No plant drink changes its allergen outcome.
- **Butter in replay:** 20 exclusions, all `NOT_IN_RECORDING` with the exact sentence.
- **Catalog-wide count** (17,546 products, 13,989 with an ingredient list). Products whose outcome changes when the list is read; every change is PASS → TO_HUMAN:
  - `AM`+`AW` STRICT: **18**. 460867, 461634, 461646, 462024, 462036, 463317, 465038, 465222, 465713, 466711, 466989, 467032, 467114, 467873, 468650, 469229, 473499, 474697.
  - `AM`+`AW` DECLARED_ONLY: **234**. Mostly products with no statement whose list names milk or wheat.
  - `AN` STRICT: **7**. 461449, 464824, 465793, 466600, 469229, 469469, 470094.
  - `AN` DECLARED_ONLY: **40**.
- **465793:**
  - Hotel with `AN` excluded: APPROVAL with P-04 to the dietitian, allergens claim UNKNOWN.
  - Ward (confirmed only): excluded `ALLERGEN_NOT_STATED`, quoting "ALMOND". Never AUTO.

## Assumptions
- `NOT_IN_RECORDING` comes after the product-file checks: a butter the ward cannot have reads `ALLERGEN_DECLARED`, which is true whatever the recording holds. Every other unrecorded product reads `NOT_IN_RECORDING`.
- Either flag (price or availability) is enough for `NOT_IN_RECORDING`. Captures record both endpoints for the same ids.
- An ingredient-list mention is `MAY_CONTAIN` (to a dietitian), never `CONTAINS`, even when the list names the allergen as an ingredient: the list is text, not a declaration.
- UNDECLARED is treated like "not stated", as in the SPEC table.
- A family word counts for an excluded member unless the member is stated FREE_FROM, mirroring `statements.py`: "nuts" counts for almonds; "MILK" does not count for lactose on a lactose-free milk.
- Oats in the list count for an `AW` exclusion (the SPEC oats rule). Wheat-based glucose syrup and gluten-free wheat starch also go to the dietitian.
- Finnish forms are matched only at the start of a word. Compounds that end in the allergen are missed: "kirnumaito" (buttermilk), "durumvehnä".
- The English and Finnish lists are both run on whichever text was kept. The cross-language exceptions (Kalamata) were taken from the catalog.
- Word list as in the task, plus plurals and inflected forms. Not included: dairy words (whey, cream, butter, cheese, buttermilk, casein), shellfish names (shrimp, crab), spelt, khorasan, E-numbers for sulphites.
- A placeholder ingredient text (`-`, `.`) is no list: English is "-" on 15 products and "." on 13, and the loader then falls back to Finnish.
- `vegetable_cream` takes Rama Professional by name. The evidence is in the data: their Finnish ingredient lists name vegetable oils or fats, and the marketing texts of 467142 and 467297 call them "vaihtoehto meijerikermalle" (an alternative to dairy cream).

## Contract changes needed
- `AvailabilityState` (or `AvailabilityAssessment`): has no "not recorded" or unknown state, so an unrecorded product's `assessment.state` still reads `NOT_DELIVERABLE`; only its sentence is honest. A `NOT_IN_RECORDING` state, or an `assessment.not_in_recording` field, would let the substitute card stop showing "Not deliverable" for it.
- `AllergenFinding`: a `source` field (`declaration` | `ingredient_list`) would let the policy and the pages tell a list conflict from a declared MAY_CONTAIN without reading the sentence.

## Not done
- `src/tta/ui/view.py` (not mine) has no label for `NOT_IN_RECORDING`. It reads "Not in recording" through `plain()`. A label such as "Not in the recording" would read better.
- The substitute card shows the availability state label: `NOT_DELIVERABLE` for an unrecorded product (contract change above).
- `docs/ASSUMPTIONS.md:48` says "30 types"; it is now 31 (`vegetable_cream`). `docs/DEMO.md` and `AIMO/USE-CASES.md` do not yet mention the 10 L cream pick or the ingredient rule. Not my files.
- `cream` still holds a quark (473205) and a protein mousse (473461) filed in category 10401. They are not blends, so they were left in.
- No change to `tta.availability`: none was needed.

## Questions written
1, `AIMO/build/questions/FIX-12a.md` (for Valio: declaration against ingredient list, 5 examples; it widens ALMOND-1).
