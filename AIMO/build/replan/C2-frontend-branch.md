# C2 — review of the shop page (`origin/frontend-shop`, commit `798b4d3`)

Reviewed 14 Nov, 15:55–16:20, in a separate worktree. Nothing was committed, merged or pushed.

**How to read this:** "ran" = I executed it (replay, no keys, own data folder, port 8011, stopped afterwards). "page" = seen in headless Chrome driven over the DevTools protocol (clicks and typing on the real page). "read" = from the code only. Scratch files and screenshots: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/C2/`.

**Not done:** `shop.css` not read; no JavaScript linter run; the school's two-signature path was run through the routes, not clicked on the page; the rate limit of the decision route not measured; `PLAN.md` sections 1, 2 and 4 only skimmed (section 5, `BRIEF.md` section 2 and the runbook's "What is already decided" were read in full); `A3`, `A5`, `P2`, `P8`, `P10`, `P15` not opened.

---

## Verdict

**Build on top of it, after the fixes F1–F4 below (about 3.5 hours: 2.5 interface, 1 back end). Keep the old pages mounted.**

- For: it runs, the suite and the linter are green, it merges cleanly, the routes pass the gateway's own objects through unchanged, each customer has its own book, and the answer card passes the five-second test the old pages fail (asked · suggested · who must decide and why, in one screen, the rest folded).
- Against, as it stands: it does the two things Valio told us not to do. **It orders with no click** (V8) and **its first screen is a chat** (W7). Its four customers are a second definition, in JavaScript, that disagrees with the plan's. And **merging Sofia's commit next to it switches every customer's limits and allergen rules off in the gateway**, while the page, as its code reads, keeps showing them (section 7).
- It does not replace the old pages: standing orders, the menu planner, the photo, `/assumptions` and any link to `/docs` exist only there. Neither side links to the other (read: no `/shop` link in `templates/`, no link out of the shop).

| Fix | What | Where | Kind | Hours | Who |
|---|---|---|---|---|---|
| **F1** | Nothing is ordered or sent without a click. One button, "Confirm order". Remove the "Ordered by your agent" wording | `static/shop/js/views/assistant.js` (`act`, line 80; `verdictBox`), `views/parts.js` (`statusTag`), `kitchens.js` (`autoSend`), `store.js:5` (a new storage key, or a browser that has opened the page keeps the old defaults) | interface | 1 | Gabriela |
| **F2** | Survive Sofia's commit: stop sending `auto_order_enabled: true`; three tests | `static/shop/js/kitchens.js:30`, `tests/ui/test_shop_api.py` | one JS line + tests | 0.5 | B0 |
| **F3** | The rules shown are the rules in force. Today a refused or lost settings call leaves the book on the hotel's defaults and the page says nothing | `src/tta/ui/shop_api.py` (refuse `/read`, `/offers`, `/orders` with 409 while `one.kitchen.is_set_up` is false); `core.js`, `main.js` (push again and retry; show the refusal; show limits and allergens from the gateway's answer, not from `localStorage`) | back end 0.5 + interface 0.5 | 1 | L4 + Gabriela |
| **F4** | Not a chat: rename "Assistant", drop the greeting, the bubbles and "conversation"; show the typed request that was sent; link `/docs` and the MCP tools | `views/assistant.js`, `main.js`, `shop.css` | interface | 1 | Gabriela |
| F5 | One definition of the four customers (section 6) | `src/tta/policy/profiles/`, `src/tta/customers/data/`, `src/tta/api/sandbox.py`, `shop_api.py`, `kitchens.js` | back end 1.5 + interface 1 | 2.5 | L3, L4, L5 + Gabriela |
| F6 | The reader's refusal in plain words; a place for the reader's question | `views/assistant.js` (`answer`, the `failed` branch) | interface | 0.5 | Gabriela, after L1 |
| F7 | Signer's name limited to the customer's people; kitchen names limited to the four; the cap on new books | `shop_api.py`, `src/tta/api/sandbox.py` | back end | 0.5 | L4 |

F1–F4 before any Valio judge sees it. F5–F7 tonight if the lanes have room. The contract lines of section 5 come after.

---

## 1. Does it run and hold

**Suite on `798b4d3`** (ran, 7 min): `3270 passed, 67 skipped, 1 deselected in 425.90s (0:07:05)`. That is the baseline's 3,260 plus the 10 new tests.
**`ruff check src tests`** (ran): `All checks passed!`

**`/shop` loads** (page): no exception, no Content-Security-Policy report. The only failed requests are `GET /favicon.ico` 404 and the expected 503 of `/shop/api/read`. The server log holds no traceback. With the width emulated at 390 px there is no sideways scroll (`scrollWidth` 390 = `clientWidth` 390). A plain `--window-size=390` screenshot is cut on the right; most likely that is the headless window's minimum width, not the page.

**The walk** (ran through the routes the page calls, one cookie jar per customer; "I need 1,000 litres of lactose-free milk by Monday"):

| Step | School | Ward | Hotel | Bakery |
|---|---|---|---|---|
| `PUT /kitchen` | 200 | 200 | 200 | 200 |
| `POST /read` | 200, `rule-based`: milk, lactose-free, 1,000 L, 2026-11-16 | same | same | same |
| `POST /offers` | 2 options. First: €2,580.64 = 384 × `469363` + 51 × `462775` + 565 × `463380` (Arla Cafè milk). Second: 1,000 × `464306`, €1,010.00, quantity not confirmed | **No option**: "30 candidates checked: 30 allergen declared" | same two options | same two options |
| Verdict | Person: purchasing manager and finance (P-01, P-02) | — | Person: purchasing manager (P-01) | Person: purchasing manager and finance (P-01, P-02) |
| `POST /orders` | `PENDING_APPROVAL` | — | `PENDING_APPROVAL` | `PENDING_APPROVAL` |
| Decision with a name | "Päivi Korhonen, Kilo School" → still waiting; "Tuomas Aho, Kilo School" (finance) → `ORDERED` | — | "Hanna Laine, Harbourside Hotel" → `ORDERED` | "Marko Heikkinen, Kallio Bakery" twice (two roles) → `ORDERED` |
| Orders · delivery day | 1 order · Mon 16 Nov | — | 1 · Mon 16 Nov | 1 · Mon 16 Nov |
| Audit, buyer | 10 events, chain verifies, names both signers | — | 9 events, names the signer | 10 events |
| Audit, supplier | 10 events, "A human at the buyer approved" | — | 9 | 10 |
| Setting changed (`auto_order_enabled` off), asked again | P-00 added | — | P-00, and P-02 because the first order counts in the day | P-00 added |
| Start again | `{"ok":true}`, orders `[]` | — | same | same |

Nothing failed. The ward's refusal is right (milk is excluded) and reads well on the page: "Nothing can be offered for this request. Looked at 30 products: 30 declares an excluded allergen."

**The same on the real page, hotel** (page): typed sentence → card with the three lines and "Sent for approval to Hanna Laine (purchasing manager)", sent with no click → "Approve as Hanna Laine" → "Ordered with approval · delivery Mon 16 Nov … by Hanna Laine, Harbourside Hotel (purchasing manager)" → order view with "Trail intact" and 9 events → "What Valio Aimo sees" → the orders, deliveries, approvals and settings views all render.

**Each customer's own example buttons** (the offers ran through the routes; the buttons send a typed request and skip the reader). Where the last column does not say "page", what the page does is read from `act()`.

| Customer | Example | Result | What the page then does |
|---|---|---|---|
| School | 40 L lactose-free milk | 40 × `469363`, €99.20, agent may order | **Orders it with no click** (page): "Ordered by your agent" |
| School | 20 kg natural yoghurt | 4 × `464517`, €48.56, person (F-03: variable-weight statement missing) | Sends it for approval with no click |
| Ward | 200 L milk substitute | 200 × `464013`, €402.00, agent may order | **Orders it with no click** (page) |
| Ward | 50 L soya drink | 50 × `464013`, €100.50, agent may order | Orders it with no click |
| Hotel | 30 L cream | 30 × `463797`, €99.30, agent may order | Orders it with no click |
| Bakery | 10 L whipping cream | 10 × `469346` (Arla Pro), €57.70, person (P-01, limit €50) | Asks the brand question first |
| Bakery | 10 L milk | 10 × `463047` (Arla), €20.10, agent may order | Asks the brand question (page); "Other brands are fine" then orders with no further click |

**Other things the walk met**
- A sentence the fixed rules cannot read ("milk for the weekend", page): a red box, "**A service the gateway depends on cannot be reached.** No GEMINI_API_KEY is set, so the gateway can read only the 7 recorded demonstration requests, and this is not one of them. The fixed rules could not read it either: milk is named with no quantity in digits and unit. Send the typed request to POST /v1/offers instead.", then "You can try again, or write the request differently." (HTTP 503 from `/shop/api/read`.)
- The reader allows 5 readings in 60 seconds per browser (ran: the 7th of 40 calls was the first 429). The page has a plain sentence for that case.
- One address may open 30 new books in 10 minutes, and **each customer is a book** (ran: I hit "Too many new demo order books from one address" after about 30). A visitor who tries all four customers uses four. Behind one venue address, the eighth such visitor in ten minutes would be refused (worked out from the cap, not run with eight browsers). `src/tta/api/sandbox.py`, `MAX_NEW_BOOKS_PER_ADDRESS`.

---

## 2. What it is built on

**Calls** (read, `src/tta/ui/shop_api.py`): `site.sandboxes.open(key)` gives the browser's `Sandbox`; on it `service.get_authority`, `kitchen.set_up`, `service.read_request`, `service.create_offer`, `service.place_order`, `service.list_orders`, `service.get_order`, `service.list_approvals`, `service.decide_approval`, `service.get_audit`; and `site.sandboxes.drop(key)`. Contracts used: `PurchaseRequest` (the body of `/offers` is validated as one), `DecisionRequest`, `ApproverRole`, `ApprovalStatus`, `AuditReader`, `Identity`, `TtaError`, `PolicyLoadError`. Every call is made as `KITCHEN_AGENT` or one of `KITCHEN_APPROVERS` of `tta.api.sandbox`.

**Passed through, not reshaped.** `_json` is `model_dump(mode="json")` of the gateway's object. A field added tonight to an offer, an order, an approval or an audit event reaches the browser. The page shows it only once a view prints it. One exception: `_refused` keeps only the text and number extensions of an error, so a list or an object in a problem (a reader's questions, say) is dropped.

**The agent run is not used.** A typed sentence goes to `service.read_request` (the reader behind `/v1/requests/parse`), then the browser sends the reading to `service.create_offer`, and then **the browser's own function `act()` decides whether to place the order** (`views/assistant.js:80`): verdict `AUTO` → order; verdict `APPROVAL` and the preference `autoSend` → order, which waits. The verdict is the gateway's. Acting on it without a click is the page's. The example buttons skip the reader and send a request typed in `kitchens.js`.

**Where the four customers live:** in JavaScript, `static/shop/js/kitchens.js`: names, people, customer numbers, addresses, limits, allergen rules, substitution scope, answer preferences, example requests, "learned" notes and past orders. The limits and allergen rules are copied to `localStorage` and pushed with `PUT /shop/api/kitchen` into the book's one custom profile. So in the gateway all four are **the same profile, `my-kitchen`**, with the same agent ("My kitchen agent") and the same three approvers. It shows: "…above the €250 limit per order of profile my-kitchen (P-01)" is what Kilo School reads, and the audit trail says "My kitchen agent" (page).

**What each module computes and stores**

| File | Computes | Stores |
|---|---|---|
| `kitchens.js` | Nothing. Constants: the four customers, 14 allergen names, the example requests, the past orders with typed-in names and euro amounts | — |
| `store.js` | Merges saved state over the defaults at load. **Saved settings win over new defaults** | `localStorage["tt-shop-v1"]`: active customer; per customer the settings, preferences, learned notes and the last 8 turns with their whole offers and orders (143,662 characters after my run) |
| `learning.js` | `prepare`: for a brand rule the buyer confirmed, adds the brand to `name_terms` of each request line of the rule's product types; builds the chips "Strict allergen rule: …" and "Confirmed data only" **from the browser's copy of the settings**. `review`: checks whether the supplier name or product name of each line of the first option contains the brand; if not, raises the brand question and **holds the order until it is answered**. `confirm`, `dismiss`, `restore`: change a note's state | Through `store.js` |
| `core.js` | `spendToday`: sums in the browser the day's ordered and waiting orders. `dataToday`: the latest of the orders' `created_at` (real time) and the offers' `time_now` (the data clock), else the browser's date. `nextDeliveryDay`: tomorrow, skipping Sunday | — |
| `views/assistant.js` | `act` (above). `approveHere`: signs every role the signed-in person holds, in a loop | — |
| `views/parts.js` | `rolesStillNeeded` from `approval.decisions[].role` or `.roles` | — |

**A rule or decision computed in the browser:** three.
1. Whether to place an order without a click (`act`).
2. The brand question and its hold (`review`): the page's own version of "same brand" (V10), by text match, for the bakery only. With "Yes, Valio only" the request is narrowed by a name term, and in this recording that swaps a confirmed Arla product for a Valio one whose quantity is not confirmed, both times I tried (page: `469477`, then `465193`).
3. The statement of which allergen rule and limits are in force (chips and side card), read from `localStorage`. See F3.

**When the reader cannot read a sentence:** the red box quoted in section 1. There is no typed form to fall back on, and no place for a question from the reader: `ask()` uses `reading.request`, `.source` and `.sentence` only. If tonight's reader answers with a question and no `request`, `prepare(undefined)` throws and the page would show a JavaScript error text (read).

---

## 3. Safety

| Question | Finding |
|---|---|
| Who can call `/shop/api` | Anyone who sends `X-Shop-Request: 1` (a fixed public value, not a secret) and a well-formed `X-Shop-Kitchen` (`^[a-z][a-z0-9-]{0,23}$`: **any** name, not only the four). No login, by design |
| The "header guard" | `_guard`: 403 without the header; 403 when `Sec-Fetch-Site` is present and is not `same-origin` or `none`; 400 without a kitchen name. Ran: no header 403, `cross-site` 403, `same-site` 403 |
| Cross-site request forgery | Covered. A form or a link cannot send the custom header; a cross-origin `fetch` with it needs a preflight, and the app answers `OPTIONS` with 405 and no CORS header (ran). The book cookie is `HttpOnly`, `SameSite=Lax`. The old pages' form token is not used here and is not needed |
| A book bound to the browser | Yes: key = the `tta_book` cookie (32 random bytes) + the kitchen name. Ran from a second cookie jar: A's orders list `[]`, A's order 404, A's audit 404, a decision on A's approval 404. `document.cookie` is empty to script (page) |
| Input limits | Text 1–2,000 characters; ids ≤ 64; key ≤ 100 with a pattern; unknown fields refused (422); a 3 MB body refused (413); settings checked as a profile file plus the page's bounds (a limit of €1,000,000,000 → 422). All ran. A kitchen `display_name` of `<script>alert(1)</script>` is accepted (200, ran); the shop never prints it (read) |
| Rate limits | `/read`: 5 in 60 s per browser. `/offers`: 20, then 429. `GET /orders`: none in 80 calls. `PUT /kitchen`: none in 60. `POST /start-again`: none in 40. New books: 30 per address per 10 minutes. All ran |
| HTML built from data | One sink: `root.innerHTML` in `main.js:181`. Everything goes through the tagged template `html` in `dom.js`, which escapes `& < > " '` in every value that is not itself built by `html`. `raw()` is used once, in `icons.js`, on constant SVG paths. Product names, the request text, notes and server sentences are escaped (read). A note holding `<script>` was stored and returned as text (ran) |
| Content-Security-Policy | Fits. No inline script or style in the page or its templates (read); bar widths are set through the style object; no report in the browser log (page) |
| The signer's name | `DecisionBody.name`: 1–80 characters, `^[\w .,'-]+$`. It replaces the approver's `display_name` for that call, so it lands in the audit event's actor and sentence, in the buyer's view only. Markup is refused (`<img …>` → 422, ran) |
| Can a visitor sign as anyone | **Yes.** Any name and any of the three roles. Ran: signing as "The gateway" gives the trail line "The gateway (purchasing manager) approved order …", with the same actor label the real gateway events carry. The page says it once, on the Approvals view only: "In this demo you can sign for anyone of the kitchen. In production each person signs in as themselves." Not next to "Approve as Hanna Laine" on the first screen, and not in the trail |
| An agent approving | Still refused: the route acts as an approver; role `agent` → 422 (ran) |

**The safety finding that matters (F3).** The rules a customer runs under exist in the gateway only after a successful `PUT /shop/api/kitchen`. A book that never got one is a copy of `hotel-kitchen`: no allergen exclusion, €750 (ran: with the header `X-Shop-Kitchen: ward` and no `PUT`, the 1,000 litres of **milk** are offered). The page pushes the settings at load, on a customer switch, on save and on reset. It does not push before a request. When the push is refused, `load()` stores the error and the next `refresh()` erases it; the first screen shows it only while loading (read: `main.js:25`, `core.js:31`, `views/assistant.js:355`). So after a refused push, a restart, a book dropped after two idle hours, or a book pushed out by the cap of 300, the ward's screen would still say "Strict allergen rule: Milk, Cereals with gluten" while the gateway applies none. The gateway half is run; the page half is read, not reproduced on the page.

---

## 4. Against Valio's answers and the brief

| Point | What the page does today | What a Valio judge thinks |
|---|---|---|
| **V8: the user confirms every order; nothing ordered alone by default** | Fails. `auto_order_enabled: true` for all four (`kitchens.js:30`). An offer the agent may take is ordered the moment it arrives: "Ordered by your agent" (page: school €99.20, ward €402.00). An offer that needs a person is sent for approval the moment it arrives (`autoSend: true` for all four). The first screen says "orders within the limits you set" | "We told you to switch this off." It is the first thing an example button shows |
| **"Not a chatbot" (W7)** | The first view is called "Assistant": "Good afternoon, Päivi", "What do you need, and by when? Write it the way you would to a colleague", the request as a bubble with a time, "Clear conversation". The answer is a structured card, not prose. There is no typed form, no product search or list, no link to `/docs`, OpenAPI or MCP, and the typed request is shown only as one line ("1,000 l lactose-free milk, by Mon 16 Nov") | A chat window on a webshop skin. The typed interface, which is the product, is invisible from this page |
| **V5: safe product first, doubts asked** | The gateway's order is kept: confirmed first, "Alternative: quantity not confirmed" second with its sentence. A doubt is not asked. The school's 40 litres: the product says nothing about nuts, peanuts or sesame ("passes as unverified"), and it is ordered alone. The doubt is listed under "Why this answer": open for the school and the ward, folded for the hotel, not shown for the bakery (short answers). The only question the page asks is the brand one | Sees the safe option first. Does not see a question about an allergen doubt |
| **B5: no coffee milk for milk** | Still offered: 565 of the hotel's 1,000 litres are Arla Cafè milk, €1,497.25 of €2,580.64, under a "MILK" tile (page). This is the gateway's answer; R2 changes it tonight. The page has no place for "coffee milk was left out" except the folded notes | The same objection as on the old page |
| **V10: substitutes, formula and brand** | A substitute line would look like any other line: the page never reads `line.substitute` or `stands_in_for` (read; none of my requests produced one). The brand question is the page's only gesture, in the browser, for the bakery | Nothing about what a substitute gives up |
| **The clock said on the page** | "Replay · recorded Valio Aimo data" in the top strip, and "Today Sat 14.11." Nothing says which instant the data shows, that we chose it, or that the log keeps real time. Audit times are real time, hours and minutes only, beside "order by Sun 15.11. 17:00" | Not told |
| **Generated data labelled synthetic** | Footer on every view: "Customers, people and past orders are made up; prices, stock and every rule come from the gateway." Orders: "Earlier orders · demo history", "Made-up history for the demo". Settings: "demo data". The agreed tag "Synthetic: made up for the demo" is not used. "What your agent knows … From your past orders" carries no tag. The limits are not labelled as ours: the gateway's note "The limit values of this profile are illustrative…" is not printed | Mostly told, in small print |
| **Confirmed, not confirmed, and why a person, in five seconds** | Passes. One line of what was read and how; a headline ("3 confirmed products cover the 1,000 L asked for, for €2,580.64 before tax."); the lines with a green dot and "384 pcs in stock · delivery Mon 16.11. · order by Sun 15.11. 17:00"; then, next to the lines, an amber box: "Sent for approval to Hanna Laine (purchasing manager). The agent cannot place this order alone: the total … is above the €750 limit per order of profile my-kitchen (P-01)", with the button inside. The hotel's whole answer fits one screen with the reasons folded (page) | The best screen we have. The words "profile my-kitchen (P-01)" spoil one line |
| **Valio's words (P3 table)** | Uses "Delivery wholesale", "delivery <date>", "pcs", "deposits not included". Does not use: "Closing time" (says "order by"), "<N> pcs available in storage" ("in stock"), "Deliverable <date>, quantity not confirmed" ("Stock not confirmed by Valio Aimo"), "Alternative products" ("Other options"), "Confirm order" ("Order now", "Send for approval", "Approve as"), "(VAT 0 %)" ("Total before tax"). "Standard order" and "Frequently purchased" have no place: the page has no standing orders | Looks like their shop, speaks differently |

Code words still on the page, all from the gateway's sentences: "profile my-kitchen", "P-01", `FREE_FROM_LACTOSE`, "free from AN", `plant_drink`, `GOODS_FROM_FINLAND_BLUE_SWAN`, "opt_1", "replay", "the gateway". The reasons list is folded, so they are one click away, except in the verdict line.

---

## 5. Against tonight's plan

**One row per line of `UI-CONTRACT.md`, "Planned, by package"**

| Package | State | Detail |
|---|---|---|
| R1, R7 prepared, then confirmed | **Missing, and breaks** | Today the page orders or sends by itself. Afterwards it does say who: "Ordered … with approval by Hanna Laine, Harbourside Hotel (purchasing manager)". Breaks on Sofia's commit (section 7). After B0 every verdict needs a person, so the page will send everything for approval by itself and offer "Approve as …": one click, wrong words |
| R2 a variant left out or offered unasked | **Partly** | `offer.notes` are printed only inside the folded "Why this answer" and in the "Nothing can be offered" box. The headline is `options[0].summary` |
| R5 what a substitute gives up | **Missing** | `line.substitute` is never read |
| R6 the dietitian's question with three choices | **Missing** | The approval card has Approve and Reject. The route already takes `option_id`; no control sends it. A new title such as "Alternative: allergen not ruled out" would show as it is, because the title is the gateway's |
| S1 four customers, who is ordering, synthetic label | **Partly** | Four customers and who is ordering: yes. They are the page's own, not the plan's (section 6). Labels say "made up", not the agreed tag |
| S2 "Suggested from your past orders" | **Missing** | No call and no place. "What your agent knows" is typed-in text |
| S4 Valio's view of an order | **Partly; goes stale** | The switch "What Valio Aimo sees" prints each event's sentence and rule ids, so new sentences show. The typed-in note under it (`views/orders.js:82`: "leaves out your limits, allergen exclusions, approvers' names, notes and your own words") becomes wrong. Products considered show only if they are in a sentence |
| R8 the clock banner | **Missing; will mix clocks** | With the demo clock, offers say Thursday and orders are stamped in real time; `dataToday()` (`core.js:44`) takes the later, so "Today" and the day's spend follow real time once an order exists |
| R9 one button per scenario, with its customer | **Partly** | Two buttons per customer, eight in all. Scenarios 1 and 2 are there. Scenario 3 (Oddlygood barista by product id), 4 (the pattern and the standing order) and 5 (whipping cream short) have no button. Each customer has its own book, so one customer's orders never fill another's day |
| A4 H2 "Decide as …" names a role still needed | **Already there** | Buttons only for roles not yet signed (`rolesStillNeeded`). Depends on `approval.decisions[].role` keeping its name |
| P14 the photo button | Not on this page | The shop has no upload |
| P16 the payment sentence | **Missing; the place exists** | The order view prints `order.record_note` |
| P7 the heading at `_result.html:192` | Not on this page | Old template only |
| A3 F5 `/run-photo` | Not on this page | Old route only |

**The reverse: shown on the page with nothing behind it**

| On the page | What is behind it |
|---|---|
| Deliveries: "24 h · 48 h · 1 fee", "Stocked products arrive the next delivery day…", "one delivery fee", "No deliveries on Sundays", "Delivery days: Mon–Fri" | Typed into `views/deliveries.js` and `kitchens.js`. The gateway knows no delivery fee and no delivery days per customer |
| The date in the header ("Mon 16.11.", "Next delivery day") | Tomorrow, skipping Sunday, computed in the browser |
| "What your agent knows", "What the agent has learned" with Confirm and Turn off | Typed-in notes. Only the bakery's brand note does anything. "Four of the last five plant-drink orders were Alpro" sits above a history of four orders, three of them Alpro |
| Earlier orders | Typed-in names and euro amounts, not catalog ids (one row is "Pirkka grated cheese 1 kg") |
| "The approver can still switch to one of these." | No control on the approval card does it |
| "Allergens kept out", "Agent orders alone up to", the allergen chips | The browser's copy of the settings (F3) |
| The day's spend meter | Summed in the browser, beside the gateway's own count |
| Customer numbers, addresses, people | Typed in; labelled as made up in the footer |
| The rule ids beside each setting, and the line "F-06 An agent can never approve…" | Typed into `views/settings.js` |
| The tab "Delivery wholesale" | Opens the delivery calendar. There is no shop: no product list, no search, no basket |

---

## 6. Its four customers against the plan's four

| | The page (`kitchens.js`) | The plan (`P1-customers.md` 4.2, the profile files) | Agree? |
|---|---|---|---|
| Hotel | "Harbourside Hotel". €750 per order, €3,000 per day, fill 90%, no exclusion, substitutes of the same kind alone. Signs: purchasing manager; finance | `hotel-kitchen.yaml`: the same five values. Purchasing manager above €750, finance above €3,000 a day | Yes |
| Ward | "City Hospital, Ward 4". €500, €1,500, fill 100%, milk and gluten, strict, no substitute alone, confirmed data only. Signs: "Ward purchasing" | `allergy-ward.yaml`: the same. Dietitian for any allergen doubt. Drift 0.1 (the page sends 0.25) | Yes, but for the drift value |
| School | "Kilo School". €250, €800. **Tree nuts, peanuts and sesame excluded for the whole school, "declared only"**, so a product that says nothing passes and can be ordered alone (ran). Substitutes: listed by Valio | `school-kitchen` (new tonight): **no exclusion in the profile; a special-diet line excludes per request, strict.** Listed by Valio only. Signs: food-service manager; dietitian for special diets. Usual products `462775`, `470863`, `464517` | **No**: the allergen rule |
| Bakery | "Kallio Bakery". €50, €400. **Substitutes of the same kind alone.** Assumes the bakery's dairy brand is **Valio**; its typed-in history is Valio whipping cream. The owner holds two roles | `bakery-cafe` (new tonight): **no substitute alone; formula matters (V10).** Usual products are **Arla** (`469346`, `464727`, `463380`) and `469512`. Signs: the owner | **No**: substitution scope and brand. Both Valio products the brand answer led to in this recording have no confirmed quantity |

All four on the page have ordering alone switched on, as the two profile files have at this commit. The runbook switches it off in every shipped profile tonight.

**What must become one definition, and where**
- Limits, allergen rule, substitution scope, who approves: the four profile files in `src/tta/policy/profiles/` (two exist; L3 writes two tonight, P1 C1). They are hashed into the policy hash, which a browser copy is not.
- Who orders and who signs, usual products, the eight weeks of history, `synthetic: true`: `src/tta/customers/data/<profile_id>.yaml` (L5, P1 C2).
- The shop then reads them: the book of a kitchen starts from its profile (`Kitchen.start_from`, with `STARTING_POINTS` holding the four ids, which P1 C1 already names at `sandbox.py:64`), and one new route lists the customers with their people and history. `kitchens.js` keeps only what is presentation: avatar colour, order of the list.
- Until then the sentences keep saying "profile my-kitchen". The smallest cure for that one line is wording: the decision sentence names the profile's display name (L3).

---

## 7. Merging

| Against | Result |
|---|---|
| `overnight-build` `277e71b` | Clean (`git merge-tree --write-tree`: a tree, no conflict). That branch changed documents only since `7f09ce7` |
| `origin/codex/mandatory-human-approval` `5673ef2` | **Clean as text, broken in behaviour.** No file is touched by both. On the merged tree (extracted to scratch, ran): `tests/ui/test_shop_api.py` → `3 failed, 7 passed` |

**Why, on the merged tree (ran through the routes):**
- Sofia's commit makes `auto_order_enabled` a value "set by the gateway" (`sandbox.py`, `_FIXED_PARTS`). The shop sends it with every customer's settings. So **every** `PUT /shop/api/kitchen` with the page's settings is refused: `422 Your kitchen: auto_order_enabled: is set by the gateway for My kitchen, not on this page`.
- The profile in force is then the default copy of the hotel: `excluded_allergens=[]`, €750. With the ward selected, the 1,000 litres of milk are offered: 384 × `469363` + 51 × `462775` + 565 × `463380`. By its code the page would still show the ward's strict rule (F3).
- The three tests: `test_kitchen_settings_are_checked_like_a_profile_file` (the settings are refused), `test_the_kitchen_limit_decides_the_verdict` (`assert 'P-01' in ['F-10']`), `test_each_kitchen_has_a_book_of_its_own` (`'PENDING_APPROVAL' == 'ORDERED'`).
- Without that one field the settings are accepted and the flow works: the school's 40 litres go to the purchasing manager under F-10.

**Tonight's packages against the page and its tests** (read, against the runbook's table)

| Package | Breaks | How |
|---|---|---|
| B0: R1 with Sofia's commit, then X2 | 3 tests; every customer's settings | Above. After X2 puts the setting back, `kitchens.js` must send `false`, or the page switches ordering alone on for all four |
| B0: R2 coffee milk | Nothing | The hotel's figure moves to 435 L and the fill rule fires as well; the page prints what it gets |
| B0: the demo clock | The "Today" tag and the spend meter mix two clocks | `core.js`, `dataToday` |
| L1 reader | The red box's words change. A reading with no `request` gives a JavaScript error text | `views/assistant.js`, `ask` |
| L2a, L2b offers | Nothing breaks. The page treats `options[0]` as the answer, so "the safe product first" must stay the first option | — |
| L3 rules and log | Nothing breaks. The typed-in note under Valio's view goes stale | `views/orders.js:82` |
| L4 gateway | `sandbox.py` (the settings list, the starting points) is what the shop's settings call stands on. The `Origin` check (P12 W3): the tests send no `Origin`, so a check that refuses a missing one turns the whole file red | I did not read A3's items |
| L5 customers | Nothing breaks. It creates the second definition of section 6 | — |

The runbook lets the build change only "a figure, a word or a field name" under `tests/ui/`. The three tests need more than that, so this review grants it (below).

---

## 8. What is missing, ranked by what a judge notices first

| # | What | Smallest fix | Files | Kind |
|---|---|---|---|---|
| 1 | An example button orders by itself | F1 | `views/assistant.js`, `views/parts.js`, `kitchens.js`, `store.js` | interface |
| 2 | The first screen is a chat | F4 | `views/assistant.js`, `main.js`, `shop.css` | interface |
| 3 | A free sentence ("milk") answers with "No GEMINI_API_KEY is set … POST /v1/offers" | F6; the reader itself is L1's work tonight | `views/assistant.js`; `src/tta/agent/**` | both |
| 4 | Coffee milk in the main offer; no sentence when it is left out | R2 in the gateway; put the sentence in `options[0].summary`, which is the page's headline | `src/tta/offers/**` | back end |
| 5 | "profile my-kitchen (P-01)" in the one line that says why a person is needed | The sentence names the customer; rule id only in the folded list | `src/tta/policy/**` wording | back end |
| 6 | The customers differ from the plan (school allergens, bakery substitutes and brand) | F5 | section 6 | both |
| 7 | The page can show rules that are not in force | F3 | `shop_api.py`; `core.js`, `main.js` | both |
| 8 | Nothing about a substitute, no suggestions, no clock banner, no dietitian question, no payment sentence | The contract lines, after the fields land: R5 1 h, S2 1 h, R8 0.5 h, R6 1.5 h, P16 0.1 h | `views/*.js` | interface |
| 9 | Valio's words | Six strings: "Closing time", "available in storage", "Deliverable <date>, quantity not confirmed", "Alternative products", "Confirm order", "(VAT 0 %)". 0.5 h | `views/parts.js`, `views/assistant.js` | interface |
| 10 | Typed-in facts: delivery terms, "four of the last five", the history | Remove the delivery lead; read history from the customer files once F5 lands. 0.5 h | `views/deliveries.js`, `kitchens.js` | interface |
| 11 | Anyone signs as anyone, "The gateway" included | F7; and one line beside "Approve as …" | `shop_api.py`; `views/assistant.js` | both |
| 12 | Many visitors behind one address | F7: raise the cap, or one book per browser holding the four kitchens | `src/tta/api/sandbox.py` | back end |
| 13 | No way from `/` to `/shop` or from the shop to `/docs`, standing orders, the menu, the assumptions | Two links. 0.1 h | the old pages' menu in `templates/`; `main.js` | interface |
| 14 | No test of the JavaScript: 1,871 lines, and "orders without a click" is untested. The 10 tests cover the routes. No browser test library is installed | Route tests under F-10 for each of the four customers' settings | `tests/ui/test_shop_api.py` | back end |

---

## What tonight's runbook should change

**The merge step.** As written: C2 first (`git merge --no-ff origin/frontend-shop`), then C1. Both are clean. Expect the suite after the two merges to show `tests/ui/test_shop_api.py` with 3 failed, on top of C1's own three. Add to **B0's first work, before X1**:
- `src/tta/ui/static/shop/js/kitchens.js:30`: `auto_order_enabled: true` → removed while the gateway fixes the value; `false` once X2 has put the setting back.
- `tests/ui/test_shop_api.py`: the `BAKERY` body the same way; `test_each_kitchen_has_a_book_of_its_own` expects the order to wait and be approved; a new test that the settings call is accepted for each of the four customers' settings.
- B0's end state gets a seventh line: "With each of the shop's four customers, `PUT /shop/api/kitchen` answers 200 and no offer of the shop is ordered without a decision."

**Files under `src/tta/ui/` the build session may edit**
- `src/tta/ui/shop_api.py`: yes, lane L4. It is Python glue over `sandbox.py`, which L4 owns.
- `tests/ui/test_shop_api.py`: yes, L4; B0 for the three tests above.
- `src/tta/ui/static/shop/js/kitchens.js`: only the values inside `BASE_SETTINGS` and the four `settings` blocks, by B0, each change written under "Changed under the interface".
- `src/tta/ui/routes.py`: only the line that mounts the shop.

**May not edit:** every other file under `src/tta/ui/static/shop/**` (the views, `main.js`, `core.js`, `store.js`, `learning.js`, `api.js`, `dom.js`, `icons.js`, `shop.css`, `index.html`), and, as before, `src/tta/ui/templates/**` and the rest of `tests/ui/**` beyond what the runbook already grants for C1's X2.

**Contract lines that become the build session's work, because the page already has the place**

| Line | Put it here, and the page shows it with no interface change | Lane |
|---|---|---|
| R2 | The sentence in `options[0].summary` (the headline) and in `offer.notes` (the folded reasons, and the "nothing can be offered" box) | L2b |
| R1, R7 | `decision.sentence` (the verdict box) and `order.status_sentence` (the verdict box and the order view) say "Prepared: confirm to order" and "Confirmed by <name>". The page treats `placed_by == "AGENT"` as "Ordered by your agent" and anything else as "Ordered with approval" | L3 |
| S4 | The supplier's `events[].sentence` and `rule_ids`: the page prints both. Products considered must be in the sentence; no structured field is printed | L3 |
| R6 | The question in `approval.reasons[]`: each is a line of the approval card. The three choices need a control (Gabriela); the route already takes `option_id` | L2b, L3 |
| A4 H2 | Keep `approval.decisions[].role` (or `.roles`) and `required_roles` as they are | L4 |
| R8 | The clock in `/healthz`, which the page already fetches for its top strip; `offer.time_now` is already read | B0 |
| P16 | The sentence in `order.record_note`: the order view prints it | L4 |
| S1 | The four profiles and the customer files, read by the shop (F5) | L3, L4, L5 |
| S2 | A route `GET /shop/api/suggestions` in `shop_api.py` that passes the suggestions through; the box is Gabriela's | L4 |
| Errors | `_refused` passes lists and objects of a problem through, so a reader's question reaches the page | L4 |

**Left for Gabriela, in this order:** F1, F4, F3 (her half), F6, F5 (her half), then R5, R8, S2, R6, the six words, the two links. About 9 hours in all; if time runs out, cut R6 and S2 first.
