# Video: shot list (2:00, strictly) — FINAL, Sun 15 Nov: the script follows what was recorded

**As recorded**
1. City Hospital, Ward 4, its Settings only: milk and cereals with gluten excluded, limit per order 500, ordering alone off.
2. Harbourside Hotel: the milk sentence, the answer (435 L confirmed).
3. The two alternatives and the suggestion; ADD on the cooking cream.
4. CONFIRM ORDER on the default option, €1,116.49 (435 L of milk and 10 L of cream). No CHOOSE: the €2,613.74 option was not taken.
5. The audit trail of that order, in both views: the buyer's and "What Valio Aimo sees".
6. The agent ordering alone at the hotel: 300 L (not 302 and 303).
7. Kallio Bakery: "You usually order this:".
8. No `/llms.txt`, no `/docs`.

- **Part A, "Step by step":** the moves as planned before the recording. The recording departed from it; see the line at its top.
- **Part B, "The script":** the spoken paragraphs for the video as recorded, each in a full and a short length.

Part A was walked twice as written from a clean start (headless Chrome, page area 1440 × 900, final code `b567e5f`, demo clock, no model). The recorded path of Part B was walked once more the same way. Pictures: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/6585c036-9723-4ff4-97e0-3fba8894a301/scratchpad/vidwalk/shots/` (`s1-…`, `s2-…` for Part A; `u1-…` for the recorded path).

## Before you record
- **Hard-reload the page once before the first take (Cmd+Shift+R):** the server was restarted on the final code, and a browser holding older scripts would not start.
- Open `http://127.0.0.1:8011/shop` in Chrome, Chrome in full screen with the toolbar hidden (View → Always Show Toolbar in Full Screen off), zoom 100%, so the page area is about 900 px high. Recorded Valio Aimo data, demo clock Thu 12 Nov 2026 14:15.
- Start clean: Settings (hotel) → bottom of the page → "Reset this customer's demo". Do the same for the ward. Back to Harbourside Hotel → Request. The right column must read "€0.00 of €3,000.00" and "Agent orders alone: never: you confirm", and the page "No requests yet".
- **Record in the order of Part A, in one browser, without reloading.**
  - Steps 1 to 9 save nothing and change no later answer (walked). Record them before step 28, which switches ordering alone on.
  - Steps 10 to 24 are one chain: each needs the one before. **Send the milk sentence once only, click ADD once only.**
  - Step 26 resets the hotel, off camera: do it only when steps 10 to 24 are recorded. The reset removes the hotel's cards and its order.
  - Steps 34 to 36 (the ward) depend on nothing.
  - A take of steps 10 to 24 went wrong: reset the hotel, menu "Request", start again from step 10. Without the reset there are extra cards, and after a confirmed order the amber box adds "today's spend would reach…".
- A toast stays about 3 seconds at the bottom of the window ("Now shopping as…", "Sent as a new request: its offer is the first result.", "Demo reset for this customer."): wait for it to go before a picture you keep.
- Folds you open stay open. After each request, and after ADD, the page scrolls by itself so the newest answer is at the top. CHOOSE does not move the page.
- Type the sentences exactly. Say litres, not cartons. No price in a sentence.
- **In a shorter window (page area about 780 px, same scrolls tried):** step 19, the second and third product rows are under the window (CONFIRM ORDER is in view); step 24, scroll about 80 px for the sentence under "Trail intact". Everything else you keep is whole.

### The reader
The server runs without a model, like the public link. Sentences are read by the fixed rules, at once, and the grey line under "Asked" says so ("read by fixed rules, no model"). Do not say that a model reads the sentence in this recording.

## Part A — Step by step

**The recording departed from this plan:** only the ward's Settings were filmed for the profiles (not the customer menu, not the hotel's Settings); after ADD the default option was confirmed at €1,116.49, without CHOOSE (steps 17 to 19 were not done, and the order has 3 products, not 4); the agent ordering alone was filmed with one request of 300 litres, not 302 and 303 (steps 31 to 33); Kallio Bakery's "You usually order this:" was filmed at the end; steps 37 and 38 (`/llms.txt`, `/docs`) were not filmed. The steps below are kept as planned.

One move per line, then what must be on screen before the next move. **CUT** marks where the editing cuts. *(off camera)* moves are not in the video. "Hold" is how long the picture stays in the finished video.

### Profiles (video 0:08–0:23)
1. *(off camera)* Be on the Request page as Harbourside Hotel, at the top. → "No requests yet"; right column "Limit per order €750.00".
2. Click the customer button, top right ("HL · Hanna Laine · Harbourside Hotel"). → The menu "SWITCH CUSTOMER": Kilo School, City Hospital, Ward 4, Harbourside Hotel ("In use"), Kallio Bakery. Hold 2 s.
3. Click "City Hospital, Ward 4". → The ward's Request page; toast "Now shopping as Jussi Nieminen, City Hospital, Ward 4".
   **CUT**
4. Click the menu "Settings". No scroll. → "Milk" and "Cereals with gluten" ticked; "Set by Sari Lehto, the dietitian"; "Strict" twice. Hold 5 s.
   **CUT**
5. *(off camera)* Click the customer button.
6. *(off camera)* Click "Harbourside Hotel". → The hotel's Request page.
7. *(off camera)* Click the menu "Settings".
8. Scroll down 500 px. → The heading "What the agent may do alone" just under the menu bar; the switch "Let the agent place orders alone" off; "Limit per order" 750; "Limit per day" 3000; "Partial deliveries: At least 90%". Hold 8 s. **Save nothing.**
   **CUT**
9. *(off camera)* Click the menu "Request". → The request box, empty.

### The milk sentence (video 0:23–0:35)
10. Click the request box and type `1,000 litres of lactose-free milk by Monday`. Trim the typing to about 5 s.
11. Press Enter. → The page scrolls to the answer: "ASKED 1,000 L lactose-free milk, by Mon 16 Nov"; "2 confirmed products cover 435 L of the 1,000 L asked for (565 L missing), for €1,083.39 before tax"; the total €1,083.39; the amber box "Needs your decision"; CONFIRM ORDER; the rows "384 pcs × €2.48" and "51 pcs × €2.57". Hold 7 s. Do not click CONFIRM ORDER.

### What the gateway suggests (video 0:35–0:51)
12. Scroll down 780 px. → In one window: "Alternative: quantity not confirmed · €1,010.00"; "Alternative: confirmed stock, completed with a substitute · €2,580.64"; "Suggested from your past orders … it was in 7 of your last 8 orders … Adding 10 L costs €33.10" with the button ADD; "Why this answer" at the bottom. Hold 9 s.
13. Click "Why this answer". → It opens at the bottom of the window ("RULES CHECKED").
14. Scroll down 650 px. → "Why this answer" just under the menu bar: "RULES CHECKED" with two rules; "LOOKED AT 26 PRODUCTS, LEFT OUT 2"; "1 single-serve portions · 1 cannot be delivered"; "21 products fit the request and are in no option because Valio does not confirm their quantity". Hold 6 s.
   **CUT**
15. *(off camera)* Scroll back up 650 px. → The picture of step 12, with ADD in the window.

### "Add", the full order, the confirmation (video 0:51–1:08)
16. Click ADD (the green button under "Suggested from your past orders"). Keep the click, 2 s. → A new answer appears on top and the page jumps to it: "ASKED 1,000 L lactose-free milk + 10 L Arla Pro Cooking cream 10% 1 L UHT lactose free (463797), by Mon 16 Nov"; total €1,116.49; toast "Sent as a new request: its offer is the first result."
   **CUT** at the click: the headline of this window reads "…For milk: Milk made for coffee…", a doubled word. Do not hold it.
17. *(off camera)* Wait for the toast to go, then scroll down 575 px. → Three rows: "384 pcs × €2.48", "51 pcs × €2.57", "Arla Pro Cooking cream 10% 1 L UHT lactose free · €33.10 · 10 pcs × €3.31"; under them "Alternative: quantity not confirmed · €1,043.10" and "Alternative: confirmed stock, completed with a substitute · €2,613.74". Keep from this picture, hold 3 s.
18. Click CHOOSE on the second alternative (€2,613.74). → The page does not move; the window shows the row "Arla Cafè milk … 565 pcs × €2.65", "Not a like-for-like replacement, and nothing like for like can be ordered. A person decides.", and the cream row.
   **CUT** at the click: in this window the list "Other options" carries the same "For milk: Milk" sentence in small text.
19. *(off camera)* Scroll up 575 px, until the "Asked" line is just under the menu bar. → "YOUR CHOICE"; "All 2 items asked for in full from confirmed stock, if 565 L may be Arla Cafè milk 1 L UHT lactose free (463380) at €2.65 per L: €2,613.74 before tax"; the total €2,613.74; the amber box "Needs your decision … A person decides whether it will do…"; CONFIRM ORDER; the rows 384, 51 and 565 pcs. Keep from this picture, hold 5 s.
20. Click CONFIRM ORDER. → In place, no jump: the green box "Confirmed by Hanna Laine · delivery Mon 16 Nov"; "Ordered for €2,613.74. Why it needed your confirmation: …"; right column "€2,613.74 · confirmed". Hold 6 s.

### The audit trail and Valio Aimo's view (video 1:08–1:24)
21. Click "Order and audit trail" in the green box. → The order page: "4 products · €2,613.74 · delivery Mon 16 Nov"; "Confirmed". Hold 2 s.
22. Scroll down 1,135 px, until the heading "Audit trail" is just under the menu bar. → "Trail intact: The audit trail is intact: each of the 11 events shown here matches its hash, and the chain they belong to verifies."; the steps "Request received", "Request read", "Price and stock checked", "Offer made", "Rules checked". Hold 7 s.
   **CUT**
23. *(off camera)* Scroll back to the top.
24. Click "What Valio Aimo sees", top right. Do not scroll. → The banner "This is Valio Aimo's view of the order, not Harbourside Hotel's"; the table "What Valio Aimo receives" with four rows (384, 51, 565 and 10 pcs) and "Total before tax €2,613.74"; under it "Trail intact … each of the 11 events …". Hold 7 s.
   **CUT**

### The agent orders alone (video 1:24–1:42)
25. *(off camera)* Click the menu "Settings".
26. *(off camera)* Scroll to the bottom and click "Reset this customer's demo". → Toast "Demo reset for this customer."; wait for it to go.
27. *(off camera)* Scroll up until the heading "What the agent may do alone" is just under the menu bar (the picture of step 8). → The switch is off.
28. Click the switch "Let the agent place orders alone". → The switch turns dark; the bar at the bottom says "Unsaved changes to limits or allergens."
29. Click SAVE. → "Saved. The gateway now applies these limits to every order of this customer." Hold 2 s.
   **CUT**
30. *(off camera)* Click the menu "Request". → Right column "Agent orders alone: when all is confirmed"; "€0.00 of €3,000.00"; "No requests yet".
31. Type `302 litres of lactose-free milk by Monday`, press Enter (trim the typing). → The green box "Ordered by your agent · delivery Mon 16 Nov"; the total €748.96; "The agent placed this order alone for €748.96 net. That was allowed: … the total of €748.96 is within the €750 limit per order; …"; the row "302 pcs × €2.48". Hold 6 s.
32. Press `/`. → The page is at the top and the cursor is in the request box.
33. Type `303 litres of lactose-free milk by Monday`, press Enter (trim the typing). → The amber box "Needs your decision: The total of €751.44 before tax is above the €750 limit per order of Harbourside Hotel."; CONFIRM ORDER; the row "303 pcs × €2.48". Hold 6 s. Do not confirm.
   **CUT**

### The ward's refusal (video 1:42–1:52)
**As recorded, this part shows Kallio Bakery instead:** customer button → "Kallio Bakery" → the block under the request box, "You usually order this: Oatly iKaffe 0,5L × 30 L, Arla Whipping cream 1 L ESL lactose free × 10 L" with the buttons ORDER THE SAME AGAIN and NOT NOW (the bakery's regular order, worked out from its past orders; "Order the same again" asks for an offer at today's prices and stock, €160.10 before tax in the walk, and nothing is ordered until a person confirms). Kilo School's Request page has no such block (checked); the hotel's has one, for its cooking cream. The ward's refusal below stays as the alternative.

34. *(off camera)* Click the customer button.
35. *(off camera)* Click "City Hospital, Ward 4". → The ward's Request page; wait for the toast to go.
36. Type `100 litres of lactose-free milk by Monday`, press Enter (trim the typing). → The tag "Strict: no milk, cereals with gluten"; the red box "Nothing can be offered for this request. 26 products checked, 26 left out. All 26: The product declares that it contains milk, which the buyer excludes." Hold 8 s.
   **CUT**

### Open standards (video 1:52–2:00)
37. Show the tab `http://127.0.0.1:8011/llms.txt`, opened in advance and zoomed to 150%. → "# Trusted Trade Agents gateway" and its first lines. Hold 4 s.
38. Show the tab `http://127.0.0.1:8011/docs`, opened in advance (it needs internet). → The 30 routes. Hold 4 s. Without internet: stay on `/llms.txt` for the 8 s.

**If the cut runs over 2:00,** drop in this order: steps 37–38 (8 s, openness), then steps 25–33 (18 s, the agent deciding alone), then steps 34–36 (10 s, the allergen refusal). Never steps 16 to 24: they are the suggestion taken, the person confirming and the log.

**If step 16 to 20 goes wrong twice,** leave "Add" out: reset, send the milk sentence, scroll 780 px, click CHOOSE on "Alternative: confirmed stock, completed with a substitute · €2,580.64", scroll up 780 px, CONFIRM ORDER. Walked twice in the earlier round: "Confirmed by Hanna Laine · delivery Mon 16 Nov", "3 products · €2,580.64", 11 events, "Trail intact" (the heading "Audit trail" is then 1,050 px down).

## Part B — The script (Hanna's story, as recorded)

The same story and structure as the first script (Hanna, who buys for Harbourside Hotel), with only what the recording changed: the profile shown is the hospital ward's; Hanna keeps the confirmed part (435 litres and the cream, €1,116.49) and does not pick the café milk; the agent orders 300 litres alone; the last part is the bakery's usual order; no line about standards or protocols.

| # | Said over | Say | Words | Speech |
|---|---|---|---|---|
| 1 | Title card | "Meet Hanna. She buys for a hotel kitchen, and her purchasing agent talks to Valio Aimo through our gateway." | 19 | 8 s |
| 2 | The ward's Settings: the allergens, then the limit per order and the switch | "Every buyer has a profile that the agent must respect. This hospital ward excludes milk and gluten, allows 500 euros per order, and its agent may not order alone. Hanna's hotel has its own." | 34 | 14 s |
| 3 | The hotel: the sentence typed, the answer with 435 L | "Hanna needs a thousand litres of lactose-free milk by Monday. The gateway checks Valio Aimo's prices and stock, and can confirm only 435 litres." | 24 | 10 s |
| 4 | The two alternatives and the suggestion | "Instead of guessing, it shows two ways to cover the rest: a cheaper milk whose stock is not confirmed, or confirmed stock completed with a café milk, named as a substitute. Each comes with its reasons." | 36 | 14 s |
| 5 | The click on ADD, the new answer (€1,116.49), CONFIRM ORDER, the green box | "It also notices this kitchen usually orders cooking cream, and Hanna adds it in one click. She keeps what is confirmed, 435 litres and the cream. That is above her limit and only part of what she asked for, so Hanna confirms it herself." | 44 | 18 s |
| 6 | The order page, "Trail intact", "What Valio Aimo sees" | "Every step, from her request to her approval, is now written in a log that cannot be changed unnoticed. Valio Aimo reads the same order in its own view, without the hotel's limits or allergens." | 35 | 14 s |
| 7 | The switch on, 300 litres, "Ordered by your agent" | "Later Hanna lets the agent order alone. 300 litres stay under her limit, so the agent places the order and says why it was allowed. Anything over the limit would still wait for her." | 34 | 14 s |
| 8 | Kallio Bakery: "You usually order this:" | "And it is the same for every kitchen: at a bakery, the gateway already knows the usual order and offers it again in one click." | 25 | 10 s |
| 9 | The last picture | "A person asks, an agent does the work, and a person stays in charge." | 14 | 6 s |

**Count:** 265 words, about 106 seconds of speech at 2.5 words a second. To leave more silence, drop the last sentence of paragraphs 4 and 7.

**Who is on screen at the bakery:** the page says you are acting as Marko Heikkinen, the bakery's owner. Hanna is the hotel's buyer, so she is not the one clicking there. The line names nobody, so the story stays hers. If "Order the same again" was clicked in the take, add: "One click, and the order is prepared, waiting for the owner's confirmation."

### The same script in the screens' own words (an earlier version, with a full and a short length for each part)


One story, eight paragraphs, in the order of the video. Each is said over one part of the video and describes what is on screen at that moment. Each comes in two lengths: take the full one where your take is long enough, the short one where it is not; they can be mixed. Leave the rest silent: the answer appearing, the totals and the green boxes need no words. Paragraphs 6 and 7 can change places if your cut has the bakery before the 300 litres.

| # | Said over | Full | Short |
|---|---|---|---|
| 1 | The ward's Settings: the allergens, then the limit per order and the switch | "Every buyer has a profile. This is a hospital allergy ward: its dietitian has excluded milk and cereals with gluten, and nobody can loosen that here. Its limit per order is five hundred euros, and its agent never orders alone." (40 words, 16 s) | "Every buyer has a profile. This allergy ward excludes milk and cereals with gluten, and its agent never orders alone." (20 words, 8 s) |
| 2 | The hotel: the sentence typed, the answer appearing | "At Harbourside Hotel, Hanna asks for a thousand litres of lactose-free milk by Monday. The gateway checks Valio Aimo's price and stock: only four hundred and thirty-five litres are confirmed." (30 words, 12 s) | "At Harbourside Hotel, Hanna asks for a thousand litres of lactose-free milk by Monday. Only four hundred and thirty-five are confirmed." (21 words, 8 s) |
| 3 | The two alternatives, the suggestion, the click on ADD | "For the rest it shows two other ways: a cheaper milk whose quantity is not confirmed, or café milk as a substitute. Hanna takes neither, but adds the cooking cream it suggests." (32 words, 13 s) | "The gateway shows two other ways to cover the rest. Hanna takes neither, but adds the cooking cream it suggests." (20 words, 8 s) |
| 4 | The new answer (€1,116.49), the click on CONFIRM ORDER, the green box | "So the order is what is confirmed: four hundred and thirty-five litres of milk, and the cream. It is above the hotel's limit per order and only part of the milk, so Hanna confirms it herself." (36 words, 14 s) | "The order is above the hotel's limit per order and only part of what she asked for, so Hanna confirms it herself." (22 words, 9 s) |
| 5 | The order page, "Trail intact", then "What Valio Aimo sees" | "Every step is in the order's audit trail, and the trail verifies. Valio Aimo has its own view of the same order, without the buyer's limit amounts or allergens." (29 words, 12 s) | "Every step is in an audit trail that verifies, and Valio Aimo has its own view." (16 words, 6 s) |
| 6 | The switch on, 300 litres, "Ordered by your agent" | "The buyer can also let the agent order alone. Then three hundred litres are ordered by the agent, because the total is within the hotel's limit per order. Above that, it waits for a person." (35 words, 14 s) | "Switched on, the agent orders three hundred litres alone, within the hotel's limit per order." (15 words, 6 s) |
| 7 | Kallio Bakery: "You usually order this:" | "At Kallio Bakery the gateway already shows what Marko usually orders. One click asks for it again, and nothing is ordered until he confirms." (24 words, 10 s) | "At Kallio Bakery the gateway already shows what Marko usually orders, one click away." (14 words, 6 s) |
| 8 | The last picture | "A person asks, an agent does the work, and a person stays in charge." (14 words, 6 s) | "A person asks, an agent does the work, and a person stays in charge." (14 words, 6 s) |

**If you clicked ORDER THE SAME AGAIN at the bakery,** add to paragraph 7: "He clicks, and the order is prepared: a hundred and sixty euros, waiting for his confirmation." (16 words, 6 s). On screen then: "2 confirmed products cover all 2 items asked for in full, for €160.10 before tax", "Prepared: confirm to order. Your agent prepared this order. Nothing is ordered until you confirm it."

**How long the whole script is** (2.5 words a second, in a 120-second video)

| Combination | Words | Speech | Silent |
|---|---|---|---|
| All full | 240 | 96 s | 24 s |
| Full for 1 to 4 and 8, short for 5 to 7 | 197 | 79 s | 41 s |
| All short | 142 | 57 s | 63 s |

**What the screens show, so the words match** (walked on the final code, 1440 × 900)
- **The ward's Settings:** "Milk" and "Cereals with gluten" ticked; "Set by Sari Lehto, the dietitian: milk and cereals with gluten stay excluded, under the strict rule. This cannot be removed or made less strict here."; "Limit per order" 500; "Limit per day" 1500; the switch "Let the agent place orders alone" off, with "Off: nothing is ordered until Jussi Nieminen confirms it."; "Partial deliveries: Only the full quantity"; "Confirmed data only" on.
- **The hotel's first answer:** "2 confirmed products cover 435 L of the 1,000 L asked for (565 L missing), for €1,083.39 before tax". The two alternatives: "quantity not confirmed · €1,010.00" and "confirmed stock, completed with a substitute · €2,580.64". The suggestion: cooking cream, "in 7 of your last 8 orders … Adding 10 L costs €33.10".
- **After ADD:** "3 confirmed products cover 1 of the 2 items asked for in full, for €1,116.49 before tax. Covered in part: 435 of 1,000 L of milk."; the amber box "The total of €1,116.49 before tax is above the €750 limit per order of Harbourside Hotel and 1 of the 2 items asked for are covered in full; milk is covered in part (435 of 1,000 L); Harbourside Hotel asks for at least 90% of every item."; three rows: 384 pcs, 51 pcs, cream 10 pcs.
- **After CONFIRM ORDER:** the green box "Confirmed by Hanna Laine · delivery Mon 16 Nov", "Ordered for €1,116.49. Why it needed your confirmation: …". The order page: "3 products · €1,116.49 · delivery Mon 16 Nov", "Confirmed"; "Trail intact … each of the 11 events …" (the heading "Audit trail" is 854 px down). Valio Aimo's view, first window: the banner "This is Valio Aimo's view of the order, not Harbourside Hotel's" ("Limit amounts and allergens are not shown to Valio Aimo"), three rows, "Total before tax €1,116.49", "Trail intact".
- **300 litres with ordering alone on:** "1 confirmed product covers the 300 L asked for, for €744.00 before tax"; the green box "Ordered by your agent · delivery Mon 16 Nov"; "The agent placed this order alone for €744.00 net. That was allowed: ordering alone is switched on for Harbourside Hotel; the total of €744.00 is within the €750 limit per order; today's spend with this order is … of the €3,000 limit per day; every statement of the offer is confirmed; and no rule asked for a person."; one row, "300 pcs × €2.48". The day's figure reads €744.00 if the hotel was reset before, €1,860.49 if it was not. Its own trail has 8 events and "Trail intact".
- **Kallio Bakery:** "you are acting as Marko Heikkinen, owner"; "You usually order this: Oatly iKaffe 0,5L × 30 L, Arla Whipping cream 1 L ESL lactose free × 10 L"; the buttons ORDER THE SAME AGAIN and NOT NOW.

## Not for the camera
- **As recorded, the window in which CONFIRM ORDER was clicked:** its headline reads "…For milk: Milk made for coffee is not offered as milk…", a doubled word in large text, before and after the click. The order page repeats it under "What was ordered". The script talks about the total and the green box, not the headline. If you can, crop or cut so the headline is on screen as briefly as possible.
- **The window right after ADD (step 16):** its headline reads "…For milk: Milk made for coffee is not offered as milk…", a doubled word in large text. Cut at the click and come back after the scroll of step 17.
- **The window right after CHOOSE (step 18):** the same sentence, in small text, under "Best confirmed option (partial fill) · €1,116.49". Cut at the click and come back at step 19.
- **Valio Aimo's view scrolled down:** its tenth step reads "Approval decided · The buyer's purchasing manager, dietitian, finance", three roles for one approval, while the buyer's log says "It needs the purchasing manager" and "Approval decided · Hanna Laine, Harbourside Hotel". The first window of that view does not show it: do not scroll there.
- **A number said over the trail:** the fold in step 14 says "LOOKED AT 26 PRODUCTS"; the trail of the order, made after ADD, says "27 products" and "3 options from 27 candidates" (the cream is the 27th). Both are right; the script names no number there.
- The buyer's log read slowly: it names "My kitchen agent" and ids ("off_…", "ord_…"). Seven silent seconds of it are fine.
- The fold "Why this answer" read slowly: "Request line 1:" twice and "goods from finland blue swan" in the small text.
- The order page's top: "Orders · ord_…" above the title, "Policy fingerprint".
- The green box of the 300 litres read slowly: if the hotel was reset before that take it says "today's spend with this order is €744.00 of the €3,000 limit per day", a little after the video showed a €1,116.49 order; without a reset it says €1,860.49, which agrees with the video.
- The older answer under the new one after ADD: "Replaced by the newer request above. Nothing is ordered from this one." Its "Asked" line shows at the bottom edge in step 17; that is fine.
- Valio Aimo's back office: it is not in this video and was not walked after ADD.
- "384 pcs available in storage" on the 303 answer, after 302 of them were ordered.
- "…by tomorrow" requests: the decision box shows a date as 2026-11-13.
- Substitutes for products outside milk, cream and plant drinks.
- The old pages (the footer link "the gateway's first pages").
