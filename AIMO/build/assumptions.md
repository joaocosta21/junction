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
