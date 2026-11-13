# Valio Aimo — questions for the booth

**Source tags:** `[DOCS]` their OpenAPI/schema descriptions · `[TESTED]` our live API calls · `[DATA]` our analysis of the 4 files

Full detail lives in [docs/](docs/) and [FINDINGS.md](FINDINGS.md). This page is just the questions.

---

## The challenge in four lines
Let **autonomous purchasing agents** find products, compare offers, and place orders against Valio Aimo — by defining **the interface and operating model**, not a marketplace. `[DOCS]`

Their anti-pattern, quoted: *"This is not about replacing today's e-commerce UI with a chatbot."*

**Core 3:** price/availability lookup · inquiry→order (fixed prices, not negotiated quotes) · permission & human-approval management.
**Rubric:** 30% working end-to-end demo · 20% problem fit · 20% autonomy & controls · 15% robustness · 15% openness. **Prizes €4,000 / €2,000 / €1,000.**

---

# ⭐ Q1 — Is the order contract ours to define?

**Fact:** The API has six operations only — `ping`, `price`, `availability`, 3 file downloads. **No order, basket or quote endpoint.** `[DOCS, TESTED]` *(404 on `/api/order`, `/api/orders`, `/api/quote`)*

**Why it matters:** 30% of the score is a *"full request → lookup → **order/approval** flow."* With no order endpoint, we have to build one — the question is how far.

**Ask:**
- Is defining the order/approval contract our deliverable, or do you have an internal schema to converge on?
- Should our order request **extend your `customer` / `requestedDate` / `products` shape**? (We plan to.)
- Does a confirmation promise **quantity, or only price**? You say *"fixed prices rather than a negotiated quote"* `[DOCS]`
- Do you want an **idempotency key**?
- Is an **MCP tool surface** acceptable as the submitted interface, or HTTP+OpenAPI as primary?

---

# ⭐ Q2 — Which `closingTime` should we honour? 53% are in the past

**Fact:** `closingTime` is *"the order cut-off to receive goods on availableDate."* `[DOCS]`
**But 129 of 244 deliverable products (53%) report a cut-off already in the past**, across 12 distinct values. Terminal products cluster at 2026-11-12T15:00 — a day before server time — while still claiming 2026-11-16 availability. `[TESTED]`

**Why it matters:** Honour them literally → we reject **most of the catalog**. Ignore them → we have no cut-off logic, and that's exactly what the 15% robustness criterion rewards.

**Ask:** Artefact of the mock we should ignore, or do you want *"cut-off passed → next delivery slot"* modelled?

---

# ⭐ Q3 — `MAY_CONTAIN` and allergen silence

**Facts:**
- Schema documents **only `CONTAINS` and `FREE_FROM`** as allergen `unit` values. `[DOCS]`
- **A third value, `MAY_CONTAIN`, is everywhere** and undocumented — AN 1,225 · AY 954 · AM 728 · SA 727. `[DATA]`
- **~59% of the catalog has no allergen statement at all** (`allergen` non-empty on 41%, `nonAllergen` on 29%). `[DATA]`
- **`X99`** = "other/unspecified", 121 CONTAINS + 74 FREE_FROM. `[DATA]`
- **Your own example product `464306` is `FREE_FROM_LACTOSE` but carries allergen `AM` = milk, as `CONTAINS`.** Lactose-free is not milk-allergen-free. `[DATA]`

**Why it matters:** Your scenario is *"allergen-safe substitution under pressure, in a school or hospital kitchen."* `[DOCS]` A filter written against the two documented values **silently treats "may contain traces" as safe.** We can only *certify* a swap on the ~29% with an explicit free-from.

**Ask:**
- Is `MAY_CONTAIN` a hard fail, or an escalation to a human?
- **Is silence ever committable** for a school/hospital kitchen?
- Are these GS1 AllergenTypeCodes — is there a lookup table?

---

# Q4 — Brief says substitution isn't core; rubric gives it 15%

**Fact:** Brief: substitution *"isn't scored as core."* Rubric: **15% for "robustness… partial availability, substitutions and delivery constraints."** `[DOCS]` These contradict.

**Ask:** Which applies? And does a **specification artefact** score on its own, or must everything be in the running demo?

---

# Q5 — Is the 5-digit `category` hierarchical?

**Facts:**
- 349 categories, all exactly 5 digits. *"Category names are not part of this data set."* `[DOCS]`
- **230 of your 250 substitution pairs (92%) stay inside the same category** `[DATA]` — so same-category is how you model substitutability.

**Why it matters:** If 10400 and 10401 are siblings under a 104xx parent, we can rank substitutes by **category distance** — which is your *"good-better-best"* ask. If it's flat, we fall back to brand + pack size, which is weaker.

**Ask:** Is the code hierarchical? Can we have a code→name mapping?

---

# Q6 — Will you judge date/lead-time logic?

**Fact:** **Both endpoints ignore `requestedDate` entirely.** 2026-11-13, 11-14 and 12-25 returned byte-identical responses; `availableDate` is frozen at 2026-11-16. Prices identical for 2025, 2026 and 2027. `[TESTED]`

**Why it matters:** Your canonical example is *"by Monday"* — untestable. Your resources promise *"delivery lead times"* `[DOCS]`, but the mock has one date.

**Ask:** Judged or not? If judged, what are the intended lead-time rules — per temperature class, logistic model, vendor?

---

# Q7 — Delivery reliability: why 25%, and does missing mean bad?

**Facts:**
- Coverage **25.2%**, dispersed ~25% across every category — **no category at 100%**. Looks like order-history volume, not product type. `[DATA]`
- **56.3% sit at exactly 1.0**; only 6.6% below 0.9; 12 products at 0.0. `[DATA]`
- **It predicts availability:** DR < 0.75 → **22.5% returned empty `scheduleLines`**; DR = 1.0 → **0%**. `[TESTED]`
- The 12 products at 0.0 still report themselves **fully available and priced**. `[TESTED]`

**Ask:**
- Why only 25% — insufficient history, deliberate cut-off, something else?
- **Should missing rank neutral or penalised?** (We currently renormalise weights and never impute.)
- Is it computed over a fixed window? 56% at exactly 1.0 suggests a short one.

---

# Q8 — Carbon: confirm it's food-only by design

**We think we answered this one ourselves — just confirming.**

**Facts:**
- Coverage is **81.2% on food, 0.4% on non-food** (non-food = cleaning, packaging, kitchen equipment, office supplies). `[DATA]`
- Every low-coverage vendor is non-food — DUNI 817 products, Essity 245, Huhtamaki 190, Diversey 343. `[DATA]`
- Makes sense: `kg CO2-eq/kg` is a food-LCA unit, meaningless for a knife.
- You say it's a **category average** `[DOCS]` — mostly true, but **89 of 279 categories (32%) hold multiple values**, split along **plant-based vs animal protein** (cat 41705: meatballs 15.79 vs vegan patties 2.195). And **86 of 177 values span multiple categories**. `[DATA]`

**Ask:** Confirm carbon is food-only by design, so we drop the axis as **not applicable** on non-food rather than showing it as a gap? And is the average computed over an external food-type taxonomy we don't have?

---

# Q9 — Deposits can't be priced

**Fact:** 506 products carry deposits, but the **7 `material` codes resolve to zero catalog products**, and there's no deposit price list anywhere. `[DATA]`

**Why it matters:** For bottled/canned goods the true payable total is unknowable — and we can't even bound it. Against a brief built on fixed-price commitments.

**Ask:** In scope for order totals, or out? (Our plan: the total **declares its own incompleteness** and escalates, rather than showing a wrong number.)

---

# Q10 — Rate limits, and is customer data coming?

**Facts:**
- *"Undisclosed rate limits are in place."* `[DOCS]` We saw no 429 at 80-id batches, ~15 calls. `[TESTED]`
- **`customer` provably changes nothing** — six different strings, identical output. `[TESTED]` You say so too. `[DOCS]`
- No customer model, spend limits, approver roles, or **order history** anywhere. `[DATA]`

**Ask:**
- Is a 1,000-product batch safe during judging? Requests/minute per key?
- Is customer/authority data coming, or is the permission model entirely ours to invent? (20% of the score is autonomy and controls — a spend cap needs a budget.)
- Your *"standing order drift detection"* scenario needs order history that isn't provided — should we synthesise it?

---

## If you only get two minutes
**Q1** (order contract) · **Q2** (stale cut-offs) · **Q3** (`MAY_CONTAIN`)

## Two openers that show we read the data
> *"Your example product 464306 is lactose-free but still flags milk as an allergen — how should an agent treat that in a hospital kitchen?"*

> *"53% of deliverable products have an order cut-off in the past. Artefact, or should we model next-slot rollover?"*
