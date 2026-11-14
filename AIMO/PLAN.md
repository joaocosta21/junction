# AIMO — build plan (Saturday 14 Nov → Sunday 15 Nov 10:00)

Rewritten on Saturday 14 Nov after the API retest and a re-read of the problem statement. **Earlier versions treated the mock's behaviour as faults to expose ("traps", a "contradiction detector"). That was the wrong frame; see §1.** Supersedes [PLAN-30H-SUPERSEDED.md](PLAN-30H-SUPERSEDED.md).

---

## 0. The score, and what we build for each point

Criteria are verbatim from the Junction platform ([CHALLENGE.md](CHALLENGE.md)). Prizes €4,000 / €2,000 / €1,000.

**The field: 105 teams registered for this challenge (published 14 Nov), the largest at the event, for three paid places.** Most will build the milk request as a happy-path flow. Judges will have little time per team, so the offer screen must show in its first seconds what the others miss: what is confirmed, what is not, and what was excluded and why.

| Weight | Criterion (their wording) | What we build for it |
|---|---|---|
| **30%** | **Working end-to-end demo** — "The solution runs through a full request → lookup → order/approval flow in the mocked environment, not just isolated pieces." | One continuous flow: pasted request → structured request → search → offer → order → approval → audit record. |
| **20%** | **Solving the problem and user need** — "how Precisely the agent matches what the buyer actually asked for, with the least manual correction needed." | Constraint extraction (product type, quantity in litres or kg, date, dietary and allergen needs) and an offer that reports each constraint as met, not met or unverified. |
| **20%** | **Autonomy and controls** — "Quality of the guardrails design. What the agent can decide alone, what needs human sign-off, and how decisions are logged and auditable." | `policy.yaml`, a human approval panel, and an audit log with one readable sentence per decision. |
| **15%** | **Robustness to exception situations** — "Handling of partial availability, substitutions and delivery constraints beyond the happy path." | The response logic in §2: not deliverable or out of stock → substitute; not enough stock → combine products; cut-off passed or quantity not confirmed → next option, with the reason stated. |
| **15%** | **Openness and credible path toward production** — "Open, documented standards rather than a proprietary format, clear visibility of assumptions, well-justified technical choices, and a credible view of next development steps" | Auto-generated OpenAPI for the gateway, an MCP tool surface, GS1 allergen codes, and an "Assumptions & next steps" page. |

### What the brief asks, and our piece for each

| Brief | Our piece |
|---|---|
| **Core 1** — "a structured way for an external agent to search for and retrieve what's available and at what price" | `search` (filter the static catalog) and `offer` (live price and availability for the narrowed set) |
| **Core 2** — "a defined interaction for moving from inquiry to commitment, based on fixed prices rather than a negotiated quote" | `offer` returns a fixed price with its validity and a verification status per claim; `order` commits it. The mock has no order endpoint, so the order record is ours. |
| **Core 3** — "what the agent may decide on its own, and what must go to a human for sign-off" | Policy engine and approval panel |
| Optional — delivery time & sustainability comparison | Labels, delivery reliability and carbon shown per option when present (Tier 2) |
| Optional — substitution and other exception handling | Response logic, §2 |
| Optional — traceability and explainability | Audit log |
| Trust protocol · guardrails model · response logic · audit trail | Verification status (§2) · `policy.yaml` · §2 with good-better-best ranking · audit log |

**The flow they describe:** a buyer's agent sends "I need 1,000 litres of lactose-free milk by Monday…"; "Your solution returns products, prices and availability in structured form; the agent places the order within its authority or sends it to a human for approval."

**Not a chatbot** ("This is not about replacing today's e-commerce UI with a chatbot"): the deliverable is a typed interface and an operating model. A working agent demonstrates it.

---

## 1. Working rule

**The mock's behaviour is the scenario, not a fault.** Valio says they bring "availability behaviour" and "delivery lead times". Unknown stock, order cut-offs that have passed, products that cannot be delivered and missing allergen data are the conditions a real purchasing agent meets. We do not report them as bugs or build a feature around catching them. The agent handles each one and says what it did.

Decided on 14 Nov:
- **The order step is ours.** There is no order endpoint by design; we do not ask Valio whether one exists.
- **Quantity not confirmed:** the agent suggests the best option with confirmed stock and names the unconfirmed product as an alternative. Ordering a product whose quantity is not confirmed always needs human approval. This covers Terminal `999999` and the very large Stock values alike: Valio told us in person on 14 Nov that when the value is very large they do not know the stock.
- **What the agent may order alone is a buyer profile setting** (§9), on top of a few fixed rules that no profile can switch off.
- **Cut-off passed:** `closingTime` is read literally. A product whose cut-off has passed cannot be promised for `availableDate`, so the agent picks another and says why.

---

## 2. Response logic — what the agent does with what the API returns

Shares are from a random sample of 1,000 products on Friday 2026-11-13 at 23:00 server time. They are sample estimates and move with the clock.

| State | How to detect | Share | What the agent does |
|---|---|---|---|
| **Confirmed** | Stock, `closingTime` later than `timeNow`, `availableAmount` between 0 and 999,999 | 25.2% | Suggests it; may order within its authority |
| **Quantity not confirmed** | `availableAmount` ≥ 999,999, cut-off still open | 9.2% | Not the suggestion. Named as an alternative with "quantity not confirmed". Ordering it always needs human approval. |
| **Cut-off passed** | `closingTime` earlier than `timeNow` | 42.3% | Cannot be promised for `availableDate` (spec: "order by closingTime at the latest to receive goods on availableDate"). Not offered for a dated request; named in the explanation. |
| **Out of stock** | a schedule line with `availableAmount` 0 | 2.9% | Exception → substitute |
| **Not deliverable** | empty `scheduleLines` | 20.3% | Exception → substitute |
| **Blocked** | `salesBlock` true | 0.1% | Exception → substitute |

- **Order of evaluation:** Blocked → Not deliverable → Out of stock → Cut-off passed → Quantity not confirmed → Confirmed. In the sample that gives 1 / 203 / 29 / 423 / 92 / 252 products. Before that ordering, 425 products (42.5%) have a passed cut-off.
- In the sample every Terminal product had a passed cut-off, so "quantity not confirmed with an open cut-off" was always a Stock product carrying a placeholder value.
- **Stock placeholder — answered by Valio in person (14 Nov):** when the value is very large they do not know the stock. The Stock values of 9,999,999,999 ÷ base units per sales unit are therefore read exactly like Terminal `999999`: quantity not confirmed. The spec sentence "Stock products are stocked by us, so we know their available quantities" does not hold for these lines. `464306`, the cheapest captured lactose-free milk, is the unconfirmed alternative, not the suggestion.
- **Suggestion plus alternative, not suggestion plus footnote:** return the unconfirmed product as a second structured option that the approver can pick, with its price and status, so no manual correction is needed if the human prefers it.
- **Verification status is our answer to the trust protocol.** For each claim in an offer (price, quantity, delivery date, origin, allergen status) the response says whether Valio's data confirms it, leaves it unknown or rules it out, so the buyer's agent needs no manual check to know what it can rely on.
- **Good-better-best:** rank eligible options by constraint fit first, then verification status, then price.

### What this does to the canonical request
From a capture of 22 of the 35 lactose-free milks in category 10400 on Friday at 21:33. **Re-check on Saturday 09:00 with one call; stock moves.**

| State | Products | Notes |
|---|---|---|
| Confirmed | 3 | `463380` Arla Café milk 1 L UHT, 698 units at €2.65 · `462775` Arla fat-free milk drink 1 L UHT, 51 units at €2.57 · `463203` Arla portion milk 100 × 2 cl, 192 cases (coffee portions, not drinking milk) |
| Quantity not confirmed | 8 | Includes the cheapest of the 24 milks with a captured price, `464306` at €1.01 per litre |
| Cut-off passed | 10 | All Terminal, including both 10 L boxes |
| Not deliverable | 1 | `464440` |

No single confirmed product covers 1,000 litres, so the canonical request is not a pure happy path. With the rule above the agent returns:
- **Suggestion (confirmed):** 698 × `463380` + 51 × `462775` = 749 L for €1,980.77 before tax. It is 251 L short and mixes café milk with fat-free milk.
- **Alternative (quantity not confirmed):** 1,000 × `464306` = €1,010.00 before tax.
- **Excluded, with reasons:** cut-off passed, not deliverable, and portion packs. The portion-pack exclusion is a product-type rule we still have to write down (the request is for drinking milk); if `463203` counted, confirmed stock would total 1,133 L.

Either way the order goes to a human: the suggestion is a partial fill and the alternative is unconfirmed.

---

## 3. Demo scenarios

**Recommended set from the scenario analysis of 14 Nov; the team still has to confirm it (§9).** One flow for every beat — request + buyer profile → search → offer with options and a status per claim → policy decision → order or approval → audit record. Only the input changes, which is what the 30% criterion asks for ("not just isolated pieces"). Stock and prices are from Friday night's captures.

| # | Scenario | What the judge sees | Aimed at |
|---|---|---|---|
| 1 | **Hotel profile — the canonical request.** "1,000 litres of lactose-free milk by Monday" | The offer of §2: a confirmed suggestion (749 L), the cheaper unconfirmed alternative, and the exclusions with reasons. It goes to a human; the approval card shows "order by Sunday 17:00"; the human picks; the order and audit record appear. | 30% · 20% problem · 20% controls · 15% robustness |
| 2 | **Allergy-ward profile — same flow, strict rule.** "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only" | All 35 lactose-free milks are rejected because each declares milk. `468319` Oatly iKaffe is rejected (declares gluten cereals, silent on milk). `464056` Alpro Barista Soya passes: milk and gluten both `FREE_FROM`, 319 units confirmed, €2.14. 200 × €2.14 = €428.00, every claim confirmed, under the spend limit → **the agent orders alone.** | 20% controls (the autonomous path) · 20% problem |
| 3 | **A substitute Valio lists fails the buyer's rule.** `473609` Oddlygood Barista oat drink, gluten-free | Its three listed substitutes are checked against the substitution rule of §7 (no allergen the original does not declare). The original declares oats only. `471690` also declares oats only, so it passes. `471881` and `464320` both add gluten cereals (`AW` `CONTAINS`) and are blocked — `471881` despite carrying a gluten-free claim. | 15% robustness · 20% controls |
| Backup | **Variable-weight beef.** "30 kg beef chuck" | `464744` €15.00/kg, 10 kg confirmed, no allergen data · `466988` €16.88/kg, 109 kg confirmed, 14 allergens `FREE_FROM`. Both have a 3 kg lot step and variable weight, so the order carries a spend ceiling, not an exact total. Use it if milk stock changes and scenario 1 turns into a plain happy path. | 20% problem · 15% robustness |

- **The autonomous path matters.** The 20% criterion scores "what the agent can decide alone" as well as what needs sign-off. Scenario 1 always ends in approval, so scenario 2 is where the agent is seen deciding alone, because every claim is confirmed and the spend is within its limit.
- **Scenario 3 in numbers (catalog):** of Valio's 249 listed substitutes, 37 declare an allergen (`CONTAINS` or `MAY_CONTAIN`) that the original does not; in 20 of those the original has allergen data. Availability for the scenario 3 products has not been captured yet: one call on Saturday morning.
- **Replay mode:** keep saved responses with a pinned clock as a fallback, in case the API is down or the cut-offs pass. If the mock's cut-off times do not roll forward, every product will be past its cut-off after Sunday 17:00.
- **Extra build on top of the core,** estimated by the analysis: about 13.5 person-hours (scenario 1 extras 5.5, scenario 2 3.5, scenario 3 2, backup 1.5, replay mode 1). The allergen and substitute checks are pure functions the biomedical members can write and test.

**Not demoing, and why:** recipe → order (every input would be synthetic and each extra line is another chance of a visible mismatch) · proactive selling (the data has no "new product" signal) · standing-order drift as a headline (the judge would be looking at invented history) · carbon ranking (all 91 products in the milk category carry the same value, 1.1).

---

## 4. Roles

| Who | Owns | Carries |
|---|---|---|
| **CS (tech lead)** | FastAPI gateway (`search`, `offer`, `order`) with auto-generated OpenAPI, the LLM agent with tool use, MCP wrapper, Modal deploy | Backbone of the 30%, most of the 15% openness |
| **Bio 1 — data & rules** | Availability normaliser (the six states of §2), allergen check, pack size, substitute candidates and ranking | 20% problem fit, 15% robustness |
| **Bio 2 — guardrails & audit** | Fixed rules, buyer profiles, policy engine, audit log | 20% autonomy and controls |
| **Bio 3 — arrives Saturday (time to confirm)** | Approval panel (unless it moves to Bio 2, §9), test and exception scenarios, pitch, video | The visible half of the 30% |

Proposals, not yet agreed (§9): Bio 1 writes the normaliser and the allergen check as pure functions with tests and CS only wires them in; the approval panel moves from Bio 3 to Bio 2, because it is the front end of Bio 2's own policy engine and Bio 3 already has about three hours of pitch and video.

Use `offer`, not `quote`, for the middle step: the brief says "fixed prices rather than a negotiated quote".

---

## 5. Schedule

### Carry-over from Friday night — confirm each is done
- Submission draft saved on the Junction platform.
- Credits claimed: Modal (`VVX-2QX-8HW`, $100 per person), Aiven ($50), Gemini (capped at 400 teams).
- Repo skeleton with the gateway calling the mock API.
- **Branches `bio1` (`AIMO/catalog_search.py`) and `bio2` (`AIMO/policy/`: `policy.yaml`, log format, validator) were written on Friday night under the old framing.** Keep the structure and the thresholds (`policy.yaml` already has an autonomous spend cap of €750, a daily cap of €3,000 and a minimum fill ratio of 0.9). Before reuse, change what §1–§2 supersede: the `when_closing_time_contradicted` setting and the `CLOSING_TIME_CONTRADICTED` trust finding (a passed cut-off now excludes the product), the list of three sentinel values and `sentinel_qty_threshold` (now `availableAmount >= 999_999`, always to a human), rule P-05 which blocks `X99` as "unspecified" (GS1: no declarable allergens), and the log format's "data-quality report back to Valio Aimo".

### Overnight build — Saturday about 02:00 to 09:00
Agents build the flow overnight from [SPEC.md](SPEC.md), one task file per agent in [build/tasks/](build/tasks/). State is in [build/STATUS.md](build/STATUS.md); how to start, watch, stop and resume is in [build/RUNBOOK.md](build/RUNBOOK.md). The run ends by writing `build/MORNING.md`: what works, how to run it, what is blocked and what a human must decide.

### Saturday 09:00 — start
- **If the overnight build ran, start from `build/MORNING.md`.** The Fase 1 work below then becomes review, correction and the parts marked blocked.
- **ALL, 15 minutes:** read the top of `CLAUDE.md`, §0–§2 here, and [FINDINGS.md](FINDINGS.md).
- **One live call** for the demo product ids, to refresh the table in §2.
- **Booth:** ask Q1, Q2 and Q7 from [BOOTH-QUESTIONS.md](BOOTH-QUESTIONS.md), then the section "Raised during the overnight build", as soon as a mentor is free. Their answers feed this morning's work.

### Overnight build — result (Saturday 11:15)
Every task is done or blocked; see `build/MORNING.md`. The full flow runs on the pages, over REST and over MCP, and is deployed from `d342dfb` at https://joaocostared--trusted-trade-agents.us-east.modal.run (`deploy/check.py`: 7 of 7). The 13:00 checkpoint below is met: the milk request goes to a human, and scenario 2 is ordered by the agent alone. What Fase 1 and Fase 2 list is built, except what `build/MORNING.md` §8 marks open: a late option when no date can be met, substitutes on product-type lines, and the delivery and sustainability comparison.

### Fase 1 — 09:00–13:00 · the full flow
- **CS:** gateway and agent, request → search → offer → order. Direct tool calls first; the MCP wrapper comes after the checkpoint. Last hour: `modal deploy` to a public URL.
- **Bio 1:** availability normaliser and allergen check, with tests; pack size from the price ratio.
- **Bio 2:** policy engine wired to the gateway; every decision logged as JSON plus one readable sentence.
- **Bio 3:** approval panel (pending approvals and the audit log), unless it moves to Bio 2.

**🚦 13:00 checkpoint — the milk request runs end to end, including one case that goes to a human for approval and one order the agent places alone (scenario 2).** If it is not green, cut everything in §8 Tier 2.

### Fase 2 — 13:30–18:00 · robustness (15%)
- **Substitution:** a requested product is not deliverable or out of stock → ranked substitutes with the trade-off explained. A substitute outside the buyer's stated preferences always goes to a human.
- **Partial availability:** stock covers part of the quantity → combine products.
- **Delivery constraints:** cut-off passed → next eligible option, with the reason.
- **CS:** MCP wrapper over the gateway.
- **Mentors:** the rest of the booth questions.

**🚦 18:00 — feature freeze.**

### Fase 3 — 18:30–22:30 · polish and submit
- "Assumptions & next steps" page (the 15% openness): why OpenAPI and MCP, what the mock does not tell us and what we assumed, what is out of scope, next steps.
- Slides, demo video (max 2:00), final submission text, three award write-ups.
- Rehearse the 3-minute pitch twice, plus 3 minutes of questions. Keep a backup video.

**Sunday:** buffer. Submission closes at **10:00**; set it to **FINAL**. Peer review 10:30–14:00, all four present.

---

## 6. Tech challenges we enter

Two awards, each resting on work the rubric needs anyway. Aiven was dropped on 14 Nov: 1.5 hours for an entry our own notes rate as scoring nothing. Storage sits behind an interface, so Postgres can be added if `DATABASE_URL` is set.

| Award | Hours | Integration point | Rubric tie |
|---|---|---|---|
| **Modal** | 1.0 | `modal_app.py` wraps the FastAPI gateway; `modal deploy` gives a public URL at the end of Fase 1. | 30% (a judge-openable demo) and 15% (path toward production). $100 credits per person. |
| **Google Gemini** | 0.5 | Already the agent's model. Structured output turns the pasted request into the typed request, so the schema is the model's output contract. | 20% problem fit. Meets their bar of "beyond simply adding an LLM to an application". |
| ~~Aiven~~ (dropped) | — | The audit log and the order and approval state live in Aiven Postgres. | 20% autonomy and controls ("how decisions are logged and auditable"). |

**Modal deploy note:** the datasets are tracked at the repo root (the copies inside `AIMO/` are gitignored), so the deployed app can read the root copies or a slim index built into the image. Loading the full product file takes about half a second and 0.6 GB, so a slim index is optional.

**How strong these entries are, by the briefs' own bars:** Modal asks for GPU serving, Sandboxes, fine-tuning or batch jobs where "Modal does the heavy lifting"; hosting a gateway is none of those, so this is a weak entry that we keep because we need the public URL anyway. Our own note in `AIVEN-CHALLENGE.md` says swapping local Postgres for Aiven Postgres "will score nothing"; the entry only has a story if the audit trail is shown back from Aiven as something the service enables. Gemini is the strongest of the three.

### Stretch awards — built overnight only if the core flow is green first
Decided by what the start line of the overnight run approves and which values are in `.env` ([build/RUNBOOK.md](build/RUNBOOK.md)). Neither may delay or endanger the core flow; both are the first things cut.

| Award | Task | What it adds | Rubric tie |
|---|---|---|---|
| **Aiven** | [S1](build/tasks/S1-aiven-postgres.md) | Orders and audit trail in Aiven PostgreSQL: the database refuses to change an audit row, and the supplier reads its own view. This is the story the plain "swap the database" entry lacked. | 20% autonomy and controls |
| **Context.dev** | [S2](build/tasks/S2-contextdev-evidence.md) | When a product has no allergen statement, the approval card shows what the manufacturer's page says, with the link. It never changes a verdict. Replaces the earlier idea (resolving code lists), which was dropped. | 20% autonomy and controls; trust protocol |

### Not entering
| Award | Reason |
|---|---|
| NVIDIA Nemotron | Its distinctive capability is vision and document input; this challenge has no images. |
| Gemma | The bar is that an open model matters (fine-tuning, on-device, privacy); nothing here needs it. |
| Cloudinary | Needs visual media and a separate submission form. |
| Oxylabs | Requires buying a $500 plan and cancelling it. |
| Atech / Arduino | Hardware has no role in a procurement interface. |

### Conflicts
- **Modal vs Aiven Runtime:** one hosting story. Modal hosts the app; Aiven provides the database.
- **Gemini vs Gemma vs Nemotron:** one model provider, Gemini.

---

## 7. Facts to encode

Verified against the live API and the full catalog; detail in [FINDINGS.md](FINDINGS.md) and [docs/](docs/). "Sample" means the 1,000-product sample of §2.

| Topic | Fact | What to do |
|---|---|---|
| Availability | Six states (§2) | One normaliser that returns the state |
| Quantity not confirmed | Terminal is always 999999. Stock placeholders equal 9,999,999,999 ÷ base units per sales unit. The largest ordinary Stock value in the sample was 7,389 (39,243 in an earlier capture). | Treat `availableAmount >= 999_999` as a placeholder; never do arithmetic on it. Valio confirmed that a very large value means the stock is not known (§2) |
| Missing fields | Optional fields are left out, never `null` | Use `.get()` |
| Unknown product id | `/api/availability` answers it like a product that cannot be delivered; `/api/price` returns `error: true` | Check ids against the local catalog first |
| Sales unit | The unit on the API line differs from the product file on 7 of 797 sample lines | Price and quantity follow the unit on the API line |
| Dates | `requestedDate` changes nothing; `availableDate` was 2026-11-16 on 767 of the 768 sample lines that carry one | Compare the buyer's needed-by date with `availableDate` ourselves |
| Customer | `customer` changes nothing | Limits live in a buyer profile (§9), with illustrative values labelled as ours |
| Pack size | `catalogPrice ÷ comparisonPrice` gives litres or kg per priced unit; `comparisonPrice` is missing on 20.6% of the sample | Ratio first, then `unitConversions` when its unit is a real volume or weight, then the product name; if still unknown, exclude the product and say why |
| Allergen data | Relations are `CONTAINS`, `MAY_CONTAIN`, `UNDECLARED` (in `allergen`) and `FREE_FROM` (in `nonAllergen`). 46.2% of the catalog and 30.6% of food products have neither group | **Buyer exclusion rule** (proposed, §9): strictness is a required input. Under strict, for each excluded allergen and its sub-codes: an explicit `FREE_FROM` passes automatically; a declared `CONTAINS` is rejected; `MAY_CONTAIN`, `UNDECLARED` or no statement goes to a human. **Substitution rule:** a substitute must not declare (`CONTAINS` or `MAY_CONTAIN`) an allergen the original does not |
| `X99` | GS1: "Does not contain declaration obligatory allergens in the product." | Map it that way; confirm with Valio (booth Q2) |
| Claims are not allergens | All 35 lactose-free milks in category 10400 declare milk as `CONTAINS` | "Lactose-free" filters on `nutritionalClaim`, never on allergens; the offer says "lactose-free, contains milk" |
| Variable weight | 632 products, 628 sold in KG; all 37 in the sample are priced per kg | Human approval until Valio says how they are invoiced (booth Q9) |
| Lot size | 674 products have a real step (1.5 on 62, 1.8 on 17) | Round with `Decimal`; one test |
| Deposits | 506 products carry deposits; the 7 codes cannot be priced | Totals exclude deposits and say so |
| VAT | `vatCode` in the file is unreliable (159 "MEDIUM MEDIUM", absent on 3,068) | Use `tax.taxRate` from `/api/price` |
| Price fields | `Price.value` excludes tax; `PriceWithTax.value` includes it | Two separate types |
| Substitutes | 250 explicit pairs on 189 products; 230 stay in the same category | A seed, not the source. Candidates: same category → same first 4 digits → same first 3 digits; re-check availability of every candidate |
| Optional axes | Delivery reliability 25.2% of products; carbon 62.9% (81.2% of food, 0.4% of non-food); both 17.8% | Show when present, never impute |
| Performance | The product file loads in about half a second, 0.6 GB | Loading at start-up is fine |
| Rate limits | 34 requests in 5 minutes, up to 251 ids each: no 429 | Filter locally, call narrowly, cache, keep a recorded-response fallback |

---

## 8. Priorities

**Mandatory — the three core requirements and the 30%:** lookup · offer and order · human approval · one order placed alone · readable audit log, as one continuous flow, including the partial fill of the canonical request.

**Good to have (the 15% robustness):** substitution with explanation · partial availability beyond the canonical case.

**Tier 2, only if time remains:** delivery time & sustainability comparison.

**Nice to have (backlog, not planned):**
- **Voice input** (speech to text): Gemini transcribes a recording, the text is shown, then the same parser and text check read it, as the photo does (T18). About 1–2 h. Scores weakly: the brief says it is "not about replacing today's e-commerce UI with a chatbot", and Gemini's audio understanding infers responses to English speech only, so spoken Finnish would not work. Text to speech scores on no criterion.

**Cut order if behind — announce each cut aloud:**
1. MCP transport (the auto-generated OpenAPI still carries the openness story)
2. Delivery and sustainability comparison (keep one sentence on what the data covers)
3. Third demo scenario → a slide
4. Substitute ranking tiers → single best substitute

**Status, Saturday 11:15:** everything under "Mandatory" and "Good to have" is built and deployed. Tier 2 is not built: reliability and carbon are loaded and shown on `GET /v1/products/{id}` only. Nothing in the cut order was cut.

**Never cut:** the canonical flow, one order the agent places alone (scenario 2), the policy engine, the approval panel, the readable audit log.

**Removed from the plan:** delivery split across dates (the mock cannot show it) and the "contradiction detector" (replaced by the response logic of §2).

---

## 9. Decisions

**Decided (14 Nov):**
- The framing in §1; the order step is ours.
- Quantity not confirmed: suggest the best confirmed option, name the unconfirmed product as an alternative, and always require human approval before ordering it.
- **The very large Stock values mean "not known".** Valio's answer in person. This closes booth Q3.
- Cut-off passed: read `closingTime` literally (§2).
- The canonical demo follows the same rule: confirmed suggestion, unconfirmed alternative, human approval.
- **What the agent may order alone: two layers.**
  - *Fixed rules, which no profile can switch off:* a quantity that is not confirmed goes to a human; a product that declares an excluded allergen is blocked; a missing fact goes to a human, never to an automatic order; an agent cannot approve its own order.
  - *Buyer profile, set per buyer:* spend limit per order and per day, minimum share of the quantity that must be covered, allergen exclusions and strictness, how far a substitute may differ, and who approves what.
  - **The limit values are illustrative.** `bio2`'s €750 per order, €3,000 per day and 90% were chosen by hand (the file marks them as open team decisions; €750 was picked so that the €1,010 milk order goes to a human). The mock has no customer limits, so they are ours and are labelled as such. Booth Q7 asks Valio what real customers set.

**Defaults taken on 14 Nov (proposed, nobody objected):**
- Stay in Valio Aimo.
- Allergen rules of §7: strictness has no default value; an explicit `FREE_FROM` passes, a declared `CONTAINS` is rejected, anything else goes to a human. For a "no gluten" buyer, oats (`GO`) go to a human.
- Scenario set of §3.
- Tech awards: Modal and Gemini. Aiven dropped (§6).

**Open — need the team:**
1. **Roles for Saturday (§4).** After the overnight build the work is review and correction. Proposal: each person reviews the area they already started — data and allergen rules, policy and audit, approval panel and pitch, gateway and deployment.

**To ask the Junction organisers:** can one project be entered in more than one partner challenge? If yes, adding a second one is better than switching.

**Specified in [SPEC.md](SPEC.md):** request → candidates, offer and order states, policy facts and profiles, the audit trail for two readers, and the assumptions page.

---

## 10. Mentor questions
[BOOTH-QUESTIONS.md](BOOTH-QUESTIONS.md) is the only list. Two-minute cut: Q1, Q2 and Q7 (Q3 was answered on 14 Nov).

---

## 11. Submission checklist (CS owns)
- [ ] Junction submission set to **FINAL**, not DRAFT (closes **Sunday 10:00**)
- [ ] Pitch video **max 2:00**, publicly viewable
- [ ] Pitch deck (PDF)
- [ ] Public GitHub repo (MIT) and the live Modal URL
- [ ] Project name, punchline and description · technologies used · credit preference
- [ ] Challenges selected: Valio Aimo, plus Modal and Gemini
- [ ] `LICENSE` file (MIT) in the repo — there is none yet
- [ ] README says where the datasets are and how to refresh them
- [ ] Gemini write-up, the four points their brief asks for: the problem and why it matters · how the Gemini API is integrated · what makes the use innovative · why Gemini is an important part of the solution
- [ ] Modal note: what it powers
- [ ] Team phone numbers and Discord username
- [ ] **All four present for peer review, Sunday 10:30–14:00**
