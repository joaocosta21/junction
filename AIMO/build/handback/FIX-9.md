# FIX-9 — done (all 9 findings fixed; live Gemini behaviour on the changed prompts not checked, by instruction)

## Findings
1. **HIGH, model's numbers taken as given: fixed.** New `textcheck.py` and `days.py` check each reading against the text before the contract model is built. They cover quantity, unit, `needed_by`, exclusions, `require_confirmed` and product ids. A disagreement is a fault named `<field>: the reading did not match the text: <why>`. It is asked once more, like any answer that does not validate, then refused as `invalid-request` with `faults`. Nothing is corrected silently. A text with no number reports the quantity missing; a text with no unit word reports the unit missing. All 3 cases of the reviewer's `rev/parse.py` now raise `invalid-request`.
2. **HIGH, run loses the order: fixed.** After the first gateway call, any exception returns the run: from the model or from a tool call that raised outside the typed errors. The run keeps its steps, the order id and the status. Its report opens with what stopped it, for example "The run ended at step 4 (get_order): the gateway failed (RuntimeError); …". When `place_order` itself raised, the order is read back through `order_for_offer`, if the gateway has it. In `gemini._send`, every SDK or transport exception becomes a `_Failure` named by its HTTP status or class name only. It is not chained, and the SDK text is not logged.
3. **HIGH, recording looks like the model: fixed.** `read(text, identity) -> Reading` is on `ModelRequestParser` (over Gemini, the recorded model or any model) and on `FallbackParser`. The three sentences, exactly:
   - "Read by gemini-3.6-flash."
   - "Gemini did not answer; read from a recording of gemini-3.6-flash made on 14 Nov 2026 at 06:14 UTC."
   - "Read from an answer written by hand, not by a model."
   
   With no key there is a fourth: "Read from a recording of … made on …; no model was asked." `parse_request` returns `read(...).request`. `FallbackParser.model_id` names what answered the last reading: the model id, `recorded` or `hand-built`.
4. **MEDIUM, outage costs ~90 s per sentence: fixed.** New `outage.py` holds `OUTAGE_MEMORY_SECONDS = 120` in one `PROCESS_OUTAGE` per process, behind a lock. The hooks give it to both Gemini models. After a `ModelUnreachable`, the Gemini model raises at once for 120 s and sends nothing. So a recorded sentence is answered from its recording, labelled, and any other sentence gets `supplier-unavailable` at once. Interactive retries are now 1. `record.py` keeps two attempts (`LIVE_CHECK_RETRIES = 1`, unchanged). The reviewer's `rev/outage.py`, re-run:
   - first sentence: 2 requests, worst case about 60.5 s;
   - second sentence: 0 requests, instant.
5. **MEDIUM, report hides refusal or silence: fixed.** The report names the gateway's last refusal before any later refusal of the runner. When the model ends with no call and there is no order, the report opens "The model stopped after N steps without an offer." or "… without an order.".
6. **MEDIUM, agent may order any option: fixed.**
   - `place_order` accepts only `offer.options[0]`. Any other id is a failed step: "Only the option ranked 1 of the latest offer, opt_1, may be ordered …". An offer with no option gives "… nothing to order".
   - `MAX_OFFERS_PER_RUN = 2`.
   - On `offer-stale` or `offer-expired`, the fresh offer from `fresh_offer_id` becomes the run's latest offer. Its summary is shown in the step result, and no new offer is asked for.
7. **LOW, recording replayed for any buyer and day: fixed.**
   - `Recording.profile_id` is required. The fixtures say `hotel-kitchen` (scenario 1 parse and run, no-quantity) and `allergy-ward` (scenario 2 parse and run).
   - A recording is served only for its profile. Another profile gets `supplier-unavailable`, and no fallback is used for it.
   - A recorded `needed_by` is re-resolved by the calendar rule when the recording's `today` differs from today: "by Monday" gives 16 Nov on Sun 15 Nov and 23 Nov on Mon 16 Nov.
   - "Today" is the date in Europe/Helsinki.
8. **LOW, recorder saves a failed reading: fixed.**
   - An `invalid-request` with `faults` is not written.
   - An `invalid-request` with `missing` is written (no-quantity).
   - A run whose model stopped answering is not written: the parse is kept, the run is not.
9. **LOW, test that cannot fail: fixed.** The injection test now uses `ObedientModel`. It reads the instruction hidden in a product name and tries to order 10,000 units every way it can: arguments, a new offer, a third offer, another option. The test asserts that the model obeyed, that each attempt was refused, and that the one order is the top option of the latest offer: 200 L, €402.00. It fails on the code before the fix.

## Built
- `src/tta/agent/textcheck.py` (new): `TextFacts.of(text, today)`, which reads numbers, unit words, excluded allergens, the "confirmed" word, product-id tokens and named dates.
- `src/tta/agent/days.py` (new): `helsinki_date`, with the EU rule as a fall-back when there is no tz database, and `named_dates`, the calendar rule.
- `src/tta/agent/labels.py` (new): the reading sentences and `made_on`.
- `src/tta/agent/outage.py` (new): `Outage`, `OUTAGE_MEMORY_SECONDS` and `PROCESS_OUTAGE`.
- `src/tta/agent/model.py`:
  - `ExtractCall.profile_id` and `.today`, and `TurnCall.profile_id`, never sent to a live model;
  - `AnswerSource`;
  - `AgentModel.answer_source`.
- `src/tta/agent/parser.py`: `read`, the text cross-check, Helsinki "today".
- `src/tta/agent/recorded.py`: `profile_id`, serving per profile, date re-resolution, `answer_source`, and `holds(kind, text, profile_id)`.
- `src/tta/agent/gemini.py`: one retry, `_Failure` (every exception named by status or class), the outage memory, `answer_source`.
- `src/tta/agent/fallback.py`: `FallbackParser.read`, the labelled fallback reading, `model_id` as last answered, profile-aware fallback.
- `src/tta/agent/runner.py`: `_Progress`. A run is returned after any exception once the gateway was called. The order is read back via `order_for_offer`. The report has an opening reason and prefers the gateway's refusal.
- `src/tta/agent/tools.py`: only the top option may be ordered; two offers at most; the fresh offer is adopted; `by_gateway` on outcomes.
- `src/tta/agent/record.py`: writes only what validated, never a run that stopped, writes `profile_id`, and uses Helsinki "today".
- `src/tta/agent/prompts.py`: four edits.
  - Parser rule 2: "also after next".
  - Parser rule 6: "gluten-free" and "nut-free" are exclusions; lactose-free is a claim.
  - Runner steps 3 and 4: only rank 1; use the fresh offer; no new `create_offer`.
- `src/tta/agent/__init__.py`: the hooks pass `PROCESS_OUTAGE` to Gemini.
- `fixtures/agent/*.json`: I added one line, `"profile_id"`, to each file by hand. Every answer is unchanged, checked by comparing the JSON before and after.
- `tests/agent/test_textcheck.py` (new). I also added tests to `test_parser`, `test_fallback`, `test_gemini`, `test_guardrails`, `test_runner`, `test_recorded` and `test_record`. `conftest.py` now has `ScriptedModel.answer_source` and an autouse fixture that clears `PROCESS_OUTAGE`.

## Tests
`COVERAGE_FILE=<scratch>/fix9/.coverage.final .venv/bin/python -m pytest tests/agent -q -p no:cacheprovider --cov=tta.agent --cov-report=term-missing`
```
src/tta/agent/record.py        170     19     20      1    87%   230-231, 236-261, 280
src/tta/agent/recorded.py      125      0     26      0   100%
src/tta/agent/runner.py        122      0     22      0   100%
src/tta/agent/schema.py         32      0      2      0   100%
src/tta/agent/summaries.py      35      0      2      0   100%
src/tta/agent/textcheck.py     127      0     46      0   100%
src/tta/agent/tools.py         150      0     30      0   100%
TOTAL                         1492     21    280      1    99%
294 passed in 11.71s
```
`.venv/bin/ruff check src/tta/agent tests/agent` → `All checks passed!`

The other folders, run read-only at the end (FIX-10 is still editing them):
- `tests/ui` → `159 passed in 12.17s`
- `tests/mcp` → `59 passed in 11.28s`
- `tests/e2e` → `16 passed in 4.39s`
- `tests/api` stops at collection: `tests/api/test_sandbox.py: ModuleNotFoundError: No module named 'tta.api.sandbox'`. That is FIX-10's test, written before its module. Without that file, `tests/api` gives `289 passed in 29.10s`.

**Tests first.** The 73 `test_textcheck` tests were seen failing against stub modules. For the rest, tests and code were written close together. To check that the tests can fail, I ran them on a scratch copy of the code before the fix: `src/tta/agent/{parser,runner,tools,fallback,recorded,record,gemini,prompts,__init__}.py` and `fixtures/agent/` taken from HEAD (`<scratch>/fix9/before/`). Result: 96 failed, 198 passed. Each of the 9 findings has failing tests; the list is in `<scratch>/fix9/before/failed-before.txt`.

**Existing tests changed** (the finding changes the intended behaviour):
- **Finding 1.** In `test_parser` (9 tests), `test_runner` and `test_guardrails` (`REQUEST` and 2 sentences), and `WARD_TEXT` in `test_fallback`, each sentence now says what its scripted reading says, usually by adding "by Monday". `test_when_gemini_answers_its_own_reading_is_used` now checks `reading.source`, because a quantity of 900 for "1,000 litres" is now refused.
- **Finding 2.** `test_a_fault_that_is_not_the_models_is_not_hidden` is replaced by a test that every other exception is named by its class only. The report of a model that stopped answering now opens with that reason.
- **Finding 3.** The `parser.model_id == DEFAULT_MODEL` assertion and the fallback log line moved to a new test.
- **Finding 4.** In `test_gemini`, "tried again twice" became once, "after two retries" became one, and "can be lowered" became "can be set". In `test_fallback`, request counts went from 3 to 2, from 4 to 3, and from 6 to 2.
- **Finding 6.** In the hijacked-model test, `opt_99` is now refused by the runner (`invalid-request`), not by the gateway (`not-found`).
- **Finding 7.** `profile_id` was added to recordings, calls and `holds` in `test_recorded` and `test_record`.
- **Finding 9.** The injection test was rewritten.
- **Not mine.** `"Too many requests"` became `"Too many"` in `test_a_refusal_of_the_gateway_is_a_failed_step…`: FIX-10 changed the limiter's sentence while I worked.

## Assumptions
**Reading check (finding 1)**
- A disagreement with the text is a fault: asked once more, then `invalid-request` with `faults`. It is not refused at once.
- Numbers are read leniently. "1,000" also reads as 1 (Finnish decimal comma), and "1 000" also as the two numbers 1 and 0. Only a number that is in no reading of the text is caught.
- Number words cover English zero to ninety, hundred, thousand, dozen, "a"/"an" and "and". There are no Finnish number words.
- Unit words come from a table, in English and Finnish. A text with no unit word gives unit missing, not a mismatch.
- Exclusions are checked in one direction only. Each exclusion in the text must be in the reading, itself or through its family (tree nuts cover almonds). An extra exclusion the reading adds is kept, for example "coeliac" → AW.
- Lactose is not in the exclusion table: "lactose-free" and "no lactose" are left to the model as a claim.
- `require_confirmed` is checked in one direction, as the finding says: true needs "confirmed", "verified" or "vahvistet…" in the text. A text that asks while the reading says false is not refused.
- `needed_by` must be one of the dates the text names; any of several is accepted.
- How days are read:
  - "next Monday" is the same day as "Monday";
  - a dotted date needs its closing dot or a year; a slashed date needs a year;
  - a date without a year is the next such date;
  - "in three days" and "end of the week" are not followed, so a reading that gives them a date is refused.
- Product ids must be whole tokens. "464013,464014" splits into two; "1,000" is a number and gives no id.

**Dates and recordings (finding 7)**
- "Today" is the Helsinki date, from `zoneinfo`. Without a tz database (possible on Modal's `debian_slim`), the EU rule is used: UTC+2, or UTC+3 between the last Sundays of March and October at 01:00 UTC.
- A recorded date is re-resolved only when its `today` differs from today (a missing `today` counts as different) and the text names exactly one date. Otherwise it is served as recorded.
- A recording is never served to an identity with no profile.

**Gemini errors and outages (findings 2, 4)**
- The outage memory sits in `GeminiModel`, as a breaker. It is set only by `ModelUnreachable`, never by a refusal (400 to 404) or an unfinished answer.
- I read "keep two in record.py" as two attempts: record.py already makes two (rule 10).
- `_send` treats every exception other than `APIError` as "no usable response (ClassName)": it is retried, then `ModelUnreachable`, so a recording may stand in. Trade-off: a bug of ours on the Gemini path would show as "Gemini did not answer" (logged by class name).
- `FallbackParser.model_id` names the last reading of the process; the last writer wins between threads.

**Runner and tools (findings 2, 5, 6)**
- After the first gateway call has been attempted, a run is returned. The call that raised is not a step.
- The step cap sentence stays at the end of the report; the other reasons for stopping open it.
- Two offers at most counts the calls sent to the gateway, including those it refused. The fresh offer of a stale or expired refusal does not count.
- The step with the stale or expired refusal stays failed. The runner never places the order on the fresh offer by itself: the model must call `place_order` again.

**Prompts**
- The prompts were edited, and the recordings were not re-recorded. Gemini's behaviour on the new wording is not checked.

## Contract changes needed
- Ports: `RequestParser.read(text, identity) -> Reading`. The orchestrator adds this. `AgentModel.answer_source` is local to `tta.agent`.
- `AgentRun.reading: Reading | None`. A run does not carry its reading's source or sentence. FIX-10's finding 7 ("use the run's reading") can get only the typed request, from `steps[n].arguments["request"]` of `create_offer`.
- `AgentRun`: there is still no field for why a run ended. Only the report's opening sentence and `stopped_at_cap` say it.
- `AgentRun.model` comment: the values are the model id, `recorded` or `hand-built`.
- `GatewayService.order_for_offer` (FIX-10): the runner calls it through `getattr` until the port names it.

## Not done
- **No live call to Gemini** (instruction): the changed prompts and tool description are not checked against the model.
- **Time zone data:** the deploy image may lack tzdata. The fallback covers it; adding `tzdata` to the image or the dependencies would be cleaner (`deploy/` and `pyproject.toml` are not mine).
- **No deadline for a whole run.** With Gemini timing out, the first sentence still waits about 60.5 s (2 × 30 s plus 0.5 s); later ones are instant for 120 s. A shorter time-out would need a `Settings` field.
- `FallbackRunner.model_id` still names the live model; only the parser's was asked for.
- `record.py` `main` and `_record_all` are covered up to the no-key exit only (87%).

## Questions written
0
