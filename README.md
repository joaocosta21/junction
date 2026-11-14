# Trusted Trade Agents

A gateway that lets a buyer's purchasing agent look up Valio Aimo products, get an offer at fixed prices, and submit a proposed order for human approval. Every claim in an offer says whether Valio's data confirms it, every product left out says why, and every step is written to a hash-chained audit trail that the buyer and Valio Aimo each read in their own view. Built at Junction 2026 for the Valio Aimo challenge "Trusted Trade Agents", against Valio Aimo's mock API; it speaks REST (OpenAPI 3.1) and MCP.

**Live demo:** https://joaocostared--trusted-trade-agents.us-east.modal.run (Modal, live Valio data with the recorded capture as fall-back; redeployed from commit `8163d5d` at about 13:00 on 14 Nov 2026, and `deploy/check.py` passed all 7 checks against it; `/menu`, `/standing-orders`, `/kitchen` and `/assumptions` answer 200 there). On its pages each browser gets its own order book: nothing one visitor does is seen by another, and **Start again** empties it.

## The flow

```
request ──► lookup ──► offer ──► policy ──► order ─┬─► pending human approval
(typed, or    (catalog +   (options, a     (fixed rules  │   └─► approve / reject
 pasted text   live price   status per      + buyer      └─► refused (BLOCK)
 read by       and stock)   claim, every    profile)
 Gemini)                    exclusion                         every step ──► audit trail (buyer view, supplier view)
                            with a reason)
```

Two runs in replay of the recorded capture (Saturday 14 Nov 2026, 02:52 server time):
- **Hotel kitchen, "1,000 litres of lactose-free milk by Monday".** Option 1: three confirmed milks cover the 1,000 litres for €2,580.64 before tax. It is above the hotel's illustrative €750 limit per order, so it goes to the purchasing manager. Option 2: one cheaper milk at €1,010.00 whose stock Valio does not confirm, so a human must approve it whatever the price. 19 products are excluded, each with its reason.
- **Allergy ward, "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only".** 200 soya drinks that state free-from milk and gluten, €402.00. Every claim is confirmed and the total is within the ward's limits. The proposal still waits for the purchasing manager (F-10).

The model reads the text and picks an option. It never decides a price, a quantity, an allergen status or a verdict: deterministic code does, and the audit trail records which rule applied.

### Added on Saturday afternoon (commits `de453e6`, `fa07e39`)

- **Delivery and sustainability comparison.** Every offer line shows delivery reliability, carbon footprint per kg and certificate labels, or "unknown". A request may set `prefer` (`PRICE`, the default, `EARLIEST`, `RELIABILITY` or `LOWER_CARBON`) and `required_labels` (for example `EU_ORGANIC_FARMING`). When the preference picks another product than price would, the offer also holds the `CHEAPEST_CONFIRMED` option and says what the difference buys. Example 5 on `/`: "100 litres of oat drink by Monday, most reliable delivery" orders `470863` at €140.00, €7.00 more than the cheapest confirmed `472145` (€133.00), for a delivery reliability of 100% instead of unknown.
- **Standing orders with drift detection.** A standing order is a stored request renewed every N days. Rule P-08 sends a renewal to the purchasing manager when a line's quantity or unit price differs from the median of its last 6 renewals by more than the profile's tolerance (hotel kitchen 25%, ours). The demo history is six weeks made up for the demonstration and marked synthetic: the mock has no order history. Page `/standing-orders`.
- **Recipe logic.** A menu (dishes × servings, minus the kitchen's stock) becomes one offer. An ingredient that cannot be had by the date is replaced by another product type that does the same job in the dish, and fixed rule F-09 sends every such stand-in to the purchasing manager. The recipe table is ours and illustrative. Page `/menu`.
- **A rule-based reader.** When no model answers (no key, Gemini out of reach, or a 401, 402 or 403 from it) and the sentence has no recording, fixed rules read the common shapes of a request and the page says "Read by fixed rules, not by a model". They never guess a quantity.

## Run it in replay

Python 3.13 is required. From the repository root:

```bash
python3.13 -m venv .venv && .venv/bin/pip install -e ".[dev]"
TTA_ENV=demo TTA_MODE=replay .venv/bin/python -m uvicorn --factory tta.api:create_app
# then open http://127.0.0.1:8000/
```

- **`TTA_ENV` must be set** to `dev` or `demo`. Unset means `prod`: the demo tokens and the pages are not loaded, and the app refuses to start without `TTA_TOKENS`.
- Replay needs no Valio key and makes no call to the mock. Answers come from `fixtures/valio/2026-11-14-demo/`, with the clock pinned to that capture.
- Without a Gemini key, the request parser and the buyer agent answer from the recordings in `fixtures/agent/`, else from fixed rules (below). Four of the eleven were recorded from `gemini-3.6-flash` on 14 Nov 2026. Seven are written by hand and say `hand-built`: the agent's run of scenario 1; the reading and the run of the brief's own sentence ("I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability.", hotel kitchen); the readings of the two Finnish sentences, and the transcription and reading of the demo photo (Gemini answered 503 and 504 when those were to be recorded, task T18). A sentence with no recording is read by fixed rules when it has a shape they know (a quantity in digits and a unit, a product type of the table or a product number, and words such as "lactose-free", "no milk", "strict", "by Monday", "confirmed only", "most reliable" or "organic"); anything else needs the key.
- If your `.env` holds `GEMINI_API_KEY`, the parser and the agent call Gemini. When Gemini cannot be reached, a sentence that has a recording is answered from it, and the report says so in its first sentence. Gemini was slow on 14 Nov (29 s to read scenario 1), and a time-out can hold a sentence for about 90 s before the recording answers. For a quick demo, put `GEMINI_API_KEY=` before the command.
- **Two kinds of order book.** On the pages, each browser has its own book in memory, with its own audit trail; it starts empty, is dropped after 2 idle hours, and **Start again** empties it. REST and MCP share one book in `var/tta.sqlite3`: there the day's spend adds up across runs, so a repeated demo meets the daily limit. Set `TTA_DB_PATH` to a new file to start that book empty. With `DATABASE_URL` set, the shared book uses PostgreSQL instead, and SQLite when the database cannot be reached at start; `/healthz` then names the reason (`docs/AIVEN.md`).
- Live data: set `VALIO_AIMO_API_KEY` in `.env` and start with `TTA_MODE=live`. When the mock cannot be reached, or fewer than 10 calls are left in the call budget, the recorded capture answers and the offer says `replay`.

What is served:

| Path | What | Who |
|---|---|---|
| `/` | Pages: paste a request or click one of five examples, see the offer, the verdict and the order; `/approvals`; `/orders/{id}` with both views of the audit trail; `/kitchen`; `/menu` (a menu becomes one order); `/standing-orders` (renew a standing order; drift goes to a human); `/assumptions`. Each browser has its own order book | `dev` and `demo` only, demo identity chosen on the page |
| `/v1/...` | REST API, among it `GET /v1/menus/recipes`, `POST /v1/menus/plan`, `POST` and `GET /v1/standing-orders`, `GET /v1/standing-orders/{id}`, `POST /v1/standing-orders/{id}/renew` | Bearer token |
| `/openapi.json`, `/docs` | Generated OpenAPI 3.1 and Swagger UI | Anyone |
| `/v1/schemas` | JSON Schema (2020-12) of every model | Anyone |
| `/mcp/` | MCP endpoint, Streamable HTTP, eight tools | Bearer token |
| `/healthz` | Mode, data source, head of the audit chain, which settings are set (true or false only) | Anyone |

Demo tokens are public by design and listed in `src/tta/api/demo_tokens.yaml`, for example `demo-agent-hotel-kitchen`, `demo-agent-allergy-ward`, `demo-approver-hotel-purchasing`, `demo-supplier-valio-aimo`. A first call:

```bash
curl -s -H "Authorization: Bearer demo-agent-allergy-ward" http://127.0.0.1:8000/v1/authority
```

The click-by-click demo, with the exact sentences on screen and a 90-second cut, is in [docs/DEMO.md](docs/DEMO.md). Deployment: [docs/DEPLOY.md](docs/DEPLOY.md).

## Five ways to see it

All five call the same service code, so a rule that holds on one holds on all. `$BASE` is `http://127.0.0.1:8000` or the live demo address.

1. **The pages.** Open `$BASE/`, click an example or paste a request, and read the offer, the verdict and the order. Decide on `/approvals` as a demo approver. Each browser works in its own order book.
2. **REST.** `GET $BASE/openapi.json` or `/docs`, with a demo token: `curl -s -H "Authorization: Bearer demo-agent-allergy-ward" $BASE/v1/authority`. The flow is `POST /v1/offers` → `POST /v1/orders` (with `Idempotency-Key`) → `GET /v1/orders/{id}`.
3. **MCP.** `POST $BASE/mcp/` (Streamable HTTP, POST only) with the same bearer token: eight tools, from `get_authority` to `get_audit`. No tool approves an order.
4. **The buyer agent.** `POST $BASE/v1/agent/run` with `{"text": "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"}` and the token `demo-agent-allergy-ward` (a recording is served only for the profile it was made for). The answer is the agent's run step by step: authority, offer, order. Without a Gemini key it runs from the recordings and says so.
5. **The audit views.** `GET $BASE/v1/audit?order_id=<id>&reader=buyer` with the buyer's token, or `reader=supplier` with `demo-supplier-valio-aimo`, which hides the buyer's limits, exclusions, approver names and notes. On the pages, `/orders/{id}` shows both views and whether the chain verifies.

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
| [docs/AWARDS.md](docs/AWARDS.md) | The Gemini, Modal and Context.dev write-ups, and Aiven for PostgreSQL |
| [docs/DEMO.md](docs/DEMO.md), [docs/DEPLOY.md](docs/DEPLOY.md) | The demo script; deploying, checking and stopping the Modal app |
| [docs/CONTEXTDEV.md](docs/CONTEXTDEV.md), [docs/AIVEN.md](docs/AIVEN.md) | Web evidence on the dietitian's approval card; the PostgreSQL order book and audit trail |
| [AIMO/WALKTHROUGH.md](AIMO/WALKTHROUGH.md) | What the gateway does, step by step, checked against the code |
| [AIMO/USE-CASES.md](AIMO/USE-CASES.md) | Valio's six example scenarios and ours, run against the system, with verdicts |
| [docs/PITCH.md](docs/PITCH.md) | Drafts for the pitch, the video and the submission form |
| [AIMO/SPEC.md](AIMO/SPEC.md) | The build contract |
| [AIMO/CHALLENGE.md](AIMO/CHALLENGE.md) | The challenge and its judging criteria, verbatim |
| [AIMO/FINDINGS.md](AIMO/FINDINGS.md) | Verified facts about the mock API and the data |
| [AIMO/BOOTH-QUESTIONS.md](AIMO/BOOTH-QUESTIONS.md) | Questions for Valio's mentors, each with an example |

## What is not done

- The agent's run of scenario 1 is a hand-written recording (by plan). The Finnish and photo readings were not checked against Gemini live: Gemini answered 503 and 504 on 14 Nov, so their recordings are written by hand, and the demo photo is a rendered stand-in for a phone photo. On the pages, Finnish free text runs only while Gemini answers, and no MCP tool reads a photo (`AIMO/build/handback/T18.md`). A whole agent run has no deadline, and the model's output length has no cap (`AIMO/build/handback/T10-followup.md`).
- The MCP endpoint was checked with the official SDK client only, not with a third-party host. It does not check the `Origin` header and has no OAuth flow (see docs/STANDARDS.md).
- A selling agent of Valio's own is not built.
- `EARLIEST` and `LOWER_CARBON` change no choice in tonight's capture: every confirmed product arrives on Monday 16 Nov, and carbon is close to one value per category (`docs/ASSUMPTIONS.md`). Both are tested on hand-built prices and stock.
- A preference can make the agent recommend a dearer product (10 L of `cream` ranked by reliability: €40.60 above the cheapest confirmed; `AIMO/build/handback/SUST-1.md`). A profile limit on that difference is not built.
- No MCP tool for menus or standing orders; they are REST routes and pages. The recipe table has no vegetables, fruit or herbs.
- The deployed app runs `8163d5d` (redeployed at about 13:00, 14 Nov): everything above, including Context.dev evidence, Aiven PostgreSQL, the photo and Finnish input, Your kitchen, and the four parts added on Saturday afternoon.

## Licence

MIT, see [LICENSE](LICENSE). The Valio Aimo datasets and recorded API answers are not ours and are not covered by it.

---

## Hackathon notes

The original README of this repository, kept as it was:

# junction
