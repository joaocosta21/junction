# Tech awards: what ran, and what a person must still run

Written Saturday 14 Nov 2026, evening, against commit `c2106fe`; brought up to date on Sunday 15 Nov 2026 at about 03:00 from the code at commit `94b21a5` and the run's log (`AIMO/build/replan/STATUS.md`). No outside service was asked for this update, so "ran" below rests on that log. Three awards are entered next to the Valio Aimo challenge: **Context.dev**, **Aiven** and **Modal**. **Gemini is not entered.**

How to read this page:
- "Ran" means it was run and the result is in the repository. "Built, not run" means the code and its offline tests exist and nobody has run it against the outside service.
- No build agent made an outside call. The outside calls of the night, all by the orchestrator and counted in the log: 8 Context.dev requests; 2 recording calls to Valio's mock (the baking recording); two Modal deploy attempts for a model, which built an image and were refused; calls to Google's Gemini from local gateways (about 4 in one trial on 14 Nov, and the build's measurement of the reader on 15 Nov); and one local server started by mistake with the team's settings, which wrote to the Aiven database and made 2 live calls to Valio's mock (see Aiven).
- The public link was last deployed at 13:00 on 14 Nov from commit `8163d5d` (`AIMO/build/STATUS.md`). Asked at 00:30 on 15 Nov it still ran that code: `/healthz` 200, live mode, `/shop` 404. **The night's code is deployed only once the last step of the run has happened** (`STATUS.md`, row DEEP); the link then answers `/shop`, and `/healthz` says `mode: replay`. Until then, everything below about signing, the four customers, suggestions, the new rules and the new evidence matcher is true of the repository, not of the link.
- Nothing here serves a model or uses a GPU. A sentence may be read by a hosted model when a key is configured; fixed rules check that reading, read in its place when no model answers, and decide what may be ordered (`docs/ASSUMPTIONS.md`, rows "Reader"). `GET /healthz` → `agent_reader` says what reads sentences on the link.

## Context.dev

**What it does.** When Valio Aimo's data does not rule out an allergen the buyer excludes, rule P-04 ("a product that may contain an excluded allergen, leaves it undeclared or says nothing about it goes to the dietitian") sends the order to a person. The approval then carries what the manufacturer's own web page says, read through Context.dev's Answers endpoint, under a heading that says it is not Valio Aimo data. A page can add a doubt and never removes one: it changes no status and no verdict, and the person decides. Details: `docs/CONTEXTDEV.md`.

**What ran.**
- 25 requests to Context.dev in all, of the 60 the team first approved (on 14 Nov at 20:51 João lifted that cap for the batch on Modal, which has not run): 17 before the evening of 14 Nov (10 trials by hand, 5 that produced the first recordings, 2 refused with 401 from an early test) and 8 that evening (`scripts/record_evidence.py --demo-set`, Sat 14 Nov, 19:56 to 19:58 Helsinki). The count is the team's log (`AIMO/build/replan/STATUS.md`); the credit figures (1,315 before that evening, 800 during it) are from the same logs and were not re-read on Context.dev's dashboard.
- 13 recorded pages are in `fixtures/evidence/`. Run through the matcher at this commit, offline: **9 are kept as evidence and 4 are dropped**, each dropped one with its reason in the sentence the approver reads. The table is in `docs/CONTEXTDEV.md`.
- The evidence shows on the shop's approval card (the dietitian's, at the ward and the school), beside the question on the result where the person who orders decides it (the hotel, the bakery), on the older `/approvals` page, in `GET /v1/approvals`, and in the audit trail. In replay, with no key, the recordings answer, so the card is the same on every run.
- `tests/evidence/`: 241 tests, none of which calls Context.dev.

**Built, not run.** The same lookup as a batch over many products on Modal (see Modal below).

**A person must still.** Redeploy so the link carries the 8 recordings of 14 Nov evening and the stricter matcher. Make the repository reachable: Context.dev's brief asks for "a GitHub repository and a demo". The branch `replan-build` was pushed to GitHub on 15 Nov at 00:37 (up to commit `dcc788d`); pushing the later commits and making the repository public are still to do.

## Aiven

**What it does.** When `DATABASE_URL` is set, the shared order book and the audit trail (the ones REST and MCP callers write to) are kept in Aiven for PostgreSQL. The database itself refuses to change or remove an audit event, through triggers that fire always. Valio Aimo's view of the trail is an SQL view, and a role that cannot log in holds `SELECT` on that view and nothing else. Details: `docs/AIVEN.md`.

**What ran.**
- The store, the triggers, the two views and the role ran against the Aiven service on the morning of 14 Nov (commit `67f3b00`), and the public link ran on it after the 11:15 deploy (`AIMO/build/STATUS.md`: "Aiven connected (no fall-back)"). That is the earlier log; it was not re-checked since.
- **By mistake, on 14 Nov at 21:22:** a local server was started with the team's settings and so used the Aiven database for about four minutes. At its start the schema statements ran, among them the rewritten view of Valio Aimo, without error; it stored the four customers' demo standing orders with their synthetic past orders, and one offer. Those rows are in the trail and cannot be removed. Nothing was ordered.
- Offline: Valio Aimo's view was rewritten to show every rule that fired, with the buyer's amounts and allergens masked. `tests/audit/test_sql_view.py` (9 tests) compares the SQL file with the Python reader as text. `tests/audit/test_pinned_hashes.py` (20 tests) pins the hashes of stored events, so a change that would make the trail already in the database unverifiable fails a test first.
- `scripts/aiven_proof.py --dry-run`, run offline: it lists its 8 statements and sends nothing.

**Not run.**
- **The SQL of Valio Aimo's view as it stands now was never executed by a database.** An earlier state of it ran once, by the mistake above; it changed after that (the product of an `evidence.attached` event is masked). The tests that execute it (`tests/store_pg`, 117 tests, the live ones marked `live`) are skipped offline and have not been run since the view was rewritten.
- **The proof script was never run against a database.** The supplier's login it needs (`valio_aimo`) was never created.
- The witness that checks the trail's head from the supplier's seat (see Modal) never ran.

**A person must still.** Run the live tests before any deploy with `DATABASE_URL`; create the supplier login; run the proof and paste its output into `docs/AIVEN.md`. Commands: `docs/DEPLOY.md`, "To run".

**Assumptions and next steps.** The pages (the shop included) write to an order book in memory per browser, not to Aiven; only REST and MCP callers use the shared book. The gateway's own login owns the tables and could drop a trigger; the hash chain would still show a changed event. Next: a gateway login that does not own the tables, and each stored order tied to its audit event (today an order row changed in the database is answered with a valid signature).

## Modal

**What it does.** Modal hosts the whole gateway (REST, MCP and the pages) as one web function behind one public address, defined in plain Python: the image with pinned libraries, the secret values, a Volume for the data, and exactly one container. For the review day that container is kept running with 4,096 MiB (it scaled to zero after 10 idle minutes before, with 1,024 MiB): the pages' order books and the demo signing key live in its memory. It costs some Modal credit while it runs, so the app is to be stopped after the judging. Details: `docs/DEPLOY.md`.

**What ran.** Three deploys on 14 Nov (09:44, 11:15, 13:00); after the second and the third, `deploy/check.py`, which then had 7 checks, passed all 7 (`AIMO/build/STATUS.md`; not re-checked since).

**Built, not run.**
- **The evidence batch as a fan-out** (`deploy/evidence_batch.py`): one function mapped over products, at most 40 at a time, one Context.dev request per call. Only its plain-Python dry run and its tests with a stand-in sender exist. It has never run on Modal.
- **The witness** (`deploy/witness.py`, scheduled hourly from `deploy/modal_app.py`): it reads the head of the audit trail with the supplier's read-only login and checks that the head it noted last time is still in place. It is defined only when `SUPPLIER_DATABASE_URL` is set on the deploying machine. That value has never been set, so the function has never existed on Modal.
- **The redeploy with the night's code**, with the link's new settings (replay, the demo clock, one container kept running): not done when this page was updated (see the top of the page).
- **A model on a Modal GPU** (`deploy/agent_model.py`, an open-weights model behind a key): on 14 Nov at 22:17 the image built and Modal refused the deploy, because the workspace has no payment method for GPU functions. Nothing is deployed and the team decided against the cost.
- `deploy/check.py` now has 10 checks; the 10 have run only against the app in memory (`tests/deploy/test_check.py`), never against the link.

**Assumptions and next steps.** Modal's brief asks for "the most ambitious working AI system built on Modal" and names four things: an open model on a GPU, Sandboxes, fine-tuning, a batch fan-out. This entry serves no model, uses no GPU, no Sandbox and no fine-tuning, and its one fan-out has not run. By the brief's own bar it is a light use of Modal: hosting done carefully. Next: run the fan-out and the witness.

## Gemini (Google DeepMind)

Not entered. The gateway can ask Gemini to read a buyer's sentence when `GEMINI_API_KEY` is set (`src/tta/agent/gemini.py`); the reading is checked against the text, a recording or the fixed rules read when the model does not answer, and no model decides anything. Measured by the build on 15 Nov with a key set, on a local gateway: the brief's own sentence was read by `gemini-3.6-flash`. Whether the link carries a key is the deployer's choice (`docs/DEPLOY.md`) and `GET /healthz` → `agent_reader` reports it.

## Could not be verified from the repository

- Anything about the public link as it answers now: no outside call was made.
- Credits spent and left at Context.dev and Modal.
- How each award is declared (a field of the Junction form, a form of the sponsor, a booth step): the three briefs do not say.
