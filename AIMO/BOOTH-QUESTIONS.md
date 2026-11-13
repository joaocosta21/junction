# Valio Aimo booth — questions with context

For each: **what we found** → **why it matters** → **what changes depending on the answer**.
Mentors: Tommi Nurmi-Aro, Ville Takanen, Riku Tapper (technical / data governance) · Hanna Forsström, Pirjo Kaartinen (commercial) · Minni Ruhtinas (online sales).

**If you only get two minutes: Q1, Q3, Q6.**

---

## Q1 — Is the order contract ours to define? ⭐ HIGHEST VALUE

**What we found:** The mock API has exactly six operations: `ping`, `price`, `availability`, and three file downloads. **There is no order, basket, quote or confirmation endpoint**, and nothing in the OpenAPI spec hints at one. We verified this (404 on `/order`, `/orders`, `/quote`).

**Why it matters:** The rubric's largest block — 30% — is *"runs through a full request → lookup → **order/approval** flow in the mocked environment."* If there is no order endpoint, "the mocked environment" must include something we build. How much we build changes by hours:
- **(a)** A real mock order service — documented schema, persistence, order IDs, state transitions. Our agent calls it over HTTP like it calls theirs.
- **(b)** A defined-and-stubbed interface — schema and semantics documented, minimal implementation.
- **(c)** The agent "commits" internally with no service boundary; approval is just app state.

**Our assumption:** (a), and that defining the contract **is** the deliverable — their brief says *"prototype the interface and operating model that would let an external purchasing agent interact with Valio Aimo's systems."* We're proposing the endpoint they don't have yet, not consuming theirs.

**Sub-questions worth asking:**
- Should our order request **extend your existing `customer` / `requestedDate` / `products` shape**, or is a new vocabulary fine? (We plan to extend it — reusing your field names is a cheap, visible production-mindedness signal.)
- **Line granularity** — one order per delivery date, or can one order span dates?
- **Idempotency** — do you want a client-supplied idempotency key? (Standard for B2B ordering; prevents double-ordering on agent retry.)
- **Does a confirmation promise quantity, or only price?** This is the crux: you say orders are based on *"fixed prices rather than a negotiated quote,"* so is price locked while quantity remains subject to actual stock?
- **Would you accept an MCP tool surface as the submitted "interface,"** or do you want HTTP + OpenAPI as primary? (Your scope note says the eventual transport is out of scope, so we plan HTTP+OpenAPI primary with MCP as a second transport over the same types.)

**What changes:** If (b) or (c), we save ~3h and spend it on guardrails and robustness. If they have an internal schema, converging on it is worth far more than inventing ours.

---

## Q2 — Will you judge date/lead-time logic at all?

**What we found:** **Both APIs ignore `requestedDate` completely.** We queried 2026-11-13, 2026-11-14 and 2026-12-25 — byte-identical responses, `availableDate` pinned to **2026-11-16** for every product, same `closingTime`, same amounts. `/price` returns identical prices for 2025-06-01, 2026-11-16 and 2027-06-01 (only `pricingDate` echoes back).

**Why it matters:** Their own canonical example is *"I need 1,000 litres of lactose-free milk **by Monday**."* But "by Monday" cannot be tested as a real constraint — there is one frozen delivery date. The brief's resources promise *"delivery lead times"*; the mock doesn't implement them.

**What changes:**
- **If they'll judge it:** we need the intended lead-time rules (per temperature class? per logistic model? per vendor?) because they cannot be reverse-engineered from a mock that returns one date.
- **If they won't:** we build the date plumbing correctly (so it's production-credible) but demo against 2026-11-16 and stop investing. Saves hours of hunting for a model that isn't there.

---

## Q3 — Which `closingTime` semantics should we honour? ⭐

**What we found:** Server time was 2026-11-13T21:33+02:00.
- Every **Terminal** product reports `closingTime` **2026-11-12T15:00** — **over a day in the past** — while simultaneously reporting itself available on 2026-11-16.
- **Stock** products report 2026-11-15T17:00 (still future).

`closingTime` is documented as *"the order cut-off time — order by closingTime at the latest to receive goods on availableDate."*

**Why it matters:** This is a direct contradiction in their own data, and it decides whether half the assortment is orderable in our demo:
- An agent that **respects** the cut-off rejects **every Terminal product**.
- An agent that **ignores** it has no cut-off logic at all — and cut-off handling is exactly the kind of exception the 15% robustness criterion rewards.

**Our plan:** detect the contradiction, degrade the commitment window to the price validity window, log the reason, and surface it as a data-quality finding. We think a system that catches its supplier contradicting itself is the strongest possible answer to their *"trust protocol"* problem statement — but we want to know if they see the stale value as a bug to ignore or behaviour to model.

**What changes:** If it's an artefact → ignore it, keep the detector as a one-line trust finding. If they want *"cut-off passed → next delivery slot"* modelled → that's real logic worth ~1h and a demo beat.

---

## Q4 — Any weighting beyond the published rubric? Does a spec artefact score?

**What we found:** The rubric is published (30% demo / 20% problem-solving / 20% autonomy / 15% robustness / 15% openness). But the "Problems we'd love to see tackled" section lists four areas — trust protocol, guardrails model, response logic, audit trail — with no weights, and they read as more important than their placement suggests.

**Also: the brief and rubric contradict each other.** The brief says substitution handling *"isn't scored as core"* (pointing at last year's Zero-Fail Logistics challenge), but the rubric allocates **15% to "robustness to exception situations: partial availability, **substitutions** and delivery constraints."**

**Why it matters:** We're planning to build for the rubric and treat substitution as scored. If the brief is right, that's 15% of our effort misdirected.

**Ask:**
- Which applies on substitution — the brief or the rubric?
- Are the four "problems we'd love tackled" weighted inside the published criteria, or separate?
- **Does a specification artefact score on its own** (typed schema + documented authority model), or do you need everything demonstrated in a running demo? The 15% openness criterion says *"open documented standards… well-justified technical choices… credible view of next development steps"* — which sounds like a document, but *"slides alone are not sufficient"* appears elsewhere.

---

## Q5 — Is the `category` code hierarchical? (and a code→name mapping)

**What we found:** 349 distinct categories, **all exactly 5 digits**, median 32 products, p90 117, max 443, only 4 singletons. The schema says explicitly: *"Category names are not part of this data set."* We inferred a few by reading Finnish product names — 10400 = drinking milk, 10401 = liquid milk products/creams, 41820 = ice cream, 52201 = chocolate, 22413 = RTD coffee drinks.

Also relevant: of the 250 explicit `substitutions` pairs in the data, **230 (92%) stay inside the same category** — strong evidence that same-category is how Valio themselves model substitutability.

**Why it matters — the hierarchy question is the valuable half:** If 10400 and 10401 are siblings under a 104xx parent, we can compute **category distance** and rank substitutes by "how far from what you asked for." That turns our substitution engine from a flat same-category filter into a defensible good-better-best ranking — which is literally their *"response logic: substitution ranking (good-better-best)"* problem statement.

**What changes:** Hierarchical → category-distance ranking, ~1h, significantly better substitution output. Flat → we fall back to brand + pack size + nutritional claim, which is weaker. A name mapping is a nice-to-have (makes the demo readable); the hierarchy is the one that changes the algorithm.

---

## Q6 — `MAY_CONTAIN`, `X99`, and silence in an allergen decision ⭐

**What we found, and this is the most consequential thing in the dataset:**
- Allergen data lives in `synkkaData.classifications` as `allergen` / `nonAllergen` ENUM groups with GS1-style two-letter codes (AM 3,160 · AW 2,794 · UW 2,550 · AE 1,317 …).
- **The schema documents only two `unit` values: `CONTAINS` and `FREE_FROM`. But a third, `MAY_CONTAIN`, is pervasive and undocumented** (AN 1,225 · AY 954 · AM 728 · SA 727 …). **Any filter written against the two documented values silently treats "may contain traces" as safe.**
- **Coverage is much thinner than it first appears.** The classification groups exist on 99.9% of products, but are *non-empty* on far fewer: `allergen` **41.1%**, `nonAllergen` **29.2%**. **So ~59% of the catalog carries no allergen statement at all.**
- **`X99`** appears 121× as CONTAINS and 74× as FREE_FROM — it means "other/unspecified," which cannot ground a safety claim either way.

**Why it matters:** Their own scenario is *"allergen-safe substitution under pressure: in a school or hospital kitchen, a substitution must still satisfy strict allergen and nutrition rules."* With this data:
- We can only **certify** a swap on the ~29% with an explicit `FREE_FROM` assertion.
- On the silent 59%, **absence of `CONTAINS` is not evidence of absence.**

This is a **policy question only they can answer**, and it's undocumented.

**Ask:**
- Should the agent treat `MAY_CONTAIN` as a hard fail for a constrained allergen, or escalate to a human?
- Is **silence ever permissible** for a school or hospital kitchen, or must the agent refuse to commit without an explicit free-from assertion?
- What does `X99` mean operationally — and should it block a safety claim?
- Is the code list GS1 AllergenTypeCode? Is there a lookup table, or do we map AE / BM / AM ourselves?

**What changes:** This determines whether our strictest policy rule is DENY or ESCALATE, and it is the centre of one of our three demo scenarios. Their answer is also a genuine product insight for them — we can show which items they could make orderable-by-agent by filling in one field.

---

## Q7 — Deposit pricing: in the order total, or out of scope?

**What we found:** 506 products carry deposits (576 deposit lines, all `unit: ST`), but the **7 distinct `material` codes resolve to zero products in the catalog**, and no deposit price list is provided anywhere.

**Why it matters:** For any bottled or canned product, **the true payable total is unknowable** — and we cannot even compute by how much it's wrong. The brief says commitments are based on fixed prices; an order total that silently omits deposits is quietly incorrect.

**Our plan:** have the total **declare its own incompleteness** (`completeness: INCOMPLETE_DEPOSITS`) and escalate to a human rather than present a wrong number.

**What changes:** If deposits are out of scope → one sentence in ASSUMPTIONS, move on. If they're expected → we need the price list, which doesn't exist in the materials.

---

## Q8 — What are the actual rate limits?

**What we found:** The OpenAPI description says *"Undisclosed rate limits are in place"* plus an explicit architectural instruction: *"solutions should not be based on frequently retrieving prices and availabilities for all products… Query the APIs only when you have narrowed down the products based on static product data."* Max 1,000 products per request (>1,000 → 422).

Empirically: 80-id batches and ~15 calls drew no 429. **The practical ceiling is untested.**

**Why it matters:** An agent loop can issue many calls. If we hit a limit **during the live demo in front of judges**, we fail the 30% criterion outright. We're already architecting the right way (filter locally on static data, then one narrow API call) and caching responses to disk so the demo can replay — but we'd like a number.

**Ask:** Is a 1,000-product batch safe during judging? Requests per minute per key? Does a 429 come back cleanly or does it drop?

---

## Q9 — Is customer or authority data coming?

**What we found:** `customer` is a free-text string that **provably does not affect any response** — we tested six different customer strings and got byte-identical output. There is no customer model, no spend limits, no approver roles, no contract assortments, and **no order history**.

**Why it matters:** 20% of the rubric is *"autonomy and controls: what the agent can decide alone, what needs human sign-off."* A spend threshold needs a budget; an approver role needs an org model. Right now we're inventing all of it.

Also: their scenario *"standing order drift detection: the agent learns a kitchen's recurring weekly order and flags anomalies before auto-renewing"* **requires order history that isn't provided.** Either it's coming, or that scenario isn't buildable as described.

**Ask:**
- Is customer/authority data (spend caps, approver roles, contract assortments, standing orders) coming later, or is the permission model entirely fictional on our side?
- For drift detection — should we synthesise order history, and does synthetic history count?

**What changes:** If it's coming, we wait and wire to theirs. If not, we synthesise a customer+policy model, document it in ASSUMPTIONS, and say so in the pitch — which is defensible, but we want to say it deliberately rather than look like we missed something.

---

## Q10 — Why is delivery reliability only 25% covered?

**What we found:**
- `deliveryReliability`: 4,425 rows = **25.2%** of the catalog (243 distinct values, range 0.0–1.0)
- Carbon footprint: 11,033 rows = **62.9%** (mostly category-average, but 89 categories hold more than one distinct value, so it isn't a clean category lookup either)
- **Both present on only 3,123 products = 17.8%**

**Why it matters:** The brief offers *"delivery time & sustainability comparison"* as an optional direction. But a three-axis price/reliability/carbon ranking is only honest on about **1 in 6 products**. The design question is what "missing" means:
- **New product with no history** → missing should rank **neutral**
- **Poor or excluded supplier** → missing should rank **penalised**
- **Deliberately withheld** → shouldn't influence ranking at all

**Our plan:** rank coverage-aware and **degrade explicitly — missing ≠ good** — stating per result which axes we could actually evaluate.

**What changes:** Their answer decides whether absence is neutral or a penalty, which is a visible scoring decision in the demo. Getting it backwards means confidently ranking a product well because we know nothing about it.
