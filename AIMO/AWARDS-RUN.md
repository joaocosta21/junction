# AWARDS-RUN — what ran for Modal, Context.dev and Aiven on Sunday 15 Nov, 03:45 to 04:00

Lane AWARDS. Times are Helsinki, from the machine. Outside calls of this lane: 79 Context.dev requests (7,900 credits), three `modal run` of the batch app, SQL to the Aiven service (68 live tests in schemas of their own, and reads plus two refused changes on the schema `tta`), three reads of the link's `/healthz`. **No deploy: the public link is as it was at 03:35.** Whole outputs: `docs/AIVEN.md` sections 4 and 5, `docs/CONTEXTDEV.md` "The 79 answers of 15 Nov", `docs/AWARDS.md`.

## Before anything else: three things the run left that someone must decide

1. **A fault in the matcher, on a demo product.** `src/tta/evidence/matching.py:70`, mark `fat-free`: `(?<![\w-])skimmed\b` also matches "Semi skimmed". The new recording of `469363` (Arla semi-skimmed lactose-free UHT, the school's substitute milk) is therefore dropped with a false reason: "the product asked for is fat-free; the page does not say fat-free". With `(?<![\w-])(?<!semi )skimmed\b` the page is kept ("contains Maito; free from laktoositon") and no other of the 92 recordings reads differently (checked in memory). Not changed: it is in `src/`.
2. **Any deploy from this tree now uploads the 79 new recordings**, `469363` with its false sentence among them. Before the matcher is corrected, a deploy makes the school's card for that milk worse than "nothing was looked up". With it corrected, a deploy puts 30 pages on the link where 9 are now.
3. **Four tests of `tests/evidence` are red, all pins on the old 13 files** (237 pass; `tests/deploy` 132 pass):
   - `test_recordings.py::test_every_recording_sent_names_only`: asserts the file list equals its 13. Its own checks hold for all 92 files (checked by hand). Re-pin: the 13 are a subset.
   - `test_record_script.py`: the two `test_the_demo_set_is_measured_in_replay…` and `test_an_offer_of_the_demo_set_that_cannot_be_built…`: exit 7 ("the total is spent"), because 92 recordings + 12 = 104 is over the default total of 60. Re-pin: pass `--total-cap`, the line becomes "104 used of …(92 recordings …)", and `NOT_YET_RECORDED` is empty.

One code line was changed, inside `deploy/`: `deploy/evidence_batch.py`, `PINNED` gained `"pyyaml==6.0.3"` (the gateway's own pin). Without it every call of the fan-out died on `import yaml`. `tests/deploy/test_evidence_batch.py`: 15 passed.

## Modal — "the most ambitious working AI system built on Modal" (GPU model · Sandboxes · fine-tuning · batch fan-out)

**Now shown: one of the four, small.** `.venv/bin/modal run -q deploy/evidence_batch.py --limit 76 --total-cap 181`:
```
Asking for 76 product(s), at most 40 at a time, 7600 credits.
Products asked                                               76
Answers received and stored                                  76
A page was found                                             53
The page names this product (shown as evidence)              18
Dropped: another product's page, or it could not be checked  35
Evidence that names an allergen (contains or may contain)    2
Credits for the answers received                             7600
```
58 seconds from start to exit; containers alive, read about every 2 s: 6, 12, 20, 29, then 40 to the end; the link's own container stayed at 1. One product ran alone before it (77 in all: 54 pages, 19 kept). The first try (03:51, 77 calls) failed on the missing library before any request left: 0 credits.

**Not run: the hourly witness.** `SUPPLIER_DATABASE_URL` is not set (asked of `tta.config` and the shell), so the function does not exist on Modal. Its code ran once by hand on this machine against the deployed view: "First run: the head was noted (33 events, last number 33, hash c5cfc61f3895…)", then "The head is the one noted last time".

**We have nothing of:** a model on a GPU · Sandboxes · fine-tuning · any model running on Modal at all.

**Chance: low.** A fan-out of 77 CPU web requests is a real use and a small one; a team that serves a model on a Modal GPU meets the brief better. It moved from "hosting only" to "hosting and one batch that ran".

## Context.dev — "one endpoint in its core flow"; "the data must visibly drive something in the demo"; a repository, a demo, a note

**Now shown.** 104 requests, 92 products asked once each: **29 shown as evidence (12 on the brand owner's own site), 40 dropped with the reason, 23 without a page.** Every product of the demo recording with no allergen statement (79) has been asked. The demo's own set is complete: `scripts/record_evidence.py --ids 469363 469386 --limit 2`:
```
469363: No evidence was found on the web for product 469363: the page found (“Arla Maitoa Suomesta Laktoositon kevytmaitojuoma (UHT) 1 l”) is not shown to be this product and was dropped: the product asked for is fat-free; the page does not say fat-free.
469386: The manufacturer's page “Arla Maitoa Suomesta Laktoositon rasvaton maitojuoma Suomi 1 l” on arla.fi says: contains “Maito”; free from “Laktoositon”.
```
**My decision on the cap, and its cost.** I asked all 77, past the 60, because João approved that set on 14 Nov and a whole set is a cleaner claim than the first 35. 41 of the 77 have no brand, and none of those can be shown: 4,100 credits bought a figure and no evidence. Of the 36 with a brand: 19 kept, 15 dropped (several on a spelling that differs by a letter or a space, such as "ulkofile" against "ulkofilee"; none checked by hand), 2 not found.

**We have nothing of:** monitors or webhooks (their most distinctive feature) · a second endpoint · web data that changes what the system decides (ours informs a person) · a lookup made live on the public link (it carries no key, by choice).

**Chance: fair, the best of the three.** Both minimum requirements are met on the public link, the extraction is narrow and every rejection has its reason, and the lead judge is on site. Against: "core flow" is arguable, since a page never changes a verdict.

## Aiven — "a meaningful part of the project, and demonstrate what it enables"

**Now shown, on the live database:**
```
UPDATE tta.audit_events SET hash = hash WHERE false;
   -> refused: SQLSTATE TA001, audit_events is append-only: UPDATE is refused, an event cannot be changed or removed
DELETE FROM tta.audit_events WHERE false;
   -> refused: SQLSTATE TA001, audit_events is append-only: DELETE is refused, an event cannot be changed or removed
SELECT count(*), max(seq) FROM tta.audit_supplier;   [as role tta_supplier]
   -> 33 | 33
SELECT 1 FROM tta.audit_events LIMIT 1;   [as role tta_supplier]
   -> refused: SQLSTATE 42501, permission denied for table audit_events
```
The first two are the gateway's own login, which owns the table. The role is also refused `audit_buyer`, `orders`, `offers`, `approvals` and both changes; it holds one grant, `SELECT` on its view. The head (33 events, `c5cfc61f…`) is the one `/healthz` shows; 26 of the 33 events are older than the running container. **`.venv/bin/python -m pytest tests/store_pg -m live`: 68 passed** (run one file at a time), tonight's view included, nothing left behind.

**Not run: `scripts/aiven_proof.py`** (it needs the supplier's own login, which does not exist; I did not create a login or choose a password).

**We have nothing of:** a second Aiven service (Kafka, ClickHouse, Valkey, Runtime) · the pages' own order books in Aiven (only REST and MCP callers write there) · a page on the link that shows the trail from the database.

**Chance: fair.** One service, used for the reason the main challenge scores at 20%, and now with a proof a mentor can read in a minute. Against: it is one PostgreSQL; a team with several services working together shows more of Aiven.

## For the deck, ready to paste (pages 12 to 14)

**Page 12, the figure:** "29 of 92" · "products show a web page as evidence; 40 pages rejected, each with its reason; 23 had no page (92 recorded answers, 104 requests sent)". After the matcher is corrected: 30 and 39.
**Page 12, a line to add:** "Every product of the demo recording with no allergen statement was looked up: 79, of which 77 in one batch on Modal."
**Page 12, the rest:** nothing to change. Until a deploy carries the new recordings, the link shows the 13 pages of 14 Nov, so say the 92 as "recorded", not as "on the demo link".

**Page 13, point 01:** "Aiven for PostgreSQL refuses to change or delete an audit event, for the gateway's own login too: tried on the live trail on 15 Nov, refused with our error TA001"
**Page 13, point 04:** "A database role that can read that view and nothing else: on the live trail it read 33 events and was refused every table behind them. Next step: Valio Aimo's own login"
**Page 13, the strip:** "Ran on 15 Nov: the public link on Aiven; 68 tests against the live service, all passed; 26 of the trail's 33 events are older than the running container. 20 tests pin the stored hashes, so a code change cannot break the existing log."

**Page 14, point 04:** "A script checks the published link after every deploy, from service health to an offer, an order, the log and MCP: all 10 checks passed on 15 Nov"
**Page 14, point 05:** "Ran on 15 Nov: a batch of 76 manufacturer-page lookups, fanned out over 40 containers, done in 58 seconds. Built, not yet run on Modal: an hourly witness of the audit log"
**Page 14, the figure (optional):** "40" · "containers at once for one batch: 76 web lookups in 58 seconds"

## What João must do himself

1. **Decide the deploy** (before 09:00; it empties the pages' order books): after the matcher line and the four pins, `.venv/bin/modal deploy --strategy recreate deploy/modal_app.py`, then once `.venv/bin/python deploy/check.py https://joaocostared--trusted-trade-agents.us-east.modal.run --mode replay`.
2. **The supplier's login, for the witness and the one-command proof** (about 5 minutes; it is a password he then holds):
   ```
   .venv/bin/python -c "import getpass, psycopg; from psycopg import sql; from tta.config import get_settings; pw = getpass.getpass('New password for valio_aimo: '); c = psycopg.connect(get_settings().database_url.get_secret_value(), autocommit=True); c.execute(sql.SQL('CREATE ROLE valio_aimo LOGIN PASSWORD {} IN ROLE tta_supplier').format(sql.Literal(pw))); print('created')"
   export SUPPLIER_DATABASE_URL='<the Aiven service URI, with user valio_aimo and that password>'
   .venv/bin/python scripts/aiven_proof.py
   ```
   Then the deploy and the check of step 1 from the same shell (the deploy reads this value from the shell, not from `.env`; it must not print "SUPPLIER_DATABASE_URL is not set"), and one run by hand: `.venv/bin/python -c "import modal; print(modal.Function.from_name('trusted-trade-agents', 'witness_audit_head').remote())"`. None of step 2 was run: the witness's deploy has only its offline tests. Only after it ran may page 14 say "an hourly witness of the audit log, scheduled on Modal".
3. **Read the balance on Context.dev's dashboard** (expected about 40,985; the answers' own figures disagree under 40 at once) and **make the repository public**: their brief asks for it.
4. **At the booths:** Context.dev (Beer van der Drift, lead judge): show the hotel's or the dietitian's card and ask whether evidence for the person who signs counts as "core flow". Aiven: show section 4 of `docs/AIVEN.md`.
5. **After the judging:** `.venv/bin/modal app stop trusted-trade-agents` (one container is kept running and costs credit).

## Left as it is, for whoever owns the file

- `var/evidence/request-count.json` reads 181; 104 requests were sent (the failed fan-out counted 77 before sending). Every run of the two recording scripts now needs `--total-cap`.
- `docs/DEPLOY.md` still says the night's code is not deployed and that the batch, the live tests and the proof never ran. `AIMO/SUBMISSION.md` line 128 still says "13 pages recorded, 9 kept as evidence, 4 dropped": now 92, 29 and 40, with 23 without a page.
- `CLAUDE.md`, Status: nothing to change.
