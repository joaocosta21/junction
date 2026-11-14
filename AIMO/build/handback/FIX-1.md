# FIX-1 — done

## Findings
1. **Fixed.** A `CONFIRMED` line with no `quantity` claim, or any line with no `price` claim, is a missing fact: F-03, purchasing manager, never `AUTO`. New fixed rule F-07 (`APPROVAL`, purchasing manager) fires per line when the `price` claim is not `CONFIRMED` or the `delivery_date` claim is `RULED_OUT`, and once on the option when a `NEEDED_BY` check is not `MET`. No `NEEDED_BY` check: silent, also with a `delivery_date` claim that is `UNKNOWN`. F-07 is in the fixed rules the loader requires, in the authority texts (rule sentence and summary) and in the hash. `make_line` builds all five claims.
2. **Fixed.** Verdict and approver role of F-01, F-02, F-03, F-04, F-05 and F-07 are pinned in `validation.FIXED_RULES`; a rules file that changes one, in either direction, is rejected at load. Left, not asked: the `when` of a fixed rule, `defaults.missing_fact_approver_role` and the per-fact `missing_role` (F-03's role comes from these) are not pinned.
3. **Fixed.** An option is expired when `valid_until <= now`.
4. **Fixed.** `format_ratio` rounds down to one decimal: 0.9996 prints `99.9%`.
5. **Fixed.** A profile whose `excluded_allergens` holds a code outside the table (`milk`, `am`, `AM `) or `X99` is rejected at load; every problem is listed.
6. **Fixed.** `make_allergen_check` builds statements and calls `tta.allergens.check_exclusions`; the copied table is gone.

## Built
- `src/tta/policy/claims.py` (new) — reads claim statuses and the needed-by check from an option; least favourable statement counts; an absent claim is `None`
- `src/tta/policy/facts.py` — `line.quantity_confirmed` missing without a claim; new facts `line.price_claim`, `line.delivery_date_claim`, `line.unconfirmed_reason`, `option.needed_by_check`, `option.needed_by`, `option.needed_by_finding`; `<=` for expiry
- `src/tta/policy/rules.yaml` — the six facts; F-07 as two entries under one id (`scope: line`, `scope: order`); summary line; fact notes
- `src/tta/policy/validation.py` — `FIXED_RULES` (verdict, role, scopes per fixed rule); one entry per scope allowed under one id, entries of one id must agree on fixed, title, verdict, role
- `src/tta/policy/engine.py` — `describe_authority` gives one `RuleSummary` per rule id, joining the texts of its entries
- `src/tta/policy/profiles.py` — exclusion codes checked with `is_known_code`; `X99` rejected
- `src/tta/policy/text.py` — `format_ratio` rounds down
- `tests/policy/test_claims.py` (new, 26 tests); `conftest.py`; additions in `test_rulebook.py`, `test_profiles.py`, `test_facts.py`, `test_order_time.py`, `test_hash.py`, `test_authority.py`, `test_missing_facts.py`

Existing tests changed (expected outcomes of no existing case changed; the 227 passed on the new `conftest.py` before any source edit):
- `conftest.py` — `make_line`: five claims, each `CONFIRMED`, `None` leaves one out; `make_option`: a `MET` needed-by check for 2026-11-16 by default, `needed_by=None` for a request without a date
- `test_rulebook.py::test_the_shipped_rules_are_exactly_those_of_the_spec` — F-07 added; ids compared after dropping the repeat; `_rule` takes an optional scope
- `test_authority.py` — F-07 in the rule list (6 fixed), one more assertion on the summary
- `test_profiles.py` — `FIXED_IDS` and two parametrisations gain F-07
- `test_missing_facts.py::test_no_missing_fact_ever_yields_auto` — three claim cases added

## Tests
Each new test was run before the fix: 65 failed, 245 passed. After:
`COVERAGE_FILE=<scratchpad>/.coverage.fix1 .venv/bin/python -m pytest tests/policy -q --cov=tta.policy --cov-report=term-missing`
```
src/tta/policy/text.py            31      0      4      0   100%
src/tta/policy/validation.py     182      1    114      1    99%   161
--------------------------------------------------------------------------
TOTAL                            961      7    282      7    99%
310 passed in 2.97s
```
`.venv/bin/ruff check src/tta/policy tests/policy` → `All checks passed!`
Importers, last run, not edited:
- `tests/audit` → `137 passed in 0.18s` (it imports nothing from `tta.policy`; an earlier run failed in `tta.audit` only, while FIX-2 was writing)
- `tests/orders` → `89 passed in 0.43s`; `tests/offers` → `117 passed in 1.84s` (both build the engine from the shipped files)

## Assumptions
- F-07 is listed twice in `rules.yaml` under one id, once per scope. `PolicyDecision.rule_ids` can hold `F-07` several times (one per line, one for the option); `Authority.rules` lists it once.
- F-07 on the option reads only `ConstraintCheck`s of kind `NEEDED_BY`; `subject` is printed as the date. Several such checks: the least favourable counts.
- On a dated option whose check says `MET`, a line with a `delivery_date` claim `UNKNOWN` does not fire F-07: the policy relies on the offer's check, as the task and SPEC §4 say. `tta.offers.checks` gives `MET` only when every line's claim is `CONFIRMED`, so the two agree today.
- A line with no `delivery_date` claim is a missing fact too (F-03), dated or not (SPEC §4, last sentence). Hand-built lines need `price`, `quantity` and `delivery_date` claims. The `allergens` and `origin` claims are not read by the policy.
- A line in a state other than `CONFIRMED` with no `quantity` claim fires F-01, not F-03: the state settles it.
- When F-07 already fires on a line, a claim missing on that line is not listed by F-03. The verdict is `APPROVAL` either way.
- A claim stated twice on a line counts as its least favourable statement.
- The `scope` of each fixed rule is pinned too: F-07 needs both entries, so dropping one is "fixed rule missing".
- `format_ratio` rounds every ratio down, not only those near 1: 0.8999 now prints `89.9%` (before: "only 90% … below the 90% minimum").
- Profile exclusion codes are not normalised: the file is rejected.
- The policy hash of both profiles changed (new rule, new facts).

## Contract changes needed
- None needed.
- `Ratio` (contracts/common.py) serialises half-up at 4 places: a fill of 0.99995 or more is `1.0` in the offer JSON and in `FiredRule.facts`, while the sentence prints `99.9%`.

## Not done
- F-05 wording, reported by FIX-3 and outside this task: for a substitute that raises `MAY_CONTAIN` to `CONTAINS` the message still says "adds an allergen the original does not declare" (`rules.yaml`, F-05 `title` and `message`).
- For T08, not mine to edit: `src/tta/orders/records.py:55` (`is_past_order_by`) uses `deadline < now`, "as in the policy". The policy, availability and `offers/revalidation.py` now all use `<=`; at the exact instant orders keeps the order pending and the policy blocks it by F-04.
- Worth adding, not built: F-07 on a line of a dated option whose `delivery_date` claim is `UNKNOWN`, so that an offer whose needed-by check contradicts its lines cannot pass.

## Questions written
0
