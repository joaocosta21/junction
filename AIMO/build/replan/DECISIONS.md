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
| A6 | **A signing key for the public link.** Without `TTA_SIGNING_KEY` as a Modal secret the link signs with a new demo key at every start. Do you want a fixed key set at the redeploy? (I can generate one; it would live only in Modal's secret store.) | Demo key | |
| A5 | **`CLAUDE.md` is out of date** and the run may not edit it: it names Gemini as the agent's model and says Aiven was dropped. Yours to change | Listed here | |

## B. Decided by the run, as the owner would (say so if you disagree; each is one change to undo)

| # | Decision | Reason | Where |
|---|---|---|---|
| B1 | A flavoured product does not replace a plain one, even when Valio lists the pair (4 of Valio's 249 pairs, e.g. coffee milk → vanilla coffee milk). Another flavour of an already flavoured product (strawberry → mango yoghurt) stays and is said | A kitchen making coffee does not want vanilla and nut in every cup; "nutty" also raises an allergen question | L2a-R, done |
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
| B16 | Scenario 3 (oat-drink substitute) can be shown at either clock: after B1 to B4 the demo clock offers Valio's own listed substitute `471690` (€155.50), the default clock a barista oat drink (€174.00) | Both are defensible answers | E1 |
| B17 | The whole suite is run once per wave, not after every lane | Lanes change the same tree at the same time; each lane's own tests are run before its commit | Orchestrator |
| B18 | No push, although fetch and outside calls are now approved | You approved fetch, deployment and the award services; a push was never mentioned | Orchestrator |
| B19 | The bakery's limit becomes €300 per order and €1,000 per day (was €50 and €400, the shop page's values) | €50 is below any wholesale order: its usual 40 L of whipping cream is about €230, so every order would cite the spend limit | L3-2, wave 2 |
| B20 | Q16: a total with a product sold by weight is called an estimate ("Valio Aimo invoices the weight delivered"); the hotel still sends such an order to a person | Valio's answer of 14 Nov; wording only | L3a, L3b |
| B21 | Plain "milk" with no regular milk in confirmed stock gets a named low-lactose or lactose-free product as the first option, and the offer says it is an alternative to regular milk | A confirmed product a person can accept beats no suggestion; in the recording no regular milk has confirmed stock | L2b |
| B22 | A preference (most reliable, lowest carbon) may cost up to 25% more than the cheapest confirmed option before the cheapest comes first; a known delivery reliability under 90% ranks with an unknown one. Both are named "our threshold" in the sentence | A preference must not buy the tenderloin (€931) for a stew (€247) | L2b |
| B23 | Under "declared only", a product with no allergen statement is still never the first option; it is the labelled alternative | The safe product wins | L2b |
| B24 | F-11 (formula) is a fixed rule: a profile or a request can add the check and never remove it. A substitute that cannot be compared counts as not keeping the formula | P10 decision 4; Valio: not sure means ask | L3-2 |
| B25 | Ward and bakery let a preference add 10% without a person; hotel and school set no limit. No profile can set more than 25% | They are the two that prefer reliability | L3-2 |
| B26 | The photo upload left the first page; the route stays | No model reads photos tonight, so a visitor's own photo would always be refused | L4c |
| B27 | The bakery's owner also decides allergen questions (the bakery gets a dietitian role held by the owner) | A bakery-café has no dietitian; without this a bakery order with an allergen doubt could never be completed | L4-2 |
| B28 | Orders waiting for a person still count toward the day's spend limit, and the approval says how much is ordered and how much is waiting | PLAN decision 9; a limit that waiting orders can slip under is no limit | L4a |
| B29 | A buyer holds at most 20 standing orders here, and nothing deletes one. On the public link the shared hotel and ward books can fill up and stay full until the data is wiped | Bounds a flood found by the security review; a delete route is not built | L4a |
| B30 | "Leave the line out" on the dietitian's card rejects the whole order, and the card says so | The interface cannot drop one line of an order | U3 |
| B31 | The brief's "proactive selling agent" is built as Valio Aimo's own suggestion of a related product: same type and brand as one the customer buys, never ordered by them, confirmed stock, checked like any product, shown last and apart, on by default | The product file has no "new" or "seasonal" mark, only a record-change date | L4-2a |
| B32 | At most one suggestion per kind and three in all; Valio's own stays silent when only another pack kind passes or one unit is in stock | Three forgotten items hid the cheaper line; a portion milk for a school's bulk order is not a suggestion | L4-2d |
| B33 | Confirmed stock of a like-for-like product fills a gap before an unconfirmed product does, even when it covers less (37 L confirmed of the same formula before 52 L unconfirmed) | A kitchen can rely on confirmed stock; the unconfirmed product stays as a labelled alternative | L2a-2 |
| B34 | Where the request says the formula matters and no formula-keeping substitute can be ordered, the product asked for (quantity not confirmed) is shown before a confirmed substitute that changes the formula. Both go to a person | Suggesting tzatziki for crème fraîche in a recipe is worse than asking | L2a-2 |
| B35 | The bakery's profile ("the formula matters") labels and ranks substitutes the same way as a request that says so | Otherwise the bakery sees the formula-changing product first unless every request repeats the word | L4-2d |
| B36 | Valio's token cannot read a customer's people, history or limits (403) | The same line as Valio's view of the log | L4-2b |
| B37 | Offers and orders are signed by the gateway with a demo key that changes at every start unless `TTA_SIGNING_KEY` is set; every proof says "demo key" and nothing says "signed by Valio" | An honest trust layer without claiming Valio's signature | L4-2b |
| B38 | A manufacturer's page is shown as evidence only when its variant marks agree with the product (fat percentage, lactose-free, UHT, flavour, pack). The chilled version's page is not shown for the UHT product | A page for a sibling can state different allergens; a false match in front of the person who signs is worse than no page | EV |
| B39 | A word in a request that is a brand in Valio's catalog ("Arla") is kept as a term the product must carry; any other unknown word before the product is still not asked about | "Arla whipping cream" must not come back as another brand; asking about every adjective would refuse ordinary sentences | L1-3 |
| B40 | "Cream for whipping" is read as whipping cream with the formula marked as mattering | The use names the product a kitchen means | L1-3 |
| B41 | "A milk substitute" is read as a plant drink, and the reading says so | It is scenario 2's own sentence | L1-2 |

## C. Questions for the team (domain)

| # | Question | Default taken |
|---|---|---|
| C1 | Are the formula tolerances right (six nutrients within 15% or 1 g, salt 0.25 g, same fat source)? A biomedical member should sign them and the fat-source word list | As in P10 |
| C2 | `VEGETARIAN` as a claim a substitute must keep hides a pair Valio itself lists (Arla whipping cream for Valio's, because Arla does not declare it on cream). Keep it in the gate? | Kept |
| C3 | (decided, B39) |  |
| C4 | Savoury flavours (garlic, smoke, herbs, cheese) are read only through the word "flavoured". Extend the list? | Not extended |
| C5 | With no like-for-like candidate, the last-resort list for a coffee milk includes sour milks. Should another product type never be offered, even as a last resort for a person? | Offered as last resort |
| C6 | The list of hosts treated as "the manufacturer's page" is ours and unverified: elovena → `elovena.fi`, `raisiofoodsolutions.fi`; oddlygood → `oddlygood.com`; fazer → `fazer.com`; valio → `valio.fi`, `valio.com`; arla → `arla.fi`, `arla.com`; alpro → `alpro.com`. Confirm or correct | Any other host reads "a web page whose owner was not checked" |
| C7 | Tzatziki ranks as a stand-in for crème fraîche and smetana (same category; no product type of ours separates them). Add types? | Not added; F-11 sends it to a person where the formula matters |

## D. Questions for Valio's mentors (booth shape: context → what we did → what we got → is that expected?)

| # | Question |
|---|---|
| D1 | Of your 249 listed substitute pairs in the product file, our formula comparison finds 100 that keep the formula, 67 that differ and 82 that cannot be compared (figures from the whole catalog, before the per-100-ml change). Are listed substitutes meant to keep the formula, or only to be "close enough to offer"? |
| D3 | Is "Delight" (`471690`, fat 1.5 g against 3 g) meant as the like-for-like replacement for the barista oat drink `473609`? Our formula check calls it a different formula; it ranks first only because you list it |
| D4 | Your brief names a selling agent for new or seasonal products. We looked for a launch or season mark in the product file and found only `synkkaData.lastUpdated`. Is there such a mark, or did we miss it? Meanwhile we suggest a related product and label it as yours |
| D5 | Who makes your own-label products "AIMO TURKISH YOGURT 5KG 10%" (`464608`) and "AIMO MAUSTAMATON JOGURTTI 5KG" (`464517`)? We found a Saare page and a Valio A+ page and did not show either, because nothing says they are the same product |
| D2 | Your view of the buyer's log now shows every rule that fired, with the buyer's limit amounts and allergens masked. Is the decision without the buyer's private values what you meant by "all the steps and decisions"? |
