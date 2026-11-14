# FALLBACK-1 — done

## Built
- `src/tta/contracts/agent.py`: `ReadingSource.RULE_BASED = "rule-based"`.
- `src/tta/agent/wording.py` (new): one word table for preferences, the 16 certificate labels (PRODUCT-DATA §3.5, without the 3 temperature ids), the lactose-free and gluten-free claims, strictness and substitute words. The text check and the reader both use it.
- `src/tta/agent/rules_reader.py` (new): `RuleReader`, which turns text into the model's proposal shape by fixed rules, and `NotReadByRules(SupplierUnavailable)`, whose `.why` names what the rules could not read.
- `src/tta/agent/rules_model.py` (new): `RuleModel`, an `AgentModel` over the reader (model id `rule-based`, `recorded=False`). Its `next_turn` is the fixed run: `get_authority`, then `create_offer`, then `place_order` on the rank-1 option read from the offer's result. When the offer has no option, it orders nothing.
- `src/tta/agent/schema.py`, `prompts.py`, `parser.py`: the model's schema now has `prefer` (nullable enum) and `required_labels` (enum array), and leaves out `standing_order_id` and `stands_in_for`. Prompt rules 15–16 and a list of label codes are added. The parser converts both fields, and refuses a label that is not a label code, a label with no word in the text, or a `prefer` other than PRICE with no word in the text. The proposal models default both fields, so the existing recordings still validate.
- `src/tta/agent/textcheck.py`: `TextFacts.preferences` and `.labels`. Shared helpers are now public (`exclusions()` also returns the indices of the words it used, plus `exclusion_triggers`, `unit_of`, `id_tokens`, `DIGIT_RUN`, `SEPARATOR`, `WORD`, `CONFIRMED`, `all_thousands`). Behaviour is unchanged.
- `src/tta/agent/days.py`: `date_spans()`, so the digits of a date are never read as a quantity.
- `src/tta/agent/labels.py`: "Read by fixed rules, not by a model." When the reading is a fallback, it ends ": Gemini did not answer." or ": no Gemini key is set."
- `src/tta/agent/fallback.py`: the order of answering. With a key, the rules are used only on `ModelUnreachable`; with no key, `live=None`. The order is the recording, else the rules, else the same `supplier-unavailable` sentence as before, with "The fixed rules could not read it either: …" added just before "Send the typed request…". A model that answered is never overridden. Runs follow the same order; a rules run's report opens "Gemini did not answer; this run was read and made by fixed rules, not by a model." (or the no-key version).
- `src/tta/agent/__init__.py`: both hooks now always return `FallbackParser` / `FallbackRunner` with the rules behind the recordings, with or without a key.
- `src/tta/agent/runner.py`: "The model stopped after …" became "The agent stopped after …", so a rules run never claims a model.
- Tests: `tests/agent/test_rules_reader.py` (new, 52 tests). Added to `test_fallback.py` (8), `test_parser.py` (7), `test_textcheck.py` (16). The xfail is removed from `test_schema.py`, which now states the two exclusions. Two wording pins changed in `test_runner.py`.

## Tests
`COVERAGE_FILE=<scratch> .venv/bin/python -m pytest tests/agent tests/api -q -p no:cacheprovider`
```
..................................                                       [100%]
898 passed in 47.61s
```
With `--cov=tta.agent`: TOTAL 99% (rules_reader 98%, rules_model 97%, fallback 99%, wording 100%). `.venv/bin/ruff check src/tta/agent/ src/tta/contracts/agent.py tests/agent/` reported "All checks passed!". The schema test no longer has an xfail.

Live check (1 Gemini request, key from `tta.config`, never printed), `gemini-3.6-flash`. "200 litres of organic oat drink as soon as possible, no milk, strict, by Monday" came back as source `model`, `plant_drink` + `oat`, 200 L, `AM` STRICT, `required_labels ["EU_ORGANIC_FARMING"]`, `prefer EARLIEST`, needed_by 2026-11-16. The new schema is accepted, and the answer passed the text check.

Verified readings: real hooks, no key, `POST /v1/requests/parse`, header `TTA-Reading-Source: rule-based` on each:
1. The brief's sentence ("I need 1,000 litres of lactose-free milk by Monday. Find an option … price and availability."). Through the API it is answered by its hand-built recording, because recordings come first. Through the rules directly: milk, FREE_FROM_LACTOSE, 1000 L, needed_by 2026-11-16, prefer null (PRICE), one answer. This equals the recording.
2. "200 litres of oat drink, no milk, no gluten, strict, by Monday" gives plant_drink, name_terms [oat], 200 L, exclude [AM, AW], STRICT, 2026-11-16.
3. "1 000 l of milk tomorrow" gives milk, 1000 L, 2026-11-15.
4. "2,5 kilos of quark by Monday, as soon as possible" gives quark, 2.5 KG, prefer EARLIEST.
5. "12 cases of mineral water and 30 packs of butter" gives 2 lines: mineral_water 12 UNIT and butter 30 UNIT.
6. "50 kg of organic beef chuck and 1 000 l of lactose-free milk; 20 kg of cheese by tomorrow, lowest carbon" gives 3 lines. Line 1 is beef_chuck with label EU_ORGANIC_FARMING, line 2 is milk with FREE_FROM_LACTOSE, line 3 is cheese. The request has prefer LOWER_CARBON and 2026-11-15.
7. "464056: 120 l by 20.11. Confirmed only." gives product_ids [464056], 120 L, 2026-11-20, require_confirmed true.
8. "30 kg gluten-free bread, most reliable" (ward) gives bread, FREE_FROM_GLUTEN, exclude [AW], prefer RELIABILITY.
9. "40 kg of MSC fresh fish by Friday" gives fresh_fish, label MARINE_STEWARDSHIP_COUNCIL_LABEL, 2026-11-20.
10. "5 kg of nut-free bread, strict" gives bread, exclude [AN], STRICT.
- (asks, as today) "200 litres of oat drink, no milk" (hotel) gives 422 `invalid-request` "Line 1 excludes milk (AM) and does not say how strictly…".

Refused (503 `supplier-unavailable`, today's sentence plus what was missing):
- "200 litres of a milk substitute by Monday": "…and this is not one of them. The fixed rules could not read it either: it asks for a substitute, which only a model reads. Send the typed request to POST /v1/offers instead."
- "Some cheese for Friday": "…: cheese is named with no quantity in digits and unit." The quantity is never guessed.
- "1.5 kg of cream cheese": "…: line 1 names more than one product type (cheese, cream)."

`POST /v1/agent/run`, no key, "300 litres of oat drink by Monday" (no recording), hotel-kitchen: 200, model `rule-based`, recorded false. Steps: get_authority, then create_offer (plant_drink + oat, 300 L, 2026-11-16), then place_order opt_1, all ok. order_status ORDERED. The report: "No Gemini key is set and this text has no recording; this run was read and made by fixed rules, not by a model. 1 confirmed product covers the 300 L asked for, for €420.00 before tax. The agent may place this order alone: … The agent placed this order alone for €420.00 net: …"

## Assumptions
- With no key, a recording made for another profile is not served (as before); the rules now read that text instead of answering OTHER_PROFILE.
- `prefer: PRICE` needs no word in the text, because it is the contract's default and changes nothing. Any other preference needs a word.
- Preference words are English plus a few Finnish and Swedish ones. "price" on its own (as in the brief's "based on price") is no preference word; "cheapest" and "lowest price" are.
- "gluten-free" is read as the claim FREE_FROM_GLUTEN and the exclusion AW (the text check requires the exclusion). This is stricter than the model's rule 6; there is a question about it.
- The rules read only product words the type table has. Most Finnish words are not in it ("maitoa" is not a milk term), so the Finnish demo sentences are read only from their recordings.
- A term of fewer than 5 letters names only the word itself or its plural ("tea" does not name "team", "rice" does not name "price"). A term of 5 letters or more also names any word it starts.
- Every exclusion in the text applies to every line, because the text check already holds a model to that. A claim or label said in a line belongs to that line; one said in a part with no quantity belongs to every line.
- Groups of three digits after a separator are thousands ("1,250 kg" is 1250 kg, never 1.25).
- A dotted date followed by a comma ("20.11.,") is not a date by the calendar rule in `days.py`, so the rules refuse its digits as a second number.
- The rules run's `AgentRun.recorded` is `False`: nothing was replayed, and `model` says `rule-based`.

## Contract changes needed
- None beyond `ReadingSource.RULE_BASED` (owned by this task).

## Not done
- Changes the page and docs need, outside `src/tta/agent/`:
  - `src/tta/ui/view.py::run_label`: a run with `model == "rule-based"` (recorded false) shows "Run live by rule-based." It should say something like "Gemini did not answer, so this run was made by fixed rules, not by a model." (or the no-key version).
  - The reading page already shows `reading.sentence`, so it says "Read by fixed rules…" with no change.
  - `src/tta/api/routes.py` `READING_HEADERS` and `src/tta/api/docs.py`: the header values listed are `model`, `recording` and `hand-built`. `rule-based` should be added.
- The rules run does not retry on a stale or expired offer (the runner instruction's step 4). It ends with the gateway's refusal.
- The rules do not read pack size ("portion packs"), number words ("two hundred"), "low lactose" or other claims; they refuse or ignore them.
- Photos are not covered (they need the model).
- A Finnish sentence whose parse is recorded but whose run is not (for example "1000 litraa laktoositonta maitoa maanantaiksi") still gets 503 on `POST /v1/agent/run` with no key. Its recorded reading plus the fixed run would serve it, but that was not built.

## Questions written
2, `AIMO/build/questions/FALLBACK-1.md` (for the team): the gluten-free claim; whether a 403/400 refusal should also fall back.
