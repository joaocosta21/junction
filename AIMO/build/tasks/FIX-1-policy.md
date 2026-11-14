# FIX-1 — Policy: read the claims, never pass on a missing one

**Scores on:** 20% (autonomy and controls). From review round 1 (Python reviewer findings 1, 7, 8; silent-failure findings 3, 7, 11; security finding 2).
**Owns:** `src/tta/policy/`, `tests/policy/`. **Builder's hand-back:** `AIMO/build/handback/T05.md`. **Read:** SPEC §4 (the paragraph "Which claims gate"), §7 (rule F-07 is new).
**Importers to re-run:** `tests/audit`.

## Findings to fix
1. **HIGH — a missing claim counts as confirmed.** `src/tta/policy/facts.py` (`_quantity_confirmed`) is `all(...)` over the line's quantity claims, so a `CONFIRMED` line with no quantity claim is "confirmed". No fact reads the `price` or `delivery_date` claims. Fix:
   - A line with no `quantity` claim, or no `price` claim, is a **missing fact** → F-03 (purchasing manager). Never `AUTO`.
   - New fixed rule **F-07** in `rules.yaml` (fixed, `APPROVAL`, purchasing manager): fires on a line whose `price` claim is not `CONFIRMED`, or whose `delivery_date` claim is `RULED_OUT`; and on the option when it carries a `ConstraintCheck` of kind `NEEDED_BY` whose result is not `MET`. An option with no `NEEDED_BY` check has no date to meet: F-07 does not fire for that, and a `delivery_date` claim that is `UNKNOWN` on such an option does not fire it either.
   - Add F-07 to the list of fixed rules the loader requires, to the authority texts, and to the hash.
   - `tests/policy/conftest.py`: `make_line` should build lines with all five claims by default, so that a test states on purpose when a claim is absent.
2. **MEDIUM — fixed rules can be weakened by editing the file.** The loader checks that F-01 to F-05 exist and are marked fixed, not what they do. Pin the verdict and approver role of every fixed rule in code (F-01 `APPROVAL`, F-02 `BLOCK`, F-03 `APPROVAL`, F-04 `BLOCK`, F-05 `BLOCK`, F-07 `APPROVAL`): a rules file that changes one is rejected at load.
3. **LOW — expiry boundary.** `facts.py` treats an option as expired when `valid_until < now`; availability treats a cut-off equal to now as passed. Use `<=`.
4. **LOW — a ratio below 1 can print as 100%.** `text.py` `format_ratio(Decimal("0.9996"))` gives "100%", so a P-03 sentence can read "only 100% … below the 100% minimum". A ratio below 1 must never print as 100%: round down, and show one decimal when the whole-number form would hide the difference.
5. **LOW — exclusion codes in a profile.** A profile with `excluded_allergens: [milk, am]` loads. Check each code with `tta.allergens.is_known_code` at load and reject the file otherwise (`X99` is not an allergen and is rejected too).
6. **LOW — the tests re-implement the allergen table.** `tests/policy/conftest.py` (`_outcome_for`) copies the table of SPEC §6. Build the `AllergenCheck` of test lines with `tta.allergens.check_exclusions` instead, so the policy tests fail if the table changes.

## Not to change
The `DECLARED_ONLY` cell (no statement → passes, shown as unverified) stays as SPEC §6 has it: that buyer chose it, and there is no default strictness.

## Rules for this fix
- Read `AIMO/build/AGENT-RULES.md` first. Then the hand-back of the package's builder (named below) and the files named in each finding.
- Other agents are working in the same tree right now: T07 writes `src/tta/offers/`, T08 writes `src/tta/orders/`, and other fix agents edit other packages. Touch only the paths this task owns. Keep every file importable after each edit: make one coherent edit per file rather than leaving it half-changed while you run something.
- For each finding: write the failing test first, see it fail, fix, see it pass. Keep the existing tests passing; change an existing test only when the finding changes the intended behaviour, and say which in the hand-back.
- Run your package's tests and the linter, with `COVERAGE_FILE` set to a file in your scratch directory. Then run the tests of the packages that import yours (named below) and report their result; do not edit them.
- Hand-back in `AIMO/build/handback/<this task id>.md` in the usual shape, with one line per finding: fixed, partly fixed (what is left), or not fixed (why).
