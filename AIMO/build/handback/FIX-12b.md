# FIX-12b — done

## Built
- `src/tta/offers/options.py`: a multi-line summary says "N of the M request lines in full" ("none" when 0), then "Covered: 0 of 10 kg of butter, request line 2; 100 of 100 L of milk, request line 1." (least covered first). One-line summaries are unchanged. `fill_ratio` is still the lowest line's.
- `src/tta/offers/wording.py`: `line_words(RequestLine)` names a line by its product type, else its name terms (quoted, read as data), else its product ids; `joined()`. `percent()` removed, since nothing calls it any more.
- `src/tta/policy/coverage.py` (new, so `facts.py` stays at 400 lines): readers for `option.least_covered` and `option.coverage_by_line`. They name lines from the subjects of the option's constraint checks, the same way the summary does.
- `src/tta/policy/facts.py`: the two order facts are wired in. A missing coverage gives `Missing`.
- Beyond P-03's message, the two new facts also had to be declared in `facts:` of `rules.yaml`, because the loader checks both directions. The policy hash changes; no test pins it.
- `src/tta/policy/rules.yaml`: P-03's message is now "only {option.fill_ratio} of {option.least_covered} is covered, below the {profile.min_fill_ratio} minimum (covered: {option.coverage_by_line})", and the two facts are declared in `facts:`. The condition and the ratio it compares are unchanged.
  - Two lines: "Only 0% of the quantity of request line 2 is covered, below the 90% minimum (covered: 0 of 10 kg of butter, request line 2; 100 of 100 L of milk, request line 1)."
  - One line: "Only 75.5% of the requested quantity is covered, below the 90% minimum (covered: 1,133 of 1,500 L)."
- `src/tta/offers/substitutes.py`: `find_substitutes` now applies the profile's `require_confirmed`. The ward's list therefore excludes exactly what the ward's offer excludes, with the same reason code and sentence.
- `src/tta/offers/substitute_wording.py`: for ALLERGEN_NOT_STATED, QUANTITY_NOT_CONFIRMED and DELIVERY_DATE_NOT_CONFIRMED the sentence reads "It adds no allergen, but this buyer's rules exclude it. <the offer's sentence>". A candidate that can be ordered with TO_HUMAN findings appends them ("…: a dietitian must decide.").
- `src/tta/offers/builder.py`: when a dated line has nothing in any option, a note follows its "no product can be offered" note: "Request line 1: nothing can arrive by Sunday 15 Nov. The earliest delivery date in Valio's data for a product that otherwise fits is Monday 16 Nov, for 11 products: 462775, … and 1 more."
  - A late product counts only if it passes every other check with its own date as the needed-by date.
- `src/tta/ui/approvals_page.py`: a new `LineFacts` holds each line with its TO_HUMAN finding sentences and its `SubstituteInfo`. `Card.lines` maps each option id to these.
- `src/tta/ui/templates/approvals.html`: each line of every option in the decision form shows, above the buttons and escaped:
  - "⚠ Allergen <finding>";
  - "⚠ Substitute In place of <original> (<id>). <gives_up>";
  - "Claims it loses: …".
- Tests:
  - new: `tests/offers/test_offer_wording.py` (16), `tests/offers/test_substitutes_buyer_rule.py` (5), `tests/policy/test_coverage_by_line.py` (6), and 7 new tests in `tests/ui/test_approvals.py`;
  - updated: `tests/policy/conftest.py` (`make_option` now carries the coverage its fill ratio implies, 1,000 L), `tests/policy/test_facts.py`, `tests/policy/test_scenarios.py`, `tests/offers/test_checks_and_edges.py` and `tests/offers/test_build_offer.py`, all for the new wording.

## Tests
`COVERAGE_FILE` set to a private scratch folder. Last line of each run, verbatim:
```
== tests/offers
227 passed in 3.44s
== tests/policy
396 passed in 2.19s
== tests/allergens
239 passed in 6.33s
== tests/catalog
161 passed in 3.90s
== tests/valio
225 passed in 1.39s
== tests/availability
78 passed in 0.07s
== tests/ui
231 passed in 24.85s
== tests/e2e
16 passed in 6.33s
```
- Earlier runs failed in FIX-12a's tests (`test_data_truth_*`, `tests/allergens`, `tests/catalog`, `tests/valio`) while FIX-12a was still writing them. Once, `tests/ui` showed 22 failures while another agent was editing the request page; the next two runs were all green.
- Also green: `tests/audit` 144, `tests/orders` 157, `tests/api` 394, `tests/mcp` 59.
- Coverage (`tests/offers tests/policy tests/ui/test_approvals.py`, 642 passed): builder 100%, coverage.py 100%, options 98%, facts 98%, wording 97%, substitutes 97%, substitute_wording 96%, approvals_page 96%; `tta.offers` + `tta.policy` + `approvals_page` 98% in total.
- `ruff check` on every path touched: all checks passed.
- Scenarios, checked in replay and by the e2e tests: S1 €2,580.64 [P-01] / €1,010.00 [F-01, P-01], 19 excluded; S2 €402.00 AUTO, 41 excluded; S3 €174.00 AUTO / €137.00 [F-01], substitute ranks 1, 12 and 13 unchanged for the hotel; backup €506.40 [P-06]. These match `docs/DEMO.md`.
  - Only the wording changed: the 1,500 L partial fill's P-03 sentence now ends "(covered: 1,133 of 1,500 L)". The numbers are the same.

## Assumptions
- "Falls short" means short of full coverage. The breakdown lists every line, least covered first (ties by line number), as the task's example lists both lines.
- Each line in the breakdown is also named by its number ("request line 2"), so two lines of one type are told apart. P-03 names the least covered line by number only.
- The policy names a line from the subjects of the option's constraint checks (product type, name terms, product ids), because `OfferOption` has no request line labels.
- `passes` keeps its meaning: it adds no allergen and declares none the buyer excludes. A candidate that only the buyer's rules exclude reads `passes: true, orderable: false` with the offer's reason, which is what the page then shows.
- The substitute list applies the profile's confirmed-only only. `SubstituteQuery` has no request-level confirmed-only or allergen exclusions.
- The earliest-date note is written per request line, for a dated line with no product in any option. It names only the earliest date and the products that make it.
- The approval card shows the trade-off for every option of the offer, inside the decision form, so an approver who picks another option sees that option's facts. An approver who cannot decide sees no form and therefore no trade-off.
- The trade-off spans reuse the class `summary` (block display inside `.option`) plus a new class `trade-off`, which has no style yet. `app.css` is not mine.

## Contract changes needed
- `Coverage.label` (or `request_line_text`): would let P-03 name "butter" without reading constraint-check subjects.
- `SubstituteCandidate.exclusion_check: AllergenCheck | None`: the buyer's exclusion rule outcome is now carried only through `reason`, `sentence` and the `ALLERGENS` claim.

## Not done
- `src/tta/ui/view.py` `can_be_ordered` (not mine): a candidate that can be ordered with TO_HUMAN findings still shows "Can be ordered". It should show "Can be ordered, needs approval", as for an unconfirmed quantity.
- The AUTO decision sentence (`rules.yaml` `decision_sentences`, not mine) still says "{option.fill_ratio} of the requested quantity is covered". For several lines all above the minimum, that gives the lowest line's share.
- Docs (not mine) to update:
  - `AIMO/WALKTHROUGH.md:527` and `:1139` quote the old one-line P-03 sentence, which now ends "(covered: 1,133 of 1,500 L)";
  - `AIMO/WALKTHROUGH.md:733-734` list as open two findings this task fixes (the substitutes route and multi-line coverage);
  - section 12's FIX-12b entry can move to done.

## Questions written
0
