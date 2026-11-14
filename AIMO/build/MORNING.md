# Morning note — what the overnight build left you

Written by the orchestrator at the end of the run (Saturday 14 Nov, late morning). Branch `overnight-build`, local only: nothing was pushed. To share it: `git push -u origin overnight-build`.

## 1. What works, and the command that proves it

| What | Proof (run from the repository folder) |
|---|---|
| The whole suite | `.venv/bin/python -m pytest -q` → **3,009 passed, 63 skipped** at `71f13f4` (11:15). One test can fail on a loaded machine: `tests/catalog/test_loader.py::test_loads_all_products_in_under_three_seconds` (a 3-second limit); it passed when run alone. |
| The brief's flow, request → lookup → order/approval, over HTTP in replay | `.venv/bin/python -m pytest tests/e2e -q`: scenarios 1 (milk), 2 (allergy ward) and 3 (substitutes), the backup beef case, the guards, and the demo script in order, from the pasted sentence to the audit trail |
| 1,000 L of lactose-free milk by Monday (hotel kitchen) | Start the app (section 2), press example 1 on `/`. Option 1: three products with confirmed stock (384 + 51 + 565 L), €2,580.64, waits for the purchasing manager (P-01, over the €750 limit). Option 2: Valio Eila 1,000 L, €1,010, stock not confirmed, so it always needs a human (F-01 + P-01). Checked at 11:05 on `71f13f4`. |
| The agent orders alone when it is within its authority | `/kitchen` → per-order limit 3,000 → save → run example 1 as "My kitchen agent": `ORDERED`, `AUTO`. Set it back to 750: `PENDING_APPROVAL` by P-01 (and P-02, the €3,000 day). |
| Allergens: declaration and ingredient list both read | `curl -s -X POST http://127.0.0.1:8001/v1/offers -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Content-Type: application/json" -d '{"needed_by":"2026-11-16","lines":[{"text":"20 litres of almond drink 465793 by Monday; no nuts","product_ids":["465793"],"quantity":20,"unit":"L","exclude_allergens":["AN"],"allergen_strictness":"STRICT"}]}'` → one option, **P-04**, to the dietitian (the drink declares tree nuts free from; its ingredients name almond). |
| Audit trail anyone can check | `/orders/{id}` on the pages: the trail for the buyer and for Valio Aimo, each event hashed into a chain (CloudEvents 1.0, SHA-256). `GET /v1/audit` returns the trail with the state of the hash chain. |
| Open interface | `/v1/openapi.json` (OpenAPI 3.1, generated), RFC 9457 problems, MCP at `/mcp/`. |
| Public demo | https://joaocostared--trusted-trade-agents.us-east.modal.run, redeployed from `d342dfb` at 11:15 with the approved command and the five named values only. `.venv/bin/python deploy/check.py https://joaocostared--trusted-trade-agents.us-east.modal.run` → **7 of 7 passed** (health, page, live offer, order by the agent, audit chain intact, MCP 401 without a token, 8 MCP tools). `/healthz`: mode live, no fall-back reasons, so Aiven PostgreSQL holds the shared book. On it: `/kitchen` 200 and in the menu; the almond drink → P-04. |

## 1b. Added Saturday afternoon (deployed from `8163d5d` at 13:00, `deploy/check.py` 7 of 7)

| What | See it | Figures (replay, capture of Sat 02:52) |
|---|---|---|
| Recipe logic, fixed rule F-09: an ingredient replaced by recipe logic always goes to a human | `/menu?example=event` | beef stew + berry quark dessert, 120 servings each: yoghurt stands in for quark; €476.48, F-09 + P-06 |
| Standing orders, rule P-08: a renewal that drifts from its history goes to a human | `/standing-orders` → load the demo one | 6 synthetic weeks around 100 L; 100 L → ordered alone, €248.00; 290 L → purchasing manager |
| Delivery and sustainability comparison: reliability, carbon, labels; "prefer" in the request | `/`, example 5 | oat drink, most reliable: `470863` €140.00 over the cheapest `472145` €133.00 |
| Rule-based reader when no model answers (also on a 401/402/403 from Gemini) | any free text with no key | "300 litres of oat drink by Monday" → read and ordered by the rules, €420.00 |

Open: a preference can make the agent order a dearer product alone under the €750 limit (10 L cream "most reliable" €73.70 against €33.10); a profile rule for it waits on the team's decision. No MCP tools for the new parts. Booth copy with all of it: http://127.0.0.1:8002.

## 2. How to run it

```
GEMINI_API_KEY= TTA_ENV=demo TTA_MODE=replay .venv/bin/python -m uvicorn --factory tta.api:create_app --port 8000
```
Replay answers from the capture of Saturday 02:52 (769 products) with the clock pinned, and needs no key. Live mode is `TTA_MODE=live` with the Valio key in `.env`; every offer says `live` or `replay`. Script for the 90-second demo: `docs/DEMO.md`.

Two local copies are running now, both replay with no keys: port **8000** is `e7e1cb2` (before FIX-11, FIX-12 and FEAT-1; the almond drink still passes there), port **8001** is `284fee8` (current code, restarted at 11:32). Use 8001 for the booth.

## 3. What is blocked, and the command that unblocks it

| Blocked | Why | Command, once the service works |
|---|---|---|
| Gemini live check of Finnish, Swedish and the photo (T18) | Gemini answered 503/504 to all 6 requests during T18 (before 10:39). The recordings for these are hand-built and say so. | `.venv/bin/python -m tta.agent.record --only finnish-1 --only finnish-2 --only photo --max-calls 10 --timeout 60` |
| Per-visitor limits seen from two networks (FIX-8) | Needs two phones on the deployed app; what peer address Modal passes on was not observed. | Two phones on different networks, three offers each with `demo-agent-allergy-ward`: each should get its own window, not share one. |
| "My kitchen agent" without a working model | The recorded readings are for `hotel-kitchen` and `allergy-ward`; a run as My kitchen agent first says "This sentence was recorded for another buyer profile", then uses the example's typed request. Verdicts are the same. | A recording of example 1 for `my-kitchen` (`tta.agent.record`), when Gemini answers. |

## 4. What you must decide

- **Tech awards.** Built and wired: Gemini (parser, photo, Finnish), Modal (hosting), Context.dev (evidence on the dietitian's card), Aiven PostgreSQL (append-only audit guarded by triggers, buyer and supplier views). `CLAUDE.md` says Aiven was dropped on 14 Nov; the code for it now exists. Whether to enter it is your call. Write-ups: `docs/AWARDS.md`.
- **The 14 decisions in `AIMO/BOOTH-NOW.md` part B**: confirm or correct them with Valio. The ones that change behaviour most: which claims gate an order without a human (T04-1), `closingTime` read literally (Q1), unconfirmed stock always to a human, the ingredient list as a statement (ALMOND-1).
- **A substitute for a product the buyer named by id.** Under `hotel-kitchen` (substitution scope `SAME_CATEGORY`) the agent buys `475224` alone instead of the named `473609`, at +27%; the constraint check says `PRODUCT_ID NOT_MET` and the verdict is `AUTO`. That is the profile's setting working as written. Is it what a buyer wants, or should a named id always go to a human? One line in `rules.yaml` either way.
- **Mixing products in one option.** Option 1 of scenario 1 combines semi-skimmed, fat-free and café milk to reach 1,000 L. Allowed today; a "mixes N products" check or a preference for fewer products is a next step.
- **A whole-catalog capture for replay** (T17 point 1): about 36 Valio calls. 10 of 150 are used here and the deployed app may use up to 120, so it fits only if the deployed budget drops to about 100. It changes every replay figure in the docs and the booth sheet, so not before the submission unless you want it.
- **Partner data in a public repository.** Valio's four data files are tracked; the README says they are not under MIT. Ask Valio (question 22) before making the repository public.

## 5. Questions

`AIMO/BOOTH-NOW.md` is the booth sheet: 25 questions with what to show, then the decisions to confirm. Each has its full write-up in `AIMO/BOOTH-QUESTIONS.md`. If you have two minutes: SCOPE-1 · T03-1 · Q1 · Q7 · Q4. Since the booth copy: ALMOND-1 now covers the whole catalog (18 products for milk/gluten, 7 for tree nuts, where the declaration says free from and the ingredient list names the allergen or says "may contain").

## 6. Who reviews what

- **Sofia:** the allergen and ingredient rules (`src/tta/allergens/`, `AIMO/BOOTH-QUESTIONS.md` T03-1, T03-2, T03-3, ALMOND-1) and the product types built on your litres logic (`src/tta/catalog/product_types.yaml`). Clinical sense check: is "goes to a dietitian" the right outcome in each case?
- **Gabriela:** the policy (`src/tta/policy/rules.yaml`, the two profiles, built on your structure) and the "Your kitchen" page (`/kitchen`): does each setting read the way a buyer would set it?
- **João:** the deployment (`docs/DEPLOY.md`, `deploy/check.py`), the API and MCP surfaces, and the submission documents (`README.md`, `docs/PITCH.md`, `docs/AWARDS.md`).
- **Everyone:** `AIMO/WALKTHROUGH.md` explains the whole thing in order, from the request to the audit trail, with the questions at the end.

## 7. Numbers

- **Valio mock calls:** 10 of 150 from this machine (T00 2, T01 2, T13 6). The deployed app has its own budget of 120 and falls back to the recording below 10; each `deploy/check.py` run spends a few of them. On the deployed app one network address gets 2 live looks a minute; after that the recording answers, labelled `replay`.
- **Gemini:** 24 requests in all, plus the T18 attempts that failed.
- **Context.dev:** 17 of 60 requests; five products recorded.
- **Catalog figures** are from the whole product file (17,546 products) unless a line says "tonight's capture" (769 products).

## 8. Independent final check (T17)

An independent agent ran the app in replay on a clean copy of `e880ad2` (10:47, before FIX-12a, FIX-12b and FEAT-1), with no outside calls, over REST, MCP and the pages. Suite on that copy: 2,820 passed, 63 skipped. Full report in the session; its answers are in `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/t17/`.

**Passed:** scenarios 1, 2, 3, the backup beef case and both guards (agent on the decision route → 403 and logged; the same Idempotency-Key twice → the same order). Two approver roles on one order works. MCP `get_offer` → `place_order` works; no token → 401. OpenAPI 3.1 (16 paths), JSON Schema (60 models), 8 MCP tools.

**Its ten weakest points, and where each stands now:**

| # | Point (score at risk) | Now |
|---|---|---|
| 1 | Replay calls a product outside the capture "not deliverable", in Valio's name (30%, 20%) | **Fixed** (`9a1893d`): "Not in the recorded copy". Checked: 20 kg flour → 82 × `NOT_IN_RECORDING`. A capture of the whole catalog would make replay answer for every product; it costs about 36 Valio calls (decision below). |
| 2 | The brief's own sentence gets 503 without a model (30%) | **Fixed** (`8cd94c2`): hand-built recordings of that exact sentence, labelled so. Checked: parse 200, agent run → €2,580.64, P-01. |
| 3 | `465793` almond drink ordered alone under a no-tree-nut rule (20%, 15%) | **Fixed** (`9a1893d`): to the dietitian (P-04). |
| 4 | A date that cannot be met leaves no option (15%) | **Partly** (`baa4e08`): the answer names the earliest date ("Monday 16 Nov, for 11 products"); it still offers no late option for a human to approve. |
| 5 | Substitutes route ignores the buyer's rule; no substitutes on product-type lines (15%, 20%) | **First half fixed** (`baa4e08`). Product-type lines still get no substitute search. |
| 6 | No reader can recompute the audit chain: `/v1/audit` serves a flat view without `previous_hash` (20%, 15%) | **Open.** Next step: serve the stored CloudEvents envelopes with `previous_hash`. |
| 7 | Option 1 mixes three different milks; scenario 3 buys another brand alone over a product named by id (20%) | **Open, a decision** (below). |
| 8 | Statuses say more than the data: allergens `CONFIRMED` when nothing was excluded; catalog price, not a net price; "never higher" while Q9 is open (20%) | **Partly**: the two assumptions are being written into `docs/ASSUMPTIONS.md`; the summary strip now reads "Every claim confirmed" / "A claim not confirmed" (`d447ac3`). The `CONFIRMED`-when-nothing-checked status is unchanged. |
| 9 | Stale docs and "being added" marks (15%) | **Being fixed** (DOCS-3). |
| 10 | Reliability and carbon loaded but unused (optional direction) | **Open.** Shown on `GET /v1/products/{id}` only. |

T17 also notes: the problem-type URIs use the placeholder `tta.example`; there is no open order message (Peppol/UBL is a next step); "ORDERED" means recorded in our own book, which the pages say.
