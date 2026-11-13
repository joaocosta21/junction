# Valio Aimo — technical findings (verified against live API + 87MB catalog)

> **Corrections applied after the full per-file analysis.** Deeper detail per artifact lives in [docs/API.md](docs/API.md), [docs/PRODUCT-DATA.md](docs/PRODUCT-DATA.md), [docs/SCHEMA-AND-CODES.md](docs/SCHEMA-AND-CODES.md), [docs/CSV-DATASETS.md](docs/CSV-DATASETS.md).

## ⚠️ Superseded claims in earlier revisions of this file
| Was | Now |
|---|---|
| API returns `null` for optional fields | **It never returns null — it omits the keys.** Zero nulls across 298 products |
| Three `availableAmount` sentinels | **Eight.** Detect by magnitude `>= 1_000_000`, never an allow-list |
| Two unavailable states | **Three.** A schedule line with `availableAmount == 0.0` while `logisticModel`/`closingTime` are populated (10/244) |
| `closingTime` has two values; Terminal stale | **12 distinct values; 53% of deliverable products (129/244) are already past** |
| Allergen states: 3 (CONTAINS/FREE_FROM/MAY_CONTAIN) | **Five-state: CONTAINS · MAY_CONTAIN (9,956) · UNDECLARED (303) · FREE_FROM · SILENT** |
| `temperatureCondition` meanings unavailable | **Decodable.** 8 = ambient (18–22 °C) · 7 = frozen (−25…−18) · 1→4 = monotone chilled ladder (0–3, 2–4, 2–6, 5–8). Codes 5/6/9 (240 products) unresolved |
| `substitutions` directed, no reverse edges | **Partly symmetric — 31 of 125 unordered pairs recorded both ways.** 196 source products (not 189), 72 A→B→C chains, 35 with >1 substitute, **one self-loop: `471661` lists itself** |
| 3,068 products have "empty" `synkkaData` | **None are empty** — minimum 2 populated keys. Sparse cluster is 2–4 keys, and the 15 rich keys are *absent*, not empty |
| Pack size needs the price ratio | **`units[unitId == salesUnit].sizeInBaseUnits` works on 100% of products** — a static, API-free path (see below) |
| `nutritionalClaim` 24 values · `allergen` codes undocumented | **21 distinct ids** (24 id+unit pairs) · **allergen codes now mapped**, 30 at high confidence |
| Carbon coverage 62.9%, gaps unexplained | **81.2% on food, 0.4% on non-food** — `kg CO2-eq/kg` is a food-LCA unit |

## ⭐ The pack-size path that beats the price ratio
`salesUnit` and `baseUnit` are **always** among the product's own `units[].unitId` — zero exceptions across 17,546 products. Four invariants hold on every row: each appears exactly once; the `baseUnit` row always has `sizeInBaseUnits == 1.0`; no duplicate `unitId`s.
→ **`units[unitId == salesUnit].sizeInBaseUnits` is available on 100% of products**, needs no API call, and needs none of the undocumented unit-code translations.
⚠️ **But `synkkaData.unitConversions` has exactly ONE row per product, never a hierarchy**, and its `synkkaPackagingType` is `CASE` on 35.6% (tracking `salesUnit`: KI → CASE 6,071). So for ~1/3 of products its `netWeight`/`volume` describes **the case, not the unit** — multiplying by pack size double-counts.
⚠️ `volume` is worse than first measured: only **1,071 of 8,970 volume rows (11.9%, = 6.1% of catalog)** carry a genuine volume unit. `netWeight.unit` by contrast is clean — GRM 9,297 / KGM 489, nothing else.
⚠️ **1,660 products (9.5%) have no static pack-size signal at all.** Name-token coverage is **88.0%** (not 81.2%) once `kpl` and comma decimals are counted; 10.9% carry an `N x M` multipack pattern.

## ⭐ Allergen safety — the real numbers
- **1,485 of 4,178 `FREE_FROM_LACTOSE` products (35.5%) declare milk `AM` as `CONTAINS`.** Only 1,255 (30%) carry a positive `AM: FREE_FROM`. *Lactose-free is not dairy-free.*
- 503 claim `FREE_FROM_LACTOSE` with a **non-zero `LACS` nutrition fact**.
- `FREE_FROM_LACTOSE` and `LOW_LACTOSE` **never co-occur** — distinct claims, never union them.
- 196 `FREE_FROM_GLUTEN` products declare oats `GO` as CONTAINS.
- **2 products assert the same allergen in both `allergen` and `nonAllergen`** — `468044` (AM), `469429` (AM + AN).
- `X99` (121 CONTAINS + 74 FREE_FROM) **names no substance** — unusable for a safety claim.
- `allergen`: 44 distinct ids / 93 pairs · `nonAllergen`: 40 ids. **Mapped at high confidence:** AM milk · AW cereals-with-gluten · UW wheat · AY soy · AE eggs · AN tree nuts · SA almonds · BM mustard · GO oats · SH hazelnuts · AS sesame · NR rye · GB barley · AF fish · AP peanuts · ML lactose · AU sulphites · BC celery · AC crustaceans · NL lupin · UM molluscs. Method: the 14 most-frequent `nonAllergen` codes form a tight block (3,580–4,651, then a cliff to 1,094) = the EU's 14 mandatory declarable allergens.

## ⭐ Category codes ARE hierarchical — at 4 digits
Products sharing the first **4** digits have mean name-similarity **0.280 vs 0.025** across prefixes (11× mean, ~100× median). `cos(10400,10401) = 0.471` vs `cos(10400,52201) = 0.146`.
**A 3-digit fallback does NOT work** (median 0.110). → category-distance substitute ranking is viable without a name mapping.

## Other traps worth knowing
- **`Price.value` is ex-VAT; `PriceWithTax.value` is inc-VAT** — same field name, opposite meaning, and `PriceWithTax` has no `valueWithTax`. A shared deserialiser mixes them silently.
- **Datetime offsets have no colon** (`+0200`) — breaks `datetime.fromisoformat` on Python ≤3.10. `availableDate` is a bare date. Open-ended prices use `validTo: "9999-12-31..."`.
- **`error: true` entries have only 4 keys**; `error: false` → all four price objects present (296/296). The only independent axis is `comparisonPrice`/`comparisonUnit`, absent together on 20.8%.
- **`netPriceFound` is true on only 7 of 298 products** — nearly everything is at catalog price.
- **`classifications.packaging` is a dead group** — present on 17,535 products, empty on every one.
- **`medias` primary flag is unreliable** — 1,394 products have 0 primaries, 2,350 have 2, two have 83. `next(m for m in medias if m["primary"])` raises.
- **GTIN is not a join key** — `salesUnitGtin` and `synkkaData.gtin` differ on 6,867 products (both correct: sales unit vs consumer unit), and 27 `gtin` values are shared by 54 products. **Use `id`.**
- **Nutrient ids differ between structures** — `nutritionalContent` uses `VITD-`/`VITC-`, `classifications.vitamin` uses `VITD`/`VITC`. A join on id silently drops them.
- **The 422 body echoes the whole rejected input** — a 1,001-id request returns ~9 KB. Truncate before logging.
- **Download redirect targets need no API key** — `/files/<hash>/<name>` returns 200 unauthenticated. Endpoints return **307**.
- Dirty enums beyond `vatCode`: `countryOfOrigin` non-ISO `zy` 179 / `xs` 11 / `zz` 5 · `productionMethod` `MARINE_FISHERY1` ×3, `AQUACULTURE1` ×2 · `basisQuantityUnit` undocumented PTN/H87/KGM/GL · 6 dirty (id,unit) pairs in `nutritionFact`/`gda`.
- **`materialAdditionalDescriptions` is schema-required yet empty on 99.9%.** Present ≠ populated, everywhere.
- Delivery reliability **predicts availability**: DR < 0.75 → 22.5% empty `scheduleLines`; DR = 1.0 → 0%.


Empirical reconnaissance. Everything here was tested, not inferred from the brief.

## Portal docs are reachable programmatically
`POST https://junction26.valioaimo.fi/login` with `password=<portal password>` (form-encoded, keep the cookie) unlocks `/docs`, `/redoc` and **`/openapi.json`** at the **root** path (not `/api/openapi.json`, which 404s). Needs the session cookie, not the API key. **The OpenAPI descriptions are the best documentation in the challenge** — full field semantics for `/price` and `/availability` that appear nowhere else.

## API surface (complete — six operations, confirmed)
`GET /api/ping` · `POST /api/price` · `POST /api/availability` · `GET /api/{products,delivery-reliability,carbon-footprint}/download`

**No order, basket, quote or confirmation endpoint exists, and no schema hints at one. Defining the inquiry→commitment contract is unambiguously our deliverable.**

Request shape for both POSTs: `{customer: str, requestedDate: date, products: [str]}`, 1–1000 items, >1000 → 422.

## ⚠️ Traps that would cost hours

### 1. Both APIs ignore `requestedDate` entirely
Queried 2026-11-13, 2026-11-14, 2026-12-25 → **byte-identical responses**. `availableDate` pinned to **2026-11-16** for every product. `/price` returns identical prices for 2025-06-01, 2026-11-16 and 2027-06-01 (only `pricingDate` echoes back).
→ **"By Monday" cannot be tested as a real date constraint.** Build date logic properly, demo against 2026-11-16, don't hunt for a lead-time model that isn't there.

### 2. `MAY_CONTAIN` — undocumented third allergen value, safety-critical
Schema documents only `CONTAINS` and `FREE_FROM`. **`MAY_CONTAIN` is pervasive** (AN 1,225, AY 954, AM 728, SA 727…). **Any allergen filter written against the two documented values silently treats "may contain traces" as safe.** Highest-consequence undocumented value in the dataset.

### 3. `closingTime` is stale and contradicts availability
Server time 2026-11-13T21:33+02:00. Every **Terminal** product reports `closingTime` **2026-11-12T15:00** — over a day past — while reporting itself available on 2026-11-16. **Stock** products report 2026-11-15T17:00 (future).
→ An agent respecting the cut-off rejects every Terminal product. One ignoring it has no cut-off logic. **Surface this inconsistency in the demo — that's a trust-protocol win, not a gap.**

### 4. Multiple undocumented sentinels in `availableAmount`
Docs mention `999999` (Terminal). Also observed: **`9999999999.0`** (Stock, effectively unlimited) and **`666666666.0`** (product 463779). `if amount == 999999` is wrong, and arithmetic on these produces absurd order proposals.

### 5. ~14% of products are not orderable — and the signal is a *missing key*
11/80 sampled returned `{productId, salesBlock: false, scheduleLines: []}` with **no `logisticModel` and no `closingTime` keys**. **`salesBlock` was never observed `true`** — it is NOT the "can't buy" signal. **Empty `scheduleLines` is.**
→ Same shape is returned for a *nonexistent* product id, so don't conflate "unknown SKU" with "known but undeliverable". Use `.get()`, not `[...]`.

### 6. `comparisonPrice`/`comparisonUnit` missing on 22.5%, and rounded
Present values are 2 dp, so the pack-size trick (below) is approximate (~0.3% error) and unavailable on ~1/5 of the catalog. Fallback chain: `unitConversions.volume`/`netWeight` (volume 51.1%, netWeight 55.8%) → parse the Finnish name (81.2% carry a size token). **No field reliably gives litres for every product** — plan a three-tier fallback with a confidence flag.

### 7. `unitConversions.volume.unit` is often not a volume unit
GRM 5,498, **H87 1,500** (UN/ECE "piece"), KGM 875, LTR 762, MLT 259, CLT 50, PTN 9, MTR 8 (metres), plus 6 with space-separated compound units ("KGM H87"). Reading `.volume` as litres is wrong more often than right.

### 8. `variableUnit: true` on 632 products breaks fixed-price commitment
Sold by variable weight — "order 10 units" doesn't determine delivered quantity or price, which is exactly what the brief says orders must be based on. **Either exclude from autonomous ordering or route to human approval — a defensible guardrail rule worth stating out loud.**

### 9. `allowedLotSize` = 0.01 on 96.2% ("no constraint"), real on 674
Real steps: 2.0 (92), 3.0 (85), **1.5 (62)**, 5.0 (54), 10.0 (40), 1.0 (39), 4.0 (34), 2.5 (21), 1.8 (17). Rounding to a multiple of 1.5 or 1.8 is the edge case that produces a wrong total on stage.

### 10. Deposits are unpriceable
506 products carry deposits (576 lines, all `unit: ST`), but the 7 `material` codes resolve to **zero** catalog products and no deposit price list exists. Order totals for bottled/canned goods are incomplete and you cannot compute by how much.

### 11. `vatCode` in the file is dirty
11,719 MEDIUM, 3,068 null, 2,593 STANDARD, **159 literal `"MEDIUM MEDIUM"`**, 1 `"STANDARD MEDIUM"`, 4 empty, 1 NOT_APPLICABLE, 1 LOW. **Use `tax.taxRate` from the price API** (schema says it's authoritative). Never parse this field.

### 12. 3,068 products (17.5%) have essentially empty `synkkaData`
Same products missing `gtin`, `vatCode`, `variableUnit` — the loose fresh-produce / non-GTIN items. **Use `id` as primary key, not GTIN**, in any open-standards story.

### 13. Performance
87 MB single JSON array: `json.load` ≈15 s and ~2 GB RSS. **Build an id-indexed slim projection once** and work from that. File is clean UTF-8 (zero mojibake), but brand names carry ® and ™ which break naive slug generation.

## The pack-size shortcut (de-risks the whole unit problem)
**`catalogPrice.value / comparisonPrice.value` = litres (or kg) per sales unit.** Verified: 1.0 for a 1 L carton sold as `ST`; 10.015 for a `KI` crate of ten 1 L; 19.94 for a 2×10 L novobox; 3.7448 for 15×2.5 dl.
→ Means **we never need the undocumented sales-unit code translations.** Round to a sensible pack size; never treat as exact.

## The canonical example is satisfiable — worked end to end
"1,000 litres of lactose-free milk by Monday":
- **4,178 products** carry `nutritionalClaim = FREE_FROM_LACTOSE`. Category **10400** = drinking milk (91 products, 35 lactose-free). 24 candidates matched lactose-free + milk; all priced, 23 returned `comparisonUnit = "L"`.
- **Cheapest: `464306`** "Valio Hyvä suomalainen Arki Eila kevytmaitojuoma" — **€1.01/L** net (list €1.44, `netPriceFound: true`), `ST` = 1 L, **Stock**, `closingTime` 2026-11-15T17:00.
- → **1,000 ST = 1,000 L = €1,010.00 ex-VAT**, single line.
- Runners-up: 464401 €1.10 · 464237 €1.30 · 464119 €1.33 (crate of 10, Terminal).

## Catalog shape
17,546 products · 0 deleted · 648 vendors · 349 categories (all 5-digit, median 32 products, p90 117, max 443, 4 singletons).
Names: fi 100%, **en 99.99%** (effectively complete — no translation problem), sv 91.8%.

### ⚠️ Correction to an earlier claim
Allergen classification *groups* exist on ~99.9% of products, but are **non-empty** on far fewer:

| Classification | Non-empty |
|---|---|
| `allergen` | **41.1%** (7,205) |
| `nonAllergen` | **29.2%** (5,119) |
| `nutritionalClaim` | **43.4%** (7,618) |

→ **~59% of the catalog has no allergen statement at all.** We can only *certify* a swap on the ~29% carrying explicit `FREE_FROM`. Elsewhere, absence of `CONTAINS` is not evidence of absence. **That asymmetry (CONTAINS / MAY_CONTAIN / FREE_FROM / silent) is an interesting trust-protocol feature to build on, not merely a gap.**

## Substitution: derivable; the explicit data is a seed, not a source
250 explicit pairs over 189 products (1.1%). All targets exist. **230/250 (92%) stay inside the same `category`** — direct evidence that same-category is how Valio themselves model it. Relation is **directed** (`substitutions[].product` always equals the owner's id; no reverse edges) — symmetrise it yourself for two-way swaps.
→ Workable candidate generator: **category + brand + derived pack size + nutritionalClaim**, gated on allergen assertions. Median products per (category, brand) = 2.

## Optional axes — honest coverage
| Axis | Coverage |
|---|---|
| `deliveryReliability` | **25.2%** (4,425 rows, 243 distinct, 0.0–1.0) |
| Carbon footprint | **62.9%** (11,033 rows, 177 distinct) — mostly category-average, but 89 categories hold >1 value, so not a clean lookup |
| **Both present** | **17.8%** (3,123 products) |

→ A three-axis ranking is honest on ~1 in 6 products. **Design it to degrade explicitly (missing ≠ good) and say so in the demo.**

**`packagingMarkedLabel` is the stronger optional axis — self-describing, well populated:**
GOODS_FROM_FINLAND_BLUE_SWAN 2,057 · MADE_IN_FINLAND_FLAG_WITH_KEY 1,772 · FINNISH_HEART_SYMBOL 826 · EU_ORGANIC_FARMING 456 · SVANEN 362 · RAINFOREST_ALLIANCE 234 · EU_ECO_LABEL 195 · MSC 104 · FAIR_TRADE_MARK 92 · ASC 51 · KRAV 26 + 6 rarer.
⚠️ **Filter out the three temperature pseudo-labels** mixed into the same group (`warmTemperature` 10,057 / `coolTemperature` 4,060 / `freezeTemperature` 3,245) — not certificates.

`nutritionalClaim` (24 values, self-describing): FREE_FROM_LACTOSE 4,178 · FREE_FROM_GLUTEN 3,047 · VEGAN 2,959 · VEGETARIAN 2,358 · FREE_FROM_PRESERVATIVES 1,526 · NO_ADDED_SUGARS 662 · HIGH_FIBRE 420 · HIGH_PROTEIN 403 · LOW_SODIUM_SALT 390 · LOW_LACTOSE 321…
⚠️ The `unit` qualifier is **inconsistent** (HIGH_PROTEIN appears 403× as HIGH, 14× as DIET) — **key on the id, not the pair.**

## Code systems
**Documented in the provided JSON schema (free):** `countryOfOrigin` ISO-3166-1 alpha-2 lowercase · `countriesOfOrigin` ISO numeric · `synkkaPackagingType` · nutrient ids (ENER-KJO, ENER-E14, FAT, FASAT, CHOAVL, SUGAR-, FIBTG, PRO-, SALTEQ) · measurement units (GRM, KGM, MGM, MMT, CMT, LTR, MLT, KJO, E14) · `vatCode` STANDARD 25.5 / MEDIUM 13.5 / LOW 10 · `productionMethod` · `unitPrecision` · `variableUnit` · `allowedLotSize`.

**Documented in OpenAPI (free once logged in):** `logisticModel` Stock vs Terminal · `comparisonUnit` KG/L only · `availableAmount` 999999 = unknown/Terminal, 0 = unavailable · empty `scheduleLines` = undeliverable · `closingTime` = order cut-off.

**Self-describing:** `packagingMarkedLabel` (19 values), `nutritionalClaim` (24 values).

**NOT documented — must infer or ask:**
- **`allergen`/`nonAllergen` two-letter ids** (93 allergen pairs, 40 nonAllergen) = the **GS1 AllergenTypeCode** list, a public external code list — mappable without Valio but not derivable from the data. Top: AM 3,160 · AW 2,794 · UW 2,550 · AE 1,317 · AY · SA · SH · AS · GO · AF · BM · ML · AP · NR… plus **`X99`** (121 CONTAINS, 74 FREE_FROM) = "other/unspecified", **a trap for any allergen-safety claim**.
- **`category`** — names explicitly excluded from the dataset. Inferable from Finnish names (10400 drinking milk, 10401 liquid milk/creams, 41820 ice cream, 52201 chocolate, 22413 RTD coffee) but manual.
- **`salesUnit`/`baseUnit`/`units[].unitId`** — schema says translations are not included. Observed: KI 8,005 · ST 5,607 · KG 1,068 · PAK 880 · BAG 697 · RAS 328 · PRK 320 · BOT 310 · SK 120 · CS 72 · KLE 66 · KRT 48 · KAN 13 · PAL 4 · NIP 3 · DSP 3 · DZ 2 (+ KRS, ZML inside `units`). **Not needed if we use the price-ratio trick.**
- **`temperatureCondition`** 1–9: 8 → 10,053 · 7 → 3,152 · 4 → 1,803 · 3 → 1,673 · 2 → 324 · 1 → 240 · 5 → 221 · null → 61 · 6 → 10 · 9 → 9. Meanings excluded, and it does **not** map cleanly to logistic model — don't assume 8 = ambient. Use `minTemperature`/`maxTemperature` instead.
- Fishing area/method codes, GHS h/p statements, producer GLNs, deposit `material` codes.

## Rate limits
"Undisclosed", with an explicit warning: *"solutions should not be based on frequently retrieving prices and availabilities for all products… Query the APIs only when you have narrowed down the products based on static product data."*
80-id batches and ~15 calls drew no 429. **Practical ceiling untested.** Architect for: filter locally on static data first, then one narrow API call.

Also confirmed empirically: **`customer` does not affect responses** (6 different strings → identical output).
