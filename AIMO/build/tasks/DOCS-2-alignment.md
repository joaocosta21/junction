# DOCS-2 — Make the documents say what the code does

**Scores on:** 15% openness ("clear visibility of assumptions, well-justified technical choices") · the submission itself.
**Read first:** `AIMO/WALKTHROUGH.md` (rewritten today, checked against the code; it is the reference for what is built), `AIMO/USE-CASES.md` (section "Other places where the code and our docs disagree"), the hand-backs in `AIMO/build/handback/` for FIX-8 to FIX-11, S2, T13, T14, T15, and `AIMO/build/STATUS.md`.
**Owns:** `AIMO/SPEC.md`, `docs/ASSUMPTIONS.md`, `docs/ARCHITECTURE.md`, `docs/STANDARDS.md`, `docs/AWARDS.md`, `docs/PITCH.md`, `README.md`, and the description text of the limits in `src/tta/api/docs.py` (text only, run `tests/api/test_openapi_and_schemas.py` after). Not `docs/DEMO.md` (FEAT-1 appends to it), not `AIMO/WALKTHROUGH.md`, not `CLAUDE.md`, not any other code.

## Do
1. Every place `AIMO/USE-CASES.md` lists as disagreeing: SPEC §13 row 3 and §4 (a passed cut-off excludes a product from every request, dated or not — the code does this; say so), the F-08 text, the P-04 routing for the ward, the "standing order" mentions (none is built: say it is a next step), the two clocks.
2. `docs/ASSUMPTIONS.md`: add what was built since it was written — the per-browser order book and the rate limits per browser, per address and overall (FIX-10, FIX-11); readings checked against the text and labelled by who read them (FIX-9); Context.dev evidence on the dietitian's approval card (S2, built; wiring in progress); and mark as "being added today" the ingredient-list check, the not-in-recording wording, Aiven PostgreSQL, the Gemini photo and Finnish input, and the "My kitchen" profile page. Keep it renderable by `tta.ui.markdown` (no HTML comments; escape `|`).
3. `docs/AWARDS.md`: a Context.dev section (from `docs/CONTEXTDEV.md` and `AIMO/build/handback/S2.md`: which endpoint, why, what it visibly drives — the dietitian's approval card — and the honest note that it never changes a verdict); an Aiven section only as "being built" with a mark `<!-- check: S1 -->`; update the Gemini section with the text check of every reading (FIX-9) and mark the photo and Finnish input as being built `<!-- check: T18 -->`.
4. `src/tta/api/docs.py`: the limits paragraph says per browser on the pages, per address for REST and MCP, 60/60/15 a minute per address, 30 new books per address per 10 minutes, and the overall ceilings.
5. README: the live link (present), the per-browser order book, and "five ways to see it" (pages, REST, MCP, the buyer agent, the audit views).
Plain language; every number with its source; nothing claimed that is not committed. Leave a `<!-- check: … -->` mark on any line that depends on S1, T18, FIX-12a, FIX-12b or FEAT-1 (all running now), naming which.

## Rules
Read-only on code except the text in `docs.py`; no call to any outside service; no git command that changes anything. Hand-back `AIMO/build/handback/DOCS-2.md` listing every change and every mark left.
