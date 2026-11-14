# P11 — Positioning: what the product is for, in Valio's own terms

Agent P11, Saturday 14 Nov. No code or document was changed. Scratch scripts: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/P11/proof.py`, `proof2.py`, `proof3.py` (replay, empty data folder, recipe of `BRIEF.md` §5).

**How to read the web facts.** Each has its URL. Pages were read through a page-reading tool that summarises; re-open the URL before a quote goes on a slide. "Not found" means not on the public page I read. It is never proof that something does not exist.

## 1. In five lines
1. Today's pitch sells control ("the agent proposes, the gateway decides") and a threat ("before someone else's platform"). It never says why a customer would choose Valio Aimo. The mentor's sentence asks for exactly that.
2. Recommended positioning: **"Valio Aimo becomes the wholesaler a buyer's agent can order from without a phone call: every answer says what is confirmed, every doubt is asked back, and a person confirms every order."**
3. Three claims carry it, each with a call that proves it today: a status on every claim (`POST /v1/offers`), the rules readable before the order (`GET /v1/authority`, 403 on self-approval), and Valio's own view of every step, with the reasons its products were left out (`GET /v1/audit?reader=supplier`).
4. Eleven sentences in `docs/PITCH.md` and `README.md` are now wrong or weak against V8, V10, B5 and B13. Replacements are in §3. Most are true only after the V8, V10 and B5 changes land.
5. Do not claim new customers, "first", "no competitor has this", or a placed order. Work: 1 hour minimum (texts), 4 hours full (texts, video script, question card). All of it is documents, none of it code.

## 2. What exists today

### 2.1 Valio Aimo and its competitors (public sources)
| Fact | Source |
|---|---|
| Heino's wholesale began in Helsinki in 1899. Heinon Tukku Oy from 1972. From the 1980s it served hotels, restaurants and catering. The competition authority approved Valio's purchase on 30 June 2021. "Valio Aimo is born" on 19 January 2022. | https://www.valioaimo.fi/en/company/ |
| The approval had a condition: Valio must protect confidential information it receives about competitors, for 10 years. | https://www.kkv.fi/en/current/press-releases/the-fcca-conditionally-approves-the-merger-between-valio-and-heinon-tukku/ |
| Valio group net sales 2025: EUR 2,422.7 million. "The Valio Aimo wholesale business also grew." No separate Valio Aimo figure found. | https://www.valio.com/news/valios-business-grew-steadily-in-2025-in-a-challenging-operating-environment/ |
| Customers: "all foodservice industry operators" (restaurants, hotels, cafes, kiosks), "from school kitchens to your local café", all of Finland. | https://www.valioaimo.fi/en/become-a-customer/delivery-wholesale/ · https://www.valioaimo.fi/en/company/ |
| How customers order today: the delivery webshop (needs a customership and customer number), phone or e-mail to the sales service (weekdays 7 to 16), two cash-and-carry stores (Helsinki, Vantaa), click and collect at one store. Delivery "within 24 hours" on agreed days. | https://www.valioaimo.fi/valio-aimo-in-english/ · https://www.valioaimo.fi/en/become-a-customer/delivery-wholesale/ |
| The webshop already has standard orders, carts for several delivery dates and personal product recommendations. My Aimo has purchase reports with carbon footprint, "My Recipes" (margin, ingredients to the cart) and an AI assistant, "A.I.mo", that finds information for the user. | https://www.valioaimo.fi/en/company/why-choose-valio-aimo-as-a-partner/innovative-tools-for-everyday-work/ |
| VALO Tilauspalvelu (since 2014): one order across Atria, Froneri, HKScan, Saarioinen, Snellman Pro and Valio, delivered by Valio's network. | https://www.valioaimo.fi/en/become-a-customer/valo-tilauspalvelu-en/ |
| The webshop was rebuilt by Vincit with an SAP ERP integration. Stated goals include "Help with new customer acquisition and retention". The Valio person quoted there is listed as a mentor in `AIMO/CHALLENGE.md:75`. | https://vincit.com/our-work/valio-aimo |
| No EDI, API or other interface for a customer's program is described on the Valio Aimo pages above. | same pages (not found) |
| Kespro (Kesko) leads: share "estimated to have strengthened in 2025 to 49.2%" (Kesko's own estimate). Kesko names its competitors: Meira Nova, Metro-tukku, Valio Aimo, Suomen Palvelutukkurit, direct deliveries, speciality wholesalers. 13 cash-and-carry outlets and an online outlet. | https://www.kesko.fi/en/investor/strategy/division-strategies/grocery-trade-strategy/ |
| Kespro digital: Kespronet webshop, Kespro ID, a Deliveries service (see orders, track a delivery), Reports. No integration, EDI, API or AI named. | https://kespro.com/en/services/digital-services · https://www.kespro.com/sv/ideer-och-inspiration/artiklar/kespron-uusi-toimitukset-palvelu-sujuvoittaa-arkea |
| Metro-tukku (Wihuri): about 20,000 products, 14 cash-and-carry outlets, a webshop with sign-in, reports. No app, EDI, API or AI named. | https://www.wihuri.fi/en/what-we-offer/metro-tukku/ · https://www.metrotukku.fi/ |
| Meira Nova (S Group): a webshop renewed in 2026, "digital customer services"; customers are restaurants, service stations, hotels, public sector. An integrator sells a supplier-side EDI connector for it. | https://www.meiranova.fi/ · https://www.celigo.com/integrations/meira-nova-oy-edi-integrations |
| Programs already order from wholesalers: JAMIX, a Finnish kitchen system, states "Digital purchase orders to suppliers directly from the JAMIX System". Which Finnish wholesalers: not named on the page. | https://www.jamix.com/?p=20618 · https://www.jamix.com/?p=27901 |

**Unverified.** "20,000+ professional kitchens, 25,000 product names, 700 suppliers" is our summary of the challenge page (`AIMO/CHALLENGE.md:8`); I did not find it on valioaimo.fi. Heinon Tukku's turnover (about €240 million, €170 million in 2020) and 340 staff come from a search summary of Valio's 2021 release; the page itself answered 404. Suomen Palvelutukkurit was not researched. An earlier attempt by Kesko to buy Heinon Tukku appears in search titles only.

**Reading.** Every wholesaler has a login webshop. None of the public pages documents a door for a buyer's own program. Valio Aimo already has an assistant inside its own portal. So the open ground is the brief's own sentence (`AIMO/CHALLENGE.md:30`): being readable by the *buyer's* agent.

### 2.2 What the pitch says today
- Punchline: "The agent proposes, the wholesaler's gateway decides: … within the agent's authority or with a human's signature." (`docs/PITCH.md:11`, repeated at `:84`).
- Opening beat: "Soon their buyers send agents, not people. The question is what an agent may see, decide and be trusted with, before someone else's platform answers it for Valio." (`docs/PITCH.md:25`).
- No punchline (`docs/PITCH.md:11-13`), pitch beat (`:25-32`) or video line (`:64-72`) says what Valio Aimo gains with its customers. The word "customer" appears once there, in "real customer limits" (`docs/PITCH.md:32`). The README opening (`README.md:3`) describes the mechanism only.

### 2.3 What the build proves today (measured by me, replay)
- `GET /v1/authority` (hotel token): 200, profile with `"illustrative": true`, `max_order_net_eur: 750.0`, `auto_order_enabled: true`.
- `POST /v1/offers`, `scenario_1`: 201, `source: replay`. Two options, €2,580.64 and €1,010.00. Each line has a `claims` list (price, quantity, delivery date, allergens, origin), each with a status and a sentence. Option 2's quantity is `UNKNOWN`: "Valio reports 9,999,999,999 ST, a placeholder that means the stock is not known." 19 excluded products, each with a reason and a sentence. Each option has `decision`: verdict `APPROVAL`, rule `P-01`, its sentence.
- Option 1's third line is `463380` "Arla Cafè milk 1 L UHT lactose free", 565 units (the B5 case).
- `POST /v1/orders`: 201 `PENDING_APPROVAL`. Decision with the agent's token: 403 `application/problem+json`, "An agent cannot approve or reject an order (F-06)". With the approver's token: 200 `ORDERED`, `HUMAN_APPROVAL`.
- `GET /v1/audit?order_id=…`: the buyer's view and the supplier's view both hold 10 events, chain `ok: true`. The supplier's JSON contains neither "750" nor "Hanna". Its `tta.v1.offer.created` event holds `facts.offer.excluded_by_reason`. The supplier token gets 403 on the buyer's view. Whether the page shows `excluded_by_reason`: not checked.
- Ward, `scenario_2`: `ORDERED`, `placed_by: AGENT`, 41 excluded. So an agent orders alone today (`src/tta/policy/profiles/allergy-ward.yaml:13`, `hotel-kitchen.yaml:14`).

## 3. What Valio's answers change
| Where | Sentence today | Why wrong or weak | Replacement |
|---|---|---|---|
| `docs/PITCH.md:11`, `:84` | "The agent proposes, the wholesaler's gateway decides … within the agent's authority or with a human's signature." | V8: the user always confirms. No customer in it. | Positioning A (§4.2). |
| `docs/PITCH.md:13` | "Purchasing agents can order from Valio Aimo today…" | False: an order commits nobody (`docs/PITCH.md:49`). | Drop. |
| `docs/PITCH.md:25` | "…before someone else's platform answers it for Valio." | Mentor: the goal is customers. This opens on a threat. | "Valio Aimo's customers order in a webshop, by phone or by e-mail. The next ones send software. The wholesaler whose answers that software can use without a person re-checking gets the order." |
| `docs/PITCH.md:26`, `:65` | "the hotel may order alone up to €750" | V8. | "The agent prepares the order. A person at the kitchen confirms every one. Ordering alone is a buyer's setting, off, as Valio asked." |
| `docs/PITCH.md:27`, `:66` | "Three confirmed milks cover it, €2,580.64." | B5: 565 of the 1,000 L are a coffee milk. Valio: "no be explicit". | "Milk means milk: a coffee milk is not offered for it. [N] confirmed milks cover [X] L for €[Y]." Figures from the owner of the B5 fix. |
| `docs/PITCH.md:29`, `:70`; `README.md:20` | "the agent orders alone" | V8. | "Every claim confirmed, within the ward's limits: the order is ready, and one confirmation places it." |
| `docs/PITCH.md:30`, `:71` | "Two substitutes Valio itself lists add gluten…" | Still true (B6 "yes"). But the demo then orders a Fazer drink for an Oddlygood one, alone (`docs/DEMO.md:79-80`). V10 and V8 both forbid that. | Add: "The same product in another size comes first. Another recipe goes to a person, with what changes." |
| `docs/PITCH.md:31`, `:69` | "Valio sees … without the buyer's limits or names." | B13: "all the steps and decisions". Lead with what Valio sees. | "Valio sees every step and every decision in its own view, and why its products were left out. The buyer's limit values and names stay with the buyer." |
| `docs/PITCH.md:72` | "Ready for any agent." | Checked with one client only (`README.md:135`). | "Open standards, every assumption on one page." |
| `README.md:3` | "A gateway that lets a buyer's purchasing agent look up … place an order within its own authority or send it to a human…" | V8, and no reason to care. | "Trusted Trade Agents makes Valio Aimo the wholesaler a buyer's own purchasing agent can read and order from. The agent gets fixed prices and stock with a status on every claim, asks a person when the data is not sure, and prepares an order that a person confirms." Then the present sentences about the audit trail and the standards. |
| `README.md:22` | "The model reads the text and picks an option." | Under V8 a person confirms. | "The model reads the text and proposes an option." |

B13 can be read two ways: Valio wants to see every step (it does: 10 of 10 events), or Valio also wants the values we hide. **DECISION D4.**

## 4. Options and recommendation

### 4.1 Why being readable by a buyer's agent wins customers
Who would send an agent (assumption, from the brief and the sources above): chains with central purchasing (the brief's hotel chain), and public kitchens whose software already turns menus into purchase orders. Allergen rules are strictest there.

| What makes an agent prefer a supplier | What the build does today | Gap |
|---|---|---|
| Answers it can use without a manual check | A status on every claim of every line; unknown stock is said, not hidden (§2.3) | "Origin: confirmed" means "the product file states it". Say so. |
| Fewer corrections | The request as read, checks per constraint, every exclusion with a reason; the reader never guesses a quantity (`README.md:29`) | "Milk" swallowed a coffee milk (B5). The type table is ours. |
| A doubt is asked back (V5) | Missing allergen data goes to the dietitian with the evidence (`docs/PITCH.md:37`) | The ask goes to an approver role, not always to the user who sent the request. |
| Clear rules about what needs a person | `GET /v1/authority`; the verdict and its rule in every option; 403 on self-approval | Two demo profiles still order alone (V8). |
| An order that goes through | One order per key, a fresh check at order time, an approval route, a record | The record commits nobody: the mock has no order endpoint. |
| Comparing wholesalers | Reliability, carbon and labels per line (`README.md:26`) | We read one wholesaler. No comparison across suppliers. |
| A new customer's agent can start | Public demo tokens | Onboarding is not built. Ordering needs a customership today. |
| Valio's agent proposes products (`AIMO/CHALLENGE.md:44`) | Nothing | Not built (`README.md:136`). A next step, one sentence. |

### 4.2 Positionings
- **A (recommended).** "Valio Aimo becomes the wholesaler a buyer's agent can order from without a phone call: every answer says what is confirmed, every doubt is asked back, and a person confirms every order."
- **B.** "The agent prepares the order, the kitchen confirms it: an open door into Valio Aimo that tells any buyer's agent what is confirmed, what is not, and why."
- **C.** "Before someone else's platform decides how agents buy food, Valio Aimo answers them itself, in the open, with its own rules and its own record."

A names the customer benefit first and holds V5 and V8 in one line. B is safer if "without a phone call" feels too bold. C is the brief's own sentence and works best as the closing line. **DECISION D1:** A as punchline, C as last line.

How to keep the 20% for autonomy under V8: the agent decides alone what to read, exclude, rank, split and prepare. A person confirms. When a rule fires, a named role signs. Ordering alone stays a visible buyer setting, off (rule P-00, `src/tta/policy/rules.yaml:294`). **DECISION D3:** say this only if the V8 change lands.

### 4.3 The three strongest claims
| Claim | Proof a judge can run | Screen | Criterion |
|---|---|---|---|
| The agent is told what is confirmed and what is not, line by line. | `POST /v1/offers` → `options[].lines[].claims[]`, `excluded[]` | Scenario 1 summary strip (`docs/DEMO.md:44-46`) | 20% match · 15% exceptions |
| The rules are readable before the order, and an agent cannot approve itself. | `GET /v1/authority`; `options[].decision`; agent token on `/v1/approvals/{id}/decision` → 403 | "What the agent may do", approval card | 20% controls |
| Valio sees every step and decision, and why its products lost the order. | `GET /v1/audit?reader=supplier` with `demo-supplier-valio-aimo` → 10 events, `excluded_by_reason` | Order record, tab "Valio Aimo's view (supplier)" | 20% auditable |

### 4.4 The 2-minute video, in beats
| Seconds | Beat | Screen |
|---|---|---|
| 0:00–0:12 | Customers order by webshop, phone, e-mail. Next they send software. Who answers it best gets the order. | Title, punchline A |
| 0:12–0:24 | One door for any buyer's agent. Not a chat window. | A real call and its JSON, then `/` |
| 0:24–0:52 | The brief's sentence. Confirmed, not confirmed, left out with reasons. Milk means milk. | Scenario 1 summary strip and options |
| 0:52–1:10 | Not sure, so it asks: allergen not stated, the person sees the evidence. | Dietitian card (example 4) |
| 1:10–1:30 | A person confirms. The agent cannot. | Approval card, approve, the 403 |
| 1:30–1:44 | A substitute keeps what matters: never a new allergen, another recipe goes to a person. | Ranked substitutes |
| 1:44–1:55 | Valio's view: every step, every decision. Line C. | Supplier tab, `/assumptions` |
Five seconds are spare. Beats 3, 5 and 6 need the B5, V8 and V10 changes; the scenarios are P2's choice.

### 4.5 Three questions a Valio judge will likely ask
1. **"How does this bring us customers?"** It does not bring one by itself. Ordering still needs a customership, and onboarding an agent is not built. It removes the re-checking between an agent and an order, for customers whose software already orders. Your own selling agent is the next step; it is not built.
2. **"We said no automatic orders. Why an agent?"** The agent prepares; a person confirms every order. The value is an order that needs no correction. Ordering alone is a setting for later, with fixed rules no setting can switch off. (True after the V8 change. Today both demo profiles allow it.)
3. **"Our data is noisy. What when you are unsure?"** Values are taken as they are. Missing never counts as safe. A doubt goes to a person with both sources quoted. Honest limit: our product-type table is hand-made, and B5 showed it can be wrong.
Also be ready for: "Does the order reach our systems?" No. It is a record in our order book.

## 5. Work items
| id | What | Files | Hours | Who | Criterion | Depends on |
|---|---|---|---|---|---|---|
| P11-1 (minimum) | Punchline A, new opening beat, README opening | `docs/PITCH.md:9-15,25,84`, `README.md:3,22` | 0.5 | anyone | None directly. It is how the 30% and 20% are seen, and it removes claims the product cannot show (15% visible assumptions). | D1 |
| P11-2 (minimum) | Question card: §4.5 and the "do not claim" list | `docs/PITCH.md:44-54` | 0.5 | a biomedical member | 15% (assumptions, next steps) | none |
| P11-3 | Replace the sentences of §3 with the final figures | `docs/PITCH.md`, `README.md`, `docs/DEMO.md:114-123` | 1 | anyone | 20% match · 20% controls, as stated | V8, V10, B5 changes; P2 |
| P11-4 | Video script of §4.4, then record | `docs/PITCH.md:58-74` | 1.5 | two people | 30% (the demo as judges see it) | build freeze |
| P11-5 (cut first) | One deck slide: how customers order today, with the sources of §2.1 | deck | 0.5 | a biomedical member | 15% (justified choices) | none |
Cut order: P11-5, then the spare polish of P11-4. Never cut P11-1 and P11-2.

## 6. What changes in the demo
- The first sentence a judge hears names customers, not control.
- "Ordered by the agent" (`docs/DEMO.md:65`, `:79`) no longer appears as the outcome. The outcome reads as an order prepared and confirmed.
- One beat shows a call and its JSON, so the product reads as an interface for programs.
- The supplier tab is introduced as "every step and every decision", measured: 10 of 10 events.
- No figure in this proposal is new. €2,580.64 and "three milks" will change with the B5 fix.

## 7. Risks and what not to claim
- **Do not claim:** new customers or more sales (nothing measured) · "first" or "no competitor has this" (public pages only) · "Valio has no AI" (A.I.mo exists) · an order placed with Valio · "the agent orders alone" as a headline · "any agent" (one client checked) · verified labels or origin (they are what the file states) · real limits (profiles are ours) · comparison across wholesalers · the 20,000 / 25,000 / 700 figures as ours (say "your brief says").
- **Chatbot risk.** A page with a text box can read as a chatbot. Say once: the pages are for the person who confirms; the interface is for the agent.
- **Order of work.** Positioning A is false until the V8 change lands. If it does not land, use B without "the kitchen confirms it" and do not headline autonomy.
- **Name.** The project name equals the challenge title (`docs/PITCH.md:82`). **DECISION D2:** keep it or pick a distinct one.
- **Small.** The demo approver is called Hanna (`docs/DEMO.md:54`), also a mentor's first name (`AIMO/CHALLENGE.md:75`). Rename only if it is cheap; tests pin the string.

## 8. Questions
- **For João (D4).** B13, "all the steps and decisions": did Valio mean it wants to see every step (true today), or also the buyer's limits, exclusions and names?
- **For Valio.** Context: you said the goal is to attract customers. What we did: we assume the first agents come from chains and from public kitchens whose kitchen software already sends orders. What we got: no public page says which customers order by program today. Example: a municipal kitchen whose menu system creates the purchase order. Ask: which customer group do you expect to send an agent first, and do any order by program today? If nobody answers: we keep the hotel chain of your brief and the allergy ward, and say the customer groups are our assumption.
