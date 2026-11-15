# Tech awards: what ran, and what a person must still run

Brought up to date on Sunday 15 Nov 2026 at 04:05 Helsinki, after the night's runs against Modal, Aiven and Context.dev. Three awards are entered next to the Valio Aimo challenge: **Context.dev**, **Aiven** and **Modal**. **Gemini is not entered.** Times are Helsinki, from the machine that ran the commands.

How to read this page:
- "Ran" means it was run against the sponsor's service and its output is kept: in `docs/CONTEXTDEV.md`, `docs/AIVEN.md`, `fixtures/evidence/` or below. "Built, not run" means the code and its offline tests exist and nobody has run it against the outside service.
- The public link, https://joaocostared--trusted-trade-agents.us-east.modal.run, was deployed on 15 Nov at 03:35 from the night's code: replay, the demo clock, no model, the Aiven database, one container kept running. `deploy/check.py` passed 10 of 10 then (`AIMO/build/replan/STATUS.md`). It was not deployed again after the runs below, so it does not carry the 79 recordings of 15 Nov.
- Nothing here serves a model or uses a GPU. A sentence may be read by a hosted model when a key is configured; fixed rules check that reading, read in its place when no model answers, and decide what may be ordered. `GET /healthz` → `agent_reader` says what reads sentences on the link: fixed rules.

## What ran on 15 Nov, in one table

| When | What | Result |
|---|---|---|
| 03:45–03:47 | Aiven: the 68 live tests of `tests/store_pg`, each in a schema of its own | 68 passed, 0 failed; nothing left behind |
| 03:47 | Aiven: the proof on the deployed schema `tta` | `UPDATE` and `DELETE` of the audit table refused with `TA001` for the gateway's own login; the supplier's role reads its view (33 events) and is refused everything else with `42501` |
| 03:49 | Context.dev: the two demo products without a page (`469363`, `469386`) | 2 answers, 2 pages; 1 kept, 1 dropped by a fault of our matcher |
| 03:51 | Modal + Context.dev: the evidence batch, first try, 77 products | failed in every container before a request left (a library missing from the image); 0 answers, 0 credits |
| 03:52–03:54 | Modal + Context.dev: the evidence batch, 1 then 76 products | 77 answers; 76 of them in 58 seconds with 40 containers at once; 54 pages, 19 kept, 35 dropped with the reason, 23 without a page |
| 03:57 | The witness's code, once by hand on the team's machine, against the deployed view | "First run: the head was noted (33 events, last number 33, hash c5cfc61f3895…)", then "The head is the one noted last time" |

## Context.dev

**What it does.** When Valio Aimo's data does not rule out an allergen the buyer excludes, rule P-04 ("a product that may contain an excluded allergen, leaves it undeclared or says nothing about it goes to the dietitian") sends the order to a person. The approval then carries what the manufacturer's own web page says, read through Context.dev's Answers endpoint, under a heading that says it is not Valio Aimo data. A page can add a doubt and never removes one: it changes no status and no verdict, and the person decides. Details, and the note the brief asks for: `docs/CONTEXTDEV.md`.

**What ran.**
- **104 requests in all** (10,400 credits by our count; the dashboard was not read): 25 through 14 Nov, 79 on 15 Nov.
- **92 recorded answers** in `fixtures/evidence/`, one per product. Read by the matcher as the code stands: **29 shown as evidence, 40 dropped with the reason in a sentence, 23 with no page.** A sample of 92 products, not a catalog figure.
- **On 15 Nov, every product of the demo recording whose data holds no allergen statement was asked:** 79 hold none; 2 had a page since 14 Nov; the other 77 went out as a fan-out on Modal. Of the 36 with a brand, 19 pages are shown, 15 dropped, 2 not found. Of the 41 without a brand, none can be shown (the first check needs a brand): 4,100 credits that bought a figure and no evidence.
- **The demo's own set is complete:** `469363` and `469386` have an answer. `469386` is shown (arla.fi: contains milk, lactose-free). `469363` is dropped for a wrong reason (below).
- The evidence shows on the shop's approval card (the dietitian's, at the ward and the school), beside the question on the result where the person who orders decides it (the hotel, the bakery), on the older `/approvals` page, in `GET /v1/approvals`, and in the audit trail. In replay, with no key, the recordings answer, so the card is the same on every run. On the public link today: the 13 recordings of 14 Nov.
- `tests/evidence/`: 241 tests, none of which calls Context.dev.

**Found by the run, not corrected.**
- **The matcher reads "Semi skimmed" as fat-free** (`src/tta/evidence/matching.py`, the mark `fat-free` matches the word "skimmed"). So the page of `469363`, Arla's semi-skimmed lactose-free UHT milk drink, which is that product, is dropped with "the product asked for is fat-free; the page does not say fat-free". With "skimmed" not read after "semi " the page is kept and no other of the 92 recordings reads differently (checked in memory; the file was not changed).
- **Four tests of `tests/evidence` pin the 13 files of 14 Nov** and fail with 92: three in `test_record_script.py`, one in `test_recordings.py`. No behaviour is wrong; the pins are.
- **The count file overstates:** `var/evidence/request-count.json` reads 181 and 104 requests were sent. The failed fan-out counted its 77 before sending.

**A person must still.** Correct the matcher and the four pins, then deploy, so the link carries the 79 recordings. Make the repository reachable: Context.dev's brief asks for "a GitHub repository and a demo".

## Aiven

**What it does.** When `DATABASE_URL` is set, the shared order book and the audit trail (the ones REST and MCP callers write to) are kept in Aiven for PostgreSQL. The database itself refuses to change or remove an audit event, through triggers that fire always. Valio Aimo's view of the trail is an SQL view, and a role that cannot log in holds `SELECT` on that view and nothing else. Details, with the proof's whole output: `docs/AIVEN.md`.

**What ran.**
- **The public link runs on it** (deploy of 15 Nov, 03:35): `/healthz` → `store.kind: postgresql`. Its audit head, 33 events ending in `c5cfc61f…a813e3`, is what the database answers. 26 of the 33 events are older than the container that serves the link.
- **The 68 live tests, 15 Nov 03:45: 68 passed.** Tonight's SQL, Valio Aimo's rewritten view included, compared on the service with what `tta.audit` shows each reader; the triggers under `UPDATE`, `DELETE`, `TRUNCATE`, an upsert and `session_replication_role = replica`; a supplier login that reads its view and is refused six other relations and two writes; the whole offer → order → approval flow, found again by a second gateway on the same database.
- **The proof on the deployed schema, 15 Nov 03:47.** With the gateway's own login, which owns the table:
  - `UPDATE tta.audit_events SET hash = hash WHERE false` → `SQLSTATE TA001, audit_events is append-only: UPDATE is refused, an event cannot be changed or removed`
  - `DELETE FROM tta.audit_events WHERE false` → `SQLSTATE TA001, audit_events is append-only: DELETE is refused, an event cannot be changed or removed`
  - both triggers read `A` (fire always).
  With the rights of Valio Aimo's role (`SET LOCAL ROLE tta_supplier`):
  - `SELECT count(*), max(seq) FROM tta.audit_supplier` → `33 | 33`
  - `SELECT 1 FROM` `tta.audit_events`, `tta.audit_buyer`, `tta.orders`, `tta.offers`, `tta.approvals` → each `SQLSTATE 42501, permission denied`
  - the same `UPDATE` and `DELETE` → `SQLSTATE 42501, permission denied for table audit_events`
  - the role's grants: `tta | audit_supplier | SELECT`, and nothing else; it cannot log in.
- **By mistake, on 14 Nov at 21:22:** a local server was started with the team's settings and wrote 9 events (four demo standing orders and one offer) into the trail. They cannot be removed; nothing was ordered.

**Not run.**
- **`scripts/aiven_proof.py`**, the one-command form of the proof: it needs the supplier's own login, which was never created. A login is a password someone must hold, so it is a person's step.
- **The witness on Modal** (see Modal).

**A person must still.** Create the supplier's login and set `SUPPLIER_DATABASE_URL` (the command is in `docs/DEPLOY.md`, "To run", step 7), then run `scripts/aiven_proof.py`.

**Assumptions and next steps.** The pages (the shop included) write to an order book in memory per browser, not to Aiven; only REST and MCP callers use the shared book. The gateway's own login owns the tables and could drop a trigger; the hash chain would still show a changed event. Next: a gateway login that does not own the tables, and each stored order tied to its audit event (today an order row changed in the database is answered with a valid signature).

## Modal

**What it does.** Modal hosts the whole gateway (REST, MCP and the pages) as one web function behind one public address, defined in plain Python: the image with pinned libraries, the secret values, a Volume for the data, and exactly one container, kept running for the review day with 4,096 MiB. It costs some Modal credit while it runs, so the app is to be stopped after the judging. Details: `docs/DEPLOY.md`.

**What ran.**
- **The public link**, deployed four times (14 Nov 09:44, 11:15, 13:00; 15 Nov 03:35); `deploy/check.py` passed 10 of 10 after the last (`AIMO/build/replan/STATUS.md`).
- **A batch fan-out, 15 Nov 03:53** (`deploy/evidence_batch.py`): one function mapped over 76 products, one HTTPS request to Context.dev per call, no call retried. **76 answers in 58 seconds from `modal run` to exit; 40 containers alive at once**, the cap we set to stay under Context.dev's 50 concurrent requests (6, 12, 20, 29, then 40, counted with `modal container list` about every 2 seconds). One product ran alone just before, to check the image. The link's own container was not touched: it stayed at 1 throughout. CPU only; no GPU, no model.
- **The first try failed, and that is in the record:** at 03:51 all 77 calls stopped at `ModuleNotFoundError: No module named 'yaml'`, 19 seconds after the start, with 28 containers up. The batch image pinned three libraries and the code it runs needs a fourth. One line fixed it (`pyyaml==6.0.3` in `PINNED`, the gateway's own pin; `tests/deploy/test_evidence_batch.py` passes). No request had left.

**Built, not run on Modal.**
- **The witness** (`deploy/witness.py`, scheduled hourly from `deploy/modal_app.py`): it reads the head of the audit trail with the supplier's read-only login and checks that the head it noted last time is still in place. It is defined only when `SUPPLIER_DATABASE_URL` is set in the shell that deploys. That login was never created, so the function has never existed on Modal. Its code ran once by hand on the team's machine against the deployed view (`docs/AIVEN.md`, section 5).
- **A model on a Modal GPU** (`deploy/agent_model.py`, an open-weights model behind a key): on 14 Nov at 22:17 the image built and Modal refused the deploy, because the workspace has no payment method for GPU functions. Nothing is deployed and the team decided against the cost.

**Assumptions and next steps.** Modal's brief asks for "the most ambitious working AI system built on Modal" and names four things: an open model on a GPU, Sandboxes, fine-tuning, a batch fan-out. This entry has one of the four, at a small size: a fan-out of 77 web requests on CPU. It serves no model and uses no GPU, no Sandbox and no fine-tuning. By the brief's own bar it is a light use of Modal: hosting done carefully, and one batch that ran. Next: the witness, once the supplier's login exists; the reader as an open model on a GPU.

## Gemini (Google DeepMind)

Not entered. The gateway can ask Gemini to read a buyer's sentence when `GEMINI_API_KEY` is set (`src/tta/agent/gemini.py`); the reading is checked against the text, a recording or the fixed rules read when the model does not answer, and no model decides anything. The public link carries no model key: `GET /healthz` → `agent_reader.kind` is `fixed_rules`.

## Could not be verified from here

- Credits left at Context.dev and at Modal: no dashboard was read.
- How each award is declared (a field of the Junction form, a form of the sponsor, a booth step): the three briefs do not say.
