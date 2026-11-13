# AIMO — Merged build plan (~15h, 3 people tonight + 1 from Saturday)

Merge of the team plan (realistic schedule, right priorities) and the deep analysis plan (data traps, contract design, tech-award stacking). **The team schedule wins on timing; the analysis wins on what to avoid and what to monetise.**

Supersedes [PLAN-30H-SUPERSEDED.md](PLAN-30H-SUPERSEDED.md), which was scoped for 30h and is ~2× over-budget.

---

## 0. Why this shape

**Prize:** €4,000 / €2,000 / €1,000, est. 25–40 teams, **published rubric**. See [CHALLENGE.md](CHALLENGE.md).

**We chose this challenge** because nothing in its rubric requires domain knowledge we lack (unlike AstraZeneca's Finnish health system), it has the largest named cash pool of any challenge we reviewed, and **45% of the score — 30% working demo + 15% openness/documentation — is available to disciplined execution alone.**

| Weight | Criterion | What we build for it |
|---|---|---|
| **30%** | Working end-to-end demo | One continuous flow: request → search → offer → order → approval. **Not isolated pieces.** |
| **20%** | Solving the problem / user need | Precise constraint matching + per-constraint satisfaction report |
| **20%** | Autonomy and controls | YAML policy engine + human approval panel + readable decision log |
| **15%** | Robustness to exceptions | Partial availability, substitutions, impossible delivery dates |
| **15%** | Openness + production path | Auto-generated OpenAPI, ASSUMPTIONS page, justified choices, next steps |

**Their anti-pattern, quoted:** *"This is not about replacing today's e-commerce UI with a chatbot."* So the deliverable is **a typed interface + an operating model**, demonstrated by a working agent — not a chat window.

**Note the rubric contradiction:** the brief says substitution "isn't scored as core," but the rubric gives 15% to robustness *including substitutions*. **Build for the rubric.**

---

## 1. Roles

| Who | Owns | Carries |
|---|---|---|
| **CS (tech lead)** | FastAPI gateway over the mock APIs (OpenAPI auto-generated), MCP server, LLM agent + tool use, **Modal deploy** | Backbone of 30%, all of 15% openness |
| **Bio 1 — data & rules** | Catalog exploration, comparison/substitution attributes (allergens, lactose, certificates, pack size, delivery), ranking logic | 20% need-matching, 15% robustness |
| **Bio 2 — guardrails & audit** | `policy.yaml` (spend limits, allowed substitutions, when human sign-off is mandatory), human-readable audit log, **Aiven Postgres** | 20% autonomy — the highest-leverage axis |
| **Bio 3 — arrives Saturday** | Test & exception scenarios, approval panel, pitch, video | The visible half of 30%, and 20% *as judges perceive it* |

⚠️ **Bio 3 is overloaded.** The approval panel is where 20% of the rubric is visually judged; the pitch and video are ~3h on their own. **Move the approval panel to Bio 2** (it's the front-end of their own policy engine) and leave Bio 3 with scenarios + pitch + video.

---

## 2. Schedule

### Fase 0 — Tonight 21:45–00:00 · arranque
- **ALL: read [FINDINGS.md](FINDINGS.md) — 10 minutes.** Every trap below is already verified; discovering them tomorrow costs hours.
- **ALL: save the submission draft by 23:30.** Hard deadline.
- **ALL: claim credits now** — Modal (`VVX-2QX-8HW`, **$100 each person**), Aiven ($50), Gemini. Minutes of work, and Gemini is capped at 400 teams.
- **Bio 1:** portal (`junction26.valioaimo.fi`), download datasets, read API docs. ✅ *API key already tested and working — `{"status":"ok"}`. Both endpoints and their schemas are documented in FINDINGS.md.*
- **Bio 2:** first `policy.yaml` — what is auto-order vs human approval — and the log format.
- **CS:** repo, gateway skeleton with **3 endpoints: `search`, `offer`, `order`** (⚠️ **not "quote"** — the brief says *"fixed prices rather than a negotiated quote"*; naming it `offer` is a free openness point), real call to the mock API.
- **ALL: choose 3 demo requests.** Recommended:
  1. **The canonical one** — "1,000 L lactose-free milk by Monday" (their own example; safest 30%)
  2. **Hospital allergen substitution** — with the certifiability split (see §4)
  3. **Partial availability** — needs more than one SKU to fill

### Fase 1 — Saturday 09:00–13:00 · full flow
- **CS:** LLM agent using the gateway via MCP: request → search → offer → order.
- **Bio 2:** policy engine wired to the gateway; every decision logged as JSON **plus one human-readable sentence**.
- **Bio 1:** good/better/best substitution ranking, with hard rules for allergens and nutrition.
- **Bio 3:** Streamlit panel — pending approvals + audit log.
- **➕ ADDED — CS, last 60 min: `modal deploy` → public URL.** Deployed at hour 6, not hour 14. A broken deploy now is an inconvenience; at hour 14 it is the project.

**🚦 CHECKPOINT 13:00 — the milk request works end to end, including one case that escalates to human approval.** If not green, cut everything in §5 Tier 2.

### Fase 2 — Saturday 13:30–18:00 · robustness (15%)
- Partial availability: split delivery across dates, or combine products.
- Substitution outside buyer preferences → **always** to a human, with the trade-off explained.
- Impossible delivery date → agent warns and proposes alternatives.
- **Bio 1 + Bio 2: validate rules with the mentors** — Tommi Nurmi-Aro / Ville Takanen / Riku Tapper (technical + data governance), Hanna Forsström / Pirjo Kaartinen (commercial). **Bring the question list in §6.**
- **➕ ADDED (~45 min): the contradiction detector.** See §4 — cheapest high-impact differentiator available.

**🚦 18:00 — FEATURE FREEZE.**

### Fase 3 — Saturday 18:30–22:30 · polish & submit
- **"Assumptions & next steps" page** (the 15%): why OpenAPI + MCP, what is out of scope, next steps (verifiable credentials, sustainability).
- Slides, demo video, final submission text.
- **➕ ADDED: three award write-ups** (15 min each) + submission checklist (§3).
- Rehearse the pitch twice. **Have a backup video.**

Sunday morning is buffer. Junction submission closes **10:00**; set status to **FINAL**, not DRAFT.

---

## 3. Tech challenges we are doing — and why

**Three awards for ~3 hours.** Each one is work we need anyway.

| Award | Hours | Integration point | Why it is honest, not a bolt-on |
|---|---|---|---|
| **Modal** | **1.0** | `modal_app.py` wraps the FastAPI gateway. `modal deploy` → autoscaling public URL. End of Fase 1. | **We need a judge-openable URL regardless.** Zero-regret, and it removes the "only works on my laptop" demo risk. Credits are **$100 per person = $400**. |
| **Gemini** | **0.5** | Already the LLM doing tool use. Use **structured output** for NL→request parsing so the schema is the model's output contract. Cost is only the write-up. | Answers their "beyond simply adding an LLM" bar: schema-constrained generation, not a chat wrapper. Nearly free since it's on the critical path. |
| **Aiven** | **1.5** | Bio 2's audit log + order/approval state → **Aiven Postgres** instead of local SQLite. | The audit log is **already a scored deliverable** (20% autonomy). Hosting it on Aiven makes the same work an award too. |

### Not doing, and why
| Award | Reason |
|---|---|
| **Context.dev** | 2h to resolve GS1/certificate code lists at runtime. Genuinely elegant and would earn openness points — **but 2h is 13% of our budget.** Cut. |
| **NVIDIA Nemotron** | Its distinctive capability is vision/document input. **There are no images in this challenge.** A text-only call is a weak entry. |
| **Gemma** | Honest bar is "running an *open* model matters" — fine-tuning, on-device, privacy. Nothing here needs that, and a fine-tune is 8–14h. |
| **Cloudinary** | Only subject-matter-constrained award (needs visual media), **plus a separate submission form**. No fit. |
| **Oxylabs** | Requires buying a $500/month plan and cancelling it. Not worth the risk for no fit. |
| **Atech / Arduino** | Hardware checkout, physical demo risk, no sensing need in a procurement protocol. |

### Conflicts to respect
- **Modal vs Aiven Runtime** — one hosting story. Modal hosts the app; Aiven provides data services. Do **not** deploy to Aiven Runtime.
- **Gemini vs Gemma vs Nemotron** — three competing LLM-provider awards. Taking two dilutes the "this model is central" claim. **Gemini only.**

---

## 4. Data traps — encode these on day one

All verified against the live API. Full detail in [FINDINGS.md](FINDINGS.md).

| # | Trap | What to do |
|---|---|---|
| 1 | **`MAY_CONTAIN` is an undocumented third allergen value**, and pervasive | The schema documents only `CONTAINS` / `FREE_FROM`. **A filter written against those two silently treats "may contain traces" as safe.** Use a four-state model: `CONTAINS / MAY_CONTAIN / FREE_FROM / SILENT`. |
| 2 | **~59% of the catalog has no allergen statement at all** | `allergen` non-empty on 41%, `nonAllergen` on 29%. **You can only *certify* a swap on the ~29% with explicit FREE_FROM.** Absence of CONTAINS is not evidence of absence. |
| 3 | **`salesBlock` is never `true`** | It is NOT the "can't buy" signal. **Empty `scheduleLines` is** (~14% of catalog). Same response shape is returned for a nonexistent product ID — don't conflate "unknown SKU" with "undeliverable". |
| 4 | **Both APIs ignore `requestedDate` entirely** | Every date returns identical responses; `availableDate` frozen at **2026-11-16**. "By Monday" cannot be tested as a real constraint. Build date logic properly, demo against 2026-11-16, don't hunt for a lead-time model. |
| 5 | **Three undocumented sentinels in `availableAmount`** | `999999`, `9999999999.0`, `666666666.0`. `if amount == 999999` is wrong, and arithmetic on these produces absurd order proposals. |
| 6 | **`comparisonPrice` missing on 22.5%**, and rounded to 2 dp | Pack size = `catalogPrice.value / comparisonPrice.value` (**this is the shortcut that means we never need the undocumented sales-unit codes**). Needs a fallback: `unitConversions` → parse the Finnish name (81.2% carry a size token). Tag every result with a confidence tier. |
| 7 | **`unitConversions.volume.unit` is often not a volume unit** | GRM 5,498 · **H87 1,500** (= "piece") · KGM 875 · LTR only 762. Reading `.volume` as litres is wrong more often than right. |
| 8 | **`variableUnit: true` on 632 products** | Sold by variable weight — unit count doesn't determine quantity or price, so **a fixed-price commitment is impossible.** Route to human approval. That's a defensible guardrail, not a limitation. |
| 9 | **`allowedLotSize`** is 0.01 ("no constraint") on 96%, real on 674 | Real steps include **1.5 and 1.8** — the values that produce a visibly wrong total on stage. Write a test for these at hour 3. |
| 10 | **Deposits are unpriceable** | 506 products carry deposits; the 7 material codes resolve to zero products and no price list exists. Have the total **declare its own incompleteness** rather than being quietly wrong. |
| 11 | **`vatCode` in the file is dirty** (159 literal `"MEDIUM MEDIUM"`) | Use `tax.taxRate` from the price API. Never parse the file field. |
| 12 | **87MB JSON = 15s load, 2GB RSS** | Build a slim id-indexed SQLite once. **Never load the JSON at demo time.** |

### ➕ The cheapest differentiator: the contradiction detector (~45 min)
**Every Terminal product reports `closingTime` 2026-11-12T15:00 — over a day in the past — while simultaneously claiming availability on 2026-11-16.** Stock products report 2026-11-15T17:00 (future).

An agent that respects cut-offs rejects half the assortment. One that ignores them has no cut-off logic at all. **Ours detects the contradiction, degrades the commitment window to the price validity window, and says so.**

This is the single moment that proves to the judges we actually read their data, and it is the literal answer to their *"trust protocol: the minimum verification standard for an agent to trust Valio Aimo's claims without a manual check."* **Fold it into the hospital/allergen demo — don't make it a fourth scenario.**

---

## 5. Priorities

### Mandatory — the 3 core requirements + the 30%
Product/price/availability search · offer and order · human approval. **One continuous flow, not loose pieces.**

### Good to have
Substitutions with explanation · partial availability · a readable audit log.

### Tier 2 — only if time remains
Sustainability comparison · proactive selling agent · standing-order drift detection.

### Cut order if behind — announce each cut aloud
1. MCP transport (the auto-generated OpenAPI already carries the openness story)
2. Sustainability/delivery ranking — **keep the coverage disclosure sentence**, drop the ranking
3. Third demo scenario → becomes a slide
4. Substitution ranking tiers → single best substitute only

**Never cut:** the canonical milk flow, the policy engine, the approval panel, the readable audit log. **Those four are ~70% of the rubric.**

---

## 6. Mentor questions — Fase 2

1. **There is no order endpoint — is the order/approval contract purely ours to define, or do you have an internal schema to converge on?** (Line granularity, idempotency, whether confirmation promises quantity or only price.)
2. **Which `closingTime` semantics should we honour**, given every Terminal cut-off is already stale relative to server time?
3. **How should an agent treat `MAY_CONTAIN` and `X99` in an allergen-safety decision — and is silence (59% of the catalog) ever permissible for a school or hospital kitchen?**
4. **Will you judge date/lead-time logic at all**, given the mock ignores `requestedDate` and has one frozen delivery date?
5. **Is the 5-digit `category` code hierarchical?** (Is 10400 a sibling of 10401 under a 104xx parent?) That one fact decides whether category-distance substitution ranking is possible. A code→name mapping would help too.
6. **Brief says substitution isn't core, rubric gives it 15% — which applies?**
7. **Deposit pricing** — expected in order totals, or out of scope?
8. **Actual rate limits?** "Undisclosed" is risky for a live demo.
9. **Is customer/authority data coming** (spend limits, approver roles, standing orders)? Their drift-detection scenario implies order history exists; none is provided.

**If two minutes: 1, 3, 6.**

---

## 7. Submission checklist (CS owns from Fase 0)
- [ ] Junction submission set to **FINAL**, not DRAFT (closes **Sunday 10:00**)
- [ ] Pitch video **max 2:00** — strictly enforced, publicly viewable
- [ ] Pitch deck (PDF)
- [ ] Public GitHub repo (MIT) + **live Modal URL**
- [ ] README with a data-fetch step (datasets are gitignored — judges need the 3 download endpoints)
- [ ] **Gemini write-up**: model used, what it does, why it matters, how we improved outputs
- [ ] **Aiven note**: which services, what they enable
- [ ] **Modal note**: what it powers
- [ ] Team phone numbers + Discord username
- [ ] **ALL FOUR present for peer review Sunday 10:30–14:00** — mandatory for main-prize eligibility
- [ ] Nemotron / Cloudinary / Context.dev / Oxylabs: **explicitly not entered**

---

## 8. Two open decisions
1. **`allergenPolicy` with no default** — forcing the caller to state their allergen strictness is a defensible safety stance and a good pitch line, but it makes the API less convenient. Agree?
2. **Scenario swap** — the agent-to-agent trust handshake (unknown agent must present a delegation credential; list price to anyone, net customer price only to a proven delegate) is the only idea that engages their *"who owns the customer relationship"* framing head-on. It was ranked below the variable-weight scenario because **the live API provably ignores `customer`**, making customer-scoped pricing our layer rather than theirs. Swap it in if the mentors seem to reward protocol ambition over data rigour.
