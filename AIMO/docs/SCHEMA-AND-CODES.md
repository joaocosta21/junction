# Valio Aimo product data — JSON Schema & code-system reference

Source of truth for this document:

- `valio_aimo_junction26_product_data_schema.json` (read in full; every semantic `description` is quoted verbatim below)
- `valio_aimo_junction26_product_data.json` — 87 MB, **17,546 products**, all counts below computed over the whole file
- Companion: `FINDINGS.md` (API behaviour, traps). This file is the static-data/code-system half.

Quoted text in `> blockquotes` is **verbatim from the schema**. Everything else is derived from the data and labelled with a confidence level.

---

## 1. The schema

### 1.1 Top level

> **title**: "Product data for Junction 2026 Valio Aimo challenge. While inspired by real-world, this dataset does not contain fully accurate product information and it must not be used for anything outside of Junction 2026 event"
> **description**: "Static product information"

`type: array` of objects, each "One product."

### 1.2 Product object

`required`: `allowedLotSize`, `baseUnit`, `category`, `deleted`, `deposits`, `id`, `salesUnit`, `synkkaData`, `units`, `vendorName` — **all present on all 17,546 products. Zero violations.**

| Field | Type | Present | Schema description (verbatim) |
|---|---|---|---|
| `id` | string | 17,546 | "Product code. Use it as the product id in the API requests and in the other data files." |
| `allowedLotSize` | number | 17,546 | "Smallest quantity step the product can be ordered in (order quantity must be a multiple of it), in sales units." |
| `baseUnit` | string | 17,546 | "Base unit of measure of the product. Unit codes such as KI are technical codes and their translations are not included in this data set." |
| `salesUnit` | string | 17,546 | "Unit of measure the product is sold in. Unit codes such as KI are technical codes…" |
| `category` | string | 17,546 | "Product category code. Category names are not part of this data set." |
| `deleted` | boolean | 17,546 | "True if the product has been deleted. Products are only included in this file if they are not deleted, so the value is always false." — **holds: 0 true** |
| `vendorName` | string | 17,546 | "Name of the vendor (supplier) of the product." |
| `deposits` | array | 17,546 | "Deposit (returnable packaging) items that are charged together with the product." |
| `units` | array | 17,546 | "Packaging hierarchy of the product: the units it can be handled in, each with its own barcode." |
| `synkkaData` | object | 17,546 | "Product information supplied by the manufacturer through the GS1 Synkka product data service. Quantity and quality vary between products, so most fields can be missing." |
| `countryOfOrigin` | string | 17,537 (**9 missing**) | "Country of origin as a lowercase ISO 3166-1 alpha-2 code, for example fi or de." |
| `temperatureCondition` | integer | 17,485 (**61 missing**) | "Code of the temperature (storage and transport) class of the product, e.g. ambient, chilled or frozen. Code meanings are not part of this data set." |
| `salesUnitGtin` | string | 17,387 (159 missing) | "GTIN (barcode number) of the sales unit. Not all products have one" |
| `substitutions` | array | **196 only (1.1%)** | "Products that can replace this product when it is not available." |

`deposits[]` required `material`, `quantity`, `unit`:
> `material`: "Product code of the deposit material." · `quantity`: "Number of deposit units charged per sales unit of the product." · `unit`: "Unit of the deposit quantity, for example ST (piece)…"

`units[]` required `sizeInBaseUnits`, `unitId` (`gtin` optional):
> `sizeInBaseUnits`: "How many base units the unit contains." · `unitId`: "Code of the unit. Unit codes such as KI are technical codes…"

`substitutions[]` required `product`, `substituteProduct`:
> `product`: "Product code of the product being substituted." · `substituteProduct`: "Product code of the product that can be offered instead."

### 1.3 `synkkaData`

`required`: `classifications`, `keyIngredients`, `marketingTexts`, `materialAdditionalDescriptions`, `medias`, `names`, `nutritionalContent` — **all keys present on all products, but several are routinely empty arrays**, which the schema does not forbid and which is the real trap:

| Required array | Empty on |
|---|---|
| `materialAdditionalDescriptions` | **17,535 (99.9%)** — effectively a dead field |
| `marketingTexts` | 5,631 (32.1%) |
| `nutritionalContent` | 5,295 (30.2%) |
| `medias` | 4,171 (23.8%) |
| `keyIngredients` | 3,499 (19.9%) |
| `classifications` | 11 |

A clean block of **3,068 products (17.5%)** is missing the whole optional half of `synkkaData` at once: `gtin`, `lastUpdated`, `countriesOfOrigin`, `storageInstructions`, `preparationInstructions`, `disposalInformations`, `usageInstructions`, `ingredients`, `fishingReports`, `safetyData`, `variableUnit`, `vatCode`, `producers`, `unitConversions` are each present on exactly **14,478** products. `brand` 14,463 · `mediasLastUpdated` 13,375 · `maxTemperature` 10,266 · `minTemperature` 10,156.

Selected verbatim descriptions:

> `variableUnit`: "True if the product is sold by variable weight, so that the actual quantity of a unit varies."
> `vatCode`: "VAT class of the product in Finland: STANDARD (25.5 %), MEDIUM (reduced rate for food, 13.5 %) or LOW (reduced rate, 10 %). The official source of truth is tax.taxRate of the price API."
> `countriesOfOrigin`: "Countries of origin as numeric ISO 3166-1 codes, for example 246 for Finland."
> `minTemperature` / `maxTemperature`: "Minimum/Maximum storage temperature in degrees Celsius."
> `producers[].id`: "Identifier of the producer, a 13-digit location number."
> `ingredients[].origins[].country`: "Country of the origin as a numeric ISO 3166-1 code, or NON_EU."
> `ingredients[].origins[].type`: "Production stage the origin refers to, for example FARMING, MILKING, REARING, BIRTH or LAST_PROCESSING."
> `ingredients[].sequence`: "Position of the ingredient in the ingredient list, starting from 1." (the only required key of an ingredient)

### 1.4 `classifications` — the generic container holding most code systems

> `name`: "Name of the group, for example allergen, nonAllergen, nutritionFact, gda, nutritionalClaim, packaging or packagingMarkedLabel."
> `type`: "Type of the values in the group: ENUM for codes or DECIMAL for numbers."
> `values[].id`: "Internal feature id" · `values[].synkkaId`: "Synkka id"
> `values[].unit`: "Unit of the value, for example GRM (gram) or KJO (kilojoule). **For allergens it tells how the allergen relates to the product: CONTAINS or FREE_FROM.**"
> `values[].value`: "Numeric value, in the unit given."

Only `id` is required on a value. All 10 observed groups and their fixed `type`:

| Group | Groups present | Non-empty | type |
|---|---|---|---|
| `packagingMarkedLabel` | 17,535 | 17,255 | ENUM |
| `allergen` | 17,535 | **7,205 (41.1%)** | ENUM |
| `nonAllergen` | 17,535 | **5,119 (29.2%)** | ENUM |
| `nutritionalClaim` | 17,535 | **7,618 (43.4%)** | ENUM |
| `packaging` | 17,535 | **0** | ENUM |
| `nutritionFact` | 15,198 | 12,244 | DECIMAL |
| `composition` | 14,467 | 14 | DECIMAL |
| `gda` | 14,467 | 11,513 | DECIMAL |
| `mineral` | 14,467 | 1,783 | DECIMAL |
| `vitamin` | 14,467 | 727 | DECIMAL |

**Schema vs data discrepancies, this section:**
- `packaging` is named in the schema but is **always empty** (0 non-empty of 17,535). Do not build on it.
- `composition`, `mineral`, `vitamin` are **real groups absent from the schema's example list**.
- `synkkaId` is present on 25,695 values but **only for `nutritionalClaim` and `packagingMarkedLabel`**; allergen/nonAllergen values carry **no** `synkkaId`.
- Every DECIMAL value carries `value` (0 missing), though the schema does not require it.

### 1.5 `nutritionalContent`

`required`: `basisQuantity`, `basisQuantityUnit`, `id`, `unit`, `value`.

> `id`: "Nutrient code, for example ENER-KJO (energy, kJ), ENER-E14 (energy, kcal), FAT, FASAT (saturated fat), CHOAVL (carbohydrate), SUGAR- (sugars), FIBTG (fibre), PRO- (protein) or SALTEQ (salt)."
> `unit`: "Unit of the value, for example GRM (gram), MGM (milligram), KJO (kilojoule) or E14 (kilocalorie)."
> `basisQuantity`: "Quantity the value is given for, for example 100." · `basisQuantityUnit`: "…for example GRM (gram) or MLT (millilitre)."
> `servingSizeUnit`: "Unit of the serving size, GRM or MLT."
> `unitPrecision`: "How exact the value is, for example APPROXIMATELY, LESS_THAN or ABOUT."
> `dailyValueIntakePercent`: "Share of the recommended daily intake that the value covers, in percent."

### 1.6 `unitConversions`

> "Weights and dimensions of each packaging level of the product."

`required`: `grossWeight`, `height`, `length`, `synkkaPackagingType`, `width` — **0 violations**. `netWeight` and `volume` are optional and frequently absent.

> `synkkaPackagingType`: "Packaging level: BASE_UNIT_OR_EACH (consumer unit), CASE or PALLET."
> `grossWeight`/`netWeight` unit: "GRM (gram) or KGM (kilogram)." · `height`/`length`/`width` unit: "MMT (millimetre) or CMT (centimetre)." · `volume` unit: "for example LTR (litre) or MLT (millilitre)."

### 1.7 `fishingReports` and `safetyData`

> `fishingReports[].id`: "Species code, for example SAL (salmon) or HER (herring)." · `name`: "Latin name of the species."
> `catchMethods[].areas`: "Codes of the fishing areas, for example 27. Names are not part of this data set"
> `catchMethods[].methods`: "Codes of the fishing method, for example TM or 03. Names are not part of this dataset."
> `catchMethods[].productionMethod`: "Production method: AQUACULTURE, MARINE_FISHERY or INLAND_FISHERY."
> `safetyData[].sheetId`: "Identifier or date of the safety data sheet."
> `safetyData[].values[].id`: "Statement code, for example h319 or p280. Descriptions of the codes are not in this dataset" · `type`: "HazardStatement or PrecautionaryStatement."

### 1.8 Fields in the data that the schema does not describe

None at the key level — the data introduces no new keys. The gaps are all **value-level**: group names (`composition`, `mineral`, `vitamin`), allergen relation `MAY_CONTAIN` / `UNDECLARED`, `vatCode` values outside the documented three, `productionMethod` values `MARINE_FISHERY1` / `AQUACULTURE1`, `unitPrecision` value `LESS_THAN_OR_EQUAL`, `origins[].type` values `SLAUGHTER`/`IMPORTATION`/`CATCH_ZONE`/`HUNTED_GATHERED`/`CUTTER`, volume units that are not volumes, and the three temperature pseudo-labels inside `packagingMarkedLabel`.

---

## 2. Code-system registry

Status legend: **DOCUMENTED IN SCHEMA** (meaning stated in a `description`) · **SELF-DESCRIBING** (id is a readable English token) · **UNDOCUMENTED** (opaque code, meaning absent from schema and data).

### 2.1 `allergen` ids — UNDOCUMENTED (GS1 AllergenTypeCode)

Where: `synkkaData.classifications[name="allergen"].values[].id`. Non-empty on 7,205 products (41.1%). 44 distinct codes. Full inference table in **§3**.

Counts (products carrying the code in any relation):
`AM` 3,902 · `AW` 3,113 · `UW` 2,899 · `AY` 2,077 · `AE` 1,910 · `AN` 1,538 · `SA` 931 · `BM` 890 · `GO` 857 · `SH` 796 · `AS` 778 · `NR` 731 · `GB` 627 · `AF` 546 · `AP` 532 · `ML` 527 · `ST` 390 · `AU` 354 · `SW` 350 · `SC` 326 · `BC` 324 · `SP` 290 · `SM` 177 · `SR` 171 · `NL` 145 · `X99` 121 · `AC` 118 · `NM` 94 · `UM` 89 · `GS` 45 · `NE` 38 · `NC` 37 · `NW` 33 · `CM` 19 · `BF` 18 · `NK` 18 · `SO` 17 · `PO` 9 · `ABD` 7 · `NP` 7 · `GK` 7 · `BP` 6 · `ADQ` 3 · `PN` 2

### 2.2 `allergen` `unit` (the relation qualifier) — PARTIALLY DOCUMENTED

Schema says only: *"For allergens it tells how the allergen relates to the product: CONTAINS or FREE_FROM."* Actual values on the `allergen` group:

| Value | Rows | Documented? |
|---|---|---|
| `CONTAINS` | 15,610 | yes |
| `MAY_CONTAIN` | 9,956 | **NO — safety-critical** |
| `UNDECLARED` | 303 | **NO** |
| `FREE_FROM` | 0 | documented but never used here |

`FREE_FROM` never appears in the `allergen` group — it lives exclusively in `nonAllergen`. The two groups are **disjoint by relation**, which means a two-valued filter written from the schema silently classifies 9,956 "may contain traces" rows and 303 "undeclared" rows as safe. 93 distinct (id, relation) pairs. Top: `(AM,CONTAINS)` 3,160 · `(AW,CONTAINS)` 2,794 · `(UW,CONTAINS)` 2,550 · `(AE,CONTAINS)` 1,317 · `(AN,MAY_CONTAIN)` 1,225 · `(AY,CONTAINS)` 1,104 · `(AY,MAY_CONTAIN)` 954 · `(AM,MAY_CONTAIN)` 728 · `(SA,MAY_CONTAIN)` 727 · `(SH,MAY_CONTAIN)` 658.

`UNDECLARED` concentrates on a small set of products that list ~14 codes at once (`AC`,`AN`,`NL`,`BC`,`UM`,`BM`,`AP`,`AS`,`AU`,`AF`,`AE`,`AW`,`AY`,`AM` ≈ 19–24 rows each). Semantics unknown; treat as **"no assertion made"**, never as negative.

### 2.3 `nonAllergen` ids — UNDOCUMENTED (same GS1 list)

Where: `classifications[name="nonAllergen"]`. Non-empty on 5,119 products (29.2%). 40 distinct codes, **`unit` is `FREE_FROM` for all 68,597 rows** — a single-valued qualifier, so key on the id alone.

`UM` 4,651 · `AC` 4,632 · `NL` 4,629 · `AU` 4,563 · `BC` 4,560 · `AF` 4,518 · `AP` 4,501 · `AS` 4,353 · `BM` 4,270 · `AN` 4,225 · `AE` 4,026 · `AY` 3,927 · `AM` 3,586 · `AW` 3,580 · `ML` 1,094 · `GS` 700 · `SC` 685 · `GB` 641 · `SW` 633 · `ST` 630 · `SA` 587 · `GO` 558 · `SH` 554 · `NR` 552 · `UW` 512 · `GK` 288 · `SM` 272 · `SP` 272 · `SR` 272 · `X99` 74 · `NC` 49 · `NK` 47 · `NW` 47 · `NE` 46 · `NM` 45 · `UN` 9 · `SO` 3 · `PN` 2 · `PO` 2 · `BF` 2

**The shape of this list is itself the key to the code system** — see §3.1. `UN` (9) appears **only** in `nonAllergen`, never in `allergen`.

### 2.4 `nutritionalClaim` ids — SELF-DESCRIBING

Where: `classifications[name="nutritionalClaim"]`. Non-empty on 7,618 products (43.4%). 21 distinct ids (not 24).

| id | Count |
|---|---|
| FREE_FROM_LACTOSE | 4,178 |
| FREE_FROM_GLUTEN | 3,049 |
| VEGAN | 2,959 |
| VEGETARIAN | 2,358 |
| FREE_FROM_PRESERVATIVES | 1,526 |
| FREE_FROM_COLOURING_AGENTS | 932 |
| FREE_FROM_ADDITIVES | 690 |
| NO_ADDED_SUGARS | 662 |
| HIGH_FIBRE | 420 |
| FREE_FROM_EGGS | 418 |
| HIGH_PROTEIN | 417 |
| LOW_SODIUM_SALT | 390 |
| FREE_FROM_SWEETENERS | 358 |
| FREE_FROM_SOY | 337 |
| LOW_LACTOSE | 321 |
| FREE_FROM_FAT | 158 |
| FREE_FROM_WHEAT | 141 |
| LOW_FAT | 110 |
| FREE_FROM_ARTIFICIAL_SWEETENERS | 24 |
| FREE_FROM_GMO | 14 |
| FREE_FROM_SODIUM_SALT | 13 |

**`unit` on nutritionalClaim** — `FREE_FROM` 11,836 · `DIET` 5,334 · `HIGH` 823 · `LOW` 820 · `NO_ADDED` 662. The structure is now explained: `synkkaId` holds the bare subject (`LACTOSE`, `GLUTEN`, `PROTEIN`, `SUGARS`…) and `unit` holds the direction, so `id` is normally `unit + "_" + synkkaId`. `DIET` is the catch-all direction used when the claim is not directional (`VEGAN`, `VEGETARIAN`) **and inconsistently on directional ones** (`HIGH_PROTEIN` appears 403× with `HIGH` and 14× with `DIET`). **Key on `id`; never on the (id, unit) pair.**

### 2.5 `packagingMarkedLabel` ids — SELF-DESCRIBING

Where: `classifications[name="packagingMarkedLabel"]`. Non-empty on 17,255 (98.3%). `unit` is **always null** (23,582 rows). 19 distinct ids:

| id | Count | Note |
|---|---|---|
| `warmTemperature` | 10,057 | **not a label** — storage pseudo-label |
| `coolTemperature` | 4,060 | **not a label** |
| `freezeTemperature` | 3,245 | **not a label** |
| GOODS_FROM_FINLAND_BLUE_SWAN | 2,057 | Finnish origin mark (Avainlippu family) |
| MADE_IN_FINLAND_FLAG_WITH_KEY | 1,772 | Avainlippu |
| FINNISH_HEART_SYMBOL | 826 | Sydänmerkki (heart-healthy) |
| EU_ORGANIC_FARMING | 456 | EU organic leaf |
| SVANEN | 362 | Nordic Swan ecolabel |
| RAINFOREST_ALLIANCE | 234 | |
| EU_ECO_LABEL | 195 | |
| MARINE_STEWARDSHIP_COUNCIL_LABEL | 104 | MSC |
| FAIR_TRADE_MARK | 92 | |
| AQUACULTURE_STEWARDSHIP_COUNCIL | 51 | ASC |
| KRAV_MARK | 26 | Swedish organic |
| OFFICIAL_ECO_LABEL_SUN | 17 | |
| SOIL_ASSOCIATION_ORGANIC_SYMBOL | 11 | |
| PUHTAASTI_KOTIMAINEN | 7 | "purely domestic" |
| DOLPHIN_SAFE | 7 | |
| UTZ_CERTIFIED | 3 | |

**Always filter out the three `*Temperature` entries before presenting this group as certification data.** They are lowercase-camel, every real label is UPPER_SNAKE — use that as the discriminator. (Their real value is as a cross-check on `temperatureCondition`, see §2.13.)

### 2.6 Nutrient ids — DOCUMENTED IN SCHEMA (9 of 55)

The schema names nine; the data carries **55** across `nutritionalContent` (and the same vocabulary inside the `nutritionFact`/`gda`/`mineral`/`vitamin` classification groups).

**Documented:** `ENER-KJO` 12,178 (energy kJ) · `PRO-` 12,164 (protein) · `FAT` 12,153 · `CHOAVL` 12,138 (carbohydrate) · `ENER-E14` 12,080 (energy kcal) · `SALTEQ` 11,952 (salt) · `FASAT` 11,889 (saturated fat) · `SUGAR-` 11,841 (sugars) · `FIBTG` 6,070 (fibre).

**Undocumented but standard INFOODS/GS1 tags** (meanings HIGH confidence from the tag convention and unit):
`LACS` 3,573 lactose · `NA` 1,078 sodium · `CA` 954 calcium · `VITD-` 602 vitamin D · `VITB12` 583 · `FAMSCIS` 567 cis-monounsaturated fat · `FAPUCIS` 525 cis-polyunsaturated fat · `RIBF` 494 riboflavin (B2) · `VITC-` 394 · `ZN` 329 zinc · `K` 313 potassium · `FE` 311 iron · `MG` 264 magnesium · `P` 260 phosphorus · `VITA-` 249 · `THIA` 234 thiamin (B1) · `NIA` 227 niacin · `VITE-` 223 · `VITB6-` 213 · `ID` 209 iodine · `FOL` 191 folate · `POLYL` 109 polyols · `PANTAC` 83 pantothenic acid · `BIOT` 77 biotin · `CHOL-` 39 cholesterol · `STARCH` 28 · `SE` 27 selenium · `ENER-GRM` 19 · `MN` 17 manganese · `VITK` 14 · `CU` 12 copper · `CAFFN` 12 caffeine · `CLD` 10 chloride · `CR` 8 chromium · `VITD` 8 · `VITC` 7 · `FAPUN3F` 6 omega-3 · `FD` 6 fluoride · `FAPUN6F` 3 omega-6 · `NUCLEOTIDE` 2 · `TAU` 2 taurine · `FOLDFE` 2 folate DFE · `COLG` 2 · `VITE` 1 · `ENER-MGM` 1 · `L_CARNITINE` 1.

Note the **duplicate spellings** — `VITD`/`VITD-`, `VITC`/`VITC-`, `VITE`/`VITE-`. Normalise by stripping a trailing `-`.

### 2.7 Measurement unit codes — DOCUMENTED IN SCHEMA (UN/ECE Rec 20)

| Where | Observed values |
|---|---|
| `nutritionalContent.unit` | `GRM` 83,395 · `KJO` 12,182 · `E14` 12,080 · `MGM` 5,109 · **`MC` 1,988 (undocumented; UN/ECE microgram)** |
| `nutritionalContent.basisQuantityUnit` | `GRM` 103,294 · `MLT` 11,230 · **`PTN` 164 (portion)** · **`H87` 30 (piece)** · `KGM` 27 · **`GL` 9** |
| `nutritionalContent.servingSizeUnit` | `GRM` 5,926 · `MLT` 362 (null 108,466) — matches schema exactly |
| `unitConversions.grossWeight.unit` | `GRM` 14,288 · `KGM` 186 — matches schema |
| `unitConversions.netWeight.unit` | `GRM` 9,297 · `KGM` 489 — matches schema |
| `unitConversions.height/length/width.unit` | `MMT` 14,426/14,426/14,427 · `CMT` 48/48/47 — matches schema |
| `unitConversions.volume.unit` | `GRM` 5,498 · **`H87` 1,500** · `KGM` 875 · `LTR` 762 · `MLT` 259 · `CLT` 50 · `PTN` 9 · `MTR` 8 · `KGM H87` 3 · `PR` 3 · `GRM H87` 2 · `KGM PTN` 1 |
| `gda` group `unit` | `GRM` 78,044 · `KJO` 11,471 · `E14` 11,365 · `MGM` 1 · `MC` 1 |
| `deposits[].unit` | `ST` 576 (only value) |

**`volume` is the dirtiest field in the file.** Only 1,071 of 7,962 rows (13.4%) carry an actual volume unit (`LTR`/`MLT`/`CLT`). 6 rows carry space-separated compound units, which are not valid unit codes at all. `basisQuantity` is 100.0 in 113,093 of ~114,700 rows; the 45 distinct values include 1.0, 40.0, 330.0 and `101.0`/`401.0`-style oddities.

`unitPrecision` — DOCUMENTED (3 of 4 values): `APPROXIMATELY` 107,160 · null 5,156 · `LESS_THAN` 2,424 · `LESS_THAN_OR_EQUAL` 8 (**undocumented**) · `ABOUT` 6.

### 2.8 `synkkaPackagingType` — DOCUMENTED IN SCHEMA, complete

`BASE_UNIT_OR_EACH` 8,215 (consumer unit) · `CASE` 6,249 · `PALLET` 10. No undocumented values. Note 14,474 products have `unitConversions` but only 8,215 `BASE_UNIT_OR_EACH` rows — the consumer level is absent for ~43% of them.

### 2.9 `vatCode` — DOCUMENTED IN SCHEMA, data violates it

Documented: `STANDARD` (25.5 %), `MEDIUM` (13.5 %, food), `LOW` (10 %).

| Value | Count | Valid? |
|---|---|---|
| `MEDIUM` | 11,719 | yes |
| *(key absent)* | 3,068 | n/a |
| `STANDARD` | 2,593 | yes |
| `"MEDIUM MEDIUM"` | **159** | **no — duplicated token** |
| `""` | **4** | **no** |
| `LOW` | 1 | yes |
| `"NOT_APPLICABLE"` | **1** | **no** |
| `"STANDARD MEDIUM"` | **1** | **no — contradictory** |

165 rows (1.1% of populated) are unparseable. Per the schema's own instruction, **use `tax.taxRate` from the price API as the source of truth.** If you must use this field, a forgiving reader is `set(value.split())` and reject anything that is not a singleton of the three documented values.

### 2.10 `productionMethod` — DOCUMENTED IN SCHEMA, data violates it

`AQUACULTURE` 159 · `MARINE_FISHERY` 152 · `INLAND_FISHERY` 22 · **`MARINE_FISHERY1` 3** · **`AQUACULTURE1` 2**. The trailing `1` is a data defect; strip trailing digits before comparing.

### 2.11 `salesUnit` / `baseUnit` / `units[].unitId` — UNDOCUMENTED by design

> "Unit codes such as KI are technical codes and their translations are not included in this data set."

| `salesUnit` (17) | `baseUnit` (16) | `units[].unitId` (23) |
|---|---|---|
| KI 8,005 · ST 5,607 · KG 1,068 · PAK 880 · BAG 697 · RAS 328 · PRK 320 · BOT 310 · SK 120 · CS 72 · **KLE 66** · KRT 48 · KAN 13 · PAL 4 · NIP 3 · DSP 3 · DZ 2 | ST 9,770 · PAK 1,725 · KI 1,573 · BAG 1,222 · KG 1,106 · BOT 893 · PRK 533 · RAS 494 · SK 89 · CS 74 · KRT 41 · KAN 14 · PAL 4 · NIP 3 · DSP 3 · DZ 2 | KI 14,157 · ST 9,832 · PAL 8,303 · **KRS 5,288** · PAK 1,813 · BAG 1,246 · KG 1,131 · BOT 903 · PRK 534 · RAS 524 · CS 227 · SK 129 · KRT 97 · KLE 69 · **ZML 37** · **DOL 26** · KAN 14 · DSP 11 · **KOR 6** · NIP 5 · **PNT 2** · DZ 2 · **MDO 1** |

Structural facts worth relying on: **every product's `salesUnit` and `baseUnit` both appear in its own `units[].unitId` list (0 exceptions)**, so `units` is a complete hierarchy and `sizeInBaseUnits` gives you the conversion without any translation. `KLE` appears as a `salesUnit` but never as a `baseUnit`; `KRS`, `ZML`, `DOL`, `KOR`, `PNT`, `MDO` appear only inside `units`.

Likely Finnish/Swedish abbreviations (**LOW confidence, inference from the language and from `sizeInBaseUnits`, not evidence**): ST *styck* = piece, KI *kiila/kolli* = case/crate, KG kilogram, PAK *pakkaus* = pack, BAG, PRK *purkki* = jar/can, RAS *rasia* = tub/tray, BOT bottle, SK *säkki* = sack, CS case, KRT *kartonki* = carton, KAN *kanisteri* = canister, PAL *lava* = pallet, KRS *kerros* = pallet layer, DZ dozen, NIP, DSP display, KLE, ZML, DOL, KOR *kori* = basket, PNT, MDO. **Do not ship these as facts.** `FINDINGS.md`'s price-ratio trick (`catalogPrice.value / comparisonPrice.value`) avoids needing them at all.

### 2.12 `allowedLotSize` — DOCUMENTED IN SCHEMA

`0.01` on **16,872 (96.2%)** = "no constraint". 73 distinct values. Real steps: 2.0 (92) · 3.0 (85) · **1.5 (62)** · 5.0 (54) · 10.0 (40) · 1.0 (39) · 4.0 (34) · 2.5 (21) · **1.8 (17)** · 6.0 (15) · 15.0 (14) · 1.6 (14) · 1.2 (13) · 0.9 (13) … down to 0.15 and up to 25.0. Non-integer steps (1.5, 1.8, 0.9, 1.44, 3.35) are the rounding edge case.

### 2.13 `temperatureCondition` — UNDOCUMENTED, but **decodable from the data**

> "Code of the temperature (storage and transport) class of the product, e.g. ambient, chilled or frozen. Code meanings are not part of this data set."

Cross-referencing against median `min`/`maxTemperature` and the `*Temperature` pseudo-labels in `packagingMarkedLabel` resolves it almost completely:

| Code | Products | Median min/max °C | Pseudo-label agreement | Inferred meaning | Confidence |
|---|---|---|---|---|---|
| 8 | 10,053 | 10 / 22 | `warmTemperature` 10,048/10,053 | **Ambient / dry** | HIGH |
| 7 | 3,152 | −25 / −18 | `freezeTemperature` 3,148/3,152 | **Frozen** | HIGH |
| 4 | 1,803 | 4 / 8 | `coolTemperature` 1,801/1,803 | **Chilled, +4…+8** | HIGH |
| 3 | 1,673 | 2 / 6 | `coolTemperature` 1,673/1,673 | **Chilled, +2…+6** | HIGH |
| 2 | 324 | 2 / 4 | `coolTemperature` 324/324 | **Chilled, +2…+4** | HIGH |
| 1 | 240 | 0 / 3 | `coolTemperature` 240/240 | **Cold chilled, 0…+3** | HIGH |
| 5 | 221 | 2 / 7 | `coolTemperature` only 7/221 | Chilled (another band) | MEDIUM |
| 6 | 10 | 4 / 20 | none | Mixed/unclassified | LOW |
| 9 | 9 | 0 / 2 | `freezeTemperature` 1/9 | Near-zero / superchilled | LOW |
| null | 61 | 15 / 25 | — | Unknown; behaves ambient | LOW |

**This extends `FINDINGS.md`**, which stated the meanings were unavailable and warned against assuming 8 = ambient. The data says 8 *is* ambient, with 99.95% label agreement. Codes 1–5 are a graded chilled ladder ordered by temperature (1 coldest), 7 is frozen, 8 is ambient. Still prefer `minTemperature`/`maxTemperature` when present (10,156 / 10,266 products) and use the code as the fallback.

### 2.14 `category` — UNDOCUMENTED by design

> "Product category code. Category names are not part of this data set."

**349 distinct codes, all exactly 5 digits.** See §5 for the inference table and hierarchy analysis.

### 2.15 `countryOfOrigin` — DOCUMENTED IN SCHEMA (ISO 3166-1 alpha-2, lowercase)

98 distinct values on 17,537 products. `fi` 7,849 (44.8%) · `de` 1,029 · `it` 977 · `se` 874 · `cn` 741 · `nl` 659 · `fr` 599 · `pl` 431 · `es` 404 · `be` 383 · `dk` 379 · `gb` 289 · `gr` 271 · `ee` 249 · `th` 223 …

**Non-ISO values present:** `zy` 179, `xs` 11, `zz` 5 — user-assigned/private-use ranges. `zz` is conventionally "unknown"; `zy` and `xs` have no standard meaning. A strict ISO validator will reject 195 products; treat these as "origin not stated".

### 2.16 `countriesOfOrigin` — DOCUMENTED IN SCHEMA (ISO 3166-1 numeric)

102 distinct values, zero-padded 3-digit strings. `246` 6,976 (Finland) · `276` 987 (DE) · `752` 770 (SE) · `380` 551 (IT) · `528` 521 (NL) · `250` 438 (FR) · `156` 431 (CN) · `616` 393 (PL) · `208` 378 (DK) · `056` 294 (BE) · `724` 282 (ES) · `233` 251 (EE) · `826` 244 (GB) · `300` 232 (GR) …

**Non-numeric value present: `NON_EU` 10** — the schema only documents `NON_EU` for `ingredients[].origins[].country`, not here. Keep the leading zeros (`056`, not `56`).

`ingredients[].origins[].country` — 75 distinct, same scheme, `246` 2,028 · **`097` 319** (not an assigned ISO code; likely an internal "EU" aggregate — MEDIUM confidence, also 99 occurrences in `countriesOfOrigin`) · `NON_EU` 172.

`ingredients[].origins[].type` — DOCUMENTED (5 of 10): `FARMING` 1,148 · `MILKING` 936 · `REARING` 665 · `BIRTH` 359 · `LAST_PROCESSING` 265 · **undocumented:** `SLAUGHTER` 51 · `IMPORTATION` 16 · `CATCH_ZONE` 15 · `HUNTED_GATHERED` 13 · `CUTTER` 2.

### 2.17 Fishing codes — UNDOCUMENTED by design (FAO code lists)

**Species** (`fishingReports[].id`) — 43 distinct, FAO ASFIS 3-alpha. `TRR` 79 (rainbow trout) · `SAL` 70 (Atlantic salmon) · `HER` 59 (herring) · `ALK` 23 (Alaska pollock) · `POK` 22 (saithe/pollock) · `COD` 16 · `PLN` 9 · `SKJ` 6 (skipjack tuna) · `BFT` 6 (bluefin tuna) · `PRA` 5 (northern prawn) · `MAC` 3 (mackerel) · `PLE` 3 (plaice) … The `name` field gives the Latin binomial, so **species are self-resolving — use `name`, not `id`.** Codes prefixed `F` (`FPI`, `FVE`, `FPP`, `FPE`, `FRO`, `FBM`, `FBU`) are non-ASFIS and appear to be a supplier-local scheme (LOW confidence).

**Areas** (`catchMethods[].areas`) — 31 distinct, FAO major fishing areas with ICES sub-division suffixes. `27` 73 (NE Atlantic) · `67` 26 (NE Pacific) · `05` 25 · `27.3.d` 17 (Baltic) · `61` 14 (NW Pacific) · `27.2` 9 · `21` 7 (NW Atlantic) · `51` 5 (W Indian) · `27.5.a` 5 · `27.4.b` 5 · `71` 4 · `88` 3 (Antarctic) · `34` 2 (E Central Atlantic) … **Dirty:** `02`, `04`, `05` are not FAO major areas (FAO uses 18, 21, 27, 31, 34, 37, 41, 47, 48, 51, 57, 58, 61, 67, 71, 77, 81, 87, 88) and `271`/`27.21`/`27.41` look like `27.1`/`27.2.1`/`27.4.1` with the dots lost. Normalise before matching.

**Methods** (`catchMethods[].methods`) — 26 distinct, **two mixed schemes**: FAO ISSCFG alpha (`TM` 31 midwater trawl · `PS` 8 purse seine · `FYK` 6 fyke net · `TX` 4 · `FPO` 3 pots · `TMS` 2 · `GN` 2 gillnet · `TBB` 2 beam trawl · `LL` 2 longline · `OTM` 1 · `SSC` 1 · `TB`/`TBS`/`LX`/`GEN`/`FCN`/`FWR` 1 each) and EU numeric gear codes (`03` 118 · `07` 17 · `02` 17 · `01` 12 · `05` 9 · `09` 9 · `08` 6, plus zero-padding errors `032` 3 and `022` 2). **A loader must branch on `code.isdigit()`.**

### 2.18 GHS statement codes — UNDOCUMENTED by design (CLP Regulation)

> "Statement code, for example h319 or p280. Descriptions of the codes are not in this dataset"

**Lowercase**, combined statements joined with `+`. These are the standard CLP H/P/EUH codes — the full text is in Annex III/IV of Regulation (EC) 1272/2008, which is public, so this is a lookup-table problem, not an inference problem.

`HazardStatement` (31 distinct): `h319` 168 (serious eye irritation) · `h314` 93 (severe skin burns) · `h290` 64 (corrosive to metals) · `h315` 52 · `h318` 43 (serious eye damage) · `h229` 32 (pressurised container) · `euh208` 29 · `h412` 28 · `euh210` 26 · `h225` 21 · `h222` 20 · `h317` 14 · `h400` 11 · `h335` 10 · `h302` 9 · `h410` 9 · `h226` 9 · `h411` 8 · `h223` 6 · `h336` 6 · `h220` 4 · `h228` 4 · `euh071` 4 · `euh031` 4 · `h315+h320` 1 · `h280` 1 · `h373` 1 · `h304` 1 · `h334` 1 · `h272` 1 · `euh066` 1.

`PrecautionaryStatement` (49 distinct): `p305+p351+p338` 250 · `p280` 175 · `p102` 167 · `p310` 91 · `p337+p313` 84 · `p101` 77 · `p501` 74 · `p303+p361+p353` 66 · `p210` 62 · `p302+p352` 41 · `p410+p412` 34 · `p313` 33 · `p251` 32 · `p211` 26 · `p260` 23 · `p301+p330+p331` 20 … plus **`unspecified` 5**, which is not a code.

### 2.19 Deposit `material` codes — UNDOCUMENTED and unresolvable

> "Product code of the deposit material."

7 distinct values on 576 lines across 506 products: `1` 160 · `4` 155 · `3` 119 · `171` 69 · `147` 46 · `2` 25 · `9708918` 2.

**Verified: 0 of 576 resolve to any `id` in the catalog**, despite the schema calling them product codes. No deposit price list exists in the dataset. Order totals for deposit-bearing goods are therefore **structurally incomplete and the gap is not quantifiable**. Likely a packaging-material key (glass / PET / aluminium / crate) rather than a sellable product — LOW confidence.

### 2.20 Other small vocabularies

- `classifications[].type` — DOCUMENTED, complete: `ENUM` / `DECIMAL`, and **fixed per group name** (no group ever mixes).
- `safetyData[].values[].type` — DOCUMENTED, complete: `HazardStatement` / `PrecautionaryStatement`.
- Language codes (`language` on all text arrays) — DOCUMENTED as ISO 639-1. `fi` 100%, `en` 99.99%, `sv` 91.8%.
- `producers[].id` — DOCUMENTED as "a 13-digit location number" (GS1 GLN). No registry supplied; `name` is populated, so use the name.

---

## 3. Inferring the allergen code system

### 3.1 The decisive structural clue

The 14 most-used `nonAllergen` codes form a tight block, all between 3,580 and 4,651 occurrences, then drop off a cliff to `ML` at 1,094:

`UM` 4,651 · `AC` 4,632 · `NL` 4,629 · `AU` 4,563 · `BC` 4,560 · `AF` 4,518 · `AP` 4,501 · `AS` 4,353 · `BM` 4,270 · `AN` 4,225 · `AE` 4,026 · `AY` 3,927 · `AM` 3,586 · `AW` 3,580

**That is exactly 14 codes, and the EU has exactly 14 mandatory declarable allergens** (Regulation 1169/2011 Annex II). A product making a free-from declaration declares against the statutory list, which is why these 14 move together. Mapping the 14 names onto the 14 codes, 12 are then confirmed independently by ingredient evidence (below) and the remaining **two — lupin and molluscs — are fixed by elimination**: `NL` = lupin, `UM` = molluscs.

Everything beyond those 14 is a **sub-code**: tree-nut species (`SA`, `SH`, `SW`, `SC`, `ST`, `SM`, `SP`, `SR` under `AN`), gluten cereals (`UW`, `GB`, `NR`, `GO`, `GS`, `GK`, `NM` under `AW`), `ML` lactose under `AM`, and a tail of non-statutory sensitivities (`NE`, `NK`, `NW`, `NC`, `CM`, `BF`, `PO`).

### 3.2 Method

For each code, token frequency in `keyIngredients` (en ∪ fi) of the products carrying it as **CONTAINS** only, scored by in-group rate × lift over the catalogue baseline. "Evidence" below gives the discriminating token, its in-group rate, and its lift.

### 3.3 The table

| Code | Count | Inferred meaning | Conf. | Evidence |
|---|---|---|---|---|
| `AM` | 3,902 | **Milk** (EU-14) | HIGH | *milk* 75.5% ×4.4; *maito* 54.8% ×5.3; *maitojauhe* 24.1% ×5.3; *butter* 32.9%; *cream* 28.8% |
| `AW` | 3,113 | **Cereals containing gluten** (EU-14, the umbrella code) | HIGH | *wheat* 84.6% ×5.8; *vehnäjauho* 71.8% ×6.0; *flour* 77.0%. Co-occurs with `UW`/`GB`/`NR` as the parent |
| `UW` | 2,899 | **Wheat** (sub-code of `AW`) | HIGH | *wheat* 92.4% ×6.4; *vehnäjauho* 78.9% ×6.5 — higher wheat purity than `AW`, i.e. species-specific |
| `AY` | 2,077 | **Soybeans** (EU-14) | HIGH | *soijalesitiini* 40.3% ×15.0; *soy* 46.5% ×8.6; *soya* 34.5% ×10.1; *lecithin* 39.8% ×9.6 |
| `AE` | 1,910 | **Eggs** (EU-14) | HIGH | *egg* 80.9% ×10.3; *kananmuna* 60.6% ×12.5; *yolk* 18.9% ×13.3 |
| `AN` | 1,538 | **Tree nuts** (EU-14, umbrella) | HIGH | *nuts* 46.0% ×11.9 with *manteli* 29.8%, *hasselpähkinä* 19.0%, *almonds* 31.8% all mixed — generic, not one species |
| `SA` | 931 | **Almonds** | HIGH | *manteli* 59.3% ×70.8; *almond* 54.4% ×34.0; *mantelit* 19.1% ×76.2 |
| `BM` | 890 | **Mustard** (EU-14) | HIGH | *sinapinsiemen* 68.5% ×35.4; *mustard* 83.5% ×21.0; *sinappi* 36.4% ×32.4 |
| `GO` | 857 | **Oats** | HIGH | *oat* 80.7% ×27.3; *kaura* 31.5% ×29.1; *kauralese* 15.6% ×30.5 |
| `SH` | 796 | **Hazelnuts** | HIGH | *hasselpähkinät* 34.1% ×112.8; *hasselpähkinä* 47.1% ×100.8; *hazelnuts* 63.8% ×40.2 |
| `AS` | 778 | **Sesame seeds** (EU-14) | HIGH | *seesaminsiemen* 39.5% ×92.4; *seesamiöljy* 22.2% ×84.8; *sesame* 84.6% ×31.4 |
| `NR` | 731 | **Rye** | HIGH | *rye* 92.6% ×34.7; *ruisjauho* 30.2% ×37.8; *ruismallas* 20.4% ×39.4 |
| `GB` | 627 | **Barley** | HIGH | *barley* 86.8% ×36.3; *ohramallas* 24.4% ×40.8; *ohramallasuute* 22.1% ×41.3 |
| `AF` | 546 | **Fish** (EU-14) | HIGH | *fish* 22.5% ×28.4; *kirjolohi* 21.4% ×36.9; *salmon* 19.7% ×36.9; *lohi*, *trout* all ×36 |
| `AP` | 532 | **Peanuts** (EU-14) | HIGH | *maapähkinä* 63.0% ×197.4; *peanut* 41.1% ×147.2; *maapähkinät* 16.4% ×160.2 |
| `ML` | 527 | **Lactose** (sub-code of `AM`) | HIGH | *milk* 86.6%; *laktoosi* 19.8% ×19.9; *whey* 29.0% ×10.8 — milk-derived but keyed on lactose, matches the `LACS` nutrient and the `LOW_LACTOSE` claim |
| `ST` | 390 | **Pistachios** | HIGH | *pistaasipähkinä* 52.9% ×309.6; *pistachio* 70.6% ×209.9; *pistaasi* 20.6% ×301.0 |
| `AU` | 354 | **Sulphur dioxide / sulphites** (EU-14) | HIGH | *kaliumdisulfiitti* 27.7% ×62.3; *metabisulphite* 15.7% ×55.2; *sulphite* 15.7% ×52.1; *dioxide* 15.4% |
| `SW` | 350 | **Walnuts** | HIGH | *saksanpähkinät* 22.2% ×779.8; *saksanpähkinä* 55.6% ×406.2; *walnuts* 55.6% ×165.2 |
| `SC` | 326 | **Cashews** | HIGH | *cashewpähkinä* 58.6% ×263.7; *cashew* 63.8% ×169.6; *cashews* 22.4% ×64.5 |
| `BC` | 324 | **Celery** (EU-14) | HIGH | *selleri* 49.6% ×96.8; *celery* 80.7% ×63.5; *selleriä* 25.2% ×35.9 |
| `SP` | 290 | **Pecans** | HIGH | *pekaanipähkinä* 100% ×1754.6; *pecan* 60.0% ×219.3 |
| `SM` | 177 | **Macadamia nuts** | HIGH | *macadamia* 100% ×649.9; *macadamiapähkinä* 60.0% ×3509.2 (n=5 CONTAINS, but unambiguous) |
| `SR` | 171 | **Brazil nuts** | MEDIUM | Only 3 CONTAINS, all generic nut mixes. Decided by elimination: the one explicit list reads *"may contain traces of nuts (almonds, hazelnuts, cashews, **Brazil nuts** and walnuts)"* and Brazil nut is the one EU tree-nut species with no other code |
| `NL` | 145 | **Lupin** (EU-14) | HIGH (structural) | Fixed by the EU-14 elimination in §3.1. **Ingredient evidence is contradictory**: 3 of its 5 CONTAINS products mention *mussel* — these also carry `UM`, so the tokens leak. Trust the structure, not the tokens. |
| `X99` | 121 | **Other / unspecified** | HIGH | No ingredient signal at all; carriers are juices and crisps (*juice* 80.2%, *concentrate* 79.3%, *citric* 51.2%) with no allergen in common. See warning below. |
| `AC` | 118 | **Crustaceans** (EU-14) | HIGH | *katkarapu* 43.1% ×210.2; *shrimp* 31.4% ×344.0; *pandalus borealis* 15.7% ×305.8 |
| `NM` | 94 | **Maize / corn** | HIGH | *corn* 66.3% ×8.9; *maissitärkkelys* 48.3%; *maissijauho* 16.9% ×12.0 |
| `UM` | 89 | **Molluscs** (EU-14) | HIGH | Structure + tokens agree: *squid* ×923.5, *snail* ×527.7, *sinisimpukka* ×692.6, *osteriuute* ×692.6, *oyster* ×167.9; carriers include "Razor Clam", "Smoked blue mussel", "Octopus ink" |
| `GS` | 45 | **Spelt** | MEDIUM | *spelt* 50.0% ×626.6; *speltti* 25.0% ×548.3 — only 12 CONTAINS and the other half of the tokens are generic cereals |
| `NE` | 38 | **Peas** | HIGH | *pea* 73.7% ×34.7; *herne* 44.7% ×71.4; *herneproteiini* 42.1%; *peas* ×109.4 |
| `NC` | 37 | **Cocoa** | MEDIUM | *cocoa* 81.1% ×16.1; *kaakaovoi* 70.3% ×18.1; *chocolate* 59.5% ×25.6 — every carrier is a chocolate product, but chocolate also carries milk/soy/nut codes, so the lift is weaker |
| `NW` | 33 | **Carrot** | HIGH | *carrot* 81.8% ×18.7; *porkkana* 78.8% ×20.2 (plus leek/parsnip as recipe companions) |
| `CM` | 19 | **Chicken meat** | HIGH | *chicken* 89.5% ×30.2; *broilerinlihaa* 26.3% ×659.6; *rintafilee* 36.8% ×170.1 |
| `BF` | 18 | **Beef** | HIGH | *beef* 77.8% ×19.9; *naudanlihaa* 16.7% ×324.9; *naudanlihauute* 22.2% ×111.4 |
| `NK` | 18 | **Coriander** | HIGH | *korianteri* **100%** ×32.6; *coriander* 94.4% ×32.4 |
| `SO` | 17 | **Carob / locust bean** | LOW | *locust* 81.2% ×65.1; *johanneksenleipäpuujauhe* 81.2% ×51.3. But all 16 CONTAINS carriers are ice creams from two brands, so this may be one supplier's habit rather than the code's meaning. Could equally be a soy variant. |
| `PO` | 9 | **Pork** | MEDIUM | *pork* 77.8% ×19.3; *porsaanliha* 44.4% ×36.6 (n=9) |
| `ABD` | 7 | **Tuna** | MEDIUM | *tuna* **100%** ×797.5; *tonnikala* 100% ×626.6; *Katsuwonus pelamis* 60% ×1503.9. All 5 CONTAINS carriers are tuna products. Note the 3-letter shape — a different code family from everything else. |
| `NP` | 7 | *unknown* | LOW | 4 CONTAINS: a sugar bun, broad beans, glögg jellies, a Christmas loaf. No common token above noise. Pulses/legumes is a guess only. |
| `GK` | 7 | **Khorasan wheat (kamut)** | LOW | 7 MAY_CONTAIN, **0 CONTAINS** — no ingredient evidence whatsoever. Carriers are brioche buns and chocolate bars. Inferred purely from its position in the `G*` cereal family (`GO` oats, `GB` barley, `GS` spelt) and the EU-14 cereal list, where kamut is the remaining named grain. |
| `BP` | 6 | **Fragrance / cosmetic sensitiser** | LOW | Not a food code: all 6 carriers are non-food (toilet rim block, lip balms, hand washes, shower gel). Tokens *linalool* ×584.9, *limonene* ×302.5, *edta* ×337.4, *aqua* ×104.4. Plausibly "Balsam of Peru" or a perfume-allergen flag. |
| `ADQ` | 3 | *fish-related, unknown* | LOW | 3 CONTAINS, all breaded white fish (Fish'n'Chips, saithe). *kala*/*fish* 100%, but n=3 and `AF` already covers fish. Possibly a species sub-code. 3-letter, like `ABD`. |
| `PN` | 2 | *unknown* | LOW | 1 CONTAINS (granola), 1 MAY_CONTAIN (ice cream). Pine nuts would fit the `*N*`/nut families but there is no token evidence. **Do not use.** |

**Codes to treat as unusable:** `PN`, `NP`, `ADQ`, `GK`, `BP`, `SO` (31 products total). **`UN`** appears 9 times and *only* in `nonAllergen`, never in `allergen` — no evidence at all; most likely "unspecified".

### 3.4 `X99` is unusable for safety claims — flag it loudly

`X99` means **"other / unspecified allergen"**. It appears 121× as `CONTAINS` and 74× as `FREE_FROM`.

- `X99 CONTAINS` tells you *an* allergen is present but **not which one**. Its carriers (fruit juices, kettle chips, smoothies) share no allergenic ingredient, which confirms the code is a free-text escape hatch, not a substance.
- `X99 FREE_FROM` is worse: it is a free-from claim about an unnamed substance, i.e. semantically empty.

**Rule:** a product with `X99 CONTAINS` can never be certified free of any allergen, and `X99 FREE_FROM` must never satisfy a free-from query. Surface it as "manufacturer declares an unspecified allergen — manual review required".

---

## 4. The nutritional-claim / allergen trap

### 4.1 The trap

`FREE_FROM_LACTOSE` is a **`nutritionalClaim`**. `AM` (milk) is an **`allergen`**. They live in different classification groups, answer different questions, and **are not consistent with each other by design**:

- *Lactose-free* is a **processing** claim — the lactose has been enzymatically split. The milk protein (casein, whey) is still there.
- *Milk-allergen-free* is a **composition** claim — no milk-derived ingredient at all.

A lactose-free milk drink is correctly both `FREE_FROM_LACTOSE` **and** `AM: CONTAINS`. It is safe for lactose intolerance and **lethal for milk-protein allergy**.

### 4.2 The worked case

Product **`464306`** — "Valio Hyvä suomalainen Arki® Eila® kevytmaitojuoma 1 l laktoositon" (the cheapest candidate in the canonical 1,000-litre example in `FINDINGS.md`):

```
nutritionalClaim: FREE_FROM_LACTOSE, FREE_FROM_ADDITIVES, FREE_FROM_COLOURING_AGENTS,
                  FREE_FROM_PRESERVATIVES, FREE_FROM_SWEETENERS, LOW_FAT,
                  LOW_SODIUM_SALT, NO_ADDED_SUGARS, VEGETARIAN
allergen:         AM = CONTAINS
```

The canonical demo product is itself the counter-example.

### 4.3 Quantification

Of the **4,178** products claiming `FREE_FROM_LACTOSE`:

| `AM` allergen relation | Products | Share |
|---|---|---|
| **`CONTAINS`** | **1,485** | **35.5%** |
| `MAY_CONTAIN` | 361 | 8.6% |
| `UNDECLARED` | 1 | 0.0% |
| no `AM` assertion at all | 2,331 | 55.8% |
| `FREE_FROM` (in `nonAllergen`) | 1,255 | 30.0% |

**More than a third of all lactose-free products explicitly contain the milk allergen**, and another 8.6% may. Only 30% carry a positive `AM FREE_FROM` assertion. The 55.8% with no assertion are the dangerous middle: silence is not a negative.

The same trap exists on gluten. Of **3,049** `FREE_FROM_GLUTEN` products, cereal allergens are declared `CONTAINS` on: `GO` (oats) **196**, `UW` (wheat) 30, `GB` (barley) 12, `AW` 11, `NR` (rye) 2. Gluten-free oats are a legitimate product (certified low-gluten oats) — but a naive engine that treats `FREE_FROM_GLUTEN` as "no cereal allergens" gets 196 products wrong. And `LOW_LACTOSE` carries `AM: CONTAINS` on **300 of 321** (93.5%), which is expected and should be stated as such.

### 4.4 The rule an allergen-safety engine must follow

1. **Never read a `nutritionalClaim` as an allergen assertion.** The two groups are separate namespaces. `FREE_FROM_LACTOSE` ⇏ `AM FREE_FROM`. `FREE_FROM_GLUTEN` ⇏ no `AW`. `FREE_FROM_EGGS`/`FREE_FROM_SOY`/`FREE_FROM_WHEAT` are marketing claims, not the GS1 declaration.
2. **Resolve the allergen question from one place only:** `allergen` (relations `CONTAINS` / `MAY_CONTAIN` / `UNDECLARED`) and `nonAllergen` (relation `FREE_FROM`).
3. **Four-state, not two-state.** For a query "free of allergen *X*":
   - `nonAllergen` has *X* → **SAFE (certified)**
   - `allergen` has *X* as `CONTAINS` → **UNSAFE**
   - `allergen` has *X* as `MAY_CONTAIN` → **UNSAFE for a safety query** (may be offered with an explicit warning for a preference query)
   - *X* appears nowhere, or as `UNDECLARED`, or the product carries `X99` → **UNKNOWN**, which is *not* safe. 59% of the catalogue lands here.
4. **Only `nonAllergen` certifies.** Absence of `CONTAINS` is never evidence of absence. Report coverage honestly: only ~29% of the catalogue can ever be certified free of anything.
5. **Expand sub-codes before answering.** "Milk-free" must check `AM` **and** `ML`. "Gluten-free" must check `AW` and `UW`, `GB`, `NR`, `GO`, `GS`, `GK`, `NM`. "Nut-free" must check `AN` and `SA`, `SH`, `SW`, `SC`, `ST`, `SM`, `SP`, `SR`. A query on the umbrella code alone under-reports.
6. **2 products are internally contradictory** — `468044` asserts `AM` in both `allergen` and `nonAllergen`; `469429` does so for `AM` and `AN`. Resolve conflicts toward unsafe and log them.

---

## 5. `category` inference

### 5.1 The 30 largest categories

349 distinct codes, all 5 digits. Names derived from lift-ranked tokens over the Finnish and English product names within each code; the `ex:` column shows real members. **Confidence is HIGH for the name's subject area, MEDIUM for its exact boundary** (several codes split a subject across sibling codes).

| Code | Products | Inferred name | Discriminating tokens / examples |
|---|---|---|---|
| 17300 | 443 | Chilled ready meals, casseroles & soups | feelia, casserole, soup, saarioinen, kokkikartano, mashed potatoes · "Saarioinen Cabbage casserole", "Feelia Goulash Soup Concentrate" |
| 22630 | 432 | Spices & seasoning blends | santa maria, meira, seasoning, pepper, mausteseos, mustapippuri · "Santa Maria Chili Explosion" |
| 41763 | 349 | Frozen cakes & tarts | cake, tart, leivospohja, cheesecake, shell, frozen · "RF Cheese cake with Raspberry swirls" |
| 64004 | 343 | Disposable trays, containers & lids | tray, biopak, rasia, lid, container, kansi · "Huhtamaki 40x230ml round plastic container" |
| 41760 | 244 | Bread (incl. frozen/part-baked) | bread, baguette, rye, vaasan, baked, sandwich, leipä · "Vaasan Mini wheat baguette" |
| 63235 | 238 | Napkins | lautasliina, napkin, dunisoft, dunilin, duni, fold · "Duni 40cm 3-ply napkin" |
| 41755 | 221 | Frozen pizza, pasta & ready meals | pizza, grandiosa, mccain, ravioli, surgital, pakasteateria · "Mondo Fresco Portobello Ravioli" |
| 22601 | 190 | Baking decorations & baking sugar | oetker, valrhona, callebaut, nonparelli, sprinkles, vaniljasokeri · "Dr. Oetker Candied lemon peel" |
| 21917 | 190 | Sauces & dressings (ambient) | sauce, kastike, pesto, bbq, teriyaki, sriracha · "Rydbergs Remoulade dressing" |
| 63114 | 181 | Cleaning agents & disinfectants | cleaner, puhdistusaine, kiilto, disinfectant, spray · "Suma Auto Oven Rinse D9.11" |
| 64001 | 180 | Disposable cups & drink glasses | cup, kartonkinen, paperboard, huhtamaki, kuumakuppi, lid · "Biopak 20cl Crystallo plastic glass" |
| 41764 | 179 | Sweet bakery: donuts, croissants, buns | donut, croissant, bun, doughnut, cinnamon, korvapuusti · "Vaasan Ring donut" |
| 63120 | 164 | Cleaning cloths, brushes & mops | cloth, brush, taski, handle, floor, mop · "Fredman Carita Premium fibre cloth" |
| 22700 | 157 | Soft drinks & lemonades | virvoitusjuoma, soft, lemonade, cola, zero, coca, muovipullo · "TOMARCHIO blood orange lemonade" |
| 52210 | 152 | Bagged confectionery & liquorice | candy, karkkipussi, malaco, makeissekoitus, remix, liquorice, fazer · "Fazer Marianne Toffee candy bag" |
| 10412 | 150 | Yoghurt | yoghurt, jogurtti, laktoositon, luonnonjogurtti, greek · "Arla Kalinka Strawberry yoghurt" |
| 18720 | 149 | Beef cuts (chilled) | naudan, beef, striploin, ulkofilee, takuumurea, tenderloin · "DRY AGED BONELESS BEEF ENTRECOTE" |
| 21596 | 147 | Preserved peppers, olives & capers | peppers, pepperoni, artichoke, stuffed, kapris, jalapeno · "Royal mild green pepper" |
| 41753 | 146 | Frozen vegetable & falafel patties | patty, kasvispihvi, vegetable, kypsä, pakaste · "Apetit Carrot Patty cooked frozen" |
| 21380 | 140 | Dry pasta | pasta, rummo, cecco, barilla, penne, macaroni, spaghetti · "Barilla 5kg Fusilli dry pasta" |
| 41705 | 140 | Frozen meatballs & meat patties | lihapyörykkä, meatball, patty, lagerblad, kypsä · "Saarioinen Ground beef patty frozen" |
| 41820 | 139 | Scooping / bulk ice cream | ice, jäätelö, irtojäätelö, scoop, sorbet, gelatolab, ingman · "Ingman 5L/2,6kg Daim scooping" |
| 41731 | 136 | Frozen vegetables | pakaste, apetit, diced, broccoli, sipulikuutio, parsakaali · "Apetit Kotimainen Peas frozen" |
| 41762 | 131 | Savoury pasties & pies | pastry, riisipiirakka, pasty, pie, lihapasteija, focaccia · "Myllyn Paras Egg-Rice Pastry" |
| 10600 | 129 | Hard & semi-hard cheese | juusto, gouda, oltermanni, cheese, valio, reggiano, polar · "GOUDA OLD N.4KG" |
| 41710 | 129 | Frozen & prepared chicken | chicken, broilerin, grillattu, roasted, breast, breaded · "Kariniemen Chicken mince 3 kg frozen" |
| 63001 | 125 | Hand soap & shower products | soap, nestesaippua, hand, foam, wash, shower, erisan · "Dove Liquid Hand soap refill" |
| 64003 | 125 | Paper doilies, straws & foil trays | kakkupaperi, fredman, doily, straw, paperipilli, foil · "Fredman foil tray 2,4l 1/2 GN" |
| 22140 | 125 | Flavoured syrups | syrup, siirappi, monin, makusiirappi, routin, karamelli · "Dansukker White Syrup 700g" |
| 41800 | 124 | Ice-cream sticks & cones (single-serve) | jäätelötuutti, cone, jäätelöpuikko, magnum, stick · "Fazer Pätkis ice cream stick" |

Compare 41820 (bulk/scooping ice cream) with 41800 (single-serve sticks and cones): the same product domain, deliberately split by format. Treat sibling codes as **format variants of one subject**, not interchangeable.

### 5.2 Are the 5-digit codes hierarchical? — Yes, measurably

Test: build a token profile for each category (name tokens, rate per product), then cosine-compare category pairs, restricted to categories with ≥10 products (102 categories, 41,901 pairs).

| Pair relationship | Pairs | Mean cosine | Median |
|---|---|---|---|
| **Same first 4 digits** (e.g. 10400 vs 10401) | 451 | **0.280** | 0.233 |
| Same first 3 digits only | 1,401 | 0.203 | 0.110 |
| **Different prefix** | 40,343 | **0.025** | 0.002 |

Same-4-digit pairs are **11× more similar on average and ~100× more similar at the median** than unrelated pairs. The requested specific comparison:

- `cos(10400, 10401)` = **0.471** (drinking milk vs liquid milk/creams — 91 and 53 products)
- `cos(10400, 52201)` = **0.146** (drinking milk vs chocolate)
- `cos(10401, 52201)` = **0.058**
- `cos(10400, 10402)` = 0.235
- `cos(52201, 52202)` = 0.482
- `cos(41820, 10400)` = 0.133 (ice cream vs drinking milk — different prefix, low)

Products in 10400 and 10401 are **3.2× closer than 10400 and 52201**, and 10401/52201 are essentially unrelated.

**First-2-digit prefixes** also partition the catalogue into coherent divisions: `21` (74 categories), `17` (54), `10` (43, dairy), `41` (38, frozen/bakery), `63` (32, cleaning/hygiene), `22` (31, beverages/baking), `64` (17, disposables), `18` (16, meat), `20` (15), `52` (9, confectionery), `90` (8), `85`/`84` (3 each), `67` (2), `11`/`32`/`77`/`30` (1 each).

**Confidence: HIGH that the codes are hierarchical and that prefix length correlates monotonically with semantic proximity. MEDIUM on the exact digit boundaries** — the 2-digit division and the 4-digit sibling group are both clearly real; whether digit 3 is a separate level or just carries through is less clear (same-3-only pairs sit between the other two but with a very low median of 0.110, so the 3-digit level is weak).

**Practical consequence for substitution:** `FINDINGS.md` reports 230/250 (92%) of explicit substitution pairs stay inside the same `category`. Of the remaining 8%, a same-first-4-digits fallback is the next-best candidate generator and is now empirically justified. Do **not** fall back to the 3-digit prefix — the similarity is too weak to defend on stage.

---

## 6. Validation rules for a loader

### 6.1 Enforce (schema-derived, data-confirmed clean)

1. `deleted` is always `false`; reject the file if any product is `true`.
2. All 10 top-level required keys and all 7 `synkkaData` required keys exist on every product — assert, don't `.get()`, for these only.
3. Every `unitConversions` entry has `grossWeight`, `height`, `length`, `width`, `synkkaPackagingType` (0 violations).
4. `salesUnit` and `baseUnit` are always present in the product's own `units[].unitId` (0 violations) — assert this and use `units[].sizeInBaseUnits` for conversions.
5. `salesUnitGtin` is globally unique (0 duplicates) — safe as a secondary key, but absent on 159 products.
6. `substitutions[].product` always equals the owning product's `id` (0 violations) and every `substituteProduct` resolves to a real `id` (0 dangling). The relation is **directed** — symmetrise it yourself.
7. `classifications[].type` is fixed per group `name` — reject a `nutritionalClaim` group typed `DECIMAL`.
8. Every DECIMAL classification value carries `value` (0 missing), even though the schema allows its absence.
9. `countriesOfOrigin` strings must stay zero-padded 3-char (`056`, not `56`).

### 6.2 Handle defensively (declared or implied constraints the data violates)

| Rule | Violations | Handling |
|---|---|---|
| `allergen.unit` ∈ {CONTAINS, FREE_FROM} per schema | **10,259 rows** (`MAY_CONTAIN` 9,956, `UNDECLARED` 303) | Accept all four states. **Treat an unknown relation as unsafe**, never as absent. |
| `vatCode` ∈ {STANDARD, MEDIUM, LOW} | **165 rows** ("MEDIUM MEDIUM" 159, "" 4, NOT_APPLICABLE 1, "STANDARD MEDIUM" 1) | Do not parse. Use `tax.taxRate` from `/price`. If forced, reject non-singletons. |
| `productionMethod` ∈ 3 documented values | **5 rows** (`MARINE_FISHERY1`, `AQUACULTURE1`) | Strip trailing digits. |
| `unitPrecision` ∈ 3 documented values | 8 rows (`LESS_THAN_OR_EQUAL`) | Accept; treat as `LESS_THAN`. |
| `unitConversions.volume.unit` is a volume unit | **6,891 of 7,962 rows (86.6%)** are GRM/KGM/H87/PTN/MTR, incl. 6 compound strings | Never read `.volume` as litres. Three-tier fallback (price ratio → netWeight → name token) with a confidence flag. |
| `countryOfOrigin` is a valid ISO 3166-1 alpha-2 | **195 rows** (`zy` 179, `xs` 11, `zz` 5) | Map to "origin not stated". |
| `countriesOfOrigin` is numeric | 10 rows (`NON_EU`), plus 99 rows of non-assigned `097` | Allow the `NON_EU` sentinel; treat `097` as an unresolved aggregate. |
| `deposits[].material` is "a product code" | **576 of 576** resolve to no `id` | Deposits are unpriceable. Carry them as an explicit "incomplete total" flag on the 506 affected products. |
| `classifications[].name` ∈ 7 documented names | `composition`, `mineral`, `vitamin` | Accept unknown group names; don't hard-code the list. |
| `packaging` group carries data | 0 of 17,535 non-empty | Don't model it. |
| Required arrays are non-empty | `materialAdditionalDescriptions` 99.9% empty; `nutritionalContent` 30.2%; `keyIngredients` 19.9% | Present ≠ populated. Check length, not presence. |
| Fishing method codes share one scheme | 2 schemes mixed + zero-padding errors (`032`, `022`) | Branch on `isdigit()`; normalise padding. |
| Fishing area codes are FAO major areas | `02`, `04`, `05`, `271`, `27.21`, `27.41` | Normalise lost dots; flag the rest unresolved. |
| GHS statement ids are codes | 5 rows of literal `unspecified` | Skip. |
| Nutrient ids are canonical | `VITD`/`VITD-`, `VITC`/`VITC-`, `VITE`/`VITE-` | Normalise by stripping a trailing `-`. |
| A code is not both `allergen` and `nonAllergen` | **2 products** (`468044` → AM; `469429` → AM, AN) | Resolve toward unsafe; log. |
| No self-referential substitution | **1 row** | Drop. |

### 6.3 Performance

Use `id` as the primary key, **not** GTIN — 3,068 products (17.5%) have no `synkkaData.gtin`. The 87 MB array costs ≈15 s and ~2 GB RSS via `json.load`; build an id-indexed slim projection once and work from that.

---

## 7. Deltas against `FINDINGS.md`

**Extends:**
- `temperatureCondition` is **decodable** (§2.13): 8 = ambient (99.95% label agreement), 7 = frozen, 1–5 = a chilled ladder ordered coldest-first. `FINDINGS.md` says the meanings are unavailable and warns against assuming 8 = ambient — the data says 8 *is* ambient.
- A **fourth** allergen relation exists: `UNDECLARED` (303 rows), alongside the undocumented `MAY_CONTAIN`. `FINDINGS.md` lists only `MAY_CONTAIN`.
- The allergen code system is now mapped: 30 codes at HIGH confidence, 5 at MEDIUM, 6 unusable (§3.3). The EU-14 block in `nonAllergen` is the structural key.
- `category` hierarchy is now **quantified** (§5.2), justifying a same-first-4-digits substitution fallback.
- `nutritionalClaim`'s `unit` inconsistency is explained: `synkkaId` holds the subject, `unit` the direction, with `DIET` as the catch-all. Confirms "key on the id".
- `packaging` is a declared classification group that is **always empty**; `composition`/`mineral`/`vitamin` are real groups absent from the schema.
- `salesUnit`/`baseUnit` are always present in the product's own `units[]` (0 exceptions), so `sizeInBaseUnits` gives a translation-free conversion path alongside the price-ratio trick.
- `materialAdditionalDescriptions` is a schema-required field that is empty on 99.9% of products.

**Corrects:**
- `nutritionalClaim` has **21** distinct ids, not 24. `FREE_FROM_GLUTEN` is 3,049 (not 3,047). `HIGH_PROTEIN` is 417 total.
- `packagingMarkedLabel` ids are `MARINE_STEWARDSHIP_COUNCIL_LABEL` (not `MSC`), `AQUACULTURE_STEWARDSHIP_COUNCIL` (not `ASC`), `KRAV_MARK` (not `KRAV`). 19 ids total including the 3 pseudo-labels, so **16 real certificates**.
- `allergen` has **44** distinct ids (93 (id, relation) pairs), `nonAllergen` **40**.
- Substitutions: **196** products carry a `substitutions` key (`FINDINGS.md` says 189); 250 rows, 1 self-referential.
- `baseUnit` has 16 values and `units[].unitId` 23 — `KLE` is a `salesUnit` but never a `baseUnit`; `KRS`, `ZML`, `DOL`, `KOR`, `PNT`, `MDO` occur only inside `units`.

**Confirms:** 17,546 products · 0 deleted · 349 five-digit categories · `allergen` non-empty 41.1% / `nonAllergen` 29.2% / `nutritionalClaim` 43.4% · dirty `vatCode` counts exactly · `allowedLotSize` 0.01 on 96.2% · `variableUnit` true on 632 · 3,068-product empty-`synkkaData` block · deposits unpriceable (576 lines, 0 resolve) · `unitConversions.volume.unit` distribution · `X99` 121/74.
