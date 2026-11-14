# T16 — Review and fixes (run by the orchestrator after waves 1, 2, 3 and at the end)

**Scores on:** 30% (it has to run) · 20% (guardrails that hold when probed).

## Each round
1. Run the whole suite and the linter: `.venv/bin/python -m pytest -q` and `.venv/bin/ruff check src tests`.
2. Launch three read-only reviewers in parallel on the wave's diff (`git diff <last reviewed commit>..HEAD -- src tests`), giving each the code and the spec, not a conclusion:
   - `python-reviewer` — correctness, types, error handling, `Decimal` use.
   - `security-reviewer` — secrets, identity and authorisation, input from the data file and the API treated as untrusted, escaping, anything a public demo URL exposes.
   - `silent-failure-hunter` — swallowed errors, fallbacks that hide a failure, a missing fact treated as a pass.
3. Check the guardrail invariants yourself, by test, not by reading:
   - an agent cannot approve; an agent cannot choose its profile; a profile cannot weaken a fixed rule;
   - no order without a policy decision; no `AUTO` with a missing fact or an unconfirmed quantity;
   - a placeholder amount never enters arithmetic; the key appears in no file under `var/`, `fixtures/` or any log.
4. Turn every critical and high finding into a fix task (`tasks/FIX-<n>.md`: the finding, the file, the failing test to add) and give it to a fresh agent with the owner's file list. Medium findings are fixed if cheap, otherwise listed in `MORNING.md`.
5. Re-run the suite. Commit.
