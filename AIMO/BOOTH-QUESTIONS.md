# Valio Aimo — project recap, schemas, and mentor questions

Self-contained. Readable cold at the booth.
**Mentors:** Tommi Nurmi-Aro · Ville Takanen · Riku Tapper (technical / data governance) — Hanna Forsström · Pirjo Kaartinen (commercial) — Minni Ruhtinas (online sales).
**If you only get two minutes: Q1, Q3, Q6.**

---

# PART 1 — What the challenge is

Valio Aimo serves 20,000+ professional kitchens, 25,000 products, 700 suppliers. They are planning a digital B2B marketplace. The question they're asking:

> How can a food-service wholesaler let **autonomous purchasing agents** place an order — finding products, comparing offers and getting the right approval — **without exposing real systems, confidential data or the marketplace roadmap?**

**We are not building a marketplace.** We prototype **the interface and operating model** through which an external purchasing agent could interact with Valio Aimo's systems at all, *"built on open, verifiable standards rather than a single platform's black box."*

**Their stated anti-pattern:** *"This is not about replacing today's e-commerce UI with a chatbot."*

### Three core requirements
1. **Product, price & availability lookup** — structured retrieval of what's available and at what price
2. **Request price & availability, then place an order** — a defined inquiry→commitment interaction, **based on fixed prices rather than a negotiated quote**
3. **Permission & human-approval management** — what the agent decides alone vs. what goes to a human

### Judging rubric
| Weight | Criterion |
|---|---|
| **30%** | Working end-to-end demo — full request → lookup → order/approval flow, **not isolated pieces** |
| **20%** | Solving the problem — how precisely the agent matches what the buyer asked, least manual correction |
| **20%** | Autonomy and controls — guardrails quality: what it decides alone, what needs sign-off, how decisions are logged and auditable |
| **15%** | Robustness to exceptions — partial availability, substitutions, delivery constraints beyond the happy path |
| **15%** | Openness + credible production path — open documented standards, visible assumptions, justified choices, next steps |

**Prizes:** €4,000 / €2,000 / €1,000.

### Four "problems we'd love to see tackled"
**Trust protocol** (minimum verification standard for an agent to trust claims on stock/price/origin without manual check) · **Guardrails model** (what needs human sign-off) · **Response logic** (partial availability, good-better-best substitution ranking) · **Audit trail** (human-readable log of decisions, for buyer *and* wholesaler).

---

# PART 2 — What we did before coming to you

We tested the live API and analysed all 17,546 products. Findings that shaped our questions:

| # | What we found | Consequence |
|---|---|---|
| 1 | **No order/quote/basket endpoint exists** (404 verified). Only 6 operations total. | Defining the order contract appears to be our deliverable → **Q1** |
| 2 | **Both APIs ignore `requestedDate`.** Three dates tested → byte-identical responses; `availableDate` frozen at **2026-11-16** | "By Monday" can't be tested as a constraint → **Q2** |
| 3 | **53% of deliverable products (129/244) report a `closingTime` already in the past**, across 12 distinct values, while still claiming 2026-11-16 availability | Respect them → reject most of the catalog. Ignore them → no cut-off logic → **Q3** |
| 4 | **`MAY_CONTAIN` is an undocumented third allergen `unit` value**, and pervasive (AN 1,225 · AY 954 · AM 728 · SA 727) | A filter on the two documented values **silently treats "may contain traces" as safe** → **Q6** |
| 5 | **~59% of the catalog has no allergen statement.** `allergen` non-empty 41.1%, `nonAllergen` 29.2% | Can only *certify* a swap on ~29% → **Q6** |
| 6 | `salesBlock` was **never `true`**. **Three** unavailable states exist: empty `scheduleLines` (~14%); the identical shape for a nonexistent id; and **one line with `availableAmount == 0.0`** while `logisticModel`/`closingTime` are populated (10/244) | Checking only `scheduleLines == []` treats the third as orderable |
| 7 | **Eight sentinels in `availableAmount`** — `999999` (documented) plus `9999999999.0`, `666666666.0`, `3333333333.0`, `1249999999.0`, `999999999.0`, `416666666.0`, `49999999.0`. Real quantities all ≤ ~120 | Detect by magnitude (`>= 1_000_000`), never an allow-list |
| 8 | **Pack size = `catalogPrice.value / comparisonPrice.value`.** Verified: 1.0 for a 1 L carton (ST), 10.015 for a crate of ten, 19.94 for 2×10 L | **Means we never need the undocumented sales-unit code translations.** Missing on 22.5%, rounded to 2 dp |
| 9 | `unitConversions.volume.unit` is often **not** a volume unit: GRM 5,498 · **H87 1,500** (= piece) · KGM 875 · LTR only 762 | Reading `.volume` as litres is wrong more often than right |
| 10 | **632 products are `variableUnit: true`** | Unit count doesn't determine quantity or price → **fixed-price commitment is impossible** |
| 11 | **Deposits unpriceable** — 506 products, 7 `material` codes resolving to **zero** catalog products, no price list | Order totals for bottled goods are incomplete → **Q7** |
| 12 | `allowedLotSize` is 0.01 ("no constraint") on 96.2%; **674 products have real steps incl. 1.5 and 1.8** | Rounding edge case that produces a wrong total on stage |
| 13 | `vatCode` in the file is dirty — 159 literal `"MEDIUM MEDIUM"` | Use `tax.taxRate` from the API |
| 14 | **`customer` provably doesn't affect responses** — six strings, identical output | No customer/authority model exists → **Q9** |
| 15 | Of 250 explicit `substitutions` pairs, **230 (92%) stay inside the same `category`** | Same-category is how Valio models substitutability → **Q5** |
| 16 | `deliveryReliability` **25.2%** · carbon **62.9%** · **both only 17.8%** | Three-axis ranking honest on ~1 in 6 products → **Q10** |

### We verified their canonical example works
> *"I need 1,000 litres of lactose-free milk by Monday"*

4,178 products carry `FREE_FROM_LACTOSE`. Category `10400` (drinking milk) has 91 products, 35 lactose-free; 24 matched. Cheapest: **`464306`** Valio Eila kevytmaitojuoma, **€1.01/L** net (list €1.44, `netPriceFound: true`), `ST` = 1 L, Stock, cut-off 2026-11-15T17:00 → **1,000 units = €1,010.00 ex-VAT**.

⚠️ **And a trap inside their own example:** `464306` is `FREE_FROM_LACTOSE` but its `allergen` classification is `[{"id":"AM","unit":"CONTAINS"}]` — **AM is milk.** Lactose-free is *not* milk-allergen-free. An agent conflating a nutritional claim with an allergen assertion would serve it to a milk-allergic ward.

---

# PART 3 — Schemas

## 3.1 API
Base `https://junction26.valioaimo.fi/api` · header `X-API-Key` · six operations.
Portal docs (`/docs`, `/redoc`, `/openapi.json`) sit at the **root** path behind the portal password, not the API key.

### `POST /price` and `POST /availability` — identical request
```jsonc
{
  "customer": "123",            // string, required. Does NOT affect responses in this challenge
  "requestedDate": "2026-11-16", // date, required. IGNORED by both endpoints (see finding 2)
  "products": ["460013", "460063"] // 1-1000 product codes. >1000 → HTTP 422
}
```

### `POST /price` → response
```jsonc
{
  "customerId": "123", "currency": "EUR", "pricingDate": "2026-11-16T00:00:00+0200",
  "products": [{
    "productId": "464306",
    "quantity": 1.0,                  // always 1.0
    "catalogPrice":    { "value": 1.01, "valueWithTax": 1.15, "validFrom": "...", "validTo": "...", "currency": "EUR" },
    "listPrice":       { /* same shape */ },   // before customer-specific price/discount
    "priceWithTax":    { "value": 1.15, "validFrom": "...", "validTo": "...", "currency": "EUR" },
    "comparisonPrice": { /* same shape */ },   // per comparisonUnit — MISSING on 22.5%
    "comparisonUnit": "L",            // only KG or L
    "tax": { "taxRate": 13.5, "taxValue": 0.14 },  // AUTHORITATIVE, use over file vatCode
    "netPriceFound": true,            // true = customer-specific net price; false = catalog price used
    "error": false                    // true = no price found (also returned for unknown ids)
  }]
}
```

### `POST /availability` → response
```jsonc
{
  "timeNow": "2026-11-13T21:33:37+0200",       // Helsinki time
  "requestedDate": "2026-11-16T00:00:00+0200",  // echo, at midnight
  "products": [{
    "productId": "464306",
    "closingTime": "2026-11-15T17:00:00+0200",  // order cut-off to receive on availableDate
    "salesBlock": false,                         // NEVER observed true — not the "can't buy" signal
    "logisticModel": "Stock",                    // Stock = we hold it | Terminal = supplier warehouse
    "scheduleLines": [{                          // EMPTY = undeliverable on any date (~14%)
      "salesBlock": false,
      "availableAmount": 9999999999.0,           // sentinels: 999999 | 9999999999.0 | 666666666.0
      "availableDate": "2026-11-16",             // may differ from requestedDate
      "salesUnit": "ST"
    }]
  }]
}
```
⚠️ `logisticModel` and `closingTime` **keys are absent entirely** on undeliverable products — use `.get()`.

### ⚠️ The API never returns `null` — it OMITS keys
The spec declares 9 fields as `anyOf [T, null]`, but **across 298 products on both endpoints, zero JSON nulls were observed.** Absent fields are simply missing from the object. Verified empirically.

| Endpoint | Fields that can be ABSENT |
|---|---|
| `/price` → `ProductPrice` | `catalogPrice` · `priceWithTax` · `comparisonPrice` · `comparisonUnit` · `tax` · `listPrice` |
| `/availability` → `ProductAvailability` | `closingTime` · `logisticModel` |
| `/availability` → `ScheduleLine` | `availableDate` |

Always present: `productId`, `quantity`, `netPriceFound`, `error` (price) · `productId`, `salesBlock`, `scheduleLines` (availability) · `salesBlock`, `availableAmount`, `salesUnit` (schedule line).

**`error` and the price objects are perfectly coupled** (verified 298 products):
- `error: false` → `catalogPrice`, `priceWithTax`, `tax`, `listPrice` present on **100%** (296/296)
- `error: true` → the entry has **only 4 keys**: `productId`, `quantity`, `netPriceFound`, `error`

**The only independent axis is `comparisonPrice` + `comparisonUnit`** — absent *together* on 20.8% (62/298) even on perfectly priced products (e.g. `460180`). This is exactly what breaks the pack-size shortcut.
`netPriceFound` is also independent — **true on only 7 of 298 products**, so nearly everything is at catalog price.

→ Use `.get()` chains throughout. `resp["catalogPrice"]["value"]` raises `KeyError`, not a null check.

### ⚠️ `Price.value` vs `PriceWithTax.value` — same name, opposite meaning
`Price.value` is tax-**exclusive** (and carries its own `valueWithTax`). `PriceWithTax.value` is tax-**inclusive** and has **no** `valueWithTax`. A shared deserialiser across both types will silently mix ex-VAT and inc-VAT numbers.

### ⚠️ Datetime format breaks `fromisoformat` on Python ≤3.10
Offsets are serialised **without a colon** (`+0200` / `+0300`). `availableDate` alone is a bare `YYYY-MM-DD`. Open-ended prices use `validTo: "9999-12-31T00:00:00+0200"`.

### ⚠️ Three distinct unavailable states, not two
1. `scheduleLines: []` — undeliverable on any date; `logisticModel` and `closingTime` keys **absent**
2. `scheduleLines: []` — **identical shape returned for a nonexistent product id**
3. **`scheduleLines` with ONE line whose `availableAmount == 0.0` and `availableDate` absent**, while `logisticModel` and `closingTime` ARE populated (10 of 244 lines; e.g. `460660` KI, `465280` PRK)

→ **Checking only `scheduleLines == []` treats state 3 as orderable.** Must also check `availableAmount > 0`.

### ⚠️ Eight sentinel values in `availableAmount` — use a magnitude threshold
`999999` (documented) · `9999999999.0` · `666666666.0` · `3333333333.0` · `1249999999.0` · `999999999.0` · `416666666.0` · `49999999.0`
Real quantities observed were all **≤ ~120**. → Detect with `amount >= 1_000_000`, **never an allow-list.**

### ⚠️ The 422 body echoes the entire rejected input
`detail[].input` contains the whole payload — a 1,001-id over-limit request returns ~9 KB. **Truncate before logging.**

Other confirmed details: `customer` is **strictly typed** (integer `123` is rejected, not coerced). `GET /api/ping` returns `{"status":"ok"}` as `application/json` (undocumented — the spec says `{}`). Download endpoints return **307**, and their `/files/<hash>/<name>` redirect targets need **no API key at all** — unauthenticated capability links. Product JSON is exactly 87,077,467 bytes.

### File downloads (follow redirects)
```bash
curl -L -H "X-API-Key: $KEY" https://junction26.valioaimo.fi/api/products/download
curl -L -H "X-API-Key: $KEY" https://junction26.valioaimo.fi/api/delivery-reliability/download
curl -L -H "X-API-Key: $KEY" https://junction26.valioaimo.fi/api/carbon-footprint/download
```

## 3.2 `valio_aimo_junction26_delivery_reliability.csv`
```csv
productId,deliveryReliability
460001,1.0
460002,1.0
```
**4,425 rows = 25.2% of catalog.** 243 distinct values, 0.0–1.0, where 1 = all orders delivered as ordered. **56.3% sit at exactly 1.0**, 72.1% at ≥0.99, only 6.6% below 0.9, 12 products at 0.0 — so a linear normalisation has almost no discriminating power; map the 0.85–1.0 band instead. Zero malformed rows, zero duplicates, all ids resolve.

## 3.3 `valio_aimo_junction26_carbon_footprint.csv`
```csv
productId,AVG kg CO2-eq/kg
460000,2.315
460001,1.44
```
**11,033 rows = 62.9%.** 177 distinct values, 0.13–30.46, median 2.11. **Category average, not a per-product measurement** — but 89 of 279 categories (31.9%) hold more than one distinct value, and 86 of 177 values span multiple categories, so **it is not a clean category lookup either.** Coverage is **81.2% on food, 0.4% on non-food** — the unit is a food-LCA unit. Zero malformed rows, zero duplicates, all ids resolve.

## 3.4 `valio_aimo_junction26_product_data.json`
JSON **array** of 17,546 objects. 87 MB → ~15 s load, ~2 GB RSS; index once, never load at demo time.

```jsonc
{
  "id": "464306",                  // REQUIRED. Product code — the key for APIs and both CSVs
  "salesUnit": "ST",               // REQUIRED. Technical code, translations NOT provided
  "baseUnit": "ST",                // REQUIRED
  "category": "10400",             // REQUIRED. 5-digit code. NAMES NOT IN DATASET (349 distinct)
  "allowedLotSize": 0.01,          // REQUIRED. Order qty must be a multiple. 0.01 = no constraint (96.2%)
  "deleted": false,                // REQUIRED. 0 deleted products present
  "vendorName": "VALIO OY TUORE",  // REQUIRED. 648 vendors
  "salesUnitGtin": "6408430000487",// 99.1%
  "countryOfOrigin": "fi",         // 99.9%. lowercase ISO 3166-1 alpha-2
  "temperatureCondition": 4,       // integer 1-9, MEANINGS NOT PROVIDED. Does NOT map to logisticModel
  "units": [                       // REQUIRED. Packaging hierarchy
    { "unitId": "ST",  "gtin": "6408430000487", "sizeInBaseUnits": 1.0 },
    { "unitId": "KI",  "gtin": "6408430101009", "sizeInBaseUnits": 20.0 },
    { "unitId": "PAL", "gtin": "6408430101016", "sizeInBaseUnits": 160.0 },
    { "unitId": "KRS", "sizeInBaseUnits": 160.0 }   // gtin optional
  ],
  "deposits": [                    // REQUIRED (often []). 506 products non-empty
    { "material": "<product code>", "quantity": 1.0, "unit": "ST" }
  ],                               // ⚠️ material codes resolve to ZERO catalog products; no price list
  "substitutions": [               // 1.1% (189 products, 250 pairs). DIRECTED — no reverse edges
    { "product": "464306", "substituteProduct": "465039" }
  ],
  "synkkaData": { /* see below */ }// REQUIRED. GS1 Synkka manufacturer data. No product has it empty;
                                   // sparse cluster is 2-4 populated keys (3,015 products)
}
```

### `synkkaData` — manufacturer-supplied, quality varies by product type
```jsonc
{
  "names": [                       // REQUIRED. fi 100% | en 99.99% | sv 91.8%
    { "language": "fi", "value": "Valio Hyvä suomalainen Arki® Eila® kevytmaitojuoma 1 l laktoositon" },
    { "language": "en", "value": "...semi skimmed milk drink 1 l lactose free" }
  ],                               // 81.2% contain a parseable size token
  "brand": "Valio",                // 82.4%
  "gtin": "6408430000487",         // 82.5% — 17.5% have NO consumer GTIN → use `id` as primary key
  "variableUnit": false,           // ⚠️ true on 632 products = sold by variable weight
  "vatCode": "MEDIUM",             // ⚠️ DIRTY (159× "MEDIUM MEDIUM") — use API tax.taxRate instead
  "minTemperature": 2, "maxTemperature": 8,   // 57.9% / 58.5% — better than temperatureCondition
  "classifications": [ /* see below */ ],      // REQUIRED
  "nutritionalContent": [          // 69.8%
    { "id": "ENER-KJO", "value": 188, "unit": "KJO",
      "basisQuantity": 100, "basisQuantityUnit": "MLT",
      "unitPrecision": "APPROXIMATELY", "dailyValueIntakePercent": 2.2, "servingSize": 200 }
  ],
  "unitConversions": [             // 82.5% — weights/dimensions per packaging level
    { "synkkaPackagingType": "BASE_UNIT_OR_EACH",   // | CASE | PALLET
      "grossWeight": {}, "netWeight": {}, "volume": {},  // ⚠️ volume.unit often GRM/H87, not LTR
      "height": {}, "width": {}, "length": {} }
  ],
  "ingredients": [                 // only 21.3%
    { "sequence": 1, "percentage": 97.0,
      "names": [{ "language": "fi", "value": "..." }],
      "origins": [{ "country": "246", "type": "..." }] }
  ],
  "countriesOfOrigin": ["246"],    // numeric ISO 3166-1 (246 = Finland)
  "keyIngredients": [], "marketingTexts": [], "storageInstructions": [],
  "preparationInstructions": [], "usageInstructions": [], "disposalInformations": [],
  "producers": [], "medias": [], "safetyData": [], "fishingReports": [],
  "lastUpdated": "2025-05-20T11:02:36+0300"
}
```

### `synkkaData.classifications` — the important one
Grouped by `name`, each `{ name, type, values: [{ id, synkkaId, unit, value }] }`.

| Group | `type` | Non-empty | Notes |
|---|---|---|---|
| **`allergen`** | ENUM | **41.1%** | `{id: "AM", unit: "CONTAINS"}`. GS1-style 2-letter codes, **not documented**. `unit` ∈ `CONTAINS` / `FREE_FROM` / **`MAY_CONTAIN` (undocumented)** |
| **`nonAllergen`** | ENUM | **29.2%** | Same shape, for free-from assertions |
| **`nutritionalClaim`** | ENUM | 43.4% | Self-describing: `FREE_FROM_LACTOSE` 4,178 · `FREE_FROM_GLUTEN` 3,047 · `VEGAN` 2,959 · `VEGETARIAN` 2,358 · `NO_ADDED_SUGARS` 662 · `HIGH_PROTEIN` 403 · `LOW_LACTOSE` 321. ⚠️ `unit` qualifier is **inconsistent** — key on `id` |
| **`packagingMarkedLabel`** | ENUM | 99.9% | Certificates, self-describing: `GOODS_FROM_FINLAND_BLUE_SWAN` 2,057 · `MADE_IN_FINLAND_FLAG_WITH_KEY` 1,772 · `FINNISH_HEART_SYMBOL` 826 · `EU_ORGANIC_FARMING` 456 · `SVANEN` 362 · `RAINFOREST_ALLIANCE` 234 · `EU_ECO_LABEL` 195 · `MSC` 104 · `FAIR_TRADE_MARK` 92 · `ASC` 51 · `KRAV` 26. ⚠️ **three temperature pseudo-labels are mixed in** (`warmTemperature` 10,057 · `coolTemperature` 4,060 · `freezeTemperature` 3,245) — **filter them out, they are not certificates** |
| `nutritionFact` | DECIMAL | 86.6% | |
| `gda`, `mineral`, `vitamin`, `composition` | DECIMAL | 82.5% | Nutrient ids ENER-KJO, ENER-E14, FAT, FASAT, CHOAVL, SUGAR-, FIBTG, PRO-, SALTEQ |
| `packaging` | ENUM | 99.9% | |

**Observed allergen codes** (93 pairs): AM 3,160 · AW 2,794 · UW 2,550 · AE 1,317 · AY · SA · SH · AS · GO · AF · BM · ML · AP · NR · GB · ST · SW · SP · SC · AU · SM · SR · BC · NL · GS · GK · NC/NK/NW/NE/NM · UM · UN · SO · PN · PO · BF — plus **`X99`** (121 CONTAINS, 74 FREE_FROM) = "other/unspecified".

### Documented code systems (in the schema — free)
ISO 3166-1 alpha-2 lowercase (`countryOfOrigin`) · ISO numeric (`countriesOfOrigin`) · `synkkaPackagingType` BASE_UNIT_OR_EACH/CASE/PALLET · nutrient ids · units GRM/KGM/MGM/MMT/CMT/LTR/MLT/KJO/E14 · `vatCode` STANDARD 25.5 / MEDIUM 13.5 / LOW 10 · `productionMethod` · `unitPrecision` · allergen `unit` as CONTAINS or FREE_FROM (**only these two**).

### NOT documented anywhere
Allergen 2-letter codes · the `MAY_CONTAIN` value · `category` names and hierarchy · `salesUnit`/`baseUnit`/`unitId` translations (KI 8,005 · ST 5,607 · KG 1,068 · PAK 880 · BAG 697 · RAS 328 · PRK 320 · BOT 310 · SK 120 · CS 72 · KLE 66 · KRT 48 · KAN 13 · PAL 4 · NIP 3 · DSP 3 · DZ 2 · KRS · ZML) · `temperatureCondition` 1–9 meanings · deposit `material` codes · fishing/GHS codes.

---

# PART 4 — Questions

Each: **what we found** → **why it matters** → **what changes with the answer.**

## Q1 — Is the order contract ours to define? ⭐
**Found:** six operations only — `ping`, `price`, `availability`, 3 downloads. **No order, basket, quote or confirmation endpoint** (404 verified), and no schema hinting at one.

**Why it matters:** the 30% criterion is *"full request → lookup → **order/approval** flow in the mocked environment."* With no order endpoint, "the mocked environment" must include something we build. Three readings, differing by hours:
- **(a)** a real mock order service — schema, persistence, order ids, state transitions; our agent calls it over HTTP like yours
- **(b)** a defined-and-stubbed interface — documented, minimal implementation
- **(c)** the agent commits internally, no service boundary; approval is app state

**Our assumption:** (a) — *"prototype the interface and operating model"* reads as us proposing the endpoint you don't have yet.

**Sub-questions:**
- Should our order request **extend your `customer` / `requestedDate` / `products` shape**? (We plan to — reusing your vocabulary is a visible production-mindedness signal.)
- **Line granularity** — one order per delivery date, or can one span dates?
- **Idempotency key** — do you want one? (Prevents double-ordering on agent retry.)
- **Does a confirmation promise quantity, or only price?** You say *"fixed prices rather than a negotiated quote"* — is price locked while quantity stays subject to actual stock?
- **Is an MCP tool surface acceptable as the submitted "interface,"** or HTTP+OpenAPI as primary? (Your scope note puts eventual transport out of scope, so we plan OpenAPI primary + MCP as a second transport over the same types.)

**Changes:** (b)/(c) saves ~3h for guardrails. An existing internal schema is worth more than anything we'd invent.

## Q2 — Will you judge date/lead-time logic at all?
**Found:** both APIs **ignore `requestedDate`**. 2026-11-13, 11-14 and 12-25 → byte-identical responses, `availableDate` pinned to **2026-11-16**. `/price` identical for 2025-06-01, 2026-11-16, 2027-06-01.

**Why it matters:** your canonical example is *"by Monday"* — untestable against one frozen date. Your resources promise *"delivery lead times"*; the mock doesn't implement them.

**Changes:** If judged → we need the intended rules (per temperature class? logistic model? vendor?), unreverse-engineerable from a single-date mock. If not → we build the plumbing correctly for production credibility, demo against 2026-11-16, stop investing.

## Q3 — Which `closingTime` semantics should we honour? ⭐
**Found:** `closingTime` has **12 distinct values**, not two — and **53% of deliverable products (129 of 244 sampled) report a cut-off that is already in the past.** Terminal products cluster at 2026-11-12T15:00 (over a day before server time 2026-11-13T21:33+02:00) while claiming 2026-11-16 availability; Stock products at 2026-11-15T17:00 (future). Documented as *"order by closingTime at the latest to receive goods on availableDate."*

**Why it matters:** decides whether **the majority** of the assortment is orderable in our demo. Respect the cut-offs literally → reject **53% of deliverable products**. Ignore them → no cut-off logic at all, and cut-off handling is exactly what the 15% robustness criterion rewards.

**Our plan:** detect the contradiction, degrade the commitment window to the price validity window, log the reason, surface it as a data-quality finding — our answer to your *"trust protocol"* problem.

**Changes:** Artefact → one-line trust finding. Behaviour to model (*"cut-off passed → next slot"*) → ~1h of real logic and a demo beat.

## Q4 — Weighting beyond the published rubric? Does a spec artefact score?
**Found:** rubric is published, but the four *"problems we'd love tackled"* carry no weights. **And the brief contradicts the rubric:** brief says substitution *"isn't scored as core"*; rubric gives **15% to robustness including substitutions**.

**Ask:** Which applies on substitution? Are the four problems weighted inside the published criteria or separate? **Does a specification artefact score on its own** (typed schema + authority model), or must everything be in a running demo? The openness criterion reads like a document, but *"slides alone are not sufficient"* appears elsewhere.

## Q5 — Is the `category` code hierarchical? (+ a name mapping)
**Found:** 349 categories, **all exactly 5 digits**, median 32 products, p90 117, max 443, 4 singletons. Schema: *"Category names are not part of this data set."* Inferred a few from Finnish names — 10400 drinking milk, 10401 liquid milk/creams, 41820 ice cream, 52201 chocolate, 22413 RTD coffee. **230 of 250 explicit substitution pairs (92%) stay inside the same category.**

**Why it matters — the hierarchy half is the valuable one:** if 10400 and 10401 are siblings under a 104xx parent, we can compute **category distance** and rank substitutes by how far from the request they are. That turns a flat same-category filter into the good-better-best ranking your *"response logic"* problem asks for.

**Changes:** Hierarchical → category-distance ranking, ~1h, much better output. Flat → fall back to brand + pack size + nutritional claim, weaker. Name mapping is cosmetic; hierarchy changes the algorithm.

## Q6 — `MAY_CONTAIN`, `X99`, and silence in an allergen decision ⭐
**Found:**
- Schema documents **only `CONTAINS` and `FREE_FROM`**. **`MAY_CONTAIN` is pervasive and undocumented** (AN 1,225 · AY 954 · AM 728 · SA 727). **A filter on the documented two silently treats "may contain traces" as safe.**
- Coverage is thin: `allergen` non-empty **41.1%**, `nonAllergen` **29.2%** → **~59% of the catalog carries no allergen statement at all.**
- **`X99`** = "other/unspecified", 121 CONTAINS + 74 FREE_FROM — cannot ground a safety claim either way.
- **In your own example:** `464306` is `FREE_FROM_LACTOSE` but `allergen: [{id: "AM", unit: "CONTAINS"}]` — **AM is milk. Lactose-free is not milk-allergen-free.**

**Why it matters:** your scenario is *"allergen-safe substitution under pressure: in a school or hospital kitchen."* We can only **certify** a swap on the ~29% with explicit `FREE_FROM`. On the silent 59%, **absence of CONTAINS is not evidence of absence.** This is a policy question only you can answer.

**Ask:**
- Is `MAY_CONTAIN` a hard fail for a constrained allergen, or an escalation?
- **Is silence ever permissible** for a school/hospital kitchen, or must the agent refuse without an explicit free-from?
- What does `X99` mean operationally — should it block a safety claim?
- Is the code list **GS1 AllergenTypeCode**? Is there a lookup table, or do we map AM/AE/BM ourselves?

**Changes:** Decides whether our strictest rule is DENY or ESCALATE, and it's the centre of one demo scenario. Your answer is also a product insight for you — we can show which items become agent-orderable by filling in one field.

## Q7 — Deposit pricing: in the total, or out of scope?
**Found:** 506 products carry deposits (576 lines, all `unit: ST`), but the **7 `material` codes resolve to zero catalog products** and no deposit price list exists anywhere.

**Why it matters:** for bottled/canned products the true payable total is **unknowable, and we cannot compute by how much.** An order total that silently omits deposits is quietly wrong — against a brief built on fixed-price commitments.

**Our plan:** have the total **declare its own incompleteness** (`completeness: INCOMPLETE_DEPOSITS`) and escalate rather than show a wrong number.

**Changes:** Out of scope → one line in ASSUMPTIONS. Expected → we need the price list, which isn't in the materials.

## Q8 — What are the actual rate limits?
**Found:** *"Undisclosed rate limits are in place"*, plus the architectural instruction *"solutions should not be based on frequently retrieving prices and availabilities for all products… query only when you have narrowed down the products based on static product data."* Max 1,000 per request. Empirically 80-id batches and ~15 calls drew no 429; **ceiling untested.**

**Why it matters:** hitting a limit **during the live demo** fails the 30% outright. We're already filtering locally first and caching to disk for replay, but we'd like a number.

**Ask:** Is a 1,000-product batch safe during judging? Requests/minute per key? Does a 429 return cleanly or drop?

## Q9 — Is customer or authority data coming?
**Found:** `customer` is free text that **provably changes nothing** (six strings → identical output). No customer model, spend limits, approver roles, contract assortments, or **order history**.

**Why it matters:** 20% of the rubric is autonomy and controls. A spend threshold needs a budget; an approver role needs an org model. We're currently inventing all of it. And your *"standing order drift detection"* scenario **requires order history that isn't provided.**

**Ask:** Is customer/authority data coming, or is the permission model entirely fictional on our side? For drift detection — should we synthesise history, and does synthetic history count?

**Changes:** If coming, we wire to yours. If not, we synthesise and document it in ASSUMPTIONS — defensible, but we want to say it deliberately rather than look like we missed it.

## Q10 — Why is delivery reliability only 25% covered? (we solved the carbon half ourselves)

**Found — carbon is explained, and it is not random.** Splitting the catalog on food vs non-food (non-food = category prefixes 63xx cleaning/napkins/tableware, 64xx packaging, 20xx kitchen equipment, 90xx office supplies — 22.6% of products):

| Segment | n | Delivery reliability | **Carbon** | Both | Neither |
|---|---|---|---|---|---|
| **Food** | 13,577 | 26.5% | **81.2%** | 23.0% | 15.4% |
| **Non-food** | 3,969 | 20.9% | **0.4%** | 0.0% | 78.7% |

Carbon isn't "62.9% with random gaps" — it's **81.2% on food and essentially zero on non-food**, because `kg CO2-eq/kg` is a food-LCA unit that is meaningless for a knife or a bottle of oven cleaner. 36 vendors with ≥20 products have <5% carbon coverage and **all are non-food** (DUNI 817 products, Essity 245, Wulff 232, Huhtamaki 190, Diversey/Kiilto 343).

**We also tested the "category average" claim.** Directionally honest but **not a clean category lookup**: of 279 categories with carbon data, 190 (68.1%) hold exactly one distinct value and **89 (31.9%) hold more**. 97.7% of covered products sit on their category's modal value. The splits are driven by **plant-based vs animal protein** — in category 41705, 105 products at 15.79 (Finnish meatballs) vs 2.195 and 1.73 (vegan patties). And **86 of 177 distinct values (48.6%) span more than one category**, with 0.79 spanning 47 — so category isn't the key either. The averages come from a coarser external food-type taxonomy ("beef", "cheese", "root vegetable") that **isn't in the dataset and isn't reconstructible from it**. Value precision corroborates averaging: 3-decimal values all end in 5 (exact midpoints of two 2-dp numbers), and 26 values carry 15–17 decimals of float noise.

→ Our rule: look carbon up **by `productId` only, never impute from a category sibling** (wrong for 32% of categories — and the splits are exactly the plant-based cases where a sustainability feature earns its keep).

**What's still open — delivery reliability.** Coverage is **dispersed ~25% everywhere** (per-category rate p25 0.15 / median 0.26 / p75 0.37, **no category at 100%**), which looks like order-history volume rather than product type. Distribution is wildly top-heavy: **56.3% at exactly 1.0**, 72.1% at ≥0.99, only 6.6% below 0.9, and **12 products at 0.0**.

**It also carries real forward signal.** An 80-product availability probe: **DR < 0.75 → 9/40 (22.5%) returned empty `scheduleLines`** and 30% unavailable overall, vs **DR == 1.0 → 0/40 empty** and 2.5% unavailable. Low-DR skews Terminal (15/40); DR=1.0 skews Stock (35/40). And the 12 products at DR 0.0 **still report themselves fully available and fully priced** — so historical reliability and the forward availability promise are independent signals that only meet in the ranking.

**Ask:**
- **Why is delivery reliability only on 25% of products** — insufficient order history, a deliberate cut-off, or something else?
- **Should missing reliability rank neutral or penalised?** (New product with no history → neutral. Excluded supplier → penalised. We currently weight-renormalise and never impute.)
- **Is reliability computed over a fixed window?** 56% sitting at exactly 1.0 suggests either a short window or few orders per product.
- **Confirm our read that carbon is food-only by design** — so we can drop the axis as *not applicable* on non-food rather than showing it as missing data.

**Changes:** Getting this backwards means confidently ranking a product well *because we know nothing about it.* Our current design: carbon absent on non-food = **not applicable, drop the axis**; delivery absent = **unknown, renormalise the weights**. Two different kinds of missing, handled differently.
