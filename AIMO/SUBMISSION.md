# Submission — what goes in the form, and what is still missing

The form closes **Sunday 15 Nov, 10:00**, automatically. The project must be set to **FINAL** before then (a FINAL project stays editable until the deadline). Peer reviewing is 10:30–14:00 at our table.

Written Sat 14 Nov, about 23:15, against code commit `b1de9d4`. Every claim below is true of that code unless it says "pending". Figures come from the recording of Valio Aimo's test data (769 products recorded Sat 02:52, plus 394 baking products recorded Sat 21:12), never from the whole catalog.

## 1. Status of each field

| Field | Limit | Status | What to do |
|---|---|---|---|
| Project name | 30 | **You have typed 9 characters already.** Options if you want one: section 2 | Pick |
| Punchline | 200 | Draft ready, section 3 | Paste |
| Description | 5,000 | Draft ready, section 4 (about 3,900 characters) | Paste; adjust the two "pending" lines |
| Challenge | — | Valio Aimo — "Trusted Trade Agents" | Select |
| Project demo | link | **Pending the redeploy.** The public link today runs this morning's code | Section 5 |
| Source code | link | **Pending the push and making the repository public** (or giving the organisers access) | Section 5 |
| Video | link, max 2:00, public | **Not recorded.** Script in section 6 | Record, upload to YouTube or Vimeo as public or unlisted-with-link |
| Other link | link | Optional: the API's own page `/docs`, or `AIMO/COVERAGE.md` on GitHub | Section 5 |
| Presentation | PDF/PPTX, 20 MB | **Not made.** Outline in section 7 | Make, export to PDF |
| Tech challenges | — | Modal, Context.dev, Aiven. Google Gemini is possible again: section 8 | Select |
| Team phones, Discord, credit preference | — | Yours | Fill in |
| Status | — | Set to FINAL | Do it early, edit after |

## 2. Project name (30 characters at most)

Keep the one you typed if you like it. Otherwise, in order of my preference:

- `Trusted Trade Gateway` (21) — says what it is, uses the challenge's own words
- `Aimo Agent Gateway` (18)
- `Orderable by Agents` (19)

## 3. Punchline (200 characters at most)

Recommended (153 characters):

> An open gateway that lets any purchasing agent read Valio Aimo's prices and stock, prepare an order, and stop for a person exactly where it should.

Alternative, more about the buyer (166 characters):

> Type what your kitchen needs. An agent finds what Valio Aimo can really deliver, explains every choice, and a person confirms. Allergens are never guessed.

## 4. Description (5,000 characters at most; markdown)

```markdown
## What it is

Valio Aimo asked how a food-service wholesaler can be **safely and openly readable by autonomous agents**. We built the wholesaler's side of that: a typed gateway between a buyer's purchasing agent and Valio Aimo's price and availability data, with the rules, the human confirmation and the audit trail that make it safe to use. It is not a chatbot on top of a webshop.

## The flow, end to end

A kitchen types **"I need 1,000 litres of lactose-free milk by Monday"** (or an agent sends the same as a typed request over REST or MCP).

1. **Read.** The request becomes a typed request. A model (Gemini Flash) reads it and is held to the buyer's own words; fixed rules are the fallback. What cannot be read is asked about, never guessed.
2. **Look up.** The gateway asks Valio Aimo for price and stock of the matching products.
3. **Offer.** Up to three options, each line carrying what is confirmed and what is not: here, 435 L confirmed for €1,083.39, 565 L missing, and an alternative whose quantity Valio Aimo does not confirm for €1,010.00.
4. **Rules.** Rules kept as data decide what the agent may do alone and what needs a person. By default a person confirms every order.
5. **Order.** The agent prepares the order; a person confirms it with one click.
6. **Log.** Every step is one sentence in a hash-chained log, with a view for the buyer and a view for Valio Aimo.

## What makes it trustworthy

- **Unknown is never read as safe.** A missing allergen statement, an unconfirmed quantity, a passed order deadline: each is said, and goes to a person.
- **Allergens are strict.** A product that declares an excluded allergen can never be ordered. The safe product comes first; a doubtful one is a labelled alternative, shown with what the manufacturer's own page says (Context.dev).
- **Substitutes are judged like a kitchen would.** Same kind of product, same use, not flavoured, and the same ingredients: two creams with the same nutrition figures are not the same formula if one lists an enzyme the other does not.
- **An agent can never approve.** Not through REST, not through MCP, not by asking nicely.
- **Valio Aimo sees the decision, not the buyer's private values:** rules that fired and products left out, without limits, excluded allergens or names.

## What makes it useful

- **Suggestions a buyer would thank you for:** the item usually ordered with this one and missing from the request, the same product in a cheaper pack, a standing order that has outgrown its quantity. Each says why, from the buyer's own history, and is added only by a click.
- **"You usually order this":** a prompt to reorder, and an alert when a request repeats a standing order.
- **From a dish to an order:** "a chocolate cake for 20" becomes ingredients, packs, prices, stock and leftovers.
- **For Valio Aimo, a back office:** what the agent channel sold, which suggestions were accepted, and the sales it could not make because stock was not confirmed.

## Open by design

OpenAPI 3.1 and JSON Schema, an MCP server with 13 tools, problem details (RFC 9457), discovery at `/.well-known/api-catalog` (RFC 9727) and `/llms.txt`, GS1 allergen codes, signed offers and orders (Ed25519). Every threshold that is ours is listed as ours.

## Honest limits

The demo replays a recording of Valio Aimo's test data at a chosen clock, because that data is frozen in time; live mode exists. The customers and their order history are synthetic and labelled so. There is no payment step and no order message to Valio Aimo's own systems: the order book is ours.

## Built with

Python, FastAPI, MCP, a YAML rule engine, SQLite or PostgreSQL (Aiven), Modal for hosting, Context.dev for manufacturer pages, Gemini Flash for reading requests. About 4,000 automated tests.
```

**Before pasting, check two lines against the final state:** "A model (Gemini Flash) reads it" is true of the local demo; it is true of the public link only if the redeploy carries the model key (your decision, section 8). "About 4,000 automated tests" is the count of the last whole-suite run (4,049 passed at wave 1; a final count comes with the last run).

## 5. Links

| Field | Value | Blocker |
|---|---|---|
| Project demo | `https://<the Modal address>/shop` (the address is in `docs/DEPLOY.md`) | The link runs this morning's code until the redeploy. The run will redeploy when the suite is green; if the session refuses, the command is `.venv/bin/modal deploy --strategy recreate deploy/modal_app.py` |
| Source code | The GitHub repository | Nothing of tonight is pushed: run `git push -u origin replan-build`, then merge to `main` or point the form at the branch. The repository is private: make it public, or add the organisers. The licence must be MIT |
| Other link | `https://<the Modal address>/docs` (the typed API a judge can try), or the coverage document `AIMO/COVERAGE.md` on GitHub | Same as above |

## 6. Video — 2:00, strictly

Record the screen on `/shop` at the demo clock. One take per block; cut hard. Suggested script (about 280 spoken words):

| Time | On screen | Say |
|---|---|---|
| 0:00–0:15 | Title, then `/shop` | "Soon the buyer at a restaurant will be an agent. Valio Aimo asked: how does a wholesaler become readable by agents, safely? We built that gateway." |
| 0:15–0:45 | Hotel: "1,000 litres of lactose-free milk by Monday" → the offer | "The agent reads the request, asks Valio Aimo for price and stock, and answers honestly: 435 litres are confirmed, 565 are not, and here is why. Nothing is guessed." |
| 0:45–1:05 | "Confirm order" → the log → "What Valio Aimo sees" | "The agent prepares the order. A person confirms. Every step is logged, and Valio Aimo sees the decision without the buyer's private limits." |
| 1:05–1:30 | Oat drink without milk → the safe product first → the manufacturer's page | "With an allergen excluded, the safe product comes first. A doubtful one goes to a person, with what the manufacturer's own page says. Allergens are never guessed." |
| 1:30–1:48 | Suggestions box → "Add"; the bakery's cake | "It also sells better: the item you usually order and forgot, a cheaper pack of the same product, a cake turned into a shopping list." |
| 1:48–2:00 | `/docs`, the MCP tools, the back office | "Open standards: OpenAPI, MCP, signed offers. Any agent can connect. None can approve." |

## 7. Presentation — outline (PDF, 3 minutes on stage if we reach the top 5)

1. **The question** — Valio Aimo's own sentence: "safely and openly readable by autonomous agents".
2. **What we built** — one diagram: agent → gateway (read, look up, offer, rules, order, log) → Valio Aimo; a person at the confirm step.
3. **The demo in one screenshot** — the 1,000 L answer: 435 L confirmed, why, the alternative.
4. **Guardrails** — what the agent decides alone, what needs a person, what is never allowed (allergens, approval). The five plain statements.
5. **Exceptions** — partial stock, substitutes judged by ingredients, the allergen doubt with evidence.
6. **It sells** — suggestions with their acceptance figures, the back office, "sales we could not make".
7. **Open** — the standards list; "any agent, 13 tools, none approves".
8. **Honest limits and next steps** — recording and clock, synthetic customers, Valio's own signature on offers, an order message to Valio's systems.

Scoring reminder for the slides' order: 30% working end-to-end demo · 20% precision of the match · 20% autonomy and controls · 15% exceptions · 15% openness.

## 8. Tech challenges to select

| Award | Select? | What we can truthfully say | Still to do |
|---|---|---|---|
| **Context.dev** | Yes | Manufacturer pages are fetched for products whose allergen data leaves a doubt and shown to the person who decides; 13 pages recorded, 9 kept as evidence, 4 dropped with the reason | Their brief asks for a GitHub repository, a demo and a short note on which endpoints were used and why: the note is in `docs/CONTEXTDEV.md` |
| **Aiven** | Yes | PostgreSQL holds the audit trail, the database refuses to change a row, and Valio Aimo reads its own view with a read-only login | The proof (`scripts/aiven_proof.py`) has not been run against the database |
| **Modal** | Yes, with modest expectations | The gateway is hosted on Modal | The brief wants "the most ambitious working AI system built on Modal"; our model does not run on Modal (no GPU without a payment method) |
| **Google Gemini** | **Your call** | Tonight Gemini 3.6 Flash read a request and ran the agent's three tool calls with the team's key | It was dropped this afternoon on the belief the key had no credits; it works. If selected, the public link must carry the key, and the key's billing should be checked first |

## 9. Checklist for Sunday morning

- [ ] Push the branch; make the repository reachable; confirm the MIT licence file is at the root
- [ ] Redeploy; open `<address>/shop` on a phone and a laptop; run the five-minute path once
- [ ] Record the video (2:00 at most), upload, check the link opens in a private window
- [ ] Export the deck to PDF (under 20 MB)
- [ ] Fill in: name, punchline, description, challenge, demo, source, video, presentation, tech challenges, phones, Discord, credit preference
- [ ] Set to **FINAL**, then re-open the page and check it says FINAL
- [ ] Be at the table at 10:30
