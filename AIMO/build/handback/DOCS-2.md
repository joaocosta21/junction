# DOCS-2 — done

All five items are done. Only the owned paths were edited, and no outside service was called. Facts were checked against the code at HEAD `9a764d4` and the hand-backs. S1 and the S2 wiring were committed while this task ran (`67f3b00`, `f3286e1`, `cf6681f`), so the documents say "committed, not yet deployed" for them, not "being built". The `<!-- check: S1 -->` marks stay, because `/healthz` and the redeploy are still open.

## Built
- `AIMO/SPEC.md`
  - §1: Aiven PostgreSQL behind the store interface, with the SQLite fallback `[S1]`.
  - §2: the reading headers on `/v1/requests/parse`; the `read-image` route `[T18]`.
  - §3: `product_ids` no longer mentions standing orders; they are a next step.
  - §4: `CUTOFF_PASSED` excludes a product from every request, dated or not (`_STATE_REASONS`), with the reason, and the claims paragraph says so too.
  - §5:
    - `NOT_IN_RECORDING` marked as being added `[FIX-12a]`.
    - The ranking now includes "keeps every dietary claim".
    - "Gives up" lists what it states (a lower price is not mentioned).
    - F-08 counts only the 8 dietary claims.
    - Substitutes are found only for lines that name ids.
    - The substitutes route does not apply the buyer's rule `[FIX-12b]`.
  - §6: the ingredient-list rule marked as being added `[FIX-12a]`.
  - §7:
    - F-04: a fresh offer comes only at order placement.
    - F-08: "dietary claim".
    - New paragraph "P-04 and the ward": confirmed-only excludes first, so P-04 never fires for the ward and its substitutes go to the purchasing manager through P-05.
  - §8: the daily spend is counted on the data clock's date. An approval whose re-check fails keeps waiting, and no fresh offer is built.
  - §9: audit `time` is real UTC.
  - §10: one source per lookup and the 30 s fallback, plus a new "Two clocks" bullet.
  - §11: the text check, the reading labels, rank 1 only, two offers per run, recordings per profile, and Finnish/photo `[T18]`.
  - §12: the upload and the fourth example `[T18]`, `/kitchen` `[FEAT-1]`, and the per-browser book (FIX-10).
  - §13 row 3: `471690` passes the allergen rule, but its cut-off has passed, so it cannot be ordered. Option 1 is 100 × `475224`, €174.00, AUTO.
  - §14: standing orders added as a next step.
- `docs/ASSUMPTIONS.md`
  - Intro bullet on "being added today".
  - Rows changed:
    - Cut-offs: every request, dated or not.
    - Unknown ids: today these read `NOT_DELIVERABLE` in Valio's name; `NOT_IN_RECORDING` is being added (FIX-12a).
    - Substitutes/dietary claims: the F-08 sentence still says "nutritional"; the rice drink `473424` is still the ward's substitute for `473609`.
    - Policy roles: P-04 never fires for the ward.
    - Audit: two clocks.
    - Interface limits, rewritten:
      - each browser or address: 20/20/5 a minute;
      - each address in total: 60/60/15;
      - the whole app: 120/120/30;
      - 30 new books per address per 10 min;
      - live looks: 6 overall, 2 per address;
      - environment tokens: 60 each;
      - `TTA_TRUSTED_PROXY_HOPS`;
      - 5 lines per request.
    - Agent loop: rank 1 only, two offers, the order is kept after a fault.
    - Agent outage: tried at most twice, about 60 s, then remembered for 120 s.
    - Demo run log: 50 runs per browser book.
    - Demo buttons: the fourth one is being added (T18).
  - New rows:
    - the per-browser order book (FIX-10);
    - the text check of every reading (FIX-9);
    - the reading labels and headers (FIX-9, FIX-10);
    - Context.dev evidence (S2, wired, not deployed).
  - New section "Being added today":
    - the ingredient list and not-in-recording (FIX-12a);
    - Aiven (S1, committed, not deployed);
    - Gemini photo and Finnish input (T18);
    - "My kitchen" (FEAT-1);
    - offers and approvals (FIX-12b).
  - Other sections:
    - Technical choices: the SQLite row now mentions Aiven.
    - Out of scope: the "stretch tasks not built" line is replaced by standing orders.
    - Next steps: item 4 updated; new 11 (standing orders with a drift rule) and 12 (a fresh offer at approval).
  - No HTML comments; renders with `tta.ui.markdown` (2 tables, 92 rows).
- `docs/AWARDS.md`
  - New intro: which awards are entered is the team's decision.
  - Gemini:
    - the text check and the reading labels (FIX-9);
    - rank 1 only and two offers per run;
    - outage memory;
    - photo and Finnish input as being added `[T18]`;
    - 294 agent tests;
    - honest note now says about 60 s.
  - Modal: the secret now carries the database URL and the Context.dev key from `cf6681f` `[S1]`; per-address vs per-browser limits.
  - New Context.dev section:
    - the Answers endpoint and why;
    - what is sent and checked;
    - the dietitian's approval card and what else it drives;
    - the demo moment `469512` `[T18 for the button]`;
    - honest notes: it never changes a verdict, the 40 s synchronous lookup, the brand check, 17 of 60 requests.
  - New Aiven section, "being added" `<!-- check: S1 -->`: what it enables, tests 110 passed and 1 xfailed, latency, admin-login and TLS notes.
- `docs/ARCHITECTURE.md`
  - Diagram: the store line and a new `evidence/` line.
  - Paragraph on the two kinds of order book.
  - Approval step: the evidence.
  - Packages:
    - `store/` adds PostgreSQL `[S1]`;
    - new `evidence/` row;
    - `orders/` uses `EvidenceFinder`;
    - `api/` gets the limits and the sandbox;
    - `agent/` gets the text check and labels, plus Finnish and photo `[T18]`;
    - `ui/` gets the evidence card and `/kitchen` `[FEAT-1]`.
  - `Store` port: `PostgresStore`.
  - Two-clocks bullet.
  - Known limits: the PostgreSQL owner login; page books are in memory.
- `docs/STANDARDS.md`
  - OpenAPI: `/docs` and `/redoc` use pinned versions with SRI and the CSP (FIX-10), replacing "FastAPI's default CDN".
  - MCP: GET and DELETE answer 405.
  - GS1: only the declaration is read today `[FIX-12a]`.
  - Next steps:
    - item 4: PostgreSQL committed `[S1]`;
    - item 10: about 60 s (FIX-9);
    - new item 11: standing orders.
- `docs/PITCH.md`
  - Optional beats: the evidence card (built), photo/Finnish `[T18]`, "My kitchen" `[FEAT-1]`.
  - Three new Q&A lines (an allergen with no data, standing orders and recipes, 1,500 L "on an empty book").
  - Description sentences on the evidence and the text check.
  - The awards line `[S1]`.
  - Technologies: Context.dev, Aiven.
- `README.md`
  - Live link at the top: deploy commit `237b37f`, per-browser book, Start again.
  - "Two kinds of order book" `[S1]`.
  - The `/` row of "What is served".
  - New section "Five ways to see it": pages, REST, MCP, the buyer agent, the audit views, each with its call.
  - Read-more rows: DEMO/DEPLOY, CONTEXTDEV/AIVEN, WALKTHROUGH, USE-CASES.
  - "What is not done": standing orders; S2 and S1 committed but not deployed `[S1]`; being added `[FIX-12a, FIX-12b, T18, FEAT-1]`.
- `src/tta/api/docs.py`
  - The limits paragraph (text only), following the item-4 spec: per browser on the pages; per address for REST, MCP and cookie-less page requests; 20/20/5 per visitor; 60/60/15 per address; 30 new books per address per 10 minutes; overall 120/120/30; the refusal names the window that was full; live looks 2 per address.
  - Its numbers come from the code's constants. To get them, I added imports of `MAX_*_PER_ADDRESS_PER_MINUTE` from `tta.api.limits` and `MAX_NEW_BOOKS_PER_ADDRESS` and `NEW_BOOKS_WINDOW_MINUTES` from `tta.api.sandbox`. These imports are the only change that is not text.

## Marks left (`<!-- check: … -->`)
- **S1:** SPEC:31; ARCHITECTURE:73; STANDARDS:136; AWARDS:58 and AWARDS:94 (the Aiven section); PITCH:90; README:38 and README:131.
- **T18:** SPEC:84, SPEC:292, SPEC:299; ARCHITECTURE:78; AWARDS:28, AWARDS:81; PITCH:38.
- **FIX-12a:** SPEC:167, SPEC:193; STANDARDS:104.
- **FIX-12b:** SPEC:175.
- **FEAT-1:** SPEC:303; ARCHITECTURE:79; PITCH:39.
- **All four running tasks:** README:132 `<!-- check: FIX-12a, FIX-12b, T18, FEAT-1 -->`.
- **`docs/ASSUMPTIONS.md` carries no marks** (the renderer would show them). Its lines that depend on running tasks say "being added today" in the text:
  - the "Unknown ids" row (FIX-12a);
  - the "Demo" buttons row (T18);
  - the "Being added today" section (all of them);
  - the SQLite technical choice and next step 4 (S1).

## Tests
```
.venv/bin/python -m pytest tests/ui/test_markdown.py tests/deploy/test_modal_app.py tests/api/test_openapi_and_schemas.py tests/api/test_docs_pages.py -q -p no:cacheprovider
53 passed in 3.04s
.venv/bin/ruff check src/tta/api/docs.py
All checks passed!
```
`docs/ASSUMPTIONS.md` rendered with `tta.ui.markdown.render`: 2 tables, 92 rows, every row 5 or 2 cells, no comment text.

## Assumptions
- S1 and the S2 wiring are described as committed, not "being built", because they landed (`67f3b00`, `f3286e1`, `cf6681f`) while this task ran.
- "Per address for REST and MCP" is described as it is coded: REST, MCP and page requests without the cookie get the 20/20/5 visitor window keyed by address, and every demo call also counts in that address's 60/60/15 cap.
- The approval-time re-check (409, the order keeps waiting, no fresh offer) is taken from `AIMO/USE-CASES.md` (re-checked there in code) and ASSUMPTIONS T08-1. I did not trace it again.
- AWARDS and PITCH say award entry is the team's decision: `CLAUDE.md` says Aiven was dropped on 14 Nov, while STATUS says the human chose to build it on Saturday.

## Contract changes needed
None.

## Not done (outside my paths; for the orchestrator)
Code text that still disagrees with what the code does:
- `src/tta/api/examples.py:49`: "Checked against the standing order."
- `src/tta/policy/rules.yaml:246,254,256,422` (F-08 and the authority text): "nutritional claim" should be "dietary claim" (the 8 codes). FIX-12b owns only P-03 there.
- `src/tta/audit/sentences.py:263`: "A fresh offer is needed." on an approval-time refusal, where none is built.
- `src/tta/offers/candidates.py` (FIX-12a's file): the ward's `ALLERGEN_NOT_STATED` sentence says "a dietitian must decide", but no dietitian is asked under confirmed-only.

Documents I do not own that are stale:
- `docs/DEPLOY.md:128-135`: the FIX-8 rule ("private peer → `X-Forwarded-For`"). It should now describe `TTA_TRUSTED_PROXY_HOPS` (default 0) and the per-browser and per-address limits.
- `docs/DEMO.md`:
  - lines 31, 33 and 134: limits per address (FIX-11 hand-back);
  - "Extra moments": 1,500 L gives [P-01, P-03] only on an empty book.
- `AIMO/WALKTHROUGH.md`:
  - §4: P-04 for the ward;
  - Step 1: the S1 run is hand-built;
  - §12: still says Context.dev is "not yet connected" and Aiven "in progress".
- The order page has no line explaining the two clocks.

## Questions written
0
