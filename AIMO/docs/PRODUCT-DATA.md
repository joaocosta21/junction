# `valio_aimo_junction26_product_data.json` — complete field reference

Everything below was measured against the actual file (87 MB, JSON array, **17,546 product objects**), not inferred from the schema. Percentages are always *of all 17,546 products* unless stated otherwise.

Companion docs: [`FINDINGS.md`](../FINDINGS.md) (verified API and catalog findings), `valio_aimo_junction26_product_data_schema.json` (official JSON Schema, the source of all field *meanings* quoted here).

Conventions used in this doc:
- **present** = the key exists on the object.
- **non-empty** = key exists *and* is not `null`, `""`, `[]` or `{}`. For arrays and the `classifications` groups, this distinction is the whole story — several groups are present on ~100% of products and empty on most of them.

Loading cost: `json.load` takes about half a second and ~0.6–0.7 GB peak RSS (measured 2026-11-14, Python 3.13). The slim index in §7 is what the query recipes there run against; it is not needed for load time.

---

## 1. Top-level field reference

| Field | Type | Present | Non-empty | Required | Meaning | Example |
|---|---|---|---|---|---|---|
| `id` | string | 100% | 100% | **yes** | Product code. The key used by `/price`, `/availability` and the two CSVs. Always exactly **6 numeric digits**, zero duplicates. | `"464306"` |
| `salesUnit` | string | 100% | 100% | **yes** | Unit the product is *ordered and priced* in. Untranslated technical code. | `"ST"` |
| `baseUnit` | string | 100% | 100% | **yes** | Base unit of measure. Equal to `salesUnit` on 10,924 products (62.3%). | `"ST"` |
| `category` | string | 100% | 100% | **yes** | 5-digit category code. **Names are deliberately not in the dataset.** | `"10400"` |
| `allowedLotSize` | number | 100% | 100% | **yes** | Order-quantity step, in sales units. | `0.01` |
| `deleted` | boolean | 100% | 100% | **yes** | Always `false` (0 deleted products in the file). Ignore it. | `false` |
| `vendorName` | string | 100% | 100% | **yes** | Supplier name, UPPERCASE, 648 distinct. | `"VALIO OY TUORE"` |
| `synkkaData` | object | 100% | 100% | **yes** | Manufacturer-supplied GS1 Synkka block. See §2. Never `null`, but comes in two very different shapes. | `{...}` |
| `units` | array | 100% | 100% | **yes** | Packaging hierarchy. Always ≥1 row. See below. | `[{...}]` |
| `countryOfOrigin` | string | 99.95% | 99.95% | no | Lowercase ISO 3166-1 alpha-2. 97 distinct values. **9 products missing.** | `"fi"` |
| `temperatureCondition` | integer | 99.65% | 99.65% | no | Storage/transport class 1–9. Meanings not in the dataset (see §4). **61 missing.** | `4` |
| `salesUnitGtin` | string | 99.09% | 99.09% | no | GTIN of the **sales unit**. **159 missing.** No duplicate values. | `"6408430000487"` |
| `deposits` | array | 100% | **2.88%** (506) | **yes** (may be `[]`) | Returnable-packaging charges. See below. | `[]` |
| `substitutions` | array | **1.12%** (196) | **1.08%** (189) | no | Explicit replacement products. 7 products carry the key with an empty array. See §6. | `[]` |

There is **no top-level `names` field** — product names live only at `synkkaData.names`.

### `units[]` — packaging hierarchy (44,357 rows total)

| Field | Type | Coverage (of rows) | Meaning |
|---|---|---|---|
| `unitId` | string | 100% | Unit code. 23 distinct values (§4). |
| `sizeInBaseUnits` | number | 100% | How many `baseUnit`s this unit contains. |
| `gtin` | string | 80.9% (35,881) | Barcode of *this* packaging level. |

Rows per product: 2 → 6,645 · 3 → 4,532 · 4 → 3,626 · 1 → 2,693 · 5 → 34 · 6 → 11 · 8 → 3 · 7 → 2.

**Three invariants hold on all 17,546 products** (verified, and the schema does not promise them — rely on them but assert them):
1. `salesUnit` appears in `units[]` exactly once.
2. `baseUnit` appears in `units[]` exactly once.
3. The `baseUnit` row always has `sizeInBaseUnits == 1.0`.
4. No product has two rows with the same `unitId`.

Consequence, and the most useful thing in this array: **`units[unitId == salesUnit].sizeInBaseUnits` gives base-units-per-sales-unit for 100% of the catalog.** It is 1.0 on 10,944 products (62.4%) and >1 on 6,602. Only two products have a non-integer value (18.5 and 2.5). This is a fully-covered multiplier — see §5, tier 2b.

Most common unitId sets: `(KI,ST)` 3,152 · `(KI,KRS,PAL,ST)` 2,459 · `(KI,PAL,ST)` 1,568 · `(ST)` 1,340 · `(KI,KRS,PAL)` 614.

### `deposits[]` — 506 products, 576 rows

| Field | Type | Coverage | Meaning |
|---|---|---|---|
| `material` | string | 100% | Product code of the deposit material. 7 distinct: `1` (160), `4` (155), `3` (119), `171` (69), `147` (46), `2` (25), `9708918` (2). |
| `quantity` | number | 100% | Deposit units per sales unit. 24.0 (273) · 12.0 (142) · 1.0 (98) · 6.0 (42) · 20.0 (7) · 16.0 (4) · 8.0 (3) · 2.0/4.0/18.0 (2 each) · 30.0 (1). |
| `unit` | string | 100% | Always `"ST"` (576/576). |

436 products have 1 deposit line, 70 have 2. **None of the 7 `material` codes resolves to a product `id` in this catalog**, and no deposit price list exists anywhere in the challenge data — deposit money is unpriceable (FINDINGS.md §4).

### `substitutions[]` — 250 rows

| Field | Type | Coverage | Meaning |
|---|---|---|---|
| `product` | string | 100% | The product being substituted. **Always equals the owning object's `id`** (250/250) — fully redundant. |
| `substituteProduct` | string | 100% | The replacement's `id`. All 250 resolve to live catalog products. |

Full analysis in §6.

---

## 2. `synkkaData` field reference

`synkkaData` exists on every product but has **exactly two shapes**:

- **Rich shape — 14,478 products (82.51%).** Has `gtin`, and with it `lastUpdated`, `variableUnit`, `vatCode`, `unitConversions`, `producers`, `countriesOfOrigin`, `brand`, `storageInstructions`, `disposalInformations`, `ingredients`, `usageInstructions`, `preparationInstructions`, `safetyData`, `fishingReports`.
- **Thin shape — 3,068 products (17.49%).** Exactly 7 keys (`names`, `classifications`, `keyIngredients`, `marketingTexts`, `materialAdditionalDescriptions`, `medias`, `nutritionalContent`), plus `mediasLastUpdated` on 122 of them. **All 15 rich-shape keys are absent, not empty** — `o["synkkaData"]["vatCode"]` raises `KeyError`. Always use `.get()`.

| Key | Type | Present | Non-empty | Meaning / notes | Example |
|---|---|---|---|---|---|
| `names` | array | 100% | 100% | `{language, value}` per language. See §2.1. | `[{"language":"fi","value":"Valio kahvimaito 1 l laktoositon UHT"}]` |
| `classifications` | array | 100% | **99.94%** (17,535) | Grouped feature values. Entire §3. 11 products have `[]`. | see §3 |
| `keyIngredients` | array | 100% | 80.06% | Free-text key-ingredient statement per language. | `[{"language":"fi","value":"rasvaton maito"}]` |
| `medias` | array | 100% | 76.23% | `{id:int, primary:bool}`. Files themselves are not in the dataset. | `[{"id":123456,"primary":true}]` |
| `nutritionalContent` | array | 100% | 69.82% | Nutrition declaration. See §2.2. | see §2.2 |
| `marketingTexts` | array | 100% | 67.91% | Marketing copy per language. **0 of the 3,068 thin products have any.** | `[{"language":"fi","value":"..."}]` |
| `materialAdditionalDescriptions` | array | 100% | **0.06%** (11) | Extra description, e.g. multipack contents. Effectively unusable. | `[]` |
| `gtin` | string | 82.51% | 82.51% | GTIN of the **consumer unit**. The shape discriminator. | `"6408430000487"` |
| `lastUpdated` | string | 82.51% | 82.51% | ISO 8601 with a `+0300` (13,623) or `+0200` (855) offset. Range **2022-10-22 → 2025-10-05**. | `"2025-10-05T21:28:56+0300"` |
| `variableUnit` | boolean | 82.51% | 82.51% | `true` on **632** products (628 with `salesUnit` `KG`, 4 with `KI`), `false` on 13,846, **absent on 3,068**. `true` = sold by variable weight (FINDINGS.md §4). | `false` |
| `vatCode` | string | 82.51% | 82.49% | Finnish VAT class. **Dirty — see §4.** Use `tax.taxRate` from `/price`. | `"MEDIUM"` |
| `unitConversions` | array | 82.51% | 82.49% | Weights/dimensions. **Exactly one row per product, never more.** See §5. | see §5 |
| `producers` | array | 82.51% | 82.45% | `{id (13-digit GLN), name}`. Exactly 1 row when present; 334 distinct GLNs. | `[{"id":"6408430000008","name":"Valio Oy"}]` |
| `countriesOfOrigin` | array | 82.51% | 82.43% | Numeric ISO 3166-1 strings, zero-padded. Top: `246` fi (6,976) · `276` de (987) · `752` se (770) · `380` it (551) · `528` nl (521). 1 entry on 14,347, 2 on 69, 3 on 35, 4 on 5, 6 on 3. | `["246"]` |
| `brand` | string | 82.43% | 82.43% | 1,500 distinct (1,465 after trimming whitespace). Top: Valio 773 · DUNI 639 · Fazer 349 · Atria 283 · Santa Maria 251. | `"Valio"` |
| `mediasLastUpdated` | string | 76.23% | 76.23% | Present on exactly the products with ≥1 media. | `"2024-03-11T09:00:00+0200"` |
| `maxTemperature` | number | 58.51% | 58.51% | Max storage °C. | `8.0` |
| `minTemperature` | number | 57.88% | 57.88% | Min storage °C. 72 products have `min` without `max`; 7,208 have neither. **No product has min > max.** | `2.0` |
| `storageInstructions` | array | 82.51% | 49.39% | Free text per language. | `[{"language":"fi","value":"Säilytä 2–8 °C"}]` |
| `disposalInformations` | array | 82.51% | 26.40% | Recycling instructions per language. | `[{"language":"fi","value":"Kartonkipakkaus"}]` |
| `ingredients` | array | 82.51% | **21.35%** (3,746 products, 3,746 rows) | Structured ingredient list: `{sequence, names[], percentage, origins[]}`. Too sparse to rely on. | see schema |
| `usageInstructions` | array | 82.51% | 21.05% | Free text per language. | — |
| `preparationInstructions` | array | 82.51% | 19.83% | Free text per language. | — |
| `safetyData` | array | 82.51% | **3.80%** (667) | GHS sheets: 681 HazardStatement + 1,411 PrecautionaryStatement rows. Codes (`h319`, `p280`) undocumented here. | — |
| `fishingReports` | array | 82.51% | **2.01%** (353) | `{id, name (Latin), catchMethods[{areas[], methods[], productionMethod}]}`. | — |

### 2.1 `names` — the one near-complete text field

| Language | Products |
|---|---|
| `fi` | **17,546 (100%)** — never empty or whitespace |
| `en` | 17,544 (99.99%) — only 2 missing |
| `sv` | 16,100 (91.76%) — 1,446 missing |
| `es` | 10 |
| `nl` | 2 |

No product has two entries for the same language. Entries per product: 3 → 16,104 · 2 → 1,437 · 5 → 2 · 1 → 2 · 4 → 1.

**923 Finnish names contain `®` or `™`** — break naive slugging/matching.

### 2.2 `nutritionalContent` (12,251 products, 114,754 rows)

Per row: `id`, `value`, `unit`, `basisQuantity`, `basisQuantityUnit`, optional `dailyValueIntakePercent`, `servingSize`, `servingSizeUnit`, `unitPrecision`.

- `basisQuantity`: 100.0 on 113,093 rows (98.6%); also 40.0 (277), 1.0 (229), 30.0 (221), 35.0 (83), 70.0 (75).
- `basisQuantityUnit`: GRM 103,294 · MLT 11,230 · **PTN 164 · H87 30 · KGM 27 · GL 9** (the last four are not in the schema's documented list).
- `unitPrecision`: APPROXIMATELY 107,160 · *(absent)* 5,156 · LESS_THAN 2,424 · LESS_THAN_OR_EQUAL 8 · ABOUT 6.
- Top ids: ENER-KJO 12,178 · PRO- 12,164 · FAT 12,153 · CHOAVL 12,138 · ENER-E14 12,080 · SALTEQ 11,952 · FASAT 11,889 · SUGAR- 11,841 · FIBTG 6,070 · LACS 3,573 · NA 1,078 · CA 954 · **VITD- 602 · VITB12 583 · FAMSCIS 567** · FAPUCIS 525 · RIBF 494 · **VITC- 394** · ZN 329 · K 313.

⚠️ **Three vitamin ids are spelled two ways inside `nutritionalContent`**: `VITD-` 602 / `VITD` 8, `VITC-` 394 / `VITC` 7, `VITE-` 223 / `VITE` 1 (never both on one product). For these three, `classifications.vitamin` carries only the hyphen-less spelling (8 / 7 / 1 values), and each of its 1,075 values has an identically spelled row in the same product's `nutritionalContent`, so a join on id drops nothing; the hyphenated rows have no `vitamin`-group counterpart at all. Normalise the trailing hyphen when aggregating one nutrient across products.

### 2.3 What characterises the 3,068 thin-`synkkaData` products

Measured directly on that subset:

- **No `brand`, no `producers`, no `vatCode`, no `variableUnit`, no `unitConversions`, no `gtin`, no `lastUpdated`, no `countriesOfOrigin`.**
- **Zero `marketingTexts`** (0/3,068). `keyIngredients` on 1,124; `nutritionalContent` on 731; `medias` on only 122.
- `classifications` is present on all 3,068, but with only **5 groups** (`allergen`, `nonAllergen`, `nutritionalClaim`, `packaging`, `packagingMarkedLabel`) on 2,337 of them, +`nutritionFact` on the other 731. The DECIMAL groups `gda`/`mineral`/`vitamin`/`composition` **never** appear.
- Still fully present: `id`, `salesUnit`, `baseUnit`, `category`, `allowedLotSize`, `vendorName`, `units`, and `salesUnitGtin` on 2,915 of 3,068.
- Top categories: **20012 (119), 20022 (108), 20031 (105), 20033 (85), 20032 (82), 20021 (76), 41731 (76), 20011 (60)** — the `200xx` codes are kitchen equipment, tableware and glassware, 41731 is frozen vegetables — plus 558 of the 901 products in the 174xx fresh-produce block.
- Top vendors: WULFF OY AB (232, office supplies), SAMBONET PADERNO (177, tableware), HEUSCHEN&SCHROUFF ORIENTAL FOODS (118), VALIO OY / VALIO AIMO (97), BUD HOLLAND B.V. (91), STAAY FOOD GROOP (91), MASTERMARK BRANDS (91), SAVO-KARJALAN LIHA (80).
- Sample fi names: `TOMAATTI "TOM BERRY" 125G RASIA HOLLANT`, `CHAMP RUSKEA HERKKUSIENI 2KG/LTK SUOMI`, `AVOMAANKURKKU SUOMI`, `BATAATTI LILA USA`, `KUKKAKAALI LILA SUOMI`.

**Characterisation:** two populations — (a) loose **fresh produce and fresh meat** bought by weight, which never passes through GS1 Synkka because there is no consumer barcode, and (b) **non-food / HoReCa hardware** (office supplies, tableware, cleaning) from vendors that do not publish Synkka data. Their names are terse uppercase operator strings, not marketing names.

**Rule: use `id` as the primary key. GTIN is unusable as a join key** — missing on 3,068 (`synkkaData.gtin`) / 159 (`salesUnitGtin`), and the two differ on 6,867 products where both exist (consumer unit vs sales unit — both are correct, they are different things).

---

## 3. `synkkaData.classifications` in depth

An array of up to 10 groups, each `{name, type, values[]}`. Each value is `{id, synkkaId?, unit?, value?}`.

**Group count per product:** 10 → 14,467 · 5 → 2,337 · 6 → 731 · 0 → 11. **No product ever repeats a group name**, so `{g["name"]: g for g in classifications}` is safe.

The five `ENUM` groups are present on all 17,535 products that have any classifications; the five `DECIMAL` groups (`nutritionFact`, `gda`, `mineral`, `vitamin`, `composition`) only on the richer subset.

| Group | `type` | Present | **Non-empty** | Distinct ids | Median / max values |
|---|---|---|---|---|---|
| `packagingMarkedLabel` | ENUM | 99.94% | **98.34%** (17,255) | 19 | 1 / 5 |
| `nutritionFact` | DECIMAL | 86.62% (15,198) | **69.78%** (12,244) | 13 | 8 / 13 |
| `gda` | DECIMAL | 82.45% (14,467) | **65.62%** (11,513) | 10 | 8 / 10 |
| `nutritionalClaim` | ENUM | 99.94% | **43.42%** (7,618) | 21 | 0 / 10 |
| `allergen` | ENUM | 99.94% | **41.06%** (7,205) | 44 | 0 / 21 |
| `nonAllergen` | ENUM | 99.94% | **29.17%** (5,119) | 40 | 0 / 33 |
| `mineral` | DECIMAL | 82.45% | **10.16%** (1,783) | 12 | 0 / 12 |
| `vitamin` | DECIMAL | 82.45% | **4.14%** (727) | 7 | 0 / 4 |
| `composition` | DECIMAL | 82.45% | **0.08%** (14) | 3 | 0 / 2 |
| `packaging` | ENUM | 99.94% | **0.00% (0)** | 0 | 0 / 0 |

⚠️ **`packaging` is a dead group**: present on 17,535 products, `values` empty on every single one. The schema advertises it; there is nothing in it.

### 3.1 `allergen` — 7,205 products, 44 ids, **four** qualifier states

`unit` values across the whole group: **CONTAINS 15,610 values / 6,847 products · MAY_CONTAIN 9,956 / 2,685 · UNDECLARED 303 / 33.**

⚠️ The schema documents only `CONTAINS` and `FREE_FROM`. In `allergen` the real values are **CONTAINS, MAY_CONTAIN and UNDECLARED** — `FREE_FROM` never appears here, it lives in `nonAllergen`. `UNDECLARED` (33 products) is a **fourth** state.

Meanings of the relation values in GS1's level-of-containment code list (T4079) — Valio's use of them is to be confirmed with Valio: `CONTAINS` "Intentionally included in the product."; `MAY_CONTAIN` not intentionally included, but may be present through shared production; `UNDECLARED` "Not intentionally included in the product and assessed not to require a cross-contact declaration"; `FREE_FROM` "The product is free from the indicated substance."

Full id list (all 44) with per-qualifier value counts:

| id | total | CONTAINS | MAY_CONTAIN | UNDECLARED |
|---|---|---|---|---|
| AM | 3,902 | 3,160 | 728 | 14 |
| AW | 3,113 | 2,794 | 300 | 19 |
| UW | 2,899 | 2,550 | 348 | 1 |
| AY | 2,077 | 1,104 | 954 | 19 |
| AE | 1,910 | 1,317 | 574 | 19 |
| AN | 1,538 | 289 | 1,225 | 24 |
| SA | 931 | 204 | 727 | — |
| BM | 890 | 467 | 400 | 23 |
| GO | 857 | 569 | 288 | — |
| SH | 796 | 138 | 658 | — |
| AS | 778 | 162 | 594 | 22 |
| NR | 731 | 431 | 300 | — |
| GB | 627 | 393 | 231 | 3 |
| AF | 546 | 476 | 49 | 21 |
| AP | 532 | 73 | 437 | 22 |
| ML | 527 | 449 | 78 | — |
| ST | 390 | 34 | 356 | — |
| AU | 354 | 267 | 65 | 22 |
| SW | 350 | 18 | 332 | — |
| SC | 326 | 58 | 268 | — |
| BC | 324 | 135 | 166 | 23 |
| SP | 290 | 10 | 280 | — |
| SM | 177 | 5 | 172 | — |
| SR | 171 | 3 | 168 | — |
| NL | 145 | 5 | 116 | 24 |
| **X99** | 121 | 121 | — | — |
| AC | 118 | 51 | 43 | 24 |
| NM | 94 | 89 | 5 | — |
| UM | 89 | 19 | 47 | 23 |
| GS | 45 | 12 | 33 | — |
| NE | 38 | 38 | — | — |
| NC | 37 | 37 | — | — |
| NW | 33 | 33 | — | — |
| CM | 19 | 19 | — | — |
| BF | 18 | 18 | — | — |
| NK | 18 | 18 | — | — |
| SO | 17 | 16 | 1 | — |
| PO | 9 | 9 | — | — |
| ABD | 7 | 5 | 2 | — |
| NP | 7 | 4 | 3 | — |
| GK | 7 | — | 7 | — |
| BP | 6 | 6 | — | — |
| ADQ | 3 | 3 | — | — |
| PN | 2 | 1 | 1 | — |

The two-letter ids are the public **GS1 AllergenTypeCode** list (AM = milk, AW = cereals containing gluten, AE = egg, AN = nuts, AS = sesame, AY = soy, …) — mappable from an external code list, not derivable from this file. **`X99`** is defined in GS1's allergen type code list (T4078) as "Does not contain declaration obligatory allergens in the product." It is on 121 products, always with `unit` `CONTAINS`; 120 of them carry no other allergen code, and 103 of those also have an empty `nonAllergen` group. Whether Valio uses the GS1 meaning is to be confirmed with them. `ABD`/`ADQ` are 3-character outliers in an otherwise 2-character space.

### 3.2 `nonAllergen` — 5,119 products, 40 ids, one qualifier

`unit` is **`FREE_FROM` on 68,597 of 68,597 values (100%)**. The group *is* the FREE_FROM assertion; the qualifier carries no information.

Full id list: UM 4,651 · AC 4,632 · NL 4,629 · AU 4,563 · BC 4,560 · AF 4,518 · AP 4,501 · AS 4,353 · BM 4,270 · AN 4,225 · AE 4,026 · AY 3,927 · AM 3,586 · AW 3,580 · ML 1,094 · GS 700 · SC 685 · GB 641 · SW 633 · ST 630 · SA 587 · GO 558 · SH 554 · NR 552 · UW 512 · GK 288 · SM 272 · SP 272 · SR 272 · X99 74 · NC 49 · NK 47 · NW 47 · NE 46 · NM 45 · UN 9 · SO 3 · PN 2 · PO 2 · BF 2.

Note the shape: a product that files a `nonAllergen` block typically files ~13 ids at once (the full EU-14 minus the ones it contains), which is why the top 14 ids all sit near 3,600–4,650.

`X99` also appears here, on 74 products (`FREE_FROM`). GS1 defines `X99` as "Does not contain declaration obligatory allergens in the product." (§3.1); how Valio intends `X99` with `FREE_FROM` is to be confirmed with them.

### 3.3 The four-state allergen model

For a product *p* and allergen code *a*, exactly one of:

| State | Source | Products with ≥1 such assertion |
|---|---|---|
| **CONTAINS** | `allergen`, `unit == "CONTAINS"` | 6,847 |
| **MAY_CONTAIN** | `allergen`, `unit == "MAY_CONTAIN"` | 2,685 |
| **UNDECLARED** | `allergen`, `unit == "UNDECLARED"` | 33 |
| **FREE_FROM** | `nonAllergen` (always FREE_FROM) | 5,119 |
| **SILENT** | neither group mentions *a* | — |

**10,341 products (58.9%) have an empty `allergen` group**, and **12,427 (70.8%) have an empty `nonAllergen` group**; **8,110 (46.2%) have neither group populated** — 30.6% of food products and 99.8% of non-food (category prefixes `63`/`64`/`20`/`90`). Silence is the default, and it is **not** evidence of absence. Only the 5,119 with `nonAllergen` can be *certified* free of anything.

### 3.4 `nutritionalClaim` — 7,618 products, 21 ids, 5 qualifiers

`unit` by product: FREE_FROM 5,893 · DIET 4,257 · HIGH 802 · LOW 738 · NO_ADDED 662.

| id | products | qualifier split |
|---|---|---|
| FREE_FROM_LACTOSE | 4,178 | FREE_FROM 4,178 |
| FREE_FROM_GLUTEN | 3,049 | FREE_FROM 3,047, **DIET 2** |
| VEGAN | 2,959 | DIET 2,959 |
| VEGETARIAN | 2,358 | DIET 2,358 |
| FREE_FROM_PRESERVATIVES | 1,526 | FREE_FROM 1,526 |
| FREE_FROM_COLOURING_AGENTS | 932 | FREE_FROM 932 |
| FREE_FROM_ADDITIVES | 690 | FREE_FROM 690 |
| NO_ADDED_SUGARS | 662 | NO_ADDED 662 |
| HIGH_FIBRE | 420 | HIGH 420 |
| FREE_FROM_EGGS | 418 | FREE_FROM 418 |
| HIGH_PROTEIN | 417 | HIGH 403, **DIET 14** |
| LOW_SODIUM_SALT | 390 | LOW 390 |
| FREE_FROM_SWEETENERS | 358 | FREE_FROM 358 |
| FREE_FROM_SOY | 337 | FREE_FROM 337 |
| LOW_LACTOSE | 321 | LOW 321 |
| FREE_FROM_FAT | 158 | FREE_FROM 158 |
| FREE_FROM_WHEAT | 141 | FREE_FROM 141 |
| LOW_FAT | 110 | LOW 109, **DIET 1** |
| FREE_FROM_ARTIFICIAL_SWEETENERS | 24 | FREE_FROM 24 |
| FREE_FROM_GMO | 14 | FREE_FROM 14 |
| FREE_FROM_SODIUM_SALT | 13 | FREE_FROM 13 |

⚠️ **21 distinct ids but 24 distinct (id, unit) pairs** — the qualifier is inconsistent for 4 ids. **Always key on `id` alone.**

### 3.5 `packagingMarkedLabel` — 17,255 products, 19 ids, `unit` always absent

`unit` is absent on all 23,582 values. Median 1 label per product, max 5.

| id | products |
|---|---|
| **warmTemperature** | 10,057 |
| **coolTemperature** | 4,060 |
| **freezeTemperature** | 3,245 |
| GOODS_FROM_FINLAND_BLUE_SWAN | 2,057 |
| MADE_IN_FINLAND_FLAG_WITH_KEY | 1,772 |
| FINNISH_HEART_SYMBOL | 826 |
| EU_ORGANIC_FARMING | 456 |
| SVANEN | 362 |
| RAINFOREST_ALLIANCE | 234 |
| EU_ECO_LABEL | 195 |
| MARINE_STEWARDSHIP_COUNCIL_LABEL | 104 |
| FAIR_TRADE_MARK | 92 |
| AQUACULTURE_STEWARDSHIP_COUNCIL | 51 |
| KRAV_MARK | 26 |
| OFFICIAL_ECO_LABEL_SUN | 17 |
| SOIL_ASSOCIATION_ORGANIC_SYMBOL | 11 |
| PUHTAASTI_KOTIMAINEN | 7 |
| DOLPHIN_SAFE | 7 |
| UTZ_CERTIFIED | 3 |

⚠️ The **first three are not certificates** — they are storage-temperature pseudo-labels (17,362 of the 23,582 values, 73.6%) smuggled into the certificate group. Filter them out, *and* note they are the best-covered temperature signal in the file: `warmTemperature` + `coolTemperature` + `freezeTemperature` covers far more products than `min`/`maxTemperature` does.

### 3.6 DECIMAL groups

**`nutritionFact`** — 12,244 products. `unit`: GRM 82,436 · KJO 12,182 · E14 12,080 · **MGM 1 · MC 1**. Ids: ENER-KJO 12,178 · PRO- 12,164 · FAT 12,153 · CHOAVL 12,138 · ENER-E14 12,080 · SALTEQ 11,952 · FASAT 11,889 · SUGAR- 11,841 · FIBTG 6,070 · **LACS 3,573** · FAPUCIS 525 · POLYL 109 · STARCH 28. Dirty pairs: `FAT|KJO` ×4, `SALTEQ|MGM` ×1, `LACS|MC` ×1.

**`gda`** — 11,513 products, same 10 ids and units as `nutritionFact` minus FAPUCIS/POLYL/STARCH, carrying the %-of-reference-intake figures. FAT 11,480 · CHOAVL 11,479 · ENER-KJO 11,467 · PRO- 11,464 · SALTEQ 11,369 · ENER-E14 11,365 · FASAT 11,330 · SUGAR- 11,285 · FIBTG 6,070 · LACS 3,573. Same 4 dirty `FAT|KJO` rows.

**`mineral`** — 1,783 products, 12 ids, `unit` MGM 3,196 / GRM 336 / MC 49. NA 1,078 · CA 954 · ZN 329 · K 313 · FE 311 · MG 264 · P 260 · SE 27 · MN 17 · CU 12 · CLD 10 · FD 6. ⚠️ **Unit varies per id** — NA is MGM 789× / GRM 285× / MC 4×; K is MGM 273× / GRM 40×; MN is MC 9× / MGM 8×. Always read the row's own `unit`.

**`vitamin`** — 727 products, 7 ids, `unit` MC 854 / MGM 221. VITB12 583 (MC 582, MGM 1) · VITA- 249 (MC) · VITB6- 213 (MGM 212, MC 1) · VITK 14 (MC) · VITD 8 (MC) · VITC 7 (MGM) · VITE 1 (MGM).

**`composition`** — 14 products. CAFFN 12 (MGM 11, GRM 1) · NUCLEOTIDE 2 (MGM) · TAU 2 (MGM).

---

## 4. Enumerations, full distributions

### `salesUnit` — 17 values, complete

| | | | | |
|---|---|---|---|---|
| KI 8,005 (45.62%) | ST 5,607 (31.96%) | KG 1,068 (6.09%) | PAK 880 (5.02%) | BAG 697 (3.97%) |
| RAS 328 (1.87%) | PRK 320 (1.82%) | BOT 310 (1.77%) | SK 120 (0.68%) | CS 72 (0.41%) |
| KLE 66 (0.38%) | KRT 48 (0.27%) | KAN 13 (0.07%) | PAL 4 (0.02%) | NIP 3 (0.02%) |
| DSP 3 (0.02%) | DZ 2 (0.01%) | | | |

### `baseUnit` — 16 values (same space minus `KLE`)

ST 9,770 (55.68%) · PAK 1,725 · KI 1,573 · BAG 1,222 · KG 1,106 · BOT 893 · PRK 533 · RAS 494 · SK 89 · CS 74 · KRT 41 · KAN 14 · PAL 4 · NIP 3 · DSP 3 · DZ 2.

### `units[].unitId` — 23 values (superset of the two above)

KI 14,157 · ST 9,832 · **PAL 8,303** · **KRS 5,288** · PAK 1,813 · BAG 1,246 · KG 1,131 · BOT 903 · PRK 534 · RAS 524 · CS 227 · SK 129 · KRT 97 · KLE 69 · **ZML 37** · **DOL 26** · KAN 14 · DSP 11 · **KOR 6** · NIP 5 · **PNT 2** · DZ 2 · **MDO 1**.

`PAL`, `KRS`, `ZML`, `DOL`, `KOR`, `PNT`, `MDO` appear only inside `units[]` (pallet / crate-stack / display levels), never as a `salesUnit` except `PAL` on 4 products. Translations are explicitly excluded from the dataset — and §5 shows you do not need them.

### `temperatureCondition` — 9 values, key absent on 61 products

| code | products | dominant (min,max) °C | reading |
|---|---|---|---|
| 8 | 10,053 (57.30%) | *(none)* 4,859; **18–22** 1,905; 5–25 578; 2–25 250 | ambient / dry |
| 7 | 3,152 (17.96%) | **−25…−18** 1,443; *(none)* 628; −24…−18 233 | frozen |
| 4 | 1,803 (10.28%) | *(none)* 977; **5–8** 254; 4–8 212; 2–8 123 | chilled, upper band |
| 3 | 1,673 (9.53%) | **2–6** 767; *(none)* 319; 3–6 191 | chilled |
| 2 | 324 (1.85%) | 2–4 99; *(none)* 66; 2–6 62 | cold chilled |
| 1 | 240 (1.37%) | 0–3 97; *(none)* 81; 0–4 30 | coldest chilled |
| 5 | 221 (1.26%) | *(none)* 208 | unclear |
| *(absent)* | 61 (0.35%) | *(none)* 60 | — |
| 6 | 10 (0.06%) | *(none)* 6; 4–20 2 | unclear |
| 9 | 9 (0.05%) | mixed | unclear |

**Evidence-based refinement of an earlier `FINDINGS.md`:** the code *does* correlate strongly with a temperature band — 1→2→3→4 is a monotone chilled ladder, 7 is frozen, 8 is ambient. What it does *not* do is map cleanly to `logisticModel`. Use codes 1–4 as "chilled", 7 as "frozen", 8 as "ambient" for *filtering*, but take actual limits from `min`/`maxTemperature` (available on only 58%) or the `warmTemperature`/`coolTemperature`/`freezeTemperature` labels in §3.5 (covered on 17,362 values).

### `category` — 349 codes

All 349 match `^\d{5}$`. Median 32 products, p90 117, max 443, 4 singletons. Names are explicitly excluded from the dataset; below are the 20 largest with a name **inferred by reading the Finnish product names in each** (inference, not data):

| code | n | inferred name | evidence (sample fi names) |
|---|---|---|---|
| 17300 | 443 | Chilled/frozen ready meals & casseroles | Saarioinen Lihakaalilaatikko, Vispipuuro, Kinkkukiusaus, Feelia Gulassikeittoaines |
| 22630 | 432 | Spices & seasoning blends | Santa Maria Chili Explosion mylly, Meira Sahrami, Knorr Aromat |
| 41763 | 349 | Frozen cakes, cheesecakes & pastries | Rollfoods Mansikka-Juustokakku, Frödinge mud cake, Caffe Latte-leivokset |
| 64004 | 343 | Disposable food containers & lids | Huhtamaki muovirasia, DUNI GN-rasia, Fredman muovikaulusvuoka |
| 41760 | 244 | Frozen & bake-off breads, loaves, rolls | Fria Kuituleipä, Vaasan Moniviljapaahtoleipä, Schulstad Ciabatta |
| 63235 | 238 | Napkins & table serviettes | Duni 40cm 3-krs lautasliina, Softlin Classic, Tork Soft Dinner |
| 41755 | 221 | Frozen pasta, tortillas, rice & pizza bases | Salud vehnätortilla, Mondo Fresco ravioli, ARDO riisi, McCain sipulirengas |
| 22601 | 190 | Baking decorations, icings & flavourings | Dr. Oetker sokerikuorrute, Meira Vaniljasokeri, Nic Suklaaströsseli |
| 21917 | 184 | Table & cooking sauces, dressings | HP Sauce, Rydbergs Remouladekastike, Santa Maria Teriyaki |
| 63114 | 181 | Cleaning & disinfecting chemicals | Suma Auto Oven Rinse, Klorin, Heti Yleispesu, Mäntysuopaliuos |
| 64001 | 180 | Disposable cups & drinking glasses | Biopak muovilasi, Huhtamaki kartonkinen kuumakuppi, DUNI kuohuviinilasi |
| 41764 | 179 | Sweet buns, doughnuts & croissants | Vaasan Toscapulla, Munkkimiehet Voipulla, Schulstad Premium Croissant |
| 63120 | 164 | Cleaning tools, cloths & brushes | Fredman Carita yleisliina, Vileda Miraclean, Diversey astianpesuharja |
| 22700 | 157 | Soft drinks & lemonades | Marli Sima, Tomarchio limonadi, Hartwall Jaffa, tonic water |
| 52210 | 152 | Sweets & candy bags/mixes | Fazer Marianne, Malaco Tv Mix, Panda Lakupala, Tyrkisk Peber |
| 10412 | 150 | Yoghurt | Arla Kalinka jogurtti, Valio turkkilainen jogurtti, Salakis jogurtti |
| 18720 | 149 | Fresh beef cuts | NAUDAN SISÄFILE FI, DRY AGED ENTRECOTE, HÄRÄNHÄNTÄ, Naudan Maksa |
| 21596 | 147 | Pickled/preserved vegetables & peppers | Royal pepperoni, Royal jalapeno, Felix sinappirelish, bambunverso |
| 41753 | 146 | Frozen vegetarian patties & dumplings | Findus Falafel, Apetit Kasvispihvi, Mondo Fresco Vihannesnyytti |
| 21380 | 140 | Dry pasta & macaroni | Barilla Fusilli, Torino suurkeittiömakaroni, Myllyn Paras Lasagne |

Useful structural reads: the `104xx`/`106xx` codes are dairy (10400 drinking milk, 10402 plant drinks, 10412 yoghurt, 10600 cheese; Valio is the largest vendor there, not the only one), `174xx` fresh produce, `200xx` kitchen equipment, tableware and glassware (non-food), `41xxx` frozen/bakery, `21xxx`/`22xxx` ambient grocery, `52xxx` confectionery, `63xxx`/`64xxx` non-food HoReCa.

### `countryOfOrigin` — 97 values, 9 products missing

fi 7,849 (44.73%) · de 1,029 · it 977 · se 874 · cn 741 · nl 659 · fr 599 · pl 431 · es 404 · be 383 · dk 379 · gb 289 · gr 271 · ee 249 · th 223 · **zy 179** · no 145 · at 141 · ch 114 · us 110 · in 108 · lv 95 · lt 86 · sk 77 · cz 73 · tr 72 · ro 69 · hu 62 · vn 59 · ph 55 · id 51 · br 49 · mx 46 · jp 33 · nz 31 · cy 31 · pt 30 · pe 28 · tw 26 · eg 25 · lk 25 · my 21, then a long tail of 1–16 each (za, ca, cr, ie, ma, gt, bg, il, ke, lu, au, ar, **xs 11**, kr, cl, ua, hr, si, ec, tn, sg, la, ae, **zz 5**, pk, mg, co, py, lb, jm, bf, cu, sv, gl, bd, ug, bo, gh, ci, mu, mw, is, dz, do, mm, kz, et, sc, mk, vc, az, ir, kh, ru, ht).

⚠️ **`zy` (179), `xs` (11) and `zz` (5) are not ISO 3166-1 codes** — user-assigned/unknown placeholders. 195 products will fail a strict ISO lookup.

### `vendorName` — 648 distinct, top 20

DUNI OY, PROFESSIONAL 817 · VALIO OY TUORE 788 · ATRIA SUOMI OY TUORE 300 · E. GAVRIELIDES OY 284 · HKFOODS FINLAND OY 266 · FEELIA OY 260 · MAUSTE-SALLINEN OY 252 · SANTA MARIA AB 251 · OY ESSITY FINLAND AB 245 · OY LANTMÄNNEN UNIBAKE AB FINLAND 242 · FAZER MAKEISET OY 241 · WULFF OY AB 232 · PRESCOTT OY 219 · ARLA OY 208 · HUHTAMAKI FOODSERVICE NORDIC OY 190 · DIVERSEY SUOMI OY 186 · MEIRA OY 180 · SAMBONET PADERNO INDUSTRIE S.P.A. 177 · OY ROLLFOODS AB PAKASTE 163 · KIILTOCLEAN OY 157.

Free text, not a code. `VALIO OY TUORE` vs `VALIO OY / VALIO AIMO` are separate strings — don't group by prefix.

### `synkkaData.vatCode` — dirty, do not parse

| value | products |
|---|---|
| `"MEDIUM"` | 11,719 |
| *absent* | 3,068 |
| `"STANDARD"` | 2,593 |
| **`"MEDIUM MEDIUM"`** | **159** |
| `""` | 4 |
| `"LOW"` | 1 |
| `"NOT_APPLICABLE"` | 1 |
| **`"STANDARD MEDIUM"`** | **1** |

Schema says STANDARD = 25.5%, MEDIUM = 13.5%, LOW = 10%, and that **`tax.taxRate` from `/price` is the source of truth**. The 160 space-joined values look like two concatenated codes; `NOT_APPLICABLE` is undocumented. Use the API.

### `allowedLotSize` — 73 distinct values

`0.01` on **16,872 (96.16%)** = "no constraint". The remaining **674** carry a real step:

2.0 (92) · 3.0 (85) · **1.5 (62)** · 5.0 (54) · 10.0 (40) · 1.0 (39) · 4.0 (34) · 2.5 (21) · **1.8 (17)** · 6.0 (15) · 15.0 (14) · 1.6 (14) · 1.2 (13) · 0.9 (13) · 0.5 (11) · 0.7 (10) · 4.5 (9) · 2.8 (8) · 3.5 (8) · 4.8 (6) · 1.4 (5) · 7.0 (5) · 0.6 (5) · 0.75 (5) · 1.3 (5) · 3.3 (4) · 0.8 (4) · 2.4 (4) · 3.2 (4) · 4.4 (3) · 2.7 (3) · 2.6 (3) · 8.0 (3) · 4.2 (3) · 1.25 (3) · 20.0, 0.35, 3.6, 2.3, 3.8, 0.4, 8.5, 21.0, 5.5, 9.5, 9.6, 6.3, 1.1 (2 each) · 12.9, 0.3, 3.7, 11.2, 0.55, 6.6, 1.7, 4.7, 16.0, 4.9, 14.0, 3.35, 5.8, 5.7, 5.3, 1.15, 1.44, 0.15, 1.35, 6.5, 6.7, 25.0, 3.4, 7.5 (1 each).

**Fractional steps (1.5, 1.8, 0.9, 1.6, 2.5, 3.35, 1.44 …) are the live landmine.** Round with `Decimal`, not float: `math.ceil(q / 1.5) * 1.5` on binary floats will produce 10.500000000000002 and fail a strict multiple check.

---

## 5. Derived quantities — the pack-size problem

Nothing in this file states "litres per sales unit". You need it for "1,000 litres of milk". Three tiers, in descending confidence.

### Tier 1 — `catalogPrice.value / comparisonPrice.value` from `/price` (**high confidence, ~79.4% available**)

The ratio of the per-sales-unit price to the per-comparison-unit price *is* the pack size in `comparisonUnit` (which the OpenAPI restricts to `KG` or `L`). Verified on saved responses (FINDINGS.md §4): 1.0 for a 1 L `ST` carton, 10.015 for a `KI` crate of ten, 19.94 for a 2×10 L novobox, 3.7448 for 15×2.5 dl.

- Requires an API call → only usable *after* local filtering.
- `comparisonPrice`/`comparisonUnit` are **missing on 20.6%** of products (206 of 1,000; random sample of 1,000, 2026-11-13 23:00).
- Values are rounded to 2 dp → ~0.3% error; crate ratios land on 10.015, not 10.0. **Round to a plausible pack size, never treat as exact.**

### Tier 2 — static fields in this file

**2a. `synkkaData.unitConversions` (medium-to-low confidence).**

Present and non-empty on 14,474 products. **Critically: exactly one row per product — never two, never a hierarchy.** That row's `synkkaPackagingType` tells you *which* level it describes:

| `synkkaPackagingType` | products |
|---|---|
| `BASE_UNIT_OR_EACH` | 8,215 (46.8%) |
| `CASE` | 6,249 (35.6%) |
| `PALLET` | 10 |
| *(no unitConversions)* | 3,072 |

And the level tracks `salesUnit`: for `salesUnit == KI` it is `CASE` 6,071 / `BASE_UNIT_OR_EACH` 1,408; for `ST` it is `BASE_UNIT_OR_EACH` 4,146 / CASE 22 / PALLET 6; for `KG`, `PAK`, `BAG` it is overwhelmingly `BASE_UNIT_OR_EACH`. So the single row usually *is* the sales unit — but on ~1,400 `KI` products it describes the consumer unit instead, and you must multiply by `units[salesUnit].sizeInBaseUnits`. **You cannot tell which case you are in without checking `synkkaPackagingType` against `salesUnit`.**

`volume` — **present on 8,970 products (51.1%), but `volume.unit` is usually not a volume unit:**

| unit | rows (all levels) | rows at BASE level | is it a volume? |
|---|---|---|---|
| **GRM** (gram) | 5,498 | 5,075 | ❌ mass |
| **H87** (piece) | 1,500 | 1,320 | ❌ count |
| **KGM** (kilogram) | 875 | 833 | ❌ mass |
| LTR | 762 | 670 | ✅ |
| MLT | 259 | 242 | ✅ |
| CLT | 50 | 50 | ✅ |
| PTN (portion) | 9 | 9 | ❌ |
| MTR (metre) | 8 | 7 | ❌ |
| `"KGM H87"` | 3 | 3 | ❌ space-joined compound |
| PR (pair) | 3 | 3 | ❌ |
| `"GRM H87"` | 2 | 2 | ❌ compound |
| `"KGM PTN"` | 1 | 1 | ❌ compound |

**Only 1,071 of 8,970 `volume` rows (11.9%) carry a genuine volume unit — 6.1% of the catalog.** Reading `.volume` as litres is wrong 88% of the time. Six rows have space-separated compound units that will crash a strict unit parser.

`netWeight` — present on 9,786 (55.8%), and here the unit is clean: **GRM 9,297 / KGM 489, nothing else.** At BASE level: GRM 7,590 / KGM 422. `grossWeight` (14,288 GRM / 186 KGM) includes packaging — never use it for content quantity.

**2b. `units[unitId == salesUnit].sizeInBaseUnits` (high confidence, 100% available).**

Available on **every** product, by the invariants in §1. It does not give litres; it gives *base units per sales unit* (1.0 on 62.4%, >1 on 6,602). Combine it with a per-base-unit quantity from `netWeight` or the name, and you get a per-sales-unit quantity with no API call. This is the piece that makes tier 2 usable rather than decorative.

### Tier 3 — parse the Finnish name (low confidence, 88.0% available)

**15,437 fi names (88.0%)** contain a `\d+([.,]\d+)?\s*(kg|g|l|dl|cl|ml|kpl)` token (higher than the 81.2% in an earlier `FINDINGS.md`, which used a narrower token set — `kpl` and comma decimals matter). **1,910 (10.9%)** contain an `N x M unit` multipack pattern (`6 x Saarioinen Lihakaalilaatikko 380g`, `Vaasan Mini Vehnäpatonki 52x130g`, `8 x Frödinge ... 400g`).

Parsing rules that the data forces on you:
- Decimal comma (`2,6kg`, `0,33L`) and decimal point both occur.
- `N x M unit` means N packs of M → total = N·M, but which of the two the *sales unit* is depends on `salesUnit`/`sizeInBaseUnits`.
- Approximations: `n. 266x15g`, `väh20x n85g`, `2kg/väh20x n85g` — `n.` = "noin" (approx), `väh` = "vähintään" (at least).
- Slash-separated gross/net: `1680/800g`, `2950/1800g`, `0,79/0,539kg` (drained weight second).
- Dimensions masquerading as sizes: `325 x 265 x 100 mm`, `45x60cm` in the non-food categories.
- 923 names contain `®`/`™`.

### Combined availability

Counting a *real* volume unit at BASE level, a `netWeight`, and a name token:

| real volume unit | netWeight | name token | products | % |
|---|---|---|---|---|
| ✗ | ✗ | ✓ | 7,866 | 44.8% |
| ✗ | ✓ | ✓ | 6,616 | 37.7% |
| **✗** | **✗** | **✗** | **1,660** | **9.5%** |
| ✓ | ✓ | ✓ | 947 | 5.4% |
| ✗ | ✓ | ✗ | 442 | 2.5% |
| ✓ | ✗ | ✓ | 8 | 0.0% |
| ✓ | ✓ | ✗ | 7 | 0.0% |

**1,660 products (9.5%) have no static pack-size signal at all** — not a volume, not a net weight, not a parseable name. For those, tier 1 is the only option, and if `comparisonPrice` is also missing, the quantity is simply unknown.

### Recommended algorithm

```python
from decimal import Decimal

def pack_size(product, price_row=None):
    """Return (quantity, unit, confidence) for ONE sales unit.
    confidence: 'high' | 'medium' | 'low' | None"""
    # Tier 1 — API ratio. Authoritative when present.
    if price_row:
        cat = price_row.get("catalogPrice", {}).get("value")
        cmp_ = price_row.get("comparisonPrice", {}).get("value")
        cu = price_row.get("comparisonUnit")          # 'KG' or 'L' only
        if cat and cmp_ and cu:
            return (round(cat / cmp_, 3), cu, "high")   # ~0.3% rounding error

    s = product.get("synkkaData", {})
    rows = s.get("unitConversions") or []
    row = rows[0] if rows else None
    # base units per sales unit — available on 100% of products
    mult = next(u["sizeInBaseUnits"]
                for u in product["units"]
                if u["unitId"] == product["salesUnit"])

    if row:
        level = row.get("synkkaPackagingType")
        # if the row already describes the sales unit, don't multiply
        scale = 1.0 if level in ("CASE", "PALLET") else mult

        # Tier 2 — volume, ONLY when the unit is really a volume
        v = row.get("volume") or {}
        if v.get("unit") in ("LTR", "MLT", "CLT"):
            litres = v["value"] * {"LTR": 1, "MLT": 0.001, "CLT": 0.01}[v["unit"]]
            return (litres * scale, "L", "medium")

        # Tier 2 — net weight. Clean units: GRM | KGM only.
        w = row.get("netWeight") or {}
        if w.get("unit") in ("GRM", "KGM"):
            kg = w["value"] * (0.001 if w["unit"] == "GRM" else 1.0)
            return (kg * scale, "KG", "medium")
        # NOTE: volume.unit GRM/KGM is a MASS mislabelled as volume (6,373 rows).
        # Treating it as mass is defensible but unverified — flag it, don't trust it.

    # Tier 3 — parse the Finnish name
    q = parse_size_token(fi_name(product))   # handles N x M, comma decimals, n./väh
    if q:
        return (*q, "low")
    return (None, None, None)
```

Then **always** reconcile against `allowedLotSize` with `Decimal`, and flag any product with `variableUnit is True` (632 products) before quoting. 628 of them are sold in `KG`, and all 37 in the random sample of 1,000 (2026-11-13 23:00) are priced per kg (`catalogPrice.value == comparisonPrice.value`), so the unit price is known; the 4 whose file `salesUnit` is `KI` are priced per pack, not per kg (37-id extras call). What is open is whether the delivered weight equals the ordered weight — to be confirmed with Valio.

---

## 6. Substitution data — all 250 pairs

| Measure | Value |
|---|---|
| Products carrying a non-empty `substitutions` array | **189** (1.08%) |
| Products carrying the key with `[]` | 7 |
| Rows / distinct edges | 250 / 250 (no duplicate rows) |
| `substitutions[].product == owner id` | 250/250 — the field is pure redundancy |
| Targets resolving to a catalog product | **250/250 (100%)** |
| Targets with `deleted == true` | **0** (and the whole file has 0 deleted products) |
| Same `category` | **230/250 (92.0%)** |
| The 20 cross-`category` pairs, by shared prefix | 11 share the first 4 digits · 5 only the first 3 · 2 only the first 2 · 2 none |
| Same `salesUnit` | 175 (70.0%) |
| Same `vendorName` | 154 (61.6%) |
| Same `brand` | 102 (40.8%) |
| Out-degree 1 / 2 / 3 / 4 / 5 | 154 / 17 / 12 / 4 / 2 — **35 products have >1 substitute** |
| In-degree 1 / 2 / 3 / 4 | 192 / 21 / 4 / 1. Most-referenced: `460239` (4), then `475772`, `460298`, `460267`, `460189` (3 each) |
| **Mutual pairs (A→B and B→A)** | **31 pairs (62 edges)** |
| **True chains (A→B→C, C≠A)** | **72 paths**; 56 targets are themselves sources |
| **Self-loop** | **1 — product `471661` lists itself as its own substitute** |

### Directedness — correction to FINDINGS.md

*This subsection refers to an earlier version of `FINDINGS.md` and is kept as history.*

An earlier `FINDINGS.md` stated the relation is directed with "no reverse edges". That is **not quite right**: 31 of the 125 unordered pairs are explicitly recorded in both directions. The accurate statement is **the relation is stored directed and is only partly symmetric** — 62 of 250 edges have their reverse present, 188 do not. You still need to symmetrise for two-way swaps, but don't assume a reverse edge is absent (and don't double-count the 31 that already exist).

### Deliverability of targets

Nothing in the static file marks a target as undeliverable, and all 250 exist and are not deleted. But **20.3% of products returned empty `scheduleLines`** (= undeliverable) from `/availability` in the random sample of 1,000 (2026-11-13 23:00), and that signal exists **only in the API**. So: *targets are all valid catalog entries; whether any given target is actually orderable is unknowable from this file.* Any substitution flow must re-check the target against `/availability` before offering it.

### Chains exist and they are shallow but real

72 A→B→C paths, clustered in a few dense neighbourhoods (the `4601xx`/`4602xx` block — looks like one dairy family where 4–5 SKUs are mutually interchangeable). Treat the edge set as an undirected graph, take connected components, and you get substitution *classes* rather than pairs. That is almost certainly the intent.

### Verdict: usable as a seed, not as a source

1.08% coverage cannot answer "what replaces product X" for a real basket. But the 250 pairs are an excellent **labelled training/validation set** for a derived engine, because they encode Valio's own notion of equivalence:

- **92% same-category** is a strong, directly observed prior → category is the primary candidate axis.
- Only 40.8% same-brand → brand is a *ranking* feature, not a filter. A cross-brand swap is normal (`Oatly iKaffe` → `Elovena kaurajuoma`).
- 70% same-`salesUnit` → unit compatibility matters but is not required; 30% of real swaps change the pack format (`SallaCarte Thai wok 10x1kg` → `SallaCarte Thai wok 1kg`).
- Median products per `(category, brand)` = **2** → category+brand alone yields almost no candidates. You need category + derived pack size + `nutritionalClaim` compatibility, gated on allergen assertions.

Recommended generator: **candidates = same `category`**, then filter by (a) no new `CONTAINS`/`MAY_CONTAIN` allergen relative to the original, (b) all of the original's `nutritionalClaim` ids preserved (lactose-free must stay lactose-free), (c) derived pack size within a tolerance band, then rank by price, `deliveryReliability`, carbon footprint and brand match. Validate it by checking it recovers the 250 known pairs — that is a measurable, demo-able number.

---

## 7. Query recipes

### 7.1 Slim index (build once, ~5 MB instead of 87 MB)

Columns worth keeping — everything needed for local filtering and ranking, nothing needed only for display:

```python
import json, sqlite3, re

SRC = "valio_aimo_junction26_product_data.json"
VOL = {"LTR": 1.0, "MLT": 0.001, "CLT": 0.01}
MASS = {"KGM": 1.0, "GRM": 0.001}

def fi(s):
    for n in s.get("names") or []:
        if n["language"] == "fi":
            return n["value"]
    return ""

def groups(s):
    return {g["name"]: (g.get("values") or [])
            for g in (s.get("classifications") or [])}

con = sqlite3.connect("aimo.db")
con.executescript("""
CREATE TABLE product (
  id TEXT PRIMARY KEY,
  name_fi TEXT, name_en TEXT,
  category TEXT, vendor TEXT, brand TEXT,
  sales_unit TEXT, base_unit TEXT,
  size_in_base REAL,              -- units[salesUnit].sizeInBaseUnits, 100% coverage
  allowed_lot REAL,
  variable_unit INTEGER,          -- NULL on the 3,068 thin products
  temp_cond INTEGER, min_temp REAL, max_temp REAL,
  country TEXT,
  gtin_sales TEXT, gtin_consumer TEXT,
  uc_level TEXT,                  -- BASE_UNIT_OR_EACH | CASE | PALLET | NULL
  net_kg REAL, vol_l REAL,        -- normalised, NULL unless the unit was real
  has_deposit INTEGER,
  thin_synkka INTEGER             -- 1 => no brand/vat/unitConversions/gtin
);
CREATE TABLE claim      (id TEXT, claim TEXT);          -- nutritionalClaim ids
CREATE TABLE allergen   (id TEXT, code TEXT, state TEXT); -- CONTAINS|MAY_CONTAIN|UNDECLARED|FREE_FROM
CREATE TABLE label      (id TEXT, label TEXT);          -- packagingMarkedLabel, certs only
CREATE TABLE substitute (src TEXT, dst TEXT);
CREATE INDEX i_cat  ON product(category);
CREATE INDEX i_clm  ON claim(claim);
CREATE INDEX i_alg  ON allergen(code, state);
""")

rows, claims, allergens, labels, subs = [], [], [], [], []
PSEUDO = {"warmTemperature", "coolTemperature", "freezeTemperature"}

for o in json.load(open(SRC)):
    s, g = o.get("synkkaData", {}), None
    g = groups(s)
    uc = (s.get("unitConversions") or [None])[0]
    net = vol = None
    if uc:
        w = uc.get("netWeight") or {}
        if w.get("unit") in MASS:
            net = w["value"] * MASS[w["unit"]]
        v = uc.get("volume") or {}
        if v.get("unit") in VOL:                 # ONLY real volume units
            vol = v["value"] * VOL[v["unit"]]
    size = next(u["sizeInBaseUnits"] for u in o["units"]
                if u["unitId"] == o["salesUnit"])
    rows.append((
        o["id"], fi(s),
        next((n["value"] for n in s.get("names") or [] if n["language"] == "en"), ""),
        o["category"], o["vendorName"], s.get("brand"),
        o["salesUnit"], o["baseUnit"], size, o["allowedLotSize"],
        None if "variableUnit" not in s else int(s["variableUnit"]),
        o.get("temperatureCondition"), s.get("minTemperature"), s.get("maxTemperature"),
        o.get("countryOfOrigin"), o.get("salesUnitGtin"), s.get("gtin"),
        uc.get("synkkaPackagingType") if uc else None,
        net, vol,
        int(bool(o.get("deposits"))), int("gtin" not in s),
    ))
    for v in g.get("nutritionalClaim", []):
        claims.append((o["id"], v["id"]))
    for v in g.get("allergen", []):
        allergens.append((o["id"], v["id"], v.get("unit")))     # CONTAINS/MAY_CONTAIN/UNDECLARED
    for v in g.get("nonAllergen", []):
        allergens.append((o["id"], v["id"], "FREE_FROM"))
    for v in g.get("packagingMarkedLabel", []):
        if v["id"] not in PSEUDO:
            labels.append((o["id"], v["id"]))
    for sub in o.get("substitutions") or []:
        if sub["product"] != sub["substituteProduct"]:          # drop the 1 self-loop
            subs.append((sub["product"], sub["substituteProduct"]))

con.executemany("INSERT INTO product VALUES (" + ",".join("?" * 21) + ")", rows)
con.executemany("INSERT INTO claim      VALUES (?,?)",   claims)
con.executemany("INSERT INTO allergen   VALUES (?,?,?)", allergens)
con.executemany("INSERT INTO label      VALUES (?,?)",   labels)
con.executemany("INSERT INTO substitute VALUES (?,?)",   subs)
con.commit()
```

For parquet instead, the same column list via `pandas.DataFrame(rows, columns=[...]).to_parquet()`; keep the four child tables as separate long-format frames rather than nested lists, so you can filter with a join.

### 7.2 Lactose-free products

```sql
-- 4,178 products. Note LOW_LACTOSE (321) is a DIFFERENT, weaker claim --
-- "vähälaktoosinen", not "laktoositon". Never union them.
SELECT p.id, p.name_fi, p.category, p.sales_unit, p.size_in_base
FROM product p JOIN claim c ON c.id = p.id
WHERE c.claim = 'FREE_FROM_LACTOSE';

-- drinking milk only (category 10400): 35 of 91
SELECT p.id, p.name_fi FROM product p JOIN claim c ON c.id = p.id
WHERE c.claim = 'FREE_FROM_LACTOSE' AND p.category = '10400';
```

⚠️ **1,485 of the 4,178 also assert allergen `AM` (milk) = CONTAINS.** That is *correct* — lactose-free milk is still dairy. A "dairy-free" filter and a "lactose-free" filter are different queries, and 503 products claim `FREE_FROM_LACTOSE` while reporting a non-zero `LACS` nutrition fact (trace lactose under the 0.01% threshold). Don't cross-validate the claim against `LACS` and reject.

### 7.3 Allergen safety with the four-state model

The plan's buyer exclusion rule ([PLAN.md](../PLAN.md) §7): an explicit `FREE_FROM` passes automatically, a declared `CONTAINS` is rejected, and `MAY_CONTAIN`, `UNDECLARED` or no statement goes to a human. The sample below only returns the set that passes automatically.

```python
SAFE_STATES = {"FREE_FROM"}                      # certifiable
UNSAFE      = {"CONTAINS", "MAY_CONTAIN", "UNDECLARED"}
# UNDECLARED is kept on the excluded side pending confirmation from Valio, not because it
# means "contains": GS1 (T4079) defines it as "Not intentionally included in the product
# and assessed not to require a cross-contact declaration".

def allergen_state(con, pid, code):
    """-> 'FREE_FROM'|'CONTAINS'|'MAY_CONTAIN'|'UNDECLARED'|'SILENT'"""
    r = con.execute("SELECT state FROM allergen WHERE id=? AND code=?",
                    (pid, code)).fetchone()
    return r[0] if r else "SILENT"

def filter_by_allergen(con, pids, code, *, strictness):   # required: the plan gives strictness no default
    """strictness:
       'certified'  -> only explicit FREE_FROM. Safe. Max 5,119 candidates.
       'permissive' -> FREE_FROM or SILENT. Covers the catalog but is NOT a
                       safety claim: 46.2% of products have neither allergen group
                       populated, and silence is not evidence of absence.
    """
    out = []
    for pid in pids:
        st = allergen_state(con, pid, code)
        if st in UNSAFE:
            continue
        if strictness == "certified" and st != "FREE_FROM":
            continue
        out.append((pid, st))
    return out
```

Two rules that follow from the data and should be surfaced in any UI:
1. **`MAY_CONTAIN` is not safe.** A filter written against the two schema-documented values (`CONTAINS`, `FREE_FROM`) silently passes 2,685 products that declare possible traces.
2. **`X99` is not an unnamed allergen.** GS1's allergen type code list (T4078) defines it as "Does not contain declaration obligatory allergens in the product." It is on 121 products in `allergen` (120 of them with no other allergen code) and on 74 in `nonAllergen`. Whether Valio uses the GS1 meaning is to be confirmed with them.

### 7.4 Candidate substitutes for a product id

```python
def candidates(con, pid, *, limit=25):
    p = con.execute("SELECT category, brand, sales_unit, size_in_base, net_kg, vol_l,"
                    "       variable_unit FROM product WHERE id=?", (pid,)).fetchone()
    cat, brand, su, size, net, vol, varu = p

    # 1. explicit pairs first, symmetrised (31 pairs already exist both ways)
    explicit = {r[0] for r in con.execute(
        "SELECT dst FROM substitute WHERE src=? UNION SELECT src FROM substitute WHERE dst=?",
        (pid, pid))}

    # 2. derived: same category (92% of real pairs stay in-category)
    must_keep = {r[0] for r in con.execute("SELECT claim FROM claim WHERE id=?", (pid,))}
    bad = {r[0] for r in con.execute(
        "SELECT code FROM allergen WHERE id=? AND state IN ('CONTAINS','MAY_CONTAIN','UNDECLARED')",
        (pid,))}

    derived = []
    for (cid, cname, cbrand, csu, cnet, cvol, cvar) in con.execute(
            "SELECT id, name_fi, brand, sales_unit, net_kg, vol_l, variable_unit "
            "FROM product WHERE category=? AND id<>?", (cat, pid)):
        if cvar:                                   # never auto-swap variable-weight
            continue
        cand_claims = {r[0] for r in con.execute("SELECT claim FROM claim WHERE id=?", (cid,))}
        if not must_keep <= cand_claims:           # must preserve every claim
            continue
        cand_bad = {r[0] for r in con.execute(
            "SELECT code FROM allergen WHERE id=? AND state IN "
            "('CONTAINS','MAY_CONTAIN','UNDECLARED')", (cid,))}
        if cand_bad - bad:                         # no NEW allergen risk
            continue
        score = (cid in explicit) * 100 \
              + (cbrand == brand) * 10 \
              + (csu == su) * 5
        if net and cnet:                           # pack-size proximity
            score += max(0.0, 5 - abs(cnet - net) / max(net, 1e-9) * 5)
        derived.append((score, cid, cname))

    return sorted(derived, reverse=True)[:limit], explicit
```

Then call `/availability` **once**, batched, on the shortlist (≤1,000 ids per request), and classify every candidate with the six states of [PLAN.md](../PLAN.md) §2. The plan widens candidates beyond this sample: same category, then the same first 4 digits, then the same first 3 (§7), and variable-weight candidates go to a human rather than being dropped.

---

## 8. Parsing pitfalls specific to this file

Counts are products affected unless noted. API-side behaviour is in `FINDINGS.md` and [API.md](API.md); these are file-side.

| # | Trap | Affected |
|---|---|---|
| 1 | **`synkkaData` has two shapes; 15 keys are *absent*, not empty.** `s["vatCode"]` raises `KeyError`. Always `.get()`. | **3,068** (17.49%) |
| 2 | **`MAY_CONTAIN` is undocumented and pervasive.** A filter on the two schema values treats "may contain traces" as safe. | **2,685** |
| 3 | **`UNDECLARED` is a fourth allergen qualifier**, not in the schema. 303 values. GS1 (T4079): "Not intentionally included in the product and assessed not to require a cross-contact declaration"; Valio's use to be confirmed. | **33** |
| 4 | **`X99` is not an unnamed allergen.** GS1 (T4078): "Does not contain declaration obligatory allergens in the product." 120 of the 121 `allergen` carriers list no other allergen code. Valio's use to be confirmed. | 121 CONTAINS + 74 FREE_FROM |
| 5 | **Allergen silence ≠ safe.** `allergen` group empty / `nonAllergen` group empty / both empty. | **10,341** / **12,427** / **8,110** (46.2%) |
| 6 | **`unitConversions.volume.unit` is usually not a volume unit** (GRM 5,498, H87 1,500, KGM 875, MTR 8, and 6 space-joined compounds like `"KGM H87"`). Only 11.9% of volume rows are genuine volumes. | 7,899 of 8,970 volume rows |
| 7 | **`unitConversions` has exactly one row**, and `synkkaPackagingType` varies — `CASE` on 6,249, so the weight is the *case*, not the consumer unit. Multiplying by `sizeInBaseUnits` then double-counts. | **6,259** (CASE+PALLET) |
| 8 | **No pack-size signal at all** (no real volume, no netWeight, no parseable name token). | **1,660** (9.5%) |
| 9 | **`classifications.packaging` is always empty** despite being present on 17,535 products. Schema advertises a group with no data. | 17,535 |
| 10 | **`classifications` is `[]` entirely** — no allergen, claim or nutrition structure whatsoever. | **11** |
| 11 | **`vatCode` is dirty**: `"MEDIUM MEDIUM"` 159, `"STANDARD MEDIUM"` 1, `""` 4, `NOT_APPLICABLE` 1. Use `tax.taxRate` from `/price`. | **165** dirty + 3,068 absent |
| 12 | **`variableUnit` is tri-state**: `true` 632, `false` 13,846, **absent 3,068**. `if not s.get("variableUnit")` conflates "fixed weight" with "unknown". | **3,700** |
| 13 | **`allowedLotSize` fractional steps** (1.5 ×62, 1.8 ×17, 0.9 ×13, 1.6 ×14, 2.5 ×21, 3.35, 1.44, 0.15 …). Float rounding fails strict multiple checks. Use `Decimal`. | **674** real steps, ~200 fractional |
| 14 | **GTIN is not a usable key.** `synkkaData.gtin` missing 3,068; `salesUnitGtin` missing 159; both missing 153; the two **differ on 6,867** (consumer vs sales unit — both correct); 27 `synkkaData.gtin` values are **shared by 54 products**. `id` is the only safe key (6 digits, 0 duplicates). | see cells |
| 15 | **`nutritionalContent` spells three vitamin ids two ways**: `VITD-` 602 / `VITD` 8, `VITC-` 394 / `VITC` 7, `VITE-` 223 / `VITE` 1. For these three, `classifications.vitamin` has only the hyphen-less spelling, on the same products, so a join on id drops nothing; aggregating by raw id splits each nutrient in two. | 602 + 394 + 223 hyphenated rows · 8 + 7 + 1 hyphen-less |
| 16 | **`nutritionalClaim` qualifier is inconsistent** — HIGH_PROTEIN appears 403× HIGH / 14× DIET; FREE_FROM_GLUTEN 3,047 FREE_FROM / 2 DIET; LOW_FAT 109/1. Key on `id` alone. | 4 ids, 17 rows |
| 17 | **`packagingMarkedLabel` mixes 3 temperature pseudo-labels into the certificate group** (17,362 of 23,582 values). Filter them before claiming "has an eco-label". | 10,057 / 4,060 / 3,245 |
| 18 | **`countryOfOrigin` has non-ISO placeholders**: `zy` 179, `xs` 11, `zz` 5, plus 9 products with no value. | **204** |
| 19 | **`fishingReports[].catchMethods[].productionMethod` has dirty values**: `MARINE_FISHERY1` ×3, `AQUACULTURE1` ×2 — undocumented variants of the documented enum. | 5 rows |
| 20 | **`nutritionalContent.basisQuantityUnit` has 4 undocumented units**: `PTN` 164, `H87` 30, `KGM` 27, `GL` 9 rows. Normalising "per 100 g" blindly breaks on these. | 230 rows |
| 21 | **Substitution self-loop**: product `471661` lists itself as its own substitute. Infinite loop in a naive resolver. | **1** |
| 22 | **Substitutions are only partly symmetric** — 62 of 250 edges have their reverse already present. Symmetrising naively creates 31 duplicate pairs. | 31 pairs |
| 23 | **`substitutions[].product` is always the owner's own id** — redundant; code that keys on it instead of the owner looks right and tests fine. | 250 rows |
| 24 | **`substitutions` key present but empty** — `"substitutions" in o` is not the same as having substitutes. | **7** |
| 25 | **`medias` primary flag is unreliable**: of 13,375 products with media, 2,350 have 2 primaries, 1,394 have 0, and 2 have **83**. `next(m for m in medias if m["primary"])` raises on 1,394. | **4,416** |
| 26 | **`®`/`™` in Finnish names** break slugs, URL keys and naive string matching. | **923** |
| 27 | **`sv` names missing**, and `en` on 2. Don't assume trilingual. | **1,446** sv |
| 28 | **`FREE_FROM_LACTOSE` co-occurs with milk-allergen CONTAINS** (correct — lactose-free milk is dairy) and with non-zero `LACS` nutrition facts. Neither is a data error; both break naive cross-validation. | **1,485** / **503** |
| 29 | **`deposits[].material` resolves to nothing.** 7 codes, 0 catalog matches, no price list → order totals for bottled goods are structurally incomplete. | **506** |
| 30 | **`deleted` is always `false`** and `temperatureCondition`/`countryOfOrigin`/`salesUnitGtin` are optional but ~99.9% present — code that treats them as guaranteed fails on a handful of rows only in production. | 61 / 9 / 159 |
| 31 | **Load cost**: `json.load` ≈0.5 s, ~0.6–0.7 GB peak RSS (measured 2026-11-14, Python 3.13). Load it once per process, not per request or inside a loop. | whole file |
