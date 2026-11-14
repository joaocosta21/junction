# SUST-1 — Delivery time and sustainability comparison

Scores on the brief's first optional direction, verbatim: "Delivery time & sustainability comparison: not just price, but delivery reliability and the certificates/sustainability labels already shown in the webshop. (Category-level carbon-footprint ranges are a stretch goal.)" And on the 20% "how precisely the agent matches what the buyer actually asked for".

Hand back by **15:30**. Other agents work at the same time on standing orders (STAND-1), recipes (MENU-1) and a rule-based reader (FALLBACK-1).

## What exists
- `Product.delivery_reliability` (share 0–1, from `valio_aimo_junction26_delivery_reliability.csv`) and `Product.carbon_kg_co2e_per_kg` (from `valio_aimo_junction26_carbon_footprint.csv`) are loaded and shown only by `GET /v1/products/{id}`.
- Since `576e4cc`: `PurchaseRequest.prefer` (`Preference`: `PRICE` default, `EARLIEST`, `RELIABILITY`, `LOWER_CARBON`) and `RequestLine.required_labels` exist in the contract. Nothing reads them yet.
- Data facts, measured over the whole files (verify before relying on them):
  - reliability has a value for 4,426 products (243 distinct values, 0.0–1.0); the three confirmed lactose-free milks `469363`, `462775`, `463380` have **none**; `464306` has 1.0.
  - carbon has a value for 11,034 products and is close to category-level: all milks 1.1, creams 1.81, beef 26.195; only 89 of 279 categories hold more than one value. So `LOWER_CARBON` mostly separates products of different categories.
  - certificate labels are the `packagingMarkedLabel` classification group (AIMO/docs/PRODUCT-DATA.md §3.5): 19 ids, of which `warmTemperature`, `coolTemperature`, `freezeTemperature` are storage temperatures, **not** certificates. The others (e.g. `EU_ORGANIC_FARMING` 456 products, `SVANEN` 362, `MARINE_STEWARDSHIP_COUNCIL_LABEL` 104, `FAIR_TRADE_MARK` 92) are labels.

## Build
1. `Product.labels: tuple[str, ...]`: the certificate labels of `packagingMarkedLabel`, the three temperature ids left out. The catalog loader reads them.
2. Every `OfferLine` carries `delivery_reliability`, `carbon_kg_co2e_per_kg` and `labels` from its product (`None` when the file has no value: unknown, never 0 and never 1).
3. `required_labels` works as `required_claims` does: a product that lacks a required label is not a candidate, and there is one constraint check per label. `ProductQuery` may get `required_labels` too, so `POST /v1/products/search` can filter by label.
4. `prefer`:
   - `PRICE` (the default): **behaviour unchanged**. Every figure the tests and `docs/DEMO.md` pin (scenario 1: €2,580.64 and €1,010.00, scenario 2: €402.00, scenario 3: €174.00) must stay exactly as it is.
   - `EARLIEST`, `RELIABILITY`, `LOWER_CARBON`: `BEST_CONFIRMED` picks confirmed products by that key first (earliest `availableDate`; highest reliability; lowest carbon per kg), then by price; combining keeps that order. A product with no value for the key ranks after every product with one, and the option's sentence says how many lines had no value. The option's title says what it was ranked by.
   - When the cheapest confirmed option differs from the preferred one, add a fourth option kind `CHEAPEST_CONFIRMED` (contract `OptionKind`) so the trade-off is on the table, with a sentence such as "€X more than the cheapest confirmed option, for Y". `MAX_OPTIONS` may become 4 for this case only.
   - The agent still orders only the top option, and the top option is the one ranked by the buyer's preference.
5. Each option shows a comparison: the earliest and latest delivery date of its lines, the lowest reliability among its lines (or "unknown for N lines"), an estimated carbon total in kg CO2e where the quantity is in kg or litres (litres counted as kilograms: state it as an assumption), and the labels every line carries.
6. The result page (`_result.html`, `view.py`) shows per line: reliability as a percentage or "unknown", carbon per kg or "unknown", labels; and per option the comparison of item 5. One example button on `/` (in `ui/examples.py`) where the preference visibly changes the choice. **Find a real case in the capture `2026-11-14-demo`** (for example a plant drink or a protein where categories differ, or a product with a certificate label); if no case in the capture changes the choice, say so in the hand-back and pick the clearest one.

## Owns (exception to AGENT-RULES rule 1: these contract files are yours for this task)
- `src/tta/contracts/product.py` (the `labels` field), `src/tta/contracts/offer.py` (line fields, option comparison fields, `OptionKind.CHEAPEST_CONFIRMED`), `ProductQuery` in `src/tta/contracts/request.py` (only `ProductQuery`; do not change `PurchaseRequest` or `RequestLine`)
- `src/tta/catalog/` except `product_types.yaml` (MENU-1 may add product types there)
- `src/tta/offers/` **except** `offers/deps.py` and the line `context = PolicyContext(...)` in `offers/options.py`: STAND-1 edits those to pass a standing order's history. Do not reformat them.
- `src/tta/ui/view.py`, `src/tta/ui/templates/_result.html`, `src/tta/ui/templates/_marks.html`, `src/tta/ui/examples.py`
- tests under `tests/catalog/`, `tests/offers/`, and new files `tests/ui/test_sustainability_*.py`; update existing tests only where they pin a shape you changed on purpose, and say which.
- `AIMO/build/handback/SUST-1.md`, `AIMO/build/questions/SUST-1.md`

Not yours: `src/tta/api/`, `src/tta/policy/`, `src/tta/agent/` (FALLBACK-1 teaches the parser to read "organic" or "lowest carbon"), `src/tta/store/`, other templates, docs. The orchestrator writes the docs and registers anything new.

## Checks before hand-back
- `.venv/bin/python -m pytest tests/catalog tests/offers tests/ui tests/e2e -q -p no:cacheprovider` (set `COVERAGE_FILE` to a scratch path) all pass, with the pinned demo figures unchanged.
- `.venv/bin/ruff check` on every file you touched.
- In the hand-back: the example you chose, with the offer it produces under `PRICE` and under the preference (ids, totals, the comparison sentence), verified by running it in replay.
