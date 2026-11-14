# AWARDS-PLAN — Modal, Context.dev and Aiven in the hours that are left

Written Saturday 14 Nov, evening, for task T1. Code read at `51e9b03` plus the working tree (B0 was running). No outside call was made, nothing was deployed, `.env` was not read, the suite was not run (tests were only counted with `--collect-only`). Statements about the deployed app, about credits and about sponsor web pages are quoted from repository files and marked as such; I could not check them.

Item ids are `AP-n`. Where an item is one of P13's, its `TA-n` is named.

## 1. The three awards at a glance

| Award | What it asks, in one line | Our angle, in one line | State today | Chance (my judgement) | Work left |
|---|---|---|---|---|---|
| **Context.dev** — "Best Use of Context.dev: Fully Structured Web" | One endpoint "in its core flow, not just as a side feature", whose data "must visibly drive something in the demo" | When Valio's data states nothing about an allergen the buyer excludes, the person who must sign sees what the maker's own page says, checked and labelled "not Valio data" | Built, 90 tests, 5 recorded pages. Shown on the old `/approvals` card only: the shop page prints a count, not the content, and no shop example reaches it | **Best of the three: fair.** Basis: both minimum requirements are met in code, the extraction is narrow and guarded (the brief's "exactly what you need … and nothing more"), the lead judge is on site. Against: it informs a person and changes no system decision; no rubric and no field size are published | Agents 4–6 h · João 0.75 h |
| **Aiven** — "Best Use of Aiven" | "a thoughtful implementation that makes a meaningful difference to the working solution" and "demonstrate what it enables" | The audit trail lives in a database that itself refuses to change a row, and Valio reads its own view with its own read-only login | Built, 119 tests (67 of them need the live service, by P13's count). Deployed since 11:15 according to `AIMO/build/STATUS.md:23`. Nothing on the public link shows it; the supplier login was never created; no proof captured | **Low to fair; fair only if the proof and the page exist.** Basis: the brief says one well-executed service can win, and ours uses triggers, views and roles for a reason the main challenge scores. Against: today the evidence is a document and skipped tests | Agents 3.5 h · João 0.75 h |
| **Modal** — "Best Use of Modal" | "the most ambitious working AI system built on Modal, where Modal does the heavy lifting" (GPU model, Sandboxes, fine-tuning, batch fan-out) | Honest hosting, plus one real fan-out (the evidence batch) and a scheduled witness of the audit head | One CPU web function. None of the brief's four asks. Since Gemini was dropped, the deployed system calls no model at all | **Low.** Basis: the brief's own bar; any team serving a model on a Modal GPU meets it better. The two additions move it from "hosting" to "light, purposeful use", not to "most ambitious" | Agents 4 h · João 0.5 h |

None of the three briefs names a prize, a separate form, a deadline or a booth demonstration (section 6). "Chance" is a judgement from the briefs' wording and our code; nothing in the repository says how many teams enter each.

## 2. Context.dev

### 2.1 The brief's own words (`CONTEXTDEV-TECH-CHALLENGE.md`)
- "use the Context.dev API to **extract exactly what you need from the web and nothing more**."
- "**To count, the project must call at least one Context.dev endpoint in its core flow, not just as a side feature.**"
- Minimum requirements: "Use **at least one Context.dev API endpoint** in the submitted project." · "**The data from Context.dev must visibly drive something in the demo.**"
- What to submit: "A **GitHub repository** and a **demo**, plus a **short note on which endpoints were used and why**."
- Pitfalls it names: "Check each output's `success` flag"; "cached results cost the same credits as fresh ones — store results in your own app".
- "**Beer van der Drift** — CTO, **challenge lead and lead judge**". On site "Saturday 09:00 → Sunday 02:00 · Sunday 07:00 → end".
- No rubric is published (`CONTEXTDEV-CHALLENGE.md`, our note: "No published judging rubric. Ask at the booth."). `CONTEXTDEV-CHALLENGE.md` is their main challenge; we are in Valio's, so only the tech track applies.

### 2.2 What counts today (checked in code)
- One endpoint, Answers: `POST https://api.context.dev/v1/web/answers`, mode `ultra`, 40 s deadline with `behavior: "fail"` (`src/tta/evidence/answers.py:27-33`). Our own shape of seven fields (`:42-50`). Only the product's two names and its brand are sent (`answer_request`).
- Guards before anything is shown: the page must name this product and its brand (`src/tta/evidence/matching.py`), the answer is stored once per product (`cache.py`), failures become a sentence, never an error (`finder.py`).
- Trigger: rule P-04 fired on the product and a finding is `NOT_STATED` or `UNDECLARED` (`finder.py:37,49-65`). Wired into the shared book and every page's own book (`src/tta/api/wiring.py:247`, `_Shared.sandbox`).
- 5 recordings in `fixtures/evidence/` (`468465`, `469512`, `473609`, `474864`, `475224`); 90 tests in `tests/evidence/`; the note exists (`docs/CONTEXTDEV.md`).
- Visible on the old pages: `src/tta/ui/templates/_evidence.html`, included in `approvals.html:45`.

### 2.3 The gap
1. **The page the demo runs on does not show it.** `src/tta/ui/static/shop/js/views/approvals.js:49` prints "N note(s) from the manufacturer's page are attached in the audit trail" and nothing of the content. P13 was written before the shop page was merged and does not have this. As it stands, the requirement "must visibly drive something in the demo" is met only on `/approvals`, a page the demo no longer uses.
2. **No shop example reaches the card.** `grep` finds `469512` in `src/tta/ui/examples.py` (old pages) and not in `static/shop/js/kitchens.js`.
3. **The demo's own customers have no recorded pages.** The school's strict rule sends products with no nut or sesame statement to the dietitian (replan `STATUS.md`, L5 hand-back); none of them is among the 5 recordings.
4. **One kind of doubt only** (P13 §2.4, confirmed: `UNSTATED` holds two relations).
5. **"Core flow" is arguable.** Evidence informs the signer and changes no decision. That is the safe design; whether the judge counts it is a booth question (section 7, João 1).
6. **The cap is per process**: `DEFAULT_MAX_CALLS = 40`, counted in memory (`answers.py:37`); a restarted container starts at 0. Already in L4-2.
7. **"Manufacturer's page" is not checked**, only that the brand appears in the name, title or host (`matching.py:41-43`). Already in L4-2 (TA-4).

### 2.4 Work items, ranked
| Id | What | Offline tonight: lane · files · done when | João | Valio criterion |
|---|---|---|---|---|
| **AP-1** | The shop's approval card shows the evidence, and one example reaches it | **U1** · `src/tta/ui/static/shop/js/views/approvals.js`, `shop.css`, one example request in the shop's examples, `tests/ui/test_shop_api.py` · Done when: in replay the typed request of `docs/CONTEXTDEV.md` (100 L of `469512`, no milk) through `/shop/api/offers` and `/shop/api/orders` gives an approval whose `evidence[0].source_url` is on `raisiofoodsolutions.fi` (a test asserts it), and the card prints, above the reasons: the heading "… not Valio Aimo data", the product name on the page, contains / may contain / free from, the link (plain `http(s)` only), the retrieval time; with `found: false` it prints the sentence. One click from a shop example gets there | — | 20% controls (the signer decides with something in front of them) · 15% exceptions (missing allergen data) |
| **AP-3** | A recording command, and the list of demo products that need a page | **L4** · new `scripts/record_evidence.py`, new `tests/evidence/test_record_script.py`; the list comes from E1's re-measured demo set · Interface: `--ids <id> …` or `--demo-set`, `--limit N` (default 20), `--dry-run`. A dry run sends nothing and prints each request body and "100 credits each". A real run goes through `EvidenceFinder` and writes `fixtures/evidence/<id>.json` in the existing format · Done when: tests pass with a stand-in `AnswerSource`; the dry run in replay prints bodies that hold only the English name, the Finnish name and the brand | Runs it (section 7, João 4) | 15% exceptions |
| **AP-4** (= TA-4, already in L4-2) | Evidence on every P-04 finding that goes to a human; the heading says "manufacturer's page" only for a listed brand-owner domain; the cap is kept on disk | **L4** · `src/tta/evidence/finder.py`, `matching.py`, `wording.py`, `answers.py`, `tests/evidence/` · Done when: the almond drink `465793` (contradiction case, P13 §2.4) yields one evidence entry in replay, `found: false` with "no recorded page" until João records it; a second `AnswersClient` on the same data folder continues the first one's count | Two lookups, inside João 4 | 20% controls · 15% exceptions |
| **AP-9** | The card answers the question that was asked: for each excluded allergen, "Valio: not stated · the page: free from, in its words 'Maidoton'". When the page names an excluded allergen under contains or may contain, the approval gains a reason line. Stricter only: evidence still never clears anything | **L4** + **U1** · new `src/tta/evidence/alignment.py`, `reading.py`, one additive field on `Evidence` in `contracts/order.py`, the card, `tests/evidence/` · Reuse `tta.allergens.ingredients.ingredient_mentions` read-only; a small free-from word table is needed because `_FINNISH["AM"]` is `("maito",)` and does not match "Maidoton" · Done when: `469512` with milk excluded reads "free from"; a page with `contains: ["Pähkinät"]` and nuts excluded adds the reason line; a word that matches nothing gives "the page's words could not be matched to this allergen", never a guess | — | 20% controls · 20% precision (less to read before signing) |

AP-9 is the first Context.dev item to cut. It is also the only one that makes the web data change something the system does, which is what the brief's "core flow" sentence asks.

Not tonight: formula evidence (TA-8, needs P10's rule first), a second endpoint for cheap re-reads, a monitor on a maker's page (P13 C3, C4: no criterion at a fair price; the brief asks for "at least one" endpoint).

### 2.5 What to say
- **Note for the submission** (the brief asks for it): "Endpoint: Answers, one request per product. Why: one call finds the maker's product page and returns our seven fields with the pages it read. When: only when Valio Aimo's data states nothing about an allergen the buyer excludes and a person must sign. Sent: the product's two names and brand, nothing about the buyer. Checked: the page must name this product and brand; a 200 with a failed or partial answer is not evidence. Stored once per product, because a cached answer costs the same. It never changes a verdict." Then the measured line from João 4 (how many products were asked, found, matched, dropped), labelled as a sample.
- **Video:** the dietitian's card for 4–5 s with the caption "From the maker's page through Context.dev — a person decides".

## 3. Aiven

### 3.1 The brief's own words (`AIVEN-CHALLENGE.md`)
- "the most impressive use of Aiven technology: a thoughtful implementation that makes a meaningful difference to the working solution."
- "**Use at least one Aiven service as a meaningful part of the project, and demonstrate what it enables.**"
- "A well-executed use of one service can be just as impressive as a solution combining several."
- "You can enter this tech challenge alongside your main challenge." · "Aiven mentors on site all days". The brief lists nothing to submit.
- Our own note in that file: swapping local Postgres for Aiven Postgres "technically qualifies and will score nothing".

### 3.2 What was decided, and why
1. **Dropped**, in the plan of the night of 13–14 Nov: "Aiven was dropped on 14 Nov: 1.5 hours for an entry our own notes rate as scoring nothing." (`AIMO/PLAN.md` as of commit `d6ac0ce`, §6). `CLAUDE.md` (Status) still says this.
2. **Built anyway**, Saturday morning: "The human chose (Saturday morning): build what can win a tech award when it meets the brief" (`AIMO/build/STATUS.md:91`). Task S1, commit `67f3b00`; deployed at 11:15 "mode live, Aiven connected (no fall-back)" (`:23`).
3. **Entered**, about 15:50: decision 7 of `AIMO/PLAN.md` §9, "Enter the Aiven award: Yes (0.5 h)", following P13.
4. **Maximise**, 17:33 (replan `STATUS.md`, João's changes).

So `CLAUDE.md` line "Aiven was dropped on 14 Nov" is out of date. The run may not edit `CLAUDE.md`; it is João's line to change.

**My recommendation: enter it.** The reason it was dropped was the cost of building it and the fear of a plain database swap. The cost is spent, and what was built is not a swap: the database enforces the audit rule the main challenge scores (20%, "how decisions are logged and auditable"). What is left is about 0.75 h of João's time and agent work in files no main lane needs. The entry has one real risk, the redeploy (3.4, AP-2); handle that and it cannot weaken the main entry, because the gateway falls back to SQLite when the database fails at start (`src/tta/api/wiring.py:128-137`).

### 3.3 What counts today (checked in code)
- `src/tta/store/postgres.py` (380 lines) behind the `Store` port; chosen when `DATABASE_URL` is set, SQLite otherwise, with the reason in `/healthz` on fall-back (`wiring.py:_order_book`).
- `sql/002_audit_append_only.sql`: triggers refuse `UPDATE`, `DELETE`, `TRUNCATE` and an insert that does not follow the head; both `ENABLE ALWAYS`.
- `sql/003_reader_views.sql`: `audit_buyer` and `audit_supplier`. `sql/004_supplier_role.sql`: a `NOLOGIN` role with `SELECT` on the supplier view only.
- Tests: 114 collected in `tests/store_pg`, 5 in `tests/api/test_store_choice.py`. P13 says 67 are skipped without the service; I did not run them.
- `docs/AIVEN.md` holds the SQL for each claim.

### 3.4 The gap
1. **Nothing on the link shows Aiven.** Every page, the shop included, writes to an in-memory SQLite book per browser (`wiring.py`, `_Shared.sandbox`: `SqliteStore()`). Only REST and MCP callers write to the shared book. `/healthz` reports a fall-back but never says which store is in use.
2. **The supplier login does not exist** (role is `NOLOGIN`; `docs/AIVEN.md` §3 gives the `CREATE ROLE … LOGIN` statement to run by hand). "Valio reads its own view" was shown by a test login only.
3. **No captured proof**, and `psql` is not installed on this machine (`command -v psql` finds nothing), so the statements of `docs/AIVEN.md` cannot be pasted as they are.
4. **The redeploy can break the deployed trail. P13 does not have this.**
   - The chain is verified by re-computing each hash from the event's model (`src/tta/audit/chain.py:event_hash`, `model_dump(mode="json")`). A field added tonight to `AuditEvent`, `AuditData` or `Actor`, even with a default, changes the canonical JSON of every event already stored, and the whole deployed trail then reads "does not verify". It cannot be cleaned: the database refuses to delete it. No test pins a stored event's hash (`tests/audit` holds no fixed hash). At `HEAD` these three models are unchanged since the deployed commit `8163d5d` (`git diff 8163d5d -- src/tta/contracts/audit.py` is empty); L3's work tonight (S4, "confirmed by") is where it could change.
   - Stored offers, orders and approvals are read back with `extra="forbid"` (`contracts/common.py:52`): a field removed or renamed tonight makes the old rows unreadable.
   - L3 changes `audit_supplier`. PostgreSQL's `CREATE OR REPLACE VIEW` accepts new columns only at the end and no change of an existing column's name, order or type. A failed migration fails the whole start-up transaction, and the gateway then runs on SQLite with a reason in `/healthz`: Aiven would be silently out of use on judging day. The test that would catch it is live-only.
   - The schema name is fixed: `tta` for the deployed app (`postgres.py:54-57`, `schema_for`).
5. The gateway's login owns the tables and could drop a trigger (`002`, the comment at its head). Stated in the write-up; not closed this weekend.

### 3.5 Work items, ranked
| Id | What | Offline tonight: lane · files · done when | João | Valio criterion |
|---|---|---|---|---|
| **AP-2** | The redeploy cannot break the trail | **L3** · `tests/audit/` (one new test), `src/tta/store/sql/003_reader_views.sql` · A test builds one event of each type with fixed values and asserts its hash against a constant written from today's models, so a change to the hashed shape goes red tonight. If the supplier view's columns change, `003` drops the view before creating it (`004` grants again at every start). **L4** · `src/tta/store/postgres.py`, `tests/store/`; one optional setting in `src/tta/config.py` (the orchestrator assigns that line) · `TTA_DB_SCHEMA`, default unchanged; `deploy/modal_app.py` sets a new name for the Sunday deploy so the new build starts a new trail and the old one stays as it is · Done when: both tests pass offline; `schema_for` returns the setting when set and refuses a name the existing pattern refuses | Runs the live tests before the deploy (João 3) | 20% auditable · 30% (the link's audit view does not turn red) |
| **AP-5** (makes TA-3 one command) | The proof as a script | **L4** · new `scripts/aiven_proof.py`, new `tests/store/test_aiven_proof.py` · Reads the URL through `tta.config` only and prints no secret. Prints, with the statement before each result: server version; the two triggers and `tgenabled`; `UPDATE`, `DELETE` and `TRUNCATE` on `audit_events`, each in its own savepoint, with the refusal's SQLSTATE and text; the head (`count`, last `seq`, last `hash`); the buyer's and the supplier's sentences for the newest order. With `--as-supplier` (a second URL from the environment variable `SUPPLIER_DATABASE_URL`): rows from `audit_supplier`, and "permission denied" for `audit_events`, `audit_buyer` and `orders`. With `--create-supplier-login`: `CREATE ROLE valio_aimo LOGIN PASSWORD … IN ROLE <schema>_supplier`, the password read from an environment variable and never printed. `--dry-run` prints the statements only · Done when: the tests pass with a stand-in connection and the dry run lists every statement | Runs it (João 7) | 20% auditable ("for buyer and Valio Aimo") · 15% path to production |
| **AP-6** (= TA-6) | Valio's log of the shared book, as a page, and the store named in `/healthz` | **New task U2** (interface) · new `src/tta/ui/supplier_page.py`, new `templates/supplier.html`, one line in `src/tta/ui/routes.py`, `tests/ui/test_supplier_page.py`; **L4** · `src/tta/api/routes.py` (`Health` gains `store`: `postgresql` or `sqlite`) · The page lists the shared book's orders (`SurfaceContext.service`) in the supplier's view only, with the state of the chain, the head, and one line: where the trail is kept and that the database refuses to change a row; on SQLite it says so instead · Done when: a test places an order over REST with a demo token and finds its supplier sentences on the page, and no limit value, allergen code or approver name (the audit package's own redaction check) | Screenshot after the check's order (João 6) | 20% auditable · 30% (an outside agent's order appears where Valio reads it) · 15% openness |

Already in L3 tonight and needed here: the SQL view changed together with the supplier's reader, and a test that both list the same fields.

Not this weekend: a gateway login that does not own the tables (P13 A3), Valkey, Kafka, ClickHouse. Each is a new service or a second URL for no criterion in these hours.

### 3.6 What to say
- **Submission:** "The shared order book and the audit trail are in Aiven for PostgreSQL. Three things a file could not give: the database itself refuses to change or remove an audit event, for the gateway's own login too; Valio Aimo reads its own redacted view with its own read-only login; the trail outlives the container." Then the script's real output. Keep the honest line: the gateway's login owns the tables today.
- **Video:** on the audit shot, the caption "Kept in Aiven PostgreSQL — the database refuses to change a row". If AP-6 is built: 3–4 s of the page after an agent's order over MCP or REST.

## 4. Modal

### 4.1 The brief's own words (`MODAL-CHALLENGE.md`)
- "Use Modal to power the project you're already building: **Serve an open model on a GPU** · **Run your agent's code in secure Sandboxes** · **Fine-tune a model on your own data** · **Fan out a big batch job**".
- "They're looking for **the most ambitious working AI system built on Modal, where Modal does the heavy lifting and the team spends its 48 hours on the problem.**"
- "Best use of Modal is a tech challenge, so you compete in it on top of your main challenge... The same project can enter other tech challenges too."
- "$100 in Modal credits per participant". Mentors "At the Modal booth throughout the event". The brief lists nothing to submit.

### 4.2 What counts today (checked in code)
- `deploy/modal_app.py` (361 lines): one function `web`, an ASGI endpoint with a public URL; `max_containers=1`, scale to zero after 600 s, 1 core, 1024 MiB, no GPU; the image defined in code with pinned libraries; a Secret of up to five named values built at deploy time (`SECRET_NAMES`); a Volume for the call budget, the recordings and a copy of the SQLite file.
- `grep -c "Cron\|Period\|Sandbox\|\.map(\|spawn\|gpu=" deploy/modal_app.py` gives 0, as P13 says.
- `deploy/check.py` (seven checks, `--mode`, `--no-order`); 50 tests in `tests/deploy/`.
- `docs/AWARDS.md` already says "By the brief's own bar this is a light use of Modal". Its sentence "The model runs on Google's API" is no longer true of the run: Gemini is dropped and the link calls no model.

### 4.3 The gap
All four of the brief's asks are absent, and the brief's subject is an "AI system". The gateway is the interface an AI agent buys through; it is not itself a model. A winning entry would serve a model on a Modal GPU. Two smaller steps are honest and useful; a third is the real one and I do not recommend it.

### 4.4 Work items, ranked
| Id | What | Offline tonight: lane · files · done when | João | Valio criterion |
|---|---|---|---|---|
| **AP-7** | The evidence batch as a Modal fan-out ("Fan out a big batch job"): one function mapped over the products whose allergen data states nothing, at most 40 at a time (Context.dev's brief: "max 50 concurrent requests per organisation") | **L4** · new `deploy/evidence_batch.py`, new `src/tta/evidence/batch.py` (which products, the summary table: asked, page found, matched, dropped as another product, names an allergen), `tests/deploy/`, `tests/evidence/` · It reuses AP-3's functions; a `local_entrypoint` takes `--limit` and `--dry-run` and writes the records to `fixtures/evidence/`; the Context.dev key goes into its own Modal Secret the way `secret_values` does it · Names checked against the installed client only (1.6.4 has `modal.Cron`, `Function.map`, `App.local_entrypoint`, `modal.Dict`); no Modal page is read · Done when: tests pass with the function called locally on a stand-in source; `--dry-run` prints the product count and the credit cost and sends nothing | Runs it (João 5) | 15% exceptions (missing allergen data, at catalog scale) · 20% controls · it also gives Context.dev its measured line and removes the 40 s wait for every product it covers |
| **AP-10** (= TA-7, already in wave 4) | A scheduled witness of the audit head. `src/tta/audit/chain.py` says a cut or a rewrite of the trail shows only if "another party" holds an earlier head, and that nobody does | **X / L4** · `deploy/modal_app.py`, `tests/deploy/`, `docs/DEPLOY.md` · A scheduled function reads `seq` and `hash` of the last row of `audit_supplier` with the supplier's login, checks that the head it noted last time is still at that position, and keeps its notes on Modal · Done when: the pure check passes its tests (same head, grown trail, shortened trail, rewritten row), and the function is not scheduled when `SUPPLIER_DATABASE_URL` is unset | The supplier login (João 7), then the deploy activates it | 20% auditable |
| (in L4-2) | The link's settings: replay and the demo clock in `deploy/modal_app.py` | L4 · already planned | The redeploy (João 6) | 30% working demo |

**Not recommended: an open model on a Modal GPU as the reader** (P13 M3). It is the only step that meets the brief's first ask, and it would give the link a model again now that Gemini is gone (20%, precision: P13 measured 10 of its own 16 sentences refused by the fixed rules). But it cannot be built to a trustworthy state tonight: the run may not deploy, call Modal or read its documentation, so the serving code would be written blind and first run on Sunday morning by João, who then also owns the video and the form. P13 puts it at 6 h or more. It also reverses a decision of today (replan `STATUS.md`, 17:33: "The fixed-rules reader is the product"). If João wants it, it is his decision and his hours, with the Modal booth beside him; it is not a lane.

Also not: Sandboxes (our agent writes no code), a scheduled job that renews standing orders (P13 §4.2, rejected there for good reasons).

### 4.5 What to say
- **Submission:** "Modal hosts the whole gateway (REST, MCP, the pages) behind one public URL from plain Python: image, secret and volume in code, scale to zero. One fan-out job on Modal read N manufacturer pages through Context.dev in M minutes [real figures from João 5]. A scheduled function on Modal witnesses the head of the audit trail [only if AP-10 is live]. We serve no model on Modal and run no GPU: by the brief's own bar this is a light use." Remove "The model runs on Google's API".
- **Video:** the Modal address on the title shot. Nothing more; seconds are better spent on the main flow.

## 5. P13's claims, checked
| Claim | Result |
|---|---|
| Modal: one CPU function, a Secret of five names, a Volume, none of the four asks; 50 tests | Holds |
| Context.dev: Answers, `ultra`, 40 s, seven fields; trigger P-04 with two relations; cap 40 in memory; brand not owner; 5 recordings; 90 tests | Holds |
| Aiven: store, triggers `ENABLE ALWAYS`, views, `NOLOGIN` role, fall-back; 119 tests | Holds (119 collected; the 52/67 split not re-run) |
| "No page uses Aiven" | Holds, and now covers the shop page too |
| Evidence is "shown first on the approval card" | True of `/approvals` only. The shop page shows a count (2.3, gap 1) |
| "Aiven connected (no fall-back)", three deploys, credits left, requests spent | Quoted from `AIMO/build/STATUS.md` and `docs/CONTEXTDEV.md`; not checkable here |
| Modal schedules, plan limits, GPU prices, the vLLM example, Context.dev credit prices, Gemini billing | P13 read sponsor pages on 14 Nov. Not in the briefs, not checked; this plan relies on none of them except "a schedule starts at deploy", which João sees at the deploy |
| TA-2, TA-5 (Gemini) | Dropped with Gemini. TA-1 and TA-9 are AP-8 below; TA-3 is AP-5 + João 7; TA-4 is AP-4; TA-6 is AP-6; TA-7 is AP-10; TA-8 is not tonight |
| Missing from P13 | The redeploy risk to the deployed trail (3.4, gap 4) |

## 6. Submission mechanics
| | Separate form | Deadline of its own | Booth step | What the brief asks to submit |
|---|---|---|---|---|
| Context.dev | The brief names none | None named | None required. The lead judge is on site until Sunday 02:00 and from 07:00 | "A GitHub repository and a demo, plus a short note on which endpoints were used and why." |
| Aiven | The brief names none | None named | None required. "mentors on site all days" | Nothing listed |
| Modal | The brief names none | None named | None required. Booth staffed "throughout the event" | Nothing listed |

- The briefs are silent on where a tech entry is declared. The Junction form has "Challenge selected" and "Technologies used" (`CLAUDE.md`, submission checklist). Ask each booth tonight (João 1). If nobody answers: select the three on the form if it lists them, name them under technologies, and put the three notes in the description with a link to `docs/AWARDS.md`.
- Context.dev asks for a GitHub repository. Ours is private today, and making it public waits on booth question 8 about Valio's data files (`AIMO/PLAN.md` §11).
- `RESOURCES.md` records that the credits listing showed "Status: Closed" with a countdown. The old plan lists claiming the Modal and Aiven credits as a Friday carry-over "to confirm"; the repository does not record that either code was redeemed, so confirm it. The Context.dev credits were redeemed and used (51,000 → 49,685, `docs/CONTEXTDEV.md`).

## 7. Do tonight (agents, offline, in this order)
An item that also raises a Valio criterion comes first; within that, the cheaper first. Cut from the bottom.

| # | Item | Lane | Files | Done when |
|---|---|---|---|---|
| 1 | **AP-1** The shop's approval card shows the evidence; one example reaches it | U1 | `static/shop/js/views/approvals.js`, `shop.css`, the shop's examples, `tests/ui/test_shop_api.py` | The replay request for `469512` without milk gives an approval with `evidence[0]` on `raisiofoodsolutions.fi` (tested) and the card prints its content under "not Valio Aimo data" |
| 2 | **AP-2** The redeploy cannot break the trail | L3 + L4 | `tests/audit/` (pinned hashes), `sql/003_reader_views.sql`, `store/postgres.py`, `config.py` (one setting), `deploy/modal_app.py`, `tests/store/` | The pinned-hash test is green on today's models; `TTA_DB_SCHEMA` chooses the schema; the view migration drops before it creates if columns changed |
| 3 | **AP-3** `scripts/record_evidence.py` and the list of demo products with no recorded page | L4 (list from E1) | new `scripts/record_evidence.py`, `tests/evidence/test_record_script.py` | Tests pass with a stand-in source; `--dry-run` prints the bodies and the cost and sends nothing |
| 4 | **AP-4** Evidence on every P-04 finding, the honest heading, the cap kept on disk (L4-2 as planned) | L4 | `src/tta/evidence/finder.py`, `matching.py`, `wording.py`, `answers.py`, `tests/evidence/` | `465793` yields one evidence entry in replay; the count survives a new client on the same folder |
| 5 | **AP-5** `scripts/aiven_proof.py` | L4 | new `scripts/aiven_proof.py`, `tests/store/test_aiven_proof.py` | Tests pass with a stand-in connection; `--dry-run` lists every statement; no secret in any output |
| 6 | **AP-6** Valio's log of the shared book as a page; `/healthz` names the store | new U2 + L4 | new `ui/supplier_page.py`, `templates/supplier.html`, `ui/routes.py` (one line), `api/routes.py`, `tests/ui/test_supplier_page.py` | A REST order with a demo token appears on the page in the supplier's words, redaction check passes; `/healthz` has `store` |
| 7 | **AP-7** The evidence batch as a Modal fan-out | L4 | new `deploy/evidence_batch.py`, `src/tta/evidence/batch.py`, `tests/deploy/`, `tests/evidence/` | Tests pass with the function called locally; `--dry-run` prints count and cost |
| 8 | **AP-8** Documents (= TA-1, TA-9 without Gemini): one true paragraph per award with what ran and what a person must still run; the Context.dev note; `docs/DEPLOY.md` (database, secret, files in the image); three video captions in `docs/PITCH.md`; the hand-over lists the `CLAUDE.md` line that is wrong | E2 | `docs/AWARDS.md`, `docs/CONTEXTDEV.md`, `docs/AIVEN.md`, `docs/DEPLOY.md`, `docs/PITCH.md`, `HANDOVER.md` | No sentence claims a model runs, a GPU, or anything not run; "The model runs on Google's API" is gone; every figure says sample or whole catalog |
| 9 | **AP-10** The scheduled witness on Modal (wave 4, as planned) | X / L4 | `deploy/modal_app.py`, `tests/deploy/`, `docs/DEPLOY.md` | The pure check passes four cases; nothing is scheduled without `SUPPLIER_DATABASE_URL` |
| 10 | **AP-9** The card answers the question asked; a page that names an excluded allergen adds a reason | L4 + U1 | new `evidence/alignment.py`, `reading.py`, `contracts/order.py` (additive), the card, `tests/evidence/` | The three cases of 2.4 pass; an unmatched word is never guessed |

Agent hours, summed from the items: about 12, in three lanes that run side by side. None blocks a wave of the main build; items 2, 4 and 9 are already on the board in some form.

## 8. João's commands (in this order)
Run from the repository root. `<url>` is `https://joaocostared--trusted-trade-agents.us-east.modal.run` (`docs/DEPLOY.md`). Commands 4, 5 and 7 exist only after items 3, 7 and 5 of section 7 are built; their flags are specified there so the agents build to them.

1. **Tonight, before 02:00 — three booths, no code.** Context.dev (Beer van der Drift): show the card and ask "Evidence on a human approval, which never changes the system's verdict: does that count as core flow, or did we read the requirement wrong?" Aiven and Modal: "How is a tech entry declared — a field of the Junction form, a form of your own, a deadline, a demonstration at the booth?" Write the answers into `AIMO/BOOTH-QUESTIONS.md`.
2. **When the run has written `HANDOVER.md`:** `.venv/bin/python -m pytest -q`. Sends nothing.
3. **Aiven, live tests:** `.venv/bin/python -m pytest tests/store_pg -q -m live`. Sends SQL to the Aiven service; each test makes and drops its own schema `tta_test_…` and its roles; the deployed schema is not touched. Capture: the last line of the output. If a test of the reader views fails, do not deploy with `DATABASE_URL` until it is fixed.
4. **Context.dev, the demo's pages:** `.venv/bin/python scripts/record_evidence.py --demo-set --dry-run`, read the list, then the same without `--dry-run` (default limit 20). Sends each product's English name, Finnish name and brand to `api.context.dev`; 100 credits each (`answers.py`, `ultra`); nothing about a buyer. Capture: the command's summary and the new files in `fixtures/evidence/`. This goes past the 60 requests the team approved (17 used): that approval is yours to raise.
5. **Modal fan-out (optional, only if 4 worked):** `.venv/bin/modal run deploy/evidence_batch.py --limit 200`. Sends the same three fields per product, from Modal containers, and the Context.dev key as a Modal Secret; up to 20,000 credits of the 49,685 that were left after the build (what the deployed app spent since is not counted anywhere). Capture: a screenshot of the Modal dashboard during the run (the parallel inputs), the printed summary table, and the Context.dev dashboard's balance before and after. Then `git add fixtures/evidence && git commit`.
6. **Redeploy, from the frozen commit:** `.venv/bin/modal deploy --strategy recreate deploy/modal_app.py`. Sends: `src/tta`, the product file, the two CSV files, `fixtures/valio`, `fixtures/agent`, `fixtures/evidence`, `docs/ASSUMPTIONS.md`; and a Secret with the values that are set among the Valio key and address, the Gemini key, `DATABASE_URL` and the Context.dev key, read through `tta.config`. Then:
   - `.venv/bin/python deploy/check.py <url> --mode replay` — places one order over REST into the shared book, which is the outside agent's order the Aiven proof and the supplier page show. Capture: the seven lines.
   - `curl -s <url>/healthz` — `status` must be `ok`, `reasons` empty, `store` `postgresql`. Capture: the JSON, and `audit_head`.
   - Screenshots: `<url>/shop` on the dietitian's card with the evidence; the supplier page with the check's order.
7. **Aiven, the proof** (set a password in your shell first; it is never printed):
   - `.venv/bin/python scripts/aiven_proof.py --create-supplier-login`
   - put the supplier's URL (the same host, port and database, user `valio_aimo`) in `.env` as `SUPPLIER_DATABASE_URL`
   - `.venv/bin/python scripts/aiven_proof.py` and `.venv/bin/python scripts/aiven_proof.py --as-supplier`
   Sends SQL to the Aiven service; the three refused statements change nothing. Capture: both outputs, pasted into `docs/AIVEN.md` under "Run on the deployed database, 15 Nov".
8. **The trail outlives the container:** wait until `.venv/bin/modal container list` shows none for the app (10 idle minutes), then `curl -s <url>/healthz` again. Capture: the same `audit_head` as in 6.
9. **Only if item 9 of section 7 was built:** deploy once more after 7 so the Secret carries `SUPPLIER_DATABASE_URL`; capture the scheduled function's first run in the Modal dashboard.
10. **Submission form, by 09:30:** the three awards as the booths said (or as 6 says when they did not); the three notes of 2.5, 3.6 and 4.5 with the real figures; the repository link (public only after Valio's answer on its data files). Change the `CLAUDE.md` Status line: Gemini dropped; Modal, Context.dev and Aiven entered.

## 9. Risks
- **A lookup holds the order for up to 40 s** when a product has neither a stored nor a recorded page and the key is deployed (`docs/CONTEXTDEV.md`, limits). The demo set must be recorded (João 4) before the video.
- **Recorded pages are real web text beside generated customer data.** Every card and the note say "not Valio Aimo data"; the Context.dev brief leaves respect for each site's terms to the team.
- **A new schema starts an empty shared trail.** That is wanted: the old trail stays intact under `tta` and the proof is made on the new one.
- **The supplier's SQL view and the Python reader can drift**, and the comparing test is live-only: João 3 before every deploy.
- **Do not chase Modal's bar.** A GPU model built in a hurry on Sunday morning puts the 30% at risk for the weakest of the three chances.
