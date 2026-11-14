# FALLBACK-1 — A rule-based reader when the model cannot answer

Scores on the 30% "working end-to-end demo": the deployed app's Gemini key runs on a zero balance today (it still answers, probably on the free tier). If Gemini stops, a pasted sentence that has no recording gets `supplier-unavailable` (503). Only 7 sentences are recorded. This task makes common sentences readable without any model, labelled as such, and teaches the model's schema the new request fields.

Hand back by **15:30**. Other agents work at the same time on the delivery and sustainability comparison (SUST-1), standing orders (STAND-1) and recipes (MENU-1). None of them edits `src/tta/agent/`.

## What exists
- `src/tta/agent/fallback.py` (read its docstring): when Gemini is unreachable, a sentence with a recording is answered from it; any other sentence answers `supplier-unavailable`. `tta.agent.outage` remembers a failure for a while. `agent/textcheck.py` checks every reading against the text. `agent/days.py` reads named days. `agent/labels.py` writes the sentences that say who read a request.
- `ReadingSource` (`contracts/agent.py`): `MODEL`, `RECORDING`, `HAND_BUILT`.
- New request fields since `576e4cc` and `d4ad9b7`: `PurchaseRequest.prefer` (`PRICE`, `EARLIEST`, `RELIABILITY`, `LOWER_CARBON`), `RequestLine.required_labels` (certificate labels such as `EU_ORGANIC_FARMING`, `MARINE_STEWARDSHIP_COUNCIL_LABEL`, `FAIR_TRADE_MARK`; the list is in AIMO/docs/PRODUCT-DATA.md §3.5, leaving out the three temperature ids), `PurchaseRequest.standing_order_id` and `RequestLine.stands_in_for` (both set by the gateway, never read from text).
- `tests/agent/test_schema.py::test_the_schema_has_the_fields_of_the_typed_request_except_the_buyers_words` is marked `xfail(strict=True)` until the model's schema follows the contract again.

## Build
1. **The model's schema and prompt** (`agent/schema.py`, `agent/prompts.py`, the parser's conversion): add `prefer` and `required_labels`, each `null`/empty unless the text says so ("lowest carbon", "most reliable", "as soon as possible", "organic", "MSC"); leave out `standing_order_id` and `stands_in_for`, as `text` is left out. `textcheck.py` refuses a `prefer` or a label the text gives no word for. Remove the xfail marker and make the test state the new exclusions.
2. **`ReadingSource.RULE_BASED`** in `contracts/agent.py`, and its sentence in `agent/labels.py`: "Read by fixed rules, not by a model: Gemini did not answer." (or as close as the existing labels allow).
3. **The reader** `src/tta/agent/rules_reader.py` (new): deterministic, no model, no network. It reads the common shapes and nothing else:
   - one or more lines split on "and", commas, semicolons, new lines; per line a quantity and unit (litres/l/L, kg/kilos, pieces/units/cases/packs → `UNIT`), with `1,000` and `1 000` and `1.5`;
   - the product type from the product-type table's own keys and terms (`catalog/product_types.yaml`, read through the catalog package; English, Finnish and Swedish words where the table has them); 6-digit product ids;
   - claims: lactose-free → `FREE_FROM_LACTOSE`, gluten-free → `FREE_FROM_GLUTEN` (use the claim codes the schema already allows); a claim is never an allergen exclusion (`textcheck.py`'s rule);
   - exclusions: "no milk", "without nuts", "nut-free", "no gluten" → GS1 codes; "strict" → `STRICT`; an exclusion with no strictness word stays without one, so the gateway asks for it as it does today;
   - dates with `agent/days.py` ("by Monday", "tomorrow", an ISO date); "confirmed only" → `require_confirmed`; the preference and label words of item 1.
   It returns the same proposal shape the model returns, so the **same** text check and conversion run on it. A sentence it cannot read fully (no quantity, no product) is refused with the same `supplier-unavailable` sentence as today, naming what was missing. It never guesses a quantity.
4. **The order of answering** in `fallback.py`, only when the model cannot be reached or no key is set: the recording if there is one, else the rule-based reader, else `supplier-unavailable`. A model that answered is never overridden. The same for `POST /v1/agent/run`: with no model and no recording, a run made of the fixed sequence the hand-built recordings use (`get_authority` → `create_offer` from the rule-based reading → `place_order` on option 1), labelled rule-based in its trace and report. Photo input is not covered (it needs the model).
5. Response headers and the page say who read it, through the existing `Reading` and labels (`TTA-Reading-Source: rule-based`). If the page needs a change outside `src/tta/agent/` to show it, write it in the hand-back instead of making it.

## Owns (exception to AGENT-RULES rule 1: this contract change is yours for this task)
- `ReadingSource` in `src/tta/contracts/agent.py`
- `src/tta/agent/` (all of it), `fixtures/agent/` (read only; add no recording)
- tests: `tests/agent/`, and `tests/api/` tests that pin the reading-source header or the 503 sentence, if any
- `AIMO/build/handback/FALLBACK-1.md`, `AIMO/build/questions/FALLBACK-1.md`

Not yours: everything else, including `src/tta/ui/`, `src/tta/api/`, docs.

## Live service
No Gemini calls are needed: everything is tested with fakes and the recordings. If you want one live check that the schema change is accepted, at most 2 requests with the key in `.env` through `tta.config` (never print the key), and record the result in the hand-back.

## Checks before hand-back
- `.venv/bin/python -m pytest tests/agent tests/api -q -p no:cacheprovider` (set `COVERAGE_FILE` to a scratch path) all pass, the schema test no longer xfail.
- `.venv/bin/ruff check` on every file you touched.
- In the hand-back: ten sentences the reader handles and what each reads to (include the brief's own sentence and "200 litres of oat drink, no milk, no gluten, strict, by Monday"), three it refuses and why, all verified by running them; and one `POST /v1/agent/run` with no key on a sentence that has no recording, with its outcome.
