# Valio Aimo — "Trusted Trade Agents"

Our challenge. €4,000 / €2,000 / €1,000. **The judging criteria are the score to maximise:** they are quoted verbatim at the top of [../CLAUDE.md](../CLAUDE.md) and in [CHALLENGE.md](CHALLENGE.md).

| File | Purpose |
|---|---|
| **[PLAN.md](PLAN.md)** | **The working plan** — rubric mapping, response logic, schedule, tech awards, cut order |
| [SPEC.md](SPEC.md) | **The build contract** — interface, data shapes, states, rules. Code follows it |
| [build/](build/) | Overnight build: [RUNBOOK.md](build/RUNBOOK.md) (how to run), [STATUS.md](build/STATUS.md) (task board), [tasks/](build/tasks/) (one file per agent) |
| [CHALLENGE.md](CHALLENGE.md) | The problem statement and judging criteria, verbatim |
| [FINDINGS.md](FINDINGS.md) | **Read first.** Verified facts about the API and the data |
| [BOOTH-QUESTIONS.md](BOOTH-QUESTIONS.md) | Questions for the Valio mentors, each with an example to show |
| [docs/FIELD-DICTIONARY.md](docs/FIELD-DICTIONARY.md) | Every field of every payload, in one layout |
| [docs/API.md](docs/API.md) · [docs/PRODUCT-DATA.md](docs/PRODUCT-DATA.md) · [docs/SCHEMA-AND-CODES.md](docs/SCHEMA-AND-CODES.md) · [docs/CSV-DATASETS.md](docs/CSV-DATASETS.md) | Per-file references |
| [PLAN-30H-SUPERSEDED.md](PLAN-30H-SUPERSEDED.md) | Earlier, over-scoped plan. Reference only; its framing is superseded |

## Data files (gitignored inside `AIMO/` — fetch with the API key)
```
valio_aimo_junction26_product_data.json          17,546 products, 87 MB
valio_aimo_junction26_product_data_schema.json   JSON Schema (from the portal)
valio_aimo_junction26_delivery_reliability.csv   25.2% of products
valio_aimo_junction26_carbon_footprint.csv       62.9% of products (81.2% of food)
openapi.json                                     Valio's API spec (from the portal)
```
Fetch the three downloadable files (follow redirects; the key is on the Junction platform and in `../.env`):
```bash
cd AIMO
curl -L -H "X-API-Key: $VALIO_AIMO_API_KEY" -o valio_aimo_junction26_product_data.json       https://junction26.valioaimo.fi/api/products/download
curl -L -H "X-API-Key: $VALIO_AIMO_API_KEY" -o valio_aimo_junction26_delivery_reliability.csv https://junction26.valioaimo.fi/api/delivery-reliability/download
curl -L -H "X-API-Key: $VALIO_AIMO_API_KEY" -o valio_aimo_junction26_carbon_footprint.csv     https://junction26.valioaimo.fi/api/carbon-footprint/download
```

## API quick reference
Base `https://junction26.valioaimo.fi/api` · header `X-API-Key` · credentials in `../.env` (gitignored)
```
GET  /ping
POST /price         { customer: str, requestedDate: date, products: [str] }  1-1000 items
POST /availability  { same shape }
```
**There is no order endpoint, by design: the order step, its approval and its record are ours to define.** Portal docs (`/docs`, `/redoc`, `/openapi.json`) need the portal password, not the API key.
