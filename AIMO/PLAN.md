# AIMO — plan after Valio's answers (Saturday 14 Nov → Sunday 15 Nov 10:00)

Rewritten on Saturday 14 Nov after Valio's mentors answered our booth questions. Twenty-one agents then studied each answer and checked the build; nothing was coded. **Their proposals are in [build/replan/](build/replan/), one file per topic, and this file is the merged order of work.** Ids such as "P8 M1" or "A2b C1" point into those files. The morning's plan is in git at `7f09ce7`.

**In one paragraph.** The flow runs end to end and the documents match it. What is wrong is what the product *decides*. It orders alone where Valio wants a person to confirm. It fills a milk order with coffee milk. It tops up whipping cream with a vegetable-fat blend. It lets a cheaper doubtful product outrank a safe one. Its fall-back reader can drop "must not contain gluten". Tonight we change those decisions first. Then we add what Valio asked for and most of the 105 teams will not have: each customer's pattern, and suggestions that respect it.

---

## 0. The score, and where we stand

Criteria are verbatim from the Junction platform ([CHALLENGE.md](CHALLENGE.md)). The score column is one agent's strict estimate from running the build offline (`build/replan/A5-rubric-score.md`): **70.5 of 100**.

| Weight | Criterion (their wording) | Today | What moves it most tonight |
|---|---|---|---|
| **30%** | **Working end-to-end demo** — "runs through a full request → lookup → order/approval flow in the mocked environment, not just isolated pieces" | 8 | A main answer a judge understands in five seconds; a public link that still works on Sunday |
| **20%** | **Solving the problem and user need** — "how precisely the agent matches what the buyer actually asked for, with the least manual correction needed" | **5** | Coffee milk out of "milk"; the reader asks instead of guessing; the usual product from the customer's history |
| **20%** | **Autonomy and controls** — "what the agent can decide alone, what needs human sign-off, and how decisions are logged and auditable" | 7 | The user confirms every order; Valio sees every rule that fired |
| **15%** | **Robustness to exception situations** — "partial availability, substitutions and delivery constraints beyond the happy path" | 7 | Substitutes that keep allergens, dietary claims and formula, in that order |
| **15%** | **Openness and credible path toward production** — "open, documented standards rather than a proprietary format, clear visibility of assumptions, well-justified technical choices, and a credible view of next development steps" | 8 | Documents made true; a discovery document; signed offers |

**What Valio wants in the end** (the mentor, as João noted it): "the end goal is for them to attract as many customers as possible to compete with their competition". **What the brief rules out:** "This is not about replacing today's e-commerce UI with a chatbot." The product is the typed interface, the rules and the log. The pages are a front end to it.

**What the brief brings, and whether we respect it** (`CHALLENGE.md:50-54`): synthetic catalog and mock API only (yes: nothing in the product reads Valio's real webshop) · prices, availability, lead times, labels, carbon (yes) · agents with tool use and open standards (yes) · recommendation logic (partly: section 4, S1 and S2) · a trust layer (partly: a status per claim and a tamper-evident log; nothing signed yet: D4) · agentic payments as context (no document of ours names x402 or Nevermined yet; a written position, no payment step: D1, `build/replan/P16-payments.md`).

---

## 1. What Valio told us on 14 Nov, and what each answer changes

The answers are João's notes from the booth, quoted in [build/replan/BRIEF.md](build/replan/BRIEF.md) section 2 and written under the questions in [BOOTH-NOW.md](BOOTH-NOW.md).

| Valio said | What we do | Work |
|---|---|---|
| Customer data can be generated; work "per user based on the user pattern" | Four customer types, each with a generated history that every screen labels as synthetic. The agent uses the history: the usual product and quantity, what was forgotten, a trend | S1, S2 |
| "deactivate automatic order but you can suggest orders the final submition should always have the input from the user" | Ordering alone is a buyer setting, **off by default**. The agent prepares the order; a person confirms it. The rules still decide whether a named role must also sign | R1, R7 |
| A buyer asking for milk does not accept coffee milk: "no be explicit" | A product type is exact. Coffee milk is its own type. A variant the buyer did not name is said on the offer | R2 |
| The data is noisy; "ensure no allergies"; "if you are not sure you need to flag it to the user" · João: "it is better to not have gluten if you are unsure" | **The safe product wins.** The agent's suggestion holds only products whose data rules the allergen out. A doubtful product is a flagged alternative that only a dietitian can choose. A reader that does not understand a word asks | R4, R6 |
| A substitute or a cheaper item must keep the brand or formula where the formula matters (baking), "a VERY IMPORTANT thing" | A "same formula" measure from the six nutrients per 100 g, which the build does not load today. Where formula matters, a different or unknown formula needs an explicit yes | R5 |
| A substitute that loses a dietary claim: "only if all the rest of product with that dietary restriction are done" (João's clarification) | A claim-losing substitute is a last resort: held back while any product that keeps the claim can be supplied, and then it still goes to a person | R5 |
| Category numbers: "sap code semi random", nobody knows | The digits are not levels. Substitute candidates are Valio's listed pairs, then the same 5-digit category. The 4- and 3-digit tiers go | R5 |
| The data is synthetic and static; "we can chose the date" | The clock stays at the recording's instant, Saturday 14 Nov 02:52, and every page says we chose it. The public link is pinned to it, because on real time nothing can be promised from Sunday 17:00 | R8 |
| Valio wants to see "all the steps and decisions" in the log | Valio's view shows every rule that fired and its outcome. The buyer's private values stay masked unless Valio asks for them | S4 |
| Variable weight is invoiced for "what is actually delivered. like in a normal store" | The total is an estimate, and the offer says so. "A maximum, never higher" is false | S7 |
| A listed substitute in another unit is converted by content: "yes the goal is to satisfy the prompt" | Confirmed for litres and kilos. A request in pieces still swaps 1 for 1 (100 pieces became 100 cases): fix | P9b Q14-1 |
| "take the values as they are in the data" | Confirmed: the build already rejects the oat drink whose data says gluten. One gap: a required claim is met by the claim field even when the allergen data contradicts it (56 products) | P4 F4 |
| A huge stock number means unknown · a substitute never adds an allergen · "by Monday" is the first Monday after today | Confirmed. No change | — |
| A webshop test login | Looked at, read only (`build/replan/P3-webshop.md`). We take its words and concepts, never its data | S3 |

---

## 2. The rules we now work by

1. **The mock's behaviour is the scenario, not a fault.** Unchanged from the morning's plan.
2. **A person confirms every order.** What the agent decides alone: reading the request, excluding products, combining them, choosing a substitute inside the allowed scope, the re-check, preparing the order, and naming who must sign. Placing the order alone exists only as a setting the buyer switches on.
3. **When in doubt, the safe product wins, and the agent asks.** A declared "contains" is never a choice. No answer from a user turns it into an order.
4. **A product type is exact.** A variant (coffee milk, another fat level, a flavour) is named on the offer, never mixed in silently.
5. **A substitute passes four gates in order:** it adds no allergen; it keeps the dietary claims, or it is a last resort; it keeps the formula where the formula matters; then Valio's listing, pack and price rank it.
6. **A category number is an opaque label.** We compare all 5 digits or nothing.
7. **The clock is chosen and labelled.** Audit records keep the real time.
8. **Everything generated is labelled as synthetic on the screen that shows it.** Nothing from Valio's real webshop enters the product or the repository (`CHALLENGE.md:52`: "everything you build against is synthetic").
9. **A suggestion never adds itself to an order.** It carries its reason in numbers, obeys the buyer's allergen exclusions and rules 3 to 5, and can be dismissed.
10. **Say whether a number is from the whole catalog (17,546 products) or from the recording (769).**

---

## 3. What the checks found in the build

Tests: 3,260 pass, 67 need live services, one timing test is left out, lint clean (15:00). The deployed link answers. No demo figure in any document is wrong. The defects below were each reproduced offline.

| Sev. | What | Where | Fixed by |
|---|---|---|---|
| Critical | The fall-back reader drops an exclusion it has no phrase for: "100 litres of oat drink, must not contain gluten, strict" was ordered alone, with a drink that declares gluten. The text check misses it for a model's reading too | A2b C1 | R4 |
| Critical | "0.100 l" is read as 100 L · "10 kg of milk chocolate" becomes 10 L of milk · "milk, not lactose-free" becomes lactose-free milk. Of 40 hard sentences, 20 came back as a wrong request | A2b C2–C4 | R4 |
| Critical | Renewals still waiting for approval count as a standing order's history, so three unapproved renewals move the baseline and the fourth is ordered alone | A2a S-1 | R3 |
| High | 100 L of 36% whipping cream is filled with 52 L of a 15% vegetable-fat blend, ordered alone, and the sentence does not say so | P10, P1 | R5 |
| High | A cheaper doubtful product is option 1 ahead of a safe one (hotel, plant drink, no gluten: €17.40 over €20.10) | P4 | R6 |
| High | "Most reliable" picks €73.70 of cream against €33.10, and a tenderloin at €931.35 against a flank at €246.96, because a known 52.4% beats an unknown | A2b H2, P2 | S6 |
| High | The five examples on the first page, clicked in order in one browser, break the fifth: waiting orders fill the €3,000 day. Approve on the first then seems to do nothing | A4 H2 | R8 |
| High | 30 of 36 two-dish menus are refused ("at most 5 lines"). A stand-in can add an allergen that no sentence names. "No quark can be offered" while option 2 offers quark | A2a M-1, M-2, M-4 | S5 |
| High | Anyone with a buyer token can create standing orders without limit; 1,500 creates grew the database to 161 MB, and audit rows cannot be deleted | A3 F1 | S9 |
| High | A result page holds 1,050 to 1,900 words; the reason for sign-off sits a screen below the outcome; words such as `FREE_FROM_LACTOSE`, "claim", "P-01" | A4 | S3 |
| Medium | Valio's view of the log hides every buyer rule that fired, the claims asked for, and 23 of the ward's 41 exclusions | P9b | S4 |
| Medium | The photo button transcribes, builds the offer and orders in one click; the lines it read appear only afterwards | P14 | R1 stops the order; D8 |
| Medium | 26 document lines are out of date, 8 of them on the assumptions page, which still says three parts are not built | A1 | D1 |
| Medium | `/mcp/` accepts a foreign `Origin` (a MUST in the MCP specification); no discovery document; the audit trail is not served as CloudEvents although a document says so | P12 | D1, D3, D5 |

Found sound by the security review: no buyer reads another's data, an agent cannot approve its own order by any route, every writing form has its token, every SQL statement is parameterised, the model cannot choose a product, a quantity or a price.

---

## 4. The work, in order

Hours are the agents' estimates for one person working with Claude Code; they order the work and say what is large. "CS" and "bio" say whose knowledge a package needs. **Tier 0 lands before anything else.** Section 6 says who builds.

**Nothing is held back.** Tier 0 is 26.25 h and Tier 1 is 19.25 h by these estimates. The build session runs agents in parallel until the work is done, so the order below is the order of value, and the "later" list comes last.

### Tier 0 — change what the product decides (about 26 hours)

| # | Work | Detail | Hours | Who | Criterion |
|---|---|---|---|---|---|
| **R1** | Ordering alone off by default, starting from Sofia's commit `5673ef2` ("Require human approval for every eligible order"), which holds on every path and already re-pins 57 test files. Its fixes: three red tests; **the buyer's setting put back, off by default**, so the autonomous path exists and is tested; the rule's place in `rules.yaml`; wording | `C1-human-approval-branch.md` X1–X4 · P8 | 2.5 | CS | 20% controls |
| **R2** | `coffee_milk` becomes its own product type (`milk` goes from 78 to 74 products). The offer says coffee milk was left out and how to ask for it | P9a M1, A1 | 1.25 | bio | 20% precision |
| **R3** | A standing order's history counts only renewals that were ordered | A2a S-1 | 0.5 | CS | 20% controls |
| **R4** | The reader asks instead of guessing. Every exclusion in the text must appear in the typed request, whoever read it. "0.100 l" is not 100 l. A number that belongs to a ward or a pack is not the quantity. A text it cannot read gets a question, not a 503. Minimum 3.5 h: C1, C2, H3, M1 | A2b C1–C4, H1, H3, M1 | 5.5 | bio + CS | 20% precision |
| **R5** | Substitutes in four gates (rule 5 of section 2): remove the 4- and 3-digit tiers (1.0); hold claim-losing candidates back while a keeper can be supplied, and count lactose-free as keeping low-lactose (1.5); load nutrition, the "same formula" measure with its tolerances, the ranking key, the "gives up" sentence in numbers, a fixed formula rule, F-11 (3.0) | P7-1 · P9b B7-1 · P10 F1–F4 | 5.5 | bio (measure, tolerances, rule) + CS (ranking) | 15% exceptions · 20% precision |
| **R6** | Safe product first. Option 1 holds only products whose data rules the excluded allergen out. "Alternative: allergen not ruled out" for the rest. The approval card asks a question with three choices. An exclusion with no strictness reads STRICT | P4 M1–M3 | 2.5 | CS + bio | 20% controls |
| **R7** | The result page says "Prepared: confirm to order" with one click. Status and audit sentences say who confirmed | P8 F1, F2 | 2.5 | CS | 30% demo · 20% controls |
| **R8** | The public link: replay with the pinned clock; a banner that says which instant and that we chose it; the five examples work in any order in one browser; the shared rate ceilings checked; the limit of 5 typed readings a minute raised. Needs one redeploy, which João approves | P5 C1–C3 · A4 H2 · A3 F3 · A5 #3 | 3.5 | CS | 30% demo |
| **R9** | Re-measure every demo figure once R1 to R7 are in. Refresh the pinned figures (at least 27 tests in 14 files for coffee milk alone) and the documents that quote them. Rewrite the demo script. One button per demo scenario on the first page, each with its customer | P9a M2 · P2 W1, W2 | 3.0 | everyone, for their own change | 30% demo |

Order inside Tier 0: R1, R2 and R3 first and together, as **one baseline branch that João merges**, with the type change and the rule sentences written by their owners, because they move almost every pinned figure and those are refreshed once. Then R4, R5 and R6 in parallel, in files that do not overlap. R5 and R6 share `src/tta/offers/`: one person owns that folder. Inside R5 the order is fixed: nutrition on the product → the measure → the ranking → the formula rule (F-11; F-10 is the human-approval rule of Sofia's commit). R7 after R1. R8 and R9 last.

### Tier 1 — what most teams will not have (about 19 hours, in this order)

| # | Work | Detail | Hours | Who | Criterion |
|---|---|---|---|---|---|
| **S1** | Four customers: profiles `bakery-cafe` and `school-kitchen` with their tokens; one pattern file per customer (usual products, 8 synthetic weeks, standing orders, stock on hand), written once with a model, committed, checked against the catalog and the recording by a test, labelled synthetic | P1 C1–C3 | 2.0 | bio + CS | 20% controls · 15% openness |
| **S2** | Suggestions from past orders, as a `suggestions` list of at most 3 on every offer: kind, product, quantity, one sentence with its numbers, the evidence. Counts and medians in the gateway; no model decides. **Minimum (2.75 h): "you usually order X with this"**, with an "Add" row on the page and an audit event. Accepting builds a new offer that meets every rule and the user's confirmation. Then, as time allows: the usual product for a type-only line (P1 C4, 2.0), "not now" remembered (0.75), a larger pack (1.0), a trend (1.5). Upselling for the seller is documented, off | P15 R1–R4a, then R4b, R5, R7 · P1 C4 | 2.75 minimum | CS + bio | the brief's "recommendation logic" · 20% precision · 30% demo |
| **S3** | The result page answers in five seconds: what you asked, what is suggested, what needs you, each in one line; the rest folded away. Valio's own words: "Closing time", "Delivery date", "N pcs available in storage" against "Deliverable <date>", "Alternative products", "Standard order" | A4 sections 2–3 · P3 W1, W2 | 3.5 | bio | 30% demo |
| **S4** | Valio's view of the log shows every rule that fired (id, title, outcome, the role that signs), the claims asked for, and every exclusion count. Limit amounts and allergen codes masked; the role instead of a name; notes left out. Valio's view also exists as SQL (`src/tta/store/sql/003_reader_views.sql`): it changes with this, or the Aiven write-up says the two differ | P9b B13-1 | 2.0 | bio + CS | 20% controls |
| **S5** | Recipes: two-dish menus accepted; the allergens a stand-in adds are named; the false "none can be offered" sentence fixed. If not started by checkpoint 2, "Menu" leaves the navigation instead | A2a M-1, M-2, M-4 | 2.5 | CS | 15% exceptions |
| **S6** | A preference never picks a much dearer product in silence: the gap is stated and, above a share set in the profile, a person decides. A known low reliability does not beat an unknown one at any price. No unconfirmed alternative that costs more than the confirmed option | A2b H2 · P2 W4, W6 | 2.0 | bio | 20% precision |
| **S7** | Variable weight: "estimated total, invoiced for what is delivered" in the three visible strings and their document lines | P9b Q16-1 | 1.5 | bio | 15% exceptions |
| **S8** | Unit words: cases, cartons, portions ("200 portions" became 200 tubs of 500 g) | A5 #5 · A2b L2 | 1.5 | bio | 20% precision |
| **S9** | Standing orders: the rate limit, at most 20 per buyer, the line cap, a limit on the list | A3 F1 | 1.5 | CS | 20% controls |

### Tier 2 — openness, awards and the story (documents start once the figures are final)

| # | Work | Detail | Hours | Who |
|---|---|---|---|---|
| **D1** | Documents made true (`docs/ASSUMPTIONS.md` is served at `/assumptions`, so its corrections are merged by 22:45, before the freeze): the 26 wrong lines; the category wording; the booth answers; the standards page corrected, with a "why not X" table, the brief's "Preferred tech" list answered line by line, and the payments paragraph; the awards write-up; the assumptions for customers, suggestions, the clock and the webshop | A1 · P7-3 · P9b DOC-1 · P12 W1 · P16 · P13 TA-1 · P3 W3 | 4.5 | bio |
| **D2** | The pitch: the positioning, the punchline, the question card, the 2:00 video script, the recording | P11-1 to P11-4 | 3.5 | two people |
| **D3** | A discovery document, `/.well-known/api-catalog` (RFC 9727), and `/llms.txt` | P12 W2 | 1.0 | CS |
| **D4** | Signed offers and orders (Ed25519, a published key, a check script) and a signed audit head: the brief's "trust layer" | P12 W8 | 2.5 | CS |
| **D5** | An `Origin` allow-list on `/mcp/` | P12 W3 | 1.0 | CS |
| **D6** | Gemini: a working key by 18:00, then re-record the Finnish readings, scenario 1's run and the brief's sentence at 21:30–22:30, after R1 to R7 and before the redeploy, because the recordings are in the deployed image | P13 TA-2 | 0.75 | CS, needs credits |
| **D7** | Aiven: the proof for the write-up (the supplier's login, real SQL output, the chain's head across a redeploy) | P13 TA-3 | 0.5 | CS |
| **D8** | The photo button stops after reading and shows the lines; a second click continues. Or the upload control leaves the page (0.25 h) | P14 PV-1 | 2.0 | CS |

**Later, only if everything above is in** (kept so nothing is lost): a request in pieces converted by content when the substitute is sold by the case (P9b Q14-1, 1 h) · a required claim checked against the allergen data (P4 F4, 1 h) · our own orders counted against confirmed stock (A5 #8, 2 h) · an option for the earliest possible date (A5 #10, 2.5 h) · variants as sub-types and a labelled "variant you did not ask for" option (P9a F1–F3, 6 h) · questions and remembered answers in the contract (P4 F1, F2, 4.5 h) · the role "the person who asked" (P8 F3, 1.5 h) · a customer switcher card (P1 C7, 1 h) · web evidence on every allergen doubt (P13 TA-4, 1.5 h) · GTIN on lines, a CloudEvents export, a mapping to Peppol (P12 W4–W6).

**If something must be dropped, drop in this order:** D8 → D5 → D4 → S9 → S8 → S7 → S6 → S5 (hide the page) → R4 down to its minimum → S4.

**Not doing, and why:** speech in or out (it scores on no criterion, and it reads as the chatbot the brief rules out) · a payment step, a 402 answer or a payment mock (Valio Aimo's own site names credit customers, who pay by invoice, and "Pay Now" customers, who pay when ordering; ours are credit customers, an assumption we label; nothing settles at order time, and for goods sold by weight the amount exists only after delivery; a written position instead: P16 PAY-1) · rebuilding the webshop's screens (the brief: not about the UI; we take its words) · anything that reads from the real webshop · moving the clock to another day (measured: it frees no confirmed stock and changes no demo result) · a second recording for bakery dry goods (the formula case is shown with cream, which the recording holds) · a name-word search for substitutes · Verifiable Credentials (a paragraph) · a model on a Modal GPU · more scenarios, more hardening, more documents than D1.

---

## 5. Customers and the demo

**Four customers** (`build/replan/P1-customers.md`). Every product id below is in the recording with confirmed stock.

| Customer | Who signs | What it shows |
|---|---|---|
| **Hotel kitchen** (exists) | Purchasing manager; finance above the day's limit | The brief's own request; partial availability on a large order; a weekly standing order |
| **Hospital ward** (exists) | Dietitian for any allergen doubt | Strict exclusions; the safe product wins; nothing without a person |
| **School kitchen** (new) | Food-service manager; dietitian for special diets | Steady weekly volumes, so drift and "the usual"; a usual product with only 51 in stock |
| **Bakery-café** (new) | The owner | Formula matters: whipping cream never topped up with a vegetable-fat blend |

A lunch restaurant and a catering company are documented only. The catering company is the counter-example: no history, so nothing is defaulted, and the agent says so.

**The demo set** (`build/replan/P2-scenarios.md`), for the 2:00 video and the 3:00 pitch. Every figure is re-measured in R9 before it is recorded.

| # | Scenario | What a judge sees | After tonight's changes |
|---|---|---|---|
| 1 | **Opener: the brief's sentence.** Hotel, "1,000 litres of lactose-free milk by Monday" | Valio's own sentence, then: what is confirmed, what is cheaper but unconfirmed, what was left out and why. Approval, order record, the two views of the log | A partial fill: 435 L confirmed (43.5%) for €1,083.39, or 1,000 L unconfirmed for €1,010.00. Both for a person. Coffee milk named as left out |
| 2 | **The ward.** "200 litres of a milk substitute; no milk, no gluten; confirmed data only" | A safe product, and the counts of products that declare the allergen or say nothing | Prepared, then confirmed by a person in one click (€402.00) |
| 3 | **The substitute.** Oddlygood Barista oat drink | Two of Valio's own listed substitutes refused: they add gluten | The order no longer goes to another brand alone; formula and brand are stated |
| 4 | **The customer's pattern.** The hotel asks for its 100 L of milk; then renews its standing order at 290 L | "You usually order 10 L of cooking cream with this": one click adds it (measured: €248.00 becomes €281.10). Then "290 L this week against a median of 100 L": waiting for approval | The suggestion is new (S2); the drift is unchanged |
| 5 | **The formula.** Bakery-café, whipping cream short | The agent offers what is in stock and asks, instead of topping up with a 15% blend | New |
| close | `/docs`, the MCP tools, the assumptions page | A real example in the interface documentation | — |

Reserve for questions: the reliability preference on oat drinks (+€7.00), the recipe, variable weight, an agent that cannot approve its own order, the buyer's own limits on "Your kitchen".

**If a judge asks "is this a chatbot?":** "No. It is a typed interface that any agent calls over OpenAPI or MCP. A sentence or a photo only fills the same typed request, the same rules judge it, and nothing is ordered until a person confirms."

---

## 6. Who does what

**Decided by João at about 15:50:** one Claude Code session builds everything of section 4 except the interface, with several agents at once. A teammate builds the interface on another branch. João merges the two.

- **The build session** follows [build/replan/RUNBOOK.md](build/replan/RUNBOOK.md): a baseline first (ordering alone off, coffee milk, standing-order history, the demo clock), then six lanes in parallel, each owning its folders (the reader · substitutes and formula · options and safety · rules and log · the gateway · customers and suggestions), then the demo set, the documents and a review. Its board is [build/replan/STATUS.md](build/replan/STATUS.md). It works on the local branch `replan-build`, never pushes, never deploys and calls no outside service.
- **The interface** is Gabriela's shop page, `/shop` (branch `frontend-shop`, reviewed in [build/replan/C2-frontend-branch.md](build/replan/C2-frontend-branch.md)). **The build runs on top of it:** it is merged at the start, and the build puts tonight's new sentences into fields the page already prints. Four fixes come first, two of them hers: nothing is ordered without a click, and the first screen stops being a chat. Her list is at the top of [build/replan/UI-CONTRACT.md](build/replan/UI-CONTRACT.md), which the build session keeps current. The old pages stay mounted: standing orders, the menu planner and the assumptions page exist only there.
- **For people:** the merge of the two branches, the redeploy, the Gemini credits, the Aiven proof, the pitch, the video, the deck and the form.
- [build/replan/SPLIT.md](build/replan/SPLIT.md) is the earlier split for four people, each with their own Claude. It stays as the fallback, and as the per-package detail (goal, files, "done when") the build session reads.

---

## 7. Order of the night

No clock times: the build runs until it is done.

1. **Baseline.** Ordering alone off, coffee milk its own type, the standing-order history fix, the demo-clock setting. Every pinned figure refreshed once. The whole suite green.
2. **Six lanes in parallel**, then their second halves (the formula rule, suggestions wired, the public link's settings, signed offers).
3. **The demo set** re-measured at the demo clock, with end-to-end tests. **The documents** made true. **A review** of the whole diff.
4. **The "later" list**, one item at a time.
5. **People:** merge the interface, redeploy, record the video (at most 2:00) from the deployed build, the deck, the form.

**Fixed points:** the submission form closes on **Sunday 15 Nov at 10:00** and must be set to FINAL. Peer review is 10:30–14:00, all four present.

---

## 8. Tech awards

Four entries (`build/replan/P13-tech-awards.md`). The score is against each sponsor's own bar. None is withdrawn; none may delay Tier 0. The build session does the part of each that needs no outside service (`build/replan/RUNBOOK.md`, "The four tech awards"); the rest is João's: Gemini credits and about 15 calls, the redeploy, two Context.dev lookups, the Aiven proof.

| Award | Today | The gap | What we do |
|---|---|---|---|
| **Google Gemini** | 5/10 | The key has no credits, so the deployed app calls no model. 4 of 11 recordings are from the model. The photo and the Finnish reading never ran live | D6: a working key by 18:00 (booth credits, else the free tier), then three recordings. Without a key, drop the photo and Finnish claims from the write-up |
| **Modal** | 3/10 | Hosting only | Stays hosting. One honest sentence |
| **Context.dev** | 6/10 | Evidence appears on one kind of doubt. The 60-request budget is not enforced on the deployed app. It puts real web pages next to synthetic records | Keep it labelled "not Valio data", off the main demo path. Optional: evidence on every allergen doubt (P13 TA-4, 1.5 h, 2 requests) |
| **Aiven** | 5/10 | It is built and holds the deployed order book, but `CLAUDE.md` and the old plan say it was dropped, and no page reads it | D7: the proof, 0.5 h. Correct the two documents |

---

## 9. Decisions

**Decided on 14 Nov, by Valio's answers or by João:** ordering alone is off by default · coffee milk is not milk · the safe product wins and a claim-losing substitute is a last resort · formula matters for substitutes and cheaper items · category digits are not levels · variable weight is invoiced as delivered · suggestions from past orders are a priority (João) · the data is static and we choose the date.

**Second booth visit, about 15:30** (answers in [BOOTH-ROUND-2.md](BOOTH-ROUND-2.md)), and what each changes:
- **"You are overcomplicating … show them the best date and example of our app"; "can't you just pretend you are requesting Thursday … for Monday?"** We choose the date and the examples. Measured: on a Thursday clock the main request gives the same two options (435 L confirmed, 1,000 L unconfirmed), nothing is left out for a passed deadline, and the oat-drink substitute becomes Valio's own listed product of the same brand, sold by the case (100 cartons become 10 cases). Decision 2 below.
- **Ordering alone: "after and if you are 100% sure yes".** The setting stays, off by default, and applies only when every statement is confirmed. Who confirms was not answered: the purchasing manager, the role that exists.
- **Suggestions: "everything … the best care for our customers".** All kinds are wanted. S2 keeps its order (forgotten item, the usual, a cheaper same-formula product, a larger pack, a trend) and a new or related product is no longer "off": it comes last.
- **The log: "show and explain why it made that decision and the logic behind it and product considered".** S4 moves into Tier 0, after R6, in its full form: every rule with its reason, and the products considered and left out, with why.
- **Formula: "consider if the prompt/user is formula dependent".** As R5 designs it: the request's words ("for baking"), the customer (a bakery: always) or the recipe line say that the formula matters; for everyday milk it does not.
- **Plain "milk": "what … makes the most sense for normal company?"** Ours to decide. Decision 6 below.
- **From Valio's slide: "Query the APIs only when needed, never for all product".** We already ask only for the candidates of one request, in 2 calls. Say so on the assumptions page.

**Taken at about 15:50** (João: go with the recommendations; decision 2 is (b); 11 stays open).

| # | Decision | Recommendation | Depends on |
|---|---|---|---|
| 1 | Who confirms an order: the purchasing manager (the role that exists) or a new role "the person who asked" (+1.5 h, P8 F3) | The purchasing manager now; the new role if Valio says so | Booth question 2 |
| 2 | The demo date. The public link runs in replay with a pinned, labelled clock either way. (a) Saturday 14 Nov 02:52, the recording's instant: no change to any test. (b) **Thursday 12 Nov 14:15**, as Valio suggested: a replay-only setting (about 1 h), the tests keep the recorded instant, the demo figures are measured at the demo instant; 47 deadlines have passed and 319 close within the hour, so both cases show | (b) | João; one redeploy |
| 3 | The four customers of section 5 | Yes | — |
| 4 | What Valio's view of the log shows: every rule and outcome, the buyer's private values masked | Yes, masked | Booth question 6 |
| 5 | The formula tolerances (six nutrients within 15% or 1 g; salt 0.25 g; the same fat source) are ours. A biomedical member owns them and can defend them | Yes; name the brand, let the formula decide | Booth question 7 |
| 6 | Plain "milk": never coffee or flavoured milk. Regular milk first; a lactose-free product is offered for plain "milk" only as a named alternative (it costs about three times as much), never the other way round. One fat level when it covers the quantity; a mix only to reach it, and the offer says so | Yes | Valio left it to us |
| 7 | Enter the Aiven award | Yes (0.5 h) | — |
| 8 | The Gemini key has no credits | The build calls no model. The write-ups drop the live photo and Finnish claims unless credits arrive and three recordings are made | João |
| 9 | Do waiting orders count in the day's spend? | Yes, and the sentence says how much is ordered and how much is waiting | — |
| 10 | The photo button: fix it or take the upload control off the page | The interface teammate decides; with ordering alone off it no longer orders by itself | — |
| 11 | The project's name equals the challenge's title. Keep it or choose another | The team's call | — |
| 12 | Commit this plan and the proposals | Done on `overnight-build`; the push is João's | João |

**For Valio:** [BOOTH-ROUND-2.md](BOOTH-ROUND-2.md), eleven questions. The first four change tonight's work: how and when they judge; who confirms and whether ordering alone may stay as a setting; which suggestions they value; what a buyer wants when stock covers 435 of 1,000 litres.

---

## 10. Facts to encode

Verified against the live API and the full catalog; detail in [FINDINGS.md](FINDINGS.md) and [docs/](docs/). "Sample" means the 1,000 random products asked of the API on Friday 13 Nov at 23:00. Rows changed on 14 Nov after Valio's answers and the agents' recounts are marked **(changed)** or **(new)**.

| Topic | Fact | What to do |
|---|---|---|
| Availability | Six states (§2) | One normaliser that returns the state |
| Quantity not confirmed | Terminal is always 999999. Stock placeholders equal 9,999,999,999 ÷ base units per sales unit. The largest ordinary Stock value in the sample was 7,389 (39,243 in an earlier capture). | Treat `availableAmount >= 999_999` as a placeholder; never do arithmetic on it. Valio confirmed that a very large value means the stock is not known (§2) |
| Missing fields | Optional fields are left out, never `null` | Use `.get()` |
| Unknown product id | `/api/availability` answers it like a product that cannot be delivered; `/api/price` returns `error: true` | Check ids against the local catalog first |
| Sales unit | The unit on the API line differs from the product file on 7 of 797 sample lines | Price and quantity follow the unit on the API line |
| Dates | `requestedDate` changes nothing; `availableDate` was 2026-11-16 on 767 of the 768 sample lines that carry one | Compare the buyer's needed-by date with `availableDate` ourselves |
| Customer **(changed)** | `customer` changes nothing | Limits live in a buyer profile, with illustrative values labelled as ours. Valio, 14 Nov: customer data can be generated (section 5) |
| Pack size | `catalogPrice ÷ comparisonPrice` gives litres or kg per priced unit; `comparisonPrice` is missing on 20.6% of the sample | Ratio first, then `unitConversions` when its unit is a real volume or weight, then the product name; if still unknown, exclude the product and say why |
| Allergen data | Relations are `CONTAINS`, `MAY_CONTAIN`, `UNDECLARED` (in `allergen`) and `FREE_FROM` (in `nonAllergen`). 46.2% of the catalog and 30.6% of food products have neither group | **Buyer exclusion rule** (proposed, §9): strictness is a required input. Under strict, for each excluded allergen and its sub-codes: an explicit `FREE_FROM` passes automatically; a declared `CONTAINS` is rejected; `MAY_CONTAIN`, `UNDECLARED` or no statement goes to a human. **Substitution rule:** a substitute must not declare (`CONTAINS` or `MAY_CONTAIN`) an allergen the original does not |
| `X99` | GS1: "Does not contain declaration obligatory allergens in the product." | Map it that way; confirm with Valio (booth Q2) |
| Claims are not allergens | All 35 lactose-free milks in category 10400 declare milk as `CONTAINS` | "Lactose-free" filters on `nutritionalClaim`, never on allergens; the offer says "lactose-free, contains milk" |
| Variable weight **(changed)** | 632 products, 628 sold in KG; all 37 in the sample are priced per kg. Valio, 14 Nov: invoiced for what is actually delivered | The total is an estimate and the offer says so; never "a maximum" (P9b Q16) |
| Lot size | 674 products have a real step (1.5 on 62, 1.8 on 17) | Round with `Decimal`; one test |
| Deposits | 506 products carry deposits; the 7 codes cannot be priced | Totals exclude deposits and say so |
| VAT | `vatCode` in the file is unreliable (159 "MEDIUM MEDIUM", absent on 3,068) | Use `tax.taxRate` from `/api/price` |
| Price fields | `Price.value` excludes tax; `PriceWithTax.value` includes it | Two separate types |
| Substitutes **(changed)** | 249 pairs on 189 products once a product paired with itself is left out; 229 stay in the same 5-digit category (recount in P7). Valio could not say that the digits are levels; measured, a shared 4- or 3-digit prefix is a neighbouring shelf, not the same product | Candidates: Valio's listed pairs, then the same 5-digit category. No shorter prefix. Then the four gates of section 2, rule 5. Re-check availability of every candidate |
| Optional axes | Delivery reliability 25.2% of products; carbon 62.9% (81.2% of food, 0.4% of non-food); both 17.8% | Show when present, never impute |
| Performance | The product file loads in about half a second, 0.6 GB | Loading at start-up is fine |
| Rate limits | 34 requests in 5 minutes, up to 251 ids each: no 429 | Filter locally, call narrowly, cache, keep a recorded-response fallback |
| Nutrition **(new)** | Six nutrients per 100 g on 11,538 of 17,546 products and on 611 of the 620 dairy products (P10). The build loads none today | Load them; the "same formula" measure reads them (R5) |
| Product types **(new)** | `milk` holds 78 products, 4 of them milks for coffee; "skimmed" as a name term also finds 29 semi-skimmed milks (P9a) | `coffee_milk` is its own type (R2); variants as sub-types later |
| Allergen counts **(changed)** | Recounted by P4: a "free from" statement contradicted by the ingredient list on 34 products (documents say 18); "no allergens to declare" on 195 (documents say 121). Under the ward's rule the data leaves a doubt on 9,713 products (55.4%) | Asking per product is impossible at that share: the safe product wins (R6) |
| Clock **(new)** | Deadlines are identical on the 62 ids shared by two recordings 3 h 52 min apart. Every confirmed product in the recording is a `Stock` product closing Sunday 15 Nov 17:00; the 366 Thursday deadlines are all `Terminal` products with unknown stock (P5) | Keep the recording's instant; pin and label it (R8) |
| The real webshop **(new)** | Same product master as our file (GTINs match, ids do not); a named category tree unrelated to our 5-digit numbers; no spend limit or approval by amount found (P3) | Words and concepts only; no data, no calls |

---

## 11. Submission checklist (CS owns)
- [ ] Junction submission set to **FINAL**, not DRAFT (closes **Sunday 10:00**; we submit at 09:30)
- [ ] Pitch video **max 2:00**, publicly viewable, recorded from the frozen build
- [ ] Pitch deck (PDF)
- [ ] Public GitHub repository (MIT) and the live Modal URL. The repository is private today; **before it goes public, booth question 8: may Valio's data files and the recorded API answers stay in it?**
- [ ] Project name, punchline and description · technologies used · credit preference
- [ ] Challenges selected: Valio Aimo, plus the tech awards of section 8
- [x] `LICENSE` file (MIT) in the repository
- [ ] README says where the datasets are and how to refresh them, and matches the frozen build
- [ ] Gemini write-up, the four points their brief asks for; only claims that ran live
- [ ] Modal, Context.dev and Aiven notes: what each powers, in one honest paragraph
- [ ] Team phone numbers and Discord username
- [ ] **All four present for peer review, Sunday 10:30–14:00**
