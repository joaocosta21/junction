# P8 — The agent suggests, the user confirms (answer V8)

Agent P8, 14 Nov. Everything marked "measured" was run offline in replay with the brief's recipe (capture `2026-11-14-demo`, fresh data folder per run). Scripts and outputs: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/P8/` (`paths.py`, `kitchen.py`, `out_on.txt`, `out_off.txt`). No repository file was changed. "Off" means my scratch copy of the two profiles with `auto_order_enabled: false`.

## 1. In five lines
1. Every order placed without a person goes through one branch: `src/tta/orders/service.py:87-90` (verdict `AUTO`). Six entry points reach it. Five placed an order alone when I ran them (REST, the agent run, MCP, a standing-order renewal, the first page); the sixth is the menu page's button.
2. The switch Valio asks for exists: rule P-00 and `auto_order_enabled`. Set to `false`, all six paths answer `PENDING_APPROVAL` and no order is placed without a human token (measured). No code change is needed for that.
3. Recommend: ship both profiles with the setting off (A), tell it as "the agent prepares, a person confirms" with one confirm click (B, without a new contract state), and keep ordering alone as a visible buyer setting that is off by default (C).
4. Minimum is 2.0 hours: two profile lines, P-00 wording, tests, document lines. In the minimum "the user" is the buyer's purchasing manager, the only role P-00 can name without code.
5. Autonomy that remains: the agent reads, excludes, combines, substitutes within scope, re-checks, prepares the order and decides who must sign. It places the order only where the buyer switched that on.

## 2. What exists today
**One choke point.** `OrderBookService.place_order` (`src/tta/orders/service.py:71`) accepts agent tokens only (`:73-74`). Verdict `AUTO` writes `ORDERED`, `placed_by: AGENT` (`:87-90`, `records.py:129-140`, `outcomes.py:27-34`, audit event `order.placed_by_agent`). Any other verdict creates an approval (`:92-97`). An agent token is refused on approval routes (F-06, `orders/access.py:36-42`).

**Paths without a person, each run offline (settings as shipped):**

| # | Path | Code | Result today (measured) |
|---|---|---|---|
| 1 | `POST /v1/orders` | `api/routes.py:198-212` → `api/service.py:221-226` | scenario_2: 201, `ORDERED`, `placed_by: AGENT`, no rule fired. "The agent placed this order alone for €402.00 net: no rule of profile allergy-ward asked for a human." scenario_1: `PENDING_APPROVAL` (P-01) |
| 2 | `POST /v1/agent/run` | `api/routes.py:302-310` → `agent/runner.py:129-163` → `agent/tools.py:203-219`; the instruction tells the model to order option 1 (`agent/prompts.py:74`) | scenario_2: steps `get_authority`, `create_offer`, `place_order`; `order_status: ORDERED` |
| 3 | MCP `place_order` | `api/mcp_surface.py:230-242` | scenario_2: `ORDERED`, `placed_by: AGENT` |
| 4 | Standing-order renewal | `standing/service.py:185-197` (order at `:197`); REST `api/standing_routes.py:94-112`; page `ui/standing_page.py:174-199` | 100 L of `469363`, fresh book: 201, `ORDERED`, `placed_by: AGENT`, €248.00. Page: "The agent placed this order alone for €248.00 net" |
| 5 | First page, "Run" and "Read the photo and run" | `ui/request_page.py:242,261` → `ui/run.py:127` (agent run) or `ui/run.py:190-202` (order at `:199`) | scenario-2 button: "Ordered by the agent". The result page has no order button: the click on "Run" also orders. The photo button was not run (it needs the model) |
| 6 | Menu page, "Order this option" | `ui/menu_page.py:177-184`, button `ui/templates/menu.html:138-144` | A person clicks, but the order is placed as the agent identity. The REST route `POST /v1/menus/plan` only plans (`api/menu_routes.py:63-78`). The shipped example `last_minute_event` is `APPROVAL` (F-09 and P-06; also P-02 in my run, where earlier orders had filled the day), so no menu order was placed alone in my run, and I did not click the page's button |

Also: at start-up `api/examples.py:186` places the scenario orders in a private in-memory store (`:251-267`) to build the `/docs` examples. It touches no real book.

**The switch.** P-00 (`policy/rules.yaml:288-302`): when `profile.auto_order_enabled` is false, verdict `APPROVAL`, role `purchasing_manager`. Fact at `rules.yaml:70`, `policy/facts.py:96`, `contracts/policy.py:35`. Both profiles ship `true` (`profiles/hotel-kitchen.yaml:14`, `profiles/allergy-ward.yaml:13`). `policy/validation.py:82-86` already names P-00 as the way "to keep a human on every order".

**The setting on a page.** "Your kitchen" has the checkbox "The agent may order alone at all" (`ui/templates/kitchen.html:56-58`, `ui/kitchen_page.py:39,46-50,92`, `api/sandbox.py:65-69`). Measured as My kitchen agent with "40 litres of oat drink by Monday": box ticked → "Ordered by the agent"; box unticked → "Sent for approval" and the button "Decide as Demo approver Hanna, My kitchen (purchasing manager)". My kitchen starts as a copy of `hotel-kitchen` (`api/sandbox.py:64,145`).

**Identities.** `api/demo_tokens.yaml:16-73`: 2 agents, 6 approvers, 1 supplier. Roles: `purchasing_manager`, `dietitian`, `finance` (`contracts/common.py:200-203`). No identity stands for "the person who asked": the first page's "who is asking" picks an agent.

**With the setting off (measured, `out_off.txt`):**
- Scenario 2, all of REST, agent run and MCP: `PENDING_APPROVAL`, `fired: [P-00]`, `required_roles: [purchasing_manager]`. Words: "The agent cannot place this order alone: profile allergy-ward does not let the agent place any order alone (P-00). It needs the purchasing manager." and "Waiting for approval by the purchasing manager, to be decided by Sunday 15 November 2026 at 17:00 (UTC+02:00): rule P-00 asks for a human."
- The ward's dietitian is refused (403): "The approval still needs the purchasing manager; this approver counts for the dietitian and holds none of them." The ward's purchasing manager approves: "Ordered for €402.00 net with approval by Demo approver Jussi (purchasing manager): rule P-00 asked for a human and was accepted." The price and availability are checked again at that moment.
- Scenario 1: same option, same €2,580.64, same signer. The sentence gains P-00: "rules P-00 and P-01 ask for a human". One signature covers both, because both name the purchasing manager.
- Standing renewal on the page: 100 L gives "Waiting for approval by the purchasing manager … rule P-00 asks for a human."; 290 L gives "… rules P-00 and P-08 ask for a human."
- An agent token on its own approval: 403 `not-authorised`, "An agent cannot approve or reject an order (F-06). A human with the role asked for decides." The order stays `PENDING_APPROVAL`.
- The app starts, `/openapi.json` builds its examples and the recorded agent run works with the setting off.

## 3. What Valio's answer changes
- Today paths 1 to 5 place an order with no human input. V8 says the order must always have the user's input. With P-00 on, a human token must sign every order, and the gateway enforces it (an agent cannot sign, F-06). So the answer is honoured by the gateway, not by a promise of the agent.
- The note can be read in more than one way. I do not pick silently:
  - "final submition": the final step of an order, or our hackathon submission. Both lead to the same build: no order without a person in what we submit.
  - "the user": the person who asked, or any authorised person of the buyer. This changes who confirms (decision D1).
  - "deactivate … maybe another question for later is setting": remove ordering alone, or keep it as a setting that is off. I read it as: off now, the setting may stay.
- The written brief still describes an autonomous path: "the agent places the order within its authority or sends it to a human" (`AIMO/CHALLENGE.md:27`), "vs. fully autonomous" (`:36`), "before auto-renewing it" (`:46`), and the 20% criterion (`:68`). So the path stays in the product, switched off.
- What is lost if we only flip the switch: both demo scenarios end the same way ("Sent for approval", purchasing manager), and the sentence reads as a failure ("The agent cannot place this order alone").

## 4. Options and recommendation
**A. Both profiles `auto_order_enabled: false`.** Cost: 2 lines. Honours V8 on every path (measured). Is the purchasing manager "the user"? Plausible for a small kitchen (the person who orders in the webshop). Weak for the ward, where the person who asks is not the purchasing manager. With A alone the difference between "within limits" and "above limits" shows only in the reasons, not in who signs.

**B. A confirmation step by the person who asked.** Two ways:
- B1 (recommended): no new contract state. P-00 names a new role `requester` ("the person who asked"). The order is `PENDING_APPROVAL` with `required_roles: [requester]`; when a limit rule also fires, `[requester, purchasing_manager]`. The existing approval machinery gives the re-check at signature time, the option choice, expiry at the "order by" time and the audit events. The result page gets one "Confirm and order" button.
- B2: new states (`PENDING_CONFIRMATION`, a confirm route, `PlacedBy.USER_CONFIRMATION`). Cleaner names. It touches the contract, the OpenAPI and MCP schemas, the store, both audit readers and the pages. I estimate 6 to 8 hours and a risk to the 30% demo. Not recommended tonight.
- A third way, a human token calling `POST /v1/orders` directly, changes who may place an order (`service.py:73-74`) and the audit model. Not recommended.

States, as the documents would name them (contract value in brackets): suggested (the offer, nothing committed) → prepared, waits for the user's confirmation (`PENDING_APPROVAL`, only P-00 fired) → waits for a named role (`PENDING_APPROVAL`, another rule fired) → `ORDERED` (`placed_by: HUMAN_APPROVAL`; `AGENT` only with the setting on) · `REJECTED` · `EXPIRED`.

What an outside agent gets from `POST /v1/orders` (measured over REST and MCP with the setting off): 201, `status: PENDING_APPROVAL`, `placed_by: null`, `decision.verdict: APPROVAL`, `decision.fired: [P-00]`, `required_roles`, `approval_id`, a status sentence. It then reads `GET /v1/orders/{id}` until `ORDERED`, `REJECTED` or `EXPIRED`. It can never confirm its own order. An option whose only fired rule is P-00 is "within the agent's authority": documented, no schema change.

**C. Ordering alone as a setting, off by default.** The boolean exists and is on "Your kitchen" today. In steps (`NEVER` · renewals of a standing order within its tolerance · within the limits) it needs a new profile field; the fact `standing.is_renewal` exists (`rules.yaml:433`). The first step matches Valio's own example, "before auto-renewing it".

**Recommendation: A now, B1 as hours allow, C as the existing boolean.** The steps of C are the first thing to cut.

**What "the agent decides alone" then means** (the answer to the 20% criterion):
- Alone, logged with a sentence each: reading the request; choosing candidates and excluding products with a reason (41 of 51 in scenario 2, 19 of 30 in scenario 1, measured); combining products to cover the quantity; ranking the options; substitutes within the profile's scope; the re-check of price and availability; refusing what can never be ordered (`BLOCK`); preparing the order; deciding who must sign and why; expiring an order nobody confirmed in time.
- A person: the commitment. One confirmation on every order. A named role as well when a rule fires.
- Placing the order alone: only where the buyer switched it on, within the limits. No setting switches off a fixed rule.

**DECISION D1.** Who is "the user": the purchasing manager (minimum, no code) or a new role "the person who asked" (item F3)?
**DECISION D2.** Does the demo show the setting switched on once? I recommend yes, on My kitchen only, under 10 seconds, with the words "off by default, as Valio asked".
**DECISION D3.** Existing tests: run them with the setting on through one fixture (recommended), or rewrite them. See section 5.
**DECISION D4.** `CLAUDE.md:36` says "Keep an autonomous path." Proposed: "Keep the autonomous path as a buyer setting, off by default (V8)." João owns that file.
**DECISION D5.** An order that waits counts in the day's spend today (`orders/spend.py`). With every order waiting first, the daily limit fills sooner. Keep, or count only confirmed orders? I recommend keep, and say so in the assumptions.

## 5. Work items
Tests that pin today's behaviour, counted with grep over `tests/`: `"ORDERED"` or `OrderStatus.ORDERED` 122 lines in 52 files; `Verdict.AUTO` or `"AUTO"` 65 lines in 39 files; 163 pin lines in 55 files that also use the shipped profiles or the wired app. I ran the suite against the "off" profiles (a scratch pytest plugin, `p8_plugin.py`): 19 failures in the first 668 tests, about 20% of the suite in collection order (`tests/agent`, `tests/allergens`, part of `tests/api`), then my time cap stopped it. That is a partial count, not a total; the names of the failing tests were not printed. Rewriting them all does not fit 2 hours. A fixture that switches the setting on for the existing tests keeps the autonomous path tested; new tests pin the shipped default.

| id | what | files | hours | who | criterion | depends on |
|---|---|---|---|---|---|---|
| **Minimum** | | | **2.0** | | | |
| M1 | Both profiles `auto_order_enabled: false`; fix the comments | `src/tta/policy/profiles/hotel-kitchen.yaml:14`, `allergy-ward.yaml:13` | 0.1 | anyone | 20% controls (V8) | — |
| M2 | P-00 and the authority summary say "the agent prepares the order, a person confirms it" (data only) | `src/tta/policy/rules.yaml:288-302,468-471` | 0.3 | biomedical | 20% | M1 |
| M3 | One fixture keeps the setting on for existing tests; new tests of the shipped default on REST, agent run, MCP, renewal and first page; fix tests that read the two files directly | `tests/conftest.py`, new `tests/e2e/test_user_confirms.py`, `tests/policy/test_profiles.py`, `tests/e2e/test_demo_script.py` | 1.0 | computer science | 30% demo | M1 |
| M4 | Document lines (list below), MCP and `/docs` texts, the agent's instruction wording | list below; `src/tta/api/mcp_surface.py:71-84,234-241`; `src/tta/api/docs.py:61`; `src/tta/agent/prompts.py:70-80` | 0.6 | biomedical | 15% openness, 20% | M1 |
| **Full** | | | **+5.5** | | | |
| F1 | Result page: headline "Prepared by the agent: confirm to order" when only P-00 fired; one "Confirm and order as …" button (today two clicks through `/approvals`); label "within the agent's authority" on such an option; same on the menu and standing pages | `src/tta/ui/outcome.py:18-48`, `ui/request_page.py`, `ui/templates/_result.html:230-240`, `_marks.html:7-13`, `menu.html:144`, `standing.html` | 1.5 | computer science | 30% one flow, 20% | M1 |
| F2 | Status and audit sentences say "confirmed by …" when P-00 is the only rule accepted, for both readers | `src/tta/orders/wording.py:75-90`, `audit/sentences.py:205-216`, `audit/supplier_sentences.py:122-132`, `audit/standing_sentences.py:60-72` | 1.0 | computer science | 20% logged and auditable | M1 |
| F3 | Role `requester`: enum, role text, P-00 names it, profiles list who holds it, one demo identity per profile and for My kitchen | `src/tta/contracts/common.py:200-203`, `audit/phrases.py:49`, `policy/rules.yaml` (roles, `:296`), both profiles `:26-29`, `api/demo_tokens.yaml`, `api/sandbox.py:81-91`, `api/identity.py:34-38` | 1.5 | computer science | 20% | D1, F1 |
| F4 | The setting in three steps, with renewals within tolerance as the first step | `src/tta/contracts/policy.py:35`, `policy/facts.py:96`, `rules.yaml:70,288-302`, `ui/kitchen_page.py:39-50,92`, `kitchen.html:56-58`, `api/sandbox.py:65-69` | 1.5 | computer science | 20% | M1 |

Cut order: F4 first, then F3, then F2. F1 is the most visible.

Document lines that say the agent orders alone: `README.md:10,20,138` · `docs/DEMO.md:10,36,65,66,70,79,108,122,147,177,189,192` · `docs/PITCH.md:26,29,39,41,70,89` · `docs/ASSUMPTIONS.md:34,59` plus a new row "ordering alone is off in every shipped profile (Valio, 14 Nov)" · `AIMO/SPEC.md:23,148,215,233,254,264,334` · `CLAUDE.md:36`. Also `AIMO/WALKTHROUGH.md` (15 matching lines) and `AIMO/PLAN.md` (7).

## 6. What changes in the demo
- **Scenario 2.** Today: "✓ Ordered by the agent". After M1: "Sent for approval", then "Decide as Demo approver Jussi (purchasing manager)" → "Approve the chosen option" → "Ordered for €402.00 net with approval by Demo approver Jussi (purchasing manager): rule P-00 asked for a human and was accepted." Two more clicks than today; one with F1. Figures do not change (200 × `464013`, €402.00). The first button was seen on the result page; the approval and its sentence were measured over REST, not by clicking the page.
- **How to tell it** (replaces `docs/DEMO.md:122`, `docs/PITCH.md:29,70`): "Every claim is confirmed and €402 is within the ward's limits, so the agent has nothing to ask. It prepares the order; one confirmation places it." Scenario 1 then reads: "Here the agent does have something to ask: €2,580.64 is above the €750 limit."
- **Scenario 1.** Same option, €2,580.64, same signer. Only the sentence changes ("rules P-00 and P-01").
- **Standing order.** 100 L no longer ends "The agent placed this order alone for €248.00 net". Both 100 L and 290 L go to the purchasing manager (measured); the difference is the reason (P-00 against P-00 and P-08). F4 would bring the contrast back.
- **Your kitchen.** The box starts unticked. `docs/DEMO.md:147` needs one more step (tick the box). Shown once: tick it, run, "Ordered by the agent" (measured), and say it is the buyer's choice and the fixed rules stay on.
- **Audit trail.** The last sentence of scenario 2 becomes "Order ord_… is ordered, with approval by Demo approver Jussi (purchasing manager): 200 ST of 464013 for €402.00 net. Price and availability were checked again and had not changed."

## 7. Risks and what not to do
- Do not add a verdict or an order state tonight. `Verdict` and `OrderStatus` are in the contract, the schemas, the store and the test pins counted above; `policy/validation.py:82-86` refuses a rulebook whose default verdict is not `AUTO`.
- Do not delete the `AUTO` branch or P-00. The criterion scores "what the agent can decide alone".
- Do not let an agent's own statement count as the user's confirmation. Only a human token signs (F-06).
- Do not leave the P-00 wording as it is: "The agent cannot place this order alone" reads as a failure on the happiest path.
- Waiting orders count in the day's spend. In my shared-book run a second scenario 1 met P-02 (finance). Use "Start again" between takes.
- A prepared order expires at the option's "order by" time (measured: Sunday 15 November 17:00). If the round moves the clock (V6), check this again.
- The pages and the REST and MCP routes keep different order books (`api/sandbox.py:1-12`). A person cannot confirm on a page an order an outside agent prepared over REST; they sign on `POST /v1/approvals/{id}/decision`. Existing limit; say it in the assumptions.
- P4's questions on uncertain data belong in the confirmation form. `DecisionRequest` has only `decision`, `option_id` and `note` (`contracts/order.py:46-51`): answers need a field there. Not built here.

## 8. Questions
**For Valio (booth shape).**
1. *Who confirms.* Context: you said the order should always have the user's input. What we did: every order the agent prepares waits for a person of the buyer; an agent cannot confirm. What we got: an order within every limit waits for one confirmation; an order above the buyer's limit waits for the purchasing manager. Example: "200 litres of a milk substitute by Monday; no milk, no gluten" → 200 × `464013`, €402.00, prepared, waiting. Ask: is one confirmation by the person who asked enough, or must a specific person (the webshop account holder) confirm every order? If nobody answers: the buyer's purchasing manager confirms.
2. *The setting.* Context: your brief says "the agent places the order within its authority" and "before auto-renewing it"; you told us to deactivate automatic ordering for now. What we did: it is a buyer setting, off in every profile we ship. Example: a weekly 100 L of `469363`, €248.00, within the 25% tolerance. Ask: may we show a buyer switching it on once for its own kitchen, is that expected or did we misread you? If nobody answers: we show it once, on the visitor's own profile, labelled "off by default".

**For the team.** D1 to D5 above. For João: what did "the user" mean in the mentor's words, the person typing the request or the customer account?
