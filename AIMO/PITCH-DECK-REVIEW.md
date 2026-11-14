# Pitch deck review — `Trusted_Trade_Agents_Combined_Junction_Pitch.pptx`

Reviewed Sunday 15 Nov 2026, from 00:30, against code commit `016cc08`. The deck: 8 slides, saved 00:28, no pictures. Nothing in the deck or the repository was changed; this file is the only output.

**How to read the evidence.**
- **[M]** = measured by me on a local server from `016cc08`, replay only, no key, demo clock Thu 12 Nov 2026 14:15 (`TTA_MODE=replay`, port 8025), through the `/shop` routes or REST. No outside service was called and the public link was not called.
- `file:line` = a line of the repository at `016cc08`.
- Where a document and the code disagree, the code wins and the row says so. Stale documents met on the way: `docs/PITCH.md` (the deck's text follows it; it describes Saturday morning's code), `docs/DEMO.md:26` (names Mikko, Leena and others removed at 23:22), `docs/DEMO.md:97` and `:185` (scenario 3 and the cake, see section 3), `docs/STANDARDS.md:114` ("15 demonstration identities"; the code has 11) and `:11` ("26 paths"; the running gateway lists 27).
- The pitch is **five minutes** (João's correction). The speaker notes in the deck are timed for 3:00.
- **The code is still moving.** Decisions B55 to B63 (`AIMO/build/replan/DECISIONS.md`, written 00:49) are being built on top of `016cc08` and are not in what I measured. Two touch the deck: **B56** gives the brief's own sentence a third option (1,000 L from confirmed stock, 565 L of it a lactose-free coffee milk named as a substitute, confirmed by a person; "the first two options stay as they are"), and **B61** rewords the confirmation sentence. So: figures below are those of `016cc08`; **re-read the 1,000 L answer and any quoted sentence from the final commit before exporting the PDF** (one request on `/shop`).

---

## 1. Verdict

1. **The deck describes Saturday morning's product.** Its demo slide carries a total (€2,580.64) and an "AUTO" outcome the code has not given since Sat 14 Nov 17:37, and its solution slide says "AI understands the request" although nothing deployed calls a model.
2. **Every fault is text.** Of 67 statements checked, 45 are correct, 8 outdated, 9 wrong, 4 cannot be shown, 1 not verified. The structure and the look hold; three slides have a card that runs past the right margin.
3. **It under-shows what scores.** No end-to-end flow with figures (30%), nothing on how a request is read (20%), no "never" column and no "an agent cannot approve" (20%), standards named only as "REST + MCP" (15%), nothing of the suggestions or Valio Aimo's back office. Five minutes leave room for all of it: sections 4 and 5.

### Change before submitting (most important first)

Every figure in a replacement was measured [M] unless a source is given.

| # | Slide | It says (exact) | What is wrong | Replacement, ready to paste |
|---|---|---|---|---|
| 1 | 5, right card | "Three confirmed products combined" · "€2,580.64" | Saturday morning's answer. Since 17:37 on 14 Nov coffee milk is its own product type, so the third product (565 × `463380`) left the answer. Today: two products, 435 L | Sub-line: **"Two confirmed products cover 435 of the 1,000 L"** · Big figure: **"€1,083.39"** · Line under it: **"565 L missing · the full 1,000 L for €1,010.00 only with stock not confirmed"** · Bottom line: **"Above the €750 limit, below the 90% minimum → the purchasing manager confirms"** |
| 2 | 5, left card | "HOSPITAL · AUTO" · "200 L of a milk alternative" · "Confirmed + within €500 agent limit" | By default the ward's order waits for a person ("Prepared: confirm to order"). The agent orders alone only when the ward switches the setting on. And "milk alternative" is not the sentence that works: [M, over REST] the gateway answers it with a question; "milk substitute" is read | Tag: **"HOSPITAL WARD · ORDERING ALONE SWITCHED ON"** · Title: **"200 L of a milk substitute"** · Bottom line: **"Every statement confirmed + within the €500 limit + the ward switched ordering alone on → the agent orders. Switched off (the default): one click by a person."** |
| 3 | 4, headline | "AI understands the request. Rules control the action." | No model is called in what we deploy. Sentences are read by fixed rules that ask instead of guessing | **"Any agent asks. Fixed rules decide. A person confirms."** Sub-line: **"A typed interface, not a chatbot: the same for every agent, over REST and MCP, with decisions that can be checked."** |
| 4 | 4, verdict strip | "AUTO" "Agent acts within authority" | Off by default in all four demo customers since 17:37 on 14 Nov | **"AUTO"** **"The agent orders alone: only if the buyer switched it on and every statement is confirmed"** |
| 5 | 1 | "The agent proposes. The wholesaler decides." | The wholesaler decides nothing here. The buyer's own person confirms; Valio Aimo approves no order | **"The agent prepares the order. A person confirms it."** (the gateway's own sentence, `src/tta/policy/human_approval.py:32`) |
| 6 | 1 | "A trust layer that lets any purchasing agent order from Valio Aimo, safely and openly." | No order reaches Valio Aimo: "ordered" is a record in our order book | **"An open gateway that lets any purchasing agent read Valio Aimo's prices and stock, prepare an order, and stop for a person exactly where it should."** (`AIMO/SUBMISSION.md:36`) |
| 7 | 5, notes | "…records the order autonomously… Three confirmed products cover the request for €2,580.64… Since the hotel's limit is €750, the purchasing manager must approve." | Same two faults, spoken | Section 2, slide 5, "Notes" |
| 8 | 3, right card | "9%" "of sampled products had a stock value that means “unknown”" | 449 of the 1,000 sampled products carry such a value. 92 (9.2%) is the share that could still be ordered with it | **"of sampled products could still be ordered, but with a quantity Valio Aimo does not confirm"** |
| 9 | 3, header and sub-line | "THE PROBLEM IS IN THE DATA" · "Real supplier data contains gaps, ambiguity and changing availability." | Presents Valio Aimo's test data as faulty, in front of Valio Aimo; and the data is synthetic and static, not "real" and "changing" | **"WHAT A PURCHASING AGENT MEETS"** · **"Valio Aimo's test data behaves like real trade: stock that is not known, order cut-offs that pass, allergen fields left empty."** |
| 10 | 6, right panel | "ALREADY DEMONSTRABLE" "17,546" "catalog products" | Search covers 17,546. Prices and stock in the demo are a recording of 1,163 | **"17,546"** **"catalog products searchable"** and, smaller, **"prices and stock replayed for 1,163 recorded products · live mode asks Valio Aimo's API"** |
| 11 | 6, item 03 | "Stale price or stock" "Re-check before committing; build a fresh offer." | True in the code, but nothing changes in a replay, so it cannot be shown. And the rubric's third word, "delivery constraints", is missing from the slide | **"Delivery constraints"** **"A product that cannot be delivered is left out, with the reason; every line shows its order deadline."** |
| 12 | 8 | "Demo: [link]   ·   Code: [link]   ·   MIT licensed" | Placeholders | **"Demo: joaocostared--trusted-trade-agents.us-east.modal.run/shop · Code: github.com/joaocosta21/junction · MIT licensed"**. Two conditions, neither checked by me: the link answers `/shop` only after tonight's redeploy; the repository is private until someone makes it public |
| 13 | 5, footer | "DEMO LIMITATION  ·  “ORDERED” means recorded in our order book; the supplier mock has no real order endpoint." | The fact is right. The framing is not: the order step is ours by design, not a gap in the mock | **"BY DESIGN · Valio Aimo's test API gives price and availability. The order step is ours: “ordered” is a record in the gateway's order book and commits nobody."** |
| 14 | 7, step 04 | "Shared audit" "A log both buyer and Valio can verify" | Listed as future. It exists: one log, two views, the chain verifies for both | **"Witnessed audit"** **"Buyer and Valio Aimo each keep the head of the log, so nobody can rewrite its end"** |
| 15 | 7, notes | "Next come real supplier orders and multi-supplier integration." | "Multi-supplier" is in none of our next steps, and it is the outcome the brief wants to avoid ("before that interface gets defined by someone else's platform") | **"Next: an order message Valio Aimo's systems can take, customers' real limits and people, and Valio Aimo signing its own statements of price, stock and origin."** |
| 16 | 4, notes | "AI reads the purchase request, while explicit code verifies… The model never invents the permissions." | As row 3 | Section 2, slide 4, "Notes" |
| 17 | 3, 6, 1 notes | the "9%" sentence; "runs with 17,546 Valio catalog products, mock price and stock services"; "[team]", "the wholesaler stays in control" | As rows 8, 10, 5 | Section 2, under each slide |
| 18 | 3, 4, 7 layout | — | The third card of slides 3 and 4 and the card row of slide 7 run past the right margin the other slides keep | Section 2, "Layout" under each slide |

---

## 2. Slide by slide

Verdicts: **CORRECT** · **OUTDATED** (was true, changed; when) · **WRONG** · **CANNOT BE SHOWN** · **NOT VERIFIED**.

### Slide 1 — title

| Text on the slide | Verdict | What is true now, and where verified | Replacement |
|---|---|---|---|
| "JUNCTION 2026  ×  VALIO AIMO" · "Trusted Trade Agents" | CORRECT | The challenge's name (`AIMO/CHALLENGE.md:1`) | — |
| "The agent proposes. The wholesaler decides." | WRONG | The person who confirms is the buyer's: [M] "Ordered for €1,083.39 net with approval by Hanna Laine, Harbourside Hotel (purchasing manager)". Valio Aimo's token cannot decide an approval: [M] 403 "The supplier reads its view of the audit trail (GET /v1/audit) and nothing else." | "The agent prepares the order. A person confirms it." |
| "A trust layer that lets any purchasing agent order from Valio Aimo, safely and openly." | CANNOT BE SHOWN | [M] every order's note: "Recorded in the gateway's order book. The Valio Aimo mock has no order endpoint… It commits nobody." "Any agent" holds for REST and MCP as built; no third-party agent host was tried (`docs/STANDARDS.md:104`) | "An open gateway that lets any purchasing agent read Valio Aimo's prices and stock, prepare an order, and stop for a person exactly where it should." |
| Notes: "Hi, we're [team]. We built Trusted Trade Agents for Valio Aimo's challenge: a trust layer so any purchasing agent can order from Valio Aimo, and the wholesaler stays in control." | WRONG | "[team]" is a placeholder. "The wholesaler stays in control": as row 2; what Valio Aimo gets is its own view of the log and a back office | "Hi, we're ⟨team name⟩. Valio Aimo asked how a wholesaler can be safely and openly readable by autonomous agents. We built that gateway: any agent can ask, fixed rules decide what it may do, and a person confirms the order." |

Layout (as rendered by LibreOffice): slides 1 and 8 have no blue top bar, no footer and no page number, and ask for Calibri and Arial where slides 2–7 ask only for Inter. They look like another deck. Not a fault of content.

### Slide 2 — "THE HUMAN BEHIND THE ORDER"

| Text on the slide | Verdict | What is true now, and where verified | Replacement |
|---|---|---|---|
| "THE HUMAN BEHIND THE ORDER" · "A simple request. A high-stakes decision." · "Finding products is easy. Trusting an agent to buy them isn’t." | CORRECT | Framing, no fact to check. See section 4: the slide opens on a person and a sentence in quotation marks, which reads as a chat product | Add under the two lines: "Valio Aimo's question: how can a wholesaler be “safely and openly readable by autonomous agents”?" (verbatim, `AIMO/CHALLENGE.md:30`) |
| "HANNA  ·  HOTEL BUYER" · "Illustrative purchasing manager" | CORRECT | [M] the hotel's customer file: contact "Hanna Laine", "Purchasing manager", Harbourside Hotel, `synthetic: true`. One of Valio Aimo's mentors is also called Hanna (`AIMO/CHALLENGE.md:75`); the surname avoids the look of having named her | "HANNA LAINE · HARBOURSIDE HOTEL" · "Synthetic demo customer · purchasing manager" |
| "“I need 1,000 litres of lactose-free milk by Monday.”" | CORRECT | The brief's own sentence (`AIMO/CHALLENGE.md:25`). In the brief "a hotel chain's agent sends this request" (`:27`), not a person | Small label above the quote: "THE BRIEF'S OWN REQUEST" |
| "01" "SAFE?" "Dietary requirements" | CORRECT | Allergen rules F-02 and P-04 (`src/tta/policy/rules.yaml:208`, `:476`) | — |
| "02" "AVAILABLE?" "Confirmed stock & delivery" | CORRECT | Rules F-01 and F-07 (`rules.yaml:192`, `:283`) | — |
| "03" "AUTHORIZED?" "Buyer-specific limits" | CORRECT | Rules P-01 to P-03 and the four profiles (`src/tta/policy/profiles/*.yaml`). The limits are ours and illustrative | — |
| Notes: "Everything starts with a person. Hanna, a hotel purchasing manager, needs 1,000 litres… That is the trust problem." | CORRECT | — | — |

Footer "01 / 06": slides 2–7 are numbered 01–06 of 06 in an 8-slide deck. Renumber when slides are added.

### Slide 3 — "THE PROBLEM IS IN THE DATA"

| Text on the slide | Verdict | What is true now, and where verified | Replacement |
|---|---|---|---|
| "EVIDENCE FROM SUPPLIER DATA" · "THE PROBLEM IS IN THE DATA" | WRONG | Framing against the project's own rule: "The mock's behaviour is the scenario, not a fault" (`CLAUDE.md`, "How to think about the mock"). Valio Aimo's people are the jury | "WHAT A PURCHASING AGENT MEETS" (both places) |
| "An agent that guesses will get it wrong." | CORRECT | Matches the reader, which asks: [M] "1.000 litres of lactose-free milk by Monday" → "Is it 1,000 or 1? Write 1000 for the first, or 1 for the second." | — |
| "Real supplier data contains gaps, ambiguity and changing availability." | WRONG | The data is synthetic ("everything you build against is synthetic", `AIMO/CHALLENGE.md:52`) and static: [M] the gateway's own clock sentence, "Valio Aimo said on 14 Nov 2026 that its test data is static" | "Valio Aimo's test data behaves like real trade: stock that is not known, order cut-offs that pass, allergen fields left empty." |
| "25%" "of sampled products had confirmed stock and an open cut-off" "1,000-PRODUCT API SAMPLE" | CORRECT | Recomputed from the saved sample (`fixtures/valio/2026-11-13-sample`, taken Fri 13 Nov 23:00): 252 of 1,000. It moves with the clock: at that moment 42% were past their cut-off | Label: "1,000-PRODUCT API SAMPLE · FRI 13 NOV, 23:00" |
| "46.2%" "of the full product catalog had no allergen statement" "17,546-PRODUCT CATALOG" | CORRECT | Counted with the project's own loader over the product file: 8,110 of 17,546. The catalog includes non-food; `AIMO/FINDINGS.md:76` gives 30.6% for food products (not recomputed by me). Expect the question | — |
| "9%" "of sampled products had a stock value that means “unknown”" "1,000-PRODUCT API SAMPLE" | WRONG | Recomputed from the same sample: 449 of 1,000 carry a placeholder amount (999,999 or more). 92 (9.2%) is the share with such a value **and** an open cut-off, that is, still orderable with a quantity that is not confirmed | "of sampled products could still be ordered, but with a quantity Valio Aimo does not confirm" |
| "LACTOSE-FREE  ≠  MILK-FREE" · "A nutritional claim is not an allergen declaration." | CORRECT | `src/tta/allergens/exclusion.py:3`: "`FREE_FROM_LACTOSE` is not a statement about milk" | — |
| "Source: team analysis of Valio Aimo catalog and 13 Nov 2026 mock API sample. Sample percentages are not catalog-wide." | CORRECT | Sample manifest: `time_now` 2026-11-13T23:00:35+0200. Keep this line: it is the "visibility of assumptions" the 15% criterion asks for | — |
| Notes: "The data makes this harder. In our 1,000-product API sample, just 25% had confirmed stock and an open ordering window; 9% had a placeholder meaning stock was unknown. Across the catalog, 46% had no allergen declaration. And lactose-free does not mean milk-free. An AI cannot safely guess." | WRONG | The 9% clause, as above; "the data makes this harder" blames the data | "This is what an agent meets in Valio Aimo's test data. When we sampled 1,000 products on Friday night, 25% had confirmed stock and an open order cut-off, and another 9% could be ordered only with a quantity Valio Aimo does not confirm. Across the whole catalog of 17,546 products, 46% carry no allergen statement. And lactose-free does not mean milk-free. So the agent must never guess: unknown is not safe." |

Layout (in the file, not a rendering effect): the three cards are 3.94 in wide; the third ends at 13.06 in, where the content of slides 5 and 6 ends at 12.58 in. Make each card 3.78 in wide: left edges at 0.72, 4.76 and 8.80 in.

### Slide 4 — "OUR SOLUTION"

| Text on the slide | Verdict | What is true now, and where verified | Replacement |
|---|---|---|---|
| "AI understands the request. Rules control the action." | OUTDATED | True of Saturday morning, when Gemini read the requests. Dropped Sat 14 Nov 17:33 (`AIMO/build/replan/STATUS.md`, "João's changes"). Today: [M] `/healthz` says `gemini_key_set: false`, `agent_provider: none`; [M] a typed sentence comes back `TTA-Read-By: rule-based`; the deploy sends no model key unless asked (`deploy/modal_app.py:124`, `:262`). A Gemini Flash reader exists as an option and answered once in a test at 22:27 (log); nothing deployed calls it | "Any agent asks. Fixed rules decide. A person confirms." |
| "Trusted Trade Agents connects buyer agents to supplier data with decisions that can be checked." | CORRECT | [M] "The audit trail is intact: each of the 10 events shown here matches its hash, and the chain they belong to verifies." | Add: "A typed interface, not a chatbot." |
| Left box: "AI" "BUYER AGENT" "REST / MCP" | CORRECT | [M] OpenAPI 3.1.0 with 27 paths; [M] `/mcp/` lists 13 tools. The agent is the buyer's and may be any agent; the demo's own agent is a fixed three-call run, labelled "rule-based" (`src/tta/agent/rules_model.py:9`, `:28`) | Circle "AI" → keep; add under "REST / MCP": "any agent" |
| Centre: "TTA  /  TRUSTED TRADE AGENTS" · "VERIFY" "facts" · "RANK" "options" · "CONTROL" "rules" · "AUDIT" "decisions" | CORRECT | Verify: [M] five statements on every line, each with a status (price, quantity, delivery date, allergens, origin; `src/tta/policy/human_approval.py:45`). Rank: [M] "Best confirmed option" first, alternatives labelled. Control: `src/tta/policy/rules.yaml`. Audit: [M] 10 events for one order | Section 5, slide C, for the fuller diagram |
| Right box: "V" "VALIO AIMO" "Price & availability" | CORRECT | The test API has price and availability and no order endpoint (`AIMO/FINDINGS.md:16`). In the demo the answers come from a recording | — |
| The two arrows: BUYER AGENT → TTA → VALIO AIMO | CORRECT | True as far as it goes. Missing: the person who confirms, the order book, and Valio Aimo's own view of the log (an arrow back). The 20% criterion is about exactly these | Section 5, slide C |
| "ONE GATEWAY. THREE VERDICTS." | CORRECT | `src/tta/contracts/common.py:185`–`187`: AUTO, APPROVAL, BLOCK | — |
| "AUTO" "Agent acts within authority" | OUTDATED | Since B0 (Sat 14 Nov 17:37) ordering alone is a buyer's setting, off in all four profiles (`auto_order_enabled: false`, e.g. `profiles/hotel-kitchen.yaml:14`); rule F-10 sends every other order to a person. Reason, in Valio Aimo's words of 14 Nov: "the final submition should always have the input from the user" (`human_approval.py:3`) | "The agent orders alone: only if the buyer switched it on and every statement is confirmed" |
| "APPROVAL" "A named human decides" | CORRECT | [M] the log names the person and the role | — |
| "BLOCK" "Unsafe action is refused" | CORRECT | F-02, F-04, F-05 (`rules.yaml:208`, `:236`, `:261`). [M] "The substitute adds 1 allergen that the original does not declare: cereals containing gluten (AW, contains). It can never be ordered as a substitute." | — |
| Notes: "Trusted Trade Agents solves that gap. It sits between buyer agents and Valio Aimo. AI reads the purchase request, while explicit code verifies product facts, ranks alternatives, applies buyer-specific rules, and logs decisions. The outcome is clear: buy autonomously, request approval, or block. The model never invents the permissions." | OUTDATED | As the headline | "Trusted Trade Agents sits between a buyer's agent and Valio Aimo's price and availability data. It is a typed interface, not a chatbot: REST and MCP, the same for any agent. Code checks five statements on every line (price, quantity, delivery date, allergens, origin), ranks the options, applies the buyer's rules and logs every step. Three outcomes: the agent may order alone, a named person must confirm, or the order is refused. By default a person confirms every order. No model decides anything, and over REST and MCP an agent's token can never approve." |

Layout (in the file): the three verdict cards are 3.95 in wide; the third ends at 13.10 in. Make each 3.77 in wide: left edges at 0.75, 4.78 and 8.81 in.

### Slide 5 — "WORKING DEMO"

| Text on the slide | Verdict | What is true now, and where verified | Replacement |
|---|---|---|---|
| "TWO END-TO-END OUTCOMES" · "WORKING DEMO" · "Same system. Two responsible outcomes." | CORRECT | — | — |
| "These scenarios run against Valio’s recorded mock data." | CORRECT | [M] `/healthz`: mode replay, 1,163 recorded products (769 recorded Sat 14 Nov 02:52, 394 at 21:12), demo clock Thu 12 Nov 14:15 | "Run on `/shop` against a recording of Valio Aimo's test data (1,163 products, Sat 14 Nov), at the demo clock Thu 12 Nov 14:15." |
| "HOSPITAL  ·  AUTO" | OUTDATED | Since Sat 17:37 (B0). [M] with the ward's profile as shipped: "Prepared: confirm to order. The agent prepares the order, a person confirms it (F-10)". [M] with "Let the agent place orders alone" switched on in Settings (`src/tta/ui/static/shop/js/views/settings.js:260`): status ORDERED, placed by the agent; the sentence is "The agent placed this order alone for €402.00 net: no rule asked for a human and every statement of the offer is confirmed." (`src/tta/orders/wording.py:82`) | "HOSPITAL WARD · ORDERING ALONE SWITCHED ON" |
| "200 L of a milk alternative" | WRONG | [M] "200 litres of a milk alternative by Monday…" → 422, "Which product should be offered instead? Name it, for example oat drink or soya drink." [M] "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only" is read and answered. If a judge types the slide's words, the demo asks a question | "200 L of a milk substitute" |
| "No milk · no gluten · confirmed only" | CORRECT | `profiles/allergy-ward.yaml:18`, `:23` | — |
| "€402" | CORRECT | [M] €402.00 before tax | "€402.00" |
| "200 × Alpro No Sugars Soya Drink" | CORRECT | [M] 200 × `464013` "Alpro No Sugars Soya drink 1L" | — |
| "✓" "Confirmed + within €500 agent limit" | OUTDATED | Both facts hold (`profiles/allergy-ward.yaml:15`; [M] all five statements CONFIRMED). Since Sat 17:37 they are not enough: the buyer must also have switched ordering alone on | "Every statement confirmed + within the €500 limit + the ward switched ordering alone on → the agent orders. Switched off (the default): one click by a person." |
| "HOTEL  ·  HUMAN APPROVAL" · "1,000 L of lactose-free milk" | CORRECT | [M] | — |
| "Three confirmed products combined" | OUTDATED | Until Sat 17:37 the answer was 384 × `469363` + 51 × `462775` + 565 × `463380` (`AIMO/BOOTH-QUESTIONS.md:462`). `463380` is a coffee milk; B0 made coffee milk its own type. [M] now: 384 × `469363` + 51 × `462775` = 435 L, and the offer says "Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk." | "Two confirmed products cover 435 of the 1,000 L" |
| "€2,580.64" | OUTDATED | Same change. [M] €1,083.39 before tax for the 435 L | "€1,083.39" |
| "Cheaper €1,010 option: stock unconfirmed" | CORRECT | [M] 1,000 × `464306`, €1,010.00, rule F-01: "Quantity not confirmed: Valio reports 9,999,999,999 ST, a placeholder that means the stock is not known." | "565 L missing · the full 1,000 L for €1,010.00 only with stock not confirmed" |
| "!" "€750 limit → manager sign-off" | CORRECT | [M] P-01 (above €750) and also P-03: "Only 43.5% of the requested quantity is covered, below the 90% minimum" | "Above the €750 limit, below the 90% minimum → the purchasing manager confirms" |
| "DEMO LIMITATION  ·  “ORDERED” means recorded in our order book; the supplier mock has no real order endpoint." | CORRECT | The fact: [M] the order's note. The words "limitation" and "no real" present a design decision of the challenge as a gap (`CLAUDE.md`: "There is no order endpoint, and that is by design") | "BY DESIGN · Valio Aimo's test API gives price and availability. The order step is ours: “ordered” is a record in the gateway's order book and commits nobody." |
| Notes: "Here is the working demo. A hospital requests 200 litres of a milk alternative, excluding milk and gluten. The gateway selects a confirmed product for €402, within the €500 authority limit, and records the order autonomously. A hotel needs 1,000 litres of lactose-free milk. Three confirmed products cover the request for €2,580.64. The system also shows a cheaper €1,010 option, but flags its stock as unconfirmed. Since the hotel's limit is €750, the purchasing manager must approve. Two decisions, each based on evidence. These are demo order records, not real supplier transactions." | OUTDATED | As the rows above | "The brief's own request, on a recording of Valio Aimo's test data. A hotel asks for 1,000 litres of lactose-free milk by Monday. Confirmed stock covers 435 litres, for €1,083.39. The gateway says 565 litres are missing, and names a cheaper option for the full quantity, €1,010, whose stock Valio Aimo does not confirm. That is above the hotel's €750 limit and below its 90% minimum, so the purchasing manager confirms, with one click, and the log says who and why. Second, a hospital ward: 200 litres of a milk substitute, no milk, no gluten, confirmed data only. One soya drink passes, €402. By default a person confirms. If the ward switches ordering alone on, the agent places it, because every statement is confirmed and it is within the €500 limit. The order step is ours by design: an order here is a record in our order book." |

Layout: none.

### Slide 6 — "PROOF IT CAN WORK"

| Text on the slide | Verdict | What is true now, and where verified | Replacement |
|---|---|---|---|
| "INNOVATION + IMPLEMENTATION" · "PROOF IT CAN WORK" · "Built for the exceptions, not just the happy path." · "A functional gateway with traceable decisions and open interfaces." | CORRECT | — | — |
| "01" "Partial availability" "Combine confirmed stock; show what is missing." | CORRECT | [M] 384 + 51 = 435 of 1,000 L; the back office says "565 L, about €1,407 at the offered price, were not [confirmed]" | Add the case: "435 of 1,000 L confirmed; the 565 L missing are said, never hidden." |
| "02" "Unsafe substitution" "Block added allergens and flag dietary changes." | CORRECT | F-05 blocks (`rules.yaml:261`), F-08 sends a lost dietary claim to a person (`:319`). [M] for oat drink `473609`, substitutes `471881` and `464320` add gluten: "It can never be ordered as a substitute." | — |
| "03" "Stale price or stock" "Re-check before committing; build a fresh offer." | CANNOT BE SHOWN | In the code: every order is checked again (`src/tta/orders/checking.py:1`); a stale or expired offer is refused with a fresh offer's id (`src/tta/api/service.py:337`–`346`). [M] a confirmed order's log says "Price and availability were checked again and had not changed." In a replay nothing changes, so the stale case never happens on screen. For an order already waiting for a person, a change blocks it and no fresh offer is built (`docs/STANDARDS.md:184`) | "Delivery constraints" "A product that cannot be delivered is left out, with the reason; every line shows its order deadline." ([M] `464440` "cannot be delivered"; [M] "for delivery on Monday 16 Nov if ordered by Sunday 15 Nov at 17:00") |
| "ALREADY DEMONSTRABLE" "17,546" "catalog products" | CANNOT BE SHOWN | The count is right (product file, counted) and search runs over all of it ([M] a search by name answered from the whole catalog). Price and stock in the demo exist for the 1,163 recorded products only. As set, the big number reads as "17,546 products with live prices" | "17,546" "catalog products searchable" + "prices and stock replayed for 1,163 recorded products · live mode asks Valio Aimo's API" |
| "REST + MCP" | CORRECT | [M] 27 REST paths, 13 MCP tools | "REST + MCP · 13 tools, none approves" |
| "Open APIs · audit events · live/replay modes" | CORRECT | OpenAPI 3.1 [M]; events `tta.v1.*` [M]; `TTA_MODE` live or replay; the public link is deployed in replay (`deploy/modal_app.py:109`) | "OpenAPI 3.1 · JSON Schema · problem details (RFC 9457) · signed offers (Ed25519)" (the standards by name score; "live/replay modes" does not). Do not write "CloudEvents": decision B63 lists "the audit trail as CloudEvents at the interface" as a next step, and [M] an event read from `/v1/audit` carries no `specversion` |
| "AUDIT TRAIL  ·  Request received  →  Offer created  →  Policy checked  →  Human approval / auto-order" | CORRECT | [M] one order's events: request.received, request.parsed, lookup.performed, offer.created, policy.evaluated (×2), suggestions.shown, approval.requested, approval.decided, order.confirmed | "AUDIT TRAIL · Request → Lookup → Offer → Rules → A person confirms → Ordered · 10 events, one sentence each, two views: the buyer's and Valio Aimo's" (uses the rubric's own word "lookup") |
| Notes: "We have also built for exceptions: partial availability, unsafe substitutes, and price or stock changes before ordering. Every step is auditable. The gateway runs with 17,546 Valio catalog products, mock price and stock services, and open REST and MCP interfaces. Real supplier ordering remains the next integration step." | CANNOT BE SHOWN | The demo and the public link run on the recording, not on the mock's services | "The exceptions are the normal case, so each has an answer. Partial availability: what is missing is said. A substitute that adds an allergen is refused for every buyer. A product that cannot be delivered is left out, with the reason. Every step is one sentence in a hash-chained log that the buyer and Valio Aimo each read in their own view. All 17,546 catalog products can be searched; the demo replays prices and stock recorded for 1,163 of them, and live mode asks Valio Aimo's API." |

Layout: none.

### Slide 7 — "IMPACT & VISION"

| Text on the slide | Verdict | What is true now, and where verified | Replacement |
|---|---|---|---|
| "IMPACT & VISION" · "One trusted layer. Many buyers." · "The same infrastructure can support purchasing teams across sectors." | CORRECT | Four buyer profiles run on one gateway (`src/tta/policy/profiles/`) | Add: "Four demo customers, all synthetic." |
| "HOSPITALS" "Dietary safety" · "SCHOOLS" "Budget control" · "HOTELS" "Operational continuity" · "BAKERIES" "Ingredient consistency" | CORRECT | The four demo customers: ward (no milk, no gluten, strict), school (no tree nuts, peanuts, sesame, strict; €250 per order), hotel (€750 per order, 90% minimum), bakery (the recipe must be kept). What the build shows for the school is the allergen rule and its dietitian more than budget | "SCHOOLS" "Allergens: a dietitian decides" · "HOTELS" "Limits and partial deliveries" · "BAKERIES" "Substitutes must keep the recipe" |
| "A CREDIBLE PATH FORWARD" · "01" "Real orders" "Order messages in an open e-procurement format (Peppol BIS Ordering)" | CORRECT | A next step, not started (`docs/STANDARDS.md:174`) | — |
| "02" "Real rules" "Customers' actual limits, approvers and roles" | CORRECT | `docs/STANDARDS.md:177` | — |
| "03" "Real identity" "OAuth-issued agent tokens and sign-in" | CORRECT | `docs/STANDARDS.md:178` | — |
| "04" "Shared audit" "A log both buyer and Valio can verify" | WRONG | It is built: [M] the same order read as buyer and as Valio Aimo, 10 events each, "the chain they belong to verifies" for both. What is not built: nobody outside holds the head of the chain (`docs/STANDARDS.md:144`, `:179`) | "Witnessed audit" "Buyer and Valio Aimo each keep the head of the log, so nobody can rewrite its end" |
| "05" "Signed claims" "Supplier-signed price, stock and origin" | CORRECT | A next step (`docs/STANDARDS.md:175`). Today the gateway signs every offer and order itself: [M] `proof` with EdDSA, `demo_key: true` | — |
| Notes: "The same infrastructure can serve hospitals, schools, hotels and bakeries, reducing repetitive checks while keeping decisions accountable. Next come real supplier orders and multi-supplier integration. The future of AI purchasing is not an agent that buys everything. It is an agent that knows when to act — and when to ask." | WRONG | "Multi-supplier integration" is in no list of next steps (`docs/STANDARDS.md:170`–`184`) and describes the platform the brief warns about (`AIMO/CHALLENGE.md:30`). The last two sentences are said again on slide 8 | "The same gateway serves a hospital ward, a school, a hotel and a bakery, each with its own limits and rules: four demo customers, all synthetic. Next: an order message Valio Aimo's systems can take, in an open format such as Peppol; customers' real limits and people; OAuth for agents; and Valio Aimo signing its own statements of price, stock and origin." |

Layout (in the file): the four sector cards run from 0.39 in to 12.93 in, wider than the content band of the other slides (0.75 to 12.58 in); make each 2.82 in wide with 0.18 in between, starting at 0.75 in. The five description boxes under the steps are 1.40 in high from 6.21 in, so they end at 7.61 in, below the slide's edge (7.5 in) and over the footer line; set their height to 0.85 in. As rendered by LibreOffice: the grey description text is hard to read on the dark background; circle 01 is filled and the others are not, which reads as "step 1 is done", and it is not started.

### Slide 8 — closing

| Text on the slide | Verdict | What is true now, and where verified | Replacement |
|---|---|---|---|
| "The future of AI purchasing isn't an agent that buys everything." · "It's an agent that knows when to act, and when to ask." | CORRECT | Matches rule F-10 and the reader that asks | — |
| "Everything starts with the human and ends with the human." | CORRECT | By default a person confirms every order | — |
| "Trusted Trade Agents" · "Demo: [link]   ·   Code: [link]   ·   MIT licensed" | NOT VERIFIED | MIT is right (`LICENSE:1`). The two links are placeholders. The public address is `https://joaocostared--trusted-trade-agents.us-east.modal.run`; I did not call it, and the log of 00:27 says it still ran Saturday morning's code with `/shop` answering 404. The repository is `github.com/joaocosta21/junction` (git remote), private at 20:55 (`DECISIONS.md` A3) | "Demo: joaocostared--trusted-trade-agents.us-east.modal.run/shop · Code: github.com/joaocosta21/junction · MIT licensed". Open both in a private window before exporting |
| Notes: "The future of AI purchasing isn't an agent that buys everything… That's Trusted Trade Agents. Thank you." | CORRECT | Repeats the end of slide 7's notes; with the new notes for slide 7 it is said once | — |

**Fonts, all slides.** Slides 2–7 ask for Inter, embedded in the file. LibreOffice does not use the embedded font and this machine has no Inter, so my rendering shows a serif stand-in. Export the PDF from the tool the deck was made in, and look at every page of the PDF: a missing font moves line breaks.

**The notes do not reach the form.** The form takes a PDF; speaker notes are not in it. Anything a peer reviewer must know has to be on a slide.

---

## 3. What changed in the product since the deck's content was written

The deck's text follows `docs/PITCH.md`, which describes Saturday morning's code. Since then (times from `AIMO/build/replan/STATUS.md`; all Sat 14 Nov unless said):

| When | What changed | The one sentence a slide could carry |
|---|---|---|
| 17:37 (B0) | A person confirms every order by default; ordering alone is a buyer's setting, off for all four customers | "The agent prepares the order. A person confirms it with one click." |
| 17:37 (B0) | Coffee milk is its own product type, so the brief's sentence answers 435 L, not 1,000 L | "435 of 1,000 L are confirmed, for €1,083.39. The gateway says so instead of filling the order with coffee milk." [M] |
| 17:33, 18:07 (L1) | No model is called; fixed rules read the sentence and ask when unsure | "Asked for “1.000 litres”, it answers: “Is it 1,000 or 1?”" [M] |
| 19:55 (L4-2b) | Every offer and order record is signed by the gateway (Ed25519), key published | "Every offer is signed. Any agent can check it with the published key." [M] |
| 19:30 (L4b) | Discovery: `/.well-known/api-catalog`, `/llms.txt`; 13 MCP tools (8 on Saturday morning, `AIMO/WALKTHROUGH.md:3`) | "An agent that knows only the address finds every way in." [M] |
| 18:29–20:59 (L2b, L5, SG) | Suggestions: the forgotten item, Valio Aimo's own suggestion only with a stated benefit; shown, never added | "“With this milk you usually also order cooking cream: 7 of your last 8 orders. Adding 10 L costs €33.10.” One click adds it." [M] |
| 21:24 | Everything a person does is on `/shop`; the older pages are not the demo | "One page: ask, confirm, read the log." |
| 21:37, 22:45 (U4, RG, U5) | A reorder prompt, an alert when a request repeats a regular order, settings for limits | "“You ordered this in 4 of your last 4 weekly orders. Order the same again for Monday?”" [M] |
| 21:56, 22:55 (FC, LF) | A substitute must keep the recipe: the same ingredients, not only the same nutrition figures; learned per customer | "For a bakery, a cream with another ingredient list is not the same cream: a person decides." (`docs/DEMO.md:173`; not re-measured by me) |
| 22:00 (CK) | A menu planner: a dish becomes one order | "“A chocolate cake for 20” becomes seven ingredient lines: €15.19 for the four with confirmed stock, €22.50 for all seven with three not confirmed." [M]; `docs/DEMO.md:185` still says €104.65 |
| 23:03 (BO) | A back office for Valio Aimo: what the agent channel sold, suggestions shown and accepted, sales that could not be made | "Valio Aimo sees the sale it could not make: 565 L, about €1,407, in this one request." [M] |
| 23:22 (SIMP) | One person confirms. Hotel and bakery: the person who orders holds every role. Ward and school: a dietitian besides, for allergen questions. 11 demo identities, not 15 | "One person, one click. A dietitian only where a customer has one." (`src/tta/api/demo_tokens.yaml:16`–`19`) |
| B52, in `016cc08` | Scenario 3 (stock-out) now leads with a confirmed product at the demo clock too | "Out of stock? A confirmed like-for-like product first (€174.00), the product asked for second, as “quantity not confirmed” (€137.00)." [M]; `docs/DEMO.md:97` still says nothing is confirmed |
| Sun 00:49 (B56 to B62), **not yet in the code I measured** | A third option for the brief's sentence (coffee milk as a named substitute); one demo agent with ordering alone on over REST and MCP; settings changes logged; "an agent cannot approve" is claimed for REST and MCP, and the demo page is said to have no login | Re-measure after the final commit before quoting |

Tech awards (Modal, Context.dev, Aiven; Gemini not entered, `docs/AWARDS.md:3`) are not on the deck and need not be: nothing to correct there.

---

## 4. The five minutes: what is missing, what to add, the order

### What the deck does not make visible, by criterion

| Criterion | What the deck shows today | What is missing |
|---|---|---|
| **30%** working end-to-end demo: "request → lookup → order/approval… not just isolated pieces" | Two result cards (slide 5), one of them with Saturday morning's figures | The flow itself, in the rubric's words, with the real figures; the demo link; a live run |
| **20%** "how Precisely the agent matches what the buyer actually asked for" | Nothing | How a sentence is read and shown back; that it asks instead of guessing; that coffee milk is not passed off as milk |
| **20%** autonomy and controls | Three verdicts (slide 4); an audit strip (slide 6) | The "never" column; that an agent's token cannot approve; who confirmed, in the log; the two views of the log |
| **15%** exceptions: "partial availability, substitutions and delivery constraints" | Partial availability, unsafe substitution, stale offer (slide 6) | Delivery constraints (the rubric's third word); the ranking of substitutes; the allergen doubt |
| **15%** openness and path to production | "REST + MCP", "Open APIs"; five next steps (slide 7) | The standards by name; what an agent can verify by itself; our assumptions said plainly |
| Valio Aimo's own sentence: "safely and openly readable by autonomous agents", "not… a chatbot" | Not on the deck. Slides 2 and 4 read the other way: a person, a sentence in quotation marks, "AI understands the request" | The sentence itself, and "a typed interface, not a chatbot" |
| Junction main prize: innovation, impact, implementation | Slide 6 header "INNOVATION + IMPLEMENTATION"; slide 7 "IMPACT" with four sectors | What is new (a wholesaler-side gateway that stops for a person and says what it does not know); who gains (the buyer: suggestions; Valio Aimo: a back office) |

Nothing on the deck names a tech sponsor, a model vendor or a competitor: nothing to remove on that count.

### Recommended order for 5:00 (300 seconds)

Slides lettered A to J are described in section 5. "Existing n" is a slide of the current deck with the fixes of section 1.

| # | Slide | Seconds | The one thing the jury must believe | First sentence the speaker says |
|---|---|---|---|---|
| A | Title (existing 1, fixed) | 10 | This team answered Valio Aimo's question, not another one | "Valio Aimo asked how a wholesaler can be safely and openly readable by autonomous agents. We built that gateway." |
| B | The request (existing 2, with Valio Aimo's sentence) | 20 | The hard part is not finding products, it is knowing what an agent may be trusted with | "Hanna buys for a hotel kitchen, and soon her agent sends this for her: a thousand litres of lactose-free milk by Monday." |
| C | What we built (existing 4, redrawn) | 25 | It is an interface for any agent, not a chatbot; rules decide; a person confirms | "This is a typed interface, not a chatbot: any agent calls it over REST or MCP, fixed rules decide, and a person confirms." |
| D | **New:** the brief's sentence, end to end | 20 | The whole flow runs: request, lookup, offer, rules, order, log | "Here is the brief's own sentence, end to end, with the real figures." |
| — | **Live demo on `/shop`** | 70 | It works in front of you, and it says what it does not know | "Now the same request, live." |
| P | **New:** it asks instead of guessing | 20 | What comes back is what was asked for, or a question | "The agent orders what was asked, or it asks. It never guesses." |
| E | **New:** the guardrails table | 35 | The line between agent and person is exact, and some things no setting can switch on | "Three columns: what the agent does alone, what a person confirms, and what nothing can switch on." |
| F | Exceptions (existing 6, left half, with slide 3's figures as a strip) | 25 | Exceptions are the normal case here, and each has an answer | "In Valio Aimo's test data the exception is the normal case, so each one has an answer." |
| G | **New:** the trust protocol and the standards | 25 | An outside agent can check what it is told without trusting us | "An agent should not have to trust us. Here is what it can check by itself." |
| H | **New:** it also sells | 20 | Buyers and Valio Aimo both gain from the channel | "And it sells: for the buyer, and for Valio Aimo." |
| I | Honest limits and next steps (existing 7, redrawn) | 20 | The team knows what is illustrative and what a pilot needs | "What is ours and illustrative, we say. Here is what a pilot needs next." |
| J | Closing (existing 8, with the links) | 10 | — | "The future of AI purchasing isn't an agent that buys everything. It's one that knows when to act, and when to ask." |
| | **Total** | **300** | | |

Existing slide 3 ("the data") leaves the main run: its three figures become one strip on slide F, and the slide itself, corrected, goes after J as a back-up for questions. Reason: in the first minute it shows Valio Aimo's data as a problem before showing anything we built, and it scores on no criterion by itself.

### The live demo: where, how long, and the condition

- **Where:** straight after slide D, for 70 seconds. D shows the figures the jury is about to see, so a slow click costs nothing.
- **What:** on `/shop`, as Harbourside Hotel: type "1,000 litres of lactose-free milk by Monday" → the answer (435 L confirmed, €1,083.39, 565 L missing, the €1,010.00 alternative) → "Confirm order" → the log → Valio Aimo's view of the same log. Every step measured [M] through the page's own routes.
- **Run it from a laptop, in replay** (the command is in `docs/DEMO.md:13`–`17`), so it does not depend on the venue's network or on the public link, which at 00:30 still ran Saturday morning's code.
- **Condition:** somebody has clicked this path once in a real browser on the final commit. `DECISIONS.md` A4 says no agent had seen `/shop` rendered; a browser check was running at 23:54 and I do not know its result. If it has not been rehearsed, stay on slide D for the 70 seconds and say the figures; D is built to carry that.
- **If the stage allows no window switch:** play the hotel block of the 2-minute video (0:15–1:05 in `AIMO/SUBMISSION.md:105`–`106`, 50 seconds) in its place and give the 20 seconds to slide E. The video was not recorded when that file was written.

### If there is no time to build new slides

Keep the eight slides, apply section 1, and use this order and timing: 1 (10 s) · 2 (25 s) · 3 (20 s) · 4 (40 s) · 5 (45 s) · live demo (75 s) · 6 (40 s) · 7 (35 s) · 8 (10 s) = 300 s. Of the new slides, build in this order as time allows: **D, E, G, H, P**.

### What to cut

- Slide 3 as a slide of its own (above).
- Slide 6's big "17,546": the number scores nothing; the standards do.
- Slide 7's four sector cards as cards: one line is enough ("one gateway, four kinds of kitchen in the demo: a hospital ward, a school, a hotel, a bakery").
- The closing said twice (notes of slides 7 and 8).
- "DEMO PROTOTYPE" in six footers: once, on slide I, with what is illustrative, says more.

---

## 5. What the deck should also have

Each slide below can be shown live on the running gateway; the place is named. Every figure is [M] unless a source is given. Texts are ready to paste. Sizes follow the existing slides: content from 0.75 in to 12.58 in, kicker at 1.04 in, headline at 1.42 in, sub-line at 2.09 in.

### B. Existing slide 2, two additions (Valio Aimo's sentence; the brief's request)

- **Scores on:** problem fit; keeps the deck off the "chatbot" reading.
- **Add** under "Trusting an agent to buy them isn’t.", small: "Valio Aimo's question: how can a wholesaler be “safely and openly readable by autonomous agents”?"
- **Add** above the quote in the card, as a label: "THE BRIEF'S OWN REQUEST".
- **Change** "HANNA · HOTEL BUYER" / "Illustrative purchasing manager" to "HANNA LAINE · HARBOURSIDE HOTEL" / "Synthetic demo customer · purchasing manager".

### C. Existing slide 4, redrawn: the person and Valio Aimo's view are in the picture

- **Scores on:** 20% autonomy and controls (who decides is drawn, not only said); "not a chatbot".
- **Headline:** "Any agent asks. Fixed rules decide. A person confirms."
- **Sub-line:** "A typed interface, not a chatbot: the same for every agent, over REST and MCP, with decisions that can be checked."
- **Diagram, top row (as now, three boxes and two arrows):**
  - Left box: circle "AI" · "BUYER'S AGENT" · "any agent · REST / MCP".
  - Centre box, title "TRUSTED TRADE AGENTS GATEWAY", five chips in a row instead of four: "LOOK UP" / "price & stock" · "VERIFY" / "5 statements" · "RANK" / "options" · "RULES" / "alone · person · never" · "LOG" / "every step".
  - Right box: circle "V" · "VALIO AIMO" · "Price & availability API".
- **Add under the centre box**, a fourth box the same style as the side boxes, 3.2 in wide: circle "P" · "A PERSON AT THE BUYER" · "confirms the order on /shop". An arrow from this box up into the centre box, labelled "confirms".
- **Add a second arrow** from the centre box to the Valio Aimo box, below the existing one, dashed, pointing right, labelled "its own view of the log: the decision, without the buyer's limits, allergens or names".
- **Verdict strip** (moves down or shrinks to one line): "AUTO — the agent orders alone: only if the buyer switched it on and every statement is confirmed" · "APPROVAL — a named person confirms" · "BLOCK — refused, even with approval".
- **Shown live:** `/shop` (the person confirms), the log's two views.
- **Sources:** five statements `src/tta/policy/human_approval.py:45`–`48`; [M] Valio Aimo's view reads "P-01, a rule the buyer set (the order is above the spend limit per order; the amount is not shown)".

### D. New: "The brief's own sentence, end to end"

- **Scores on:** 30% working end-to-end demo (the rubric's own chain); 15% partial availability.
- **Kicker:** "WORKING DEMO · REQUEST → LOOKUP → ORDER / APPROVAL"
- **Headline:** "“1,000 litres of lactose-free milk by Monday.”"
- **Sub-line:** "The brief's own request, on /shop, against a recording of Valio Aimo's test data."
- **Layout:** five boxes in one row from 0.75 in to 12.58 in (each 2.2 in wide, 0.17 in apart, 2.4 in high, top at 2.75 in), an arrow between each pair; a full-width strip under them at 5.45 in; a small source line at 6.6 in.
  1. **"1 · REQUEST"** — "Read as: 1,000 L of milk, claim lactose-free, needed by Monday 16 Nov." Small: "Read by fixed rules. No model."
  2. **"2 · LOOKUP"** — "Price and stock of 26 matching products." Small: "2 left out, each with its reason: a portion pack, one that cannot be delivered."
  3. **"3 · OFFER"** — big "435 L confirmed · €1,083.39". Small: "565 L missing. Alternative: the full 1,000 L for €1,010.00, quantity not confirmed by Valio Aimo."
  4. **"4 · RULES"** — "Above the hotel's €750 limit per order. 43.5% covered, below its 90% minimum." Small: "→ the agent cannot order alone."
  5. **"5 · ORDER"** — "Hanna Laine, purchasing manager, confirms with one click." Small: "Ordered for €1,083.39 net."
- **Strip:** "THE LOG · 10 events, one sentence each · the chain of hashes verifies · two views: the buyer's and Valio Aimo's"
- **Source line:** "Recording of Valio Aimo's test data, Sat 14 Nov 2026 (1,163 products), at the demo clock Thu 12 Nov 14:15. Customer and limits are ours and illustrative. The order step is ours by design: “ordered” is a record in the gateway's order book."
- **Shown live:** `/shop`, Harbourside Hotel; this is the live demo's path. [M] on `/shop` the sentence is read by the fixed rules. Over REST with the hotel's demo token the same sentence is answered from a labelled recording of an earlier model reading ([M] `TTA-Read-By: gemini-3.6-flash`, source "recording"; `docs/DEMO.md:45`): if the demo is run over REST, box 1 reads "Read from a labelled recording" instead.
- **Sources:** [M] the log's own sentences: "The request was read as: 1,000 litres of product type milk with claim FREE_FROM_LACTOSE, needed by Monday 16 November 2026."; "The gateway looked up price and availability of 26 products in a recorded copy of Valio Aimo's data."; "2 options from 26 candidates, 2 products excluded with a reason"; left out: `463203` (portion pack), `464440` (cannot be delivered).
- **Before exporting:** decision B56 adds a third option to this answer in the final commit. Run the request once and add it to box 3 if it is there; boxes 1, 2, 4 and 5 are not expected to move.

### P. New: "It orders what was asked, or it asks"

- **Scores on:** 20% precision of the match, "with the least manual correction needed".
- **Kicker:** "PRECISION" · **Headline:** "What was asked is what comes back. Or a question." · **Sub-line:** "Fixed rules read the request and show the reading. What they cannot read is asked about, never guessed."
- **Layout:** a two-column table, four rows, the left column in quotation marks.

| The buyer writes | The gateway answers |
|---|---|
| "1,000 litres of lactose-free milk by Monday" | "Read as: 1,000 L of milk, claim lactose-free, needed by Monday 16 Nov." And in the offer: "Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk." |
| "1.000 litres of lactose-free milk by Monday" | "Is it 1,000 or 1? Write 1000 for the first, or 1 for the second." |
| "100 litres of milk chocolate by Monday" | "Is “milk chocolate” the product? The rules would read plain milk." |
| "40 litres of Arla whipping cream by Monday" | Read as cream that must carry "Arla" and "whipping" in its name: the brand is kept, not swapped. |

- **Bottom line:** "A model may read the sentence instead (optional, off here). It never sets a price, a quantity, an allergen status or a verdict."
- **Shown live:** type any row on `/shop`, or `POST /v1/requests/parse` on `/docs`.
- **Sources:** all four [M] over `POST /v1/requests/parse` (answers read "rule-based"; rows 2 and 3 are 422 with `question`).

### E. New: the guardrails model as a table

- **Scores on:** 20% autonomy and controls ("what the agent can decide alone, what needs human sign-off, and how decisions are logged"); the brief's "guardrails model".
- **Kicker:** "GUARDRAILS" · **Headline:** "What the agent decides alone, what a person confirms, what nothing can switch on."
- **Layout:** three columns of equal width (3.77 in, as the fixed verdict cards), each with a coloured tag on top (green, amber, red, as slide 4's AUTO, APPROVAL, BLOCK), top at 2.6 in, 3.3 in high; a strip under them.

| **THE AGENT, ALONE** | **A PERSON CONFIRMS** | **NEVER, EVEN WITH APPROVAL** |
|---|---|---|
| Search, read prices and stock, build offers, prepare the order | Above the buyer's limit per order or per day | A product that declares an allergen the buyer excludes |
| Place the order: only if the buyer switched "Let the agent place orders alone" on, no rule asks for a person, and all five statements of every line are confirmed | Less than the buyer's minimum share of the quantity is covered | A substitute that adds an allergen |
| Example: Ward 4, 200 L of soya drink, €402.00, within its €500 limit: "The agent placed this order alone." | Quantity, price or delivery date not confirmed by Valio Aimo | An offer that expired or changed before the order |
| Default for all four demo customers: **off**. A person confirms every order | An excluded allergen the data does not rule out: the dietitian, where the customer has one | An agent approving an order: over REST and MCP its token is refused (403) |
| | A substitute that loses a dietary claim, does not keep the recipe, or is a last resort | |

- **Strip:** "Limits are the buyer's settings (illustrative here). The fixed rules hold for every buyer: no profile can switch one off. Every decision is one sentence in the log, with the rule that fired and who confirmed."
- **Shown live:** `/shop` → Settings ("Let the agent place orders alone"; "What the agent never does on its own, whatever you set"); `GET /v1/authority` on `/docs`.
- **Sources:** [M] `GET /v1/authority` as the ward: "Always to a human: a product whose quantity is not confirmed, whose price is not confirmed or whose delivery date is ruled out; … a substitute that lacks a dietary claim of the product it replaces; a substitute that does not keep the formula where the formula matters; a substitute that is a last resort; and any fact a rule needs that is missing." and "Never, even with approval: a product that contains an excluded allergen, a substitute that declares an allergen the product asked for does not, and an option that expired or changed before the order." [M] ward with the setting on: ORDERED, placed by the agent, €402.00. [M] agent token on the decision route: 403 "An agent cannot approve or reject an order (F-06)." Fixed rules cannot be weakened by a profile: `src/tta/policy/rules.yaml:11`–`14`. "Over REST and MCP" is deliberate: the demo page has no login (decision B62).

### F. Existing slide 6, left half, as the exceptions slide

- **Scores on:** 15% robustness ("partial availability, substitutions and delivery constraints"); the brief's "response logic… good-better-best".
- **Keep** the kicker and the headline "Built for the exceptions, not just the happy path."
- **Four rows, full width** (the right dark panel moves to slide G):
  1. "Partial availability" — "435 of 1,000 L confirmed. The 565 L missing are said, never hidden."
  2. "Substitutes, ranked" — "A barista oat drink out of confirmed stock: first a confirmed like-for-like product (€174.00), then the product asked for as “quantity not confirmed” (€137.00), then the substitute Valio Aimo lists (€155.50, not confirmed). Two listed substitutes add gluten: never offered."
  3. "Allergen doubt" — "Milk excluded: the product whose data rules milk out comes first (€236.00). The cheaper one whose data says nothing (€208.00) is a labelled alternative, and a person decides."
  4. "Delivery constraints" — "A product that cannot be delivered is left out, with the reason. Every line shows its order deadline: “if ordered by Sunday 15 Nov at 17:00”."
- **Strip at the bottom (slide 3's figures):** "WHY THIS IS THE NORMAL CASE · 1,000 products sampled from Valio Aimo's test API, Fri 13 Nov 23:00: 25% with confirmed stock and an open cut-off, 9% orderable with a quantity not confirmed · whole catalog, 17,546 products: 46.2% with no allergen statement"
- **Shown live:** `/shop`, Harbourside Hotel: "100 litres of Oddlygood Barista oat drink, product 473609, by Monday" (row 2); "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk, strict rule" (row 3); the 1,000 L answer (rows 1 and 4).
- **Sources:** [M] row 2: 100 × `475224` €174.00 (F-10), `473609` €137.00 (F-01), 10 × `471690` €155.50 (F-01); `471881` and `464320` "can never be ordered as a substitute" ([M] over `POST /v1/products/473609/substitutes`). [M] row 3: 100 × `473424` €236.00, `469512` €208.00 (P-04, the dietitian's role, held at the hotel by the person who orders). Strip: section 2, slide 3.

### G. New: the trust protocol and the standards

- **Scores on:** 15% openness ("open, documented standards rather than a proprietary format"); the brief's "trust protocol: … for an external agent to trust Valio Aimo's claims on stock, price and origin without a manual check"; innovation.
- **Kicker:** "TRUST PROTOCOL · OPEN STANDARDS" · **Headline:** "What an outside agent can check by itself."
- **Layout:** two panels side by side, as slide 6 (left white, right dark).
- **Left panel, title "EVERY LINE OF AN OFFER: FIVE STATEMENTS, EACH CONFIRMED OR NOT"**, then a five-row table (example: the €1,010.00 alternative, product `464306`):

| Statement | Status | In the gateway's words |
|---|---|---|
| Price | confirmed | "Valio's price is €1.01 per ST before tax, valid until 31 Dec 2026" |
| Quantity | **not known** | "Valio reports 9,999,999,999 ST, a placeholder that means the stock is not known." |
| Delivery date | confirmed | "Delivery on Monday 16 Nov… if ordered by Sunday 15 Nov at 17:00." |
| Allergens | confirmed | "The buyer excluded no allergen, so there is nothing to check." |
| Origin | confirmed | "The product file states the country of origin: FI." |

  Under it: "One statement not confirmed, and a person decides. Unknown is never read as safe."
- **Right panel, title "WITHOUT ASKING US"**, five lines:
  - "Find every way in from the address alone: /.well-known/api-catalog (RFC 9727) · /llms.txt"
  - "Read the contract: OpenAPI 3.1 · JSON Schema · MCP, 13 tools, none approves"
  - "Check the signature on every offer and order: Ed25519, key at /.well-known/jwks.json"
  - "Keep the head of the log: every event carries its hash; /healthz publishes the count and the last hash"
  - "Know its authority before it acts: GET /v1/authority, with the hash of the rules in force"
  - Smaller: "Errors an agent can branch on: problem details (RFC 9457) · allergens as GS1 codes"
- **Bottom strip:** "Signed by this gateway, with a demo key. Not yet signed by Valio Aimo: that is the next step."
- **Shown live:** open the three addresses in a browser; `POST /v1/offers` on `/docs` shows `proof` (`/docs` loads its viewer from the internet, `docs/STANDARDS.md:36`).
- **Sources:** [M] the five claims of `464306` in the offer; [M] `proof`: "algorithm": "EdDSA", "canonicalization": "RFC 8785", "demo_key": true; [M] `/.well-known/jwks.json` (Ed25519), `/.well-known/api-catalog` (profile RFC 9727), `/llms.txt`, all 200 with no token; [M] OpenAPI 3.1.0, 13 MCP tools; [M] `policy_hash` in `GET /v1/authority`; [M] errors as `type`, `title`, `status`, `detail`; [M] `/healthz` gives `audit_head` (events, last hash). A reader's view of an event carries `hash` and not the previous one (`src/tta/contracts/audit.py:120`–`130`), so a reader cannot recompute the chain alone: the gateway checks it and says so, and the reader can keep the head. Hence the wording of line 4; do not write "anyone can verify the chain". GS1 codes: `docs/STANDARDS.md:148`. Do not add "CloudEvents" (decision B63).

### H. New: "It also sells"

- **Scores on:** 20% user need ("least manual correction": the forgotten item); the brief's scenarios "proactive selling agent" and "standing order drift"; Junction impact (who gains). It is also the team's stated main goal: used, intuitive, more sales.
- **Kicker:** "FOR THE BUYER AND FOR VALIO AIMO" · **Headline:** "It also sells."
- **Layout:** left, three stacked cards (white); right, one dark panel.
- **Left, card 1, tag "THE FORGOTTEN ITEM":** "“With this milk you usually also order Arla Pro Cooking cream 10%: it was in 7 of your last 8 orders, 10 L each time, and it is not in this request. Adding 10 L costs €33.10.”" Small: "One click: the order goes from €248.00 to €281.10, under the same rules."
- **Left, card 2, tag "VALIO AIMO'S OWN SUGGESTION, ONLY WITH A STATED BENEFIT":** "“Because you buy Oatly iKaffe 0.5 L, Valio Aimo suggests Oatly iKaffe Oat drink 1.5 L: the same kind of plant drink, with the same formula, €1.48 a litre instead of €2.88. For your usual 30 L: €44.40, €42.00 less.”"
- **Left, card 3, tag "YOU USUALLY ORDER THIS":** "“You ordered Arla Pro Cooking cream 10%, 10 L, in 4 of your last 4 weekly orders. Order the same again for Monday 16 November?”"
- **Right panel, title "VALIO AIMO'S BACK OFFICE":**
  - "What the agent channel sold: requests, offers, orders confirmed, euros"
  - "Suggestions shown and accepted, with the value added and the value saved for buyers, as two numbers"
  - "Sales that could not be made:" then, larger, "“435 of 1,000 L of lactose-free milk could be confirmed: 565 L, about €1,407 at the offered price, were not.”"
  - Small: "Never a buyer's limits, allergens or names."
- **Bottom line:** "A suggestion is shown, never added. The order history is synthetic, and every sentence says so."
- **Shown live:** `/shop`: Harbourside Hotel, "100 litres of lactose-free milk by Monday" (card 1); Kallio Bakery, "30 litres of oat drink by Monday" (card 2); opening the hotel (card 3); the menu entry "Valio Aimo back office" after the 1,000 L request (right panel).
- **Sources:** all [M] through the `/shop` routes; card 1 accepted and confirmed: "Confirmed by Hanna Laine, Harbourside Hotel (purchasing manager): ordered for €281.10 net."; the back office's own note: "No figure is given per buyer. A buyer's limits, excluded allergens, names, notes and own words… are not in what is counted." The back office counts what was done in that browser, so its other figures differ per run: quote only the sentence above.

### I. Existing slide 7, redrawn: "Honest limits, and what a pilot needs"

- **Scores on:** 15% openness ("clear visibility of assumptions… a credible view of next development steps"); Junction implementation.
- **Kicker:** "ASSUMPTIONS AND NEXT STEPS" · **Headline:** "What is ours, we say. What a pilot needs, we know."
- **One line under the headline (replaces the four sector cards):** "One gateway, four kinds of kitchen in the demo: a hospital ward, a school, a hotel, a bakery. All four are synthetic."
- **Left column, title "TODAY, AND SAID ON THE PAGES":**
  - "Data: a recording of Valio Aimo's test API (1,163 products, Sat 14 Nov), at a clock we chose. Live mode asks the API per request."
  - "Customers, people, limits and order history: ours, synthetic."
  - "No model is called. A model is optional and decides nothing."
  - "“Ordered” is a record in our order book. No message to Valio Aimo's systems, no payment."
  - "Signatures are the gateway's, with a demo key. The demo page has no login."
- **Right column, title "A CREDIBLE PATH FORWARD"**, the five steps as now, with 04 corrected:
  "01 Real orders — an order message in an open e-procurement format (Peppol BIS Ordering)" · "02 Real rules — customers' actual limits, approvers and roles" · "03 Real identity — OAuth-issued agent tokens and sign-in" · "04 Witnessed audit — buyer and Valio Aimo each keep the head of the log" · "05 Signed claims — Valio Aimo signs its own price, stock and origin"
- **Shown live:** the clock strip on every view of `/shop` ([M] "Demo clock: Thursday 12 November 2026 at 14:15… We chose it: Valio Aimo said on 14 Nov 2026 that its test data is static."); the labels "From a synthetic order history" in every suggestion [M]; "(demo key)" in `/healthz` [M].
- **Sources:** next steps `docs/STANDARDS.md:170`–`184`; no login on the demo page: decision B62.
- **Drawing:** all five circles in one style (none filled); description text in the light colour of the headline's sub-line, not grey.

### J. Existing slide 8: the links

As section 1, row 12. If the form's "Source Code" field points at a branch, write the same branch here (the code is on `replan-build`, pushed at 00:37 by the log).

---

## 6. Questions a judge is likely to ask from these slides

1. **"Where is the AI? Is a model making these decisions?"** No model is called in what we show: fixed rules read the request and ask when they cannot, and every price, quantity, allergen status and verdict comes from tested code and rules kept as data. The AI is the buyer's agent on the other side of the interface; a Gemini Flash reader is in the repository as an option and ran in one test on Saturday night, switched off since (over REST the two demo sentences answer from a labelled recording of an earlier model reading, and say so).
2. **"I asked for 1,000 litres and you give me 435. Is that a good answer?"** It is the true one: in the recording, confirmed stock of lactose-free milk covers 435 L, so the gateway says 565 L are missing and names the full-quantity option whose stock Valio Aimo does not confirm, for a person to choose. On Saturday morning it filled the gap with coffee milk without saying so; that is the fault we removed (a third option that names the coffee milk as a substitute is being added tonight: check before answering).
3. **"Does the agent ever order alone? And can it approve its own order?"** Only where the buyer switches it on, and then only when no rule fires and all five statements of every line are confirmed; it is off for all four demo customers because Valio Aimo told us on 14 Nov that the final step should always have the user's input. Over REST and MCP an agent's token is refused on the approval route with 403; the demo page has no login, so there you act as the person shown.
4. **"Did Valio Aimo receive this order?"** No. The test API has price and availability and, by design, no order endpoint, so the order step is ours: a record in the gateway's order book that commits nobody; an order message in an open format such as Peppol BIS Ordering is our first next step and is not started.
5. **"Is this real data? Are those real customer limits?"** The catalog (17,546 products) is Valio Aimo's file and all of it can be searched; prices and stock in the demo are a recording of the test API for 1,163 products, shown at a clock we chose because the test data is static. The four customers, their people, limits and order history are ours and synthetic, and the pages say so.
6. **"What can Valio Aimo trust, and what does it see?"** It reads the same log as the buyer in its own view: every rule that fired and every product left out for a reason in its own data, without the buyer's limits, excluded allergens or names; and a back office counted from that view only. Offers and orders are signed by the gateway with a demo key, not by Valio Aimo, and nobody outside yet holds the head of the log: both are named next steps.

---

## 7. What I could not verify

- **The public link.** Not called, by instruction. Whether `/shop`, `/docs`, `/mcp/` and `/llms.txt` answer there, and so whether slide 8's demo link works, depends on tonight's redeploy.
- **The final commit.** Everything measured is `016cc08`. Decisions B55 to B63 are being built after it; B56 (a third option for the 1,000 L sentence) and B61 (the confirmation sentence) can move text I quote. Re-read both from the final commit.
- **How the deck looks in PowerPoint or Google Slides.** Seen only as LibreOffice renders it, without the Inter font. The card positions in section 2 are read from the file and do not depend on the renderer.
- **`/shop` in a browser.** I drove the page's routes (`/shop/api/*`), not the page: the labels of buttons and views are read from the page's source, not seen.
- **The recording's own clock.** All measurements are at the demo clock. "17 left out at the recording's clock" (`docs/DEMO.md:71`) and other figures of that clock are not re-measured, and none is used above.
- **Three figures taken from documents, marked where used:** 30.6% of food products with no allergen statement (`AIMO/FINDINGS.md:76`); the bakery's enzyme example (`docs/DEMO.md:173`); "20,000+ professional kitchens" (`AIMO/CHALLENGE.md:8`, our summary of the brief, not verbatim) — not used in any replacement; check the challenge page before putting it on a slide.
- **The model test of 22:27** (Gemini Flash, three tool calls): from the log; not re-run, since it needs an outside call.
- **The tech awards** (what ran on Modal, Aiven, Context.dev): `docs/AWARDS.md` only; the deck claims nothing about them.
- **Whether the repository is public** and which branch the form points at.
