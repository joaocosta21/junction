# Valio Aimo — "Trusted Trade Agents"

Our chosen main challenge. €4,000 / €2,000 / €1,000.

| File | Purpose |
|---|---|
| **[PLAN.md](PLAN.md)** | **The working plan** — ~15h schedule, roles, tech awards, cut order |
| [BOOTH-QUESTIONS.md](BOOTH-QUESTIONS.md) | Mentor questions, each with context and decision impact |
| [FINDINGS.md](FINDINGS.md) | **Read first.** 12 verified data/API traps, coverage stats, decoded code systems |
| [CHALLENGE.md](CHALLENGE.md) | The brief, rubric, scenarios, resources |
| [PLAN-30H-SUPERSEDED.md](PLAN-30H-SUPERSEDED.md) | Earlier 30h plan — over-scoped, kept for the contract schemas and scenario list |

## Data files (gitignored — fetch with the API key)
```
valio_aimo_junction26_product_data.json          17,546 products, 87MB
valio_aimo_junction26_product_data_schema.json   JSON Schema
valio_aimo_junction26_delivery_reliability.csv   25.2% coverage
valio_aimo_junction26_carbon_footprint.csv       62.9% coverage
```
Fetch (follow redirects, key from the Junction platform):
```bash
curl -L -H "X-API-Key: $VALIO_AIMO_API_KEY" https://junction26.valioaimo.fi/api/products/download
curl -L -H "X-API-Key: $VALIO_AIMO_API_KEY" https://junction26.valioaimo.fi/api/delivery-reliability/download
curl -L -H "X-API-Key: $VALIO_AIMO_API_KEY" https://junction26.valioaimo.fi/api/carbon-footprint/download
```

## API quick reference
Base `https://junction26.valioaimo.fi/api` · header `X-API-Key` · credentials in `../.env` (gitignored)
```
GET  /ping
POST /price         { customer: str, requestedDate: date, products: [str] }  1-1000 items
POST /availability  { same shape }
```
**No order endpoint exists — defining that contract is our deliverable.** Portal docs (`/docs`, `/redoc`, `/openapi.json`) need the portal password, not the API key.
