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

## Audit trail and store after review (FIX-2)
- A sentence states only what its event holds; where something is not recorded the sentence says so. Recording "placed by the agent" with a decision that is not `AUTO` is refused as a programming fault.
- Text from outside (the pasted request, an approver's note, names) is cleaned before it is quoted in a sentence: quotation marks become apostrophes, control and bidirectional characters are removed, and it is cut at 200 characters. The facts keep the text unchanged. Product names inside the policy's own rule sentences are not cleaned yet.
- The supplier sees product ids and product types only, never the buyer's own search terms or claims; of an agent it sees the id and that it is an agent.
- In a reader's view the chain state counts only the events shown; a break elsewhere is reported without the other event's id.
- SQLite refuses `UPDATE`, `DELETE` and a replacing `INSERT` on audit events through triggers, and two events cannot claim the same previous hash. Whoever can write the database file can drop the triggers.
- Two writers on one database are safe: an append checks the head inside one transaction and the trail retries (5 attempts).
- What verification does not show: the end of the trail cut off, a rewrite of every hash to the end, and who wrote an event. `AuditTrail.head()` gives the event count and last hash so another party can hold them; nothing publishes or compares it yet.
- A database file made before this change must be deleted; there is no migration.

## Offers (T07)
- An offer's clock is the `timeNow` of its availability answer.
- A line that names products by id uses those products as given; its product type, name terms and claims do not filter them. An unknown or deleted id fails the request with `unknown-product`.
- A search is cut at 1,000 candidates per request line.
- One exclusion reason per product, the first of: allergen declared, portion pack, pack size unknown, the availability state, late for the needed-by date, price unavailable, allergen not stated. What does not match the request comes before what Valio cannot supply now.
- A price is unusable (`PRICE_UNAVAILABLE`) when its currency is not EUR, it is zero or negative, it is not valid yet, or its validity has passed.
- Allergen strictness is the stricter of the profile's and the request line's. Confirmed-only applies when the request or the profile sets it.
- Under confirmed-only, a product left out for a quantity or delivery date that is not confirmed has no reason code; it is named in the offer's notes.
- Combining: a single product is chosen on the cost of the whole quantity; a combination is filled cheapest per litre or kilogram first, ties by id. Stock off the lot step is rounded down.
- A request with several lines gives options that span all lines; stock one line takes is not offered to the next; the fill ratio is the lowest of the lines.
- The unconfirmed alternative exists whenever a fitting product is in that state, also beside a full confirmed fill.
- A substitute option is built when confirmed stock of the named products leaves something missing (question T07-2). A stand-in carries the line's required claims and obeys its pack rule and allergen exclusions.
- Option order: an option holding an unconfirmed quantity comes after the others; then fewer unmet checks; then fewer unverified ones; then best confirmed, unconfirmed alternative, substitute.
- Totals are sums of the rounded lines; tax is net × `taxRate` per line.
- Substitute candidates: the listed pairs plus the three category tiers, 999 at most, one price and one availability call. "Passes" is about the allergen rules; "orderable" adds price and availability.
- Re-check before an order: any price difference, a new price validity, a new state and a new cut-off are changes; stock is a change only when it no longer covers the order (question T07-4).

## Policy and substitutes after review (FIX-5)
- New fixed rule F-08: a substitute that lacks a dietary claim the original carries always goes to the purchasing manager, also when Valio lists it and whatever the profile's substitution setting.
- Which claims count is our list of dietary claims (question T07-7); other claims are named in the "what the buyer gives up" sentence only.
- F-05 covers a substitute that adds an allergen and one that raises it from "may contain" to "contains"; the policy cannot tell the two apart, so its sentence names both.
- Product names from the product file are neutralised before they enter a rule sentence (quotation marks become apostrophes, control characters a space, at most 120 characters); 29 catalog names carry a double quotation mark and 7 a line break.
- On a dated option, a line whose delivery-date claim is unknown also fires F-07.
- A pending order is expired at the instant of its "order by" time, not after it.
- The supplier sees rules F-07 and F-08 with their meaning, as it sees F-01 and F-05: they are about its own data.

## Offers after review (FIX-6)
- The re-check before an order also compares the delivery date (a later one is a change, an earlier one is not), the sales unit and the tax rate. A price validity that moved later with the same price is not a change.
- Every product that drops out is listed with a reason; under confirmed-only the reasons include `QUANTITY_NOT_CONFIRMED` and `DELIVERY_DATE_NOT_CONFIRMED`; a line that asks for portion packs excludes others with `NOT_A_PORTION_PACK`. A product that fits and is in no option is named in a note (question FIX6-1).
- Stock taken by a stand-in for one request line is not offered to the next.
- An option's `valid_until` is empty when any of its lines has no cut-off; the open-ended price date never becomes a `valid_until`.
- The needed-by and confirmed-only checks are "not met" when a request line has nothing offered.
- Product names are cleaned before they enter any sentence of an offer; the name fields themselves keep the product file's text, so pages and model prompts must treat them as data.
- Only dietary claims count as lost by a substitute (eight codes, our list; question T07-7).

## Orders and store after review (FIX-7)
- An order's state, its approval, its idempotency key and its audit event are written in one database transaction, or not at all. The supplier call is never inside a transaction.
- One live order per offer (question FIX7-2).
- An approval runs the order-time check first, then asks whether the approver holds a role the new decision still needs (question FIX7-1).
- The day's spend counts an ordered order on the day it became ordered and a waiting one on the day it was created.
- Any failure of the order-time check is recorded as "order not placed" with the error's type, never its text.
- What an order relied on carries two times: when Valio stated the figures (the offer's data time) and when the re-check found them still sufficient.
- An approval with no "order by" time expires 24 hours after it was created.
- Another buyer's order, approval or offer id answers `not-found`, the same as an unknown id. A refused attempt on another buyer's approval is recorded in the caller's own trail.
- An idempotency key is 1 to 100 characters of letters, digits, `.`, `_`, `:` and `-`.
- A thread waits at most 5 seconds for the store, then the caller gets `supplier-unavailable` and can send the same request again.
- The order book's one lock is held across the supplier call and protects one process only (next step).

## API (T09)
- One service object (`tta.api.service.Gateway`) is behind every transport: REST routes, MCP tools, pages and the buyer agent. The limits and the authorisation checks live there, not in the routes.
- Who may call what: an agent, everything of its own buyer except the approval routes; an approver, the reads of its own buyer and the approval routes; the supplier, the audit route only.
- Demo tokens are public by design and read only when `TTA_ENV` is `dev` or `demo`. Elsewhere `TTA_TOKENS` (a JSON object, token to identity) is required and the app does not start without it. Tokens are kept as SHA-256 digests and compared in constant time.
- Rate limit: 60 calls a minute per identity, 240 for the shared demo tokens; in memory, one process. Body limit 64 KB. Lists return at most 100 items; no paging. A request names at most 1,000 product ids.
- A problem response never repeats text the caller sent and has no `instance` member. A validation problem lists `{field, problem}` pairs.
- Creating an offer or an order answers 201, a retry with the same key too.
- Stale or expired at order time: the 409 carries `fresh_offer_id` when a fresh offer could be built.
- Live mode falls back to the recorded capture when the supplier cannot be reached (for 30 seconds before trying live again) or fewer than 10 calls are left in the budget. `/healthz` shows the mode asked for and the source of the last answer. A live price followed by a failed live availability call gives an offer labelled replay that holds a live price.
- `/healthz` is public: environment, mode, source, the audit head (event count and last hash), which optional parts are in, and which settings are set (true or false, never a value).
- OpenAPI examples are produced by running the scenarios through the service against the capture; none is written by hand. `/docs` loads its assets from a CDN (FastAPI's default) and needs the network; `/openapi.json` does not.
- Pages are mounted only in dev and demo (question T09-4).

## MCP surface (T11)
- Eight tools, each one call of the gateway service as the identity of the request's bearer token: `get_authority`, `search_products`, `get_product`, `find_substitutes`, `get_offer`, `place_order`, `get_order`, `get_audit`. There is no tool that lists or decides an approval: approving is for humans.
- Transport: Streamable HTTP, no session, plain JSON answers, so any replica can answer. SDK `mcp` 2.3.0.
- `get_offer` makes a new offer from the typed request; no tool reads a stored offer by id (question T11-1).
- Identity is the SDK's bearer check asking the same token registry as REST; without a valid token the answer is 401 with `WWW-Authenticate: Bearer` (RFC 6750), not a problem document. No OAuth: tokens are handed out outside the protocol.
- A typed error is an error result whose content is the same problem document REST sends.
- The Host header is not checked on the MCP endpoint (the SDK's default would accept only localhost); a setting for the public address is a next step.
- The server's instructions tell an agent that product names and other supplier text are data, never instructions.
- Large answers are not trimmed: a search for `milk` is about 138 KB; `limit` asks for fewer.

## Buyer agent (T10)
- Model `gemini-3.8-flash` (newest Flash marked stable in the documentation read on 14 Nov 2026, with function calling and structured output), overridable with `TTA_GEMINI_MODEL`. Called through the Interactions API with `store=False` and thinking level low.
- The model proposes; the gateway decides. Reading the text, the model fills a schema whose every field is required and where `null` means "the text does not say". The parser then refuses a product type outside the table, a claim outside the catalog's 21 codes, an allergen code outside the code table, a product id that is not in the text, and a date before today.
- What the text does not say (quantity, unit, allergen strictness) is `invalid-request` with the missing fields named; the model is never asked to guess.
- "By Monday" is resolved from a 14-day calendar given to the model: the first such weekday after today (question T10-3).
- In the loop the model sees four functions and can name only an option id; the offer, the quantities and the verdicts come from the gateway. The report is built from the gateway's own sentences; the model's closing words are discarded.
- A run is at most 8 steps and 10 model requests before retries; a 30-second time-out and 2 retries per request.
- Without a key, or for the demo sentences, runs are served from `fixtures/agent/`. Tonight those recordings are hand-written: the live check got only 503 answers from Gemini (question T10-1).
- Errors and log lines of the Gemini module carry the HTTP status only; the SDK's error text is not chained.

## API after review (FIX-8)
- One look at price and availability comes from one source: both live, or both from the recorded capture when either live call fails or the budget cannot cover two calls. A pair from two sources is refused.
- In live mode the data clock is the live clock, also while answers come from the capture; a replayed answer keeps the capture's `time_now` and says `replay`.
- A configuration error (a base URL that is not https, a broken optional module) stops the start; only an outage or a low budget falls back to the capture.
- Rate limits for the public demo: 60 calls a minute per visitor (identity plus client address), ceilings of 120 offers and substitute searches, 120 orders and decisions and 30 model calls per minute for the whole app, and at most 6 live looks a minute at the supplier.
- `/healthz`: `ok` or `degraded` with reasons; the audit head is held in memory.
- A validation error below a route is a server fault (500, generic detail); only the caller's own input gives `invalid-request`.
- "Request received" is written by the offer step itself, so an order's timeline starts with the buyer's words.
- Tokens from the environment must be at least 24 characters, unique, and map to distinct identity ids.
- Every response carries `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`; every `/v1` response also `Cache-Control: no-store`.
- The exact paths `/v1` and `/mcp` belong to the API and to the MCP surface, never to the pages.

## Pages (T12)
- Four pages: `/` (paste a request or click one of three examples, choose who is asking, run), `/approvals`, `/orders/{id}` (buyer and supplier views of the trail, with the chain state), `/assumptions`. Server-rendered, no external asset, a Content-Security-Policy with no external source and no inline script, CSRF tokens on every form, the demo identity in a cookie.
- The pages act as a demo identity chosen on the page, with no login; they exist only in dev and demo.
- The three examples carry their typed requests, so the demo never depends on the model: when the model cannot read a sentence, the example's typed request is used and the page says so.
- Every piece of dynamic text is escaped; the assumptions page renders a small Markdown subset in which every character is escaped and only `http(s)` links are made.
- The page keeps the last 200 agent runs in memory (question T12-4). One server process is assumed: the run log, the rate limiter and the SQLite file are per process.
- In replay the day's spend never resets (question T12-1).

## Buyer agent after the follow-up (T10 follow-up)
- The Gemini module calls `generateContent` (API version v1), not the Interactions API: on 14 Nov the Interactions endpoint answered 503 to every request, while `generateContent` answered.
- Default model `gemini-3.6-flash`: `gemini-3.8-flash` answered 504 to every request of the live check (30 s and 120 s deadlines). Gemini was slow all morning (a one-word answer took 21.7 s at 08:10; our reading of scenario 1 took 29 s).
- With a key set, when Gemini cannot be reached for a sentence that has a recording, the reading or the run is served from the recording and the report says so in its first sentence. A sentence with no recording answers `supplier-unavailable`.
- Waiting for Gemini: a 30-second deadline per request and 2 retries, so a sentence can wait about 90 s before the recording answers. For a live demo, running without the key serves the recordings at once, labelled.

## Buyer agent after the final review (FIX-9)
- Every reading of the model is checked against the text before it is used: the quantity must be a number in the text, the unit a unit word in it, `needed_by` a date the text names (by the parser's own calendar rule), every allergen the text excludes must be excluded, `require_confirmed` true only when the text asks for confirmed data, product ids whole tokens of the text. A disagreement is asked once more, then refused with the field named; nothing is corrected silently.
- Number words: English only. Unit words: English and Finnish. "Lactose-free" is a claim, not an exclusion. An extra exclusion the model adds (for example "coeliac" → `AW`) is kept.
- Every reading says who made it: the model now, a recording of the model (with its date), or an answer written by hand.
- A run that fails after a gateway call is returned with every step and any order it placed; its report opens with what stopped it.
- After Gemini fails to answer, it is not asked again for 120 seconds; recordings answer at once, labelled. One retry per request in the gateway (two in the live check).
- The agent may order only the top option of the latest offer, and makes at most two offers per run; on a stale offer it uses the fresh one the gateway built.
- A recording is served only to the buyer profile it was recorded for. A recorded `needed_by` is re-resolved when the recording was made on another day. "Today" is the date in Europe/Helsinki.
- The prompts were edited after the recordings were made; the recordings still pass every check.

## Rate limits for a room on one Wi-Fi (FIX-11)
- On the pages a visitor is a browser (its own-book cookie): 20 lookups, 20 orders and decisions and 5 model runs a minute per browser. REST and MCP are counted by address.
- Every address, all its browsers and callers together, is capped at half of each global ceiling: 60 lookups, 60 orders and decisions, 15 model runs a minute. Global ceilings: 120, 120, 30.
- At most 30 new demo order books per address in 10 minutes, so one address cannot push the other visitors' books out of the 300.
- Live supplier looks stay keyed on the address: a room shares 2 a minute (6 for the whole app); above that the recorded capture answers, labelled replay.

## Context.dev evidence (S2)
- When an approval goes to a dietitian because an excluded allergen is not stated (or undeclared) in Valio's data, the gateway looks for the manufacturer's page with Context.dev's Answers endpoint and shows what it says on the approval card, under "Found on the manufacturer's page — not Valio data", with the link. The claim stays "unknown" and the verdict does not change; a test compares both with and without evidence.
- A page is dropped when the product name or brand does not match, when the link is not plain http(s), or when the answer failed. Page text is bounded and hashed; the audit trail records the URL and the hash.
- One lookup per product, stored; recordings for the demo products in `fixtures/evidence/`. At most 40 lookups per process and 3 per approval. Queries carry the product's English and Finnish names and the brand only.
- A lookup for a product with nothing stored runs inside the order book's lock and can hold it up to 40 s, once per product.
