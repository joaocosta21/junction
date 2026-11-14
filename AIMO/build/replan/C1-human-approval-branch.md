# C1 — Review of `5673ef2` "Require human approval for every eligible order" (Sofia, `origin/codex/mandatory-human-approval`)

Agent C1, 14 Nov, 15:37–16:00. **Ran** = executed in my worktree on the commit, offline in replay (brief §5 recipe, fresh data folder per script). **Read** = from the diff or the file. Scripts and outputs: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/c1/` (`paths.py`, `pages.py`, `pages2.py`, `pytest.out`, `tests.diff`). Nothing was changed in the main checkout.

## Verdict
**Take it with a named list of fixes.** It does what its title says on every path (ran), but it does it by a rule written in code, it removes the buyer's setting from the page and deletes the autonomous path, and it leaves 3 tests red.

| # | Fix | Hours | When |
|---|---|---|---|
| X1 | 3 failing tests; the first-page agent cards lost the limits (`€750`, `€500`) | 0.25 | before it becomes the baseline |
| X2 | Restore ordering alone as a buyer setting, **off by default** (steps in §4) | 1.5 | after; moves none of her default-path pins |
| X3 | Rule id `F-10` is the one PLAN R5 reserves for the formula rule: R5 takes `F-11`, or this one is renamed. `rules.yaml:7` still says "no rule is written in code": say where F-10 lives, or move it to data | 0.25 | with X2 |
| X4 | Wording still untrue (list in §6) | 0.5 | with D1 |
| X5 | Decide: an approval asked of finance can now be completed only by the purchasing manager once P-02 stops holding (§3) | 0–0.5 | decision |

Hours are my estimates, not measured. **Gain against writing R1 from the plan (2.0 h): about 1 h if the setting stays removed (X1+X3+X4 = 1.0 h); none if it is restored (2.5 h).** What it buys either way: it exists, it is measured on 7 paths, 57 test files already pin the shipped default, and `docs/DEMO.md` is rewritten for the new outcomes (part of R9).

**For Sofia:** The commit holds on every path we tried and the test rewrite is honest, thank you; three tests it did not touch fail (`tests/deploy/test_check.py`, `tests/evidence/test_approval_evidence.py`, `tests/ui/test_pages.py`). We keep it as the baseline but put ordering alone back as a buyer setting that is off by default, because the 20% criterion scores "what the agent can decide alone" and Valio's second answer allows the setting.

## 1. What it does
**Mechanism (read): code, not the profile.** New `src/tta/policy/human_approval.py` holds a constant rule `F-10` ("Every order needs human approval", fixed, APPROVAL, purchasing manager) and `require_human_approval(decision)`: a BLOCK, or an APPROVAL that already names a role, passes unchanged; anything else becomes APPROVAL by the purchasing manager with F-10 appended. It is applied in `RulePolicyEngine.evaluate` (`engine.py:119`) and again at order time (`orders/checking.py:87`). The `AUTO` branch of `OrderBookService.place_order` is deleted. Both profile files still ship `auto_order_enabled: true`; P-00 is not what forces approval.

| File | Change |
|---|---|
| `README.md` | Opening line, flow diagram, scenario 2, the "dearer product" limit: "submit a proposed order for human approval", F-10 |
| `docs/DEMO.md` | 21 lines: every "Ordered by the agent" outcome becomes "Sent for approval"; kitchen section retitled "the buyer sets its review limits"; standing-order steps; video line |
| `agent/summaries.py` | `auto_order_enabled` dropped from the profile fields in the agent's trace |
| `api/docs.py` | `/docs` intro: verdicts are "`APPROVAL` or `BLOCK`"; "Every eligible order waits for an authorised human decision" |
| `api/mcp_surface.py` | `INSTRUCTIONS`, `get_offer`, `place_order` texts: no `AUTO`; "submit … for human approval" |
| `api/routes.py` | `POST /v1/orders` summary and text |
| `api/sandbox.py` | `auto_order_enabled` leaves the kitchen's settings and is pinned `True` in its fixed parts |
| `orders/checking.py` | Order-time decision wrapped in `require_human_approval` |
| `orders/outcomes.py`, `records.py`, `wording.py` | `placed_alone`, `placed_by_agent` and the "placed this order alone" sentence deleted |
| `orders/service.py` | The `AUTO` branch deleted: every order that is not blocked creates an approval |
| `policy/engine.py` | `evaluate` returns the wrapped decision; F-10 is first in the authority's rule list and in the policy hash |
| `policy/rules.yaml` | Comment on `AUTO`; P-00's authority texts; the two authority summary sentences replaced by F-10 sentences |
| `policy/validation.py` | One error message |
| `standing/__init__.py` | Docstring |
| `ui/kitchen_page.py`, `kitchen.html` | The checkbox "The agent may order alone at all" removed; titles reworded |
| `index.html` | Each agent card says only "Every order requires human approval." (the limits are gone) |
| `approvals.html`, `menu.html`, `standing.html` | Lead texts; the menu button is always "Send this option for approval" |

- **The setting.** Still a field of `BuyerProfile`, still `true` in both files (comment "false sends every order to a human (P-00)", now misleading). Not editable on "Your kitchen" (ran): no checkbox; a hand-made form with it answers 422, "The settings were not saved. Nothing was changed: auto_order_enabled: is set by the gateway for My kitchen, not on this page". It still does one thing (ran with a scratch copy of the profiles set to `false`): P-00 is named instead of F-10 ("rules P-00 and P-01 ask for a human"). It no longer decides whether an order is placed alone.
- **Is `AUTO` reachable?** No. Read: `require_human_approval` never returns it and `place_order` has no branch for it. Ran: the paths below, none placed an order without a person. Left as dead code: `Verdict.AUTO`, `PlacedBy.AGENT`, the event `order.placed_by_agent` and its sentences for both readers, "Ordered by the agent" in `ui/outcome.py`, `decision_sentences.AUTO` in `rules.yaml:459`.
- **"Eligible"** is not defined. Read from `routes.py` ("An eligible option becomes a `PENDING_APPROVAL` order … `BLOCK` gives a `policy-blocked` problem"): an option the policy does not block and whose re-check passed.

## 2. Does it hold
**Suite (ran once, whole):**
```
FAILED tests/deploy/test_check.py::test_every_check_passes_against_the_gateway
FAILED tests/evidence/test_approval_evidence.py::test_an_order_the_agent_places_alone_asks_for_no_evidence
FAILED tests/ui/test_pages.py::test_the_profiles_are_shown_with_their_limits_and_labelled_as_illustrative
3 failed, 3258 passed, 67 skipped, 1 deselected in 397.45s (0:06:37)
```
Run alone again: `3 failed in 10.01s`. All three are files the commit did not touch, pinning the old outcome: `"ORDERED" in` the deploy check's detail (got "PENDING_APPROVAL by None"); `order.status is ORDERED`; `"€750" in page and "€500" in page`. 3,261 tests ran against 3,260 on `7f09ce7`: the extra one was not traced. The suite took 6:37 because my replay scripts ran beside it.
**Lint (ran):** `All checks passed!`

**Every path, ordering without a person (ran, shipped profiles):**

| Path | Result, in the words a person reads |
|---|---|
| `POST /v1/orders`, scenario 2 | 201 `PENDING_APPROVAL`, `placed_by: null`, fired `F-10`. "Every order needs human approval before it can be confirmed (F-10). It needs the purchasing manager." · "Waiting for approval by the purchasing manager, to be decided by Sunday 15 November 2026 at 17:00 (UTC+02:00): rule F-10 asks for a human." |
| `POST /v1/orders`, scenario 1 | `PENDING_APPROVAL`, fired `P-01` only (F-10 is not added when another rule names a role). "The agent cannot place this order alone: the total of €2,580.64 before tax is above the €750 limit per order of profile hotel-kitchen (P-01). It needs the purchasing manager." |
| `POST /v1/agent/run`, scenario 2 | steps `get_authority`, `create_offer`, `place_order`; `order_status: PENDING_APPROVAL`; the report ends "rule F-10 asks for a human." |
| MCP `place_order` | `PENDING_APPROVAL`, fired `F-10`, same sentences. Tools: no approve tool |
| Renewal, REST | `PENDING_APPROVAL` (in my shared book it met P-02, finance) |
| Renewal, page, fresh book | 100 L: "Waiting for approval by the purchasing manager … rule F-10 asks for a human." 290 L: "… rule P-08 asks for a human." |
| Menu, REST plan then order; page button | `PENDING_APPROVAL`, fired `F-09`, `P-02`, `P-06`; page: "Sent for approval … rules F-09 and P-06 ask for a human." |
| First page, all 5 example buttons | Each: "Sent for approval", then "Decide as Demo approver Hanna (purchasing manager)" (Jussi for the ward; "Leena (dietitian)" alone for example 4) |
| Your kitchen, "40 litres of oat drink by Monday" | "Sent for approval" · "Decide as Demo approver Hanna, My kitchen (purchasing manager)" |
| Agent token on its own approval | 403: "An agent cannot approve or reject an order (F-06). A human with the role asked for decides." |

Not run: the photo button (it needs the model).

## 3. The tests
57 files, 212 lines out and 218 in; `assert` lines 163 out, 164 in; 11 tests renamed, none added or removed; no skip, no xfail, no conftest change (counted on the diff). I read the whole diff of all 57.
- **Almost all changes flip the expected outcome only:** `ORDERED` → `PENDING_APPROVAL`, `AUTO` → `APPROVAL`, `fired == ()` → `rule_ids == ("F-10",)`, "Ordered by the agent" → "Sent for approval", event `order.placed_by_agent` → `approval.requested`.
- **Weakened (exact sentence → substring, or dropped):** `tests/orders/test_place_order.py:51` (status sentence → `"F-10" in`), `tests/orders/test_decide.py:238`, `tests/orders/test_decide_at_order_time.py:102` (exact status sentence dropped), `tests/policy/test_scenarios.py:152` (exact decision sentence → `"F-10" in`), `tests/policy/test_authority.py:46` (two exact summary sentences → substrings), `tests/ui/test_order.py:42`. Dropped with nothing in its place: "within its authority" in the last audit sentence (`tests/e2e/test_scenario_2_allergy_ward.py:61`, `tests/api/test_flow.py:100`): no test now pins the sentence that says who confirmed. `tests/e2e/test_demo_script.py:54` went from `[ORDERED]*3 + [PENDING_APPROVAL]` to `[PENDING_APPROVAL]*4`, so that line no longer shows the fourth run differing (lines around it not read).
- **Strengthened:** `tests/agent/test_fallback.py:500` (one status instead of two); `tests/orders/test_one_order_per_offer.py`; `tests/api/test_flow.py:95` checks the approval's role.
- **A behaviour change inside a test:** `tests/orders/test_decide.py:233`. An approval asked of finance (P-02), once P-02 no longer holds at decision time: before, finance completed it; now finance gets `NotAuthorised` and the purchasing manager, never named on that approval, must sign (F-10).
- **Autonomous path:** tested nowhere, because no code can take it. 17 lines with `AUTO` and 14 with `PlacedBy.AGENT` or `placed_by_agent` remain in tests of sentences and contracts.
- **New default end to end:** yes. `tests/e2e/test_scenario_2_allergy_ward.py` goes request → `PENDING_APPROVAL` → `approve_all_roles` → `ORDERED`, `HUMAN_APPROVAL`, with events `approval.requested`, `approval.decided`, `order.confirmed`. Also REST, MCP, agent run, renewal and the pages. No test pins the 422 for a forged `auto_order_enabled`.

## 4. Against the plan (P8)
| Item | State | How |
|---|---|---|
| M1 profiles `false`, comments | **Missing** | Both stay `true`; approval is forced in code |
| M2 P-00 and authority wording, data only | **Done differently** | Authority summary rewritten around F-10; P-00's text points at F-10. "The agent cannot place this order alone" stays on every other rule, and the audit says "The agent could not place order … alone, because 1 rule asks for a human. F-10: …" on the happiest path: the failure wording the plan wanted gone |
| M3 one fixture, new tests for the default | **Done differently** | No fixture: 57 files re-pinned to the default. 3 files missed |
| M4 documents, MCP, `/docs`, prompts | **Partly** | Done: `README.md`, `docs/DEMO.md`, MCP instructions, `/docs` intro, the order route. Missing: §6 list |
| F1 "Prepared: confirm to order", one click | **Missing** | "Sent for approval" → "Decide as …" → "Approve the chosen option": two clicks. Only the menu button was renamed |
| F2 "confirmed by …" sentences | **Missing** | "Ordered for €402.00 net with approval by Demo approver Jussi (purchasing manager): rule F-10 asked for a human and was accepted." |

**Where hers is better:** no path can be forgotten (two enforcement points, branch deleted, ran on every path above); one signature is enough when a specialist already signs (example 4: the dietitian alone; P-00 would add the purchasing manager, read from the rule's role, not run); the suite pins what we ship.
**Where the plan is better:** the rule stays data (`rules.yaml:7`: "This file is DATA … no rule is written in code"; the hash is no longer "this file plus the profile"); the buyer keeps a setting; the autonomous path stays tested; R7 and the role "the person who asked" build on P-00.
**What the unconditional rule costs.** Against Valio: nothing. It matches the first answer word for word and is stricter than the second ("after and if you are 100% sure yes"). On the 20% criterion: "what the agent can decide alone" no longer holds any order, under any setting; "Your kitchen" changes only the reason shown and whether finance also signs; P8 §7 said "Do not delete the `AUTO` branch or P-00", and `CLAUDE.md` says "Keep an autonomous path".
**Smallest change that keeps her work and puts the setting back, off by default (X2; designed by reading, not built or run):**
1. `require_human_approval(decision, profile)`: unchanged decision when `profile.auto_order_enabled` is true (two call sites).
2. Both profile files and My kitchen: `auto_order_enabled: false`. P-00's own `when` must then stop firing, or it names P-00 and the purchasing manager on every decision and breaks her pins; F-10 becomes the rule the setting drives, so it is no longer "fixed" and leaves "Always, whatever you set".
3. `git checkout 7f09ce7 -- src/tta/orders/service.py src/tta/orders/records.py src/tta/orders/outcomes.py src/tta/orders/wording.py` (28 lines: the `AUTO` branch).
4. Checkbox back: the hunks of `ui/kitchen_page.py`, `kitchen.html`, `api/sandbox.py`, `agent/summaries.py`, `index.html`, `menu.html`.
5. Tests: `tests/policy/test_profiles.py:38,54,248`; about six new tests of the switched-on path. Her pins on the default should hold, because the fixtures read the shipped files.

## 5. Who is asked
The buyer's **purchasing manager**, whenever no other rule names a role. Words: "It needs the purchasing manager."; button "Decide as Demo approver Jussi (purchasing manager)". The ward's dietitian is refused: "The approval still needs the purchasing manager; this approver counts for the dietitian and holds none of them." When another rule names a role, only that role signs. There is no "person who asked".
**Audit (ran):** yes, by name for the buyer, by role for Valio.
- Buyer: "Demo approver Jussi (purchasing manager) approved order ord_…. This approval accepts rule F-10." · "Order ord_… is ordered, with approval by Demo approver Jussi (purchasing manager): 200 ST of 464013 for €402.00 net. Price and availability were checked again and had not changed."
- Valio: "A human at the buyer approved order ord_…." · "… is ordered, with approval by a human at the buyer …"

## 6. What else is in it
- **Outside the title:** the first-page cards lose each profile's limits; the kitchen checkbox is removed; `auto_order_enabled` leaves the agent's trace; the policy hash of every profile changes (F-10 is hashed).
- **Still untrue after the commit (read, X4):** `index.html:7` "the agent orders within its authority or the order goes to a human"; `kitchen.html` lead "Set what … may order without a human"; `ui/examples.py:77` "within the spend limit: the agent orders alone." (the scenario-2 button); `base.html:35`; `agent/prompts.py:72` and `agent/tools.py:49` "what you may decide alone"; `mcp_surface.py:184`; `routes.py:102`; both profile comments; `rules.yaml:7,16`. Untouched documents: `docs/PITCH.md` (7 lines), `docs/ASSUMPTIONS.md` (served at `/assumptions`; no row says ordering alone is off), `docs/ARCHITECTURE.md`, `docs/AWARDS.md`, `AIMO/SPEC.md`.
- **`README.md`, `docs/DEMO.md`:** I found no line that is false against what I ran. `docs/DEMO.md` quotes "? Waiting for approval · €248.00 net, rule F-10." as page text; the page says "Waiting for approval by the purchasing manager, to be decided by …: rule F-10 asks for a human."
- **Secrets:** none in the added lines (grep for key, secret, token, bearer, key prefixes).
- **Message and trailers:** subject only, no body, no trailer. Author and committer `sofia <sofia.costa@junitec.com>`, 14 Nov 15:31 +0200. Not our `<type>: <description>` format.

## 7. Merging
- **Onto `7f09ce7`:** a fast-forward. Its parent is `7f09ce7`, which is `overnight-build` and `origin/overnight-build` (rev-parse).
- **Later.** 17 of its 57 test files also hold coffee-milk pins (`463380`, `2,580.64`, `2580.64`, `565`): `tests/api/test_sandbox_profile.py`, `tests/e2e/test_demo_script.py`, `tests/offers/test_data_truth_recording.py`, `tests/offers/test_exclusions_and_requests.py`, `tests/orders/test_concurrency.py`, `test_decide.py`, `test_decide_at_order_time.py`, `test_place_order.py`, `tests/policy/test_claims.py`, `test_custom_profile.py`, `test_dated_lines.py`, `test_missing_facts.py`, `test_order_time.py`, `test_rules.py`, `test_scenarios.py`, `tests/ui/test_order.py`, `test_run.py`. The `565` pattern is loose, so 17 is an upper bound. None of her changed lines holds a pin (0 in the diff), so a package started **from this commit** meets no conflict; one started from `7f09ce7` conflicts only where the two edits are within 3 lines (seen: `tests/orders/test_decide.py:229` and `:233`; not checked file by file).
- **Standing orders (R3):** `tests/standing/test_renewal_flow.py`, `test_rest_and_page.py`, `tests/policy/test_standing_drift.py`. Every renewal now waits, so once only ordered renewals count as history, each test that builds a history by renewing must approve each renewal. Not run.
- **Substitutes (R5):** `tests/e2e/test_scenario_3_substitutes.py`, `tests/policy/test_substitute_claims.py`, `test_stands_in_for.py`, `test_facts.py`, `test_rules.py`; and the id `F-10` (X3).
- **First or not:** taking it first saves the plan's "new tests for the shipped default" and the outcome lines of the demo script, and adds one approval step to every later test that needs an `ORDERED` order. It must be first: after R2 it would conflict in up to 17 files.
