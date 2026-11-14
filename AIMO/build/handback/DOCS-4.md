# DOCS-4 — done

## Built
Per document: what changed, and what each figure was checked against. "Replay" means the whole app run in-process (`TestClient(create_app(Settings.for_tests(tta_env="demo")))`, capture `2026-11-14-demo`, no key, empty book), driving the pages as a judge clicks them, plus REST calls.
- `README.md`: live-demo line now `8163d5d`, ~13:00, 7 of 7 (from the task brief; not re-checked, no outside call); new subsection "Added on Saturday afternoon", one item per part, with `prefer`, `required_labels`, `CHEAPEST_CONFIRMED`; served-paths table names `/menu`, `/standing-orders`, five examples and the six new routes; the no-key bullet says the rules read what has no recording. "What is not done": removed the two lines now false (comparison, standing orders/recipes "not built"); added EARLIEST/LOWER_CARBON with no real case, the dearer-preference gap, no MCP tools for the new parts, the deployed commit. Figures (€140.00/€133.00/€7.00, 470863/472145): replay, example 5.
- `AIMO/SPEC.md`: layout (`menus/`, `standing/`); §2 the six routes; §3 `prefer`, `standing_order_id`, `lines[].required_labels`, `lines[].stands_in_for`/`stands_in_role` (removed "Standing orders are not built"); §5 `CHEAPEST_CONFIRMED`, ranking with the preference, the comparison (step 6); §7 F-09, `standing_order_drift_ratio`/P-08, tolerances in the profile table; §9 the two standing-order events; §11 the order of answering with the rule-based reader and the model's schema; §12 `/menu`, `/standing-orders`, example 5; §14 standing orders no longer "none is built". Checked against `contracts/request.py`, `common.py`, `offer.py`, `audit.py`, `rules.yaml`, `offers/options.py` (`MAX_OPTIONS_WITH_CHEAPEST = 4`), `agent/fallback.py`, `agent/gemini.py`, `api/routes.py`.
- `docs/DEMO.md`: new section "Added on Saturday afternoon: three more moments": the menu (`/menu?example=event`), the standing order (load, renew 100 then 290), example 5. Every quoted sentence and figure was read off the replay pages: €476.48 / €540.81, the four lines and their nets, F-09 + P-06 sentence; history 100/96/104/100/98/102 L at €2.48, €248.00 AUTO, P-08 sentence, "5 renewals … synthetic"; €140.00/€133.00/€117.00, 20 excluded (11/8/1), 38 looked up, reliability 100%/unknown, 0.435 kg CO2e/kg, 43.5 kg comparison sentence; price-only gives 472145 €133.00 (REST). €719.20 is 290 × €2.48. Two now-false lines fixed: the beef backup pasted as text is now read by the rules (replay: 200, `rule-based`), and "Free text answers 503".
- `docs/AWARDS.md` (Gemini section only): the schema reads `prefer` and `required_labels`; the one live check (from FALLBACK-1 hand-back, not re-run); 401/402/403 count as out of reach; the rule-based reader stands in. Checked against `agent/gemini.py`, `agent/fallback.py`.
- `docs/PITCH.md`: three optional beats, one per moment, each with its criterion. Also rewrote the Q&A answer "Standing orders? Recipes? Not built", which is now false (one line beyond the three).
- `docs/ARCHITECTURE.md`: package table rows `standing/`, `menus/`; new modules in `contracts/`, `policy/`, `offers/`, `audit/`, `api/`, `agent/`, `ui/`. Lines now false fixed: F-01…F-09 in the picture, "at most three options" (fourth under a preference), the `Store` port's promise (standing orders), the "Optional — delivery and sustainability: Not built" row.
- `docs/STANDARDS.md`: no package table there. Lines now false fixed: the model's schema vs the contract (two fields left out), the CloudEvents subjects (`standing_order/<id>`), next steps 9 (comparison) and 11 (standing orders).
- `AIMO/WALKTHROUGH.md`: new section "12b. Added this afternoon" between 12 and 13 (numbered 12b so sections 13–17 and their anchors keep their numbers), one subsection per part; contents entry. Figures as in DEMO.md; the "Some cheese for Friday" refusal checked in replay (503, "cheese is named with no quantity in digits and unit").
- `AIMO/BOOTH-QUESTIONS.md`: under "Raised during the overnight build". For Valio: SUST-1 (carbon per kg), SUST-2 (labels), STAND-1 (order history), MENU-1 (functional groups). For the team: STAND-2 (tolerances), FALLBACK-1 (gluten-free), FALLBACK-2 (refusals, marked PARTLY SETTLED: 401/402/403 now fall back, 400/404 do not). Figures checked in replay: scenario 1 "about 1,100 kg CO2e", 460825 €174.00 AUTO with `EU_ORGANIC_FARMING`.
- `AIMO/build/handback/DOCS-4.md`: this file.

## Tests
No code changed; no test run. Verification scripts (scratchpad only, replay, no outside call) as described above.

## Assumptions
- The deployment facts (commit `8163d5d`, ~13:00, 7 of 7, four pages 200) are taken from the task brief; I made no outside call.
- On the deployed app, example 5 is read by Gemini if the key answers, else by the rules; only the no-key replay reading was checked, and DEMO.md says so.
- The walkthrough's new section is numbered "12b" to avoid renumbering 13–17.
- `docs/ASSUMPTIONS.md` is consistent with what I wrote; not edited.

## Contract changes needed
None.

## Not done
- `AIMO/WALKTHROUGH.md` section 12 still says "The public URL still runs the build from before these commits until the final redeploy", and its contents entry reads "Being added today" against the heading "Landed today": both outside this task's list; left as they were.
- `AIMO/BOOTH-NOW.md` not touched (teammate editing).

## Questions written
0 new; 7 rewritten into `AIMO/BOOTH-QUESTIONS.md` from `AIMO/build/questions/SUST-1.md`, `STAND-1.md`, `MENU-1.md`, `FALLBACK-1.md`.
