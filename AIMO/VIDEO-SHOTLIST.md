# Video: shot list (2:00, strictly) — FINAL, Sun 15 Nov 03:55

Every block below was walked as written in Chrome (headless, 1440 × 900) on commit `dbb8e13`, at the demo clock, with the pictures looked at, without a model, which is how your server runs. One lane is still adding a price limit read from the sentence: it changes none of these blocks.

## Before you record
- Open `http://127.0.0.1:8011/shop` in Chrome, window about 1440 × 900, zoom 100%. Recorded Valio Aimo data, demo clock Thu 12 Nov 2026 14:15.
- **Record in this order, in one browser, without reloading: blocks 2, 3, 4, then 5, then 6.** Block 4 needs the orders of blocks 2 and 3 still in the book, and must come before the ward (block 5).
- Start clean: Settings (hotel) → bottom of the page → "Reset this customer's demo". Do the same for the ward. Reset the hotel again only where a block says so.
- A toast stays about 3 seconds at the bottom of the window ("Now shopping as…", "Sent as a new request…"): wait for it to go before the moment you cut on.
- Folds you open stay open. After each request the page scrolls by itself so the answer is at the top.
- Type the sentences exactly. Say litres, not cartons. No price in a sentence.

### The reader
The server runs without a model, like the public link (João, 03:50: "the public link without the model so the experience is fluid"). Sentences are read by the fixed rules, at once, and the grey line under "Asked" says so. No waiting between requests is needed. The deck still says, truthfully, that a model can read the sentence and that the rules check it and decide: that path exists and was measured, it is only not switched on here.

## The blocks

| # | Time | Keep | Do (exact) | Cut when you see | Say |
|---|---|---|---|---|---|
| 1 | 0:00–0:08 | 8 s | Title card: "Trusted Trade Agents: a wholesaler that agents can read, safely and openly" | — | "We asked our agent for a thousand litres of lactose-free milk by Monday. It confirmed 435, and told us why it would not promise the rest." |
| 2 | 0:08–0:38 | 30 s | Harbourside Hotel is the first customer shown. Type `1,000 litres of lactose-free milk by Monday`, Enter. The page scrolls to the answer. Then scroll down about half a window: the two other options are under the first one's rows. | First: "2 confirmed products cover 435 L of the 1,000 L asked for (565 L missing), for €1,083.39 before tax", the total €1,083.39 and CONFIRM ORDER. After the scroll: "Alternative: quantity not confirmed · €1,010.00" and "Alternative: confirmed stock, completed with a substitute · €2,580.64" | "The gateway reads the sentence, asks Valio Aimo for price and stock and answers in structure: 435 litres are confirmed. The rest it offers two ways, for a person to choose: cheaper, but Valio Aimo does not confirm the quantity; or all from confirmed stock, with a lactose-free barista milk named as a substitute. Nothing is guessed." |
| 3 | 0:38–0:55 | 17 s | Scroll back up. Click CONFIRM ORDER. Click "Order and audit trail" in the green box. Scroll to the log. Click the tab "What Valio Aimo sees" (under "Show this order as"). | The green box "Confirmed by Hanna Laine · delivery Mon 16 Nov"; then "Trail intact … each of the 11 events …"; then the banner "This is Valio Aimo's view of the order, not Harbourside Hotel's" | "The agent prepares; a person confirms, because this order is above her limit. Every step is in a log that cannot be changed unnoticed, and Valio Aimo sees its own view of it, without the buyer's limits." |
| 4 | 0:55–1:13 | 18 s | **No reset.** Menu "Request". Type `100 litres of lactose-free milk by Monday`, Enter. Scroll to "Suggested from your past orders"; click "Add". Click CONFIRM ORDER on the new first result. Then the strip tab at the very top, "Valio Aimo's back office (demo)". | The suggestion: cooking cream "was in 7 of your last 8 orders… Adding 10 L costs €33.10"; the total going from €248.00 to €281.10; then the back office: "2 orders confirmed · €1,364.49", "€33.10 added to baskets", "565 L asked for, not confirmed · €1,407.16 at offered prices" | "It also sells: it noticed what Hanna forgot, one click. And Valio Aimo sees its side: what it sold through agents, and 565 litres, about fourteen hundred euros, it could not sell because its own data did not confirm the stock." |
| 5 | 1:13–1:30 | 17 s | Customer menu → City Hospital, Ward 4. Type `100 litres of lactose-free milk by Monday`, Enter. | "Nothing can be offered for this request. 26 products checked, 26 left out. All 26: The product declares that it contains milk, which the buyer excludes." | "A milk-allergy ward asks for lactose-free milk. Twenty-six checked, twenty-six refused. Lactose-free is still milk: a claim is not an allergen declaration, and missing data never means safe." |
| 6 | 1:30–1:50 | 20 s | Customer menu → Harbourside Hotel. Settings → bottom → "Reset this customer's demo". In Settings switch "Let the agent place orders alone" on → SAVE (bar at the bottom). Menu "Request". Type `302 litres of lactose-free milk by Monday`, Enter. Type `303 litres of lactose-free milk by Monday`, Enter. | First: "Ordered by your agent · delivery Mon 16 Nov", €748.96, "…That was allowed: ordering alone is switched on for Harbourside Hotel; the total of €748.96 is within the €750 limit per order; …". Second: "Needs your decision: The total of €751.44 before tax is above the €750 limit per order of Harbourside Hotel." | "The buyer decides what the agent may do alone. 302 litres, the agent orders, and says why it was allowed. One litre more, and it waits for Hanna. Over REST and MCP an agent can prepare an order and never approve one." |
| 7 | 1:50–2:00 | 10 s | Two tabs opened in advance: `http://127.0.0.1:8011/llms.txt`, then `http://127.0.0.1:8011/docs`. | The text of `/llms.txt`; then the 30 routes of `/docs` | "Open standards: OpenAPI, MCP, signed offers, MIT-licensed. Valio Aimo asked for this interface to be defined before someone else's platform defines it. Here it is, in the open." |

Total: 120 s. The raw clicks of blocks 2 to 7 take about 16 seconds in all; everything else is reading time you choose in the edit.

## Optional swaps (each fits the same seconds)
- **For block 4 or 6, the brief's "standing order drift":** Hotel → menu "Standing orders" → type 290 in the quantity box → RENEW ONCE AT 290 L → "…290 L this week against a median of 100 L over the last 6 renewals, more than the 25% tolerance of Harbourside Hotel", €719.20 → CONFIRM ORDER. Say: "It learned the weekly order, and flags a jump before renewing it."
- **For block 5, the allergen doubt with the manufacturer's page:** Hotel, `100 litres of Elovena barista oat drink, product 469512, by Monday; no milk, strict rule` → the safe product first (€236.00) → "Choose" on "Alternative: allergen not ruled out · €208.00" → the question with "FOUND ON THE WEB, NOT VALIO AIMO DATA" and three buttons. Say: "With an allergen excluded the safe product comes first; a doubtful one goes to a person, with what the manufacturer's own page says."
- **In block 3, to show the third option:** before confirming, "Choose" on the €2,580.64 option → label YOUR CHOICE, a third row 565 × Arla Café, and the fold "What differs". Then "Choose" the first option again and confirm.

## Not for the camera
- A headline that starts "Request line 1:" (it appears right after "Add" in block 4): cut before it or keep the frame on the total.
- The buyer's log read slowly: it names "My kitchen agent" and ids.
- "…by tomorrow" requests: the decision box shows a date as 2026-11-13.
- Substitutes for products outside milk, cream and plant drinks.
- The back office in a browser that already ran the ward's block: it then counts the ward's refused 100 L as a sale not made.
- The old pages (the footer link "the gateway's first pages").
