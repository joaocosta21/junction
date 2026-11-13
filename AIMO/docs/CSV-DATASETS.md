# The two Valio Aimo CSV datasets — reference and join guide

Everything below was computed from the three provided files plus 3 live API calls. No figure here is inferred.
Catalog denominator throughout: **17,546 products** (`valio_aimo_junction26_product_data.json`, all `deleted: false`, 17,546 distinct ids).

Verdict up front:

- **Both CSVs are clean.** Zero malformed rows, zero duplicates, zero nulls, zero empty fields, and **every single productId in both files resolves to a catalog product**.
- **Delivery-reliability missingness is mildly structured** (χ²/df ≈ 7.8 by category, 15.0 by vendor) — not random, but there is no clean rule. It behaves like "whichever SKUs happened to accumulate enough order history".
- **Carbon missingness is almost entirely explained by one thing: food vs. non-food.** Carbon coverage is **81.2% across food categories and 0.4% across non-food** (tableware, napkins, cleaning chemicals, kitchen equipment, office supplies). This is the key insight and it changes the ranking design.
- **The "category average" claim is substantially true but not exactly true.** 190 of 279 categories hold exactly one value; 97.7% of covered products sit on their category's modal value. It is *not* a clean category lookup, because 86 of the 177 distinct values are shared across several categories — the real key is a coarser food-type taxonomy that is not in the dataset.

---

## 1. `valio_aimo_junction26_delivery_reliability.csv`

| Property | Value |
|---|---|
| Header (exact) | `productId,deliveryReliability` |
| Data rows | 4,425 |
| File encoding | UTF-8, no BOM, LF, `,` delimiter, no quoting |
| `productId` dtype | **string of exactly 6 ASCII digits** — 4,425/4,425 |
| `deliveryReliability` dtype | float |
| Duplicate productIds | **0** (4,425 distinct) |
| Malformed rows | **0** |
| Null / empty values | **0** |
| productIds not in catalog | **0** |
| Catalog coverage | **4,425 / 17,546 = 25.2%** |

### Value distribution

| Statistic | Value |
|---|---|
| min | 0.0 |
| max | 1.0 |
| mean | 0.9719 |
| median | 1.0 |
| distinct values | 243 |

Precision: 218 of the 243 distinct values carry 3 decimals, 18 carry 2, 7 carry 1. Consistent with a ratio of fulfilled to ordered lines, rounded to 3 dp.

Histogram (0.1 buckets):

| Bucket | n |
|---|---|
| 0.0–0.1 | 13 |
| 0.1–0.2 | 0 |
| 0.2–0.3 | 7 |
| 0.3–0.4 | 7 |
| 0.4–0.5 | 6 |
| 0.5–0.6 | 31 |
| 0.6–0.7 | 30 |
| 0.7–0.8 | 56 |
| 0.8–0.9 | 141 |
| 0.9–1.0 | 4,134 |

Thresholds:

| Condition | n | % of scored |
|---|---|---|
| `== 1.0` | 2,490 | 56.3% |
| `>= 0.99` | 3,192 | 72.1% |
| `< 0.95` | 564 | 12.7% |
| `< 0.90` | 291 | 6.6% |
| `< 0.75` | 115 | 2.6% |
| `< 0.50` | 33 | 0.7% |
| `< 0.25` | 13 | 0.3% |
| `== 0.0` | 12 | 0.3% |

**The distribution is extremely top-heavy.** More than half the scored products are at a perfect 1.0 and 72% are at 0.99 or better. A naive linear 0→1 normalisation therefore produces almost no discrimination: the whole interesting signal lives in the bottom 6.6% of the scored set, which is 1.7% of the catalog.

### The twelve products at exactly 0.0

| id | category | vendor | name (fi, truncated) |
|---|---|---|---|
| 460873 | 64003 | FREDMAN OPERATIONS OY | Fredman kakkupaperilajitelma suorakaide |
| 462574 | 63130 | OY ORTHEX FINLAND AB | ORTHEX 250X80MM KIRKAS MIKROKUPU |
| 469141 | 21150 | RAVINTORAISIO OY KUIVA | 6 x Elovena 10X30g voimakaura välipalakeksi |
| 469628 | 17210 | VELJEKSET MATTILA OY | Mattila Bros. Smokehouse Ny deli pastrami |
| 469677 | 20033 | AIRAM ELECTRIC OY AB | AIRAM 3L TERÄSPUMPPUTERMOS |
| 471283 | 41760 | EESTI PAGAR AS | Eesti Pagar Vehnäpatonki 40 x 140g |
| 472118 | 63235 | DUNI OY, PROFESSIONAL | DUNI Bio Dunisoft®-lautasliina 40 x 40 cm |
| 473939 | 21461 | MIDSONA FINLAND OY | 2x URTEKRAM Luomu Kivetön Aurinkokuivattu |
| 474010 | 41760 | OY ROLLFOODS AB PAKASTE | Rollfoods Pitaleipä ovaali 115 g x 3 kpl |
| 474111 | 21594 | PRESCOTT OY | 5x Monarch Kikherne 3/1,8kg pussi |
| 476973 | 22705 | OY HARTWALL AB | 24 x Hartwall Novelle Lähdevesi 0,5 l |
| 477051 | 21400 | VALIO OY TUORE | Valio glögi tumma 1 l kausituote |

Note 477051 — "kausituote" (seasonal product). Several of these read like discontinued or seasonal SKUs rather than genuinely unreliable supply.

### What 0.0 means in practice — tested against the live API

`POST /api/availability` and `POST /api/price`, `requestedDate` 2026-11-16, three low-reliability ids:

| id | DR | logisticModel | scheduleLines | availableAmount | priced? |
|---|---|---|---|---|---|
| 469628 | **0.0** | Terminal | 1 line | **999999.0** (unknown/unlimited) | yes, €32.87/KG |
| 476973 | **0.0** | Stock | 1 line | **416666666.0** | yes, €18.22 (€1.52/L) |
| 466305 | **0.01** | *(key absent)* | **`[]` — empty** | — | yes, €46.57 |

**A 0.0 delivery reliability does not stop the availability API returning the product as fully available.** Two of the three worst products in the dataset report themselves available in unlimited quantity on the requested date. The two signals are independent: `deliveryReliability` is *historical* fulfilment, `availability` is a *forward* promise, and the forward promise is blind to the history.

> Incidental finding, not in `FINDINGS.md`: **`416666666.0` is a fourth undocumented `availableAmount` sentinel**, alongside the known `999999`, `9999999999.0` and `666666666.0`. Any `if amount == 999999` guard remains wrong.

But the correlation is real in aggregate. A single 80-id availability call comparing the 40 lowest-DR products against 40 products at DR 1.0:

| Group | n | empty `scheduleLines` (undeliverable) | all-zero `availableAmount` | combined unavailable |
|---|---|---|---|---|
| DR < 0.75 | 40 | **9 (22.5%)** | 3 | **30.0%** |
| DR == 1.0 | 40 | **0 (0.0%)** | 1 | **2.5%** |

Also: the low-DR group is 15/40 Terminal and 16/40 Stock; the DR=1.0 group is 35/40 Stock. **Low delivery reliability predicts both undeliverability and Terminal logistics.** Against the ~14% catalog-wide undeliverable baseline in `FINDINGS.md`, DR < 0.75 roughly doubles the risk and DR == 1.0 roughly eliminates it. Caveat: the DR=1.0 sample is the first 40 by id order, not a random draw, so treat the exact rates as indicative.

### Do low values cluster?

By vendor, among vendors with ≥20 scored products, share scoring below 0.9:

| Vendor | low / scored | rate |
|---|---|---|
| PNM CHIPSTERS OY PAKASTE | 7/21 | 33.3% |
| OY ESSITY FINLAND AB | 20/79 | 25.3% |
| FEELIA OY | 6/32 | 18.8% |
| DUNI OY, PROFESSIONAL | 48/301 | 15.9% |
| PNM CHIPSTERS OY TEOLLINEN | 5/33 | 15.2% |
| NIC-FINLAND OY | 3/20 | 15.0% |
| VALIO OY PAKASTE | 3/21 | 14.3% |
| DIVERSEY SUOMI OY | 18/130 | 13.8% |
| PRESCOTT OY | 11/87 | 12.6% |
| RAVINTORAISIO OY KUIVA | 3/26 | 11.5% |

By category, among categories with ≥15 scored products:

| Category | low / scored | rate |
|---|---|---|
| 18720 | 13/15 | **86.7%** |
| 18701 | 7/15 | 46.7% |
| 63210 | 6/15 | 40.0% |
| 64010 | 5/17 | 29.4% |
| 63120 | 18/65 | 27.7% |
| 10632 | 4/15 | 26.7% |
| 63241 | 5/20 | 25.0% |
| 63231 | 7/29 | 24.1% |
| 17306 | 6/26 | 23.1% |
| 52209 | 5/22 | 22.7% |

**Yes, it clusters, and the clustering is mostly non-food.** DUNI (napkins/tableware), Essity (hygiene paper), Diversey (cleaning chemicals) are three of the top four vendors by low-reliability count, and five of the ten worst categories are `63xxx`/`64xxx` (disposables and cleaning). Category 18720 is the single most extreme pocket in the dataset: 13 of 15 scored products below 0.9. Note the inversion though — PNM Chipsters *Pakaste* (frozen) and Valio *Pakaste* also appear, so frozen-chain products are a second, smaller cluster.

---

## 2. `valio_aimo_junction26_carbon_footprint.csv`

| Property | Value |
|---|---|
| Header (exact) | `productId,AVG kg CO2-eq/kg` |
| Data rows | 11,033 |
| File encoding | UTF-8, no BOM, LF, `,` delimiter, no quoting |
| `productId` dtype | **string of exactly 6 ASCII digits** — 11,033/11,033 |
| `AVG kg CO2-eq/kg` dtype | float |
| Duplicate productIds | **0** (11,033 distinct) |
| Malformed rows | **0** |
| Null / empty values | **0** |
| productIds not in catalog | **0** |
| Catalog coverage | **11,033 / 17,546 = 62.9%** |

Note the header contains a space and a slash. It is not a safe Python identifier — rename it on load.

### Value distribution

| Statistic | Value |
|---|---|
| min | 0.13 |
| max | 30.46 |
| mean | 3.6141 |
| median | 2.11 |
| distinct values | **177** |

Percentiles: p1 0.17 · p5 0.38 · p25 1.16 · p50 2.11 · p75 4.98 · p95 10.09 · p99 26.20.

Histogram:

| kg CO2-eq/kg | n |
|---|---|
| 0.0–0.5 | 824 |
| 0.5–1 | 1,337 |
| 1–2 | 3,178 |
| 2–3 | 1,905 |
| 3–5 | 1,279 |
| 5–10 | 1,902 |
| 10–20 | 303 |
| 20–50 | 305 |

Heavily right-skewed with a long tail (red meat and hard cheese at the top end). **Normalise on log or rank, not linear** — a single 30.46 product otherwise compresses everything below 5 into the same visual band.

Only 177 distinct values over 11,033 products — a mean of 62 products per value. The ten most common values alone cover 3,131 products:

| Value | n products | n categories |
|---|---|---|
| 1.44 | 482 | 5 |
| 2.11 | 377 | — |
| 4.975 | 376 | — |
| 2.19 | 348 | 6 |
| 1.215 | 313 | — |
| 1.93 | 274 | 7 |
| 0.79 | 232 | **47** |
| 5.21 | 214 | 8 |
| 26.195 | 211 | — |
| 5.085 | 204 | — |

### 3. Is it a category average? — the test

Grouping the 11,033 covered products by catalog `category`:

| Result | Count |
|---|---|
| Categories holding carbon data | **279** |
| …with **exactly one** distinct value | **190 (68.1%)** |
| …with **more than one** | **89 (31.9%)** |

Distinct-values-per-category histogram: 1 → 190 · 2 → 63 · 3 → 20 · 4 → 5 · 5 → 1. **No category holds more than five distinct values.**

Covered products sitting in a single-value category: 5,430 / 11,033 (49.2%).
Covered products sitting on their own category's **modal** value: **10,782 / 11,033 (97.7%)**.
Categories where the modal value covers ≥90% of products: **256 / 279**.

So the multi-value categories are overwhelmingly *one dominant value plus a handful of outliers*, not genuine within-category variance. Example — category 41705, 112 covered products, 5 values:

| Value | n | What it is |
|---|---|---|
| 15.79 | **105** | dominant: Finnish meatballs / meat patties (Lagerblad, Saarioinen) |
| 4.46 | 3 | fish/meat-pie mix |
| 3.48 | 1 | Findus pyttipannu |
| 2.195 | 2 | vegan burger patties |
| 1.73 | 1 | Hälsans Kök Sensational Burger (plant-based) |

### What distinguishes the outliers

Within the 89 multi-value categories:

| Grouping | groups | single-valued | share |
|---|---|---|---|
| (category, vendor) | 924 | 811 | **87.8%** |
| (category, brand) | 1,175 | 1,064 | **90.6%** |

Vendor and brand both "explain" the splits, but that is mostly an artefact — a vendor typically sells only one product sub-type inside a category, so vendor is a proxy. Reading the names makes the real driver obvious: **the splits are by food sub-type, specifically plant-based vs. animal protein.** In 41705 the 1.73 and 2.195 rows are the vegan patties and the 15.79 row is the meat; in 41723 (fish/vegetarian frozen, 4 values) the vegan black-bean burger gets 2.195, the fish products 4.46 and the beef timbales 15.79. Country of origin does **not** explain the splits (the 15.79 group in 41705 is 85 `fi` + 7 `se`; the 1.73 outlier is `cz` but so are plenty of 15.79 products elsewhere).

The decisive evidence against a per-category lookup runs the other way:

| Test | Result |
|---|---|
| Distinct carbon values | 177 |
| Values appearing in **more than one** category | **86 / 177 (48.6%)** |
| Value → n-categories histogram | 1 → 91 · 2 → 41 · 3 → 22 · 4 → 7 · 5 → 7 · 6 → 5 · 7 → 2 · 8 → 1 |
| Most-shared value | **0.79 spans 47 categories** (232 products) |

Value precision corroborates averaging: of the 177 distinct values, 95 carry 2 decimals, 44 carry 3, and 12 carry 1 — and the 3-decimal ones end in `5` (`4.975`, `1.215`, `26.195`, `2.195`, `5.085`), i.e. exact midpoints of two 2-dp numbers. 26 further values carry 15–17 decimals, which is float representation error from that same averaging (`0.14500000000000002`, `5.425000000000001`).

**Verdict.** The portal's claim is directionally honest and the numbers are genuinely coarse — 177 values for 11,033 products, 97.7% of them on their category's modal value, several values that are plainly the mean of two others. But it is **not** a clean `category → value` lookup:

1. 89 categories (32%) carry more than one value, so the mapping is not a function of `category`.
2. 48.6% of values span multiple categories, so `category` is not the key either — the averages are computed over a **coarser, external food-type taxonomy** (roughly "beef", "cheese", "root vegetable", "syrup") that is not present in the dataset and cannot be reconstructed from it.
3. Consequence for the build: **treat the value as a per-product attribute you look up by `productId`, and never impute a missing one from its category sibling.** Imputing would be wrong for the 32% of categories that split, and the splits are exactly the interesting cases — plant-based alternatives, which is where a sustainability feature earns its keep. Also never present the figure as a measurement of *this* product; it is a class average with no per-product precision.

---

## 4. Coverage — and whether missingness is structured

### Headline (verified, matches `FINDINGS.md`)

| Segment | n | % of 17,546 |
|---|---|---|
| Delivery reliability present | 4,425 | **25.2%** |
| Carbon footprint present | 11,033 | **62.9%** |
| **Both present** | **3,123** | **17.8%** |
| Carbon only | 7,910 | 45.1% |
| Delivery only | 1,302 | 7.4% |
| **Neither** | **5,211** | **29.7%** |

### Missingness is structured — and the structure is food vs. non-food

Chi-square of observed vs. binomial-expected coverage counts, over groups with ≥20 products (ratio 1.0 would mean coverage is assigned at random):

| Axis | Grouping | χ² | df | **χ²/df** |
|---|---|---|---|---|
| Delivery reliability | category | 1,832 | 235 | **7.80** |
| Delivery reliability | vendor | 2,854 | 190 | **15.02** |
| Carbon footprint | category | 8,877 | 235 | **37.78** |
| Carbon footprint | vendor | 8,241 | 190 | **43.37** |

Both are structured, carbon five times more so than delivery. The per-category coverage rate spread shows the same thing:

| Axis | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| Delivery reliability | 0.00 | 0.15 | 0.26 | 0.37 | 0.83 |
| Carbon footprint | 0.00 | 0.56 | 0.81 | 0.89 | **1.00** |

Delivery reliability has **no category at 100%** and 22 categories (n≥5) at 0% — it is dispersed around 25% everywhere, with a long tail of pockets. Carbon is sharply bimodal: 35 categories at 100% and 63 at 0%.

Cross-tab by 2-digit category prefix, which separates the catalog cleanly:

| Prefix | n | DR coverage | **CF coverage** | What it is |
|---|---|---|---|---|
| 41xx | 3,262 | 26.1% | 77.6% | frozen / prepared |
| 21xx | 3,219 | 27.6% | 80.2% | dry groceries |
| 17xx | 2,237 | 32.2% | 83.0% | fresh produce / deli |
| 22xx | 1,902 | 25.8% | 84.0% | drinks |
| **63xx** | 1,817 | 32.6% | **0.3%** | **cleaning, napkins, tableware** |
| 10xx | 1,524 | 25.7% | 85.1% | dairy |
| **64xx** | 1,039 | 16.0% | **0.8%** | **packaging, candles, bags** |
| **20xx** | 889 | 7.1% | **0.1%** | **kitchen equipment, utensils, glassware** |
| 52xx | 628 | 21.7% | 74.5% | confectionery |
| 18xx | 608 | 15.0% | 90.5% | bakery |
| **90xx** | 224 | 3.6% | **0.0%** | **office supplies** |
| 11xx | 81 | 3.7% | 85.2% | dairy ingredients |
| 85xx | 59 | 13.6% | 86.4% | — |

Splitting the catalog on that one boundary (`63/64/20/90` = non-food):

| Segment | n | % catalog | DR | **CF** | Both | Neither |
|---|---|---|---|---|---|---|
| **Food** | 13,577 | 77.4% | 26.5% | **81.2%** | **23.0%** | 15.4% |
| **Non-food** | 3,969 | 22.6% | 20.9% | **0.4%** | **0.0%** | **78.7%** |

**This is the single most important number in this document.** Carbon coverage is not 62.9% with random gaps — it is **81.2% on food and essentially zero on non-food**. 36 vendors with ≥20 products have under 5% carbon coverage, and reading their catalogues confirms it: DUNI (817 products, napkins and plastic trays), Essity/Tork (245, toilet paper), Wulff (232, office supplies), Huhtamaki (190, foodservice packaging), Diversey and Kiilto (343 combined, cleaning chemicals), Sambonet/Bormioli/Tognana (262, crockery and glassware). 57 categories with ≥10 products have zero carbon data, covering 3,165 products. Non-food has **zero** products with both axes present.

The unit explains it: the figure is **kg CO2-eq per kg of product**, which is a food-LCA unit. It is meaningless for a chef's knife or a bottle of oven cleaner, and the dataset correctly declines to invent one.

### Other cross-tabs

`variableUnit` (sold by weight):

| variableUnit | n | DR | CF |
|---|---|---|---|
| `false` | 13,846 | 24.9% | 65.0% |
| `null` (field absent) | 3,068 | 27.7% | 48.2% |
| `true` | 632 | 21.0% | **87.7%** |

GTIN presence — identical split, because `gtin` and `variableUnit` go missing together (the 3,068 non-GTIN products of `FINDINGS.md` #12):

| has `gtin` | n | DR | CF |
|---|---|---|---|
| `false` | 3,068 | 27.7% | 48.2% |
| `true` | 14,478 | 24.7% | 66.0% |

`synkkaData` sparseness. Note the `FINDINGS.md` characterisation of "essentially empty `synkkaData`" needs a correction: **no product has a completely empty `synkkaData`** — the minimum is 2 populated keys. The real distribution of populated keys is bimodal: a cluster at 2–4 keys (3,015 products) and a cluster at 12–23 (14,500). Using ≤3 keys as the sparse test:

| synkkaData sparse (≤3 keys) | n | DR | CF |
|---|---|---|---|
| `false` | 15,164 | 25.3% | 66.5% |
| `true` | 2,382 | 24.9% | 40.0% |

`temperatureCondition`:

| temp | n | DR | CF |
|---|---|---|---|
| null | 61 | 14.8% | 19.7% |
| 1 | 240 | 20.8% | 95.4% |
| 2 | 324 | 41.4% | 85.2% |
| 3 | 1,673 | 23.3% | 77.9% |
| 4 | 1,803 | 26.0% | 88.0% |
| 5 | 221 | **61.5%** | 95.0% |
| 6 | 10 | 30.0% | 90.0% |
| 7 | 3,152 | 26.4% | 77.1% |
| 8 | 10,053 | 23.9% | **49.4%** |
| 9 | 9 | 0.0% | 100.0% |

Condition 8 (10,053 products — the ambient-looking bucket that `FINDINGS.md` warns against reading literally) drags carbon coverage down because it is where all the non-food sits.

`countryOfOrigin` (top 12):

| coo | n | DR | CF |
|---|---|---|---|
| fi | 7,849 | 22.7% | 70.7% |
| de | 1,029 | 32.7% | 39.4% |
| it | 977 | 27.6% | 46.0% |
| se | 874 | 23.5% | 67.6% |
| **cn** | 741 | 23.6% | **18.4%** |
| nl | 659 | 30.3% | 54.8% |
| fr | 599 | 26.2% | 64.4% |
| pl | 431 | 22.5% | 52.0% |
| es | 404 | 35.9% | 74.8% |
| be | 383 | 30.8% | 66.3% |
| dk | 379 | 30.6% | 66.8% |
| gb | 289 | 27.3% | 51.2% |

China at 18.4% carbon coverage is not a sourcing story, it is the same food/non-food story — imported tableware and utensils.

`salesUnit`:

| salesUnit | n | DR | CF |
|---|---|---|---|
| KI | 8,005 | 19.6% | 61.0% |
| ST | 5,607 | 28.1% | 59.4% |
| KG | 1,068 | 31.2% | **90.7%** |
| PAK | 880 | 25.0% | **27.3%** |
| BAG | 697 | 38.6% | 81.9% |
| RAS | 328 | 32.9% | 79.0% |
| PRK | 320 | 38.4% | **94.7%** |
| BOT | 310 | **45.5%** | 79.7% |
| SK | 120 | 33.3% | 51.7% |
| CS | 72 | 26.4% | 69.4% |

`KG` and `PRK` (jars) are near-fully carbon-covered; `PAK` at 27% is the disposables/packaging unit.

### `logisticModel`

**Not obtainable from the static catalog.** It only appears in the `/api/availability` response, and `FINDINGS.md` records that it is *absent as a key* on the ~14% of products with empty `scheduleLines`. Cross-tabulating coverage against it at catalog scale would need ~220 API calls, which the portal's rate-limit guidance explicitly discourages. The 80-id probe in §1 is the partial answer: the low-DR group skews Terminal (15/40) while the DR=1.0 group skews Stock (35/40).

### Summary answer

**Missingness is structured, but the two axes are structured differently, and this distinction drives the ranking design:**

- **Carbon** is *missing-by-design*. The gap is a category boundary (food vs. non-food), not a data-quality gap. There is nothing to recover, and no amount of extra work will produce a carbon figure for a napkin. 81.2% coverage within its applicable domain is good coverage.
- **Delivery reliability** is *missing-at-random-ish*. χ²/df of 7.8–15 says the gaps are not uniform, but there is no clean boundary: coverage sits between 15% and 37% for the middle half of categories, no category reaches 100%, and the low-coverage pockets (20xx kitchen equipment at 7.1%, 90xx office supplies at 3.6%) are a weak tendency rather than a rule. The best available explanation is order-history volume — low-turnover SKUs have too few historical lines to score.

**That asymmetry answers the ranking question directly.** For carbon, "missing" on a non-food product means *not applicable* and the axis should be dropped from the comparison entirely rather than scored. For delivery reliability, "missing" means *unknown* — and given that the scored distribution is 56% perfect and only 6.6% below 0.9, an unknown product is probably fine but cannot be certified, so it must never out-rank a product with a verified good score.

---

## 5. Ranking design recommendation

Three axes: price, delivery reliability, carbon. Only **17.8% of the catalog** carries all three, and **23.0% within food**. The design has to be honest about that rather than hide it.

### Normalise each axis within the candidate set, not globally

All three axes are normalised across the shortlist the user is actually choosing between (typically 5–50 products from one category), not against the whole catalog. A global normalisation makes every candidate in a category look identical.

**Price** — always present (the `/price` API covers everything, including the undeliverable products, as §1 confirms). Normalise on **comparison price** (€/kg or €/L), never the sales-unit price, otherwise a crate beats a carton on arithmetic alone. Use the `catalogPrice / comparisonPrice` pack-size trick from `FINDINGS.md` when `comparisonPrice` is absent (22.5% of products), and carry the resulting confidence flag into the display. Linear min-max over the candidate set:

```
score_price = (max_p - p) / (max_p - min_p)      # 1.0 = cheapest
```

**Delivery reliability** — present on 25.2%. A linear 0→1 map wastes the whole scale: 72% of scored products sit above 0.99. Map the decision-relevant band instead:

```
score_delivery = clamp((dr - 0.85) / 0.15, 0, 1)   # 0.85 -> 0, 1.0 -> 1
```

This gives real separation across the 0.85–1.0 range where 93% of the data lives, and floors everything below 0.85 at zero — which is correct, since below 0.85 the §1 probe says you are looking at a materially elevated chance of the product being undeliverable outright.

**Carbon** — present on 62.9% overall, 81.2% of food. The distribution runs 0.13–30.46 with p75 at 4.98, so linear normalisation is dominated by the tail. Use **rank-within-candidate-set** or log:

```
score_carbon = (log(max_c) - log(c)) / (log(max_c) - log(min_c))
```

Rank is preferable in a demo because it is self-evidently fair and needs no explanation.

### Handling missing values — absence must never read as good

Three rules, in order:

**1. Never impute.** No category averages for carbon (§3: the mapping is not a function of category, and the splits are exactly the plant-based-vs-meat cases that matter). No default reliability. An imputed value is indistinguishable from a measured one once it is in the pipeline.

**2. Renormalise the weights per product — do not substitute a value.** For each candidate, compute the weighted score over only the axes it actually has, with the weights rescaled to sum to 1:

```python
def rank_score(scores, weights):
    """scores: {axis: float|None}; weights: {axis: float}."""
    present = {a: w for a, w in weights.items() if scores.get(a) is not None}
    if not present:
        return None, 0.0
    total = sum(present.values())
    value = sum(scores[a] * (w / total) for a, w in present.items())
    return value, total          # total = fraction of intended evidence
```

This is the only neutral treatment. Substituting 0 penalises missing data (a product with no carbon figure loses to a worse-carbon product that happens to be measured — dishonest). Substituting 1 or the mean rewards it (absence reads as good — the failure mode the brief warns about). Renormalising says "I judged this product on the evidence available", which is the truth.

**3. Make evidence coverage a visible tie-breaker, never a hidden score component.** `total` from above is the fraction of intended evidence the product had. Sort primarily on the score, then break ties on higher coverage, and **display coverage on every result**. Do not fold it into the score — that silently re-penalises missing data and reintroduces problem 2.

**4. Drop non-applicable axes rather than scoring them as missing.** When the candidate set is non-food (category prefix `63`/`64`/`20`/`90`), carbon is not missing, it is not applicable: 0.4% coverage, 0 products with both axes. Drop the axis from the UI for that query entirely and rank on price + delivery. Showing an empty carbon column on a napkin query looks like a broken feature; saying "carbon footprint is not published for non-food products" looks like a system that knows what it is doing.

### Disclose per result

Each result row should carry, inline:

- the comparison price with its unit, and whether it came from `comparisonPrice` (exact) or the pack-size ratio (approximate, ~0.3% error)
- delivery reliability as the raw figure plus its meaning (`0.94 — 94% of historical order lines fulfilled`), or **`no delivery history`** — never a blank cell and never a zero
- carbon as the raw figure, **explicitly labelled a category average, not a product measurement**, or `not published`, or `not applicable (non-food)`
- an evidence badge: **`3/3 axes`**, `2/3`, `1/3`

And, from §1, one honest caveat worth surfacing because it is a trust win rather than a gap: **delivery reliability is historical and the availability API does not know about it.** A product at 0.0 reliability will still tell you it has 999,999 units available on Monday. The ranking is the only place that information meets.

### Coverage figures a demo should display

Put these on screen rather than in the speaker notes:

| Metric | Figure |
|---|---|
| Catalog size | 17,546 products |
| Price | **100%** (API, all products) |
| Delivery reliability | **25.2%** (4,425) |
| Carbon footprint | **62.9%** (11,033) — **81.2%** of food products |
| **All three axes** | **17.8%** (3,123) — **23.0%** of food products |
| No optional axis at all | 29.7% (5,211) |
| Carbon on non-food | **0.4%** — axis not applicable |
| Products scoring below 0.9 reliability | 291 (1.7% of catalog, 6.6% of scored) |

The honest headline: **a full three-axis comparison is possible on about 1 in 6 products, 1 in 4 within food.** Say it out loud. The system is more credible for declaring the limit than for hiding it behind imputed numbers, and the §1 probe gives you the payoff line — the 1.7% of the catalog that *is* flagged unreliable is genuinely the risky tail, and nothing else in the dataset will tell you about it.

---

## 6. Join recipes

### ⚠ productIds are zero-padded strings — verified

Both CSVs: **100% of productIds are exactly 6 ASCII digits**, and the catalog `id` field is declared `"type": "string"` in the provided schema.

Verified empirically, so you can make an informed decision:

| Check | Result |
|---|---|
| All ids exactly 6 chars | **yes** — 4,425/4,425 and 11,033/11,033 |
| All ids pure digits | **yes** |
| Ids with a **leading zero** | **0 in both files** |
| Collisions after `int()` round-trip | **0 in both files** |

So in *this* dataset an int cast happens to be lossless — the observed id range starts at 460000. **Keep them as strings anyway.** The schema says string, the live API accepts and returns strings (`"productId": "469628"`), and any id that ever starts with a 0 would silently fail to join after an int round-trip. A numeric cast is a latent bug that costs nothing to avoid. The loaders below assert the invariant rather than trusting it.

### Pure-Python (no pandas available in this environment)

```python
import csv
import json
from pathlib import Path

AIMO = Path("/Users/joaocosta/Pessoal/junction/AIMO")
ID_LENGTH = 6


def load_metric_csv(path: Path, value_column: str) -> dict[str, float]:
    """Load a {productId: value} map, keeping ids as zero-padded strings."""
    result: dict[str, float] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["productId", value_column]:
            raise ValueError(f"unexpected header in {path.name}: {reader.fieldnames}")
        for line_no, row in enumerate(reader, start=2):
            product_id = (row.get("productId") or "").strip()
            raw_value = (row.get(value_column) or "").strip()
            if not product_id or not raw_value:
                raise ValueError(f"{path.name}:{line_no} empty field")
            if len(product_id) != ID_LENGTH or not product_id.isdigit():
                raise ValueError(f"{path.name}:{line_no} bad productId {product_id!r}")
            if product_id in result:
                raise ValueError(f"{path.name}:{line_no} duplicate productId {product_id}")
            result[product_id] = float(raw_value)
    return result


delivery_reliability = load_metric_csv(
    AIMO / "valio_aimo_junction26_delivery_reliability.csv", "deliveryReliability"
)
carbon_footprint = load_metric_csv(
    AIMO / "valio_aimo_junction26_carbon_footprint.csv", "AVG kg CO2-eq/kg"
)
# 4425 11033
print(len(delivery_reliability), len(carbon_footprint))
```

Attach to a catalog index. The 87MB load takes ~15s and ~2GB RSS, so build a slim projection once and reuse it (`FINDINGS.md` #13):

```python
NON_FOOD_PREFIXES = frozenset({"63", "64", "20", "90"})


def build_index(catalog_path: Path) -> dict[str, dict]:
    """productId -> slim product record, with both CSV metrics attached."""
    products = json.loads(catalog_path.read_text(encoding="utf-8"))
    index: dict[str, dict] = {}
    for product in products:
        product_id = product["id"]
        if not isinstance(product_id, str):
            raise TypeError(f"catalog id is {type(product_id).__name__}, expected str")
        category = product.get("category") or ""
        index[product_id] = {
            "id": product_id,
            "category": category,
            "vendorName": product.get("vendorName"),
            "nameFi": _finnish_name(product),
            "deliveryReliability": delivery_reliability.get(product_id),
            "carbonFootprint": carbon_footprint.get(product_id),
            # carbon is a food-LCA unit; absent on non-food BY DESIGN, not missing
            "carbonApplicable": category[:2] not in NON_FOOD_PREFIXES,
        }
    return index


def _finnish_name(product: dict) -> str:
    names = (product.get("synkkaData") or {}).get("names") or []
    for name in names:
        if isinstance(name, dict) and name.get("language") == "fi":
            return name.get("value") or ""
    return ""


catalog = build_index(AIMO / "valio_aimo_junction26_product_data.json")

# Both CSVs are fully resolvable against the catalog - assert it, don't assume it.
orphans = [pid for pid in (delivery_reliability | carbon_footprint) if pid not in catalog]
assert not orphans, f"{len(orphans)} CSV productIds missing from catalog: {orphans[:5]}"
```

### If pandas is available

```python
import pandas as pd

DTYPES = {"productId": "string"}   # never int64 - zero-padding is load-bearing

delivery = pd.read_csv(
    AIMO / "valio_aimo_junction26_delivery_reliability.csv", dtype=DTYPES
)
carbon = pd.read_csv(
    AIMO / "valio_aimo_junction26_carbon_footprint.csv", dtype=DTYPES
).rename(columns={"AVG kg CO2-eq/kg": "carbonFootprint"})

for name, frame in (("delivery", delivery), ("carbon", carbon)):
    bad = frame.loc[~frame["productId"].str.fullmatch(r"\d{6}"), "productId"]
    if len(bad):
        raise ValueError(f"{name}: {len(bad)} malformed productIds, e.g. {bad.head(3).tolist()}")
    if frame["productId"].duplicated().any():
        raise ValueError(f"{name}: duplicate productIds")

products = pd.DataFrame(catalog.values())          # or project the JSON directly
joined = (
    products.astype({"id": "string"})
    .merge(delivery, how="left", left_on="id", right_on="productId")
    .merge(carbon, how="left", left_on="id", right_on="productId", suffixes=("_dr", "_cf"))
    .drop(columns=["productId_dr", "productId_cf"])
)
```

**Always `how="left"` from the catalog.** An inner join silently collapses the catalog to the 17.8% with both axes, which is precisely the bias this document exists to prevent.

### Reproducing the headline figures

```python
total = len(catalog)
has_dr = sum(1 for p in catalog.values() if p["deliveryReliability"] is not None)
has_cf = sum(1 for p in catalog.values() if p["carbonFootprint"] is not None)
has_both = sum(
    1 for p in catalog.values()
    if p["deliveryReliability"] is not None and p["carbonFootprint"] is not None
)
food = [p for p in catalog.values() if p["carbonApplicable"]]
food_cf = sum(1 for p in food if p["carbonFootprint"] is not None)

print(f"catalog           {total}")
print(f"delivery          {has_dr} ({100 * has_dr / total:.1f}%)")   # 4425 (25.2%)
print(f"carbon            {has_cf} ({100 * has_cf / total:.1f}%)")   # 11033 (62.9%)
print(f"both              {has_both} ({100 * has_both / total:.1f}%)")  # 3123 (17.8%)
print(f"carbon on food    {food_cf}/{len(food)} ({100 * food_cf / len(food):.1f}%)")  # 11018/13577 (81.2%)
```

---

## Appendix — corrections and additions to `FINDINGS.md`

| `FINDINGS.md` claim | Status |
|---|---|
| `deliveryReliability` 25.2%, 4,425 rows, 243 distinct, 0.0–1.0 | **Confirmed exactly.** |
| Carbon 62.9%, 11,033 rows, 177 distinct | **Confirmed exactly.** |
| Both present 17.8% (3,123) | **Confirmed exactly.** |
| "89 categories hold >1 value, so not a clean lookup" | **Confirmed** (190 single / 89 multi of 279). Extended: the stronger argument is that 86 of 177 values span multiple categories, so `category` is not the key at all. |
| #12: "3,068 products have essentially empty `synkkaData`" | **Needs qualifying.** The 3,068 figure is right as the count of products missing `gtin`/`vatCode`/`variableUnit`, but no product has an empty `synkkaData` — the minimum populated-key count is 2, and the sparse cluster is 2–4 keys (3,015 products). |
| #4: `availableAmount` sentinels 999999 / 9999999999.0 / 666666666.0 | **Add a fourth: `416666666.0`** (observed on product 476973). |
| ~14% of products not orderable | **Consistent, and now predictable.** DR < 0.75 → 22.5% empty `scheduleLines`; DR == 1.0 → 0%. |
| "Design the three-axis ranking to degrade explicitly (missing ≠ good)" | **Confirmed and sharpened.** Carbon absence on non-food is *not applicable*, not *missing* — drop the axis, don't score it. See §5. |
