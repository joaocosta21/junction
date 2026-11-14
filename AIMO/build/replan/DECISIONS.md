# Decisions and questions for João

Kept by the build session while you are away. Read top to bottom when you come back; answer in the session or write under "Your answer". Nothing here stops the build: each item says what the run did in the meantime.

Last updated: Sat 14 Nov, about 19:00.

## A. Needs your answer (the run cannot decide these for you)

| # | Question | What the run does meanwhile | Your answer |
|---|---|---|---|
| A1 | **Context.dev budget.** 17 of the 60 requests the team approved are used. Recording a page for every demo product with an allergen doubt, as a Modal fan-out, could go past 60 (up to 20,000 credits). Raise the cap? | Stays within 60 | |
| A2 | **A model on a Modal GPU as the reader.** It is the only thing that meets Modal's main ask ("the most ambitious working AI system built on Modal"). It cannot be made trustworthy tonight and would undo "the fixed-rules reader is the product". Build it anyway? | Not built. Modal gets honest hosting, the evidence batch as a fan-out and a scheduled witness of the audit trail | |
| A3 | **The repository is private.** Context.dev asks for "a GitHub repository and a demo"; Junction needs the organisers to reach the source. Make it public, and when? The run never pushes | Nothing pushed | |
| A4 | **The shop page in a real browser.** No agent has seen it rendered (layout, phone width, keyboard). Open `/shop` once before the video and tell me what looks wrong | Checked by driving the page's code against a local gateway only | |
| A5 | **`CLAUDE.md` is out of date** and the run may not edit it: it names Gemini as the agent's model and says Aiven was dropped. Yours to change | Listed here | |

## B. Decided by the run, as the owner would (say so if you disagree; each is one change to undo)

| # | Decision | Reason | Where |
|---|---|---|---|
| B1 | A flavoured product does not replace a plain one (the nutty-vanilla barista drink is not a substitute for a plain barista oat drink) | A kitchen making coffee does not want vanilla and nut in every cup; "nutty" also raises an allergen question | L2a-R, running |
| B2 | A substitute must be the same product type; a pair Valio lists across types stays, ranked last | Coffee milk ranked first as a substitute for whole milk | L2a-R |
| B3 | Same use ranks first (barista for barista) but does not exclude | A drinking oat drink still works in a pinch | L2a-R |
| B4 | Per 100 g and per 100 ml are comparable for drinks (your decision), not for solids | About 3% apart for liquids | L2a-R |
| B5 | Ordering alone needs all five statements confirmed on every line, origin and delivery date included | Valio: "after and if you are 100% sure yes" | B0, `policy/human_approval.py` |
| B6 | Rule P-00 is retired; F-10 is the rule the buyer's setting drives, kept in code; the formula rule will be F-11 | P-00 fired beside every other rule | B0 |
| B7 | The school keeps the strict rule for tree nuts, peanuts and sesame, so every confirmed bulk milk and yoghurt goes to the dietitian (none states it is free from them) | Valio: when unsure, the safe product. Costs: the school's demo always ends at the dietitian | Runbook; L5 |
| B8 | A suggestion is shown and never applied; accepting it is one click that builds a new offer | Runbook: "a suggestion never adds itself" | L5 |
| B9 | The forgotten item stays silent only when the other product of the same type is not usually ordered with it | Otherwise the ward's rice drink would never be suggested beside its soya drink | L5 |
| B10 | Ward and bakery prefer reliability; hotel and school prefer price | Proposal P1 | L5 |
| B11 | With the buyer's setting on, the shop page orders an "agent may order" decision with no click; with it off (the default) nothing is ordered without "Confirm order" | It is what the setting means | U1 |
| B12 | "Confirm order" also signs for each needed role the signed-in person holds | One click, as the review asked | U1 |
| B13 | Valio's view shows a rule about an excluded allergen without the allergen and without the product | The product plus Valio's own data would reveal the allergen | L3b |
| B14 | Valio's view shows a required claim such as `FREE_FROM_PEANUTS` | Decision D1 of the proposal; it does hint at an exclusion | L3b |
| B15 | The reader asks about "1.000 litres" (1,000 or 1?), about cases and portions, and about anything it cannot read; with no model an unread text is a question (422), not "service unavailable" | Asking beats guessing; it is the only reader a judge meets | L1 |
| B16 | Scenario 3 (oat-drink substitute) is shown at the default clock unless B1 to B4 fix it at the demo clock too | At the demo clock it offered the nutty-vanilla drink | E1 decides after L2a-R |
| B17 | The whole suite is run once per wave, not after every lane | Lanes change the same tree at the same time; each lane's own tests are run before its commit | Orchestrator |
| B18 | No push, although fetch and outside calls are now approved | You approved fetch, deployment and the award services; a push was never mentioned | Orchestrator |
| B19 | The bakery's limit becomes €300 per order and €1,000 per day (was €50 and €400, the shop page's values) | €50 is below any wholesale order: its usual 40 L of whipping cream is about €230, so every order would cite the spend limit | L3-2, wave 2 |
| B20 | Q16: a total with a product sold by weight is called an estimate ("Valio Aimo invoices the weight delivered"); the hotel still sends such an order to a person | Valio's answer of 14 Nov; wording only | L3a, L3b |
| B21 | Plain "milk" with no regular milk in confirmed stock gets a named low-lactose or lactose-free product as the first option, and the offer says it is an alternative to regular milk | A confirmed product a person can accept beats no suggestion; in the recording no regular milk has confirmed stock | L2b |
| B22 | A preference (most reliable, lowest carbon) may cost up to 25% more than the cheapest confirmed option before the cheapest comes first; a known delivery reliability under 90% ranks with an unknown one. Both are named "our threshold" in the sentence | A preference must not buy the tenderloin (€931) for a stew (€247) | L2b |
| B23 | Under "declared only", a product with no allergen statement is still never the first option; it is the labelled alternative | The safe product wins | L2b |

## C. Questions for the team (domain)

| # | Question | Default taken |
|---|---|---|
| C1 | Are the formula tolerances right (six nutrients within 15% or 1 g, salt 0.25 g, same fat source)? A biomedical member should sign them and the fat-source word list | As in P10 |
| C2 | `VEGETARIAN` as a claim a substitute must keep hides a pair Valio itself lists (Arla whipping cream for Valio's, because Arla does not declare it on cream). Keep it in the gate? | Kept |
| C3 | A brand word before the product ("Arla milk") is dropped silently by the reader. Ask about it, or add a brand field? | Dropped, as before |

## D. Questions for Valio's mentors (booth shape: context → what we did → what we got → is that expected?)

| # | Question |
|---|---|
| D1 | Of your 249 listed substitute pairs in the product file, our formula comparison finds 100 that keep the formula, 67 that differ and 82 that cannot be compared (figures from the whole catalog, before the per-100-ml change). Are listed substitutes meant to keep the formula, or only to be "close enough to offer"? |
| D2 | Your view of the buyer's log now shows every rule that fired, with the buyer's limit amounts and allergens masked. Is the decision without the buyer's private values what you meant by "all the steps and decisions"? |
