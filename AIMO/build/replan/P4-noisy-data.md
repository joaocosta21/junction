# P4 — Noisy data, and asking the user when the agent is not sure

Answers V5 and V9-Q2, and João's clarification of B7 (BRIEF line 30): "it is better to not have gluten if you are unsure so that you dont kill any1".
Every count below is mine, over the whole catalog of 17,546 products unless a capture is named. Scripts: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/P4/` (`count_noise.py`, `count_noise2.py`, `count_noise3.py` for the counts; `run_offline.py` … `run_offline4.py` for the replay requests, each with its own data folder). Nothing in the repository was changed.

## 1. In five lines
1. I counted eight kinds of noise. Under the ward's rule (no milk, no gluten, strict) the data is "not sure" for 9,713 of 17,546 products (55.4%), safe for 2,864 and declared for 4,969. A question per product is impossible: the safe product must win and a question must be the exception.
2. Today a doubt becomes an approval for the dietitian (rule P-04) with a quoted reason, the maker's page, and three acts: approve, approve another option, reject. For a strict buyer that already is "flag it and ask". Four gaps, all verified offline: the doubtful product is the default when it is cheaper; nothing is remembered (the same question comes back); `DECLARED_ONLY` lets a doubt pass and the agent order alone; an exclusion without a strictness is an HTTP 422, not the safe reading.
3. Recommendation, one rule, "safe first": rank 1 holds only products whose data rules the allergen out. A doubtful product is a flagged alternative that only a dietitian can choose. When no safe product can be supplied, the question is "use it anyway, or leave it out", and the default is leave it out. A declared "contains" is never a choice for anyone.
4. "Take the values as they are in the data": the build agrees where a label says gluten-free and the data says contains (`471881` is rejected). It disagrees in one place: a required claim is met by the claim group alone, even when the allergen data contradicts it (56 products). Our other readings (families, oats, ingredient list, `X99`, `UNDECLARED`) are inferences, all in the cautious direction.
5. Minimum, 2 hours: the safe-first fill, and the approval card worded as a question with three choices. Everything else, about 10 hours more (about 8 without "leave one line out"): strict by default, the claim-against-data check, questions and answers in the contract, remembered answers.

## 2. What exists today

### 2.1 The kinds of noise, counted
| # | Kind | Count (whole catalog unless said) | Example | Against the documents |
|---|---|---|---|---|
| 1 | No allergen statement at all | 8,110 (46.2%). 4,566 of them have an ingredient list; in 308 the list names an allergen word. 504 carry the claim `FREE_FROM_LACTOSE` and 656 `FREE_FROM_GLUTEN` with no statement | `463168` Peltolan blue cheese (ingredient list: "Maito") | Matches `AIMO/FINDINGS.md` §3 and `BOOTH-NOW.md` Q10 |
| 2 | "Free from" contradicted by the ingredient list | 89 over all codes. Milk or gluten (`AM`, `AW`): **34** (11 + 25, 2 in both). Tree nuts (`AN`): 7 | `465793` Alpro Barista Almond; `465038` Jymy ice cream | Tree nuts match. Milk or gluten: the documents say 18 (`BOOTH-NOW.md:103`, `BOOTH-QUESTIONS.md:313`, `WALKTHROUGH.md:733`, `:760`, `:1059`). Today's reader gives 34: **those lines are out of date** |
| 2b | No statement (or `UNDECLARED`) about milk or gluten, and the ingredient list names it | 232 | `463168` | Not in the documents |
| 3 | A family declared absent, a member declared present | 176: gluten cereals 132 (74 oats only; 46 with wheat, rye or barley "contains"; 12 "may contain"), tree nuts 45 (19 "contains", 26 "may contain"), milk 1 (lactose, `462051`). The same code both "free from" and declared: 2 (`468044`, `469429`) | `460124` Fria loaf; `461333` Toblerone | Matches `BOOTH-NOW.md` Q9 (176) |
| 4a | "May contain" | 2,685 products, 9,956 rows | `465657` | Matches |
| 4b | `UNDECLARED` | 33 products, 303 rows | `460556` | Matches |
| 4c | `X99` "no allergens to declare" | **195**: 121 in the `allergen` group and 74 in the `nonAllergen` group. 169 carry no other code. 8 carry it next to a declared allergen (`460042`: `X99`, contains eggs and mustard) | `460622` Marli apple juice | `FINDINGS.md` §3 and `BOOTH-NOW.md` Q11 give 121: **the 74 in the `nonAllergen` group are missing there** |
| 5 | A dietary claim or name that the data contradicts | 56 in all. Claim `FREE_FROM_GLUTEN` while gluten cereals are declared "contains": 43 (11 on `AW` itself, 32 through wheat, rye or barley). Name says gluten-free and "contains": 29. `FREE_FROM_LACTOSE` and lactose "contains": 4. `VEGAN` and an animal allergen "contains": 7. `FREE_FROM_SOY` and soy "contains": 1 | `471881` (V9-Q2); `465336` Santa Maria bay leaf (vegan, contains lactose) | Not counted in the documents |
| 6 | Product file and API name different sales units | Captures, not catalog: 15 of 624 lines (demo capture), 7 of 797 (Friday sample), 1 of 25 (extras); 23 of 1,397 distinct products | `461439` Risifrutti (file `KI`, API `ST`) | Matches `BOOTH-NOW.md` Q6 and `FINDINGS.md` §1 |
| 7 | Names disagree between languages | 1, with my list of 9 plant words on the English and Finnish names | `474864`: English "almond drink", Finnish "soijajuoma", declares soya. Its twin `474774` has the same English name and is the almond drink | Matches `BOOTH-NOW.md` Q28 |
| 8 | Pack size cannot be worked out | From the product file alone: 2,367 (13.5%) give neither litres nor kg. With the price: 7 of 769 (demo capture), 92 of 1,000 (Friday sample) | `471732` | Not counted in the documents |

The ward's rule over the catalog (`AM`, `AW`, ingredient list read): STRICT gives PASS 2,864 · REJECT 4,969 · TO_HUMAN 9,713. `DECLARED_ONLY` gives PASS 11,844 · REJECT 4,969 · TO_HUMAN 733.

### 2.2 What the build does for each kind (each run offline in replay)
| Kind | What happens | Where | Checked with |
|---|---|---|---|
| 1 No statement | STRICT: `TO_HUMAN`, P-04, dietitian, maker's page attached. Confirmed-only (the ward): dropped as `ALLERGEN_NOT_STATED`, nobody is asked. `DECLARED_ONLY`: PASS "unverified", verdict `AUTO` | `allergens/exclusion.py:34-45`, `policy/rules.yaml:347-363`, `offers/candidates.py:365-373`, `evidence/finder.py:49-65` | Hotel, `469512`, no milk: APPROVAL, dietitian. Ward, `469512`: excluded, substitute `473424` offered. Hotel, `DECLARED_ONLY`: AUTO |
| 2 Ingredient list against "free from" | Finding becomes `MAY_CONTAIN`, `TO_HUMAN` under both rules, sentence quotes both. Never a pass, never a block | `allergens/exclusion.py:191-228`, `allergens/ingredients.py:127-141` | Hotel, `465793`, no tree nuts: "The ingredient list names "ALMOND" … while the product states it is free from tree nuts (AN): a dietitian must decide." |
| 3 Family against member | The less safe statement counts: REJECT when the member is "contains" (66 cases), dietitian when it is "may contain" or oats under a gluten exclusion (112 cases) | `allergens/statements.py:74-91`, `:113-130` | `460124`, `461333`, `462051`: REJECT (function level, not in the capture). `475224`, `473956` (oats): dietitian |
| 4 May contain, undeclared, `X99` | May contain: dietitian under both rules. `UNDECLARED` and `X99` alone: dietitian under STRICT, pass "unverified" under `DECLARED_ONLY` | `allergens/exclusion.py:39-44`, `allergens/statements.py:89-90` | Hotel, `463218`, no milk: dietitian. `460556`, `460622` at function level (none in the demo capture) |
| 5 Claim against data | For an exclusion the claim is never read: `471881` is REJECT, F-02 BLOCK. For a required claim the claim group alone decides: "Every product offered carries the nutritional claim FREE_FROM_GLUTEN. A claim is not an allergen statement." | `allergens/exclusion.py:3-4`, `policy/rules.yaml:157-170`, `offers/checks.py:153-156`, `catalog/search.py:131` | Hotel, `471881`, no gluten: `ALLERGEN_DECLARED`. The required-claim case cannot be shown in replay: `471881` is the only such product in the demo capture and it is not deliverable there. The check reads the claim group only (code) |
| 6 Unit differs | The API unit wins for price and quantity. A size read from the file is dropped unless the price ratio gives it. No flag on the line | `offers/candidates.py:123-126`, `:287-296` | Hotel, 24 units of `461439`: 24 single cups at €1.00, verdict AUTO, nothing says the file sells cases of 12 |
| 7 Names disagree | Nothing. The search matches the English name | `catalog/search.py` | Hotel, plant drink with name term "almond": `474864` (soya) is the unconfirmed alternative, with no flag |
| 8 Pack size unknown | Dropped as `PACK_SIZE_UNKNOWN` with a sentence; a substitute is offered | `offers/candidates.py:337-345`, `catalog/pack.py:87-101` | Hotel, 10 L of `471732`: excluded, substitute `468565` |
| Unreadable data | An allergen code or relation outside the table rejects the whole product file, for every buyer. 0 products today | `catalog/loader.py:243-270`, `catalog/data_errors.py:15-16`, `allergens/exclusion.py:118-128` | The catalog loads: 17,546 products |

### 2.3 The dietitian's card and the trail (run: hotel, 10 × `469512`, no milk, strict)
- Order `PENDING_APPROVAL`, role dietitian. Card: "Found on the manufacturer's page — not Valio data" (`ui/templates/_evidence.html:4-24`), "Why a human is needed" (`ui/templates/approvals.html:47-50`), every option of the offer as a radio button, a note, "Approve the chosen option" and "Reject the order" (`approvals.html:61-98`). The contract is `DecisionRequest`: decision, option, note (`contracts/order.py:46-51`).
- The purchasing manager is refused (403, written to the trail). The dietitian approves: `approval.decided` reads "Demo approver Leena (dietitian) approved order … This approval accepts rule P-04. Note: …" (`audit/sentences.py:180-195`).
- Evidence never changes a status (`evidence/finder.py:4-5`, `contracts/order.py:69-70`). In replay only 5 products have a recorded page (`fixtures/evidence/`).
- **The same request sent again after the approval raises the same question again.** Nothing is remembered.
- A declared "contains" cannot be approved: the offer leaves the product out (`offers/candidates.py:307-312`), F-02 is BLOCK and fixed (`policy/rules.yaml:157-170`, pinned in code, `rules.yaml:11-12`), and the policy runs again at approval (`tests/orders/test_decide.py:153`).

### 2.4 "Take the values as they are in the data": every place where we do not
| # | Where | What we do | Against V9-Q2 |
|---|---|---|---|
| 1 | `allergens/exclusion.py:3-4` | A name or claim never overrides a declaration: `471881` declares gluten cereals, so it is rejected | **Agrees.** This is the Q2 case |
| 2 | `offers/checks.py:153-156`, `catalog/search.py:131` | A required claim is met by the claim group alone, also when the allergen data says "contains" (56 products) | **Disagrees.** Here the label wins over the data. Work item F4 |
| 3 | `allergens/statements.py:113-119` | A declared member counts for its family even when the family is stated "free from": REJECT for a "contains" member (46 gluten, 19 nuts, 1 milk), dietitian for "may contain" (12 gluten, 26 nuts) | Both values are in the data; we take the less safe one. Agrees with B7. The Fria loaf (gluten-free wheat starch) is rejected for a no-gluten buyer: question B8 is still open |
| 4 | `allergens/statements.py:122-130` | Declared oats count as "may contain" gluten cereals, also when `AW` is "free from" (76 products): dietitian | An inference. A literal reading of Q2 would pass them. It asks, it does not decide: fits V5 and B7. Keep |
| 5 | `allergens/statements.py:133-141` | A declared family counts as "may contain" for a member not stated | An inference, cautious |
| 6 | `allergens/exclusion.py:209-220` | The ingredient list turns a "free from" or a missing statement into `MAY_CONTAIN` (line 216). The declared value survives only in the sentence | An inference from free text by word match. It asks, it never passes or blocks. The field should keep the declared value (F1) |
| 7 | `allergens/statements.py:89-90` | `X99` is not read as "free from": dietitian under STRICT (195 products) | We discount a declared value. A literal reading of Q2 would pass it. B9 is open. Keep: 0 such products in the demo capture |
| 8 | `allergens/exclusion.py:41-42` | `UNDECLARED` is not read as "free from" (33 products) | Same as 7 |
| 9 | `allergens/exclusion.py:43-44` | Under `DECLARED_ONLY` no statement passes | Not an override, but a doubt that passes: against V5 and B7 unless a person confirms |
| 10 | `allergens/substitution.py:50-63` | A substitute with no statement at all "adds no allergen" and passes F-05 (checked: `check_substitute(…, ())` passes) | Reads absence as safe. Against "no data means unknown". Work item F6, with P10 |
| 11 | `catalog/pack.py:87-101` | The price ratio replaces the file's own size when they disagree (`466382`: file 3.39 kg, ratio 2.0 kg) | An inference between two Valio sources, labelled `PRICE_RATIO`. Q13 is open |
| 12 | `offers/candidates.py:123-126` | The API's sales unit replaces the file's | A choice between two Valio sources. Q6 and Q7 are open. No flag (F5) |
| 13 | `evidence/finder.py:4-5` | The maker's page is shown and changes nothing | **Agrees** |

## 3. What Valio's answers change
- **V9-Q2 confirms the demo.** Scenario 3 says `471881` "can never be ordered as a substitute". We can now say "Valio confirmed on 14 Nov: the allergen data wins over the label." It also makes row 2 of §2.4 a fault.
- **V5 ("flag it to the user to ask for his input") is met for a strict buyer** by the approval. It is not met in two places: under confirmed-only nobody is asked (the product is dropped with a reason, which is safe and is what B7 wants), and under `DECLARED_ONLY` the doubt passes and the verdict is `AUTO`.
- **B7 as clarified is not met.** Verified: hotel, 10 L of plant drink, no gluten, strict. Rank 1 is 10 × `475224` Fazer Aito Barista oat drink, €17.40, allergen claim `UNKNOWN`, "needs the dietitian". `464013` Alpro No Sugars Soya drink states free from gluten cereals, has confirmed stock, and is in no option: "the options take the cheapest products". Cause: the confirmed pool is every candidate with confirmed stock, whatever its allergen outcome (`offers/planning.py:95-103`). The ward's scenario is right only because the profile sets `require_confirmed` (`policy/profiles/allergy-ward.yaml:22`).
- **V8 (the user always confirms)** removes the `AUTO` risk of `DECLARED_ONLY`, and gives the questions a natural place: the confirmation step.
- **"The least manual correction" (20%)** is hurt twice: the same question is asked again after an answer, and "gluten-free oat drink" typed by the hotel fails with 422 "does not say how strictly … The strictness is never guessed" (`agent/parser.py:55-59` on `/v1/requests/parse`, `allergens/exclusion.py:92-93` on `/v1/offers`; both checked).

## 4. Design and decisions

### 4.1 What counts as "not sure"
For each excluded allergen the rule already gives one of three outcomes. "Not sure" is exactly `TO_HUMAN`, plus four doubts that are not about allergens.
- **Sure it is safe:** an explicit "free from" on the code, with nothing against it. Outcome PASS, allergen claim `CONFIRMED`.
- **Sure it is not:** a declared "contains", on the code, on a member, or as the less safe of two statements. Outcome REJECT. **Nobody is asked and nobody can answer.**
- **Not sure about an allergen:** no statement · `UNDECLARED` · `X99` alone · "may contain" · oats under a gluten exclusion · the ingredient list names what the declaration leaves open or denies · a substitute with no statement at all.
- **Not sure about something else:** a required dietary claim the data contradicts · file and API units differ · names disagree between languages · pack size unknown.

### 4.2 The rules (20% controls, 20% precision, 15% exceptions)
- **R1, safe first.** Rank 1, the option the agent suggests and the default at confirmation, holds only products whose data rules out every excluded allergen. Price and preference rank among safe products only. This holds under both strictness values.
- **R2, the doubtful product is never the default.** It is shown as "Alternative: allergen not ruled out", it always needs the dietitian, and it appears in two cases only: no safe product can cover the quantity, or the buyer named that product by id. In the second case rank 1 is still a safe product.
- **R3, when no safe product can be supplied,** the agent suggests nothing as default and says so: "No product whose data rules out milk can be delivered by Monday." It asks one question per doubtful line, to the dietitian. Silence means no order: the approval expires at "order by" as today.
- **R4, a declared "contains" never becomes an order.** A REJECT product is never a line and never a choice. A question exists only for a `TO_HUMAN` finding. The policy runs again when an answer is given, and F-02 stays BLOCK. No profile setting, request field, note or remembered answer changes this.
- **R5, no model, no web page and no agent resolves an allergen doubt.** Evidence is shown; a person with the role decides.

### 4.3 The question
- **Words** (templates, built from the finding's sentence, never by a model): "The agent is not sure. Valio Aimo's data makes no statement about milk for Elovena 1l oat drink barista (469512). The maker's page says milk-free; that is not Valio data."
- **Choices:**
  1. "Take the safe product: Alpro Rice drink 1L, states free from milk, €23.60." (`473424`, the product the ward's run offers today in place of `469512`.) Shown only when one exists; it is the preselected choice.
  2. "Use Elovena anyway. I have checked it." Dietitian only; a note is required.
  3. "Leave it out." The preselected choice when there is no safe product.
- **Who may answer.** An allergen question: only a person the buyer profile lists as dietitian (`approver_roles`, `policy/profiles/*.yaml:26-29`). Other doubts (unit, pack, name, claim): the person who confirms the order, or the purchasing manager. An agent never answers (F-06).
- **The audit trail.** Minimum: today's `approval.decided` sentence, which already names the person, the role, the option chosen and the note. Full: two events, `question.asked` and `question.answered`, each with the product, the allergen, the values as they are in the data, the choice and the person. The supplier's sentence names the product and the kind of doubt, not the buyer's exclusion.
- **Memory.** An answer is kept for the buyer, the product, the allergen and a fingerprint of the product's allergen statements and ingredient list. The next offer says "Accepted for this buyer by Leena (dietitian) on 14 Nov" and does not ask again. A "leave it out" is kept too: the product is then excluded with that reason. A remembered answer is void when the data changes, is never applied to a REJECT, and never moves a doubtful product to rank 1.
- **With V8.** Yes, the confirmation step can carry the questions. The person confirming answers the non-allergen questions there and sees the allergen flags. If an allergen question is open and that person is not the dietitian, confirming sends the order to the dietitian, as an approval does today. Same `questions` list on both steps (P8 owns the step).

### 4.4 Decisions for the team
- **DECISION D1.** Safe first (R1, R2), even when the doubtful product is cheaper. Measured cost on the test request: €20.10 instead of €17.40 for 10 L, €201.00 instead of €174.00 for 100 L. Recommended: yes. It is B7.
- **DECISION D2.** An exclusion with no strictness is read as STRICT and the result says so, instead of HTTP 422. This changes SPEC §3 ("There is no default"). Recommended: yes.
- **DECISION D3.** Only a listed dietitian answers an allergen question; the requester answers the others. Recommended: yes.
- **DECISION D4.** Remember answers as in §4.3. Recommended: full version only; in the minimum, name it as the next step.
- **DECISION D5.** Keep `DECLARED_ONLY` as an explicit buyer setting for a preference that is not an allergy; it is never a default, and under V8 a person confirms every "unverified" line. Recommended: keep.
- **DECISION D6.** Keep today's cautious readings until Valio answers: gluten-free wheat starch rejected (46 products), `X99` and `UNDECLARED` to the dietitian (195 and 33). Recommended: keep, and list them on `/assumptions`.
- **DECISION D7.** A required dietary claim that the allergen data contradicts excludes the product, with a reason (V9-Q2). Recommended: yes, full version.

### 4.5 Contract, states and pages, without code
- **Minimum:** no new field, state or page. `DecisionRequest` already carries the choice (option or reject) and the note.
- **Full:**
  - `Question`: id · kind · product id · request line · allergen code · sentence · `declared` (the values as the data gives them) · quotes (ingredient words, maker's page) · choices · safe choice · who may answer.
  - `Answer`: question id · choice (`TAKE_SAFE`, `USE_ANYWAY`, `LEAVE_OUT`) · person · roles · note · time · remember.
  - `OfferOption.questions`, `Approval.questions`, `Approval.answers`, `DecisionRequest.answers`. `AllergenFinding.declared_relation` and `AllergenFinding.settled_by`.
  - `ExclusionReason.CLAIM_CONTRADICTED` and `REFUSED_BY_BUYER`. Option title "Alternative: allergen not ruled out".
  - States: none new. `PENDING_APPROVAL` is "waiting for an answer"; P8's confirmation state carries the same list.
  - Store: one table of remembered answers. Audit: `question.asked`, `question.answered`.
  - Pages: the card on `/approvals`; a "Remembered answers" list with "forget" on the same page; the question block on the request result and on P8's confirmation.

## 5. Work items
Minimum first. CS = the computer-science member. Bio = a biomedical member.

| id | What | Files | Hours | Who | Criterion | Depends on |
|---|---|---|---|---|---|---|
| M1 | Safe first: with an exclusion, rank 1 takes only products whose allergen claim is `CONFIRMED`; doubtful stock goes to a flagged alternative; title "Alternative: allergen not ruled out"; tests | `offers/planning.py`, `offers/options.py`, `tests/offers/` | 1.5 | CS | 20% controls, 20% precision | D1; same file as P10's ranking |
| M2 | The card as a question: "The agent is not sure", the finding, the three choices mapped to approve safe option, approve this option (note required), reject; safe option preselected | `ui/templates/approvals.html`, `ui/approvals_page.py` | 0.5 | Bio | 20% controls | M1 |
| M3 | No strictness given: read as STRICT and say so | `allergens/exclusion.py`, `offers/candidates.py`, `agent/parser.py`, SPEC §3 | 0.5 | any | 20% precision | D2 |
| F4 | Required dietary claim against the allergen data: exclude with a reason; one table claim to allergen code | `offers/candidates.py`, `contracts/common.py`, a small table | 1 | Bio | 20% precision, 15% exceptions | D7 |
| F1 | `Question` and `Answer` in the contract, on the offer, the approval and the decision; two audit events; `declared_relation` | `contracts/`, `orders/service.py`, `audit/`, `ui/` | 2.5 | CS | 20% controls, 15% open standards | M1, M2, P8 |
| F2 | Remembered answers: table, fingerprint, applied in the offer, P-04 reads unanswered findings only, list with "forget" | `store/`, `offers/candidates.py`, `policy/facts.py`, `policy/rules.yaml`, `ui/` | 2 | CS | 20% precision | F1, D4 |
| F6 | A substitute with no allergen statement: ranked after those with one, and sent to a person | `allergens/substitution.py`, `offers/substitutes.py` | 1 | Bio | 15% exceptions | P10 |
| F5 | A note on the line when the file and the API name different units | `offers/lines.py`, `ui/templates/_result.html` | 0.5 | any | 15% exceptions | none |
| F3 | "Leave it out" for one line of a multi-line order (needs a new plan without the line) | `offers/`, `orders/` | 2 | CS | 15% exceptions | F1 |
| D0 | Correct the out-of-date figures (18 becomes 34; `X99` 121 becomes 195) and list the cautious readings on `/assumptions` | `AIMO/` documents, `docs/ASSUMPTIONS.md` | 0.25 | any | 15% assumptions | none |

Cut first: F3, then F5, F6, F2, F4, F1. A flag for names that disagree between languages is dropped: 1 product in 17,546.

## 6. What changes in the demo
- **Hotel, "10 litres of plant drink, no gluten".** Today: rank 1 is 10 × Fazer Aito Barista oat drink (`475224`), €17.40, "It needs the dietitian". After M1: rank 1 is 10 × Alpro No Sugars Soya drink (`464013`), €20.10, "states it is free from cereals containing gluten", no question. The oat drink becomes "Alternative: allergen not ruled out". Both figures measured; the second by running the same request with confirmed-only, which already fills from safe products.
- **Scenario 2 (ward) does not move:** 200 × `464013`, €402.00. Scenario 1 is not touched by this topic.
- **Scenario 3 gains a sentence:** "Valio confirmed on 14 Nov: the allergen data wins over the label", for `471881`.
- **The dietitian's card (Elovena `469512`, no milk).** Today: "Why a human is needed" and two buttons. After M2: the question of §4.3 with three choices and the safe product preselected. Which safe product M1 puts first for this request must be measured after the change.
- **Asked twice.** Today the second identical request needs the dietitian again (measured). After F2: "Accepted for this buyer by Leena (dietitian) on 14 Nov", no second question.
- **"50 litres of gluten-free oat drink by Monday", typed as the hotel.** Today: HTTP 422. After M3: read as no gluten, strict, "the safe reading, because no rule was given".
- **One sentence for the pitch:** "For a ward that excludes milk and gluten, Valio's data settles 45% of the catalog. For the other 55% our agent suggests a product the data clears, and asks a dietitian only when there is none."

## 7. Risks and what not to do
- Do not ask a question for every doubtful product: 9,713 products are doubtful for the ward's rule.
- Do not let a remembered answer, the maker's page or a model move a doubtful product to rank 1 or settle a doubt.
- Do not touch F-02. Do not "fix" the gluten-free wheat-starch rejection or the reading of `X99` tonight: both are cautious, and Valio has not answered B8, B9 or Q11.
- An option whose allergen claim is `UNKNOWN` still has the kind `BEST_CONFIRMED` and the title "Best confirmed option" (`offers/options.py:41`; measured through the API). The result page lists it under "A claim not confirmed" (`ui/request_page.py:107-111`), so the title and the heading disagree. M1 removes the case.
- The ingredient reader matches words. It over-asks (`469229`, "nut-flavored nut-free" spread, is read as naming nuts). It can only cause a question, never a pass. Do not widen it tonight.
- M1 changes `offers/planning.py`, which P10 (substitute ranking) and P8 (confirmation) also touch: one owner for that file.
- One unreadable allergen code stops the whole gateway today (`catalog/loader.py:258-270`). For production, set the product aside with a reason instead. Not for tonight; name it as a next step (15%).
- A substitute chosen for closeness can be a doubtful one while a safe one exists (measured: for `464320` with gluten excluded the substitute is `469512`, oats, dietitian). Safe first must be the first sort key of P10's ranking too.

## 8. Questions
**For the team:** D1 to D7 above. One more: should Valio see in its log that an allergen question was asked about its product (B13 says "all the steps and decisions")? It tells Valio which data gaps cost orders, and it reveals that the buyer excludes something.

**For Valio, in the booth shape:**
1. **Who is "the user" who answers?**
   - Context: you said that when the agent is not sure it must flag it to the user and ask for input.
   - What we did: an allergen doubt goes to a named dietitian at the customer, not to the person who typed the order.
   - What we got: the purchasing manager is refused; only the dietitian can accept the product.
   - Example: Elovena barista oat drink 1 l says nothing about milk. A kitchen that excludes milk asks for it.
   - Ask: "At your customers, who would answer this: the person ordering, or a named dietitian or quality person?"
   - If nobody answers: the role the buyer's profile names, the dietitian by default.
2. **"No allergens to declare" (follow-up to 11 and B9).**
   - Context: 195 products carry only a general statement, GS1 code X99.
   - What we did: for a strict buyer we do not read it as "free from milk"; a dietitian decides.
   - What we got: Marli Natur apple juice 1 L goes to a dietitian for a ward that excludes milk.
   - Ask: "You told us to take the values as they are in the data. Does that mean an agent may treat 'no allergens to declare' as free from all 14 allergens?"
   - If nobody answers: it stays a question for the dietitian.
3. **Gluten-free wheat starch (follow-up to 9 and B8).**
   - Context: 46 products say "free from cereals containing gluten" and also "contains" wheat, rye or barley.
   - What we did: the less safe statement counts, so a buyer who excludes gluten never gets them.
   - Example: Fria fibre-rich loaf, named "glutenfree", free from gluten cereals, contains wheat.
   - Ask: "For a coeliac ward, should the agent reject this loaf, or ask the dietitian?"
   - If nobody answers: it stays rejected.
