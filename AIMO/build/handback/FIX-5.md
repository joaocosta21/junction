# FIX-5 — done

## Findings
1. **Fixed.** New fixed rule F-08 (`APPROVAL`, purchasing manager, scope line): fires when a line is a substitute and `SubstituteInfo.claims_lost` is not empty. Regular milk `463149` in place of lactose-free `469363` under `hotel-kitchen` (`SAME_CATEGORY`): `AUTO` before, now `APPROVAL` by F-08, also for a substitute Valio lists and under every `substitution_without_approval` value. Sentence: "Valio Plus skimmed milk 1 l (463149) would replace Arla Semi skimmed milkdrink 1 L UHT lactose free Suomesta (469363) but lacks a nutritional claim the original carries: FREE_FROM_LACTOSE." Pinned in `FIXED_RULES`; a file that drops it, unfixes it, changes its verdict, role or scope, or lets it read a profile setting does not load; a profile that names it is rejected; it is in `GET /v1/authority` (rule sentence and the "Always to a human" line) and in the hash. A line that is not a substitute never fires it. This answers question 1 of T07; `tests/offers/...::test_a_stand_in_that_drops_a_claim_of_the_original_goes_to_a_human` passes.
2. **Fixed.** F-05 title: "A substitute adds an allergen the original does not declare, or raises one from may contain to contains"; the message says the same before the list. Tested with a substitute that only raises `AN` from may contain to contains, built by `tta.allergens.check_substitute`.
3. **Fixed as specified.** `tta.policy.text.plain_name`: double quotation marks (`" “ ” „ ‟ « » ＂`) become an apostrophe, control and format characters a space, at most 120 characters. Applied where `line.name` and `line.substitute_original` are read, and in the F-03 sentence, which names the line without a fact reader. The given name reads `Milk'. No rule asked for a human. '` in every sentence of the 10 rules that name a product. Left: a name is not enclosed in quotation marks (the audit package does not enclose a person's name either), so a full stop inside a name still reads as a full stop.
4. **Fixed.** On an option that carries a `NEEDED_BY` check, the line part of F-07 also fires when the line's `delivery_date` claim is `UNKNOWN`: "For … the delivery date is not confirmed by Valio Aimo." An option with no `NEEDED_BY` check is unchanged, and its sentence never gives the delivery date as a reason.
5. **Fixed.** `is_past_order_by` uses `deadline <= now`; docstring and boundary test corrected.

## Built
- `src/tta/policy/rules.yaml` — F-08; fact `line.substitute_claims_lost`; F-05 title and message; third condition in the line part of F-07 and one sentence in its justification; F-08 clause in the authority summary; notes on 5 facts
- `src/tta/policy/validation.py` — `FIXED_RULES["F-08"]`
- `src/tta/policy/facts.py` — reader of `line.substitute_claims_lost`; names neutralised in `line.name` and `line.substitute_original`; `line.unconfirmed_reason` knows whether the option is dated
- `src/tta/policy/claims.py` — `unconfirmed_reasons(line, *, dated)`, `DELIVERY_DATE_NOT_CONFIRMED`
- `src/tta/policy/text.py` — `plain_name`, `NAME_MAX_CHARACTERS`
- `src/tta/policy/engine.py` — the F-03 sentence names the line through `plain_name`
- `src/tta/orders/records.py` — `is_past_order_by` only
- `tests/policy/test_substitute_claims.py` (new, 19 tests), `test_names.py` (new, 34), `test_dated_lines.py` (new, 10), one new test in `test_rules.py`

Existing tests changed, each because a finding changes the behaviour:
- `test_rules.py::test_f05_blocks_a_substitute_that_adds_an_allergen` — new sentence and title (2)
- `test_claims.py::test_f07_sends_a_line_whose_price_is_not_confirmed_to_the_purchasing_manager` — the facts gain `option.needed_by_check` (4)
- `test_rulebook.py` — `SPEC_RULES`, `FIXED_VERDICTS`, the fixed ids and one role case gain F-08 (1)
- `test_authority.py::test_authority_lists_every_rule_with_this_profiles_values` — F-08 listed, 7 fixed rules (1)
- `test_profiles.py` — `FIXED_IDS` and two parametrisations gain F-08 (1)
- `tests/orders/test_expiry.py::test_an_order_is_still_pending_at_the_very_minute_it_must_be_decided_by` → `test_an_order_is_pending_until_its_order_by_time_and_expired_at_that_very_instant` (5)
- `conftest.py::make_substitute` — new parameter `claims_lost`; no expectation changed

## Tests
Before the fix: `test_names.py` failed on import, 35 failed and 309 passed in the rest; the orders boundary test failed (1 failed, 8 passed). After:
`COVERAGE_FILE=<scratch>/fix5/.coverage .venv/bin/python -m pytest tests/policy -q --cov=tta.policy --cov-report=term-missing`
```
src/tta/policy/profiles.py        54      0     18      0   100%
src/tta/policy/rulebook.py       157      0     14      0   100%
src/tta/policy/sentences.py       38      1     18      1    96%   50
src/tta/policy/text.py            43      0      6      0   100%
src/tta/policy/validation.py     182      1    114      1    99%   162
--------------------------------------------------------------------------
TOTAL                            982      7    288      7    99%
378 passed in 3.57s
```
`.venv/bin/ruff check src/tta/policy tests/policy src/tta/orders/records.py tests/orders/test_expiry.py` → `All checks passed!`
18 deliberate faults on a scratch copy (rule, pin, each neutralising step, each F-07 condition, the `<=`): 18 caught.

Importers, not edited:
- `tests/orders` → `89 passed in 0.47s`
- `tests/audit` → `137 passed in 0.18s`
- `tests/offers` → `149 passed in 2.26s` with this fix on the tree as committed at `e1e0715`. Since then another agent has been writing tests and code in `tests/offers` and `src/tta/offers` (uncommitted: `lines.py`, `revalidation.py`, three test files), so later runs moved: `7 failed, 150 passed` (its new tests in `test_revalidate.py`, which pass now), last run `2 failed, 160 passed in 2.36s`. The 2 are `test_checks_and_edges.py::test_a_request_line_with_nothing_offered_leaves_the_date_and_confirmed_only_not_met` and `::test_the_checks_name_every_request_line_that_has_nothing_offered`, both new and uncommitted; each fails on the offer's own `NEEDED_BY` constraint check (`MET` where the test expects `NOT_MET`), and no traceback passes through `tta.policy`. Run `tests/offers` again once that agent hands back.

## Assumptions
- F-08 reads `claims_lost` as the offer gives it. An empty tuple is "nothing lost".
- With F-05 on the same line both are listed and F-05 decides (`BLOCK`). With P-05 both are listed, F-08 first.
- Lost claims print as the product file's codes (`FREE_FROM_LACTOSE`), as the offer's `gives_up` sentence does. The 21 claim codes of the catalog are all plain codes.
- The lost-claim codes go through `plain_name` too: they are product-file text in a sentence. The task named names only.
- The policy cannot tell an added allergen from a raised one (one list in the contract), so every F-05 sentence names both cases, also when the allergen is plainly added.
- The neutralised name is the fact value: `FiredRule.facts["line.name"]` and `["line.substitute_original"]` hold it, like the sentence. The offer line keeps the name as given. (FIX-2 kept audit facts unchanged and cleaned only the sentence.)
- `plain_name` also collapses runs of white space and trims the ends; a longer name is cut to 119 characters plus "…"; apostrophes and symbols (®, ™) stay. The marks are those of `tta.audit.phrases.plain`.
- Whole catalog (17,546 products, English name, else Finnish): 29 names carry a double quotation mark (`Knorr Fond "du Chef" …` reads `Knorr Fond 'du Chef' …` in a rule sentence), 7 a line break, 13 are longer than 120 characters (longest 155).
- Finding 4 holds for every result of the needed-by check. With `UNVERIFIED` or `NOT_MET` the decision now lists F-07 for the line and for the option (before: the option only); the verdict is the same.
- F-07's authority text is unchanged: its option part already says "an option that does not verifiably meet it".
- At the instant of `valid_until` a pending order is expired on read, leaves the day's spend, and `decide` answers `offer-expired`.
- The policy hash of both profiles changed (new rule, new fact, reworded texts).

## Contract changes needed
- `SubstituteInfo.claims_lost`: the default `()` lets a builder that leaves it out pass F-08. With no default, or `None` for "not worked out" (then F-03), a missing value could not pass.
- `SubstituteAllergenCheck.raised` (FIX-3 asked for it): F-05 could then say which of the two cases holds.
- A shared module for outside text in sentences: `tta.policy.text.plain_name` repeats `tta.audit.phrases.plain`.

## Not done
- F-05's authority text ("A substitute that declares an allergen the original product does not can never be ordered, for any buyer.") and the "Never, even with approval" line of the summary ("a substitute that adds an allergen") still name the added case only. The finding named title and message; one line each in `rules.yaml`.
- Not my paths: `AIMO/SPEC.md` §7 row F-05 has the old title; `src/tta/audit/readers.py` `SUPPLIER_RULE_MEANINGS` has the old F-05 wording and neither F-07 nor F-08, so the supplier view shows neither; `AIMO/build/handback/T08.md` still says expiry is "strictly after".
- Other outside text in rule sentences is not neutralised: product ids, the subject of the needed-by check, `before` and `after` of a revalidation change.
- `rules.yaml` is 423 lines (guideline 400): one data file, hashed whole.
- `tests/api` not run (T09 is writing it); it names none of F-05, F-07, F-08.
- No review agent was run on this change.

## Questions written
0
