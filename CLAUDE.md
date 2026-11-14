# Junction 2026 — Project Context

## THE SCORE TO MAXIMISE — never lose sight of this
We are entered in **Valio Aimo — "Trusted Trade Agents"** (€4,000 / €2,000 / €1,000). Every design choice, cut and hour is weighed against these criteria, quoted verbatim from the Junction platform:

| Weight | Criterion | Their wording |
|---|---|---|
| **30%** | Working end-to-end demo | "The solution runs through a full request → lookup → order/approval flow in the mocked environment, not just isolated pieces." |
| **20%** | Solving the problem and user need | "how Precisely the agent matches what the buyer actually asked for, with the least manual correction needed." |
| **20%** | Autonomy and controls | "Quality of the guardrails design. What the agent can decide alone, what needs human sign-off, and how decisions are logged and auditable." |
| **15%** | Robustness to exception situations | "Handling of partial availability, substitutions and delivery constraints beyond the happy path." |
| **15%** | Openness and credible path toward production | "Open, documented standards rather than a proprietary format, clear visibility of assumptions, well-justified technical choices, and a credible view of next development steps" |

**Before proposing or building anything, name the criterion it scores on.** If it scores on none, it is not worth the time.

## What Valio Aimo asks for — anchor every decision here
Full verbatim text: `AIMO/CHALLENGE.md`.

**Core — the solution must enable:**
1. "Product, price & availability lookup: a structured way for an external agent to search for and retrieve what's available and at what price."
2. "Requesting price & availability, then placing an order: a defined interaction for moving from inquiry to commitment, based on fixed prices rather than a negotiated quote."
3. "Permission & human-approval management: what the agent may decide on its own, and what must go to a human for sign-off."

**Optional directions (not required to win):** delivery time & sustainability comparison · substitution and other exception handling · traceability and explainability.

**The flow they describe:** a buyer's agent sends "I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability." — "Your solution returns products, prices and availability in structured form; the agent places the order within its authority or sends it to a human for approval."

**Not a chatbot:** "This is not about replacing today's e-commerce UI with a chatbot. It is about defining how a European food-service wholesaler can be safely and openly readable by autonomous agents – before that interface gets defined by someone else's platform."

**Problems they'd love tackled:** trust protocol (what an agent can trust about stock, price and origin without a manual check) · guardrails model (what needs human sign-off) · response logic (partial availability, "good-better-best" substitution ranking) · audit trail (human-readable log for buyer and Valio Aimo).

### How to think about the mock (corrected 2026-11-14)
- **The mock's behaviour is the scenario, not a fault.** Unknown stock, order cut-offs that have passed, products that cannot be delivered and missing allergen data are the conditions a real purchasing agent meets. We do not present them as bugs. The agent handles each one and says what it did.
- **There is no order endpoint, and that is by design.** The order step, its approval and its record are ours to define. Do not ask Valio whether one exists.
- **Quantity not confirmed** (Terminal `999999`, or the very large Stock values): the agent suggests the best option with confirmed stock and names the unconfirmed product as an alternative. Ordering a product whose quantity is not confirmed always needs human approval. Valio confirmed in person on 14 Nov that a very large value means they do not know the stock, so Stock and Terminal are read the same way.
- **Keep an autonomous path.** The 20% criterion scores what the agent can decide alone as well as what needs sign-off. What the agent may order alone is a **buyer profile** setting (spend limits, minimum fill, allergen rule, substitution scope) on top of fixed rules that no profile can switch off (PLAN §9). Limit values are illustrative and labelled as ours; the mock has no customer limits.
- **`closingTime` is read literally:** the spec says "order by closingTime at the latest to receive goods on availableDate". A product whose cut-off has passed cannot be promised for that date.
- **Allergens:** a `nutritionalClaim` is never an allergen statement (lactose-free milk still contains milk). `X99` is GS1's "Does not contain declaration obligatory allergens". No data means unknown, not safe.
- **Questions for Valio mentors** go in `AIMO/BOOTH-QUESTIONS.md` in one form: context → what we did → what we got → "is that expected, or did we do something wrong?", each with a concrete example.
- **Numbers:** say whether a figure is from the whole catalog (17,546 products) or from a sample of live calls. Never state a sample figure as a catalog fact.

### Where things are
| File | Purpose |
|---|---|
| `AIMO/PLAN.md` | The working plan: rubric mapping, response logic, schedule, tech awards, cut order |
| `AIMO/SPEC.md` | The build contract: interface, data shapes, states, rules. Code follows it |
| `AIMO/build/` | Overnight build: `RUNBOOK.md` (how to run), `STATUS.md` (task board), `tasks/` (one file per agent) |
| `AIMO/CHALLENGE.md` | The problem statement and judging criteria, verbatim |
| `AIMO/BOOTH-QUESTIONS.md` | Questions for the Valio mentors, with examples |
| `AIMO/FINDINGS.md` | Verified facts about the API and data |
| `AIMO/docs/` | Field dictionary and per-file references for the API, product data, code systems and CSVs |

## Hard constraints (disqualification risk)
- **No code written before the event.** All code outside open-source libraries must be written at the hackathon. No pre-existing project, no code tied to an existing company.
- Team size 1–4. Must participate in at least one challenge.
- Submission is MIT-licensed; organizers must be able to access the source.
- Team must attend **live peer reviewing, Sunday Nov 15, 10:30–14:00**, on site. Skipping it = ineligible for the main prize.

## Deadlines
- **Sunday Nov 15, 10:00** — submission form closes automatically. No late submissions.
- Project must be set to **FINAL** (not DRAFT) before the deadline. Drafts are not reviewed. FINAL submissions remain editable until the deadline.
- 10:30–14:00 — peer reviewing. Be at your table; absent teams get marked "not present".
- Top 5 (by peer review) pitch 3 min on stage + 3 min judge Q&A. 7 judges vote.

## Submission checklist
- [ ] Project name, punchline, description
- [ ] Challenge selected
- [ ] Technologies used
- [ ] **Pitch video, max 2:00** — strictly enforced, publicly viewable (YouTube/Vimeo)
- [ ] Demo link
- [ ] Source code link + publicity setting
- [ ] Credit preference
- [ ] Pitch deck (PDF)
- [ ] Team phone numbers
- [ ] Discord username
- [ ] Status set to FINAL

## Junction main-prize criteria (peer review, separate from the Valio Aimo score above)
1. **Innovation** — is it new/different vs. other projects? What specifically distinguishes it?
2. **Impact** — significance of the problem solved, and the *ratio* of people helped to total people affected. Reach matters as much as depth.
3. **Implementation** — realistic, viable, feasible to actually build and deploy.

Partners pick challenge winners/runners-up independently of the peer-reviewed top 5, using the Valio Aimo criteria at the top of this file.

## Working priorities
- A working demo beats a broader but broken scope. Demo-path first, polish later. One continuous request → lookup → order/approval flow is worth 30% on its own.
- Peer reviewers are other hackers seeing the project for ~minutes: the punchline and the demo must land fast.
- Reserve real time Saturday night/Sunday morning for video + deck + submission form. Submission is at 10:00, not after.

## Team
Four people, all from Portugal, all finishing their master's degrees:
- **3 × biomedical engineering**
- **1 × computer science**

`RECOMMENDATION.md` records a later capability update: all four program competently.

- **Implementation bandwidth is still the constraint.** Keep scope narrow and the stack boring and familiar.
- Biomedical backgrounds bring nutrition, physiology and clinical reasoning (useful for the allergen and nutrition rules in the school/hospital scenario) plus signal processing, statistics and experimental method.
- **No Finnish speakers.** Product names are available in English for 99.99% of the catalog, so this is not a blocker here.

## Open questions about us (to fill in)
- Which of us is comfortable with frontend/UI work?
- Do any of us have ML/data experience beyond coursework (PyTorch, sklearn, embeddings)?

## Status
- **Challenge: Valio Aimo — "Trusted Trade Agents". Decided.** Working documents are in `AIMO/`. The other challenge briefs in the repo root and `RECOMMENDATION.md` are kept for reference only.
- **Tech awards entered:** Modal (hosting, the evidence batch, a scheduled witness of the audit trail), Context.dev (manufacturer pages as evidence on allergen doubts) and Aiven (PostgreSQL: an audit trail the database refuses to change, with a read-only view for Valio). Google Gemini was dropped on 14 Nov: the key has no credits and no model is called. What ran and what did not is in `docs/AWARDS.md`; the plan is `AIMO/build/replan/AWARDS-PLAN.md`.
- **Stack:** Python, FastAPI gateway with auto-generated OpenAPI and an MCP surface, a fixed-rules reader for sentences (a model is optional and off), YAML policy engine, human confirmation of every order by default, a shop page at `/shop`. Live mode asks Valio's API per request; the demo runs in replay from a recording at a chosen clock.
- **Submission gotchas:** Cloudinary needs its own separate form. Oxylabs requires buying a $500 plan (free first month with code `JUNCTION2026`) — **cancel it after**. Atech kits are first come, first served at their booth. We enter none of these three.
