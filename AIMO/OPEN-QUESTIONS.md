# Open questions for Valio Aimo, with examples

**How to use this at the booth**
1. Before you walk over, start the app and open the data shell (Setup, below), then press **Start again** on the page.
2. Read the **Ask** line out as written. Show the example only when the mentor asks "where?". Write the answer under the question.
3. The mock's behaviour is the scenario we are meant to handle, not a fault: we are checking how we read it, not reporting bugs. Do not ask about an order endpoint or about very large stock values. Both are settled.

**The two-minute cut:** ask the first five, in order: 0 `SCOPE-1` · 1 `T03-1` · 2 `Q1` · 3 `Q7` · 4 `Q4` (group A).

**Where the numbers come from.** *Catalog* means all 17,546 products in the product file. *Tonight* means the capture of Sat 14 Nov 02:52, Valio server time: 769 products (categories 104xx and 18720, the scenario products and their listed substitutes). *Friday sample* means 1,000 random products, captured Fri 13 Nov 23:00. *Friday extras* means 37 ids captured Fri 23:03. A figure from a capture or the sample is not a catalog fact. The id before each title finds the full write-up in `AIMO/BOOTH-QUESTIONS.md`.

---

## Setup (once, 10 seconds)

**App** (pages at http://127.0.0.1:8000/):
```sh
cd /Users/joaocosta/Pessoal/junction && GEMINI_API_KEY= TTA_ENV=demo TTA_MODE=replay TTA_DB_PATH=/tmp/tta-booth.sqlite3 .venv/bin/python -m uvicorn --factory tta.api:create_app
```
Replay mode answers from tonight's capture with the clock pinned to Sat 02:52, so the outcomes below are certain. Each browser keeps its own order book. Run scenario 3 last: its €174 order counts in the hotel's day and adds finance to scenario 1. **Start again** empties the book. REST calls need `-H "Authorization: Bearer demo-agent-hotel-kitchen"`.

**Data shell.** Open a second terminal. Every "Shell:" line below is typed at its `>>>` prompt.
```sh
cd /Users/joaocosta/Pessoal/junction && python3 -I -i -c "
import json, csv
L = lambda path: json.load(open(path))
P = {p['id']: p for p in L('valio_aimo_junction26_product_data.json')}
def cap(name, n=1):
    d = 'fixtures/valio/' + name + '/'
    a = {x['productId']: x for k in range(1, n + 1) for x in L(d + 'availability-%d.json' % k)['products']}
    r = {x['productId']: x for k in range(1, n + 1) for x in L(d + 'price-%d.json' % k)['products']}
    return a, r
A, R = cap('2026-11-14-demo')
F, FR = cap('2026-11-13-sample', 4)
X, XR = cap('2026-11-13-extras')
REL = {r['productId']: r['deliveryReliability'] for r in csv.DictReader(open('valio_aimo_junction26_delivery_reliability.csv'))}
def name(i): return next(n['value'] for n in P[i]['synkkaData']['names'] if n['language'] == 'en')
def g(i, group): return [(v['id'], v.get('unit')) for c in P[i]['synkkaData']['classifications'] if c['name'] == group for v in c['values']]
def f(i):
    p = P[i]
    return dict(unit=p['salesUnit'], units={u['unitId']: u['sizeInBaseUnits'] for u in p.get('units', [])}, lot=p['allowedLotSize'], category=p['category'], variable_weight=p['synkkaData'].get('variableUnit'), deposits=p.get('deposits'))
def av(i, s=None):
    a = (s or A)[i]
    line = (a.get('scheduleLines') or [{}])[0]
    return dict(model=a.get('logisticModel'), cutoff=a.get('closingTime'), amount=line.get('availableAmount'), date=line.get('availableDate'), unit=line.get('salesUnit'))
def pr(i, s=None):
    r = (s or R)[i]
    c, k = r.get('catalogPrice', {}), r.get('comparisonPrice', {})
    return dict(price=c.get('value'), valid=c.get('validFrom', '')[:10] + ' to ' + c.get('validTo', '')[:10], per=(k.get('value'), r.get('comparisonUnit')), error=r.get('error'))
print('Ready. Tonight (Sat 14 Nov 02:52): A, R. Friday sample (23:00): F, FR. Friday extras (23:03): X, XR.')
"
```
`name(id)` gives the English name. `g(id, 'allergen')` gives a classification group. `f(id)` gives the file's units. `av(id)` gives tonight's availability and `pr(id)` tonight's price; pass `F`/`FR` or `X`/`XR` to read Friday's captures instead.

---

## A. Ask these first

### 0 · `SCOPE-1` · Which of your example scenarios would you most like to see?
- **Ask:** "Of the scenarios in your brief, which would you most like to see an agent do on top of this: the buyer setting its agent's limits, standing-order drift, recipe to order, or your own selling agent?"
- **Show:** the live demo, https://joaocostared--trusted-trade-agents.us-east.modal.run. Click **Scenario 2 · allergy ward**: the ward's agent orders 200 L of soya drink alone, €402.00. Then click **Scenario 1 · hotel kitchen**: €2,580.64 is above the hotel's €750 limit, so the order goes to the purchasing manager. The link reads the live mock. If it is slow, or a number differs, make the same two clicks on the laptop app, which shows the recorded numbers.
- **If there is time:** (1) "Do customers set their own ordering limits and approvers today, or does Valio Aimo set them in the account?" (2) "The mock has no order history: may we define a kitchen's standing order ourselves, or do you have example order patterns?" (3) "The product file has no field for new or seasonal products, and no recipes: is there one we missed, or should we bring our own small list?" (Catalog: none of the 75 field names contains new, season, launch, campaign, recipe, menu or promo.)
- **Why it matters:** the answer decides what we build in the last hours. Options (a), the buyer's limits, and (b), standing-order drift, both score on the 20% autonomy-and-controls criterion.
- **Built so far:** the core (lookup, an offer at fixed prices, an order placed within the agent's authority or sent to a named human, and an audit trail for both buyer and Valio), plus two of the six scenarios: allergen-safe substitution for a hospital ward (scenario 2) and a substitute when the product asked for cannot be supplied (scenario 3). The buyer limits live in two profile files, and no page can edit them yet. If Valio does not answer: (a) and (b) first, (c) if time allows, (d) last.

### 1 · `T03-1` · A "gluten free" oat drink that declares gluten
- **Ask:** "The 0.5 l Oddlygood Barista is named gluten free and carries the gluten-free claim, yet it declares cereals containing gluten, and the 1 l packs do not. Is that expected, or did we get something wrong?"
- **Show:** in the shell, `[(i, name(i), g(i, 'allergen')) for i in ('473609', '471690', '471881')]` returns:
  - `473609` (1 l): `GO` (oats) CONTAINS
  - `471690` (1 L Delight): `GO` CONTAINS
  - `471881` (0,5 l): **`AW` CONTAINS**, `GO` CONTAINS

  Then `g('471881', 'nutritionalClaim')` returns `FREE_FROM_GLUTEN`, `FREE_FROM_PRESERVATIVES`, `VEGAN`. On the page, open Scenario 3 → "Substitutes, ranked" → no. 13, "✕ Fails the allergen rule … cereals containing gluten (AW, contains). It can never be ordered as a substitute." (Catalog: `471881` is one of the three substitutes Valio lists for `473609`. Tonight it also has no schedule line.)
- **Why it matters:** this is demo scenario 3 (15% robustness). A Valio judge may say the product is gluten free, and our page says it can never be ordered.
- **Built while waiting:** the declaration counts, never the name or the claim. A substitute may not declare an allergen the original does not (`src/tta/allergens/substitution.py`), so neither `471881` nor `464320` (Oatly iKaffe) can ever be ordered in place of `473609`, for any buyer.

### 2 · `Q1` · Order cut-offs that have already passed
- **Ask:** "We read closingTime literally: once it has passed, the product cannot arrive on availableDate, so our agent leaves it out and says why. Is that expected, or did we get something wrong?"
- **If there is time:** "Do the cut-offs move forward over the weekend, or will every product be past its cut-off after Sunday 17:00?" (`464119` still showed Thursday 15:00 with delivery on Monday both tonight and in the live check at 08:12.)
- **Show:** in the shell, `av('464119'), av('464306')`:
  - `464119`, Valio skimmed milk 1 l lactose free: Terminal, cut-off **2026-11-12 15:00**, delivery 2026-11-16
  - `464306`, Valio Eila semi skimmed milk drink 1 l lactose free: Stock, cut-off 2026-11-15 17:00, delivery 2026-11-16

  Both are from tonight's capture, with `timeNow` Sat 14 Nov 02:52. On the page, Scenario 1 reads "Excluded: 19 products … 17 × Cut-off passed".
- **Why it matters:** this rule removes 17 of the 30 lactose-free milks from scenario 1 tonight. In the Friday sample, 425 of 1,000 products (42.5%) already had a passed cut-off.
- **Built while waiting:** a product whose cut-off has passed is excluded, with the time named ("Order cut-off passed on Thursday 12 Nov at 15:00, so delivery on Monday 16 Nov cannot be promised"). Replay mode keeps the demo working if every cut-off has passed by judging time.

### 3 · `Q7` · What limits do real customers set?
- **Ask:** "The mock has no customer model, so we wrote our own limits. What do real customers put on ordering: a euro cap per order, a cap per day, an approved product list, approver roles? One example is enough."
- **Show:** the page `/`, box "Who is asking". Hotel kitchen: €750 per order, €3,000 per day, at least 90% of the quantity covered. Allergy ward: €500 per order, €1,500 per day, 100% covered, excludes `AM` and `AW` (strict), confirmed data only. Each is labelled illustrative. The spec says: "In this challenge, however, customer number does not affect response so you can pass in whatever."
- **Why it matters:** 20% autonomy and controls. Every number in our two buyer profiles is ours, and one real example would make them credible.
- **Built while waiting:** two buyer profiles, `src/tta/policy/profiles/hotel-kitchen.yaml` and `allergy-ward.yaml`. They set spend per order and per day, minimum fill, allergen exclusions, substitution scope, variable weight, deposits and approver roles, on top of fixed rules that no profile can switch off.

### 4 · `Q4` · What an accepted order commits to
- **Ask:** "When Valio Aimo accepts an order today, what is committed at that moment: the price, the quantity, the delivery date?"
- **Show:** in the shell, `pr('464306'), av('464306')`: price €1.01, valid 2026-09-01 to 2026-12-31; delivery 2026-11-16 if ordered by 2026-11-15 17:00; amount 9999999999, which means not known. On the page, Scenario 1 → option 2 reads "✓ Price: confirmed ? Quantity: not confirmed ✓ Delivery date: confirmed".
- **Why it matters:** it decides how we word "ordered" in the pitch, and what an agent may promise (core requirement 2).
- **Built while waiting:** the price is committed for its validity window. The date is committed only if the order is placed before the cut-off. The quantity is committed only when the stock figure is an ordinary number (`src/tta/availability/claims.py`). An order is a record in our order book, and the page says "It commits nobody."

---

## B. How to read the data

### 5 · `Q2` · Allergen values that are not in the schema
- **Ask:** "We read X99 and UNDECLARED with their GS1 meanings, 'no declarable allergens' and 'not intentionally included'. Is that how your data uses them, or did we get it wrong?"
- **If there is time:** "For an allergy diet, who decides whether 'may contain' is acceptable: you, or the customer's own policy?"
- **Show:** in the shell, `[(i, name(i), g(i, 'allergen')) for i in ('465657', '460556', '460622')]`:
  - `465657`, Aino raspberry chocolate ice cream: `AM` CONTAINS, `AN` **MAY_CONTAIN**
  - `460556`, Turun Sinappia mild mustard 6 kg: `BM` CONTAINS and 13 other codes **UNDECLARED**
  - `460622`, Marli Natur apple juice 1 L: only **`X99` CONTAINS**

  Catalog counts: MAY_CONTAIN on 2,685 products and UNDECLARED on 33. `X99` appears on 121 products in `allergen` (on 120 of them as the only code) and on 74 in `nonAllergen`. The schema documents only CONTAINS and FREE_FROM.
- **Why it matters:** scenario 2 and the trust protocol. It decides whether an agent may take `X99` as safe without a dietitian.
- **Built while waiting:** we use the GS1 meanings. Under STRICT, `X99`, UNDECLARED and no statement all go to a dietitian. Under DECLARED_ONLY they pass, marked unverified. MAY_CONTAIN always goes to a dietitian (`src/tta/allergens/exclusion.py`).

### 6 · `T03-2` · An allergen family stated "free from" while one of its members is declared
- **Ask:** "Some products state 'free from gluten cereals' and 'contains wheat', or 'free from tree nuts' and 'contains almonds'. We read the first as gluten-free wheat starch and the second as a data error. Is that expected, or did we get something wrong?"
- **Show:** in the shell, `[(i, name(i), g(i, 'allergen'), [c for c, u in g(i, 'nonAllergen') if c in ('AW', 'AN')]) for i in ('460124', '461333')]`:
  - `460124`, Fria fiber-rich loaf "glutenfree": `UW` (wheat) CONTAINS while `AW` is FREE_FROM
  - `461333`, Toblerone: `SA` (almonds) CONTAINS while `AN` is FREE_FROM

  Catalog: 176 products. `AW` accounts for 132 (76 with oats, 35 with wheat CONTAINS), `AN` for 45 and `AM` with lactose for 1; two products count under both `AW` and `AN`. To see the rule in action:
  ```sh
  curl -s -X POST http://127.0.0.1:8000/v1/offers -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Content-Type: application/json" -d '{"lines":[{"text":"10 of 460124 or 461333","product_ids":["460124","461333"],"quantity":10,"unit":"UNIT","exclude_allergens":["AW","AN"],"allergen_strictness":"STRICT"}]}' | python3 -I -c "import json,sys; [print(e['product_id'], e['sentence']) for e in json.load(sys.stdin)['excluded']]"
  ```
  It answers "460124 The product declares that it contains wheat (UW), part of the excluded cereals containing gluten (AW)." and the same for almonds.
- **Why it matters:** scenario 2's strict allergen rule. A buyer who excludes gluten must never get a product that declares wheat.
- **Built while waiting:** both statements are read, and the less safe one counts. When the family is excluded, a member declared CONTAINS rejects the product. A member declared MAY_CONTAIN, or declared oats, goes to a dietitian (`src/tta/allergens/statements.py`).

### 7 · `Q5` · Products with no allergen data
- **Ask:** "Almost half the catalog has no allergen statement at all. Does no data mean the supplier declared nothing, so an agent must treat it as unknown rather than safe?"
- **Show:** in the shell, `[(i, name(i), g(i, 'allergen'), g(i, 'nonAllergen'), [c for c, u in g(i, 'nutritionalClaim')]) for i in ('463168', '463427')]`:
  - `463168`, Peltolan blue cheese 1.6 kg: no allergen entries at all
  - `463427`, HK cooked ham 6 × 300 g: no allergen entries, yet it claims `FREE_FROM_GLUTEN` and `FREE_FROM_LACTOSE`

  In the Friday sample both were priced and deliverable on Monday. `sum(1 for i in P if not g(i, 'allergen') and not g(i, 'nonAllergen'))` returns 8110: that is 8,110 of 17,546 products (46.2%), and 4,149 of the 13,577 food products (30.6%; non-food means category prefixes 63, 64, 20 and 90).
- **Why it matters:** scenario 2 and the trust protocol. For a hospital ward, "no data" must never read as "safe".
- **Built while waiting:** no statement means unknown, and under STRICT it goes to a dietitian. When confirmed data only is asked for, the product is excluded as "Allergen not stated". Five products are excluded this way in scenario 2 tonight, for example `474864` Oddlygood almond drink: "makes no statement about milk (AM)".

### 8 · `T02-1` · Is an `allowedLotSize` of 0.01 "no step"?
- **Ask:** "allowedLotSize is 0.01 on almost every carton and case. We read it as 'no step set' and order whole cases, so 13 cases rather than 12.5 for 250 litres here. Is that expected, or did we get something wrong?"
- **Show:** in the shell, `name('463038'), f('463038'), pr('463038')`. This is the Valio Eila semi skimmed milk drink 10 l novobox, lactose free: its sales unit `KI` holds 2 × 10 l, the lot is 0.01, and the price is €31.31 at €1.57/L, about 20 L per case. So 250 L is 12.5 cases.

  Catalog: the lot is 0.01 on 16,872 of 17,546 products, including 16,476 of the 16,478 not sold by the kilogram. A real step is set on 674 products, 672 of them sold by the kilogram. In the three captures (1,745 ids), no `availableAmount` has a fraction.
- **Why it matters:** 20% on matching the buyer's request precisely. The quantity we order must be one Valio can deliver.
- **Built while waiting:** whole units for every sales unit except `KG`. Kilogram products with 0.01 keep 0.01 kg steps, and a real step is used as given. Quantities are rounded up (`src/tta/catalog/lots.py`): with the beef's 3 kg step, 31 kg becomes 33 kg (€557.04).

### 9 · `T02-2` · What does `comparisonPrice` divide by?
- **Ask:** "We take comparisonPrice to be catalogPrice divided by the content of one sales unit, using the drained weight where there is one, rounded to cents. Is that expected, or did we get something wrong?"
- **Show:** in the shell:
  - `pr('460396'), P['460396']['synkkaData']['unitConversions'][0]['volume']`: Valio skimmed milk 10 l novobox, €8.75 ÷ €0.88/L = 9.943, while the file says 10.0 LTR (tonight).
  - `pr('466382', FR), P['466382']['synkkaData']['unitConversions'][0]['netWeight']`: Filos feta cubes in brine "2kg", €32.33 ÷ €16.17/kg = 2.0, while the file's `netWeight` is 3,390 g (Friday sample).
- **Why it matters:** the pack size turns "1,000 litres" into a number of cases (20% match), and no field states it directly.
- **Built while waiting:** we use the file's own size when the two rounded prices are consistent with it (10 L, not 9.943), and the ratio otherwise (`src/tta/catalog/pack.py`). We checked this on 1,321 captured price lines (a sample).

### 10 · `Q10` · The sales unit differs between the API and the product file
- **Ask:** "On some lines the API's sales unit is not the product file's, and we let the price and the available amount follow the unit on the API line. Is that expected, or did we get something wrong?"
- **Show:** in the shell, `[(i, name(i), f(i)['unit'], f(i)['units'], av(i)['unit'], pr(i)['price'], pr(i)['per']) for i in ('464615', '465244')]`:
  - `464615`, Valio A+ greek yoghurt 1 kg: the file says `KI` (5 tubs), the API says `ST`; €2.92 at €2.92/kg is the price of one tub.
  - `465244`, Arla 5 dl low fat milk: the file says `ST`, the API says `KI` (6 bottles); €6.22 at €2.07/L is the price of a case of six (3 L).

  Tonight 15 of the 624 lines with a schedule line differ. In the Friday sample it was 7 of 797, for example `460657`, Marli tomato juice: the file says `KI` (10 cartons), the API line says `ST` with 112 available, at €2.26 and €2.26/L.
- **Why it matters:** reading the wrong unit multiplies an order by 5 or 10 (20% match, 15% robustness).
- **Built while waiting:** price and quantity follow the unit on the API line. The file's unit is used only when the API gives none (`src/tta/offers/candidates.py`).

### 11 · `T07-5` · A listed substitute sold in another sales unit
- **Ask:** "When a substitute you list is sold in another sales unit than the original, we convert the quantity by volume, so 100 single litres become 10 cases of ten. Is that expected, or did we get something wrong?"
- **Show:** in the shell, `[(i, name(i), f(i)['unit'], pr(i)['price'], pr(i)['per'], av(i)['cutoff']) for i in ('473609', '471690')]`:
  - `473609`, Oddlygood Barista 1 l: `ST`, €1.37
  - `471690`, its listed substitute "1 L Delight": `KI`, €15.55 at €1.56/L, cut-off passed Thu 12 Nov 15:00

  On the page, Scenario 3 → substitute no. 1 reads: "one sales unit holds 10 L, not 1 L; it costs €0.19 more per L." Catalog: 75 of Valio's 250 listed pairs have different sales units in the product file.
- **Why it matters:** scenario 3 and the 15% on substitutions. Swapping unit for unit would order ten times too much.
- **Built while waiting:** quantities are converted through the pack size and rounded up to the lot step.

### 12 · `Q8` · Deposits
- **Ask:** "Is a deposit already inside catalogPrice, or charged on top, and if on top, at what value per deposit code?"
- **Show:** in the shell, `f('476204')['deposits'], pr('476204', FR)['price'], [XR[c]['error'] for c in ('1', '2', '3', '4', '147', '171', '9708918')]`. Bundaberg ginger beer 12 × 37.5 cl carries deposit material `1`, 12 ST, and Friday's price for it was €22.09. The price endpoint answered `error: true` for all 7 deposit codes (Friday extras). Catalog: 506 products carry deposits (576 rows, 7 codes), and none of the codes is a product.
- **Why it matters:** a total that leaves out deposits is not the invoice (core requirement 2, fixed prices).
- **Built while waiting:** totals exclude deposits and say so. In both profiles, a line with a deposit goes to finance (rule P-07).

### 13 · `Q9` · Variable-weight products
- **Ask:** "If an agent orders 30 kg of a variable-weight product, is the invoice for exactly 30 kg, or for the weight actually delivered?"
- **Show:** in the shell, `name('466988'), f('466988'), pr('466988'), av('466988')`: Well Beef chuck roll, sold in `KG`, lot 3 kg, variable weight, €16.88/kg, 109 kg in stock tonight. Then:
  ```sh
  curl -s -X POST http://127.0.0.1:8000/v1/offers -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Content-Type: application/json" -d '{"lines":[{"text":"30 kg beef chuck","product_type":"beef_chuck","quantity":30,"unit":"KG"}]}' | python3 -I -c "import json,sys; o=json.load(sys.stdin)['options'][0]; print(o['summary']); [print(f['rule_id'], f['sentence']) for f in o['decision']['fired']]"
  ```
  It answers "1 confirmed product covers the 30 kg asked for, for €506.40 before tax. The total is a ceiling: … the invoice can be lower, never higher." and fires P-06. Catalog: 632 variable-weight products, 628 of them sold in `KG`. All 37 in the Friday sample are priced per kg.
- **Why it matters:** it is the demo's backup scenario, and it falls under the 15% on delivery constraints. The answer decides whether a fixed-price total exists for these lines.
- **Built while waiting:** the total is marked as a ceiling, and the line goes to the purchasing manager (rule P-06).

### 14 · `Q11` · Category codes
- **Ask:** "Is the 5-digit category code a hierarchy, and which digits are the levels? Can we have the category names?"
- **Show:** in the shell, `[(a, P[a]['category'], b, P[b]['category']) for a, b in (('460027', '460065'), ('461480', '461927'), ('460211', '467530'))]`:
  - tomato NL/BE/ES → tomato Finland: 17401 → 17401
  - Myllyn Paras strawberry-rhubarb pie → berry-mix pie: 41765 → 41763
  - white cabbage → SallaCarte shredded cabbage: 17404 → 17443

  Catalog: of Valio's 250 listed pairs, 230 share all 5 digits, 11 the first 4, 5 the first 3, 2 the first 2 and 2 none.
- **Why it matters:** the "good-better-best" ranking of substitutes (15%) depends on how far a substitute may stray.
- **Built while waiting:** substitute tiers. Valio's listed pairs come first, then the same 5 digits, the same first 4, and the same first 3, labelled weaker (`src/tta/offers/substitutes.py`). We also wrote 30 product types of our own (`src/tta/catalog/product_types.yaml`).

### 15 · `Q12` · Delivery reliability
- **Ask:** "What exactly does the delivery-reliability number measure, and does a missing value mean there is no delivery history?"
- **Show:** in the shell, `[(i, REL.get(i), av(i)) for i in ('464306', '473463', '463038')]`:
  - `464306`: 1.0, Stock
  - `473463`, Atria beef tenderloin: 0.332, 0 available
  - `463038`, Valio Eila 10 l: no row, Terminal

  Catalog: 4,425 of 17,546 products have a value (25.2%). Of those, 56.3% are exactly 1.0 and 12 are 0.0.
- **Why it matters:** delivery-time comparison (an optional direction) and the ranking: a missing value must never rank above a good one.
- **Built while waiting:** the raw value is loaded onto each product. `GET /v1/products/473463` shows `"delivery_reliability": 0.332`. A product with no row stays empty and is never imputed. The value does not change the ranking yet.

---

## C. How the mock and the judging work

### 16 · `Q6` · Stock that covers only part of a line
- **Ask:** "When stock covers only part of an order line, what happens today: a partial delivery, a substitute, or the line is dropped?"
- **Show:** in the shell, `av('469363'), av('461360')`: Arla lactose-free milk drink 1 L has 384 in stock, and Alpro almond drink has 50. The request carries no quantity and the answer has at most one schedule line, so nothing says when the rest could come. Then:
  ```sh
  curl -s -X POST http://127.0.0.1:8000/v1/offers -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Content-Type: application/json" -d '{"needed_by":"2026-11-16","lines":[{"text":"1,500 litres of lactose-free milk by Monday","product_type":"milk","required_claims":["FREE_FROM_LACTOSE"],"quantity":1500,"unit":"L"}]}' | python3 -I -c "import json,sys; o=json.load(sys.stdin)['options'][0]; print(o['summary']); [print(f['rule_id'], f['sentence']) for f in o['decision']['fired']]"
  ```
  It answers "3 confirmed products cover 1,133 L of the 1,500 L asked for (367 L missing), for €2,933.09 before tax." and "P-03 Only 75.5% of the requested quantity is covered, below the 90% minimum."
- **Why it matters:** the 15% criterion names partial availability.
- **Built while waiting:** the rest is filled from other confirmed products and shown as one combined option. Below the profile's minimum fill, the order goes to a human (rule P-03; `src/tta/offers/combining.py`).

### 17 · `Q13` · Call volume during judging
- **Ask:** "Is our call volume fine during judging? Each offer makes two calls, at most six offers a minute reach your API, and the deployed link makes at most 120 calls in all."
- **Show:** in the shell, `L('fixtures/valio/2026-11-14-demo/manifest.json')['product_count'], L('fixtures/valio/2026-11-14-demo/manifest.json')['calls']` returns 769 products in 2 calls (tonight's capture). The live check at 08:12 made 6 calls for the three scenarios. On Friday, 34 requests in 5 minutes drew no 429 and no rate-limit header.
- **Why it matters:** the 30% end-to-end demo must not lose its supplier in the middle of judging.
- **Built while waiting:**
  - we narrow products down locally before calling
  - answers are cached for 60 seconds
  - at most 6 offers a minute reach the live API (2 per visitor)
  - the deployed link has a budget of 120 calls
  - the recorded capture answers, labelled replay, when the budget runs low or the mock does not answer (`src/tta/api/fallback.py`, `deploy/modal_app.py`)

### 18 · `T01-1` · Must an agent send a named User-Agent?
- **Ask:** "A call with a library's default User-Agent got 403, and the same key with a named one got 200. Is that expected, and is a named User-Agent the rule an external agent should follow?"
- **Show:** `grep -n "USER_AGENT =" src/tta/valio/client.py` returns `37:USER_AGENT = "tta-gateway/0.1"`. The 403/200 pair was seen on `GET /api/ping` on Sat 14 Nov 02:40 (`AIMO/FINDINGS.md` §1). It is not re-run here.
- **Why it matters:** 15% openness. Being "openly readable by autonomous agents" should not depend on an undocumented header.
- **Built while waiting:** the client always sends `User-Agent: tta-gateway/0.1` and `Accept: application/json`. A 403 is reported with that hint and is not retried.

### 19 · Ask any 1 · How and when do you judge?
- **Ask:** "How and when do you judge: at our table, from the video, or on the deployed link? And will the mock API stay up, unchanged, until then?"
- **Show:** `curl -s http://127.0.0.1:8000/healthz` returns `"mode": "replay"` and `"replay_capture": "2026-11-14-demo"`. Every page carries the yellow label "Replay: recorded Valio Aimo data, clock pinned to the recording".
- **Why it matters:** the 30% end-to-end demo. The answer decides whether we demo live or from the recording.
- **Built while waiting:** replay mode answers from tonight's capture with the clock pinned to Sat 02:52. The deployed link runs live and falls back to the capture, labelled, when the mock fails or the budget runs low.

### 20 · Ask any 2 · Must exception cases run live?
- **Ask:** "Do exception cases have to run in the live demo, or does a documented, tested rule count?"
- **Show:** on the page, Scenario 1 reads "Excluded: 19 products, each with its reason: 17 × Cut-off passed, 1 × Portion pack, 1 × Not deliverable." `ls tests/e2e` lists one end-to-end test file per scenario, plus the beef backup and the guards.
- **Why it matters:** 15% robustness. The answer decides whether the partial fill at 1,500 L has to be on stage.
- **Built while waiting:** passed cut-offs, unknown stock, products that cannot be delivered, allergen exclusions and substitutes all run in the three scenarios. The partial fill, variable weight and an agent trying to approve its own order run as typed requests and are tested in `tests/e2e/`.

### 21 · Ask any 3 · Webshop test accounts
- **Ask:** "The brief mentions webshop test accounts. Are they available?"
- **Show:** `grep -n "Webshop test accounts" AIMO/CHALLENGE.md` finds line 60: "Webshop test accounts to be shared separately."
- **Why it matters:** an account could ground our buyer profiles (question 3) in a real customer setup (20% controls).
- **Built while waiting:** nothing; we have not used them.

### 22 · Ask any 4 · May your data stay in a public MIT repository?
- **Ask:** "The hackathon requires a public MIT repository. May your datasets and a few recorded answers of the mock API stay in it, or should we keep them out?"
- **Show:** `git ls-files 'valio_aimo_*' fixtures/valio | wc -l` returns 22: 4 datasets and 18 recorded API files. The README says: "The Valio Aimo datasets and recorded API answers are not ours and are not covered by it."
- **Why it matters:** it is a submission rule, so there is a disqualification risk, and it bears on the 15% openness criterion. Our tests read the recorded answers.
- **Built while waiting:** the README leaves the data out of the MIT licence. We must decide before the repository goes public.

---

## Numbers corrected or added against `BOOTH-QUESTIONS.md` and `WALKTHROUGH.md`

- **T03-2:** 176 products, not 178. The 178 adds the per-family counts (`AW` 132 + `AN` 45 + `AM` 1), but two Marabou products (`466691`, `467090`) count under both `AW` and `AN`.
- **Q1 (WALKTHROUGH "about half the catalog at any time"):** it is a sample figure. 425 of the Friday sample's 1,000 products (42.5%) had a passed cut-off, which is 53% of the 797 with a schedule line. FINDINGS' 42.3% counts 423, because it gives the blocked line and lines with amount 0 states of their own.
- **Q8:** the €22.09 for `476204` comes from Friday's price call, not from the product file, which has no prices.
- **Q10:** Friday's 7 of 797 holds. Tonight's capture adds 15 of 624, in both directions, so the examples now use tonight's `464615` and `465244`.
- **Q11:** the 20 pairs that leave the 5-digit category are 11 sharing 4 digits, 5 sharing 3, 2 sharing 2 and 2 sharing none. The booth file named only the first two groups.
- **T02-2:** the "186 of 190" and "481 of 513" fit counts are left out. They were not recomputed, and `src/tta/catalog/sizes.py` gives other figures (188 of 190 and 486 of 513, within 3%). Only the 1,321 lines were recounted.
- **Not verifiable from saved files, kept as reported:** six customer strings giving identical prices (Q7, Friday) and the 403/200 User-Agent pair (T01-1, 02:40).
