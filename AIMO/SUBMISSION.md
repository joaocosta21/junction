# Submission — what goes in the form

The form closes **Sunday 15 Nov, 10:00**, automatically. Set the project to **FINAL** early (a FINAL project stays editable until the deadline). Peer reviewing is 10:30–14:00 at our table.

Written Sun 15 Nov, early morning, against tonight's code. Figures come from the recording of Valio Aimo's test data (1,163 products), never from the whole catalog, unless said.

## 1. Each field

| Field | Limit | What to enter | Still to do |
|---|---|---|---|
| Project name | 30 | The one you typed, or `Trusted Trade Agents` (20) | — |
| Punchline | 200 | Section 2 | Paste |
| Description | 5,000 | Section 3 (4,597 characters) | Paste |
| Challenge | — | Valio Aimo — "Trusted Trade Agents" | Select |
| Project demo | link | `https://joaocostared--trusted-trade-agents.us-east.modal.run/shop` | Live with tonight's code; all 10 deployment checks passed. One more redeploy follows the last fixes; the address does not change |
| Source code | link | `https://github.com/joaocosta21/junction` | **Not ready:** `main` has no code yet and the repository is private. The six steps are in `AIMO/SOURCE-CODE-REVIEW.md` (about ten minutes) |
| Video | link, max 2:00, public | Record from `AIMO/VIDEO-SHOTLIST.md` | Record, upload to YouTube or Vimeo, check the link in a private window |
| Other link | link | `https://joaocostared--trusted-trade-agents.us-east.modal.run/docs` (the typed API a judge can try) | — |
| Presentation | PDF/PPTX, 20 MB | Deck v5 with the three rows of `AIMO/PITCH-DECK-REVIEW-V5.md` and the page 12–14 text of `AIMO/AWARDS-RUN.md` | Edit, export to PDF on the machine the deck was made on (it needs the font Inter), look at every page |
| Tech challenges | — | Context.dev, Aiven, Modal: section 4 | Select |
| Team phones, Discord, credit preference | — | Yours | Fill in |
| Status | — | FINAL | Set early; re-open the page and check it says FINAL |

## 2. Punchline (200 characters at most)

Recommended (147 characters):

> An open gateway that lets any purchasing agent read Valio Aimo's prices and stock, prepare an order, and stop for a person exactly where it should.

Alternative (155 characters):

> Type what your kitchen needs. An agent finds what Valio Aimo can really deliver, explains every choice, and a person confirms. Allergens are never guessed.

## 3. Description (4,597 of 5,000 characters; markdown)

```markdown
## What it is

Valio Aimo asked how a food-service wholesaler can be **safely and openly readable by autonomous agents**. We built the wholesaler's side of that: a typed gateway between a buyer's purchasing agent and Valio Aimo's price and availability data, with the rules, the human confirmation and the audit trail that make it safe to use. It is not a chatbot on top of a webshop.

## The flow, end to end

A kitchen types **"I need 1,000 litres of lactose-free milk by Monday"**, or an agent sends the same as a typed request over REST or MCP.

1. **Read.** The sentence becomes a typed request. What cannot be read is asked about, never guessed; a price named in the sentence ("under €400") is applied as a spend limit for that request.
2. **Look up.** Price and stock of every matching product, each statement marked confirmed or not.
3. **Offer.** Here, three options: 435 L from confirmed stock for €1,083.39; 1,000 L for €1,010.00 with a quantity Valio Aimo does not confirm; or all 1,000 L from confirmed stock for €2,580.64, with a lactose-free café milk named as a substitute. Nothing is invented.
4. **Rules.** Rules kept as data decide what the agent may do alone and what needs a person. By default a person confirms every order.
5. **Order.** The agent prepares; a person confirms with one click.
6. **Log.** Every step is one sentence in a hash-chained log, with a view for the buyer and a view for Valio Aimo.

## Guardrails

- **Unknown is never read as safe.** A missing allergen statement, an unconfirmed quantity, a passed order deadline: each is said, and goes to a person.
- **A claim is not a declaration.** A milk-allergy ward asking for lactose-free milk gets 26 products checked and 26 refused: lactose-free is still milk. A doubtful product goes to the dietitian, with what the manufacturer's own page says (Context.dev).
- **The buyer sets the agent's authority.** With "ordering alone" switched on at the hotel, the agent orders 302 L (€748.96) and says why it was allowed; 303 L (€751.44) waits for a person, because of the €750 limit. A substitute that is not like for like, or clearly dearer, always goes to a person.
- **Over REST and MCP an agent can never approve.** Its token is refused and the attempt is logged.
- **Valio Aimo sees the decision, not the buyer's private values:** no limits, no excluded allergens, no names.

## Exceptions

Partial stock is offered as partial, with the rest two ways. A date that cannot be met is answered with the earliest date, for a person to accept. Substitutes are judged like a kitchen would: same kind of product, same use, same formula; where the recipe matters, the same brand with the same formula comes first; and where nothing fits, it says so instead of offering a wrong product.

## It also sells

The item a buyer usually orders and forgot, a cheaper pack of the same product, a standing order that has outgrown its quantity, a dish turned into an order ("a chocolate cake for 20"). For Valio Aimo, a back office: what the agent channel sold, which suggestions were accepted, and the sales it could not make because its own data did not confirm the stock (in the demo: 565 L, about €1,407).

## Open, documented standards

OpenAPI 3.1 and JSON Schema, an MCP server with 13 tools of which none approves, problem details (RFC 9457), discovery at `/.well-known/api-catalog` (RFC 9727) and `/llms.txt`, GS1 allergen codes, offers and orders signed with Ed25519 and a published key set. An agent that knows only the address reaches an order waiting for a person in four requests. MIT-licensed.

## Assumptions

The demo replays a recording of Valio Aimo's test data at a fixed clock (1,163 products with prices and stock; 17,546 searchable). The four customers and their order histories are synthetic. Spend limits are illustrative and ours. The order step is ours by design: "ordered" is a record in the gateway's order book. Offers are signed by the gateway with a demo key. The demo page has no login. Sentences are read by fixed rules; a model reader exists as an option, and whoever reads, rules decide.

## Next steps

Valio Aimo signing its own statements of price, stock and origin; people signing in with their own accounts; an order message Valio Aimo's systems can take; orders tied to their log entries; a nutrition standard for schools and hospitals; Finnish.

## Built with

Python, FastAPI, MCP, a YAML rule engine, PostgreSQL on Aiven for the audit trail (the database itself refuses a change), Modal for hosting and batch lookups, Context.dev for manufacturer pages. About 6,200 automated tests.
```

The test count is of the whole suite as run tonight (6,189 passed before the last fixes; the hand-over has the final count).

## 4. Tech challenges to select

| Award | What we can truthfully say (run on 15 Nov) | Our own estimate |
|---|---|---|
| **Context.dev** | The manufacturer's own page is shown beside an allergen doubt, to the person who decides. Every product of the recording with no allergen statement was looked up: 104 requests in all, 92 recorded answers, 29 kept as evidence, 40 rejected each with its reason, 23 with no page. Their brief asks for a public repository, a demo and a note on which endpoints were used: `docs/CONTEXTDEV.md` | Fair, the best of the three |
| **Aiven** | The public link's audit trail is in Aiven for PostgreSQL. The database itself refuses to change or delete an audit event, for the gateway's own login too (tried on the live trail); a read-only role reads Valio Aimo's view and nothing behind it; 68 tests passed against the live service. `docs/AIVEN.md`, section 4 | Fair |
| **Modal** | Modal hosts the gateway (one container, 10 of 10 checks). A batch of 76 manufacturer-page lookups was fanned out over 40 containers and done in 58 seconds. No model runs on a GPU | Low: their brief rewards a model running on Modal |

Google Gemini is not selected: a model reader exists and was measured, but the public demo runs without one.

Deck text for pages 12 to 14 is in `AIMO/AWARDS-RUN.md`.

## 5. The morning, in order

1. `git push` when the build says the last commit is in.
2. The source code steps of `AIMO/SOURCE-CODE-REVIEW.md` (ask Valio about their data; move the other challenges' briefs; push to `main`; make it public; tell the teammates their commit e-mail addresses become public).
3. Deck: the last three rows of `AIMO/PITCH-DECK-REVIEW-V5.md`; export to PDF.
4. Record the video from `AIMO/VIDEO-SHOTLIST.md` against `http://127.0.0.1:8011/shop`; upload; check the link in a private window.
5. Fill in the form; set FINAL; re-open and check.
6. Rehearse the three-minute pitch once with the live minute (`AIMO/PITCH-SCRIPT.md`; the runbook is at the end of `AIMO/DEMO-CHECK.md`).
7. Be at the table at 10:30. After the judging: `modal app stop trusted-trade-agents`.
