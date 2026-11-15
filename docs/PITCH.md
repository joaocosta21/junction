# Pitch, video and submission drafts

**Drafts for the team to rewrite.** First written for Saturday morning's product; its claims were brought to the running system on Sun 15 Nov 2026, about 03:00, in line with `AIMO/PITCH-DECK-REVIEW.md` (sections 1a and 1b), which has the moments to play and the deck's corrections. The text that goes into the form, and the final video shot list, are in `AIMO/SUBMISSION.md`: where this page and that one differ, that one wins. Every number comes from the recordings used in replay (1,163 products recorded on Saturday 14 Nov 2026), at the demo clock (Thursday 12 Nov 2026, 14:15), measured through `/shop` as `docs/DEMO.md` gives it; none is a figure of the whole catalog. The answers were not compared with the live mock since Saturday morning, when the product was another. Limits and people's names are illustrative and ours: say so when they appear.

The five criteria, from `AIMO/CHALLENGE.md`: **30%** working end-to-end demo · **20%** precise match to what the buyer asked · **20%** autonomy and controls · **15%** exceptions · **15%** openness and path to production.

---

## Three candidate punchlines

1. **"The agent prepares the order. A person confirms it."** (the gateway's own sentence; with the sub-line "An open gateway that lets any purchasing agent read Valio Aimo's prices and stock, prepare an order, and stop for a person exactly where it should.")
2. **"An open front door for purchasing agents: every claim checked, every exclusion explained, every decision on the record."**
3. **"Purchasing agents can read Valio Aimo's prices and stock today and prepare an order, and everyone can see what they were allowed to decide."**

Our pick to start from: 1. It names the split that the 20% controls criterion scores. The earlier wording, "the wholesaler's gateway decides", was dropped: the wholesaler decides nothing here, the buyer's own person confirms, and no order reaches Valio Aimo ("ordered" is a record in the gateway's order book).

---

## The 3-minute pitch

Stage pitch: 3 minutes by the Junction rules, then 3 minutes of questions; João's figure for the deck is 5 minutes, and the plan for 5:00 is in `AIMO/PITCH-DECK-REVIEW.md`, section 4. Run in replay at the demo clock on `/shop`, from an empty order book ("Start again"), scenarios in the order 1, 2, 3 (see `docs/DEMO.md`, "Before you start").

| Time | Beat | What to show | What to say (draft) | Criterion |
|---|---|---|---|---|
| 0:00–0:20 | The problem | Title slide | "Valio Aimo serves more than 20,000 professional kitchens. Soon their buyers send agents, not people. The question is what an agent may see, decide and be trusted with, before someone else's platform answers it for Valio." | Problem fit |
| 0:20–0:35 | What we built | `/shop`, the four customers | "A gateway any purchasing agent can call, by REST or MCP. What the agent may decide is the buyer's own setting: by default it prepares the order and a person confirms; the hotel can let it order alone up to €750." | 20% controls |
| 0:35–1:10 | Scenario 1 | Summary strip, options, exclusions | "1,000 litres of lactose-free milk by Monday. It does not pretend: 435 litres are confirmed, €1,083.39, and 565 are not. The cheapest milk covers all of it for €1,010, but Valio Aimo does not confirm its stock. A third option fills the 1,000 litres from confirmed stock with 565 litres of coffee milk, named as a substitute, €2,580.64. A person chooses. Two products are left out, each with its reason: a portion pack, one that cannot be delivered." | 30% · 20% match · 15% |
| 1:10–1:30 | The approval | Approval card, then Approve | "€1,083.39 is above the €750 limit and covers less than 90% of what was asked: two rules, and Hanna Laine confirms. Over REST and MCP an agent's token cannot approve: the gateway refuses it and logs the attempt." | 20% controls · Core 3 |
| 1:30–1:50 | Scenario 2 | The prepared order, then Confirm | "An allergy ward: no milk, no gluten, confirmed data only. 41 of 51 products are left out. One soya drink states free-from milk and gluten and every statement is confirmed, €402: the order is prepared and Jussi Nieminen confirms it with one click. If the ward switches ordering alone on, the agent orders it and says why it was allowed." | 20% autonomy |
| 1:50–2:10 | Scenario 3 | Ranked substitutes | "A product with no confirmed stock. Two substitutes Valio itself lists declare gluten, which the product asked for does not: they fail the allergen rule and can never be ordered as substitutes, for any buyer. A substitute that is not like for like always goes to a person." | 15% exceptions |
| 2:10–2:35 | Audit trail | Order record, then the supplier tab | "Every step is one sentence, hash-chained. Valio Aimo reads the same log in its own view: what was asked of its data, every rule that fired and what was ordered, without the buyer's limits, allergens or names." | 20% auditable |
| 2:35–3:00 | Open and next | `/openapi.json`, `/assumptions` | "OpenAPI, MCP, problem details, signed offers and orders, GS1 allergen codes. Every assumption is on one page, with the next steps. Next: an order message Valio Aimo's systems can take, customers' real limits and people, and Valio Aimo signing its own statements of price, stock and origin." | 15% openness |

### Optional beats

Each can replace a beat above; none is in the 3-minute plan yet. All are on `/shop`. Ranked moments with fallbacks: `AIMO/PITCH-DECK-REVIEW.md`, section 1a.
- **The dietitian's evidence card.** Kilo School asks for 20 L of almond drink. Valio's data does not rule out tree nuts for `465793`, so rule P-04 sends it to the school's dietitian, Riikka Mäkelä, whose card shows the maker's page on alpro.com: it names almond, labelled as not Valio Aimo data. At the hotel, which has no dietitian, the same kind of question (the oat drink `469512`, milk not stated) is asked of Hanna Laine on the result, with the maker's page beside it (*Maidoton*, milk-free). "The web informs the person who decides; it never makes the order go through." 20% controls.
- **Lactose-free is not milk-free.** City Hospital, Ward 4 asks for 100 L of lactose-free milk: 26 products checked, 26 refused, each because it declares milk. 20% controls · 15% exceptions.
- **302 litres, 303 litres.** With ordering alone switched on at the hotel (`/shop` → Settings): 302 L, €748.96, is ordered by the agent; 303 L, €751.44, waits for Hanna Laine, because of the €750 limit. The switch itself is an event in the log. 20% controls, Core 3.
- **Next steps, not beats: a photo of an order list, an order in Finnish.** Reading a photo needs a model to be configured. Read by the fixed rules, a sentence in Finnish or Swedish is told that they read English only.
- **A dish becomes one order.** Kallio Bakery types "A chocolate cake for 20 by Monday": a recipe of ours (illustrative) becomes 7 request lines and one offer; the lines with confirmed stock are the first option and the owner confirms. Figures: `docs/DEMO.md`, scenario 7. 30% end to end.
- **A standing order that drifts.** On `/shop` → Standing orders, the hotel's weekly milk renewed at the stored 100 L is prepared for a person (€248.00); at a typed 290 L, €719.20 and still under €750, rule P-08 asks: "290 L this week against a median of 100 L over the last 6 renewals". The past weeks are synthetic and labelled. No scheduler renews it: a person asks. 20% controls.
- **A preference changes the choice.** "100 litres of oat drink by Monday, most reliable delivery" (hotel) puts the 100%-reliable oat drink first at €140.00 and keeps the cheapest, €133.00, on the table: "€7.00 more than the cheapest confirmed option, for a delivery reliability of at least 100% instead of unknown". Both are prepared for a person. 20% match · optional direction "delivery time & sustainability".

### Likely questions, and the short answer

- **"Is a model deciding?"** No. A model may read the sentence, when one is configured; the gateway checks that reading against the text and refuses one that does not match. When no model answers, a recording or the fixed rules read it, and the rules ask a question when they cannot. Every answer says who read it. Prices, quantities, allergen checks and verdicts come from tested code, and the trail names the rule. `/healthz` says what reads sentences on the link.
- **"Why would you not order the €1.01 milk?"** Valio reports 9,999,999,999 units, which Valio told us in person means the stock is not known. It is offered as a full option; ordering it always needs a human (rule F-01).
- **"Are these real limits?"** No. The mock has no customer limits, so all four profiles are ours and labelled as illustrative. We asked Valio what real customers set (`AIMO/BOOTH-QUESTIONS.md`, Q7).
- **"What does 'ordered' commit?"** Nothing yet: the mock has no order endpoint. The record keeps the lines, the prices with their validity and the stock statements it relied on. Mapping it to an open order message is our first next step.
- **"Why is a product named gluten-free rejected?"** `471881` declares cereals containing gluten. The declaration counts, not the name or the claim.
- **"Does it work on live data?"** Live mode asks Valio Aimo's API for each request (`TTA_MODE=live`); it last answered an offer on 14 Nov. Tonight's answers were measured in replay only and were not compared with the live mock. We demo in replay, at a clock we chose, so the outcome cannot move.
- **"Partial availability?"** The 1,000 litres: confirmed stock of the milk asked for covers 435 L (43.5%), below the hotel's 90% minimum, so rule P-03 fires beside P-01 (on an empty order book; after other orders that day, P-02 can fire too). A request that cannot arrive by its date is answered with the earliest date as an alternative a person accepts.
- **"Can the agent order alone?"** Yes, when the buyer switches it on, no rule fires and every statement of every line is confirmed. It is off for the four demo customers, so over REST and MCP every demo order waits for a person; on `/shop` → Settings it can be switched on: 302 L is ordered by the agent, 303 L goes to a person.
- **"What stops an agent approving its own order?"** Over REST the approval route refuses an agent's token (403) and logs the attempt; MCP has no approval tool. The demo page has no login: it acts as the customer's person. In production no page is mounted and people sign with their own tokens.
- **"Can the log and the signature be trusted?"** A changed, inserted or removed event is detected and named. A cut tail is caught only by someone who kept the head. The signature says this gateway answered this record, with a demo key; it is not Valio Aimo's, and a stored order edited in the database would still get a valid one today. Next: each stored order tied to its audit entry, and Valio Aimo signing its own statements.
- **"What if Valio's data says nothing about an allergen?"** Unknown, never safe: under a strict rule it goes to a person (P-04): the dietitian at the ward and the school, the person who orders at the hotel and the bakery. The card shows what the maker's web page says, labelled as not Valio Aimo data, from a page recorded through Context.dev; it never changes the verdict.
- **"Standing orders? Recipes?"** Both are on `/shop`: a standing order renewed at a typed quantity (rule P-08 on drift) and a dish typed as a sentence (recipe logic, rule F-09). The recipe table and the demo's past weeks are ours, labelled illustrative and synthetic. Next steps: a scheduler, recipes around a seasonal ingredient, a watch that runs before the kitchen asks; none exists today.

---

## The 2:00 video: shot list

Recorded from the running app in replay at the demo clock, on `/shop`, from an empty order book. Strictly 2:00 or less. Screen capture with a voice-over; captions carry the numbers. **A draft: the shot list to record from is `AIMO/SUBMISSION.md`, section 6.**

| # | Time | Shot | Voice-over (draft) | Caption |
|---|---|---|---|---|
| 1 | 0:00–0:08 | Title card: name and punchline | "Purchasing agents are coming to food-service wholesale." | Trusted Trade Agents |
| 2 | 0:08–0:18 | `/shop`, the four customers | "This gateway lets any buyer's agent read Valio Aimo's prices and stock and prepare an order, within an authority the buyer sets." | Illustrative profiles |
| 3 | 0:18–0:40 | Type scenario 1; the answer; scroll the three options | "A thousand litres of lactose-free milk by Monday. 435 litres are confirmed, 565 are not, and it says so. The cheapest milk has no confirmed stock; a third option completes the order with coffee milk, named as a substitute." | 435 L confirmed €1,083.39 · 1,000 L not confirmed €1,010.00 · 1,000 L with a substitute €2,580.64 |
| 4 | 0:40–0:50 | Products left out | "Every product left out says why." | 2 left out, each with a reason |
| 5 | 0:50–1:05 | "Confirm order" on the result | "Above the €750 limit and below 90% of the quantity, so Hanna Laine decides. Over REST and MCP an agent cannot approve its own order." | Rules P-01, P-03 · F-06 |
| 6 | 1:05–1:20 | The order's log; switch to "What Valio Aimo sees" | "Each step, one sentence, hash-chained. Valio Aimo sees its own view, without the buyer's limits." | 11 events · chain verifies |
| 7 | 1:20–1:35 | Type scenario 2; Confirm | "An allergy ward: no milk, no gluten, confirmed data only. Every statement confirmed: the order is prepared, and one click by Jussi Nieminen places it." | €402.00 · confirmed by a person (ordered by the agent only if the ward switches that on) |
| 8 | 1:35–1:48 | Type scenario 3; the substitute options | "The product asked for has no confirmed stock. A substitute that is not like for like always goes to a person; one that adds an allergen can never be ordered as a substitute." | Not like for like → a person |
| 9 | 1:48–2:00 | `/openapi.json`, then `/assumptions` | "Open standards, every assumption and next step written down. Ready for any agent." | OpenAPI · MCP · problem details · GS1 |

Keep a second take as a backup. The video must be publicly viewable (YouTube or Vimeo).

---

## Submission form: draft text

Fields from the checklist in `CLAUDE.md`. Fields that need a person's details are left as placeholders.

**Project name** (draft): Trusted Trade Agents

**Punchline** (draft): The agent prepares the order. A person confirms it. An open gateway that lets any purchasing agent read Valio Aimo's prices and stock, prepare an order, and stop for a person exactly where it should.

**Description** (draft):
> Trusted Trade Agents is a gateway that makes Valio Aimo readable by any purchasing agent, over REST (OpenAPI 3.1) and MCP. An agent sends a request such as "1,000 litres of lactose-free milk by Monday". The gateway searches the catalog, looks up price and availability (from Valio Aimo's API in live mode; from a recording in the demo), and returns an offer with up to three options. Each claim on each line says whether Valio's data confirms it (price, quantity, delivery date, allergens, origin), and every product left out says why: a passed cut-off, unknown stock, a declared allergen, a portion pack.
>
> A policy of fixed rules plus a buyer profile decides whether the agent may order alone or a person must confirm: spend limits, minimum fill, allergen rules, how far a substitute may differ. By default a person confirms every order; ordering alone is the buyer's own switch. Unknown stock always goes to a person, and over REST and MCP an agent can never approve its own order. "Ordered" is a signed record in the gateway's order book: the order step is ours to define, and it commits nobody. Substitutes are ranked good-better-best and must never add an allergen the original does not declare.
>
> Every step is written as an event with one readable sentence, hash-chained, with one view for the buyer and one for Valio Aimo. When Valio's data says nothing about an excluded allergen, the person who must decide (a dietitian at the ward and the school) sees what the manufacturer's own web page says, labelled as not Valio Aimo data. A buyer's sentence is read into the typed request by a model when one is configured, with fixed rules as its check and its fallback: a reading that does not match the text is refused, the rules read when no model answers and ask a question when they cannot, and every answer says who read it. Nothing but tested code sets a price, a quantity or a verdict. Every assumption we made about the mock is listed with its reason on an assumptions page, with the next steps a pilot would take.

**Challenge:** Valio Aimo — "Trusted Trade Agents". Tech awards entered: Modal, Context.dev and Aiven; what ran for each and what did not is in `docs/AWARDS.md`. Google's Gemini award is not entered.

**Technologies used** (draft): Python 3.13, FastAPI, Pydantic v2, Uvicorn, SQLite, Jinja2, httpx, PyYAML, an optional model reader (Google Gemini API through `google-genai`, or any OpenAI-compatible endpoint), Model Context Protocol (official Python SDK), Modal, Context.dev Answers API, Aiven for PostgreSQL (psycopg 3), OpenAPI 3.1, JSON Schema 2020-12, CloudEvents 1.0 (the envelope audit events are stored in), JSON Web Signature (Ed25519), RFC 9457 problem details, GS1 allergen code lists, pytest, ruff.

**Demo link:** https://joaocostared--trusted-trade-agents.us-east.modal.run/shop (the link answers `/shop` only once the night's code is redeployed; at 00:30 on 15 Nov it still ran Saturday morning's code)

**Source code link and publicity:** _the GitHub repository; public, MIT licence_. Before it goes public, decide whether Valio's datasets and recorded answers may stay in it (`AIMO/BOOTH-QUESTIONS.md`, "Ask any Valio person").

**Pitch video:** _YouTube or Vimeo link, 2:00 or less, public_

**Pitch deck:** _PDF_

**Credit preference, team phone numbers, Discord username:** _filled in by the team_

**Status:** set to **FINAL** before Sunday 15 Nov, 10:00.
