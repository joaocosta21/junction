# Pitch, video and submission drafts

**Drafts for the team to rewrite.** Every number comes from the replay capture of Saturday 14 Nov 2026, 02:52 Valio time, as `docs/DEMO.md` gives it; the end-to-end tests check those numbers. The live mock gave the same results for all three scenarios at 08:12 that morning (`docs/DEMO.md`). Limits and approver names are illustrative and ours: say so when they appear.

The five criteria, from `AIMO/CHALLENGE.md`: **30%** working end-to-end demo · **20%** precise match to what the buyer asked · **20%** autonomy and controls · **15%** exceptions · **15%** openness and path to production.

---

## Three candidate punchlines

1. **"The agent proposes, the wholesaler's gateway decides: fixed-price orders from Valio Aimo, within the agent's authority or with a human's signature."**
2. **"An open front door for purchasing agents: every claim checked, every exclusion explained, every decision on the record."**
3. **"Purchasing agents can order from Valio Aimo today, and everyone can see what they were allowed to decide."**

Our pick to start from: 1. It names the split that the 20% controls criterion scores, and it says "fixed-price orders", the brief's own words.

---

## The 3-minute pitch

Stage pitch: 3 minutes, then 3 minutes of questions. Run in replay from an empty database, scenarios in the order 1, 2, 3 (see `docs/DEMO.md`, "Before you start").

| Time | Beat | What to show | What to say (draft) | Criterion |
|---|---|---|---|---|
| 0:00–0:20 | The problem | Title slide | "Valio Aimo serves more than 20,000 professional kitchens. Soon their buyers send agents, not people. The question is what an agent may see, decide and be trusted with, before someone else's platform answers it for Valio." | Problem fit |
| 0:20–0:35 | What we built | `/`, the two agents | "A gateway any purchasing agent can call, by REST or MCP. The agent's authority is a buyer profile: the hotel may order alone up to €750." | 20% controls |
| 0:35–1:10 | Scenario 1 | Summary strip, options, exclusions | "1,000 litres of lactose-free milk by Monday. Three confirmed milks cover it, €2,580.64. The cheapest milk, €1,010, has no confirmed stock: it is offered, but only a human can pick it. Nineteen products are excluded, each with its reason: passed cut-offs, a portion pack, one not deliverable." | 30% · 20% match · 15% |
| 1:10–1:30 | The approval | Approval card, then Approve | "€2,580 is above the agent's limit: rule P-01, the purchasing manager decides. The agent cannot approve its own order; the gateway refuses it." | 20% controls · Core 3 |
| 1:30–1:50 | Scenario 2 | Green outcome | "An allergy ward: no milk, no gluten, confirmed data only. 41 products are excluded. One soya drink states free-from milk and gluten, every claim is confirmed, €402 is within its limit: the agent orders alone." | 20% autonomy |
| 1:50–2:10 | Scenario 3 | Ranked substitutes | "A product with no confirmed stock. Two substitutes Valio itself lists add gluten. The gateway shows them and never lets them be ordered, for any buyer." | 15% exceptions |
| 2:10–2:35 | Audit trail | Order record, then the supplier tab | "Every step is one sentence, hash-chained, in an open event format. Valio sees what was asked of its data and what was ordered, without the buyer's limits or names." | 20% auditable |
| 2:35–3:00 | Open and next | `/openapi.json`, `/assumptions` | "OpenAPI, MCP, CloudEvents, problem details, GS1 allergen codes. Every assumption is on one page. Next: an order message in an open e-procurement format, and real customer limits." | 15% openness |

### Optional beats, once their parts are on the deployed app

Each can replace a beat above; none is in the 3-minute plan yet.
- **The dietitian's evidence card** (built and wired, S2). The hotel asks for 100 L of Elovena barista oat drink `469512` without milk. Valio's data says nothing about milk, so P-04 alone sends it to the dietitian, whose card shows the maker's page: *Maidoton*, milk-free, labelled as not Valio data. "The web informs the human who signs; it never makes the order go through." 20% controls.
- **A photo of an order list, or an order in Finnish** (being added, T18). Gemini transcribes the photo, the transcription is shown, then the same parser and text check read it. 20% match. <!-- check: T18 -->
- **"My kitchen"** (being added, FEAT-1). Raise the per-order limit to €3,000 and scenario 1 is ordered by the agent alone; set it back to €750 and it goes to the purchasing manager. The fixed rules stay on whatever is set. 20% controls, Core 3. <!-- check: FEAT-1 -->

### Likely questions, and the short answer

- **"Is the model deciding?"** No. Gemini reads the sentence and chooses which function to call. Prices, quantities, allergen checks and verdicts come from tested code, and the trail names the rule.
- **"Why would you not order the €1.01 milk?"** Valio reports 9,999,999,999 units, which Valio told us in person means the stock is not known. It is offered as a full option; ordering it always needs a human (rule F-01).
- **"Are these real limits?"** No. The mock has no customer limits, so both profiles are ours and labelled as illustrative. We asked Valio what real customers set (`AIMO/BOOTH-QUESTIONS.md`, Q7).
- **"What does 'ordered' commit?"** Nothing yet: the mock has no order endpoint. The record keeps the lines, the prices with their validity and the stock statements it relied on. Mapping it to an open order message is our first next step.
- **"Why is a product named gluten-free rejected?"** `471881` declares cereals containing gluten. The declaration counts, not the name or the claim.
- **"Does it work on live data?"** Yes. At 08:12 on 14 Nov, six live calls gave the same products, prices, verdicts and rules as the capture. We demo in replay so the outcome cannot move with the stock.
- **"Partial availability?"** Ask for 1,500 litres: confirmed stock covers 1,133 L (75.5%), below the hotel's 90% minimum, so rule P-03 fires as well (on an empty order book; after other orders that day, P-02 can fire too).
- **"What if Valio's data says nothing about an allergen?"** Unknown, never safe: under a strict rule it goes to the dietitian (P-04). The approval card shows what the maker's web page says, labelled as not Valio data, found through Context.dev; it never changes the verdict.
- **"Standing orders? Recipes?"** Not built. Recipes belong to the buyer's agent, which sends the gateway a request with several lines. Standing orders with a drift check are a next step on `/assumptions`.

---

## The 2:00 video: shot list

Recorded from the running app in replay, from an empty database. Strictly 2:00 or less. Screen capture with a voice-over; captions carry the numbers.

| # | Time | Shot | Voice-over (draft) | Caption |
|---|---|---|---|---|
| 1 | 0:00–0:08 | Title card: name and punchline | "Purchasing agents are coming to food-service wholesale." | Trusted Trade Agents |
| 2 | 0:08–0:18 | `/`, the two agent cards | "This gateway lets any buyer's agent order from Valio Aimo, within an authority the buyer sets." | Illustrative profiles |
| 3 | 0:18–0:40 | Click Scenario 1; summary strip; scroll the two options | "A thousand litres of lactose-free milk by Monday. Three confirmed milks cover it. The cheapest has no confirmed stock, so only a human may choose it." | €2,580.64 confirmed · €1,010.00 not confirmed |
| 4 | 0:40–0:50 | Excluded products, the first rows | "Every product left out says why." | 19 excluded, each with a reason |
| 5 | 0:50–1:05 | Approval card; type a note; Approve | "Above the agent's €750 limit, so the purchasing manager decides. The agent cannot approve its own order." | Rule P-01 · F-06 |
| 6 | 1:05–1:20 | Order record; audit trail; switch to the supplier tab | "Each step, one sentence, hash-chained. Valio sees its own view, without the buyer's limits." | 9 events · chain verifies |
| 7 | 1:20–1:35 | Click Scenario 2; green outcome | "An allergy ward: no milk, no gluten, confirmed data only. Every claim confirmed, within its limit: the agent orders alone." | €402.00 · ordered by the agent |
| 8 | 1:35–1:48 | Click Scenario 3; ranked substitutes | "Two substitutes Valio lists add gluten. They can never be ordered." | Fails the allergen rule |
| 9 | 1:48–2:00 | `/openapi.json`, then `/assumptions` | "Open standards, every assumption written down. Ready for any agent." | OpenAPI · MCP · CloudEvents · GS1 |

Keep a second take as a backup. The video must be publicly viewable (YouTube or Vimeo).

---

## Submission form: draft text

Fields from the checklist in `CLAUDE.md`. Fields that need a person's details are left as placeholders.

**Project name** (draft): Trusted Trade Agents

**Punchline** (draft): The agent proposes, the wholesaler's gateway decides: fixed-price orders from Valio Aimo, within the agent's authority or with a human's signature.

**Description** (draft):
> Trusted Trade Agents is a gateway that makes Valio Aimo readable and orderable by any purchasing agent, over REST (OpenAPI 3.1) and MCP. An agent sends a request such as "1,000 litres of lactose-free milk by Monday". The gateway searches the catalog, fetches live price and availability, and returns an offer with up to three options. Each claim on each line says whether Valio's data confirms it (price, quantity, delivery date, allergens, origin), and every product left out says why: a passed cut-off, unknown stock, a declared allergen, a portion pack.
>
> A policy of fixed rules plus a buyer profile decides whether the agent may order alone or a human must sign: spend limits, minimum fill, allergen rules, how far a substitute may differ. Unknown stock always goes to a human, and an agent can never approve its own order. Substitutes are ranked good-better-best and must never add an allergen the original does not declare.
>
> Every step is written as a CloudEvents event with one readable sentence, hash-chained, with one view for the buyer and one for Valio Aimo. When Valio's data says nothing about an excluded allergen, the dietitian who must sign sees what the manufacturer's own web page says, labelled as not Valio data. A Gemini agent reads the buyer's words into the typed request, every reading checked against the text, and drives the flow through the same functions; it never sets a price, a quantity or a verdict. Every assumption we made about the mock is listed with its reason on an assumptions page.

**Challenge:** Valio Aimo — "Trusted Trade Agents". Tech awards (the team decides): Google DeepMind — Best Use of Gemini API; Best Use of Modal; Context.dev (write-up in `docs/AWARDS.md`); Aiven, once its part is on the deployed app. <!-- check: S1 -->

**Technologies used** (draft): Python 3.13, FastAPI, Pydantic v2, Uvicorn, SQLite, Jinja2, httpx, PyYAML, Google Gemini API (`google-genai`, `gemini-3.6-flash`), Model Context Protocol (official Python SDK), Modal, Context.dev Answers API, Aiven for PostgreSQL (psycopg 3), OpenAPI 3.1, JSON Schema 2020-12, CloudEvents 1.0, RFC 9457 problem details, GS1 allergen code lists, pytest, ruff.

**Demo link:** https://joaocostared--trusted-trade-agents.us-east.modal.run

**Source code link and publicity:** _the GitHub repository; public, MIT licence_. Before it goes public, decide whether Valio's datasets and recorded answers may stay in it (`AIMO/BOOTH-QUESTIONS.md`, "Ask any Valio person").

**Pitch video:** _YouTube or Vimeo link, 2:00 or less, public_

**Pitch deck:** _PDF_

**Credit preference, team phone numbers, Discord username:** _filled in by the team_

**Status:** set to **FINAL** before Sunday 15 Nov, 10:00.
