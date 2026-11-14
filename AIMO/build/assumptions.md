# Assumptions collected during the build

One line each, by package. T15 turns this into `docs/ASSUMPTIONS.md` and the `/assumptions` page.

## Foundation (T00)
- The CloudEvents `type` prefix is the plain project name `tta.v1.`: the project owns no domain for a reverse-DNS prefix. A deployment replaces it with its own.
- Problem `type` URIs use the placeholder base `https://tta.example/problems/`; a deployment serves real pages there.
- The customer number sent to the mock is `123`; it does not change the mock's answers (API.md section 3).
- Every request to the mock asks for delivery on Monday 16 Nov 2026; the mock ignores `requestedDate` (API.md section 8.6).
- Tonight's replay capture covers categories `104xx` and `18720` (769 products). In replay, a product outside the capture behaves as an unknown id does live.

## Availability (T04)
- A cut-off exactly equal to "now" counts as passed; a price whose `validTo` equals "now" is no longer valid.
- A product is `BLOCKED` when `salesBlock` is true on the product or on its schedule line.
- `usable_amount` is empty for every state except `CONFIRMED`, including cut-off passed lines that carry a real figure.
- Claim `quantity`: cut-off passed is `UNKNOWN`; confirmed stock below the line's quantity is `RULED_OUT`.
- Claim `delivery_date`: `RULED_OUT` when the cut-off has passed, even with no needed-by date; `UNKNOWN` when no date was asked or Valio gives no date or cut-off.
- Claim `price`: an expired `validTo` is `UNKNOWN` (the table has no ruled-out for price). `validFrom` is not checked.
- Claim `allergens`: `CONFIRMED` when the buyer excluded nothing.
- Claim `origin`: the placeholder codes `zy`, `xs`, `zz` count as not stated (80 of 17,546 catalog products state no origin).
- Which claims gate an order without a human: price, quantity, allergens always; delivery date only for a dated request; origin never (SPEC section 4).
- Dates and times are written in the offset Valio sent (Helsinki). Sales-unit codes (`ST`, `KI`, `KG`) are shown as Valio sends them: no translation is published.
