# L4a (standing orders, menus, orders, store) — done, with two changes needed from L4b / L3 to finish M-1 and the P-02 sentence

No git write, no outside call, `.env` not read, no new dependency, no contract change. Every figure was measured offline in replay at the **default clock** (the recording's instant, Sat 14 Nov 2026 02:52 Helsinki); nothing here was measured at the demo clock.

## Per package

| Package | What changed | Proof |
|---|---|---|
| **A3 F1** (HIGH) | `POST /v1/standing-orders` is limited: (1) a buyer holds at most **20** standing orders, counted inside the unit of work that saves (`StandingOrders.set_up`, so the page's demo load is bounded too); (2) a set-up is counted by the rate limit as an offer is (`CallKind.LOOKUP`), **in windows of its own** (see "Defaults"); (3) in dev and demo the request has at most 5 lines, as an offer; (4) the list answers at most 100 (`LIMIT 100` in both stores, and in `StandingOrders.list`). A refused set-up writes no row and no audit event. `RateLimited` added to the route's documented problems | `tests/standing/test_set_up_limits.py` (7 tests; `test_the_reviews_flood_is_refused_over_rest` is the review's proof shortened: a 20-line 2,000-character request answers 422, 40 set-ups give at most 20 × 201 and then 429) · `tests/store/test_sqlite_store.py::test_the_list_of_standing_orders_answers_the_first_hundred` |
| **A2a M-1** | The planner asks for a plan's offers through `service.create_menu_offer` when the gateway service has it, else through `create_offer` as before. A menu of more than 20 lines is refused in plain words ("This menu needs 21 request lines; one offer holds at most 20. Plan fewer dishes at once.") instead of a validation error. **`Gateway` does not have the method yet: until L4b adds it (below), lasagne + oven pancake still answers 422 "at most 5 lines; this one has 7" in dev and demo** | `tests/menus/test_review_a2a.py::test_m1_*` (3 tests; the first uses a stand-in service that has the method: 7 lines planned in 3 offers; the second passes today and skips itself once `Gateway` has the method) |
| **A2a M-2** | A stand-in's sentence, and a plan note, name the allergens its product declares and which of them the recipe's own type does not declare (new `menus/allergens.py`; one catalog search and one product read, no supplier call). Nothing is blocked: F-09 already sends it to a person | `test_m2_*` (2 tests): rice porridge for 5,000, confirmed only → "Allergens: Oatly iKaffe Oat drink 1L (464320) declares cereals containing gluten (AW) and oats (GO). The recipe's milk does not declare them: check the dish against the guests' allergies."; the demo's yoghurt for quark → "… declares milk (AM), as the recipe's quark (maitorahka) does." |
| **A2a M-4** | A line fails only when **no option** of the first offer covers it to the profile's minimum. The recipe's own ingredient is kept and the sentence names the option that holds it | `test_m4_*` (2 tests): the demo menu without "confirmed only" keeps quark, 1 offer instead of 3, "Option 1 (Best confirmed option (partial fill)) covers 0% of that line; option 2 (Alternative: quantity not confirmed) covers 100%: the recipe's own ingredient is kept, and a person chooses the option." With "confirmed only" the demo is unchanged (yoghurt stands in, €476.48) |
| **A2a M-3** | An ingredient that cannot be sourced **stays in the final offer** with nothing offered for it. So the offer shows what is missing and existing rules judge it: P-03 (fill below the minimum) and, when the menu has a date, the fixed rule F-07. A plan note says so. No contract or policy change was needed | `test_m3_*` (2 tests). Reproduced first: with ordering alone switched on in a browser's kitchen, oven pancake for 50 was **ORDERED by the agent alone** (8 × 463047, €16.08, eggs, flour and sugar missing). Now `PENDING_APPROVAL`, F-07 and P-03, reason "… 0 of 2 kg of eggs, request line 2 …" |
| **A2a M-5** | Sentences: "not in the recorded capture" → "not in this demo's recording"; an ingredient whose only reason is that reads "Cannot be sourced in this demo: eggs: none of its 30 products is in this demo's recording of Valio Aimo's data, so no price or stock is known for it; …" (no date). The page's label is not mine (below) | `test_m5_*` |
| **A4 H2** (back end) | Decided from PLAN decision 9: **waiting orders still count** in the day. `orders/spend.py` now keeps the two parts (`day_spend() -> DaySpend(ordered, waiting)`); `day_committed_net_eur` is unchanged in value. An approval that P-02 asks for carries one more line in `approval.reasons` saying both parts. The five examples of the first page, in four different orders in one order book, never meet the limit per day: the hotel's four come to €1,605.39 of €3,000 on B0's tree | `tests/api/test_l4a_five_examples.py` (5 tests) · `tests/orders/test_spend.py` (3 new) · `tests/orders/test_decide.py` (reasons 2 → 3) |
| **P16** `order.record_note` | Every order record now ends with: "No payment is taken here: the buyer is assumed to be a Valio Aimo credit customer, invoiced after delivery for what is delivered." Set in `orders/records.py`; the contract's default constant is untouched | `tests/orders/test_place_order.py::test_the_order_record_keeps_…` |
| Coordinator's message (L3a landed) | Three pins in my folders updated to what the code now says (checked by running, values below); `APPROVER_NOT_LISTED` now gets the profile's display name (`orders/service.py`); `placed_alone(net, offer.profile_id)` left as it is | the run below |

## Tests (verbatim, shared working tree, after L3a landed)
```
.venv/bin/python -m pytest tests/orders tests/standing tests/menus tests/store tests/store_pg tests/api/test_l4a_five_examples.py -q -p no:cacheprovider
367 passed, 68 skipped in 66.23s (0:01:06)

.venv/bin/ruff check src/tta/orders src/tta/standing src/tta/menus src/tta/store src/tta/api/standing_routes.py src/tta/api/menu_routes.py tests/orders tests/standing tests/menus tests/store tests/store_pg tests/api/test_l4a_five_examples.py
All checks passed!
```
Coverage of `tta.menus`, `tta.standing`, `tta.orders` together: 98% (`menus/allergens.py` 85%).

## Files
Changed: `src/tta/api/standing_routes.py` · `src/tta/api/menu_routes.py` (docstring) · `src/tta/standing/service.py` · `src/tta/store/schema.py` · `src/tta/store/sql/__init__.py` · `src/tta/store/sqlite_store.py` · `src/tta/store/postgres.py` (docstrings) · `src/tta/menus/planner.py` · `plan.py` · `wording.py` · `src/tta/orders/spend.py` · `checking.py` · `records.py` · `service.py` (one argument) · `tests/menus/test_planner.py` · `tests/orders/test_decide.py` · `test_ordering_alone.py` · `test_place_order.py` · `test_spend.py` · `tests/standing/test_renewal_flow.py` · `tests/store/test_sqlite_store.py`
Created: `src/tta/menus/allergens.py` · `tests/menus/test_review_a2a.py` · `tests/standing/test_set_up_limits.py` · `tests/api/test_l4a_five_examples.py` · this file.
Not mine and seen in my folders: `src/tta/orders/wording.py`, `tests/orders/test_wording.py` (L3a).

## Contract fields added
None. (`StandingOrders.__init__` gained two optional keyword arguments, `count_set_up` and `max_request_lines`, and a method `with_limits`; existing callers are unchanged.)

## Figures measured (default clock, replay)
- Five examples: scenario 1 €1,083.39 · 2 €402.00 (ward) · 3 €174.00 · 4 €208.00 · 5 €140.00 on B0's tree; hotel total €1,605.39. **On the shared tree after other lanes' changes, scenario 4 is €236.00** (not my change; hotel total €1,633.39). No P-02 either way.
- Scenario 1 three times in one book: the third meets P-02 at €3,772.17, "€0.00 ordered and €2,688.78 waiting".
- Oven pancake, 50 servings: before, final offer milk only, €16.08, F-10 (AUTO with the setting on); now 4 lines, €16.08, fill 0, F-07 + P-03, 1 offer instead of 2.
- Rice porridge, 5,000 servings, confirmed only: milk covers 38% (the review's 84% was before coffee milk left the type); 1,500 × 464320, €2,670.00, F-07, F-09, P-01, P-03.
- Lasagne 50 + oven pancake 50 through `create_menu_offer`: 7 lines, 3 offers, option 1 €214.22 (14 × 463047 milk, 8 × 474852 brisket for minced meat), F-07, F-09, P-03, P-06; 5 ingredients not in the recording.
- Demo menu without "confirmed only": option 1 €441.44 (no quark, F-07, P-03, P-06), option 2 €481.22 with 3 × 477044 quark (F-01 × 3, P-06).

## Pins moved
In tests I do not own: **none.** Checked by running `tests/api`, `tests/e2e`, `tests/ui`, `tests/mcp`, `tests/audit`, `tests/evidence`, `tests/deploy` and the root tests on a copy of commit `6fab186` plus only this lane's files (in the scratchpad, so no other lane's half-done change is in it): every test passed. On the shared tree two tests of `tests/ui/test_approvals.py` failed when I ran them (`test_a_card_sent_to_the_dietitian_shows_the_allergen_findings_above_the_buttons`, `test_the_trade_off_is_escaped[finding]`); both pass on the copy with my files, so they come from another lane.
In my folders, moved by L3a and updated: `tests/orders/test_decide.py` ("Prepared: confirm to order. The agent prepares the order, a person confirms it (F-10): a role this approval already names confirms." and "Confirmed by Finance (demo) (finance): ordered for €700.00 net.") · `tests/orders/test_ordering_alone.py` ("… €428.00 net: no rule asked for a human and every statement of the offer is confirmed.") · `tests/standing/test_renewal_flow.py` ("… tolerance of Harbourside Hotel.").

## Needed from another lane
1. **L4b, `src/tta/api/service.py`, class `Gateway` (finishes M-1).** Add
   ```python
   def create_menu_offer(self, identity: Identity, request: PurchaseRequest) -> Offer:
       """An offer for a menu plan: as `create_offer`, under the contract's 20 lines instead of the demonstration's 5.
       The planner builds each line from the recipe table (a product type and a quantity), so the large free text
       the 5 keeps out cannot arrive this way."""
       _require_agent(identity)
       self._deps.limiter.check(identity, CallKind.LOOKUP)
       return self._offer(identity, request)
   ```
   Nothing else: the planner finds it by name (`menus/planner.py`, `MENU_OFFER`), on the REST route and on the menu page alike. It must not be exposed as a route or an MCP tool. After it lands: `tests/menus/test_menu_page.py::test_a_refusal_of_the_gateway_is_shown_on_the_page` (five dishes, expects "at most 5 lines") will need another refusal to show; a 7-line plan asks for up to 3 offers of 7 lines each, and the review saw large plans take long: time one.
2. **L4b, `src/tta/api/app.py:118` (optional).** To count set-ups in the gateway's own windows instead of windows of their own, `Gateway` would expose its limiter and `app.py` would pass `count_set_up=lambda identity: limiter.check(identity, CallKind.LOOKUP)` to `StandingOrders(...)`; `include_standing_routes` keeps a counter that is already set.
3. **L3 (rules) with a contract field, for the P-02 sentence itself.** Today the two parts are only in `approval.reasons`. To put them in the rule's sentence: `PolicyContext.day_waiting_net_eur: Decimal | None = None` (`contracts/policy.py`), a fact for it in `policy/facts.py`, P-02's `message` in `rules.yaml` ("… would reach €X before tax (€A ordered, €W waiting for approval, €B this order), above …"), `OfferDeps.day_spend` returning both parts (`offers/deps.py`, `api/wiring.py:173`; `tta.orders.spend.day_spend` gives them). I pass the context from `orders/checking.py` once the field exists.
4. **L3, F-09's sentence (M-2, second half).** The plan names the stand-in's allergens; rule F-09's own sentence on the approval does not. It needs a line fact with the declared codes of a `stands_in_for` line.
5. **Interface, `src/tta/ui/menu_page.py:49` and `templates/menu.html:92` (M-5).** The label and heading "Cannot arrive in time" → "Cannot be sourced". The sentence under it is now right.
6. **`contracts/ports.py:201`**, docstring of `Store.list_standing_orders`: "every standing order" is now "the first 100".
7. **Documents (E2):** `docs/DEPLOY.md:150` quotes `record_note`; it now has one more sentence.

## Defaults taken
- **Waiting orders count in the day** (PLAN decision 9). The prompt's "the fifth must not be sent to finance because earlier examples are waiting" holds on the figures since B0 (€1,605.39 of €3,000), not by a rule change. A visitor who runs the large example three times does meet P-02, and the approval says why. If the team wants waiting orders not to count, it is one line (`COMMITTED_STATUSES` in `orders/spend.py`) plus pins; the limit would then be enforced when a person approves, since the day is read again at decision time.
- **20 standing orders per buyer**, ours and illustrative. No route deletes one, so on the public link the hotel's and the ward's shared books fill once and stay full until the data is wiped.
- **A set-up has its own rate-limit windows** with the gateway's values, because the gateway service keeps its limiter private and `api/service.py` is not mine.
- **M-3 through existing rules, not a new fixed rule.** Without a needed-by date only P-03 fires, and a profile whose minimum fill is 0 would let an incomplete menu through alone when its ordering-alone setting is on. A fixed rule needs a request field and a rule (L3).
- **M-2 compares with what every product of the recipe's type declares**; when the catalog search does not return all of them (more than 100), nothing is compared and every declared code is named. It errs towards naming more.
- The probe offer keeps its 5 lines (`MAX_PROBE_LINES`), also with `create_menu_offer`.
- A2a's S-2 to S-8, M-6 to M-8 and A3 F2 are not in my packages and are not built.

## Open questions
- For the team: should a standing order be deletable (the cap makes this matter)?
- For the team: is "credit customer" the assumption to show on every order (P16 labels it as ours)?

## For the interface
| Field, route or sentence | Example | What a person should read |
|---|---|---|
| `order.record_note` | "Recorded in the gateway's order book. … It commits nobody. No payment is taken here: the buyer is assumed to be a Valio Aimo credit customer, invoiced after delivery for what is delivered." | As it is; the order views print it already |
| `approval.reasons[]`, one more line when P-02 fired | "Before this order, today's spend of this buyer is €2,688.78 before tax: €0.00 ordered and €2,688.78 waiting for approval. A waiting order counts until a person rejects it or its time to decide passes." | As it is, under the rule's sentence |
| `POST /v1/standing-orders` → 422 | "This buyer already has 20 standing orders, the most one buyer sets up here. Renew one of them (POST /v1/standing-orders/{standing_order_id}/renew) instead of setting up another." | A page that sets one up should show the problem's `detail` |
| `POST /v1/standing-orders` → 422 / 429 | "In this demonstration the request of a standing order has at most 5 lines; this one has 6. Set the others up as another standing order." · the usual rate-limit problem with `Retry-After` | the `detail` |
| `plan.dishes[].ingredients[].sentence`, status `STANDS_IN` | "… Allergens: Oatly iKaffe Oat drink 1L (464320) declares cereals containing gluten (AW) and oats (GO). The recipe's milk does not declare them: check the dish against the guests' allergies." | Printed already as the ingredient's sentence |
| `plan.notes[]` | the same allergen sentence when the stand-in adds something or states nothing · "3 ingredients cannot be sourced (eggs, flour and sugar). Their lines stay in the offer with nothing offered for them, so the offer says what is missing and the rules judge the menu as a whole: an order of the rest goes to a person." | Notes; worth showing above the options |
| `plan.cannot_be_sourced[].sentence` | "Cannot be sourced in this demo: eggs: none of its 30 products is in this demo's recording of Valio Aimo's data, so no price or stock is known for it; the recipe lists no alternative that does the same job." | Heading and label should say "Cannot be sourced", not "Cannot arrive in time" |
| `ingredient.request_line_index` on `CANNOT_BE_SOURCED`, and `plan.lines[]` | `1` | New: an unsourced ingredient has a line in the final offer (covered 0). The "Request lines" list shows it; the options show "0 of 2 kg of eggs" |
| `ingredient.sentence`, status `ORDERED_AS_IN_RECIPE` | "12 kg to order as quark (maitorahka), on line 3 of the offer. Option 1 (Best confirmed option (partial fill)) covers 0% of that line; option 2 (Alternative: quantity not confirmed) covers 100%: the recipe's own ingredient is kept, and a person chooses the option." | As it is |
| `POST /v1/menus/plan` → 422 | "This menu needs 21 request lines; one offer holds at most 20. Plan fewer dishes at once." | the `detail` |
