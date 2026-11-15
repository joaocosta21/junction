# Demo check: the video and the live minute, walked as written (Sun 15 Nov, 04:05; walked again on the final code, 04:45)

## Verdict (second walk, final code `b567e5f`)
- **Video: yes, as the shot list now stands.** Blocks 2 to 6 work as written on the final code, every promised word and figure is on screen, and block 6 needs no scroll and no click between the two sentences. Three small corrections to the shot list remain (section 5).
- **Live minute: yes, as slide 5 now stands** (about 50 s, five actions, the same clicks and the same 300 px scroll at a page area 900 px high).

## 0. What differs on the final code
Walked again in the recording order (blocks 2, 3, 4, 5, 6, then the live minute from a fresh browser), page area 1440 × 900, with the hero also at 1440 × 780, 1280 × 720 and 390 × 844. Pictures: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/6585c036-9723-4ff4-97e0-3fba8894a301/scratchpad/democheck/shots2/`. Everything not named here is as in the first walk.

1. **Block 2, the hero.** The headline is one line longer, so everything under it sits 23 px lower.
   - Headline's last sentence, as it appears: "Milk made for coffee is not offered as milk: it appears only as a named substitute, or when coffee milk is asked for by name (product type coffee milk)." It no longer contradicts the third option, and reads well.
   - 1440 × 900, right after the request: CONFIRM ORDER 576–610 px down (was 553–587), in the window; alternatives at 850–948 and 956–1,174.
   - 1440 × 900, after the 300 px scroll: total 117–167, "Needs your decision" 181–322, CONFIRM ORDER 276–310, alternatives 550–648 and 656–874. All whole, 26 px to spare.
   - 1440 × 780, right after the request: CONFIRM ORDER 576–610, in the window.
   - 1440 × 780, after the 300 px scroll: CONFIRM ORDER 276–310, in the window, but the second alternative (656–874) is cut 94 px short. It needs 415 px: CONFIRM ORDER 161–195, alternatives 435–533 and 541–759, the total under the header.
2. **"New request /" and the "/" key.** Both appear and both work.
   - The pill is at the top right of the newest result only (809–937 px across, 96–124 down). It covers nothing: the bold line keeps 150 px free for it, also when that line takes two rows (after Add) and at 390 px wide.
   - A click on it, or "/", scrolls to the top of the page and puts the cursor in the request box. "/" also works from an order page and from Settings; typed inside the box it is a character.
   - Block 6: `302 …` Enter, "/", `303 …` Enter is enough. No scroll, no click.
3. **Block 4 after Add**, on screen as written and filmable:
   - "2 confirmed products cover all 2 items asked for in full, for €281.10 before tax. For milk: Milk made for coffee is not offered as milk: it appears only as a named substitute, or when coffee milk is asked for by name (product type coffee milk)."
   - "Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free (464306) for the 100 L of milk, and from confirmed stock the 10 L of Arla Pro Cooking cream 10% 1 L UHT lactose free (463797): all 2 items asked for in full, €134.10 before tax. Valio does not confirm the quantity in stock of 464306, so a human must approve this option."
   - "For milk: Milk made…" doubles the word; it is the one rough spot.
4. **The back office.**
   - After block 4, unchanged: "2 orders confirmed", "€1,364.49 confirmed, before tax", "€33.10 added to baskets, before tax", "565 L asked for, not confirmed", "€1,407.16 at offered prices, before tax". The sentence: "2 confirmed by a person (€1,364.49 before tax), 0 placed by the agent alone (€0.00 before tax)".
   - After block 6 (which resets the hotel): "1 order confirmed", "€748.96 confirmed, before tax", "0 confirmed by a person (€0.00 before tax), 1 placed by the agent alone (€748.96 before tax)", and no 565 L ("No quantity is counted here as a sale Valio Aimo could not make.").
   - After the live minute and the 302 without a reset: "1 confirmed by a person (€1,083.39 before tax), 1 placed by the agent alone (€748.96 before tax)", and the 565 L · €1,407.16 still there.
5. **The customer switch while a request is on its way: fixed.** With 300 ms of delay per call, in both directions, and with 1,500 ms: the ward's page holds only its two refusals ("Nothing can be offered for this request", tags "Strict: no milk, cereals with gluten"), the hotel's page only its own offer (€248.00, "Prepared: confirm to order").
6. **New, and small.**
   - The tile counts the agent's own order as "confirmed": after block 6 it reads "1 order confirmed" beside "0 confirmed by a person". `src/tta/ui/static/shop/js/views/backoffice.js:95`.
   - At a page area 600 px high CONFIRM ORDER is now cut by the bottom edge right after a request (576–610; computed from the measured positions).
   - On a 390 × 844 phone the title "Needs your decision" now starts at the bottom edge and CONFIRM ORDER is 174 px below the window (was 130).
   - Still as before, not among the six fixes: the same sentence sent twice shows "1,130 L asked for, not confirmed · €2,814.32"; "Reset this customer's demo" asks nothing.

Not walked again: block 7, the "under €400" figure, the typo sentences, the reload and the server restart.

## First walk (commit `d617d5c`): verdict then
- **Video: yes.** All seven blocks worked and every promised word and figure appeared; the "Do" column needed corrections in blocks 2, 3, 4, 6 and 7, since applied to the shot list.
- **Live minute: not as slide 5 was then written (about 65 s); yes with the shorter sentences (about 50 s), since applied to slide 5.**

## How this was checked, and what was not
- Own server from the clean copy of `d617d5c`, replay, demo clock Thu 12 Nov 2026 14:15, no model, no key, port 8051. Headless Chrome 157, a new browser context per run. 86 pictures of the window; the ones a cut or a claim depends on were looked at (about 20), the rest checked by the words in the window: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/6585c036-9723-4ff4-97e0-3fba8894a301/scratchpad/democheck/shots/`.
- **The page area was 1440 × 900.** A real Chrome window of 1440 × 900 has a shorter page area (tabs and toolbar; about 780 px is my assumption, not measured on João's machine). The layout is the same at every width from 1280 up; only the height changes what fits. Measured at 900, 780, 667 and 600 px high; the 720 row is computed from the same positions: see "Window height".
- **Not rendered: `/docs`.** It loads Swagger UI from `cdn.jsdelivr.net`, an outside call this lane may not make. Its 30 routes were counted in `/openapi.json` instead (30 operations, HEAD included). It needs internet when filmed.
- **Not walked:** the three optional swaps of the shot list.
- **Second walk:** the same way from the clean copy of `b567e5f`; what it changed is in section 0, and the sections below are the first walk except where they say "final code".
- Seconds for "raw clicks" are estimates (a script clicked; I assume 1.2 s per pointer action and 7 s to type a sentence). Page response times are measured.

## 1. The video, block by block (recording order 2, 3, 4, 5, 6, 7)

Page response, measured: every answer 0.16–0.37 s after Enter; Confirm 0.16–0.28 s; order page 0.17 s; Valio Aimo's view 0.16 s; Add 0.18 s; reset 0.18 s. Toasts stay 3.2–3.3 s.

| # | Works as written | On screen, as it appears | Spoken line true of the picture | Raw actions | Do not film |
|---|---|---|---|---|---|
| 2 | Yes | "2 confirmed products cover 435 L of the 1,000 L asked for (565 L missing), for €1,083.39 before tax." · "€1,083.39" · CONFIRM ORDER, all in the first window. After the scroll: "Alternative: quantity not confirmed · €1,010.00" and "Alternative: confirmed stock, completed with a substitute · €2,580.64" | Yes, since the shot list says "looks up Valio Aimo's price and stock" and "café milk" | type + Enter + 1 scroll: 2 s, plus 7 s typing | Final code: nothing. The headline's last sentence now agrees with the third option (section 0). The grey line shows the real time of the take |
| 3 | Yes (the shot list no longer scrolls to the log before the tab) | "Confirmed by Hanna Laine · delivery Mon 16 Nov" · "The audit trail is intact: each of the 11 events shown here matches its hash, and the chain they belong to verifies." · "This is Valio Aimo's view of the order, not Harbourside Hotel's" | Yes ("Limit amounts and allergens are not shown to Valio Aimo") | 4 actions: 5 s | Order page, buyer's view: "Orders · ord_…" above the title, "P-01", "P-03", "rules P-01 and P-03 asked for a human and were accepted", the policy fingerprint; in the log "off_…" and "(P-01)" |
| 4 | Yes | "…it was in 7 of your last 8 orders, 10 L each time, and it is not in this request. Adding 10 L costs €33.10." · €248.00 → €281.10 · back office: "2 orders confirmed", "€1,364.49 confirmed, before tax", "€33.10 added to baskets, before tax", "565 L asked for, not confirmed", "€1,407.16 at offered prices, before tax" | Yes | 8 actions: 10 s, plus 7 s typing | Final code: both sentences after Add are filmable (section 0). The toast "Sent as a new request: its offer is the first result." (3.3 s); "384 pcs available in storage" although block 3 just ordered 384 of it |
| 5 | Yes | "Nothing can be offered for this request" · "26 products checked, 26 left out. All 26: The product declares that it contains milk, which the buyer excludes." | Yes | 2 clicks + type + Enter: 3 s, plus 7 s typing | The toast "Now shopping as Jussi Nieminen, City Hospital, Ward 4" (3.2 s; gone by the time the sentence is typed) |
| 6 | Yes. Final code: `302 …` Enter, "/", `303 …` Enter, no scroll and no click | "Ordered by your agent · delivery Mon 16 Nov" · "The agent placed this order alone for €748.96 net. That was allowed: ordering alone is switched on for Harbourside Hotel; the total of €748.96 is within the €750 limit per order; today's spend with this order is €748.96 of the €3,000 limit per day; every statement of the offer is confirmed; and no rule asked for a person." · "Needs your decision" · "The total of €751.44 before tax is above the €750 limit per order of Harbourside Hotel." | Yes | 11 actions: 13 s, plus 14 s typing | The toast "Demo reset for this customer." (3.2 s). The six actions before the switch are setup: film from the switch |
| 7 | `/llms.txt` yes; `/docs` not rendered by me | `/llms.txt`: 33 lines of plain text; `/openapi.json`: 30 operations, licence "MIT" | Yes | 2 tab changes: 2 s | `/llms.txt` at 100% is 13 px text on a full-width page: zoom that tab to 150%. Its links read `http://127.0.0.1:8011/…` |

**Voice-over against the seconds** (150 words a minute, numbers counted as spoken): block 1: 31 words, 12.4 s in 12 s. Block 2: 62 words, 24.8 s in 26 s. Block 3: 37, 14.8 s in 17 s. Block 4: 45, 18.0 s in 18 s. Block 5: 33, 13.2 s in 15 s. Block 6: 45, 18.0 s in 20 s. Block 7: 29, 11.6 s in 12 s. Total 112.8 s of speech in 120 s (seconds as the shot list now gives them).

**Window height (final code).** The answer's layout is fixed: after a request the page scrolls itself so that CONFIRM ORDER sits 576–610 px down and the two alternatives end 1,174 px down. The order page puts "Trail intact" 804–872 px down and the tab "What Valio Aimo sees" 225–261 px down. Measured at 900 and 780; the 720 and 600 rows are computed from the same positions.

| Page area height | After the hero answer | To see both alternatives | Order page |
|---|---|---|---|
| 900 | headline, total, CONFIRM ORDER in the window | scroll 300 px: total, "Needs your decision", CONFIRM ORDER and both alternatives in one window | "Trail intact" and the tab both in the window, no scroll |
| 780 | same | scroll 415 px: CONFIRM ORDER and both alternatives in one window; the total is under the header. At 300 px the second alternative is cut | scroll 120 px for "Trail intact"; the tab stays |
| 720 | CONFIRM ORDER in the window | scroll 475 px: both alternatives whole, CONFIRM ORDER just under the header | scroll 180 px for "Trail intact"; the tab is then half under the header, scroll back a little to click it |
| 600 | CONFIRM ORDER cut by the bottom edge | scroll 595 px, then back up to confirm | scroll 300 px; the tab is gone, scroll back to click it |

## 2. The live minute (slide 5), from a fresh browser

Slide 5 now carries the shortened sentences of this table. As it was first written: 141 spoken words, 56 s at 150 words a minute, plus about 3 s of typing that the first sentence does not cover and about 5 s where the pointer travels in silence: **about 65 s.** Shortened (below): 103 words, 41 s, plus the same 8 s: **about 50 s.** If it still runs long, drop the closing sentence first; keep the click on "What Valio Aimo sees".

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
| 7: 302 litres ordered, 303 waits | Harbourside Hotel → Settings (the switch is in the first window at 900 high) → "Let the agent place orders alone" → SAVE → Request → `302 litres of lactose-free milk by Monday` → press "/" (final code) → `303 litres of lactose-free milk by Monday` | "Ordered by your agent · delivery Mon 16 Nov", €748.96 · then "Needs your decision: The total of €751.44 before tax is above the €750 limit per order of Harbourside Hotel." | Yes, to the litre. **No reset is needed** after the live minute: the sentence then reads "today's spend with this order is €1,832.35 of the €3,000 limit per day" |
| 9: 565 litres, about €1,400 | scroll to the top → strip tab "Valio Aimo's back office (demo)" → scroll down 680 px | "565 L asked for, not confirmed" · "€1,407.16 at offered prices, before tax" · "435 of 1,000 L of lactose-free milk could be confirmed: 565 L, about €1,407 at the offered price, were not." | Yes, **only if the hero sentence was sent exactly once in this browser and the hotel was not reset since.** Sent twice: "1,130 L · €2,814.32". After the hotel's reset: "No quantity is counted here as a sale Valio Aimo could not make." Still 565 L after the ward's refusal, the 302 and the 303 |

## 4. What can go wrong in front of people

| Tried | What the person sees | On stage |
|---|---|---|
| Page reloaded mid-flow | Answers and orders stay, and an answer can still be confirmed. Lost: text typed and not sent, open folds, and the tab "What Valio Aimo sees" (back to the buyer's view of the same order) | Carry on; click the tab again |
| Same sentence sent twice | Two identical cards, the new one on top, each with CONFIRM ORDER. Back office doubles: "1,130 L asked for, not confirmed · €2,814.32" | Send the hero once. If twice: reset the hotel before showing the back office |
| CONFIRM ORDER clicked twice | One order. The button is replaced by the green box; the link "Order and audit trail" lands where the button was, so a slow second click opens the order page | Nothing: that is the next step anyway |
| Customer switched with an answer open | The other customer's page, empty. Switching back shows the answer, still confirmable | Switch back |
| Customer switched while a request is on its way | **Fixed on the final code:** each customer's page shows only its own answer, at 300 ms and 1,500 ms of delay per call, both directions. On `d617d5c` the answer was made with the other customer's rules and filed under the first one | Nothing |
| 1280 × 720 | Same layout. CONFIRM ORDER is in the window after a request (576–610 of 720, final code) | Full screen; zoom 80% gives the 900-high picture |
| 390 px wide (phone, 844 high) | Asked line with the "New request /" pill, headline and total in the window; on the final code "Needs your decision" starts at the bottom edge and CONFIRM ORDER is 174 px below it. No sideways scroll; "Settings" is reached by swiping the menu row | One short swipe |
| `1000 liters of lactose free milk by monday` | The same answer: "1,000 L lactose-free milk, by Mon 16 Nov", 435 L, €1,083.39. Also `1000l lactose-free milk monday` and `lactosefree` | None needed |
| `1.000 litres…` or `a thousand litres…` | No answer: "The agent needs an answer before it can look this up" · "Is it 1,000 or 1? Write 1000 for the first, or 1 for the second." / "What quantity of milk is needed?" | Type `1,000` or `1000`. Fallback: the example chip under the box, one click, same answer |
| Day's limit | Hero orders 1 and 2 read as the first. **At the third hero sentence** (two confirmed, €2,166.78) the box adds "…with this order today's spend would reach €3,250.17 before tax (€2,166.78 ordered, €0.00 waiting for a person, and this order's €1,083.39), above the €3,000 limit per day of Harbourside Hotel…". Still confirmable; the right column then reads "€3,250.17 of €3,000.00" | Reset the hotel before the pitch; do not rehearse after it |
| "Reset this customer's demo" mid-demo | One click, no question asked. Toast "Demo reset for this customer."; that customer's cards, orders and settings are gone (ordering alone back to off) and its 565 L leaves the back office. The other customers keep theirs | Send the hero again (6 s) |
| Server restarted with cards on the page | The right column says "€0.00 of €3,000.00" while old green cards stay. Old CONFIRM ORDER: "No such offer, order or approval. No offer has this id." with ASK AGAIN. Old "Order and audit trail": "Order not found. It may belong to another customer, or the demo order book was emptied." A new sentence works | Reset both customers after any restart |
| Server down | "The request could not be read into a typed request. The gateway could not be reached. Check that it is running." | Go to the recorded video |

## 5. Corrections

Every correction of the first walk is in `AIMO/VIDEO-SHOTLIST.md` and in slide 5 of `AIMO/PITCH-SCRIPT.md` as they now stand, or was made unnecessary by the final code (block 6's scroll and click, the two "not for the camera" sentences after Add). Slide 5 needs nothing more.

### Shot list, still to correct
- Before you record, window: "In a shorter window every scroll below is longer." → "In a shorter window every scroll below is longer: at a page area of about 780 px block 2 needs 415 px, not 300, for the second alternative to be whole (CONFIRM ORDER stays in the window)."
- Not for the camera: "The back office after block 6: it then also shows the order the agent placed alone." → "The back office after block 6: the reset has removed the 565 L ('No quantity is counted here as a sale Valio Aimo could not make') and the tile reads '1 order confirmed · €748.96' for an order no person confirmed."
- Introduction: "One lane is still adding a price limit read from the sentence: it changes none of these blocks." → remove (the price limit is in; "under €400" was walked on `d617d5c`).

## 6. Problems that need a code change, most serious first

State on the final code `b567e5f`, each looked at in the browser: 1, 2, 3, 4, 6 and 7 are fixed; 5 and 8 are as they were. One new, small: the back-office tile counts the agent's own order under "orders confirmed" (`src/tta/ui/static/shop/js/views/backoffice.js:95`). The line numbers below are those of `d617d5c`.

1. Fixed. **A customer switch while a request is on its way applies the other customer's rules.** `src/tta/ui/static/shop/js/core.js:31` (`export const api = () => gateway(memory.active)`) is read again at every step of a turn: `views/assistant.js:122` (read), `:192` (offer), `:255` (decision), `:271` (order). The turn should keep the customer it was sent for. The server refuses the order, so nothing wrong is ordered; the page still shows milk offered under the milk-allergy ward. Reproduced at 300 ms and 1,500 ms of delay per call, so reachable on the public link.
2. Fixed. **The back office puts both orders' money on the person.** `src/tta/api/insights.py:95` sums every placed order into `confirmed_net`, and `:100` prints it inside "confirmed by a person (…)": "1 confirmed by a person (€1,832.35 before tax), 1 placed by the agent alone". Visible whenever the back office is opened after the 302.
3. Fixed. **The unconfirmed alternative of a two-line request names one product for both lines.** `src/tta/offers/options.py:524` with `_covered_phrase` at `:545–555`: "Valio Hyvä … (464306) for all 2 items asked for in full, €134.10 before tax". In the window right after Add in block 4.
4. Fixed. **"Request line 1:" in a headline a person reads.** `src/tta/offers/wording.py:77`. Known to the shot list.
5. Open. **The same request sent twice is counted twice as a sale not made.** `src/tta/api/insight_missed.py:154–171` adds every offer. It may be intended (demand asked twice); it is why slide 9's figure needs exactly one hero sentence.
6. Fixed. **The headline keeps only the first sentence of the milk note.** "Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk." stands above an option that offers a café milk; the sentence that resolves it (`src/tta/catalog/product_types.yaml:43`, "It is offered only as a named substitute…") reaches the offer's notes and not the option's summary.
7. Fixed. **The request box loses the cursor and leaves the window after every answer.** Measured: after an answer the focus is on the page body and `#ask-text` is 630 px above the window. The scroll to the answer is in `src/tta/ui/static/shop/js/main.js:150` and `:241`. A second sentence needs a scroll and a click first.
8. Open. **"Reset this customer's demo" asks nothing.** `src/tta/ui/static/shop/js/views/settings.js:178`. One click removes the orders and the 565 L.

Not a code change, but a question a judge can ask: a second request still shows "384 pcs available in storage" after 384 were ordered. The recorded stock does not go down, and the order book commits nobody.

## 7. Runbook for the morning

**Before the pitch**
1. The server was restarted on the final code: hard-reload the page once (Cmd+Shift+R, as the shot list says), then do step 3, because the cards from before a restart are dead. Do not restart it again.
2. One Chrome window, full screen, toolbar hidden. Tab 1 `/shop`, tab 2 `/llms.txt` at 150%, tab 3 `/docs` (needs internet). On a 1280 × 720 projector set tab 1 to 80% zoom.
3. Reset: Harbourside Hotel → Settings → bottom → "Reset this customer's demo". Customer menu → City Hospital, Ward 4 → the same. Back to Harbourside Hotel → Request.
4. Check the right column: "€0.00 of €3,000.00", "Agent orders alone: never: you confirm", and "No requests yet" below the box.
5. Copy `1,000 litres of lactose-free milk by Monday` to the clipboard. Do not rehearse after the reset; if you do, reset again.

**The live minute**
1. Click the request box, paste, Enter. "Hanna asks for a thousand litres of lactose-free milk by Monday."
2. Point at the headline. "Only 435 litres are confirmed, so the gateway does not promise the rest."
3. Scroll 300 px, until both alternatives are whole (415 px if the page area is about 780 px high). "It offers two other ways, clearly labelled: cheaper with unconfirmed stock, or all confirmed with a café milk as a named substitute."
4. Point at the amber box. "This order is above the hotel's €750 limit and below its 90% minimum, so the agent asks Hanna."
5. Click CONFIRM ORDER. "She confirms, and the order is recorded."
6. Click "Order and audit trail". "Every step is in an audit trail that verifies,"
7. Click "What Valio Aimo sees", top right. "and Valio Aimo has its own view of it, without the buyer's limits."
8. Back to the slides. "Request, lookup, offer, approval, order: end to end."

**If**
- **the page asks a question instead of answering** ("Is it 1,000 or 1?", "What quantity of milk is needed?"): the number was typed as `1.000` or in words. Click the example chip "1,000 litres of lactose-free milk by Monday" under the box: one click, the same answer.
- **the amber box is longer ("today's spend would reach…"), or there are two identical cards, or a red box says "No such offer, order or approval"**: the book is not clean. Settings → bottom → "Reset this customer's demo" → Request → send again. Six seconds.
- **"The gateway could not be reached. Check that it is running."**: the server is down. Go to the recorded video; do not open the terminal on stage.

**If a judge says "show me"**: the clicks are in section 3. No reset between the live minute and any of the four; never reset before showing the 565 litres. For 302 and 303: Settings → switch on → SAVE → menu "Request" → `302 …` Enter → press "/" → `303 …` Enter.
