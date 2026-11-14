# A4 — the product as a Valio Aimo judge meets it

How I looked: the app ran offline with the brief's recipe (replay, no key, own data folder) and I sent every page and form through the test client, as one browser with one cookie jar. I read the HTML as text and looked at pictures: GET pages of the team's copy on port 8002, and my own captured copies of the form results. Nothing was posted to ports 8000 to 8002 and no outside service was called. Scripts, page dumps and pictures are in the scratchpad folder `replan/A4/` (`run2.py` to `run7.py`, `out3/` to `out6/`, `shots/`).

Limit of this run: it is replay with no model. The deployed app runs live with a Gemini key (README), and I did not touch it. Findings marked **[no model]** or **[replay]** appear there only when Gemini or the mock does not answer. Hours are my estimates.

## 1. In five lines

- A careful, honest product that reads like an audit report. In five minutes the wholesale judge sees that it works, and cannot say in one sentence what happened to his 1,000 litres or why. A result page holds 1,050 to 1,900 visible words below the form (counted, five examples).
- Hurt 1: it does what Valio said not to do. Three of the five examples end in "✓ Ordered by the agent" (V8). Example 3 orders another brand's barista oat drink alone (V10). Example 1 fills 565 of the 1,000 litres with coffee milk under "✓ Product type: met" (B5).
- Hurt 2: clicking the five examples in the order offered breaks the fifth, and then "Approve" on the first leaves it "Sent for approval". Cause: orders still waiting count in the day's spend.
- Hurt 3: the words. `FREE_FROM_LACTOSE`, `ST`, `plant_drink`, "claim", "P-01", "the gateway", "the mock", "sha256:…", "opt_1". The reason a person is needed is one screen below the outcome.
- The technical pass is strong: `/docs` is organised by the brief's three core points, a first call works in two minutes, errors are sentences. Do not spend hours there.

## 2. First five seconds, screen by screen

Seen as a picture unless marked (text).

| Screen | What the eye lands on | Clear or not | The fix |
|---|---|---|---|
| `/` at 1280×900 | Black bar, yellow "Replay: recorded Valio Aimo data, clock pinned to the recording", the title, three profile cards with euro limits | Not clear what to do. No example button on the first screen; the input box is cut by the bottom edge. "My kitchen" repeats the hotel's limits | Examples first, then the box, then "who is asking" as a small choice. 0.5 h |
| `/` at 390 px | The same, in one column. The menu bar does not wrap: "Standing orders" is cut, "Assumptions" is off screen; the "Who is asking" box runs past the right edge. Examples start about 1,750 px down, two phone screens | Not clear | Let the menu wrap; examples first. 0.5 h |
| Result, example 1 | The page opens at three boxes: green "Every claim confirmed", amber "A claim not confirmed", red "Excluded", then "Outcome: ? Sent for approval" | Offered, confirmed and not confirmed: clear. Why it went to a person, and to whom: not there. It is one screen lower, inside option 1. What was asked is above the strip | Put the reason and the next button in the Outcome box: "Sent to the purchasing manager: €2,580.64 is above the €750 limit per order." 1 h |
| Result, example 2 | Green box, "✓ Ordered by the agent" | Clear, and against V8 | Section 4 |
| Result, example 3 | Green box naming Fazer Aito "in place of" Oddlygood, "✓ Ordered by the agent" | Clear, and against V10 and V8. **[no model]** a grey note says "The buyer agent could not run: No GEMINI_API_KEY is set…" | Section 4 |
| Result, example 4 | Green box: "No option has every claim confirmed: price, quantity, allergens, and the date when one was asked for." Amber box: "1 confirmed product covers the 100 L asked for" | Not clear. A "confirmed product" sits under "A claim not confirmed", and the box does not say which fact is missing (the milk statement) | Amber box: "Elovena barista: Valio's data says nothing about milk. The dietitian decides." 0.5 h |
| Result, example 5, after the other four | "? Sent for approval" | Wrong for the story: the button promised reliability; the page says finance must approve because of €3,102.64 | Finding H2 |
| `/approvals` | "Deciding as" list, then the card: "? Waiting for approval", "Why a human is needed", two options side by side | Clear. The best screen | Keep |
| Order record after Approve, fresh browser | "✓ Ordered with human approval" | Clear | Keep |
| Order record after Approve, after five examples | Amber "? Sent for approval", black button "Decide as Demo approver Hanna" (who has just decided) | Not clear: looks as if Approve did nothing | Finding H2 |
| `/kitchen` | Title, a grey box ending in a 64-character hash, then a long form | Clear enough. Labels say the limits are ours | Hide the hash; collapse the 44 allergen boxes. 0.5 h |
| `/menu` (text) | A form of nine dishes with grams per serving and 14 stock boxes | The form is clear. The result is a table per dish; see M4 | M4 |
| `/standing-orders` (text) | One button, then a history table marked "Synthetic: made up for the demo", one box, the hint "Try the usual 100, then 290" | Clear. Works as written | Keep |
| `/assumptions` (text) | A table of 7,670 words with a "Where in the code" column | Clear for a programmer only | Five lines on top: what is ours, what is Valio's. 0.5 h |
| `/docs` | Title, "One flow", sections "Core 1: lookup", "Core 2: offer and order", "Core 3: authority and approval" with the brief's own words | Clear | Keep |

## 3. Findings, ranked

Criterion codes: D = 30% demo · M = 20% precise match · C = 20% autonomy and controls · X = 15% exceptions · O = 15% openness.

### HIGH

| # | Screen or route | What the judge meets | What it should be | Hours | Crit. |
|---|---|---|---|---|---|
| H1 | `/` examples 2, 3, 5; `/standing-orders` | "✓ Ordered by the agent … The agent placed this order alone for €402.00 net". Three of five examples and the 100-litre renewal (€248.00) order with no person. Valio: "for now deactivate automatic order … the final submition should always have the input from the user" (V8). The switch exists ("The agent may order alone at all", P-00) and is on in both profiles (`src/tta/policy/profiles/hotel-kitchen.yaml:14`, `allergy-ward.yaml:13`). With it off, the page says "Sent for approval … P-00" to a purchasing manager, which is a sign-off, not the user's own yes | The result ends in a suggestion and one button for the user, "Order this". The menu page already stops at the offer and waits for a button ("Send this option for approval" in the run I made). Ordering alone stays as a setting, shown off. **DECISION**: does "off" apply to the pages only, or to REST and MCP too | 1 (default off, button texts, documents) to 4 (a confirm step by the user, apart from approval) | C, D |
| H2 | `/`, `/approvals`, `/orders/{id}`, `/kitchen` | In one browser, examples 1 to 5 in order: the fifth says "today's spend would reach €3,102.64 … above the €3,000 limit per day … It needs finance", against its own button text and the README ("orders `470863` at €140.00"). Then Approve on example 1 as Hanna gives "? Sent for approval … still waiting for approval by finance", and the button offered is Hanna again. On `/kitchen`: I raised the limit per order to €3,000 and repeated the 1,000-litre request; still "Sent for approval", now "€5,161.28" for two requests nobody approved. Cause: waiting orders count in the day (`src/tta/orders/spend.py:13`). Each example alone, in a fresh browser, does what its button says (checked 2, 3, 4, 5) | The five examples must work in any order in one browser. Minimum: a daily limit that fits them, and "Decide as" naming a role still needed. Better: say "€174.00 ordered and €2,788.64 waiting for approval today" in the sentence. **DECISION**: should waiting orders count | 0.5 to 1.5 | D, C |
| H3 | `/` example 1; typed "1000 litres of milk by Monday" | Option 1 of the main example is 384 + 51 + 565 units; the 565 are "Arla Cafè milk", €1,497.25 of the €2,580.64, under "✓ Product type: met. Every product offered is of the product type 'milk'." Plain "milk" gives four products: whole low-lactose 132, semi-skimmed lactose-free 384, fat-free lactose-free 51, Cafè milk 433. Valio on coffee milk in a milk order: "no be explicit" (B5) | Coffee milk is its own type. When one product cannot cover the quantity, the page says so and offers the mix as a choice with the differences named, never as "met". The figures of example 1 will change; I did not measure the new ones | 1 to 3 | M, X |
| H4 | `/` example 3 | The buyer names product 473609. The page orders 100 × Fazer Aito barista (475224) alone, €174.00, and says itself "the brand is Fazer Aito, not Oddlygood®; Valio does not list it as a substitute", with "✕ Product asked for: not met" below. Barista drinks are the formula case Valio named (V10) | A substitute is never ordered alone. Headline: "Not available as asked. Closest: …", same brand first, with what differs. Minimum: `substitution_without_approval: NONE` for the hotel | 0.5 to 3 | X, C, M |
| H5 | `/` typed text | A doubt becomes an error or a silent exclusion, never a question (V5). **[no model]** "milk" gives an HTTP 503 page: "A service the gateway depends on cannot be reached. No GEMINI_API_KEY is set … milk is named with no quantity in digits and unit. Send the typed request to POST /v1/offers instead." The Finnish sentence and "10 kg of cake flour and 5 kg of baking chocolate" give the same. The ward's "50 litres of oat drink by Monday, no gluten" gives "✕ Nothing to order": four oat drinks are left out with "The product makes no statement about milk (AM): a dietitian must decide", and nobody is asked. The same screen says "Confirmed data only: no" in the request and "Confirmed data only was asked for" in the exclusion | A question on the page: "How much milk, and by when?" with the box filled in. For the ward: "4 oat drinks say nothing about milk and do not settle gluten. Send them to the dietitian?" No setting names, no "POST" | 1.5 to 2 | M, X, D |

### MEDIUM

| # | Screen or route | What the judge meets | What it should be | Hours | Crit. |
|---|---|---|---|---|---|
| M1 | Result page | Long. The approve button is after the options and the 19 excluded products. "Outcome" appears twice | Short top: asked · offered · not confirmed · who decides and why · button. The rest closed | 1 | D |
| M2 | Result strip | "Claim" means two things (a fact of Valio's data; a nutritional claim). For two lines, the green "Every claim confirmed" box says "covers 1 of the 2 request lines … 0 of 20 kg of chicken" | Name the boxes "Can be ordered, all checked" · "Possible, but not confirmed: stock" · "Left out, with the reason" | 1 | M, D |
| M3 | All pages | Words a kitchen manager does not use: `FREE_FROM_LACTOSE`, `GOODS_FROM_FINLAND_BLUE_SWAN`, "384 ST", "€2.48 per ST", "9,999,999,999 ST", "product type `plant_drink`", "pack: bulk", "AM, AW (strict)", "Confirmed data only", "P-01 profile rule: illustrative value", "opt_1", "net", "the gateway", "the mock", "Replay … clock pinned", "Policy and profile in force: sha256:…", "tta.v1.policy.evaluated · hash …" | One table of display names: "lactose-free", "cartons", "milk (AM)", "your limit per order". Rule ids and hashes only inside the audit trail | 1.5 | D, C |
| M4 | `/menu` | Two dishes (creamy chicken pasta × 100, oven pancake × 80): "The request is not valid. In this demonstration a request has at most 5 lines; this one has 8." **[replay]** butter, fish and rice read "✕ Cannot arrive in time … (20 not in the recorded capture)": it looks as if Valio has no butter. Amounts differ on one screen: 0.5 KG butter and "1 KG butter"; 4.8 KG rice and "5 KG rice". "9 × Evryday c3kg Beef Chuck roll" means 9 kg and reads as nine pieces. "left_out" in the lead | Lift the cap for menus. A grey state "Not in tonight's recorded data", never "cannot arrive". "0.5 kg, sold as 1 kg". "9 kg" | 1.5 | D, X |
| M5 | `/orders/{id}` | "What was ordered" stands above an order that waits, and above one that says "Rejected …: nothing was ordered" | "What was asked to be ordered" until it is ordered | 0.25 | D |
| M6 | `/orders/{id}` audit | Event times are real time ("14 Nov 12:46:31 UTC"); every other time is the recording's ("Saturday 14 Nov 2026 at 02:52"). Two clocks, about twelve hours apart | Label the column "recorded at (real time)" | 0.25 | C |
| M7 | Supplier view, page and `GET /v1/audit?reader=supplier` | All nine steps are there. The request loses "lactose-free" ("read as: 1,000 litres of product type milk") and a decision loses its reason ("a human at the buyer must approve this order."). Valio wants "all the steps and decisions" (B13) | Keep what was asked of Valio's products; give the kind of reason without the value ("above the buyer's own order limit"). **DECISION**: what the buyer hides | 1 | C, O |
| M8 | `/` example 3, `/kitchen` | Substitute ranks read "1., 12., 13." under "Listed by Valio Aimo as substitutes: 3". "€15.55 per sales unit" beside "€0.19 more per L". F-08 says a substitute that lacks a nutritional claim "always goes to the purchasing manager"; example 3's substitute "does not carry … FREE_FROM_PRESERVATIVES" and is ordered alone (the rule covers only `DIETARY_CLAIMS`, `src/tta/offers/substitutes.py:53`) | Number 1 to 3 inside the group. Price per litre. F-08: "a dietary claim, such as lactose-free or gluten-free" | 0.5 | X |
| M9 | `/` examples 3 and 4 **[no model]** | "The fixed rules could not read it either: 473609 is named with no quantity in digits and unit", under a sentence that says "100 litres" | No note when the example ran from its typed request | 0.25 | D |
| M10 | `/` typed "I need 50 kg of butter by Friday" **[replay]** | "✕ Nothing to order … 20 × Not in the recorded copy". The green box says "No option has every claim confirmed: price, quantity, allergens, and the date when one was asked for." | "Butter is not in tonight's recorded data. Try milk, cream, plant drinks or beef." | 0.5 | D |
| M11 | `/assumptions`, `docs/ASSUMPTIONS.md:27` | "Delivery reliability … It is not used in ranking yet." Example 5 ranks by it. The document line is wrong | Correct the row | 0.1 | O |

### LOW

| # | Screen or route | What the judge meets | Hours |
|---|---|---|---|
| L1 | `/kitchen` | 44 allergen boxes by GS1 code, among them "BP Linalool" and "NW Carrots". "AW Cereals" here, "cereals containing gluten (AW)" on results. Small input boxes | 0.5 |
| L2 | `/standing-orders` | The 290-litre renewal that waits is already a row of the history | 0.25 |
| L3 | REST | Problem types point to `https://tta.example/problems/…`. `price_valid_to` is `9999-12-31` for "no end date". The MCP tool list is 94 KB | 0.5 |
| L4 | `/` empty box | "Nothing to run. Write a request in the box, or pick one of the examples." Fine | 0 |

## 4. Against Valio's answers

- **V8, ordering without the user.** Today: examples 2 (€402.00), 3 (€174.00) and 5 (€140.00, alone in a fresh browser) and the 100-litre renewal (€248.00). The same over REST: `status: ORDERED, placed_by: AGENT` for `scenario_2`. The judge who said "deactivate automatic order" sees "✓ Ordered by the agent" on the second click and concludes we did not listen. The setting he called "a question for later" is already built; show it, switched off.
- **V10, substitutes and formula.** Today: example 3 (H4). In example 4 the first ranked substitute for Elovena barista is again Fazer Aito, "✓ Can be ordered", and second is "Alpro Rice drink", a rice drink for a barista oat drink. The ranking uses allergens, category and price; brand is only mentioned. Example 1's "option" is three milks of different fat content and use. He would say: this is the mistake I warned about.
- **B5, coffee milk.** Today: 565 of 1,000 litres in the first example, 433 for plain "milk" (H3). He answered "no be explicit" and sees it in the first click.
- **V5, ask when unsure.** Asked well: example 4 goes to the dietitian with the reason, and the web evidence card is labelled "not Valio data". Decided alone: the ward's request drops 4 oat drinks whose data says nothing about milk, with the words "a dietitian must decide", asks nobody and ends "Nothing to order"; "milk" with no quantity is an error page **[no model]**; the menu drops butter, fish and rice without a question **[replay]**. He would say: good instinct, but the only way it asks is the approval queue.
- **B13, what Valio sees.** M7.
- **V6, the date.** The first example excludes 19 of 30 products, 17 for "Cut-off passed on Thursday 12 Nov at 15:00". It is honest, and it makes the wholesaler look unable to deliver most of its lactose-free milk. Valio said the date is ours to choose. An earlier pinned clock would change every demo figure; I did not measure it.

## 5. The technical judge's pass

- **First call in two minutes: yes.** `/docs` renders Swagger UI, loaded from jsDelivr: the picture taken at load shows its "LOADING" spinner, the one taken later shows the page. 23 operations, each with a summary; 10 carry examples. `GET /v1/authority` with `demo-agent-hotel-kitchen` answers 200 with the rules as sentences. `POST /v1/offers` with the example `scenario_1` answers 201 in 0.36 s with €2,580.64 and €1,010.00. `POST /v1/orders` answers `PENDING_APPROVAL`; the approver's token then gives `ORDERED`.
- **Two snags.** The token names are inside the security scheme, shown only after "Authorize" is clicked: put one line at the top, "Authorize with `demo-agent-hotel-kitchen`, then try `GET /v1/authority`." The example body of `POST /v1/orders` holds a fixed offer id (`off_af4c9bb551f2`); an id that is not in the book answers 404 "No offer has this id.", so say in the example "paste the `offer_id` you just received". 0.2 h for both.
- **Errors are readable.** `application/problem+json` with a title, a sentence and the field: no token, a wrong token, a missing `Idempotency-Key`, a missing field, an unknown offer. An agent that tries to approve gets 403: "An agent cannot approve or reject an order (F-06)."
- **What an agent may do alone is clear before it orders:** `GET /v1/authority`, and a verdict (`AUTO`, `APPROVAL`, `BLOCK`) with the rules that fired on every option.
- **MCP, read offline:** `initialize` and `tools/list` answer through the test client. Eight tools, plain descriptions, "No tool approves an order". Without a token: 401.
- **Audit:** the buyer's view is 39 KB and the supplier's 24 KB for one order; same events, same hashes. A buyer's token may read the supplier's view; the supplier's token asking for the buyer's view gets 403 with a sentence.
- **Weak:** the opening text of `/docs` has a 200-word paragraph on limits. No `servers` entry. `auto_order_enabled: true` is the first thing `/v1/authority` shows (V8).

## 6. What is already good and must not be broken

- The page opens at a summary of four boxes. Keep the idea; change the words.
- The ticks per fact (price, quantity, delivery date, allergens, origin) and the sentence "Valio reports 9,999,999,999 … a placeholder that means the stock is not known".
- The approval card: "Why a human is needed", the role, the options side by side, the refusal for a wrong role.
- Every "ours" label: "Illustrative profile", "Synthetic: made up for the demo", "Demo approvers: invented names", recipes "ours and illustrative", web evidence "not Valio data".
- The excluded list, with a count and a reason for each product.
- `/standing-orders`: one hint, two numbers, and it does what it says.
- The two audit views with the hash line; the REST errors; `/docs` organised by the brief.
- Speed: every page answered in under 0.1 s in replay.
- Each example, alone in a fresh browser, does what its button says.
