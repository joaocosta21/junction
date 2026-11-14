# P9a — Product-type precision: "milk" is not coffee milk (answer B5)

Agent P9a, Saturday 14 Nov. No code, test, fixture or document was changed. Scratch scripts and their outputs are in
`/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/P9a/`.
Every count below is mine. "Catalog" means the whole product file (17,546 products, loaded once by `dump_types.py`).
"Pinned clock" means replay of capture `2026-11-14-demo` at `2026-11-14T02:52:45+02:00`, run through the brief's offline recipe.

## 1. In five lines
1. Valio answered B5 with "no be explicit": a buyer who asks for milk does not get coffee milk. Today type `milk` (78 products, catalog) holds 4 milks for coffee, and one of them is 565 of the 1,000 L of the main demo.
2. Measured at the pinned clock without the 4 coffee milks: option 1 becomes a partial fill, 435 L (43.5%) = 384 × `469363` + 51 × `462775`, €1,083.39, approval for P-01 and P-03. Option 2 is unchanged: 1,000 × `464306`, €1,010.00, quantity not confirmed.
3. Coffee milk is not the only case. A name term is a weak variant filter: "skimmed" finds 46 milks, 29 of them semi-skimmed. The rule-based reader cannot read "coffee milk" at all, and reads "barista oat drink" as any oat drink. `butter` holds a vegan block, `cream` holds a quark and a mousse.
4. Recommendation: a product type names one kind of product. A different kind is its own type (`coffee_milk`). A variant a buyer names (fat level, whipping or cooking) is a sub-type in the same table. An option may mix sub-types of the type asked for, and the product-type check says which ones it holds. It never crosses to another type without a label and a person.
5. Minimum (2 h): move coffee milk to its own type (0.5 h) and refresh the demo figures in tests and documents (1.5 h). First addition (0.75 h): one note on the offer that says coffee milk was left out and how to ask for it. Full: sub-types for milk and cream, the check that names them, and a labelled option "with a variant you did not ask for" that keeps a full 1,000 L option in the demo.

## 2. What exists today (verified)

**The type table.** `src/tta/catalog/product_types.yaml:21-31` defines `milk` as category `10400` without the terms "sour", "piimä", "coffee drink", "maitokahvi", "soygurt": 78 products, 30 with the claim `FREE_FROM_LACTOSE`. Its note says the 4 milks for coffee stay in (`462626`, `464237`, `473142`, `463380`). `docs/ASSUMPTIONS.md:50` says "Coffee milks stay in `milk`" and `tests/catalog/test_search.py:75-76` asserts it. A type has categories, name terms, exclude terms and claims and nothing else (`src/tta/catalog/product_types.py:25-38`); an unknown key in the file is refused. There is no notion of a variant.

**From a request line to an option.**
- `find_products` sends one query per line: type, name terms, claims, labels (`src/tta/offers/candidates.py:157-174`). Every product of the type is a candidate. The type filter is category + claims + name terms + exclude terms (`src/tta/catalog/search.py:113-135`). A name term matches the start of an English word or any part of the Finnish name (`src/tta/catalog/text.py:37-46`).
- A candidate drops out only for allergens, pack kind, the recording, pack size, availability state, a late date, the price, or confirmed-only (`candidates.py:393-403`). Nothing looks at what variant it is.
- The fill takes the cheapest single product that covers the quantity, else the cheapest products first, over all confirmed candidates of the line (`src/tta/offers/combining.py:71-104`, `planning.py:155-165`). This is how semi-skimmed, fat-free and Cafè milk ended up in one option.
- The product-type check asks the catalog whether each offered product is of the type asked for (`src/tta/offers/checks.py:109-117`). The candidates came from that same filter, so for a request by type it is always MET: "Every product offered is of the product type 'milk'." It says nothing about variants or a mix.
- The option summary counts products and does not name them: "3 confirmed products cover the 1,000 L asked for, for €2,580.64 before tax." (`src/tta/offers/options.py:178-186`). The page shows each line's product name (`src/tta/ui/templates/_result.html:106`) and the checks (`:134-139`). No mark says "this is a milk for coffee".
- No policy rule reads the product type or a variant. `src/tta/policy/facts.py:366-371` reads the product-type check only to word rule F-09.

**How the request is read.**
- The model may choose `product_type` only from the table's keys (`src/tta/agent/schema.py:84`, enum built from the table at `:104-107`). Rule 4 of the instruction tells it to put "a word that narrows the kind further" in `name_terms` (`src/tta/agent/prompts.py:33-36`). The recorded reading of scenario 1 is type `milk`, claim `FREE_FROM_LACTOSE`, no name term (`fixtures/agent/parse-scenario-1.json`).
- The rule-based reader takes its words from the same table: a type's key and its name terms are the buyer's words for it, its exclude terms rule it out, and the longest type named wins (`src/tta/agent/rules_reader.py:105-115`, `:170-177`). Only the one word before the type narrows it (`:303-308`).
- A new type key therefore reaches the model's schema, the instruction and the rule-based reader with no code change.

**What I measured on today's code.**

| Probe | Result | How |
|---|---|---|
| Rule-based reader, "200 litres of coffee milk by Monday" | Not read: "line 1 names more than one product type (coffee, milk)" | `RuleReader` on the real table |
| Rule-based reader, "200 litres of semi-skimmed milk" | type `milk`, name term `skimmed` | same |
| Rule-based reader, "100 litres of barista oat drink" | type `plant_drink`, name term `oat`; "barista" is dropped | same |
| `milk` + name term "skimmed" | 46 products: 16 skimmed, 29 semi-skimmed, 1 one-percent | catalog, the code's own matching rule |
| `milk` + name term "semi-skimmed" | 29 of the 35 semi-skimmed or low-fat milks | same |
| `milk` + name term "fat free" | 5 of the 24 skimmed or fat-free milks | same |
| `milk` + name term "coffee" | 3 of the 4 coffee milks (not Arla "Cafè milk") | same |
| `plant_drink` + name term "almond" | 5, one of them `474864`, whose Finnish name says soya ("soijajuoma") | same |

So a buyer who writes "skimmed milk" can be given semi-skimmed milk today, and the name-term check reads MET.

**What a request that names no variant gets today (pinned clock, today's table, `run_s2.py`).** In every row the product-type check reads MET and nothing says a variant was chosen or mixed.

| Request | Option 1 |
|---|---|
| Hotel, 200 L of "milk", no claim | 200 × `469363`, a **lactose-free** semi-skimmed milk drink, €496.00 (€2.48 per litre), verdict AUTO. Regular skimmed milk `469477` at €0.88 per litre is only the unconfirmed alternative. 55 of the 78 milks are past their cut-off |
| Hotel, 1,000 L of "milk", no claim | 132 × `463047` (whole, low lactose) + 384 × `469363` + 51 × `462775` + 433 × `463380` (Cafè milk) = €2,496.16 |
| Hotel, 50 L of "cream" | 50 × `463797` Arla Pro **cooking** cream 10 %, €165.50, verdict AUTO |
| Ward, scenario 2 as it is (200 L of a milk substitute) | 200 × `464013` Alpro No Sugars Soya drink, €402.00: one plain product. Of the 10 candidates that fit, 3 are barista and 2 are flavoured |
| Ward, scenario 2 with 1,000 L | Five products in one option: 1 × `460509` + 478 × `464013` (soya) + 319 × `464056` (**barista** soya) + 109 × `473424` (rice) + 93 × `465793` (**barista** almond) = €2,124.03 |

**Survey of type `milk` (78 products, catalog; classified by product name with `survey_milk.py`, "not stated" when the name says nothing).**

| Kind of variant | Count | Examples |
|---|---|---|
| Milk for coffee | 4 | `462626`, `464237`, `473142`, `463380` |
| Flavoured | 1 | `473142` (vanilla; also a coffee milk) |
| Fat: semi-skimmed or low-fat ("kevytmaito") | 35 | `469363`, `464306`, `463359` |
| Fat: skimmed or fat-free ("rasvaton") | 24 | `462775`, `463171`, `464401` |
| Fat: whole ("täysmaito") | 10 | `464073`, `462744`, `469181` |
| Fat: 1 % / 3 % / 1.5 % portion milk / not stated | 2 / 1 / 1 / 1 | `463290`, `476856` / `463335` / `463203` / `464473` |
| Heat treatment: UHT / ESL / not stated in the name | 17 / 12 / 49 | `463380` / `464179` / `463171` |
| Organic (label `EU_ORGANIC_FARMING`) | 11 | `462921`, `463313`, `463810` |
| Lactose: free / low / no claim | 30 / 2 / 46 | `469363` / `463047`, `469541` / `463171` |
| Portion pack by the catalog's rule (100 × 2 cl) | 1 | `463203` |
| Cartons of 0.2 to 0.25 L / 0.5 L | 5 / 6 | `463779`, `465283` / `464097`, `464440` |
| Boxes of 10 L / 20 L | 10 / 4 | `460396`, `463038` / `469209`, `476560` |
| Cartons of 1 L / 1.75 L | 44 / 8 | `469363` / `469119` |
| Milk drink for cooking, "Keittiön Kiehu" (use is my assumption from the name) | 1 | `464473` |

Of the 30 lactose-free milks: 4 for coffee, 16 semi-skimmed, 6 skimmed, 2 whole, 1 with 3 %, 1 portion milk; 15 UHT, 4 ESL; 1 organic.

**The other types the demos use (catalog, by product name; counts within one type can overlap where said).**

| Type | Products | What one key hides |
|---|---|---|
| `cream` | 44 | whipping 15 · cooking 17 (7 of them flavoured: smoked cheese, pesto, sweet chili …) · coffee cream 4 · low-fat cream 3 · spray cans sold by weight 3 (`462652`, `473847`, `474206`) · **not cream 2**: a layered quark `473205` and a protein mousse `473461`. Fat in the name: 10 % 6, 15 % 7, 38 % 1, none 30 |
| `plant_drink` | 51 | **only 19 are plain.** Barista or "for coffee" 25 · flavoured 17 (10 are both) · protein drinks 3 · one 20 ml portion pack `472270`. Base: oat 38, soya 9, almond 5, coconut 1, rice 1 (overlap) |
| `butter` | 20 | **a plant-based block with the claim `VEGAN`, `471792`** · clarified 2 (`472127`, `475708`) · brown butter `474681` · butter for laminating `464761` · unsalted 3, salted 8, salt not in the name 9 · lactose-free 8, low-lactose 10 |
| `yoghurt` | 150 | 25 say natural or unflavoured in the name, 125 do not · Greek or Turkish style 32 · drinking yoghurt 10 · one dessert with no "yoghurt" in its name `472914` |
| `quark` | 49 | 4 are not quark by name: 3 mousses (`467294`, `467300`, `468178`) and a pasha (`474706`) · 15 protein quarks |
| `beef_chuck` | 7 | one cooked sous vide `474242` · one Wagyu `469795` · all 7 sold by variable weight |
| `beef` | 149 | every cut from tenderloin to bones; the type alone names no cut |

## 3. What Valio's answer changes
- **B5, "no be explicit"** (`AIMO/BOOTH-NOW.md:310-311`). The note can be read two ways. (a) No; the agent must be explicit about what it offers. (b) No; the buyer must be explicit to get coffee milk. Both say: coffee milk is not offered for "milk" unless asked for. The design below serves both. **João should say which was meant.**
- **V10**: "lets say you want a normal milk it is fine but for cakes/things that require the formula the ingredient and chemestry can make a difference". I read this as: within plain milk the agent may choose, and where the use depends on the product (whipping or cooking cream, butter or a plant block) it may not.
- **V5**: "if you are not sure you need to flag it to the user". A variant the buyer did not name is such a case: say it, do not hide it.
- **The gap today**: the agent chooses a variant silently, mixes variants silently, and the only check on the type cannot fail.

## 4. Options and recommendation

**The rule I propose (answers "how exact must a match be").**
1. **Kind is exact.** A type holds one kind of product. A product a buyer would send back is not in it: it has its own type or none. It is never added to an option silently.
2. **A variant the buyer names is exact.** It is matched through the table (a sub-type), never through a loose word in the name.
3. **A variant the buyer did not name is the agent's choice, and the offer says so.** One option may mix sub-types of the type asked for; the product-type check names them.
4. **Crossing to another kind needs a label and a person.** It is a separate option, never rank 1 over a fitting one, and never ordered by the agent alone.

**DECISION D1 — is coffee milk its own type?** Recommended: yes, `coffee_milk` (4 products), left out of `milk` (74 products, 26 lactose-free). The offline run used the exclude terms "coffee milk", "kahvimaito", "cafè" in memory; "cafè milk" selects the same 4 products (checked on the names). It is data only. With it the rule-based reader reads "200 litres of coffee milk by Monday" as type `coffee_milk` and "200 l kahvimaito" too (run on an in-memory table). The alternative, keeping it in `milk` and marking it, contradicts the answer.

**DECISION D2 — how to represent variants.**

| Option | Cost | Trade-off |
|---|---|---|
| A. Name terms only (today) | 0 | Wrong on real names: "skimmed" returns 29 semi-skimmed milks; "barista" is dropped by the reader |
| **B. Sub-types in the same table**, each with `parent: milk` | data + one optional field | One dimension per parent (fat level for milk, use for cream). Model, reader and search pick them up from the table. Verified in memory: the Finnish terms "rasvaton", "kevytmaito", "täysmaito" select 24, 35 and 10 milks with no overlap, and the rule-based reader then reads "semi-skimmed milk", "skimmed milk", "whole milk", "whipping cream" and "cooking cream" as the sub-type with no name term |
| C. A general attribute model (dimension → value → terms) with request fields | contract, parser, instruction, reader, page | Most expressive, too much for tonight |

Recommended: B. Other dimensions already have a field: lactose-free is a claim, organic is a label, portion packs are the pack preference.

**DECISION D3 — may one option mix variants without saying so?** No. It may mix, and it says so. Measured cost of forbidding a mix in scenario 1 (pinned clock, coffee milk out): semi-skimmed alone 384 L (38.4%, €952.32), fat-free alone 51 L (5.1%, €131.07), whole milk no confirmed stock; mixed 435 L. Recommended sentence, on the product-type check, result still MET: "Every product offered is milk. The request names no fat level: this option holds semi-skimmed milk (469363) and skimmed milk (462775)." Do not use UNVERIFIED for this: it would change the ranking (`options.py:141-155`) for something that is not a doubt about data.

**DECISION D4 — how the offer marks a variant the buyer did not name.**

| Option | Cost | Trade-off |
|---|---|---|
| **a. The product-type check names the sub-types in the option** (D3) | 1.5 h | Visible on the page and in the API; no new concept |
| b. A separate labelled option for a sibling type, "With a variant you did not ask for: milk for coffee" | 3 h | Keeps a full 1,000 L option in the demo (today's €2,580.64 basket, now labelled and always for a person). New option kind, so contract, page and policy sentence change |
| c. A question to the user before any offer (as V5) | 2 h+ | One more round trip for every vague request; works against "least manual correction". V8 already puts a person on every order, so the confirmation screen (P8) is where the buyer corrects a variant |

Recommended: a. Build b only if scenario 1 stays a partial fill. P5 measured that it does: moving the clock back frees no confirmed stock, and P5 recommends keeping the recording's own instant (`AIMO/build/replan/P5-clock.md`, five lines 2 and 5, and `:58`, `:94`). So b is worth its 3 hours if the team wants a full 1,000 L option in the main demo. Not c.

**DECISION D5 — how a buyer says a variant is fine.** (1) By naming it: "coffee milk" is type `coffee_milk`; "semi-skimmed milk" is the sub-type. Works with D1 and D2 for the typed request and the rule-based reader (run in memory); for the model it follows from the key list (not run: no outside call). (2) With option b, by approving the labelled option; the approval is in the audit trail. (3) A request field `also_accept` (type keys) or a buyer-profile setting: full version, first to cut. `LineProposal` already has the pattern for a field with a default that old recordings lack (`src/tta/agent/parser.py:100-101`).

**DECISION D6 — the default when the request says only "milk".** Plain milk of any fat level, any heat treatment and any brand, in bulk packs (the pack default for litres already leaves out `463203`). Never coffee milk, never flavoured. Open point: `milk` also holds 26 lactose-free and 2 low-lactose products that a plain "milk" request can be filled with. Measured: 200 L of "milk" gets a lactose-free milk drink today. See question 2 for Valio.

## 5. Work items

| Id | What | Files | Hours | Who | Criterion | Depends on |
|---|---|---|---|---|---|---|
| **M1** | Coffee milk out of `milk` (74), new type `coffee_milk` (4); update the entry's note; recount | `src/tta/catalog/product_types.yaml`, `tests/catalog/test_search.py`, `tests/catalog/test_product_types.py` | 0.5 | biomedical | 20% precision | D1 |
| **M2** | Refresh the demo figures once: tests, `docs/DEMO.md`, `docs/PITCH.md`, `README.md`, `docs/ASSUMPTIONS.md:50`, `AIMO/WALKTHROUGH.md`; redeploy | see section 6 | 1.5 | any | 30% demo | M1; after any clock change, if the team makes one |
| A1 | First addition. An optional `note` on a type, shown as an offer note when a request line asks for that type: "Milk for coffee is another product type (coffee_milk) and is not offered for milk. Ask for coffee milk to include it." | `product_types.py`, `product_types.yaml`, `src/tta/contracts/ports.py`, `src/tta/catalog/catalog.py`, `src/tta/offers/builder.py`, tests | 0.75 | CS or any | 20% precision; 15% visible assumptions | M1 |
| F1 | Sub-types with `parent`: `skimmed_milk` (24), `semi_skimmed_milk` (35), `whole_milk` (10), `whipping_cream` (15), `cooking_cream` (17); one sentence in parser rule 3: "choose the most specific key" | `product_types.yaml`, `product_types.py`, `src/tta/agent/prompts.py`, catalog tests | 1.5 | biomedical (data), CS (field) | 20% precision | D2 |
| F2 | The product-type check names the sub-types an option holds and says when it mixes them | `src/tta/offers/checks.py`, `ports.py`, `catalog.py`, offer tests | 1.5 | CS | 20% precision; 20% logged decisions | F1, D3 |
| F3 | Labelled option for a sibling type (`related: [coffee_milk]`): new option kind, the line says which type it is, product-type check NOT_MET naming it, always for a person | `contracts/common.py`, `contracts/offer.py`, `offers/planning.py`, `offers/options.py`, `policy/rules.yaml`, `ui/templates/_result.html`, tests | 3 | CS | 15% exceptions; 20% controls | M1; agree the option's shape with P10 (substitutes) and P8 (confirmation) |
| F4 | Remove strangers by data: `butter` without `471792`; `cream` without `473205`, `473461`; recount; re-run the menu tests | `product_types.yaml`, catalog and menu tests | 0.5 | biomedical | 20% precision | — |
| F5 | `also_accept` on the request line, or a profile setting | contracts, schema, parser, policy loader | 2 | CS | 20% controls | F3 |
| F6 | Documents: type, sub-type, sibling in `AIMO/SPEC.md` section 3 step 2 and `docs/ASSUMPTIONS.md` | documents | 0.5 | any | 15% openness | F1 |

Minimum = M1 + M2 (2 h). Cut order, first to go: F5, F4, F3, F2, F1, A1. M1 and M2 stay.

## 6. What changes in the demo

**Scenario 1, measured at the pinned clock (hotel kitchen, 1,000 L lactose-free milk by Monday 16 Nov), `run_s1.py`.**

| | Today (`milk` = 78) | Coffee milk out (`milk` = 74) |
|---|---|---|
| Products looked up | 30 | 26 |
| Excluded | 19: 17 cut-off passed, 1 portion pack, 1 not deliverable | 17: 15 cut-off passed, 1 portion pack, 1 not deliverable |
| Option 1 | Best confirmed, 1,000 L: 384 × `469363` (€2.48) + 51 × `462775` (€2.57) + 565 × `463380` (€2.65) = **€2,580.64** net, €2,929.02 gross | Best confirmed **(partial fill)**, **435 L, 43.5%**: 384 × `469363` + 51 × `462775` = **€1,083.39** net, €1,229.64 gross; 565 L missing |
| Verdict on option 1 | APPROVAL, P-01 | APPROVAL, **P-01 and P-03**: "only 43.5% of the requested quantity is covered, below the 90% minimum" |
| Option 2 | Alternative, quantity not confirmed: 1,000 × `464306` = €1,010.00; APPROVAL, F-01 and P-01 | the same |
| Fit and in no option | 7 products | 6 products (none has confirmed stock: option 1 takes all of it and is still short) |

- The summary strip reads "2 confirmed products cover 435 L of the 1,000 L asked for (565 L missing), for €1,083.39 before tax."
- With A1 the offer adds the note about milk for coffee. With F3 a third option shows today's 1,000 L basket, labelled.
- 15 of the 26 plain lactose-free milks are out because their cut-off (Thursday 12 Nov 15:00) passed. P5 reports that an earlier clock frees no confirmed stock and measured the same €1,083.39 for 435 L (`P5-clock.md:58`), so these figures hold for the clock P5 recommends.
- P5 left the four coffee milks out through `product_ids`, which switches on the substitute option, and a coffee milk (`464237`) or a coffee drink (`469266`) came back as a substitute (`P5-clock.md:58`, `:65`). Through the type table, which is the real change, the offer has two options and no substitute. For the substitutes topic: a stand-in for milk must not be another kind without the label of rule 4.
- The example of booth question 20 (1,500 L) drops from 1,133 L to 435 L of confirmed stock (`AIMO/BOOTH-NOW.md:227`).
- `docs/DEMO.md:147-148` (My kitchen agent orders option 1 alone after the limit is raised) no longer holds as written: option 1 is a 43.5% fill, and P-03 sends it to a person unless the minimum fill is lowered too.

**Where the old figures live (grep over the repository, by file; `AIMO/build/handback`, `tasks` and `questions` are records and should not be rewritten).**
- `2,580.64` or `2580.64`: `docs/DEMO.md` 7 · `AIMO/WALKTHROUGH.md` 9 · `docs/PITCH.md` 2 · `README.md` 1 · `AIMO/USE-CASES.md` 2 · `AIMO/BOOTH-QUESTIONS.md` 3 · `AIMO/OPEN-QUESTIONS.md` 1 · `AIMO/build/MORNING.md` 2 · `src/tta/offers/wording.py` 1 (a docstring example, harmless) · 13 test files.
- `463380`: `docs/DEMO.md` 3 · `AIMO/WALKTHROUGH.md` 4 · `AIMO/PLAN.md` 2 · `AIMO/FINDINGS.md` 1 · `src/tta/audit/phrases.py` 1 (a docstring) · 31 test files, most of which build the line by hand and do not depend on the type table.
- "coffee milk" or "Café/Cafè": `docs/ASSUMPTIONS.md:50`, `AIMO/WALKTHROUGH.md:192` and `:1271`, `AIMO/PLAN.md:76` and `:82`, `tests/catalog/test_search.py:75`.
- **Recordings of the model's answers (`fixtures/agent/`): nothing to change.** They hold no figure. Five parse recordings say `"product_type": "milk"`, which stays a key, and the run recordings order `opt_1`, which is now the partial fill.
- **OpenAPI examples: nothing to edit.** They are built when the app starts by running the scenarios (`src/tta/api/examples.py:1-9`), so they change by themselves. No exported copy with the figure is in the repository.
- `fixtures/valio/`: unchanged; `463380` stays in the recording as data.
- The app on Modal shows the old figures until it is deployed again.

**Tests that fail with coffee milk out (measured).** A scratch pytest plugin pointed the table loader at a scratch copy of the YAML; no repository file was changed.
- Run 1, stopped by me after 864 of 2,449 tests (order: catalog, offers, policy, part of e2e): 22 failures. `tests/catalog/`: `test_product_types.py` 1, `test_search.py` 4. `tests/offers/`: `test_build_offer.py` 1, `test_data_truth_recording.py` 1, `test_exclusions_and_requests.py` 1, `test_offer_wording.py` 1, `test_preference_offer.py` 3, `test_scenario_1_milk.py` 1. `tests/policy/`: 0, because those tests build their lines by hand. `tests/e2e/`: `test_demo_script.py` 2, `test_scenario_1_milk.py` 4, and one each in `test_guards.py`, `test_scenario_2_allergy_ward.py` and `test_scenario_3_substitutes.py`.
- **Those last three are not established.** In a run of 7 tests without the patch, the `test_guards` test failed too and the other two passed. They may depend on the order of the tests or on state the e2e tests shared in my run. Check them after the change.
- Run 2, complete (`tests/ui/test_approvals.py`, `test_order.py`, `test_run.py`, `test_view.py`, `tests/api/test_sandbox_profile.py`): 8 failed, 97 passed. `test_approvals.py` 1, `test_order.py` 1, `test_run.py` 4, `test_sandbox_profile.py` 2. The messages are the figures: "€2,580.64", "3 confirmed products cover the 1,000 L asked for", "Show the other 14" (19 exclusions became 17), rules `('P-01', 'P-03')` where `('P-01',)` was expected, and `PENDING_APPROVAL` where `ORDERED` was expected for the kitchen with a higher limit.
- So **at least 27 tests in 14 files** change, plus 3 to check. Not run with the patch: the rest of `tests/e2e`, `tests/ui` and `tests/api`, and all of `tests/agent`, `tests/menus`, `tests/standing`, `tests/orders`, `tests/audit`, `tests/mcp`.

## 7. Risks and what not to do
- **Do not refresh the figures twice.** P5 recommends keeping the clock, so M1 is the only cause of new figures. If the team moves the clock anyway, make both changes first, measure once, then do M2.
- **Do not present 43.5% as a failure.** Partial availability is the scenario (15% criterion). The agent offers what is confirmed, names what is not, and says what it left out.
- **Do not build an attribute engine tonight** (option C). Sub-types cover the variants buyers name most.
- **A type's name terms are also the buyer's words for the rule-based reader** (`rules_reader.py:105-115`). Use "cafè milk", not "cafè", so a sentence about a café does not name the type. A sub-type named by a single common word can make a line "name two types" and stop the reader: test each new key with a sentence.
- **Do not put flavoured or barista drinks out of `plant_drink` tonight** without re-measuring scenario 2; "barista oat drink" would need two dimensions. Left as a finding.
- **Names are noisy** (V5): `474864` is "almond drink" in English and "soijajuoma" (soya drink) in Finnish. A type or a name term never replaces the allergen data.
- **The table is ours.** Keep `derived_from` and the test that recounts `products` for every new entry, and say so in `docs/ASSUMPTIONS.md`.
- Sub-type counts are from product names. Five milks would be in no fat sub-type and stay reachable through `milk`: `463290` and `476856` (1 %), `463335` (3 %), `463203` (portion milk) and `464473` (no fat level in the name).
- The rule-based reader does not read "200 litres of fat-free milk": it takes "free" for an exclusion ("it excludes something the allergen table does not name"). Sub-types do not fix that; the model path is not affected.

## 8. Questions
**For the team**
1. João: did "no be explicit" mean the agent must say what it offers, the buyer must name coffee milk, or both?
2. D1 to D6 above. The one that changes the plan most is D4: build the labelled option (F3, 3 h) or accept a main demo whose first option is a 43.5% partial fill.
3. Should `docs/DEMO.md:147-148` (the agent orders alone after the limit is raised) move to a request that is filled in full?

**For Valio, in the booth shape**
1. *Mixing fat levels.* Context: a kitchen asks for 1,000 L of lactose-free milk and names no fat level. What we did: looked for confirmed stock by fat level. What we got: semi-skimmed 384 L (`469363`), fat-free 51 L (`462775`), whole none. Example: one delivery of 384 L semi-skimmed plus 51 L fat-free. Ask: "Is a mix of fat levels acceptable when the offer says so, or must a buyer get one fat level?" If nobody answers: we mix and say so on the offer.
2. *Lactose-free for plain "milk".* Context: a buyer asks for "milk" and names no claim. What we did: type `milk`, once coffee milk is out, holds 46 products with no lactose claim, 26 lactose-free and 2 low-lactose. What we got: the cheapest confirmed product wins, whichever it is. Example (pinned clock, today's table; `469363` is not a coffee milk, so M1 does not change it): 200 L of "milk" is answered with 200 × `469363`, a lactose-free milk drink at €2.48 per litre; regular skimmed milk `469477` at €0.88 per litre has no confirmed quantity. Ask: "Would a buyer who asks for milk accept a lactose-free milk drink?" If nobody answers: we leave it in and name it on the offer.
