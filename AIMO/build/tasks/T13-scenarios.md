# T13 — Scenarios end to end, and the demo script

**Scores on:** 30% ("a full request → lookup → order/approval flow … not just isolated pieces") · 15% (exceptions).
**Needs:** T09, T10, T12 (T11 if it landed). **Owns:** `tests/e2e/`, `docs/DEMO.md`.
**Read first:** SPEC §13 · `AIMO/PLAN.md` §2, §3 · all hand-backs.

## Build
- **End-to-end tests over HTTP in replay** for every row of SPEC §13, starting from the pasted sentence (recorded model) and ending at the audit trail.
- **One live run** (at most 6 calls to the Valio API): the three scenarios against the live mock. Report, per scenario, what differs from the replay capture.
- **`docs/DEMO.md`:** the demo click by click for the three scenarios and the backup — what to paste, who is asking, what appears, the exact sentences on screen, and one line on which criterion each moment scores. Include a 90-second cut. State which mode to demo in and how to switch to replay.
- **Scenario facts:** if tonight's capture no longer supports a scenario as planned (for example the soy drink is no longer confirmed, or a single milk now covers 1,000 litres), find the product or request that restores the intended demonstration, and say so at the top of the hand-back.

## You do not fix other packages
A failure outside `tests/e2e/` is reported with the failing test, the response body and your reading of the cause. The orchestrator sends it to the owner.

## Notes from waves 1 to 3 (read every hand-back in `AIMO/build/handback/` first, T09 to T12 and FIX-5 to FIX-8 most closely)
- **Start the app:** `TTA_ENV=demo TTA_MODE=replay .venv/bin/python -m uvicorn --factory tta.api:create_app`. `TTA_ENV` must be set: an unset environment is `prod`, which has no demo tokens and refuses to start without `TTA_TOKENS`. In tests: `create_app(Settings.for_tests(tta_data_dir=tmp_path / "var", tta_env="demo"))`; `tests/api/conftest.py` shows how to share one catalog across tests.
- **Surfaces:** REST under `/v1`, MCP at `/mcp/` (eight tools, bearer token), pages at `/` in dev and demo only. Demo tokens: `src/tta/api/demo_tokens.yaml`.
- **The model:** Gemini answered 503 to every live request on 14 Nov, so the parser and the agent run on the hand-written recordings of `fixtures/agent/` (`model: "hand-built"` in a trace). The sentences that have a recording are in those five files; the beef backup sentence has none, so it starts from the typed request. End-to-end tests start from the pasted sentence where a recording exists, and from the typed request otherwise; say which in each test's name.
- **What tonight's capture gives** (replay `2026-11-14-demo`, data clock Saturday 14 Nov 02:52): scenario 1 → option 1 three confirmed milks (`469363` 384, `462775` 51, `463380` 565) €2,580.64 `APPROVAL` P-01, option 2 `464306` €1,010.00 `APPROVAL` F-01 P-01; scenario 2 → 200 × `464013` €402.00 `AUTO`; scenario 3 → `471690` passes but its cut-off has passed, `471881` and `464320` fail (`SUBSTITUTE_ADDS_ALLERGEN`), best orderable `475224`; backup → 30 × `466988` €506.40 `APPROVAL` P-06.
- **SPEC §13 against tonight's data:** scenario 1 "verdict APPROVAL with the rules named" holds (P-01) but the fill is full, not partial: say so at the top of the hand-back and in `docs/DEMO.md`, and show the partial-fill case with a second request if you find one in the capture that makes it (for example a quantity above the three milks' confirmed stock of 1,133 litres). Scenario 3's "`471690` passes" holds for the allergen rule; tonight it cannot be ordered (cut-off passed) — show that as the exception it is.
- **Live run:** at most 6 calls to the Valio API (the budget file shows 4 used). Use `TTA_MODE=live`; check `source` on each offer and on `/healthz`. If the mock refuses or is down, two attempts, then mark the live run blocked with the command, as rule 10 says.
- `docs/DEMO.md` also gives the MCP address and the token header for a judge who wants to point an agent at it, and says that orders commit nobody.
