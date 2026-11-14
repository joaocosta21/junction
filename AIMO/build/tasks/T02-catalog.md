# T02 — Catalog: loader, search, product types, pack size

**Scores on:** 20% (how precisely the agent matches what the buyer asked for) · Core 1 (lookup).
**Needs:** T00. **Owns:** `src/tta/catalog/`, `tests/catalog/`.
**Read first:** SPEC §3 · `AIMO/docs/PRODUCT-DATA.md` · `AIMO/docs/FIELD-DICTIONARY.md` · `AIMO/docs/CSV-DATASETS.md` · `AIMO/FINDINGS.md` §2, §4, §5 · `AIMO/catalog_search.py` (Sofia's Friday work: keep its litres logic and credit it in the module docstring).

## Build
- **Loader** for the product file at the repository root (path from config): parse once into the `Product` contract model, keeping only what the system uses (ids, English and Finnish names, vendor, category, sales unit and units, lot size, variable weight, deposits, nutritional claims, allergen statements, listed substitutes, origin when present). Join delivery reliability and carbon as optional fields; never impute a missing one.
- **Search** implementing the `Catalog` port: by product type, name terms (English first, then Finnish), required claims, category prefix, with the fallback of SPEC §3 step 3. Deterministic ordering.
- **`product_types.yaml`:** keys → category codes, name terms, claims. Must contain `milk`, `plant_drink`, `beef_chuck`, and the commonest food-service types you can derive from the catalog's categories (aim for 20 to 30). Each entry notes how it was derived.
- **Pack size** (litres or kg per sales unit) from the live price ratio, then `unitConversions`, then the product name; returns the value and its source, or "unknown".
- **Portion-pack detector** and **lot rounding** (`Decimal`, round up to the step).
- `get_product`, `listed_substitutes`, `same_category(id, digits)`.

## Tests to write first
- 17,546 products load, in under 3 seconds.
- "milk" with claim lactose-free returns exactly the 35 products of category 10400 that carry the claim (find the claim's code in the data; do not guess it).
- `464056` is found under `plant_drink`; `464744` and `466988` under `beef_chuck`.
- `463203` is a portion pack; `464306` is not, and its pack size is 1 L from the captured price.
- A product with no comparison price falls through to the next pack-size source; one with none is "unknown".
- Lot step 1.5: a need of 4 becomes 4.5. A step of 3 kg: a need of 30 stays 30, 31 becomes 33.
- 250 listed substitution pairs on 189 products.
- An unknown id returns nothing, without an exception.
- A name term with no match returns an empty result and says which term failed.

## Out of scope
Availability, allergen decisions, ranking. You return candidates; others judge them.
