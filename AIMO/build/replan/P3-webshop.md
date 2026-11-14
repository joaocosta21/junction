# P3 — Valio Aimo's real webshop (answer V4): what it shows, and what we take from it

Agent P3, 14 Nov, 15:10. Topic: the webshop Valio gave us a test login for.

**Ground rule for this whole file** (`AIMO/CHALLENGE.md:52`): "No real-time, live or confidential data or systems – everything you build against is synthetic." The webshop is Valio's real system. Our catalog and the mock API are synthetic. So this file recommends **vocabulary, structure and concepts to follow**. It recommends **nothing that calls the shop, and no shop data in our product or repository**. Where the real shop and our synthetic data differ, that is expected (the catalog is synthetic and noisy on purpose) and is not a fault on either side.

**How I looked.** Read only, with the test login, on 14 Nov 14:45–15:06. 339 requests in total to the shop's hosts (limit 400). Of these: 29 direct reads, 310 made by a headless browser (page files, pictures, the page's own data calls and their pre-flight calls). The 288 requests to the shop and its data interface were spaced at least 1 second apart. The 51 requests of the two sign-ins to the login host were not spaced (the sign-in page loading in a browser), and the browser also fetched 23 files from the sign-in provider's and the bot check's own script hosts. A guard in the browser blocked every call to the shop's data interface that was not a GET, except the sign-in exchange. Counted from my scratch logs. No cart, order, template, favourite, profile or setting was touched.
Three things a teammate should know: (1) I signed in twice, because my own guard blocked the first sign-in exchange. (2) After each sign-in the sign-in page itself sent one call named `accounts.setAccountInfo` to the login host. I did not choose it and cannot see what it writes (assumption: last-login or language bookkeeping). (3) No captcha or bot check stopped me. The session files are deleted; the login is in no file.

## 1. In five lines
1. The shop and our synthetic data come from the same product master: for our demo milk `464306` the real shop shows the same name, GTIN, allergen statement, nutritional claims, package labels, nutrition table and case and pallet sizes. Product numbers, category codes, prices and stock differ, as expected.
2. The shop has a named category tree (three levels, codes of 2, 3 and 4 digits where each level is a prefix of the next). Our 5-digit category numbers are a different code system: no digit relation. We do not import the names (DECISION D1).
3. The shop already has the words for everything our agent does: "Closing time", "Delivery date", "N pcs available in storage" against "Deliverable <date>" (its wording for a product whose quantity it does not show), "Alternative products", "Substitute product", "Order templates", "Standard orders" with "Unapproved lines" and "Suspend order", "Main user", "Does not contain" allergen filter. We use other words for the same things today.
4. Recommendation: a 2-hour vocabulary pass (our pages, option lines and audit sentences use the shop's words) plus the availability line in the shop's two forms. Then, if time allows, a light re-skin that follows the shop's page structure with our own name, no logo, no pictures, no copied texts.
5. For the "credible path to production" criterion: say in our docs that the shop runs on a standard commerce platform that already has carts per delivery date, order templates, standard orders and closing times, so our open order contract maps onto existing concepts. We state this as a next step. We build nothing against it.

## 2. What exists today (ours)
- Pages and navigation: `src/tta/ui/templates/base.html:12-19` — brand "Trusted Trade Agents", links Request · Approvals · Your kitchen · Menu · Standing orders · Assumptions.
- Look: `src/tta/ui/static/app.css:5-15` (black ink on white paper, green/amber/red marks, blue links), `app.css:26` (system font). No header band, no product cards.
- A product option line: `src/tta/ui/templates/_candidate.html:2-11` — rank, name, id, "Listed by Valio Aimo" tag, marks "Passes the allergen rule" and can-be-ordered, "<price> per sales unit", one sentence.
- Our words today: "Order by <time>" (`_result.html:95`), "Cut-offs are judged against that time" (`_result.html:75`), "a cut-off passed" (`src/tta/audit/readers.py:18`, `src/tta/audit/sentences.py:259`), "Substitute" and "Substitutes, ranked" (`_result.html:113,167`), "Listed by Valio Aimo as substitutes" (`_result.html:188`), "Price, before tax", "Stock stated", "not confirmed" (`order.html:97,105`), "Standing orders" (`standing.html:3-5`; 12 template and sentence lines use the phrase, counted with grep over `src/tta/ui/templates/*.html` and `src/tta/audit/standing_sentences.py`).
- Certificate labels are already carried from the synthetic file: `src/tta/catalog/loader.py:46` (`packagingMarkedLabel`), `src/tta/contracts/offer.py:78`, `src/tta/contracts/request.py:64,119`.
- Our synthetic data, for the comparison in section 4 (read from `valio_aimo_junction26_product_data.json`, whole file loaded once, 17,546 products): `464306` → category `10400`, `464013` → `10402`, `466988` → `18720`; `464306` has `allergen = AM, CONTAINS`, `packagingMarkedLabel = GOODS_FROM_FINLAND_BLUE_SWAN, coolTemperature`, units KI = 20 and PAL = 160 base units.
- Our field notes on the mock: `AIMO/docs/FIELD-DICTIONARY.md:151` (`closingTime`), `:153` (`logisticModel` Stock or Terminal), `:161` (`availableAmount` placeholders), `:181` (`category`: "Category names are not part of this data set").

## 3. What the real shop shows (kept apart from our data)
Everything in this section is the real shop, seen with the test account. It is description, not data for our product.

### 3.1 Map of the shop
- **Platform (verified from the page's own files):** SAP Commerce Cloud with the open-source Spartacus storefront. Three languages: Finnish (default), English, Swedish. Currency EUR.
- **Top bar, five services:** Valioaimo.fi · Cash & Carry (Finnish name Pikatukku) · Delivery wholesale (Toimitustukku, the one we saw) · VALO Order Service · My Aimo (Minun Aimo). On the right: the customer account in use, the user's name, the language.
- **Header:** logo · PRODUCTS · ORDERS · NEWS · a wide search box ("Search for products") · "Delivery date" with the chosen date and a count of open carts · "Cart" with line count and total.
- **PRODUCTS menu:** My Favourites · Frequently purchased · Offers · New products · Seasonal products · the eight departments with product counts · "See the whole product catalog".
- **ORDERS menu:** Order Management · Order templates (FI: Tilauspohjat) · Complaints (Reklamaatiot) · Reports (Raportit). Standard orders (Vakiotilaukset) exist in the app's texts and data calls; the test account has none and I did not find the menu entry.
- **NEWS menu:** seasonal and campaign pages, Announcements (Tiedotteet), newsletter, FAQ, Contact.
- **Account:** My information · Change password · Log out · "My Organization" (Oma organisaatio) with user roles.
- **Front page:** "Browse product categories" (one pill per department: name plus count) · a banner · tabs "Your favorite products" and "On offer right now" with product cards · announcements.
- Not opened (request budget): the order template, order history, complaints and reports pages, a category listing, the cart. Their words below come from the app's translation file (657 texts each in English and Finnish, counted).

### 3.2 Category tree
- Yes, the shop shows a tree with names. Three levels below the root. Codes are prefix-built: 2 digits (department) → 3 digits → 4 digits.
- The eight departments, as navigation labels: Fruits and Vegetables · Fresh meat and fish · Fresh products · Industrial groceries · Frozen food · Nonfood · Drinks · Alcohol products. The tree counts 18,176 products for the test account (the shop's own figure). Our file has 17,546.
- **Relation to our numbers: none by digits.** Matched through the GTIN of three of our demo products:

| Our synthetic category | Our product | The real shop's path for the same GTIN |
|---|---|---|
| `10400` | `464306` | Fresh products › Dairy products › Milk and buttermilk (codes of 2, 3 and 4 digits, each a prefix of the next) |
| `10402` | `464013` | Fresh products › Plant-based › Plant-based milk-like |
| `18720` | `466988` | Fresh meat › Veal and beef (two lower levels read; the department above them, Fresh meat and fish, is my inference) |

- So V7 stands: our 5-digit number is another code system (the mentor said "sap code semi random"). Three examples do not prove a rule for all 349 numbers.

### 3.3 A product page
Order on the page, top to bottom:
1. Breadcrumb of the category path.
2. Name (large condensed heading), product number, "EAN <number>". One round certificate mark at the top right when the product has one.
3. Availability line: a green dot and "<N> pcs available in storage", and a link "Availability in Cash & Carry" (stock per store).
4. Price block: price without tax per sales unit (large) · comparison price per litre or kilo · price with tax and the VAT rate in brackets · a minus/plus quantity control with the unit.
5. Description. Action row: Add as favourite · Add to Order Template · Add to comparison · Print · Copy link.
6. Two tabs of product cards: **"Alternative products"** and **"Compatible products"**.
7. "Nutritional content": a table per 100 g, then vitamins and minerals.
8. "Product information": Ingredients (allergens in capitals) · **Allergens** · **Nutritional Claims** · Cooking instruction · Instructions · Storage information · Country of origin/Country of manufacture · Manufacturer · Unit conversions (for example "1 crt = 20 pcs (EAN …)").
- "Allergens" and "Nutritional Claims" are two separate rows. That is our own rule (a claim is never an allergen statement).
- Ingredients carry an origin each (ingredient → country → activity such as "Milking" or "Farming").
- Certificates and sustainability labels ("the certificates/sustainability labels already shown in the webshop", `AIMO/CHALLENGE.md:20`): a group named "Package labels" with the same codes as our `packagingMarkedLabel`, shown as a mark on the picture and usable as a filter.
- No deposit line on the one product page I opened (a milk carton). Deposits appear in the cart totals ("Deposits (VAT 0 %)").

### 3.4 Search and filters
- One search box. Results can be sorted by Relevance · Comparison price · Name.
- Filter groups: Country of origin/Country of manufacture · Manufacturer · **"Does not contain"** (one entry per allergen, and one entry for "Does not contain declaration obligatory allergens", our `X99`) · **"Product attributes"** (among them Lactose free, Gluten free, Organic, Produce of Finland, Key Flag, Heart sign, Vegetarian, Stock Product, Frozen) · two category levels · "Nutritional content" ranges per 100 g (energy, fat, carbohydrates, fibre, protein, salt).
- A search for "lactose free milk" returned 67 products of many kinds (chocolate, ice cream, a flour mix, coffee drinks, milk). The shop's own search has the problem Valio named in B5 ("be explicit"): the words alone do not select drinking milk.

### 3.5 Ordering, as far as it can be read without changing anything
- **Delivery date first.** The header always shows the chosen delivery date. A click opens a month calendar with week numbers. Legend: Current day · Selected date · Open cart · Order confirmed. For the test account, delivery days are Monday to Saturday, never Sunday; on Saturday 14 Nov the first selectable day was Monday 16 Nov.
- **One cart per delivery date.** The calendar marks each day that has an open cart; totals are "Delivery date total".
- **Closing time (FI: Sulkuaika) per product and delivery date.** Each product card has a clock. In the 9 search rows whose dates I read on Saturday 14 Nov: 7 had stock, Monday 16 Nov as delivery day and a closing time of Sunday 15 Nov 17:00 Finnish time; 2 had no stock quantity, Wednesday 18 Nov as first delivery day and a closing time of Monday 16 Nov 15:00. The cart warns "Product closing time approaching". A text whose key is named after the closing time says "Not available for your preferred delivery date" and offers to move the line to another date (I did not see it on screen).
- **Two availability wordings.** "<N> pcs available in storage" for products with stock in the wholesaler's storage. "Deliverable <date>" with no quantity for the others (the app's own key for this text is "terminal availability"; I saw it on one product flagged as terminal, and a date without quantity on one stocked product that had no stock). One card showed "999+ pcs available in storage".
- **An order stays open until its closing time** (read from the status texts, not seen on screen). Statuses: Created · Open ("closes <date> at <time>") · Not modifiable · Processed · Not paid.
- **Cart header fields:** Customer · Delivery address · User · User reference · Message to driver · Payment method. Totals: Purchases (VAT 0 %) · Deposits · Delivery fee · "Additional reservation" (an extra amount held for variable-weight products, matching Valio's answer to Q16) · Total (VAT 0 %) · Total (incl. VAT). Final button: "Confirm order".
- **Order templates:** named product lists; "Add to Order Template" on every product. A setting can hide normal order templates from basic users.
- **Standard orders** (the shop's English word for recurring orders): name, reference, days of the week, repetition (weekly or every other week), a processing time in days before a new or changed one takes effect, "Suspend order" with a reason and a period, "Resume order", an e-mail reminder, **"Unapproved lines"** with an approve/reject step. Its exception messages: "Product quantity was not sufficient, quantity changed" and "Item is discontinued".
- **Roles:** "Main user" (FI: Pääkäyttäjä) and ordinary users. The main user accepts or dismisses new user applications ("Pending approval"). In the texts and data I read I found **no spend limit and no order approval by amount**. Who approves standard-order lines is not visible (question Q1).
- **Account conditions the shop tracks:** the cart carries flags for credit limit exceeded, credit block, sales block and unapproved changes; the customer account carries an alcohol permission, a tobacco permission, a kitchen alcohol licence, a school milk scheme flag, net prices and group discounts. What each one does to an order I did not test.
- **Minimum order:** none found. A delivery fee exists per customer.

### 3.6 The data interface behind the pages, as concepts
The pages talk to the platform's standard REST interface, with Valio's additions. We do not call it and do not store its answers. Its field names are useful only as vocabulary:

| Concept in the real shop | Its name there | In the mock or our files |
|---|---|---|
| Latest order time for a delivery date | `closingTimeForTheFuture` | `closingTime` |
| First delivery date | `availableDate` | `availableDate` |
| Held in storage or not | `terminalProduct` true/false | `logisticModel` Stock/Terminal |
| Quantity | a number plus a display text | `availableAmount` with placeholders |
| Category path with names | `categories` (code, name) | `category`, a number without a name |
| Allergens, claims, labels | `allergen`, `nutritionalclaim`, `packagingmarkedlabel` | the same three groups in `synkkaData.classifications` |

What it has that the hackathon material lacks: search with filters; alternative and compatible products per product; stock per Cash & Carry store; price with tax, comparison price, offer price with the struck-out price and validity dates; a delivery-day calendar per customer; favourites, "Frequently purchased" and "last purchased" per customer; order templates; standard orders; order history, complaints, reports; account blocks and permissions. The mock has none of these, by design. They are the list of things our own interface may define.

### 3.7 The look (CSS values read from the shop's stylesheet and computed styles)
- Colours: dark teal `#005670` (top bar, headings, links, round buttons) · darker teal `#003747` · lavender header band `#eee8f5` · pale panel `#f2f6f8` · border `#dee4e6` · muted text `#8c9699` · lime call-to-action and "new" tag `#c0e021` and offer red `#f9423a` (these two matched to the screen by eye) · white cards on the pale panel.
- Type: headings and buttons in a bold condensed face (National 2 Compressed), h2 40px, h3 32px, buttons 18px uppercase with 0.5px letter spacing. Navigation and most text in a geometric sans (Matter); the page default is Open Sans, 16px. National 2 and Matter are commercial fonts: we do not copy the files.
- Shapes: pill-shaped category chips and action links (30px radius), round icon buttons, square-cornered cards with a thin border (cards by eye).
- A product card, top to bottom: tags at the top left ("NEW PRODUCT", "OFFER", "SEASONAL") and two round icons at the top right (add to template, favourite) · picture · name in teal bold · product number (a snowflake before it for frozen) and pack size · price large and bold, red with the old price struck out when on offer · two small lines (comparison price; price with tax) · round cart button · bottom line: availability on the left, clock on the right.

### 3.8 Automated clients
- `/robots.txt` returns the app's own page, so there is no robots file. I did not open the terms of sale (the footer links to them). A person should read them before anyone automates anything there.
- For us the question is closed by `AIMO/CHALLENGE.md:52`: we build against synthetic data only.

## 4. Real shop and synthetic data, side by side
| Our demo product | In the real shop | Same | Different (expected) |
|---|---|---|---|
| `464306` | Found by its GTIN, under another product number (7 digits) | Name, GTIN, allergen statement (contains milk), nutritional claims (lactose free and others), package labels (Blue Swan, cool storage), nutrition per 100 g, 20 per case and 160 per pallet with the same case and pallet GTINs, origin Finland | Product number. Category code. Price (higher in the shop than our recorded €1.01, which is `BRIEF.md:69`'s €1,010.00 for 1,000). Stock: the shop shows a confirmed three-digit quantity in storage; our recording says quantity not confirmed |
| `464013` | Found by GTIN (search row only) | Name, allergen statement (contains soy; ours `AY, CONTAINS`) | Product number, category code; in storage with a confirmed quantity |
| `466988` | Found by GTIN (search row only) | Name, sold by kilo, no allergen listed on either side | Product number, category code |
| `471881` | Not found by GTIN (0 results) | — | Not in the test account's range today, or the GTIN is synthetic. So the shop cannot settle Q2 (oat drink, gluten). Valio's answer stands: "take the values as they are in the data" |
| `469363`, `463380`, `473609`, `465793` | Not looked up (request budget) | | |

Reading: **the ids do not match; the GTINs do.** Master data matches where I looked. Price, stock and dates are the synthetic part. We keep trusting only the synthetic data and the mock.

One note for whoever owns V6 (order deadlines): the latest `closingTime` in our capture is `2026-11-15T17:00:00+0200` (`AIMO/docs/FIELD-DICTIONARY.md:151`). That is the same instant as the real shop's closing time for Monday delivery of the 7 stocked rows above. It is a sample of 9 rows of the real shop, not a rule for our data.

## 5. What Valio's answer changes, and what this changes in our plan (ranked)
V4 gave us the real shop to look at; João asks whether our interface should be close to it. Answer: close in words and structure, yes; in data and calls, no.
1. **Speak the shop's language** (20% least manual correction; 15% credible path). A Valio judge reads "Closing time", "Delivery date", "available in storage", "Deliverable", "Alternative products", "Standard order" every day. Today we say "cut-off", "order by", "stock stated", "substitutes", "standing order". Section 6 is the table.
2. **Our unconfirmed-quantity rule is the shop's own split** (20% autonomy and controls; 15% exceptions). The shop shows a quantity only for products in storage and shows "Deliverable <date>" for the rest. We present our rule in those words: confirmed stock can be ordered within the profile; "Deliverable" products always need sign-off.
3. **A passed closing time has a shop-native answer** (15% exceptions): "not available for your delivery date; next possible date <date>". Our agent says and does the same.
4. **V8 and the shop agree on who confirms** (20% autonomy and controls). I found no spend limits in the shop; a person presses "Confirm order", and an order stays open until its closing time. So: the agent prepares the cart for a delivery date, a person confirms, and the sign-off deadline is the closing time. Spend limits and the autonomous path stay ours, labelled as ours.
5. **V2 "per user pattern" has shop-native names** (20% precision): "Frequently purchased", "My Favourites", "Order templates", "Standard orders". P-agents that generate customer types should name the generated history with these words.
6. **V10 "same brand" has a shop-native field** (20% precision; 15% exceptions): the shop filters by "Manufacturer" and lists "Alternative products" per product. Our substitute ranking can state "same manufacturer" as a named reason.
7. **Compare by comparison price** (20% precision): the shop's second sort is price per litre or kilo. We already rank by price per requested unit (`src/tta/offers/combining.py:31,94`); we label it "comparison price".
8. **Path to production in one honest paragraph** (15% openness): section 1, line 5.
9. **The look** (15% credible path, and the peer review's first impression; nothing on the other criteria). Last in rank. Cut first.

## 6. Mapping table: the shop's word → our word today → proposed
| The shop's word (EN / FI) | Our word today | Proposed |
|---|---|---|
| Closing time / Sulkuaika | "Order by", "cut-off" | "Closing time" on pages and in audit sentences. Keep `closingTime` and `valid_until` as field names |
| Delivery date / Toimituspäivä | "Delivery date", "by Monday" | Keep. Show it first, in the header of every option, as the shop does |
| <N> pcs available in storage / varastossa | "Stock stated: <N>" | "<N> <unit> available in storage" |
| Deliverable <date> / Toimitettavissa | "not confirmed", "quantity not confirmed" | "Deliverable <date>, quantity not confirmed". Keep our explanation next to it |
| Not available / Ei saatavilla | "not available" | Keep |
| Alternative products | "Substitutes, ranked" | "Alternative products, ranked" as the section title |
| Substitute product / Korvaava tuote | "Substitute" (mark on a line) | Keep "Substitute" on the line: it is the shop's word in order messages |
| Compatible products / Yhteensopivat tuotteet | — | Not needed. Do not build |
| Standard order / Vakiotilaus | "Standing order" | "Standard order" on pages and in sentences. **DECISION D3** (the URL `/standing-orders` and API names stay) |
| Suspend order · Resume order · Unapproved lines | paused, pending approval | Use these three for the same states where we have them |
| Order template / Tilauspohja | "Your kitchen", "Menu" lists | Keep our page names; call a saved product list an "order template" |
| Frequently purchased · My Favourites | usual order, history | Use for generated customer history (V2) |
| Does not contain | "excluding allergens" | "Does not contain: <allergens>" as the label of the exclusion |
| Product attributes · Package labels | "labels", "claims" | "Package labels" for certificates, "Nutritional claims" for claims |
| Allergens / Allergeenit | "allergen statement" | Keep both; head the row "Allergens" |
| Comparison price | "price per requested unit" | "Comparison price (per litre or kilo)" |
| Price (VAT 0 %) · (incl. VAT) | "Price, before tax" | "(VAT 0 %)" in table heads |
| Deposits / Pantit | "deposits not included" | Keep |
| Main user / Pääkäyttäjä | "purchasing manager", approver | Keep our role; add "(the account's main user)" once on the approvals page |
| Confirm order / Vahvista tilaus | approve, place order | Button text "Confirm order" where a person commits |
| Cash & Carry · Delivery wholesale | — | Say once that we model Delivery wholesale |

## 7. Options and recommendation
**How close should our pages be to the shop?**
- A. Words only (W1, W2). 2 hours. No risk. Serves three criteria.
- B. Words plus structure (A, then W3 and W4): a header band with the delivery date, option lines laid out like the shop's product card. About 5 hours in all. A Valio judge recognises the layout. Risk: template changes break page tests late at night.
- C. A look-alike with their colours, fonts and logo. Rejected: it copies a brand, the fonts are licensed, and a clone of the webshop argues against the brief's "not about replacing today's e-commerce UI with a chatbot".
**Recommendation: A now, B only if the demo path is green by 20:00.** In B, use the palette values of 3.7 as a nod (teal headings, pale panels, one lime button) under our own name, with system fonts (a condensed system face for headings), no logo, no pictures.

- **DECISION D1 — category names.** The shop has names; our file has none. Recommended: do not copy the shop's names. Show our numbers with labels we derive from our own synthetic product names, marked as ours (this belongs to the agent handling V7). Alternative: ask the mentors whether the department names may be used (Q2).
- **DECISION D2 — how far to re-skin:** A or B above.
- **DECISION D3 — "Standing order" → "Standard order"** in visible text. It is Valio's word, but "standing order" is the common English term and is in our video script. Recommended: rename on pages, say "standard order (recurring)" once.
- **DECISION D4 — do we mention the real shop in the pitch?** Recommended: one sentence, "our words and page structure follow Valio Aimo's webshop; all data is the synthetic set".

## 8. Work items
| id | what | files | hours | who | criterion | depends on |
|---|---|---|---|---|---|---|
| W1 (minimum) | Vocabulary pass: section 6, visible text only | `src/tta/ui/templates/*.html`, `src/tta/audit/sentences.py`, `readers.py`, `standing_sentences.py`, tests that assert strings | 1.5 | biomedical | 20% precision, 15% openness | D3 |
| W2 (minimum) | Availability line in two forms plus "Closing time"; a passed closing time shows the next possible date | `_candidate.html`, `_result.html`, `order.html`, `src/tta/ui/view.py` | 1 | biomedical | 15% exceptions, 20% controls | — |
| W3 | Docs: one paragraph in `docs/ASSUMPTIONS.md` and `README.md`: what we took from the shop (words, structure), what we did not (data, calls), the path to production | docs | 0.5 | any | 15% openness | D4 |
| W4 | Option line as a card: tags, comparison price, availability left and closing time right; rows "Allergens", "Nutritional claims", "Package labels" | `_candidate.html`, `app.css` | 1.5 | computer-science | 15% openness, 20% precision | W1, W2, D2 |
| W5 | Header band: our name, "Delivery date" chip, request box where the shop has search; palette and type scale | `base.html`, `app.css` | 1.5 | computer-science | 15% openness | D2 |
| W6 | "Same manufacturer" as a named reason in substitute ranking text | owner of V10 | 0.5 | with V10 | 20% precision, 15% exceptions | V10 plan |

Minimum version, 2 hours: W1 plus the two availability wordings of W2 (text only, 0.5 hour). The "next possible date" half of W2 is the next 0.5 hour. Cut order: W5, W4, W6, W3. Total 6.5 hours if everything is done.

## 9. What changes in the demo
- Scenario 1's second option reads, for example, "Deliverable Mon 16 Nov, quantity not confirmed, needs sign-off" in place of "not confirmed". The first reads "<N> pcs available in storage".
- Every option shows "Closing time <day> <time>". The audit trail says "closing time passed" where it says "a cut-off passed" today.
- The substitutes section is titled "Alternative products, ranked".
- With B: a Valio judge sees a header with the delivery date and option cards in the order they know.
- No figure of the demo changes: W1–W5 change text and layout only. Not measured, because nothing was built in this round.

## 10. Risks and what not to do
- **Do not call the shop from our code, tests, agent or demo. Do not store its answers, product numbers, prices, pictures, texts or category names in the repository.** (`AIMO/CHALLENGE.md:52`.)
- Do not use the test login again for building. A human look for 10 minutes (section 11) is enough.
- Do not present a shop figure as a fact about our catalog, or the other way round.
- Do not "fix" synthetic data from the shop (Q2 and Q5 answers: "take the values as they are in the data").
- Do not copy the logo, the fonts or the photos. Colours and layout order are safe to echo.
- A renaming pass late at night breaks string tests: do W1 early and run the whole test suite once after it.
- "999+ pcs available in storage" is the shop's display for a large stock. Our rule stays as Valio confirmed it (B2: a huge number means unknown, the order goes to a human).

## 11. Ten-minute click-through for a teammate (look, change nothing)
1. Sign in. Read the top bar and the header: delivery date and cart are always visible.
2. Front page: the department pills with counts; one product card: tags, price lines, availability line, clock.
3. Click "Delivery date": the calendar, week numbers, the legend. Close it without picking a day.
4. PRODUCTS menu: My Favourites, Frequently purchased, Offers, New products.
5. Search the GTIN of our `464306` (`salesUnitGtin` in our product file). Open the product.
6. On the product page: breadcrumb, availability line, the three price lines, the certificate mark.
7. Scroll: "Alternative products" and "Compatible products"; "Allergens" and "Nutritional Claims" as separate rows; "Unit conversions".
8. Search "lactose free milk": open the filters "Does not contain" and "Product attributes"; look at the sort choices. Note how many results are not milk.
9. ORDERS → Order templates, then Order Management: read the status words and "closes <date> at <time>". Open nothing for editing.
10. Account menu → My information and My Organization: the roles. Then log out.
Do not press: the cart buttons, plus/minus, the star, "Add to Order Template", a calendar day, "Confirm order".

## 12. Questions
For the team:
- D1 to D4 above.
- B7's answer is still ambiguous and touches W4's "Nutritional claims" row: João to say what was meant.

For Valio, in the booth shape:
- **Q1 — who approves a standard order?** Context: your webshop's standard orders have "Unapproved lines" and an approve/reject step. What we did: we looked at the texts only; the test account has no standard order. What we got: we cannot see who approves, the customer's main user or Valio Aimo. Example: a kitchen adds 20 cartons of milk to its Monday standard order. The ask: who must approve that line, and by when? If nobody answers: in our model the buyer's approver signs off any change to a recurring order, and the change takes effect after a processing time we label as ours.
- **Q2 — may we show your department names?** Context: our product file has 349 category numbers without names; your webshop shows eight named departments. What we did: nothing, we copied none. Example: our category `10400` holds the lactose-free milk of our demo. The ask: may our demo label categories with your department names, or should we label them ourselves? If nobody answers: our own labels, derived from the product names of the synthetic file, marked as ours.
- **Q3 — is "Deliverable <date>" the same thing as Terminal 999999?** Context: your webshop shows a quantity for products in storage and "Deliverable <date>" for the others; the mock gives 999999 for Terminal products. What we did: we treat both as "quantity not confirmed", and such an order always goes to a person. The ask: is that the right reading? If nobody answers: we keep it (you confirmed B2 in person).
