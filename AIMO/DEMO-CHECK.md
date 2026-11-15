# Demo check: the video and the live minute, walked as written (Sun 15 Nov, 04:05)

## Verdict
- **Video: yes.** All seven blocks work as written and every promised word and figure appears. The "Do" column needs corrections in blocks 2, 3, 4, 6 and 7 (scrolls and clicks the shot list omits or puts in the wrong order), and the voice-over is 113 s of speech in 120 s, with blocks 1 and 7 longer than their own seconds.
- **Live minute: not as slide 5 is written (about 65 s). Yes with the shorter slide 5 below (about 50 s) and five actions.** The flow itself worked first time from a fresh browser, every time.

## How this was checked, and what was not
- Own server from the clean copy of `d617d5c`, replay, demo clock Thu 12 Nov 2026 14:15, no model, no key, port 8051. Headless Chrome 157, a new browser context per run. 86 pictures of the window; the ones a cut or a claim depends on were looked at (about 20), the rest checked by the words in the window: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/6585c036-9723-4ff4-97e0-3fba8894a301/scratchpad/democheck/shots/`.
- **The page area was 1440 × 900.** A real Chrome window of 1440 × 900 has a shorter page area (tabs and toolbar; about 780 px is my assumption, not measured on João's machine). The layout is the same at every width from 1280 up; only the height changes what fits. Measured at 900, 780, 667 and 600 px high; the 720 row is computed from the same positions: see "Window height".
- **Not rendered: `/docs`.** It loads Swagger UI from `cdn.jsdelivr.net`, an outside call this lane may not make. Its 30 routes were counted in `/openapi.json` instead (30 operations, HEAD included). It needs internet when filmed.
- **Not walked:** the three optional swaps of the shot list.
- Seconds for "raw clicks" are estimates (a script clicked; I assume 1.2 s per pointer action and 7 s to type a sentence). Page response times are measured.

## 1. The video, block by block (recording order 2, 3, 4, 5, 6, 7)

Page response, measured: every answer 0.16–0.37 s after Enter; Confirm 0.16–0.28 s; order page 0.17 s; Valio Aimo's view 0.16 s; Add 0.18 s; reset 0.18 s. Toasts stay 3.2–3.3 s.

| # | Works as written | On screen, as it appears | Spoken line true of the picture | Raw actions | Do not film |
|---|---|---|---|---|---|
| 2 | Yes | "2 confirmed products cover 435 L of the 1,000 L asked for (565 L missing), for €1,083.39 before tax." · "€1,083.39" · CONFIRM ORDER, all in the first window. After the scroll: "Alternative: quantity not confirmed · €1,010.00" and "Alternative: confirmed stock, completed with a substitute · €2,580.64" | Two words differ: the voice says "asks Valio Aimo", the grey line says "recorded Valio Aimo data"; the voice says "barista milk", the screen says "Arla Cafè milk 1 L UHT lactose free (463380)" | type + Enter + 1 scroll: 2 s, plus 7 s typing | The headline ends "Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk." while the third option offers a café milk. They are never in one window after the scroll; do not hold both. The grey line shows the real time ("· 03:34") |
| 3 | Yes, but "Scroll to the log" before the tab puts the tab out of the window | "Confirmed by Hanna Laine · delivery Mon 16 Nov" · "The audit trail is intact: each of the 11 events shown here matches its hash, and the chain they belong to verifies." · "This is Valio Aimo's view of the order, not Harbourside Hotel's" | Yes ("Limit amounts and allergens are not shown to Valio Aimo") | 4 actions: 5 s | Order page, buyer's view: "Orders · ord_…" above the title, "P-01", "P-03", "rules P-01 and P-03 asked for a human and were accepted", the policy fingerprint; in the log "off_…" and "(P-01)" |
| 4 | Yes | "…it was in 7 of your last 8 orders, 10 L each time, and it is not in this request. Adding 10 L costs €33.10." · €248.00 → €281.10 · back office: "2 orders confirmed", "€1,364.49 confirmed, before tax", "€33.10 added to baskets, before tax", "565 L asked for, not confirmed", "€1,407.16 at offered prices, before tax" | Yes | 8 actions: 10 s, plus 7 s typing | After Add: the headline "…Request line 1: Coffee milk was left out…"; the alternative "…(464306) for all 2 items asked for in full, €134.10 before tax"; the toast "Sent as a new request: its offer is the first result." (3.3 s); "384 pcs available in storage" although block 3 just ordered 384 of it |
| 5 | Yes | "Nothing can be offered for this request" · "26 products checked, 26 left out. All 26: The product declares that it contains milk, which the buyer excludes." | Yes | 2 clicks + type + Enter: 3 s, plus 7 s typing | The toast "Now shopping as Jussi Nieminen, City Hospital, Ward 4" (3.2 s; gone by the time the sentence is typed) |
| 6 | Yes, but the second sentence cannot be typed without scrolling up and clicking the box | "Ordered by your agent · delivery Mon 16 Nov" · "The agent placed this order alone for €748.96 net. That was allowed: ordering alone is switched on for Harbourside Hotel; the total of €748.96 is within the €750 limit per order; today's spend with this order is €748.96 of the €3,000 limit per day; every statement of the offer is confirmed; and no rule asked for a person." · "Needs your decision" · "The total of €751.44 before tax is above the €750 limit per order of Harbourside Hotel." | Yes | 11 actions: 13 s, plus 14 s typing | The toast "Demo reset for this customer." (3.2 s). The six actions before the switch are setup: film from the switch |
| 7 | `/llms.txt` yes; `/docs` not rendered by me | `/llms.txt`: 33 lines of plain text; `/openapi.json`: 30 operations, licence "MIT" | Yes | 2 tab changes: 2 s | `/llms.txt` at 100% is 13 px text on a full-width page: zoom that tab to 150%. Its links read `http://127.0.0.1:8011/…` |

**Voice-over against the seconds** (150 words a minute, numbers counted as spoken): block 1: 31 words, 12.4 s in 8 s. Block 2: 62 words, 24.8 s in 30 s. Block 3: 37, 14.8 s in 17 s. Block 4: 45, 18.0 s in 18 s. Block 5: 33, 13.2 s in 17 s. Block 6: 45, 18.0 s in 20 s. Block 7: 29, 11.6 s in 10 s. Total 112.8 s of speech in 120 s.

**Window height.** The answer's layout is fixed: after a request the page scrolls itself so that CONFIRM ORDER sits 553–587 px down and the two alternatives end 1,151 px down. The order page puts "Trail intact" 804–872 px down and the tab "What Valio Aimo sees" 225–261 px down.

| Page area height | After the hero answer | To see both alternatives | Order page |
|---|---|---|---|
| 900 | headline, total, CONFIRM ORDER in the window | scroll 300 px: total, "Needs your decision", CONFIRM ORDER and both alternatives in one window | "Trail intact" and the tab both in the window, no scroll |
| 780 | same | scroll 390 px: CONFIRM ORDER and both alternatives in one window; the total is under the header | scroll 120 px for "Trail intact"; the tab stays |
| 720 | CONFIRM ORDER in the window | scroll 450 px: both alternatives whole, CONFIRM ORDER just under the header | scroll 180 px for "Trail intact"; the tab is then half under the header, scroll back a little to click it |
| 600 | CONFIRM ORDER at the very bottom edge | scroll 570 px, then back up to confirm | scroll 300 px; the tab is gone, scroll back to click it |

## 2. The live minute (slide 5), from a fresh browser

As written: 141 spoken words, 56 s at 150 words a minute, plus about 3 s of typing that the first sentence does not cover and about 5 s where the pointer travels in silence: **about 65 s.** Shortened (below): 103 words, 41 s, plus the same 8 s: **about 50 s.** If it still runs long, drop the closing sentence first; keep the click on "What Valio Aimo sees".

| Spoken (shortened) | Action | In the window (page area 900 high) | Eye |
|---|---|---|---|
| "Hanna asks for a thousand litres of lactose-free milk by Monday." | click the box, paste or type, Enter | answer in 0.2 s; the page scrolls itself: "ASKED 1,000 L lactose-free milk, by Mon 16 Nov" at the top | the "Asked" line |
| "Only 435 litres are confirmed, so the gateway does not promise the rest." | none | "2 confirmed products cover 435 L of the 1,000 L asked for (565 L missing), for €1,083.39 before tax." | the first line of the headline |
| "It offers two other ways, clearly labelled: cheaper with unconfirmed stock, or all confirmed with a café milk as a named substitute." | scroll 300 px | "Alternative: quantity not confirmed · €1,010.00" and "Alternative: confirmed stock, completed with a substitute · €2,580.64", both whole; total, "Needs your decision" and CONFIRM ORDER still above them. Gone from the window: the "Asked" line and the headline | "Other options", lower half |
| "This order is above the hotel's €750 limit and below its 90% minimum, so the agent asks Hanna." | none | "The total of €1,083.39 before tax is above the €750 limit per order of Harbourside Hotel and only 43.5% of the requested quantity is covered, below the 90% minimum (covered: 435 of 1,000 L)." | the amber box |
| "She confirms, and the order is recorded." | click CONFIRM ORDER | in place, no jump: green "Confirmed by Hanna Laine · delivery Mon 16 Nov" | the green box |
| "Every step is in an audit trail that verifies," | click "Order and audit trail" | order page at its top; "Trail intact … each of the 11 events …" at the bottom of the window | bottom green box |
| "and Valio Aimo has its own view of it, without the buyer's limits." | click "What Valio Aimo sees" (top right) | "This is Valio Aimo's view of the order, not Harbourside Hotel's" and the table "What Valio Aimo receives" | the purple banner |

"26 matching products" is true (the trail says "looked up price and availability of 26 products" and "3 options from 26 candidates") but 26 is nowhere in the answer's window: it is in the fold "Why this answer" and in the log.

## 3. The four figures, shown on the page

| Slide | Clicks | Appears | Matches the spoken sentence |
|---|---|---|---|
| 6: "under €400" sends a €496 order to a person | Harbourside Hotel → Request → `200 litres of lactose-free milk by Monday, under €400` → Enter | "Needs your decision" · "The total of €496.00 before tax is above the €400 you named for this request." · €496.00 (200 pcs × €2.48) | Yes, to the euro. With ordering alone switched on the box is the same |
| 7: ward, 26 checked, 26 refused | customer menu → City Hospital, Ward 4 → `100 litres of lactose-free milk by Monday` → Enter | "26 products checked, 26 left out. All 26: The product declares that it contains milk, which the buyer excludes." | Yes |
| 7: 302 litres ordered, 303 waits | Harbourside Hotel → Settings (the switch is in the first window at 900 high) → "Let the agent place orders alone" → SAVE → Request → `302 litres of lactose-free milk by Monday` → scroll up, click the box → `303 litres of lactose-free milk by Monday` | "Ordered by your agent · delivery Mon 16 Nov", €748.96 · then "Needs your decision: The total of €751.44 before tax is above the €750 limit per order of Harbourside Hotel." | Yes, to the litre. **No reset is needed** after the live minute: the sentence then reads "today's spend with this order is €1,832.35 of the €3,000 limit per day" |
| 9: 565 litres, about €1,400 | scroll to the top → strip tab "Valio Aimo's back office (demo)" → scroll down 680 px | "565 L asked for, not confirmed" · "€1,407.16 at offered prices, before tax" · "435 of 1,000 L of lactose-free milk could be confirmed: 565 L, about €1,407 at the offered price, were not." | Yes, **only if the hero sentence was sent exactly once in this browser and the hotel was not reset since.** Sent twice: "1,130 L · €2,814.32". After the hotel's reset: "No quantity is counted here as a sale Valio Aimo could not make." Still 565 L after the ward's refusal, the 302 and the 303 |

## 4. What can go wrong in front of people

| Tried | What the person sees | On stage |
|---|---|---|
| Page reloaded mid-flow | Answers and orders stay, and an answer can still be confirmed. Lost: text typed and not sent, open folds, and the tab "What Valio Aimo sees" (back to the buyer's view of the same order) | Carry on; click the tab again |
| Same sentence sent twice | Two identical cards, the new one on top, each with CONFIRM ORDER. Back office doubles: "1,130 L asked for, not confirmed · €2,814.32" | Send the hero once. If twice: reset the hotel before showing the back office |
| CONFIRM ORDER clicked twice | One order. The button is replaced by the green box; the link "Order and audit trail" lands where the button was, so a slow second click opens the order page | Nothing: that is the next step anyway |
| Customer switched with an answer open | The other customer's page, empty. Switching back shows the answer, still confirmable | Switch back |
| Customer switched while a request is on its way | **The answer is made with the other customer's rules and filed under the first one.** With 300 ms of network delay per call: the ward's page showed "1 confirmed product covers the 100 L asked for, for €248.00 before tax" with CONFIRM ORDER, for lactose-free milk; the hotel's page showed the ward's refusal. Clicking CONFIRM ORDER: "No such offer, order or approval. No offer has this id." No order is made. Locally the whole answer takes 0.16 s, too short for a hand | Do not touch the customer menu until the answer is on the page |
| 1280 × 720 | Same layout. CONFIRM ORDER is in the window after a request (553–587 of 720) | Full screen; zoom 80% gives the 900-high picture |
| 390 px wide (phone, 844 high) | Asked line, headline, total and the title "Needs your decision" in the window; CONFIRM ORDER is 130 px below it. No sideways scroll; "Settings" is reached by swiping the menu row | One short swipe |
| `1000 liters of lactose free milk by monday` | The same answer: "1,000 L lactose-free milk, by Mon 16 Nov", 435 L, €1,083.39. Also `1000l lactose-free milk monday` and `lactosefree` | None needed |
| `1.000 litres…` or `a thousand litres…` | No answer: "The agent needs an answer before it can look this up" · "Is it 1,000 or 1? Write 1000 for the first, or 1 for the second." / "What quantity of milk is needed?" | Type `1,000` or `1000`. Fallback: the example chip under the box, one click, same answer |
| Day's limit | Hero orders 1 and 2 read as the first. **At the third hero sentence** (two confirmed, €2,166.78) the box adds "…with this order today's spend would reach €3,250.17 before tax (€2,166.78 ordered, €0.00 waiting for a person, and this order's €1,083.39), above the €3,000 limit per day of Harbourside Hotel…". Still confirmable; the right column then reads "€3,250.17 of €3,000.00" | Reset the hotel before the pitch; do not rehearse after it |
| "Reset this customer's demo" mid-demo | One click, no question asked. Toast "Demo reset for this customer."; that customer's cards, orders and settings are gone (ordering alone back to off) and its 565 L leaves the back office. The other customers keep theirs | Send the hero again (6 s) |
| Server restarted with cards on the page | The right column says "€0.00 of €3,000.00" while old green cards stay. Old CONFIRM ORDER: "No such offer, order or approval. No offer has this id." with ASK AGAIN. Old "Order and audit trail": "Order not found. It may belong to another customer, or the demo order book was emptied." A new sentence works | Reset both customers after any restart |
| Server down | "The request could not be read into a typed request. The gateway could not be reached. Check that it is running." | Go to the recorded video |

## 5. Corrections

### Shot list
- Before you record, window: "window about 1440 × 900" → "Chrome in full screen with the toolbar hidden, so the page area is about 900 px high. In a shorter window every scroll below is longer (table 'Window height' in `AIMO/DEMO-CHECK.md`)."
- Before you record, order: "Block 4 needs the orders of blocks 2 and 3 still in the book, and must come before the ward (block 5)." → "Block 4 needs the orders of blocks 2 and 3 still in the book: send the hero sentence once only (twice shows 1,130 L · €2,814.32) and keep block 6's reset after block 4 (the reset removes the 565 L). The ward's block no longer changes the back office."
- Block 2, Do: "Then scroll down about half a window" → "Then scroll down 300 px, until both alternatives are whole in the window; the total, 'Needs your decision' and CONFIRM ORDER stay in it."
- Block 2, Say: "asks Valio Aimo for price and stock" → "looks up Valio Aimo's price and stock" (the screen says "recorded Valio Aimo data").
- Block 2, Say: "with a lactose-free barista milk named as a substitute" → "with a lactose-free café milk named as a substitute" (the screen says "Arla Cafè milk").
- Block 3, Do: "Scroll back up. Click CONFIRM ORDER." → "Click CONFIRM ORDER (it is still in the window)."
- Block 3, Do: "Click 'Order and audit trail' in the green box. Scroll to the log. Click the tab 'What Valio Aimo sees'" → "Click 'Order and audit trail'. Do not scroll: 'Trail intact' is at the bottom of the window (in a shorter window scroll 120 px at most, or the tab leaves it). Click the tab 'What Valio Aimo sees', top right."
- Block 4, Do: "Then the strip tab at the very top, 'Valio Aimo's back office (demo)'." → "Scroll to the top of the page (the strip does not follow), click 'Valio Aimo's back office (demo)', cut on '2 orders confirmed · €1,364.49', then scroll down 680 px for '€33.10' and '565 L · €1,407.16'."
- Block 6, Do: "Type `302 …`, Enter. Type `303 …`, Enter." → "Type `302 …`, Enter. Scroll back to the top and click in the request box (after an answer it is 630 px above the window and has no cursor). Type `303 …`, Enter."
- Block 6, Do: "In Settings switch 'Let the agent place orders alone' on" → "Click 'What the agent may do' in the left column (the switch is about 2,500 px above the reset link), switch 'Let the agent place orders alone' on".
- Block 7, Do: add "zoom the `/llms.txt` tab to 150%; `/docs` needs internet".
- Times: block 1 "8 s" → "12 s"; block 2 "30 s" → "26 s"; block 5 "17 s" → "15 s"; block 7 "10 s" → "12 s". Total stays 120 s.
- Total line: "The raw clicks of blocks 2 to 7 take about 16 seconds in all" → "about 35 seconds of pointer actions in all, plus about 7 seconds for each of the five typed sentences unless they are pasted; the page answers in under 0.4 s each time".
- Not for the camera: "The back office in a browser that already ran the ward's block: it then counts the ward's refused 100 L as a sale not made." → remove (no longer true: the page says "Not counted here: requests where nothing could be offered because the buyer's own requirements left products out.").
- Not for the camera, add: "After Add in block 4: the alternative '…(464306) for all 2 items asked for in full, €134.10 before tax'." · "The order page's buyer view read slowly: 'Orders · ord_…', P-01, P-03." · "The back office after block 6: '1 confirmed by a person (€1,832.35 before tax), 1 placed by the agent alone' (the amount is both orders)."

### Slide 5
- "The gateway checks 26 matching products, but only **435 litres are confirmed**." + "It does not invent availability. 435 litres are confirmed; for the rest it offers two ways, clearly labelled: …" → "Only 435 litres are confirmed, so the gateway does not promise the rest. It offers two other ways, clearly labelled: cheaper with unconfirmed stock, or all confirmed with a café milk as a named substitute."
- "or fully confirmed with a barista milk as a named substitute" → "or all confirmed with a café milk as a named substitute".
- "The confirmed offer costs **€1,083.39**, exceeding the hotel's €750 purchasing limit and falling below its 90% minimum coverage. **So the agent requests human approval.**" → "This order is above the hotel's €750 limit and below its 90% minimum, so the agent asks Hanna."
- "Hanna approves it, and the order is recorded in our demo system." → "She confirms, and the order is recorded."
- "Every decision is documented, with separate views for the buyer and Valio Aimo." → "Every step is in an audit trail that verifies, and Valio Aimo has its own view of it, without the buyer's limits."
- "**From request to lookup, offer, approval and order — the entire workflow works end-to-end.**" → say it on the way back to the slides, or drop it first if the minute runs long.
- "*Open the audit trail and supplier view.*" → "*Click 'Order and audit trail', then 'What Valio Aimo sees' at the top right. No scrolling.*"
- Header "0:52–2:00" → "about 50 s with the sentences above".

## 6. Problems that need a code change, most serious first
1. **A customer switch while a request is on its way applies the other customer's rules.** `src/tta/ui/static/shop/js/core.js:31` (`export const api = () => gateway(memory.active)`) is read again at every step of a turn: `views/assistant.js:122` (read), `:192` (offer), `:255` (decision), `:271` (order). The turn should keep the customer it was sent for. The server refuses the order, so nothing wrong is ordered; the page still shows milk offered under the milk-allergy ward. Reproduced at 300 ms and 1,500 ms of delay per call, so reachable on the public link.
2. **The back office puts both orders' money on the person.** `src/tta/api/insights.py:95` sums every placed order into `confirmed_net`, and `:100` prints it inside "confirmed by a person (…)": "1 confirmed by a person (€1,832.35 before tax), 1 placed by the agent alone". Visible whenever the back office is opened after the 302.
3. **The unconfirmed alternative of a two-line request names one product for both lines.** `src/tta/offers/options.py:524` with `_covered_phrase` at `:545–555`: "Valio Hyvä … (464306) for all 2 items asked for in full, €134.10 before tax". In the window right after Add in block 4.
4. **"Request line 1:" in a headline a person reads.** `src/tta/offers/wording.py:77`. Known to the shot list.
5. **The same request sent twice is counted twice as a sale not made.** `src/tta/api/insight_missed.py:154–171` adds every offer. It may be intended (demand asked twice); it is why slide 9's figure needs exactly one hero sentence.
6. **The headline keeps only the first sentence of the milk note.** "Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk." stands above an option that offers a café milk; the sentence that resolves it (`src/tta/catalog/product_types.yaml:43`, "It is offered only as a named substitute…") reaches the offer's notes and not the option's summary.
7. **The request box loses the cursor and leaves the window after every answer.** Measured: after an answer the focus is on the page body and `#ask-text` is 630 px above the window. The scroll to the answer is in `src/tta/ui/static/shop/js/main.js:150` and `:241`. A second sentence needs a scroll and a click first.
8. **"Reset this customer's demo" asks nothing.** `src/tta/ui/static/shop/js/views/settings.js:178`. One click removes the orders and the 565 L.

Not a code change, but a question a judge can ask: a second request still shows "384 pcs available in storage" after 384 were ordered. The recorded stock does not go down, and the order book commits nobody.

## 7. Runbook for the morning

**Before the pitch**
1. Do not restart the server. If it was restarted, the cards on the page are dead: do step 3.
2. One Chrome window, full screen, toolbar hidden. Tab 1 `/shop`, tab 2 `/llms.txt` at 150%, tab 3 `/docs` (needs internet). On a 1280 × 720 projector set tab 1 to 80% zoom.
3. Reset: Harbourside Hotel → Settings → bottom → "Reset this customer's demo". Customer menu → City Hospital, Ward 4 → the same. Back to Harbourside Hotel → Request.
4. Check the right column: "€0.00 of €3,000.00", "Agent orders alone: never: you confirm", and "No requests yet" below the box.
5. Copy `1,000 litres of lactose-free milk by Monday` to the clipboard. Do not rehearse after the reset; if you do, reset again.

**The live minute**
1. Click the request box, paste, Enter. "Hanna asks for a thousand litres of lactose-free milk by Monday."
2. Point at the headline. "Only 435 litres are confirmed, so the gateway does not promise the rest."
3. Scroll 300 px, until both alternatives are whole. "It offers two other ways, clearly labelled: cheaper with unconfirmed stock, or all confirmed with a café milk as a named substitute."
4. Point at the amber box. "This order is above the hotel's €750 limit and below its 90% minimum, so the agent asks Hanna."
5. Click CONFIRM ORDER. "She confirms, and the order is recorded."
6. Click "Order and audit trail". "Every step is in an audit trail that verifies,"
7. Click "What Valio Aimo sees", top right. "and Valio Aimo has its own view of it, without the buyer's limits."
8. Back to the slides. "Request, lookup, offer, approval, order: end to end."

**If**
- **the page asks a question instead of answering** ("Is it 1,000 or 1?", "What quantity of milk is needed?"): the number was typed as `1.000` or in words. Click the example chip "1,000 litres of lactose-free milk by Monday" under the box: one click, the same answer.
- **the amber box is longer ("today's spend would reach…"), or there are two identical cards, or a red box says "No such offer, order or approval"**: the book is not clean. Settings → bottom → "Reset this customer's demo" → Request → send again. Six seconds.
- **"The gateway could not be reached. Check that it is running."**: the server is down. Go to the recorded video; do not open the terminal on stage.

**If a judge says "show me"**: the clicks are in section 3. No reset between the live minute and any of the four; never reset before showing the 565 litres.
