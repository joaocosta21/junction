# T10-followup — partly done: live check not passed

**The live check did not pass. No model id answered.** `generateContent` on `gemini-3.8-flash` returned HTTP 504 three times out of three:
- `.venv/bin/python -m tta.agent.record --only scenario-1 --max-calls 2`: 2 requests (the call and its one retry), both 504.
- `.venv/bin/python -m tta.agent.record --only scenario-1 --max-calls 1 --timeout 120`: 1 request, 504 after 120 s.
- I stopped after these two attempts (rule 10). That is 3 requests from me and 9 of tonight's 20 in all, so 11 are unused.
- `fixtures/agent/` is unchanged: all five files are still `hand-built`. Nothing was written, because the script writes only after an answer.

**What the 504 means.** The SDK sends its client time-out to the service as the server's deadline (`X-Server-Timeout`; a test now pins this). A 504 therefore means "the service did not finish within the deadline". Giving it 120 s instead of 30 s did not help.

The orchestrator's trivial prompt answered at 07:50, so there are two possible causes:
- **(a)** the service is under load (the Interactions endpoint's 503s point the same way);
- **(b)** something about our request: a 9 KB instruction plus constrained JSON output.

A likely mechanism for (b): `max_output_tokens` is unset, so a constrained answer that runs on (repeated whitespace or items) never ends within the deadline. With a cap, the API would answer `MAX_TOKENS` quickly, and `GeminiModel` already refuses that cleanly. I did not build the cap (rule 2); it is a one-line config change.

**One-request discriminator to run first:** the 07:50 probe again, then
`TTA_GEMINI_MODEL=gemini-3.6-flash .venv/bin/python -m tta.agent.record --only scenario-1 --max-calls 1`.
- If the probe answers in seconds and ours still returns 504: the cause is our request. Add the cap.
- If both fail: the cause is the service.

**When it answers:** `.venv/bin/python -m tta.agent.record --max-calls 11` (7 requests if nothing is retried), then `.venv/bin/python -m pytest tests/agent -q`.

**Decision needed for the demo (the fallback works, but it is slow with tonight's failure).** With a key set and Gemini returning 504, each sentence waits about 92 s (3 attempts × 30 s deadline, plus 1.5 s between tries) before the recording answers. 503s are fast, so the wait comes from the time-out.
- **A:** unset `GEMINI_API_KEY` for the demo. Answers are instant and labelled `hand-built`.
- **B:** lower the time-out or retries when a recording exists. Not built; needs a `Settings` field.
- **C:** keep it as is.

I recommend A until the live check passes.

## Built
- `src/tta/agent/gemini.py` now uses `generateContent` (`client.models.generate_content`) instead of the Interactions API.
  - API: version `v1`, pinned in `HttpOptions`.
  - Structured output: `response_mime_type` + `response_json_schema`.
  - Function calling: one `Tool` with automatic function calling off; `thinking_level` `low`.
  - `ModelUnreachable(SupplierUnavailable)` is raised after the retries; a refusal stays a plain `SupplierUnavailable`.
  - Finish reasons: only `STOP` counts as an answer.
  - Errors: SDK `APIError.code` or `httpx.TransportError`. Errors and logs carry the HTTP status only, and the SDK error is not chained.
  - `sdk_transport(..., timeout_seconds=30)`.
- `src/tta/agent/contents.py` (new) turns the runner's history steps into `contents`:
  - the model's `Content` goes back unchanged, thought signatures included;
  - `FunctionResponse` carries the call's `id` when the model gave one, and `{"output"|"error": …}`;
  - the results of one turn go back in one `user` content;
  - the four declarations are sent as `parameters` in the OpenAPI form.
- `src/tta/agent/fallback.py` (new): `FallbackParser` and `FallbackRunner` (question T10-1, as decided). The report opens with "Gemini did not answer; this run was served from a recording made on 14 Nov 2026 at 08:05 UTC." For hand-written answers the sentence ends "…from answers written by hand, not by a model."
- `src/tta/agent/recorded.py`: `recordings_of(text)` and `holds(kind, text)`; `label_for` now uses them.
- `src/tta/agent/__init__.py`: with a key, the hooks return the Gemini parser and runner wrapped over the recorded ones. With no key, nothing changes. `profile_strictness()` is read once per hook.
- `src/tta/agent/record.py`: `ContentTransport`, plus `--timeout` (for the live check only; the gateway keeps 30 s).
- `src/tta/agent/model.py`: one comment (history is plain steps). The interface, parser, runner, tools, prompts and schema are unchanged.
- `tests/agent/test_gemini.py`: rewritten for `generateContent`, 35 tests over the real SDK and `httpx.MockTransport`.
- `tests/agent/test_fallback.py`: new, 15 tests.
- `tests/agent/test_recorded.py`, `tests/agent/test_record.py`: one new test each.

## Tests
`COVERAGE_FILE=<scratch>/cov/.coverage.t10f .venv/bin/python -m pytest tests/agent -q -p no:cacheprovider --cov=tta.agent --cov-report=term-missing`
```
src/tta/agent/contents.py       54      2     12      0    97%   62-63
src/tta/agent/fallback.py       64      1      8      1    97%   46
src/tta/agent/gemini.py        123      0     16      0   100%
src/tta/agent/record.py        150     19     16      1    86%   200-201, 206-231, 250
src/tta/agent/recorded.py      104      0     18      0   100%
------------------------------------------------------------------------
TOTAL                         1021     24    158      2    97%
148 passed in 7.91s
```
- `.venv/bin/python -m pytest tests/api -q -p no:cacheprovider` → `251 passed in 22.00s`
- `.venv/bin/python -m pytest tests/ui -q -p no:cacheprovider` → `159 passed in 12.26s`
- `.venv/bin/ruff check src/tta/agent tests/agent` → `All checks passed!`

Tests-first record:
- The 24 wire-format and recorded-model tests failed one by one on the old module (with only the `ModelUnreachable` name stubbed in).
- The two time-out tests failed before the option existed.
- `test_fallback.py` failed at collection first (`No module named 'tta.agent.fallback'`), not test by test.

## Assumptions
- Documentation read 14 Nov 2026: the `(generateContent)` pages of aistudio.google.com/docs (structured output, function calling, thought signatures, thinking), the v1 `generateContent` reference, "API versions" and troubleshooting.
- `parameters` (the docs' Python form), not `parameters_json_schema`: the SDK 3.3.0 sends the latter in snake_case on the wire.
- The SDK also sends `thinkingConfig.thinking_level` in snake_case. I left it as the SDK sends it; it has not been checked against the live API.
- `Part.from_function_response` in SDK 3.3.0 takes no `id`, so the part is built directly with `FunctionResponse(id=…)`.
- The model's turn is kept in the history as `{"type": "model_content", "content": <Content as JSON>}` and read back with `model_validate_json`. A test checks that the signature's base64 goes back byte for byte.
- A call without an id is named `gemini-<turn>-<n>` here, and its result goes back without an id.
- An empty finish reason means "not stopped" (per the v1 reference). Any reason other than `STOP` is `supplier-unavailable` and is not retried. The error names the reason when the reference lists it; otherwise it says "not recognised".
- Retried: no response, 408, 429 and any 5xx (previously only 500/502/503/504). Never retried: 400 to 404.
- Automatic function calling is off on `extract` too. It has no tools, so the only effect is that one request stays one call.
- The fallback applies to `ModelUnreachable` only:
  - parse route: when the sentence has a parse recording;
  - run route: when it has both a parse and a run recording, and only before the run's first gateway call. The run is then served wholly from the recording. After a call, what Gemini did stands under its own name.
- "Some milk for Monday" on the run route with Gemini down answers `supplier-unavailable`, not `invalid-request`, because it has no run recording.
- On the parse route, only the log says the reading came from a recording (see contract changes).
- A sentence whose answers include any hand-written one is reported as hand-written. Dates are shown in UTC.

## Contract changes needed
- `PurchaseRequest` / parse route: no field or header can say "read from a recording, Gemini did not answer". Only the log says it.
- `AgentRun`: no field for the fallback. It shows through `model` (`recorded`/`hand-built`), `recorded: true` and the report's first sentence. A field such as `fallback: "gemini-unreachable"` would let pages show it without parsing text.
- `Settings`: the time-out and retries are still constants. A setting would allow option B above.

## Not done
- **The live check** (see the top), and therefore no model-recorded fixtures. `prompts.py` is untouched because there is no model reading to compare.
- No `max_output_tokens` cap (recommended above).
- Still no deadline for a whole run.
- Scenario 1's run stays hand-built by design of the plan (question T10-5, unchanged).
- `record.py` `main` and `_record_all` are still covered only up to the no-key exit and the option parsing.

## Questions written
0. The two decisions (the demo key setting and the output cap) are in this hand-back.
