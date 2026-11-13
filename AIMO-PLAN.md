# AIMO-TTP — 30h build plan

**Codename: AIMO-TTP (Trusted Trade Protocol).**
Framing: **we ship a specification plus a reference implementation of both sides** — a Valio Aimo-side agent-readable interface and an external buyer agent that drives it. That is the direct answer to their anti-pattern ("not a chatbot") and it carries the 15% openness criterion.

## 0. Four positioning calls that drive everything

1. **The product is a contract, not a chatbot.** Everything typed: JSON Schema + OpenAPI 3.1 for the order/approval layer we invent, plus an MCP server as a thin second transport over the same tools.
2. **Trust = claim provenance.** Every field the agent acts on is wrapped in a `Claim` envelope with source, observedAt, confidence tier, verification status. **The dataset hands us the killer demo: `closingTime` 2026-11-12 contradicts `availableDate` 2026-11-16.** A system that detects and surfaces its supplier's own contradiction is the strongest trust artifact available here.
3. **Guardrails are derived from data defects, not invented.** `variableUnit` (632 products) genuinely cannot support a fixed-price commitment. Deposits (506) genuinely cannot be totalled. 59% of the catalog genuinely has no allergen statement. Each becomes a named, justified policy rule — far more credible than "spend over €5k needs approval."
4. **Degrade explicitly, never silently.** Missing ≠ good. Every ranking states its own coverage.

### Rubric mapping
| Rubric | Weight | Earned where |
|---|---|---|
| Working E2E demo | 30% | `demo/scripts/*` driving real APIs → order → approval → fulfilment + operator console |
| Problem/user need | 20% | Requirement-spec parser + constraint satisfaction with per-constraint report |
| Autonomy & controls | 20% | `policy/` rule engine + approval state machine + signed audit ledger |
| Robustness | 15% | Partial-allocation planner + good-better-best substitution + exception taxonomy |
| Openness/production path | 15% | `spec/` — JSON Schema, OpenAPI, MCP manifest, ASSUMPTIONS.md, ROADMAP.md |

## A. Architecture

```
aimo-ttp/
├── spec/                              # the 15% lives here
│   ├── openapi.yaml                   # our invented order/approval API, OAS 3.1
│   ├── schemas/{claim,requirement-spec,offer,order-request,
│   │            order-response,approval,audit-event}.schema.json
│   ├── policy/default-policy.yaml     # the guardrail model, as data
│   ├── mcp-manifest.json
│   ├── ASSUMPTIONS.md                 # every inferred code system + confidence
│   ├── TRUST-PROTOCOL.md
│   └── ROADMAP.md
├── ttp/
│   ├── catalog/{build_index,index,units,allergens,labels,categories}.py
│   ├── sources/{aimo_client,normalize}.py
│   ├── trust/{claims,verifiers,attest}.py
│   ├── policy/{engine,rules}.py
│   ├── planner/{match,allocate,substitute,rank}.py
│   ├── orders/{store,state,api}.py
│   ├── audit/{ledger,render}.py
│   └── agent/{intent,tools,loop,mcp_server}.py
├── console/app/{orders/[id],audit/[id],trust}/page.tsx
├── demo/{scenarios/*.yaml,run_demo.py}
├── modal_app.py
└── README.md
```

### Technology choices
| Choice | Why |
|---|---|
| **Python 3.12 + FastAPI + Pydantic v2** | Pydantic is the single source of truth; `model_json_schema()` generates `spec/schemas/*`, FastAPI generates `openapi.yaml`. **The spec cannot drift from the code — that IS the openness story, for free.** |
| **SQLite+FTS5 for catalog, Aiven Postgres for orders** | 87MB JSON = 15s load, 2GB RSS. Slim index once → ~15MB SQLite. Local filtering respects the published rate-limit guidance. |
| **Aiven ClickHouse for audit ledger** | Append-only, high-cardinality event analytics. The honest Aiven story (observability of agent decisions, not a hosting swap). Postgres mirror for last-N so console never depends on ClickHouse uptime. |
| **Gemini structured output + function calling** | Two places only: NL→RequirementSpec, and audit-narrative generation. **Deterministic code does all arithmetic and all policy.** "LLM at the edges, deterministic core" is the right answer and a talking point against the chatbot anti-pattern. |
| **Ed25519 over offers + audit events** | 2h. Literal answer to "trust claims without a manual check" and the brief's "verifiable credential / trust-layer approaches." Not a blockchain — a signed, replayable offer with a validity window. |
| **MCP as a second transport** | Open standards without making MCP the only interface. HTTP+OpenAPI primary. |
| **Modal deploy** | One command to a public URL. |

### Ownership
- **A — CS lead, contract & server.** `spec/`, `orders/`, `audit/ledger.py`, `trust/attest.py`, deploy. Owns the 15% artifact + backbone of 30%.
- **B — data.** `catalog/`, `sources/`, `trust/verifiers.py`. **Every trap in AIMO-FINDINGS.md is B's responsibility to encode on day one.**
- **C — decision logic.** `planner/`, `policy/`. Carries 20% need-matching + 15% robustness.
- **D — surface.** `console/`, `agent/intent.py`, `audit/render.py`, then pitch/deck/video from H20.

### Schedule
**H0–H1 — all four, no code.** Lock the Claim envelope, OrderRequest/Response field names, approval state names, demo scenario list. A writes Pydantic stubs within the hour so everyone codes against real types. **Claim all credits now.** Pull `openapi.json` from the portal into `reference/`.

**H1–H5 — parallel foundations.**
- A: `spec/schemas/*` as Pydantic; `orders/state.py`; `orders/api.py` stubs returning fixtures. **H5 deliverable: API callable and typed.** Unblocks C and D.
- B: `build_index.py` → SQLite+FTS5. Then `aimo_client.py` (batch-80, backoff, on-disk cache) and **`normalize.py` encoding all traps as named constants** — `SENTINEL_AMOUNTS = {999999, 9999999999.0, 666666666.0}`, `is_deliverable = bool(resp.get("scheduleLines"))` never `salesBlock`, `.get()` everywhere, `tax.taxRate` only, `DATE_SEMANTICS = "echo-only, frozen at 2026-11-16"`.
- C: `units.py` three-tier resolver returning `(value, tier, confidence)`; `allergens.py` **four-state** `CONTAINS | MAY_CONTAIN | FREE_FROM | SILENT` plus `X99` as hard un-certifiable.
- D: `intent.py` Gemini structured output → RequirementSpec; console skeleton, 3 routes, mock data.

**H5–H9 — first vertical slice.**
- A: real persistence, idempotency, policy call site, audit event on every transition, hash chain + signing.
- B: `verifiers.py` — minimum four contradiction detectors: stale-closingTime, sentinel-amount, missing-comparisonPrice, deposit-unpriceable. Each emits structured `TrustFinding` with severity.
- C: `match.py` + `allocate.py`. **Must handle lot-size steps (1.5/1.8 are the stage-killers)**, `unitPrecision`, partial fill across SKUs with stated shortfall.
- D: approval screen on A's real API — requested vs proposed diff, every triggered rule with reason, per-constraint satisfaction table, Approve / Reject / Approve-with-edit.

**H9 — CHECKPOINT 1.** Canonical example headless: 1,000 L lactose-free → `464306` → 1,000 ST → **€1,010.00 ex-VAT** → order → auto-approve → audit rendered. Not green? Cut Tier 3 scenarios immediately.

**H9–H14 — depth on scored axes.**
- A: approvals endpoint, `validTo` expiry sweeper, re-quote flow, `GET /audit/{id}` in JSON + markdown. **Deploy to Modal + Aiven at H12, not H19.**
- B: ClickHouse sink; delivery-reliability + carbon joins with explicit coverage reporting; `labels.py` with temperature pseudo-labels filtered.
- C: `substitute.py` good-better-best (category + brand + derived pack size + nutritionalClaim, gated on allergen assertion, seed pairs symmetrised); full `rules.py`; coverage-aware `rank.py`.
- D: audit narrative (Gemini writes prose **from** structured events, never invents — assert every number in the prose exists in the events); trust panel.

**H14 — CHECKPOINT 2.** Console decision: if Next.js isn't convincing, freeze and rebuild in Streamlit in 2h. **Scenario list frozen to exactly 4.**

**H14–H18 — scenario hardening, paired.** A+C on `demo/scenarios/*.yaml` with deterministic replay (cached responses — the demo cannot die on wifi). B+D on polish, coverage disclosures, `ASSUMPTIONS.md`, `TRUST-PROTOCOL.md`, `ROADMAP.md`.

**H18–H20 — freeze.** Dress rehearsal of all four scenarios, twice, on the deployed URL. Demo-path bugs only. **H20 hard code freeze.**

**H20–H26 — pitch.** D leads deck + video. A writes submission text + award notes. B+C write README + spec walkthrough. **Record against replay, not live APIs.**

**H26–H29 — sleep in shifts**, two down two on. **H29–H30 submit.** In by H28 at the latest.

### Minimum demo path (green at H9, protected to H20)
**NL request → RequirementSpec → local catalog filter → one narrow `/price`+`/availability` call → signed Offer with validity window → OrderRequest → policy evaluation → auto-commit or human approval in console → hash-chained audit trail readable as plain English.**

On-path files only: `agent/intent.py`, `catalog/{index,units}.py`, `sources/{aimo_client,normalize}.py`, `planner/{match,allocate}.py`, `policy/engine.py`, `orders/{api,state,store}.py`, `audit/{ledger,render}.py`, `console/app/orders/[id]`.
Off-path (the 15%+20% uplift, after H9): substitution, ranking, MCP, ClickHouse, audit-event signing, trust panel.

## B. The order/approval contract

Principles: **extend** the existing `{customer, requestedDate, products}` vocabulary rather than replace it; every commitment references a signed, time-bounded offer; approval is a first-class resource, not a flag.

### Claim envelope
```json
{"value": 1.01, "unit": "EUR/L", "source": "aimo.price.v1",
 "observedAt": "2026-11-13T21:33:00+02:00",
 "validFrom": "...", "validTo": "...",
 "confidence": "ASSERTED",
 "derivation": "catalogPrice.value / comparisonPrice.value",
 "findings": [{"code":"UNIT_DERIVED_TIER_1","severity":"info",
               "message":"Litres per sales unit derived from price ratio; ±0.3%"}]}
```
`confidence` ∈ **ASSERTED** (supplier stated) · **DERIVED** (we computed, derivation recorded) · **INFERRED** (heuristic, e.g. name token) · **UNKNOWN** (absent, never silently defaulted).
→ Only ASSERTED and DERIVED may back an autonomous commitment. INFERRED forces approval. UNKNOWN blocks the line.

### RequirementSpec — key field
`allergenPolicy` ∈ `REQUIRE_EXPLICIT_FREE_FROM` | `REJECT_CONTAINS_AND_MAY_CONTAIN` | `REJECT_CONTAINS_ONLY`, **required, no default.** Defaulting it is a safety decision. That one required field is the cleanest expression of the MAY_CONTAIN / silent-catalog problem in the whole spec.

### Offer — `POST /ttp/v1/offers`
Replaces the "quote" the brief rules out: **fixed-price, time-bounded, signed**, not a negotiation.
Key fields: `priceValidFrom/To`, `orderCutoff`, **`cutoffTrust` ∈ CONSISTENT | CONTRADICTED_BY_SOURCE | ABSENT**, `fulfilment` ∈ COMPLETE | PARTIAL | SUBSTITUTED | UNFULFILLABLE, per-line `derivedPackSize{value,unit,confidence,derivation}`, `constraintReport[]`, `trustFindings[]`, `substitutionTier`, `alternatives[]` with explicit tradeoff text, `coverage{}`, `signature{alg:Ed25519}`.
**`totals.completeness` ∈ COMPLETE | INCOMPLETE_DEPOSITS | INCOMPLETE_VARIABLE_WEIGHT** — how the unpriceable-deposit finding becomes a feature: the total declares its own incompleteness rather than lying.
For every Terminal product in this dataset `cutoffTrust = CONTRADICTED_BY_SOURCE`. **That field alone is the trust-protocol demo beat.**

### OrderRequest
Keeps `customer`, `requestedDate`, `products` **verbatim as top-level keys** — same vocabulary as `/price` and `/availability` — extended with `offerRef{offerId,offerHash}`, `commitment{priceBasis,acceptPriceDriftBps,acceptPartial,acceptSubstitutionTiers,maxTotalExVat}`, `authority{agentId,actingFor,policyRef,delegationProof}`, `idempotencyKey`. **Say this out loud in the pitch — it's a concrete openness point.**
**`products[].units` is in sales units, never derived litres.** Derived quantities never cross the commitment boundary — that rule is what makes the 22.5% missing-comparisonPrice problem non-fatal.

### Approval state machine
```
DRAFT →submit→ VALIDATING →policy→ AUTO_COMMITTED →ack→ CONFIRMED → FULFILLED
                   ├─ESCALATE→ PENDING_APPROVAL ─approve────────→│
                   │              ├─approve_with_edit→ VALIDATING (new offer)
                   │              ├─reject→ REJECTED
                   │              └─timeout(expiresAt)→ EXPIRED
                   ├─DENY→ BLOCKED
                   └─offer stale→ REQUOTE_REQUIRED → VALIDATING
CONFIRMED →cancel(before cutoff)→ CANCELLED
```
- **Offer binding:** valid only while `now < priceValidTo` AND `offerHash` matches. Stale offer never silently re-prices → `REQUOTE_REQUIRED`, new Offer with a **price diff**; diff > `acceptPriceDriftBps` re-escalates. Direct answer to "how does it reference the price validity window."
- **Approval expiry** = `min(priceValidTo, orderCutoff)`; when `cutoffTrust == CONTRADICTED_BY_SOURCE` fall back to `priceValidTo` **and log the reason**. Handles the stale-closingTime trap without rejecting every Terminal product.
- **`approve_with_edit` cannot commit directly** — re-enters VALIDATING, re-prices, re-runs policy. Prevents a human bypassing policy.
- **Idempotency:** key unique per customer; replay returns original with `"replayed": true`; different body → `409 IDEMPOTENCY_KEY_CONFLICT` with body-hash diff.

### Guardrail rules — all data-justified
| ID | Rule | Verdict | Justification |
|---|---|---|---|
| R-01 | Allergen-constrained line needs explicit `FREE_FROM` | DENY if absent | 59% silent; absence of CONTAINS ≠ evidence of absence |
| R-02 | `MAY_CONTAIN` on constrained allergen | DENY strict / ESCALATE standard | Undocumented third value; silent-pass is the worst available bug |
| R-03 | `variableUnit: true` | ESCALATE always | 632 products; fixed-price commitment impossible |
| R-04 | Total incomplete via deposits | ESCALATE | 506 products unpriceable |
| R-05 | Pack size `INFERRED` on quantity-constrained line | ESCALATE | 22.5% missing comparisonPrice |
| R-06 | Sentinel `availableAmount` AND qty > threshold | ESCALATE | three observed sentinels |
| R-07 | Total > autonomous spend cap | ESCALATE | standard control |
| R-08 | Substitution outside `mustHave` | ESCALATE | brief's own example |
| R-09 | Substitution inside `mustHave`, tier ≤ max, drift ≤ bps | AUTONOMOUS | what we actually want automated |
| R-10 | `X99` allergen code on constrained line | DENY | "other/unspecified" can't ground a safety claim |
| R-11 | Empty `scheduleLines` | DENY line as `UNDELIVERABLE`, distinct from `UNKNOWN_SKU` | ~14%; same shape as nonexistent id |
| R-12 | Partial fill below `minFillRatio` | ESCALATE | robustness |
| R-13 | New vendor never ordered from | ESCALATE | governance |
| R-14 | Cumulative daily spend > rolling cap | ESCALATE | **closes the many-small-orders hole most teams leave open** |

Each verdict carries `approverRole`. Policy file is versioned and **its hash lands in every audit event** — so "which rules were in force when this was approved" is answerable.

### Audit trail
Hash-chained append-only: `{eventId, orderId, seq, ts, actor{type,id}, action, inputsHash, policyHash, payload, prevHash, hash, sig}`.
Actions: `SPEC_RECEIVED, CANDIDATES_FILTERED, PRICES_FETCHED, TRUST_FINDING_RAISED, OFFER_ISSUED, ORDER_SUBMITTED, POLICY_EVALUATED, APPROVAL_REQUESTED, HUMAN_DECIDED, STATE_CHANGED, OFFER_EXPIRED, REQUOTED, FULFILLED`.
**Two renderings from one source:** `application/json` (verifiable chain) and `text/markdown` (narrative — *"I filtered 17,546 products to 24 on lactose-free + drinking-milk. I queried prices for those 24 in one call. I chose 464306 at €1.01/L, 8% cheaper than the runner-up. I could not verify stock quantity because availableAmount returned a sentinel. Spend of €1,010 exceeded your €750 autonomous cap, so I asked Maija, who approved at 21:41."*).
Per-event `visibility` ∈ `BUYER | SUPPLIER | BOTH` — the data-ownership nuance the brief gestures at.

## C. Demo scenarios

**Final set: 1, 2, 3, 4 — with 13 folded into 4, and 9 as a 30-second coda.**
Story arc: *here is what your data can and cannot be trusted to assert, here is where we drew the autonomy line because of it, here is the receipt.*

### Tier 1 — build these
**1. The silent catalog (allergen certifiability audit).** Hospital kitchen sourcing 40 items for a nut-free ward. Agent splits the catalog into four verification states — explicitly nut-free / contains / may-contain / **silent** — refuses to commit on the silent set, and returns a shortlist of items where Valio Aimo could close the gap with one data field. *Trust + guardrails + audit.* Buildable: 29.2% `nonAllergen`, 41.1% `allergen`, ~59% silent, 93 GS1 codes. **Highest impact — reframes a data gap as the sponsor's own roadmap insight. No other team will find this because it requires having counted.**

**2. "Your own system disagrees with itself."** Restaurant group asks for 12 Terminal items for Monday. Every one reports a cut-off already past while claiming Monday availability. Agent flags the contradiction, degrades the commitment window to price validity, documents why, files a data-quality report back to Valio Aimo. *Trust + audit + robustness.* Verified in the data. **Highest impact — the moment judges believe we read their data.**

**3. The variable-weight budget trap.** Catering company, hard €2,000 ceiling. Half the basket is variable weight, so unit count doesn't determine the invoice. Agent quarantines those lines, commits autonomously on fixed-unit ones, gives the human a worst-case price envelope. *Guardrails + response logic + trust.* 632 products. **High — a genuine logical impossibility in their own commercial model, and we name it.**

**4. Partial fill with good-better-best, honestly ranked.** University canteen needs 1,800 L lactose-free by Monday; no single SKU covers it. Three-line allocation respecting lot-size steps, offering Good (cheapest, mixed packs) / Better (single SKU, +6%) / Best (Finnish-origin, +11%) — each card stating which of price/reliability/carbon it could actually evaluate. *Response logic + trust + audit.* **High — the 15% robustness clause in one screen, and "missing ≠ good" is a line judges repeat.**

### Tier 2 — if ahead, else slides
5. **Public procurement origin mandate** — municipal kitchen contractually ≥60% Finnish-origin spend; agent optimises price *subject to a portfolio-level constraint*, showing running percentage. (Labels: 2,057 + 1,772 + 826.) **High and highly differentiated — nobody else will model portfolio-level constraints.**
6. **The deposit-shaped hole in the invoice** — `totals.completeness: INCOMPLETE_DEPOSITS`, bounds the unknown, escalates. "Our total declares its own incompleteness instead of being quietly wrong."
7. **Night-shift delegated authority** — 02:00 agent on reduced cap, queues rather than blocks, approval lands at 06:00 still inside price validity. ~1h on top of the engine.
8. **Legacy order-list import** — 120 codes; separates "never existed" from "exists but undeliverable" (identical API response shape), tells the buyer which 14 need a replacement decision vs which were typos.
9. **Cap evasion by a thousand small orders** — rolling-daily-spend rule fires on the seventh order; audit shows the cumulative curve. ~45 min, one slide.
10. **Agent-to-agent trust handshake** — unknown agent must present a delegation credential; catalog+list price to anyone, net customer price only to a proven delegate. **Note honestly that `customer` provably does not affect live responses, so customer-scoped pricing is our layer, not theirs.** Only scenario engaging "who owns the customer relationship" head-on.

### Tier 3 — slides or cut
11. Fish day with real MSC/ASC certificates (104/51 products — thin but genuine). 12. Organic share creep (overlaps 5). 13. **Offer went stale mid-approval** — fold into scenario 4 as a 20-second beat; near-zero marginal cost once the state machine exists. 14. Multi-site allocation (2h plumbing for a scale story, not a trust story). 15. Unit-conversion confession — already visible inside 1 and 4 via `confidence`; don't spend a slot.

## D. Tech awards — pursue three, fourth if H14 green. ~5.5h total

| Award | Incr. | Integration | Why honest |
|---|---|---|---|
| **Modal** | **1.0h** | `modal_app.py` wraps `orders/api.py`; `modal deploy` → public URL. Catalog index build as a Modal function. | Need the URL regardless. Zero-regret. **A, H12.** |
| **Aiven** | **1.5h** | **ClickHouse as the audit ledger sink**; console analytics view (decisions per rule, escalation rate, mean time-to-approval, findings by code). Postgres for order state. | The explicitly blessed "observe the agent" use. Not a hosting swap — the ledger is a scored deliverable. **B, H12–14.** |
| **Gemini** | **1.0h** | (a) `intent.py` NL→RequirementSpec via **structured output using our JSON Schema** — the spec file is literally the model's output contract; (b) `audit/render.py` narrative constrained to facts in the event list, with a post-hoc assertion every number in the prose appears in the events. | Answers "beyond adding an LLM" specifically: schema-constrained generation + verified grounding. **D.** |
| **Context.dev** *(conditional)* | **2.0h** | `allergens.py` / `labels.py` resolve the **undocumented** code systems at runtime from authoritative public sources (GS1 AllergenTypeCode; MSC/ASC/EU Organic/Svanen bodies). Cache locally — cached calls cost full credits. | Qualifies properly: in the core flow, visibly drives the demo. **Rare case where an award integration also earns rubric points** — it's the openness criterion (open external code lists, not proprietary mappings) AND the trust criterion (cited provenance for every inferred code). **B.** |

**Conflicts, plainly:**
- **Modal vs Aiven Runtime** — one hosting story. Modal hosts; Aiven supplies data services.
- **Gemini vs Gemma vs Nemotron** — take **Gemini only.** Gemma's honest bar is "running an *open* model matters" and nothing here needs that. Nemotron's edge is vision/document input and there are no images. Either as a text-only API call is a weak entry that costs hours and dilutes the pitch.
- **Context.dev vs Exa vs Oxylabs** — Context.dev wins: 50k credits, no card, no rate limit (50 concurrent), **and the lead judge is the CTO who is on site nearly the whole event.**
- **Cloudinary — skip.** Only subject-matter-constrained award, separate form, no visual media here.
- **Atech — skip.** Hardware risk, no sensing need.

**Reinforcing pairs to name in the submission:** audit ledger → Aiven + 20% autonomy + 15% openness (one unit of work, three returns). Code-system resolution → Context.dev + trust protocol + ASSUMPTIONS.md. Public URL → Modal + the 30%.

## E. Risk register

| # | Failure mode | Lik. | Mitigation | Owner |
|---|---|---|---|---|
| 1 | **Demo dies on rate limits or wifi during the pitch** | High | Disk cache from H3; `run_demo.py --replay` serves from cache. **Record the video against replay.** Live-call the API once on stage early as proof, then switch. | B |
| 2 | **Scope sprawl: 15 scenarios, 4 half-built** | High | Frozen to 4 at H14, no exceptions. Tier 2/3 become slides. "Slide" is a legitimate deliverable. | A enforces |
| 3 | **Console looks prototype-y, tanks perceived 30%** | Med-high | Streamlit fallback decision at H14, 2h budget. **The approval screen specifically must look deliberate — it's where 20% is visible.** | D |
| 4 | **Spec and code drift; `spec/` becomes a lie** | Med | Pydantic is source of truth; `make spec` regenerates, CI fails if dirty. **Never hand-edit spec files.** | A |
| 5 | **Lot-size arithmetic produces a wrong total on stage** | Med | Property tests on `allocate.py` for steps 1.5/1.8/2.5/3.0 + `unitPrecision`; golden test asserting €1,010.00 exactly. **Written at H6, not H19.** | C |
| 6 | **First deploy at H19 and it fails** | Med | Deploy at H12. Broken at H12 is an inconvenience; at H19 it's the project. | A |
| 7 | **Gemini hallucinates a constraint, agent orders wrong thing on stage** | Med | Structured output + schema validation + **RequirementSpec shown to the human before any commitment** in the escalated path; confirmation echo logged on the autonomous path. **The LLM never computes a price, quantity or policy verdict.** | D |
| 8 | **Two people editing `spec/schemas` at H1–H5** | Med | **A owns `spec/` exclusively.** One hour of undivided attention prevents six hours of merge pain. | A |
| 9 | **Catalog build eats 2GB, laptop swaps during demo** | Low-med | Index built once, committed as ~15MB SQLite. 87MB JSON never loaded at demo time. | B |
| 10 | **Five other teams build the same lactose-free-milk flow** | High | Can't avoid it — it's their example and the safest 30%. **Differentiate entirely on scenarios 1–3. Lead the pitch with the contradiction detector, not the milk.** | All |
| 11 | **Forgetting an award's separate requirement at submission** | Med | A maintains a checklist from H1: Junction form, repo public, Modal URL live, Context.dev endpoint note, Aiven note, Gemini four-question write-up, Nemotron/Cloudinary explicitly not entered. | A |

### Cut order if behind — announce each cut aloud
1. Context.dev (−2h) → 2. ClickHouse analytics view, keep the ledger (−1h) → 3. MCP transport, OpenAPI already carries openness (−1.5h) → 4. Three-axis ranking, **keep the coverage disclosure text** (−1.5h) → 5. Scenario 3 → slide (−1.5h) → 6. Audit-event signing, **keep Offer signing** (−1h) → 7. Next.js → Streamlit (−2h, but spend it)

**Never cut:** the canonical happy path, the policy engine with at least R-01/R-02/R-03/R-07, the approval screen, the human-readable audit narrative. **Those four are 70% of the rubric and were green at H9.**

## Two things to settle before H0
1. **`allergenPolicy` has no default.** Forcing the caller to state it is a defensible safety stance and a pitch point, but it makes the API less convenient and a judge could read it as friction. Agree or not?
2. **Scenario 10 (agent-to-agent trust handshake)** is the only one engaging their "who owns the customer relationship" framing head-on, but was ranked Tier 2 because the live API provably ignores `customer`, making it our layer rather than theirs. **Swap it for scenario 3 (variable-weight) if you think the mentors reward protocol ambition over data rigour** — judgement call, no signal on the panel.
