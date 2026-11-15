# Submission — what goes in the form

The form closes **Sunday 15 Nov, 10:00**, automatically. Set the project to **FINAL** early (a FINAL project stays editable until the deadline). Peer reviewing is 10:30–14:00 at our table.

Rewritten Sun 15 Nov after three independent checks of the text against the final code (`b567e5f`): the judging criteria, the four problems, the core and optional items; the six example scenarios, each run; the three partners' briefs. Figures come from the recording of Valio Aimo's mock that the demo replays (1,163 products), never from the whole catalog (17,546), unless said.

## 1. Each field

| Field | Limit | What to enter | Still to do |
|---|---|---|---|
| Project name | 30 | The one you typed, or `Trusted Trade Agents` (20) | — |
| Punchline | 200 | Section 2 | Paste |
| Description | 5,000 | Section 3 (4,922 characters; 4,972 if the form counts a line break as two) | Paste, then read the preview: the form may not render markdown |
| Challenge | — | Valio Aimo — "Trusted Trade Agents" | Select |
| Project demo | link | `https://joaocostared--trusted-trade-agents.us-east.modal.run/shop` | Live with the final code; 10 of 10 deployment checks passed |
| Source code | link | `https://github.com/joaocosta21/junction` | **Not ready until pushed and public:** section 5, step 3. Context.dev's brief requires a GitHub repository |
| Video | link, max 2:00, public | Record from `AIMO/VIDEO-SHOTLIST.md` | Record, upload to YouTube or Vimeo, check the link in a private window |
| Other link | link | `https://joaocostared--trusted-trade-agents.us-east.modal.run/docs` (the typed API a judge can try) | — |
| Presentation | PDF/PPTX, 20 MB | Deck v5 with the three rows of `AIMO/PITCH-DECK-REVIEW-V5.md` | On page 12 use **30 pages shown, 39 rejected, 23 with no page, of 92** (not 29 and 40). Export to PDF on the machine the deck was made on (it needs the font Inter), look at every page |
| Tech challenges | — | Context.dev, Aiven, Modal: section 4 | Select |
| Team phones, Discord, credit preference | — | Yours | Fill in |
| Status | — | FINAL | Set early; re-open the page and check it says FINAL |

## 2. Punchline (200 characters at most)

Recommended (168 characters; it uses the brief's own words: fixed prices, authority, sign-off, logged):

> An open gateway: any purchasing agent reads Valio Aimo's fixed prices and stock, orders within its authority, and a person signs off the rest. Every decision is logged.

Alternative (147 characters):

> An open gateway that lets any purchasing agent read Valio Aimo's prices and stock, prepare an order, and stop for a person exactly where it should.

## 3. Description (4,922 of 5,000 characters; markdown)

Each heading answers one of the organiser's lists in their own words: the flow and the three core items; the four "problems we'd love to see tackled"; the optional direction on delivery and sustainability; the six example scenarios; the openness criterion; then one paragraph for each technology partner.

```markdown
## What it is

Valio Aimo asked how a food-service wholesaler can be **safely and openly readable by autonomous agents**. We built the wholesaler's side: a typed gateway between a buyer's purchasing agent and Valio Aimo's price and availability data, with rules, human sign-off and an audit trail. Not a chatbot on a webshop.

## Request → lookup → order/approval, end to end

A kitchen types **"1,000 litres of lactose-free milk by Monday"**, or an agent sends it over REST or MCP.

1. **Lookup.** An agent searches 17,546 products and gets price and availability in structured form. Here: the 26 lactose-free milks, coffee milk not counted as milk. Of 126 test sentences, 67 were read, 59 asked about, none read wrong.
2. **Inquiry to commitment, at fixed prices.** Three options at Valio Aimo's prices, nothing negotiated: 435 L confirmed for €1,083.39; 1,000 L for €1,010.00 with a quantity Valio Aimo does not confirm; 1,000 L from confirmed stock for €2,580.64, with a café milk named as a substitute. Price and stock are asked again when the order is placed.
3. **Permission and human approval.** `GET /v1/authority` tells the agent what it may decide alone. The agent prepares the order; a person signs off.

## The four problems

- **Trust protocol.** Every line states price, stock, delivery date, allergens and origin as confirmed, unknown or ruled out; offers and orders are signed (Ed25519, published keys). For an allergen the buyer excludes, no statement means unknown, not safe: at a milk-allergy ward all 26 lactose-free milks are refused.
- **Guardrails model.** Rules are data. Human sign-off above the buyer's spend threshold and for substitutions outside stated preferences (not like for like, or over 25% dearer). Fully autonomous only if the buyer switches it on: then 302 L (€748.96) is ordered alone and says why; 303 L (€751.44) waits, above the €750 limit. Over REST and MCP an agent can never approve.
- **Response logic.** Partial availability is offered as partial. Substitutes from Valio Aimo's own assortment are ranked good-better-best: same product in another pack, same brand, other brand. Where nothing fits, it says so.
- **Audit trail.** A human-readable log, one sentence per step with the rule that fired, hash-chained, for both buyer and Valio Aimo, who sees no limit, allergen or person's name.

**Not just price:** each option states delivery reliability, carbon footprint and certificate labels; "most reliable delivery" re-ranks the offer.

## The six example scenarios

- **Recipe → order:** "a chocolate cake for 20" becomes one 7-line order from our 10 recipes; kitchen stock is taken off.
- **Last-minute event:** "beef stew for 80 for tomorrow" names each ingredient that cannot arrive and offers the earliest date.
- **Stock-out:** a product with 0 in stock gets a ranked substitute, the trade-off in figures (2.9 L packs, not 3 L).
- **Selling agent:** with an offer, Valio Aimo suggests a related product (the same oat drink in a larger pack, €42.00 less on 30 L), added only if accepted. Its back office counts what it sold and could not sell.
- **Allergen-safe substitution:** at the ward an oat drink with no milk statement is replaced by a rice drink that states free from; the dietitian must approve.
- **Standing order drift:** a weekly 100 L renewed at 290 L is outside the 25% tolerance and waits for a person.

## Open standards, technical choices

OpenAPI 3.1, JSON Schema, MCP (13 tools, none approves), RFC 9457 errors, RFC 9727 discovery, `/llms.txt`, GS1 allergen codes: no proprietary format. Fixed rules decide, never a model, so the same request on the same data gets the same answer. MIT.

## Assumptions

The demo replays a recording of Valio Aimo's mock (1,163 products with prices and stock) at a fixed clock. A stock figure of 999,999 or more is read as not known (confirmed by Valio Aimo). Customers, histories, recipes and limits are synthetic and ours. The order step is ours by design. The demo page has no login and keeps each browser's orders in memory; on the demo link REST and MCP write to PostgreSQL.

## Next steps

Valio Aimo signing its own statements; orders as Peppol BIS; sign-in for people and agents; new and seasonal products marked; a check that runs before the kitchen asks; a nutrition standard; Finnish.

## Built with

Python, FastAPI, MCP, YAML rules. About 6,200 automated tests.

**Context.dev** (Answers): the product's web page beside an allergen doubt, for the person who decides. Of 92 products asked, 30 shown, 39 rejected with the reason. `docs/CONTEXTDEV.md`

**Aiven PostgreSQL** keeps the audit trail: triggers refuse UPDATE and DELETE (tried on the live trail) and a role with one grant reads only Valio Aimo's view. `docs/AIVEN.md`

**Modal** hosts the demo link (one web endpoint, 10 of 10 deploy checks) and ran a batch fan-out: 76 product-page lookups over 40 CPU containers in 58 seconds. `docs/AWARDS.md`
```

What the checks changed, so nobody puts it back:
- "The manufacturer's own page" became "the product's web page": 17 of the 30 pages shown are on a site whose owner was not checked.
- The audit trail in Aiven PostgreSQL is the one REST and MCP callers write to on the demo link. The `/shop` page keeps each browser's order book in memory. The Assumptions say so.
- "A passed order deadline goes to a person" was wrong: the product is left out for that date, and the later date goes to a person.
- "Proactive" is not claimed: the suggestion comes with an offer the buyer asked for. Nothing watches stock before someone asks. Both are next steps.
- The demo's stock-out sentence uses a product whose quantity is not confirmed. A real stock-out for a judge who asks: product `469316` (0 in stock) gives a ranked substitute for €152.68.

## 4. Tech challenges to select

| Award | What we can truthfully say | Our own estimate | Cheapest way to raise it |
|---|---|---|---|
| **Context.dev** | One endpoint (Answers) with our own schema of seven fields; the product's web page is shown beside an allergen doubt to the person who decides, and a page can add a doubt, never remove one. 92 recorded answers: 30 shown, 39 rejected each with its reason, 23 with no page. The 79 products with no allergen statement are every such product of the demo capture (769 products). The public link replays the recordings; it makes no live call. The note their brief asks for: `docs/CONTEXTDEV.md` | Fair | The repository must be pushed: their brief requires one |
| **Aiven** | Aiven PostgreSQL holds the order book and audit trail of REST and MCP callers on the public link. Triggers refuse UPDATE and DELETE of an audit event, for the gateway's own login too (tried on the live trail); a role with one grant reads only Valio Aimo's view; 68 tests passed against the live service, in schemas of their own. `docs/AIVEN.md`, section 4. Not run: `scripts/aiven_proof.py` with a supplier's login | Fair | Show section 4 of `docs/AIVEN.md` at Aiven's booth; `/healthz` on the link names the store |
| **Modal** | One web endpoint in plain Python serves REST, MCP and the pages; 10 of 10 checks after the last deploy. One batch fan-out ran: 76 product-page lookups over 40 CPU containers in 58 seconds. Built and not run: an hourly witness of the audit trail | Low: no model runs on Modal; one of the brief's four uses, small | — |

Do not put counts of the live trail (events, orders) in the form: they change with every check of the link.

## 5. The morning, in order

1. Record the video from `AIMO/VIDEO-SHOTLIST.md` against `http://127.0.0.1:8011/shop`; upload; check the link in a private window.
2. Ask Valio Aimo at the booth whether their data files may stay in a public repository.
3. Source code: `git push origin replan-build`, then `git push origin delivery:main` (the clean branch without the team's working notes), make the repository public, tell the teammates their commit e-mail addresses become public, and open the repository in a private window.
4. Deck: the three rows of `AIMO/PITCH-DECK-REVIEW-V5.md` and the Context.dev figures above; export to PDF.
5. Fill in the form from sections 1 to 4; set FINAL; re-open and check.
6. Rehearse the three-minute pitch once with the live minute (`AIMO/PITCH-SCRIPT.md`; the runbook is at the end of `AIMO/DEMO-CHECK.md`).
7. Be at the table at 10:30. After the judging: `modal app stop trusted-trade-agents`.
