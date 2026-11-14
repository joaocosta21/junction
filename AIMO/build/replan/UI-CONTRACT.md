# What the interface needs from tonight's build

For the teammate who builds the interface. The build session keeps this file current: after each task it adds the fields, routes and sentences a page should show or call. **The build does not edit `src/tta/ui/` or `tests/ui/`**, except the lines listed at the end.

The pages are a front end to the typed interface; the brief says "this is not about replacing today's e-commerce UI with a chatbot". Use Valio's own words where the webshop has one (`P3-webshop.md`, the mapping table): "Closing time", "Delivery date", "N pcs available in storage" for confirmed stock, "Deliverable <date>" where no quantity is known, "Alternative products", "Standard order".

## For Gabriela: the shop page, in this order (`C2-frontend-branch.md`)
The review of `frontend-shop` says: build on top of it. It runs, it is safe on the points checked, and its answer card passes the five-second test the old pages fail. Four things must change before a Valio judge sees it; the first and the last are the two things Valio told us not to do.

| # | What | Where | Hours |
|---|---|---|---|
| **F1** | **Nothing is ordered or sent without a click.** One button, "Confirm order". Remove "Ordered by your agent". Today the school (€99.20) and the ward (€402.00) are ordered with no click | `views/assistant.js` (`act`, line 80; `verdictBox`), `views/parts.js` (`statusTag`), `kitchens.js` (`autoSend`), `store.js:5` (a new storage key, or a browser that already opened the page keeps the old defaults) | 1 |
| **F4** | **Not a chat.** Valio's slide: "it is NOT a chatbot". Rename "Assistant", drop the greeting, the bubbles and "conversation"; show the typed request that was sent; link `/docs` and the MCP tools | `views/assistant.js`, `main.js`, `shop.css` | 1 |
| **F3** (your half) | The rules shown are the rules in force: show limits and allergens from the gateway's answer, not from `localStorage`; when a settings call is refused, push again, retry and show the refusal | `core.js`, `main.js` | 0.5 |
| F6 | The reader's refusal in plain words, and a place for the reader's question. Today an unreadable sentence shows "No GEMINI_API_KEY is set … POST /v1/offers" | `views/assistant.js` (`answer`, the `failed` branch) | 0.5 |
| F5 (your half) | One definition of the four customers: read them from the new route; `kitchens.js` keeps only presentation. The school's allergen rule and the bakery's substitution scope and brand change (see the runbook, "Four customers, one definition") | `kitchens.js` | 1 |
| then | What a substitute gives up, in numbers (R5) · the clock strip (R8) · the suggestions box with "Add" and "Not now" (S2) · the three choices on the approval card (R6) · Valio's own words · a link between `/` and `/shop` | — | — |

The build session edits only `shop_api.py`, `tests/ui/test_shop_api.py`, the setting values in `kitchens.js` and the shop's line in `routes.py`. It puts tonight's new sentences into fields your page already prints, so most of them show with no change on your side (the table is in the runbook, "Where a sentence goes so the shop page shows it").

## What a judge must see in the first five seconds of a result (`A4-judge-run.md`, sections 2 and 3)
1. What was asked, in one line.
2. What is suggested, in one line: products, quantity, total.
3. What needs a person, and why, in one line, next to the outcome and not a screen below it.
Everything else is folded away. No code words on the page: not `FREE_FROM_LACTOSE`, "claim", "verdict", "replay", "fill ratio", or a rule id without its words. Today a result holds 1,050 to 1,900 words.

## Planned, by package (the build session fills in the exact fields as each lands)

| Package | What the page should do | Detail |
|---|---|---|
| R1, R7 | An order is **prepared, then confirmed by a person**. The result says "Prepared: confirm to order" with one click. Afterwards the page says who confirmed. Nothing on a page says "ordered by the agent" unless the buyer switched that setting on | `P8-confirm.md` F1, F2 |
| R2 | The offer says when a variant was left out ("coffee milk was left out; ask for it by name") or is offered without being asked ("lactose-free; you did not ask for it") | `P9a-product-type-precision.md` A1 |
| R5 | A substitute line shows what it gives up in numbers (fat, protein, sugars), whether it keeps the formula, the brand, and that a claim-losing substitute is a last resort | `P10-formula.md` F3, F8 |
| R6 | The dietitian's card asks a question with three choices: use this product anyway, take the next safe product, leave the line out. A safe product is always the first option; a doubtful one is labelled "Alternative: allergen not ruled out" | `P4-noisy-data.md` M1, M2 |
| S1 | Four customers. The page says who is ordering and labels generated history "Synthetic: made up for the demo" wherever it shows | `P1-customers.md` C7, section 5.4 |
| S2 | A small box under the offer, "Suggested from your past orders": each suggestion with its sentence in numbers, "Add" and "Not now". "Add" builds a new offer; nothing is added silently | `P15-recommendations.md` R4a, R4b |
| S4 | Valio's view of an order shows each rule that fired, its reason, and the products considered and left out | `P9b-booth-answers.md` B13-2 |
| R8 | A banner on every page: which instant the clock shows, that we chose it, and that the log keeps the real time | `P5-clock.md` section 4, "Labels" |
| R9 | One button per demo scenario on the first page, each with its customer. The five examples must work in any order in one browser | `P2-scenarios.md` W2; `A4-judge-run.md` H2 |
| A4 H2 | After an approval, the button "Decide as …" names a role that is still needed, or is not shown | `A4-judge-run.md` H2 |
| P14 | The photo button stops after reading and shows the lines it read; a second click continues. Or the upload control leaves the page | `P14-photo-voice.md` PV-1 |
| P16 | One sentence on the order page: no payment is taken here; the buyer is a credit customer, invoiced for what is delivered | `P16-payments.md` PAY-2 |
| P7 | The heading above the substitutes at `src/tta/ui/templates/_result.html:192` is wrong whenever a category tier shows; the tiers go away tonight | `P7-categories.md` section 1 |
| A3 F5 | `/run-photo` reads up to 5 MB before it checks the form's token: check the token first | `A3-security.md` F5 |

## New fields and routes (filled in by the build session)

| Task | Field or route | Example | The sentence a person should read |
|---|---|---|---|
| — | — | — | — |

## Changed under the interface (only figures, status words or field names; filled in by the build session)

| Task | File and line | Before → after | Why |
|---|---|---|---|
| — | — | — | — |
