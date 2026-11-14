# T15 — Documents: README, assumptions, standards, award write-ups, pitch outline

**Scores on:** 15% ("open, documented standards … clear visibility of assumptions, well-justified technical choices, and a credible view of next development steps") · the submission itself.
**Needs:** T13. **Owns:** `README.md` (root), `docs/ASSUMPTIONS.md`, `docs/STANDARDS.md`, `docs/ARCHITECTURE.md`, `docs/AWARDS.md`, `docs/PITCH.md`.
**Read first:** `AIMO/CHALLENGE.md` · SPEC (all) · every hand-back (their assumptions) · `AIMO/BOOTH-QUESTIONS.md` (every "if no answer, we build" line) · `GOOGLE-CHALLENGE.md`, `MODAL-CHALLENGE.md` · `CLAUDE.md` (submission checklist).

## Build
- **`README.md`:** read the existing file first. New top: what this is in three sentences, the flow, how to run it in replay in three commands, how to run the tests, where the datasets are and how to refresh them, the licence. Keep the existing hackathon notes below under their own heading; delete nothing.
- **`docs/ASSUMPTIONS.md`** per SPEC §14: one table — what we assumed, why, what would change it, where it lives in the code.
- **`docs/STANDARDS.md`:** each open standard we use, where, and why; then the next steps toward production. **Check every claim about a standard against its own specification page and cite the URL.** Leave out anything you cannot confirm.
- **`docs/ARCHITECTURE.md`:** one diagram in text, the packages, the ports, where each brief requirement lives.
- **`docs/AWARDS.md`:** Gemini — the four points its brief asks for, answered literally from what was built; Modal — what it powers, stated honestly; Aiven and Context.dev only if S1 or S2 were built, from `docs/AIVEN.md` and `docs/CONTEXTDEV.md`.
- **`docs/PITCH.md`:** three candidate punchlines; a 3-minute pitch outline tied to the five criteria; a shot list for the 2:00 video; draft text for the submission form fields. Drafts for the team to rewrite, marked as such.

## Rules
- Describe only what exists and passes its tests. A feature that is partly done is described as partly done.
- Plain language, short sentences, numbers with their source (catalog or sample).
