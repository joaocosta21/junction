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

## Valio client (T01)
- The live clock is the server's last `timeNow` carried forward by the time passed since; before the first availability answer it is UTC now. Only an availability answer moves it (`/api/price` states no server time).
- `requestedDate` sent to the mock is the clock's current date; the mock ignores it. Passing the buyer's needed-by date down is a next step.
- Cache: 60 seconds, keyed by endpoint and the sorted distinct ids of the whole call. A cache hit costs no budget.
- Call budget: every HTTP attempt counts, retries included; the count is kept in `var/valio_call_budget.json`. A budget file that cannot be read stops every call.
- Retries: a time-out or a 5xx, after 1 s and 2 s. A 4xx (429 included) and a connection failure are reported at once.
- Every failure of the supplier call is `supplier-unavailable`; the underlying HTTP error is never attached, because it holds the request and the request holds the key.
- Parsing is strict: a body that breaks the published shape, or leaves out a requested id, refuses the whole answer.
- Replay answers an id outside the capture as the live API answers an unknown id (confirmed live with `459999`).
- Live mode needs a writable data directory: every answer is recorded, and the call fails if it cannot be.
- Agents must identify themselves: the client sends `User-Agent: tta-gateway/0.1` (question T01-1).

## Allergens (T03)
- `X99` is a general statement, never a statement about one allergen: under `STRICT` the product goes to a dietitian, under `DECLARED_ONLY` it passes as unverified. `X99` cannot be excluded and is never an "added allergen" (195 products carry it).
- Families: `AW` → `UW GB NR GO GS GK`; `AN` → `SA SH SW SC ST SM SP SR`; `AM` → `ML`; `AF` → `ABD ADQ` (tuna `ABD` under fish is our reading).
- Family excluded: a member `CONTAINS` rejects, a member `MAY_CONTAIN` goes to a human; a member stated `FREE_FROM` says nothing about the family.
- Oats: with `AW` excluded, declared `GO` goes to a dietitian under both strictness values, unless another gluten cereal is declared `CONTAINS` (then rejected). 243 catalog products go to a human this way.
- Member excluded with no statement of its own and a declared family: reported as `MAY_CONTAIN`, to a human (keeps lactose-free milk from being rejected when only lactose is excluded).
- A family stated `FREE_FROM` is not read as a statement about a member (178 products state a family free-from and still declare a member).
- Conflicting statements: least safe wins, in the order `CONTAINS`, `MAY_CONTAIN`, `UNDECLARED`, `FREE_FROM`. Gluten-free wheat starch (35 products) is therefore rejected for a "no gluten" buyer (question T03-3).
- Substitution rule compares codes one by one, without families, and looks at the code, not the level. 37 of 249 listed substitutes fail it (whole catalog).
- An original with no allergen statement and a substitute that declares one fails the rule.
- An excluded code outside the code table raises `invalid-request`; so does an exclusion with no strictness.
- GS1 allergen names come from GS1 code list T4078 (read 14 Nov); 8 match the names our docs quote, the other 37 deserve a spot check.

## Store and audit trail (T06)
- One hash chain for the whole trail (Gabriela's draft had one per order). The first event's previous hash is 64 zeros.
- Event hash: SHA-256, hex, over the event's JSON without its own hash, keys sorted, no spaces, UTF-8. This is not RFC 8785 canonical JSON.
- The chain shows a changed, removed or inserted event. It does not show the last events being cut off, nor a rewrite of every hash; that needs the head hash to be held by the other party (next step).
- One audit writer per database and process. Two processes writing one database could give two events the same previous hash.
- Audit events are stamped with the real time; the pinned replay clock is used only for cut-offs and price validity (question T06-2).
- Supplier view hides: approver id, name, role and note; every buyer rule (P-) and F-02; the pasted text; allergen exclusions and strictness; the profile and its limits; option titles and constraint checks. It shows: the agent's id, lines, prices, totals, availability, the statements relied on, who placed the order (agent or human approval), and rules F-01, F-03, F-04, F-05, F-06.
- Facts in an event are summaries (exclusions as counts by reason); the full offer is read by its id. Largest event in the sample flow is about 9 KB.
- The trail of an order is its events plus the events of its offer.
- Sentences quote the policy decision's own rule sentences; they are never rebuilt or produced by a model.
- Times in sentences keep the offset they carry; quantities are in sales units; money is net of tax.
- SQLite 3.38 or later is needed. SQLite itself does not refuse an update of an audit row; the code exposes no update or delete (the PostgreSQL store adds a database trigger).
- The policy hash is written `sha256:<hex>`; event hashes are bare hex.

## Catalog (T02)
- The product-type table is ours: 29 keys, categories inferred from the English names in each category, counts over the whole catalog. It is not a complete taxonomy.
- `milk` is the whole of category 10400 (91 products; three are not milk). Lactose-free milk is `milk` plus claim `FREE_FROM_LACTOSE`: exactly 35 products.
- `plant_drink` is category 10402 narrowed by name terms to 51 of 66 (coconut milks for cooking, iced coffees and a cooking base are left out).
- Name terms match the English name at the start of a word, or the Finnish name anywhere (terms under 4 letters must start a word). English matches are listed first. Accents are not folded.
- Search without a product type keeps the category with most matches and every category with at least half as many.
- Pack size: live price ratio first (using the file's own figure when the two prices are consistent with it), then the unit-conversion row, then the name. A weight is never turned into litres or the other way round. A product sold by `KG` is 1 kg per sales unit.
- With no price, the product file gives a pack size for 15,179 of 17,546 products; 2,367 are unknown and drop out of a litre or kg request with `PACK_SIZE_UNKNOWN`.
- Portion pack: a sales unit holding more than one inner unit of 5 cl or 50 g or less (744 catalog products). Our threshold (question T02-3).
- Lot step: `allowedLotSize` 0.01 is read as "no step set": countable units are ordered whole, kilogram products keep 0.01 kg, the 674 real steps are used as given (question T02-1).
- Origin placeholders `zy`, `xs`, `zz` (195 products) load as no origin.
- Listed substitutes are Valio's pairs as listed, in one direction.
- The catalog needs all three data files at start-up; a missing or malformed one stops the start rather than serving a partial catalog.

## Policy (T05)
- The policy is data: `src/tta/policy/rules.yaml` (39 declared facts, F-01 to F-05, P-00 to P-07, F-06 as an access rule) and one YAML file per buyer profile. The structure is Gabriela's.
- A missing fact never passes: it fires F-03 (to a human). That includes the day's committed spend, the re-check at order time, an option with no `valid_until`, a missing allergen check for a buyer with exclusions, and a product that does not say whether it is sold by variable weight (3,068 of 17,546 catalog products).
- F-01 fires for every availability state other than confirmed, and for a confirmed line whose quantity claim is not confirmed.
- F-02 and P-04 read the outcome of the allergen rule; the policy does not redo it.
- F-04 is evaluated only at order time: the option's `valid_until` has passed, or the re-check found a change.
- P-01 and P-02 fire strictly above the limit; P-03 strictly below the minimum. P-02 compares the day's committed spend plus this order with the daily limit.
- Roles the plan does not name: P-00, P-05 and P-06 go to the purchasing manager.
- `SAME_CATEGORY` includes substitutes listed by the supplier; "same category" is the same 5-digit category (question T05-1).
- `AUTO_WITH_CEILING` (variable weight) lets the agent order alone only when the total is marked as a ceiling; `NOTE` (deposits) only when the total says it excludes deposits.
- `allergy-ward`: variable weight and deposits both need approval (question T05-2).
- A blocked decision names no approver role. An approval decision requires the roles of every rule that asks for a human.
- Policy hash: `sha256:` + SHA-256 of the canonical JSON of the rules plus the profile; comments and key order do not change it.
- A profile file cannot name a rule or carry a setting outside the profile contract: it has no way to switch off a fixed rule.
- Gabriela's rules for not-deliverable products, estimated pack sizes and lot steps are not carried over: the offer excludes those products before the policy runs.
- All limit values are illustrative. Demo approvers exist for every role on both profiles.

## Orders and approvals (T08)
- Every order passes one check just before it is placed or approved: a fresh look at price and availability, then the policy with the order-time flag set. It is the only place the policy is called for an order.
- Stale or expired is read from rule F-04's facts: expired when the option's time or a validity has passed, stale otherwise.
- Idempotency keys are scoped to the agent. A key is bound only when an order is created; the same key with another offer or option is `invalid-request`.
- Only an agent places an order. Reads are limited to the caller's own buyer; the supplier reads no order through this service.
- Who may decide: an approver of the same buyer, who holds a role still missing and is listed under that role in the buyer profile's `approver_roles`. An agent on the approval route is refused (F-06) and the attempt is recorded.
- Every approval, not only the last, re-checks and re-evaluates at order time; the roles required are those of that evaluation.
- Choosing another option starts the approval again on that option (question T08-2). A failed re-check at approval leaves the order waiting (question T08-1).
- Expiry: strictly after the option's `valid_until`, applied when the order is next read, listed or decided. No `valid_until`, no expiry.
- The day's spend counts orders in `ORDERED` and `PENDING_APPROVAL` created on the data clock's date. In replay every order carries the capture's time, so all of them are "today".
- An order completed by a human is recorded as placed with human approval, even when the policy would ask for nobody at that moment.
- Writes are serialised by one lock in the process, held during the fresh check. State is saved first, then the audit event; there is no transaction across the two, and two gateway processes on one database are not protected (next step: a unit of work in the store).
- Deciding an approval that is already closed is `invalid-request` (there is no conflict type).

## Valio client hardening (FIX-4)
- The live clock is the later of this machine's time and the server's stated time; a `timeNow` more than 12 hours from this machine's UTC time refuses the answer; the clock never moves backwards. A machine clock more than 12 hours wrong stops live availability.
- The base URL must be `https://` (loopback hosts excepted, for tests).
- Accepted ranges: a price from 0 to 1,000,000, an amount from 0 to 100,000,000,000 (the largest placeholder seen is 9,999,999,999). A 200 body over 20 MB is refused; the limit is checked after the download.
- The call budget is counted under a file lock (POSIX), so several clients and processes count correctly.
- A spent budget or a missing key tells the caller only that the supplier cannot be asked right now; the specifics go to a warning log record. Other supplier error details still name internals (listed for a later pass).

## Allergens and catalog after review (FIX-3)
- A member's own statement beats its declared family only when it is `FREE_FROM`; a member marked `UNDECLARED` or not stated under a declared family goes to a human.
- The substitution rule also fails a substitute that raises an allergen from "may contain" to "contains" (0 of 249 listed pairs do; 37 of 249 still fail for adding one).
- Allergen codes in the product file are stripped and upper-cased; a code outside the code table rejects the file (the real file has 45 codes, none unknown).
- A deleted product behaves like an unknown id (the catalog has none today).
- `milk` leaves out sour milks, the coffee drink and the soy yoghurt of category 10400 by name (78 of 91; 30 lactose-free). Milks sold for coffee stay in (question FIX3-1). `sour_milk` is its own type; the table has 30 types.

## Policy after review (FIX-1)
- New fixed rule F-07: a line whose price claim is not confirmed, or whose delivery-date claim is ruled out, and an option whose needed-by check is not met, go to the purchasing manager.
- A line with no price, quantity or delivery-date claim is a missing fact (F-03). The policy does not read the allergens claim (it reads the allergen rule's outcome) or the origin claim.
- On a dated option the policy relies on the offer's needed-by check; that check says "met" only when every line's delivery-date claim is confirmed.
- The verdict, approver role and scope of every fixed rule are pinned in code: a rules file that changes one is rejected at load. The conditions of a fixed rule are not pinned (the policy hash shows any change).
- An option is expired when its `valid_until` is at or before now.
- A ratio is printed rounded down to one decimal, so a partial fill never reads as 100%.
- A profile whose excluded allergens hold an unknown code, or `X99`, is rejected at load.
