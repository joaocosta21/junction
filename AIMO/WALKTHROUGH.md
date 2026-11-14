# Walkthrough: what the gateway does, why, and how to check it

For the team, and for anyone who was not there when it was built. Rewritten on Saturday 14 Nov 2026, about 20:30, against commit `c2106fe`. The earlier walkthrough (1,300 lines, written that morning against `3ef0657`) described a flow that no longer exists: an agent that ordered alone by default, a first option of €2,580.64 filled with coffee milk, eight MCP tools, a model reading the requests. Its text is in git history.

How to read it:
- **Money** is in euros before tax ("net") unless a sentence says otherwise.
- **Times** are Helsinki time (UTC+2).
- **Figures say where they come from.** "Catalog" is Valio Aimo's whole product file, 17,546 products. "The recording" is the copy of Valio's price and availability answers used in replay: 769 products, recorded Saturday 14 Nov 2026 at 02:52 Helsinki. "Measured" means I re-ran the committed code offline in replay for this document, through the application's test client, with no key set and no outside call.
- **A rule id always comes with its words.**
- **Not run by anyone:** the pages in a real browser; a redeploy of the public link with tonight's code; the new SQL view for Valio on PostgreSQL. The end-to-end re-measure of the whole demo set (task E1) had not run when this was written, so `docs/DEMO.md` may still carry older figures.

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
9. [Known limits](#9-known-limits)
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

- **Approver roles.** Purchasing manager, finance, dietitian. Each profile names who holds each role; at the bakery the owner holds all three. The names are invented (the hotel's purchasing manager is Hanna Laine in the customer file, "Demo approver Hanna" on her token).
- **Tokens.** 15 demo tokens in `src/tta/api/demo_tokens.yaml`: 4 agents, 10 approvers and Valio Aimo's reader. They are public by design and load only when `TTA_ENV` is `dev` or `demo`. An unset `TTA_ENV` means `prod`: no demo token, and no start without `TTA_TOKENS`. The buyer's profile comes from the token, never from the request.

---

## 3. The flow, on the brief's own request

The hotel's agent sends **"1,000 litres of lactose-free milk by Monday"**. Measured at both clocks; the outcome differs only where said.

```
request ─► read into a typed request ─► candidate products ─► price and availability
        ─► exclusions, each with a reason ─► options ─► the rules ─► order prepared ─► a person confirms ─► audit trail
```

**1. Who is asking.** Every call carries a bearer token. `GET /v1/authority` answers the caller's own rules in sentences, the first being: "The agent prepares the order, a person confirms it (F-10). The purchasing manager confirms when no other approval role is required."

**2. The text becomes a typed request.** `POST /v1/requests/parse` reads 1,000 L, product type `milk`, claim `FREE_FROM_LACTOSE`, needed by Monday 16 Nov 2026. **No model is called**: no key is set tonight, and Gemini was dropped. With no key the order of readers is (`src/tta/agent/fallback.py`): a recording of that exact sentence if `fixtures/agent/` holds one, else the fixed-rules reader (`src/tta/agent/rules_reader.py`). The answer's headers say which: this sentence is one of the recorded ones (`TTA-Reading-Source: recording`, `TTA-Read-By: gemini-3.6-flash`, a recording made on 14 Nov), while "100 litres of oat drink by Monday, most reliable delivery" and "40 litres of cream for whipping by Monday" are read by the rules (`rule-based`; the second sets `keep_formula` on the line). What the rules cannot read is asked about, never guessed: "Some cheese for Friday" answers 422 with a `question` ("What quantity of cheese is needed? …"), `not_read` and `read_by`. A model is an option a deployer may add by setting a key; the code path exists (`src/tta/agent/gemini.py`) and was not run tonight. Any agent can skip this step and send the typed request to `POST /v1/offers`.

**3. Candidates.** Product type `milk` is category `10400` without sour milk, a coffee drink, a soy yoghurt and the milks for coffee: 74 products (catalog; `src/tta/catalog/product_types.yaml`, which a test recounts). Milk for coffee is its own type, `coffee_milk`, 4 products: Valio Aimo, asked on 14 Nov whether a buyer who asks for milk accepts it, answered "no be explicit". The claim narrows the 74 to 26 candidates (measured; the catalog file says 26 too). The table of 32 product types is ours.

**4. Price and availability.** One price call and one availability call for all candidates, both from the same source. In replay: the recording.

**5. Exclusions, each with a reason.** At the recording's clock 17 are left out: 15 whose order deadline has passed, 1 portion pack, 1 that cannot be delivered. At the demo clock 2 are left out (the portion pack and the undeliverable one). The Thursday clock changes neither option: the confirmed stock is the same 435 L, and 21 products then fit the request and are in no option (6 at the recording's clock).

**6. Options.**
- **Option 1, "Best confirmed option (partial fill)":** 384 × `469363` + 51 × `462775`, **435 L of the 1,000 L**, **€1,083.39**. The summary also says that `462775` differs in formula from `469363` (fat 0 g, not 1.5 g) and that coffee milk was left out.
- **Option 2, "Alternative: quantity not confirmed":** 1,000 × `464306`, **€1,010.00**. Valio reports a very large stock figure for it, which Valio confirmed in person means the stock is not known.
- A note names the products that fit and are in no option.

Each offer line states five things, each `CONFIRMED`, `UNKNOWN` or `RULED_OUT`: price, quantity, delivery date, allergens, origin. This is our answer to the brief's "trust protocol".

**7. The rules.** They run on every option before anything is ordered.
- Option 1 goes to the purchasing manager: "the total of €1,083.39 before tax is above the €750 limit per order of Harbourside Hotel (P-01) and only 43.5% of the requested quantity is covered, below the 90% minimum (covered: 435 of 1,000 L) (P-03)".
- Option 2 goes to the purchasing manager: its quantity is not confirmed by Valio Aimo (F-01), and it is above the €750 limit per order (P-01).

**8. The order is prepared.** `POST /v1/orders` with the offer and option ids needs the header `Idempotency-Key`; without it the answer is 400. With it: 201, a `Location` header, status `PENDING_APPROVAL`. Just before, price and availability are read again; a change refuses the order (rule F-04: an option that expired or changed cannot be ordered, a fresh offer is needed). `ORDERED` means recorded in our order book: nothing is sent to Valio, no payment is taken, and the record says so.

**9. A person confirms.** The agent's own token on the decision route answers 403: "An agent cannot approve or reject an order (F-06). A human with the role asked for decides." The hotel's finance approver is refused too: the approval needs the purchasing manager. Demo approver Hanna approves: `ORDERED`, placed by `HUMAN_APPROVAL`.

**10. The audit trail.** Nine events for this path (request received, request parsed, lookup performed, offer created, rules checked for each of the two options, approval requested, approval decided, order confirmed), plus one `authorisation.refused` for each refused attempt: 11 in my run, and the chain verified ("The audit trail is intact: each of the 11 events shown here matches its hash, and the chain they belong to verifies."). Events are CloudEvents 1.0 envelopes in a SHA-256 hash chain; every sentence comes from a template.
- **The buyer's view** names the customer, the limits, the approver and her note.
- **Valio Aimo's view** shows the same steps and every rule that fired, with the buyer's values masked and the masking said: "P-01, a rule the buyer set (the order is above the spend limit per order; the amount is not shown)"; "The buyer's purchasing manager approved order …". Valio asked for "all the steps and decisions"; the buyer's amounts, allergens, names and notes stay the buyer's.

**11. The proof.** Every offer and order record carries `proof`: a detached JSON Web Signature (EdDSA) over the record's canonical JSON, with the public key at `/.well-known/jwks.json`. It says that this gateway answered this record. It does not say Valio Aimo signed anything. With no `TTA_SIGNING_KEY` set the key is a demo key made at each start, and `/healthz` and every proof say so.

*In the code:* `src/tta/api/` (identity, routes, signing), `agent/`, `catalog/`, `valio/`, `availability/`, `offers/`, `policy/`, `orders/`, `audit/`.

---

## 4. The allergy ward

The ward's agent asks for **200 litres of a plant drink by Monday, no milk, no gluten, confirmed data only** (the pasted sentence "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only" reads to this; it is one of the recorded sentences).

- **The allergen rule.** A product that declares an excluded allergen is left out and can never be ordered (F-02). Under the strict rule, a product that may contain it, leaves it undeclared or says nothing goes to the dietitian (P-04); under "confirmed data only" it is left out instead. A nutritional claim is never an allergen statement. No data means unknown, not safe.
- **Measured, recording's clock:** 41 products left out (18 declare an excluded allergen, 12 past their deadline, 6 not deliverable, 5 with no statement on an excluded allergen). At the demo clock also 41 (18, 6, 6 and 11).
- **The option, both clocks:** 200 × `464013` Alpro No Sugars Soya drink, **€402.00**, all confirmed.
- **The verdict:** "Prepared: confirm to order. The agent prepares the order, a person confirms it (F-10): the purchasing manager confirms." The order waits as `PENDING_APPROVAL`. The earlier walkthrough had this order placed by the agent alone; that is no longer the default.
- **Ordering alone** is the buyer's setting `auto_order_enabled`, off in all four profiles. Valio Aimo, 14 Nov: "for now deactivate automatic order … the final submition should always have the input from the user", and of the setting: "after and if you are 100% sure yes". Switched on, the agent orders alone only when no other rule fires and price, quantity, delivery date, allergens and origin are confirmed on every line (`src/tta/policy/human_approval.py`). I did not re-measure the switched-on path; `tests/e2e/test_no_order_without_a_person.py` covers the default.

---

## 5. A product with no confirmed stock

The hotel asks for **100 litres of `473609`** (Oddlygood Barista oat drink). Its quantity is not confirmed, so the gateway looks for a substitute.

How a substitute is chosen (`src/tta/offers/substitutes.py`): candidates are the pairs Valio lists and the products of the same 5-digit category, nothing wider (Valio did not confirm that the digits are levels). In order:
1. The allergen rule: a substitute that adds an allergen the original does not declare can never be ordered, for any buyer (F-05).
2. Dietary claims: one that loses a claim such as lactose-free is a last resort, held back while a claim-keeper can be ordered.
3. The same kind of product: another product type, or a flavoured product for a plain one, is a last resort too.
4. The formula (six nutrients and the fat source), then listed by Valio, pack, verification, price.

Measured:
- **Recording's clock.** Option 1, "With a substitute for a product that cannot be supplied in full": 100 × `475224` Fazer Aito Professional Barista oat drink, **€174.00**, prepared for a person to confirm (F-10). Option 2: `473609` itself, €137.00, quantity not confirmed (F-01), to the purchasing manager.
- **Demo clock.** Option 1 is `473609` itself, €137.00 (F-01). Option 2 is the substitute Valio lists, 10 cases of `471690`, **€155.50**: 100 one-litre cartons become 10 cases of ten (Valio, on converting by volume: "yes the goal is to satisfy the prompt"). Its quantity is not confirmed either (F-01).

Other exception paths, measured at the recording's clock:

| Situation | What happens |
|---|---|
| 1,500 L of lactose-free milk | The same 435 L confirmed (1,065 L missing), €1,083.39; P-01 and P-03 send it to the purchasing manager. Alternative 1,500 × `464306`, €1,515.00 |
| 30 kg of beef chuck, sold by weight | 30 kg of `466988`, "about €506.40 … The total is an estimate: a product is sold by weight, and Valio Aimo invoices the weight delivered." P-06 (a product sold by variable weight) sends it to the purchasing manager |
| An agent tries to approve | 403, recorded as `authorisation.refused` |
| No `Idempotency-Key` on an order | 400 |
| A text the rules cannot read | 422 with a question |

Not re-measured here, and described in `AIMO/SPEC.md` and `AIMO/COVERAGE.md`: suggestions from the customer's pattern, standing orders, menus, the formula rule firing, evidence from a manufacturer's page.

---

## 6. The rules in one table

Read from `src/tta/policy/rules.yaml` and `src/tta/policy/human_approval.py`; the list is what `GET /v1/authority` answers. P-00 is retired.

| Rule | In its words | Outcome |
|---|---|---|
| **F-01** | A product whose quantity Valio Aimo does not confirm always goes to the purchasing manager | approval |
| **F-02** | A product that declares an allergen the buyer excludes can never be ordered, even with approval | block |
| **F-03** | When a fact a rule needs is missing, a human decides. Missing data never counts as good data | approval |
| **F-04** | An option that has expired, whose order cut-off has passed, or whose price or availability changed since the offer cannot be ordered. A fresh offer is needed | block |
| **F-05** | A substitute that declares an allergen the original product does not can never be ordered, for any buyer | block |
| **F-06** | An agent can never approve an order, its own included: approval routes refuse agent tokens | refused (403) |
| **F-07** | A product whose price is not confirmed or whose delivery date is ruled out, and an option that does not verifiably meet the needed-by date, always go to the purchasing manager | approval |
| **F-08** | A substitute that lacks a nutritional claim of the product it replaces, for example lactose-free, always goes to the purchasing manager | approval |
| **F-09** | A product type that recipe logic chose in place of a recipe's own ingredient always goes to the purchasing manager | approval |
| **F-10** | The agent prepares the order, a person confirms it. Driven by the buyer's setting, so listed as not fixed; lives in code | approval, purchasing manager |
| **F-11** | Where the formula matters (the profile or the request line says so), a substitute whose formula differs or cannot be compared always goes to the purchasing manager | approval |
| **F-12** | A substitute that is a last resort (it lacks a dietary claim, is flavoured where the original is not, or is another product type) always goes to the purchasing manager | approval |
| **P-01** | An order above the profile's limit per order goes to the purchasing manager | approval |
| **P-02** | When the day's orders, this one included, pass the limit per day, the order goes to finance | approval |
| **P-03** | An option that covers less than the profile's minimum share goes to the purchasing manager | approval |
| **P-04** | A product that does not rule out an excluded allergen goes to the dietitian | approval |
| **P-05** | A substitute outside what the profile accepts goes to the purchasing manager | approval |
| **P-06** | A product sold by variable weight goes to the purchasing manager: its total is an estimate | approval |
| **P-07** | A product that carries a deposit goes to finance: deposits have no published price | approval |
| **P-08** | A standing-order renewal whose quantity or unit price differs from the median of its last 6 renewals by more than the profile's tolerance goes to the purchasing manager | approval |
| **P-09** | An option ranked by a preference that costs more than the profile's share above the cheapest confirmed option goes to the purchasing manager | approval |

The strictest outcome among the rules that fire decides. A rules file that weakens a fixed rule is refused at start (`src/tta/policy/validation.py`).

---

## 7. The ways in

All surfaces call one service object, so no rule holds on one and not on another.

- **REST** under `/v1`, described in OpenAPI 3.1 at `/openapi.json` (generated from the code). `/v1/schemas` serves the JSON Schema of 96 models, each naming its dialect. `/.well-known/api-catalog`, `/llms.txt` and `/.well-known/jwks.json` are served. Routes beyond the core: `/v1/customers`, `/v1/menus/plan`, `/v1/standing-orders`. Valio's token cannot read a customer (403, measured).
- **MCP** at `/mcp/`, same tokens, **13 tools**: `get_authority`, `search_products`, `get_product`, `find_substitutes`, `get_offer`, `place_order`, `get_order`, `get_audit`, `get_customer`, `plan_menu`, `set_up_standing_order`, `renew_standing_order`, `list_standing_orders`. **None approves.** A request whose `Origin` header names a foreign web origin is refused with 403 (measured); a request with no `Origin` is served. The Host header is not checked.
- **The pages**, in `dev` and `demo` only, no login: the shop page at `/shop`, and the older pages `/`, `/kitchen`, `/menu`, `/standing-orders`, `/approvals`, `/orders/{id}`, `/assumptions`. All answered 200 in my run; **nobody has looked at them in a real browser**. Each browser gets its own in-memory order book (at most 300, dropped after 2 hours idle; `src/tta/api/sandbox.py`).
- **Limits per minute** (`src/tta/api/limits.py`, ours): one visitor 20 offers, 20 orders and decisions, 15 request readings; one address 60, 60, 60; all callers together 240 each. Bodies up to 64 KB.
- **The public link.** `deploy/modal_app.py` sets replay and the demo clock for it. Whether the link runs tonight's code was not checked: no redeploy was made in this run (`docs/DEPLOY.md`).

---

## 8. Check it yourself

From the repository root, in replay. The two empty settings keep a local `.env` from adding a model key or a shared database; `TTA_ENV=demo` is needed, because unset means `prod`.

```bash
mkdir -p /tmp/tta-check
GEMINI_API_KEY= DATABASE_URL= TTA_ENV=demo TTA_MODE=replay TTA_DB_PATH=/tmp/tta-check/w.sqlite3 \
  .venv/bin/python -m uvicorn --factory tta.api:create_app --port 8790
```

In a second terminal. The expected answers below are what the same calls gave through the application's test client at `c2106fe`; I did not start a server on a port.

```bash
B=http://127.0.0.1:8790; A="Authorization: Bearer demo-agent-hotel-kitchen"; J="Content-Type: application/json"

curl -s $B/healthz        # "mode":"replay", the clock sentence, "store":{"kind":"sqlite"}, "signing":{"demo_key":true}
curl -s $B/v1/authority -H "$A"      # the profile, 20 rules (F-01 to F-12 without F-06, P-01 to P-09), the summary

curl -s -X POST $B/v1/requests/parse -H "$A" -H "$J" -d '{"text":"Some cheese for Friday"}'
#   422, with "question", "not_read", "read_by":"rule-based"

curl -s -X POST $B/v1/offers -H "$A" -H "$J" -d '{"needed_by":"2026-11-16","lines":[{"text":"1,000 litres of lactose-free milk by Monday","product_type":"milk","required_claims":["FREE_FROM_LACTOSE"],"quantity":1000,"unit":"L"}]}'
#   201: opt_1 1083.39 APPROVAL [P-01, P-03]; opt_2 1010.0 APPROVAL [F-01, P-01]; 17 excluded; a "proof"

curl -s -X POST $B/v1/orders -H "$A" -H "$J" -H "Idempotency-Key: check-1" -d '{"offer_id":"<offer_id>","option_id":"opt_1"}'
#   201, "status":"PENDING_APPROVAL", an "approval_id"; without the Idempotency-Key header: 400
curl -s -X POST $B/v1/approvals/<approval_id>/decision -H "$A" -H "$J" -d '{"decision":"APPROVE"}'
#   403: "An agent cannot approve or reject an order (F-06). …"
curl -s -X POST $B/v1/approvals/<approval_id>/decision -H "Authorization: Bearer demo-approver-hotel-purchasing" -H "$J" -d '{"decision":"APPROVE","note":"Checked with the kitchen."}'
#   200, "status":"ORDERED", "placed_by":"HUMAN_APPROVAL"
curl -s "$B/v1/audit?order_id=<order_id>&reader=buyer" -H "Authorization: Bearer demo-approver-hotel-purchasing"
curl -s "$B/v1/audit?order_id=<order_id>&reader=supplier" -H "Authorization: Bearer demo-supplier-valio-aimo"
#   both: 10 events (9 plus the refused attempt), "chain":{"ok":true,…}; Valio's view shows no €750, no name, no note
```

For the demo clock add `TTA_DEMO_CLOCK=2026-11-12T14:15:00+02:00` to the first command: the same two options and totals, 2 excluded.

**The tests.** The scenarios over HTTP are in `tests/e2e/` (scenarios 1 to 3, the beef backup, the guards, the demo clock, "no order without a person"). I did not run the test folders for this document; the last whole-suite count in the build log is of wave 1 (`4049 passed, 6 failed, 68 skipped` on commit `db4c035`, the six being known pins since handed on), and later lanes ran their own folders only.

---

## 9. Known limits

- **Orders commit nobody.** `ORDERED` is a record in our order book. No order message reaches Valio and no payment is taken.
- **No model reads requests.** The fixed-rules reader is the product; it reads the shapes it knows and asks about the rest. Seven sentences have recordings of a model's reading and are answered from them, labelled.
- **Every customer value is ours.** Limits, people, usual products, order history (synthetic), thresholds.
- **In replay most of the catalog has no price.** The recording holds 769 of 17,546 products; a product outside it is left out as "not in the recording", never as undeliverable in Valio's name.
- **The proof is the gateway's, with a demo key** unless a key is set. Nothing is signed by Valio.
- **One process.** Limits, the pages' books and locks are in memory.
- **The audit chain** shows a changed, removed or inserted event; it cannot show the last events cut off unless another party holds an earlier head.
- **MCP:** no OAuth; tokens are handed out outside the protocol. Host is not checked.
- **Not run:** the pages in a browser, a redeploy with tonight's code, the new SQL view for Valio on PostgreSQL, a live call to Valio's mock tonight.

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
| `Q8` | Are deposits inside the price? | Totals leave deposits out and say so; P-07 sends the order to finance |
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

The run's full list, with reasons, is `AIMO/build/replan/DECISIONS.md` (B1 to B42). The ones a reader of this walkthrough meets:

| Decision | Where to change it |
|---|---|
| Ordering alone is a buyer setting, off by default; switched on it needs all five statements confirmed on every line | `auto_order_enabled` in the profile; `src/tta/policy/human_approval.py` |
| Milk for coffee is not milk | `src/tta/catalog/product_types.yaml` |
| A substitute is the same 5-digit category, the same product type, and not flavoured for plain | `src/tta/offers/substitutes.py`, `src/tta/catalog/kinds.py` |
| A last-resort substitute always goes to a person (F-12) | `src/tta/policy/rules.yaml` |
| The formula tolerances: 15% or 1 g, salt 0.25 g, same fat source | `src/tta/offers/formula.py` |
| The demo clock, Thursday 12 Nov 2026 14:15 | `TTA_DEMO_CLOCK` |
| The four customers, their limits and their synthetic history | `src/tta/policy/profiles/`, `src/tta/customers/data/` |
| Valio's view masks the buyer's amounts, allergens, names and notes, and says so | `src/tta/audit/readers.py`, `supplier_decisions.py` |
| Audit events carry the real time, not the demo clock | `src/tta/api/wiring.py` |
| One waiting or ordered order per offer; a retry with the same key returns the first order | `src/tta/orders/service.py` |
| Each browser of the pages gets its own order book | `src/tta/api/sandbox.py` |
| Offers and orders are signed by the gateway, with a demo key unless one is set | `src/tta/api/signing.py`, `TTA_SIGNING_KEY` |
