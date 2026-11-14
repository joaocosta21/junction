# Walkthrough: what the gateway does, why, and how to check it

For the team, and above all for anyone who was not there when it was built. It describes the code as committed on branch `overnight-build` on Saturday 14 Nov 2026 (checked against commit `3ef0657`), not what was planned. Reading time: about 45 minutes for sections 1 to 12; sections 13 to 15 are history, other documents and a glossary; sections 16 and 17 are the booth material for Valio Aimo. With 10 minutes, read sections 1, 3.0 and 17.

How to read it:
- **Money** is in euros before tax ("net") unless a sentence says otherwise.
- **Times** are Helsinki time (UTC+2, two hours ahead of UTC, the world reference time) unless marked UTC.
- **Numbers** in the scenarios come from re-running the system for this document on the recorded Valio data defined in section 2 (the capture). A count over the whole product file says "catalog".
- **"(scores on: …)"** names the judging criterion of section 1 that a piece of the system serves.
- **"In the code"** lines come last in each step. Paths are relative to the repository root.
- Internal task ids and review history are kept out of the main text. They are all in section 13.

## Contents
1. [What the judges score and what the brief asks](#1-what-the-judges-score-and-what-the-brief-asks)
2. [Who and what is involved](#2-who-and-what-is-involved)
3. [Scenario 1, step by step: 1,000 litres of lactose-free milk](#3-scenario-1-step-by-step-1000-litres-of-lactose-free-milk)
4. [Scenario 2: the allergy ward, ordered by the agent alone](#4-scenario-2-the-allergy-ward-ordered-by-the-agent-alone)
5. [Scenario 3: the product asked for has no confirmed stock](#5-scenario-3-the-product-asked-for-has-no-confirmed-stock)
6. [Other exception paths](#6-other-exception-paths)
7. [The ways in, the two modes, the deployment](#7-the-ways-in-the-two-modes-the-deployment)
8. [How the code is cut: packages, ports and contracts](#8-how-the-code-is-cut-packages-ports-and-contracts)
9. [The rules in one table](#9-the-rules-in-one-table)
10. [Check it yourself](#10-check-it-yourself)
11. [Known limits](#11-known-limits)
12. [Being added today](#12-being-added-today)
13. [How it was built and what the reviews changed](#13-how-it-was-built-and-what-the-reviews-changed)
14. [Other documents](#14-other-documents)
15. [Glossary](#15-glossary)
16. [Questions for Valio Aimo still without an answer](#16-questions-for-valio-aimo-still-without-an-answer)
17. [Decisions we took on our own — to confirm with Valio Aimo](#17-decisions-we-took-on-our-own--to-confirm-with-valio-aimo)

---

## 1. What the judges score and what the brief asks

Everything below is weighed against this section. The full brief is `AIMO/CHALLENGE.md`.

### 1.1 The five judging criteria

Quoted from the Junction platform. The last column is the short name used in the rest of this document.

| Weight | Criterion | Their wording | Short name below |
|---|---|---|---|
| 30% | Working end-to-end demo | "The solution runs through a full request → lookup → order/approval flow in the mocked environment, not just isolated pieces." | end-to-end demo, 30% |
| 20% | Solving the problem and user need | "how Precisely the agent matches what the buyer actually asked for, with the least manual correction needed." | match to the request, 20% |
| 20% | Autonomy and controls | "Quality of the guardrails design. What the agent can decide alone, what needs human sign-off, and how decisions are logged and auditable." | autonomy and controls, 20% |
| 15% | Robustness to exception situations | "Handling of partial availability, substitutions and delivery constraints beyond the happy path." | exceptions, 15% |
| 15% | Openness and credible path toward production | "Open, documented standards rather than a proprietary format, clear visibility of assumptions, well-justified technical choices, and a credible view of next development steps" | openness, 15% |

### 1.2 The brief's three core requirements

Quoted: "the solution must enable":
- **Core 1.** "Product, price & availability lookup: a structured way for an external agent to search for and retrieve what's available and at what price."
- **Core 2.** "Requesting price & availability, then placing an order: a defined interaction for moving from inquiry to commitment, based on fixed prices rather than a negotiated quote."
- **Core 3.** "Permission & human-approval management: what the agent may decide on its own, and what must go to a human for sign-off."

Their example: "I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability." … "A hotel chain's agent sends this request. Your solution returns products, prices and availability in structured form; the agent places the order within its authority or sends it to a human for approval."

And what it is not: "This is not about replacing today's e-commerce UI with a chatbot."

### 1.3 What else the brief invites

Optional directions (not required to win): delivery time and sustainability comparison; substitution and other exception handling; traceability and explainability ("a human-readable record of what the agent did and why").

Four "problems we'd love to see tackled":
- **Trust protocol:** what an external agent can trust about stock, price and origin without a manual check.
- **Guardrails model:** which decisions need human sign-off.
- **Response logic:** partial availability and "good-better-best" substitution ranking.
- **Audit trail:** a human-readable log "for both buyer and Valio Aimo".

Substitution is optional in the brief but named in the exceptions criterion (15%), so it is built.

### 1.4 What was built, in one paragraph

A **gateway**: one Python web service that sits between a buyer's purchasing agent and Valio Aimo's price and availability service. The agent sends a request. The gateway finds matching products, asks Valio for fixed prices and stock, and answers with an **offer**: a few ranked options, each saying what is confirmed and what is not, why other products were left out, and whether the agent may order it alone. The agent then orders. The gateway checks again, and either records the order at once or sends it to a named human. Every step is written to an audit trail that the buyer and Valio each read in their own words.

| Brief | Built | Section |
|---|---|---|
| Core 1, lookup | Product search, and an offer with live price and availability | 3, steps 3 to 9 |
| Core 2, inquiry to commitment at fixed prices | Offer, then order with a fresh re-check | 3, step 11 |
| Core 3, permission and approval | Rules as data, a buyer profile per buyer, named approvers | 3, steps 10 and 12; 9 |
| Trust protocol | A status for each claim of each offer line | 3, step 8 |
| Response logic | Combined fills, partial fills, ranked substitutes | 3, step 7; 5; 6 |
| Audit trail | One event per step, two readers, a hash chain | 3, step 13 |
| Delivery time and sustainability comparison | **Not built** (the data is loaded and shown on a product, nothing more) | 11 |

---

## 2. Who and what is involved

The terms here are used in every later section.

- **Valio Aimo (the supplier).** The food-service wholesaler that set the challenge.
- **The mock API.** The web service Valio set up for the hackathon (API: an interface that programs call). It has two endpoints, `price` and `availability`, each taking up to 1,000 product ids per call. It has **no order endpoint**, so placing and approving orders is ours to define. Its answers are synthetic.
- **Product.** One item Valio sells, with a six-digit id. Example: `464306`, "Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free".
- **Catalog.** Valio's product file, read locally at start: 17,546 products with names, category codes, sales units, allergen statements, nutritional claims and listed substitutes. It holds no price and no stock; those come from the mock API.
- **Nutritional claim.** A label in the product file such as `FREE_FROM_LACTOSE` or `VEGAN`. It is **not** an allergen statement: all 30 lactose-free milks of scenario 1 still declare milk.
- **Allergen statement.** What a product declares about one allergen, with a GS1 code (GS1 is the standards body behind barcodes; its codes are public): `AM` milk, `AW` cereals containing gluten. Example: `473609` declares "contains `GO`" (oats).
- **Buyer.** A professional kitchen that buys from Valio. Two invented buyers exist: a hotel kitchen and a hospital allergy ward.
- **Buyer's agent.** Software acting for one buyer: it sends requests and places orders. Ours is a Gemini-driven loop (Gemini is Google's language model), but any agent can call the gateway.
- **Buyer profile.** The settings that say what one buyer's agent may do alone: spend limits, minimum share of the quantity, allergen exclusions, which substitutes are acceptable. One file per buyer, in YAML (a plain-text settings format). Both profiles are ours and illustrative: the mock has no customers and Valio publishes no customer limits.

| Setting | `hotel-kitchen` | `allergy-ward` |
|---|---|---|
| Agent may order alone at all | yes | yes |
| Spend limit per order | €750 | €500 |
| Spend limit per day, this order included | €3,000 | €1,500 |
| Minimum share of the quantity covered | 90% | 100% |
| Excluded allergens, strictness | none | `AM` milk, `AW` gluten, `STRICT` |
| Substitutes accepted without a human | same category | none |
| Variable-weight products | to a human | to a human |
| Products with a deposit | to a human | to a human |
| Confirmed data only | no | yes |

- **Approver and approver roles.** A human at the buyer who signs off what the agent may not do alone. Three roles: **purchasing manager**, **dietitian**, **finance**. The profile names who holds each role. Demo approvers: Hanna (hotel, purchasing manager), Mikko (hotel, finance), Leena (hotel, dietitian), Jussi, Anna and Sari (ward: purchasing manager, finance, dietitian). The names are invented.
- **The gateway.** Our service, in `src/tta/` (`tta` stands for Trusted Trade Agents). Agents reach it over HTTP (the web's request protocol; HTTPS is its encrypted form), either as **REST** calls (plain web requests whose bodies are JSON, the common text format for structured data) or through **MCP**, a protocol for language-model agents (both in section 7).
- **Live and replay.** Two modes of the gateway. In **live** mode it calls the mock API. In **replay** mode it answers from a capture and calls nobody.
- **Capture.** Recorded answers of the mock API, kept in the repository. The default one is `fixtures/valio/2026-11-14-demo`: one price call and one availability call for 769 products (the categories whose codes start with 104, the category 18720, and the scenario products with their listed substitutes), taken on Saturday 14 Nov 2026 at 02:52:45 Helsinki time. Every scenario number of sections 3 to 6 comes from it.
- **Data clock.** The time against which order cut-offs, price validity and approval deadlines are judged. In replay it is **pinned** to the capture's time, Saturday 02:52:45, so the outcomes never change with the hour. In live mode it is Valio's own server time (`timeNow`), carried forward between answers and never moved backwards. Audit events are an exception: they are stamped with the real time.

---

## 3. Scenario 1, step by step: 1,000 litres of lactose-free milk

### 3.0 The whole path at a glance

The hotel kitchen's agent sends: **"1,000 litres of lactose-free milk by Monday"**.

```
 1 who is asking ─► 2 text becomes a typed request ─► 3 candidate products ─► 4 price and availability
     ─► 5 availability state ─► 6 exclusions ─► 7 options ─► 8 claims ─► 9 constraint checks
     ─► 10 verdict ─► 11 the agent orders ─► 12 a human approves ─► 13 the audit trail
```

| | Outcome in replay |
|---|---|
| Read as | 1,000 L, product type `milk`, nutritional claim `FREE_FROM_LACTOSE`, needed by Monday 16 Nov 2026 |
| Candidates | 30 lactose-free milks |
| Excluded | 19: 17 order cut-off passed, 1 portion pack, 1 not deliverable |
| Option 1 | 384 × `469363` + 51 × `462775` + 565 × `463380`, all stock confirmed, **€2,580.64** |
| Option 2 | 1,000 × `464306`, stock not confirmed by Valio, **€1,010.00** |
| Verdict | Both need a human: option 1 is above the €750 limit per order; option 2 also has an unconfirmed quantity |
| End | Hanna (purchasing manager) approves option 1; the order is recorded; 9 audit events, chain intact |

### Step 1. The agent sends the request, and the gateway knows who is asking

**What the agent sees.** Every call carries a **bearer token**, a secret string in the header `Authorization: Bearer <token>`. Without one, the gateway answers 401. With the hotel agent's token, `GET /v1/authority` answers the agent's own authority in plain sentences, for example: "Alone, at most: €750 before tax per order and €3,000 before tax per day, this order included, with at least 90% of the requested quantity covered."

**What the gateway decides.** A token maps to exactly one **identity**:
- an **agent**, bound to one buyer profile and holding no approver role;
- an **approver**, a human of one buyer with one or more roles;
- the **supplier reader**, Valio, which may read only its own view of the audit trail.

The buyer profile is never a field of the request. It comes from the token.

**Why.** An agent must not be able to pick its own authority, approve its own order, or read another buyer's orders (scores on: autonomy and controls, 20%). Asking for another buyer's order answers "not found", exactly as for an id nobody issued.

Nine demo tokens exist, public by design, in `src/tta/api/demo_tokens.yaml`. They load only when the setting `TTA_ENV` is `dev` or `demo`. When `TTA_ENV` is unset it means `prod`: no demo token exists, and the gateway refuses to start unless real tokens are given in `TTA_TOKENS` (each at least 24 characters). Tokens are kept only as SHA-256 digests (a one-way fingerprint) and compared in constant time.

*In the code:* `src/tta/api/identity.py`, `src/tta/api/demo_tokens.yaml`, `src/tta/config.py`, `src/tta/contracts/common.py` (`Identity`).

### Step 2. The text becomes a typed request

**Terms.** A **typed request** is the structured form of what the buyer wants: an optional needed-by date, an optional "confirmed data only" flag, and one or more **request lines**. Each line holds the buyer's own words, a product type or product ids, required nutritional claims, a quantity with a unit (`L`, `KG`, or `UNIT` for sales units), allergen exclusions and their strictness, and a pack preference (bulk by default). A **product type** is a key of a table we wrote, such as `milk` or `plant_drink`.

**What the buyer sees.** On the page: "read as 1,000 L of product type milk, with claim FREE_FROM_LACTOSE, pack: bulk", "Needed by: Monday 16 Nov 2026".

**What the gateway decides.** Gemini (model `gemini-3.6-flash`) is asked to fill the typed request, under a JSON Schema (a machine-checkable description of the expected fields). It may choose a product type only from the table's 30 keys. Its answer is a **proposal**, and the gateway then holds it to the text itself, without a model:
- the quantity must be a number written in the text ("1,000", "1 000", "a thousand");
- the unit must match a unit word of the text (English or Finnish);
- the date must be the one a fixed calendar rule gives for the day the text names: "Monday" is the first Monday after today, in Helsinki, by the data clock (in replay: Saturday 14 Nov, so Monday 16 Nov);
- every allergen the text excludes ("no milk", "without gluten") must be excluded;
- "confirmed data only" may be set only if the text says "confirmed" or "verified";
- a product id must be a whole word of the text.

A disagreement is asked once more, then refused as `invalid-request` with the field named. Nothing is corrected silently. What the text does not say is reported, never guessed: "Some milk for Monday" answers 422, "Line 1 does not say how much is needed: the quantity is missing. A quantity is never guessed."

**Who read it.** The answer says so, in the headers `TTA-Read-By` and `TTA-Reading-Source` and on the page. Three sentences have **recordings** of Gemini's real answers in `fixtures/agent/`: scenario 1's reading (14 Nov, 07:13 UTC), scenario 2's reading and its whole agent run (06:16 UTC), and "Some milk for Monday" (06:17 UTC). Scenario 1's agent run is written by hand, and says so. With no Gemini key, only these three sentences can be read; any other text answers 503 and points to sending the typed request instead. With a key, if Gemini cannot be reached, a recorded sentence is answered from its recording and labelled ("Gemini did not answer; …"), and Gemini is not asked again for 120 seconds. A recording is served only for the buyer profile it was recorded for.

**Why.** The brief scores how precisely the agent matches what the buyer asked (scores on: match to the request, 20%). The design rule from the specification is that **the model never decides a price, a quantity, an allergen status or a verdict**: the model reads text, code decides (scores on: autonomy and controls, 20%). The model is also optional: any agent may skip this step and send a typed request to `POST /v1/offers`.

*In the code:* `src/tta/agent/parser.py`, `textcheck.py`, `days.py` (the calendar rule), `schema.py`, `prompts.py`, `gemini.py` (`DEFAULT_MODEL`), `fallback.py`, `outage.py`; recordings in `fixtures/agent/`.

### Step 3. The catalog gives the candidate products

**Terms.** A **candidate** is a product that matches what the request line names, before price, stock and rules are looked at.

**What the buyer sees.** "Products looked up: 30".

**What the gateway decides.**
- The product type `milk` is category `10400` without the words "sour", "piimä", "coffee drink", "maitokahvi" and "soygurt". That keeps 78 products (catalog) and leaves out 11 sour milks, a milk coffee drink and a soy yoghurt. Milks for coffee stay in; `463380` "Cafè milk" is one of them.
- The required nutritional claim `FREE_FROM_LACTOSE` narrows the 78 to **30**.
- A line that names products by id uses exactly those ids, after checking they are in the catalog (scenario 3). A line with neither a type nor ids searches the English, then Finnish, names.

**Why.** "Milk" should not bring sour milk. A bulk buyer should not get single-serve portions (step 6). (Scores on: match to the request, 20%.) The product-type table is ours: the catalog has 349 five-digit category codes and no category names. Each of its 30 entries records how it was derived and how many products it selects.

*In the code:* `src/tta/catalog/product_types.yaml`, `search.py`, `catalog.py`.

### Step 4. One look at Valio's price and availability

**What the gateway decides.** One price call and one availability call for all candidates, **both answered by the same source**: both live, or both from the capture, never one of each.

With the price in hand, it works out two numbers per product:
- **Pack size:** how many litres or kilograms one **sales unit** (the unit Valio sells in: a carton, a case, a kilogram) holds. Valio writes sales units as codes such as `ST`, `KI` and `KG` and publishes no translation; in the data `ST` is usually a single item and `KI` a case. Three sources, in order: the live price ratio (`catalogPrice ÷ comparisonPrice`), the product file's unit conversions, the product name. When none gives a size, the product is excluded (step 6). The three milks of option 1 hold 1 L per sales unit, from the price ratio.
- **Lot step:** the multiple a quantity must be ordered in. The file's `allowedLotSize` of 0.01 means "no step", read as whole sales units (kilogram products keep 0.01 kg). Real steps are used as given: the backup beef chuck is sold in steps of 3 kg, so 31 kg becomes 33 kg.

In live mode the client to the mock API:
- sends a named `User-Agent` header, because the API sits behind Cloudflare (a service that screens web traffic), which refuses Python's default;
- waits at least one second between calls and caches answers for 60 seconds;
- counts calls against a budget kept in a file under a lock (150 by default; 120 on the deployed app);
- retries twice on a time-out or a server error, never on a refusal;
- talks HTTPS only (plain HTTP only to this machine, for tests), and does not read an answer over 20 MB;
- refuses a server time more than 12 hours from the machine's own.

**When live mode answers from the capture.** When the mock cannot be reached, when fewer than 10 calls would be left in the budget, or when more than 6 live looks a minute are asked for (2 per address). The offer then says `source: replay`.

**What the buyer sees.** In replay, a yellow box on every page: "Replay: recorded Valio Aimo data, clock pinned to the recording". Every offer carries `source` (`live` or `replay`) and `time_now`. `/healthz` shows the mode and the source.

**Why.** The demo must survive the mock being down, slow or out of budget, and a judge must be able to tell recorded data from live data (scores on: end-to-end demo, 30%; openness, 15%). Price and stock from one source, because an offer mixing a live price with recorded stock would rest on no single statement of Valio's.

*In the code:* `src/tta/valio/` (`client.py`, `replay.py`, `budget.py`, `clock.py`, `recorder.py`), `src/tta/api/fallback.py`, `src/tta/offers/deps.py`, `src/tta/catalog/pack.py`, `lots.py`.

### Step 5. Each product gets an availability state

**Terms.** An **availability state** is one of six labels for what Valio's availability answer says about a product. They are checked in this order; the first that applies wins.

| State | When | Example tonight |
|---|---|---|
| `BLOCKED` | Valio has blocked sales | — |
| `NOT_DELIVERABLE` | no delivery date at all | `464440`: "Valio cannot currently deliver this product on any date." |
| `OUT_OF_STOCK` | stock 0 | — |
| `CUTOFF_PASSED` | the order cut-off (`closingTime`) is at or before now | 17 milks: "Order cut-off passed on Thursday 12 Nov at 15:00, so delivery on Monday 16 Nov cannot be promised." |
| `QUANTITY_NOT_CONFIRMED` | stock reported as 999,999 or more | `464306`: "Valio reports 9,999,999,999 ST, a placeholder that means the stock is not known." |
| `CONFIRMED` | otherwise | `469363`: "384 ST confirmed in stock, for delivery on Monday 16 Nov if ordered by Sunday 15 Nov at 17:00." |

Of the 30 candidates: 17 cut-off passed (all of them Terminal products, which in Valio's words "are delivered from supplier's warehouses"), 8 quantity not confirmed, 4 confirmed (one of them the portion pack of step 6), 1 not deliverable.

**Why these rules.**
- The API documentation says to "order by closingTime at the latest to receive goods on availableDate". So a cut-off that has passed means that date can no longer be promised, and a cut-off equal to now counts as passed.
- Valio confirmed in person on 14 Nov that a very large stock figure means "not known". That figure is never used in arithmetic.
- (Scores on: exceptions, 15%: "partial availability … and delivery constraints".)

*In the code:* `src/tta/availability/states.py`; the threshold in `src/tta/contracts/availability.py`.

### Step 6. Products that cannot serve the request are excluded, each with a reason

**Terms.** An **exclusion** is a candidate left out of every option, with a reason code and one sentence.

**What the gateway decides.** Each candidate goes through these checks in order; the first that fails is its reason:
1. it declares an allergen the buyer excludes (`ALLERGEN_DECLARED`);
2. it is a pack of single-serve portions on a bulk line (`PORTION_PACK`: one inner unit of 5 cl or 50 g or less), or the reverse;
3. its pack size is unknown (`PACK_SIZE_UNKNOWN`);
4. its state is blocked, not deliverable, out of stock or cut-off passed;
5. its delivery date is later than the needed-by date (`LATE_FOR_NEEDED_BY`);
6. its price cannot carry an order: none, not in euros, not positive, or not valid now (`PRICE_UNAVAILABLE`);
7. only under "confirmed data only": an excluded allergen is not settled, the quantity is not confirmed, or the delivery date is not confirmed.

A product whose cut-off has passed is excluded whether or not the request names a date.

**What the buyer sees.** Scenario 1 excludes 19: 17 × "Cut-off passed", 1 × "Not deliverable", and 1 × "Portion pack": "Arla Portion milk 100x2 cl … (463203) This is a pack of single-serve portions: one sales unit holds 100 portions of 0.02 L. The request is for bulk packs."

**Why.** Nothing is hidden: a buyer or a judge can see why each product is not offered (scores on: exceptions, 15%; match to the request, 20%).

*In the code:* `src/tta/offers/candidates.py` (`exclusion_for` and the checks under it).

### Step 7. The options: what the gateway proposes

**Terms.** An **offer** is the gateway's answer to one request. It holds up to three **options**, ranked. An option is one way to fill the request; it holds one or more **lines**, each one product with a quantity in sales units, a unit price and a total. An offer is stored and has an id (`off_…`); options are `opt_1`, `opt_2`, `opt_3`.

**What the gateway decides.** Three kinds of option:
- **Best confirmed** (`BEST_CONFIRMED`): products with confirmed stock only. The cheapest single product that covers the whole quantity. If none does, the cheapest per litre first until the quantity is covered. If confirmed stock still falls short, a partial fill that says how much is missing.
- **Alternative, quantity not confirmed** (`ALTERNATIVE_UNCONFIRMED`): the cheapest fitting product whose stock Valio does not confirm, for the whole quantity. A full option a human can choose, not a footnote.
- **Substitute** (`SUBSTITUTE`): only when the request named products by id and they cannot be supplied in full (scenario 3).

Ranking: an option holding any unconfirmed quantity is never first. After that, fewer unmet checks (step 9), fewer unverified checks, the kind, then the lowest total.

Each option also carries its totals (net, tax, gross; whether the total is a ceiling because of variable weight; whether it leaves deposits out), how much of each line it covers, and **valid until**: the earliest price end and order cut-off of its lines. After that time it can no longer be ordered as offered.

**What the buyer sees.**
- **Option 1:** "3 confirmed products cover the 1,000 L asked for, for €2,580.64 before tax." None of the confirmed milks has 1,000 in stock, so the cheapest come first: 384 × `469363` at €2.48 (all its stock), 51 × `462775` at €2.57 (all its stock), 565 × `463380` at €2.65 (of 698). Gross €2,929.02. Valid until Sunday 15 Nov 17:00.
- **Option 2:** "Valio Hyvä … (464306) for the 1,000 L asked for, €1,010.00 before tax. Valio does not confirm the quantity in stock, so a human must approve this option." The cheapest per litre, but never the suggestion.
- **A note:** 7 more products fit the request and are in no option. All 7 have stock Valio does not confirm; only the cheapest such product becomes option 2.

**Why.** "Good-better-best" ranking and partial availability are named in the brief (scores on: exceptions, 15%; match to the request, 20%). Showing the cheaper unconfirmed choice beside the confirmed one lets a human trade price against certainty.

*In the code:* `src/tta/offers/builder.py`, `planning.py` (which lines go into which option), `combining.py`, `options.py` (totals, rank), `lines.py`.

### Step 8. What can be trusted: a status for each claim

**Terms.** A **claim** here is one statement an offer line makes. Every line states five: `price`, `quantity`, `delivery_date`, `allergens`, `origin`. Each has a **status**: `CONFIRMED` (Valio's data confirms it), `UNKNOWN` (the data does not say) or `RULED_OUT` (the data says it does not hold), with a sentence. Do not confuse it with a nutritional claim (section 2).

| Claim | `CONFIRMED` | `UNKNOWN` | `RULED_OUT` |
|---|---|---|---|
| price | a price, valid now | no price, or its validity has ended | — |
| quantity | confirmed stock covers the line | stock not confirmed, or cut-off passed | out of stock, not deliverable, blocked, or too little |
| delivery date | cut-off open and delivery on or before the needed-by date | no needed-by date given, or no date or cut-off from Valio | cut-off passed, or delivery later than needed |
| allergens | every excluded allergen is settled by an explicit statement (or nothing is excluded) | an excluded allergen is "may contain", "undeclared" or not stated | an excluded allergen is declared "contains" |
| origin | the product file states a country | absent | — |

**Which claims hold an order back from the agent.** Price and quantity always. The delivery date only when the request gives a needed-by date. Allergens through the allergen rule (section 4). Origin never: it is shown, but no buyer asked for it.

**What the buyer sees.** Option 1: all five claims confirmed on every line, for example "Valio's price is €2.48 per ST before tax, with no end date." and "The buyer excluded no allergen, so there is nothing to check." Option 2: quantity `UNKNOWN`.

**Why.** This is our answer to the brief's "trust protocol": an agent can see, claim by claim, what it may rely on without a manual check (scores on: autonomy and controls, 20%; match to the request, 20%). Without the "which claims hold an order back" rule, a request with no date, or a product with no stated origin, could never be ordered alone.

*In the code:* `src/tta/availability/claims.py`; the gating list `GATING_CLAIMS` in `src/tta/offers/candidates.py`; `AIMO/SPEC.md` §4.

### Step 9. What the buyer asked for, checked: the constraint checks

**Terms.** A **constraint check** is one per thing the buyer asked for (product type, product id, name words, quantity, needed-by date, each nutritional claim, each allergen exclusion, pack, confirmed data only), with a result `MET`, `NOT_MET` or `UNVERIFIED` and a sentence.

**What the buyer sees.** Option 1 has five checks, all met, among them "Every product offered carries the nutritional claim FREE_FROM_LACTOSE. A claim is not an allergen statement." and "Every product offered is delivered by Monday 16 Nov if ordered by its cut-off." Option 2's quantity check is `UNVERIFIED`: "The 1,000 L asked for are offered, but Valio does not confirm the quantity in stock."

**Why.** The judges score "how precisely the agent matches what the buyer actually asked for" (scores on: match to the request, 20%). The checks say it per request, not in general.

*In the code:* `src/tta/offers/checks.py`.

### Step 10. The verdict: may the agent order alone?

**Terms.**
- A **rule** is one written condition with a consequence. **Fixed rules** (`F-01` to `F-08`) hold for every buyer; no profile can switch them off. **Profile rules** (`P-00` to `P-07`) compare an option with one buyer's settings. All are listed in section 9.
- A **verdict** is the outcome for one option: `AUTO` (the agent may order alone), `APPROVAL` (a human with a named role must sign) or `BLOCK` (cannot be ordered, even with approval). When several rules fire, the most severe verdict wins.
- The **policy hash** is a SHA-256 fingerprint of the rules plus the profile in force, stored with every decision, so later one can tell exactly which rules decided.

**What the gateway decides.** The rules run on every option before the agent orders, so the agent knows its options in advance. Every rule that fires is listed with its sentence and the facts it read. A fact a rule needs that is missing never counts as passing: it fires F-03, which sends the option to a human.

- **Option 1 → `APPROVAL`**, by P-01, to the purchasing manager: "The agent cannot place this order alone: the total of €2,580.64 before tax is above the €750 limit per order of profile hotel-kitchen (P-01). It needs the purchasing manager."
- **Option 2 → `APPROVAL`**, by F-01 (quantity not confirmed) and P-01, also to the purchasing manager. The page tags F-01 "fixed rule: no profile can switch it off".

**Why.** "What the agent can decide alone, what needs human sign-off" is the heart of the 20% criterion and of Core 3 (scores on: autonomy and controls, 20%). The rules are data a person can read and change, never a model's judgement.
- The fixed rules' verdicts and roles are also written in code. A rules file that weakens or drops one is refused when the gateway starts.
- A profile file that names a fixed rule, or carries an unknown setting, is refused too.
- `GET /v1/authority` lists every rule with the caller's own limit values.

*In the code:* `src/tta/policy/rules.yaml` (the rules as data), `src/tta/policy/profiles/*.yaml`, `engine.py`, `facts.py`, `validation.py` (the fixed rules pinned), `hashing.py`.

### Step 11. The agent orders

**Terms.**
- An **order** is the agent's commitment to one option of one offer, kept in the gateway's **order book** (its database of offers, orders and approvals). Its status is `PENDING_APPROVAL`, `ORDERED`, `REJECTED` or `EXPIRED`.
- **`ORDERED` means recorded in our order book.** The mock has no order endpoint, so nothing is sent to Valio. The record holds what a supplier order message would need, and says it commits nobody.
- An **idempotency key** is a string the agent invents and sends with an order, in the header `Idempotency-Key`. Sending the same order again with the same key returns the first order instead of placing a second. Agents retry after time-outs; a retry must never buy twice.

**What the gateway decides** on `POST /v1/orders` with `{"offer_id": …, "option_id": "opt_1"}`:
1. Only an agent token may place an order. The key is required: 1 to 100 letters, digits, `.`, `_`, `:` or `-`.
2. The same key from the same agent returns the first order. The same key for another offer or option is refused.
3. An offer answers one request: while one of its orders waits or is ordered, another order on it is refused, whatever the option or key.
4. A **fresh re-check** of price and availability, skipping the cache, compared with what the offer stated. It counts as a change when any of these moved: the price, the tax rate, the price validity, the availability state, the cut-off, or the sales unit. It also counts when delivery is now **later**, or stock **no longer covers** the option. Stock that moved but still covers is not a change; neither is an earlier delivery.
5. The rules again, at order time, with today's spend of this buyer.
6. One outcome:
   - expired or changed (rule F-04) → 409 `offer-stale` or `offer-expired`, carrying `fresh_offer_id`: a new offer for the same request, made on the spot;
   - any other `BLOCK` → 422 `policy-blocked`;
   - `AUTO` → `ORDERED`, placed by the agent;
   - `APPROVAL` → `PENDING_APPROVAL`, with an approval id, the roles needed and a decide-by time.

The order, its approval, its key and its audit event are written in **one database transaction**: all or nothing. A refusal by the re-check or by the rules also writes an audit event.

**What the agent sees.** 201, `PENDING_APPROVAL`: "Waiting for approval by the purchasing manager, to be decided by Sunday 15 November 2026 at 17:00 (UTC+02:00): rule P-01 asks for a human." The record lists the statements the order relied on: for each product, the price and its end, the state, the stock figure, the delivery date, the cut-off and the time Valio stated them. The same request with the same key returns the same order. A second key on the same offer answers 422: "Offer … already has an order: …, which is waiting for approval."

**Errors** follow RFC 9457 (the internet standard for machine-readable error answers, `application/problem+json`), each with a stable type such as `offer-stale`. No error repeats text the caller sent.

**Why.** Core 2: "moving from inquiry to commitment, based on fixed prices". The order commits to the prices of the offer, and only if they still hold. (Scores on: end-to-end demo, 30%; autonomy and controls, 20%.)

*In the code:* `src/tta/orders/service.py`, `checking.py` (re-check and rules), `outcomes.py` (the one-transaction writes), `records.py`, `spend.py`; `src/tta/offers/revalidation.py`; `src/tta/api/service.py` (`fresh_offer_id`); `src/tta/store/sqlite_store.py` (`atomic()`).

### Step 12. A human approves

**Terms.** An **approval** is the request for sign-off attached to a waiting order: which roles it needs, why, and until when.

**What the approver sees.** On `/approvals`, a card: "Waiting for approval · Order by Sunday 15 Nov 2026 at 17:00 (UTC+02:00): after that the order expires", the reasons, "Needs: purchasing manager", and the options of the offer, the proposed one checked. Over the REST interface (section 7): `GET /v1/approvals?status=pending`, then `POST /v1/approvals/{id}/decision` with `{"decision": "APPROVE"}` (optionally `option_id` and `note`) or `"REJECT"`.

**What the gateway decides.**
- **An agent can never approve** (rule F-06). The agent's token on the decision route answers 403: "An agent cannot approve or reject an order (F-06). A human with the role asked for decides." The attempt is written to the audit trail.
- **The approver must hold a role the approval still needs**, and the buyer's profile must list that person under it. Mikko (finance) on this approval answers 403: "The approval still needs the purchasing manager; this approver counts for finance and holds none of them." Also recorded.
- **Approving re-runs the order-time check** (step 11, points 4 to 6) before the order becomes `ORDERED`. If Valio's data changed, the answer is `offer-stale` and the order keeps waiting.
- **Another option of the same offer** may be chosen. The rules run again on it, `BLOCK` still blocks, and approvals given for the first option do not carry over.
- **Several roles:** the order stays waiting until every role the rules ask for has signed.
- **A rejection** ends the order as `REJECTED`; nothing is ordered.
- **Expiry:** an approval can be decided until the option's "valid until" time, or 24 hours after it was created when the option has none. Expiry is applied the next time the order or the approval list is read. In replay the data clock stands still at Saturday 02:52, so a waiting order never expires there.

**What happens in scenario 1.** Hanna approves with the note "Checked with the kitchen." → `ORDERED`, placed with human approval: "Ordered for €2,580.64 net with approval by Demo approver Hanna (purchasing manager): rule P-01 asked for a human and was accepted."

**Why.** Core 3, "what must go to a human for sign-off", and a named, accountable person for each kind of decision (scores on: autonomy and controls, 20%; end-to-end demo, 30%).

*In the code:* `src/tta/orders/service.py` (`decide`, `_approve`, `_reject`, `_current` for expiry), `access.py` (who may decide), `records.py` (`roles_still_needed`, `approved`, `decide_by`); `src/tta/ui/approvals_page.py`.

### Step 13. The audit trail records it

**Terms.**
- An **audit event** is one record per step, written when the step happens and never changed afterwards.
- Each event sits in a **CloudEvents 1.0** envelope (a public standard for event records: fields `specversion`, `id`, `source`, `type`, `time`, `subject`, `data`).
- Its `data` holds the actor (agent, human or the gateway), the rule ids and the facts they read, the policy hash, and two sentences: one for the buyer and one for Valio.
- The **hash chain**: each event carries the SHA-256 hash of the event before it and its own hash, computed over the event's content. Changing an old event breaks the link to the next one. There is one chain per order book, across all buyers.
- The **buyer view** and the **supplier view** are the two ways to read the same events.

**What gets written in scenario 1.** Nine events, in order:

| Event type | Buyer's sentence (shortened) |
|---|---|
| `request.received` | The agent sent a request for profile hotel-kitchen: "1,000 litres of lactose-free milk by Monday". |
| `request.parsed` | The request was read as: 1,000 litres of product type milk with claim FREE_FROM_LACTOSE, needed by Monday 16 November 2026. |
| `lookup.performed` | The gateway looked up price and availability of 30 products in a recorded copy of Valio Aimo's data (replay). |
| `offer.created` | … 2 options from 30 candidates, 19 products excluded with a reason. Option 1 … €2,580.64 … Option 2 … €1,010.00 … |
| `policy.evaluated` (×2) | One per option, with its verdict sentence. |
| `approval.requested` | The agent could not place order … alone, because 1 rule asks for a human. P-01: … sent to the purchasing manager, to be decided by Sunday 15 November 2026 at 17:00 (UTC+02:00). |
| `approval.decided` | Demo approver Hanna (purchasing manager) approved order …. This approval accepts rule P-01. Note: "Checked with the kitchen." |
| `order.confirmed` | Order … is ordered, with approval by Demo approver Hanna …. Price and availability were checked again and had not changed. |

Refused attempts add `authorisation.refused` events (the two 403s of step 12 make it eleven).

**Who sees what.**
- **The buyer view** is for the buyer's own agent and approvers. It shows everything about that buyer's own requests: options, exclusions, rules, limits, approvers, notes.
- **The supplier view** is what Valio's token gets. The same events, but:
  - Valio's sentences never show a limit value, an allergen exclusion, an approver's name or role, a note, or the buyer's own words;
  - humans appear as "a human at the buyer";
  - only fixed rules that rest on Valio's own data are named, never F-02 or a profile rule.

  Examples: "The buyer's agent sent a purchase request." and "The buyer's rules were checked for option opt_2: a human at the buyer must approve this order. Fixed rule that applied: F-01 (a line's quantity is not confirmed)."
- A buyer's agent or approver may also ask for the supplier view of its own events, to see what Valio sees.

Every sentence is built from a template, never by a model.

**Protection.**
- **In the database:** triggers refuse any change, deletion or replacement of an event, and no two events may follow the same event.
- **The chain** shows an event that was changed, removed or inserted, unless every hash after it was recomputed too.
- **What the chain cannot show:**
  - the last events cut off: a shorter chain still verifies;
  - a rewrite from some event to the end with the hashes recomputed: there is no secret key;
  - who wrote an event: nothing is signed.
- **The head** (the number of events and the last hash) is published at `/healthz`. Another party holding an earlier head would catch the first two cases, but nothing compares heads yet.

**What the reader sees.** On `/orders/{id}`: "The audit trail is intact: each of the 9 events shown here matches its hash, and the chain they belong to verifies", and a tab for each view.

**Why.** "how decisions are logged and auditable" and the brief's log "for both buyer and Valio Aimo" (scores on: autonomy and controls, 20%). CloudEvents and SHA-256 are open, documented formats anyone can check with standard tools (scores on: openness, 15%).

*In the code:* `src/tta/audit/` (`trail.py`, `chain.py`, `sentences.py`, `supplier_sentences.py`, `readers.py`, `views.py`), `src/tta/contracts/audit.py`, `src/tta/store/schema.py` (the triggers).

---

## 4. Scenario 2: the allergy ward, ordered by the agent alone

The ward's agent sends: **"200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"**. Same path as scenario 1. What differs:

**The request and the profile.** Read as 200 L of product type `plant_drink`, excluding `AM` (milk) and `AW` (cereals containing gluten), confirmed data only, needed by Monday 16 Nov. The ward's profile adds the same two exclusions with strictness `STRICT`, and sets confirmed data only too. A request can add exclusions and strictness; it can never remove the profile's.

**The allergen rule.** For each excluded allergen, the gateway reads what the product declares:

| The product says | `STRICT` | `DECLARED_ONLY` |
|---|---|---|
| free from it | passes | passes |
| contains it | rejected | rejected |
| may contain it | to the dietitian | to the dietitian |
| "undeclared", or nothing at all | to the dietitian | passes, shown as unverified |

**How the rule reads the data.**
- **Families are read both ways.** `AW` covers wheat `UW`, barley `GB`, rye `NR`, oats `GO`, spelt `GS` and khorasan `GK`:
  - a declared member declares the family;
  - declared oats count as "may contain" gluten, because oats can be gluten-free or not, so they go to the dietitian;
  - a declared family means a member may be contained, unless the product states that member free.
- **Conflicting statements:** the least safe one counts. A "gluten free" bread that declares wheat is rejected under a no-gluten exclusion.
- **`X99`** is GS1's general "does not contain declaration obligatory allergens". It is never read as a statement about one allergen.
- **No data means unknown, never safe.** 46.2% of the catalog (8,110 of 17,546 products) has no allergen statement at all.

Under "confirmed data only", a product the rule would send to the dietitian is excluded instead (`ALLERGEN_NOT_STATED`). Without it, the product stays in the offer and rule P-04 sends the order to the dietitian.

**What the buyer sees.**
- **Candidates and exclusions:** 51 candidates; 41 excluded: 18 × "Declares an excluded allergen" (for example Oatly Oat Drink Organic `460825`, which declares `AW`), 12 × cut-off passed, 6 × not deliverable, 5 × "Allergen not stated" ("Confirmed data only was asked for. The product makes no statement about milk (AM): a dietitian must decide.").
- **The option:** 200 × `464013` Alpro No Sugars Soya drink 1L at €2.01 = **€402.00** (gross €456.27), "478 ST confirmed in stock". It states "free from milk (AM)" and "free from cereals containing gluten (AW)". All five claims are confirmed, and all seven constraint checks are met, including one per allergen and "Confirmed data only".
- No unconfirmed alternative is offered, because confirmed data only was asked for.

**The verdict: `AUTO`.** "The agent may place this order alone: the total of €402.00 before tax is within the €500 limit per order, today's spend would be €402.00 of the €1,500 limit per day of profile allergy-ward, 100% of the requested quantity is covered, and no rule asks for a human." The order becomes `ORDERED`, placed by the agent, with no approval.

**The trail** has six events, ending with `order.placed_by_agent`: "The agent placed order … alone, within its authority under profile allergy-ward: 200 ST of 464013 for €402.00 net. No rule asked for a human."

**Why it matters.** The 20% criterion scores "what the agent can decide alone" as well as what needs sign-off; this is the autonomous path, under the strictest profile (scores on: autonomy and controls, 20%; match to the request, 20%). A school or hospital kitchen with allergen rules is one of the brief's own example scenarios.

**Today's spend.** The verdict depends on what the same buyer already committed today: orders that are ordered or waiting, counted on the date of the data clock. An order counts on the day it was ordered, or, while it waits, the day it was created. In replay that day never ends. So repeating scenario 2 in one order book eventually crosses the €1,500 a day and goes to finance. On the pages every browser has its own book (section 7), and the **Start again** button empties it.

*In the code:* `src/tta/allergens/` (`exclusion.py` holds the table above as a literal, `statements.py` the family rules, `codes.py` the 45 codes); `src/tta/orders/spend.py`.

---

## 5. Scenario 3: the product asked for has no confirmed stock

The hotel's agent sends: **"100 litres of Oddlygood Barista oat drink, product 473609, by Monday"**. This sentence has no recording, so with no Gemini key the page says "The buyer agent could not run …" and uses the example's typed request, saying so.

**Terms.** A **substitute** is another product offered in place of one the buyer named by id. The **substitution rule** is an allergen check that holds for every buyer, with or without exclusions: a substitute must not declare ("contains" or "may contain") an allergen the original does not declare, and must not raise one from "may contain" to "contains".

**What the gateway decides.**
- `473609`'s stock is not confirmed (9,999,999,999), so no confirmed option can supply it, and 100 L are missing. Because the product was named by id, the gateway looks for a substitute.
- **Candidates**, in order: the substitutes Valio itself lists for it (3), then products of the same five-digit category, then the same first four digits, then the same first three, until three can be ordered. Each is re-checked for price and availability.
- **Ranking:** passes the substitution rule; keeps every dietary claim of the original; closer category; listed by Valio; pack size closest; verification status; price difference.
  - **Dietary claims** are a short list of nutritional claims we chose: lactose-free, low-lactose, gluten-free, wheat-free, egg-free, soy-free, vegan, vegetarian.
- Each candidate says in one sentence what the buyer gives up.

**What the buyer sees under "Substitutes, ranked"** (13 shown):
- **1. `471690`** Oddlygood Barista Delight. "✓ Passes the allergen rule · ✕ Cannot be ordered: Cut-off passed."
- **2. `475224`** Fazer Aito Professional Barista Oat drink, 130 ST confirmed. Passes, can be ordered.
- **12. `464320`** Oatly iKaffe and **13. `471881`** Oddlygood Barista 0.5 l, both listed by Valio. They fail: "The substitute adds 1 allergen that the original does not declare: cereals containing gluten (AW, contains). It can never be ordered as a substitute."
- `471881` is named "gluten free" and carries the nutritional claim `FREE_FROM_GLUTEN`, yet declares `AW`. The declaration counts, never the name or the claim.

Across the catalog, 37 of Valio's 249 listed substitute pairs fail this rule.

**The offer.**
- **Option 1, substitute:** 100 × `475224` at €1.74 = **€174.00**. What the buyer gives up: "it does not carry the original's nutritional claim FREE_FROM_PRESERVATIVES; the brand is Fazer Aito, not Oddlygood®; Valio does not list it as a substitute; it costs €0.37 more per L." The "Product asked for" check is `NOT_MET`.
- **Option 2, unconfirmed alternative:** `473609` itself, €137.00, needs the purchasing manager (F-01). It is cheaper but ranks second, because an option holding an unconfirmed quantity is never first.

**The verdict on option 1: `AUTO`.** The three substitute rules all pass:
- F-05 does not fire: the substitute adds no allergen.
- F-08 does not fire: preservative-free is not a dietary claim, so nothing counts as lost.
- P-05 does not fire: the hotel accepts substitutes of the same category.

The agent orders it alone. That holds while the hotel's day stays under €3,000: after scenario 1 in the same book, "today's spend would be €2,754.64 of the €3,000 limit per day". Asked as the ward, P-05 would send any substitute to a human: the ward's profile accepts none without one.

**Why.** "Substitution and other exception handling" and "Allergen-safe substitution under pressure" are in the brief. A substitute that Valio itself lists can still be unsafe for this buyer, and the gateway says so and blocks it (scores on: exceptions, 15%; autonomy and controls, 20%). F-08 exists because the allergen rule alone cannot see a lost claim: regular milk `463149` declares the same allergen as lactose-free milk `469363`, and without F-08 the hotel's agent could order it alone in its place (tested).

*In the code:* `src/tta/offers/substitutes.py` (candidates, ranking, `DIETARY_CLAIMS`), `substitute_wording.py`, `planning.py` (`_substitute_lines`); `src/tta/allergens/substitution.py`; the page's example in `src/tta/ui/examples.py`.

---

## 6. Other exception paths

None of these needs a button; each is a typed request or is shown by tests.

| Situation | What happens | Where it is shown |
|---|---|---|
| **Partial fill.** 1,500 L of lactose-free milk | Confirmed stock is 1,133 L (384 + 51 + 698). Option 1: "3 confirmed products cover 1,133 L of the 1,500 L asked for (367 L missing), for €2,933.09"; quantity check `NOT_MET`. On an empty book, P-01 and P-03 fire: "only 75.5% of the requested quantity is covered, below the 90% minimum". Option 2: 1,500 × `464306`, €1,515.00 | `POST /v1/offers`; tested |
| **Variable weight and lot step.** 30 kg beef chuck (no date) | 30 × `466988` at €16.88/kg = €506.40, marked as a ceiling: "the invoice can be lower, never higher". P-06 sends it to the purchasing manager. The lot step is 3 kg: 31 kg is sold as 33 kg, €557.04. The delivery-date claim is `UNKNOWN` (no date was asked), which holds nothing back | `tests/e2e/test_backup_beef.py`; `docs/DEMO.md`, "Backup" |
| **Price or stock changed, or the option expired, before the order** | 409 `offer-stale` or `offer-expired` with `fresh_offer_id`. In replay nothing changes, so only tests show it | `tests/api/test_problems.py`, `tests/orders/test_decide.py` |
| **Approval too late** | The order becomes `EXPIRED`, with an audit event | `tests/orders/test_expiry.py`, `test_approval_window.py` |
| **An agent tries to approve** | 403, recorded as `authorisation.refused` | `tests/e2e/test_guards.py` |
| **A retry** | Same key, one order | `tests/e2e/test_guards.py` |
| **No quantity in the text** | 422, quantity named as missing | step 2 |
| **A fact a rule needs is missing** (for example, the product file does not say whether a product is sold by weight: 3,068 products) | F-03, to a human | `tests/policy/` |
| **A product with a deposit** | Totals leave deposits out (no deposit has a published price) and say so; P-07 sends it to finance under both profiles | `src/tta/policy/rules.yaml` |

---

## 7. The ways in, the two modes, the deployment

### The surfaces

Four surfaces, all calling the same service code: no rule can hold on one surface and not on another.

- **REST** (plain web requests with JSON) under `/v1`. The interface description in OpenAPI 3.1 (the common open format for web interfaces) is generated from the code at `/openapi.json`, with examples produced by running the scenarios on the capture; `/docs` and `/redoc` show it. `/v1/schemas` gives the JSON Schema of every data shape. `/healthz` gives the mode, the source and the audit head.
- **MCP** (Model Context Protocol, the open protocol through which language-model agents call tools) at `/mcp/`, with the same tokens. Eight tools: `get_authority`, `search_products`, `get_product`, `find_substitutes`, `get_offer`, `place_order`, `get_order`, `get_audit`. **No tool lists or decides an approval**: approvals are REST routes for approver tokens only.
- **The pages** at `/`, `/approvals`, `/orders/{id}` and `/assumptions`. They are for people at the demo and exist only when `TTA_ENV` is `dev` or `demo`. There is no login: the visitor picks the demo agent or approver on the page. Security:
  - a Content-Security-Policy (the browser rule list saying where a page may load code from) allows only the gateway's own files and no inline script;
  - every form carries a CSRF token (a secret that stops another site from submitting the form);
  - all text is escaped.
- **The buyer agent** (`POST /v1/agent/run`). A Gemini loop over four functions: read the authority, get an offer, place an order, read the order.
  - The offer is always built for the request as read.
  - The model may order **only the option ranked 1**, and at most one order per run.
  - A run takes at most 8 steps.
  - The report is assembled from the gateway's own sentences, never the model's words.
  - A run that fails after ordering keeps the order and says what stopped it.

### The sandbox: a private order book per browser

On the pages, each browser gets its own **sandbox**: an empty order book in memory, with its own audit trail. One visitor's orders never count in another's daily spend or appear on another's approvals page. Every page says: "Your own demo order book: nothing you do here is seen by other visitors, and it commits nobody." **Start again** empties this browser's book. At most 300 books are kept; one idle for 2 hours is dropped; a restart empties all.

REST and MCP keep one **shared** order book, in the database file (`TTA_DB_PATH`). The pages do not show it, and it does not see the pages' books.

### Rate limits

All values are ours: the mock publishes none.
- **Demo tokens.** They are public, so a caller is counted as a **visitor**: on the pages a browser (by its own-book cookie); on REST and MCP an address. Each visitor gets per minute: 20 offers and substitute searches, 20 orders and approval decisions, 5 request readings and agent runs.
- **Per address** (demo only): at most 60 / 60 / 15 a minute for all browsers and callers behind it together. A room on one Wi-Fi shares one address, so this is half the whole-app ceiling.
- **The whole app:** 120 / 120 / 30 a minute.
- **New own books:** at most 30 per address in 10 minutes.
- **Tokens from the environment** are counted per token, 60 calls a minute.
- **The forwarded address header** (`X-Forwarded-For`) is believed only when `TTA_TRUSTED_PROXY_HOPS` says a proxy of ours stands in front.
- **Request bodies** over 64 KB are refused.

On the pages, an example button still runs from its typed request when the agent is held back by its limit, and says so.

### Live, replay and the deployment

`TTA_MODE=replay` is the default and is the mode for the demo script (`docs/DEMO.md`): the outcomes of this document are then certain.

The app is **deployed on Modal** (a cloud hosting service) at https://joaocostared--trusted-trade-agents.us-east.modal.run.
- It was deployed from commit `237b37f` at 09:44. The rate limits per browser and per address above were committed after that and are not deployed yet.
- It runs `TTA_MODE=live`, so its numbers come from the live mock and may differ from this document.
- It makes at most 120 live calls, then answers from the capture, labelled.
- It runs one container, which scales to zero when idle. SQLite (a database kept in a single file) works on the container's disk, and a copy is kept on a Modal Volume (Modal's persistent disk).

*In the code:* `src/tta/api/` (`app.py`, `routes.py`, `mcp_surface.py`, `service.py`, `sandbox.py`, `limits.py`, `docs.py`, `wiring.py`), `src/tta/ui/`, `src/tta/agent/runner.py`, `tools.py`; `deploy/modal_app.py`, `docs/DEPLOY.md`.

---

## 8. How the code is cut: packages, ports and contracts

**Terms.**
- A **contract** is a shared data shape that every package uses, written as a Pydantic model (a Python class whose fields are validated). Contracts are frozen (cannot be changed after creation), refuse unknown fields, and keep money and quantities as exact decimals, sent as JSON numbers. They are in `src/tta/contracts/`.
- A **port** is a promise one part makes to the others: a Python `Protocol`, a list of methods without code. Example: the `ValioGateway` port promises `price(ids)` and `availability(ids)`. The live client, the replay of a capture and the fall-back between them all keep that promise, so the offer builder does not know which one it talks to. There are 13 ports, in `src/tta/contracts/ports.py`, all synchronous.

**Why it is cut this way.**
- Many builders worked on separate packages at the same time; each could test its package alone against stand-ins of its neighbours.
- A part can be swapped without touching the rest: live or recorded data, SQLite or another database, Gemini or recorded answers.
- `src/tta/api/wiring.py` is the one place that connects the real parts.

(Scores on: openness, 15%: "well-justified technical choices".)

| Package | Does | Steps |
|---|---|---|
| `contracts/` | Data shapes, typed errors, ports | all |
| `config.py` | Settings from the environment; secrets never printed | 1 |
| `api/` | Web app, identity, limits, errors, REST, MCP, fall-back live → replay, sandboxes | 1, 4, 7 |
| `agent/` | Gemini: reading text, the buyer-agent loop, recordings | 2 |
| `catalog/` | Product file, search, product types, pack size, lot step | 3, 4 |
| `valio/` | Client of the mock API, capture replay, call budget, clocks | 4 |
| `availability/` | The six states, the claim statuses | 5, 8 |
| `allergens/` | GS1 codes and families, exclusion rule, substitution rule | 4 (sc. 2), 5 (sc. 3) |
| `offers/` | Candidates, exclusions, options, checks, substitutes, re-check | 6, 7, 9, 11 |
| `policy/` | Rules, profiles, engine, policy hash | 10 |
| `orders/` | Placing, approving, expiry, idempotency, today's spend | 11, 12 |
| `store/` | SQLite: offers, orders, approvals, keys, append-only audit events | 11, 13 |
| `audit/` | Events, sentences, chain, two views | 13 |
| `ui/` | The pages | 7 |

The three files that hold most of the judgement: `src/tta/policy/rules.yaml`, `src/tta/allergens/exclusion.py`, `src/tta/offers/planning.py`. `docs/ARCHITECTURE.md` has the package map and the ports in more detail.

---

## 9. The rules in one table

The verdict and role of each fixed rule are pinned in code; profile values are per buyer (section 2).

| Rule | In plain words | Verdict, who signs |
|---|---|---|
| **F-01** | A line's quantity is not confirmed by Valio | approval, purchasing manager |
| **F-02** | A line declares an allergen the buyer excludes (the offer already excludes such products; this is a second lock) | block |
| **F-03** | A fact a rule needs is missing: missing data never counts as good data | approval, the role of the missing fact (purchasing manager by default) |
| **F-04** | At order time the option has expired, a cut-off has passed, or price or availability changed | block; a fresh offer is made |
| **F-05** | A substitute adds an allergen the original does not declare, or raises one from may contain to contains | block |
| **F-06** | An agent calls an approval route | refused (403) |
| **F-07** | A line's price is not confirmed, its delivery date is ruled out, or a needed-by date is not verifiably met | approval, purchasing manager |
| **F-08** | A substitute lacks a dietary claim of the product it replaces (for example lactose-free) | approval, purchasing manager |
| **P-00** | The profile does not let the agent order alone at all | approval, purchasing manager |
| **P-01** | The order total is above the limit per order | approval, purchasing manager |
| **P-02** | Today's spend with this order is above the limit per day | approval, finance |
| **P-03** | The option covers less than the minimum share of the quantity | approval, purchasing manager |
| **P-04** | A line does not rule out an excluded allergen (may contain, or not stated under `STRICT`) | approval, dietitian |
| **P-05** | A substitute is outside what the profile accepts (none, Valio-listed, or same category) | approval, purchasing manager |
| **P-06** | A line is sold by variable weight (unless the profile allows it when the total is a ceiling) | approval, purchasing manager |
| **P-07** | A line carries a deposit (unless the profile accepts a total that leaves it out) | approval, finance |

**The agent orders alone only when** no fixed rule fires and every profile limit holds: price and quantity confirmed, allergens settled, the date met if one was given, enough of the quantity covered, no substitute outside the profile, and spend within both limits.

---

## 10. Check it yourself

All commands below were run for this document on a clean copy of the committed code. Run them from the repository root.

**The tests** (about 2½ minutes):
```bash
cd /Users/joaocosta/Pessoal/junction
.venv/bin/python -m pytest -q                 # the whole suite: 2,610 tests
.venv/bin/python -m pytest tests/e2e -q       # the three scenarios, the backup and the guards over HTTP: 16 tests
```
At `3ef0657`, 2,608 pass and 2 fail:
- `tests/ui/test_view.py::test_every_code_has_its_own_words[ExclusionReason]` fails because the new exclusion code `NOT_IN_RECORDING` (committed in the contracts at 10:23) has no page wording yet; the fix in progress adds it (section 12). Up to `e7e1cb2` it passed.
- `tests/catalog/test_loader.py::test_loads_all_products_in_under_three_seconds` is a timing test: it failed while other agents were running their tests on the same machine, and passes when run alone.

The 16 end-to-end tests pass.

**The gateway, on a spare port with a scratch database**, in replay, with no Gemini key (no outside call is made):
```bash
mkdir -p /tmp/tta-check
GEMINI_API_KEY= TTA_ENV=demo TTA_MODE=replay TTA_DB_PATH=/tmp/tta-check/w.sqlite3 \
  .venv/bin/python -m uvicorn --factory tta.api:create_app --port 8790
```
`TTA_ENV=demo` is needed: without it the app runs as `prod` and does not start. The app also reads `.env`. Once the Aiven work of section 12 lands, put `DATABASE_URL=` (empty) in front as well, so a check never writes to the shared database.

**In a second terminal** (each comment says what to expect):
```bash
B=http://127.0.0.1:8790; A="Authorization: Bearer demo-agent-hotel-kitchen"; J="Content-Type: application/json"

curl -s $B/healthz                                   # "status":"ok", "mode":"replay", "source":"replay"
curl -s -o /dev/null -w "%{http_code}\n" $B/v1/authority          # 401: no token
curl -s $B/v1/authority -H "$A" | python3 -m json.tool | head -30   # the profile, its rules, the plain summary

curl -s -X POST $B/v1/requests/parse -H "$A" -H "$J" -d '{"text":"Some milk for Monday"}'
#   422 invalid-request: "Line 1 does not say how much is needed: the quantity is missing. …"

curl -s -X POST $B/v1/offers -H "$A" -H "$J" -d '{"needed_by":"2026-11-16","lines":[{"text":"1,000 litres of lactose-free milk by Monday","product_type":"milk","required_claims":["FREE_FROM_LACTOSE"],"quantity":1000,"unit":"L"}]}' > /tmp/tta-check/offer.json
python3 -c "import json; o=json.load(open('/tmp/tta-check/offer.json')); print(o['offer_id'], [(p['option_id'], p['totals']['net'], p['decision']['verdict'], [f['rule_id'] for f in p['decision']['fired']]) for p in o['options']], len(o['excluded']))"
#   off_… [('opt_1', 2580.64, 'APPROVAL', ['P-01']), ('opt_2', 1010.0, 'APPROVAL', ['F-01', 'P-01'])] 19
```
Then place the order, try to approve it as the agent, approve it as Hanna, and read both views (put the ids from the answers in):
```bash
curl -s -X POST $B/v1/orders -H "$A" -H "$J" -H "Idempotency-Key: check-1" -d '{"offer_id":"<offer_id>","option_id":"opt_1"}'
#   201, "status":"PENDING_APPROVAL", "approval_id":"apr_…"   (the same command again returns the same order)
curl -s -X POST $B/v1/approvals/<approval_id>/decision -H "$A" -H "$J" -d '{"decision":"APPROVE"}'
#   403 not-authorised: "An agent cannot approve or reject an order (F-06). …"
curl -s -X POST $B/v1/approvals/<approval_id>/decision -H "Authorization: Bearer demo-approver-hotel-purchasing" -H "$J" -d '{"decision":"APPROVE","note":"Checked with the kitchen."}'
#   200, "status":"ORDERED", "placed_by":"HUMAN_APPROVAL"
curl -s "$B/v1/audit?order_id=<order_id>&reader=buyer" -H "Authorization: Bearer demo-approver-hotel-purchasing"
curl -s "$B/v1/audit?order_id=<order_id>&reader=supplier" -H "Authorization: Bearer demo-supplier-valio-aimo"
#   both: 10 events (the 9 of step 13 plus the refused attempt), "chain":{"ok":true,…}
#   the supplier's view has no €750, no Hanna and no note
```

**In the browser**, at `http://127.0.0.1:8790/`:
1. **Scenario 1.** Option 1 €2,580.64 to the purchasing manager (P-01); option 2 €1,010.00 with F-01; 19 exclusions with reasons; "Run from answers written by hand, not by a model".
2. **"Decide as Demo approver Hanna"**, approve. The order record opens: "Ordered with human approval".
3. **On the order record**, switch to "Valio Aimo's view (supplier)". No limit, no name, no note; the chain verifies.
4. **Scenario 2.** "Ordered by the agent", €402.00, no approval.
5. **Scenario 3.** `471690` passes but its cut-off has passed; `464320` and `471881` add gluten and can never be ordered; `475224` is ordered.
6. **`/assumptions`** (every assumption, 74 rows) and **`/docs`** (the generated interface). `/docs` loads its viewer from a public CDN (content delivery network), so it needs the network.

If an outcome differs, the browser's book was not empty: press **Start again** and run 1, 2, 3 once each. The full click-by-click script and a 90-second cut are in `docs/DEMO.md`.

---

## 11. Known limits

- **Orders commit nobody.** `ORDERED` is a record in our order book; the mock has no order endpoint. A supplier order message in an open e-procurement format is a next step (`docs/ASSUMPTIONS.md`).
- **One process.** These live in memory, for one process: the order book's lock, the rate limiter, the agent-run log, the pages' books and the cached audit head. Two gateway processes on one database are not protected against each other. The deployment runs one container for that reason.
- **The audit chain** cannot show the last events cut off, or a rewrite from some event to the end, unless another party holds an earlier head; nothing compares heads yet. Nothing is signed. Whoever can write the database file can drop its triggers.
- **SQLite** on the container's disk, with a copy on Modal's Volume, unless `DATABASE_URL` points at the Aiven PostgreSQL service (section 12); then the shared book and audit trail live there.
- **No login on the pages**, so they exist only in `dev` and `demo`.
- **No browser test.** The pages are tested over HTTP. Their small script (send a form once, switch approver) is not run in a browser by the suite.
- **MCP:** no OAuth (tokens are handed out outside the protocol), and the `Origin` header is not checked. `docs/STANDARDS.md` states both as departures, with the fix as a next step.
- **Not built:**
  - delivery-time and sustainability comparison (the reliability and carbon figures are loaded onto each product and shown by `GET /v1/products/{id}`, nothing more);
  - recipe logic, standing-order drift, and a selling agent of Valio's own.
- **Replay never ends its day:** with the clock pinned, today's spend keeps growing in one book, and a waiting order never expires.
- **Fixed today (section 12), kept here so the change is visible:**
  - replay and products outside the capture: they are now excluded as "Not in the recorded copy" (`NOT_IN_RECORDING`), never as "not deliverable";
  - the ingredient list is now read as a statement too: when the declaration says free from and the ingredient list names the allergen or says "may contain" (18 products for milk/gluten, 7 for tree nuts, whole catalog), the product goes to a dietitian with both quoted. `465793` Alpro Barista Almond drink is one of them. Valio is asked which source wins (section 16, `ALMOND-1`);
  - the substitutes route now applies the buyer's own exclusion rule as the offer does;
  - an offer with several lines now says what each line covers, so 100 L of milk plus 10 kg of butter no longer reads "the least covered at 0.0%" for the whole offer;
  - the product type `cream` leaves vegetable-fat blends out.
- **Every limit value is illustrative**, ours, and labelled as ours: profiles, rate limits, portion-pack size, product types.
- **Partner data in the repository.** Valio's four data files are tracked and the repository will be public. The README says they are not under the MIT licence; whether they may stay is a question to Valio (section 16, question 22).

---

## 12. Landed today (Saturday morning)

Each piece was built by its own agent, then checked (its tests, lint, scope) and committed. All of it is in the code described above. The public URL still runs the build from before these commits until the final redeploy.

- **Aiven PostgreSQL** (`S1`, `67f3b00`, 10:34).
  - The shared order book and audit trail can live in a managed PostgreSQL database, behind the same `Store` port.
  - The database itself refuses rewrites of audit events (triggers on UPDATE, DELETE and TRUNCATE), and a supplier view and a read-only supplier role are defined in SQL.
  - If the database cannot be reached at start, the app falls back to SQLite and `/healthz` says so (`7b93821`).
  - The pages' per-browser books stay in memory.
- **Gemini: a photo of an order list, and orders in Finnish and Swedish** (`T18`, `812de0f`, 10:39).
  - Two steps: Gemini transcribes the photo into text, shown to the person; then the same parser and text check read that text.
  - A fourth example button on the first page, for the dietitian's approval: `469512` Elovena oat drink, whose milk the product file says nothing about, under a strict no-milk rule.
  - Gemini answered 503/504 during the live check, so the recordings for Finnish and the photo are hand-built and say so. The live check is a command in `AIMO/build/MORNING.md`.
- **Context.dev evidence** (`S2`, `7abb44e`, connected in `f3286e1`).
  - When an approval goes to the dietitian because an excluded allergen is not stated, the card shows what the manufacturer's page says, under "Found on the manufacturer's page — not Valio data", with the link. It never changes a status or a verdict.
  - Without a Context.dev key it reads stored and recorded answers only (five products) and asks nobody.
- **Rate limits for a room on one Wi-Fi** (`FIX-11`, `289a3c7`). Described in section 7.
- **Fixes from the use-case check** (`AIMO/USE-CASES.md`).
  - `FIX-12a` (`9a1893d`): in replay, a product missing from the capture is excluded as `NOT_IN_RECORDING`, never presented as Valio's statement; the product's own ingredient list counts as an allergen statement (an excluded allergen named there, or "may contain", while the declaration says free from, goes to the dietitian: 18 products for milk/gluten, 7 for tree nuts over the whole catalog); `cream` leaves vegetable-fat blends out.
  - `FIX-12b` (`baa4e08`): coverage named per request line; substitutes judged by the buyer's own exclusion rule; the earliest possible delivery date named when every product is late; the trade-off (allergen findings, what a substitute gives up) shown on the approval card.
- **Your kitchen: the buyer sets what its agent may decide alone** (`FEAT-1`, `b91e135`, 10:58).
  - A page, "Your kitchen" in the menu, where a visitor sets the limits, the minimum fill, the allergen rule and the substitution scope of their own profile, `my-kitchen`, and runs requests as "My kitchen agent".
  - Each setting is shown with the rule it drives (P-00 to P-07) in the kitchen's own values; below them the fixed rules F-01 to F-08, under "Always, whatever you set". A form that names a fixed rule, or a value out of range, is refused with the field named, and nothing changes.
  - The profile is checked exactly as a profile file is, and it lives only in that browser's book; REST and MCP never see it.
  - Known gap: without a working Gemini model, a run as My kitchen agent first says the recorded sentence was made for another profile, then uses the example's typed request. The verdicts are the same.

---

## 13. How it was built and what the reviews changed

This section holds the history the rest of the document leaves out.

**How the build ran.** On the night of 13 to 14 Nov 2026, from 02:36, one orchestrating Claude session ran a loop over `AIMO/build/RUNBOOK.md`:
- **Contracts first.** The orchestrator wrote the contracts and ports first (task T00), so parallel builders could not drift apart. Only the orchestrator changed them, when a hand-back asked.
- **One task file per builder** (`AIMO/build/tasks/`), each naming the paths it owns, the criterion it scores on and the tests to write first.
- **A hand-back per task.** Each builder wrote one on finishing (`AIMO/build/handback/`). `AIMO/build/STATUS.md` is the board and the log. Together they let the run survive a context reset and a two-hour stop.
- **Hand-backs were checked, not trusted.** The orchestrator re-ran each builder's tests, checked it touched only its own paths, and read the files that carry the logic before committing.
- **Four review rounds**, each by three independent reviewers (correctness, security, silent failures). Each was given the code and the specification, never a conclusion to confirm. No critical finding. High findings became fix tasks.

| Task | What it built |
|---|---|
| T00 | Branch, environment, contracts and ports, the three captures |
| T01 to T06 (wave 1, in parallel) | Valio client and replay; catalog; allergens; availability; policy; store and audit trail |
| T07, T08 (wave 2) | Offers; orders and approvals |
| T09 | REST interface, identity, errors |
| T10 and its follow-up | The Gemini parser and buyer agent; the switch to `generateContent` and recordings |
| T11 | MCP |
| T12 | The pages |
| T13 | The scenarios end to end; `docs/DEMO.md` |
| T14 | Modal deployment |
| T15 | README, assumptions, standards, award notes, pitch outline |
| T16 | The review rounds |
| T17 | Final check against the brief: not done yet |
| T18, S1, S2 | Section 12 |
| FIX-1 to FIX-11 | Below |

**What each review round changed.**
- **Round 1** (the six wave-1 packages):
  - the 60-second cache could hide a change from the re-check before an order → the re-check now skips the cache;
  - the rules counted a missing claim as confirmed → FIX-1 and fixed rule F-07;
  - FIX-2 (audit and store: sentences, no rewrite, supplier view), FIX-3 (allergens and catalog: least safe wins, `milk` means milk, 91 → 78 products) and FIX-4 (Valio client: budget lock, clock bound, HTTPS only, bounded answers) came from the same round.
- **From the offers builder, not a review:** regular milk could stand in for lactose-free milk and be ordered alone → FIX-5 and fixed rule F-08.
- **Round 2** (offers, orders), giving FIX-6 and FIX-7:
  - the re-check missed a moved delivery date, sales unit and tax rate;
  - under confirmed-only, dropped products were not listed;
  - two request lines could take one substitute's stock twice;
  - a failed write between order and approval left an order nobody could decide → one transaction (`Store.atomic()`), and one order per offer.
- **Round 3** (the REST interface), giving FIX-8:
  - an offer could mix a live price with recorded stock → one source per lookup;
  - live mode with a bad address started on the capture → it now refuses to start;
  - an unset `TTA_ENV` meant demo tokens → it now means `prod`;
  - one visitor could lock out others and spend the supplier budget → per-visitor limits.
- **Final round** (agent, pages, MCP), giving FIX-9 (agent) and FIX-10 (pages and API):
  - the model's quantity, date and exclusions were not checked against the text → the text check;
  - a reading from a recording was not labelled → labels;
  - a run that failed after ordering could lead to a second order → no lost or double order;
  - one shared order book for all visitors → a sandbox per browser;
  - one visitor could fill the whole app's limits, and the forwarded address could be forged → limits per visitor and kind, the forwarded address believed only when configured;
  - also the deployed budget of 120 live calls.
- **FIX-11** came from a question FIX-10 raised: a room on one Wi-Fi shares one address. Committed at 10:01.

**Outside services.**
- **Valio:** 10 of the 150 approved live calls from the build machine (capture 2, client check 2, scenario live run 6). The live run on 14 Nov at 08:12 gave the same results as the capture for all three scenarios. The deployed app has its own budget of 120, about 4 used by the post-deployment check.
- **Gemini:** a budget of 20 requests for the night. The Interactions endpoint answered 503 and `gemini-3.8-flash` 504, so the build moved to `generateContent` and `gemini-3.6-flash`. The live check passed at 08:17 (scenario 2 read and ordered, €402.00; the no-quantity sentence refused).
- **Modal:** deployed at 09:44 from `237b37f`; all seven post-deployment checks passed.

**What went wrong.** A usage limit stopped three builders from 05:40 to 07:42; their work stayed in the tree and restarted builders finished it. Gemini's newer endpoint failed all night.

---

## 14. Other documents

| Document | What it is | Current? |
|---|---|---|
| `AIMO/CHALLENGE.md` | The brief and the judging criteria, verbatim | Yes |
| `AIMO/SPEC.md` | The contract the code was built to | Mostly; updated where an overnight decision changed it |
| `AIMO/PLAN.md` | Friday's plan, before any code | No: overnight decisions are not in it |
| `docs/ARCHITECTURE.md` | Package map, ports, where each brief requirement lives | Yes |
| `docs/ASSUMPTIONS.md` (page `/assumptions`) | Every assumption, why, what would change it, where in the code | Yes; its rate-limit text is still to be aligned with the per-browser limits |
| `docs/DEMO.md` | The demo click by click, a 90-second cut | Yes, for replay |
| `docs/STANDARDS.md` | Each open standard used, checked against its specification, and the departures | Yes |
| `AIMO/OPEN-QUESTIONS.md`, `AIMO/BOOTH-NOW.md` | The booth copies of sections 16 and 17 | Yes |
| `AIMO/BOOTH-QUESTIONS.md` | The full write-up of every question, by id | Yes |
| `AIMO/build/` | Task files, hand-backs, status log | Yes |

---

## 15. Glossary

- **Approval.** The request for sign-off attached to a waiting order: roles needed, reasons, deadline.
- **Approver, roles.** A human at the buyer; purchasing manager, dietitian or finance, as the buyer's profile lists.
- **Audit event.** One record per step, in a CloudEvents envelope, with a sentence for the buyer and one for Valio.
- **Availability state.** One of six: blocked, not deliverable, out of stock, cut-off passed, quantity not confirmed, confirmed.
- **Buyer, buyer's agent.** The kitchen that buys; the software that orders for it.
- **Buyer profile.** One buyer's settings for what its agent may do alone. Ours are illustrative.
- **Buyer view, supplier view.** The same audit events in the buyer's words, or in Valio's words without the buyer's limits, exclusions, names, notes or text.
- **Candidate.** A product matching what a request line names, before price, stock and rules.
- **Capture.** Recorded answers of the mock API; the default one is Saturday 14 Nov 02:52, 769 products.
- **Catalog.** Valio's product file, 17,546 products, read locally.
- **Claim, status.** One of five statements on an offer line (price, quantity, delivery date, allergens, origin), each confirmed, unknown or ruled out.
- **Constraint check.** One per thing the buyer asked for: met, not met or unverified.
- **Contract.** A shared, frozen data shape in `src/tta/contracts/`.
- **Cut-off.** Valio's `closingTime`: order by it to receive goods on the stated delivery date.
- **Data clock.** The time cut-offs and deadlines are judged against: pinned to the capture in replay; Valio's server time in live mode.
- **Exclusion.** A candidate left out of every option, with a reason code and a sentence.
- **Fixed rule, profile rule.** A rule that holds for every buyer (F-), or one that compares with a buyer's own settings (P-).
- **Gateway.** Our service, `src/tta/`.
- **Hash chain, head.** Each audit event carries the hash of the one before; the head is the count and the last hash.
- **Idempotency key.** A string sent with an order so a retry returns the first order instead of placing a second.
- **Line.** One product of an option, with quantity, price and claims; also, one item of a request ("request line").
- **Live, replay.** Calling the mock API, or answering from a capture.
- **Lot step.** The multiple a quantity must be ordered in.
- **Mock API.** Valio's hackathon service: price and availability, no orders.
- **Nutritional claim.** A product-file label such as `FREE_FROM_LACTOSE`; never an allergen statement.
- **Offer, option.** The answer to a request, with up to three ranked options; an option is one way to fill it.
- **Order, order book.** A commitment to one option, recorded in the gateway's database; `ORDERED` commits nobody at Valio.
- **Policy hash.** Fingerprint of the rules plus the profile in force, stored with each decision.
- **Port.** A promise one part makes to the others (a Python `Protocol`); 13 of them.
- **Request, typed request.** What the buyer wants, as text or in its structured form.
- **Sandbox.** The pages' private, in-memory order book for one browser.
- **Substitute, substitution rule.** A product offered in place of one named by id; it may not add or raise an allergen.
- **Verdict.** `AUTO`, `APPROVAL` or `BLOCK` for one option; the most severe of the rules that fire.
- **Visitor.** Who a rate limit counts when the public demo tokens are used: a browser on the pages, an address on REST and MCP.

---

## 16. Questions for Valio Aimo still without an answer

This is the booth copy, `AIMO/OPEN-QUESTIONS.md`, brought in whole, plus two questions raised after it was written (`DATA-1` and `ALMOND-1`, marked below): 25 questions, each with what to ask, what to show, why it matters and what the gateway does until someone answers. Every example was verified by running it. The id before each title finds the full write-up in `AIMO/BOOTH-QUESTIONS.md`. The questions are about how to read Valio's data and how the challenge is judged. The decisions we want Valio to confirm are in section 17.

### How to use this at the booth
1. Before you walk over, start the app and open the data shell (Setup, below), then press **Start again** on the page.
2. Read the **Ask** line out as written. Show the example only when the mentor asks "where?". Write the answer under the question.
3. The mock's behaviour is the scenario we are meant to handle, not a fault: we are checking how we read it, not reporting bugs. Do not ask about an order endpoint or about very large stock values. Both are settled.

**The two-minute cut:** ask the first five, in order: 0 `SCOPE-1` · 1 `T03-1` · 2 `Q1` · 3 `Q7` · 4 `Q4` (group A).

**Where the numbers come from.**
- *Catalog* means all 17,546 products in the product file.
- *Tonight* means the capture of Sat 14 Nov 02:52, Valio server time: 769 products (categories 104xx and 18720, the scenario products and their listed substitutes).
- *Friday sample* means 1,000 random products, captured Fri 13 Nov 23:00.
- *Friday extras* means 37 ids captured Fri 23:03.

A figure from a capture or the sample is not a catalog fact.

### Setup (once, 10 seconds)

**App** (pages at http://127.0.0.1:8000/):
```sh
cd /Users/joaocosta/Pessoal/junction && GEMINI_API_KEY= TTA_ENV=demo TTA_MODE=replay TTA_DB_PATH=/tmp/tta-booth.sqlite3 .venv/bin/python -m uvicorn --factory tta.api:create_app
```
Replay mode answers from tonight's capture with the clock pinned to Sat 02:52, so the outcomes below are certain. Each browser keeps its own order book. **Start again** empties it. Run the scenarios once each, in the order 1, 2, 3: every order counts in that buyer's day, and a second scenario 1 in the same book adds finance (P-02). REST calls need `-H "Authorization: Bearer demo-agent-hotel-kitchen"`.

**Data shell.** Open a second terminal. Every "Shell:" line below is typed at its `>>>` prompt.
```sh
cd /Users/joaocosta/Pessoal/junction && python3 -I -i -c "
import json, csv
L = lambda path: json.load(open(path))
P = {p['id']: p for p in L('valio_aimo_junction26_product_data.json')}
def cap(name, n=1):
    d = 'fixtures/valio/' + name + '/'
    a = {x['productId']: x for k in range(1, n + 1) for x in L(d + 'availability-%d.json' % k)['products']}
    r = {x['productId']: x for k in range(1, n + 1) for x in L(d + 'price-%d.json' % k)['products']}
    return a, r
A, R = cap('2026-11-14-demo')
F, FR = cap('2026-11-13-sample', 4)
X, XR = cap('2026-11-13-extras')
REL = {r['productId']: r['deliveryReliability'] for r in csv.DictReader(open('valio_aimo_junction26_delivery_reliability.csv'))}
def name(i): return next(n['value'] for n in P[i]['synkkaData']['names'] if n['language'] == 'en')
def g(i, group): return [(v['id'], v.get('unit')) for c in P[i]['synkkaData']['classifications'] if c['name'] == group for v in c['values']]
def f(i):
    p = P[i]
    return dict(unit=p['salesUnit'], units={u['unitId']: u['sizeInBaseUnits'] for u in p.get('units', [])}, lot=p['allowedLotSize'], category=p['category'], variable_weight=p['synkkaData'].get('variableUnit'), deposits=p.get('deposits'))
def av(i, s=None):
    a = (s or A)[i]
    line = (a.get('scheduleLines') or [{}])[0]
    return dict(model=a.get('logisticModel'), cutoff=a.get('closingTime'), amount=line.get('availableAmount'), date=line.get('availableDate'), unit=line.get('salesUnit'))
def pr(i, s=None):
    r = (s or R)[i]
    c, k = r.get('catalogPrice', {}), r.get('comparisonPrice', {})
    return dict(price=c.get('value'), valid=c.get('validFrom', '')[:10] + ' to ' + c.get('validTo', '')[:10], per=(k.get('value'), r.get('comparisonUnit')), error=r.get('error'))
print('Ready. Tonight (Sat 14 Nov 02:52): A, R. Friday sample (23:00): F, FR. Friday extras (23:03): X, XR.')
"
```
- `name(id)` gives the English name.
- `g(id, 'allergen')` gives a classification group.
- `f(id)` gives the file's units.
- `av(id)` gives tonight's availability and `pr(id)` tonight's price; pass `F`/`FR` or `X`/`XR` to read Friday's captures instead.

### 16.A Ask these first

#### 0 · `SCOPE-1` · Which of your example scenarios would you most like to see?
- **Ask:** "Of the scenarios in your brief, which would you most like to see an agent do on top of this: the buyer setting its agent's limits, standing-order drift, recipe to order, or your own selling agent?"
- **Show:** the live demo, https://joaocostared--trusted-trade-agents.us-east.modal.run.
  - Click **Scenario 2 · allergy ward**: the ward's agent orders 200 L of soya drink alone, €402.00.
  - Then click **Scenario 1 · hotel kitchen**: €2,580.64 is above the hotel's €750 limit, so the order goes to the purchasing manager.
  - The link reads the live mock. If it is slow, or a number differs, make the same two clicks on the laptop app, which shows the recorded numbers.
- **If there is time:**
  1. "Do customers set their own ordering limits and approvers today, or does Valio Aimo set them in the account?"
  2. "The mock has no order history: may we define a kitchen's standing order ourselves, or do you have example order patterns?"
  3. "The product file has no field for new or seasonal products, and no recipes: is there one we missed, or should we bring our own small list?" (Catalog: none of the 75 field names contains new, season, launch, campaign, recipe, menu or promo.)
- **Why it matters:** the answer decides what we build in the last hours. Options (a), the buyer's limits, and (b), standing-order drift, both score on autonomy and controls, 20%.
- **Built so far:** the core (lookup, an offer at fixed prices, an order placed within the agent's authority or sent to a named human, and an audit trail for both buyer and Valio), plus two of the six scenarios: allergen-safe substitution for a hospital ward (scenario 2) and a substitute when the product asked for cannot be supplied (scenario 3). The buyer limits live in two profile files, and no page can edit them yet. If Valio does not answer: (a) and (b) first, (c) if time allows, (d) last.

#### 1 · `T03-1` · A "gluten free" oat drink that declares gluten
- **Ask:** "The 0.5 l Oddlygood Barista is named gluten free and carries the gluten-free claim, yet it declares cereals containing gluten, and the 1 l packs do not. Is that expected, or did we get something wrong?"
- **Show:** in the shell, `[(i, name(i), g(i, 'allergen')) for i in ('473609', '471690', '471881')]` returns:
  - `473609` (1 l): `GO` (oats) CONTAINS
  - `471690` (1 L Delight): `GO` CONTAINS
  - `471881` (0,5 l): **`AW` CONTAINS**, `GO` CONTAINS

  Then `g('471881', 'nutritionalClaim')` returns the nutritional claims `FREE_FROM_GLUTEN`, `FREE_FROM_PRESERVATIVES`, `VEGAN`. On the page, open Scenario 3 → "Substitutes, ranked" → no. 13: "✕ Fails the allergen rule … cereals containing gluten (AW, contains). It can never be ordered as a substitute." (Catalog: `471881` is one of the three substitutes Valio lists for `473609`. Tonight it also has no schedule line.)
- **Why it matters:** this is demo scenario 3 (exceptions, 15%). A Valio judge may say the product is gluten free, and our page says it can never be ordered.
- **Built while waiting:** the declaration counts, never the name or the nutritional claim. A substitute may not declare an allergen the original does not (`src/tta/allergens/substitution.py`), so neither `471881` nor `464320` (Oatly iKaffe) can ever be ordered in place of `473609`, for any buyer.

#### 2 · `Q1` · Order cut-offs that have already passed
- **Ask:** "We read closingTime literally: once it has passed, the product cannot arrive on availableDate, so our agent leaves it out and says why. Is that expected, or did we get something wrong?"
- **If there is time:** "Do the cut-offs move forward over the weekend, or will every product be past its cut-off after Sunday 17:00?" (`464119` still showed Thursday 15:00 with delivery on Monday both tonight and in the live check at 08:12.)
- **Show:** in the shell, `av('464119'), av('464306')`:
  - `464119`, Valio skimmed milk 1 l lactose free: Terminal, cut-off **2026-11-12 15:00**, delivery 2026-11-16
  - `464306`, Valio Eila semi skimmed milk drink 1 l lactose free: Stock, cut-off 2026-11-15 17:00, delivery 2026-11-16

  Both are from tonight's capture, with `timeNow` Sat 14 Nov 02:52. On the page, Scenario 1 reads "Excluded: 19 products … 17 × Cut-off passed".
- **Why it matters:** this rule removes 17 of the 30 lactose-free milks from scenario 1 tonight. In the Friday sample, 425 of 1,000 products (42.5%) already had a passed cut-off.
- **Built while waiting:** a product whose cut-off has passed is excluded, with the time named ("Order cut-off passed on Thursday 12 Nov at 15:00, so delivery on Monday 16 Nov cannot be promised"). Replay mode keeps the demo working if every cut-off has passed by judging time.

#### 3 · `Q7` · What limits do real customers set?
- **Ask:** "The mock has no customer model, so we wrote our own limits. What do real customers put on ordering: a euro cap per order, a cap per day, an approved product list, approver roles? One example is enough."
- **Show:** the page `/`, box "Who is asking".
  - Hotel kitchen: €750 per order, €3,000 per day, at least 90% of the quantity covered.
  - Allergy ward: €500 per order, €1,500 per day, 100% covered, excludes `AM` and `AW` (strict), confirmed data only.
  - Each is labelled illustrative. The API specification says: "In this challenge, however, customer number does not affect response so you can pass in whatever."
- **Why it matters:** autonomy and controls, 20%. Every number in our two buyer profiles is ours, and one real example would make them credible.
- **Built while waiting:** two buyer profiles, `src/tta/policy/profiles/hotel-kitchen.yaml` and `allergy-ward.yaml`. They set spend per order and per day, minimum fill, allergen exclusions, substitution scope, variable weight, deposits and approver roles, on top of fixed rules that no profile can switch off.

#### 4 · `Q4` · What an accepted order commits to
- **Ask:** "When Valio Aimo accepts an order today, what is committed at that moment: the price, the quantity, the delivery date?"
- **Show:** in the shell, `pr('464306'), av('464306')`: price €1.01, valid 2026-09-01 to 2026-12-31; delivery 2026-11-16 if ordered by 2026-11-15 17:00; amount 9999999999, which means not known. On the page, Scenario 1 → option 2 reads "✓ Price: confirmed ? Quantity: not confirmed ✓ Delivery date: confirmed".
- **Why it matters:** it decides how we word "ordered" in the pitch, and what an agent may promise (Core 2).
- **Built while waiting:**
  - the price is committed for its validity window;
  - the date is committed only if the order is placed before the cut-off;
  - the quantity is committed only when the stock figure is an ordinary number (`src/tta/availability/claims.py`);
  - an order is a record in our order book, and the page says "It commits nobody."

### 16.B How to read the data

#### 4a · `DATA-1` · The product file and the API: which to trust (added after the booth copy)
- **Ask:** "In production, would an agent get product data through an API too, or a file like this? When the file and the API disagree, which one wins? How often does the file change? And may we show recorded API answers in the demo when the mock is down, labelled as recorded?"
- **Show:** in the shell, `name('461439'), f('461439')['unit'], av('461439')['unit']`: 12 × Risifrutti blueberry rice 175 g; the file says `KI`, tonight's API line says `ST`. Tonight the two differ on 15 of the 624 products with a schedule line. Allergen and ingredient text exist only in the file (and `465793` contradicts itself there, `ALMOND-1`).
- **Why it matters:** the trust protocol and openness, 15%: an agent must know which source each statement comes from.
- **If no answer, we build:** price, quantity and sales unit follow the API; everything about what the product is follows the file; an offer always says whether its API data is live or recorded.

#### 4b · `ALMOND-1` · An almond drink declared free from tree nuts (added after the booth copy; ask this one)
- **Ask:** "Alpro Barista Almond drink declares tree nuts as free from, but its own ingredient list names almond. Which is right, the declaration or the ingredient list? Is this a data error in the hackathon file?"
- **Show:** in the shell, `name('465793'), [c for c, u in g('465793', 'nonAllergen')], P['465793']['synkkaData']['keyIngredients'][0]['value']`:
  - `465793`, Alpro Barista Almond drink 1L: no `allergen` entries; `nonAllergen` (free from) lists `AN`, tree nuts, among 15 codes;
  - its English ingredient list: "Water, ALMOND (2.5%), Sugar, … MAY CONTAIN REMAINS FROM NUTS (NOT PEANUTS). Dairy-free and gluten-free. Low sugar."
- **Why it matters:** the trust protocol and the allergen rule (autonomy and controls, 20%). A buyer who excludes tree nuts must not get almond drink without a person deciding.
- **Whole catalog (FIX-12a):** the same conflict, FREE_FROM declared while the ingredient list names the allergen or says "may contain", appears on 18 products for milk/gluten (`AM`+`AW`) and 7 for tree nuts (`AN`). Examples: `465038` Jymy Organic ice cream Liquorice: `AM` free from, ingredients "WHOLE MILK*, CREAM*, … skimmed MILK POWDER*" · `461634` Jalostaja Liver Paste: `AM` free from, "… MILK powder …" · `465713` Pipers Crisps: `AM` free from, "LACTOSE (MILK)" · `466989` Schlagfix: `AM` free from, "May contain traces of milk" · `470094` Fazer Gluten-Free Runeberg pastry: `AN` free from, "flavour (bitter almond)". Wider ask: "When the declaration and the ingredient list disagree, which one should an agent trust? Are these conflicts expected in the hackathon file, or did we read the groups wrong?"
- **Built now (commit 9a1893d):** neither source wins. The product goes to a dietitian, whose card quotes both. A declared CONTAINS is still a rejection.

#### 4c · `OFFER-1` · How to present an offer: whole-order options or good-better-best per item (added after the booth copy)
- **Ask:** "How should an offer be shown to a buyer's agent: a few ranked whole-order options, or good-better-best per item so the agent can mix? How many options are useful? And is a mark per claim (price, quantity, delivery date, allergens, origin: confirmed, not confirmed, ruled out) on each line what you would want an agent to rely on, or too much?"
- **Show:** on the page, example 1 (two options side by side, five marks per line); then `curl -s -X POST http://127.0.0.1:8001/v1/offers -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Content-Type: application/json" -d '{"needed_by":"2026-11-16","lines":[{"text":"100 litres of lactose-free milk","product_type":"milk","quantity":100,"unit":"L","required_claims":["FREE_FROM_LACTOSE"]},{"text":"10 litres of cream","product_type":"cream","quantity":10,"unit":"L"}]}' | python3 -c "import json,sys;[print(o['rank'],o['title'],o['totals']['net'],o['decision']['verdict'],[l['product_id'] for l in o['lines']]) for o in json.load(sys.stdin)['options']]"` → `1 Best confirmed option 281.1 AUTO ['469363', '463797']` and `2 Alternative: quantity not confirmed 127.3 APPROVAL ['464306', '464249']`.
- **Why it matters:** the 20% match to the request ("the least manual correction") and the brief's "good-better-best" ranking. Today an approver who wants confirmed milk and the cheaper cream cannot pick that; the agent never mixes the two kinds of option.
- **Built until now:** at most three whole-order options (best confirmed, quantity not confirmed, substitute), ranked by constraint fit, then verification status, then price (SPEC §5). Good-better-best per item only on the substitutes route.

#### 5 · `Q2` · Allergen values that are not in the schema
- **Ask:** "We read X99 and UNDECLARED with their GS1 meanings, 'no declarable allergens' and 'not intentionally included'. Is that how your data uses them, or did we get it wrong?"
- **If there is time:** "For an allergy diet, who decides whether 'may contain' is acceptable: you, or the customer's own policy?"
- **Show:** in the shell, `[(i, name(i), g(i, 'allergen')) for i in ('465657', '460556', '460622')]`:
  - `465657`, Aino raspberry chocolate ice cream: `AM` CONTAINS, `AN` **MAY_CONTAIN**
  - `460556`, Turun Sinappia mild mustard 6 kg: `BM` CONTAINS and 13 other codes **UNDECLARED**
  - `460622`, Marli Natur apple juice 1 L: only **`X99` CONTAINS**

  Catalog counts: MAY_CONTAIN on 2,685 products and UNDECLARED on 33. `X99` appears on 121 products in `allergen` (on 120 of them as the only code) and on 74 in `nonAllergen`. The schema documents only CONTAINS and FREE_FROM.
- **Why it matters:** scenario 2 and the trust protocol. It decides whether an agent may take `X99` as safe without a dietitian.
- **Built while waiting:** we use the GS1 meanings. Under STRICT, `X99`, UNDECLARED and no statement all go to a dietitian. Under DECLARED_ONLY they pass, marked unverified. MAY_CONTAIN always goes to a dietitian (`src/tta/allergens/exclusion.py`).

#### 6 · `T03-2` · An allergen family stated "free from" while one of its members is declared
- **Ask:** "Some products state 'free from gluten cereals' and 'contains wheat', or 'free from tree nuts' and 'contains almonds'. We read the first as gluten-free wheat starch and the second as a data error. Is that expected, or did we get something wrong?"
- **Show:** in the shell, `[(i, name(i), g(i, 'allergen'), [c for c, u in g(i, 'nonAllergen') if c in ('AW', 'AN')]) for i in ('460124', '461333')]`:
  - `460124`, Fria fiber-rich loaf "glutenfree": `UW` (wheat) CONTAINS while `AW` is FREE_FROM
  - `461333`, Toblerone: `SA` (almonds) CONTAINS while `AN` is FREE_FROM

  Catalog: 176 products. `AW` accounts for 132 (76 with oats, 35 with wheat CONTAINS), `AN` for 45 and `AM` with lactose for 1; two products count under both `AW` and `AN`. To see the rule in action:
  ```sh
  curl -s -X POST http://127.0.0.1:8000/v1/offers -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Content-Type: application/json" -d '{"lines":[{"text":"10 of 460124 or 461333","product_ids":["460124","461333"],"quantity":10,"unit":"UNIT","exclude_allergens":["AW","AN"],"allergen_strictness":"STRICT"}]}' | python3 -I -c "import json,sys; [print(e['product_id'], e['sentence']) for e in json.load(sys.stdin)['excluded']]"
  ```
  It answers "460124 The product declares that it contains wheat (UW), part of the excluded cereals containing gluten (AW)." and the same for almonds.
- **Why it matters:** scenario 2's strict allergen rule. A buyer who excludes gluten must never get a product that declares wheat.
- **Built while waiting:** both statements are read, and the less safe one counts. When the family is excluded, a member declared CONTAINS rejects the product. A member declared MAY_CONTAIN, or declared oats, goes to a dietitian (`src/tta/allergens/statements.py`).

#### 7 · `Q5` · Products with no allergen data
- **Ask:** "Almost half the catalog has no allergen statement at all. Does no data mean the supplier declared nothing, so an agent must treat it as unknown rather than safe?"
- **Show:** in the shell, `[(i, name(i), g(i, 'allergen'), g(i, 'nonAllergen'), [c for c, u in g(i, 'nutritionalClaim')]) for i in ('463168', '463427')]`:
  - `463168`, Peltolan blue cheese 1.6 kg: no allergen entries at all
  - `463427`, HK cooked ham 6 × 300 g: no allergen entries, yet it carries the nutritional claims `FREE_FROM_GLUTEN` and `FREE_FROM_LACTOSE`

  In the Friday sample both were priced and deliverable on Monday. `sum(1 for i in P if not g(i, 'allergen') and not g(i, 'nonAllergen'))` returns 8110: that is 8,110 of 17,546 products (46.2%), and 4,149 of the 13,577 food products (30.6%; non-food means category prefixes 63, 64, 20 and 90).
- **Why it matters:** scenario 2 and the trust protocol. For a hospital ward, "no data" must never read as "safe".
- **Built while waiting:** no statement means unknown, and under STRICT it goes to a dietitian. When confirmed data only is asked for, the product is excluded as "Allergen not stated". Five products are excluded this way in scenario 2 tonight, for example `474864` Oddlygood almond drink: "makes no statement about milk (AM)".

#### 8 · `T02-1` · Is an `allowedLotSize` of 0.01 "no step"?
- **Ask:** "allowedLotSize is 0.01 on almost every carton and case. We read it as 'no step set' and order whole cases, so 13 cases rather than 12.5 for 250 litres here. Is that expected, or did we get something wrong?"
- **Show:** in the shell, `name('463038'), f('463038'), pr('463038')`. This is the Valio Eila semi skimmed milk drink 10 l novobox, lactose free: its sales unit `KI` holds 2 × 10 l, the lot is 0.01, and the price is €31.31 at €1.57/L, about 20 L per case. So 250 L is 12.5 cases.

  Catalog: the lot is 0.01 on 16,872 of 17,546 products, including 16,476 of the 16,478 not sold by the kilogram. A real step is set on 674 products, 672 of them sold by the kilogram. In the three captures (1,745 ids), no `availableAmount` has a fraction.
- **Why it matters:** match to the request, 20%. The quantity we order must be one Valio can deliver.
- **Built while waiting:** whole units for every sales unit except `KG`. Kilogram products with 0.01 keep 0.01 kg steps, and a real step is used as given. Quantities are rounded up (`src/tta/catalog/lots.py`): with the beef's 3 kg step, 31 kg becomes 33 kg (€557.04).

#### 9 · `T02-2` · What does `comparisonPrice` divide by?
- **Ask:** "We take comparisonPrice to be catalogPrice divided by the content of one sales unit, using the drained weight where there is one, rounded to cents. Is that expected, or did we get something wrong?"
- **Show:** in the shell:
  - `pr('460396'), P['460396']['synkkaData']['unitConversions'][0]['volume']`: Valio skimmed milk 10 l novobox, €8.75 ÷ €0.88/L = 9.943, while the file says 10.0 LTR (tonight).
  - `pr('466382', FR), P['466382']['synkkaData']['unitConversions'][0]['netWeight']`: Filos feta cubes in brine "2kg", €32.33 ÷ €16.17/kg = 2.0, while the file's `netWeight` is 3,390 g (Friday sample).
- **Why it matters:** the pack size turns "1,000 litres" into a number of cases (match to the request, 20%), and no field states it directly.
- **Built while waiting:** we use the file's own size when the two rounded prices are consistent with it (10 L, not 9.943), and the ratio otherwise (`src/tta/catalog/pack.py`). We checked this on 1,321 captured price lines (a sample).

#### 10 · `Q10` · The sales unit differs between the API and the product file
- **Ask:** "On some lines the API's sales unit is not the product file's, and we let the price and the available amount follow the unit on the API line. Is that expected, or did we get something wrong?"
- **Show:** in the shell, `[(i, name(i), f(i)['unit'], f(i)['units'], av(i)['unit'], pr(i)['price'], pr(i)['per']) for i in ('464615', '465244')]`:
  - `464615`, Valio A+ greek yoghurt 1 kg: the file says `KI` (5 tubs), the API says `ST`; €2.92 at €2.92/kg is the price of one tub.
  - `465244`, Arla 5 dl low fat milk: the file says `ST`, the API says `KI` (6 bottles); €6.22 at €2.07/L is the price of a case of six (3 L).

  Tonight 15 of the 624 lines with a schedule line differ. In the Friday sample it was 7 of 797, for example `460657`, Marli tomato juice: the file says `KI` (10 cartons), the API line says `ST` with 112 available, at €2.26 and €2.26/L.
- **Why it matters:** reading the wrong unit multiplies an order by 5 or 10 (match to the request, 20%; exceptions, 15%).
- **Built while waiting:** price and quantity follow the unit on the API line. The file's unit is used only when the API gives none (`src/tta/offers/candidates.py`).

#### 11 · `T07-5` · A listed substitute sold in another sales unit
- **Ask:** "When a substitute you list is sold in another sales unit than the original, we convert the quantity by volume, so 100 single litres become 10 cases of ten. Is that expected, or did we get something wrong?"
- **Show:** in the shell, `[(i, name(i), f(i)['unit'], pr(i)['price'], pr(i)['per'], av(i)['cutoff']) for i in ('473609', '471690')]`:
  - `473609`, Oddlygood Barista 1 l: `ST`, €1.37
  - `471690`, its listed substitute "1 L Delight": `KI`, €15.55 at €1.56/L, cut-off passed Thu 12 Nov 15:00

  On the page, Scenario 3 → substitute no. 1 reads: "one sales unit holds 10 L, not 1 L; it costs €0.19 more per L." Catalog: 75 of Valio's 250 listed pairs have different sales units in the product file.
- **Why it matters:** scenario 3 (exceptions, 15%). Swapping unit for unit would order ten times too much.
- **Built while waiting:** quantities are converted through the pack size and rounded up to the lot step.

#### 12 · `Q8` · Deposits
- **Ask:** "Is a deposit already inside catalogPrice, or charged on top, and if on top, at what value per deposit code?"
- **Show:** in the shell, `f('476204')['deposits'], pr('476204', FR)['price'], [XR[c]['error'] for c in ('1', '2', '3', '4', '147', '171', '9708918')]`.
  - Bundaberg ginger beer 12 × 37.5 cl carries deposit material `1`, 12 ST, and Friday's price for it was €22.09.
  - The price endpoint answered `error: true` for all 7 deposit codes (Friday extras).
  - Catalog: 506 products carry deposits (576 rows, 7 codes), and none of the codes is a product.
- **Why it matters:** a total that leaves out deposits is not the invoice (Core 2, fixed prices).
- **Built while waiting:** totals exclude deposits and say so. In both profiles, a line with a deposit goes to finance (rule P-07).

#### 13 · `Q9` · Variable-weight products
- **Ask:** "If an agent orders 30 kg of a variable-weight product, is the invoice for exactly 30 kg, or for the weight actually delivered?"
- **Show:** in the shell, `name('466988'), f('466988'), pr('466988'), av('466988')`: Well Beef chuck roll, sold in `KG`, lot 3 kg, variable weight, €16.88/kg, 109 kg in stock tonight. Then:
  ```sh
  curl -s -X POST http://127.0.0.1:8000/v1/offers -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Content-Type: application/json" -d '{"lines":[{"text":"30 kg beef chuck","product_type":"beef_chuck","quantity":30,"unit":"KG"}]}' | python3 -I -c "import json,sys; o=json.load(sys.stdin)['options'][0]; print(o['summary']); [print(f['rule_id'], f['sentence']) for f in o['decision']['fired']]"
  ```
  It answers "1 confirmed product covers the 30 kg asked for, for €506.40 before tax. The total is a ceiling: … the invoice can be lower, never higher." and fires P-06. Catalog: 632 variable-weight products, 628 of them sold in `KG`. All 37 in the Friday sample are priced per kg.
- **Why it matters:** it is the demo's backup scenario, and it falls under delivery constraints (exceptions, 15%). The answer decides whether a fixed-price total exists for these lines.
- **Built while waiting:** the total is marked as a ceiling, and the line goes to the purchasing manager (rule P-06).

#### 14 · `Q11` · Category codes
- **Ask:** "Is the 5-digit category code a hierarchy, and which digits are the levels? Can we have the category names?"
- **Show:** in the shell, `[(a, P[a]['category'], b, P[b]['category']) for a, b in (('460027', '460065'), ('461480', '461927'), ('460211', '467530'))]`:
  - tomato NL/BE/ES → tomato Finland: 17401 → 17401
  - Myllyn Paras strawberry-rhubarb pie → berry-mix pie: 41765 → 41763
  - white cabbage → SallaCarte shredded cabbage: 17404 → 17443

  Catalog: of Valio's 250 listed pairs, 230 share all 5 digits, 11 the first 4, 5 the first 3, 2 the first 2 and 2 none.
- **Why it matters:** the "good-better-best" ranking of substitutes (exceptions, 15%) depends on how far a substitute may stray.
- **Built while waiting:** substitute tiers. Valio's listed pairs come first, then the same 5 digits, the same first 4, and the same first 3, labelled weaker (`src/tta/offers/substitutes.py`). We also wrote 30 product types of our own (`src/tta/catalog/product_types.yaml`).

#### 15 · `Q12` · Delivery reliability
- **Ask:** "What exactly does the delivery-reliability number measure, and does a missing value mean there is no delivery history?"
- **Show:** in the shell, `[(i, REL.get(i), av(i)) for i in ('464306', '473463', '463038')]`:
  - `464306`: 1.0, Stock
  - `473463`, Atria beef tenderloin: 0.332, 0 available
  - `463038`, Valio Eila 10 l: no row, Terminal

  Catalog: 4,425 of 17,546 products have a value (25.2%). Of those, 56.3% are exactly 1.0 and 12 are 0.0.
- **Why it matters:** delivery-time comparison (an optional direction) and the ranking: a missing value must never rank above a good one.
- **Built while waiting:** the raw value is loaded onto each product. `GET /v1/products/473463` shows `"delivery_reliability": 0.332`. A product with no row stays empty and is never imputed. The value does not change the ranking yet.

### 16.C How the mock and the judging work

#### 16 · `Q6` · Stock that covers only part of a line
- **Ask:** "When stock covers only part of an order line, what happens today: a partial delivery, a substitute, or the line is dropped?"
- **Show:** in the shell, `av('469363'), av('461360')`: Arla lactose-free milk drink 1 L has 384 in stock, and Alpro almond drink has 50. The request carries no quantity and the answer has at most one schedule line, so nothing says when the rest could come. Then:
  ```sh
  curl -s -X POST http://127.0.0.1:8000/v1/offers -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Content-Type: application/json" -d '{"needed_by":"2026-11-16","lines":[{"text":"1,500 litres of lactose-free milk by Monday","product_type":"milk","required_claims":["FREE_FROM_LACTOSE"],"quantity":1500,"unit":"L"}]}' | python3 -I -c "import json,sys; o=json.load(sys.stdin)['options'][0]; print(o['summary']); [print(f['rule_id'], f['sentence']) for f in o['decision']['fired']]"
  ```
  It answers "3 confirmed products cover 1,133 L of the 1,500 L asked for (367 L missing), for €2,933.09 before tax." and "P-03 Only 75.5% of the requested quantity is covered, below the 90% minimum."
- **Why it matters:** the exceptions criterion (15%) names partial availability.
- **Built while waiting:** the rest is filled from other confirmed products and shown as one combined option. Below the profile's minimum fill, the order goes to a human (rule P-03; `src/tta/offers/combining.py`).

#### 17 · `Q13` · Call volume during judging
- **Ask:** "Is our call volume fine during judging? Each offer makes two calls, at most six offers a minute reach your API, and the deployed link makes at most 120 calls in all."
- **Show:** in the shell, `L('fixtures/valio/2026-11-14-demo/manifest.json')['product_count'], L('fixtures/valio/2026-11-14-demo/manifest.json')['calls']` returns 769 products in 2 calls (tonight's capture). The live check at 08:12 made 6 calls for the three scenarios. On Friday, 34 requests in 5 minutes drew no 429 and no rate-limit header.
- **Why it matters:** the end-to-end demo (30%) must not lose its supplier in the middle of judging.
- **Built while waiting:**
  - we narrow products down locally before calling;
  - answers are cached for 60 seconds;
  - at most 6 offers a minute reach the live API (2 per address);
  - the deployed link has a budget of 120 calls;
  - the recorded capture answers, labelled replay, when the budget runs low or the mock does not answer (`src/tta/api/fallback.py`, `deploy/modal_app.py`).

#### 18 · `T01-1` · Must an agent send a named User-Agent?
- **Ask:** "A call with a library's default User-Agent got 403, and the same key with a named one got 200. Is that expected, and is a named User-Agent the rule an external agent should follow?"
- **Show:** `grep -n "USER_AGENT =" src/tta/valio/client.py` returns `37:USER_AGENT = "tta-gateway/0.1"`. The 403/200 pair was seen on `GET /api/ping` on Sat 14 Nov 02:40 (`AIMO/FINDINGS.md` §1). It is not re-run here.
- **Why it matters:** openness, 15%. Being "openly readable by autonomous agents" should not depend on an undocumented header.
- **Built while waiting:** the client always sends `User-Agent: tta-gateway/0.1` and `Accept: application/json`. A 403 is reported with that hint and is not retried.

#### 19 · Ask any 1 · How and when do you judge?
- **Ask:** "How and when do you judge: at our table, from the video, or on the deployed link? And will the mock API stay up, unchanged, until then?"
- **Show:** `curl -s http://127.0.0.1:8000/healthz` returns `"mode": "replay"` and `"replay_capture": "2026-11-14-demo"`. Every page carries the yellow label "Replay: recorded Valio Aimo data, clock pinned to the recording".
- **Why it matters:** the end-to-end demo, 30%. The answer decides whether we demo live or from the recording.
- **Built while waiting:** replay mode answers from tonight's capture with the clock pinned to Sat 02:52. The deployed link runs live and falls back to the capture, labelled, when the mock fails or the budget runs low.

#### 20 · Ask any 2 · Must exception cases run live?
- **Ask:** "Do exception cases have to run in the live demo, or does a documented, tested rule count?"
- **Show:** on the page, Scenario 1 reads "Excluded: 19 products, each with its reason: 17 × Cut-off passed, 1 × Portion pack, 1 × Not deliverable." `ls tests/e2e` lists one end-to-end test file per scenario, plus the beef backup and the guards.
- **Why it matters:** exceptions, 15%. The answer decides whether the partial fill at 1,500 L has to be on stage.
- **Built while waiting:** passed cut-offs, unknown stock, products that cannot be delivered, allergen exclusions and substitutes all run in the three scenarios. The partial fill, variable weight and an agent trying to approve its own order run as typed requests and are tested in `tests/e2e/`.

#### 21 · Ask any 3 · Webshop test accounts
- **Ask:** "The brief mentions webshop test accounts. Are they available?"
- **Show:** `grep -n "Webshop test accounts" AIMO/CHALLENGE.md` finds line 60: "Webshop test accounts to be shared separately."
- **Why it matters:** an account could ground our buyer profiles (question 3) in a real customer setup (autonomy and controls, 20%).
- **Built while waiting:** nothing; we have not used them.

#### 22 · Ask any 4 · May your data stay in a public MIT repository?
- **Ask:** "The hackathon requires a public MIT repository. May your datasets and a few recorded answers of the mock API stay in it, or should we keep them out?"
- **Show:** `git ls-files 'valio_aimo_*' fixtures/valio | wc -l` returns 22: 4 datasets and 18 recorded API files. The README says: "The Valio Aimo datasets and recorded API answers are not ours and are not covered by it."
- **Why it matters:** it is a submission rule, so there is a disqualification risk, and it bears on openness, 15%. Our tests read the recorded answers.
- **Built while waiting:** the README leaves the data out of the MIT licence. We must decide before the repository goes public.

#### 23 · S2-1 · `469512` states nothing about milk; its maker's page says milk-free
- **Ask:** "`469512` Elovena barista oat drink states nothing about milk in your file, but Raisio's own food-service page says *Maidoton*, milk-free. Is the statement missing only in the hackathon file, or at the source too?"
- **Show:** `python3 -c "import json;d={p['id']:p for p in json.load(open('valio_aimo_junction26_product_data.json',encoding='utf-8-sig'))};s=d['469512']['synkkaData'];print({c['name']:[v['id']+' '+v.get('unit','') for v in c['values']] for c in s['classifications'] if c['name'] in ('allergen','nonAllergen')});e=json.load(open('fixtures/evidence/469512.json'))['response']['json_content'];print(e['source_url'],e['free_from'])"` → `{'allergen': ['GO CONTAINS'], 'nonAllergen': []}` and the Raisio page with `['Gluteeniton', 'Laktoositon', 'Maidoton', 'Kananmunaton']`.
- **Why it matters:** 46% of the catalog has no allergen statement; this is the case the Context.dev evidence is for (autonomy and controls, 20%).
- **Built while waiting:** the claim stays "not stated", the order goes to a dietitian, and the approval card shows the maker's page under "not Valio data" (built, not yet wired into the running app).

#### 24 · S2-2 · `474864`: almond drink in English, soya drink in Finnish
- **Ask:** "`474864`'s English name says almond drink, the Finnish and Swedish names say soya drink, and it declares soya. Which is right?"
- **Show:** `python3 -c "import json;d={p['id']:p for p in json.load(open('valio_aimo_junction26_product_data.json',encoding='utf-8-sig'))};s=d['474864']['synkkaData'];print({n['language']:n['value'] for n in s['names']});print([v['id']+' '+v.get('unit','') for c in s['classifications'] if c['name']=='allergen' for v in c['values']])"` → `{'en': 'Oddlygood® almond drink 1 l no sugars UHT', 'fi': 'Oddlygood® soijajuoma 1 l no sugars UHT', …}` and `['AY CONTAINS']`.
- **Why it matters:** a buyer searching in English gets a soya drink as an almond drink (match to the request, 20%).
- **Built while waiting:** the allergen declaration counts; the almond-drink page found on the web was dropped as not matching.

### Numbers corrected or added against `BOOTH-QUESTIONS.md` and the earlier walkthrough

- **T03-2:** 176 products, not 178. The 178 adds the per-family counts (`AW` 132 + `AN` 45 + `AM` 1), but two Marabou products (`466691`, `467090`) count under both `AW` and `AN`.
- **Q1** (the earlier walkthrough said "about half the catalog at any time"): it is a sample figure. 425 of the Friday sample's 1,000 products (42.5%) had a passed cut-off, which is 53% of the 797 with a schedule line. FINDINGS' 42.3% counts 423, because it gives the blocked line and lines with amount 0 states of their own.
- **Q8:** the €22.09 for `476204` comes from Friday's price call, not from the product file, which has no prices.
- **Q10:** Friday's 7 of 797 holds. Tonight's capture adds 15 of 624, in both directions, so the examples now use tonight's `464615` and `465244`.
- **Q11:** the 20 pairs that leave the 5-digit category are 11 sharing 4 digits, 5 sharing 3, 2 sharing 2 and 2 sharing none. The booth file named only the first two groups.
- **T02-2:** the "186 of 190" and "481 of 513" fit counts are left out. They were not recomputed, and `src/tta/catalog/sizes.py` gives other figures (188 of 190 and 486 of 513, within 3%). Only the 1,321 lines were recounted.
- **Setup** (this copy only): `AIMO/OPEN-QUESTIONS.md` says to run scenario 3 last because its €174 "adds finance to scenario 1". Run as 3 then 1 in one empty book, scenario 1 still needs only the purchasing manager (€174 + €2,580.64 = €2,754.64, under €3,000). Finance is added by a second scenario 1 in the same book.
- **Not verifiable from saved files, kept as reported:** six customer strings giving identical prices (Q7, Friday) and the 403/200 User-Agent pair (T01-1, 02:40).

---

## 17. Decisions we took on our own — to confirm with Valio Aimo

Each line says what we decided, why, and the one place to change it. Section 17.A holds the 14 decisions about Valio's data or business. They need Valio's confirmation, and are worded as questions to read out at the booth (the booth copy is part B of `AIMO/BOOTH-NOW.md`). Section 17.B holds the team's own choices about how the gateway works. None of them needs Valio, but the team should agree with each.

### 17.A To confirm with Valio Aimo

| # | We decided … is that right? | Why | To change |
|---|---|---|---|
| V1 | **What the agent may order alone:** only when price and quantity are confirmed, allergens are settled, the delivery date is met if the buyer gave one, the quantity is covered, the spend is within the buyer's limits, and no substitute is outside what the buyer allows. Anything else goes to a named human. Is that the right line? | Without a fixed line on which claims hold an order back, a request with no date, or a product with no stated origin, could never be ordered alone. Origin is shown but never holds an order back. Fixed rule F-07 makes the rules read the price and delivery-date claims; before it they ignored both | `AIMO/SPEC.md` §4; `GATING_CLAIMS` in `src/tta/offers/candidates.py`; F-07 in `src/tta/policy/rules.yaml` |
| V2 | **Very large stock (999,999 or more, Terminal or Stock) means the quantity is not known:** always to a human, never the suggestion. Valio told us this in person on 14 Nov; does it still hold? | An agent must never commit a buyer to stock nobody confirmed | `QUANTITY_NOT_CONFIRMED_THRESHOLD` in `src/tta/contracts/availability.py`; F-01 in `rules.yaml`; ranking in `src/tta/offers/options.py` |
| V3 | **A cut-off exactly at "now" counts as passed.** | "Order by closingTime at the latest". The code also excludes a product whose cut-off has passed from every request, dated or not, while `AIMO/SPEC.md` §4 says "for a dated request" | `src/tta/availability/states.py`; `_STATE_REASONS` in `src/tta/offers/candidates.py` |
| V4 | **A nutritional claim is never an allergen statement:** lactose-free milk still "contains milk". | All 30 lactose-free milks of scenario 1 declare milk (`AM`) | `src/tta/allergens/exclusion.py` (claims are never an input); the claim check sentence in `src/tta/offers/checks.py` |
| V5 | **"Milk" leaves out sour milk, the milk coffee drink and soy yoghurt, but keeps milks for coffee.** `463380` Arla Cafè milk supplies 565 of the 1,000 litres in the demo. Would a buyer asking for milk accept coffee milk? | Without coffee milks, option 1 of scenario 1 is a partial fill | `exclude_terms` of `milk` in `src/tta/catalog/product_types.yaml` |
| V6 | **A substitute may never add an allergen the original does not declare, or raise "may contain" to "contains"**: blocked for every buyer. | A buyer who chose the original chose its allergens. 37 of Valio's 249 listed substitute pairs fail this (catalog) | `src/tta/allergens/substitution.py`; F-05 in `rules.yaml` |
| V7 | **A substitute that drops a dietary claim (lactose-free → regular, gluten-free → regular) always goes to a human.** We count as dietary: lactose-free, low-lactose, gluten-free, wheat-free, egg-free, soy-free, vegan, vegetarian. Others (no preservatives, no added sugar …) are only mentioned. Right list? | Regular milk declares the same allergen as lactose-free milk, so without this the hotel's agent could order it alone. Counting every claim made a rice drink the best stand-in for a gluten-free oat drink | `DIETARY_CLAIMS` in `src/tta/offers/substitutes.py`; F-08 in `rules.yaml` |
| V8 | **Oats under a "no gluten" request go to a dietitian; gluten-free wheat starch is rejected.** | Oats can be gluten-free or not. On conflicting statements the least safe one counts, and a declared wheat is a declared gluten cereal | `src/tta/allergens/statements.py` |
| V9 | **A product carrying only `X99` goes to a dietitian for a strict buyer** (under `DECLARED_ONLY` it passes, shown as unverified). | `X99` is a general statement, never one about a single allergen | `src/tta/allergens/statements.py`, `exclusion.py` |
| V10 | **Single-serve packs (an inner unit of 5 cl or 50 g or less) are left out of a bulk request.** `463203`, 100 × 2 cl milk, is excluded from "1,000 litres of milk". | A kitchen ordering 1,000 litres does not want 50,000 portions | `PORTION_MAX_LITRES`, `PORTION_MAX_KG` in `src/tta/catalog/pack.py` |
| V11 | **"By Monday" means the first Monday after today** (Helsinki date, by the data clock). The live client sends today's date as `requestedDate` (the mock ignores it) and the gateway compares `availableDate` itself. | One calendar rule, the same for the parser and for every recorded reading | `src/tta/agent/days.py`; `src/tta/valio/client.py` |
| V12 | **Before an order we look again.** A change of price, tax rate, price validity, availability state, cut-off or sales unit refuses the order and builds a fresh offer, and so do a later delivery date or stock that no longer covers. Stock that moved but still covers the order is not a change, and neither is an earlier delivery. | An order rests on the statements of its offer; stock moves with every other buyer's order | `src/tta/offers/revalidation.py`; F-04 in `rules.yaml` |
| V13 | **What Valio sees in its view of the audit trail:** what was asked of your data, what was offered and ordered, the figures each order relied on, the agent's identity, and whether it acted alone or with a human, but not the buyer's limits, allergen exclusions, approver names or notes. Is that what you would want to see? | The brief asks for a log "for both buyer and Valio Aimo"; the buyer's limits and people are the buyer's business | `src/tta/audit/readers.py`, `supplier_sentences.py` |
| V14 | **"Ordered" means recorded in our order book; it commits nobody**, because the mock has no order endpoint. Is that how you want it described? | Nothing is sent to Valio, and no page may suggest otherwise | `src/tta/orders/wording.py`; the line on every page (`src/tta/ui/`) |

### 17.B The team's own choices

| # | Decision | Why | To change |
|---|---|---|---|
| T1 | Audit events carry the real time, not the data clock | Otherwise every demo event would read 02:52 | `UtcClock` in `src/tta/api/wiring.py` |
| T2 | Each profile names a demo approver for every role | An approval needing a role nobody holds could never complete | `approver_roles` in `src/tta/policy/profiles/*.yaml` |
| T3 | One waiting or ordered order per offer | The same option could be bought twice under two keys | `_require_no_order_yet` in `src/tta/orders/service.py` |
| T4 | An approver who picks another option starts the approval again on it | An earlier signature was given for something else | `approved` in `src/tta/orders/records.py` |
| T5 | Today's spend counts an order on the day it was ordered (or, while it waits, the day it was created) | An order approved the next day would count on the wrong day | `src/tta/orders/spend.py` |
| T6 | The ward's profile sends variable weight and deposits to a human | The specification set neither for the ward; this is the cautious value | `src/tta/policy/profiles/allergy-ward.yaml` |
| T7 | An unset `TTA_ENV` means `prod`, which loads no demo token | A deployment that lost the variable would otherwise accept the public tokens | `src/tta/config.py` |
| T8 | Gemini through `generateContent`, model `gemini-3.6-flash` | The Interactions endpoint answered 503 all night; `gemini-3.8-flash` answered 504; 3.6 answered | `DEFAULT_MODEL` in `src/tta/agent/gemini.py`, or the setting `TTA_GEMINI_MODEL` |
| T9 | When Gemini cannot be reached, a recorded sentence is answered from its recording, labelled | The demo must not depend on a slow outside service | `src/tta/agent/fallback.py` |
| T10 | The agent may order only the top-ranked option | The specification said "pick the top option" only in the model's instructions; a product name in the data could have steered it | `src/tta/agent/tools.py` |
| T11 | The model's reading is checked against the text | The model must not decide a quantity, a date or an exclusion | `src/tta/agent/textcheck.py` |
| T12 | Each browser of the pages gets its own order book | With one shared book, scenario 2 ordered alone three times and then went to finance for everybody | `src/tta/api/sandbox.py`, `src/tta/ui/` |
| T13 | Rate limits per visitor and per kind of call, a cap per address, and the forwarded address believed only when configured | One visitor could fill the whole app's limits or invent new visitor identities, and a room on one Wi-Fi must not share one visitor's allowance | `src/tta/api/limits.py`, `TTA_TRUSTED_PROXY_HOPS` |
| T14 | At most 6 live looks at Valio a minute for the whole app, 2 per address (Valio is asked about the volume in question 17, `Q13`) | One visitor could spend the call budget for everybody | `src/tta/api/limits.py`, `src/tta/api/fallback.py` |
| T15 | The deployed app may make at most 120 live calls | 150 were approved for the night and 10 were used before deploying | `DEPLOYED_CALL_BUDGET` in `deploy/modal_app.py` |
| T16 | The Aiven and Context.dev pieces were not built overnight | The run's rule allowed them only if the scenarios were green before 06:30, and a usage limit stopped the agents from 05:40 to 07:42. On Saturday morning a human chose to build them (section 12) | `AIMO/build/tasks/S1-aiven-postgres.md`, `S2-contextdev-evidence.md` |
| T17 | Scenario 3 on the page is asked by the hotel, and ends with the agent ordering `475224` alone | The hotel accepts substitutes of the same category; asked by the ward, a human decides | `agent_id` of scenario 3 in `src/tta/ui/examples.py` |
