# Valio Aimo — questions for the booth

The only question list. Every question has the same shape: **context → what we did → what we got → an example to show → "is that expected, or did we get something wrong?"** The last line is what we build if nobody answers.

**How to ask:** the mock's behaviour is the scenario we are meant to handle, not a fault. We are checking our reading, not reporting bugs.

**How the numbers were produced (Friday 2026-11-13, 23:00 server time)**
- **"The sample"** = a random sample of 1,000 of the 17,546 products, sent to `/api/availability` and `/api/price` with `requestedDate` 2026-11-16. It came back as 440 Stock, 357 Terminal and 203 with no schedule line. Sample figures are estimates, not catalog totals.
- **"The catalog"** = counted over all 17,546 products in the product file.
- Examples with live values (Q1, Q3–Q10, Q12) must be re-run before showing.

## If you only get two minutes: SCOPE-1 · T03-1 · Q1 · Q7 · Q4

Updated Saturday 14 Nov. The booth-ready versions are `AIMO/OPEN-QUESTIONS.md` (every open question with an example to show) and `AIMO/BOOTH-NOW.md` (the questions plus the decisions to confirm). This file keeps the full history.
Their answers feed Saturday-morning work, so ask them as soon as a mentor is free.

---

## Settled — we handle these ourselves, do not ask them

| Topic | Why it is settled | What we do |
|---|---|---|
| There is no order endpoint | Core requirement 2 asks us to define "a defined interaction for moving from inquiry to commitment". The spec has 6 operations and none for orders. | Our own order step, with approval and an audit record |
| `requestedDate` changes nothing | The spec says `availableDate` is the "Earliest date when amount is available. Note that this might differ from your requestedDate". 24 products with 4 different dates returned identical product data. | We compare the buyer's needed-by date with `availableDate` ourselves |
| Products that cannot be delivered (20.3% of the sample have no schedule line; 2.9% show amount 0) | The spec says "Empty array means product cannot currently be delivered on any date". This is the brief's "what happens when the exact request can't be met". | Exception → ranked substitute, with the trade-off explained |
| Terminal quantity is 999999 | The spec says it is "always 999999 since actual value is not known". | Never the suggestion; named as an alternative; ordering it always needs human approval |
| Very large quantities on Stock products (Q3) | **Answered by Valio in person on 14 Nov:** when the value is very large they do not know the stock. | Same as Terminal: quantity not confirmed |

---

## Q1 — Order cut-offs that have already passed

- **Context:** the spec says `closingTime` is "the order cut-off time (= order by closingTime at the latest to receive goods on availableDate)".
- **We did:** sent the sample to `/api/availability` on Friday at 23:00 server time.
- **We got:** all 357 Terminal products had a `closingTime` already in the past (between 2026-11-11 13:00 and 2026-11-13 12:30; 229 of them at 2026-11-12 15:00), and 356 of them show `availableDate` 2026-11-16. For Stock, 372 of 440 close on Sunday 2026-11-15 17:00 and 68 closed on Friday at 13:00.
- **Example to show** — two Valio lactose-free milks, values captured in one call on Friday at 23:03 server time. Request to reproduce:

  ```
  POST /api/availability
  {"customer": "123", "requestedDate": "2026-11-16", "products": ["464119", "464306"]}
  ```

  | | `464119` skimmed milk 1 l lactose free UHT | `464306` Eila semi-skimmed milk drink 1 l |
  |---|---|---|
  | `logisticModel` | Terminal | Stock |
  | `closingTime` | **2026-11-12T15:00** — 32 hours before `timeNow` | 2026-11-15T17:00 — still open |
  | `timeNow` | 2026-11-13T23:03 | 2026-11-13T23:03 |
  | `availableDate` | **2026-11-16** | 2026-11-16 |
  | `availableAmount` | 999999 | 9999999999 |
  | `salesBlock` | false | false |

- **Ask:** "We read closingTime literally: once it has passed, the product can no longer arrive on availableDate, so our agent picks a product whose cut-off is still open and says why. Is that the right reading, or did we get something wrong?"
- **Then:** "Do the closingTime values move forward over the weekend, or will every product be past its cut-off after Sunday 17:00?"
- **If no answer, we build:** that rule. A product whose cut-off has passed is not offered for a dated request, and the explanation names it. We keep a replay mode with saved responses in case every cut-off has passed by judging time.

## Q2 — Allergen values that are not in the schema

- **Context:** allergen-safe substitution for school and hospital kitchens is one of your scenarios. The schema says the allergen relation is `CONTAINS` or `FREE_FROM`.
- **We did:** counted every value of that field across the catalog, and looked the codes up in the public GS1 code lists.
- **We got:** two more relation values — `MAY_CONTAIN` on 2,685 products and `UNDECLARED` on 33 — and the code `X99` on 121 products in `allergen` (120 of which list no other allergen) plus 74 in `nonAllergen`. GS1 defines `X99` as "Does not contain declaration obligatory allergens in the product" and `UNDECLARED` as "Not intentionally included in the product and assessed not to require a cross-contact declaration".
- **Example to show** — the `allergen` group of three products in the product file:

  | Product | `allergen` entries |
  |---|---|
  | `465657` Aino raspberry chocolate ice cream | `AM` `CONTAINS` · `AN` **`MAY_CONTAIN`** |
  | `460556` Turun Sinappia mild mustard 6 kg | `BM` `CONTAINS` · 13 other codes **`UNDECLARED`** |
  | `460622` Marli Natur apple juice 1 L | only **`X99`** `CONTAINS` |

- **Ask:** "We read these with the GS1 meanings: X99 is a product with no declarable allergens, UNDECLARED is not intentionally included. Is that how your data uses them, or did we get it wrong?"
- **Then:** "For an allergy diet, who decides whether 'may contain' is acceptable — you, or the customer's own policy?"
- **If no answer, we build:** GS1 meanings. Allergen strictness is a required input with no default (proposed, PLAN §9). Under the strict setting an explicit `FREE_FROM` for that allergen passes automatically, a declared `CONTAINS` is rejected, and everything else goes to a human.

## Q3 — Very large stock quantities on Stock products · ANSWERED, do not ask again

**Answer (Valio, in person, 14 Nov):** when the value is very large they do not know the stock. We read these lines like Terminal: quantity not confirmed; never the suggestion; named as an alternative; ordering needs human approval. The rest of this section is kept as the record of what we asked.

- **Context:** the spec explains 999999 for Terminal ("actual value is not known"). For Stock it says "Stock products are stocked by us, so we know their available quantities" and does not mention the values below.
- **We did:** looked at `availableAmount` in the sample.
- **We got:** all 357 Terminal lines are 999999, as documented. But 92 of 440 Stock lines carry values such as 9999999999, 4999999999 or 416666666 — each equals 9,999,999,999 divided by the base units per sales unit. The largest ordinary Stock value was 7,389.
- **Example to show:**

  | Product (all Stock) | Base units per sales unit | `availableAmount` | 9,999,999,999 ÷ units |
  |---|---|---|---|
  | `464306` Eila milk drink 1 l | 1 | 9999999999 | 9,999,999,999 |
  | `477398` Schweppes Indian Tonic 1.5 L | 12 | 833333333 | 833,333,333 |
  | `463779` Valio Eila milk drink 2.5 dl UHT | 15 | 666666666 | 666,666,666 |
  | `477367` Hartwall Novelle Plus 24 × 0.5 l | 24 | 416666666 | 416,666,666 |
  | `465158` Tropic apple juice 1 L | 1 | **3239** | — an ordinary value |

- **Why it matters:** it decides the canonical request. `464306`, Valio's own lactose-free milk at €1.01 per litre, carries this value. Read as "not known", our agent suggests 749 litres of Arla milk at about €2.64 instead and only mentions it.
- **Ask:** "We treat those Stock values like Terminal: quantity not known. Our agent suggests a product with a confirmed quantity, mentions these as an alternative and asks a human before ordering one. Is 'not known' the right reading, or do they mean the stock is effectively unlimited?"
- **If no answer, we build:** any amount of 999,999 or more means "quantity not confirmed"; it is never used in arithmetic, and ordering it needs human approval. The reading is one switch in the code.

---

## Q4 — What an accepted order commits to

- **Context:** the brief asks for "a defined interaction for moving from inquiry to commitment, based on fixed prices rather than a negotiated quote". The mock has no order step, so we define it.
- **We did:** designed our offer so that every claim carries a status: confirmed, not confirmed, or ruled out.
- **We got** — for `464306`, from `/api/price` and `/api/availability`:

  | Claim | What the API gives | Status in our offer |
  |---|---|---|
  | Price | 1.01 per unit, `validFrom` 2026-09-01, `validTo` 2026-12-31 | fixed until 2026-12-31 |
  | Delivery date | `availableDate` 2026-11-16, `closingTime` 2026-11-15T17:00 | 2026-11-16 if ordered before Sunday 17:00 |
  | Quantity | `availableAmount` 9999999999 | not confirmed |

- **Ask:** "When Valio Aimo accepts an order today, what is committed at that moment — the price, the quantity, the delivery date? Is our reading of these three fields right?"
- **If no answer, we build:** price is committed for its validity window; the date is committed if the order is placed before `closingTime`; quantity is committed only when the stock figure is an ordinary number.

## Q5 — Products with no allergen data

- **We did:** counted products with nothing in the `allergen` group and nothing in the `nonAllergen` group.
- **We got:** 8,110 of 17,546 (46.2%). Leaving out non-food categories (cleaning, packaging, equipment, office), it is 4,149 of 13,577 food products (30.6%).
- **Example to show** — both came back priced and with a schedule line for 2026-11-16, and neither has any entry in `allergen` or `nonAllergen`:

  | Product | What the product file says about allergens |
  |---|---|
  | `463168` Peltolan blue cheese 1.6 kg | no entry in either group |
  | `463427` HK cooked ham 6 × 300 g | claims `FREE_FROM_GLUTEN`, `FREE_FROM_LACTOSE`, `HIGH_PROTEIN`, but no allergen entries |

- **Ask:** "Is that expected? Does no data mean the supplier declared nothing, so an agent must treat it as unknown rather than safe?"
- **If no answer, we build:** no data means unknown; under the strict setting it goes to a human.

## Q6 — When stock covers only part of an order

- **Context:** your rubric scores "handling of partial availability".
- **We got:** the API returns at most one schedule line per product and the request carries no quantity, so it cannot express a delivery split across dates.
- **Example to show** — `461360` Alpro almond drink 1 L: Stock, one schedule line, `availableAmount` 50, `availableDate` 2026-11-16. A need for 200 gets the same single line of 50; nothing says when the other 150 could come.
- **Ask:** "When stock covers only part of an order line, what happens today — partial delivery, a substitute, or the line is dropped?"
- **If no answer, we build:** fill the remainder from a second product and show the order as combined.

## Q7 — What limits do real customers set?

- **Context:** your rubric scores "what the agent can decide alone, what needs human sign-off". The spec says `customer` does not affect responses in this challenge.
- **We did:** sent the same 24 products with six different `customer` strings.
- **We got:** every per-product field was identical.
- **Example to show** — `/api/price` for `464306`:

  | `customer` sent | `customerId` returned | Price | `netPriceFound` |
  |---|---|---|---|
  | `"123"` | `"123"` | 1.01 | true |
  | `"ACME-RESTAURANT-42"` | `"ACME-RESTAURANT-42"` | 1.01 | true |

- **Ask:** "Since the mock has no customer model, we write our own limits. What do real customers put on ordering — a euro cap per order, an approved product list, approver roles? One example is enough."
- **Follow-up, now that our limits are per-buyer profile settings:** "Which of these would a real customer set, and with what typical values: a euro limit per order, a limit per day, a minimum share of the quantity that must be covered, an approved product list, who approves what?"
- **If no answer, we build:** a buyer profile per customer (spend limit per order and per day, minimum fill, allergen rule, substitution scope) with illustrative values, labelled as ours.

## Q8 — Deposits

- **We did:** took the 7 deposit `material` codes in the catalog (1, 2, 3, 4, 147, 171, 9708918) and looked them up as product ids, in the catalog and in `/api/price`.
- **We got:** 506 products carry deposits. None of the 7 codes is a catalog product, and `/api/price` returns `error: true` for all 7.
- **Example to show:**

  ```
  Product file, 476204 (Bundaberg Ginger Beer 12 × 37.5 cl), catalogPrice 22.09:
    "deposits": [{"material": "1", "unit": "ST", "quantity": 12.0}]

  POST /api/price   {"customer": "123", "requestedDate": "2026-11-16", "products": ["1"]}
    {"productId": "1", "quantity": 1.0, "netPriceFound": false, "error": true}
  ```

- **Ask:** "Is that expected? Is the deposit already inside catalogPrice, or charged on top — and if on top, what is the value per code?"
- **If no answer, we build:** totals exclude deposits and say so.

## Q9 — Variable-weight products

- **We did:** counted `variableUnit: true` in the catalog and checked how those products are priced in the sample.
- **We got:** 632 products, 628 of them sold in KG. All 37 that fell in the sample are priced per kg (`catalogPrice` equals `comparisonPrice`).
- **Example to show** — `467620` Atria cooked beef strips "ca 2 kg": sold in `KG`, `allowedLotSize` 2.0, `catalogPrice` 20.99 and `comparisonPrice` 20.99 per KG. For an order of 2 kg: is the invoice 2 × 20.99 = 41.98, or the actual weight × 20.99?
- **Ask:** "If an agent orders 10 kg of a variable-weight product, is the delivered and invoiced weight exactly 10 kg, or the actual weight?"
- **If no answer, we build:** variable-weight lines go to a human, because the final amount may differ from the offer.

## Q10 — Sales unit differs between the API and the product file

- **We did:** compared `salesUnit` on each `/api/availability` line with `salesUnit` in the product file.
- **We got:** they differ on 7 of 797 lines.
- **Example to show** — `460657` Marli Natur tomato juice 1 L:

  | Source | Unit |
  |---|---|
  | Product file | `salesUnit` `KI` (1 KI = 10 ST) |
  | `/api/availability` line | `salesUnit` `ST`, `availableAmount` 112 |
  | `/api/price` | 2.26, and 2.26 per L — the price of one 1 L carton, not of a case of ten |

- **Ask:** "Is that expected? Which unit do the price and the available amount refer to?"
- **If no answer, we build:** price and quantity follow the unit on the API line.

## Q11 — Category codes

- **Context:** your brief asks for "good-better-best" substitution ranking; category names are not in the data.
- **We did:** compared the categories of the two products in each of your 250 substitution pairs.
- **We got:** 230 pairs stay in the same 5-digit category. Of the other 20, 11 share the first 4 digits and 5 share only the first 3.
- **Example to show** — three of your substitution pairs:

  | Product → substitute | Categories | Shared digits |
  |---|---|---|
  | `460027` Tomato NL/BE/ES → `460065` Tomato Finland | 17401 → 17401 | all 5 |
  | `461480` Myllyn Paras strawberry-rhubarb pie → `461927` Myllyn Paras berry-mix pie | 41765 → 41763 | first 4 |
  | `460211` White cabbage Finland → `467530` SallaCarte shredded cabbage 1 kg | 17404 → 17443 | first 3 |

- **Ask:** "Is the category code a hierarchy — which digits are the levels? And can we have the category names?"
- **If no answer, we build:** substitute tiers — same category → same 4 digits → same 3 digits (labelled weaker).

## Q12 — Delivery reliability

- **We did:** joined the delivery-reliability file to the catalog.
- **We got:** 4,425 of 17,546 products have a value (25.2%). 56.3% of those are exactly 1.0 and 12 are 0.0.
- **Example to show:**

  | Product | `deliveryReliability` | Availability on Friday |
  |---|---|---|
  | `464306` Eila milk drink 1 l | 1.0 | Stock, 9999999999 |
  | `473463` Atria beef tenderloin ca 2.4 kg | 0.332 | `availableAmount` 0 |
  | `463038` Valio Eila milk drink 10 l | no row in the file | Terminal, 999999 |

- **Ask:** "What exactly does the number measure, and does a missing value mean no delivery history?"
- **If no answer, we build:** missing means "no history" and is never imputed; we show the raw value without a gloss.

## Q13 — Call volume

- **We did:** 34 requests on Friday night, at least 3 seconds apart, up to 251 products each.
- **We got:** no 429 and no rate-limit headers.
- **Ask:** "Is that volume fine during judging? Our demo makes about N calls of at most 50 products." *(fill in N)*
- **If no answer, we build:** filter locally, a few narrow calls per run, a response cache and a recorded-response fallback.

---

## Ask any Valio person

- "How and when do you judge — at our table, the video, or the deployed link — and will the mock API stay up unchanged until then?"
- "Do exception cases have to run in the live demo, or does a documented rule count?"
- "The brief mentions webshop test accounts. Are they available?"
- "The hackathon requires a public MIT repository. May the datasets and a few recorded responses of the mock API stay in it, or should we keep them out?"

---

## Raised during the overnight build

The build agents add questions here in the same shape as above. Empty until the run starts.

### For Valio

**T01-1 · Must an agent send a named User-Agent?** (from the Valio client)
- **Context:** the API sits behind Cloudflare. The brief wants the wholesaler "openly readable by autonomous agents"; many agents call through an HTTP library with its default user agent.
- **We did:** called `GET /api/ping` with the same key and two user agents (14 Nov, 02:40), then `/api/availability` and `/api/price` at 03:13 with `User-Agent: tta-gateway/0.1`.
- **We got:** 403 with Python's default user agent, 200 a minute later with a named one; 200 on both later calls.
- **Example to show:** the same ping, once with the library default and once with `User-Agent: tta-gateway/0.1`.
- **Ask:** "A call with a library's default User-Agent got 403 while the same key with a named one got 200 — is that expected, or did we get something wrong? If expected, is a named User-Agent the rule an external agent should follow?"
- **If no answer, we build:** the client always sends a named User-Agent and `Accept: application/json`; a 403 is reported once as `supplier-unavailable` with that hint and never retried.

**T03-1 · `471881` is named "gluten free" and declares cereals containing gluten** (from the allergen package; whole catalog)
- **Context:** the substitution check: a substitute must not declare an allergen the original does not declare. `473609` (Oddlygood Barista oat drink 1 l, gluten free) lists three substitutes.
- **We did:** compared the `allergen` group of `473609` with that of each listed substitute.
- **We got:** `473609` and `471690` declare only oats (`GO` CONTAINS). `471881` — the 0.5 l pack of the same drink, named "gluten free", claim `FREE_FROM_GLUTEN` — declares `AW` CONTAINS as well.
- **Example to show:** `473609` → `GO`; `471690` → `GO`; `471881` → **`AW`**, `GO`.
- **Ask:** "The 0.5 l pack of the same gluten-free oat drink declares cereals containing gluten and the 1 l packs do not. Is that expected, or did we get something wrong?"
- **If no answer, we build:** the allergen declaration counts, never the name or the claim. `471881` fails the substitution rule and cannot be ordered as a substitute for `473609`. This is in demo scenario 3.

**T03-2 · A family stated "free from" while one of its members is declared** (whole catalog)
- **Context:** a buyer excludes a family code such as `AW` (cereals containing gluten) or `AN` (tree nuts); we also read the member codes (wheat, oats, almonds).
- **We did:** counted products whose `nonAllergen` group holds the family while the `allergen` group declares a member.
- **We got:** 176 distinct products (two count under both `AW` and `AN`): 132 for `AW` (76 with oats, 35 with wheat CONTAINS), 45 for `AN`, 1 for `AM` with lactose.
- **Example to show:** `460124` Fria loaf "glutenfree": `AW` FREE_FROM and `UW` (wheat) CONTAINS · `461333` Toblerone: `AN` FREE_FROM and `SA` (almonds) CONTAINS.
- **Ask:** "We read 'free from gluten cereals' with 'contains wheat' as gluten-free wheat starch, and 'free from tree nuts' with 'contains almonds' as a data error. Is that expected, or did we get something wrong?"
- **If no answer, we build:** two statements, the least safe counts: with the family excluded, a declared member rejects the product (oats go to a dietitian).

**T02-1 · Is an `allowedLotSize` of 0.01 "no step"?** (from the catalog package; whole catalog)
- **Context:** `allowedLotSize` is 0.01 on 16,872 of 17,546 products, including 16,476 of the 16,478 not sold by the kilogram (cartons, cases, bags, bottles). A real step (1.5, 3.0 …) is on 674 products, 672 of them sold by the kilogram.
- **We did:** rounded every quantity up to the product's step.
- **We got:** for a countable sales unit a 0.01 step allows a fraction of a case. In our captures (a sample of 1,745 ids) no `availableAmount` has a fraction.
- **Example to show:** `463038`, "Valio Eila semi skimmed milk drink 10 l novobox lactose free", sales unit `KI` (a case of two 10-litre boxes), lot 0.01: 250 litres is 12.5 cases.
- **Ask:** "We read 0.01 as 'no step set' and order whole cartons and cases, so 13 cases here. Is that expected, or did we get something wrong?"
- **If no answer, we build:** whole units for every sales unit except `KG`; kilogram products with 0.01 keep 0.01 kg steps; a real step is used as given.

**T02-2 · What does `comparisonPrice` divide by?** (sample of 1,321 captured price lines)
- **Context:** no field states the litres or kilograms in one sales unit. We derive it as `catalogPrice ÷ comparisonPrice`.
- **We did:** compared that ratio with the product file (`unitConversions`, else the size in the name).
- **We got:** the ratio is rounded because both prices have two decimals (8.75 ÷ 0.88 = 9.943 for a 10-litre box). The file's figure fits on 186 of 190 litre lines and 481 of 513 kg lines. Where it does not, the comparison price seems to use another weight than `netWeight`.
- **Example to show:** `460396` "Valio skimmed milk 10 l novobox": ratio 9.943, file says 10 litres. `466382` "Filos feta cubes in brine 2kg": `netWeight` 3.39 kg, ratio 2.0.
- **Ask:** "We take `comparisonPrice` to be `catalogPrice` divided by the content of one sales unit (drained weight where there is one), rounded to cents. Is that expected, or did we get something wrong?"
- **If no answer, we build:** the file's figure when it is consistent with the two prices (10 litres, not 9.943), otherwise the ratio.

**T07-5 · Is a listed substitute meant across sales units?** (from the offers package)
- **Context:** the product file lists substitutes for 189 products. We convert quantities through litres or kilograms per sales unit.
- **We did:** looked up the substitutes of `473609` (Oddlygood Barista oat drink 1 l, sold by the piece, €1.37).
- **We got:** the listed substitute `471690` (the same drink, "Delight") is sold by the case of 10 litres at €15.55, so 100 pieces of the original become 10 cases. Tonight its order cut-off has also passed (Thursday 12 Nov 15:00).
- **Ask:** "When a listed substitute is sold in another sales unit than the original, do you expect the buyer to convert the quantity by volume, as we do — is that expected, or did we get something wrong?"
- **If no answer, we build:** quantities are converted through the pack size and rounded up to the lot step.

**SCOPE-1 · Which of your example scenarios would you most like to see? — ask this first** (from the team, Saturday morning)
- **Context:** the brief lists six "example scenarios to spark ideas". We built the core you ask for — lookup, an offer at fixed prices, an order placed by the agent within its authority or sent to a named human, and an audit trail for buyer and Valio — plus two of the six: allergen-safe substitution in a hospital kitchen, and a substitute when a product cannot be supplied.
- **What we can build next, today:** (a) a page where the buyer sets what its agent may decide alone (spend limits, allergens, substitutes); (b) a standing weekly order and a guardrail that sends a renewal to a human when quantities or cost drift; (c) recipe → order: a menu planned around a seasonal ingredient, scaled to the number of covers, with substitutes following the recipe; (d) Valio's own agent suggesting a product to the buyer's agent.
- **Example to show:** scenario 2 on the live demo (https://joaocostared--trusted-trade-agents.us-east.modal.run): the ward's agent orders 200 L of soya drink alone, €402.00; then scenario 1, where the hotel's €2,580.64 order goes to the purchasing manager.
- **Ask:** "Of the scenarios in your brief, which would you most like to see an agent do on top of this — the buyer setting its agent's limits, standing-order drift, recipe to order, or your own selling agent?"
- **Follow-ups, if there is time:**
  1. "Do your customers set their own ordering limits and approvers today, or does Valio Aimo set them in the customer account?"
  2. "The mock has no order history. May we define a kitchen's standing order ourselves, or do you have example order patterns?"
  3. "The product file has no field for new or seasonal products, and no recipes. How would your agent know a product is seasonal — is there a field we missed, or should we bring our own small list?"
- **If no answer, we build:** (a) and (b) first, both in the controls criterion; (c) if time allows; (d) last, with a lower-carbon alternative from the carbon file instead of "seasonal".

### For the team

**T04-1 · Which claims must be confirmed before the agent orders alone?** (from the availability package)
- **Context:** every offer line states five claims (price, quantity, delivery date, allergens, origin), each confirmed, unknown or ruled out. The plan says the agent orders alone only when "every claim is confirmed".
- **We did:** ran the rule on tonight's capture.
- **We got:** read over all five claims, a request with no date can never be ordered by the agent (the delivery-date claim is "unknown" because nothing was asked), and neither can any of the 80 catalog products with no country of origin.
- **Example to show:** `469363`, 384 units confirmed, cut-off Sunday 17:00 — with "by Monday" all five are confirmed; with no date the delivery-date claim is unknown.
- **Ask:** "Should the agent be held back by a claim the buyer did not ask about?"
- **Built overnight (change it if you disagree):** price, quantity and allergens always count; the delivery date counts only when the request gives a date; origin is shown and never holds an order back (SPEC §4).

**T01-2 · Which date do we send as `requestedDate`?** (from the Valio client)
- **Context:** both endpoints require `requestedDate`; the mock ignores it (24 products × 4 dates gave identical product fields).
- **We did:** the client sends the clock's current date; tonight's capture was taken with 2026-11-16.
- **We got:** the same answer for both dates (`469363`: 384 units, €2.48, cut-off Sunday 17:00, delivery 16 Nov).
- **Ask:** "Should the buyer's needed-by date be passed down to the Valio call, for a real API that honours it?"
- **Built overnight:** the clock's current date. The needed-by date is compared with `availableDate` in our own code, so the demo does not depend on it. Passing the date down is listed as a next step (it needs one argument on two port methods).

**T03-3 · Gluten-free wheat starch under a "no gluten" exclusion** (from the allergen package; whole catalog)
- **Context:** declared oats go to a dietitian when `AW` is excluded, because gluten-free oats exist. The catalog shows the same pattern for wheat.
- **We got:** 35 products state `AW` FREE_FROM and wheat CONTAINS; the rule rejects them. 243 products go to a dietitian through the oat rule.
- **Example to show:** `460124` Fria Fiber-rich loaf, "glutenfree" → rejected for a ward that excludes `AW`.
- **Ask (for the biomedical side of the team):** "Should gluten-free wheat starch go to a dietitian like oats, instead of being rejected?"
- **Built overnight:** rejected, the safer reading. Only oats have the exception.

**T06-1 · What does Valio see about our rules and approvers?** (from the audit package)
- **Context:** the plan says Valio does not see the buyer's limit values, allergen exclusions, approver names and notes. It does not say whether Valio sees which rule sent an order to a human.
- **Built overnight:** in the supplier view a human is "A human at the buyer" (no name, role or note). Valio sees only the rules about its own data — F-01 (quantity not confirmed), F-03, F-04, F-05, F-06 — and none of the buyer's own rules (spend limits, fill ratio, allergen exclusions).
- **Example to show:** the hotel order approved on the unconfirmed alternative reads, for Valio: "A human at the buyer approved order ord_1 and chose another option of the same offer: opt_2 (1,000 ST of 464306 for €1,010.00 net)", with rule F-01 only.
- **Ask:** "Is that the split we want to show the judges?" The list is `SUPPLIER_RULE_MEANINGS` in `src/tta/audit/readers.py`.

**T06-2 · Which clock stamps the audit events in replay?**
- **Context:** in replay the data clock is pinned to the capture's `timeNow`, so every audit event of a demo run would carry the same time, the human's approval included.
- **Built overnight:** the audit trail is stamped with the real time; the pinned clock is used only for cut-offs and price validity. The offer still records the data time it was built against.
- **Ask:** "Is real time on the audit trail what you expect to see in the demo?"

**T02-3 · Is 50 g the right limit for a portion pack?** (from the catalog package; whole catalog)
- **Context:** a request in litres or kg leaves out single-serve packs: an inner unit of 5 cl or 50 g or less.
- **We got:** 744 of 17,546 products are portion packs by this rule. `463203` (100 × 2 cl milk) is one, as intended — but so are `468798` "6x Meira black peppercorn mill 49g" and `465619` "Findus Fishfinger ca 360x28g".
- **Ask:** "Keep 50 g, lower it, or apply the rule only to drinks and spreads?"
- **Built overnight:** the limit as written. The exclusion is shown with its reason, and `pack: ANY` on the request turns it off.

**T02-4 · The `milk` product type is the whole of category 10400** (noted by the orchestrator)
- **Context:** the product-type table is ours (29 types, derived from the names in each category). `milk` is category 10400: 91 products, of which 88 are milk; the other three are a sour milk, a coffee drink and a soy yoghurt. Lactose-free milk = `milk` + claim `FREE_FROM_LACTOSE` = 35 products, among them lactose-free sour milks (`477050`, `476957`).
- **Ask:** "Should a request for 'milk' leave out sour milk and coffee drinks?" Tonight none of them is the cheapest option, so the demo is not affected.

**T05-1 · Does "same category" also accept a substitute Valio lists from another category?** (from the policy package)
- **Context:** the profile setting `substitution_without_approval` has three values: `NONE` · `LISTED_BY_SUPPLIER` · `SAME_CATEGORY`. Of Valio's 250 listed pairs, 20 leave the 5-digit category (whole catalog).
- **Built overnight:** a widening scale. Under `SAME_CATEGORY` a substitute Valio lists is accepted without a human even from another category; an unlisted one must be in the same 5-digit category. One line in `src/tta/policy/rules.yaml` (`substitution_scopes`) changes it.
- **Ask:** "Is that the reading we want?"

**T05-2 · The allergy ward's settings for variable weight and deposits**
- **Context:** the plan sets both to "needs approval" for the hotel and names neither for the ward.
- **Built overnight:** both "needs approval" for the ward as well, the cautious value. Scenario 2 is not affected (`464056` has no deposit and is not sold by variable weight).
- **Ask:** "Agreed?"

**T05-3 · Demo approvers** (settled by the orchestrator, for information)
- Every role now has a demo person on both profiles: hotel — purchasing manager, finance, dietitian; ward — dietitian, purchasing manager, finance. Without that, an approval needing a role nobody holds could never complete. Names and ids are placeholders in the two profile files.

**T08-1 · A price changes while an order waits for approval** (from the orders package)
- **Built overnight:** the approver gets `offer-stale` (or `offer-expired`), one "order not placed" event is written, and the order keeps waiting. The approver can still pick another option or reject; otherwise the order expires at its "order by" time. Until then it counts in the day's spend.
- **Ask:** "Should a failed re-check close the order at once instead?"

**T08-2 · An approval does not carry over to another option**
- **Built overnight:** when an approver picks another option of the same offer, the approval starts again on that option: earlier approvals were for something else. They stay in the audit trail.
- **Example to show:** finance approves option 1 (€3,180.00); the purchasing manager then picks option 2 (€3,445.00); the order waits for finance again.
- **Ask:** "Agreed?"

**T08-3 · A refused attempt names the caller in the target's trail**
- **Built overnight:** every refused attempt to decide an approval is recorded with the approval it was aimed at. If the ward's dietitian tries to decide a hotel approval, the hotel's trail shows that person's demo name and role.
- **Ask:** "Should the trail of the targeted buyer say only 'an approver of another buyer'?"

**T08-4 · No separate "policy evaluated" event at order time**
- **Built overnight:** the outcome event (placed by agent, approval requested, blocked, not placed) carries the policy decision, the facts it read and the policy hash. A separate "policy evaluated" event is written when the offer is built.
- **Ask:** "Is one event per outcome what we want on the timeline?"

**FIX3-1 · Is a milk for coffee what a buyer who asks for "milk" expects?** (answers T02-4 in part)
- **Built overnight:** the `milk` type now leaves out the 13 products of category 10400 that are not milk (11 sour milks, a coffee drink, a soy yoghurt): 78 of 91 stay, and lactose-free milk is 30 products instead of 35. A new type `sour_milk` holds the 11 (the table has 30 types).
- **Still in `milk`:** four milks sold for coffee — `462626`, `464237` "Valio coffee milk", `473142` "coffee milk drink vanilla" and `463380` "Arla Cafè milk 1 L UHT lactose free".
- **Why it matters tonight:** `463380` supplies 565 of the 1,000 litres in scenario 1's best option. Without it the confirmed lactose-free milks cover 435 litres and option 1 becomes a partial fill.
- **Ask:** "Keep the coffee milks in `milk`? Drop the vanilla one?" Leaving one out is one term in `exclude_terms` of `milk` in `src/tta/catalog/product_types.yaml`.

**T07-1 · A substitute that drops a claim of the original** (settled by the orchestrator, for information)
- **Found:** the substitution rule looks at allergens only, so regular milk passed as a stand-in for a lactose-free milk named by id, and the hotel's agent could order it alone.
- **Decided overnight:** a new fixed rule F-08 — a substitute that lacks a nutritional claim the original carries (lactose-free, gluten-free) always goes to a human. Substitutes that keep every claim are ranked first.

**T07-2 · A stand-in when the named product is only "quantity not confirmed"**
- **Built overnight:** when a product asked for by id has no confirmed stock (also when its quantity is just not confirmed, or its cut-off has passed), the offer puts a confirmed stand-in first and the named product second as the unconfirmed alternative.
- **Example to show:** `473609` by id, 100 L, hotel: option 1 stand-in `475224` (€174.00, agent may order), option 2 `473609` itself (€137.00, needs a human).
- **Ask:** "Is the stand-in first what a buyer expects?"

**T07-3 · A partial fill of the product asked for, or a full fill with a stand-in, first?**
- **Built overnight:** the product asked for comes first (40 of 100 L, needs a human for the short fill); the full fill with a stand-in is option 2.
- **Ask:** "Should the full fill come first?"

**T07-4 · Is stock that moved but still covers the order a change?**
- **Built overnight:** at the re-check before an order, stock is a change only when it no longer covers what the order takes. A price difference in either direction, a new cut-off and a new price validity are always changes.
- **Ask:** "Agreed?"

**T07-6 · Tonight's scenario products** (for information)
- Scenario 1: 384 × `469363` + 51 × `462775` + 565 × `463380` = €2,580.64, full fill, needs the purchasing manager (over €750). Alternative: 1,000 × `464306` = €1,010.00, quantity not confirmed.
- Scenario 2: 200 × `464013` Alpro No Sugars Soya drink 1 L = €402.00, ordered by the agent alone. Friday's plan named `464056` (€2.14); `464013` is cheaper tonight and states the same free-from.
- Scenario 3: `471690` passes the allergen rule but its cut-off has passed tonight; `471881` and `464320` fail (they add `AW`). The best stand-in that can be ordered is `475224` Fazer Aito Barista oat drink, gluten-free.
- Backup: 30 kg → 30 × `466988` = €506.40, a ceiling, needs a human (variable weight).

**T07-7 · Which claims of the original must a substitute keep?** (for the biomedical side of the team)
- **Context:** rule F-08 sends a substitute to a human when it lacks a nutritional claim the original carries, and such substitutes rank after those that keep every claim. The catalog has 21 claim codes.
- **Decided overnight:** only dietary claims count — `FREE_FROM_LACTOSE`, `LOW_LACTOSE`, `FREE_FROM_GLUTEN`, `FREE_FROM_WHEAT`, `FREE_FROM_EGGS`, `FREE_FROM_SOY`, `VEGAN`, `VEGETARIAN`. Claims about preservatives, colouring agents, additives, sugars, sweeteners, fibre, protein, salt, fat and GMO are named in the "what the buyer gives up" sentence and change nothing else.
- **Why:** counting every claim made a rice drink the best stand-in for a gluten-free barista oat drink, ahead of another barista oat drink that only lacks "free from preservatives".
- **Ask:** "Is that the right list? Should `NO_ADDED_SUGARS` or `LOW_SODIUM_SALT` count for a hospital?" The list is one constant in `src/tta/offers/substitutes.py`.

**FIX6-1 · A product that fits and is not needed: a listed reason, or a note?**
- **Built overnight:** every product that drops out is listed with a reason code and a sentence. A product that passes every check but is in no option (a cheaper one covers the quantity) is named in one note per request line, not in the exclusions list.
- **Tonight:** scenario 1 — 30 candidates = 4 in the two options + 19 excluded + 7 fitting and not needed. Scenario 2 — 51 = 1 + 41 + 9.
- **Ask:** "Should 'fits, not needed' be a reason code of its own so the page can show it in the same table?" One function changes (`_unused_notes` in `src/tta/offers/builder.py`).

**FIX6-2 · Where the price stands in the option order**
- **Built overnight:** options are ordered by: holds an unconfirmed quantity (always after the others), unmet checks, unverified checks, kind (best confirmed, unconfirmed alternative, substitute), net total. An offer has at most one option of each kind, so the price decides nothing today.
- **Ask:** "Should the cheaper of two options that fit alike come first whatever its kind?"

**FIX7-1 · Who completes an approval when the rules no longer ask for anybody?**
- **Context:** an approval re-runs the rules at the moment of approving. Sometimes they then need nobody (the day's spend fell back because another order was rejected).
- **Built overnight:** any approver listed for that buyer can then complete the order; it is recorded as placed with that person's approval.
- **Ask:** "Agreed, or should it still need the role first asked for?"

**FIX7-2 · One order per offer**
- **Built overnight:** while an order of an offer is waiting or ordered, a second order on the same offer is refused and the answer names the existing order. After a rejection or an expiry the offer can be ordered again. Before, the same option could be ordered twice under two keys.
- **Ask:** "Agreed?" A repeat purchase asks for a new offer.

**T09-1 · "Request received" is not yet in an order's trail**
- **Context:** the trail of an order is found through its offer. The event with the buyer's pasted words is written before any offer exists, so the order's timeline starts at "request parsed".
- **Planned overnight (fix task after review round 3):** the offer step writes "request received" itself, from the words kept on each request line, so the timeline starts with what the buyer wrote.

**T09-2 · An agent cannot list approvals**
- **Built overnight:** the gateway refuses an agent on the approval list as well as on the decision (403). An approver may read its own buyer's authority, catalog, offers, orders and audit trail, and decide approvals. The supplier reads the audit trail only.
- **Ask:** "Should the agent be able to see that its order is waiting, through the approvals list?" It already sees the order's status.

**T09-3 · Rate limits on the public demo**
- **Built overnight:** 60 calls a minute per token; 240 a minute for the shared demo tokens, because every visitor of the demo uses the same ones. Request bodies are capped at 64 KB and lists at 100 items.
- **Ask:** "Are those numbers right for the judging session?" They are constants in `src/tta/api/limits.py`.

**T09-4 · Pages exist only in dev and demo**
- **Built overnight:** the pages act as a demo identity chosen on the page, with no login, so they are mounted only when `TTA_ENV` is `dev` or `demo`. The API and the MCP surface take a bearer token in every environment.
- **Ask:** "Agreed that a production deployment would have no pages until there is a login?"

**T11-1 · Over MCP, "get offer" makes a new offer; nothing reads a stored one**
- **Context:** the plan names eight MCP tools and one offer tool, `get_offer`. REST has two: make an offer, and read a stored one by id.
- **Built overnight:** the MCP tool `get_offer` takes the typed request and makes a new offer each time. When an order is refused as stale, the answer carries the id of a fresh offer, but no MCP tool can read an offer by id, so an MCP agent asks again with the request.
- **Ask:** "Add a ninth tool that reads a stored offer by id?" It is one function in `src/tta/api/mcp_surface.py`.

**T11-2 · The MCP address** (for information)
- The endpoint is `/mcp/`. The exact path `/mcp` without the last slash is being routed to the same place in the API fix (FIX-8); until that is in, give MCP hosts the address with the slash. Header: `Authorization: Bearer <token>`; in the demo, for example `demo-agent-allergy-ward`.
- Not checked yet with a third-party MCP host (Claude Desktop, MCP Inspector): only with the official SDK client, in both protocol versions it speaks.

**T10-1 · When Gemini is down and a key is set, should the recorded answers take over?** (from the buyer agent)
- **Context:** without a key the parser and the agent run on the recordings in `fixtures/agent/`. With a key they call Gemini, and when Gemini cannot be reached they answer `supplier-unavailable`.
- **We got:** on 14 Nov Gemini answered 503 to every request of the live check (05:35, and again at 07:45), so with the key set the pasted scenario sentence fails while the same sentence works without a key.
- **Ask:** "For the demo, should a known scenario sentence fall back to its recording, labelled as such, when Gemini does not answer?" (orchestrator's recommendation: yes.)

**T10-2 · What a trace calls answers a person wrote**
- **Built overnight:** the recordings were written by hand because the live check got no answer; a run served from them shows `model: "hand-built"`. Once `python -m tta.agent.record` succeeds, its runs say `model: "recorded"`.

**T10-3 · "By Monday" said on a Monday**
- **Built overnight:** a weekday means the first such day after today, so "by Monday" said on Monday 16 Nov means Monday 23 Nov. The parser refuses only a date before today.
- **Ask:** "Is next Monday right, or should it be refused as unclear?"

**T10-4 · The model cannot name an offer, a product or a quantity** (for information)
- The model sees four functions: authority, create offer, place order (an option id only) and order status. The offer is built for the request the parser read, an order names an option of the run's latest offer, and one run places one order. The gateway's verdict applies to whichever option the model picks.

**T10-5 · The recorded run of scenario 1 is hand-written by design**
- The live check records the run of scenario 2 only; scenario 1's run file holds the same three calls, marked hand-built.

**FIX8-1 · Per-visitor limits on the deployed demo depend on the address Modal hands the app**
- **Built overnight:** each visitor using a shared demo token gets its own rate-limit window, keyed by the client address (the first `X-Forwarded-For` address when the direct peer is private). Global ceilings per minute: 120 offers and substitute searches, 120 orders and decisions, 30 model calls; at most 6 live looks a minute reach the Valio mock, above that the recorded capture answers, labelled replay.
- **Not checked on Modal yet:** which peer address the app sees there. Check after deploying: from two phones on different networks, three offers each with the ward token and the limit set to 2 — each phone should get 201, 201, 429.

**FIX8-2 · What `/healthz` shows**
- **Built overnight:** `ok` or `degraded` with reasons, the mode asked for, the source of the last answer, the audit head (event count and last hash), which optional parts are in, and which settings are set (true or false only, never a value or the budget).
- **Ask:** "Keep the environment name and the capture name in the public health answer?"

**FIX8-3 · Live mode without a supplier key**
- **Built overnight:** it serves the recorded capture and `/healthz` says `degraded`. A configuration that is wrong in another way (a base URL that is not https) stops the start.
- **Ask:** "Should a missing key stop the start too?"

**T12-1 · Repeated demos on one database change the outcome — decide before the public link is shared** (from the pages)
- **Context:** the daily spend limit counts the buyer's orders of the data clock's date. In replay the clock is pinned to the capture (Saturday 14 Nov 02:52), so that day never ends.
- **We got:** scenario 2 is "Ordered by the agent" three times; the fourth run goes to finance, because 4 × €402.00 is above the ward's €1,500 a day. Scenario 1 a second time needs finance too. The gateway is right each time — it shows rule P-02 working — but on a public demo link every visitor adds to the same day.
- **Built overnight:** nothing in the gateway. The demo script starts from an empty database and runs each scenario once, in the order 1, 2, 3.
- **Ask:** "For the deployed link, do we accept that later visitors may see the daily limit apply, or do we want a demo-only reset (which would break 'append-only' on a public link)?" Orchestrator's view: accept it and say so on the page; the sentence on screen explains it.

**T12-2 · The beef backup has no one-click example**
- **Built overnight:** three examples (scenarios 1, 2, 3). Without a Gemini key the backup sentence cannot be read from the page. A fourth button is one entry in `EXAMPLES` of `src/tta/ui/examples.py`.

**T12-3 · Scenario 3 ends with the hotel's agent ordering a substitute alone**
- **Built overnight:** scenario 3 is "100 litres of Oddlygood Barista oat drink, product 473609, by Monday", asked by the hotel kitchen. Tonight option 1 is the substitute `475224` (€174.00), and the hotel's profile allows a substitute in the same category, so the agent orders it alone; `473609` itself is option 2 (quantity not confirmed). The ranked substitutes are shown below: `471690` passes but its cut-off has passed; `464320` and `471881` add gluten and can never be ordered.
- **Ask:** "Is that the story, or should the allergy ward ask it (its profile allows no substitute without a human)?" Changing who asks is one field of the example.

**T12-4 · The agent's steps are not stored**
- **Built overnight:** the page keeps the last 200 agent runs in memory; after a restart the offer, the order and the outcome are still there, the agent's steps are not.

**T13-1 · The partial fill of scenario 1 needs 1,500 litres tonight** (from the scenarios task, for information)
- Tonight three confirmed milks cover 1,000 L in full (€2,580.64, needs the purchasing manager by P-01). The partial fill and rule P-03 of the plan come back with **1,500 litres**: 1,133 L confirmed, 75.5% covered, P-01 and P-03, €2,933.09. It is tested and is a Q&A moment in `docs/DEMO.md`.
- The live run (6 calls to the Valio mock at 08:12) matched the 02:52 capture exactly: same products, stock, prices, cut-offs and verdicts.
- The shared day spend on the public link is question T12-1.

**T14-1 · The database on Modal is a copy kept on a Volume** (from the deployment, for information)
- Modal Volumes have no file locking and SQLite's WAL mode fails on network file systems, so the database runs on the container's local disk; a copy is put back from the Volume at start and saved to it about a second after each change and at shutdown. The call budget and the live recordings are written straight to the Volume. One container at most, scale to zero, stops after 10 idle minutes.
- Redeploy with `.venv/bin/modal deploy --strategy recreate deploy/modal_app.py`, so an old and a new container never write the copy together.

**T14-2 · Reset the shared order book before peer review?**
- Every visitor of the deployed link shares one order book, so the ward's autonomous order (scenario 2, €402) goes through alone three times a day and then goes to finance (question T12-1). `docs/DEPLOY.md` gives the steps to start the judging day on an empty database.
- **Ask:** "Reset it at 10:00 on Sunday, before peer review starts?" Orchestrator's view: yes.

---

## Claims we no longer make

Earlier versions of this page (including the 16-row table still on the `bio1` branch) said these.

| Earlier claim | What holds |
|---|---|
| Unknown stock, passed cut-offs and undeliverable products are faults or contradictions in the mock | They are the "availability behaviour" the brief says the mock brings. We handle them and explain; we do not report them |
| "Is there an order endpoint?" as a question for Valio | Settled: the order step is ours to define |
| "Every Terminal product's closingTime is 2026-11-12T15:00" | 229 of 357 (64%); 12 distinct values. What holds: all 357 are in the past |
| "Respecting cut-offs rejects half the catalog" | 42.5% of the sample; 53% of products that have a schedule line |
| "`salesBlock` is never true" | True once in 1,000 (`470094`) |
| "~14% of products are undeliverable" | 20.3% have no schedule line, plus 2.9% with amount 0 |
| "Three sentinels in `availableAmount`" | Two rules: Terminal 999999; Stock 9,999,999,999 ÷ base units per sales unit (9 distinct values in the sample) |
| "Three dates → byte-identical responses" | Per-product fields identical; the echoed date and `timeNow` differ |
| "`comparisonPrice` missing on 22.5%" | 20.6% of the sample |
| "Price ratio = pack size, so we never need the unit codes" | It gives kg or litres per priced unit, not a count, and is unavailable for 1 product in 5 |
| "Unknown id cannot be told from undeliverable" | True for `/api/availability` only; `/api/price` returns `error: true` for non-catalog ids |
| "`variableUnit` makes a fixed-price commitment impossible" | 628 of 632 are sold in KG and all 37 sampled are priced per kg; the open point is delivered vs ordered weight (Q9) |
| "~59% of the catalog has no allergen statement" | 58.9% have an empty `allergen` group; 46.2% have neither group; 30.6% of food products |
| "Lactose trap: 35% of lactose-free products declare milk" | The count is right (1,485 of 4,178) but it is correct labelling: lactose-free milk is still milk, including our demo product `464306` |
| "`X99` names no substance" | GS1: "Does not contain declaration obligatory allergens in the product" |
