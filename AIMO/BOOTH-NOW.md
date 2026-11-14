# At the Valio Aimo booth — questions in plain words (Saturday 14 Nov)

**How to use:** read the **Ask** line out loud. Show the example only if they ask "where?". Write their answer under the question.
**Demo:** https://joaocostared--trusted-trade-agents.us-east.modal.run
**Numbers:** *catalog* = all 17,546 products in the product file. *Recording* = the API answers we recorded on Sat 14 Nov 02:52. *Friday sample* = 1,000 random products we asked the API about on Fri 13 Nov 23:00.
Every example was checked on Sat 14 Nov against the product file, the recordings and the booth app in replay.
The product numbers at the end of each question are only for looking things up. The long versions, with shell commands, are in `AIMO/OPEN-QUESTIONS.md` and `AIMO/BOOTH-QUESTIONS.md` (search the ref).

---

## A. Questions

### If you only have two minutes, ask 1–5

**1. Which of your example scenarios should we build next?**
- **Context:** we built the core: the agent looks up products, gets an offer at fixed prices, then orders on its own within its limits or sends the order to a named person to approve. Every step is logged for the buyer and for Valio. We also built two of the six example scenarios in your brief: a hospital ward ordering allergen-safe food, and a substitute when the product asked for can't be supplied.
- **Example (demo):**
  - Scenario 2, allergy ward, asks: "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only". The agent picks Alpro No Sugars Soya drink 1L, 200 L for €402.00. That's within the ward's €500 limit, so it orders on its own.
  - Scenario 1, hotel kitchen, asks: "1,000 litres of lactose-free milk by Monday". Three Arla milks cover it for €2,580.64. That's above the hotel's €750 limit per order, so it goes to the purchasing manager.
- **Ask:** "Which would you most like to see next: the buyer setting what its agent may do alone, a weekly standing order that alerts a human when it changes, recipe-to-order, or Valio's own selling agent?"
- **If there's time:** "Do customers set their own limits and approvers today, or does Valio?" · "Can we make up a kitchen's standing order, or do you have real order patterns?" · "Nothing in the data marks a product as new or seasonal, and there are no recipes. Did we miss a field?"
- *Ref SCOPE-1*
- **Answer:** ________________________________________

**2. An oat drink labelled gluten-free whose allergen data says it contains gluten**
- **Context:** when the agent picks a substitute, we block it if it contains an allergen the original doesn't. To decide what a product contains, we trust the allergen declaration, not the product name or a "gluten-free" label.
- **Example:** Valio lists three substitutes for Oddlygood Barista oat drink 1 l. What each allergen declaration says:
  - Original, Oddlygood Barista oat drink 1 l (named "gluten free"): contains oats.
  - Substitute, Oddlygood Barista oat drink 1 L Delight (named "gluten free"): contains oats. It passes the allergen check.
  - Substitute, Oddlygood Barista oat drink **0.5 l** (named "gluten free", with the "free from gluten" claim): contains oats **and contains cereals containing gluten**. Blocked.
  - Substitute, Oatly iKaffe oat drink 1L: contains oats and contains cereals containing gluten. Blocked.
  - Our demo (Scenario 3, substitutes list) says the 0.5 l pack "can never be ordered as a substitute".
- **Ask:** "The 0.5 l Oddlygood Barista is labelled gluten-free, but its allergen data says it contains gluten, and the 1 l packs don't say that. Which one is right?"
- **Why we ask:** it's in our demo. If a Valio judge knows the drink is gluten-free, our rejection looks like a bug.
- *Ref T03-1 · products 473609 (1 l), 471690 (Delight), 471881 (0.5 l), 464320 (Oatly)*
- **Answer:** take thw values as they are in the data.

**3. The order deadline has passed, but the delivery date is still shown**
- **Context:** for each product the API gives a delivery date and an order deadline ("order by X to receive it on that date"). Your spec says exactly that. We read it literally: once the deadline has passed, the agent can't promise that date, so it drops the product and says why.
- **Example (recording, made Saturday 02:52):**
  - Valio skimmed milk 1 l lactose free: the API says **order by Thursday 12 Nov 15:00**, delivery Monday 16 Nov. Thursday had already passed.
  - Valio Eila semi-skimmed milk drink 1 l lactose free: order by Sunday 15 Nov 17:00, delivery Monday 16 Nov. Still open.
  - Our agent drops the skimmed milk. In our main demo (1,000 L of lactose-free milk), 17 milks are dropped for this reason.
- **Ask:** "This milk says 'order by Thursday' and 'delivery Monday', and today is Saturday. Can we still get it on Monday, or is it too late?"
- **If there's time:** "The skimmed milk still said Thursday at 02:52 and again at 08:12 on Saturday. Will the deadlines update, or will every product be past its deadline by Sunday evening?"
- *Ref Q1 · products 464119, 464306 · field closingTime*
- **Answer:** ________________________________________

**4. What limits do real customers set?**
- **Context:** the mock has no customer accounts. Your spec says the customer number doesn't change the answer. So we made up the limits that decide what the agent may order on its own, and the page labels them as illustrative.
- **Example:**
  - Hotel kitchen: the agent orders alone up to €750 per order and €3,000 per day, if at least 90% of the quantity is covered. Substitutes from the same category are allowed. Anything else goes to the purchasing manager.
  - Allergy ward: up to €500 per order and €1,500 per day, 100% covered, no milk, no gluten, and only offers where everything is confirmed. Every substitute goes to a person.
- **Ask:** "What limits do real customers put on ordering today: a euro cap per order or per day, a list of approved products, who approves? One real example is enough."
- *Ref Q7*
- **Answer:** ________________________________________

**5. What does an accepted order lock in?**
- **Context:** there is no order endpoint, so in our demo "ordered" means recorded in our own order book. We need to know what a real order fixes.
- **Example:** what the API says about Valio Eila semi-skimmed milk drink 1 l lactose free (recording):
  - Price: €1.01, valid 1 Sep – 31 Dec 2026. We mark it **confirmed**.
  - Delivery: Monday 16 Nov if ordered by Sunday 15 Nov 17:00. We mark it **confirmed**, as long as the order is placed before the deadline.
  - Stock: 9,999,999,999, which you told us means unknown. We mark it **not confirmed**, so a person must approve.
  - In our demo, 1,000 L of it is €1,010.00, shown as "quantity not confirmed".
- **Ask:** "When Valio accepts an order today, what's fixed at that moment: the price, the quantity, the delivery date?"
- *Ref Q4 · product 464306*
- **Answer:** ________________________________________

### Reading your data

**6. Product file or API: which one should an agent trust?**
- **Context:** we get two sources. The product file says what a product *is*: names, allergens, ingredients, pack sizes, substitutes. The API says what it *costs* and whether it can arrive. Sometimes they disagree.
- **Example:** 12 × Risifrutti blueberry rice snack, 175 g cups (recording).
  - The product file says it's sold **by the case of 12 cups**.
  - The API says it's sold **by the single cup**: price €1.00, 24 in stock.
  - The price per kilo (€5.71/kg × 175 g = €1.00) shows the €1.00 is for one cup. With the file's unit, it would read as a whole case for €1.00, 12 times too cheap. And "24 in stock" could mean 24 cups or 24 cases (288 cups).
  - Across the recording, the file and the API give different units on 15 of 624 products.
- **Ask:** "In production, would an agent get product data through an API too, or from a file like this? When they disagree, which wins? How often does the file change? And may we show recorded API answers in the demo when the mock is down, clearly labelled as recorded?"
- **What we do now:** price, quantity and sales unit come from the API. Everything else comes from the file. Each offer says whether its data is live or recorded.
- *Ref DATA-1 · product 461439*
- **Answer:** ________________________________________

**7. Follow-up to 6: is the price per piece or per case?**
- **Context:** when the file and the API give different sales units, the price and the stock could refer to either one. We follow the API.
- **Example 1:** Valio A+ greek natural yoghurt, 1 kg tubs, lactose free (recording).
  - The product file says it's sold **by the case of 5 tubs**.
  - The API says it's sold **by the single tub**: price €2.92, 100 in stock.
  - The price per kilo (€2.92/kg × 1 kg = €2.92) shows the €2.92 is for one tub. With the file's unit, it would read as a case of 5 for €2.92, 5 times too cheap. And "100 in stock" could mean 100 tubs or 100 cases (500 tubs).
- **Example 2, the other way round:** Arla low-fat milk, 5 dl bottles (recording).
  - The product file says it's sold **by the single bottle**.
  - The API says it's sold **by the case of 6 bottles**: price €6.22. Stock shows 999,999, which means unknown.
  - The price per litre (€6.22 ÷ 3 L = €2.07/L, the figure the API gives) shows the €6.22 is for a case of six. With the file's unit, it would read as one bottle for €6.22, 6 times too expensive.
- **Ask:** "When the two differ, do the price and the stock always follow the API's unit?"
- **Why we ask:** reading the wrong unit puts the price and the quantity off by 5, 6 or 12 times in these examples.
- *Ref Q10 · products 464615, 465244*
- **Answer:** ________________________________________

**8. The allergen declaration says "free from nuts", the ingredient list says almond**
- **Context:** each product has an allergen declaration and a separate ingredient list. Sometimes they contradict each other.
- **Example:** Alpro Barista Almond drink 1L.
  - Allergen declaration: **free from tree nuts**.
  - Ingredient list: "Water, **ALMOND** (2.5%), Sugar, … MAY CONTAIN REMAINS FROM NUTS (NOT PEANUTS)."
- **More of the same** (in the catalog: 18 products for milk or gluten, 7 for tree nuts):
  - Jymy Organic liquorice ice cream: declares **free from milk**. Ingredients start "WHOLE MILK, CREAM, sugar, skimmed MILK POWDER".
  - Jalostaja liver paste: declares **free from milk**. Ingredients include "MILK powder".
  - Pipers crisps, cider vinegar & sea salt: declares **free from milk**. Ingredients include "LACTOSE (MILK)".
  - Schlagfix spray cream: declares **free from milk**. Ingredients end "May contain traces of milk".
  - Fazer Gluten-Free Runeberg pastry: declares **free from tree nuts**. Ingredients include "flavour (bitter almond)".
- **Ask:** "When the allergen declaration and the ingredient list disagree, which one should an agent trust?"
- **What we do now:** neither wins. The product goes to a dietitian, who sees both quoted.
- *Ref ALMOND-1 · products 465793, 465038, 461634, 465713, 466989, 470094*
- **Answer:** ________________________________________

**9. "Free from gluten" but "contains wheat"**
- **Context:** allergens come in families. "Cereals containing gluten" includes wheat and oats, and "tree nuts" includes almonds. Some products say a whole family is absent while declaring one of its members.
- **Example:**
  - Fria fibre-rich loaf, 8 × 500 g, named "glutenfree". Its declaration says **free from cereals containing gluten** and also **contains wheat**.
  - Toblerone, 20 × 100 g. Its declaration says **free from tree nuts** and also **contains almonds**.
  - 176 products in the catalog have a contradiction like this.
- **Ask:** "We read the gluten-free loaf as using gluten-free wheat starch, and Toblerone as a data error. Is that right?"
- **What we do now:** the less safe statement counts. A buyer who excludes gluten never gets the loaf.
- *Ref T03-2 · products 460124, 461333*
- **Answer:** ________________________________________

**10. Products with no allergen data at all**
- **Context:** many products have no allergen declaration: neither "contains" nor "free from".
- **Example:**
  - Peltolan blue cheese 1.6 kg: the allergen declaration is empty. Cheese contains milk, but the data doesn't say so.
  - HK cooked ham 6 × 300 g: the allergen declaration is empty, yet it carries "free from gluten" and "free from lactose" claims.
  - In the catalog, 8,110 of 17,546 products (46%) are like this. Among food products only, it's 4,149 of 13,577 (31%).
- **Ask:** "When there's no allergen data, does it just mean nothing was declared, so an agent must treat it as unknown rather than safe?"
- **What we do now:** we treat it as unknown. A strict buyer's order goes to a dietitian. A buyer who asks for confirmed data only doesn't get the product.
- *Ref Q5 · products 463168, 463427*
- **Answer:** ________________________________________

**11. "No allergens to declare", "undeclared" and "may contain"**
- **Context:** your documentation lists only two allergen values, "contains" and "free from". The data also uses three others. We read them with their meanings in the GS1 standard ("undeclared" = not intentionally added).
- **Example:**
  - Marli Natur apple juice 1 L: its only allergen value is **"no allergens to declare"**.
  - Turun Sinappia mild mustard 6 kg: **contains mustard**, and each of the other 13 allergens is marked **"undeclared"**.
  - Aino raspberry chocolate ice cream: contains milk, and **may contain tree nuts**.
  - In the catalog: "may contain" on 2,685 products, "undeclared" on 33, "no allergens to declare" on 121.
- **Ask:** "Do these values mean what the GS1 standard says? Could an agent treat the apple juice as safe without a dietitian checking it?"
- **If there's time:** "For an allergy diet, who decides whether 'may contain' is acceptable: Valio or the customer?"
- **What we do now:** for a strict buyer like the ward, all three go to a dietitian.
- *Ref Q2 · products 460622, 460556, 465657 · code X99*
- **Answer:** ________________________________________

**13. How many litres or kilos are in one case?**
- **Context:** no field says how much one sales unit holds. We work it out as price ÷ price per litre (or per kilo), and check it against the product file.
- **Example:**
  - Valio skimmed milk 10 l novobox (recording): €8.75 at €0.88/L. €8.75 ÷ €0.88 = 9.94 L. The file says 10 L, so the gap is rounding.
  - Filos feta cubes in brine, named "2kg" (Friday sample): €32.33 at €16.17/kg. €32.33 ÷ €16.17 = **2.0 kg**, but the file's net weight is **3.39 kg**. The price per kilo uses 2 kg. Our guess is that 2 kg is the cheese without the brine.
- **Ask:** "Is the price per litre or per kilo the price divided by what one sales unit holds, using the drained weight when there is one?"
- *Ref T02-2 · products 460396, 466382 · field comparisonPrice*
- **Answer:** ________________________________________

**14. A listed substitute sold in a different unit**
- **Context:** the product file lists substitutes, and sometimes the substitute is sold in a different unit from the original.
- **Example (recording):**
  - Original: Oddlygood Barista oat drink 1 l, sold by the **single carton**, €1.37 (€1.37/L).
  - Valio's listed substitute: Oddlygood Barista oat drink 1 L Delight, sold by the **case of 10 cartons**, €15.55 (€1.56/L).
  - For 100 cartons of the original, we order 10 cases of the substitute. Swapping 1 for 1 would order 100 cases (1,000 L), ten times too much.
  - In the catalog, 75 of Valio's 250 listed pairs use different units.
- **Ask:** "When a listed substitute comes in a different unit, should the agent convert by volume like we do, so 100 cartons become 10 cases?"
- *Ref T07-5 · products 473609, 471690*
- **Answer:** yes the goal is to satisfy the prompt

**15. Bottle deposits**
- **Example:** 12 × Bundaberg ginger beer 0%, 37.5 cl bottles.
  - The product file says each case carries a deposit: deposit type "1", 12 of them (one per bottle).
  - The price API says €22.09 for the case (Friday sample).
  - We asked the price API for all 7 deposit types. Every answer was an error.
  - So we can't tell whether the €22.09 includes the 12 deposits. In the catalog, 506 products carry a deposit.
- **Ask:** "Is the deposit already in the price, or charged on top? If on top, how much per deposit type?"
- **What we do now:** totals leave deposits out and say so. Any order with a deposit goes to finance.
- *Ref Q8 · product 476204*
- **Answer:** ________________________________________

**16. Products sold by weight**
- **Example:** Well Beef chuck roll (recording).
  - Sold by the kilo in 3 kg steps, at €16.88/kg, with 109 kg in stock.
  - The file marks it "variable weight": each piece weighs a bit differently.
  - Ordering 30 kg = €506.40. But the pieces delivered could weigh, say, 29.4 kg or 30.8 kg.
- **Ask:** "If an agent orders 30 kg of a product like this, is the invoice for exactly 30 kg, or for what's actually delivered?"
- **What we do now:** the total is shown as a maximum, and the order goes to the purchasing manager.
- *Ref Q9 · product 466988*
- **Answer:** what is actually delivered. like in a normal store

**17. Category numbers**
- **Context:** every product has a 5-digit category number. When Valio lists no substitute, we look for one in the same category: all 5 digits first, then the first 4, then the first 3. That only works if the digits are levels.
- **Example:** three of Valio's own listed substitutes:
  - Tomato NL/BE/ES → Tomato Finland: 17401 → 17401 (all 5 digits match).
  - Myllyn Paras strawberry-rhubarb pie → Myllyn Paras berry-mix pie: 41765 → 41763 (first 4 match).
  - White cabbage Finland → SallaCarte shredded cabbage 1 kg: 17404 → 17443 (first 3 match).
  - Of the 250 listed pairs, 230 share all 5 digits.
- **Ask:** "Is the category number a hierarchy, and which digits are the levels? Can we have the category names?"
- *Ref Q11*
- **Answer:** ________________________________________

**18. Delivery reliability**
- **Context:** you give a delivery-reliability number for 4,425 of the 17,546 products (25%).
- **Example:**
  - Valio Eila semi-skimmed milk drink 1 l lactose free: **1.0**.
  - Atria beef tenderloin: **0.332**. It also shows 0 in stock in the recording.
  - Valio Eila milk drink 10 l novobox: **no value**.
- **Ask:** "What does this number measure, for example the share of orders delivered on time and in full? Does no value mean there's no delivery history?"
- **What we do now:** it's shown on the product but doesn't change the ranking yet.
- *Ref Q12 · products 464306, 473463, 463038*
- **Answer:** ________________________________________

### Offers

**19. How should an offer be shown to a buyer's agent?**
- **Context:** today an offer gives up to three ready-made whole baskets, ranked: everything confirmed first, then a basket whose stock isn't confirmed (always to a person), and a substitute when the product asked for can't be supplied. Each line gets five marks: price, quantity, delivery date, allergens, origin. Each one is confirmed, not confirmed, or ruled out.
- **Example:** the hotel kitchen asks for 100 L of lactose-free milk and 10 L of cream by Monday (recording).
  - Basket 1, everything confirmed: Arla lactose-free semi-skimmed milk (100 L) + Arla Pro cooking cream 10% (10 L), **€281.10**. The agent orders it alone.
  - Basket 2, stock not confirmed: Valio Eila lactose-free milk (100 L) + Valio cooking cream 15% (10 L), **€127.30**. It goes to a person. On the Valio Eila line: price ✓, quantity ? ("Valio reports 9,999,999,999, which means the stock is not known"), delivery ✓, allergens ✓, origin ✓.
  - What the agent can't do: take the confirmed Arla milk with the cheaper Valio cream. It must pick a whole basket.
- **Ask:** "Should an offer be a few ranked whole baskets like this, or good-better-best for each product so the agent can mix? How many options are useful? Are the five marks per line useful, or too much?"
- *Ref OFFER-1*
- **Answer:** ________________________________________

**20. Stock that covers only part of an order**
- **Context:** when stock covers only part of a line, the API says nothing about when the rest could come.
- **Example:** the hotel kitchen asks for 1,500 L of lactose-free milk by Monday (recording).
  - Confirmed stock: Arla semi-skimmed milk 384 L + Arla fat-free milk 51 L + Arla Café milk 698 L = **1,133 L** (75.5%). 367 L are missing.
  - The agent offers the 1,133 L for €2,933.09 and sends it to a person, because the hotel requires 90%.
  - It also offers 1,500 L of Valio Eila for €1,515.00, whose stock is unknown, also for a person.
- **Ask:** "When stock covers only part of an order line, what happens today: a partial delivery, a substitute, or the line is dropped?"
- *Ref Q6 · products 469363, 462775, 463380*
- **Answer:** ________________________________________

### How the mock and the judging work

**21. Is our call volume OK?**
- **Example:**
  - Each offer makes 2 calls to your API, one for price and one for availability, however many products it covers. The recording asked about 769 products in 2 calls.
  - Our deployed link lets at most 6 offers a minute reach your API (2 per visitor), and 120 calls in total. After that it answers from the recording, labelled as recorded.
  - On Friday, 34 requests in 5 minutes got no rate-limit error.
- **Ask:** "Is that fine during judging?"
- *Ref Q13*
- **Answer:** ________________________________________

**22. Do agents have to identify themselves?**
- **Example:** Saturday 14 Nov 02:40, same API key, the ping call:
  - with Python's default User-Agent: **403, blocked** (the API sits behind Cloudflare);
  - a minute later with a named User-Agent, "tta-preflight/1.0": **200, OK**.
  - Since then our gateway always sends "tta-gateway/0.1" and gets 200.
- **Ask:** "Is that expected? Should every agent send a named User-Agent?"
- *Ref T01-1*
- **Answer:** ________________________________________

**23. How and when do you judge?**
- **Context:** the deployed link reads your live mock. If the mock fails, it answers from the recording and says so.
- **Ask:** "Do you judge at our table, from the video, or on the deployed link? Will the mock API stay up, unchanged, until then?"
- **Answer:** ________________________________________

**24. Must the exceptions run live?**
- **Example:**
  - Live in the three demo scenarios: deadlines that have passed, unknown stock, products that can't be delivered, allergen exclusions, substitutes.
  - Not on the page, only as typed requests covered by tests: partial stock (question 20), products sold by weight (question 16), and an agent trying to approve its own order.
- **Ask:** "Do exception cases have to run live in the demo, or does a documented, tested rule count?"
- **Answer:** ________________________________________

**25. Webshop test accounts**
- **Example:** the challenge text says "Webshop test accounts to be shared separately." We haven't received any.
- **Ask:** "Are the webshop test accounts available?"
- **Answer:** ________________________________________

**26. Your data in our public repository**
- **Example:** the submission must be a public repository under the MIT licence. Right now it holds 4 of your data files and 18 recorded API answers. The README says they're yours and not under the MIT licence.
- **Ask:** "May your data files and the recorded API answers stay in the repository, or should we take them out?"
- **Answer:** ________________________________________

### Allergen data from manufacturers' websites

**27. An oat drink with no milk statement**
- **Example:** Elovena barista oat drink 1 l.
  - Your file: contains oats. **Nothing about milk**, neither "contains" nor "free from".
  - Raisio's own food-service page (raisiofoodsolutions.fi) says "Gluteeniton, Laktoositon, **Maidoton**, Kananmunaton": gluten-free, lactose-free, **milk-free**, egg-free.
  - For a buyer who excludes milk under a strict rule, our agent sends it to a dietitian instead of ordering it.
- **Ask:** "Is the milk statement missing only in the hackathon file, or at the source too?"
- **What we do now:** it stays "not stated". The dietitian sees the maker's page labelled "not Valio data".
- *Ref S2-1 · product 469512*
- **Answer:** ________________________________________

**28. Almond drink or soya drink?**
- **Example:** one Oddlygood product.
  - English name: "Oddlygood® **almond** drink 1 l no sugars UHT".
  - Finnish name: "Oddlygood® **soijajuoma** 1 l no sugars UHT" (soya drink). Swedish name: "Oddlygood® **sojadryck** …" (soya drink).
  - Allergen declaration: **contains soya**.
  - A buyer asking in English for almond drink would get this product, which declares soya.
- **Ask:** "Is this an almond drink or a soya drink?"
- *Ref S2-2 · product 474864*
- **Answer:** ________________________________________

---

## B. Decisions we made ourselves — confirm or correct

1. **When the agent orders alone:** only if price, quantity and allergens are all confirmed, the delivery date is met, the full quantity is covered, the spend is within the buyer's limits, and any substitute is one the buyer allows. Everything else goes to a named person. *"Is that the right line?"*
   - **Answer:** ________________________________________
2. **A huge stock number means unknown**, so the order always goes to a human. Example: Valio Eila lactose-free milk shows 9,999,999,999. *(You told us this on 14 Nov. Just confirm it still holds.)*
   - **Answer:** yes
3. **A deadline exactly at the current time counts as passed.**
   - **Answer:** this is all static data so we can chose the date
4. **"Lactose-free" is not an allergen statement.** Example: Valio Eila lactose-free milk declares "contains milk", and we keep it out for a buyer who excludes milk.
   - **Answer:** ________________________________________
5. **"Milk" leaves out sour milk, coffee drinks and soy yoghurt, but includes coffee milk.** Arla Café milk 1 L lactose free supplies 565 of the 1,000 litres in our demo. *"Would a buyer asking for milk accept coffee milk?"*
   - **Answer:** no be explicit
6. **A substitute can never add an allergen the original doesn't have,** or turn "may contain" into "contains". This holds for every buyer. Example: the 0.5 l oat drink in question 2.
   - **Answer:** yes
7. **A substitute that loses a dietary claim always goes to a human** (lactose-free → regular, gluten-free → regular). We count as dietary: lactose-free, low-lactose, gluten-free, wheat-free, egg-free, soy-free, vegan, vegetarian. Other claims (no preservatives, no added sugar …) are only mentioned. *"Right list?"*
   - **Answer:** yes and only in the last case
8. **For a buyer who wants no gluten:** oats go to a dietitian, and products with gluten-free wheat starch are rejected. Example: the Fria loaf in question 9 is rejected.
   - **Answer:** ________________________________________
9. **For a strict buyer, a product marked only "no allergens to declare" goes to a dietitian.** Example: Marli Natur apple juice in question 11.
   - **Answer:** ________________________________________
10. **Single-serve packs (5 cl or 50 g or less) are left out of bulk orders.** Example: Arla portion milk, 100 × 2 cl, is not used for "1,000 litres of milk".
    - **Answer:** ________________________________________
11. **"By Monday" means the first Monday after today.**
    - **Answer:** yes
12. **Right before ordering, the agent checks again.** A price change, a new deadline or a later delivery date cancels the offer and builds a new one. Stock that moved but still covers the order doesn't.
    - **Answer:** ________________________________________
13. **What Valio sees in the log:** what was asked, what was offered and ordered, the figures each order relied on, which agent acted, and whether it acted alone or with a human. Valio doesn't see the buyer's limits, allergen exclusions, approver names or notes. *"Is that what you'd want to see?"*
    - **Answer:** all the steps and decisions
14. **"Ordered" means recorded in our order book. It commits nobody,** because the mock has no order endpoint. *"Is that how you want it described?"*
    - **Answer:** ________________________________________
