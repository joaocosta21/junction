# DOCS-3 — Settle the `<!-- check -->` marks: the documents say what is now committed

Scores on the 15% "openness and credible path toward production" ("clear visibility of assumptions") and on the 30% demo (the documents a judge reads must match the code they run).

## Context
DOCS-2 aligned eight documents with the code at `9a764d4` and left 26 `<!-- check: … -->` marks on lines that depended on work still running: S1, T18, FIX-12a, FIX-12b, FEAT-1. All five are now committed:
- S1 Aiven PostgreSQL: `67f3b00` (and `/healthz` reason `7b93821`). Hand-back `AIMO/build/handback/S1.md`.
- S2 Context.dev evidence: `7abb44e`, wired in `f3286e1` (answers from recordings without a key). Hand-back `S2.md`.
- T18 Gemini photo + Finnish/Swedish: `812de0f`. Its **live check is blocked** (Gemini answered 503/504): the Finnish and photo recordings are hand-built and labelled so. Hand-back `T18.md`.
- FIX-12a: `9a1893d` (not-in-recording exclusion `NOT_IN_RECORDING`; the ingredient list counts as an allergen statement — a FREE_FROM declaration contradicted by the ingredient list, or a "may contain", goes to the dietitian; 18 products for AM+AW and 7 for AN over the whole catalog of 17,546; `cream` leaves vegetable-fat blends out). Hand-back `FIX-12a.md`.
- FIX-12b: `baa4e08` (coverage per request line; the substitutes route judges candidates by the buyer's own exclusion rule; the earliest possible date when every product is late; the trade-off on the approval card). Hand-back `FIX-12b.md`.
- FEAT-1: `b91e135` ("Your kitchen", `/kitchen`, in the menu since then; a per-browser buyer profile `my-kitchen`, checked as a profile file is; "My kitchen agent" and three approvers bound to it; REST and MCP never see it). Hand-back `FEAT-1.md`.

**The deployment is not yet redone.** The public URL still runs a build from before these commits. Do not write that any of the above is on the deployed app. Where a line is about what the deployed app has, write "on the deployed app after the final redeploy" only if the line must say something; the orchestrator updates those lines after the redeploy. Leave exactly those lines with a mark `<!-- check: deploy -->`.

## Do
1. Find every `<!-- check` mark in `README.md`, `docs/*.md` and `AIMO/SPEC.md` (`grep -rn "<!-- check" README.md docs AIMO/SPEC.md`). For each: read the line, read the commit or hand-back it depends on, check the claim against the code (`src/tta/…`, `git show <commit> --stat`), rewrite the line to say what is committed now ("being added" → what it does), and remove the mark. Keep `<!-- check: deploy -->` only on lines about the deployed app.
2. Lines that describe a limit since fixed (for example "only the declaration is read today", "the substitutes route applies the substitution rule but not the buyer's own exclusion rule", "an offer reports only the least covered line"): say it is fixed and how it behaves now.
3. `docs/ASSUMPTIONS.md`: the number of product types. Count them in `src/tta/catalog/product_types.yaml` and correct the figure everywhere it appears in the owned documents.
4. `docs/DEPLOY.md`: check the rate-limit and forwarded-header wording against `src/tta/api/limits.py`, `src/tta/api/sandbox.py` and `src/tta/config.py` (`TTA_TRUSTED_PROXY_HOPS`) and correct what differs. Numbers there now: per browser 20/20/5 a minute, per address 60/60/15, global 120/120/30, live looks 6 a minute overall and 2 per address, 30 new books per address per 10 minutes — verify each against the code before writing it.
5. `docs/DEMO.md`: the limits (as in 4), the `cream` product type, the ingredient-list rule, and that the "Your kitchen" section matches the page (it is in the menu now).

## Owns
`README.md`, `docs/ARCHITECTURE.md`, `docs/PITCH.md`, `docs/AWARDS.md`, `docs/STANDARDS.md`, `docs/ASSUMPTIONS.md`, `docs/DEPLOY.md`, `docs/DEMO.md`, `AIMO/SPEC.md`, and the hand-back `AIMO/build/handback/DOCS-3.md`. Nothing else: no `src/`, `tests/`, `fixtures/`, `deploy/`, no other `AIMO/` file.

## Rules
- Plain language, short sentences, the house style of the documents. Every number with its source; say whether a figure is from the whole catalog (17,546 products) or from a sample of live calls.
- Nothing claimed that is not committed. If code and a document disagree, the code wins; if you cannot tell, keep the line as it is and list it in the hand-back.
- No outside service is called. Do not run the server. You may run tests (`COVERAGE_FILE=<scratchpad>/.cov .venv/bin/python -m pytest tests/<pkg> -q -p no:cacheprovider`) to confirm a behaviour.
- Finish in 20 minutes: a redeploy waits on `docs/ASSUMPTIONS.md`. Do `docs/ASSUMPTIONS.md` first and say in the hand-back when it was done.

## Hand-back
Per document: the marks settled (line, what it says now, what you checked it against); the marks left (`deploy` only, or anything you could not verify, with why). Files touched.
