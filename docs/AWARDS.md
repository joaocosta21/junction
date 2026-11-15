# Technology partners: what ran on Modal, Context.dev and Aiven

For a reader from Modal, Context.dev or Aiven. State on Sunday 15 Nov 2026, at the final code (commit `b567e5f`). Three partner awards are entered next to the Valio Aimo challenge: **Context.dev**, **Aiven** and **Modal**. Times are Helsinki, from the machine that ran the commands.

How to read this page:
- **"Ran"** means it was run against the partner's service and its output is kept: in `docs/CONTEXTDEV.md`, `docs/AIVEN.md`, `fixtures/evidence/` or below. **"Built, not run"** means the code and its offline tests exist and it was never run against the outside service. Each partner's section ends with those, under "Next steps".
- **The public link**, https://joaocostared--trusted-trade-agents.us-east.modal.run, runs the final code: replay mode at a demo clock, one container kept running. `deploy/check.py` passed 10 of 10 checks against it after the last deploy (`docs/DEPLOY.md`).
- **No model runs anywhere in this entry, and no GPU is used.** Fixed rules read a buyer's sentence and decide what may be ordered. A model reader exists as an option and is off: `GET /healthz` → `agent_reader` says what reads sentences on the link, and it says fixed rules.
- **Figures about products are from recordings**, not from Valio Aimo's whole catalog of 17,546 products: the demo replays recorded price and availability answers for 1,163 products, of which the capture `2026-11-14-demo` holds 769.

## What ran, in one table

| When | What | Result |
|---|---|---|
| 14 Nov | Context.dev: 13 products with an allergen doubt | 13 answers recorded; 9 shown as evidence, 4 rejected with the reason |
| 14 Nov 09:44, 11:15, 13:00; 15 Nov 03:35 | Modal: four deploys of the gateway | The link answered; `deploy/check.py` passed after the fourth (10 of 10) |
| 15 Nov 03:45–03:47 | Aiven: the 68 live tests of `tests/store_pg`, each in a schema of its own | 68 passed, 0 failed; nothing left behind |
| 15 Nov 03:47 | Aiven: the proof on the deployed schema `tta` | `UPDATE` and `DELETE` of the audit table refused with `TA001` for the gateway's own login; the supplier's role reads its view and is refused everything else with `42501` |
| 15 Nov 03:49 | Context.dev: the two demo products without a recorded page (`469363`, `469386`) | 2 answers, 2 pages, both shown as evidence as the code stands |
| 15 Nov 03:51 | Modal + Context.dev: the evidence batch, first try, 77 products | Failed in every container before a request left (a library missing from the image); 0 answers, 0 credits |
| 15 Nov 03:52–03:54 | Modal + Context.dev: the evidence batch, 1 product alone, then 76 as a fan-out | 77 answers; the 76 in 58 seconds with 40 containers at the peak; 19 shown as evidence, 35 rejected with the reason, 23 without a page |
| 15 Nov 03:57 | The witness's code, once by hand on the team's machine, against the deployed view | "First run: the head was noted", then "The head is the one noted last time" |
| 15 Nov, about 04:30 | Modal: the fifth deploy, from the final code `b567e5f` | `deploy/check.py`: 10 of 10 passed; the link carries the 92 recorded answers |

## Context.dev

**What it does.** When Valio Aimo's data does not rule out an allergen the buyer excludes, rule P-04 ("a product that may contain an excluded allergen, leaves it undeclared or says nothing about it goes to the dietitian") sends the order to a person. That person then sees what the product's web page says, read through Context.dev's Answers endpoint into our own JSON schema of seven fields, under a heading that says it is not Valio Aimo data. A page can add a doubt and never removes one: it changes no status and no verdict, and the person decides. Details, and the note the brief asks for: `docs/CONTEXTDEV.md`.

**What ran.**
- **92 recorded answers** in `fixtures/evidence/`, one per product: 13 of 14 Nov, 79 of 15 Nov. Read by the matcher as the code stands (`src/tta/evidence/`):
  - **30 shown as evidence.** 13 are on a host we list as the brand owner's and are called "the manufacturer's page"; 17 are on another host and are called "a web page whose owner was not checked".
  - **39 rejected, each with its reason in a sentence:** 19 because the product has no brand in Valio Aimo's data, so no page can be shown to be its maker's; 8 because the page's product name says words the product's does not; 5 for a mark the page and the product do not share (organic, UHT); 3 because the page does not show the brand; 1 each for a percentage, a pack size, too little of the name, and an answer that names no page it read.
  - **23 with no page.**
  - This is a sample of 92 products, not a catalog figure.
- **On 15 Nov every product of the capture `2026-11-14-demo` (769 products) whose data holds no allergen statement was asked: 79.** 2 by the recording script, 77 on Modal (1 alone, then 76 as a fan-out). Of the 36 of the 77 with a brand: 19 shown, 15 rejected, 2 not found. Of the 41 without a brand none can be shown, because the first check needs a brand.
- **The demo's own set is complete.** `469386` is shown (arla.fi: contains milk, lactose-free). `469363`, Arla's semi-skimmed lactose-free UHT milk drink, was first rejected by a fault of our matcher, which read "Semi skimmed" as fat-free; the fault was corrected in `b567e5f` and the page is shown. No other of the 92 answers reads differently for that change.
- **Requests.** By the team's own log 104 requests were sent in all: the 92 recorded answers and 12 that left no recording (10 early trials by hand, 2 refused with 401). Each answer's own metadata says 100 credits. Context.dev's dashboard was not read.
- `tests/evidence/`: none of its tests calls Context.dev.

**Where to see it.**
- On the public link, `/shop`: as the hotel, "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk, strict rule"; as the school, "20 litres of almond drink by Monday" (`docs/DEMO.md`, scenarios 4a and 4b). The page's text is beside the question on the result where the person who orders decides (the hotel, the bakery), and on the dietitian's approval card (the ward, the school).
- Over REST: `GET /v1/approvals` → `evidence[]`; in the audit trail, the event `evidence.attached`.
- The link holds no Context.dev key, by choice: in replay the recorded answers are read, so the card is the same on every run and no lookup is made during the demo.
- Code: `src/tta/evidence/` (`answers.py` the request, `reading.py` and `matching.py` the checks). The recording script: `scripts/record_evidence.py`.

**Next steps.** Not built: monitors or webhooks, a second endpoint, a lookup made live on the public link. A page informs the person who signs; it does not change what the gateway decides. The list of hosts treated as a brand owner's is ours and was not verified with the brands.

## Aiven

**What it does.** When `DATABASE_URL` is set, the shared order book and the audit trail, the ones REST and MCP callers write to, are kept in Aiven for PostgreSQL. The database itself refuses to change or remove an audit event, through triggers that fire always. Valio Aimo's view of the trail is an SQL view, and a role that cannot log in holds `SELECT` on that view and nothing else. Details, with the proof's whole output: `docs/AIVEN.md`.

**What ran.**
- **The public link runs on it:** `/healthz` → `store.kind: postgresql`, and the audit head it shows is what the database answers. The trail outlived the container: on 15 Nov it held events older than the container serving the link.
- **The 68 live tests, 15 Nov 03:45: 68 passed**, each in a schema of its own. The SQL of the views, Valio Aimo's included, compared on the service with what `tta.audit` shows each reader; the triggers under `UPDATE`, `DELETE`, `TRUNCATE`, an upsert and `session_replication_role = replica`; a supplier login that reads its view and is refused six other relations and two writes; the whole offer → order → approval flow, found again by a second gateway on the same database.
- **The proof on the deployed schema, 15 Nov 03:47.** With the gateway's own login, which owns the table:
  - `UPDATE tta.audit_events SET hash = hash WHERE false` → `SQLSTATE TA001, audit_events is append-only: UPDATE is refused, an event cannot be changed or removed`
  - `DELETE FROM tta.audit_events WHERE false` → `SQLSTATE TA001, audit_events is append-only: DELETE is refused, an event cannot be changed or removed`
  - both triggers read `A` (fire always).
  With the rights of Valio Aimo's role (`SET LOCAL ROLE tta_supplier`):
  - `SELECT count(*), max(seq) FROM tta.audit_supplier` → answered (the figures of that minute are in `docs/AIVEN.md`)
  - `SELECT 1 FROM` `tta.audit_events`, `tta.audit_buyer`, `tta.orders`, `tta.offers`, `tta.approvals` → each `SQLSTATE 42501, permission denied`
  - the same `UPDATE` and `DELETE` → `SQLSTATE 42501, permission denied for table audit_events`
  - the role's grants: `tta | audit_supplier | SELECT`, and nothing else; it cannot log in.
- **By mistake, on 14 Nov at 21:22:** a local server was started with the team's settings and wrote 9 events (four demo standing orders and one offer) into the trail. They cannot be removed; nothing was ordered.

**Where to see it.** `docs/AIVEN.md`, section 4, for the proof. On the link: `GET /healthz` → `store.kind` and `audit_head`. The SQL: `src/tta/store/sql/002_audit_append_only.sql`, `003_reader_views.sql`, `004_supplier_role.sql`. The live tests: `tests/store_pg/` (skipped without a PostgreSQL).

**Assumptions.**
- **The shop page does not write to Aiven.** `/shop` keeps each browser's order book in the container's memory. Only REST and MCP callers write to the shared book and trail.
- The gateway's own login owns the tables and could drop a trigger; the hash chain would still show a changed event.
- The supplier's rights were taken with `SET LOCAL ROLE` by the gateway's login. No login for Valio Aimo exists.

**Next steps.**
- **Built, not run: `scripts/aiven_proof.py`**, the one-command form of the proof. It needs the supplier's own login, which was not created. The commands are in `docs/DEPLOY.md`, "Next steps: built, not run".
- **Built, not run on Modal: the scheduled witness** (see Modal).
- Not built: a gateway login that does not own the tables; each stored order tied to its audit event (today an order row changed in the database is answered with a valid signature); the pages' order books in the database.

## Modal

**What it does.** Modal hosts the whole gateway (REST, MCP and the pages) as one web function behind one public address, defined in plain Python: the image with pinned libraries, the secret values, a Volume for the data, and exactly one container, kept running for the review day with 4,096 MiB. Details: `docs/DEPLOY.md`.

**What ran.**
- **The public link**, deployed five times (14 Nov 09:44, 11:15, 13:00; 15 Nov 03:35; 15 Nov about 04:30 from the final code `b567e5f`). `deploy/check.py` passed 10 of 10 after the last: health, page, offer, order, audit trail, MCP refused without a token, MCP tools, a foreign origin refused, the API catalog, the signing key.
- **A batch fan-out, 15 Nov 03:53** (`deploy/evidence_batch.py`): one function mapped over 76 products, one HTTPS request to Context.dev per call, no call retried. **76 answers in 58 seconds from `modal run` to exit; 40 containers at the peak**, the cap we set to stay under Context.dev's 50 concurrent requests (6, 12, 20, 29, then 40, counted with `modal container list` about every 2 seconds). One product ran alone just before, to check the image. The link's own container was not touched: it stayed at 1 throughout. CPU only.
- **The first try failed, and that is in the record:** at 03:51 all 77 calls stopped at `ModuleNotFoundError: No module named 'yaml'`, 19 seconds after the start, with 28 containers up. The batch image pinned three libraries and the code it runs needs a fourth. One line fixed it (`pyyaml==6.0.3` in `PINNED`, the gateway's own pin; `tests/deploy/test_evidence_batch.py` passes). No request had left.

**Where to see it.** The link itself. `deploy/modal_app.py` (the app, its image, Secret, Volume and limits), `deploy/check.py` (the ten checks), `deploy/evidence_batch.py` (the fan-out), `tests/deploy/` (offline tests; none calls Modal).

**Assumptions.** Modal's brief asks for "the most ambitious working AI system built on Modal" and names four things: an open model on a GPU, Sandboxes, fine-tuning, a batch fan-out. This entry has one of the four, at a small size: a fan-out of 76 web requests on CPU. It serves no model and uses no GPU, no Sandbox and no fine-tuning. By the brief's own bar it is a light use of Modal: hosting done carefully, and one batch that ran. The one container costs Modal credit while it runs, so the app is to be stopped after the judging.

**Next steps.**
- **Built, not run on Modal: the witness** (`deploy/witness.py`, scheduled hourly from `deploy/modal_app.py`). It reads the head of the audit trail with the supplier's read-only login and checks that the head it noted last time is still in place. It is defined only when `SUPPLIER_DATABASE_URL` is set in the shell that deploys. That login was not created, so the function never existed on Modal. Its code ran once by hand on the team's machine against the deployed view (`docs/AIVEN.md`, section 5).
- **Built, not deployed: a model on a Modal GPU** (`deploy/agent_model.py`, an open-weights model as an optional reader of sentences). On 14 Nov at 22:17 the image built and Modal refused the deploy, because the workspace has no payment method for GPU functions. Nothing is deployed and the team decided against the cost.

## The optional model reader (no award entered)

The gateway can ask a hosted model to read a buyer's sentence when a key is configured (`src/tta/agent/gemini.py`, `GEMINI_API_KEY`); the reading is checked against the text, a recording or the fixed rules read when no model answers, and no model decides anything. It is off: the public link carries no model key, and `GET /healthz` → `agent_reader.kind` is `fixed_rules`. Google's Gemini award is not entered.

## Not verified

- Credits left at Context.dev and at Modal: no dashboard was read.
- The request counter on the team's machine (`var/evidence/request-count.json`, not in the repository) overstates: the failed first try of the fan-out counted its 77 requests before sending any.
