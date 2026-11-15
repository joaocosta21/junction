# Deployment on Modal

The public demo of the gateway runs as one Modal app. `deploy/modal_app.py` defines it and `deploy/check.py` checks it after a deploy. Tests: `tests/deploy/` (132 tests, none of which calls Modal or the link).

**State on Sunday 15 Nov 2026.** The public link, https://joaocostared--trusted-trade-agents.us-east.modal.run, runs the final code, commit `b567e5f`: replay mode at the demo clock, no model key, one container kept running. The order book and audit trail that REST and MCP callers write to are in Aiven for PostgreSQL; the shop page keeps each browser's order book in the container's memory. It was deployed five times: on 14 Nov at 09:44, 11:15 and 13:00, on 15 Nov at 03:35, and on 15 Nov at about 04:30 from `b567e5f`. After the last deploy `deploy/check.py <url> --mode replay` passed 10 of 10 checks against the link. This page describes `deploy/modal_app.py` at that commit: what a deploy sets up, how the link was checked, how to deploy it again, and what was built and not run ("Next steps: built, not run").

Statements about how Modal behaves come from its documentation as the team read it on 13 and 14 Nov, or from the source of the Modal client 1.6.4 installed in `.venv`. Each says which. None was re-read since.

## What a deploy from this commit sets up

| Part | What it is |
|---|---|
| App | `trusted-trade-agents`, one web function `web`, served with `@modal.asgi_app(label="trusted-trade-agents")`. Modal runs the ASGI app and its lifespan itself, so uvicorn is not used. |
| Image | `debian_slim`, Python 3.13. Twelve libraries installed with `uv_pip_install`, pinned to the versions the tests ran with: the ones `pyproject.toml` declares, plus Starlette. **`cryptography` (50.0.2) is among them since 14 Nov**: the gateway signs offers and orders with it, and does not start without it. `modal` and `uvicorn` are not installed. |
| Files in the image | `src/tta` (code, YAML, templates, static files) · the product JSON and the two CSV files from the repository root · `fixtures/valio/`, `fixtures/agent/`, `fixtures/evidence/` · `deploy/witness.py` · `docs/ASSUMPTIONS.md`, if it exists when you deploy. Caches, `.pyc` files and every dot-file are left out. Nothing else from the repository goes in: no `.env`, no `.claude/`, no `var/`. Modal adds these files when the container starts; they are not baked into an image layer. |
| Volume | `trusted-trade-agents-data` at `/data`, created on the first deploy. It holds the Valio call budget, the recordings of live answers, stored web evidence with its request count (`evidence/`), and a copy of the SQLite database. It is not deleted when the app is stopped or redeployed. |
| Scaling | Exactly one container (SQLite, the rate limiter and the pages' books are per process), **kept running for the review day** (`MIN_CONTAINERS = 1`, decision B55): the pages' order books and the demo signing key live in its memory, and a container that stopped after 10 idle minutes took a reviewer's orders with it. Up to 100 requests at once; above that requests queue (Modal docs). 1 core, 4096 MiB: measured on 15 Nov, 553 MiB after start and about 1 MiB for each used book of the pages, of which up to 1,000 are kept. No GPU. **It costs Modal credit for as long as the app is deployed**: stop it after the judging (see "Redeploy, roll back, stop"), or set `MIN_CONTAINERS = 0` and `MEMORY_MIB = 1024` in `deploy/modal_app.py` and redeploy to go back to scale-to-zero. |

### The public link's settings

Set in the image (`IMAGE_ENV`), the same for every deploy from this commit:

| Setting | Value | What it means |
|---|---|---|
| `TTA_ENV` | `demo` | Only the 11 public demo tokens of `src/tta/api/demo_tokens.yaml` are accepted (4 agents, 6 approvers, 1 supplier). The pages are served. |
| `TTA_MODE` | `replay` | Every price and availability answer comes from the recording `2026-11-14-demo` (769 products, recorded Sat 14 Nov 2026 02:52 Helsinki, which gives the clock) and, for baking products, from `2026-11-14-baking` (394 products, the same Saturday at 21:12): 1,163 products in all. No call to Valio Aimo's mock is made. |
| `TTA_DEMO_CLOCK` | `2026-11-12T14:15:00+02:00` | Order deadlines are judged against Thursday 12 Nov 2026, 14:15 Helsinki. We chose it: Valio Aimo said on 14 Nov that its test data is static. The setting is honoured in replay only and refused outside `dev` and `demo`. `/healthz` says which clock is in force; the audit trail keeps the real time. |
| `TTA_DATA_DIR` | `/data` | The Volume. |
| `TTA_DB_PATH` | `/tmp/tta/tta.sqlite3` | SQLite on the container's own disk (see below). |
| `TTA_VALIO_CALL_BUDGET` | `120` | Unused in replay. If the mode is ever set to live again, the app may make at most this many calls. |

Read on the deploying machine through `tta.config` and sent as one Modal Secret (`modal.Secret.from_dict`). A value that is not set is left out. No value appears in a command line, the image, a repository file or any output.

| Name | Effect when set |
|---|---|
| `DATABASE_URL` | The shared order book and audit trail go to Aiven for PostgreSQL (`docs/AIVEN.md`). `/healthz` names the store in use. |
| `TTA_DB_SCHEMA` | The PostgreSQL schema to use instead of `tta`. Audit events cannot be removed, so a build that can no longer read the old trail starts a new one in a new schema; the old one stays untouched. A new schema starts an empty shared trail. |
| `CONTEXT_DEV_API_KEY` | A product with an allergen doubt and no stored or recorded page is looked up at Context.dev (at most 40 requests per gateway, counted on the Volume). Without it only stored and recorded pages are read. |
| `VALIO_AIMO_API_KEY`, `VALIO_AIMO_BASE_URL` | Unused in replay. |
| `GEMINI_API_KEY` | Sent to the link only when the deploying shell sets `TTA_DEPLOY_WITH_MODEL=1`; otherwise it stays on the deploying machine even when it is set there. With it, the gateway asks Gemini first to read a sentence and checks the reading against the text; without it, or when the model does not answer, a recording or the fixed rules read it. Whoever reads, fixed rules decide what may be ordered. `/healthz` → `agent_reader` reports what reads sentences on the link (`settings.gemini_key_set` says whether a key is there). The figures of `docs/DEMO.md` were measured with no key. |

**The signing key is carried when it is set.** The gateway signs every offer and order record with the key in `TTA_SIGNING_KEY`, and with a demo key generated at each start when that setting is absent. `deploy/modal_app.py` puts `TTA_SIGNING_KEY` into the Secret when the deploying machine has it set (`secret_values`; the deploy prints "TTA_SIGNING_KEY is sent in the Secret." or "TTA_SIGNING_KEY is not set: the public link signs with a demo key that changes at every cold start."). **For the review day no fixed key is set**: the link signs with a demo key, every proof says so and `/healthz` shows `signing.demo_key: true`. The key changes each time the container starts, which with one container kept running is at a deploy or after a crash, no longer after 10 idle minutes; a record signed before a restart then no longer verifies against `/.well-known/jwks.json`.

### The database

**With `DATABASE_URL`:** PostgreSQL. At every start the store runs its migrations in one transaction. Valio Aimo's view, `audit_supplier`, is **dropped and created again at every start**: PostgreSQL refuses to replace a view whose columns changed, and a refused statement would fail the whole start-up. The drop removes the grant to the supplier's role, which the next migration gives again. If the database cannot be reached or prepared, the gateway starts on SQLite and `/healthz` gives the reason. The view's SQL was run on the Aiven service on 15 Nov: the 68 live tests of `tests/store_pg` passed, each in a schema of its own, and the deploys of 15 Nov started on PostgreSQL (`docs/AIVEN.md`).

**Without it:** SQLite on the container's local disk. When the container starts, the copy on the Volume is copied back. After each request a thread checks whether the database changed; if so it takes a consistent copy with SQLite's backup API, puts it on the Volume in one step and commits the Volume. One more copy is made at shutdown. SQLite does not run on the Volume itself: SQLite says WAL mode does not work over a network file system, and Modal says Volumes do not support distributed file locking (both as read on 13 Nov). **The cost:** a crash loses what changed in the last second before the copy, and writes around a redeploy can be lost.

Either way, **the pages keep each browser's order book in memory**; only REST and MCP callers use the shared book.

### The witness (defined only with `SUPPLIER_DATABASE_URL`)

When `SUPPLIER_DATABASE_URL` is set on the deploying machine, a second function runs every hour: it reads the head of the audit trail from Valio Aimo's view with the supplier's read-only login and checks that the head it noted last time is still in place (`deploy/witness.py`); its notes are kept in a `modal.Dict`. It gets its own Secret with that URL and the schema name, and never the gateway's login. Without the value no such function exists and nothing is scheduled. **It was never scheduled on Modal:** no login for the supplier was created, so the value was never set and the function was never defined there. Its code ran once by hand on the team's machine against the deployed view, on 15 Nov (`docs/AIVEN.md`, section 5). See "Next steps: built, not run".

## Deploy it again

From the repository root, in this order. `<url>` is the public link above. Each step says what it sends and when it last ran.

1. **The whole suite.** `.venv/bin/python -m pytest -q`. Sends nothing. Last run on `b567e5f`, on 15 Nov: 6,213 passed, 69 skipped (68 need a PostgreSQL), 1 deselected (a timing test). One process over the whole suite did not finish on the team's 16 GB machine, so it was run folder by folder (`for d in tests/*/; do .venv/bin/python -m pytest $d -q -p no:cacheprovider; done`) and `tests/ui` file by file.
2. **Aiven, the live tests.** `.venv/bin/python -m pytest tests/store_pg -q -m live`. Sends SQL to the Aiven service; each test makes and drops its own schema `tta_test_…` and its roles; the deployed schema is not touched. Last run on 15 Nov at 03:45, one file at a time: 68 passed. If a test of the reader views fails, do not deploy with `DATABASE_URL` until it is fixed.
3. **Context.dev, pages for the demo's products.** `.venv/bin/python scripts/record_evidence.py --demo-set --dry-run` lists what would be asked and sends nothing; the same without `--dry-run` sends each product's English name, Finnish name and brand to `api.context.dev`, at most 10 requests a run (`--limit`). Ran on 14 and 15 Nov: every product of the demo set has a recorded answer in `fixtures/evidence/`. The requests sent so far are past the script's default total of 60, so a further run needs `--total-cap` (`docs/CONTEXTDEV.md`).
4. **Modal fan-out (optional).** `.venv/bin/python deploy/evidence_batch.py --limit 200 --dry-run` prints the count and the cost offline. `.venv/bin/modal run deploy/evidence_batch.py --limit 200` is the run: the same three fields per product from Modal containers, at most 40 at a time, with the Context.dev key as its own Modal Secret. It ran once, on 15 Nov at 03:53, as `.venv/bin/modal run -q deploy/evidence_batch.py --limit 76 --total-cap 181`: 76 answers in 58 seconds, 40 containers at the peak (`docs/AWARDS.md`). Each answer costs Context.dev credits, and `--total-cap` bounds the total across runs.
5. **Redeploy, from the reviewed commit.** Check `.venv/bin/modal profile current`, then:
   ```
   .venv/bin/modal deploy --strategy recreate deploy/modal_app.py
   ```
   `--strategy recreate` stops the old container as soon as the new version is live; the default keeps old containers serving while new ones start (Modal docs), which would mean two copies of the database written to one file on the Volume. The files are uploaded from disk as they are, uncommitted changes included. A deploy empties every browser's order book on the pages and, without `TTA_SIGNING_KEY`, starts a new demo signing key.
6. **Check it.**
   - `.venv/bin/python deploy/check.py <url> --mode replay`. With `--mode replay` the health check fails unless the link is in replay; without `--mode` the script takes the link's own mode from `/healthz`. It places one order over REST into the shared book. Last run after the deploy from `b567e5f`: 10 of 10 passed.
   - `curl -s <url>/healthz`: `status` must be `ok`, `reasons` empty, `mode` `replay`, `clock.demo_clock_set` `true`, `store.kind` `postgresql` when `DATABASE_URL` was set, and `agent_reader` naming the reader the deploy was meant to have (`fixed_rules` without `TTA_DEPLOY_WITH_MODEL=1`; `gemini` with it and a key on the deploying machine). Note `audit_head`. The answer verifies the whole audit chain of the shared book, at most once every 30 seconds: a reason that starts "The audit trail does not verify: event …" names the first stored event that was changed, removed or inserted (or a row that is no audit event), and the status is then `degraded`.
   - From two networks (for example Wi-Fi and mobile data): `rate_limit_caller.bucket` in `/healthz` must differ. If both read the same label, every visitor shares one address's windows (see "Request rates on the public link"). On 15 Nov at 03:42 a computer and a phone on mobile data read two different buckets.
   - Open `<url>/shop` in a browser. The page was walked in Chrome against a local gateway, the last time on the final commit `b567e5f` on 15 Nov; that walk was not repeated against the link.
7. **The trail outlives the container.** One container is kept running, so it does not stop when idle: redeploy once more (step 5 starts a new container), then `curl -s <url>/healthz` again: the same `audit_head` as in step 6. On 15 Nov the trail read from the database held events older than the container that served the link (`docs/AIVEN.md`).

## The checks of `deploy/check.py`

Standard library only. It sends the ward's public demo token and exits 0 when every check passes. Ten checks, eight with `--no-order`:

1. **health.** `GET /healthz` answers 200, `environment` is `demo` and `mode` is the one expected (`--mode`; without it, the link's own mode).
2. **page.** `GET /` answers HTML that holds "Trusted Trade Agents".
3. **offer.** The ward's request (200 litres of a plant drink, no milk, no gluten, confirmed data only) sent to `POST /v1/offers` answers 201 with at least one option.
4. **order.** `POST /v1/orders` on the first option answers 201, `ORDERED` or `PENDING_APPROVAL`.
5. **audit.** `GET /v1/audit?order_id=…` says the hash chain verifies.
6. **mcp without a token.** `POST /mcp/` is refused with 401.
7. **mcp tools.** `initialize` and `tools/list` with the ward's token answer 200 and list at least one tool; the line prints how many and their names (13 at this commit).
8. **mcp foreign origin.** `POST /mcp/` with the ward's token and the `Origin` of another site is refused with 403.
9. **api catalog.** `GET /.well-known/api-catalog` answers `application/linkset+json` and links the OpenAPI document and the MCP endpoint.
10. **signing key.** `GET /.well-known/jwks.json` holds one Ed25519 key, the one `/healthz` names; the line says whether it is a demo key.

`--no-order` leaves out the order and the audit check. The ten run against the app in memory in `tests/deploy/test_check.py`, and all ten passed against the public link after the last deploy, from `b567e5f` on 15 Nov.

If a check fails, read the logs with `.venv/bin/modal app logs trusted-trade-agents`.

## The address and what it serves

The pattern is `https://<workspace>--trusted-trade-agents.modal.run` (Modal docs); `modal deploy` prints it.

| Path | What |
|---|---|
| `/shop` | The shop page: the four customers, a request, the offer, "Confirm order", approvals, the log for the buyer and for Valio Aimo |
| `/`, `/approvals`, `/orders/{id}`, `/kitchen`, `/menu`, `/standing-orders` | The older pages |
| `/assumptions` | `docs/ASSUMPTIONS.md` as it was when you deployed |
| `/docs`, `/redoc`, `/openapi.json`, `/v1/schemas` | The REST interface. `/docs` and `/redoc` load their assets from one CDN, at exact versions checked by hash. |
| `/.well-known/api-catalog`, `/llms.txt` | Every way in, for a program and for a language model |
| `/.well-known/jwks.json` | The public key offers and order records are signed with |
| `/mcp/` | The MCP endpoint (Streamable HTTP), with `Authorization: Bearer <demo agent token>` |
| `/healthz` | Environment, mode, clock, `ok` or `degraded` with reasons (among them an audit chain that does not verify, checked at most every 30 seconds), the head of the audit chain, the store in use, the signing key |

One container is kept running, so a request does not wait for a start, except right after a deploy.

## Redeploy, roll back, stop

- **Redeploy.** Run the deploy command again. The Volume and its data stay. On SQLite a write the old container made after its last copy can be lost, so redeploy when nobody is using the demo.
- **Back to live mode.** Set `DEPLOYED_MODE` to `"live"` in `deploy/modal_app.py` and redeploy; `tests/deploy` expects `replay` and fails until it is changed back. The demo clock is ignored in live mode.
- **Roll back.** Deploy the last good commit from a separate worktree:
  ```
  git worktree add ../tta-last-good <commit>
  cd ../tta-last-good && ../junction/.venv/bin/modal deploy --strategy recreate deploy/modal_app.py
  ```
  The secret values are still read through the `tta` package installed in `.venv`, which is this repository's `src/tta` and its `.env`. The image is built from the worktree's files.
- **Stop.** `.venv/bin/modal app stop trusted-trade-agents`. By Modal's documentation this is permanent and the address stops answering; the Volume is kept. Not tried.
- **Start an empty SQLite order book.** Wait until `.venv/bin/modal container list` shows none for the app, then `.venv/bin/modal volume rm trusted-trade-agents-data tta.sqlite3`. A PostgreSQL trail cannot be emptied: choose a new schema with `TTA_DB_SCHEMA`.

## Request rates on the public link

Per minute, in one process's memory (`src/tta/api/limits.py`). All values are ours and illustrative: the mock publishes no rate limit.

| Kind of call | Per visitor | Per address | All callers |
|---|---|---|---|
| Offers, substitute searches and reads of the catalog and the audit trail | 60 | 60 | 240 |
| Orders and approval decisions | 20 | 60 | 240 |
| Request readings and agent runs | 15 | 60 | 240 |

- **Who a visitor is.** On the pages, a browser, known by its own-book cookie. On REST and MCP, and for a browser without the cookie, its address. The per-address column counts all browsers and callers of one address together.
- **Raised for the review day (decision B55).** Lookups per visitor 20 → 60: on REST and MCP a visitor is an address, so everybody behind one Wi-Fi shared the 20, whichever token each sent. 60 is also the address's whole cap for lookups: one REST or MCP caller can now use all of it, and the browsers behind the same address share what is left. Orders (20 per visitor) and readings (15) are unchanged.
- **Other limits.** At most 400 new own order books per address in 10 minutes (was 30: 8 reviewers behind the venue's one address, clicking through the 4 customers, reached it, and every call of the room was then refused for up to 10 minutes), 1,000 books in all (was 300), one idle for 2 hours is dropped (`src/tta/api/sandbox.py`). Bodies up to 64 KB. A buyer holds at most 20 standing orders, and nothing deletes one: on the shared book they can fill up and stay full. A change of a book's settings writes one audit event and is refused (`429`) once the address has stored its 100 MB of the day.
- **The address.** The limiter keys on the direct peer; an IPv6 address counts by its /64. The gateway reads `X-Forwarded-For` only when `TTA_TRUSTED_PROXY_HOPS` is set (default 0). `deploy/modal_app.py` does not set it. A gateway started locally with uvicorn is another matter: by default uvicorn itself believes `X-Forwarded-For` from the machine it runs on and rewrites the peer address before the gateway sees it, so a local run that should not believe it is started with `--no-proxy-headers` (found by a security check on 15 Nov). Modal runs the ASGI app without uvicorn (above), so the link should not be affected; that is reasoned from the deploy file, not tested. **Observed on 15 Nov at 03:42:** `/healthz` read from a computer on one network and from a phone on mobile data showed two different buckets, so visitors on different networks are counted apart. Callers behind one address share that address's windows, and the pages still tell browsers apart by their cookie.

## Cost guard

- Exactly one container, **kept running** for the review day (1 core, 4096 MiB): it uses credit until the app is stopped or redeployed with `MIN_CONTAINERS = 0`. No GPU.
- In replay no call reaches Valio Aimo's mock. A model is called only when the link carries a model key (`TTA_DEPLOY_WITH_MODEL=1`): then each sentence read costs one or more calls to it, within the 15 readings a minute per visitor.
- Context.dev: at most 40 requests per gateway, counted on the Volume, and none without the key.
- Modal's prices and plan limits are not restated here: they were read on 14 Nov and not re-checked.

## Assumptions of a deploy from this commit, and next steps

- **Demo signing key**, new at every container start (above): at a deploy or after a crash.
- **The pages' books are in the container's memory**: a deploy or a crash empties every browser's order book.
- **One shared order book for REST and MCP.** Each demo customer's day's spend adds up there across all callers, waiting orders included. Under the demo clock "today" never ends, so repeated runs add up until the limit per day sends every order to a person (rule P-02). Next: a reset of the shared demo book, or a real calendar.
- **The shop page was walked in Chrome against a local gateway**, not against the link: several times on 15 Nov, the last on the final commit `b567e5f`, at 1440 × 900 and, for the first screen, down to 390 × 844. Next: the same walk on the link.
- **The pages' orders are not in Aiven.** Only REST and MCP callers write to the shared order book and audit trail; the shop page writes to its browser's book in memory.
- **The pages have no login.** A page acts as the customer's person it shows, so whoever opens it can confirm as any of that customer's people; an agent's token is refused on the approval routes over REST and MCP only. Next: people sign in with their own accounts, and no page is mounted outside `dev` and `demo` (already so).
- **SQLite copy** (without `DATABASE_URL`): the last second before a crash, and writes around a redeploy, can be lost.
- **`GET /mcp/` with `Accept: text/event-stream`** holds a connection that sends nothing; each takes one of the 100 concurrent inputs until the client leaves.
- **`/assumptions`** shows `docs/ASSUMPTIONS.md` as it was at deploy time.
- **`/docs` and `/redoc`** need the CDN; the rest of the site loads nothing from elsewhere.

## Next steps: built, not run

- **`scripts/aiven_proof.py` with the supplier's login.** The script was not run: it needs a login for Valio Aimo's reader, and none was created. The same statements were run by hand on the deployed schema on 15 Nov, with the role's rights taken through `SET LOCAL ROLE` (`docs/AIVEN.md`, section 4). To run the script: as the admin login, once, by hand: `CREATE ROLE valio_aimo LOGIN PASSWORD '<a strong password>' IN ROLE tta_supplier;` (with the new schema's name in place of `tta` if `TTA_DB_SCHEMA` was set). Put that login's URL in the environment as `SUPPLIER_DATABASE_URL`. Then `.venv/bin/python scripts/aiven_proof.py` (add `--schema <name>` for another schema). It sends 8 statements with the supplier's login; the two it expects to be refused are written `WHERE false`. The script has no flag that creates the login.
- **The scheduled witness on Modal** (`deploy/witness.py`). It was never defined on Modal, for the same reason. To run it: deploy once more with `SUPPLIER_DATABASE_URL` set in the deploying shell, and look for the scheduled function's first run in Modal's dashboard.
- **A model on a Modal GPU** (`deploy/agent_model.py`, an optional reader of sentences, off everywhere). On 14 Nov the image built and Modal refused the deploy, because the workspace has no payment method for GPU functions. Nothing is deployed.
- **Stopping the app** (`modal app stop`) was not tried.

## What runs on Modal, in short

- Modal hosts the whole gateway (REST, MCP and the pages) behind one public HTTPS address, deployed with one command from plain Python, with no Dockerfile or YAML.
- The image is defined in code with pinned libraries; secret values are read on the deploying machine and are never in the image, the code or the repository; a Volume keeps the data across restarts. For the review day the app does not scale to zero (one container is kept running); the setting to go back is one constant.
- One batch fan-out ran on Modal (`deploy/evidence_batch.py`, 15 Nov at 03:53: 76 web lookups, 40 containers at the peak, 58 seconds). One scheduled function, the witness, is built and was not run there.
- No GPU, no model served, no Sandboxes and no fine-tuning: by the bar of Modal's brief this is a light use of Modal.
