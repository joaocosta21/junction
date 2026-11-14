# DOCS-4 — The documents describe the four parts added this afternoon

Scores on the 15% "openness and credible path toward production" ("clear visibility of assumptions, well-justified technical choices, and a credible view of next development steps") and on the 30% demo (the documents a judge reads must match what the deployed app does).

Finish in 40 minutes.

## What landed (read the hand-backs before writing)
- **SUST-1** delivery and sustainability comparison: `AIMO/build/handback/SUST-1.md`. Commit `fa07e39`.
- **STAND-1** standing orders with drift detection, rule P-08: `AIMO/build/handback/STAND-1.md`. Commit `fa07e39`.
- **MENU-1** recipe logic, fixed rule F-09: `AIMO/build/handback/MENU-1.md`. Commit `fa07e39`. Since its hand-back the orchestrator carried `stands_in_for` and `stands_in_role` onto the offer line, so F-09 **does** fire now: the demo menu (beef stew and berry quark dessert, 120 servings each, butter 3 kg and sugar 2 kg in stock, by 2026-11-16, confirmed only) gives €476.48 net, APPROVAL with F-09 and P-06.
- **FALLBACK-1** rule-based reader: `AIMO/build/handback/FALLBACK-1.md`. Commit `de453e6`. Since its hand-back the orchestrator made a 401, 402 or 403 from Gemini count as out of reach (`src/tta/agent/gemini.py`, `NOT_AVAILABLE_TO_US`), so the recordings and then the rules stand in.
- `docs/ASSUMPTIONS.md` already has the rows for all four (`8163d5d`): read it and stay consistent; **do not edit it**.
- Redeployed from `8163d5d` at about 13:00 on 14 Nov; `deploy/check.py` passed 7 of 7; `/menu`, `/standing-orders`, `/kitchen`, `/assumptions` answer 200 on https://joaocostared--trusted-trade-agents.us-east.modal.run.

## Do
1. `README.md`: what the gateway does now (one short paragraph or list item per part), the new routes (`/v1/menus/recipes`, `/v1/menus/plan`, `/v1/standing-orders` and its three sub-routes), the new pages (`/menu`, `/standing-orders`), the new request fields (`prefer`, `required_labels`), and the deployed commit.
2. `AIMO/SPEC.md`: the new request fields, option kind `CHEAPEST_CONFIRMED`, the comparison, rules P-08 and F-09, the routes and pages, the rule-based reader's place in the order of answering.
3. `docs/DEMO.md`: a short section for each of the three demo moments, with the exact clicks and the figures (verify each figure in replay before writing it): the menu example (`/menu?example=event`), the standing order (load the demo one on `/standing-orders`, renew at 100 L then at 290 L), and example 5 on `/` ("100 litres of oat drink by Monday, most reliable delivery").
4. `docs/AWARDS.md` (Gemini section): the model's schema now reads `prefer` and `required_labels`; one live check passed (FALLBACK-1 hand-back); the rule-based reader stands in when the model does not answer. Nothing else in that file.
5. `docs/PITCH.md`: at most three lines, one per new demo moment, each naming the criterion it scores on.
6. `docs/ARCHITECTURE.md`, `docs/STANDARDS.md`: the new packages (`menus/`, `standing/`) and modules in the package table; nothing else unless a line is now false.
7. `AIMO/WALKTHROUGH.md`: a new section after section 12, "Added this afternoon", one subsection per part, in the walkthrough's own plain style: what it does, why (the brief's words), the rule it adds, the demo figures, what is ours and illustrative.
8. `AIMO/BOOTH-QUESTIONS.md`: append under "Raised during the overnight build" (For Valio / For the team) the questions in `AIMO/build/questions/SUST-1.md`, `STAND-1.md`, `MENU-1.md`, `FALLBACK-1.md`, rewritten in the booth shape the file uses (context → what we did → what we got → example → ask → what we build if nobody answers). **Do not edit `AIMO/BOOTH-NOW.md`**: a teammate is editing it at the booth.

## Owns
`README.md`, `AIMO/SPEC.md`, `docs/DEMO.md`, `docs/AWARDS.md`, `docs/PITCH.md`, `docs/ARCHITECTURE.md`, `docs/STANDARDS.md`, `AIMO/WALKTHROUGH.md`, `AIMO/BOOTH-QUESTIONS.md`, `AIMO/build/handback/DOCS-4.md`. Nothing else: not `docs/ASSUMPTIONS.md`, not `AIMO/BOOTH-NOW.md`, no code.

## Rules
- Plain language, short sentences, the house style of each document. Every number with its source; say whether a figure is from the whole catalog (17,546 products) or from the capture.
- Nothing claimed that is not committed and verified. If the code and a hand-back disagree, the code wins. You may run the app in replay in-process (`fastapi.testclient.TestClient(tta.api.create_app())` with `TTA_ENV=demo TTA_MODE=replay` and empty key variables) to verify a figure. No outside service is called.

## Hand-back
Per document: what you added or changed, and what you checked each figure against. Files touched.
