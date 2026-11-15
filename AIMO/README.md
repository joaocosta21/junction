# Valio Aimo: "Trusted Trade Agents"

The documents of the challenge entry that are not code: the brief, the contract the code follows, the account of what was built, and the references for Valio Aimo's API and data. The project's front page is [../README.md](../README.md).

| File | What it holds |
|---|---|
| [CHALLENGE.md](CHALLENGE.md) | The problem statement and the judging criteria, verbatim, with our reading of them |
| [SPEC.md](SPEC.md) | The contract: interface, data shapes, states, rules. The code follows it |
| [COVERAGE.md](COVERAGE.md) | The brief's 16 items one by one: what works, the proof, the assumptions and the next steps |
| [WALKTHROUGH.md](WALKTHROUGH.md) | What the gateway does, step by step, why each piece is there, the questions asked of Valio Aimo and the decisions we took on our own |
| [USE-CASES.md](USE-CASES.md) | The brief's six example scenarios: what holds now for each, in one table |
| [FINDINGS.md](FINDINGS.md) | Facts about Valio Aimo's mock API and data, each counted from the product file or from saved answers |
| [docs/FIELD-DICTIONARY.md](docs/FIELD-DICTIONARY.md) | Every field of every payload, in one layout |
| [docs/API.md](docs/API.md) · [docs/PRODUCT-DATA.md](docs/PRODUCT-DATA.md) · [docs/SCHEMA-AND-CODES.md](docs/SCHEMA-AND-CODES.md) · [docs/CSV-DATASETS.md](docs/CSV-DATASETS.md) | One reference per source: the API, the product file, its JSON Schema and code lists, the two CSV files |
| `policy/` and `catalog_search.py` | The first drafts of Friday 13 Nov: a guardrail policy as data with its log format, and a catalog search. They were the starting point for `src/tta/policy/` and `src/tta/catalog/` and are kept unchanged; the rules in force are in `src/tta/policy/` |

Some of these documents cite the team's working notes of the weekend (the plan, the build log, the questions asked at Valio Aimo's booth) as the source of a figure or a decision. Those notes are on the branch `replan-build`, at the paths cited.

## Data files

Valio Aimo's, not ours. They are at the repository root:

```
valio_aimo_junction26_product_data.json          17,546 products, 87 MB
valio_aimo_junction26_product_data_schema.json   JSON Schema (from the portal)
valio_aimo_junction26_delivery_reliability.csv   25.2% of products
valio_aimo_junction26_carbon_footprint.csv       62.9% of products (81.2% of food)
```

Valio Aimo's own `openapi.json` comes from the portal and is not in the repository.

To fetch the three downloadable files again, from the repository root (follow redirects; the key is on the Junction challenge page):

```bash
curl -L -H "X-API-Key: $VALIO_AIMO_API_KEY" -o valio_aimo_junction26_product_data.json       https://junction26.valioaimo.fi/api/products/download
curl -L -H "X-API-Key: $VALIO_AIMO_API_KEY" -o valio_aimo_junction26_delivery_reliability.csv https://junction26.valioaimo.fi/api/delivery-reliability/download
curl -L -H "X-API-Key: $VALIO_AIMO_API_KEY" -o valio_aimo_junction26_carbon_footprint.csv     https://junction26.valioaimo.fi/api/carbon-footprint/download
```

## Valio Aimo's mock API, in short

Base `https://junction26.valioaimo.fi/api` · header `X-API-Key`. The whole reference is [docs/API.md](docs/API.md).

```
GET  /ping
POST /price         { customer: str, requestedDate: date, products: [str] }  1-1000 items
POST /availability  { same shape }
```

**There is no order endpoint, by design: the order step, its approval and its record are ours to define.** The portal's own documents (`/docs`, `/redoc`, `/openapi.json`) need the portal password, not the API key.
