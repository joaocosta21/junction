# Video: shot list (2:00, strictly) — DRAFT of Sun 15 Nov 02:35

**Status: draft for rehearsal.** The page is still being polished (three lanes are running), so labels and one or two figures can still move. The final version replaces this file when those lanes land, and says so on this line. Rehearse now; record when this line says FINAL.

## Before you record
- Open `http://127.0.0.1:8011/shop` in Chrome, window about 1440 × 900, zoom 100%. It runs the recorded Valio Aimo data at the demo clock (Thu 12 Nov 2026, 14:15), with no model and no keys, the same as the public link will.
- Every customer has its own order book in your browser. To start clean: Settings → "Reset this customer's demo" for each customer you will use. Do it before every take: the day's spend adds up and changes what the rules say.
- Record each block as its own take. Cut on the "cut when" moment. Waiting for an answer is under a second; cut any wait.
- Say litres, not cartons. Put no price in a sentence. Type the sentences exactly as written here.
- Voice: record it separately over the cut; the lines below are about 260 words, which is two minutes at a calm pace.

## The blocks

| # | Time | Keep | Do (exact) | Cut when you see | Say |
|---|---|---|---|---|---|
| 1 | 0:00–0:08 | 8 s | Title card: "Trusted Trade Agents: a wholesaler that agents can read, safely and openly" | — | "We asked our agent for a thousand litres of lactose-free milk by Monday. It confirmed 435, and told us why it would not promise the rest." |
| 2 | 0:08–0:38 | 30 s | Customer: Harbourside Hotel (it is the first one shown). Click the first example chip, or type `1,000 litres of lactose-free milk by Monday` and press Enter. Let the page scroll to the answer. Move the mouse down the three options. | "435 L of the 1,000 L", the total €1,083.39, and the two other options: 1,000 L for €1,010.00 with a quantity not confirmed, and all 1,000 L from confirmed stock with a substitute for €2,580.64 | "It reads the request, asks Valio Aimo for price and stock, and answers in structure. 435 litres are confirmed. The rest it offers two ways: cheaper, but Valio Aimo does not confirm the quantity; or all from confirmed stock, with a named substitute. Nothing is guessed." |
| 3 | 0:38–0:55 | 17 s | Click "CONFIRM ORDER". Then "Order and audit trail". Scroll to the log. Click "What Valio Aimo sees". | The green box "Confirmed by Hanna Laine"; then "Trail intact" with the steps; then the banner "This is Valio Aimo's view of the order" | "The agent prepares; a person confirms, because this order is above her limit. Every step is in a log that cannot be changed unnoticed, and Valio Aimo sees its own view, without the buyer's limits." |
| 4 | 0:55–1:13 | 18 s | Customer: City Hospital, Ward 4. Type `100 litres of lactose-free milk by Monday`, Enter. | Nothing is offered, and the reason: the products declare that they contain milk | "A milk-allergy ward asks for lactose-free milk. Twenty-six checked, twenty-six refused. Lactose-free is still milk: a claim is not an allergen declaration, and no data never means safe." |
| 5 | 1:13–1:35 | 22 s | Customer: Harbourside Hotel (reset first). Settings → switch "ordering alone" on → save. Back to Request. Type `302 litres of lactose-free milk by Monday`, Enter. Then type `303 litres of lactose-free milk by Monday`, Enter. | First: "Ordered by your agent", €748.96, with why it was allowed. Second: "Needs your decision", €751.44, above the €750 limit per order | "The buyer decides what the agent may do alone. 302 litres, the agent orders, and says why it was allowed. One litre more, and it waits for Hanna. Over REST and MCP an agent can prepare an order and never approve one." |
| 6 | 1:35–1:50 | 15 s | Hotel (reset; ordering alone off). Type `100 litres of lactose-free milk by Monday`, Enter. Scroll to the suggestion for cooking cream; click "Add". Then the strip tab "Valio Aimo's back office (demo)". | The cream "in 7 of your last 8 orders", the total going from €248.00 to €281.10; then the back office's figures | "It also sells: it noticed what Hanna forgot. And Valio Aimo sees what it sold through agents, and the stock it could not confirm as sales it did not make." |
| 7 | 1:50–2:00 | 10 s | Browser tabs prepared in advance: `/llms.txt`, then `/docs`. | The list of routes in `/docs` | "Open standards: OpenAPI, MCP, signed offers, MIT-licensed. Valio Aimo asked for this interface to be defined before someone else's platform defines it. Here it is, in the open." |

Total: 120 s.

## If a block does not behave as written
- Block 2 shows only two options, or other figures: tell me; do not record it.
- Block 4 has been measured through the interface, not yet looked at on the page at the final commit: rehearse it first. Fallback for the same 18 seconds: Hotel, `100 litres of Elovena barista oat drink, product 469512, by Monday; no milk` → the safe product first (€236.00); click "Choose" on "Alternative: allergen not ruled out" (€208.00) → the question with the manufacturer's page beside it. Say: "With an allergen excluded the safe product comes first; a doubtful one goes to a person, with what the manufacturer's own page says."
- Block 5: if the 302 L order is not placed by the agent, the hotel's day already holds orders: reset the hotel and try again.
- Block 6 alternative, the brief's "standing order drift": Hotel → Standing orders → type 290 in "This week's quantity" → "RENEW ONCE AT 290 L" → "290 L this week against a median of 100 L over the last 6 renewals, more than the 25% tolerance" (€719.20) → Confirm. Say: "It learned the weekly order, and flags a jump before renewing it."

## Not for the camera
- Substitutes for products outside dairy and plant drinks.
- The cake (scenario 7) until the final version of this file says it reads well.
- Any step on the old pages (the footer link "the gateway's first pages").
