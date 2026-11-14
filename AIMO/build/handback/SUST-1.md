# SUST-1 — done, with one line outside my paths still needed before the new example runs end to end

**Merge blocker (STAND-1 owns `src/tta/audit/`):** add `OptionKind.CHEAPEST_CONFIRMED: "cheapest confirmed"` to `OPTION_KINDS` in `src/tta/audit/phrases.py`. Without that line, recording `OFFER_CREATED` for an offer that holds the new option raises `KeyError` at `src/tta/audit/sentences.py:120`. That breaks `POST /v1/offers`, the page and MCP whenever a preference changes the choice. Price-only offers are not affected. I checked this in replay: `offer_text(offer, for_buyer=True)` raises `KeyError <OptionKind.CHEAPEST_CONFIRMED>`. After the line is added:
- remove the `xfail` marker from `tests/ui/test_sustainability_page.py::test_the_audit_trail_names_the_cheapest_confirmed_kind`. It is `strict`, so it fails until the marker goes;
- remove the `audit_names_the_kind` fixture in the same file. For now it adds the words for the length of each page test.

## Built
- `src/tta/contracts/product.py`: `Product.labels`, the certificate labels of `packagingMarkedLabel`.
- `src/tta/contracts/offer.py`: `OfferLine.delivery_reliability`, `.carbon_kg_co2e_per_kg` and `.labels` (`None` or `()` when the file has no value). `OptionComparison` holds the earliest and latest delivery, the lowest reliability, an estimated carbon total, a count of the lines that have no value for each, the labels every line carries, and a sentence. `OfferOption.comparison` holds it.
- `src/tta/contracts/request.py`: `ProductQuery.required_labels`.
- `src/tta/contracts/common.py`: `OptionKind.CHEAPEST_CONFIRMED` and `ConstraintKind.LABEL` (see Contract changes).
- `src/tta/catalog/loader.py`: reads the labels and leaves out the three temperature ids. Any other id that is not an UPPER_SNAKE code rejects the file and names the product.
- `src/tta/catalog/search.py`: a `required_labels` filter. A label alone is enough for a search, and a label no product carries is named in the note.
- `src/tta/offers/preference.py` (new): the keys, the tiers (a product with no value ranks last), the title suffixes and the "no value for N lines" sentence.
- `src/tta/offers/comparison.py` (new): the comparison of an option and the "for Y" phrase of the trade-off.
- `src/tta/offers/combining.py`: `Supply.tier`. The fill uses the best tier alone if it can cover the quantity, then the two best tiers, and so on. Under `PRICE` every supply has tier 0, so the fill is the same as before.
- `src/tta/offers/planning.py`:
  - the preferred fill becomes `BEST_CONFIRMED`;
  - the price fill becomes the `CHEAPEST_CONFIRMED` draft when it picks something different;
  - a substitute must carry every required label.
- `src/tta/offers/options.py`:
  - `KIND_ORDER` puts `CHEAPEST_CONFIRMED` second, and `MAX_OPTIONS_WITH_CHEAPEST = 4`;
  - the cheapest option is kept only when its net total is lower;
  - the titles say what ranked the option, and the summaries carry the trade-off;
  - each option gets its comparison;
  - the `PolicyContext(...)` line was not touched.
- `src/tta/offers/checks.py`: one `LABEL` constraint check per label, including on a request line with nothing offered.
- `src/tta/offers/candidates.py`: passes `required_labels` to the search.
- `src/tta/offers/lines.py`: lines carry reliability, carbon and labels.
- `src/tta/offers/builder.py`: passes `request.prefer` on. The "in no option" note now says what ranked the products.
- `src/tta/ui/view.py`: words and a tone for `CHEAPEST_CONFIRMED`, words for `LABEL` and for `Preference`.
- `src/tta/ui/templates/_result.html`:
  - each line shows reliability as a percentage or "unknown", carbon per kg or "unknown", and its labels or "none stated";
  - each option has a "Compared with the other options" sentence;
  - the request shows "Ranked by" and any required labels.
- `src/tta/ui/examples.py`: fifth example `scenario-5`, "100 litres of oat drink by Monday, most reliable delivery" (hotel kitchen, `prefer=RELIABILITY`).
- Tests (new): `tests/catalog/test_labels.py`, `tests/offers/test_preference_fill.py`, `tests/offers/test_preference_offer.py`, `tests/offers/test_required_labels.py`, `tests/ui/test_sustainability_page.py`.
- Existing tests I changed, because each pins a shape I changed on purpose:
  - `tests/ui/test_pages.py`: 4 example buttons become 5;
  - `tests/ui/test_run_unit.py`: the list of example keys includes `scenario-5`;
  - `tests/offers/test_untrusted_names.py`: "every kind" no longer includes `CHEAPEST_CONFIRMED`, which only appears under a preference.

**The example, run in replay on capture `2026-11-14-demo`:**
- **PRICE:**
  - Option 1, `BEST_CONFIRMED` "Best confirmed option": `472145` (Oatly No Sugars Oat Drink 1L), **€133.00**, AUTO. The comparison sentence reads: "Delivery on Monday 16 Nov. Delivery reliability unknown for 1 line. Carbon footprint about 43.5 kg CO2e, a litre counted as a kilogram. No certificate label stated."
  - Option 2, `ALTERNATIVE_UNCONFIRMED`: `468465`, €117.00, APPROVAL.
- **RELIABILITY:**
  - Option 1, `BEST_CONFIRMED` "Best confirmed option, ranked by delivery reliability": `470863` (Oatly Oat Drink Semi 1L), **€140.00**, AUTO.
    - Summary: "1 confirmed product covers the 100 L asked for, for €140.00 before tax. €7.00 more than the cheapest confirmed option, for a delivery reliability of at least 100% instead of unknown."
    - Comparison: "Delivery on Monday 16 Nov. Lowest delivery reliability 100%. Carbon footprint about 43.5 kg CO2e, a litre counted as a kilogram. No certificate label stated."
  - Option 2, `CHEAPEST_CONFIRMED` "Cheapest confirmed option": `472145`, **€133.00**, AUTO. Summary: "The cheapest confirmed option: 1 confirmed product covers the 100 L asked for, for €133.00 before tax. €7.00 less than the option ranked by delivery reliability."
  - Option 3, `ALTERNATIVE_UNCONFIRMED`: `468465`, €117.00, APPROVAL.
  - On the page, the agent orders `470863` alone (status ORDERED, placed by the agent).
- **Pinned figures are unchanged under all four preferences:** scenario 1 €2,580.64, scenario 2 €402.00, scenario 3 €174.00, the dietitian case €208.00.

## Tests
`COVERAGE_FILE=<scratchpad>/.coverage .venv/bin/python -m pytest tests/catalog tests/offers tests/ui tests/e2e -q -p no:cacheprovider --cov=tta.offers --cov=tta.catalog --cov-report=term-missing`
```
src/tta/offers/comparison.py              84      4     22      4    92%   56, 80, 130, 142
src/tta/offers/options.py                126      1     20      1    99%   239
src/tta/offers/planning.py               175      2     44      3    98%   143, 254, 270->273
src/tta/offers/preference.py              51      4     20      4    89%   51, 62, 89, 95
----------------------------------------------------------------------------------
TOTAL                                   2104     24    546     25    98%
=========================== short test summary info ============================
XFAIL tests/ui/test_sustainability_page.py::test_the_audit_trail_names_the_cheapest_confirmed_kind - tta.audit.phrases.OPTION_KINDS has no words for CHEAPEST_CONFIRMED yet (STAND-1 owns src/tta/audit)
681 passed, 1 xfailed in 81.16s (0:01:21)
```
`.venv/bin/ruff check` passes on every Python file I touched. `tests/contracts`, `tests/api/test_openapi_and_schemas.py` and `tests/test_foundation.py` also pass (49 tests; run read-only).

## Assumptions
- How a preference picks products: the products whose value is best go first. If they can cover the quantity, by one product or several combined, nothing worse is used. Otherwise the next value is added, and so on. Within that set: one product that covers the quantity alone, best value first and then lowest cost; otherwise products are combined in order of value, then price. A product with no value comes after every product with one.
- The keys: `EARLIEST` uses `availableDate`; `RELIABILITY` uses the highest share; `LOWER_CARBON` uses the lowest kg CO2e per kg of the product, not the option's total.
- A preference never outranks constraint fit or verification status. This keeps the spec's ranking and the `Preference` docstring ("once every constraint is met"). If the cheapest option fits better, it ranks first and the agent orders it. That can happen only when a line names products by id, or when the preferred product's allergen data leaves a check unverified. The case is tested: two named products and a required organic label.
- `CHEAPEST_CONFIRMED` is the price fill over the same confirmed stock, sharing stock across request lines as before. It is offered only when its picks differ from the preferred fill and its net total is lower.
- `ALTERNATIVE_UNCONFIRMED` and `SUBSTITUTE` still pick by price, and both are built on the preferred confirmed lines.
- The carbon estimate is sales units × pack size × kg CO2e per kg, with a litre counted as a kilogram. A line with no value, or with no pack size in kilograms or litres, counts as unknown.
- Labels: the three `*Temperature` ids are left out by name. Every other id must match `[A-Z][A-Z0-9_]{0,59}`, or the file is rejected, as an unknown allergen code is.
- Required labels are trimmed and put in capitals, as claims are. A line that names products by id is not filtered by label, as with claims: a named product without the label fails its `LABEL` check (NOT_MET).
- The comparison counts lines, as the task words it ("unknown for N lines").
- The example sentence needs a model to read "most reliable delivery" as `prefer=RELIABILITY`. With no model the example's typed request is used. FALLBACK-1 teaches the rule-based reader.

## Contract changes needed
- **Needed, not mine:** `src/tta/audit/phrases.py` `OPTION_KINDS[OptionKind.CHEAPEST_CONFIRMED] = "cheapest confirmed"`. This is the merge blocker described at the top.
- **Made outside the listed files:**
  - `OptionKind.CHEAPEST_CONFIRMED` is in `src/tta/contracts/common.py`, because `OptionKind` lives there, not in `offer.py`;
  - `ConstraintKind.LABEL`, in the same file, was needed for "one constraint check per label".
  - Both are one-line additions. No other agent owns `common.py`.
- **Suggested:** a structured field on the option, for example `net_above_cheapest: Money | None`, so a buyer's agent and a policy rule can read the trade-off without parsing the sentence (see "Not done").

## Not done
- **No real case for `EARLIEST` in tonight's capture.** All 123 confirmed products have `availableDate` Mon 16 Nov 2026, so `EARLIEST` cannot change a choice tonight.
- **No real case for `LOWER_CARBON` either.** It changed nothing in the requests I ran: scenarios 1 to 5, type `cream` 10 L, and name term "beef" 30 kg. Carbon is equal within those categories.
- Both keys are tested with hand-built prices and stock over the real catalog instead.
- **A guardrail to add (policy, not mine):** a preference can make the agent order a dearer product alone. In replay, 10 L of type `cream` ranked by reliability gives `464727`, €73.70, AUTO. The cheapest confirmed is `463797`, €33.10: €40.60 more, ordered by the agent alone. For 30 kg of "beef", `463053` costs €1,330.50 against `466952` at €352.80; both are APPROVAL for other reasons. A profile rule such as "the preferred option costs more than N% above the cheapest confirmed → purchasing manager" would close it. It needs the structured field above.
- **A bug I saw in an existing file I own and did not fix (rule 2):** in `src/tta/offers/checks.py`, `_all_or_named` runs `str.format` on a sentence that contains the caller's name term or claim. A term with `{` or `}` raises when the check fails, which happens on a named product. I escaped braces for labels only. The fix is to escape in `_name_terms` and `_claims` too.
- Docs and the assumptions page: for the orchestrator. The data facts from the task file:
  - reliability: 4,426 and 11,034 are the files' line counts including the header. 4,425 products have a reliability value and 11,033 a carbon value, as `AIMO/FINDINGS.md` section 6 says.
  - The three lactose-free milks having no reliability value, `464306` = 1.0, 243 distinct values, and the 16 real labels with their counts all check out.
- `.comparison` and `.line-facts` have no style of their own, because `app.css` is not mine. The line facts reuse `.line-price`.

## Questions written
2, `AIMO/build/questions/SUST-1.md` (for Valio):
- carbon per kilogram or per litre for liquids, and whether it is a category average;
- whether `packagingMarkedLabel` ids are certificates an agent can rely on.
