# Deployment on Modal

The public demo of the gateway runs as one Modal app. `deploy/modal_app.py` defines it, and `deploy/check.py` checks it after a deploy. Both were built and tested locally (`tests/deploy/`, 49 tests). **No deploy has been made yet**, so nothing in this file has been observed on Modal. Statements about Modal come from its documentation, or from the source of the Modal client 1.6.4 installed in `.venv`. Each one says which.

## What is deployed

| Part | What it is |
|---|---|
| App | `trusted-trade-agents`, one web function `web`, served with `@modal.asgi_app(label="trusted-trade-agents")`. Modal runs the ASGI app and its lifespan itself, so uvicorn is not used. |
| Image | `debian_slim`, Python 3.13. The libraries of `pyproject.toml` are installed with `uv_pip_install`, pinned to the versions the tests ran with, plus Starlette. `modal` and `uvicorn` are not installed. |
| Files in the image | `src/tta` (code, YAML, templates, static files) · the product JSON and the two CSV files from the repository root · `fixtures/valio/` · `fixtures/agent/` · `docs/ASSUMPTIONS.md`, if it exists when you deploy. They keep the repository's layout under `/app`. Caches, `.pyc` files and every dot-file are left out. Nothing else from the repository goes in: no `.env`, no `.claude/`, no `var/`. Modal adds these files when the container starts. They are not baked into an image layer. |
| Environment | `TTA_ENV=demo`, so only the nine public demo tokens of `src/tta/api/demo_tokens.yaml` are accepted. `TTA_MODE=live`: the gateway switches to the recorded capture on its own, labelled replay, when the mock cannot be reached or the call budget is low. `TTA_DATA_DIR=/data` (the Volume). `TTA_DB_PATH=/tmp/tta/tta.sqlite3` (the container's own disk). It also holds the paths of the product file, the CSV files and the fixtures under `/app`, and `PYTHONPATH=/app/src`. |
| Secret | One `modal.Secret.from_dict`, built on your machine at deploy time from `tta.config.get_settings()`: `VALIO_AIMO_API_KEY`, `VALIO_AIMO_BASE_URL` and `GEMINI_API_KEY`, and nothing else. A value that is not set is left out. Without the Valio key the app serves the capture. Without the Gemini key it uses the recorded model answers. Without the base URL it uses its default. Inside the container nothing is read and the Secret is empty, which is how Modal's own `Secret.from_local_environ` behaves. No value appears in a command line, the image, a repository file or any output. |
| Volume | `trusted-trade-agents-data` at `/data`, created on the first deploy (`create_if_missing=True`, Volumes v1, the default). It holds the Valio call budget (`valio_call_budget.json`), the recordings of live answers (`recordings/`) and a copy of the database (`tta.sqlite3`). It is not deleted when the app is stopped or redeployed. |
| Database | SQLite runs on the container's local disk. When the container starts, the copy on the Volume is copied back to local disk. After each request a thread checks SQLite's `data_version`. If the database changed, it takes a consistent copy with SQLite's backup API, puts it on the Volume in one step and commits the Volume (`DatabaseSaver`, `SaveAfterRequests`). One more copy is made at lifespan shutdown. Modal's own background commits and its commit at container shutdown also run (Modal docs, "Volumes"). |
| Scaling | `max_containers=1` (SQLite, the in-memory rate limiter and the pages' run log are per process). `min_containers=0`: it scales to zero. `scaledown_window=600`: it stops after 10 idle minutes. `@modal.concurrent(max_inputs=100)` takes many requests at once, and above that requests queue (Modal docs, "Web endpoints"). `cpu=1.0`, `memory=1024` MiB; measured locally, the app peaks at about 630 MiB with the catalog loaded. No GPU. |

**Why SQLite does not run on the Volume.** The store opens the database in WAL mode. Four facts point away from a live SQLite file on the Volume:
- SQLite says WAL does not work over a network file system.
- Modal says Volumes do not support distributed file locking.
- Modal says a v1 Volume may rewrite a whole file for a small write.
- Modal's only SQLite example builds the database off the Volume and copies it in.

The copy approach relies only on whole-file writes and `commit()`, which that example uses. It was run locally with the files laid out as the image lays them out, restarted, and the order and the audit chain came back. **The cost:** a crash loses whatever changed in the last second before the copy. Writes between a container's final copy and a new container's start can also be lost (see "Redeploy").

## Before deploying

1. Check that Modal is authenticated: `.venv/bin/modal profile current`.
2. Check that the three values are in the environment or `.env`. The deploy reads them through `tta.config` and prints none of them. Once deployed, `/healthz` shows `valio_key_set` and `gemini_key_set` as true or false.
3. Deploy from the reviewed commit. The files are uploaded from disk as they are, uncommitted changes included.
4. Run the tests: `.venv/bin/python -m pytest tests/deploy -q`.

## Deploy

One command, from the repository root:

```
.venv/bin/modal deploy --strategy recreate deploy/modal_app.py
```

`--strategy recreate` stops the old container as soon as the new version is live. The default `rolling` strategy keeps old containers serving while new ones start (Modal docs, "Managing deployments"). Here that would mean two copies of the database being written to the same file on the Volume. The first deploy builds the library layer. Later deploys reuse it as long as `PINNED` and `IMAGE_ENV` do not change.

## The URL

`modal deploy` prints the URL, and `.venv/bin/modal app list` lists the app. The pattern is `https://<source>--<label>.modal.run` (Modal docs, "Web endpoint URLs"). `<source>` is the workspace name, plus `-<suffix>` if the Modal environment has a suffix.

```
https://<workspace>--trusted-trade-agents.modal.run
```

| Path | What |
|---|---|
| `/` | The request page, with three one-click scenarios |
| `/approvals` | Pending approvals, decided as a demo approver |
| `/orders/{id}` | The order record, with the buyer's and the supplier's views of the audit trail |
| `/assumptions` | `docs/ASSUMPTIONS.md` as it was when you deployed |
| `/docs`, `/openapi.json`, `/v1/schemas` | The REST interface. `/docs` loads Swagger's assets from a CDN. |
| `/mcp/` | The MCP endpoint (Streamable HTTP), with `Authorization: Bearer <demo agent token>` |
| `/healthz` | Environment, mode, source of the last look, `ok` or `degraded` with reasons, and the head of the audit chain |

The first request after the app has been idle waits for a container to start. Building the app takes about 2 s locally, on top of Modal's own container start, which was not measured.

## Checks right after

```
.venv/bin/python deploy/check.py https://<workspace>--trusted-trade-agents.modal.run
```

It uses only the standard library, sends the public ward token, and exits 0 when every check passes:

1. **health.** `GET /healthz` answers 200, with `environment` demo and `mode` live. It prints `status`, `reasons`, `source`, `valio_key_set`, `gemini_key_set` and the number of audit events.
2. **page.** `GET /` answers HTML.
3. **offer.** Scenario 2 is sent by HTTP as the allergy ward's demo agent (`POST /v1/offers`) and answers 201 with at least one option. It prints the offer's `source`: `live` means the mock answered, `replay` means the capture did.
4. **order.** `POST /v1/orders` on the first option answers 201, `ORDERED` or `PENDING_APPROVAL`.
5. **audit.** `GET /v1/audit?order_id=…` says the hash chain verifies.
6. **mcp without a token.** `POST /mcp/` is refused with 401.
7. **mcp tools.** `initialize` and `tools/list` with the ward token answer 200 and list the eight tools.

Options:
- `--no-order` stops after the offer. Use it on the judging day: each order counts toward the ward's daily spend limit (see "Known limits").
- `--mode replay` is for a deployment that was switched to replay.

The script passed against the app in replay in memory (`tests/deploy/test_check.py`), against uvicorn in replay, and against the container layout simulated locally in live mode with no key.

The same checks by hand:

```
U=https://<workspace>--trusted-trade-agents.modal.run
curl -sS $U/healthz
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' $U/
curl -sS -X POST $U/v1/offers -H 'Authorization: Bearer demo-agent-allergy-ward' -H 'Content-Type: application/json' \
  -d '{"needed_by":"2026-11-16","require_confirmed":true,"lines":[{"text":"200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only","product_type":"plant_drink","quantity":200,"unit":"L","exclude_allergens":["AM","AW"]}]}'
curl -sS -X POST $U/v1/orders -H 'Authorization: Bearer demo-agent-allergy-ward' -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: deploy-check-1' -d '{"offer_id":"<offer_id>","option_id":"opt_1"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST $U/mcp/ -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'   # 401
```

If a check fails, read the logs with `.venv/bin/modal app logs trusted-trade-agents`. The gateway logs supplier failures, a call budget it cannot save, and failed database copies ("could not be saved to the Volume").

## Redeploy, roll back, stop

- **Redeploy.** Run the deploy command again. The Volume and its data stay. The new container copies the database back from the Volume. A write the old container made after its last copy can be lost, so redeploy when nobody is using the demo.
- **Switch to replay.** In `deploy/modal_app.py`, set `IMAGE_ENV["TTA_MODE"]` to `"replay"` and redeploy. `tests/deploy` expects `live` and will fail until you change it back.
- **Roll back.** `.venv/bin/modal app rollback trusted-trade-agents` needs a Team or Enterprise plan (Modal pricing page, "Managing deployments"). On the Starter plan, deploy the last good commit from a separate worktree:
  ```
  git worktree add ../tta-last-good <commit>
  cd ../tta-last-good && ../junction/.venv/bin/modal deploy --strategy recreate deploy/modal_app.py
  ```
  The secret values are still read through the `tta` package installed in `.venv`, which is this repository's `src/tta` and its `.env`. The image is built from the worktree's files.
- **Stop.** `.venv/bin/modal app stop trusted-trade-agents`. Modal says this is permanent: a stopped app cannot be restarted, and the URL stops answering. The Volume is kept. Deploying again under the same name is expected to create the app anew; this was not tried.
- **Read the data.** `.venv/bin/modal volume ls trusted-trade-agents-data` lists the files, and `.venv/bin/modal volume get trusted-trade-agents-data tta.sqlite3 <local file>` downloads the database copy.
- **Start an empty order book** (for example before judging, see "Known limits"). The container makes one last copy as it stops, so delete the copy while no container runs:
  1. Wait until `.venv/bin/modal container list` shows none for the app, after 10 idle minutes. Or stop it with `.venv/bin/modal container stop <id>`.
  2. Run `.venv/bin/modal volume rm trusted-trade-agents-data tta.sqlite3`.
  3. The next request starts on an empty database. A request that arrives between steps 1 and 2 starts a container on the old copy.

## Cost guard

- One container at most, scaled to zero after 10 idle minutes. No minimum container and no GPU.
- Modal bills per second only while a container runs. CPU and memory are charged on whichever is higher, the request or the actual use (Modal docs, "Resources").
- At the listed prices ($0.0000131 per physical core per second, $0.00000222 per GiB per second, Modal pricing page), one running hour of this container (1 core, 1 GiB) costs about $0.055. Each idle tail of 10 minutes costs about $0.01. The Starter plan includes $30 of credits a month.
- The call budget caps calls to the Valio mock at 120 (`TTA_VALIO_CALL_BUDGET` in `IMAGE_ENV`: the human approved 150 for the overnight run and 10 were used before the deployment). The count is kept on the Volume, so it holds across restarts and is separate from the count on a laptop. When fewer than 10 calls are left, the capture answers. Raising the budget means setting that variable in `IMAGE_ENV`, or deleting `valio_call_budget.json` from the Volume while no container runs.
- Calls to Gemini are limited by the gateway's own limits on request readings and agent runs: 5 a minute per browser (or per address without the pages' cookie), 15 per address, 30 for the whole app (`src/tta/api/limits.py`).

## Per-visitor rate limits behind Modal

The limits, per minute, in one process's memory (`src/tta/api/limits.py`, all illustrative):

| Kind of call | Per visitor | Per address | Whole app |
|---|---|---|---|
| Offers and substitute searches | 20 | 60 | 120 |
| Orders and approval decisions | 20 | 60 | 120 |
| Request readings and agent runs | 5 | 15 | 30 |

- **Who a visitor is.** On the pages, a browser, known by its own-book cookie. On REST and MCP, and for a browser without the cookie, its address. The per-address column counts all browsers and callers of one address together.
- **Other limits.** At most 30 new own order books per address in 10 minutes (`src/tta/api/sandbox.py`). Live looks at the mock: 6 a minute for the whole app, 2 per address; above that the capture answers, labelled `replay` (`src/tta/api/fallback.py`). A token from the environment, outside the demo: 60 calls a minute per token.
- **The address.** `tta.api.limits.client_key_of` keys on the direct peer; an IPv6 address counts by its /64. `X-Forwarded-For` is read only when `TTA_TRUSTED_PROXY_HOPS` is set (`src/tta/config.py`, default 0, at most 10): with N, the N-th entry from the right, the address the outermost trusted proxy saw. Entries a caller wrote further left are never read, and a header with fewer entries leaves the peer. `deploy/modal_app.py` does not set it, so on the deployed app after the final redeploy the header is never read. <!-- check: deploy -->

- **What the app sees on Modal.** The Modal docs ("Web endpoints", section "Client IP address") say: "You can access the IP address of the client making the request. This can be used for geolocation, whitelists, blacklists, and rate limits." Their example reads `request.client.host`, which is the ASGI scope's `client`. In the Modal client's own runtime (`modal/_runtime/asgi.py`, `_add_forwarded_for_header`), a comment says Modal strips `X-Forwarded-For` from the scope. That comment sits in the code that proxies `@modal.web_server`, and it is the only place where the header is mentioned.
- **So the rule will see each address, with nothing to change.** The peer is the visitor's own public address, and with no trusted proxy hop `client_key_of` keys on it and never reads the header. This is inferred from the documentation and not observed. FIX-8's live check confirms it: set the limit to 2 and send three offers with `demo-agent-allergy-ward` from two phones on different networks. Each phone should get 201, 201, 429. That check spends live Valio calls.
- **Shared addresses share a window.** Visitors behind one NAT, such as a venue Wi-Fi or a carrier-grade NAT, share the per-address windows (60, 60 and 15 a minute). On the pages each browser also has its own window of 20, 20 and 5, so one browser cannot use up the address's share. The whole-app ceilings apply to everyone together.
- **If an observation contradicts this:**
  - If the peer turns out to be a proxy address that Modal puts in front of every visitor, set `TTA_TRUSTED_PROXY_HOPS` to the number of proxies that append to `X-Forwarded-For`. That only helps if Modal sends the header, which its client source says it strips.
  - Without the header, the pages still tell browsers apart by their cookie; REST and MCP callers behind one address share its windows.

## The order book on the pages

Checked in the templates and not changed, because the pages are T12's:
- The outcome of a run (`src/tta/ui/templates/_result.html`) and the buyer's order record (`order.html`) print the order's `record_note`: "Recorded in the gateway's order book. The Valio Aimo mock has no order endpoint; this record holds everything a supplier order message would need. It commits nobody." (`ORDER_RECORD_NOTE`, `src/tta/contracts/order.py`).
- The footer of every page (`base.html`) says: "An order here is a record in the gateway's order book; the Valio Aimo mock has no order endpoint." It does not say "commits nobody". Adding those words to `base.html` would put them on every page.

## Known limits of this deployment

- **One order book for REST and MCP.** On the pages each browser has its own book in memory, but REST and MCP callers share one database, where the day's spend of each demo buyer adds up (T12, question 1). At tonight's prices, scenario 2 (€402) is ordered by the agent alone three times in a day within the ward's illustrative €1,500 daily limit. From the fourth run it goes for approval. Scenario 1 and the hotel kitchen's €3,000 behave the same way. In live mode "today" is the real date. To start the judging day on an empty book, use the steps in "Start an empty order book" above.
- **SQLite copy.** Writes made in the last second before a crash can be lost, as can writes made around a redeploy.
- **The call budget's lock on the Volume.** `CallBudget` locks its file with `fcntl.flock` in the data directory, which is on the Volume. Modal does not document file locks inside one container. If the lock fails, every live call is refused, the capture answers (`source: replay`) and the log says "could not be saved to valio_call_budget.json". The fix is a different data directory on local disk, at the cost of a budget that resets on every container start.
- **Gemini.** With `GEMINI_API_KEY` set, a scenario click waits on the live model, and a whole run has no deadline (T10, T12). Modal answers a request for at most 150 s, then redirects (Modal docs, "Request timeouts").
- **`GET /mcp/` with `Accept: text/event-stream`** holds a connection that sends nothing (T11). Each such connection takes one of the 100 concurrent inputs until the client leaves or Modal ends it.
- **`/assumptions`** shows `docs/ASSUMPTIONS.md` as it was at deploy time.

## What the Modal write-up can honestly claim

- Modal hosts the whole gateway (REST, MCP and the pages) behind one public HTTPS URL, deployed with one command from plain Python, with no Dockerfile or YAML.
- The image is defined in code with pinned libraries. The code and data files are added at container start.
- Secrets: only the values the app reads go into a Modal Secret, built from the local configuration at deploy time: the Valio key and base URL and the Gemini key, and since `cf6681f` the database URL and the Context.dev key, which reach the deployed app at the final redeploy. <!-- check: deploy --> They are never in the image, the code or the repository.
- A Modal Volume keeps the order book and audit trail (as a copy committed after each change), the Valio call budget and the recordings of live answers, across restarts and scale-to-zero.
- Cost guard: one container, scale to zero, per-second billing, no GPU.
- It cannot claim GPU work, an open model, Sandboxes, fine-tuning or a batch fan-out. The model runs on Google's Gemini API. By the brief's own bar this is a light use of Modal.
- Until a deploy has been made and checked, the write-up can say only "prepared".
