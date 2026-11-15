# Walkthrough: what the gateway does, why, and how to check it

For the team, and for anyone who was not there when it was built. Rewritten on Saturday 14 Nov 2026, about 20:30, against commit `c2106fe`. The earlier walkthrough (1,300 lines, written that morning against `3ef0657`) described a flow that no longer exists: an agent that ordered alone by default, a first option of €2,580.64 filled with coffee milk, eight MCP tools, a model as the only reader of requests. Its text is in git history.

**Corrected on Sunday 15 Nov 2026, about 03:00**, after the night's checks and fixes (commit `94b21a5`): the people and roles, the third option of the brief's request, rule F-12 and who decides it, the limits and counts, and what is claimed about approvals, the audit trail and the pages. What was measured again is marked "15 Nov": it was asked of a local gateway in replay at the demo clock, over REST with the demo tokens or through the routes the shop page calls. Everything else is as measured on 14 Nov.

How to read it:
- **Money** is in euros before tax ("net") unless a sentence says otherwise.
- **Times** are Helsinki time (UTC+2).
- **Figures say where they come from.** "Catalog" is Valio Aimo's whole product file, 17,546 products. "The recording" is the copy of Valio's price and availability answers used in replay: 769 products, recorded Saturday 14 Nov 2026 at 02:52 Helsinki, joined since that evening with a second recording of 394 baking products (21:12 the same day): 1,163 products in all. "Measured" means I re-ran the committed code offline in replay for this document, through the application's test client, with no key set and no outside call.
- **A rule id always comes with its words.**
- **Not run for this correction:** any test folder; a redeploy of the public link; the SQL view for Valio on PostgreSQL. The shop page was walked in headless Chrome on 15 Nov at about 01:00, before the last fixes to it (`AIMO/build/replan/REVIEW.md`, section BW). The demo's figures at both clocks are in `docs/DEMO.md`, which wins where this file differs.

Where each subject is kept now:

| Subject | Document |
|---|---|
| The contract: data shapes, states, every rule | `AIMO/SPEC.md` |
| Every assumption and threshold that is ours | `docs/ASSUMPTIONS.md` (served at `/assumptions`) |
| The open standards used, and the departures | `docs/STANDARDS.md` |
| The brief's 16 items, one by one, with the proof | `AIMO/COVERAGE.md` |
| Packages and ports | `docs/ARCHITECTURE.md` |
| The public link, its settings and checks | `docs/DEPLOY.md` |
| The tech awards: what ran and what did not | `docs/AWARDS.md` |
| The brief and the judging criteria, verbatim | `AIMO/CHALLENGE.md` |
| The questions for Valio's mentors in full | `AIMO/BOOTH-QUESTIONS.md` |

## Contents
1. [What the judges score](#1-what-the-judges-score)
2. [Who and what is involved](#2-who-and-what-is-involved)
3. [The flow, on the brief's own request](#3-the-flow-on-the-briefs-own-request)
4. [The allergy ward](#4-the-allergy-ward)
5. [A product with no confirmed stock](#5-a-product-with-no-confirmed-stock)
6. [The rules in one table](#6-the-rules-in-one-table)
7. [The ways in](#7-the-ways-in)
8. [Check it yourself](#8-check-it-yourself)
9. [Assumptions and next steps](#9-assumptions-and-next-steps)
10. [Questions for Valio Aimo: answered and open](#10-questions-for-valio-aimo-answered-and-open)
11. [Decisions we took on our own](#11-decisions-we-took-on-our-own)

---

## 1. What the judges score

Quoted from the Junction platform (`AIMO/CHALLENGE.md`).

| Weight | Criterion | Their wording |
|---|---|---|
| 30% | Working end-to-end demo | "The solution runs through a full request → lookup → order/approval flow in the mocked environment, not just isolated pieces." |
| 20% | Solving the problem and user need | "how Precisely the agent matches what the buyer actually asked for, with the least manual correction needed." |
| 20% | Autonomy and controls | "Quality of the guardrails design. What the agent can decide alone, what needs human sign-off, and how decisions are logged and auditable." |
| 15% | Robustness to exception situations | "Handling of partial availability, substitutions and delivery constraints beyond the happy path." |
| 15% | Openness and credible path toward production | "Open, documented standards rather than a proprietary format, clear visibility of assumptions, well-justified technical choices, and a credible view of next development steps" |

The brief's three core requirements: a structured product, price and availability lookup; a defined step from inquiry to commitment at fixed prices; and permission and human-approval management. Its own words on what this is not: "This is not about replacing today's e-commerce UI with a chatbot."

**What was built, in one paragraph.** A gateway: one Python web service between a buyer's purchasing agent and Valio Aimo's price and availability service. The agent sends a request. The gateway finds matching products, reads fixed prices and stock, and answers with an offer: a few ranked options, each saying what is confirmed and what is not, why other products were left out, and who must confirm. The agent prepares an order; a person at the buyer confirms it. Every step is written to an audit trail that the buyer and Valio Aimo each read in their own words.

---

## 2. Who and what is involved

- **The mock API.** Valio Aimo's hackathon service: `price` and `availability`, up to 1,000 product ids per call (`MAX_IDS_PER_CALL`, `src/tta/valio/client.py`). It has no order endpoint, by design: the order step is ours to define.
- **Catalog.** Valio's product file, read locally at start: 17,546 products. It holds no price and no stock.
- **Live and replay.** In replay the gateway answers from the recording and calls nobody; replay is the default (`tta_mode` in `src/tta/config.py`) and every figure here is from it.
- **The clock.** In replay, order deadlines are judged against the recording's instant, Saturday 14 Nov 2026 02:52. The setting `TTA_DEMO_CLOCK` replaces it, in replay and in `dev` and `demo` only; the demo clock we chose is Thursday 12 Nov 2026 14:15. Valio Aimo said on 14 Nov that its test data is static, "so we can chose the date". `/healthz` says which clock is in force. Audit events always carry the real time.
- **Customers.** Four invented buyers, each a profile file (`src/tta/policy/profiles/`) and a customer file with people, usual products and a **synthetic** order history (`src/tta/customers/data/`). The mock has no customers, limits or approvers: every value is ours and illustrative.

| | Harbourside Hotel (`hotel-kitchen`) | City Hospital, Ward 4 (`allergy-ward`) | Kilo School (`school-kitchen`) | Kallio Bakery (`bakery-cafe`) |
|---|---|---|---|---|
| Agent may order alone (`auto_order_enabled`) | off | off | off | off |
| Limit per order / per day | €750 / €3,000 | €500 / €1,500 | €250 / €800 | €300 / €1,000 |
| Minimum share of the quantity | 90% | 100% | 100% | 100% |
| Excluded allergens | none | milk `AM`, gluten cereals `AW`, strict | tree nuts `AN`, peanuts `AP`, sesame `AS`, strict | none |
| Substitute without a person | same category | none | only those Valio lists | none |
| Confirmed data only | no | yes | no | no |
| The formula matters on every line | no | no | no | yes |
| A preference may cost, without a person | no limit set | 10% more | no limit set | 10% more |

- **Approver roles.** Purchasing manager, finance, dietitian. Each profile names who holds each role, and **one person confirms**: at the hotel (Hanna Laine) and the bakery (Marko Heikkinen) the person who orders holds all three; at the ward (Jussi Nieminen) and the school (Päivi Korhonen) the person who orders also holds finance, and the only second person is the dietitian (Sari Lehto, Riikka Mäkelä), for allergen doubts, a lost dietary claim and a substitute whose formula differs or that is not like for like. No customer has a separate finance signer. The names are invented (the customer file says Hanna Laine; her REST token says "Demo approver Hanna").
- **Tokens.** 11 demo tokens in `src/tta/api/demo_tokens.yaml`: 4 agents, 6 approvers and Valio Aimo's reader. They are public by design and load only when `TTA_ENV` is `dev` or `demo`. An unset `TTA_ENV` means `prod`: no demo token, and no start without `TTA_TOKENS`. The buyer's profile comes from the token, never from the request.

---

## 3. The flow, on the brief's own request

The hotel's agent sends **"1,000 litres of lactose-free milk by Monday"**. Measured at both clocks; the outcome differs only where said.

```
request ─► read into a typed request ─► candidate products ─► price and availability
        ─► exclusions, each with a reason ─► options ─► the rules ─► order prepared ─► a person confirms ─► audit trail
```

**1. Who is asking.** Every call carries a bearer token. `GET /v1/authority` answers the caller's own rules in sentences, the first being: "The agent prepares the order, a person confirms it (F-10). The purchasing manager confirms when no other approval role is required."

**2. The text becomes a typed request.** `POST /v1/requests/parse` reads 1,000 L, product type `milk`, claim `FREE_FROM_LACTOSE`, needed by Monday 16 Nov 2026. **Who reads it.** When a key is set (`GEMINI_API_KEY`, or an OpenAI-compatible endpoint through the `TTA_AGENT_*` settings) a model is asked first; the gateway checks its reading against the text and refuses one that does not match, never correcting it. When no model answers, or none is configured, the order of readers is (`src/tta/agent/fallback.py`): a recording of that exact sentence if `fixtures/agent/` holds one, else the fixed-rules reader (`src/tta/agent/rules_reader.py`). `GET /healthz` → `agent_reader` says what reads sentences on a deployment. My runs set no key. The answer's headers say who read: over REST with the hotel's token this sentence is one of the recorded ones (`TTA-Reading-Source: recording`, `TTA-Read-By: gemini-3.6-flash`, `TTA-Reading-Sentence: Read from a recording of gemini-3.6-flash made on 14 Nov 2026 at 07:13 UTC; no model was asked.`; 15 Nov). A recording is served only to the profile it was made for, so on `/shop`, whose book has a profile of its own, the same sentence is read by the fixed rules and says so. Over REST "100 litres of oat drink by Monday, most reliable delivery" and "40 litres of cream for whipping by Monday" are read by the rules (`rule-based`; the second sets `keep_formula` on the line). What the rules cannot read is asked about, never guessed: "Some cheese for Friday" answers 422 with a `question` ("What quantity of cheese is needed? …"), `not_read` and `read_by`. Since 15 Nov a minus, cartons, a price per unit and a Finnish or Swedish sentence are asked about too, and an amount named for the whole request ("under €400") is read as a spend limit for that request, applied by rule P-01 as the lower of it and the buyer's own limit per order (commit `fe3ae8c`). With a key set (measured by the build on 15 Nov on a local server at the demo clock, not by me): this sentence was read by `gemini-3.6-flash` into the same typed request (`TTA-Read-By: gemini-3.6-flash`, `TTA-Reading-Source: model`); a loosely worded sentence whose day the model got wrong was refused ("the reading did not match the text: the text names another day"); and when the model answered HTTP 429 twice, the fixed rules read the sentence and the answer said so. Measured again by the build at 03:40 with a key set: after a first HTTP 429 the model is not asked again for 120 seconds; in that time a sentence the fixed rules can read is read by them, and one they cannot read is answered 503 with the rules' own reason in it ("The language model did not answer … The fixed rules could not read it either: …"). Whoever reads, every price, quantity, allergen status and verdict is deterministic code. Any agent can skip this step and send the typed request to `POST /v1/offers`.

**3. Candidates.** Product type `milk` is category `10400` without sour milk, a coffee drink, a soy yoghurt and the milks for coffee: 74 products (catalog; `src/tta/catalog/product_types.yaml`, which a test recounts). Milk for coffee is its own type, `coffee_milk`, 4 products: Valio Aimo, asked on 14 Nov whether a buyer who asks for milk accepts it, answered "no be explicit". The claim narrows the 74 to 26 candidates (measured; the catalog file says 26 too). The table of 32 product types is ours.

**4. Price and availability.** One price call and one availability call for all candidates, both from the same source; for this request one more of each, for the substitute of option 3. In replay: the recording.

**5. Exclusions, each with a reason.** At the recording's clock 17 are left out: 15 whose order deadline has passed, 1 portion pack, 1 that cannot be delivered. At the demo clock 2 are left out (the portion pack and the undeliverable one). The Thursday clock changes neither option: the confirmed stock is the same 435 L, and 21 products then fit the request and are in no option (6 at the recording's clock).

**6. Options.**
- **Option 1, "Best confirmed option (partial fill)":** 384 × `469363` + 51 × `462775`, **435 L of the 1,000 L**, **€1,083.39**. The summary also says that `462775` differs in formula from `469363` (fat 0 g, not 1.5 g) and that coffee milk was left out.
- **Option 2, "Alternative: quantity not confirmed":** 1,000 × `464306`, **€1,010.00**. Valio reports a very large stock figure for it, which Valio confirmed in person means the stock is not known.
- **Option 3, "Alternative: confirmed stock, completed with a substitute"** (since 15 Nov): the 435 L of option 1 plus 565 × `463380`, a lactose-free milk made for coffee, **€2,580.64** (€2,929.02 with tax). All 1,000 L come from confirmed stock; the coffee milk is named as a substitute and "not a like-for-like replacement: another product type (coffee milk, not milk); made for coffee …". It is listed last.
- A note says that 21 products fit the request and are in no option because Valio does not confirm their quantity.

Each offer line states five things, each `CONFIRMED`, `UNKNOWN` or `RULED_OUT`: price, quantity, delivery date, allergens, origin. This is our answer to the brief's "trust protocol".

**7. The rules.** They run on every option before anything is ordered.
- Option 1 goes to the purchasing manager: "the total of €1,083.39 before tax is above the €750 limit per order of Harbourside Hotel (P-01) and only 43.5% of the requested quantity is covered, below the 90% minimum (covered: 435 of 1,000 L) (P-03)".
- Option 2 goes to the purchasing manager: its quantity is not confirmed by Valio Aimo (F-01), and it is above the €750 limit per order (P-01).
- Option 3 goes to the purchasing manager: a substitute that is not a like-for-like replacement always needs a person (F-12), and it is above the limit per order (P-01).

**8. The order is prepared.** `POST /v1/orders` with the offer and option ids needs the header `Idempotency-Key`; without it the answer is 400. With it: 201, a `Location` header, status `PENDING_APPROVAL`. Just before, price and availability are read again; a change refuses the order (rule F-04: an option that expired or changed cannot be ordered, a fresh offer is needed). `ORDERED` means recorded in our order book: nothing is sent to Valio, no payment is taken, and the record says so.

**9. A person confirms.** The agent's own token on the decision route answers 403: "An agent cannot approve or reject an order (F-06). A human with the role asked for decides." Demo approver Hanna, who holds every role at the hotel, approves: `ORDERED`, placed by `HUMAN_APPROVAL`, "Ordered for €1,083.39 net with approval by Demo approver Hanna: rules P-01 and P-03 asked for a human and were accepted." (15 Nov). This guarantee is the token's: it holds over REST, and MCP has no approval tool. The demo pages have no login (section 7).

**10. The audit trail.** Eleven events for this path (request received, request parsed, lookup performed, offer created, rules checked for each of the three options, suggestions shown, approval requested, approval decided, order confirmed), plus one `authorisation.refused` for each refused attempt: 12 in my run of 15 Nov, and the chain verified ("The audit trail is intact: each of the 12 events shown here matches its hash, and the chain they belong to verifies."). Events are stored in CloudEvents 1.0 envelopes in a SHA-256 hash chain; `GET /v1/audit` answers a reader's view of each (`id`, `type`, `time`, `actor`, `sentence`, `rule_ids`, `facts`, `hash`), which is not a CloudEvents document. Every sentence comes from a template.
- **The buyer's view** names the customer, the limits, the approver and her note.
- **Valio Aimo's view** shows the same steps and every rule that fired, with the buyer's values masked and the masking said: "P-01, a rule the buyer set (the order is above the spend limit per order; the amount is not shown)"; "A person of the buyer approved order …". Valio asked for "all the steps and decisions"; the buyer's amounts, allergens, names and notes stay the buyer's.

**11. The proof.** Every offer and order record carries `proof`: a detached JSON Web Signature (EdDSA) over the record's canonical JSON, with the public key at `/.well-known/jwks.json`. It says that this gateway answered this record. It does not say Valio Aimo signed anything. With no `TTA_SIGNING_KEY` set the key is a demo key made at each start, and `/healthz` and every proof say so. The proof is made when the record is answered: an order row edited in the database is answered with the edited values and a proof that verifies (found on 15 Nov, not fixed; section 9).

*In the code:* `src/tta/api/` (identity, routes, signing), `agent/`, `catalog/`, `valio/`, `availability/`, `offers/`, `policy/`, `orders/`, `audit/`.

---

## 4. The allergy ward

The ward's agent asks for **200 litres of a plant drink by Monday, no milk, no gluten, confirmed data only** (the pasted sentence "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only" reads to this; it is one of the recorded sentences).

- **The allergen rule.** A product that declares an excluded allergen is left out and can never be ordered (F-02). Under the strict rule, a product that may contain it, leaves it undeclared or says nothing goes to the dietitian (P-04); under "confirmed data only" it is left out instead. A nutritional claim is never an allergen statement. No data means unknown, not safe.
- **Measured, recording's clock:** 41 products left out (18 declare an excluded allergen, 12 past their deadline, 6 not deliverable, 5 with no statement on an excluded allergen). At the demo clock also 41 (18, 6, 6 and 11).
- **The option, both clocks:** 200 × `464013` Alpro No Sugars Soya drink, **€402.00**, all confirmed.
- **The verdict:** "Prepared: confirm to order. The agent prepares the order, a person confirms it (F-10): the purchasing manager confirms." The order waits as `PENDING_APPROVAL`; then "Confirmed by Demo approver Jussi (purchasing manager): ordered for €402.00 net." (REST, 15 Nov; the role is said because the ward has a second person). The earlier walkthrough had this order placed by the agent alone; that is no longer the default.
- **Ordering alone** is the buyer's setting `auto_order_enabled`, off in all four profiles. Valio Aimo, 14 Nov: "for now deactivate automatic order … the final submition should always have the input from the user", and of the setting: "after and if you are 100% sure yes". Switched on, the agent orders alone only when no other rule fires and price, quantity, delivery date, allergens and origin are confirmed on every line (`src/tta/policy/human_approval.py`). Measured on 15 Nov on `/shop` → Settings, in the browser's own order book: with the switch on, the ward's 200 L are ordered by the agent, and the order says why: "The agent placed this order alone for €402.00 net. That was allowed: ordering alone is switched on for City Hospital, Ward 4; the total of €402.00 is within the €500 limit per order; today's spend with this order is €402.00 of the €1,500 limit per day; every statement of the offer is confirmed; and no rule asked for a person." At the hotel 302 L of lactose-free milk (€748.96) are ordered by the agent and 303 L (€751.44) go to a person. The switch is an audit event. Over REST and MCP no demo agent has the setting on, so every order of a demo token waits for a person. `tests/e2e/test_no_order_without_a_person.py` covers the default.

---

## 5. A product with no confirmed stock

The hotel asks for **100 litres of `473609`** (Oddlygood Barista oat drink). Its quantity is not confirmed, so the gateway looks for a substitute.

How a substitute is chosen (`src/tta/offers/substitutes.py`): candidates are the pairs Valio lists and the products of the same 5-digit category, nothing wider (Valio did not confirm that the digits are levels). In order:
1. The allergen rule: a substitute that adds an allergen the original does not declare can never be ordered, for any buyer (F-05).
2. Dietary claims: one that loses a claim such as lactose-free is a last resort, held back while a claim-keeper can be ordered.
3. The same kind of product: another product type, or a flavoured product for a plain one, is a last resort too. Where no product type of ours says what the original is, a candidate whose name lacks the original's kind words ("yolk", "cocoa powder") is never an offer option.
4. The formula (the two ingredient lists compared, then six nutrients and the fat source), then listed by Valio, pack, verification, price.

Every substitute whose verdict is not "replaceable" goes to a person, whatever the buyer's settings (F-12, since 15 Nov); at the ward and the school that person is the dietitian.

Measured on 15 Nov at 02:51 through the shop's routes, on commit `fd4098b` (`docs/DEMO.md` has the whole measurement):
- **Both clocks.** Option 1, "With a substitute for a product that cannot be supplied in full": 100 × `475224` Fazer Aito Professional Barista oat drink, **€174.00**, confirmed stock, to a person under F-12 ("not a like-for-like replacement: a different formula …") and P-05 ("the substitute costs €37.00 more than the product you asked for (27% more): a person decides"). Option 2: `473609` itself, €137.00, quantity not confirmed (F-01).
- **Demo clock only.** Option 3 is the substitute Valio lists, 10 cases of `471690`, **€155.50**: 100 one-litre cartons become 10 cases of ten (Valio, on converting by volume: "yes the goal is to satisfy the prompt"). Its quantity is not confirmed (F-01), and it is not like for like either (F-12). At the recording's clock its order deadline has passed.

Other exception paths, measured at the recording's clock:

| Situation | What happens |
|---|---|
| 1,500 L of lactose-free milk | The same 435 L confirmed (1,065 L missing), €1,083.39; P-01 and P-03 send it to the purchasing manager. Alternative 1,500 × `464306`, €1,515.00 |
| 30 kg of beef chuck, sold by weight | 30 kg of `466988`, "about €506.40 … The total is an estimate: a product is sold by weight, and Valio Aimo invoices the weight delivered." P-06 (a product sold by variable weight) sends it to the purchasing manager |
| An agent tries to approve | 403, recorded as `authorisation.refused` |
| No `Idempotency-Key` on an order | 400 |
| A text the rules cannot read | 422 with a question |

Described with their figures in `docs/DEMO.md` and `AIMO/COVERAGE.md`: suggestions from the customer's pattern and Valio Aimo's own, standing orders and their renewal on `/shop`, menus from a sentence, the formula rule firing, evidence from a manufacturer's page, and a date that cannot be met answered with the earliest date.

---

## 6. The rules in one table

Read from `src/tta/policy/rules.yaml` and `src/tta/policy/human_approval.py`; the list is what `GET /v1/authority` answers. P-00 is retired. Where a sentence names a role, the authority says it for the caller's buyer: "the dietitian" at the ward and the school, "the purchasing manager" where the person who orders holds that role (15 Nov).

| Rule | In its words | Outcome |
|---|---|---|
| **F-01** | A product whose quantity Valio Aimo does not confirm always goes to the purchasing manager | approval |
| **F-02** | A product that declares an allergen the buyer excludes can never be ordered, even with approval | block |
| **F-03** | When a fact a rule needs is missing, a human decides. Missing data never counts as good data | approval |
| **F-04** | An option that has expired, whose order cut-off has passed, or whose price or availability changed since the offer cannot be ordered. A fresh offer is needed | block |
| **F-05** | A substitute that declares an allergen the product asked for does not can never be ordered as a substitute, for any buyer. A person who wants that product asks for it by name | block |
| **F-06** | An agent can never approve an order, its own included: approval routes refuse agent tokens (over REST; MCP has no approval tool) | refused (403) |
| **F-07** | A product whose price is not confirmed or whose delivery date is ruled out, and an option that does not verifiably meet the needed-by date, always go to the purchasing manager | approval |
| **F-08** | A substitute that lacks a dietary claim of the product it replaces, for example lactose-free, always goes to the dietitian (the role; at the hotel and the bakery the person who orders holds it) | approval |
| **F-09** | A product type that recipe logic chose in place of a recipe's own ingredient always goes to the purchasing manager | approval |
| **F-10** | The agent prepares the order, a person confirms it. Driven by the buyer's setting, so listed as not fixed; lives in code | approval, purchasing manager |
| **F-11** | Where the formula matters (the profile or the request line says so), a substitute whose formula differs or cannot be compared always goes to the purchasing manager; at the ward and the school to the dietitian | approval |
| **F-12** | A substitute that is not a like-for-like replacement of the product asked for (another formula, use, flavour or product type, or one the data cannot show to be like for like) always goes to the purchasing manager, whatever the buyer sets; at the ward and the school to the dietitian | approval |
| **P-01** | An order above the profile's limit per order goes to the purchasing manager | approval |
| **P-02** | When the day's orders, this one included, pass the limit per day, the order goes to the purchasing manager (the rule's role is finance, which the person who orders holds at all four customers) | approval |
| **P-03** | An option that covers less than the profile's minimum share goes to the purchasing manager | approval |
| **P-04** | A product that does not rule out an excluded allergen goes to the dietitian | approval |
| **P-05** | A substitute outside what the profile accepts goes to the purchasing manager; so does one that costs more than 25% above what the product it replaces would have cost, or whose price cannot be compared (25% is ours where the profile sets no share) | approval |
| **P-06** | A product sold by variable weight goes to the purchasing manager: its total is an estimate | approval |
| **P-07** | A product that carries a deposit goes to the purchasing manager (the role is finance, as P-02): deposits have no published price | approval |
| **P-08** | A standing-order renewal whose quantity or unit price differs from the median of its last 6 renewals by more than the profile's tolerance goes to the purchasing manager | approval |
| **P-09** | An option ranked by a preference that costs more than the profile's share above the cheapest confirmed option goes to the purchasing manager | approval |

The strictest outcome among the rules that fire decides. A rules file that weakens a fixed rule is refused at start (`src/tta/policy/validation.py`).

---

## 7. The ways in

All surfaces call one service object, so no rule holds on one and not on another.

- **REST** under `/v1`, described in OpenAPI 3.1 at `/openapi.json` (generated from the code). The document holds 27 paths, and `/v1/schemas` serves the JSON Schema of 98 models, each naming its dialect (both counted from the running gateway on 15 Nov). `/.well-known/api-catalog`, `/llms.txt` and `/.well-known/jwks.json` are served. Search and get-product take `price_and_availability=true` and then carry price and availability for at most 20 products a call. Routes beyond the core: `/v1/customers`, `/v1/menus/plan`, `/v1/standing-orders`, `/v1/insights` (Valio Aimo's back office, for its token only). Valio's token cannot read a customer (403, measured).
- **MCP** at `/mcp/`, same tokens, **13 tools**: `get_authority`, `search_products`, `get_product`, `find_substitutes`, `get_offer`, `place_order`, `get_order`, `get_audit`, `get_customer`, `plan_menu`, `set_up_standing_order`, `renew_standing_order`, `list_standing_orders`. **None approves.** An argument a tool does not know is refused, as REST refuses an unknown field. A request whose `Origin` header names a foreign web origin is refused with 403 (measured); a request with no `Origin` is served. The Host header is not checked.
- **The pages**, in `dev` and `demo` only, **no login**: the shop page at `/shop`, where everything a person does now happens (requests and dishes, confirming, suggestions, standing orders and their renewal, settings, the log in both views, Valio Aimo's back office), and the older pages `/`, `/kitchen`, `/menu`, `/standing-orders`, `/approvals`, `/orders/{id}`, `/assumptions`. Whoever opens `/shop` acts as the customer's person and can sign as any of its people; the page says so ("Demo, no login: you are acting as Hanna Laine, Harbourside Hotel."). So "an agent cannot approve" is a guarantee of REST and MCP, where the token says who calls; in production no page is mounted. The shop page was walked in headless Chrome on 15 Nov, before its last fixes. Each browser gets its own in-memory order book per customer (at most 1,000 are kept, one idle for 2 hours is dropped, and one address opens at most 400 new ones in 10 minutes; `src/tta/api/sandbox.py`). A change of settings on the page is an audit event, listed in Settings under "What changed", and at the ward and the school the dietitian's allergen exclusions cannot be removed there.
- **Rate limits per minute** (`src/tta/api/limits.py`, ours): one visitor 60 lookups (offers, searches, reads), 20 orders and decisions, 15 request readings; one address 60, 60, 60; all callers together 240 each. On REST and MCP a visitor is an address. Bodies up to 64 KB.
- **The public link.** `deploy/modal_app.py` sets replay and the demo clock for it, and since 15 Nov one container kept running with 4,096 MiB, because the pages' books and the demo signing key live in its memory. Whether the link runs this code was not checked for this correction (`docs/DEPLOY.md`).

---

## 8. Check it yourself

From the repository root, in replay. The two empty settings keep a local `.env` from adding a model key or a shared database; `TTA_ENV=demo` is needed, because unset means `prod`.

```bash
mkdir -p /tmp/tta-check
GEMINI_API_KEY= DATABASE_URL= TTA_ENV=demo TTA_MODE=replay TTA_DB_PATH=/tmp/tta-check/w.sqlite3 \
  .venv/bin/python -m uvicorn --factory tta.api:create_app --port 8790 --no-proxy-headers
```

`--no-proxy-headers`: without it a local uvicorn believes an `X-Forwarded-For` header sent from the same machine, and the rate limiter would count a caller under an address of its choosing.

In a second terminal. The expected answers below are what the same calls gave on 15 Nov against a local server of the working tree at `94b21a5`, at the demo clock; the count of excluded products at the recording's clock (17) is from the shop's routes.

```bash
B=http://127.0.0.1:8790; A="Authorization: Bearer demo-agent-hotel-kitchen"; J="Content-Type: application/json"

curl -s $B/healthz        # "mode":"replay", the clock sentence, "store":{"kind":"sqlite"}, "signing":{"demo_key":true}
curl -s $B/v1/authority -H "$A"      # the profile, 20 rules (F-01 to F-12 without F-06, P-01 to P-09), the summary

curl -s -X POST $B/v1/requests/parse -H "$A" -H "$J" -d '{"text":"Some cheese for Friday"}'
#   422, with "question", "not_read", "read_by":"rule-based"

curl -s -X POST $B/v1/offers -H "$A" -H "$J" -d '{"needed_by":"2026-11-16","lines":[{"text":"1,000 litres of lactose-free milk by Monday","product_type":"milk","required_claims":["FREE_FROM_LACTOSE"],"quantity":1000,"unit":"L"}]}'
#   201: opt_1 1083.39 APPROVAL [P-01, P-03]; opt_2 1010.0 APPROVAL [F-01, P-01]; opt_3 2580.64 APPROVAL [F-12, P-01]; 17 excluded; a "proof"

curl -s -X POST $B/v1/orders -H "$A" -H "$J" -H "Idempotency-Key: check-1" -d '{"offer_id":"<offer_id>","option_id":"opt_1"}'
#   201, "status":"PENDING_APPROVAL", an "approval_id"; without the Idempotency-Key header: 400
curl -s -X POST $B/v1/approvals/<approval_id>/decision -H "$A" -H "$J" -d '{"decision":"APPROVE"}'
#   403: "An agent cannot approve or reject an order (F-06). …"
curl -s -X POST $B/v1/approvals/<approval_id>/decision -H "Authorization: Bearer demo-approver-hotel-purchasing" -H "$J" -d '{"decision":"APPROVE","note":"Checked with the kitchen."}'
#   200, "status":"ORDERED", "placed_by":"HUMAN_APPROVAL"
curl -s "$B/v1/audit?order_id=<order_id>&reader=buyer" -H "Authorization: Bearer demo-approver-hotel-purchasing"
curl -s "$B/v1/audit?order_id=<order_id>&reader=supplier" -H "Authorization: Bearer demo-supplier-valio-aimo"
#   both: 12 events (11 plus the refused attempt), "chain":{"ok":true,…}; Valio's view shows no €750, no name, no note
```

For the demo clock add `TTA_DEMO_CLOCK=2026-11-12T14:15:00+02:00` to the first command: the same three options and totals, 2 excluded.

**The tests.** The scenarios over HTTP are in `tests/e2e/` (scenarios 1 to 3, the beef backup, the guards, the demo clock, "no order without a person"). I did not run the test folders for this document; the whole suite on the final code is the last check's work (`AIMO/build/replan/STATUS.md`, row DEEP), and until it has run some tests pin figures the night's fixes moved.

---

## 9. Assumptions and next steps

First what in the demo is ours and stated as such, then what a pilot would add. A next step does not exist today.

- **Orders commit nobody.** `ORDERED` is a record in our order book. No order message reaches Valio and no payment is taken.
- **A model may read a sentence and never decides.** With a key set it is asked first, and its reading is checked against the text and refused when it does not match. The fixed rules are its check and its fallback; they read the shapes they know and ask about the rest. Every figure of this document was measured with no key set. `fixtures/agent/` holds eleven recordings (4 of a model's answer made on 14 Nov, 7 written by hand); over REST and MCP a sentence that has one for the caller's profile is answered from it, labelled, when no model answers or none is configured; in my runs on `/shop`, with no key, every sentence was read by the rules.
- **Every customer value is ours.** Limits, people, usual products, order history (synthetic), thresholds.
- **In replay most of the catalog has no price.** The recordings hold 1,163 of 17,546 products; a product outside it is left out as "not in the recording", never as undeliverable in Valio's name.
- **The proof is the gateway's, with a demo key** unless a key is set. Nothing is signed by Valio.
- **One process.** Limits, the pages' books and locks are in memory.
- **The audit chain** shows a changed, removed or inserted event; it cannot show the last events cut off unless another party holds an earlier head.
- **MCP:** no OAuth; tokens are handed out outside the protocol. Host is not checked.
- **The demo pages have no login.** Over REST and MCP an agent cannot approve; on `/shop` whoever opens the page signs as the customer's people. Next: people sign in with their own accounts; the token-bound decision already exists over REST.
- **One person holds every role at the hotel and the bakery.** No four eyes there, by choice; the dietitian is a second person at the ward and the school only. Next: a second signer above a limit.
- **Next: stored orders tied to their audit entries.** Today an order edited in the database is answered with a valid proof and the chain stays intact; `/healthz` walks the chain and reports a changed event, and cannot see this.
- **Next: the trail as CloudEvents at the interface.** Today it is stored in that envelope and answered as a reader's view, and a reader cannot recompute a hash from its masked view.
- **Next steps, none of which exists today:** Valio Aimo signing its own statements; an order message Valio Aimo's systems can take; a nutrition standard for schools and hospitals; new and seasonal products marked in the data; recipes around a seasonal ingredient; a scheduler for standing orders and a check that runs before the kitchen asks; an origin filter; Finnish; a demo agent that orders alone over REST and MCP (today it is shown on `/shop`).
- **Not run for this correction:** the tests, a redeploy, the SQL view for Valio on PostgreSQL.

---

## 10. Questions for Valio Aimo: answered and open

The full write-up of each question, with its example, is in `AIMO/BOOTH-QUESTIONS.md` under the id given. The catalog counts that the earlier walkthrough printed beside each question were not recounted tonight and are left out. Answers are quoted from a team member's notes of what was said at the booth on 14 Nov.

### Answered in person on 14 Nov

| Id | We asked | The answer, as noted | What the gateway does |
|---|---|---|---|
| `Q3` | A very large stock value means the stock is not known? | "yes" | Never the suggestion, never used in arithmetic, always to a person (F-01) |
| `Q1` | Order deadlines already passed; a deadline exactly at "now" | "this is all static data so we can chose the date" | The deadline is read literally; the demo clock is ours and said on every page |
| V5 of the old list | Would a buyer asking for milk accept coffee milk? | "no be explicit" | `coffee_milk` is its own type; an offer for milk says it was left out |
| `T03-1`, `Q2` | A drink labelled gluten-free whose allergen data says it contains gluten: which is right? | "take thw values as they are in the data." | The declaration counts, never the name or the claim |
| `T07-5` | A listed substitute in another sales unit: convert by volume? | "yes the goal is to satisfy the prompt" | 100 cartons become 10 cases |
| `Q9` | Variable weight: invoiced for the weight ordered or delivered? | "what is actually delivered. like in a normal store" | The total is an estimate and says so; P-06 |
| V6 | A substitute can never add an allergen | "yes" | F-05 |
| V7 | A substitute that loses a dietary claim always goes to a person | "yes and only in the last case"; clarified by João: only when no product that keeps the claim can be supplied | Held back as a last resort; F-08 and F-12 |
| V11 | "By Monday" means the first Monday after today | "yes" | `src/tta/agent/days.py` |
| V13 | What Valio sees in the log | "all the steps and decisions"; later: "the log should show and explain why it made that decision and the logic behind it and product considered" | Valio's view shows every rule that fired and the products left out, the buyer's values masked. Whether masking is what was meant is still to confirm |
| V1 | May the agent order alone? | "for now deactivate automatic order … the final submition should always have the input from the user"; as a setting: "tbh after and if you are 100% sure yes" | F-10; the setting is off in every profile |
| `Q11` | Is the category code a hierarchy? | "sap code semi random?? he doesnt know" | Not confirmed: substitutes come from the same 5-digit category only |
| `Q7` | What limits do real customers set? | "it is generic data that can be generated" | Four invented customers, labelled synthetic |
| `SCOPE-1` | Which scenario matters most? | "the goal is to try and see per user based on the user pattern"; on suggestions: "everything no?" | Suggestions from the customer's pattern (`AIMO/COVERAGE.md`) |
| Formula | — | "for cakes/things that require the formula the ingredient and chemestry can make a difference" | F-11; `keep_formula` on a request line; the bakery's profile |
| Ask any 3 | Webshop test accounts | A test login to the real webshop was given | The login is written in no file of the repository |

### Still open

| Id | The question | What the gateway does meanwhile |
|---|---|---|
| `Q4` | What does an accepted order commit to: price, quantity, delivery date? | Price for its validity window; the date if ordered before the deadline; the quantity only when stock is an ordinary number |
| `DATA-1` | Product file or API when they disagree; how often the file changes | Price, quantity and sales unit follow the API; what the product is follows the file |
| `ALMOND-1` | `465793` declares tree nuts free-from while its ingredient list names almond: which wins? | Neither: the product goes to the dietitian with both quoted |
| `OFFER-1` | Whole-order options, or good-better-best per item? | Whole-order options; per item only on the substitutes route |
| `Q2` | Are `X99` and `UNDECLARED` used with their GS1 meanings? Who decides on "may contain"? | GS1 meanings; under the strict rule all go to the dietitian |
| `T03-2` | A family stated free-from while a member is declared | The less safe statement counts |
| `Q5` | Does no allergen data mean "declared nothing"? | No data means unknown, not safe |
| `T02-1` | Is `allowedLotSize` 0.01 "no step"? | Whole units, except products sold by the kilogram |
| `T02-2` | What does `comparisonPrice` divide by? | Used to work out litres or kilograms per sales unit |
| `Q10` | Sales unit differs between API and file | Price and quantity follow the API line |
| `Q8` | Are deposits inside the price? | Totals leave deposits out and say so; P-07 sends the order to a person (the finance role, held by the person who orders) |
| `Q12` | What does delivery reliability measure; what does a missing value mean? | Ranks only when the request prefers reliability; a missing value is unknown, never imputed |
| `Q6` | Stock that covers part of a line: what happens today? | The rest is filled from other confirmed products; below the minimum share, P-03 |
| `Q13` | Is our call volume fine? | Replay by default |
| `T01-1` | Must an agent send a named User-Agent? | The client sends `tta-gateway/0.1` |
| `S2-1`, `S2-2` | `469512` states nothing about milk; `474864` is an almond drink in English and a soya drink in Finnish | The declaration counts; a doubt goes to the dietitian |
| — | A mark for new or seasonal products in the product file? | None found; Valio Aimo's own suggestion is a related product and says so |
| — | Is "Delight" `471690` meant as the like-for-like replacement of `473609`? | Offered because Valio lists it |
| — | Payment; the order format; may Valio's data stay in a public MIT repository? | Not answered. No payment step; no order message; the README leaves the data out of the licence |

---

## 11. Decisions we took on our own

The run's full list, with reasons, is `AIMO/build/replan/DECISIONS.md` (B1 to B67). The ones a reader of this walkthrough meets:

| Decision | Where to change it |
|---|---|
| Ordering alone is a buyer setting, off by default; switched on it needs all five statements confirmed on every line | `auto_order_enabled` in the profile; `src/tta/policy/human_approval.py` |
| Milk for coffee is not milk | `src/tta/catalog/product_types.yaml` |
| A substitute is the same 5-digit category, the same product type, and not flavoured for plain | `src/tta/offers/substitutes.py`, `src/tta/catalog/kinds.py` |
| A substitute that is not judged replaceable always goes to a person, also with ordering alone on (F-12, B64) | `src/tta/policy/rules.yaml` |
| One person confirms; a dietitian is the second person at the ward and the school only, and decides a differing formula there (B54, B66) | `approver_roles` in the profiles; `src/tta/api/demo_tokens.yaml` |
| The brief's request gets a third option that fills the quantity from confirmed stock with a named substitute (B56); a date that cannot be met is answered with the earliest date (B67) | `src/tta/offers/completing.py`, `src/tta/offers/` |
| The demo pages have no login, and the claims say "over REST and MCP" (B62) | `src/tta/ui/`, `/llms.txt` |
| The formula tolerances: 15% or 1 g, salt 0.25 g, same fat source | `src/tta/offers/formula.py` |
| The demo clock, Thursday 12 Nov 2026 14:15 | `TTA_DEMO_CLOCK` |
| The four customers, their limits and their synthetic history | `src/tta/policy/profiles/`, `src/tta/customers/data/` |
| Valio's view masks the buyer's amounts, allergens, names and notes, and says so | `src/tta/audit/readers.py`, `supplier_decisions.py` |
| Audit events carry the real time, not the demo clock | `src/tta/api/wiring.py` |
| One waiting or ordered order per offer; a retry with the same key returns the first order | `src/tta/orders/service.py` |
| Each browser of the pages gets its own order book | `src/tta/api/sandbox.py` |
| Offers and orders are signed by the gateway, with a demo key unless one is set | `src/tta/api/signing.py`, `TTA_SIGNING_KEY` |
