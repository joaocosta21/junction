# P10 — A substitute or a cheaper item must keep the formula where the formula matters (V10)

Agent P10, 14 Nov. No code or document was changed. Every figure below was counted by a scratch script in
`/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/P10/`
(named with each figure) or is quoted with `path:line`. "Whole catalog" means all 17,546 products of the product file.
"Demo capture" means `fixtures/valio/2026-11-14-demo` (769 products). Nutrient figures are per 100 g or 100 ml, in the
order fat / saturated fat / protein / carbohydrate / sugars / salt.

## 1. In five lines
1. The data can judge sameness. Fat, saturated fat, protein, carbohydrate, sugars and salt per 100 g are on 611 of 620 dairy products (98.5%) and on 11,538 of 17,546 products of the catalog (65.8%, with energy); an ingredient text is on 99.8% of dairy. The build loads no nutrition value and compares none.
2. Today the build's only idea of sameness is the category number. Measured in replay: for 100 L of Arla Pro whipping cream (36% fat) the offer fills 52 L with a 15% vegetable-fat cooking blend, the verdict is AUTO, and the sentence says only "Valio does not list it as a substitute".
3. Recommendation: a "same formula" measure with named tolerances (six nutrients, each within 15% or 1 g; same fat source in the ingredient text) and five outcomes: same product in another pack · same brand · other brand · different · not known. It ranks after the allergen rule and after the dietary-claim gate, and before listing, pack size and price.
4. Where the formula matters (the request says so, a recipe line, a sensitive product type, or the profile), a different or unknown formula is never the suggestion: it is shown flagged, with the differences in numbers, and needs an explicit yes (new fixed rule F-10). A cheaper item is suggested unasked only when it adds no allergen, loses no dietary claim and keeps the formula.
5. With a draft of the measure: of Valio's 249 listed pairs 101 keep the formula, 71 do not, 77 cannot be compared. In the demo capture 244 of 613 dairy products have a cheaper product that keeps everything (whipping cream: €4.04 less per litre). Minimum version: 3 hours. A biomedical member owns the tolerances.

## 2. What exists today

### 2.1 What the data offers (whole catalog; script `coverage.py` over an extract of all 17,546 products)
"Per 100" counts a `synkkaData.nutritionalContent` row with `basisQuantity` 100 and unit `GRM` or `MLT`.

| Field | All 17,546 | Dairy 104xx (620) | Cream 10401 (53) | Butter 10500 (20) | Fats, oils, eggs 105xx (200) | Cheese 10600/02/03 (295) | Flour 21300/10 (87) | Sugar 22100 (40) |
|---|---|---|---|---|---|---|---|---|
| Brand | 14,463 (82.4%) | 610 (98.4%) | 53 | 19 | 167 (83.5%) | 248 (84.1%) | 76 (87.4%) | 39 |
| English name | 17,544 | 620 | 53 | 20 | 200 | 295 | 87 | 40 |
| Name holds a % figure (the only trace of a "line") | 426 (2.4%) | 62 (10.0%) | 20 (37.7%) | 0 | 16 | 53 (18.0%) | 0 | 0 |
| Fat per 100 | 11,986 (68.3%) | 611 (98.5%) | 53 | 19 | 187 (93.5%) | 291 (98.6%) | 83 (95.4%) | 39 |
| Saturated fat per 100 | 11,722 (66.8%) | 611 | 53 | 19 | 187 | 283 (95.9%) | 82 | 39 |
| Protein per 100 | 11,998 (68.4%) | 611 | 53 | 19 | 182 (91.0%) | 291 | 83 | 39 |
| Carbohydrate per 100 | 11,971 (68.2%) | 611 | 53 | 19 | 182 | 285 (96.6%) | 83 | 39 |
| Sugars per 100 | 11,676 (66.5%) | 611 | 53 | 19 | 181 (90.5%) | 284 (96.3%) | 82 | 39 |
| Salt per 100 | 11,786 (67.2%) | 611 | 53 | 19 | 181 | 291 | 79 (90.8%) | 39 |
| Energy per 100 | 12,038 (68.6%) | 611 | 53 | 19 | 187 | 291 | 83 | 39 |
| All six (fat, protein, carbohydrate, sugars, salt, energy) | 11,538 (65.8%) | 611 (98.5%) | 53 (100%) | 19 (95%) | 181 (90.5%) | 283 (95.9%) | 78 (89.7%) | 39 (97.5%) |
| Ingredient text `keyIngredients`, any language | 14,045 (80.0%) | 619 (99.8%) | 53 | 19 | 195 (97.5%) | 291 (98.6%) | 84 (96.6%) | 39 |
| Ingredient text in English | 11,590 (66.1%) | 606 (97.7%) | 52 | 19 | 156 (78.0%) | 249 (84.4%) | 76 | 38 |
| Structured `ingredients` array | 3,746 (21.3%) | 431 (69.5%) | 45 | 16 | 52 (26.0%) | 202 (68.5%) | 30 | 0 |
| Net weight or volume in `unitConversions` (raw field) | 10,242 (58.4%) | 306 (49.4%) | 29 | 13 | 119 | 112 (38.0%) | 73 | 34 |
| At least one nutritional claim | 7,618 (43.4%) | 568 (91.6%) | 50 | 18 | 102 (51.0%) | 227 (76.9%) | 58 | 5 |
| Lists a substitute (self-loop dropped) | 188 (1.1%), 249 pairs | 23 (3.7%) | 3 | 1 | 3 | 11 | 0 | 0 |

Eggs (categories 10590 and 10592, 30 products): all six nutrients on 30.

What this means:
- **Nutrition is the strong field.** In dairy it is nearly complete. In the whole catalog a third of the products have none (non-food and thin records), so "not known" is a real outcome.
- **The ingredient text is the second field.** It separates a dairy cream from a vegetable-fat blend when the fat figure is the same. `464249` Valio cooking cream 15%: "CREAM, water, modified starch." `469162` Valio cooking cream alternative 15%: "skim MILK, water, vegetable oil (rapeseed), modified starches, emulsifier (E472e), flavouring, colour (carotenes)."
- **The structured `ingredients` array cannot be used.** For both creams above it holds one row, `Milk`, with no percentage.
- **An English ingredient text of "-" counts as present in the table.** `467142` and `467297` (Rama Professional) carry "-" in English; their Finnish text is complete and names buttermilk, hardened palm oil and coconut oil. The loader already falls back to the Finnish text when the English one has no letter (`src/tta/catalog/loader.py:178-191`), so the word lists of the measure need the Finnish words. 77 products of the catalog have all six nutrients and no usable ingredient text in either language; none of them is dairy (script check at 15:06).
- **Brand is nearly complete in dairy.** The product line is not a field. It is only in the name ("Valio Eila®", "Valio Keittiön", "Oatly iKaffe", "Oddlygood® Barista"). Some brand values already hold a line ("Arla Pro", "Arla Lempi", "Valio maidot").
- **Valio's listed substitutes are few:** 249 pairs on 188 products.
- **Noise in the nutrition rows.** 167 products carry a fat row that is not per 100 g or ml. Stated kcal disagrees with 9 × fat + 4 × protein + 4 × carbohydrate + 2 × fibre by more than 25 kcal and 25% on 217 of the 11,733 products that carry all four (script `sens.py`); in dairy on 4 of 611, for example `469452` (716 kcal stated, 173 computed) and `465283` (197 stated, 47 computed): a kJ value in the kcal field. Energy is the noisiest of the six and adds nothing the other figures do not hold.
- **Pack size:** the build derives it by its own tiers (`PackSize.source`, `src/tta/contracts/product.py:77-88`). I counted the raw field only.

### 2.2 What the build does today (code read, then run offline in replay as `hotel-kitchen`)
- **The product holds no nutrition value.** `src/tta/contracts/product.py:31-62` has brand, claims, allergen statements, listed substitutes and the ingredient text (`:54`). `src/tta/catalog/loader.py:164-169` reads claims, substitutes and ingredient text; it never reads `nutritionalContent`.
- **Nothing knows the buyer's purpose.** `src/tta/contracts/request.py:44-79` has no field for it. A search of `src/tta` (`*.py`, `*.yaml`) for `baking`, `purpose`, `intended_use`, `formula`, `nutritionalContent`, `per_100` finds only the phrase "on purpose" in four comments.
- **Candidates:** the pairs Valio lists, then the same 5-digit category, the same first 4 digits, the same first 3 (`src/tta/offers/substitutes.py:45`, `:161-176`). Shown: every listed one, then category tiers until three can be ordered, at most 10 unlisted (`:41-43`, `:226-242`).
- **Ranking** (`substitutes.py:253-266`): passes the allergen rules → keeps every dietary claim → category distance → listed by Valio → pack size closest → verification → price per litre or kg → id. Composition is not in it.
- **The "gives up" sentence** (`src/tta/offers/substitute_wording.py:57-76`) compares: claims not carried, brand, listed or not, category number, pack size, price when dearer (`:110`), quantity not confirmed. When none differs it says "nothing the data shows is given up" (`:26-29`).
- **Allergens:** a substitute may not add an allergen or raise one from may contain to contains (`src/tta/allergens/substitution.py:25-47`); rule F-05 blocks it (`src/tta/policy/rules.yaml:201-213`). A dietary claim lost sends the line to a human, rule F-08 (`rules.yaml:255-268`); the eight dietary claims are at `substitutes.py:53-64`.
- **Profile scope, rule P-05** (`rules.yaml:365-383`, scopes `:53-56`, fact `src/tta/policy/facts.py:318-324`): NONE, LISTED_BY_SUPPLIER or SAME_CATEGORY. The hotel accepts SAME_CATEGORY without a human (`src/tta/policy/profiles/hotel-kitchen.yaml:19`), the ward nothing (`allergy-ward.yaml:19`).
- **Offers:** a substitute line appears only when the request names products by id and they cannot be supplied in full (`src/tta/offers/planning.py:201-203`). It is the first ranked candidate that carries the request's required claims and labels and can be ordered (`planning.py:231-239`). There is no unasked cheaper suggestion.
- **Recipes, rule F-09** (`rules.yaml:273-285`): the menu planner swaps product types by role, for example cream → vegetable-fat cream → milk (`src/tta/menus/recipes.yaml:37-45`), and the line goes to a human. It works between types. Inside a type it takes whatever the offer ranks first.

Measured (scripts `run_subs.py`, `run_offer.py`, `run_s3.py`; replay, clock 2026-11-14 02:52):

| What was asked | What came back | What it does not say |
|---|---|---|
| Substitutes of `464194` Valio whipping cream 1 l (38 / 22 / 2.0 / 2.8 / 2.8 / 0.07). 619 candidates checked. | Rank 1 `463837`, the same cream in 2 dl. Rank 2 `469162` cooking cream alternative 15% (15 / 1.4, rapeseed oil). Rank 3 `464249` cooking cream 15%. Rank 4 `463442` coffee cream 10%. Rank 5 `464221` low fat cream 10%. The first other whipping cream is rank 6 (`464699`, 35%). `469346` Arla Pro whipping cream 36%, which Valio lists, is rank 10: it does not declare VEGETARIAN. | Rank 3's sentence in full: "Compared with Valio whipping cream 1 l UHT lactose free: Valio does not list it as a substitute; Valio does not confirm the quantity in stock." Fat 15 against 38 is not mentioned. |
| Offer: 100 L of `469346` Arla Pro whipping cream (36 / 23 / 2.2 / 2.9 / 2.9 / 0.06), 48 L confirmed. | Option SUBSTITUTE, €411.12: 48 L of it and 52 L of `463975` Arla Pro Ruoka 15% "vegetable mix" (15 / 1.3 / 1.5 / 4.9 / 2.0 / 0.06; "Skimmed MILK (Finland), water, rapeseed oil, …"). Verdict **AUTO**: "The agent may place this order alone … no rule asks for a human." | "Compared with Arla Pro Whipping cream 1 L UHT lactose free: Valio does not list it as a substitute." |
| Offer: 100 L of `464727` Arla whipping cream 35%, 37 L confirmed. | SUBSTITUTE, €435.23: 63 L of the same `463975`. Verdict AUTO. | "the brand is Arla Pro, not Arla; Valio does not list it as a substitute." |
| Offer: 300 L of `463797` Arla Pro cooking cream 10%. | SUBSTITUTE, €857.22: 186 L of `463975`. APPROVAL, by the spend limit P-01 only. | The fat source. |
| Substitutes of `473609` Oddlygood Barista oat drink (scenario 3). | Rank 1 `471690` Barista "Delight", listed by Valio: fat 1.5, not 3.0. | "one sales unit holds 10 L, not 1 L; it costs €0.19 more per L." |

### 2.3 Real examples (ids; demo capture unless said; price per litre is `comparisonPrice` of the recorded price call)
| Case | Products and numbers |
|---|---|
| Same product, another pack | `464194` Valio whipping cream 1 l (38 / 22 / 2.0 / 2.8 / 2.8 / 0.07; €3.91/L) = `463837` 2 dl (€8.05/L) = `463366` 10 l (€4.92/L): the six values are identical. Also `464249` cooking cream 15% 1 l = `463828` 2 dl = `476880` 10 l (15 / 8.8 / 1.9 / 5.3 / 2.9 / 0.19). |
| Same brand, another fat level | Valio: whipping cream `464194` 38, cooking cream `464249` 15, coffee cream `463442` 10. Valio milk: `469549` semi skimmed (1.5 / 0.9 / 3.2 / 4.8 / 4.8 / 0.1) and `469556` whole (3.5 / 2.1 / 3.2 / 4.8 / 4.8 / 0.1). Oatly: `464320` iKaffe 3.0 and `470863` Oat Drink Semi 1.5. |
| Another brand, nearly the same | `464194` Valio (38 / 22 / 2.0 / 2.8 / 2.8 / 0.07) and `469346` Arla Pro whipping cream (36 / 23 / 2.2 / 2.9 / 2.9 / 0.06), a pair Valio lists. `469549` Valio semi skimmed and `476927` Arla semi skimmed (1.5 / 1.0 / 3.5 / 4.8 / 4.8 / 0.1). `469363` Arla lactose-free milk drink (1.5 / 1.0 / 3.2 / 3.0 / 3.0 / 0.09) and `464306` Valio Arki Eila (1.5 / 0.9 / 3.0 / 3.1 / 3.1 / 0.1): the two options of the main demo. |
| Whipping cream at another fat level | `464194` 38 against `467142` Rama Professional Whipping 30% (30 / 28 / 1.8 / 3.4 / 2.0 / 0.09; English ingredient text "-", the Finnish one names buttermilk, hardened palm oil and coconut oil) and `463299` Millac Gold 33.5 (33.5 / 28.6 / 2.7 / 4.0 / 4.0 / 0.14; its text names lactose-free buttermilk first, then partially hardened vegetable fat from palm, then lactose-free cream at 6%). |
| Vegetable-fat blend against dairy cream | `464249` Valio cooking cream 15% (15 / **8.8**) against `469162` Valio cooking cream alternative 15% (15 / **1.4**). Same fat, same brand, same category. Only saturated fat and the ingredient text tell. |
| Butter against a spread (whole catalog; not in the demo capture, so no price) | `464411` Valio butter unsalted (fat 82, saturated 48, salt 0.02; "Pasteurised CREAM and culture"). `476849` Valio Oivariini butter-blend (75 / 31, salt 1.4; "BUTTER, rapeseed oil, water, salt and vitamin D."). `461904` Sunnuntai margarine for baking (80 / 38, salt 0.7; vegetable fats). `460684` Keiju margarine 60 (60 / 15). Salted `475797` (salt 1.4) against unsalted `464411` (0.02). `471792` Eleplant "plant power" sits in the butter category 10500 with fat 82 and saturated 53 like butter; its text starts "Vegetable oils and fats (coconut, rapeseed, shea)". |
| Barista oat drink against a plain one | `473609` Oddlygood Barista (3.0 / 0.3 / 1.2 / 6.6 / 3.5 / 0.1; "… rapeseed oil, acidity regulator (potassium phosphates) …"; €1.37/L) against `468465` Oddlygood oat drink (1.0 / 0.1 / 1.2 / 6.6 / 3.5 / 0.12; no acidity regulator; €1.17/L). `472598` Fazer Aito Barista 2.8 against `472833` Fazer Aito Oat Drink 1.2. |
| Listed by Valio, different all the same | `473609` → `471690` Barista "Delight": fat 1.5, not 3.0. `464249` → `463797`: fat 10, not 15. `464306` (carbohydrate 3.1) → `464201` Valio lactose-free milk (4.8): a "milk drink" with less sugar against a milk with all of it. |
| Cheaper, keeps the formula | `464727` Arla whipping cream €7.37/L → `465193` Valio food service whipping cream €3.33/L: €4.04 less per litre (55%); 35 / 23 / 2.0 / 3.0 against 35 / 21 / 2.2 / 3.0; both texts list cream and the stabiliser carrageenan, nothing else. `469346` Arla Pro €5.77/L → `465193`: €2.44 less (42%). `464320` Oatly iKaffe €1.78/L → `470889` Oatly Oat Drink Whole €1.40/L (fat 3.0 against 2.8, the same ingredients in the same order): €0.38 less (21%). `469363` → `464306`: €1.47 less per litre (59%), the main demo. Note: Valio reports no real stock figure for `465193` and `464306`, so the existing rule sends them to a human. |
| Cheaper, does not keep the formula | `464249` Valio cooking cream 15% €2.63/L → `469162` cooking cream alternative €1.79/L: €0.84 less (32%), saturated fat 1.4 against 8.8, vegetable oil. `473609` Barista €1.37/L → `468465` plain oat drink €1.17/L: €0.20 less (15%), fat 1.0 against 3.0, no acidity regulator. |
| Same formula, dietary claim lost | `469126` Valio whipping cream 2 dl lactose free → `469050` Valio Keittiön whipping cream 2 dl: six identical values (35 / 21 / 2.2 / 3.0 / 3.0 / 0.07), same brand, and FREE_FROM_LACTOSE is gone. The nutrition panel cannot see it. |

## 3. What Valio's answer changes
- **V10 says sameness depends on composition and on the use.** The build measures sameness by category number, and V7 says nobody confirmed that the digits are levels. Inside one category number few pairs keep the formula (draft measure, whole catalog, script `sens.py`): 21.9% of the pairs in milk 10400, 11.2% in cream 10401, 5.5% in plant drinks 10402, 14.7% in butter 10500. For `464194`, 14 of the 52 other creams keep the formula and 38 do not.
- **"Listed by Valio" does not mean "same formula" either.** Of the 249 listed pairs: 41 are the same product in another pack, 26 the same brand within tolerance, 34 another brand within tolerance (101 keep the formula), 71 differ, 77 cannot be compared (no nutrition on one side). For dairy originals (44 pairs): 29 keep it, 15 do not.
- **The hotel profile lets the agent take a different formula alone.** P-05's widest scope is SAME_CATEGORY; that is what produced the AUTO verdict of section 2.2. With V8 every order now needs the user, but the offer still presents the blend as the suggestion and the sentence still hides the difference.
- **The sentence must carry numbers.** The mentor's words are about chemistry. "Fat 15 g, not 36 g; saturated fat 1.3 g, not 23 g; it names a vegetable oil" is what lets a cook say no in five seconds.
- **V5 gives the rule for missing data:** not sure means ask. A third of the catalog has no nutrition, so the measure needs a "not known" outcome that asks, never a silent pass.
- **B7 as clarified at 14:51 sets the order.** A substitute that loses a dietary claim is a last resort and goes to a human. Formula comes after that. The example `469126` → `469050` shows why: the formula measure calls them the same product. Of the 39 listed pairs that lose a dietary claim (the build's list of eight), 15 keep the formula (3 + 1 + 11 by tier), 23 differ, 1 is not known.
- **Valio's end goal is winning customers.** The build never points to a saving. A cheaper item that provably keeps allergens, claims and formula is a selling point the data supports for 244 of 613 dairy products of the demo capture (section 4.5).

## 4. Options and recommendation

### 4.1 How the agent knows the formula matters
| Source | What sets it | Cost |
|---|---|---|
| a. The request says so | The reader sets `keep_formula: true` on a line when the buyer's words name a use: baking, pastry, whipping, sauce, cake, foam, a recipe. | Reader prompt and rules reader; depends on Gemini reading it right. |
| b. A recipe line | The menu planner sets it on every line it creates: an ingredient of a recipe is the case V10 describes. | One line in `menus/needs.py`. |
| c. The product type | A flag `formula_sensitive` in the product-type table. True: cream, vegetable_cream, butter, cheese, quark, yoghurt, eggs, flour, sugar, olive_oil. False: milk, plant_drink, juice, soft_drink, mineral_water, coffee, tea and the rest. The list is ours. | One column in a YAML file. Works with no model at all. |
| d. The buyer profile | `formula_match: BY_TYPE` or `ALWAYS` (a bakery: always). | One setting. |

Rule for combining them: any source that says yes wins. A request or a profile can add the check and can never remove it, as `stands_in_for` already works (`src/tta/contracts/request.py:66-70`).

Default when nothing says:
- Option A, always matters. Safe, but it flags a milk for drinking, which V10 says is fine.
- Option B, matters only when said. A buyer who does not say "for baking" gets the blend. This is today's behaviour and it is what V10 objects to.
- **Option C, recommended:** the product type decides; a product named by id whose type is not in the table counts as "matters" (V5: not sure means ask).

**DECISION 1:** the default (recommended: C) and the list of sensitive types. A biomedical member writes the list.

### 4.2 The measure
Two products have the same formula when **all** of this holds:
1. Fat, saturated fat, protein, carbohydrate, sugars and salt per 100 g or ml are present on both, on the same basis.
2. Each differs by no more than **15% of the original's value or 1.0 g, whichever is larger; for salt 15% or 0.25 g**.
3. The ingredient texts agree on the fat source: either both name a vegetable oil or fat (vegetable oil, vegetable fat, rapeseed, palm, coconut, shea, sunflower, and the Finnish words) or neither does.

Energy is not compared: it follows from the other figures and is the noisiest field (section 2.1).

Why these numbers (to be signed by a biomedical member; they are ours and must be labelled so):
- **1.0 g floor.** The catalog's own milk grades are 1.5 g of fat apart (0 / 1.5 / 3.0 to 3.5), and a barista oat drink is 1.5 g from its light version. The floor must stay under 1.5 g or skimmed, semi-skimmed and whole milk become one formula. It should not go under about 0.5 g because labels are rounded. Assumption, from memory, not checked in this round: EU guidance rounds fat, carbohydrate, sugars and protein to 1 g from 10 g up and to 0.1 g below.
- **15%.** It keeps whipping creams of 35, 36 and 38% fat together (38 against 35 is 7.9%) and separates 38 from 30 (21%) and from 15.
- **Salt 0.25 g.** It separates unsalted butter (0.02) from salted (0.8, 1.4, 2.1) and does not separate creams at 0.07 and 0.19.
- **For comparison (assumption, from memory, to verify before it is cited):** the European Commission's guidance on label tolerances (December 2012) lets a label be off by ±1.5 g of fat or ±2 g of carbohydrate, sugars or protein under 10 g per 100 g, ±20% from 10 to 40 g, ±8 g above, and ±0.375 g of salt under 1.25 g. Ours is tighter at the low end on purpose, because of the milk grades.
- **Sensitivity over the 249 listed pairs** (script `sens.py`): 10% and 0.5 g gives 87 within and 85 different; 15% and 1.0 g gives 101 and 71; 20% and 1.0 g gives 104 and 68; 20% and 1.5 g gives 110 and 61. The verdict moves on 24 pairs of 249 across the four settings.

What a different ingredient text means:
- Minimum version: only the fat source. It is what separates cream from blend, butter from spread and margarine.
- Full version: the first ingredient (assumption: EU labelling lists ingredients in descending order of weight) and the functional additives present on one side only (acidity regulator, stabiliser, emulsifier, modified starch, thickener) are named in the sentence. They do not change the outcome alone: the text is free text in two languages, and a mismatch from spelling must not cry wolf.

When data is missing (V5):
- No nutrition on either side, a row not per 100 g or ml, or a different basis: outcome **not known**.
- Numbers within tolerance but no usable ingredient text on one side, in English or Finnish (77 products of the catalog have all six nutrients and no such text; none is dairy): outcome **not known**, with the sentence "the nutrition figures agree; the ingredient list is missing".
- Not known is never treated as same.

Limits to say out loud: the panel does not show protein type, heat treatment, stabiliser dose or lactose. `464761` Valio butter for laminating (83 / 48) is within tolerance of `464411` Valio butter (82 / 48); a pastry cook may still care. So the wording is "the data shows no difference", as `NOTHING_GIVEN_UP` already says, never "identical".

**DECISION 2:** the tolerances (15%, 1.0 g, salt 0.25 g), the six nutrients, energy left out.

### 4.3 The reading of "same brand/formula"
João's note says "need to be same brand/formula". It can be read two ways:
- R1: the same brand **and** the same formula. Only "same product, other pack" and "same brand" pass.
- R2: the brand stands for the formula. Another brand with the same formula passes, and the brand is named.

**Recommended: R2**, with a profile setting `substitute_brand: ANY | SAME` for a buyer who wants R1. Reason: Valio itself lists cross-brand pairs (102 of 250 are same-brand, `AIMO/docs/PRODUCT-DATA.md:585`), and R1 would rule out `469346` Arla Pro for `464194` Valio, which Valio lists and which differs by 2 g of fat.
**DECISION 3:** R1 or R2. João heard the answer; he should say.

### 4.4 The order of the gates, and the outcomes
Order (first decides first):
0. **Allergen rule.** Adds or raises an allergen (F-05), or declares one the buyer excludes: shown with the reason, never orderable. Unchanged.
1. **Dietary claims (B7, clarified).** A candidate that loses a dietary claim of the original, or a claim or label the request requires, is a last resort: not shown while a candidate that keeps them can be supplied; when shown it goes to a human (F-08). No formula outcome can lift it. Agent P9b checks what the build does today.
2. **Formula outcome (new):** A same product in another pack → B same brand, within tolerance → C another brand, within tolerance → D different → E not known.
3. Listed by Valio → pack size closest → verification status → price per litre or kg.

The formula outcome takes the place of "category distance" in the ranking key (`substitutes.py:260`). Where candidates come from is agent P7's topic.

| Outcome | Formula matters | Formula does not matter (for example milk to drink) |
|---|---|---|
| A. Same product, other pack | May be the suggestion. "The same product in 2 dl packs: 5 packs per litre." | The same. |
| B. Same brand, within tolerance | May be the suggestion. Differences in numbers when there are any. | The same. |
| C. Other brand, within tolerance | May be the suggestion. The brand is named. (Under R1: flagged, explicit yes.) | The same. |
| D. Different formula | Never the suggestion. Shown flagged, with every difference in numbers. Needs the user's explicit yes to this line, by rule F-10. | May be the suggestion. The differences are still in the sentence. |
| E. Not known | Never the suggestion. Flagged: "cannot be compared: no nutrition data for …". Explicit yes, by rule F-10. | Shown, with "composition not known". |

The sentences (built from data, as `gives_up` is today):
- D: "Different formula: fat 15 g, not 36 g; saturated fat 1.3 g, not 23 g; carbohydrate 4.9 g, not 2.9 g per 100 g. Its ingredient list names a vegetable oil; the original's does not."
- C: "Same formula within our tolerance (fat 38 g against 36 g, saturated fat 22 g against 23 g per 100 g). Other brand: Valio, not Arla Pro."
- A: "The same product in another pack: 0.2 L, not 1 L."

**Good, better, best:** best is A or B; better is C; good is D with its numbers, and only where the formula does not matter. Where it matters and fewer than three of A to C can be ordered, the list says so and shows D and E flagged below a line. Nothing is hidden by the formula gate; only the dietary-claim gate hides.

**DECISION 4:** F-10 as a fixed rule that no profile can switch off (recommended, since Valio called V10 very important), or as a profile rule. And who says yes: the purchasing manager (exists today) or a new kitchen role.

**DECISION 5 (with P9b):** which claims are in the dietary gate. Today's list of eight includes VEGETARIAN and VEGAN (`substitutes.py:53-64`). 17 of the 39 listed pairs that lose a dietary claim lose only one of these two. The measured effect: `469346` Arla Pro whipping cream becomes a last resort for `464194` only because Arla does not declare VEGETARIAN on cream, and a 15% cooking cream that keeps the claim stays ahead of it. João's words are about safety ("so that you dont kill any1"). Options: keep all eight (no change, the safe reading of "when in doubt"), or keep lactose, gluten, wheat, egg and soy always and count VEGAN and VEGETARIAN only when the request or the profile asks for them.

### 4.5 Cheaper suggestions, unasked
Options:
- Never. Safe; ignores Valio's goal.
- Whenever cheaper in the category. This is the trap V10 names.
- **Recommended: only when every condition holds.**
  1. It passes gate 0: it adds no allergen and raises none, declares none the buyer excludes, and it carries an allergen statement when the original does (no data is unknown, not safe).
  2. It passes gate 1: it keeps every dietary claim of the original, every claim and label the request requires, and the certificate labels of the original (organic). The check is the same function F-08 uses (`claims_lost`, `substitutes.py:217-223`), so the two cannot drift apart.
  3. Its formula outcome is A, B or C. Never D or E, even where the formula does not matter: an unasked suggestion must not need a judgement.
  4. Its price is confirmed and lower per litre or kg by at least a named share (ours: 5%), and it can be delivered by the needed-by date.
- It never replaces what was asked. It is one extra line under the option, and the user chooses (V8).

Checked on the demo capture (script `claims_cheaper.py`; dairy 104xx; same 5-digit category; price per litre or kg from the recorded price call; "can be delivered" means it has a schedule line):
- 613 products have a comparison price. 550 of them have a cheaper product in their category.
- For 411 at least one cheaper product loses a dietary claim. For 297 at least one adds an allergen.
- For 152 at least one cheaper product **keeps the formula** and still loses a dietary claim or adds an allergen. This is what the two gates stop and what a formula check alone would let through.
- **244 have a cheaper product that keeps allergens, dietary claims and formula.** The script asserts that none of the 244 suggestions loses a dietary claim or adds an allergen: true by construction, since conditions 1 and 2 are filters applied before the price is looked at.
- For 226 the cheaper products that keep allergens and claims all change the formula: nothing is suggested.
- Not checked in the script: labels (organic). `464699` is organic and its cheaper same-formula product `465193` is not, which is why condition 2 names labels.

**DECISION 6:** unasked cheaper suggestions on or off (recommended: on, under the four conditions), the 5%, and whether a profile may restrict them to the same brand.

### 4.6 Contract fields, rules and settings (names only, no code)
- `Product.nutrition`: `fat`, `saturated_fat`, `protein`, `carbohydrate`, `sugars`, `salt` (each a number or none) and `basis` (G or ML). The loader fills it from rows with `basisQuantity` 100.
- `FormulaCheck`: `outcome` (SAME_PRODUCT_OTHER_PACK · SAME_BRAND · OTHER_BRAND · DIFFERENT · NOT_KNOWN), `differences` (nutrient, original value, other value), `ingredient_note`, `sentence`.
- `SubstituteCandidate.formula` and `SubstituteInfo.formula` (the offer line).
- `RequestLine.keep_formula` (true adds the check; none leaves it to the type) and the same on `SubstituteQuery`.
- `ProductType.formula_sensitive` in `src/tta/catalog/product_types.yaml`.
- Tolerances as named values in one file, labelled ours and illustrative.
- Policy facts: `line.formula_matters`, `line.substitute_formula_outcome`, `line.substitute_formula_differences`.
- **Rule F-10 (fixed, per line):** a substitute whose formula differs from the original's, or cannot be compared, on a line where the formula matters → APPROVAL. The fired rule records the outcome and the differences, so the buyer and Valio read the same reason in the log.
- **P-05:** a scope SAME_FORMULA between LISTED_BY_SUPPLIER and SAME_CATEGORY. The hotel moves from SAME_CATEGORY to SAME_FORMULA.
- Profile settings: `formula_match` (BY_TYPE · ALWAYS), `substitute_brand` (ANY · SAME), `cheaper_suggestions` (OFF · SAME_FORMULA), `min_saving_ratio`.

## 5. Work items
Hours are estimates. Minimum version first: F1 to F4, 3 hours.

| id | What | Files it would touch | Hours | Who | Criterion | Depends on |
|---|---|---|---|---|---|---|
| F1 | Nutrition per 100 g on the product | `src/tta/contracts/product.py`, `src/tta/catalog/loader.py`, loader tests | 0.5 | computer-science member | 20% precision | — |
| F2 | The measure: two products in, a `FormulaCheck` out. Tolerances as named values. The examples of section 2.3 as its tests | new `src/tta/offers/formula.py`, new test file | 1.0 | biomedical member (owns the tolerances and the fat-source words) | 20% precision; 15% openness (visible assumptions) | F1 |
| F3 | Into the substitutes: the outcome on each candidate, in the ranking key after the dietary claims, and in the "gives up" sentence with numbers | `src/tta/offers/substitutes.py`, `substitute_wording.py`, `planning.py`, `src/tta/contracts/offer.py` | 0.75 | computer-science member | 15% exceptions; 20% precision | F2; shares these files with P7, P9a, P9b |
| F4 | Rule F-10, its three facts, and `formula_sensitive` on the product types | `src/tta/policy/rules.yaml`, `facts.py`, `validation.py`, `src/tta/catalog/product_types.yaml`, `product_types.py` | 0.75 | biomedical member (rule text, type list) with the computer-science member (facts) | 20% autonomy and controls | F3 |
| F5 | `keep_formula` on the request line; the reader sets it from the buyer's words; the menu planner sets it on recipe lines | `src/tta/contracts/request.py`, `src/tta/agent/prompts.py`, `rules_reader.py`, `schema.py`, `src/tta/menus/needs.py` | 1.0 | computer-science member | 20% precision | F4; same parsing step as P9a |
| F6 | The cheaper suggestion under the four conditions, as one extra line of the offer | `src/tta/offers/planning.py`, `options.py`, `src/tta/contracts/offer.py`, the offer page | 1.5 | computer-science member | 20% precision; 30% demo; Valio's goal | F3; P8 for how it is confirmed |
| F7 | Profile settings and the P-05 scope SAME_FORMULA | `src/tta/contracts/policy.py`, `src/tta/policy/profiles/*.yaml`, `rules.yaml`, `facts.py` | 0.75 | biomedical member | 20% autonomy and controls | F4 |
| F8 | The formula on the pages: two columns of numbers, the differences marked; the assumptions page and `docs/ASSUMPTIONS.md` name the tolerances as ours | `src/tta/ui/`, `docs/ASSUMPTIONS.md`, `AIMO/SPEC.md` | 1.0 | biomedical member | 15% openness; 30% demo | F3 |
| F9 | Ingredient text beyond the fat source: first ingredient and functional additives named in the sentence, with the Finnish words | `src/tta/offers/formula.py` | 1.0 | biomedical member | 20% precision | F2 |
| F10 | A script that prints the figure for the pitch from the product file: of 249 listed pairs, how many keep the formula | new script, `docs/PITCH.md` | 0.5 | biomedical member | 15% openness | F2 |
| F11 | One request line filled by several products: say when they differ in formula | `src/tta/offers/options.py` | 0.5 | computer-science member | 20% precision | F2; P9a's outcome |

Cut first, in this order: F11, F9, F10, F7, F8, F6, F5. Without F5 the formula still matters by product type (source c), which covers cream, butter, cheese, eggs, flour and sugar with no model call.

## 6. What changes in the demo
- **A new exception to show (15% criterion).** "100 L of Arla Pro whipping cream" (`469346`, 48 L confirmed). Today: 52 L of the 15% vegetable blend `463975`, verdict AUTO, €411.12, and the sentence "Valio does not list it as a substitute." After F1 to F4: `463975` is no longer the suggestion; it is shown flagged with "Different formula: fat 15 g, not 36 g; saturated fat 1.3 g, not 23 g; carbohydrate 4.9 g, not 2.9 g per 100 g; its ingredient list names a vegetable oil", and rule F-10 asks for a yes. 15 of the 52 other creams keep the formula of `469346` (draft measure); among them `464727` Arla whipping cream 35% with 37 L confirmed and `464194` Valio whipping cream 38% with no confirmed quantity. Which one the new ranking picks was not built, so it is not measured.
- **Scenario 3 (`473609`, barista oat drink) gains a line.** Rank 1 today is `471690` "Delight", listed by Valio, and the sentence speaks of pack and price. With the measure it reads "fat 1.5 g, not 3.0 g". The two candidates closest in formula, `471881` (same product, 0.5 l) and `464320` Oatly iKaffe (other brand, within tolerance), are the two the allergen rule fails (run `run_s3.py`: `passes` false for both). One screen shows both checks and their order.
- **Scenario 1, the main demo.** The cheaper option (€1,010.00, `464306`) against the confirmed one (€2,580.64) can say: "same formula within our tolerance as `469363` (fat 1.5 g against 1.5 g, protein 3.0 g against 3.2 g, carbohydrate 3.1 g against 3.0 g per 100 ml), other brand; €1,570.64 less." That is the saving sentence Valio's goal asks for. The confirmed option mixes three formulas (fat 1.5, 0 and 3.0 g: `469363`, `462775`, `463380`); P9a's change to "milk" will alter that option.
- **With F6:** asking for `464727` Arla whipping cream shows one line below the option: "`465193` Valio food service whipping cream keeps the formula (fat 35 g against 35 g, saturated fat 21 g against 23 g) and costs €3.33 per litre against €7.37: €404 less on 100 L. Other brand. Valio does not confirm the quantity in stock."
- **A pitch figure:** "Valio lists 249 substitutes. By the nutrition label 101 keep the formula, 71 do not, 77 cannot be compared. Inside one category number only 11% of cream pairs keep it."

## 7. Risks and what not to do
- **Do not let the formula outrank the dietary claims or the allergens.** 15 listed pairs keep the formula and lose a dietary claim. `469126` → `469050` is the example to put in a test.
- **Do not present the tolerances as Valio's or as law.** They are ours. The two EU references in section 4.2 are from memory and unverified; cite them only after a member has read the source.
- **Do not say "identical".** The panel misses heat treatment, protein type and stabiliser dose. Say "the data shows no difference".
- **Do not hide candidates with the formula gate.** A cook may accept a blend in a gravy; the recipe table already says so (`recipes.yaml:42-43`). Flag and ask.
- **Do not derive a product line from the name.** It is free text. Brand plus formula does the job.
- **Do not use the structured `ingredients` array, and do not compare energy.**
- **The draft measure ignores the basis (g against ml).** The real one must return "not known" when the bases differ.
- **A strict tolerance can cry wolf.** `475224` Fazer Aito Professional Barista comes out different from `473609` on sugars (1.6 against 3.5) although both are barista drinks with 3.0 g of fat. The sentence shows the numbers, so the user can overrule in one click; the full version orders the "different" candidates by how far they are.
- **Four agents touch `substitutes.py` and `planning.py`** (P7, P9a, P9b, this one). Give the two files one owner.
- **F6 without F5 can annoy:** a cheaper line on every option. Show at most one, the largest saving.

## 8. Questions
For the team:
1. DECISION 3: did the mentor mean the same brand and formula, or the formula with the brand as its sign?
2. DECISION 5: are VEGETARIAN and VEGAN in the safety gate, or only when the buyer asks for them?
3. Who answers a formula question in a kitchen: the purchasing manager, or a new role for the chef?

For Valio, in the booth shape:
- **Q-F1. Is a listed substitute safe to use in a recipe?** Context: you said a substitute must keep the formula where the formula matters. What we did: we compared the nutrition labels of your 249 listed pairs. What we got: 71 differ by more than 15% or 1 g on fat, saturated fat, protein, carbohydrate, sugars or salt. Example: `473609` Oddlygood Barista oat drink lists `471690` Barista Delight, with fat 1.5 g, not 3.0 g; `464249` cooking cream 15% lists `463797` at 10%. The ask: is a listed substitute meant as "the same for a recipe" or as "the same kind of product"? If nobody answers: a listed substitute gets no exemption; the formula check applies to it and the difference is shown.
- **Q-F2. How close is close enough?** Context: we need a tolerance. What we did: 15% or 1 g per nutrient. What we got: whipping creams of 35, 36 and 38% count as one formula; 30% and 15% do not. The ask: do your sales people use a rule of thumb, for example fat within 2 points? If nobody answers: our values, labelled ours.
- **Q-F3. May the agent point to a cheaper product of another brand?** Context: your goal is winning customers. What we did: we looked for cheaper products that keep allergens, dietary claims and formula. What we got: `464727` Arla whipping cream €7.37 per litre against `465193` Valio food service whipping cream €3.33, same formula within tolerance. The ask: would you want that suggestion made unasked, across brands? If nobody answers: yes, across brands, and a buyer profile can restrict it to the same brand.
