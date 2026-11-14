# Valio Aimo Junction 2026 API — field dictionary

Every field of every payload the six operations return, once, in one layout; depth lives in [API.md](API.md), [PRODUCT-DATA.md](PRODUCT-DATA.md), [SCHEMA-AND-CODES.md](SCHEMA-AND-CODES.md) and [CSV-DATASETS.md](CSV-DATASETS.md).

## 0. Legend

| Column | Content | Source |
|---|---|---|
| `Field path` | Dotted path, `[]` = array item; API objects: relative to the object named in the table heading; product JSON: full path from the product object (`$[]`), `[name=x]` = the classification group with that `name`; CSV: column header | spec / schema / file |
| `Type` | Declared JSON type; API fields not in the spec are typed as observed | `openapi.json` (3.1.0, API version 0.1.0) · `valio_aimo_junction26_product_data_schema.json` (draft 2020-12) |
| `Declared` | `required` = in the parent's `required` list · `optional` = not in it · `nullable` = spec type is `anyOf [T, null]` · `items` = array-item node · `not declared` = absent from the spec | spec / schema only; the JSON Schema declares no nullable type, `enum`, `format` or `additionalProperties` anywhere; the CSVs have no schema |
| `Actual` | What is on the wire or in the file | File payloads: measured 2026-11-13 by walking the complete local files (17,546 products; 4,425 and 11,033 CSV rows). API payloads: **observed on sample**, marked ◐ — `/api/price` and `/api/availability` figures come from a seeded random sample of 1,000 catalog ids (5.7% of the 17,546-product catalog) plus the made-up id `459999`, sent in 4 calls per endpoint on 2026-11-13 at 23:00 server time, together with a 24-id set repeated over 4 dates and 6 customer strings, a 37-id call and 5 `GET` probes from the same retest; ping, `422`, `401` and download rows come from the earlier captures of 2026-11-13 ~22:18; both are logged in [API §12](API.md#12-live-verification-log), and nothing was re-called for this page |
| `Values / format` | Closed value sets in full (frequency order), formats, units, sentinels; `not named in schema` = value occurs in the data but the schema text does not mention it; counts in parentheses | same as `Actual`; `declared:` prefixes a constraint taken from the spec |
| `Meaning` | Verbatim wording of the spec or schema in quotes; `—` = the source says nothing | `openapi.json` operation descriptions · schema `description` |
| `Ref` | Section holding the detail: API = API.md, PD = PRODUCT-DATA.md, SC = SCHEMA-AND-CODES.md, CSV = CSV-DATASETS.md | — |

File-wide facts (measured): the product file contains no JSON `null` and no duplicate key — an unset field is an absent key, an empty array or (rarely) `""`; every schema `number` is written as a float literal (`1.0`), every `integer` as an int; the ◐ captures contain no JSON `null` either.

## 1. Operations, auth and error envelopes

Base URL `https://junction26.valioaimo.fi` ([API §1](API.md#1-authentication)); the spec declares 6 operations, 11 component schemas and one security scheme.

### Operations

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `GET /api/ping` | no body → `200` schema `{}` | `ping_api_ping_get`; tag On-demand; security `APIKeyHeader` | ◐ `200`, `application/json`, body `{"status":"ok"}` | no body, no parameters | — (summary only: “Ping”) | [API §4](API.md#4-get-apiping) |
| `POST /api/availability` | body `ProductsRequest` → `200` `AvailabilityResponse`, `422` `HTTPValidationError` | `availability_api_availability_post`; tag On-demand; security `APIKeyHeader`; body required | ◐ `200` for each of 4 calls of 250–251 ids (44,960–47,705 B); unknown codes answered inside a `200` | request and response `application/json` | “Tells whether the products can be delivered on the requested date and how much is available.” | [API §6](API.md#6-post-apiavailability) · [API §12](API.md#12-live-verification-log) |
| `POST /api/price` | body `ProductsRequest` → `200` `PriceResponse`, `422` `HTTPValidationError` | `price_api_price_post`; tag On-demand; security `APIKeyHeader`; body required | ◐ `200` for each of 4 calls of 250–251 ids (162,932–166,164 B); `422` on invalid body; unknown codes answered inside a `200`; `GET` → `405` with `Allow: POST` | request and response `application/json` | “Returns the price of the products for the customer on the requested date.” | [API §5](API.md#5-post-apiprice) · [API §12](API.md#12-live-verification-log) |
| `GET /api/products/download` | no body → `200` schema `{}` | `product_data_download_link_api_products_download_get`; tag File downloads; security `APIKeyHeader` | ◐ `307`, empty body, `Location: /files/<32 hex>/valio_aimo_junction26_product_data.json` | target `application/json`, 87,077,467 B (= local copy) | “Provides product data file as JSON. Follow the redirect (curl -L).” | [API §9](API.md#9-file-download-endpoints) · [API §9.1](API.md#91-the-redirect-target-does-not-require-the-api-key) |
| `GET /api/delivery-reliability/download` | no body → `200` schema `{}` | `delivery_reliability_download_link_api_delivery_reliability_download_get`; tag File downloads; security `APIKeyHeader` | ◐ `307`, empty body, `Location: /files/<32 hex>/valio_aimo_junction26_delivery_reliability.csv`; `HEAD` on the target without the key returned `200` | target `text/csv; charset=utf-8`, 56,741 B (= local copy) | “Provides the delivery reliability file as CSV (productId, deliveryReliability). Follow the redirect (curl -L).” | [API §9](API.md#9-file-download-endpoints) |
| `GET /api/carbon-footprint/download` | no body → `200` schema `{}` | `carbon_footprint_download_link_api_carbon_footprint_download_get`; tag File downloads; security `APIKeyHeader` | ◐ `307`, empty body, `Location: /files/<32 hex>/valio_aimo_junction26_carbon_footprint.csv` | target `text/csv; charset=utf-8`; size not captured (local copy 156,990 B) | “Provides the carbon footprint file as CSV (productId, AVG kg CO2-eq/kg). Follow the redirect (curl -L).” | [API §9](API.md#9-file-download-endpoints) |

### Auth header — security scheme `APIKeyHeader`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `X-API-Key` | request header (string) | `type: apiKey`, `in: header`; listed in `security` of all 6 operations | ◐ missing or malformed key → `401` (next table); not accepted on `/docs`, `/redoc`, `/openapi.json` (session cookie there); not needed on `/files/...` targets (2 `HEAD` calls) | opaque string | — | [API §1](API.md#1-authentication) · [API §1.2](API.md#12-missing-or-invalid-key) · [API §1.3](API.md#13-portal-docs-use-a-different-credential) |

### Error body for `401` / `404` / `405` — not in the spec

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `detail` | `string` (observed) | not declared (spec lists only `200`, and `422` on the two POSTs) | ◐ `401` on `GET /api/ping` without a key; `404` on an unknown path (`/api/openapi.json`; `GET /api/order`, `/api/orders`, `/api/quote`, `/api/basket`); `405` on `GET /api/price` (header `Allow: POST`); `application/json` | `Invalid or missing API key` (401) · `Not Found` (404) · `Method Not Allowed` (405) | — | [API §1.2](API.md#12-missing-or-invalid-key) · [API §1.3](API.md#13-portal-docs-use-a-different-credential) |

### `HTTPValidationError` — body of `422`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `detail` | `ValidationError[]` | optional | ◐ present in all 4 captured `422` bodies; 1–3 items; every violated field reported in one response | array of `ValidationError` | — (spec `title` only: “Detail”) | [API §3.1](API.md#31-validation-errors--httpvalidationerror--validationerror) |

### `ValidationError` — `HTTPValidationError.detail[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `loc` | `(string or integer)[]` | required | ◐ present on all 8 captured errors; always `["body", <field>]` | path to the offending value | — (spec `title` only: “Location”) | [API §3.1](API.md#31-validation-errors--httpvalidationerror--validationerror) |
| `msg` | `string` | required | ◐ present on all 8 | human-readable English text | — (spec `title` only: “Message”) | [API §3.1](API.md#31-validation-errors--httpvalidationerror--validationerror) |
| `type` | `string` | required | ◐ present on all 8 | seen: `missing`, `string_type`, `list_type`, `too_short`, `too_long`, `date_from_datetime_parsing` | — (spec `title` only: “Error Type”) | [API §3.1](API.md#31-validation-errors--httpvalidationerror--validationerror) |
| `input` | `any` | optional | ◐ present on all 8; echoes the offending value (`{}` for missing fields; the whole 1,001-item array, ~9 KB, on `too_long`) | any JSON value | — (spec `title` only: “Input”) | [API §3.1](API.md#31-validation-errors--httpvalidationerror--validationerror) |
| `ctx` | `object` | optional | ◐ present on 3 of 8 (`too_short`, `too_long`, `date_from_datetime_parsing`); key absent on `missing`, `string_type`, `list_type` | keys seen: `field_type`, `min_length`, `max_length`, `actual_length`, `error` | — (spec `title` only: “Context”) | [API §3.1](API.md#31-validation-errors--httpvalidationerror--validationerror) |

## 2. `GET /api/ping`

The spec declares an empty response schema (`{}`); the one field below is known from a single captured call.

### Ping response — not in the spec

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `status` | `string` (observed) | not declared (response schema `{}`) | ◐ `{"status":"ok"}` with `200` (1 call) | `ok` | — | [API §4](API.md#4-get-apiping) · [API §12](API.md#12-live-verification-log) |

## 3. `POST /api/price`

◐ cells rest on the random sample of 1,000 catalog ids (all priced, `error: false`) plus the made-up id `459999` (`error: true`), 2026-11-13 23:00.

### `ProductsRequest` — request body of `/api/price` and `/api/availability`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `customer` | `string` | required | ◐ integer `123` → `422` `string_type` (no coercion); 6 different strings on a 24-id set → every per-product field identical | any string; spec example `"123"` | “In this challenge, however, customer number does not affect response so you can pass in whatever.” | [API §3](API.md#3-shared-request-schema--productsrequest) · [API §3.1](API.md#31-validation-errors--httpvalidationerror--validationerror) |
| `requestedDate` | `string` | required | ◐ `2026-11-16` accepted; `not-a-date` → `422` `date_from_datetime_parsing` (“Input should be a valid date or datetime…”); 4 dates (2025-06-01 … 2027-06-01) on a 24-id set → every per-product field identical, only the echoed date and `timeNow` differ | declared: `format: date` (`YYYY-MM-DD`) | /price: “(=the desired delivery date of the products)” · /availability: “(your desired delivery date)” | [API §3](API.md#3-shared-request-schema--productsrequest) · [API §3.1](API.md#31-validation-errors--httpvalidationerror--validationerror) |
| `products` | `string[]` | required | ◐ `[]` → `422` `too_short`; 1,001 items → `422` `too_long`; a string → `422` `list_type`; unknown codes accepted | declared: `minItems: 1`, `maxItems: 1000`; items are product-code strings (`$[].id`, 6 digits) | “Product codes to query, 1-1,000 per request” · “A longer list is rejected with HTTP 422.” | [API §3](API.md#3-shared-request-schema--productsrequest) · [API §3.1](API.md#31-validation-errors--httpvalidationerror--validationerror) |

### `PriceResponse` — `200` body

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `customerId` | `string` | required | ◐ echo of request `customer` (6 strings tried, e.g. `"123"`, `"åäö ravintola 12"`) | string | “The customer id from the request. Not meaningful in this challenge.” | [API §5.1](API.md#51-response--priceresponse) |
| `currency` | `string` | required | ◐ `EUR` in every capture | `EUR` | “Currency of all prices.” | [API §5.1](API.md#51-response--priceresponse) |
| `pricingDate` | `string` | required | ◐ request date at midnight: `2026-11-16T00:00:00+0200`; `2025-06-01` → `2025-06-01T00:00:00+0300` | `YYYY-MM-DDTHH:MM:SS+ZZZZ` (offset without colon) | “The date the prices apply to (the requested date).” | [API §5.1](API.md#51-response--priceresponse) |
| `products` | `ProductPrice[]` | required | ◐ one entry per requested id, in request order (4 calls, 1,001 ids) | array of `ProductPrice` | “One entry per requested product.” | [API §5.1](API.md#51-response--priceresponse) |

### `ProductPrice` — `PriceResponse.products[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `productId` | `string` | required | ◐ always present (1,001/1,001) | product code as requested, incl. unknown codes | — (no row in the spec's `/api/price` table) | [API §5.2](API.md#52-productprice) · [API §7.2](API.md#72-what-actually-happens-on-the-wire) |
| `quantity` | `number` | required | ◐ always present; `1.0` on 1,001/1,001 | `1.0` | “Quantity the price is for (always 1.0)” | [API §5.2](API.md#52-productprice) · [API §7.2](API.md#72-what-actually-happens-on-the-wire) |
| `catalogPrice` | `Price` | optional, nullable | ◐ key present on 1,000/1,001 = exactly the `error == false` entries; never `null` | `Price` object | “Price per sales unit before tax. `value` is without tax, `valueWithTax` with tax.” | [API §5.2](API.md#52-productprice) · [API §7.2](API.md#72-what-actually-happens-on-the-wire) |
| `priceWithTax` | `PriceWithTax` | optional, nullable | ◐ key present on 1,000/1,001 (`error == false`); never `null` | `PriceWithTax` object | “The price including tax, with its validity period.” | [API §5.2](API.md#52-productprice) · [API §7.2](API.md#72-what-actually-happens-on-the-wire) |
| `comparisonPrice` | `Price` | optional, nullable | ◐ key present on 794 of the 1,000 catalog ids; absent on 206 priced entries (20.6%) and on the error entry; never `null` | `Price` object | “Price per `comparisonUnit` (for example per kg) so products of different size can be compared.” | [API §5.2](API.md#52-productprice) · [API §7.2](API.md#72-what-actually-happens-on-the-wire) |
| `comparisonUnit` | `string` | optional, nullable | ◐ key present on 794 of the 1,000 catalog ids, exactly with `comparisonPrice`; never `null` | declared in text: `KG`, `L`; ◐ `KG` (636), `L` (158) | “Unit of the comparison price. Only KG (kilogram) and L (litre) are used” | [API §5.2](API.md#52-productprice) · [API §7.2](API.md#72-what-actually-happens-on-the-wire) |
| `tax` | `Tax` | optional, nullable | ◐ key present on 1,000/1,001 (`error == false`); never `null` | `Tax` object | “`taxRate` (percent) and `taxValue` (the tax amount in currency).” | [API §5.2](API.md#52-productprice) · [API §7.2](API.md#72-what-actually-happens-on-the-wire) |
| `listPrice` | `Price` | optional, nullable | ◐ key present on 1,000/1,001 (`error == false`); never `null` | `Price` object | “Price before the customer-specific price or discount” | [API §5.2](API.md#52-productprice) · [API §7.2](API.md#72-what-actually-happens-on-the-wire) |
| `netPriceFound` | `boolean` | required | ◐ always present; `true` on 13 of 1,000 | `true`, `false` | “True when a customer-specific net price was found, false when the catalog price was used” | [API §5.2](API.md#52-productprice) · [API §7.2](API.md#72-what-actually-happens-on-the-wire) |
| `error` | `boolean` | required | ◐ always present; `false` on all 1,000 catalog ids; `true` on the made-up id `459999` (and on the 7 deposit material codes in the 37-id call), leaving only `productId`, `quantity`, `netPriceFound`, `error` | `true`, `false` | “True when no price could be found for the product” | [API §5.2](API.md#52-productprice) · [API §7.2](API.md#72-what-actually-happens-on-the-wire) |

### `Price` — `ProductPrice.catalogPrice`, `.comparisonPrice`, `.listPrice`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `value` | `number` | required | ◐ present in every captured `Price` | amount **excluding** tax, in `currency` | “Price per sales unit before tax. `value` is without tax, `valueWithTax` with tax.” (stated for `catalogPrice`) | [API §5.3](API.md#53-price-used-by-catalogprice-comparisonprice-listprice) · [API §8.9](API.md#89-other-wire-level-gotchas) |
| `valueWithTax` | `number` | required | ◐ present in every captured `Price` | amount **including** tax, in `currency` | “Price per sales unit before tax. `value` is without tax, `valueWithTax` with tax.” (stated for `catalogPrice`) | [API §5.3](API.md#53-price-used-by-catalogprice-comparisonprice-listprice) · [API §8.9](API.md#89-other-wire-level-gotchas) |
| `validFrom` | `string` | required | ◐ present in every captured `Price` | `YYYY-MM-DDTHH:MM:SS+ZZZZ` (offset without colon); offsets `+0200` and `+0300` seen | “Period on which the price is valid” | [API §5.3](API.md#53-price-used-by-catalogprice-comparisonprice-listprice) · [API §8.9](API.md#89-other-wire-level-gotchas) |
| `validTo` | `string` | required | ◐ present in every captured `Price` | `YYYY-MM-DDTHH:MM:SS+ZZZZ` (offset without colon); open-ended sentinel `9999-12-31T00:00:00+0200` | “Period on which the price is valid” | [API §5.3](API.md#53-price-used-by-catalogprice-comparisonprice-listprice) · [API §8.9](API.md#89-other-wire-level-gotchas) |
| `currency` | `string` | required | ◐ `EUR` | `EUR` | — (response level: “Currency of all prices.”) | [API §5.3](API.md#53-price-used-by-catalogprice-comparisonprice-listprice) · [API §8.9](API.md#89-other-wire-level-gotchas) |

### `PriceWithTax` — `ProductPrice.priceWithTax`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `value` | `number` | required | ◐ present in every captured `PriceWithTax`; equals `catalogPrice.valueWithTax` on 1,000 of 1,000 | amount **including** tax (no `valueWithTax` key in this object) | “The price including tax, with its validity period.” | [API §5.4](API.md#54-pricewithtax-used-by-pricewithtax-only) |
| `validFrom` | `string` | required | ◐ present in every captured `PriceWithTax` | `YYYY-MM-DDTHH:MM:SS+ZZZZ` (offset without colon) | “Period on which the price is valid” | [API §5.4](API.md#54-pricewithtax-used-by-pricewithtax-only) |
| `validTo` | `string` | required | ◐ present in every captured `PriceWithTax` | `YYYY-MM-DDTHH:MM:SS+ZZZZ` (offset without colon); sentinel `9999-12-31T00:00:00+0200` | “Period on which the price is valid” | [API §5.4](API.md#54-pricewithtax-used-by-pricewithtax-only) |
| `currency` | `string` | required | ◐ `EUR` | `EUR` | — | [API §5.4](API.md#54-pricewithtax-used-by-pricewithtax-only) |

### `Tax` — `ProductPrice.tax`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `taxRate` | `number` | required | ◐ present in every captured `Tax` | percent; ◐ `13.5` (783), `25.5` (217) | “`taxRate` (percent) and `taxValue` (the tax amount in currency).” | [API §5.5](API.md#55-tax) · [API §8.8](API.md#88-taxtaxrate-is-authoritative-over-the-files-vatcode) |
| `taxValue` | `number` | required | ◐ present in every captured `Tax` | amount in `currency` | “`taxRate` (percent) and `taxValue` (the tax amount in currency).” | [API §5.5](API.md#55-tax) · [API §8.8](API.md#88-taxtaxrate-is-authoritative-over-the-files-vatcode) |

## 4. `POST /api/availability`

Request body is `ProductsRequest` (§3); ◐ cells rest on the random sample of 1,000 catalog ids (797 entries with a schedule line, 203 without) plus the made-up id `459999`, 2026-11-13 23:00.

### `AvailabilityResponse` — `200` body

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `timeNow` | `string` | required | ◐ `2026-11-13T23:00:16+0200` … `2026-11-13T23:00:35+0200` over the 4 calls | `YYYY-MM-DDTHH:MM:SS+ZZZZ` (offset without colon) | “Server time when the answer was produced (Helsinki time).” | [API §6.1](API.md#61-response--availabilityresponse) |
| `requestedDate` | `string` | required | ◐ `2026-11-16T00:00:00+0200` for request `2026-11-16` | `YYYY-MM-DDTHH:MM:SS+ZZZZ` (offset without colon); note the request field of the same name is `YYYY-MM-DD` | “The date from the request, at midnight.” | [API §6.1](API.md#61-response--availabilityresponse) |
| `products` | `ProductAvailability[]` | required | ◐ one entry per requested id, in request order (4 calls, 1,001 ids) | array of `ProductAvailability` | “One entry per requested product, in request order.” | [API §6.1](API.md#61-response--availabilityresponse) |

### `ProductAvailability` — `AvailabilityResponse.products[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `productId` | `string` | required | ◐ always present (1,001/1,001) | product code as requested, incl. unknown codes | “The product code.” | [API §6.2](API.md#62-productavailability) |
| `closingTime` | `string` | optional, nullable | ◐ key present on 797 of 1,000, absent on the 203 entries with `scheduleLines: []`; never `null`; earlier than `timeNow` on 425 of 797 (Terminal 357 of 357, Stock 68 of 440) | `YYYY-MM-DDTHH:MM:SS+ZZZZ` (offset without colon); ◐ 14 distinct values (12 on Terminal, 2 on Stock), `2026-11-11T13:00:00+0200` … `2026-11-15T17:00:00+0200` | “The order cut-off time (= order by closingTime at the latest to receive goods on availableDate)” | [API §6.2](API.md#62-productavailability) · [API §8.7](API.md#87-closingtime-has-often-already-passed-especially-on-terminal-products) |
| `salesBlock` | `boolean` | required | ◐ always present; `true` on 1 of 1,000 (`470094`), `false` on 999 | `true`, `false` | “If true, Product cannot be ordered currently” | [API §6.2](API.md#62-productavailability) · [API §8.3](API.md#83-salesblock-is-rarely-true) |
| `logisticModel` | `string` | optional, nullable | ◐ key present on 797 of 1,000, absent on the same 203 entries; never `null` | ◐ `Stock` (440), `Terminal` (357) | “Stock products are stocked by us, so we know their available quantities. Terminal products are delivered from supplier's warehouses and we don't know the actual available quantities” | [API §6.2](API.md#62-productavailability) · [API §7.2](API.md#72-what-actually-happens-on-the-wire) |
| `scheduleLines` | `ScheduleLine[]` | required | ◐ always present; length 0 on 203 of 1,000 (20.3%), length 1 on 797 | array of `ScheduleLine` | “If product is available, array has exactly one entry. Empty array means product cannot currently be delivered on any date” | [API §6.2](API.md#62-productavailability) · [API §8.4](API.md#84-empty-schedulelines-is-the-real-undeliverable-signal) |

### `ScheduleLine` — `ProductAvailability.scheduleLines[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `salesBlock` | `boolean` | required | ◐ always present; `true` on 1 of 797 (`470094`), `false` on 796 | `true`, `false` | “If true, product cannot be ordered currently” | [API §6.3](API.md#63-scheduleline) · [API §8.3](API.md#83-salesblock-is-rarely-true) |
| `availableAmount` | `number` | required | ◐ always present (797/797); Terminal: `999999.0` on 357 of 357; Stock (440): `0.0` on 29, a placeholder equal to floor(9,999,999,999 ÷ `sizeInBaseUnits` of the sales unit) on 92, whole-number quantities 1 … 7,389 on 319 | in `salesUnit`; declared in text: `999999` (Terminal, unknown), `0` (not available); ◐ Stock placeholder: 9 distinct values, `9999999999.0` (81) … `416666666.0`; `availableAmount >= 999_999` detects both placeholders | “Quantity available, in `salesUnit`. For Terminal products this is always 999999 since actual value is not known. 0 means not available.” | [API §6.3](API.md#63-scheduleline) · [API §8.1](API.md#81-availableamount-placeholders-two-rules) · [CSV §1 live test](CSV-DATASETS.md#what-00-means-in-practice--tested-against-the-live-api) |
| `availableDate` | `string` | optional, nullable | ◐ key present on 768 of 797, absent on exactly the 29 lines with `availableAmount == 0.0`; never `null` | `YYYY-MM-DD` (date only); ◐ `2026-11-16` on 767 of 768, `2026-12-30` on 1 (`470094`) | “Earliest date when amount is available. Note that this might differ from your requestedDate” | [API §6.3](API.md#63-scheduleline) · [API §8.2](API.md#82-availableamount--0-is-a-third-unavailable-state) |
| `salesUnit` | `string` | required | ◐ always present (797/797); differs from the product file's `$[].salesUnit` on 7 of 797 (e.g. `460657`: file `KI`, API `ST`) | packaging unit code as in `$[].salesUnit`; ◐ `KI` (353), `ST` (253), `KG` (47), `PAK` (47), `BAG` (41), `PRK` (16), `BOT` (15), `SK` (9), `RAS` (6), `CS` (5), `KLE` (5) | “Technical code of sales unit” | [API §6.3](API.md#63-scheduleline) |

## 5. File downloads

HTTP behaviour of the three `GET .../download` operations is in §1 (declared `200`, ◐ `307` to an unauthenticated `/files/...` URL); the payload schemas follow.

### 5.1 Product JSON — `valio_aimo_junction26_product_data.json`

Single JSON array, 87,077,467 bytes, 17,546 products; the schema and the data contain the same 148 paths (root included), every schema-`required` key is present on every parent object and every value has its declared JSON type.

#### Product object — `$[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `$` | `array<object>` | root (`type: array`) | 17,546 items, all objects; ascending `id` | UTF-8 JSON | “Static product information” | [PD §1](PRODUCT-DATA.md#1-top-level-field-reference) · [SC §1.1](SCHEMA-AND-CODES.md#11-top-level) |
| `$[]` | `object` | items | 17,546 objects; 11–14 keys each; 6 distinct key sets | object | “One product.” | [PD §1](PRODUCT-DATA.md#1-top-level-field-reference) · [SC §1.2](SCHEMA-AND-CODES.md#12-product-object) |
| `allowedLotSize` | `number` | required | always present | `0.01` … `25.0` sales units; 73 distinct; `0.01` on 16,872 | “Smallest quantity step the product can be ordered in (order quantity must be a multiple of it), in sales units.” | [PD §4 allowedLotSize](PRODUCT-DATA.md#allowedlotsize--73-distinct-values) · [SC §2.12](SCHEMA-AND-CODES.md#212-allowedlotsize--documented-in-schema) |
| `baseUnit` | `string` | required | always present; matches exactly one `units[].unitId` row, whose `sizeInBaseUnits` is `1.0`, on every product | `ST`, `PAK`, `KI`, `BAG`, `KG`, `BOT`, `PRK`, `RAS`, `SK`, `CS`, `KRT`, `KAN`, `PAL`, `NIP`, `DSP`, `DZ` | “Base unit of measure of the product. Unit codes such as KI are technical codes and their translations are not included in this data set.” | [PD §4 baseUnit](PRODUCT-DATA.md#baseunit--16-values-same-space-minus-kle) · [SC §2.11](SCHEMA-AND-CODES.md#211-salesunit--baseunit--unitsunitid--undocumented-by-design) |
| `category` | `string` | required | always present | 349 codes, each exactly 5 digits | “Product category code. Category names are not part of this data set.” | [PD §4 category](PRODUCT-DATA.md#category--349-codes) · [SC §2.14](SCHEMA-AND-CODES.md#214-category--undocumented-by-design) · [SC §5.1](SCHEMA-AND-CODES.md#51-the-30-largest-categories) |
| `countryOfOrigin` | `string` | optional | key present on 17,537 of 17,546 products (99.95%), absent on 9 | 97 distinct, each 2 lowercase letters; not ISO 3166-1 codes: `zy` (179), `xs` (11), `zz` (5) | “Country of origin as a lowercase ISO 3166-1 alpha-2 code, for example fi or de.” | [PD §4 countryOfOrigin](PRODUCT-DATA.md#countryoforigin--97-values-9-products-missing) · [SC §2.15](SCHEMA-AND-CODES.md#215-countryoforigin--documented-in-schema-iso-3166-1-alpha-2-lowercase) |
| `deleted` | `boolean` | required | always present | `false` on all 17,546 | “True if the product has been deleted. Products are only included in this file if they are not deleted, so the value is always false.” | [PD §1](PRODUCT-DATA.md#1-top-level-field-reference) |
| `deposits` | `array<object>` | required | always present; `[]` on 17,040 of 17,546 (97.12%); length 0–2 | array of deposit items | “Deposit (returnable packaging) items that are charged together with the product.” | [PD §1 deposits[]](PRODUCT-DATA.md#deposits--506-products-576-rows) |
| `id` | `string` | required | always present; 17,546 distinct (unique); file is in ascending `id` order | exactly 6 ASCII digits, `460000` … `477545`, none with a leading zero; keep as string | “Product code. Use it as the product id in the API requests and in the other data files.” | [PD §1](PRODUCT-DATA.md#1-top-level-field-reference) · [CSV §6](CSV-DATASETS.md#6-join-recipes) |
| `salesUnit` | `string` | required | always present; matches exactly one `units[].unitId` row on every product; equals `baseUnit` on 10,924 | `KI`, `ST`, `KG`, `PAK`, `BAG`, `RAS`, `PRK`, `BOT`, `SK`, `CS`, `KLE`, `KRT`, `KAN`, `PAL`, `NIP`, `DSP`, `DZ` | “Unit of measure the product is sold in. Unit codes such as KI are technical codes and their translations are not included in this data set.” | [PD §4 salesUnit](PRODUCT-DATA.md#salesunit--17-values-complete) · [SC §2.11](SCHEMA-AND-CODES.md#211-salesunit--baseunit--unitsunitid--undocumented-by-design) |
| `salesUnitGtin` | `string` | optional | key present on 17,387 of 17,546 products (99.09%), absent on 159; equals `units[unitId == salesUnit].gtin` on 17,387 of 17,387 | digits only, length 8, 12, 13 or 14; 17,387 distinct (no duplicates) | “GTIN (barcode number) of the sales unit. Not all products have one” | [PD §1](PRODUCT-DATA.md#1-top-level-field-reference) · [PD §8 #14](PRODUCT-DATA.md#8-parsing-pitfalls-specific-to-this-file) |
| `substitutions` | `array<object>` | optional | key present on 196 of 17,546 products (1.12%), absent on 17,350; `[]` on 7 of 196 (3.57%); length 0–5 | array of substitution rules | “Products that can replace this product when it is not available.” | [PD §1 substitutions[]](PRODUCT-DATA.md#substitutions--250-rows) · [PD §6](PRODUCT-DATA.md#6-substitution-data--all-250-pairs) |
| `temperatureCondition` | `integer` | optional | key present on 17,485 of 17,546 products (99.65%), absent on 61 | `1` … `9`; by frequency: `8`, `7`, `4`, `3`, `2`, `1`, `5`, `6`, `9`; meanings not in the data | “Code of the temperature (storage and transport) class of the product, e.g. ambient, chilled or frozen. Code meanings are not part of this data set.” | [PD §4 temperatureCondition](PRODUCT-DATA.md#temperaturecondition--9-values-key-absent-on-61-products) · [SC §2.13](SCHEMA-AND-CODES.md#213-temperaturecondition--undocumented-but-decodable-from-the-data) |
| `units` | `array<object>` | required | always present; never `[]`; length 1–8 | array of packaging units | “Packaging hierarchy of the product: the units it can be handled in, each with its own barcode.” | [PD §1 units[]](PRODUCT-DATA.md#units--packaging-hierarchy-44357-rows-total) |
| `vendorName` | `string` | required | always present | free text; 648 distinct; length 5–35 | “Name of the vendor (supplier) of the product.” | [PD §4 vendorName](PRODUCT-DATA.md#vendorname--648-distinct-top-20) |

#### `units[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `units[]` | `object` | items | 44,357 items on 17,546 products; no repeated `unitId` within a product | object | “One packaging unit.” | [PD §1 units[]](PRODUCT-DATA.md#units--packaging-hierarchy-44357-rows-total) |
| `units[].gtin` | `string` | optional | key present on 35,881 of 44,357 objects (80.89%), absent on 8,476 | digits only, length 8, 12, 13 or 14; 35,881 distinct (no duplicates in the file) | “GTIN (barcode number) of the unit.” | [PD §1 units[]](PRODUCT-DATA.md#units--packaging-hierarchy-44357-rows-total) |
| `units[].sizeInBaseUnits` | `number` | required | always present (44,357 objects); `0.0` on 1 row (product `476872`, unit `ZML`) | `0.0` … `56000.0` base units; 655 distinct | “How many base units the unit contains.” | [PD §1 units[]](PRODUCT-DATA.md#units--packaging-hierarchy-44357-rows-total) · [PD §5 tier 2](PRODUCT-DATA.md#tier-2--static-fields-in-this-file) |
| `units[].unitId` | `string` | required | always present (44,357 objects) | `KI`, `ST`, `PAL`, `KRS`, `PAK`, `BAG`, `KG`, `BOT`, `PRK`, `RAS`, `CS`, `SK`, `KRT`, `KLE`, `ZML`, `DOL`, `KAN`, `DSP`, `KOR`, `NIP`, `PNT`, `DZ`, `MDO` | “Code of the unit. Unit codes such as KI are technical codes and their translations are not included in this data set.” | [PD §4 units[].unitId](PRODUCT-DATA.md#unitsunitid--23-values-superset-of-the-two-above) · [SC §2.11](SCHEMA-AND-CODES.md#211-salesunit--baseunit--unitsunitid--undocumented-by-design) |

#### `deposits[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `deposits[]` | `object` | items | 576 items on 506 products | object | “One deposit item.” | [PD §1 deposits[]](PRODUCT-DATA.md#deposits--506-products-576-rows) |
| `deposits[].material` | `string` | required | always present (576 objects); 0 of 576 values equal a product `id` | `1`, `4`, `3`, `171`, `147`, `2`, `9708918` | “Product code of the deposit material.” | [PD §1 deposits[]](PRODUCT-DATA.md#deposits--506-products-576-rows) · [SC §2.19](SCHEMA-AND-CODES.md#219-deposit-material-codes--undocumented-and-unresolvable) |
| `deposits[].quantity` | `number` | required | always present (576 objects) | `1.0`, `2.0`, `4.0`, `6.0`, `8.0`, `12.0`, `16.0`, `18.0`, `20.0`, `24.0`, `30.0` | “Number of deposit units charged per sales unit of the product.” | [PD §1 deposits[]](PRODUCT-DATA.md#deposits--506-products-576-rows) |
| `deposits[].unit` | `string` | required | always present (576 objects) | `ST` on all rows | “Unit of the deposit quantity, for example ST (piece). Unit codes such as KI are technical codes and their translations are not included in this data set.” | [PD §1 deposits[]](PRODUCT-DATA.md#deposits--506-products-576-rows) |

#### `substitutions[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `substitutions[]` | `object` | items | 250 items on 189 products | object | “One substitution rule.” | [PD §1 substitutions[]](PRODUCT-DATA.md#substitutions--250-rows) |
| `substitutions[].product` | `string` | required | always present (250 objects); equals the owning product's `id` on 250 of 250 | product code (6 digits); 189 distinct | “Product code of the product being substituted.” | [PD §1 substitutions[]](PRODUCT-DATA.md#substitutions--250-rows) |
| `substitutions[].substituteProduct` | `string` | required | always present (250 objects); 250 of 250 are catalog `id`s; 1 row names its own product | product code (6 digits); 218 distinct | “Product code of the product that can be offered instead.” | [PD §1 substitutions[]](PRODUCT-DATA.md#substitutions--250-rows) · [PD §6](PRODUCT-DATA.md#6-substitution-data--all-250-pairs) |

#### `synkkaData`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `synkkaData` | `object` | required | always present; never `{}`; 7–8 keys on 3,068 products (those without `synkkaData.gtin`), 21–25 keys on 14,478 | object | “Product information supplied by the manufacturer through the GS1 Synkka product data service. Quantity and quality vary between products, so most fields can be missing.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) · [SC §1.3](SCHEMA-AND-CODES.md#13-synkkadata) |
| `synkkaData.brand` | `string` | optional | key present on 14,463 of 17,546 products (82.43%), absent on 3,083; leading/trailing whitespace on 168 | free text; 1,500 distinct raw strings (1,465 after trimming); length 2–53 | “Brand of the product.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.classifications` | `array<object>` | required | always present; `[]` on 11 of 17,546 (0.06%); length 0–10; groups per product: 0 on 11, 5 on 2,337, 6 on 731, 10 on 14,467; no repeated `name` within a product | array of classification groups | “Classifications of the product, grouped by name: nutrition values, allergens, labels, claims and packaging.” | [PD §3](PRODUCT-DATA.md#3-synkkadataclassifications-in-depth) · [SC §1.4](SCHEMA-AND-CODES.md#14-classifications--the-generic-container-holding-most-code-systems) |
| `synkkaData.countriesOfOrigin` | `array<string>` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068; `[]` on 15 of 14,478 (0.10%); length 0–10 | array of country-code strings | “Countries of origin as numeric ISO 3166-1 codes, for example 246 for Finland.” | [SC §2.16](SCHEMA-AND-CODES.md#216-countriesoforigin--documented-in-schema-iso-3166-1-numeric) |
| `synkkaData.countriesOfOrigin[]` | `string` | items | 14,653 items on 14,463 products | 102 distinct; 3-character zero-padded digit strings (`246`, `056`); non-numeric: `NON_EU` (10) | “A numeric ISO 3166-1 country code.” | [SC §2.16](SCHEMA-AND-CODES.md#216-countriesoforigin--documented-in-schema-iso-3166-1-numeric) |
| `synkkaData.disposalInformations` | `array<object>` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068; `[]` on 9,845 of 14,478 (68.00%); length 0–3 | array of `{language, value}` | “Instructions for recycling or disposing of the packaging in several languages.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.fishingReports` | `array<object>` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068; `[]` on 14,125 of 14,478 (97.56%); length 0–3 | array of species reports | “Catch information of fish products.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) · [SC §1.7](SCHEMA-AND-CODES.md#17-fishingreports-and-safetydata) |
| `synkkaData.gtin` | `string` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068; equals `units[unitId == baseUnit].gtin` on 13,561 of 14,478; equals `salesUnitGtin` on 7,605 of 14,472 having both | digits only, length 8, 11, 12, 13 or 14; 14,451 distinct (not unique) | “GTIN (barcode number) of the consumer unit.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) · [PD §8 #14](PRODUCT-DATA.md#8-parsing-pitfalls-specific-to-this-file) |
| `synkkaData.ingredients` | `array<object>` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068; `[]` on 10,732 of 14,478 (74.13%); length 0–1 | array holding at most one ingredient object | “Ingredients in structured form, in order of the ingredient list.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) · [SC §1.3](SCHEMA-AND-CODES.md#13-synkkadata) |
| `synkkaData.keyIngredients` | `array<object>` | required | always present; `[]` on 3,499 of 17,546 (19.94%); length 0–9 | array of `{language, value}` | — (schema misspells the keyword as `descrption`: “Ingredient statement or main ingredients of the product in different languages”) | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.lastUpdated` | `string` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068 | `YYYY-MM-DDTHH:MM:SS+ZZZZ` (offset without colon); `+0300` on 13,623, `+0200` on 855; 2022-10-22 … 2025-10-05 | “Time the product information was last updated, as an ISO 8601 timestamp.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.marketingTexts` | `array<object>` | required | always present; `[]` on 5,631 of 17,546 (32.09%); length 0–3 | array of `{language, value}` | “Marketing description of the product in several languages.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) · [SC §1.3](SCHEMA-AND-CODES.md#13-synkkadata) |
| `synkkaData.materialAdditionalDescriptions` | `array<object>` | required | always present; `[]` on 17,535 of 17,546 (99.94%); length 0–21 | array of `{language, value}` | “Additional description of the product, for example the contents of a multipack in several languages.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) · [SC §1.3](SCHEMA-AND-CODES.md#13-synkkadata) |
| `synkkaData.maxTemperature` | `number` | optional | key present on 10,266 of 17,546 products (58.51%), absent on 7,280; present without `minTemperature` on 182 | `-25.0` … `100.0` °C; 40 distinct | “Maximum storage temperature in degrees Celsius.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.medias` | `array<object>` | required | always present; `[]` on 4,171 of 17,546 (23.77%); length 0–83; items with `primary == true` per non-empty array: 0 on 1,394, 1 on 8,959, 2 or more on 3,022 | array of `{id, primary}` | “Images and other media of the product. The files themselves are not part of this data set.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) · [PD §8 #25](PRODUCT-DATA.md#8-parsing-pitfalls-specific-to-this-file) |
| `synkkaData.mediasLastUpdated` | `string` | optional | key present on 13,375 of 17,546 products (76.23%), absent on 4,171; present exactly on the products whose `medias` is non-empty | `YYYY-MM-DDTHH:MM:SS+ZZZZ`; `+0300` on 12,284, `+0200` on 1,091; 2023-05-25 … 2025-10-10 | “Time the images and other media were last updated, as an ISO 8601 timestamp.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.minTemperature` | `number` | optional | key present on 10,156 of 17,546 products (57.88%), absent on 7,390; present without `maxTemperature` on 72; never greater than `maxTemperature` | `-60.0` … `70.0` °C; 43 distinct | “Minimum storage temperature in degrees Celsius.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.names` | `array<object>` | required | always present; never `[]`; length 1–5; no repeated `language` within a product | array of `{language, value}` | “Product name in several languages.” | [PD §2.1](PRODUCT-DATA.md#21-names--the-one-near-complete-text-field) |
| `synkkaData.nutritionalContent` | `array<object>` | required | always present; `[]` on 5,295 of 17,546 (30.18%); length 0–38 | array of nutrient rows | “Nutrition declaration of the product.” | [PD §2.2](PRODUCT-DATA.md#22-nutritionalcontent-12251-products-114754-rows) · [SC §1.5](SCHEMA-AND-CODES.md#15-nutritionalcontent) |
| `synkkaData.preparationInstructions` | `array<object>` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068; `[]` on 10,998 of 14,478 (75.96%); length 0–3 | array of `{language, value}` | “Instructions for preparing the product in several languages.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.producers` | `array<object>` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068; `[]` on 11 of 14,478 (0.08%); length 0–1 | array holding at most one producer | “Producers of the product.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.safetyData` | `array<object>` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068; `[]` on 13,811 of 14,478 (95.39%); length 0–1 | array holding at most one sheet | “Safety data of hazardous products.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) · [SC §1.7](SCHEMA-AND-CODES.md#17-fishingreports-and-safetydata) |
| `synkkaData.storageInstructions` | `array<object>` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068; `[]` on 5,812 of 14,478 (40.14%); length 0–3 | array of `{language, value}` | “Instructions for storing the product in several languages.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.unitConversions` | `array<object>` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068; `[]` on 4 of 14,478 (0.03%); length 0–1 | array holding at most one packaging level | “Weights and dimensions of each packaging level of the product.” | [PD §5 tier 2](PRODUCT-DATA.md#tier-2--static-fields-in-this-file) · [SC §1.6](SCHEMA-AND-CODES.md#16-unitconversions) |
| `synkkaData.usageInstructions` | `array<object>` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068; `[]` on 10,784 of 14,478 (74.49%); length 0–3 | array of `{language, value}` | “Instructions for using the product in several languages.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.variableUnit` | `boolean` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068 | `false` (13,846), `true` (632) | “True if the product is sold by variable weight, so that the actual quantity of a unit varies.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) · [PD §8 #12](PRODUCT-DATA.md#8-parsing-pitfalls-specific-to-this-file) |
| `synkkaData.vatCode` | `string` | optional | key present on 14,478 of 17,546 products (82.51%), absent on 3,068; `""` on 4 | `MEDIUM`, `STANDARD`, `LOW`; not named in schema: `MEDIUM MEDIUM` (159), `""` (4), `NOT_APPLICABLE` (1), `STANDARD MEDIUM` (1) | “VAT class of the product in Finland: STANDARD (25.5 %), MEDIUM (reduced rate for food, 13.5 %) or LOW (reduced rate, 10 %). The official source of truth is tax.taxRate of the price API.” | [PD §4 vatCode](PRODUCT-DATA.md#synkkadatavatcode--dirty-do-not-parse) · [SC §2.9](SCHEMA-AND-CODES.md#29-vatcode--documented-in-schema-data-violates-it) |

#### `synkkaData.classifications[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `synkkaData.classifications[]` | `object` | items | 160,741 items on 17,535 products | object | “One classification group.” | [PD §3](PRODUCT-DATA.md#3-synkkadataclassifications-in-depth) · [SC §1.4](SCHEMA-AND-CODES.md#14-classifications--the-generic-container-holding-most-code-systems) |
| `synkkaData.classifications[].name` | `string` | required | always present (160,741 objects) | `packagingMarkedLabel`, `allergen`, `nonAllergen`, `nutritionalClaim`, `packaging`, `nutritionFact`, `gda`; not named in schema: `composition` (14,467), `mineral` (14,467), `vitamin` (14,467) | “Name of the group, for example allergen, nonAllergen, nutritionFact, gda, nutritionalClaim, packaging or packagingMarkedLabel.” | [SC §1.4](SCHEMA-AND-CODES.md#14-classifications--the-generic-container-holding-most-code-systems) |
| `synkkaData.classifications[].type` | `string` | required | always present (160,741 objects); fixed per `name` (see group table) | `ENUM`, `DECIMAL` | “Type of the values in the group: ENUM for codes or DECIMAL for numbers.” | [SC §2.20](SCHEMA-AND-CODES.md#220-other-small-vocabularies) |
| `synkkaData.classifications[].values` | `array<object>` | required | always present (160,741 objects); `[]` on 97,263 of 160,741 (60.51%); length 0–33 | array of group values | “Values of the group.” | [SC §1.4](SCHEMA-AND-CODES.md#14-classifications--the-generic-container-holding-most-code-systems) |
| `synkkaData.classifications[].values[]` | `object` | items | 349,777 items on 17,296 products; key sets seen: `id` · `id,synkkaId` · `id,unit` · `id,synkkaId,unit` · `id,unit,value` | object | “One value of the group.” | [SC §1.4](SCHEMA-AND-CODES.md#14-classifications--the-generic-container-holding-most-code-systems) |
| `synkkaData.classifications[].values[].id` | `string` | required | always present (349,777 objects) | 120 distinct across all groups; per-group sets in the group table | “Internal feature id” | [SC §1.4](SCHEMA-AND-CODES.md#14-classifications--the-generic-container-holding-most-code-systems) |
| `synkkaData.classifications[].values[].synkkaId` | `string` | optional | key present on 25,695 of 349,777 objects (7.35%), absent on 324,082; only in `nutritionalClaim` (19,475 of 19,475 values) and `packagingMarkedLabel` (6,220 of 23,582) | 37 distinct UPPER_SNAKE tokens | “Synkka id” | [SC §2.4](SCHEMA-AND-CODES.md#24-nutritionalclaim-ids--self-describing) · [SC §2.5](SCHEMA-AND-CODES.md#25-packagingmarkedlabel-ids--self-describing) |
| `synkkaData.classifications[].values[].unit` | `string` | optional | key present on 326,195 of 349,777 objects (93.26%), absent on 23,582; absent on all 23,582 `packagingMarkedLabel` values, present on every other value | `GRM`, `FREE_FROM`, `KJO`, `CONTAINS`; not named in schema: `E14` (23,445), `MAY_CONTAIN` (9,956), `DIET` (5,334), `MGM` (3,434), `MC` (905), `HIGH` (823), `LOW` (820), `NO_ADDED` (662), `UNDECLARED` (303) | “Unit of the value, for example GRM (gram) or KJO (kilojoule). For allergens it tells how the allergen relates to the product: CONTAINS or FREE_FROM.” | [SC §2.2](SCHEMA-AND-CODES.md#22-allergen-unit-the-relation-qualifier--partially-documented) · [SC §2.7](SCHEMA-AND-CODES.md#27-measurement-unit-codes--documented-in-schema-unece-rec-20) |
| `synkkaData.classifications[].values[].value` | `number` | optional | key present on 212,254 of 349,777 objects (60.68%), absent on 137,523; present on every value of the five `DECIMAL` groups and on no value of the `ENUM` groups | `0.0` … `27000.0` in the value's `unit`; 3,878 distinct | “Numeric value, in the unit given.” | [PD §3.6](PRODUCT-DATA.md#36-decimal-groups) |

#### `synkkaData.classifications[]` by group `name`

Pseudo-paths: one row per value of `name`, describing that group's `values[]`.

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `synkkaData.classifications[name=allergen].values[]` | `ENUM` | named in the schema `description` | group present on 17,535 products; `values` non-empty on 7,205; 25,869 values; value keys: `id,unit` | `id`: 44 distinct codes (list in Ref); `unit`: `CONTAINS` (15,610), `MAY_CONTAIN` (9,956), `UNDECLARED` (303); 5 ids occur only here: `ABD`, `ADQ`, `BP`, `CM`, `NP` | — | [PD §3.1](PRODUCT-DATA.md#31-allergen--7205-products-44-ids-four-qualifier-states) · [SC §2.1](SCHEMA-AND-CODES.md#21-allergen-ids--undocumented-gs1-allergentypecode) · [SC §2.2](SCHEMA-AND-CODES.md#22-allergen-unit-the-relation-qualifier--partially-documented) · [SC §3.3](SCHEMA-AND-CODES.md#33-the-table) |
| `synkkaData.classifications[name=nonAllergen].values[]` | `ENUM` | named in the schema `description` | group present on 17,535 products; `values` non-empty on 5,119; 68,597 values; value keys: `id,unit` | `id`: 40 distinct codes (list in Ref); `unit`: `FREE_FROM` (68,597); 1 id occurs only here: `UN` | — | [PD §3.2](PRODUCT-DATA.md#32-nonallergen--5119-products-40-ids-one-qualifier) · [SC §2.3](SCHEMA-AND-CODES.md#23-nonallergen-ids--undocumented-same-gs1-list) · [SC §3.3](SCHEMA-AND-CODES.md#33-the-table) |
| `synkkaData.classifications[name=nutritionalClaim].values[]` | `ENUM` | named in the schema `description` | group present on 17,535 products; `values` non-empty on 7,618; 19,475 values; value keys: `id,synkkaId,unit` | `id`: `FREE_FROM_LACTOSE`, `FREE_FROM_GLUTEN`, `VEGAN`, `VEGETARIAN`, `FREE_FROM_PRESERVATIVES`, `FREE_FROM_COLOURING_AGENTS`, `FREE_FROM_ADDITIVES`, `NO_ADDED_SUGARS`, `HIGH_FIBRE`, `FREE_FROM_EGGS`, `HIGH_PROTEIN`, `LOW_SODIUM_SALT`, `FREE_FROM_SWEETENERS`, `FREE_FROM_SOY`, `LOW_LACTOSE`, `FREE_FROM_FAT`, `FREE_FROM_WHEAT`, `LOW_FAT`, `FREE_FROM_ARTIFICIAL_SWEETENERS`, `FREE_FROM_GMO`, `FREE_FROM_SODIUM_SALT`; `unit`: `FREE_FROM` (11,836), `DIET` (5,334), `HIGH` (823), `LOW` (820), `NO_ADDED` (662) | — | [PD §3.4](PRODUCT-DATA.md#34-nutritionalclaim--7618-products-21-ids-5-qualifiers) · [SC §2.4](SCHEMA-AND-CODES.md#24-nutritionalclaim-ids--self-describing) |
| `synkkaData.classifications[name=packagingMarkedLabel].values[]` | `ENUM` | named in the schema `description` | group present on 17,535 products; `values` non-empty on 17,255; 23,582 values; value keys: `id` or `id,synkkaId` | `id`: `warmTemperature`, `coolTemperature`, `freezeTemperature`, `GOODS_FROM_FINLAND_BLUE_SWAN`, `MADE_IN_FINLAND_FLAG_WITH_KEY`, `FINNISH_HEART_SYMBOL`, `EU_ORGANIC_FARMING`, `SVANEN`, `RAINFOREST_ALLIANCE`, `EU_ECO_LABEL`, `MARINE_STEWARDSHIP_COUNCIL_LABEL`, `FAIR_TRADE_MARK`, `AQUACULTURE_STEWARDSHIP_COUNCIL`, `KRAV_MARK`, `OFFICIAL_ECO_LABEL_SUN`, `SOIL_ASSOCIATION_ORGANIC_SYMBOL`, `PUHTAASTI_KOTIMAINEN`, `DOLPHIN_SAFE`, `UTZ_CERTIFIED` | — | [PD §3.5](PRODUCT-DATA.md#35-packagingmarkedlabel--17255-products-19-ids-unit-always-absent) · [SC §2.5](SCHEMA-AND-CODES.md#25-packagingmarkedlabel-ids--self-describing) |
| `synkkaData.classifications[name=packaging].values[]` | `ENUM` | named in the schema `description` | group present on 17,535 products; `values` non-empty on 0 | no values in the file | — | [PD §3](PRODUCT-DATA.md#3-synkkadataclassifications-in-depth) · [SC §1.4](SCHEMA-AND-CODES.md#14-classifications--the-generic-container-holding-most-code-systems) |
| `synkkaData.classifications[name=nutritionFact].values[]` | `DECIMAL` | named in the schema `description` | group present on 15,198 products; `values` non-empty on 12,244; 106,700 values; value keys: `id,unit,value` | `id`: `ENER-KJO`, `PRO-`, `FAT`, `CHOAVL`, `ENER-E14`, `SALTEQ`, `FASAT`, `SUGAR-`, `FIBTG`, `LACS`, `FAPUCIS`, `POLYL`, `STARCH`; `unit`: `GRM` (82,436), `KJO` (12,182), `E14` (12,080), `MGM` (1), `MC` (1) | — | [PD §3.6](PRODUCT-DATA.md#36-decimal-groups) · [SC §2.6](SCHEMA-AND-CODES.md#26-nutrient-ids--documented-in-schema-9-of-55) |
| `synkkaData.classifications[name=gda].values[]` | `DECIMAL` | named in the schema `description` | group present on 14,467 products; `values` non-empty on 11,513; 100,882 values; value keys: `id,unit,value` | `id`: `FAT`, `CHOAVL`, `ENER-KJO`, `PRO-`, `SALTEQ`, `ENER-E14`, `FASAT`, `SUGAR-`, `FIBTG`, `LACS`; `unit`: `GRM` (78,044), `KJO` (11,471), `E14` (11,365), `MGM` (1), `MC` (1) | — | [PD §3.6](PRODUCT-DATA.md#36-decimal-groups) · [SC §2.6](SCHEMA-AND-CODES.md#26-nutrient-ids--documented-in-schema-9-of-55) |
| `synkkaData.classifications[name=mineral].values[]` | `DECIMAL` | not named in schema | group present on 14,467 products; `values` non-empty on 1,783; 3,581 values; value keys: `id,unit,value` | `id`: `NA`, `CA`, `ZN`, `K`, `FE`, `MG`, `P`, `SE`, `MN`, `CU`, `CLD`, `FD`; `unit`: `MGM` (3,196), `GRM` (336), `MC` (49) | — | [PD §3.6](PRODUCT-DATA.md#36-decimal-groups) · [SC §2.6](SCHEMA-AND-CODES.md#26-nutrient-ids--documented-in-schema-9-of-55) |
| `synkkaData.classifications[name=vitamin].values[]` | `DECIMAL` | not named in schema | group present on 14,467 products; `values` non-empty on 727; 1,075 values; value keys: `id,unit,value` | `id`: `VITB12`, `VITA-`, `VITB6-`, `VITK`, `VITD`, `VITC`, `VITE`; `unit`: `MC` (854), `MGM` (221) | — | [PD §3.6](PRODUCT-DATA.md#36-decimal-groups) · [SC §2.6](SCHEMA-AND-CODES.md#26-nutrient-ids--documented-in-schema-9-of-55) |
| `synkkaData.classifications[name=composition].values[]` | `DECIMAL` | not named in schema | group present on 14,467 products; `values` non-empty on 14; 16 values; value keys: `id,unit,value` | `id`: `CAFFN`, `NUCLEOTIDE`, `TAU`; `unit`: `MGM` (15), `GRM` (1) | — | [PD §3.6](PRODUCT-DATA.md#36-decimal-groups) · [SC §2.6](SCHEMA-AND-CODES.md#26-nutrient-ids--documented-in-schema-9-of-55) |

#### Localised text arrays — `{language, value}` items

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `synkkaData.disposalInformations[]` | `object` | items | 13,772 items on 4,633 products | object `{language, value}` | “The text in one language.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.disposalInformations[].language` | `string` | required | always present (13,772 objects) | `fi`, `sv`, `en` | “Language of the text as an ISO 639-1 code, for example fi, sv or en.” | [SC §2.20](SCHEMA-AND-CODES.md#220-other-small-vocabularies) |
| `synkkaData.disposalInformations[].value` | `string` | required | always present (13,772 objects); leading/trailing whitespace on 5 | free text; 2,230 distinct; length 1–516 | “The text.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.keyIngredients[]` | `object` | items | 38,440 items on 14,047 products | object `{language, value}` | “The text in one language.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.keyIngredients[].language` | `string` | required | always present (38,440 objects) | `fi`, `sv`, `en`, `et`, `da`, `de`, `es`, `nl`, `fr`, `no`, `it`, `ru`, `lt`, `lv` | “Language of the text as an ISO 639-1 code, for example fi, sv or en.” | [SC §2.20](SCHEMA-AND-CODES.md#220-other-small-vocabularies) |
| `synkkaData.keyIngredients[].value` | `string` | required | always present (38,440 objects); leading/trailing whitespace on 1,075 | free text; 32,473 distinct; length 1–4354 | “The text.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.marketingTexts[]` | `object` | items | 34,159 items on 11,915 products | object `{language, value}` | “The text in one language.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.marketingTexts[].language` | `string` | required | always present (34,159 objects) | `fi`, `sv`, `en` | “Language of the text as an ISO 639-1 code, for example fi, sv or en.” | [SC §2.20](SCHEMA-AND-CODES.md#220-other-small-vocabularies) |
| `synkkaData.marketingTexts[].value` | `string` | required | always present (34,159 objects); leading/trailing whitespace on 359 | free text; 29,022 distinct; length 1–2861 | “The text.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.materialAdditionalDescriptions[]` | `object` | items | 144 items on 11 products | object `{language, value}` | “The text in one language.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.materialAdditionalDescriptions[].language` | `string` | required | always present (144 objects) | `en`, `fi`, `sv` | “Language of the text as an ISO 639-1 code, for example fi, sv or en.” | [SC §2.20](SCHEMA-AND-CODES.md#220-other-small-vocabularies) |
| `synkkaData.materialAdditionalDescriptions[].value` | `string` | required | always present (144 objects) | free text; 132 distinct; length 59–146 | “The text.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.names[]` | `object` | items | 51,202 items on 17,546 products | object `{language, value}` | “The text in one language.” | [PD §2.1](PRODUCT-DATA.md#21-names--the-one-near-complete-text-field) |
| `synkkaData.names[].language` | `string` | required | always present (51,202 objects) | `fi`, `en`, `sv`, `es`, `nl` | “Language of the text as an ISO 639-1 code, for example fi, sv or en.” | [SC §2.20](SCHEMA-AND-CODES.md#220-other-small-vocabularies) |
| `synkkaData.names[].value` | `string` | required | always present (51,202 objects); leading/trailing whitespace on 239 | free text; 49,076 distinct; length 1–171 | “The text.” | [PD §2.1](PRODUCT-DATA.md#21-names--the-one-near-complete-text-field) |
| `synkkaData.preparationInstructions[]` | `object` | items | 10,116 items on 3,480 products | object `{language, value}` | “The text in one language.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.preparationInstructions[].language` | `string` | required | always present (10,116 objects) | `fi`, `sv`, `en` | “Language of the text as an ISO 639-1 code, for example fi, sv or en.” | [SC §2.20](SCHEMA-AND-CODES.md#220-other-small-vocabularies) |
| `synkkaData.preparationInstructions[].value` | `string` | required | always present (10,116 objects); leading/trailing whitespace on 123 | free text; 5,253 distinct; length 1–1279 | “The text.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.storageInstructions[]` | `object` | items | 25,384 items on 8,666 products | object `{language, value}` | “The text in one language.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.storageInstructions[].language` | `string` | required | always present (25,384 objects) | `fi`, `sv`, `en` | “Language of the text as an ISO 639-1 code, for example fi, sv or en.” | [SC §2.20](SCHEMA-AND-CODES.md#220-other-small-vocabularies) |
| `synkkaData.storageInstructions[].value` | `string` | required | always present (25,384 objects); leading/trailing whitespace on 203 | free text; 5,232 distinct; length 1–475 | “The text.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.usageInstructions[]` | `object` | items | 10,690 items on 3,694 products | object `{language, value}` | “The text in one language.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.usageInstructions[].language` | `string` | required | always present (10,690 objects) | `fi`, `sv`, `en` | “Language of the text as an ISO 639-1 code, for example fi, sv or en.” | [SC §2.20](SCHEMA-AND-CODES.md#220-other-small-vocabularies) |
| `synkkaData.usageInstructions[].value` | `string` | required | always present (10,690 objects); leading/trailing whitespace on 100 | free text; 4,511 distinct; length 1–1167 | “The text.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |

#### `synkkaData.nutritionalContent[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `synkkaData.nutritionalContent[]` | `object` | items | 114,754 items on 12,251 products | object | “One nutrient.” | [PD §2.2](PRODUCT-DATA.md#22-nutritionalcontent-12251-products-114754-rows) · [SC §1.5](SCHEMA-AND-CODES.md#15-nutritionalcontent) |
| `synkkaData.nutritionalContent[].basisQuantity` | `number` | required | always present (114,754 objects) | `1.0` … `401.0`; 45 distinct; `100.0` on 113,093 | “Quantity the value is given for, for example 100.” | [PD §2.2](PRODUCT-DATA.md#22-nutritionalcontent-12251-products-114754-rows) |
| `synkkaData.nutritionalContent[].basisQuantityUnit` | `string` | required | always present (114,754 objects) | `GRM`, `MLT`; not named in schema: `PTN` (164), `H87` (30), `KGM` (27), `GL` (9) | “Unit of the basis quantity, for example GRM (gram) or MLT (millilitre).” | [SC §2.7](SCHEMA-AND-CODES.md#27-measurement-unit-codes--documented-in-schema-unece-rec-20) |
| `synkkaData.nutritionalContent[].dailyValueIntakePercent` | `number` | optional | key present on 5,600 of 114,754 objects (4.88%), absent on 109,154 | `0.0` … `1667.0` percent; 336 distinct | “Share of the recommended daily intake that the value covers, in percent.” | [SC §1.5](SCHEMA-AND-CODES.md#15-nutritionalcontent) |
| `synkkaData.nutritionalContent[].id` | `string` | required | always present (114,754 objects) | 55 distinct nutrient codes (schema names 9: `ENER-KJO`, `ENER-E14`, `FAT`, `FASAT`, `CHOAVL`, `SUGAR-`, `FIBTG`, `PRO-`, `SALTEQ`) | “Nutrient code, for example ENER-KJO (energy, kJ), ENER-E14 (energy, kcal), FAT, FASAT (saturated fat), CHOAVL (carbohydrate), SUGAR- (sugars), FIBTG (fibre), PRO- (protein) or SALTEQ (salt).” | [SC §2.6](SCHEMA-AND-CODES.md#26-nutrient-ids--documented-in-schema-9-of-55) · [PD §2.2](PRODUCT-DATA.md#22-nutritionalcontent-12251-products-114754-rows) |
| `synkkaData.nutritionalContent[].servingSize` | `number` | optional | key present on 6,288 of 114,754 objects (5.48%), absent on 108,466 | `100.0`, `400.0`, `500.0` | “Size of one serving.” | [SC §1.5](SCHEMA-AND-CODES.md#15-nutritionalcontent) |
| `synkkaData.nutritionalContent[].servingSizeUnit` | `string` | optional | key present on 6,288 of 114,754 objects (5.48%), absent on 108,466 | `GRM`, `MLT` | “Unit of the serving size, GRM or MLT.” | [SC §2.7](SCHEMA-AND-CODES.md#27-measurement-unit-codes--documented-in-schema-unece-rec-20) |
| `synkkaData.nutritionalContent[].unit` | `string` | required | always present (114,754 objects) | `GRM`, `KJO`, `E14`, `MGM`; not named in schema: `MC` (1,988) | “Unit of the value, for example GRM (gram), MGM (milligram), KJO (kilojoule) or E14 (kilocalorie).” | [SC §2.7](SCHEMA-AND-CODES.md#27-measurement-unit-codes--documented-in-schema-unece-rec-20) |
| `synkkaData.nutritionalContent[].unitPrecision` | `string` | optional | key present on 109,598 of 114,754 objects (95.51%), absent on 5,156 | `APPROXIMATELY`, `LESS_THAN`, `ABOUT`; not named in schema: `LESS_THAN_OR_EQUAL` (8) | “How exact the value is, for example APPROXIMATELY, LESS_THAN or ABOUT.” | [SC §2.7](SCHEMA-AND-CODES.md#27-measurement-unit-codes--documented-in-schema-unece-rec-20) |
| `synkkaData.nutritionalContent[].value` | `number` | required | always present (114,754 objects) | `0.0` … `27000.0` in `unit` per `basisQuantity`; 3,896 distinct | “Amount of the nutrient, in the unit given, per basisQuantity.” | [PD §2.2](PRODUCT-DATA.md#22-nutritionalcontent-12251-products-114754-rows) |

#### `synkkaData.unitConversions[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `synkkaData.unitConversions[]` | `object` | items | 14,474 items on 14,474 products | object | “One packaging level.” | [PD §5 tier 2](PRODUCT-DATA.md#tier-2--static-fields-in-this-file) · [SC §1.6](SCHEMA-AND-CODES.md#16-unitconversions) |
| `synkkaData.unitConversions[].grossWeight` | `object` | required | always present (14,474 objects) | object `{unit, value}` | “Gross weight, including packaging of the packaging level.” | [SC §1.6](SCHEMA-AND-CODES.md#16-unitconversions) |
| `synkkaData.unitConversions[].grossWeight.unit` | `string` | required | always present (14,474 objects) | `GRM`, `KGM` | “Unit of the value: GRM (gram) or KGM (kilogram).” | [SC §2.7](SCHEMA-AND-CODES.md#27-measurement-unit-codes--documented-in-schema-unece-rec-20) |
| `synkkaData.unitConversions[].grossWeight.value` | `number` | required | always present (14,474 objects) | `0.307` … `6784000.0` in `unit`; 5,188 distinct | “Numeric value, in the unit given.” | [PD §5 tier 2](PRODUCT-DATA.md#tier-2--static-fields-in-this-file) |
| `synkkaData.unitConversions[].height` | `object` | required | always present (14,474 objects) | object `{unit, value}` | “Height of the packaging level.” | [SC §1.6](SCHEMA-AND-CODES.md#16-unitconversions) |
| `synkkaData.unitConversions[].height.unit` | `string` | required | always present (14,474 objects) | `MMT`, `CMT` | “Unit of the value: MMT (millimetre) or CMT (centimetre).” | [SC §2.7](SCHEMA-AND-CODES.md#27-measurement-unit-codes--documented-in-schema-unece-rec-20) |
| `synkkaData.unitConversions[].height.value` | `number` | required | always present (14,474 objects) | `0.5` … `105252.0` in `unit`; 531 distinct | “Numeric value, in the unit given.” | [SC §1.6](SCHEMA-AND-CODES.md#16-unitconversions) |
| `synkkaData.unitConversions[].length` | `object` | required | always present (14,474 objects) | object `{unit, value}` | “Length of the packaging level.” | [SC §1.6](SCHEMA-AND-CODES.md#16-unitconversions) |
| `synkkaData.unitConversions[].length.unit` | `string` | required | always present (14,474 objects) | `MMT`, `CMT` | “Unit of the value: MMT (millimetre) or CMT (centimetre).” | [SC §2.7](SCHEMA-AND-CODES.md#27-measurement-unit-codes--documented-in-schema-unece-rec-20) |
| `synkkaData.unitConversions[].length.value` | `number` | required | always present (14,474 objects) | `2.0` … `3100.0` in `unit`; 625 distinct | “Numeric value, in the unit given.” | [SC §1.6](SCHEMA-AND-CODES.md#16-unitconversions) |
| `synkkaData.unitConversions[].netWeight` | `object` | optional | key present on 9,786 of 14,474 objects (67.61%), absent on 4,688 | object `{unit, value}` | “Net weight of the contents of the packaging level.” | [SC §1.6](SCHEMA-AND-CODES.md#16-unitconversions) |
| `synkkaData.unitConversions[].netWeight.unit` | `string` | required | always present (9,786 objects) | `GRM`, `KGM` | “Unit of the value: GRM (gram) or KGM (kilogram).” | [SC §2.7](SCHEMA-AND-CODES.md#27-measurement-unit-codes--documented-in-schema-unece-rec-20) |
| `synkkaData.unitConversions[].netWeight.value` | `number` | required | always present (9,786 objects) | `0.2` … `200000.0` in `unit`; 1,478 distinct | “Numeric value, in the unit given.” | [PD §5 tier 2](PRODUCT-DATA.md#tier-2--static-fields-in-this-file) |
| `synkkaData.unitConversions[].synkkaPackagingType` | `string` | required | always present (14,474 objects) | `BASE_UNIT_OR_EACH`, `CASE`, `PALLET` | “Packaging level: BASE_UNIT_OR_EACH (consumer unit), CASE or PALLET.” | [SC §2.8](SCHEMA-AND-CODES.md#28-synkkapackagingtype--documented-in-schema-complete) |
| `synkkaData.unitConversions[].volume` | `object` | optional | key present on 8,970 of 14,474 objects (61.97%), absent on 5,504 | object `{unit, value}` | “Volume of the packaging level.” | [PD §5 tier 2](PRODUCT-DATA.md#tier-2--static-fields-in-this-file) |
| `synkkaData.unitConversions[].volume.unit` | `string` | required | always present (8,970 objects) | `LTR`, `MLT`; not named in schema: `GRM` (5,498), `H87` (1,500), `KGM` (875), `CLT` (50), `PTN` (9), `MTR` (8), `KGM H87` (3), `PR` (3), `GRM H87` (2), `KGM PTN` (1) | “Unit of the value: for example LTR (litre) or MLT (millilitre).” | [PD §5 tier 2](PRODUCT-DATA.md#tier-2--static-fields-in-this-file) · [SC §2.7](SCHEMA-AND-CODES.md#27-measurement-unit-codes--documented-in-schema-unece-rec-20) |
| `synkkaData.unitConversions[].volume.value` | `number` | required | always present (8,970 objects) | `0.0` … `200000.0` in `unit`; 670 distinct | “Numeric value, in the unit given.” | [PD §5 tier 2](PRODUCT-DATA.md#tier-2--static-fields-in-this-file) |
| `synkkaData.unitConversions[].width` | `object` | required | always present (14,474 objects) | object `{unit, value}` | “Width of the packaging level.” | [SC §1.6](SCHEMA-AND-CODES.md#16-unitconversions) |
| `synkkaData.unitConversions[].width.unit` | `string` | required | always present (14,474 objects) | `MMT`, `CMT` | “Unit of the value: MMT (millimetre) or CMT (centimetre).” | [SC §2.7](SCHEMA-AND-CODES.md#27-measurement-unit-codes--documented-in-schema-unece-rec-20) |
| `synkkaData.unitConversions[].width.value` | `number` | required | always present (14,474 objects) | `4.4` … `1100.0` in `unit`; 508 distinct | “Numeric value, in the unit given.” | [SC §1.6](SCHEMA-AND-CODES.md#16-unitconversions) |

#### `synkkaData.ingredients[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `synkkaData.ingredients[]` | `object` | items | 3,746 items on 3,746 products; key sets: `names,origins,sequence` (1,927) · `names,origins,percentage,sequence` (1,542) · `names,percentage,sequence` (244) · `names,sequence` (28) · `sequence` (4) · `origins,sequence` (1) | object | “One ingredient.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) · [SC §1.3](SCHEMA-AND-CODES.md#13-synkkadata) |
| `synkkaData.ingredients[].names` | `array<object>` | optional | key present on 3,741 of 3,746 objects (99.87%), absent on 5; never `[]`; length 1–3 | array of `{language, value}` | “Name of the ingredient in several languages.” | [SC §1.3](SCHEMA-AND-CODES.md#13-synkkadata) |
| `synkkaData.ingredients[].names[]` | `object` | items | 10,815 items on 3,741 products | object | “The name in one language.” | [SC §1.3](SCHEMA-AND-CODES.md#13-synkkadata) |
| `synkkaData.ingredients[].names[].language` | `string` | required | always present (10,815 objects) | `fi`, `sv`, `en` | “Language of the name as an ISO 639-1 code.” | [SC §2.20](SCHEMA-AND-CODES.md#220-other-small-vocabularies) |
| `synkkaData.ingredients[].names[].value` | `string` | required | always present (10,815 objects); leading/trailing whitespace on 13 | free text; 2,014 distinct; length 1–58 | “The name.” | [SC §1.3](SCHEMA-AND-CODES.md#13-synkkadata) |
| `synkkaData.ingredients[].origins` | `array<object>` | optional | key present on 3,470 of 3,746 objects (92.63%), absent on 276; never `[]`; length 1 | array holding exactly one origin | “Where the ingredient comes from, by production stage.” | [SC §1.3](SCHEMA-AND-CODES.md#13-synkkadata) |
| `synkkaData.ingredients[].origins[]` | `object` | items | 3,470 items on 3,470 products | object | “One origin.” | [SC §1.3](SCHEMA-AND-CODES.md#13-synkkadata) |
| `synkkaData.ingredients[].origins[].country` | `string` | required | always present (3,470 objects) | 75 distinct; 3-character digit strings, or `NON_EU` (172) | “Country of the origin as a numeric ISO 3166-1 code, or NON_EU.” | [SC §2.16](SCHEMA-AND-CODES.md#216-countriesoforigin--documented-in-schema-iso-3166-1-numeric) |
| `synkkaData.ingredients[].origins[].type` | `string` | required | always present (3,470 objects) | `FARMING`, `MILKING`, `REARING`, `BIRTH`, `LAST_PROCESSING`; not named in schema: `SLAUGHTER` (51), `IMPORTATION` (16), `CATCH_ZONE` (15), `HUNTED_GATHERED` (13), `CUTTER` (2) | “Production stage the origin refers to, for example FARMING, MILKING, REARING, BIRTH or LAST_PROCESSING.” | [SC §2.16](SCHEMA-AND-CODES.md#216-countriesoforigin--documented-in-schema-iso-3166-1-numeric) |
| `synkkaData.ingredients[].percentage` | `number` | optional | key present on 1,786 of 3,746 objects (47.68%), absent on 1,960 | `0.8` … `100.0` percent; 226 distinct | “Share of the ingredient in the product, in percent.” | [SC §1.3](SCHEMA-AND-CODES.md#13-synkkadata) |
| `synkkaData.ingredients[].sequence` | `integer` | required | always present (3,746 objects) | `0` … `99`, 33 distinct; `0` on 48 rows | “Position of the ingredient in the ingredient list, starting from 1.” | [SC §1.3](SCHEMA-AND-CODES.md#13-synkkadata) |

#### `synkkaData.fishingReports[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `synkkaData.fishingReports[]` | `object` | items | 379 items on 353 products | object | “One fish species.” | [SC §1.7](SCHEMA-AND-CODES.md#17-fishingreports-and-safetydata) · [SC §2.17](SCHEMA-AND-CODES.md#217-fishing-codes--undocumented-by-design-fao-code-lists) |
| `synkkaData.fishingReports[].catchMethods` | `array<object>` | required | always present (379 objects); `[]` on 41 of 379 (10.82%); length 0–1 | array holding at most one production method | “How and where the fish was produced.” | [SC §1.7](SCHEMA-AND-CODES.md#17-fishingreports-and-safetydata) |
| `synkkaData.fishingReports[].catchMethods[]` | `object` | items | 338 items on 314 products | object | “One production method.” | [SC §1.7](SCHEMA-AND-CODES.md#17-fishingreports-and-safetydata) |
| `synkkaData.fishingReports[].catchMethods[].areas` | `array<string>` | required | always present (338 objects); `[]` on 143 of 338 (42.31%); length 0–3 | array of area-code strings | “Codes of the fishing areas, for example 27. Names are not part of this data set” | [SC §2.17](SCHEMA-AND-CODES.md#217-fishing-codes--undocumented-by-design-fao-code-lists) |
| `synkkaData.fishingReports[].catchMethods[].areas[]` | `string` | items | 231 items on 179 products | 31 distinct codes (`27`, `27.3.d`, `05`, …) | “A fishing area code.” | [SC §2.17](SCHEMA-AND-CODES.md#217-fishing-codes--undocumented-by-design-fao-code-lists) |
| `synkkaData.fishingReports[].catchMethods[].methods` | `array<string>` | required | always present (338 objects); `[]` on 164 of 338 (48.52%); length 0–6 | array of method-code strings | “Codes of the fishing method, for example TM or 03. Names are not part of this dataset.” | [SC §2.17](SCHEMA-AND-CODES.md#217-fishing-codes--undocumented-by-design-fao-code-lists) |
| `synkkaData.fishingReports[].catchMethods[].methods[]` | `string` | items | 261 items on 157 products | `03`, `TM`, `07`, `02`, `01`, `05`, `09`, `PS`, `FYK`, `08`, `TX`, `032`, `FPO`, `022`, `TMS`, `GN`, `TBB`, `LL`, `FCN`, `OTM`, `SSC`, `FWR`, `LX`, `TBS`, `TB`, `GEN` | “A fishing method code.” | [SC §2.17](SCHEMA-AND-CODES.md#217-fishing-codes--undocumented-by-design-fao-code-lists) |
| `synkkaData.fishingReports[].catchMethods[].productionMethod` | `string` | required | always present (338 objects) | `AQUACULTURE`, `MARINE_FISHERY`, `INLAND_FISHERY`; not named in schema: `MARINE_FISHERY1` (3), `AQUACULTURE1` (2) | “Production method: AQUACULTURE, MARINE_FISHERY or INLAND_FISHERY.” | [SC §2.10](SCHEMA-AND-CODES.md#210-productionmethod--documented-in-schema-data-violates-it) |
| `synkkaData.fishingReports[].id` | `string` | required | always present (379 objects) | 43 distinct 3-letter uppercase codes | “Species code, for example SAL (salmon) or HER (herring).” | [SC §2.17](SCHEMA-AND-CODES.md#217-fishing-codes--undocumented-by-design-fao-code-lists) |
| `synkkaData.fishingReports[].name` | `string` | required | always present (379 objects); `""` on 13; leading/trailing whitespace on 1 | free text; 71 distinct | “Latin name of the species.” | [SC §2.17](SCHEMA-AND-CODES.md#217-fishing-codes--undocumented-by-design-fao-code-lists) |

#### `synkkaData.safetyData[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `synkkaData.safetyData[]` | `object` | items | 667 items on 667 products | object | “One safety data sheet.” | [SC §1.7](SCHEMA-AND-CODES.md#17-fishingreports-and-safetydata) · [SC §2.18](SCHEMA-AND-CODES.md#218-ghs-statement-codes--undocumented-by-design-clp-regulation) |
| `synkkaData.safetyData[].sheetId` | `string` | required | always present (667 objects) | free text; 532 distinct; length 1–25; mixes ids and dates | “Identifier or date of the safety data sheet.” | [SC §1.7](SCHEMA-AND-CODES.md#17-fishingreports-and-safetydata) |
| `synkkaData.safetyData[].values` | `array<object>` | required | always present (667 objects); `[]` on 283 of 667 (42.43%); length 0–16 | array of statements | “Hazard and precautionary statements of the sheet.” | [SC §2.18](SCHEMA-AND-CODES.md#218-ghs-statement-codes--undocumented-by-design-clp-regulation) |
| `synkkaData.safetyData[].values[]` | `object` | items | 2,092 items on 384 products | object | “One statement.” | [SC §2.18](SCHEMA-AND-CODES.md#218-ghs-statement-codes--undocumented-by-design-clp-regulation) |
| `synkkaData.safetyData[].values[].id` | `string` | required | always present (2,092 objects) | 80 distinct (31 with `HazardStatement`, 49 with `PrecautionaryStatement`); lowercase, `+`-joined (`p305+p351+p338`); literal `unspecified` on 5 | “Statement code, for example h319 or p280. Descriptions of the codes are not in this dataset” | [SC §2.18](SCHEMA-AND-CODES.md#218-ghs-statement-codes--undocumented-by-design-clp-regulation) |
| `synkkaData.safetyData[].values[].type` | `string` | required | always present (2,092 objects) | `PrecautionaryStatement`, `HazardStatement` | “HazardStatement or PrecautionaryStatement.” | [SC §2.20](SCHEMA-AND-CODES.md#220-other-small-vocabularies) |

#### `synkkaData.medias[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `synkkaData.medias[]` | `object` | items | 24,977 items on 13,375 products | object | “One media item.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.medias[].id` | `integer` | required | always present (24,977 objects) | `9810` … `570551881044226`; 24,916 distinct over 24,977 items | “Id of the media item.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.medias[].primary` | `boolean` | required | always present (24,977 objects) | `true` (16,051), `false` (8,926) | “True for the main image of the product.” | [PD §8 #25](PRODUCT-DATA.md#8-parsing-pitfalls-specific-to-this-file) |

#### `synkkaData.producers[]`

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `synkkaData.producers[]` | `object` | items | 14,467 items on 14,467 products | object | “One producer.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |
| `synkkaData.producers[].id` | `string` | required | always present (14,467 objects) | exactly 13 digits; 334 distinct | “Identifier of the producer, a 13-digit location number.” | [SC §2.20](SCHEMA-AND-CODES.md#220-other-small-vocabularies) |
| `synkkaData.producers[].name` | `string` | required | always present (14,467 objects); leading/trailing whitespace on 1 | free text; 333 distinct; length 6–42 | “Name of the producer.” | [PD §2](PRODUCT-DATA.md#2-synkkadata-field-reference) |

### 5.2 Delivery reliability CSV — `valio_aimo_junction26_delivery_reliability.csv`

56,741 bytes, ASCII, no BOM, CRLF line endings, comma-delimited, no quoting, header row + 4,425 data rows of 2 fields, ascending `productId`.

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `productId` | CSV text | — (no schema; column named in the spec description) | non-empty on all 4,425 rows; 4,425 distinct; all are catalog `id`s; covers 25.22% of the 17,546 products | exactly 6 ASCII digits, `460001` … `477545` | “Provides the delivery reliability file as CSV (productId, deliveryReliability).” | [CSV §1](CSV-DATASETS.md#1-valio_aimo_junction26_delivery_reliabilitycsv) · [CSV §6](CSV-DATASETS.md#6-join-recipes) |
| `deliveryReliability` | CSV text (decimal) | — (no schema; column named in the spec description) | non-empty and numeric on all 4,425 rows; 243 distinct; `0.0` on 12, `1.0` on 2,490 | `0.0` … `1.0`; 1–3 fraction digits; no unit or definition given | — (the spec names the column only) | [CSV §1](CSV-DATASETS.md#1-valio_aimo_junction26_delivery_reliabilitycsv) |

### 5.3 Carbon footprint CSV — `valio_aimo_junction26_carbon_footprint.csv`

156,990 bytes, ASCII, no BOM, CRLF line endings, comma-delimited, no quoting, header row + 11,033 data rows of 2 fields, ascending `productId`.

| Field path | Type | Declared | Actual | Values / format | Meaning | Ref |
|---|---|---|---|---|---|---|
| `productId` | CSV text | — (no schema; column named in the spec description) | non-empty on all 11,033 rows; 11,033 distinct; all are catalog `id`s; covers 62.88% of the 17,546 products | exactly 6 ASCII digits, `460000` … `477528` | “Provides the carbon footprint file as CSV (productId, AVG kg CO2-eq/kg).” | [CSV §2](CSV-DATASETS.md#2-valio_aimo_junction26_carbon_footprintcsv) · [CSV §6](CSV-DATASETS.md#6-join-recipes) |
| `AVG kg CO2-eq/kg` | CSV text (decimal) | — (no schema; column named in the spec description) | non-empty and numeric on all 11,033 rows; 177 distinct | `0.13` … `30.46`; unit per header: kg CO2-eq per kg; literal has no fraction on 224 rows (`1`, `5`), 1–3 fraction digits on 10,014, 15–17 on 795 (e.g. `0.20500000000000002`); header contains spaces and `/` | — (the spec names the column only) | [CSV §2](CSV-DATASETS.md#2-valio_aimo_junction26_carbon_footprintcsv) · [CSV §4](CSV-DATASETS.md#4-coverage--and-whether-missingness-is-structured) |

## 6. Keys and same-named fields across payloads

Join keys first, then every field name that recurs with a different meaning or type (`currency`, `validFrom`, `validTo`, `salesBlock`, `salesUnit`, `productId` and `language` recur with the same meaning).

| Key | Field | Joins to | Exact string form | Measured |
|---|---|---|---|---|
| Product code | `$[].id` (product JSON) | `ProductsRequest.products[]` · `ProductPrice.productId` · `ProductAvailability.productId` · `productId` (both CSVs) · `substitutions[].product` · `substitutions[].substituteProduct` | 6 ASCII digits, JSON string / unquoted CSV text; catalog range `460000` … `477545`, no leading zeros | CSV ids in catalog: 4,425/4,425 and 11,033/11,033; `substituteProduct` in catalog: 250/250; ◐ API echoes the requested code, including codes not in the catalog |
| Sales unit | `$[].salesUnit` | `units[].unitId` · `ScheduleLine.salesUnit`; `allowedLotSize` and `availableAmount` are expressed in it | 2–3 uppercase letters (17 codes in the catalog) | one matching `units[]` row on 17,546/17,546; ◐ `ScheduleLine.salesUnit` differs from `$[].salesUnit` on 7 of 797 sampled lines |
| Base unit | `$[].baseUnit` | `units[].unitId` (`sizeInBaseUnits` is counted in it) | 2–3 uppercase letters (16 codes) | matching row with `sizeInBaseUnits == 1.0` on 17,546/17,546 |
| GTIN | `salesUnitGtin` · `synkkaData.gtin` · `units[].gtin` | each other only; no GTIN in the API or the CSVs | digit string, length 8–14 | `salesUnitGtin` = `units[unitId == salesUnit].gtin` on 17,387/17,387; `synkkaData.gtin` = `units[unitId == baseUnit].gtin` on 13,561/14,478; `synkkaData.gtin` has 27 repeated values |
| Nutrient code | `synkkaData.nutritionalContent[].id` | `classifications[name=nutritionFact, gda, mineral, vitamin, composition].values[].id` | uppercase token, some with a trailing `-` (`PRO-`, `VITD-`) | 35 of the 35 classification ids occur identically in `nutritionalContent`; 20 of its 55 ids occur only there (incl. `VITD-`, `VITC-`, `VITE-`, while `VITD`, `VITC`, `VITE` occur in both) |
| Allergen code | `classifications[name=allergen].values[].id` | `classifications[name=nonAllergen].values[].id` | 2–3 uppercase characters (`AM`, `X99`) | 45 codes in the union, 39 in both groups |
| VAT | `Tax.taxRate` (number, percent) | `synkkaData.vatCode` (string class) | schema text maps `STANDARD` 25.5, `MEDIUM` 13.5, `LOW` 10 | `vatCode` absent on 3,068 products and outside the three names on 165; ◐ `taxRate` 13.5 / 25.5; in the sample `MEDIUM` → 13.5 on 666 of 666, `STANDARD` → 25.5 on 140 and 13.5 on 4, `MEDIUM MEDIUM` → 13.5 on 17, `vatCode` absent → 13.5 on 96 and 25.5 on 77 |
| Country | `$[].countryOfOrigin` | `synkkaData.countriesOfOrigin[]` · `ingredients[].origins[].country` | 2 lowercase letters vs 3-character digit strings or `NON_EU` — no shared form | not joinable without an external ISO 3166 table |
| Deposit material | `deposits[].material` | nothing in the provided data | digit string, 1–7 characters | 0/576 equal a product `id` |
| Request echo | `ProductsRequest.customer` · `.requestedDate` | `PriceResponse.customerId` · `PriceResponse.pricingDate` · `AvailabilityResponse.requestedDate` | request `YYYY-MM-DD` → response `YYYY-MM-DDT00:00:00+ZZZZ` | ◐ `2026-11-16` → `2026-11-16T00:00:00+0200` |

| Name | Occurs in | Type there | Meaning there |
|---|---|---|---|
| `value` | `Price.value` | number | amount excluding tax |
| `value` | `PriceWithTax.value` | number | amount including tax |
| `value` | `classifications[].values[].value` · `nutritionalContent[].value` · `unitConversions[].{grossWeight,netWeight,volume,height,length,width}.value` | number | quantity in the sibling `unit` |
| `value` | `[].value` of the 8 text arrays and of `ingredients[].names[]` | string | text in the sibling `language` |
| `unit` | `deposits[].unit` | string | packaging unit code (`ST`), same code system as `salesUnit` |
| `unit` | `classifications[].values[].unit` | string | measurement unit in `DECIMAL` groups (`GRM`, `KJO`, …); relation or qualifier in `ENUM` groups (`CONTAINS`, `FREE_FROM`, `DIET`, …) |
| `unit` | `nutritionalContent[].unit` · `unitConversions[].*.unit` | string | measurement unit of the sibling `value` (`GRM`, `KGM`, `MMT`, …); a different code system from `salesUnit` / `unitId` (`KG` vs `KGM`) |
| `id` | `$[].id` | string, 6 digits | product code (the join key) |
| `id` | `synkkaData.medias[].id` | integer | media item id |
| `id` | `classifications[].values[].id` · `nutritionalContent[].id` · `fishingReports[].id` · `safetyData[].values[].id` | string | feature / nutrient / species / statement code — four unrelated code systems |
| `id` | `synkkaData.producers[].id` | string, 13 digits | producer location number |
| `name` | `classifications[].name` | string | group discriminator (10 values) |
| `name` | `fishingReports[].name` · `producers[].name` | string | Latin species name · producer name; product names are `synkkaData.names[].value` |
| `names` | `synkkaData.names` · `ingredients[].names` | array of `{language, value}` | product name vs ingredient name |
| `type` | `ValidationError.type` | string | validation error code |
| `type` | `classifications[].type` · `ingredients[].origins[].type` · `safetyData[].values[].type` | string | `ENUM`/`DECIMAL` · production stage · statement kind |
| `values` | `classifications[].values` · `safetyData[].values` | array of object | `{id, synkkaId?, unit?, value?}` vs `{id, type}` |
| `detail` | `422` body (`HTTPValidationError`) | array of `ValidationError` | validation errors |
| `detail` | `401` / `404` / `405` body | string | ◐ error message |
| `products` | `ProductsRequest.products` | array of string | product codes to query |
| `products` | `PriceResponse.products` · `AvailabilityResponse.products` | array of `ProductPrice` · array of `ProductAvailability` | one result per requested code |
| `requestedDate` | `ProductsRequest.requestedDate` | string, `YYYY-MM-DD` | desired delivery date |
| `requestedDate` | `AvailabilityResponse.requestedDate` | string, datetime with offset | the request date at midnight (`/api/price` returns it as `pricingDate`) |
| `quantity` | `ProductPrice.quantity` | number | quantity the price is for (`1.0`) |
| `quantity` | `deposits[].quantity` | number | deposit units per sales unit |
| `gtin` | `synkkaData.gtin` · `units[].gtin` | string | consumer-unit barcode vs barcode of that packaging unit (`salesUnitGtin` = sales-unit barcode) |

## 7. Declared vs occurring field sets

Key-level comparison only; value-level deviations are in the rows above.

| Payload | Declared paths | Occurring paths | Occurring, not declared | Declared, never occurring |
|---|---|---|---|---|
| API objects (`openapi.json`, 11 schemas) | 46 | ◐ all 43 response/error fields seen at least once (the 3 `ProductsRequest` fields are request-only) | ◐ `status` (ping `200`); string `detail` (`401`, `404`, `405`); status `307` on the three download operations (declared `200`) | none at key level (the `null` alternative of the 9 `nullable` fields was never seen) |
| Product JSON (schema) | 148 (root included) | 148 | none | none |
| Delivery reliability CSV (spec description) | 2 columns | 2 columns | none | none |
| Carbon footprint CSV (spec description) | 2 columns | 2 columns | none | none |
