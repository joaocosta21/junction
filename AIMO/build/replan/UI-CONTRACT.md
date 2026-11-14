# What the interface needs from tonight's build

For the teammate who builds the interface. The build session keeps this file current: after each task it adds the fields, routes and sentences a page should show or call. **The build does not edit `src/tta/ui/` or `tests/ui/`**, except the lines listed at the end.

The pages are a front end to the typed interface; the brief says "this is not about replacing today's e-commerce UI with a chatbot". Use Valio's own words where the webshop has one (`P3-webshop.md`, the mapping table): "Closing time", "Delivery date", "N pcs available in storage" for confirmed stock, "Deliverable <date>" where no quantity is known, "Alternative products", "Standard order".

## For Gabriela: the shop page, in this order (`C2-frontend-branch.md`)
The review of `frontend-shop` says: build on top of it. It runs, it is safe on the points checked, and its answer card passes the five-second test the old pages fail. Four things must change before a Valio judge sees it; the first and the last are the two things Valio told us not to do.

| # | What | Where | Hours |
|---|---|---|---|
| **F1** | **Nothing is ordered or sent without a click.** The defaults are switched off already in the merged branch (`auto_order_enabled: false`, `autoSend: false` for all four, storage key `tt-shop-v2`). Still yours: one button, "Confirm order", and the wording "Ordered by your agent" | `views/assistant.js` (`act`, line 80; `verdictBox`), `views/parts.js` (`statusTag`), `kitchens.js` (`autoSend`), `store.js:5` (a new storage key, or a browser that already opened the page keeps the old defaults) | 1 |
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

### L5 — customers and suggestions (pure functions; the routes come with L4-2)
- **Customers, from `tta.customers.shipped_customers()`** (the list route is L4-2's). Each: `customer_id`, `name` ("Harbourside Hotel"), `kind`, `detail`, `customer_number`, `address`, `delivery_days`, `contact {name: "Hanna Laine", title: "Purchasing manager"}`, `people {"purchasing_manager": "Hanna Laine", "finance": "Mikko Saari", "dietitian": "Leena Koski"}`, `usual[] {product_id, product_type, unit, use}`, `history[] {delivered_on, quantities, prices}`, `standing_orders[]`, `synthetic: true`. Every history row is shown with "Synthetic: made up for the demonstration". The page's typed-in history should be replaced by this: its hotel row dated 13 Nov is after the demo clock.
- **A suggestion** (`tta.contracts.suggestion.Suggestion`; reaches a page as `offer.suggestions[]` and `GET /shop/api/suggestions` once L4-2 wires it): `kind`, `sentence`, `product_id`, `name`, `quantity`, `unit`, `evidence.orders_matching` / `orders_considered` / `synthetic` (show under "Why?"), `effect.net_change_eur` (larger pack), `accept_request` (post to `/v1/offers` for "Add to the request" or "Switch"; a suggestion never adds itself), `standing_order_id` (the trend's "Store 84 L?").
- **Sentences a person reads** (catalog names, measured offline):
  - FORGOTTEN_ITEM: "In 7 of your last 8 orders with Arla Semi skimmed milkdrink 1 L UHT lactose free Suomesta (469363) you also ordered Arla Pro Cooking cream 10% 1 L UHT lactose free (463797), usually 10 L. It is not in this request. From a synthetic order history."
  - USUAL_PRODUCT: "Your usual milk is … (469363): it is in 8 of your last 8 orders of milk. Confirm it before it is ordered. From a synthetic order history."
  - USUAL_QUANTITY: "You usually order 100 L of … (469363): the median of your last 6 orders, which ranged from 98 to 104 L. Confirm the quantity before it is ordered."
  - QUANTITY_TREND: "Your last 3 orders of Oatly Oat Drink Semi 1L (470863) have a median of 84 L against 70 L for the 3 before (+20%), each higher than the last. The standing order still says 60 L. Store 84 L? From a synthetic order history."
  - LARGER_PACK: "Oatly iKaffe Oat drink 1,5L (473278) is the same product in a larger pack: €1.48 per litre against €1.78. 40 × 1.5 L cover the 60 L for €88.80, €18.00 less. 156 are confirmed in stock for delivery on Monday 16 November."
  - The usual-product question: "Your last 8 orders of milk hold A (id) 4 times and B (id) 4 times. Which one do you mean?"

### B0 — the baseline
| Field, route or sentence | Example | What a person should read |
|---|---|---|
| `profile.auto_order_enabled` (`GET`/`PUT /shop/api/kitchen`, `authority.profile`) | `false` | The setting exists again, off by default; a page that does not send it gets `false`. "Off: every order needs a person." |
| The setting's rule id | `F-10` | `views/settings.js:190` prints `rule("P-00")`: P-00 no longer exists, the rule is F-10 |
| `authority.rules[]` F-10 | `fixed: false` | F-10 left the locked list. Off: "Every order needs human approval before it can be confirmed: this profile does not let the agent place an order alone. …" On: "This profile lets the agent place an order alone, and only when no rule asks for a human and every statement of the offer is confirmed: …" |
| `decision.verdict == "AUTO"`, `order.placed_by == "AGENT"` | ward, 200 L, setting on | Only when the buyer switched the setting on: "The agent placed this order alone for €402.00 net: …" |
| `decision.sentence`, setting on, a statement not confirmed | | "The agent orders alone only when every statement of the offer is confirmed (F-10). Not confirmed: the origin of 464013. It needs the purchasing manager." |
| `offer.notes[0]` when a line asks for `milk` | | "Request line 1: Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk. Ask for coffee milk by name (product type coffee_milk) to get it." |
| Product type `coffee_milk` | `{"product_type": "coffee_milk"}` | A typed request or an example button can ask for it |
| `offer.time_basis` | `"recording"`, `"supplier"`, `"demo_setting"` | What `offer.time_now` rests on |
| `GET /healthz` → `clock` | `{now, basis, demo_clock_set, recorded_at, sentence}` | "Demo clock: Thursday 12 November 2026 at 14:15 (UTC+02:00), set with TTA_DEMO_CLOCK. Order deadlines are judged against it. We chose it: … The audit trail is stamped with the real time." |
| Scenario 1 on any page | | 435 L of 1,000 L, €1,083.39, P-01 and P-03; alternative €1,010.00 |

### L3b — Valio's view of the log (no new route or field needed: the shop page prints `events[].sentence`, `rule_ids`, `actor.display_name`)
- `actor.display_name` for a human in Valio's view: "The buyer's purchasing manager" (was "A human at the buyer"); `actor.role`: `"purchasing_manager"`.
- `rule_ids` in Valio's view: every rule that fired, e.g. `["P-01","P-03"]` (was `[]`).
- `policy.evaluated`: "The buyer's rules were checked for option opt_1: the buyer's purchasing manager must approve this order. Rules that applied: P-01, a rule the buyer set (the order is above the spend limit per order; the amount is not shown): approval by the buyer's purchasing manager. … The strictest outcome among the rules that applied decides."
- `offer.created`: "… 2 products were considered and left out: 1 that cannot be delivered (464440); 1 sold in portion packs, which the request does not ask for (463203)."
- `approval.decided`: "The buyer's purchasing manager approved order ord_… . This approval accepts rules P-01 and P-03."
- Facts a page may show for Valio: `facts.decision.rules[] {rule_id, title, fixed, verdict, approver_role, product_id}`, `facts.decision.required_roles`, `facts.offer.left_out[] {product_id, name, request_line_index, reason}`, `facts.offer.excluded_by_reason`.
- A total with a product sold by weight, both readers: "for about €506.40 net (an estimate: sold by weight, Valio Aimo invoices the weight delivered)".

### L1 — the reader
| Field or sentence | Example request | What a person reads |
|---|---|---|
| 422 `question` (the question alone) | `Ward 4 200 litres of milk` | "Is the quantity 4,200, or 200? Write it without a space, for example 4200." |
| 422 `not_read` | `100 litres of milk, not lactose-free` | it says "not lactose-free", and the rules cannot tell whether "lactose-free" is wanted or not |
| 422 `detail` | `5 dl of cream` | "The fixed rules did not read this request, and nothing was guessed: it gives a quantity in "dl" … "5 dl" is 0.5 litres. Is that the quantity? Then write "0.5 litres"." |
| 422 `read_by` | | `rule-based` |
| `question` for a case | `10 cases of oat drink by Monday` | "How many litres, kilograms or single packs is that? Write the quantity in one of those units, or name the product by its 6-digit number." |
| `question` for milk for coffee | `200 litres of milk for coffee` | 'Is it milk for coffee? Then write "coffee milk". For both, write each with its own quantity.' |
| `Reading.sentence` when STRICT was assumed | `50 litres of gluten-free oat drink by Monday` | "… No allergen rule was given for cereals containing gluten (AW): read as strict, the safe reading. A product with no allergen statement goes to a person." |

### L2a — substitutes and formula
- `candidates[].gives_up` and `line.substitute.gives_up` now end with the formula in numbers: "… Different formula: fat 15 g, not 38 g; saturated fat 8.8 g, not 22 g; carbohydrate 5.3 g, not 2.8 g per 100 g." · another fat source: "… Its ingredient list names a vegetable oil or fat; the original's does not." · kept: "… Same formula within our tolerance of 15% or 1 g per nutrient (salt 0.25 g): fat 38 g against 36 g; …" · cannot be compared: "… the figures of the product asked for are per 100 ml and this product's are per 100 g."
- `candidates[].sentence`, last resort: "… It does not carry the original's nutritional claim VEGAN. Last resort: no candidate that keeps every dietary claim of the original can be ordered, so a person decides whether this one will do."
- `SubstituteResult.notes[]`: "13 candidates that lack a dietary claim of the original are held back as a last resort: 4 that keep every dietary claim can be ordered."
- `category_distance`: 0 (same category) or 1 (another, only a pair Valio lists). The heading "Other products of the same category" is now true for every unlisted candidate.
- `product.nutrition`: `{"fat": 38.0, "saturated_fat": 22.0, "protein": 2.0, "carbohydrate": 2.8, "sugars": 2.8, "salt": 0.07, "basis": "G"}` — two columns of numbers for the substitute comparison.

### L3a — rules, wording, four profiles
| Field | What a person reads |
|---|---|
| `decision.sentence`, F-10 only | "Prepared: confirm to order. The agent prepares the order, a person confirms it (F-10): the purchasing manager confirms." |
| `order.status_sentence`, waiting | "Prepared: confirm to order. Waiting for the purchasing manager to confirm, by Sunday 15 November 2026 at 17:00 (UTC+02:00) (rule F-10: a person confirms every order)." |
| `order.status_sentence`, one of two roles signed | "Confirmed by Hanna Laine (purchasing manager); still waiting for finance to confirm, by … " |
| `order.status_sentence`, ordered | "Confirmed by Jussi Nieminen (purchasing manager): ordered for €402.00 net." |
| `order.status_sentence`, placed by the agent | "The agent placed this order alone for €402.00 net: no rule asked for a human and every statement of the offer is confirmed." |
| `decision.sentence`, `approval.reasons[]`, limit rules | "… above the €750 limit per order of Harbourside Hotel (P-01)" |
| `authority.profile.display_name` | "Harbourside Hotel", "City Hospital, Ward 4", "Kilo School", "Kallio Bakery" |
| `authority.rules[]` P-06 | "A product sold by variable weight goes to the purchasing manager: its total is an estimate, because Valio Aimo invoices the weight delivered, which can be lower or higher than the weight ordered." |
| Profiles `school-kitchen`, `bakery-cafe` | school: `excluded_allergens: [AN, AP, AS]`, STRICT; bakery: `substitution_without_approval: NONE`. `kitchens.js` still says DECLARED_ONLY for the school and SAME_CATEGORY for the bakery: to change with the customers route (wave 2) |

### L2b — options and safety
| Field | What a person reads |
|---|---|
| `options[].title` | "Alternative: allergen not ruled out" · "Alternative: quantity not confirmed, allergen not ruled out" · "Confirmed option ranked by delivery reliability" |
| `options[0].summary`, safe first | "1 confirmed product covers the 10 L asked for, for €20.10 before tax. Its data rules out every excluded allergen; the alternative whose data does not costs €2.70 less." |
| `options[].summary`, doubtful alternative | "Fazer Aito Professional Barista Oat drink, gluten-free 1L UHT (475224) for the 10 L asked for, €17.40 before tax. The product data does not rule out cereals containing gluten (AW), so a dietitian must decide." |
| `options[0].summary`, coffee milk | "… for €1,083.39 before tax. Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk." |
| `options[].summary`, preference | "… €40.60 more than the cheapest confirmed option, for a delivery reliability of at least 100% instead of unknown, a premium of 122.7%." |
| `options[].net_above_cheapest` | `"40.60"`: what the preference costs |
| `offer.notes[]` | "Request line 1: no allergen rule was given for milk (AM), so it was read as strict: …" · "… no product whose data rules out cereals containing gluten (AW) can be offered, so no option is suggested as safe: a dietitian must decide on each alternative." · "… 467014, whose quantity Valio does not confirm, would cost €382.20, not less than the €246.96 of confirmed stock that covers the whole quantity, so it is not offered as an alternative." · "… a request for milk is filled with regular milk first. Lactose-free or low-lactose milk is offered only as a named alternative: 463047." |
| `offer.suggestions` | `[]` until wave 2 |
| `lines[].substitute.formula`, `.last_resort` | filled on an offer's stand-in line |

### L3-2 — the formula rule, the preference rule, the log's wording
- `decision.fired[]` with `rule_id: "F-11"`: show `sentence` ("Cooking blend 15% 1 L (463975) would replace Arla Pro whipping cream 36% 1 L (469346) where the formula matters (Kallio Bakery uses its products as ingredients), and the data does not show the same formula: Different formula: fat 15 g, not 36 g; …"); `facts["line.substitute_formula_differences"]` is a list for bullets.
- `decision.fired[]` with `rule_id: "P-09"`: "This option is ranked by the buyer's preference and costs €20.00 more before tax than the cheapest confirmed option, a premium of 20%, above the 10% that Harbourside Hotel lets a preference add without a human."
- `GET /v1/authority` → `profile.formula_matters`, `profile.max_preference_premium_ratio`; two new rows under "The rules in force" (F-11, P-09).
- Audit `events[].sentence` already says "384 pcs of 469363", "a recorded copy of Valio Aimo's data" and names the buyer: the rewrites in `words.js:24-39` can go.
- Order confirmed under F-10 alone: "Order ord_… is ordered, confirmed by Hanna Laine (purchasing manager): 200 pcs of 464013 for €402.00 net."
- To change on the page: `kitchens.js:194-195` bakery `max_order_net_eur: 300`, `max_daily_net_eur: 1000`, `formula_matters: true`, `substitution_without_approval: "NONE"`; the old kitchen page's form has neither new setting.

### L4a — standing orders, menus, orders (full table: `AIMO/build/handback/L4a.md`)
- `order.record_note` ends "No payment is taken here: the buyer is assumed to be a Valio Aimo credit customer, invoiced after delivery for what is delivered."
- `approval.reasons[]`, one more line when P-02 fired: "Before this order, today's spend of this buyer is €2,688.78 before tax: €0.00 ordered and €2,688.78 waiting for approval. A waiting order counts until a person rejects it or its time to decide passes."
- `POST /v1/standing-orders` 422: "This buyer already has 20 standing orders, the most one buyer sets up here. Renew one of them … instead of setting up another."
- Menu plan: `ingredient.sentence` for a stand-in names the allergens it adds; `plan.notes[]` says what cannot be sourced and that the lines stay in the offer; `plan.cannot_be_sourced[].sentence`. The label "Cannot arrive in time" (`ui/menu_page.py:49`, `templates/menu.html:92`) should read "Cannot be sourced".

### L4b — the API edge
- `GET /.well-known/api-catalog` (RFC 9727 linkset) and `GET /llms.txt`: "An agent that knows only the address finds the interface." Worth a link in the shop's "For developers".
- `/mcp/` with a foreign `Origin`: 403. `Location` on the 201 of an offer and an order. `POST /v1/orders` without a key: 400.
- Rate-limit refusals now name 15 (browser), 60 (address) and 240 (all callers) for request readings.

### L2a-R — is a product replaceable
- `candidates[].gives_up` and `lines[].substitute.gives_up` begin with the verdict: "Replaceable: same type, same use, not flavoured, same formula within tolerance." · "Replaceable as far as the data shows: … the formula cannot be compared." · "Not a like-for-like replacement: flavoured with nut and vanilla; the product asked for is not flavoured." (other reasons: "another product type (coffee milk, not milk)", "not made for coffee, as the product asked for is", "a different formula (fat 1.5 g, not 3 g)").
- `notes[]`: "12 candidates that are not the same kind of product (11 flavoured where the original is not, or the reverse and 1 of another product type) are held back as a last resort: 4 of the same kind can be ordered."
- `lines[].substitute.last_resort` is also true for a flavoured or other-type stand-in.

### U3 — done on the pages
The page's customer values equal the profile files (`tests/ui/test_shop_customers.py`); `GET /shop/api/offers/{offer_id}`; the substitute note with its table; the dietitian's three choices; F-11 and P-09 rows in "rules in force"; the old kitchen page's two new settings. Left: the suggestions box and the customers route (after L4-2d), the menu label "Cannot be sourced", a real-browser check at 390 px.

### L4-2a — suggestions as a service (reach a page once L4-2d wires them)
- `offer.suggestions[]`: `kind`, `serves`, `product_id`, `name`, `quantity`, `unit`, `sentence`, `effect.net_change_eur`, `availability`, `stock_confirmed`, `checks[]`, `evidence`, `accept_request` (the button posts it to `POST /v1/offers`; nothing is added to the current offer).
- `kind == "FROM_SUPPLIER"`: show last and apart, under "Suggested by Valio Aimo, not from your orders". Example: "Valio Aimo suggests Oatly Oat Drink Whole 1L (470889): a plant drink of the brand Oatly, like the Oatly Oat Drink Semi 1L (470863) you usually order, and in none of your 8 past orders (a synthetic history). … 249 sales units are confirmed in stock for delivery on Monday 16 November. Adding it costs €1.40 before tax."
- Cheaper line: "Oatly iKaffe Oat drink 1,5L (473278) costs €1.48 per litre against €2.88 for Oatly iKaffe 0,5L (468319): 49% less. It keeps the formula within our tolerance. … 20 × 1.5 L cover the 30 L for €44.40, €42.00 less."
- Standing-order page: `standing_order_trends(...)`; school: "… a median of 84 L against 70 L for the 3 before (+20%) … The standing order still says 60 L. Store 84 L?" Standing orders at start: `so_demo_hotel_milk` (8 renewals), `so_ward_plant_drinks` (16), `so_school_weekly` (8), `so_bakery_weekly` (8); `standing.html:29` still says "six synthetic past weeks".
- "Why not" under a list (buyer's view only): `dropped[].sentence`.

### L4-2c — evidence
- `approval.evidence[]` is present for any allergen doubt that goes to a person. Found, listed host: "The manufacturer's page “Elovena Kaurajuoma kahviin” on raisiofoodsolutions.fi says: contains KAURA; free from Gluteeniton, Laktoositon, Maidoton, Kananmunaton. Asked about milk (AM): Valio Aimo's data states nothing; the page says free from, in its words “Maidoton”." · unlisted host: "A web page whose owner was not checked, “…” on shop.example says: …" · a page that names an excluded allergen: "… check the product before approving. What a page says can add a doubt and never removes one."
- Headings (`tta.evidence.wording.heading`): "Manufacturer's page, not Valio Aimo data" / "A web page that names this product, not Valio Aimo data (its owner was not checked)". The fixed heading in `_evidence.html` and `shop/js/views/approvals.js` is untrue for an unlisted host: use a neutral heading until `Evidence.is_owner_page` exists.

## Changed under the interface (only figures, status words or field names; filled in by the build session)

| Task | File and line | Before → after | Why |
|---|---|---|---|
| merge | `src/tta/ui/static/shop/js/kitchens.js:53` | `auto_order_enabled: true` → `false` | Valio: no order without a person. The setting stays on the settings view |
| merge | `src/tta/ui/static/shop/js/kitchens.js:87,125,164,199` | `autoSend: true` → `false` | Nothing is sent for approval without a click; the page already shows "Send for approval" |
| merge | `src/tta/ui/static/shop/js/store.js:5` | `tt-shop-v1` → `tt-shop-v2` | A browser that already opened the page would keep the old defaults |
| merge | `src/tta/ui/templates/index.html` (the customer cards) | "Every order requires human approval." → the same, plus the limits and who they decide | Sofia's commit dropped the limits; a test pins them |
| merge | `tests/ui/test_shop_api.py:106` | `ORDERED` → `PENDING_APPROVAL` | An order inside the kitchen's limit waits for a person too |

**B0 (the interface is ours since 14 Nov 17:33, so these are a record, not a request):** `kitchen_page.py` and `kitchen.html` have the "Ordering alone" checkbox again (rule F-10); `index.html` and `menu.html` follow the setting; `standing_page.py:145` uses `ReplayGateway.from_settings`; `site.py`'s banner names the demo clock when one is set; pinned figures in `tests/ui/test_approvals.py`, `test_order.py`, `test_run.py`, `test_kitchen_page.py`, `test_shop_api.py` moved with scenario 1 (€2,580.64 → €1,083.39) and with P-00 → F-10. `kitchens.js` not changed.
