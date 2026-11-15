# Valio Aimo — verified findings

Rewritten on Saturday 14 Nov. Every figure here was recomputed from the product file or from saved live responses; the older text of this file, with its superseded claims, is gone. Field-level detail is in [docs/](docs/), starting with [docs/FIELD-DICTIONARY.md](docs/FIELD-DICTIONARY.md).

**How to read the numbers**
- **Catalog** = counted over all 17,546 products in the product file.
- **Sample** = a random sample of 1,000 products sent to `/api/availability` and `/api/price` on Friday 2026-11-13 at 23:00 server time. Sample figures are estimates and move with the clock.
- **Fixed set** = 24 products sent with 4 dates and 6 customer strings.

**How to read the behaviour:** the mock's behaviour is the scenario, not a fault. Unknown stock, passed cut-offs and undeliverable products are what the agent has to handle and explain.

---

## 1. The API

- **Six operations:** `GET /api/ping`, `POST /api/price`, `POST /api/availability`, and three file downloads. There is no order endpoint; the order step is ours. `GET` on `/api/order`, `/api/orders`, `/api/quote` and `/api/basket` returns 404.
- **Request for both POSTs:** `{customer: str, requestedDate: date, products: [str]}`, 1 to 1,000 ids. Header `X-API-Key`. Valio's spec is saved locally as `AIMO/openapi.json` (gitignored).
- **`requestedDate` changes nothing** (fixed set, 4 dates): every per-product field is identical; only the echoed date and `timeNow` differ. Prices come back even for dates outside their own `validFrom`–`validTo`. The spec does say `availableDate` "might differ from your requestedDate".
- **`customer` changes nothing** (fixed set, 6 strings), as the spec states. `/api/price` echoes it as `customerId`.
- **Optional fields are left out, never `null`.** Use `.get()`.
- **Dates:** datetimes carry an offset without a colon (`2026-11-12T15:00:00+0200`); `availableDate` is a bare date; open-ended prices use `validTo` `9999-12-31…`.
- **Rate limits are undisclosed.** 34 requests in 5 minutes, up to 251 ids each, drew no 429 and no rate-limit headers. The spec asks us to query only products already narrowed down from the static data.

### Availability — six states (sample)
| State | How to detect | Share |
|---|---|---|
| Confirmed | Stock, `closingTime` later than `timeNow`, amount between 0 and 999,999 | 25.2% |
| Quantity not confirmed | amount ≥ 999,999, cut-off still open | 9.2% |
| Cut-off passed | `closingTime` earlier than `timeNow` | 42.3% |
| Out of stock | a schedule line with amount 0 and no `availableDate` | 2.9% |
| Not deliverable | empty `scheduleLines`, no `logisticModel`, no `closingTime` | 20.3% |
| Blocked | `salesBlock` true | 0.1% (one product, `470094`) |

What the agent does in each state is in [SPEC.md](SPEC.md) §4, "The six states".

- **`closingTime`:** all 357 Terminal products in the sample were already past their cut-off (12 distinct values between 2026-11-11 13:00 and 2026-11-13 12:30; 229 at 2026-11-12 15:00). Stock: 372 of 440 close on Sunday 2026-11-15 17:00; 68 closed on Friday at 13:00.
- **`availableDate`:** 2026-11-16 on 767 of the 768 lines that carry one; the blocked product shows 2026-12-30.
- **Send an explicit `User-Agent`.** The API sits behind Cloudflare. On 14 Nov at 02:40 `GET /api/ping` with the same key returned 403 when the request carried Python's default user agent and 200 a minute later with an explicit one (`tta-preflight/1.0`). Friday's calls all sent `retest-client/1.0`.
- **`availableAmount`:** Terminal is always 999999 (documented: "actual value is not known"). For Stock the spec says "Stock products are stocked by us, so we know their available quantities" and does not mention placeholders. On Stock, 92 of 440 lines carry a placeholder equal to 9,999,999,999 ÷ base units per sales unit (9999999999, 4999999999, 416666666 …). The largest ordinary Stock value was 7,389. Detect with `availableAmount >= 999_999`. **Valio confirmed in person on 14 Nov that a very large value means they do not know the stock**, so these Stock lines are read like Terminal: quantity not confirmed.
- **Unknown product id:** `/api/availability` answers it exactly like a product that cannot be delivered. `/api/price` returns `error: true` for it and `error: false` for all 1,000 catalog ids. Check ids against the local catalog.
- **Sales unit:** the unit on the API line differs from the product file's `salesUnit` on 7 of 797 lines (`460657`: file `KI`, API `ST`). The price follows the API unit.

### Price (sample)
- `catalogPrice` is the price per sales unit. `Price.value` excludes tax and `Price.valueWithTax` includes it; `PriceWithTax.value` includes tax. Keep the two types apart.
- `tax.taxRate` was present on every priced product: 13.5 or 25.5.
- `comparisonPrice` and `comparisonUnit` are absent together on 20.6%.
- `netPriceFound` is true on 13 of 1,000, for any customer string.

---

## 2. The catalog

- 17,546 products, none deleted, 648 vendors, 349 categories (all 5-digit codes, no names).
- Names: Finnish 100%, **English 99.99%**, Swedish 91.8%.
- The product file loads in about half a second and 0.6 GB. It contains no JSON `null`: an unset field is an absent key.
- **Use `id` as the key.**

### The canonical request, worked
"1,000 litres of lactose-free milk by Monday":
- 4,178 products carry the claim `FREE_FROM_LACTOSE`. Category 10400 holds 35 of them.
- **All 35 declare milk (`AM`) as `CONTAINS`.** Lactose-free is not milk-free; the offer has to say both.
- Cheapest of the 24 with a captured price: `464306` at €1.01 per litre (customer price; list €1.44), one unit = 1 L, Stock, cut-off Sunday 17:00. 1,000 units = €1,010.00 before tax. Its quantity is a Stock placeholder (see §1).
- In a capture of 22 of the 35 on Friday at 21:33: 3 confirmed (`463380` 698 units, `463203` 192 cases of 100 × 2 cl, `462775` 51 units), 8 quantity not confirmed, 10 cut-off passed, 1 not deliverable. No single confirmed product covers 1,000 litres. Re-check before the demo.

---

## 3. Allergens

- **Relation values:** `CONTAINS` (15,610 rows), `MAY_CONTAIN` (9,956 rows, 2,685 products) and `UNDECLARED` (303 rows, 33 products) in the `allergen` group; `FREE_FROM` in the `nonAllergen` group. The schema documents only `CONTAINS` and `FREE_FROM`.
- **Meanings, from the public GS1 code lists** (Valio's use of them is to be confirmed, booth Q2):
  - `CONTAINS` — "Intentionally included in the product."
  - `MAY_CONTAIN` — not intentionally included, but may be present through shared production.
  - `UNDECLARED` — "Not intentionally included in the product and assessed not to require a cross-contact declaration"
  - `FREE_FROM` — "The product is free from the indicated substance."
  - `X99` — "Does not contain declaration obligatory allergens in the product." On 121 products, 120 of which list no other allergen code.
- **Coverage:** `allergen` is non-empty on 41.1% of products and `nonAllergen` on 29.2%. **46.2% have neither** (30.6% of food products, 99.8% of non-food). No data means unknown, not safe.
- **A nutritional claim is not an allergen statement:** of the 4,178 `FREE_FROM_LACTOSE` products, 1,485 declare milk as `CONTAINS` and 1,255 carry `AM` as `FREE_FROM`. That is correct labelling, not a data error.
- **Codes checked against the GS1 list:** `AM` milk · `AW` cereals containing gluten (`UW` wheat, `NR` rye, `GB` barley, `GO` oats) · `AE` eggs · `AF` fish · `AC` crustaceans · `UM` molluscs · `AP` peanuts · `AY` soy · `AN` tree nuts (`SA` almond, `SH` hazelnut, `SW` walnut, `SC` cashew, `ST` pistachio, `SP` pecan, `SM` macadamia, `SR` Brazil nut) · `BC` celery · `BM` mustard · `AS` sesame · `AU` sulphites · `NL` lupin · `ML` lactose. The full table is in [docs/SCHEMA-AND-CODES.md](docs/SCHEMA-AND-CODES.md) §3.3.

---

## 4. Pack size and units

- **`catalogPrice.value ÷ comparisonPrice.value` gives litres or kg per priced unit:** 1.00 for `464306` (1 L), 10.015 for `464119` (case of ten 1 L), 19.94 for `463038` (case of two 10 L). It is rounded (prices have 2 decimals) and unavailable when `comparisonPrice` is missing (20.6% of the sample).
- **`units[unitId == salesUnit].sizeInBaseUnits` is a count of base units, not litres or kg.** It is 1.0 on 62.4% of products.
- **`unitConversions…volume` is not reliably a volume:** of 8,970 rows only 1,071 carry a litre, millilitre or centilitre unit.
- Sales units: `KI` 8,005 · `ST` 5,607 · `KG` 1,068 · `PAK` 880 · `BAG` 697 and 12 rarer codes. Translations are not published.
- **Lot size:** `allowedLotSize` is 0.01 on 96.16% of products; the other 674 have a real step (1.5 on 62, 1.8 on 17).
- **Variable weight:** `variableUnit` is true on 632 products (628 sold in KG), false on 13,846 and absent on 3,068. All 37 in the sample are priced per kg. Open point: whether delivered weight equals ordered weight (booth Q9).
- **Deposits:** 506 products carry deposits (576 rows, 7 material codes). None of the codes is a product id and `/api/price` returns `error: true` for all 7, so deposits cannot be priced (booth Q8).
- **VAT:** `vatCode` in the file is unreliable (159 "MEDIUM MEDIUM", absent on 3,068). Use `tax.taxRate` from `/api/price`.

---

## 5. Substitution and categories

- 250 explicit substitution pairs on 189 products; one product (`471661`) lists itself.
- 230 pairs stay in the same 5-digit category. Of the other 20, 11 share the first 4 digits and 5 share only the first 3.
- Use the pairs as a seed. Candidate substitutes: same category, then same first 4 digits, then same first 3 (labelled weaker), always re-checking availability and allergens.

---

## 6. Optional comparison data

| Data | Coverage |
|---|---|
| Delivery reliability | 25.2% of products (4,425); 56.3% of those are exactly 1.0, 12 are 0.0 |
| Carbon footprint | 62.9% (11,033); **81.2% of food products, 0.4% of non-food** |
| Both | 17.8% (3,123) |

- Show a value when it exists; never impute a missing one.
- **Labels (`packagingMarkedLabel`):** `GOODS_FROM_FINLAND_BLUE_SWAN` 2,057 · `MADE_IN_FINLAND_FLAG_WITH_KEY` 1,772 · `FINNISH_HEART_SYMBOL` 826 · `EU_ORGANIC_FARMING` 456 · `SVANEN` 362 and rarer ones. Filter out the three temperature pseudo-labels in the same group (`warmTemperature`, `coolTemperature`, `freezeTemperature`).
- **Claims (`nutritionalClaim`, 21 ids):** `FREE_FROM_LACTOSE` 4,178 · `FREE_FROM_GLUTEN` 3,049 · `VEGAN` 2,959 · `VEGETARIAN` 2,358 · `FREE_FROM_PRESERVATIVES` 1,526 · `LOW_LACTOSE` 321.

---

## 7. Earlier claims that did not survive
The list is at the end of the team's booth questions, under "Claims we no longer make" (`AIMO/BOOTH-QUESTIONS.md`, on branch `replan-build`).
