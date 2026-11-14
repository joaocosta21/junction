# Trusted Trade Agents

A gateway that lets a buyer's purchasing agent look up Valio Aimo products, get an offer at fixed prices, and place an order within its own authority or send it to a human for approval. Every claim in an offer says whether Valio's data confirms it, every product left out says why, and every step is written to a hash-chained audit trail that the buyer and Valio Aimo each read in their own view. Built at Junction 2026 for the Valio Aimo challenge "Trusted Trade Agents", against Valio Aimo's mock API; it speaks REST (OpenAPI 3.1) and MCP.

## The flow

```
request ──► lookup ──► offer ──► policy ──► order ─┬─► placed by the agent (AUTO)
(typed, or    (catalog +   (options, a     (fixed rules  ├─► sent to a human (APPROVAL) ──► approve / reject
 pasted text   live price   status per      + buyer      └─► refused (BLOCK)
 read by       and stock)   claim, every    profile)
 Gemini)                    exclusion                         every step ──► audit trail (buyer view, supplier view)
                            with a reason)
```

Two runs in replay of the recorded capture (Saturday 14 Nov 2026, 02:52 server time):
- **Hotel kitchen, "1,000 litres of lactose-free milk by Monday".** Option 1: three confirmed milks cover the 1,000 litres for €2,580.64 before tax. It is above the hotel's illustrative €750 limit per order, so it goes to the purchasing manager. Option 2: one cheaper milk at €1,010.00 whose stock Valio does not confirm, so a human must approve it whatever the price. 19 products are excluded, each with its reason.
- **Allergy ward, "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only".** 200 soya drinks that state free-from milk and gluten, €402.00. Every claim is confirmed and the total is within the ward's limits, so the agent places the order alone.

The model reads the text and picks an option. It never decides a price, a quantity, an allergen status or a verdict: deterministic code does, and the audit trail records which rule applied.

## Run it in replay

Python 3.13 is required. From the repository root:

```bash
python3.13 -m venv .venv && .venv/bin/pip install -e ".[dev]"
TTA_ENV=demo TTA_MODE=replay .venv/bin/python -m uvicorn --factory tta.api:create_app
# then open http://127.0.0.1:8000/
```

- **`TTA_ENV` must be set** to `dev` or `demo`. Unset means `prod`: the demo tokens and the pages are not loaded, and the app refuses to start without `TTA_TOKENS`.
- Replay needs no Valio key and makes no call to the mock. Answers come from `fixtures/valio/2026-11-14-demo/`, with the clock pinned to that capture.
- Without a Gemini key, the request parser and the buyer agent answer from the recordings in `fixtures/agent/`. Four of the five were recorded from `gemini-3.6-flash` on 14 Nov 2026; the agent's run of scenario 1 is written by hand, and a run from it says `hand-built`. Sentences with no recording need the key.
- If your `.env` holds `GEMINI_API_KEY`, the parser and the agent call Gemini. When Gemini cannot be reached, a sentence that has a recording is answered from it, and the report says so in its first sentence. Gemini was slow on 14 Nov (29 s to read scenario 1), and a time-out can hold a sentence for about 90 s before the recording answers. For a quick demo, put `GEMINI_API_KEY=` before the command.
- Orders and the audit trail go to `var/tta.sqlite3`. The day's spend adds up across runs on one database, so a repeated demo meets the daily limit. Set `TTA_DB_PATH` to a new file to start from an empty order book.
- Live data: set `VALIO_AIMO_API_KEY` in `.env` and start with `TTA_MODE=live`. When the mock cannot be reached, or fewer than 10 calls are left in the call budget, the recorded capture answers and the offer says `replay`.

What is served:

| Path | What | Who |
|---|---|---|
| `/` | Pages: paste a request or click one of three examples, see the offer, the verdict and the order; `/approvals`; `/orders/{id}` with both views of the audit trail; `/assumptions` | `dev` and `demo` only, demo identity chosen on the page |
| `/v1/...` | REST API | Bearer token |
| `/openapi.json`, `/docs` | Generated OpenAPI 3.1 and Swagger UI | Anyone |
| `/v1/schemas` | JSON Schema (2020-12) of every model | Anyone |
| `/mcp/` | MCP endpoint, Streamable HTTP, eight tools | Bearer token |
| `/healthz` | Mode, data source, head of the audit chain, which settings are set (true or false only) | Anyone |

Demo tokens are public by design and listed in `src/tta/api/demo_tokens.yaml`, for example `demo-agent-hotel-kitchen`, `demo-agent-allergy-ward`, `demo-approver-hotel-purchasing`, `demo-supplier-valio-aimo`. A first call:

```bash
curl -s -H "Authorization: Bearer demo-agent-allergy-ward" http://127.0.0.1:8000/v1/authority
```

The click-by-click demo, with the exact sentences on screen and a 90-second cut, is in [docs/DEMO.md](docs/DEMO.md).
Deployment on Modal is prepared, not live: see [docs/DEPLOY.md](docs/DEPLOY.md). <!-- check: deploy/ and docs/DEPLOY.md exist (T14); replace with the URL only if T14 deployed -->

## Run the tests

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
```

The tests never call the Valio API or Gemini: they run on the recorded captures and on fakes. `tests/e2e/` runs the demo scenarios over HTTP in replay, from the pasted sentence to the audit trail. One package at a time: `.venv/bin/python -m pytest tests/offers -q`. Per-package counts and coverage are on the build board, `AIMO/build/STATUS.md`.

## Datasets, and how to refresh them

| What | Where | Refresh |
|---|---|---|
| Valio Aimo product file (17,546 products) and its JSON Schema | `valio_aimo_junction26_product_data.json`, `valio_aimo_junction26_product_data_schema.json` | Download with the API key (below) |
| Delivery reliability and carbon footprint | `valio_aimo_junction26_delivery_reliability.csv`, `valio_aimo_junction26_carbon_footprint.csv` | Download with the API key (below) |
| Recorded price and availability answers of the mock | `fixtures/valio/<capture>/` (`manifest.json` holds the server's `timeNow`) | `scripts/capture_valio.py` |
| Recorded model answers for the demo sentences | `fixtures/agent/` | `.venv/bin/python -m tta.agent.record` (needs `GEMINI_API_KEY`) |

Download the three data files to the repository root (the key is on the Junction challenge page; keep it in `.env`, which is gitignored):

```bash
curl -L -H "X-API-Key: $VALIO_AIMO_API_KEY" -o valio_aimo_junction26_product_data.json       https://junction26.valioaimo.fi/api/products/download
curl -L -H "X-API-Key: $VALIO_AIMO_API_KEY" -o valio_aimo_junction26_delivery_reliability.csv https://junction26.valioaimo.fi/api/delivery-reliability/download
curl -L -H "X-API-Key: $VALIO_AIMO_API_KEY" -o valio_aimo_junction26_carbon_footprint.csv     https://junction26.valioaimo.fi/api/carbon-footprint/download
```

Record a new replay capture, then point the app at it:

```bash
.venv/bin/python scripts/capture_valio.py --capture <new-name> --category-prefix 104 --category-prefix 18720 --with-listed-substitutes
TTA_ENV=demo TTA_MODE=replay TTA_REPLAY_CAPTURE=<new-name> .venv/bin/python -m uvicorn --factory tta.api:create_app
```

Each chunk of up to 1,000 ids costs two calls to the mock (price and availability). The script does not count against the gateway's call budget. The tests read the committed captures by name, so give a new capture a new name.

The datasets and recorded answers are Valio Aimo's synthetic data, not covered by this repository's licence. Whether they may stay in a public repository is an open question for Valio (`AIMO/BOOTH-QUESTIONS.md`, "Ask any Valio person").

## Read more

| Document | What it holds |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The packages, the ports, and where each part of the brief lives |
| [docs/STANDARDS.md](docs/STANDARDS.md) | Each open standard we use, checked against its specification, and the next steps toward production |
| [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) | Every assumption, why, what would change it, and where it is in the code (also served at `/assumptions`) |
| [docs/AWARDS.md](docs/AWARDS.md) | The Gemini and Modal write-ups |
| [docs/PITCH.md](docs/PITCH.md) | Drafts for the pitch, the video and the submission form |
| [AIMO/SPEC.md](AIMO/SPEC.md) | The build contract |
| [AIMO/CHALLENGE.md](AIMO/CHALLENGE.md) | The challenge and its judging criteria, verbatim |
| [AIMO/FINDINGS.md](AIMO/FINDINGS.md) | Verified facts about the mock API and the data |
| [AIMO/BOOTH-QUESTIONS.md](AIMO/BOOTH-QUESTIONS.md) | Questions for Valio's mentors, each with an example |

## What is not done

- The agent's run of scenario 1 is a hand-written recording (by plan); the other four recordings come from Gemini. A whole agent run has no deadline, and the model's output length has no cap (`AIMO/build/handback/T10-followup.md`).
- Not deployed. The Modal files are prepared (T14). <!-- check: T14 state in AIMO/build/STATUS.md -->
- The MCP endpoint was checked with the official SDK client only, not with a third-party host. It does not check the `Origin` header and has no OAuth flow (see docs/STANDARDS.md).
- Delivery-time and sustainability comparison (an optional direction of the brief) is not built.
- The stretch tasks on Aiven PostgreSQL and Context.dev were not built.

## Licence

MIT, see [LICENSE](LICENSE). The Valio Aimo datasets and recorded API answers are not ours and are not covered by it.

---

## Hackathon notes

The original README of this repository, kept as it was:

# junction
