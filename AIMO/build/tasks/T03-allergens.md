# T03 — Allergens: codes, exclusion rule, substitution rule

**Scores on:** 20% (controls: what goes to a dietitian) · 15% (substitutions) · 20% (matching a dietary need precisely).
**Needs:** T00. **Owns:** `src/tta/allergens/`, `tests/allergens/`.
**Read first:** SPEC §6 · `AIMO/docs/SCHEMA-AND-CODES.md` (allergen codes and families) · `AIMO/FINDINGS.md` §3 · `tta/contracts/allergen.py`.

## Build — pure functions over the contract's allergen statements, no I/O
- **Code table:** every allergen code in the catalog with its GS1 English name, and the families (for example the cereals under `AW`, the nuts under `AN`).
- **`statement_for(statements, code)`** → `FREE_FROM` · `CONTAINS` · `MAY_CONTAIN` · `UNDECLARED` · `NOT_STATED`. Family-aware in both directions; on conflicting statements the least safe counts.
- **`check_exclusions(statements, excluded, strictness)`** → per allergen `PASS`, `REJECT` or `TO_HUMAN`, the overall outcome, and one sentence per allergen. The table of SPEC §6 is the specification.
  - Oats: with `AW` excluded, a product declaring `GO` goes `TO_HUMAN`.
  - `X99` ("Does not contain declaration obligatory allergens") is a general statement, not a statement about one allergen: under `STRICT` it goes `TO_HUMAN` with a sentence that says so; under `DECLARED_ONLY` it passes. Record this as an assumption (booth Q2).
  - A nutritional claim is never an input to this module.
- **`check_substitute(original, substitute)`** → pass or fail, with the allergens the substitute adds (`CONTAINS` or `MAY_CONTAIN`).

## Tests to write first (hand-built statements)
- Every cell of the SPEC §6 table.
- Conflict: `FREE_FROM` and `MAY_CONTAIN` for one code → `MAY_CONTAIN`.
- Family: `AW` excluded, product declares wheat `CONTAINS` → `REJECT`; `AW` `FREE_FROM` and `GO` `CONTAINS` → `TO_HUMAN`.
- No statements at all → `TO_HUMAN` under `STRICT`, `PASS` (unverified) under `DECLARED_ONLY`.
- Substitute adds `MAY_CONTAIN` of a code the original lacks → fail, naming the code.

## Integration tests (file `test_integration_catalog.py`, guarded with `pytest.importorskip("tta.catalog.loader")`)
- All 35 lactose-free milks of category 10400 → `REJECT` for `AM`.
- `464056` with `AM` and `AW` excluded, `STRICT` → `PASS`. `468319` → `REJECT` (`AW`).
- `473609` against `471690` → pass; against `471881` and `464320` → fail, adding `AW`.
- Over the whole catalog: how many listed substitutes fail the substitution rule. FINDINGS says 37 of 249; if you count differently, report both numbers, do not bend the code.
