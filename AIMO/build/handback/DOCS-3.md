# DOCS-3 — done

`docs/ASSUMPTIONS.md` was finished first, at 11:10 local time (the coordinator's three added items included). It holds no `<!-- -->` mark: `/assumptions` escapes every character, so a mark there would show on the page as text.

## Built
- `docs/ASSUMPTIONS.md`: 31 product types, cream; the "Being added today" section became "Added on 14 Nov", with commits; new rows for the ingredient list and for price (`catalogPrice`, `netPriceFound`); variable-weight ceiling marked as ours (Q9); Unknown ids, Demo, Agent recordings (11), SQLite/PostgreSQL choice and next step 4 now describe what is committed.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/AWARDS.md`, `docs/PITCH.md`, `docs/STANDARDS.md`, `AIMO/SPEC.md`: 26 marks settled (see per document below).
- `docs/DEPLOY.md`: a table of the rate limits, how visitors and addresses are told apart, `TTA_TRUSTED_PROXY_HOPS`; stale "private or loopback" fallback removed.
- `docs/DEMO.md`: the limits, the renamed summary-strip headings (d447ac3), the 7 recorded requests, the brief and the hand-built recordings, and two Q&A moments (ingredient list, cream).
- `AIMO/build/handback/DOCS-3.md`.

## Tests
`COVERAGE_FILE=<scratchpad>/.cov .venv/bin/python -m pytest tests/ui/test_pages.py tests/ui/test_edges.py -q -p no:cacheprovider`
```
...........................                                              [100%]
27 passed in 4.20s
```
I also checked the table column counts of every edited document with a script: they all match. Recording counts come from `RecordedModel(Path('fixtures/agent'))`: 7 parses, 3 runs, 1 photo.

## Per document
**docs/ASSUMPTIONS.md** (it had no marks; the stale lines were fixed)
- Product types: "30 types" became "31" (31 top-level keys in `src/tta/catalog/product_types.yaml`, counted with `yaml.safe_load`). Added: `cream` is 44 of the 53 products of 10401, and the 9 blends are `vegetable_cream` (from the yaml).
- Unknown ids: now `NOT_IN_RECORDING`, with its sentence, price, quantity and date `UNKNOWN`, and product-file reasons kept (`contracts/common.py:143`, FIX-12a hand-back).
- New row, Allergens: the ingredient list counts as a statement when the declaration is FREE_FROM, UNDECLARED or none, and gives MAY_CONTAIN, which sends the product to a dietitian (`allergens/exclusion.py:66,209`). Figures 18 and 7 are for the whole catalog of 17,546 products, 13,989 of them with a list (FIX-12a hand-back). The DECLARED_ONLY sentence of the strictness row points to it.
- New row, Price (coordinator item 1): every price, the price claim and every total use `catalogPrice` (`offers/candidates.py`, `availability/claims.py:73`, `offers/lines.py`). `netPriceFound` is parsed and used nowhere else.
- Variable weight (coordinator item 2): the ceiling sentence is ours, assumes the invoice is never above the weight ordered, Q9 open.
- Evidence row: "not yet on the deployed app" removed (the page ships with the redeploy).
- Demo row: four example buttons; the fourth is checked in `ui/examples.py:99`.
- Agent row: 11 recordings, 4 from Gemini and 7 hand-built, including the brief (`8cd94c2`) and T18's four.
- Technical choices (SQLite/PostgreSQL) and next step 4: "being added" became committed (`67f3b00`).
- "Added on 14 Nov" section: one bullet per task, each with its commit. The healthz reason is from `7b93821` (`routes.py`, `wiring.py:102`). Kitchen facts are checked in `api/sandbox.py:61-92` and `kitchen.html`. T18's not-done items are stated (Finnish free text on the pages needs Gemini live).

**README.md**
- l.38 (S1): PostgreSQL with `DATABASE_URL`, SQLite fallback, `/healthz` names the reason. Deploy wording removed.
- l.131 (S1): rewritten as the one deploy line, which lists every committed piece that reaches the app at the final redeploy. Kept `<!-- check: deploy -->`.
- l.132 (FIX-12a, FIX-12b, T18, FEAT-1): removed from "What is not done". l.127 now carries T18's real not-done items: not checked live, stand-in photo, Finnish needs Gemini on the pages, no MCP photo tool (T18 hand-back).
- Unmarked but stale, fixed: l.36 (11 recordings, 7 hand-built, brief sentence) and l.114 ("Aiven being added").
- l.5 (`237b37f`): `<!-- check: deploy -->` added, as the coordinator asked.

**docs/ARCHITECTURE.md**
- l.73 (S1): `67f3b00`, plus the `/healthz` reason from `7b93821`. "Not yet deployed" removed.
- l.78 (T18): photo in two visible steps, Finnish or Swedish (`agent/prompts.py:28,54`), `812de0f`.
- l.79 (FEAT-1): `/kitchen` "Your kitchen" in the menu (`base.html:16`), plus the approval card's per-line findings (FIX-12b).

**docs/AWARDS.md**
- l.28 (T18): what was built, plus a "Not checked live" bullet: 503/504, hand-built recordings, stand-in photo.
- l.81 (T18): the fourth button by its label.
- l.94–95 (S1): "Status: committed", `/healthz` reason since `7b93821`. The deploy sentence is kept with `<!-- check: deploy -->`.
- l.58 (S1): about the deploy secret, so the mark is now `<!-- check: deploy -->`.
- Unmarked, fixed: l.3 ("being added today"), l.22 ("30" became "31" product-type keys), l.102 (S1's expected failure fixed since `7b93821`).

**docs/PITCH.md**
- l.38 (T18): "being added" removed; it says the demo answers from hand-built recordings.
- l.39 (FEAT-1): "Your kitchen", `/kitchen`, as "My kitchen agent". The €3,000/€750 claim is checked in `tests/ui/test_kitchen_page.py:159`.
- l.90 (S1): about the deployed app, so the mark is now `<!-- check: deploy -->`.

**docs/STANDARDS.md**
- l.104 (FIX-12a): the limit is fixed. It now says how the list is read, that 465793 goes to the dietitian, and that Finnish compounds are missed.
- l.136 (S1): already says it reaches the app at the final redeploy, so the mark is now `<!-- check: deploy -->`.

**AIMO/SPEC.md**
- l.31 (S1): `/healthz` names the fallback; "not yet on the deployed app" removed.
- l.84 (T18): committed, `812de0f`.
- l.167 (FIX-12a): `NOT_IN_RECORDING` committed, with UNKNOWN claims.
- l.175 (FIX-12b): the limit is fixed. The route now judges by the buyer's rule, confirmed-only included (`offers/substitutes.py:116-122`).
- l.193 (FIX-12a): the ingredient rule is committed, and the condition is corrected to FREE_FROM, UNDECLARED or none, any case, family members, under either strictness. The old text said FREE_FROM only and "in capitals".
- l.292 and l.299 (T18), l.303 (FEAT-1): committed. Each says what it does now.

**docs/DEPLOY.md**: every number checked in code.
- Limits (`api/limits.py:60-76`):
  - 20/20/5 per browser, or per address without the cookie
  - 60/60/15 per address
  - 120/120/30 for the whole app
  - live looks 6 for the whole app and 2 per address (`api/fallback.py:51-52, 175`, keyed by `current_client_key`)
  - 30 new books per address per 10 minutes (`api/sandbox.py:49-52`)
  - 60 a minute per environment token (`RateLimit()` default)
- Addresses: IPv6 counts by its /64.
- `TTA_TRUSTED_PROXY_HOPS`: default 0, at most 10 (`config.py:23,56`). With N, the N-th entry from the right (`limits.py:267-278`). `deploy/modal_app.py` does not set it.
- What I corrected:
  - The section said X-Forwarded-For is used when the peer is private or loopback. That is not in the code.
  - The NAT bullet said "60 calls a minute per demo identity".
  - "One order book for every visitor": the pages have had per-browser books since FIX-10.
  - "three values" in the secret: now five (`modal_app.py:115`).
  - The Gemini line said 30 a minute only.
- Two lines have `<!-- check: deploy -->`: the header is never read on the deployed app, and the secret's five values.

**docs/DEMO.md**: the limits as in DEPLOY ("2 from one visitor" became "2 from one address"). Headings renamed: **Every claim confirmed** and **A claim not confirmed** (d447ac3), 3 places each. "3 recorded demonstration requests" became 7 (`recorded.py:243`, 7 parses loaded). The brief and T18's hand-built recordings are added. "Your kitchen" matches the page: menu label, "Save my kitchen", "Spend limit per order", "Always, whatever you set". New Q&A bullets for `465793` and for `cream` → `463797`, from the FIX-12a hand-back; both products are in the capture's `ids.json`.

## Marks left
Only `<!-- check: deploy -->`, 8 in all:
- `README.md` l.5 and l.131
- `docs/AWARDS.md` l.59 and l.95
- `docs/PITCH.md` l.90
- `docs/STANDARDS.md` l.136
- `docs/DEPLOY.md` l.138 and l.166

There are none in `docs/ASSUMPTIONS.md`, `docs/ARCHITECTURE.md` or `AIMO/SPEC.md`.

## Assumptions
- `docs/ASSUMPTIONS.md` ships with the redeployed code, so lines saying "not yet on the deployed app" were removed there instead of marked.
- The prompt's product-type keys are the whole table (31), because `parser.py:269` passes `self._keys`. I did not trace where `self._keys` is built.
- 465793 and the `cream` → `463797` €33.10 AUTO outcome are taken from the FIX-12a hand-back. I did not re-run them.

## Contract changes needed
None.

## Not done
- **Coordinator item 1's premise is wrong.** `netPriceFound` is not false on all 769 lines of `2026-11-14-demo`: it is **true on 50 and false on 719**. I counted the `price-*.json` bodies; for example `462718` and `462970` are true. The response has no separate net-price field. I wrote the figures as counted, labelled as the capture. Nothing in the code reads the flag, so "no customer net price is used" holds either way.
- Not verified, left as is: AWARDS "It is looked up only when P-04 fired and an excluded allergen is not stated or undeclared; a 'may contain' … gets none". It is unclear whether an ingredient-list finding (MAY_CONTAIN) gets evidence.
- For the team: CLAUDE.md says Aiven was dropped as a tech award on 14 Nov, while PITCH l.90 and AWARDS still list it as a team decision once deployed. I left both as they are.

## Questions written
0
