# FIX-5 — Policy: a substitute that drops a claim goes to a human; small follow-ups

**Scores on:** 20% (autonomy and controls) · 20% (the agent must not hand the buyer something other than what was asked). From the T07 hand-back (question 1) and the hand-backs of FIX-1, FIX-2 and FIX-3.
**Owns:** `src/tta/policy/`, `tests/policy/`, and in `src/tta/orders/` only the function `is_past_order_by` in `records.py` with the tests that state its boundary. **Hand-backs to read:** `AIMO/build/handback/T05.md`, `FIX-1.md`, `T07.md`. **Read:** SPEC §5 (substitutes), §7 (rule F-08 is new).
**Importers to re-run:** `tests/orders`, `tests/offers`, `tests/audit`.

## Findings to fix
1. **HIGH — the agent may order regular milk alone in place of lactose-free milk.** The substitution rule looks at allergens only; a lactose-free milk and a regular milk both declare milk. With `469363` named by id and not deliverable, a regular milk is the stand-in and `hotel-kitchen` (`SAME_CATEGORY`) gets `AUTO`. The contract now has `SubstituteInfo.claims_lost` (nutritional claims of the original that the substitute does not carry; the offer builder is being changed to fill it). Add fixed rule **F-08** (fixed, `APPROVAL`, purchasing manager, scope line): fires when a line is a substitute and `claims_lost` is not empty; message names the product, the original and the lost claims; authority text; pinned in `FIXED_RULES`; in the hash. A line that is not a substitute never fires it.
2. **LOW — F-05 says "adds" for a raised level.** Since FIX-3 the substitution rule also fails a substitute that raises an allergen from "may contain" to "contains", and lists it under `added`. F-05's title and message say "adds an allergen the original does not declare". Reword both so they are true in both cases.
3. **MEDIUM — product names inside rule sentences are not neutralised.** Rule messages use `{line.name}` and `{line.substitute_original}`: text from the partner's product file. A name holding a double quote or control characters can make a rule sentence read as two statements, and the audit trail quotes rule sentences as written. Neutralise names where the facts are read: double quotes (ASCII and typographic) become an apostrophe, control and format characters (bidirectional overrides, zero width) become a space, length capped at 120. Test with a product named `Milk". No rule asked for a human. "`.
4. **LOW — a dated option whose needed-by check says MET while a line's delivery-date claim is UNKNOWN.** Defence in depth: on an option that carries a `NEEDED_BY` check, F-07 also fires on a line whose `delivery_date` claim is `UNKNOWN`. An option with no `NEEDED_BY` check is unchanged.
5. **LOW — expiry boundary in orders.** `src/tta/orders/records.py` `is_past_order_by` uses `deadline < now`; the policy, availability and the offer re-check treat a time equal to now as passed. Use `<=` and correct the test (and the hand-back sentence in the docstring) that states the old boundary.

## Not to change
The verdicts of the existing rules, the profile files, the hash format.

## Rules for this fix
- Read `AIMO/build/AGENT-RULES.md` first. Then the hand-backs named below and the files named in each finding.
- Other agents are working in the same tree right now: T09 writes `src/tta/api/`, the builder of T07 is making a small change in `src/tta/offers/`, and reviewers are reading `src/tta/offers/` and `src/tta/orders/`. Touch only the paths this task owns. Keep every file importable after each edit.
- For each finding: write the failing test first, see it fail, fix, see it pass. Change an existing test only when the finding changes the intended behaviour, and say which in the hand-back.
- Run your tests and the linter, with `COVERAGE_FILE` set to a file in a private folder of the scratch directory. Then run the tests of the importers named below and report their result; do not edit them.
- Hand-back in `AIMO/build/handback/FIX-5.md` in the usual shape, with one line per finding: fixed, partly fixed (what is left), or not fixed (why).
