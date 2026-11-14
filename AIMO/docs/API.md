# Valio Aimo Junction 2026 — API Reference

Authoritative reference for the mock API at `https://junction26.valioaimo.fi`.

Sources:
- OpenAPI 3.1 spec, fetched live from the portal root (`/openapi.json`) — field-meaning tables below are quoted from its endpoint descriptions.
- Live calls captured **2026-11-13T22:18+02:00** (server time). Counts labelled "random sample of 1,000" come from a retest at 2026-11-13 23:00 server time: a seeded random sample of 1,000 catalog ids plus the made-up id `459999` (§12). All JSON in this document is real captured output, not invented.
- Empirical behaviour already verified in [`../FINDINGS.md`](../FINDINGS.md) is cited rather than repeated.

API version reported by the spec: `0.1.0`. Title: *Valio Aimo Junction 2026 Challenge*.

---

## 1. Authentication

| Surface | Base | Credential |
|---|---|---|
| API (`/api/*`) | `https://junction26.valioaimo.fi/api` | HTTP header **`X-API-Key`** |
| Portal docs (`/docs`, `/redoc`, `/openapi.json`) | `https://junction26.valioaimo.fi` | **session cookie**, not the API key |

The spec declares exactly one security scheme and applies it to every operation:

```json
"securitySchemes": { "APIKeyHeader": { "type": "apiKey", "in": "header", "name": "X-API-Key" } }
```

### 1.1 Where the key comes from

The key is issued by the challenge organisers. In this repo it lives in `.env` at the repo root as `VALIO_AIMO_API_KEY` (alongside `VALIO_AIMO_BASE_URL`, `VALIO_AIMO_PORTAL`, `VALIO_AIMO_PORTAL_PASSWORD`). **The key is never written into source, docs, or logs.** Load it into the environment and reference it as a variable:

```bash
set -a && . ./.env && set +a   # run from the repo root
```

Every `curl` example below uses `$VALIO_AIMO_API_KEY`.

### 1.2 Missing or invalid key

Captured:

```bash
curl -s -w '\nHTTP %{http_code}\n' https://junction26.valioaimo.fi/api/ping
```

```json
{"detail":"Invalid or missing API key"}
```

→ `HTTP 401`, `content-type: application/json`. The same body is returned for a malformed key.

### 1.3 Portal docs use a different credential

The human documentation (`/docs`, `/redoc`) and the machine spec are served from the **root** path and gated by a **session cookie**, obtained by form-posting the portal password:

```bash
curl -s -c /tmp/jar -X POST https://junction26.valioaimo.fi/login \
  -d "password=$VALIO_AIMO_PORTAL_PASSWORD"          # → 303, Set-Cookie: session=...
curl -s -b /tmp/jar https://junction26.valioaimo.fi/openapi.json -o openapi.json
```

Gotchas confirmed live:

- **`/api/openapi.json` 404s** (`{"detail":"Not Found"}`). The spec is only at the root path.
- `VALIO_AIMO_PORTAL` in `.env` has a **trailing slash**; naive concatenation yields `//login`, which also returns `{"detail":"Not Found"}` with `HTTP 404`. Strip it.
- The session cookie has `Max-Age=43200` (12 h), `HttpOnly`, `Secure`, `SameSite=lax`.
- The API key is **not** accepted on the root doc paths, and the session cookie is **not** accepted on `/api/*`.

---

## 2. Published usage guidance (verbatim)

From `info.description` of the OpenAPI document:

> Use on-demand apis to query for dynamic data such as price and availability. File download apis will provide data sets needed in the challenge. The files do not change during the challenge unless announced separately.
>
> Note that solutions should not be based on frequently retrieving prices and availabilities for **all** products. In real world that would not be feasible since prices and availabilities are customer specific in this B2B scenario and they will constantly change. Query the APIs only when you have narrowed down the products that you are interested in based on static product data. Undisclosed rate limits are in place for the APIs

From the `/api/price` and `/api/availability` descriptions (both, identically):

> **Limit:** a request can contain at most 1 000 products. A longer list is rejected with HTTP 422. Query only the products you need.

> In reality, prices are customer specific so passing in a different customer number can return different prices for the same product / date combination. In this challenge, however, customer number does not affect response so you can pass in whatever.

Rate limits are **undisclosed**. No `429` was observed at the volumes used here (see §12): the 23:00 retest made 34 requests in under 5 minutes, up to 251 ids each, and drew no `429` and no rate-limit headers; the practical ceiling is untested.

---

## 3. Shared request schema — `ProductsRequest`

Both POST endpoints take the identical body.

| Field | Type | Required | Constraints | Meaning |
|---|---|---|---|---|
| `customer` | `string` | yes | — | Customer number. Must be a string (`"123"`, not `123`). Does not affect the response in this challenge (24 products × 6 different strings: every per-product field identical; `/api/price` echoes it as `customerId`). |
| `requestedDate` | `string` | yes | `format: date` (`YYYY-MM-DD`); a full datetime is also accepted by the date parser | Desired delivery date. **Changes no per-product field on either endpoint** (24 products × 4 dates, §8.6) — only echoed back. |
| `products` | `string[]` | yes | `minItems: 1`, `maxItems: 1000` | Product codes to query, 1–1 000 per request. Unknown codes are accepted and answered (see §6/§7). |

`Content-Type: application/json` is required.

Spec-supplied example:

```json
{ "customer": "123", "products": ["460013", "460063", "463989", "460056"], "requestedDate": "2026-11-16" }
```

### 3.1 Validation errors — `HTTPValidationError` / `ValidationError`

`HTTP 422`, `content-type: application/json`, body `{"detail": [ValidationError, ...]}`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `detail[].type` | `string` | yes | Pydantic error code (`missing`, `string_type`, `list_type`, `too_short`, `too_long`, `date_from_datetime_parsing`, …). |
| `detail[].loc` | `(string\|integer)[]` | yes | Path to the offending value, always rooted at `"body"`. |
| `detail[].msg` | `string` | yes | Human-readable message. |
| `detail[].input` | any | no | **Echo of the offending input value.** |
| `detail[].ctx` | `object` | no | Error-specific context (`min_length`, `max_length`/`actual_length`, parser `error`). |

#### Captured: missing fields

```bash
curl -s -X POST https://junction26.valioaimo.fi/api/price \
  -H "X-API-Key: $VALIO_AIMO_API_KEY" -H 'Content-Type: application/json' -d '{}'
```

```json
{"detail":[
 {"type":"missing","loc":["body","customer"],"msg":"Field required","input":{}},
 {"type":"missing","loc":["body","requestedDate"],"msg":"Field required","input":{}},
 {"type":"missing","loc":["body","products"],"msg":"Field required","input":{}}]}
```

All missing fields are reported in one response, not just the first.

#### Captured: wrong types

```bash
-d '{"customer":123,"requestedDate":"not-a-date","products":"464306"}'
```

```json
{"detail":[
 {"type":"string_type","loc":["body","customer"],"msg":"Input should be a valid string","input":123},
 {"type":"date_from_datetime_parsing","loc":["body","requestedDate"],
  "msg":"Input should be a valid date or datetime, invalid character in year",
  "input":"not-a-date","ctx":{"error":"invalid character in year"}},
 {"type":"list_type","loc":["body","products"],"msg":"Input should be a valid list","input":"464306"}]}
```

Note `customer` is **not** coerced from an integer — strict string typing.

#### Captured: empty `products` array

```bash
-d '{"customer":"123","requestedDate":"2026-11-16","products":[]}'
```

```json
{"detail":[{"type":"too_short","loc":["body","products"],
 "msg":"List should have at least 1 item after validation, not 0",
 "input":[],"ctx":{"field_type":"List","min_length":1,"actual_length":0}}]}
```

#### Captured: more than 1 000 products (1 001 sent)

```json
{"detail":[{"type":"too_long","loc":["body","products"],
 "msg":"List should have at most 1000 items after validation, not 1001",
 "input":["464306","464306", ... all 1001 entries ... ],
 "ctx":{"field_type":"List","max_length":1000,"actual_length":1001}}]}
```

⚠️ **`input` echoes the entire rejected array.** A 1 001-id over-limit request produces a ~9 KB error body; a client that logs `detail` verbatim will log the whole payload back. Truncate before logging.

---

## 4. `GET /api/ping`

**Purpose:** liveness / credential check. Tag: *On-demand*. `operationId: ping_api_ping_get`.

Request: no body, no parameters. Requires `X-API-Key`.

Response schema in the spec is empty (`{}`). Captured actual response:

```bash
curl -s -i https://junction26.valioaimo.fi/api/ping -H "X-API-Key: $VALIO_AIMO_API_KEY"
```

```
HTTP/2 200
content-type: application/json
```
```json
{"status":"ok"}
```

| Field | Type | Nullability | Meaning |
|---|---|---|---|
| `status` | `string` | always present | Literal `"ok"`. Undocumented in the spec; captured empirically. |

Use this — never `/api/price` — to validate a key or probe reachability.

---

## 5. `POST /api/price`

**Purpose (spec):** *"Returns the price of the products for the customer on the requested date."* Tag: *On-demand*. `operationId: price_api_price_post`.

Request: [`ProductsRequest`](#3-shared-request-schema--productsrequest).

### 5.1 Response — `PriceResponse`

| Field | Type | Nullability | Meaning (spec wording) |
|---|---|---|---|
| `customerId` | `string` | required | "The customer id from the request. Not meaningful in this challenge." |
| `currency` | `string` | required | "Currency of all prices." Observed: `EUR`. |
| `pricingDate` | `string` | required | "The date the prices apply to (the requested date)." Returned as an ISO datetime with Helsinki offset, e.g. `2026-11-16T00:00:00+0200` (note: offset without a colon). |
| `products` | `ProductPrice[]` | required | "One entry per requested product." One entry per **requested slot**, in request order (duplicates are echoed once per occurrence). |

### 5.2 `ProductPrice`

Spec `required`: `productId`, `quantity`, `netPriceFound`, `error`. Everything else is `anyOf [T, null]` — and in practice **omitted, never `null`** (§7).

| Field | Type | Declared | Observed | Meaning (spec wording) |
|---|---|---|---|---|
| `productId` | `string` | required | always | The product code. |
| `quantity` | `number` | required | always | "Quantity the price is for (always 1.0)." Confirmed: `1.0` on all 1,000 (random sample of 1,000, 2026-11-13 23:00). |
| `catalogPrice` | `Price` | `\| null` | present iff `error == false` | "Price per sales unit before tax. `value` is without tax, `valueWithTax` with tax." |
| `priceWithTax` | `PriceWithTax` | `\| null` | present iff `error == false` | "The price including tax, with its validity period." |
| `comparisonPrice` | `Price` | `\| null` | **key absent** on 206 of 1,000 (20.6%; random sample of 1,000, 2026-11-13 23:00) | "Price per `comparisonUnit` (for example per kg) so products of different size can be compared." |
| `comparisonUnit` | `string` | `\| null` | absent exactly when `comparisonPrice` is absent | "Unit of the comparison price. Only KG (kilogram) and L (litre) are used." |
| `tax` | `Tax` | `\| null` | present iff `error == false` | "`taxRate` (percent) and `taxValue` (the tax amount in currency)." |
| `listPrice` | `Price` | `\| null` | present iff `error == false` | "Price before the customer-specific price or discount." |
| `netPriceFound` | `boolean` | required | always | "True when a customer-specific net price was found, false when the catalog price was used." Observed `true` on 13 of 1,000 (same sample). |
| `error` | `boolean` | required | always; `false` on all 1,000 sampled catalog ids, `true` on the non-catalog id (§8.5) | "True when no price could be found for the product." |

### 5.3 `Price` (used by `catalogPrice`, `comparisonPrice`, `listPrice`)

| Field | Type | Nullability | Meaning |
|---|---|---|---|
| `value` | `number` | required | Amount **excluding** tax. |
| `valueWithTax` | `number` | required | Amount **including** tax. |
| `validFrom` | `string` | required | "Period on which the price is valid" — start. ISO datetime, Helsinki offset. |
| `validTo` | `string` | required | Period end. Open-ended prices use the sentinel `9999-12-31T00:00:00+0200`. |
| `currency` | `string` | required | Per-price currency; duplicates the top-level `currency`. |

### 5.4 `PriceWithTax` (used by `priceWithTax` only)

Same as `Price` **minus `valueWithTax`**: `value` (number, required) — here `value` is the tax-**inclusive** amount — plus `validFrom`, `validTo`, `currency`. Do not share a deserialiser between `Price` and `PriceWithTax`: the meaning of `value` differs.

### 5.5 `Tax`

| Field | Type | Nullability | Meaning |
|---|---|---|---|
| `taxRate` | `number` | required | VAT percent. Observed: `13.5`, `25.5`. **Authoritative** — see §8.8. |
| `taxValue` | `number` | required | Tax amount in `currency`, for `quantity` = 1. |

### 5.6 Captured example — request

```bash
curl -s -X POST https://junction26.valioaimo.fi/api/price \
  -H "X-API-Key: $VALIO_AIMO_API_KEY" -H 'Content-Type: application/json' \
  -d '{"customer":"123","requestedDate":"2026-11-16","products":["464306","460180","999999"]}'
```

### 5.7 Captured example — response (real values, 2026-11-13)

Fully populated entry (`464306`, the cheapest lactose-free milk per FINDINGS.md):

```json
{
  "customerId": "123",
  "currency": "EUR",
  "pricingDate": "2026-11-16T00:00:00+0200",
  "products": [
    {
      "productId": "464306",
      "quantity": 1.0,
      "catalogPrice": {"value": 1.01, "valueWithTax": 1.15,
        "validFrom": "2026-09-01T00:00:00+0300", "validTo": "2026-12-31T00:00:00+0200", "currency": "EUR"},
      "priceWithTax": {"value": 1.15,
        "validFrom": "2026-09-01T00:00:00+0300", "validTo": "2026-12-31T00:00:00+0200", "currency": "EUR"},
      "comparisonPrice": {"value": 1.01, "valueWithTax": 1.15,
        "validFrom": "2026-09-01T00:00:00+0300", "validTo": "2026-12-31T00:00:00+0200", "currency": "EUR"},
      "comparisonUnit": "L",
      "tax": {"taxRate": 13.5, "taxValue": 0.14},
      "listPrice": {"value": 1.44, "valueWithTax": 1.63,
        "validFrom": "2025-01-02T00:00:00+0200", "validTo": "9999-12-31T00:00:00+0200", "currency": "EUR"},
      "netPriceFound": true,
      "error": false
    }
  ]
}
```

Entry with **no comparison price** (`460180`) — note `comparisonPrice` and `comparisonUnit` keys are *absent*, and `netPriceFound` is `false` so `catalogPrice` < `listPrice` still holds via a catalog-level discount:

```json
{
  "productId": "460180",
  "quantity": 1.0,
  "catalogPrice": {"value": 26.08, "valueWithTax": 32.73,
    "validFrom": "2026-05-01T00:00:00+0300", "validTo": "9999-12-31T00:00:00+0200", "currency": "EUR"},
  "priceWithTax": {"value": 32.73,
    "validFrom": "2026-05-01T00:00:00+0300", "validTo": "9999-12-31T00:00:00+0200", "currency": "EUR"},
  "tax": {"taxRate": 25.5, "taxValue": 6.65},
  "listPrice": {"value": 32.6, "valueWithTax": 40.91,
    "validFrom": "2026-05-01T00:00:00+0300", "validTo": "9999-12-31T00:00:00+0200", "currency": "EUR"},
  "netPriceFound": false,
  "error": false
}
```

Unpriceable / unknown product (`999999`) — **only four keys exist**:

```json
{ "productId": "999999", "quantity": 1.0, "netPriceFound": false, "error": true }
```

---

## 6. `POST /api/availability`

**Purpose (spec):** *"Tells whether the products can be delivered on the requested date and how much is available."* Tag: *On-demand*. `operationId: availability_api_availability_post`.

Request: [`ProductsRequest`](#3-shared-request-schema--productsrequest).

### 6.1 Response — `AvailabilityResponse`

| Field | Type | Nullability | Meaning (spec wording) |
|---|---|---|---|
| `timeNow` | `string` | required | "Server time when the answer was produced (Helsinki time)." e.g. `2026-11-13T22:18:22+0200`. |
| `requestedDate` | `string` | required | "The date from the request, at midnight." e.g. `2026-11-16T00:00:00+0200`. |
| `products` | `ProductAvailability[]` | required | "One entry per requested product, in request order." |

### 6.2 `ProductAvailability`

Spec `required`: `productId`, `salesBlock`, `scheduleLines`.

| Field | Type | Declared | Observed | Meaning (spec wording) |
|---|---|---|---|---|
| `productId` | `string` | required | always | "The product code." |
| `closingTime` | `string` | `\| null` | **key absent** on 203 of 1,000 (all of them the empty-`scheduleLines` entries; random sample of 1,000, 2026-11-13 23:00) | "The order cut-off time (= order by closingTime at the latest to receive goods on availableDate)." |
| `salesBlock` | `boolean` | required | always; **`true` on 1 of 1,000** (`470094`, §8.3), `false` on the rest | "If true, Product cannot be ordered currently." |
| `logisticModel` | `string` | `\| null` | **key absent** on the same 203 entries | "Stock products are stocked by us, so we know their available quantities. Terminal products are delivered from supplier's warehouses and we don't know the actual available quantities." Observed values: `Stock` (440), `Terminal` (357). |
| `scheduleLines` | `ScheduleLine[]` | required | always present; length 0 or 1 | "If product is available, array has exactly one entry. Empty array means product cannot currently be delivered on any date." |

### 6.3 `ScheduleLine`

Spec `required`: `salesBlock`, `availableAmount`, `salesUnit`.

| Field | Type | Declared | Observed | Meaning (spec wording) |
|---|---|---|---|---|
| `salesBlock` | `boolean` | required | always; **`true` on 1 of 797 lines** (`470094`), `false` on the rest | "If true, product cannot be ordered currently." |
| `availableAmount` | `number` | required | always | "Quantity available, in `salesUnit`. For Terminal products this is always 999999 since actual value is not known. 0 means not available." See §8.1 — Stock lines carry a second placeholder rule that the spec does not mention. |
| `availableDate` | `string` | `\| null` | **key absent** on 29 of 797 lines — exactly the lines where `availableAmount == 0` | "Earliest date when amount is available. Note that this might differ from your requestedDate." `2026-11-16` on 767 of the 768 lines that carry one, `2026-12-30` on one (`470094`). |
| `salesUnit` | `string` | required | always | "Technical code of sales unit." Observed: `KI`, `ST`, `KG`, `PAK`, `BAG`, `PRK`, `BOT`, `SK`, `RAS`, `CS`, `KLE`. Differs from the product file's `salesUnit` on 7 of 797 lines (e.g. `460657`: file `KI`, API `ST`). Translations are not published (FINDINGS.md). |

### 6.4 Captured example — request

```bash
curl -s -X POST https://junction26.valioaimo.fi/api/availability \
  -H "X-API-Key: $VALIO_AIMO_API_KEY" -H 'Content-Type: application/json' \
  -d '{"customer":"123","requestedDate":"2026-11-16","products":["464306","464119","460660","999999"]}'
```

### 6.5 Captured example — response (real values, 2026-11-13T22:18+02:00)

```json
{
  "timeNow": "2026-11-13T22:18:22+0200",
  "requestedDate": "2026-11-16T00:00:00+0200",
  "products": [
    {
      "productId": "464306",
      "closingTime": "2026-11-15T17:00:00+0200",
      "salesBlock": false,
      "logisticModel": "Stock",
      "scheduleLines": [
        {"salesBlock": false, "availableAmount": 9999999999.0, "availableDate": "2026-11-16", "salesUnit": "ST"}
      ]
    },
    {
      "productId": "464119",
      "closingTime": "2026-11-12T15:00:00+0200",
      "salesBlock": false,
      "logisticModel": "Terminal",
      "scheduleLines": [
        {"salesBlock": false, "availableAmount": 999999.0, "availableDate": "2026-11-16", "salesUnit": "KI"}
      ]
    },
    {
      "productId": "460660",
      "closingTime": "2026-11-13T13:00:00+0200",
      "salesBlock": false,
      "logisticModel": "Stock",
      "scheduleLines": [
        {"salesBlock": false, "availableAmount": 0.0, "salesUnit": "KI"}
      ]
    },
    { "productId": "999999", "salesBlock": false, "scheduleLines": [] }
  ]
}
```

(The four entries are real, captured in the same 298-product response; they are shown together here to put all four shapes side by side.)

---

## 7. Nullability and missing keys

This is the single most important implementation detail: the spec declares these fields nullable while the server omits them.

### 7.1 Declared `| null` in the spec

| Schema | Field | Declaration |
|---|---|---|
| `ProductPrice` | `catalogPrice`, `priceWithTax`, `comparisonPrice`, `comparisonUnit`, `tax`, `listPrice` | `anyOf [T, null]`, not in `required` |
| `ProductAvailability` | `closingTime`, `logisticModel` | `anyOf [string, null]`, not in `required` |
| `ScheduleLine` | `availableDate` | `anyOf [string, null]`, not in `required` |
| `ValidationError` | `input`, `ctx` | not in `required` |

### 7.2 What actually happens on the wire

**Across the random sample of 1,000 (2026-11-13 23:00) on both endpoints, not one JSON `null` was returned.** Every optional field is **omitted entirely** when it has no value. Observed key sets:

`/api/price` (n = 1,001: the 1,000 sampled catalog ids plus the made-up id `459999`):

| Keys present | Count | Case |
|---|---|---|
| all 10 | 794 | priced, with comparison price |
| 8 (no `comparisonPrice`, no `comparisonUnit`) | 206 | priced, comparison price unavailable |
| 4 (`productId`, `quantity`, `netPriceFound`, `error`) | 1 | `error: true` — the made-up id |

`/api/availability` (n = 1,001, same ids):

| Keys present | Count | Case |
|---|---|---|
| 5 (incl. `closingTime`, `logisticModel`) | 797 | has a schedule line |
| 3 (`productId`, `salesBlock`, `scheduleLines`) | 204 | `scheduleLines: []` — 203 undeliverable catalog products and the made-up id |

`ScheduleLine`: `availableDate` key absent on all 29 lines with `availableAmount == 0`, present on all 768 others.

This matches FINDINGS.md §1 (optional fields are left out, never `null`).

### 7.3 Why `.get()` is mandatory

A typed client written from the spec will model these as `Optional[T] = None` and reach for them directly. On the wire there is no key at all, so:

- `entry["comparisonPrice"]` → **`KeyError`** on ~21% of priced products.
- `entry["closingTime"]` → **`KeyError`** on ~20% of availability entries — i.e. exactly the undeliverable ones your filter is trying to reject.
- `line["availableDate"]` → **`KeyError`** on every out-of-stock line.

Rules:

1. Read every non-`required` field with `.get(key)` (or a Pydantic model with a default of `None`, which tolerates both absent keys and explicit `null`).
2. Treat **absent** and **`null`** as the same thing. The server currently only ever omits, but the spec permits `null`, so handle both.
3. Never branch on `key in entry` as a semantic signal where a cheaper, documented signal exists — use `error` for price and `len(scheduleLines)` for availability.
4. Do not derive "is a Terminal product" from `"logisticModel" in entry`; derive "is undeliverable" from `scheduleLines == []` and only then skip.

---

## 8. Sentinels and gotchas

### 8.1 `availableAmount` placeholders: two rules

The spec documents `999999` (Terminal: "actual value is not known") and `0` (not available). In the random sample of 1,000 (2026-11-13 23:00; 797 schedule lines) every placeholder follows one of two rules:

| Rule | Lines | Note |
|---|---|---|
| **Terminal:** `availableAmount == 999999.0` | 357 of 357 Terminal lines | the documented "unknown" value |
| **Stock:** `availableAmount == floor(9,999,999,999 ÷ sizeInBaseUnits)`, with `sizeInBaseUnits` of the product's sales unit (`units[unitId == salesUnit]` in the product file) | 92 of 440 Stock lines | not in the spec. 9 distinct values in the sample: `9999999999.0` (81 lines, sales unit = 1 base unit), `4999999999.0`, `2499999999.0`, `1666666666.0`, `1428571428.0`, `999999999.0`, `833333333.0`, `499999999.0`, `416666666.0`; also `666666666.0` for `463779` (15 base units per `KI`) in the 37-id extras call |

The other Stock lines: `0.0` on 29 (not available, §8.2) and an ordinary whole-number quantity on 319 (1 – 7,389, median 35).

→ **`if amount == 999999` is wrong, and so is any fixed allow-list.** One threshold covers both rules: treat `availableAmount >= 999_999` as "quantity unknown", never as a number to do arithmetic on. A `>= 1_000_000` rule misses the spec's own Terminal value `999999`. The largest ordinary Stock value in the sample was 7,389; nothing fell between 7,389 and 999,999.

### 8.2 `availableAmount == 0` is a third unavailable state

A product can have a **non-empty** `scheduleLines` with `availableAmount: 0.0` **and no `availableDate` key**. 29 such lines in the random sample of 1,000 (2026-11-13 23:00), all `Stock` (e.g. `470193`, `467011`; `460660` in the §6.5 example), all with a populated `logisticModel` and `closingTime`. A client that only checks `scheduleLines == []` will treat these as orderable. Check both.

### 8.3 `salesBlock` is rarely `true`

`true` on 1 of 1,000 products in the random sample (2026-11-13 23:00): `470094`, at product level and on its schedule line (Terminal, `availableAmount` 999999.0, `availableDate` 2026-12-30). `false` on the other 999 products and 796 lines. Treat `true` at either level as "cannot be ordered currently" (the spec's wording). It is rare: empty `scheduleLines` (§8.4) and zero-amount lines (§8.2) are the common unavailable states.

### 8.4 Empty `scheduleLines` is the real undeliverable signal

203 of 1,000 (20.3%; random sample of 1,000, 2026-11-13 23:00) returned `{productId, salesBlock: false, scheduleLines: []}`. That is the authoritative "cannot be delivered on any date" answer, per the spec's own wording.

### 8.5 Unknown SKU is indistinguishable from known-but-undeliverable on `/api/availability` only

On `/api/availability` the made-up id `459999` (absent from the catalog) returned the same shape as each of the 203 undeliverable catalog products in the random sample of 1,000 (2026-11-13 23:00), e.g. `465854`:

```json
{ "productId": "459999", "salesBlock": false, "scheduleLines": [] }
```

`/api/price` does tell them apart: it returned `error: true` (four keys) for `459999` and for the 7 non-catalog deposit material codes, and `error: false` with a price for all 1,000 sampled catalog ids, the 203 undeliverable ones included. → Still **validate SKU existence against the static product file locally**: `/api/availability` alone reports a typo'd SKU as "not available".

### 8.6 `requestedDate` is ignored

24 products × 4 dates (2025-06-01, 2026-11-16, 2026-11-18, 2027-06-01; captured 2026-11-13 23:03): every per-product field is identical on both endpoints. The responses are not byte-identical: the echoed `requestedDate` / `pricingDate` and `timeNow` differ. `availableDate` does not follow the request (`2026-11-16` on 16 lines and `2026-12-30` on one, for all four dates). `/api/price` returns prices for dates outside their own `validFrom`–`validTo`: for 2025-06-01, 20 of the 23 priced products carry a `catalogPrice.validFrom` later than the requested date; for 2027-06-01, 4 carry a `validTo` (2026-12-31) earlier than it. Build real date logic, but demo against **2026-11-16**.

### 8.7 `closingTime` has often already passed, especially on Terminal products

At `timeNow` 2026-11-13T23:00:16–23:00:35+0200, random sample of 1,000 (797 with a schedule line; **14 distinct cut-off values**: 12 on Terminal, 2 on Stock):

| `closingTime` | Count | Relative to now |
|---|---|---|
| `2026-11-15T17:00:00+0200` | 372 | future (Stock) |
| `2026-11-12T15:00:00+0200` | 229 | **past** (Terminal) |
| `2026-11-13T13:00:00+0200` | 68 | **past**, same day (Stock) |
| `2026-11-12T14:00:00+0200` | 28 | **past** (Terminal) |
| `2026-11-12T12:00:00+0200` | 27 | **past** (Terminal) |
| `2026-11-12T13:00:00+0200` | 21 | **past** (Terminal) |
| `2026-11-12T14:30:00+0200` | 15 | **past** (Terminal) |
| `2026-11-12T12:30:00+0200` | 12 | **past** (Terminal) |
| `2026-11-12T16:00:00+0200` | 10 | **past** (Terminal) |
| `2026-11-12T13:30:00+0200` | 9 | **past** (Terminal) |
| `2026-11-11T13:00:00+0200` | 2 | **past** (Terminal) |
| `2026-11-12T10:30:00+0200` | 2 | **past** (Terminal) |
| `2026-11-12T15:30:00+0200` | 1 | **past** (Terminal) |
| `2026-11-13T12:30:00+0200` | 1 | **past**, same day (Terminal, `470094`) |
| key absent | 203 | undeliverable |

Split: **425 past / 372 future / 203 absent.** Terminal: 357 of 357 already past. Stock: 372 at 2026-11-15T17:00 (future), 68 at 2026-11-13T13:00 (past). **53.3% of products with a schedule line (425 of 797) report a cut-off already in the past**, and 424 of those 425 carry an `availableDate` (the other is a zero-amount line). The team reads `closingTime` literally ([PLAN.md](../PLAN.md) §2): a product whose cut-off has passed cannot be promised for `availableDate`, so it is not offered for a dated request and the explanation names it. That rule excludes 42.5% of this sample. These counts move with the clock: the sample was taken on a Friday at 23:00.

### 8.8 `tax.taxRate` is authoritative over the file's `vatCode`

The static product file's `vatCode` is dirty — 159 literal `"MEDIUM MEDIUM"`, 1 `"STANDARD MEDIUM"`, 4 empty, key absent on 3 068 (FINDINGS.md §4). The price API's `tax.taxRate` is a clean number (`13.5` / `25.5` observed) and the spec says it is the tax rate that applies. **Never parse `vatCode`; always use `tax.taxRate`.**

### 8.9 Other wire-level gotchas

- **Timezone offsets are written without a colon** (`+0200`, `+0300`). `datetime.fromisoformat` handles this on Python ≥ 3.11; on 3.10 and earlier it raises. Normalise before parsing.
- **`validTo: "9999-12-31T00:00:00+0200"`** is the open-ended-price sentinel. Do not feed it to date arithmetic or to a database `timestamptz` column without clamping.
- Dates mix formats: `availableDate` is a bare `YYYY-MM-DD`; every other date-like field is a full offset datetime.
- `pricingDate`/`requestedDate` echo the request at Helsinki midnight — offset is seasonal (`+0200` in November, `+0300` in summer).
- `PriceWithTax.value` is tax-**inclusive** while `Price.value` is tax-**exclusive**. Equal field names, opposite meanings.
- Duplicate ids in `products` are answered once per occurrence; de-duplicate client-side to save budget.
- The 422 body echoes the full rejected input (§3.1).

---

## 9. File download endpoints

Three operations, all `GET`, all requiring `X-API-Key`, all tagged *File downloads*, all returning **`307 Temporary Redirect`** with an empty body.

| Path | Redirect target | Type | Size |
|---|---|---|---|
| `/api/products/download` | `/files/<hash>/valio_aimo_junction26_product_data.json` | `application/json` | **87 077 467 B (~83 MiB)** |
| `/api/delivery-reliability/download` | `/files/<hash>/valio_aimo_junction26_delivery_reliability.csv` | `text/csv; charset=utf-8` | 56 741 B |
| `/api/carbon-footprint/download` | `/files/<hash>/valio_aimo_junction26_carbon_footprint.csv` | `text/csv; charset=utf-8` | — |

Spec descriptions:

> Provides product data file as JSON. Follow the redirect (curl -L). This will not change during the challenge without separate announcement so you only need to retrieve it once

> Provides the delivery reliability file as CSV (productId, deliveryReliability). Follow the redirect (curl -L). …

> Provides the carbon footprint file as CSV (productId, AVG kg CO2-eq/kg). Follow the redirect (curl -L). …

### 9.1 The redirect target does NOT require the API key

Captured, with **no** `X-API-Key` header:

```bash
curl -s -I https://junction26.valioaimo.fi/files/<hash>/valio_aimo_junction26_delivery_reliability.csv
# HTTP/2 200 · content-type: text/csv; charset=utf-8 · content-length: 56741
```

The `/files/<hash>/<name>` URLs are unauthenticated, capability-style links: the key gates only the `/api/*/download` indirection. Consequences:

- Treat the `/files/...` URL as a secret-ish artefact; it is a public download link for anyone who has it.
- `curl -L` works, but so does any plain HTTP client with no credential once you have the location.
- Resolve the location cheaply without transferring the body:

```bash
curl -s -o /dev/null -w '%{redirect_url}\n' \
  https://junction26.valioaimo.fi/api/products/download -H "X-API-Key: $VALIO_AIMO_API_KEY"
```

⚠️ **Do not download the product JSON repeatedly.** It is ~83 MB and already present in this repo at `AIMO/valio_aimo_junction26_product_data.json`. `json.load` on it takes about half a second and ~0.6–0.7 GB peak RSS (measured 2026-11-14, Python 3.13; FINDINGS.md §2).

---

## 10. Client implementation checklist

A Python client against this API must do all of the following.

**Transport & auth**
1. Read the key from the environment (`VALIO_AIMO_API_KEY`); never hard-code, never log it, never put it in a URL.
2. Send `X-API-Key` and `Content-Type: application/json` on every `/api/*` call.
3. Probe with `GET /api/ping` (expect `{"status":"ok"}`) at start-up; a `401` means the key is missing/invalid and no amount of retrying will fix it.
4. Use one `requests.Session` / `httpx.Client` with keep-alive. Set an explicit timeout (connect 5 s, read 30 s — the 298-id calls returned in well under that).

**Batching**
5. Hard-cap `products` at **1 000** per request, client-side. Do not learn the limit from a `422`.
6. De-duplicate ids and preserve a request-order → id mapping; the response is positional, one entry per requested slot.
7. Prefer a few large batches over many small ones. 298 ids in one call is fine and drew no `429`; two such calls back-to-back drew no `429` either. The 14 calls of that session (§12) drew no `429`, and neither did the 34 requests in under 5 minutes of the 23:00 retest (up to 251 ids each; no rate-limit headers either).
8. **Filter on the static product file first.** The published guidance is explicit: do not bulk-query prices/availability for all products; narrow down on static data, then make one narrow API call. 17 546 products would be 18 calls per sweep — don't.

**Backoff & errors**
9. Rate limits are undisclosed. Implement exponential backoff with jitter (base 1 s, ×2, cap ~60 s, ≤5 attempts) on `429` and `5xx`; honour `Retry-After` if present. **Stop the whole sweep on the first `429`** rather than hammering.
10. Never retry a `422` or `401` — both are deterministic client errors.
11. When logging a `422`, strip or truncate `detail[].input`; it contains your whole request body.
12. Treat a `200` with `error: true` as a per-product failure, not a request failure. Do not abort the batch.

**Parsing**
13. Use `.get()` (or Pydantic models with `None` defaults) for every field not in the spec's `required` list. Absent keys, not nulls (§7).
14. Normalise `+0200`-style offsets before `fromisoformat` on Python < 3.11; clamp `9999-12-31` before any date arithmetic.
15. Keep `Price` and `PriceWithTax` as distinct types — `value` means different things.

**Which fields to trust**
16. Not orderable if `scheduleLines` is empty, `availableAmount == 0` or `salesBlock` is true on the product or the line. Passing that is necessary, not sufficient: apply items 18 and 19.
17. Treat `salesBlock: true` (product or line level) as not orderable; it was `true` on 1 of 1,000 sampled products (`470094`, §8.3).
18. Treat `availableAmount >= 999_999` as "quantity unknown" (a `>= 1_000_000` rule misses the Terminal value `999999`); never do arithmetic on it or propose an order sized from it.
19. Compare `closingTime` with `timeNow`. A product whose cut-off has passed cannot be promised for `availableDate`: do not offer it for a dated request, and name it in the explanation ([PLAN.md](../PLAN.md) §2).
20. Ignore `requestedDate` as a constraint the API enforces — it does not. Enforce lead time yourself.
21. Use `tax.taxRate` for VAT, never the file's `vatCode`.
22. Use `catalogPrice.value` for ex-VAT line totals; use `listPrice.value` only to show the discount, and check `netPriceFound` to say whether the price is customer-specific.
23. Use `comparisonPrice`/`comparisonUnit` when present (≈79%) for per-kg/per-L comparison; fall back to `catalogPrice.value / comparisonPrice.value` for pack size (FINDINGS.md) and to the three-tier name/unit fallback when absent — with a confidence flag.
24. Validate SKUs against the local catalog before querying, so "unknown SKU" and "undeliverable" stay distinguishable (§8.5).

**Caching**
25. Cache the three downloaded files on disk permanently — the spec says they do not change during the challenge. Load the 83 MB JSON once per process (about half a second, ~0.6–0.7 GB peak RSS) and index it by `id`.
26. Cache price and availability responses in-process with a short TTL (minutes) keyed on the id set only — `customer` and `requestedDate` provably do not affect the result, so do not key on them (but keep them in the request).
27. Persist raw responses alongside `timeNow`/`pricingDate` so any quoted price or availability is auditable and re-verifiable.

---

## 11. Copy-pasteable curl recipes

```bash
# Load credentials (never echo them)
set -a && . ./.env && set +a   # run from the repo root
BASE=https://junction26.valioaimo.fi

# 1. Liveness / key check
curl -s "$BASE/api/ping" -H "X-API-Key: $VALIO_AIMO_API_KEY"

# 2. Price
curl -s -X POST "$BASE/api/price" \
  -H "X-API-Key: $VALIO_AIMO_API_KEY" -H 'Content-Type: application/json' \
  -d '{"customer":"123","requestedDate":"2026-11-16","products":["464306","464401","464237"]}'

# 3. Availability
curl -s -X POST "$BASE/api/availability" \
  -H "X-API-Key: $VALIO_AIMO_API_KEY" -H 'Content-Type: application/json' \
  -d '{"customer":"123","requestedDate":"2026-11-16","products":["464306","464119"]}'

# 4. Large batch from a file (≤1000 ids)
curl -s -X POST "$BASE/api/price" \
  -H "X-API-Key: $VALIO_AIMO_API_KEY" -H 'Content-Type: application/json' \
  -d @request.json -o price.json -w 'HTTP %{http_code}\n'

# 5. Resolve a download link WITHOUT transferring the body
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' \
  "$BASE/api/products/download" -H "X-API-Key: $VALIO_AIMO_API_KEY"

# 6. Inspect a download target's size/type (no key needed on /files/...)
curl -s -I "$(curl -s -o /dev/null -w '%{redirect_url}' \
  "$BASE/api/delivery-reliability/download" -H "X-API-Key: $VALIO_AIMO_API_KEY")"

# 7. Download the small CSVs (safe); the product JSON is ~83 MB — use the local copy instead
curl -sL "$BASE/api/delivery-reliability/download" \
  -H "X-API-Key: $VALIO_AIMO_API_KEY" -o delivery_reliability.csv
curl -sL "$BASE/api/carbon-footprint/download" \
  -H "X-API-Key: $VALIO_AIMO_API_KEY" -o carbon_footprint.csv

# 8. Refresh the OpenAPI spec (portal session cookie, root path — NOT /api/openapi.json)
curl -s -c /tmp/aimo.jar -X POST "$BASE/login" -d "password=$VALIO_AIMO_PORTAL_PASSWORD" -o /dev/null
curl -s -b /tmp/aimo.jar "$BASE/openapi.json" -o openapi.json
```

---

## 12. Live-verification log

14 API calls, 2026-11-13 ~22:18–22:22 EET. **No `429` observed.**

| # | Call | Result |
|---|---|---|
| 1 | `POST /login` + `GET /openapi.json` (cookie) | 303 + 200, 11 984 B spec |
| 2 | `POST /api/price`, 298 ids | 200, 194 354 B |
| 3 | `POST /api/availability`, 298 ids | 200, 56 650 B |
| 4 | `GET /api/ping` | 200 `{"status":"ok"}` |
| 5 | `POST /api/price` `{}` | 422, three `missing` errors |
| 6 | `POST /api/price` wrong types | 422, three type errors |
| 7 | `POST /api/price` `products: []` | 422 `too_short` |
| 8 | `POST /api/price` 1 001 ids | 422 `too_long`, full input echoed |
| 9–11 | three `*/download` | 307 each, `/files/<hash>/<name>` |
| 12 | `GET /api/ping` with no key | 401 `{"detail":"Invalid or missing API key"}` |
| — | `HEAD /files/...` ×2, no key (not `/api/*`) | 200 each |
| 13–14 | `POST /api/availability` re-run, 298 ids | 200, identical shape 4 min later |

**Retest, 2026-11-13 23:00.** 34 requests in under 5 minutes (23:00:06–23:04:47 EET), up to 251 ids each. **No `429` and no rate-limit headers** (response headers seen: `Date`, `Content-Type`, `Content-Length`, `Connection`, `Cache-Control`, `Server`, `x-robots-tag`, `cf-cache-status`, `CF-RAY`, and `allow` on the `405`).

| # | Call | Result |
|---|---|---|
| 1 | `GET /api/ping` | 200 |
| 2–9 | `POST /api/availability` and `POST /api/price`, 4 chunks each (250/250/250/251 ids): seeded random sample of 1,000 catalog ids plus the made-up id `459999` | 200 each |
| 10–11 | availability + price, 37 ids including the 7 deposit material codes | 200; the 7 codes return `scheduleLines: []` / `error: true` |
| 12–29 | availability + price, 24 ids × 4 dates (customer `123`) and × 5 further customer strings (date 2026-11-16) | 200 each; every per-product field identical (§8.6) |
| 30 | `GET /api/price` | 405 `{"detail":"Method Not Allowed"}`, `Allow: POST` |
| 31–34 | `GET /api/order`, `/api/orders`, `/api/quote`, `/api/basket` | 404 `{"detail":"Not Found"}` each; the spec declares no order operation |
