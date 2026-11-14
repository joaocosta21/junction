# P7 — Category numbers: where we read the digits as levels, what the data says, what replaces it

Topic: Valio's answer V7 ("sap code semi random?? he doesnt know"). Written 14 Nov, 15:10. No code or document was changed.

How every figure was made. "Catalog" means all 17,546 products of `valio_aimo_junction26_product_data.json`. "Capture" means the 769 products of `fixtures/valio/2026-11-14-demo` in replay. Scripts are in the scratch folder `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/P7/`: `analysis.py` (pairs of products and of categories), `analysis2.py` (Valio's listed pairs, candidate sources), `subs_run2.py` and `subs_analyze.py` (the substitute search over the capture).

## 1. In five lines
1. Two places read a category number as levels: the substitute search (`CATEGORY_TIERS = ((5, 0), (4, 1), (3, 2))`, `src/tta/offers/substitutes.py:45`, through `Catalog.same_category(id, digits)`) and the public search field `category_prefix` (`src/tta/contracts/request.py:121`). Product types, the policy scope `SAME_CATEGORY`, the search's narrowing and the offer lines use all 5 digits and are safe whatever the digits mean.
2. Catalog: a shared prefix marks a neighbouring shelf, not the same product. Two products of different categories that share the first 4 digits have an English name word in common in 20.6% of pairs (first 3 digits only: 22.5%), against 39.2% inside one category and 2.7% for any two products.
3. Capture, today: under `hotel-kitchen` 47 of 769 substitute searches go past the category, and in 31 the only candidates shown that can be ordered come from a shorter prefix (coconut cream for milk powder). Under `allergy-ward` 572 go past it and 497 are answered only from a shorter prefix (rice drink for yoghurt).
4. Recommendation: remove both shorter tiers (1 hour). Candidates are the pairs Valio lists, then the same 5-digit category. In the minimum version nothing replaces the fallback: the answer is "no substitute can be ordered, a person chooses". Another kind of product for the same job is a stated rule of ours with a reason (the `alternatives` of `src/tta/menus/recipes.yaml`), never a digit.
5. Keep `category_prefix` and `category_distance` in the public interface and describe both as opaque (decisions D3, D4). Scenarios 1, 2 and 3 do not change.

## 2. What exists today

### 2a. Every use of a category number
"5 digits" is a group label and is safe. "Prefix" reads the digits as levels.

| Where | What it does | Reads |
|---|---|---|
| `src/tta/catalog/catalog.py:36-39` | Index of products by full category | 5 digits |
| `src/tta/catalog/catalog.py:79-97` · port `src/tta/contracts/ports.py:93-95` | `same_category(product_id, digits)`: products whose category starts with the first `digits` digits (1 to 5, `catalog.py:23,84`) | **Prefix** when `digits` < 5 |
| `src/tta/offers/substitutes.py:45` | `CATEGORY_TIERS = ((5, 0), (4, 1), (3, 2))` | **Prefix** (4 and 3) |
| `src/tta/offers/substitutes.py:161-176` (`_pool`) | Pool = listed pairs, then the three tiers (`:167-168`), 999 at most | **Prefix** |
| `src/tta/offers/substitutes.py:226-242` (`_shown`) | Opens the next tier until 3 candidates can be ordered (`:230-233`, `ENOUGH_ORDERABLE` `:41`); shows 10 unlisted at most, those that can be ordered first | **Prefix** |
| `src/tta/offers/substitutes.py:154-158` (`substitute_distance`) | Distance of a listed pair: 0, 1, 2, or 3 "outside" | **Prefix** |
| `src/tta/offers/substitutes.py:257-266` (rank key) | `each.distance` is the third key, before "listed by Valio" | **Prefix** (as an order) |
| `src/tta/offers/planning.py:227,280` | An offer's stand-in line is the first ranked candidate that can be ordered; `category_distance` goes on the line | Prefix, through the search |
| `src/tta/contracts/offer.py:40-43,224` | Public field `category_distance`: "0 same 5-digit category, 1 same first 4, 2 same first 3, 3 listed from further away" | **Prefix** (as a statement) |
| `src/tta/offers/substitute_wording.py:27,68-69` | "same category"; "it is from category X, not Y" when distance > 0 | 5 digits |
| `src/tta/policy/rules.yaml:51-56,122,382` · `src/tta/policy/facts.py:46-48,319-324` | `SAME_CATEGORY` means `category_distance == 0`; anything else is `OUTSIDE` and goes to a human (P-05) | 5 digits |
| `src/tta/policy/profiles/hotel-kitchen.yaml:19` · `src/tta/ui/kitchen_page.py:62` | Profile setting and its label "Any product of the same category" | 5 digits |
| `src/tta/catalog/product_types.yaml` (31 `categories:` lists) · `src/tta/catalog/search.py:129` | A type lists full codes; membership is exact. Counted: 40 entries, 37 distinct codes, all 5 digits, all in the catalog | 5 digits |
| `src/tta/contracts/request.py:121` · `src/tta/catalog/search.py:63,130` | Public query field `category_prefix`: `product.category.startswith(prefix)`, any length. It has no description in the OpenAPI document. Giving it switches off the narrowing (`search.py:85`) | **Prefix** |
| `src/tta/catalog/search.py:145-160,211` · `src/tta/contracts/product.py:39,96` · `src/tta/contracts/offer.py:55` | Narrowing to the main categories; `Product.category`, `SearchResult.categories`, `OfferLine.category` | 5 digits |
| MCP `search_products` (`src/tta/api/mcp_surface.py:192`) and REST `POST /v1/products/search` (`src/tta/api/routes.py:136-144`) | Take `ProductQuery`, so `category_prefix` is public on both | **Prefix** |
| MCP `find_substitutes` (`mcp_surface.py:209-215`) and REST `POST /v1/products/{id}/substitutes` (`routes.py:158-169`) | Return the tiers and `category_distance` | **Prefix**, through the search |
| `src/tta/ui/templates/_result.html:192` | Heading "Other products of the same category" over every unlisted candidate | **Wrong today** when a tier of 4 or 3 digits is shown |
| `scripts/capture_valio.py:80,111` · `README.md:106` | `--category-prefix 104` picks the ids of a capture | Prefix, tooling only, harmless |
| Tests | `tests/catalog/test_substitutes.py:32-51` (5, 4, 3 digits), `tests/catalog/test_search.py:186,202,236,263-264`, `tests/api/test_limits.py:176` (`category_prefix`), `tests/policy/test_rules.py:237-240`, `tests/policy/test_names.py:125` (distance 1 and 2), `tests/ui/conftest.py:132` | — |

### 2b. The data test (catalog)
The 349 codes are all 5 digits. They form 129 groups on 4 digits (69 hold more than one category: 289 categories, 14,659 products), 43 on 3 digits, 18 on 2 and 9 first digits.

Pairs of products, by how many leading digits of the category they share. Each row is 200,000 pairs drawn evenly from all pairs of that row (seed 7). A "name word" is a word of the English name with 3 letters or more, no digit, not a word of the product's brand.

| Pair | Pairs in the catalog | Share a name word | Same brand | Same allergen codes | Median energy gap (kJ/100 g) |
|---|---|---|---|---|---|
| Same 5 digits | 1,008,877 | 39.2% | 18.7% | 51.7% | 187 |
| Same first 4, other 5th | 2,170,147 | 20.6% | 9.8% | 44.3% | 316 |
| Same first 3, other 4th | 5,779,847 | 22.5% | 2.4% | 30.1% | 495 |
| Same first 2, other 3rd | 10,004,145 | 2.7% | 1.5% | 37.3% | 776 |
| Same first digit only | 18,651,436 | 1.5% | 1.4% | 42.0% | 623 |
| Other first digit | 116,307,833 | 1.4% | 0.3% | 33.7% | 659 |
| Any two products | 153,922,285 | 2.7% | 0.9% | 35.2% | 631 |

What it shows:
- The code is not random. Sharing 3 digits is far above chance.
- The 4th digit is not a reliable level for names: 20.6% (first 4) is no higher than 22.5% (first 3). It does add brand, allergen and energy likeness.
- Even at 4 digits, a pair is half as alike as inside a category. Of the 289 categories that have a sibling on 4 digits, 119 have such a sibling as the category with the most similar names (cosine of name-word counts over all 60,726 category pairs). For 122 of the 349 the most similar category does not share even the first 2 digits.
- This agrees with `AIMO/docs/SCHEMA-AND-CODES.md:557` (§5.1): "Treat sibling codes as format variants of one subject, not interchangeable." Its §5.2 then concludes the opposite for substitutes; see section 9.

**The sentence a judge can check:** over the whole catalog, two products from different categories that share the first 4 digits have an English name word in common in 20.6% of pairs, against 39.2% inside one category and 2.7% for any two products.

Five prefixes where the grouping holds (same subject, another format):
| Prefix | Products |
|---|---|
| `4180x` | 41800 "36xFazer Pätkis ice cream stick 39g/0.6dl" · 41801 "6x Jymy Organic ice cream Vanilla 500ml" |
| `1059x` | 10590 "Kieku Barn Eggs L180 12300g" · 10592 "Danaeg Scrambled egg mix 10 kg from barn eggs" |
| `1050x` | 10500 "Valio Luomu™ butter 200 g" · 10501 "Lurpak butter portion 100 pcs x 8 g" · 10502 "Lieksan Barbeque butter flavoured butter 80g" |
| `6323x` | 63230 "Duni 24cm 2-ply yellow napkin 300pcs" · 63231 "Duni 33cm 2-ply napkin black 125pcs" · 63235 "Duni 40cm 3-ply bordeaux napkin 125pcs" |
| `1742x` | 17421 "POTATO WASHED 1KG" · 17422 "Maatilan Mash potato peeled 10 kg" · 17423 "JEPO Cooked baked potato 3kg" |

Five where it clearly does not:
| Prefix | Products |
|---|---|
| `2260x` | 22600 "Meira Salt iodised 1kg" · 22601 "Meira Vanilla sugar 700g", "Dr. Oetker Candied lemon peel 100 g" |
| `2139x` | 21390 "GoGreen Red Lentils 400 g" · 21391 "Tuoppi 1 L Kotikalja malt drink extract" · 21393 "Vegesun Pea protein mince 2kg" · 21394 "Mestari 20kg Instant Mashed Potato powder" |
| `6327x` | 63270 "PIIPPO 200M COTTON CORD FOR MEAT" · 63271 "Fredman coffee filter 90mm 250 pcs x4" · 63272 "Fredman cling film for dispenser 45cmx300m x 3rolls" · 63273 "LOOK® Roasting bag M 25cmx38cm 10pcs x 24" |
| `2140x` | 21403 "Biotta Carrot juice 500ml organic" · 21402 "Valio raspberry-peach soup with fiber 1 kg, no added sugar" · 21405 "24 x Warsteiner Premium Fresh alcohol-free beer 0,0% 0,33 l bottle box" |
| `1040x` (our demo) | 10400 "Arla whole milk 10 L novobox" · 10401 "Valio whipping cream 20 l novobox lactose free" · 10402 "Alpro Soya drink, vanilla 1L" · 10404 "Dovgan Condensed milk, sweetened 1000g/761 ml" · 10405 "Valio skimmed milk powder instant 10 kg" |

On 3 digits: `105xx` holds butter (10500), olive oil (10531) and eggs (10590). `187xx` holds salmon (18701), pork (18710), beef (18720) and chicken (18750). `225xx` holds tea (22530) and cocoa powder (22540).

**Valio's own pairs.** 250 pairs on 189 products. One is `471661` → itself. Of the other 249: 229 share all 5 digits, 11 the first 4, 5 the first 3, 2 the first 2, 2 nothing. (`AIMO/FINDINGS.md:98` says 230 because it counts the self pair, and it leaves out the last 4. The comment at `substitutes.py:46`, "4 of the 249", is right.)

The 20 pairs that leave the category, and what they share: a name word in 17, the brand in 6, the allergen codes in 13; 9 change the sales unit.
| Digits shared | Pair |
|---|---|
| 4 | `461110` Pineapples Gold (17415) → `461078` Nectarine (17414) |
| 4 | `461480` Myllyn Paras pie strawberry-rhubarb (41765) ↔ `461927` Myllyn Paras pie berry mix (41763), listed both ways: 2 pairs |
| 4 | `462398` Saarioinen Orange marmalade 6 kg (21452) → `471775` 12 x Saarioinen Orange marmalade 230 g (21450) |
| 4 | `464237` Valio coffee milk 1 l lactose free UHT (10400) → `466238` 5 x Arla Café 1 L 10% lactose free cream (10401) |
| 4 | `465655` Rynkeby Lingonberry juice drink concentrate 10 L (21401) → `465623` 12 x Bonne Cranberry lingonberry Juice 1 L (21400) |
| 4 | `469312` Kung Markatta Organic Lemon juice 1 L (21403) → `467809` DeliMax Lemon juice concentrate 5 L (21401) |
| 4 | `469782` Vaasan Wheat rye roll 40x70g (41760) → `462418` Schulstad Rustic Multigrain roll 40x73g (41761) |
| 4 | `470463` Rynkeby orange-sea buckthorn shot 1 L (21400) → `476024` Greenfinns tyrnitäysmehu 1 L and → `469486` Biona Organic Carrot juice 750 ml (21403): 2 pairs |
| 4 | `471395` Vaasan Small Cinnamon bun 90x55g (41765) → `471018` Vaasan Small Cinnamon bun 80x40g (41764) |
| 3 | `460211` White cabbage Finland kg (17404) → `467530` SallaCarte Cabbage shredded 1 kg and → `467549` Cabbage grated 1 kg (17443): 2 pairs |
| 3 | `460352` Spring onions bunch 100 g (17405) → `460469` Chives 100 g bunch (17451) |
| 3 | `467200` SallaCarte Red paprika shredded 1 kg (17443) → `460239` Capsicum red (17406) |
| 3 | `474438` Bazooka Juicy Drops Mallows 100 g (52208) → `473065` 10 x Haribo Chamallows 250 g (52210) |
| 2 | `466300` Lagerblad pancake carrot-spinach (41753) → `471376` Lagerblad Pancake vegan (41830) |
| 2 | `467859` Lagerblad Quark pancake (41755) → `472587` Lagerblad American pancake (41830) |
| 0 | `469442` Vegem seitan kebab 2 kg (17306) → `471790` 5x MUU Vebab Flake 1 kg frozen (41753) |
| 0 | `476428` Octopus raw 1 kg (41721) → `469726` Nuchar 500 g octopus tentacle (18705) |

These follow the product (cabbage, pancake, octopus, marmalade) across fresh, prepared and frozen codes. Each is a choice somebody at Valio made for one product. We already take them first.

### 2c. What the 4- and 3-digit tiers do today (capture, replay)
Method: `tta.offers.substitutes.find_substitutes` (2,307 searches: 769 products, two queries for the hotel, one for the ward; the hotel's figures are the same with and without the date), the function behind `POST /v1/products/{id}/substitutes` (`src/tta/api/service.py:161-166`), for each of the 769 products, with `needed_by` 2026-11-16 and no quantity. Called directly because the route allows 20 lookups a minute per visitor (`src/tta/api/limits.py:65`); for the first product the route gave the same candidates. The capture holds every product of `104xx`, so all three tiers are measured for dairy. For beef (18720) no search left the category, so the 3-digit tier towards fish, pork and chicken (not in the capture) was never used.

| | `hotel-kitchen` | `allergy-ward` (excludes milk and gluten) |
|---|---|---|
| Searches | 769 | 769 |
| Go past the 5-digit category | 47 (38 show first-4 candidates, 9 show first-3) | 572 (552 show first-4, 336 show first-3) |
| The only candidates shown that can be ordered come from a shorter prefix | 31 | 497 |
| Of those: the category and the listed pairs hold none that can be ordered (exact, every candidate judged) | 20 | 497 |
| Of those: the category holds 1 or 2 that can be ordered, pushed off the list of 10 by shorter-prefix candidates that rank higher | 11 | 0 |
| The best-ranked candidate that can be ordered comes from a shorter prefix | 34 | 518 |
| Shorter-prefix candidates shown / of them can be ordered | 405 / 394 | 4,840 / 3,039 |
| Of those shown: share a name word with the original / same brand | 37% / 27% | 14% / 2% |
| Same-category candidates shown, for comparison: name word / brand | 67% / 47% (7,227 shown) | 32% / 20% (2,850 shown) |
| Without the two tiers: searches with 0 / 1-2 / 3 or more candidates that can be ordered (exact) | 20 / 27 / 722 | 497 / 75 / 197 |

Under `hotel-kitchen` the 47 are thin categories: milk powder 10405 (14 of 14 searches), soft-ice mixes 10432 (16 of 16), 10418 (4 of 4), 10431 (4), 10412 (4), 10413 (3), 10419 (1), and the soy yoghurt filed under milk (1). Under `allergy-ward` all 474 searches on a product of ten dairy categories (10400, 10401, 10404, 10405, 10411, 10412, 10419, 10430, 10431, 10432) leave the category and find nothing there that this buyer can order. The cause is the profile's exclusion of milk and gluten (`src/tta/policy/profiles/allergy-ward.yaml:17`): for originals in 10400, 10401, 10412 and 10430, 29,015 of the 35,649 same-category candidates that cannot be ordered carry the reason `ALLERGEN_DECLARED`, and 6,182 `SUBSTITUTE_ADDS_ALLERGEN`.

Examples, good:
- hotel: `469216` Valio Eila PRO lactose free whole milk powder 25 kg → rank 3 `464306` Valio Eila semi skimmed milk drink 1 l lactose free (first 4). Same brand, keeps lactose-free, liquid for powder.
- hotel: `465122` AIMO crème fraîche 2 kg 28% lactose free → rank 3 `464608` AIMO Turkish yogurt 5 kg 10% lactose free (first 4). Same brand and claims; a cook may accept it cold.
- ward: `469363` Arla lactose-free milk → rank 1 `473424` Alpro Rice drink 1 L (first 4). What a milk-free diet would take, reached because 10402 happens to sit next to 10400.

Examples, bad:
- hotel: `469148` Valio skimmed milk powder high heat 20 kg → rank 1 `464217` Spice Up! Coconut cream 165 ml (first 4).
- hotel: `467622` Flora Professional Plant Cooking 15% 1 L → rank 1 `465122` AIMO crème fraîche 28% (first 4). It loses `VEGAN`, `FREE_FROM_LACTOSE` and `FREE_FROM_GLUTEN`.
- hotel: `471582` Oatly Soft serve mix 1 L → rank 1 `472145` Oatly No Sugars Oat Drink 1 L (first 3).
- hotel: `472516` Oddlygood Soygurt 400 g, filed under milk → rank 1 `464217` Spice Up! Coconut cream 165 ml (first 4).
- ward: `460700` Salakis Turkish Yoghurt Natural 1 kg → rank 5 `467622` Flora Professional Plant Cooking 15% (first 4), rank 6 `473424` Alpro Rice drink 1 L (first 3).
- ward: `460525` Lieksan Pasha curd 90 g → rank 5 `473424` Alpro Rice drink 1 L (first 3).

The allergen rule cannot stop these: coconut cream adds no allergen to milk powder. Only the kind of product is wrong. All of them are `OUTSIDE` for the policy, so none can be ordered without a human today (P-05).

## 3. What Valio's answer changes
- **V7:** nobody at Valio confirms that the digits are levels. `docs/ASSUMPTIONS.md:26` says the tiers change if "Valio explains the code hierarchy". Valio did not. The tiers are now an assumption with no owner.
- **V10** (same brand or formula) and **B5** ("no be explicit": coffee milk is not milk) both ask for candidates narrower than a category. A prefix goes the other way.
- **V5** ("if you are not sure you need to flag it"): "no substitute, a person chooses" is the flagged answer. Rice drink for yoghurt is a guess.
- **V8** (a human confirms every order) and P-05 mean the tiers never fed the autonomous path. Removing them costs nothing on the 20% autonomy criterion.
- The data does not rescue the tiers: a prefix is a neighbouring shelf (2b), and what the tiers return is another kind of product in most cases (2c).

## 4. Options and recommendation

Sources tested against Valio's 249 pairs, the only ground truth in the data on what Valio calls a substitute (catalog; pool = median number of candidates for the 188 products that list a pair):

| Source of candidates | Pairs found (of 249) | Of the 20 cross-category pairs | Median pool |
|---|---|---|---|
| Same 5-digit category | 229 | 0 | 76 |
| Same first 4 digits | 240 | 11 | 260 |
| Same first 3 digits | 245 | 16 | 672 |
| Same product type (our table: 31 types, 37 of 349 categories, 2,864 products) | 83 | 0 | 0 |
| Same category and same product type, when the original has one | 229 | 0 | 76 |
| At least 1 shared name word, whole catalog | 216 | 17 | 302 |
| At least 2 shared name words, whole catalog | 136 | 6 | 11 |
| 10 nearest by name words, whole catalog | 135 | 7 | 10 |
| Same category and at least 1 shared name word | 199 | 0 | 18 |

No automatic source reaches the cross-category pairs without a pool of hundreds. The listed pairs themselves are always in the pool whatever their category (`substitutes.py:165-166`).

| Option | What | For | Against |
|---|---|---|---|
| **A. Nothing replaces the tiers** (recommended, minimum) | Listed pairs, then the same 5-digit category. When none can be ordered: say so, a person chooses | 1 hour. No unverified assumption. No wrong-kind candidate. Keeps all 249 of Valio's pairs | 20 hotel searches and 497 ward searches of the capture end with no candidate that can be ordered |
| B. Keep the tiers, label them "nearby code, not a product relation" | No code | 0 hours | Keeps offering rice drink for yoghurt; the page heading stays wrong; contradicts V10 |
| C. A stated table of ours: "this product type can be replaced by that one, for this reason" | The `alternatives` idea of `src/tta/menus/recipes.yaml:12-14`, moved to the product-type table: `milk` → `plant_drink` "for a buyer who excludes milk; it is not milk" | Gives the ward its milk-free answer on purpose, with a reason a biomedical member writes. Always a human's decision, as F-09 already is | 2.5 hours. Covers only the types we write. Overlaps P10 |
| D. Shared name words across the catalog | A similarity search | Finds 17 of the 20 | Pool of 302; "red", "bunch", "lactose" match; cannot be verified by midnight |

**Recommendation: A now. C only if the team wants the ward's "instead of milk" in the demo, and it is the first thing to cut.**

- **DECISION D1.** Remove the first-4 and first-3 tiers. Recommended: yes.
- **DECISION D2.** What replaces them. Recommended: nothing (A). Otherwise C. Not D.
- **DECISION D3.** `category_prefix`. Recommended: keep the field and its behaviour, add the description it lacks: "Leading digits of Valio's category code. A filter on the code as text. The codes are Valio's SAP numbers; Valio does not document levels and we do not assume any." Renaming or removing it changes the OpenAPI document, the MCP tool and 5 test call sites for no score.
- **DECISION D4.** `category_distance`. Recommended: keep the field; it takes two values, 0 (same 5-digit category) and 1 (another category, which only a pair Valio lists can be). A rename to a boolean touches stored offers, the page and the tests.
- **For P10 (ranking is theirs).** The rank key puts category before "listed by Valio" (`substitutes.py:257-266`): a pair Valio lists from another category ranks after every unlisted product of the same category. Also for P10: Valio's own pairs keep the brand in 104 of the 173 pairs where both brands are known, share a name word in 216 of 249 and declare the same allergen codes in 187 of 249.

## 5. Work items
Minimum version first (P7-1 to P7-3: 2 hours). Cut order: P7-7, P7-6, P7-5, P7-4.

| Id | What | Files | Hours | Who | Criterion | Depends on |
|---|---|---|---|---|---|---|
| P7-1 | Remove the two shorter tiers. Unlisted candidates come from the same 5-digit category only. `substitute_distance` returns 0 or 1. A test: no unlisted candidate of another category is ever returned | `src/tta/offers/substitutes.py` (`:3-4,40-47,154-176,226-242`), `tests/catalog/test_substitutes.py`, `tests/offers/` | 1.0 | Computer-science member | 20% precision; 15% exceptions; 15% openness | D1 |
| P7-2 | Contract texts: `category_distance` (two values), a description for `category_prefix`, the two docstrings that say "category" | `src/tta/contracts/offer.py:40-43,224`, `src/tta/contracts/request.py:121`, `src/tta/api/routes.py:142`, `src/tta/api/mcp_surface.py:192` | 0.25 | Computer-science member | 15% openness | D3, D4 |
| P7-3 | Correct the document lines of section 9 | 11 documents | 0.75 | A biomedical member | 15% openness (visible assumptions) | D1 |
| P7-4 | One sentence when no candidate can be ordered: "Valio lists no substitute that can be ordered and no other product of category N can be ordered now. A person chooses." On the result and the page | `src/tta/offers/substitutes.py` (`_shown` notes), `src/tta/ui/templates/_result.html:186` | 0.5 | A biomedical member | 15% exceptions; 20% controls | P7-1 |
| P7-5 | `same_category(product_id)` without `digits` | `src/tta/contracts/ports.py:93`, `src/tta/catalog/catalog.py:23,79-97`, `tests/ui/conftest.py:132`, `tests/catalog/test_loader.py:174-193`, `tests/catalog/test_substitutes.py:32-51` | 0.5 | Computer-science member | 15% openness, small | P7-1 |
| P7-6 | Inside the category, keep only candidates of the original's product type when it has one (in 10400: milk, not sour milk, not the soy yoghurt). It loses none of Valio's 229 same-category pairs | `src/tta/offers/substitutes.py` (`_pool`), `src/tta/catalog/product_types.py` | 1.5 | Computer-science member; a biomedical member for the type entries | 20% precision | P10; the split of coffee milk out of `milk` (B5) |
| P7-7 | Option C: `alternatives` per product type, each with a reason, as a last tier that always goes to a human | `src/tta/catalog/product_types.yaml`, `product_types.py`, `substitutes.py`, `rules.yaml` (reuse F-09's shape) | 2.5 | A biomedical member writes the entries; computer-science member wires them | 15% exceptions; 20% precision (ward) | D2, P10 |

## 6. What changes in the demo
- **Scenarios 1 and 2:** nothing. They name no product by id, and a substitute is sought only for a named product (`src/tta/offers/planning.py:201-203`).
- **Scenario 3** (`473609` Oddlygood Barista oat drink, hotel): nothing. Measured: 13 candidates, 3 listed and 10 of the same category, none from a shorter prefix.
- **The dietitian's oat drink** (`469512`, ward): today 10 candidates, 7 of the same category and 3 from the first-4 tier (rank 7 is `467543` Flora Professional Plant Allpurpose 31%, a plant cream). After: 10 of the same category (the list holds 10 unlisted), of which 2 can be ordered; the 3 plant creams give way to 3 more products of the category. Measured with the date and no quantity: re-measure with the button's 100 L before changing `docs/DEMO.md`.
- **The page:** "Other products of the same category" becomes true in every case (`_result.html:192`).
- **A ward search on a dairy product** (for example `469363`): today 10 plant drinks and plant creams. After: the candidates of the category, each with its reason (it declares milk), none can be ordered.
- **A judge who asks "what if nothing in the category can be had?"** hears: Valio's own listed pairs are tried first and cross categories; after that we stop and hand over, because Valio could not tell us what a neighbouring code means, and we measured it (2b).

## 7. Risks and what not to do
- Do not say the digits are random. The data shows real grouping on 3 digits. Say: a prefix is a shelf, not a product.
- Do not present our measurement as Valio's taxonomy.
- Do not rename `category_prefix` or `category_distance` before the freeze.
- Do not build a name-similarity search in this round (option D).
- Thin categories lose candidates: 20 hotel searches of the capture end with none, and 27 with one or two. That is the honest answer, and P7-4 says it in one sentence.
- The ward loses the accidental "rice drink for milk". If that matters for the demo, it is option C, written on purpose.
- An old worktree copy, `.claude/worktrees/agent-a019def0889123585/AIMO/FINDINGS.md:36`, says "Category codes ARE hierarchical — at 4 digits". Do not copy from it.
- The capture tool's `--category-prefix` only selects ids. Leave it.

## 8. Questions
For the team: D1 to D4 above.

For Valio, one, in the booth shape:
- **Context:** every product has a 5-digit category number, with no names. You told us it is a SAP code and that its digits may mean nothing.
- **We did:** we compared products that share the first 4 digits with products of the same category, over all 17,546.
- **We got:** they share a name word in 20.6% of pairs, against 39.2% inside a category. Neighbouring codes hold neighbouring goods, not the same product.
- **Example:** 10400 is milk, 10401 cream, 10402 plant drinks, 10405 milk powder.
- **Ask:** "Your webshop shows a product tree. Is that tree available as data (code, name, parent)? If so we would use it instead of the digits."
- **If nobody answers, we build:** the category number as a label only; substitutes from your listed pairs and from the same category; nothing wider.

## 9. Document lines that state or imply levels (work item P7-3)
`README.md` states no hierarchy; its line 106 uses `--category-prefix 104` to pick a capture and needs no change. `AIMO/BOOTH-NOW.md:191-198` is João's file: the question is accurate and its answer line is empty.

| Line | Says now | Corrected sentence |
|---|---|---|
| `AIMO/PLAN.md:230` | "Candidates: same category → same first 4 digits → same first 3 digits; re-check availability of every candidate" | "Candidates: the pairs Valio lists, then the same 5-digit category. Nothing wider: Valio could not confirm that the digits are levels (14 Nov). Every candidate is re-checked for price, availability and allergens." |
| `AIMO/SPEC.md:183` | "…then the same 5-digit category, then the same first 4 digits, then the same first 3." | "**Candidates:** the pairs Valio lists (250 pairs on 189 products), then the other products of the same 5-digit category. The category number is a label: no shorter prefix is used. Every candidate is re-checked for price and availability." |
| `AIMO/SPEC.md:184` | "→ category distance →" | "→ same category →" |
| `docs/ASSUMPTIONS.md:26` | "Substitute tiers: the same 5-digit category, then the same first 4 digits, then the first 3 (labelled weaker)… Changes if: Valio explains the code hierarchy (Q11)." | "The 5-digit category number is a label. Substitute candidates are the pairs Valio lists and the other products of the same category; no shorter prefix is used. 'Same category' in a profile means the same 5 digits. Why: Valio called it a SAP code and could not say what the digits mean (14 Nov). Catalog: two products of different categories sharing the first 4 digits share a name word in 20.6% of pairs, against 39.2% inside a category and 2.7% for any two. Changes if: Valio publishes a product tree." |
| `docs/ASSUMPTIONS.md:126` | "What the category digits mean, and their names." | "The names of the categories. Valio could not say what the digits mean (14 Nov); we read the number as a label." |
| `AIMO/FINDINGS.md:98` | "230 pairs stay in the same 5-digit category. Of the other 20, 11 share the first 4 digits and 5 share only the first 3." | "229 of the 249 pairs between two different products stay in the same 5-digit category (230 of 250 with the pair of `471661` and itself). Of the other 20, 11 share the first 4 digits, 5 only the first 3, 2 only the first 2 and 2 none." |
| `AIMO/FINDINGS.md:99` | "Candidate substitutes: same category, then same first 4 digits, then same first 3 (labelled weaker)…" | "Take the pairs first. Other candidates: the same 5-digit category only, always re-checking availability and allergens." |
| `AIMO/WALKTHROUGH.md:492` | "…then products of the same five-digit category, then the same first four digits, then the same first three, until three can be ordered." | "**Candidates**, in order: the substitutes Valio itself lists for it (3), then the other products of the same five-digit category." |
| `AIMO/WALKTHROUGH.md:493` | "closer category" | "same category" |
| `AIMO/WALKTHROUGH.md:1168` · `AIMO/OPEN-QUESTIONS.md:201` | "Built while waiting: substitute tiers… the same first 4, and the same first 3, labelled weaker" | "Built: Valio's listed pairs come first, then the same 5 digits. The tiers on 4 and 3 digits were removed after Valio's answer of 14 Nov." |
| `AIMO/BOOTH-QUESTIONS.md:193` | Same sentence as `FINDINGS.md:98` | Same correction |
| `AIMO/BOOTH-QUESTIONS.md:203` | "If no answer, we build: substitute tiers — same category → same 4 digits → same 3 digits (labelled weaker)." | "Answered 14 Nov: a SAP code; the mentor did not know what the digits mean. We build: listed pairs, then the same 5-digit category, nothing wider." |
| `AIMO/docs/SCHEMA-AND-CODES.md:559` (heading of §5.2) | "Are the 5-digit codes hierarchical? — Yes, measurably" | "Do neighbouring codes hold similar products? More than chance, not enough to substitute" |
| `AIMO/docs/SCHEMA-AND-CODES.md:582` | "Confidence: HIGH that the codes are hierarchical…" | "The measurement shows that neighbouring codes hold more similar names than chance. It does not show that the digits are levels, and Valio could not confirm it (14 Nov)." |
| `AIMO/docs/SCHEMA-AND-CODES.md:584,638` | "A same-first-4-digits fallback is the next-best candidate generator…" · "justifying a same-first-4-digits substitution fallback" | "No prefix fallback is used." · "quantified (§5.2); it does not justify a substitution fallback." |
| `AIMO/docs/PRODUCT-DATA.md:819` | "…same category, then the same first 4 digits, then the same first 3 (§7)" | "…the same 5-digit category (§7)" |
| `AIMO/build/assumptions.md:155` | "the listed pairs plus the three category tiers" | "the listed pairs plus the same 5-digit category" |
| `docs/ARCHITECTURE.md:92` | "category neighbours" | "products of the same category" |
