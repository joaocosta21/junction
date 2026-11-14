# Tech awards: what ran, and what a person must still run

Written Saturday 14 Nov 2026, evening, against commit `c2106fe`. Three awards are entered next to the Valio Aimo challenge: **Context.dev**, **Aiven** and **Modal**. **Gemini is not entered.**

How to read this page:
- "Ran" means it was run and the result is in the repository. "Built, not run" means the code and its offline tests exist and nobody has run it against the outside service.
- No build agent made an outside call tonight. The only outside calls of the evening were 8 Context.dev requests, sent by the orchestrator with the team's approval.
- The public link was last deployed at 13:00 on 14 Nov from commit `8163d5d` (`AIMO/build/STATUS.md`). **Tonight's code is not deployed.** Everything below about signing, the four customers, suggestions, the new rules and the new evidence matcher is true of the repository, not yet of the link.
- No model is served or called by this system as documented: the reader is fixed rules. Nothing here uses a GPU.

## Context.dev

**What it does.** When Valio Aimo's data does not rule out an allergen the buyer excludes, rule P-04 ("a product that may contain an excluded allergen, leaves it undeclared or says nothing about it goes to the dietitian") sends the order to a person. The approval then carries what the manufacturer's own web page says, read through Context.dev's Answers endpoint, under a heading that says it is not Valio Aimo data. A page can add a doubt and never removes one: it changes no status and no verdict, and the person decides. Details: `docs/CONTEXTDEV.md`.

**What ran.**
- 25 requests to Context.dev in all, of the 60 the team approved: 17 before tonight (10 trials by hand, 5 that produced the first recordings, 2 refused with 401 from an early test) and 8 tonight (`scripts/record_evidence.py --demo-set`, Sat 14 Nov, 19:56 to 19:58 Helsinki). The count is the team's log (`AIMO/build/replan/STATUS.md`); the credit figures (1,315 before tonight, 800 tonight) are from the same logs and were not re-read on Context.dev's dashboard.
- 13 recorded pages are in `fixtures/evidence/`. Run through the matcher at this commit, offline: **9 are kept as evidence and 4 are dropped**, each dropped one with its reason in the sentence the approver reads. The table is in `docs/CONTEXTDEV.md`.
- The evidence shows on the shop's approval card and on the older `/approvals` page, in `GET /v1/approvals`, and in the audit trail. In replay, with no key, the recordings answer, so the card is the same on every run.
- `tests/evidence/`: 191 tests, none of which calls Context.dev.

**Built, not run.** The same lookup as a batch over many products on Modal (see Modal below).

**A person must still.** Redeploy so the link carries tonight's 8 recordings and the stricter matcher. Decide whether to raise the 60-request approval before any larger batch. Make the repository reachable: Context.dev's brief asks for "a GitHub repository and a demo", and nothing was pushed tonight.

## Aiven

**What it does.** When `DATABASE_URL` is set, the shared order book and the audit trail (the ones REST and MCP callers write to) are kept in Aiven for PostgreSQL. The database itself refuses to change or remove an audit event, through triggers that fire always. Valio Aimo's view of the trail is an SQL view, and a role that cannot log in holds `SELECT` on that view and nothing else. Details: `docs/AIVEN.md`.

**What ran.**
- The store, the triggers, the two views and the role ran against the Aiven service on the morning of 14 Nov (commit `67f3b00`), and the public link ran on it after the 11:15 deploy (`AIMO/build/STATUS.md`: "Aiven connected (no fall-back)"). That is the earlier log; it was not re-checked tonight.
- Tonight, offline only: Valio Aimo's view was rewritten to show every rule that fired, with the buyer's amounts and allergens masked. `tests/audit/test_sql_view.py` (7 tests) compares the SQL file with the Python reader as text. `tests/audit/test_pinned_hashes.py` (20 tests) pins the hashes of stored events, so a change that would make the trail already in the database unverifiable fails a test first.
- `scripts/aiven_proof.py --dry-run`, run offline: it lists its 8 statements and sends nothing.

**Not run.**
- **The new SQL of Valio Aimo's view was never executed by a database.** The tests that execute it (`tests/store_pg`, 116 tests, the live ones marked `live`) are skipped offline.
- **The proof script was never run against a database.** The supplier's login it needs (`valio_aimo`) was never created.
- The witness that checks the trail's head from the supplier's seat (see Modal) never ran.

**A person must still.** Run the live tests before any deploy with `DATABASE_URL`; create the supplier login; run the proof and paste its output into `docs/AIVEN.md`. Commands: `docs/DEPLOY.md`, "To run".

**Honest limits.** The pages (the shop included) write to an order book in memory per browser, not to Aiven; only REST and MCP callers use the shared book. The gateway's own login owns the tables and could drop a trigger; the hash chain would still show a changed event.

## Modal

**What it does.** Modal hosts the whole gateway (REST, MCP and the pages) as one web function behind one public address, defined in plain Python: the image with pinned libraries, the secret values, a Volume for the data, one container that scales to zero. Details: `docs/DEPLOY.md`.

**What ran.** Three deploys on 14 Nov (09:44, 11:15, 13:00); after the second and the third, `deploy/check.py`, which then had 7 checks, passed all 7 (`AIMO/build/STATUS.md`; not re-checked tonight).

**Built, not run.**
- **The evidence batch as a fan-out** (`deploy/evidence_batch.py`): one function mapped over products, at most 40 at a time, one Context.dev request per call. Only its plain-Python dry run and its tests with a stand-in sender exist. It has never run on Modal.
- **The witness** (`deploy/witness.py`, scheduled hourly from `deploy/modal_app.py`): it reads the head of the audit trail with the supplier's read-only login and checks that the head it noted last time is still in place. It is defined only when `SUPPLIER_DATABASE_URL` is set on the deploying machine. That value has never been set, so the function has never existed on Modal.
- **The redeploy with tonight's code**, with the link's new settings (replay, the demo clock).
- `deploy/check.py` now has 9 checks; the 9 have run only against the app in memory (`tests/deploy/test_check.py`), never against the link.

**Honest limits.** Modal's brief asks for "the most ambitious working AI system built on Modal" and names four things: an open model on a GPU, Sandboxes, fine-tuning, a batch fan-out. This entry serves no model, uses no GPU, no Sandbox and no fine-tuning, and its one fan-out has not run. By the brief's own bar it is a light use of Modal: hosting done carefully.

## Gemini (Google DeepMind)

Not entered. No model is called: the team dropped Gemini on 14 Nov at 17:33, and the fixed-rules reader is the product. The Gemini client and its recordings are still in the repository (`src/tta/agent/gemini.py`, `fixtures/agent/`) as an option a deployer may switch on with a key; see the caution in `docs/DEPLOY.md`.

## Could not be verified from the repository

- Anything about the public link as it answers now: no outside call was made.
- Credits spent and left at Context.dev and Modal.
- How each award is declared (a field of the Junction form, a form of the sponsor, a booth step): the three briefs do not say.
