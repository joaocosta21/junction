# Walkthrough — how the gateway works, why each piece is there, and how to check it

Written 14 Nov 2026, 09:30, by the orchestrator of the overnight build, for the team. It explains what was **built**, not what was planned. Every section says what a piece does, why it exists (the judging criterion or the review finding it answers), where it lives, and one way to check it yourself. Section 5 lists the decisions taken overnight without a human: read that one first if you only have ten minutes.

Parts still being changed when this was written (fix task FIX-10: a private sandbox per browser, rate limits per visitor and per kind) are marked **(FIX-10)**.

---

## 1. Which document says what

| Document | What it is | Is it current? |
|---|---|---|
| `AIMO/PLAN.md` | Friday's intent: the rubric mapping, the scenarios, the schedule | No. Written before any code; overnight decisions are not in it (T17 updates §5 and §8) |
| `AIMO/SPEC.md` | The contract the code follows: interface, states, rules | Mostly. Updated overnight where a decision changed it (§4 claims that gate, §5 exclusion codes, §7 rules F-05, F-07, F-08) |
| `docs/ARCHITECTURE.md` | Package map, ports, where each brief requirement lives | Yes |
| `docs/ASSUMPTIONS.md` (page `/assumptions`) | Every assumption, why, what would change it, where in the code | Yes (74 rows) |
| `docs/DEMO.md` | The demo click by click, a 90-second cut | Yes |
| `AIMO/build/` | How it was built: one task file per agent, every hand-back, the status log | Yes; `STATUS.md` is the log |
| `AIMO/BOOTH-QUESTIONS.md`, section "Raised during the overnight build" | Questions for Valio and for the team, each with what we built if nobody answers | Yes |
| **This file** | The why, and how to check | Yes, as of 09:30 |

---

## 2. The shape

```
  buyer's agent (REST · MCP)       demo visitor (pages)       Gemini (reads text, runs the loop)
            │                            │                              │
            └──────────────┬─────────────┴──────────────────────────────┘
                           ▼
                 Gateway service  (src/tta/api/service.py)
          who may call what · rate limits · stores · writes audit events
                           │
          ┌────────────────┼──────────────────────────┐
          ▼                ▼                          ▼
   offers (build,     orders (place, approve,     audit trail (CloudEvents,
   re-check)          expire, idempotency)         hash chain, two readers)
          │                │                          │
   catalog · availability · allergens · policy   store (SQLite, append-only audit)
          │
   valio client (live, budget, cache)  or  replay (recorded capture)
```

**Why it is cut this way.** Each box is a package with one job, and packages talk only through the **ports** in `src/tta/contracts/ports.py` (Python protocols) and the **contract models** in `src/tta/contracts/` (frozen Pydantic models, `Decimal` for money). Three reasons:
- Six agents built six packages at the same time last night. Each could test its package alone against fakes of its neighbours.
- A part can be swapped without touching the rest: live API or recorded capture, SQLite or PostgreSQL, Gemini or recorded answers.
- **No logic lives in a transport.** REST, MCP, the pages and the Gemini agent all call the same service functions, so a rule cannot hold on one surface and not another.

Check: `grep -n "class .*Protocol" src/tta/contracts/ports.py` lists the 13 ports.

---

## 3. One request, step by step

The running example is scenario 1: the hotel kitchen's agent sends **"1,000 litres of lactose-free milk by Monday"**. Numbers are from tonight's replay capture (`fixtures/valio/2026-11-14-demo/`, Saturday 14 Nov 02:52 server time, 769 products).

### Step 0 — Who is asking
- **What:** the bearer token maps to one identity: an **agent** bound to one buyer profile, an **approver** with roles for one buyer, or the **supplier** reader. The profile is never a request field.
- **Why:** 20% controls. An agent cannot choose its own authority, approve its own order, or read another buyer's data.
- **Where:** `src/tta/api/identity.py`, `src/tta/api/demo_tokens.yaml` (nine public demo tokens, loaded only when `TTA_ENV` is `dev` or `demo`). An unset `TTA_ENV` means `prod`: no demo tokens, and the app refuses to start without `TTA_TOKENS`. Tokens are kept as SHA-256 digests and compared in constant time.
- **Check:** `curl -s localhost:8000/v1/authority` → 401; with `-H "Authorization: Bearer demo-agent-hotel-kitchen"` → the profile and its plain-language summary.

### Step 1 — Reading the text (Gemini)
- **What:** Gemini (`gemini-3.6-flash`, through `generateContent` with a JSON schema) turns the sentence into a proposal. The parser then **checks the proposal against the text**:
  - the quantity must be a number that appears in the text;
  - the unit must match a unit word in the text;
  - the date must be one the text names;
  - every allergen the text excludes must be excluded;
  - product ids must be whole words of the text.

  A disagreement is refused with the field named. A missing quantity or allergen strictness is reported, never guessed. Result: milk, claim `FREE_FROM_LACTOSE`, 1,000 L, needed by Monday 16 Nov 2026.
- **Why:** 20% precise match, and the spec's rule that **the model never decides a price, a quantity, an allergen status or a verdict**. The cross-check came from the final review: before it, a model answer of 10,000 litres for "1,000 litres" would have passed.
- **Recordings:** `fixtures/agent/` holds Gemini's own answers for scenarios 1 and 2 and the "no quantity" sentence, recorded this morning. When Gemini does not answer, a known sentence is served from its recording, and the reading says so ("Gemini did not answer; read from a recording … made on 14 Nov 2026 at 07:13 UTC"). After one failure Gemini is not asked again for 120 s. A recording is served only to the buyer profile it was recorded for.
- **Where:** `src/tta/agent/parser.py`, `textcheck.py`, `days.py` (the calendar rule: "Monday" is the first Monday after today, Helsinki date), `schema.py`, `prompts.py`, `fallback.py`, `outage.py`.
- **Check:** `curl -s -X POST localhost:8000/v1/requests/parse -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Content-Type: application/json" -d '{"text":"Some milk for Monday"}'` → `invalid-request` naming the quantity.

### Step 2 — Candidates from the catalog
- **What:** the product type `milk` maps to category 10400. Name terms leave out sour milks, the coffee drink and the soy yoghurt, which gives 78 products. The claim `FREE_FROM_LACTOSE` narrows that to 30. For each product the step works out:
  - **pack size** in litres per sales unit, from the live price ratio first, then the product file's size, then the product name;
  - **portion packs** (100 × 2 cl), which are excluded from a bulk request;
  - **lot rounding**: a lot step of 0.01 means whole units.
- **Why:** 20% precise match. A buyer asking for 1,000 litres of milk wants neither 2 cl portions nor sour milk. A claim is never read as an allergen statement: lactose-free milk still contains milk.
- **Where:** `src/tta/catalog/` — `product_types.yaml` (30 types, each with how it was derived), `pack.py`, `sizes.py` (credits Sofia's litres logic from `bio1`), `lots.py`, `search.py`.
- **Check:** `POST /v1/products/search` with `{"product_type":"milk","required_claims":["FREE_FROM_LACTOSE"]}` → `total: 30`.

### Step 3 — One look at price and availability
- **What:** one price call and one availability call for the candidates, **both from the same source**: live, or the recorded capture. In live mode the gateway falls back to the capture when the mock fails or the call budget is low, and every offer says `source: live` or `replay`.
- **Why:** 30% working demo (it survives the mock being down) and 15% production path. "Same source" came from review round 3: an offer could mix a live price with replayed stock.
- **How the client behaves:**
  - it sends a named `User-Agent`, because Cloudflare refuses Python's default (FINDINGS §1);
  - it waits one second between calls and caches answers for 60 s;
  - the call budget is kept in a file under a lock;
  - the re-check before an order always skips the cache (`fresh=True`);
  - the server's `timeNow` is refused when it is more than 12 hours from this machine's clock.
- **Where:** `src/tta/valio/` (client, replay, budget, clock, recorder), `src/tta/api/fallback.py`, `src/tta/offers/deps.py`.
- **Check:** `GET /healthz` shows `mode` and `source`; `var/valio_call_budget.json` shows the live calls used (10 of 150 tonight).

### Step 4 — Six availability states
- **What:** each product is classified, in this order:
  1. `BLOCKED`
  2. `NOT_DELIVERABLE` (no schedule line)
  3. `OUT_OF_STOCK` (0)
  4. `CUTOFF_PASSED` (`closingTime` at or before now)
  5. `QUANTITY_NOT_CONFIRMED` (`availableAmount` ≥ 999,999, Terminal or Stock; that value never enters arithmetic)
  6. `CONFIRMED`
- **Why:** 15% exceptions, and Valio's own answer on 14 Nov that very large Stock values mean "not known". Tonight 17 of the 30 milks have a cut-off that has passed (Thursday 15:00, Terminal products).
- **Where:** `src/tta/availability/states.py`. Friday's 1,000-product sample classifies exactly as `FINDINGS.md` says: 1 / 203 / 29 / 423 / 92 / 252.

### Step 5 — What can be trusted: a status per claim
- **What:** every line of an offer states five claims — `price`, `quantity`, `delivery_date`, `allergens`, `origin` — each `CONFIRMED`, `UNKNOWN` or `RULED_OUT`, with a sentence.
- **Which claims hold an order back:**
  - price and quantity always;
  - the delivery date only when the request gives a date;
  - allergens through the allergen rule;
  - origin never.
- **Why:** this is our answer to the brief's "trust protocol". The gating rule was decided overnight (question T04-1). Without it, any request with no date, or any product with no stated origin, could never be ordered alone.
- **Where:** `src/tta/availability/claims.py`; SPEC §4, paragraph "Which claims gate".

### Step 6 — Allergens
- **What:** the buyer's exclusions (profile plus request) are checked against the product's statements, by the table in SPEC §6:
  - `FREE_FROM` passes;
  - `CONTAINS` is rejected;
  - `MAY_CONTAIN` goes to a dietitian;
  - no statement goes to a dietitian under `STRICT`, and passes as unverified under `DECLARED_ONLY`.

  Families are read in both directions (wheat is under `AW`). Least safe wins. Oats go to a dietitian under a no-gluten exclusion. `X99` is a general statement, never one about a single allergen.

  A second rule covers substitutes: a substitute must not add an allergen the original does not declare, nor raise one from "may contain" to "contains".
- **Why:** 20% controls (what reaches a dietitian) and 15% substitutions. 46.2% of the catalog has no allergen statement, so "no data" must mean unknown, never safe.
- **Where:** `src/tta/allergens/` (`exclusion.py` holds the table as a literal dictionary; `substitution.py`; `codes.py` lists 45 codes with their families).
- **Check:** in scenario 2, all 18 products of the search that declare milk or gluten are excluded as `ALLERGEN_DECLARED`.

### Step 7 — The offer: options, exclusions, constraint checks
- **What:** at most three options:
  - `BEST_CONFIRMED`: confirmed stock only; the cheapest single product that covers the quantity, else the cheapest first until it is covered, else a partial fill that says what is missing;
  - `ALTERNATIVE_UNCONFIRMED`: the cheapest product whose quantity Valio does not confirm, as a full option a human can choose;
  - `SUBSTITUTE`: only when products named by id cannot be supplied.

  Every excluded product is listed with a reason code and a sentence. Every thing the buyer asked for gets a constraint check (`MET`, `NOT_MET`, `UNVERIFIED`). `valid_until` is the earliest price validity and cut-off of an option's lines.
- **Tonight:**
  - option 1 is 384 × `469363` + 51 × `462775` + 565 × `463380` = **€2,580.64**, full fill;
  - option 2 is 1,000 × `464306` = **€1,010.00**, quantity not confirmed;
  - 19 products are excluded (17 cut-off passed, the portion pack `463203`, one not deliverable), and 7 that fit but are not needed are named in a note.
- **Why:** 20% precise match, 15% partial availability and substitutions, and the brief's "good-better-best" ranking. Friday's plan expected a 749-litre partial fill; tonight's stock covers 1,000 litres. The partial-fill story comes back at **1,500 litres** (75.5% covered, rules P-01 and P-03, €2,933.09); it is tested.
- **Where:** `src/tta/offers/` (`builder.py`, `candidates.py`, `combining.py`, `planning.py`, `checks.py`, `substitutes.py`, `revalidation.py`).

### Step 8 — The policy verdict on each option
- **What:** the rules of section 4 run on each option. Every rule that fires is listed with its sentence and the facts it read. The most severe verdict wins: `AUTO` < `APPROVAL` < `BLOCK`. A fact a rule needs and cannot find fires F-03, so it never passes. Each decision carries the SHA-256 hash of the rules plus the profile in force.
- **Tonight:**
  - option 1 → `APPROVAL` by P-01 (€2,580.64 is above the hotel's €750 per order), to the purchasing manager;
  - option 2 → `APPROVAL` by F-01 (quantity not confirmed) and P-01.
- **Why:** 20% autonomy and controls: what the agent may decide alone and what needs a named human, decided by data a person can read, never by a model.
- **Where:** `src/tta/policy/rules.yaml` (the rules as data; the structure is Gabriela's from `bio2`), `profiles/*.yaml`, `engine.py`, `facts.py`, `validation.py`. The verdict and role of every fixed rule are pinned in code, so a rules file that weakens one is refused at start.
- **Check:** `GET /v1/authority` lists every rule with the profile's own values.

### Step 9 — The order
- **What:** `POST /v1/orders` with an `Idempotency-Key` runs these steps:
  1. a **fresh** re-check of price and availability, compared field by field with the offer (price, validity, state, cut-off, stock, delivery date, sales unit, tax rate);
  2. the policy again, at order time, with the day's spend;
  3. one outcome:
     - a change or expiry → `offer-stale` or `offer-expired`, with a fresh offer;
     - `BLOCK` → `policy-blocked`;
     - `AUTO` → `ORDERED` by the agent;
     - `APPROVAL` → `PENDING_APPROVAL`, with the roles named.

  Rules that hold around it:
  - the same key returns the first order;
  - an offer has at most one live order;
  - the order, its approval, its key and its audit event are written in **one transaction**, or not at all.
- **Why:** 30% (the order half of the flow), 20% controls, and the brief's "fixed prices, not a negotiated quote". The transaction and one-order-per-offer rules came from review round 2: a crash between two writes left an order nobody could decide, and two keys could buy the same option twice.
- **What "ordered" means:** recorded in our order book. The mock has no order endpoint, and the record says it commits nobody.
- **Where:** `src/tta/orders/` (`service.py`, `checking.py`, `outcomes.py`, `spend.py`, `access.py`), `src/tta/store/sqlite_store.py` (`atomic()`).

### Step 10 — Approval
- **What:** an approver of the same buyer decides an approval. They must hold a role the approval still needs and be listed under that role in the buyer's profile. Every approval re-checks and re-runs the policy before `ORDERED`. An approver may choose another option of the same offer; the policy runs again, and `BLOCK` still blocks. An agent on the decision route is refused (rule F-06), and the attempt is recorded. A pending order expires at its "order by" time, or 24 hours after creation when it has none.
- **Tonight:** Demo approver Hanna (purchasing manager) approves → `ORDERED`, recorded as placed with human approval.
- **Why:** 20% controls ("what must go to a human for sign-off").
- **Check:** `POST /v1/approvals/{id}/decision` with an agent token → 403 `not-authorised`.

### Step 11 — The audit trail
- **What:** one event per step: request received, parsed, lookup, offer created, policy evaluated, approval requested, approval decided, confirmed, and the other outcomes.
  - **Envelope:** each event is a **CloudEvents 1.0** envelope holding the actor, the rule ids and facts, the policy hash, and the previous event's hash. Every event is chained to the one before by SHA-256.
  - **Two sentences per event**, built from templates and never by a model: one for the buyer, and one for Valio. Valio's sentence shows no limit value, allergen exclusion, approver name or note, and none of the buyer's own words.
  - **In the database**, triggers refuse any update or delete of an event, and two events cannot claim the same previous hash.
- **Why:** 20% "how decisions are logged and auditable"; the brief asks for a human-readable log "for both buyer and Valio Aimo"; and 15% open standards.
- **Limit, stated as such:** the chain shows a changed, removed or inserted event. It does not show the end of the trail cut off, unless someone holds the head hash that `/healthz` publishes.
- **Where:** `src/tta/audit/` (`trail.py`, `chain.py`, `sentences.py`, `supplier_sentences.py`, `readers.py`), `src/tta/store/schema.py`.
- **Check:** `GET /v1/audit?order_id=<id>&reader=buyer`, then `&reader=supplier` → the same events, the supplier's redacted; `chain.ok: true`.

### Step 12 — The surfaces
- **REST** under `/v1`. The OpenAPI 3.1 document at `/openapi.json` is generated, with its examples produced by running the scenarios. Errors are RFC 9457 problem documents, and none repeats text the caller sent.
- **MCP** at `/mcp`: eight tools on the same service, the same bearer tokens, and **no tool that lists or decides an approval**.
- **Pages** at `/`, in dev and demo only:
  - paste a request or click one of three examples, and see the offer, verdict and order;
  - `/approvals`;
  - `/orders/{id}`, with both views of the trail and the chain state;
  - `/assumptions`.

  They carry a Content-Security-Policy with no external source and no inline script, CSRF tokens on every form, and escaped text everywhere. **(FIX-10)** each browser gets its own order book, so one visitor's orders never count in another's daily limit.
- **The buyer agent** (`POST /v1/agent/run`): a Gemini function-calling loop over four tools (authority, create offer, place order, order status). The model can name only an option id, and **only the top option** may be ordered. Every product, price and quantity comes from the gateway, and the report is built from the gateway's own sentences. A run that fails after ordering keeps the order and says what stopped it.

---

## 4. The rules — what the agent may do alone

**Fixed rules** (no profile can switch them off; verdict and role pinned in code):

| Rule | Fires when | Verdict | Why it exists |
|---|---|---|---|
| F-01 | A line's quantity is not confirmed | APPROVAL, purchasing manager | Valio said very large stock values mean "not known"; nobody commits a buyer to stock nobody confirmed |
| F-02 | A line declares an excluded allergen | BLOCK | Defence in depth: the offer already excludes it |
| F-03 | A fact a rule needs is missing | APPROVAL | Missing data never counts as good data (3,068 products do not say whether they are sold by variable weight) |
| F-04 | At order time the option expired, a cut-off passed, or price or availability changed | BLOCK, with a fresh offer | An order rests on the statements of its offer |
| F-05 | A substitute adds an allergen, or raises one to "contains" | BLOCK | 37 of Valio's 249 listed substitutes do (whole catalog) |
| F-06 | An agent calls an approval route | refused | An agent never approves |
| F-07 | A price is not confirmed, a delivery date is ruled out, or a needed-by date is not verifiably met | APPROVAL, purchasing manager | Added overnight (review round 1): the policy did not read the price or date claims at all |
| F-08 | A substitute lacks a dietary claim the original carries | APPROVAL, purchasing manager | Added overnight (T07): regular milk could stand in for lactose-free milk and be ordered alone |

**Buyer-profile rules** (values illustrative and labelled as ours; Valio publishes no customer limits):

| Rule | Setting | hotel-kitchen | allergy-ward |
|---|---|---|---|
| P-00 | agent may order alone at all | yes | yes |
| P-01 | spend per order (purchasing manager) | €750 | €500 |
| P-02 | spend per day, this order included (finance) | €3,000 | €1,500 |
| P-03 | minimum share of the quantity covered | 90% | 100% |
| P-04 | excluded allergens and strictness (dietitian) | none | milk `AM`, gluten `AW`, `STRICT` |
| P-05 | substitutes without a human | same category | none |
| P-06 | variable-weight products | to a human | to a human |
| P-07 | products with a deposit | to a human | to a human |

**The agent orders alone only when** no fixed rule fires and every profile limit holds: price, quantity and allergens confirmed, the date met if one was given, the quantity covered, no substitute outside the profile, and spend within both limits. Tonight that is scenario 2: the ward, 200 × `464013` Alpro No Sugars Soya drink, which states it is free from milk and gluten, **€402.00**, ordered by the agent with no human.

---

## 5. Decisions taken overnight without a human — check these

Each was the default the spec pointed to, or a fix for a reviewer's finding. Each is also a question in `AIMO/BOOTH-QUESTIONS.md` ("Raised during the overnight build"). The column "To change" names the one place to edit.

| # | Decision | Why | To change |
|---|---|---|---|
| 1 | Price, quantity and allergens always gate an order; the date only when asked; origin never | Otherwise an undated request could never go alone | SPEC §4; `OfferLine.confirmed_for_order`; policy facts |
| 2 | New fixed rule F-07 (price, delivery date) | The policy ignored those claims | `src/tta/policy/rules.yaml` |
| 3 | New fixed rule F-08; only **dietary** claims count (lactose-free, low-lactose, gluten-free, wheat-free, egg-free, soy-free, vegan, vegetarian) | Counting every claim made a rice drink the best stand-in for a gluten-free barista oat drink | `DIETARY_CLAIMS` in `src/tta/offers/substitutes.py` |
| 4 | `milk` excludes sour milk, the coffee drink and soy yoghurt; coffee milks stay in | `463380` "Cafè milk" supplies 565 of tonight's 1,000 L; without it option 1 is a partial fill | `exclude_terms` in `product_types.yaml` |
| 5 | A cut-off equal to now counts as passed | "Order by closingTime at the latest" | `availability/states.py` |
| 6 | Gluten-free wheat starch is rejected under a no-gluten exclusion (only oats go to a dietitian) | Least safe wins on conflicting statements | `allergens/statements.py` |
| 7 | Audit events are stamped with real time, not the pinned replay clock | Otherwise every demo event shows 02:52 | `src/tta/api/wiring.py` (audit clock) |
| 8 | A demo approver exists for every role on both profiles | An approval needing a role nobody held could never complete | `approver_roles` in `profiles/*.yaml` |
| 9 | One live order per offer | The same option could be bought twice under two keys | `src/tta/orders/service.py` |
| 10 | Choosing another option restarts the approval on it | An approval was for something else | `orders/service.py` |
| 11 | The day's spend counts an order on the day it became ordered | A pending order approved the next day counted on the wrong day | `orders/spend.py` |
| 12 | `allergy-ward`: variable weight and deposits go to a human | The spec named neither for the ward | `profiles/allergy-ward.yaml` |
| 13 | An unset `TTA_ENV` is `prod` (fails closed) | A deployment with the variable lost would have loaded the public tokens | `src/tta/config.py` |
| 14 | Gemini through `generateContent`, model `gemini-3.6-flash` | The Interactions endpoint answered 503 all night; 3.8 answered 504 to every request; 3.6 answered | `DEFAULT_MODEL` in `src/tta/agent/gemini.py`, or `TTA_GEMINI_MODEL` |
| 15 | When Gemini is down, a known sentence is served from its recording, labelled | The demo must not depend on a slow service | `src/tta/agent/fallback.py` |
| 16 | The agent may order only the top option | SPEC §11 "pick the top option" was only a prompt; a product name could steer it | `src/tta/agent/tools.py` |
| 17 | The model's reading is checked against the text | The model must not decide a quantity | `src/tta/agent/textcheck.py` |
| 18 | **(FIX-10)** Each browser gets a private order book on the pages | Every visitor shared one day's spend: scenario 2 went alone three times, then went to finance for everyone | `src/tta/ui/`, `src/tta/api/` |
| 19 | **(FIX-10)** Rate limits per visitor **and per kind**; `X-Forwarded-For` trusted only when configured | One visitor could fill every global ceiling and forge fresh visitor keys | `src/tta/api/limits.py`, `TTA_TRUSTED_PROXY_HOPS` |
| 20 | Live supplier looks: at most 6 a minute for the whole app | One visitor could spend the call budget for everyone | `src/tta/api/limits.py` |
| 21 | The deployed app may make at most 120 live calls | 150 were approved for the night; 10 were used before the deployment | `DEPLOYED_CALL_BUDGET` in `deploy/modal_app.py` |
| 22 | Stretch tasks S1 (Aiven) and S2 (Context.dev) skipped | The runbook's rule: only if the scenarios were green before 06:30; a usage limit stopped the agents from 05:40 to 07:40 | Task files are ready in `AIMO/build/tasks/` |
| 23 | Scenario 3 on the page is asked by the hotel and ends with the agent ordering the substitute `475224` alone (€174.00) | The hotel's profile allows a same-category substitute | One field in `src/tta/ui/examples.py` (ask as the ward to show a human instead) |

---

## 6. How the build ran, and why that way

- **The orchestrator wrote the contracts first** (T00), so the parallel agents could not drift apart. The contracts were changed only by the orchestrator, when a hand-back asked for it.
- **One task file per agent** (`AIMO/build/tasks/`), each naming the paths it owns, the criterion it scores on, and the tests to write first. These files and `STATUS.md` let the run survive a context reset, a crash, and the two-hour usage limit. The restarted agents picked up exactly where the first ones stopped.
- **Every hand-back was checked, not trusted.** The orchestrator ran the agent's tests itself, checked the agent touched only its own paths, and read the files that carry the logic before committing.
- **Four review rounds, each with three independent reviewers** (correctness, security, silent failures), given the code and the spec but never a conclusion to confirm. There were no critical findings. High findings became fix tasks: FIX-1 to FIX-10 — 10 tasks, about 80 findings in all.
- **Outside services:**
  - Valio: 10 of 150 calls used. The live run matched the capture exactly.
  - Gemini: 18 of 20 requests used, after the endpoint and model changes of decision 14.
  - Modal: not deployed yet; one deployment is approved.
  - Aiven and Context.dev: unused.
- **What went wrong:**
  - a usage limit stopped three agents from 05:40 to 07:40;
  - Gemini's newer endpoint failed all night;
  - the orchestrator twice committed or changed something that broke tests and then repaired it: a port change that broke 45 tests (reverted at once), and a recording committed while four tests still pinned the old time (fixed in the next commit).

---

## 7. Check it yourself in 20 minutes

```bash
cd /Users/joaocosta/Pessoal/junction && git switch overnight-build
.venv/bin/python -m pytest -q                         # the whole suite
.venv/bin/python -m pytest tests/e2e -q               # the scenarios over HTTP, from the pasted sentence
GEMINI_API_KEY= TTA_ENV=demo TTA_MODE=replay TTA_DB_PATH=/tmp/tta-demo.sqlite3 \
  .venv/bin/python -m uvicorn --factory tta.api:create_app
```

Then, in the browser at `http://127.0.0.1:8000/`:
1. **Scenario 1** (hotel). See option 1 at €2,580.64 to the purchasing manager (P-01), option 2 at €1,010.00 with F-01, and 19 exclusions with their reasons.
2. **`/approvals`.** As Hanna (purchasing manager), approve. The order becomes ordered.
3. **`/orders/<id>`.** Switch between the buyer and supplier views. The supplier view has no €750, no Hanna, no note. Check that the chain is intact.
4. **Scenario 2** (ward). Ordered by the agent, €402.00, no approval.
5. **Scenario 3.** `471690` passes the allergen rule but its cut-off has passed; `471881` and `464320` add gluten and can never be ordered; `475224` is ordered.
6. **`/assumptions`.** Every assumption in one table.
7. **`http://127.0.0.1:8000/docs`.** The generated OpenAPI, with examples from the scenarios.

To read the code in the order a request flows, follow section 3's "Where" lines. The three files that hold most of the judgement are `src/tta/policy/rules.yaml`, `src/tta/allergens/exclusion.py` and `src/tta/offers/planning.py`.

---

## 8. Known limits and what is not done

- **Not deployed yet.** `deploy/modal_app.py` and `docs/DEPLOY.md` are ready, and the one approved deployment runs after FIX-10.
- **No browser test.** The pages were checked over HTTP and by their text; their small JavaScript (form-once, approver selector) was not run in a browser.
- **One process.**
  - The order book's lock, the rate limiter and the agent-run log are per process, and the deployment runs one container.
  - Two gateway processes on one database are not protected.
  - SQLite runs on the container's disk, with a copy saved to the Modal Volume.
- **Audit chain:** it does not show the end of the trail cut off unless another party holds the published head hash.
- **MCP:** no OAuth (tokens are handed out outside the protocol), and no Host or Origin check on the MCP endpoint. Both are stated as departures in `docs/STANDARDS.md`.
- **Partner data:** the four Valio data files are tracked in the repository. Decide before it goes public (README says they are not under the MIT licence).
- **22 questions to Valio are still without an answer:** section 9.

---

## 9. Open questions for Valio — still without an answer

22 in all. Only Q3 (very large stock values) has been answered: Valio said in person on 14 Nov that they mean "not known". Each question is written out in full, with its example, in `AIMO/BOOTH-QUESTIONS.md`; the id in the first column finds it there. The last column is what the gateway does until someone answers, so no answer blocks the demo.

### Ask these four first

| Id | Question | Why it matters | What we built meanwhile |
|---|---|---|---|
| T03-1 | `471881` (Oddlygood Barista oat drink 0.5 l) is named "gluten free" and carries the claim, yet declares cereals containing gluten (`AW`); the 1 l packs do not. Is that expected? | It is in demo scenario 3. A Valio judge may say the product is gluten free | The declaration counts, never the name or the claim. `471881` fails the substitution rule and can never be ordered as a substitute |
| Q1 | We read `closingTime` literally: once it has passed, the product cannot arrive on `availableDate`. Right reading? | It excludes 17 of the 30 lactose-free milks tonight, and about half the catalog at any time | A product whose cut-off has passed is excluded, with the reason named. A replay mode covers judging time |
| Q7 | What limits do real customers set: a euro cap per order, an approved product list, approver roles? One example is enough | Every number in our buyer profiles is ours and labelled illustrative | Two profiles, `hotel-kitchen` (€750 per order, €3,000 a day) and `allergy-ward` (€500, €1,500, no milk, no gluten) |
| Q4 | When Valio Aimo accepts an order today, what is committed at that moment: the price, the quantity, the delivery date? | Decides how we word "ordered" in the pitch | Price committed for its validity; date if ordered before the cut-off; quantity only when the stock figure is a real number. Orders are recorded in our order book and commit nobody |

### How to read the data

| Id | Question | What we built meanwhile |
|---|---|---|
| Q2 | Do `X99` and `UNDECLARED` have their GS1 meanings ("no declarable allergens", "not intentionally included")? | GS1 meanings. Under `STRICT`, `X99` goes to a dietitian; under `DECLARED_ONLY` it passes as unverified |
| T03-2 | 178 products state a family "free from" while declaring one of its members (gluten-free loaf with wheat; Toblerone "free from tree nuts" with almonds). Gluten-free wheat starch and a data error? | Two statements; the least safe counts. With the family excluded, a declared member rejects the product (oats go to a dietitian) |
| Q5 | 46.2% of the catalog has no allergen statement at all. Does no data mean the supplier declared nothing, so an agent must treat it as unknown? | Unknown, never safe. Under `STRICT` it goes to a dietitian |
| T02-1 | `allowedLotSize` is 0.01 on 16,476 countable products (cases, cartons). Does 0.01 mean "no step"? | Whole units for every sales unit except kilograms; kilograms keep 0.01 kg; the 674 real steps are used as given |
| T02-2 | What does `comparisonPrice` divide by: the content of one sales unit (drained weight where there is one), rounded to cents? | The file's own size when the two prices are consistent with it (10 L, not 9.943), otherwise the ratio |
| Q10 | The API's sales unit differs from the product file's on 7 of 797 lines. Which unit do the price and the amount refer to? | Price and quantity follow the unit on the API line |
| T07-5 | Is a listed substitute meant across sales units? `473609` is sold by the piece; its listed substitute `471690` by the 10-litre case | Quantities are converted through the pack size and rounded up to the lot step |
| Q8 | Is a deposit already inside `catalogPrice`, or charged on top, and at what value per code? | Totals exclude deposits and say so; a line with a deposit goes to a human |
| Q9 | Is a variable-weight product invoiced at the weight ordered or the weight delivered? | The total is marked as a ceiling; the line goes to a human |
| Q11 | Is the category code a hierarchy (which digits are the levels)? Can we have the category names? | Substitute tiers: same 5 digits → same 4 → same 3; 30 product types of our own |
| Q12 | What does delivery reliability measure, and does a missing value mean no history? | Missing means no history and is never imputed; the raw value is shown without a gloss |

### How the mock and the judging work

| Id | Question | What we built meanwhile |
|---|---|---|
| Q6 | When stock covers only part of an order line, what happens today: a partial delivery, a substitute, or the line is dropped? | Fill the rest from a second product; show the option as combined; below the buyer's minimum fill it goes to a human |
| Q13 | Is our call volume fine during judging? One offer is 2 calls (price and availability, up to 1,000 products each); tonight's live run made 6 calls for three scenarios; the deployed app may make at most 120 | Filter locally, a 60-second cache, at most 6 live looks a minute, and the recorded capture when the budget runs low |
| T01-1 | A call with Python's default `User-Agent` got 403 from Cloudflare; with a named one, 200. Is a named User-Agent the rule an external agent should follow? | The client always sends `User-Agent: tta-gateway/0.1`; a 403 is reported once, never retried |
| Ask any 1 | How and when do you judge: at our table, the video, or the deployed link? Will the mock API stay up unchanged until then? | Replay mode with tonight's capture; the deployed link falls back to it, labelled |
| Ask any 2 | Do exception cases have to run in the live demo, or does a documented rule count? | Every exception runs in the demo or in a tested request (partial fill at 1,500 L, substitutes, cut-off passed) |
| Ask any 3 | The brief mentions webshop test accounts. Are they available? | Not used |
| Ask any 4 | The hackathon requires a public MIT repository. May the datasets and a few recorded responses of the mock API stay in it? | The README says the data is not under the MIT licence. **Decide before the repository goes public** |

