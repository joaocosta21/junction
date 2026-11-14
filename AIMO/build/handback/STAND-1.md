# STAND-1 — done

## Built
- `src/tta/contracts/standing.py` (new): `StandingOrder`, `RenewalLine`, `Renewal` (with `synthetic`), `StandingHistory`, `DriftKind`, `DriftCheck`, `DriftReport`, `NewStandingOrder`, `RenewStandingOrder`. It imports no offer, order or policy contract (`PolicyContext` imports it).
- `src/tta/contracts/policy.py`: `BuyerProfile.standing_order_drift_ratio` (ratio 0 to 1, default `None` = not set); `PolicyContext.standing_history` (`None` = not a renewal, never a missing fact).
- `src/tta/contracts/ports.py`: `Store` gains `save_standing_order`, `get_standing_order`, `list_standing_orders`, `save_renewal`, `list_renewals` (additions only).
- `src/tta/contracts/audit.py`: `AuditEventType.STANDING_ORDER_CREATED` (`standing_order.created`) and `STANDING_ORDER_RENEWED` (`standing_order.renewed`). This file is not on my list; see "Contract changes needed".
- `src/tta/policy/reading.py` (new): `Missing` and `Reading` moved out of `facts.py`, which re-imports them, so the standing facts can use them without an import cycle. Every existing `from tta.policy.facts import Missing` still works.
- `src/tta/policy/drift.py` (new): `assess_drift(option, history, tolerance) -> DriftReport`. `DRIFT_WINDOW = 6` and `MIN_RENEWALS_TO_JUDGE = 3`. The quantity is compared for each request line, the unit price for each product, each against the median of that line's last 6 renewals.
- `src/tta/policy/standing_facts.py` (new): `standing.is_renewal`, `standing.history_judged`, `standing.largest_drift`, `standing.drift_found`, `standing.standing_order_id`, `standing.renewals_compared`.
- `src/tta/policy/facts.py`: the `profile.standing_order_drift_ratio` reader and `**STANDING_FACTS`. These were surgical edits; MENU-1's F-09 lines are untouched.
- `src/tta/policy/rules.yaml`: seven facts declared, and rule **P-08** (profile rule, order scope, APPROVAL, purchasing manager), with its authority texts and justification.
- `src/tta/policy/profiles/hotel-kitchen.yaml` sets the tolerance to `0.25`; `allergy-ward.yaml` sets it to `0.1`.
- `src/tta/store/schema.py`, `sqlite_store.py`, `sql/005_standing_orders.sql` (new), `sql/__init__.py`, `postgres.py`: the tables `standing_orders` and `standing_renewals` and the five port methods, on both stores.
- `src/tta/audit/standing_sentences.py` (new): buyer and supplier sentences for both events. They are registered in `sentences.py` and `supplier_sentences.py`. `trail.py` gives these events the subject `standing_order/<id>`. The supplier sees neither the buyer's name for the standing order nor the drift, whose sentence states the tolerance.
- `src/tta/orders/checking.py`: the order-time and decision-time policy context carries the history of the standing order that the offer's request renews. It leaves out this offer's own renewal, which is already recorded while the order waits.
- `src/tta/offers/deps.py`: `OfferDeps.standing_history` is optional (default `None`), plus `standing_history_of()`. `offers/options.py`: only the `PolicyContext(...)` line and its import.
- `src/tta/standing/` (new): `history.py` (`standing_history`, `history_lookup`; renewals whose order was REJECTED or EXPIRED are left out), `service.py` (`StandingOrders`: create, set_up, list, find, get, renew), `models.py` (`RenewalOutcome`, `StandingOrderDetail`), `demo.py` (`load_demo`).
- `src/tta/api/standing_routes.py` (new): `POST/GET /v1/standing-orders`, `GET /v1/standing-orders/{id}`, `POST /v1/standing-orders/{id}/renew`, and `include_standing_routes(app, standing)`.
- `src/tta/ui/standing_page.py` and `templates/standing.html` (new): the page `/standing-orders`, `POST /standing-orders/demo` and `POST /standing-orders/{id}/renew`.
- `src/tta/ui/kitchen_page.py` and `templates/kitchen.html`: a "Standing orders" fieldset. The tolerance is entered as a percentage, an empty field means not set, and P-08's sentence carries the kitchen's own value.
- Tests:
  - new: `tests/standing/` (conftest, `test_renewal_flow.py`, `test_rest_and_page.py`), `tests/policy/test_standing_drift.py`, `tests/audit/test_standing_events.py`, `tests/orders/test_standing_history_at_order_time.py`;
  - added to: `tests/store/test_sqlite_store.py` and `tests/store/conftest.py` (these run on PostgreSQL too, through `tests/store_pg/test_store_contract.py`), `tests/ui/test_kitchen_page.py`;
  - P-08 added to the pinned rule lists in `tests/policy/test_authority.py` and `test_rulebook.py`.

## What the orchestrator adds, and where
1. `src/tta/api/wiring.py`, `wire()`: add `standing_history=history_lookup(store),` to the `OfferDeps(...)` call, with `from tta.standing import history_lookup`. Both the shared book and every page sandbox go through `wire()`. Without it, a request that names a standing order is refused (`invalid-request`, "This gateway keeps no standing orders…").
2. `src/tta/api/app.py`, `_application(parts)`: after `app.include_router(public)`, add `include_standing_routes(app, StandingOrders(store=parts.store, audit=parts.audit, gateway=parts.service, clock=parts.clock))`, with `from tta.api.standing_routes import include_standing_routes` and `from tta.standing import StandingOrders`. The pages mount never takes `/v1`.
3. `src/tta/ui/routes.py`, `create_surface()`: add `standing_page.add_routes(app, site)` after `kitchen_page.add_routes(app, site)`, and import `standing_page`.
   - The page sandbox needs nothing new. The page keeps one `StandingOrders` per book (a `WeakKeyDictionary` over `book.store`, `book.audit`, `book.service`).
   - Its clock is the capture's pinned clock in replay and the machine's UTC clock in live mode.
   - It reads the capture once (`ReplayGateway(settings.replay_capture_dir)`) for the demo's prices.
4. `src/tta/ui/templates/base.html`: add the menu link `<a href="/standing-orders"{% if path == "/standing-orders" %} aria-current="page"{% endif %}>Standing orders</a>`.
5. `src/tta/api/sandbox.py`: add `"standing_order_drift_ratio"` to `KITCHEN_SETTINGS`, so that "Start from a copy of hotel-kitchen" copies its 25%. Until then My kitchen starts with the tolerance unset: a renewal with enough history goes to a human for a missing fact (F-03). Saving the kitchen form sets it either way.
6. The docs (route table, assumptions page) and, if wanted, MCP tools for the four routes.

`tests/standing/test_rest_and_page.py` makes changes 1 and 3 by monkeypatching and change 2 by calling `include_standing_routes`. It shows the exact wiring working end to end.

## Tests
```
COVERAGE_FILE=<scratch> .venv/bin/python -m pytest tests/standing tests/policy tests/store tests/audit tests/orders tests/ui/test_kitchen_page.py -q -p no:cacheprovider
.................................                                        [100%]
825 passed in 10.77s
```
Coverage of the new code (same run with `--cov`): standing_routes 100%, standing/history 100%, standing/models 100%, standing/service 94%, standing/demo 95%, policy/drift 99%, policy/standing_facts 95%, audit/standing_sentences 97%, ui/standing_page 95%, sqlite_store 100%. Total 81% with postgres.py included; postgres.py is covered by the live tests below.
```
.venv/bin/python -m pytest tests/store_pg/test_store_contract.py -m live -q -p no:cacheprovider -k "standing or renewal or implements"
.....                                                                    [100%]
5 passed, 66 deselected in 20.27s
```
This ran against the Aiven service: the four standing-order store tests and the port check, in throwaway `tta_test_*` schemas.

The whole live PostgreSQL suite: `.venv/bin/python -m pytest tests/store_pg -m live -q -p no:cacheprovider`
```
FAILED tests/store_pg/test_postgres_store.py::test_the_store_works_only_in_its_own_schema
1 failed, 65 passed, 47 deselected, 1 error in 552.04s (0:09:12)
```
- **The failure:** that test pins the schema's table list, and my two new tables were not on it. I added `"standing_orders", "standing_renewals"` to the list in `tests/store_pg/test_postgres_store.py`. That folder is not on my list; this one line is the only change there. Re-run live: passed.
- **The error:** `test_reader_views.py::test_the_supplier_view_keeps_only_the_rules_tta_audit_lets_the_supplier_see`. The summary did not keep the traceback. Re-run live twice, alone and with the whole `test_reader_views.py` file: passed both times (`7 passed in 83.69s`). Its cause is not known; it looks like a one-off in the service, not in the code.

`ruff check` passes on every file I touched.

These neighbouring suites still pass (read-only check): `tests/api/test_sandbox_profile.py`, `test_openapi_and_schemas.py`, `test_flow.py`, `tests/ui/test_pages.py` (98 passed).

## Demo run, verified in replay (capture 2026-11-14-demo)
I loaded "Weekly lactose-free milk, hotel kitchen" (`so_demo_hotel_milk`). It starts with six synthetic weeks of 100, 96, 104, 100, 98 and 102 L of 469363 at €2.48, the capture's price; the median is 100 L.

- **Renewed at 100 L**: ORDERED, AUTO, no rule fired, €248.00.
  - Decision: "The agent may place this order alone: the total of €248.00 before tax is within the €750 limit per order, today's spend would be €248.00 of the €3,000 limit per day of profile hotel-kitchen, 100% of the requested quantity is covered, and no rule asks for a human."
  - Drift: "Standing order so_demo_hotel_milk is within the 25% tolerance: 100 L this week against a median of 100 L over the last 6 renewals and €2.48 per ST of 469363 this week against a median of €2.48 over the last 6 renewals. 6 renewals of the history are synthetic, made up for the demonstration: the Valio Aimo mock has no order history."
- **Renewed at 290 L** (€719.20, under the €750 limit, so it was AUTO before P-08): PENDING_APPROVAL, rule P-08, purchasing manager.
  - P-08: "For standing order so_demo_hotel_milk, 290 L this week against a median of 100 L over the last 6 renewals, more than the 25% tolerance of profile hotel-kitchen."
  - Decision: "The agent cannot place this order alone: for standing order so_demo_hotel_milk, 290 L … of profile hotel-kitchen (P-08). It needs the purchasing manager."
  - When the approver decides, the order is checked again and P-08 still holds; approval then gives ORDERED, placed with human approval.
- **Audit (buyer)**:
  - created: 'The agent set up standing order so_demo_hotel_milk, "Weekly lactose-free milk, hotel kitchen", renewed every 7 days: 100 litres of product 469363. It starts with 6 past renewals made up for the demonstration, marked synthetic: the Valio Aimo mock has no order history.'
  - renewed (100 L): '… as offer off_…. Standing order so_demo_hotel_milk is within the 25% tolerance: … Order ord_… was placed by the agent within its authority.'
  - renewed (290 L): '… Standing order so_demo_hotel_milk drifts beyond the 25% tolerance: 290 L this week against a median of 100 L over the last 6 renewals. 5 renewals of the history are synthetic, … Order ord_… waits for approval by the purchasing manager.'
- **Audit (supplier)**: "The buyer's agent set up a standing order." / "The buyer's agent renewed a standing order as offer off_…. Order ord_… is pending approval."

## Assumptions
- One tolerance per profile covers both quantity and unit price. "More than" is strict: exactly 25% passes.
- Quantity drift compares this renewal's requested quantity of a request line with the median of what past renewals ordered of that line, in its unit. Unit-price drift compares each product's net price per sales unit with the median over past renewals that carried that product.
- "That line's last N renewals" means the last 6 renewals that carry the line. A line with fewer than 3 is not compared and is listed under "not compared". When nothing at all can be compared, the history is too short to judge and P-08 does not fire.
- The median, not the mean, so one unusual week does not move what counts as usual.
- A renewal joins the history when its order exists, whether ORDERED or PENDING_APPROVAL. A renewal whose order was later REJECTED or EXPIRED is left out of the history.
- History is read in the order of `renewed_at`, ties in saved order. A real renewal is dated with its offer's `time_now`, the data clock.
- A profile without a tolerance: a renewal with enough history goes to a human for the missing fact (F-03); a request that renews nothing is unaffected. The custom "My kitchen" profile starts unset until change 5 above.
- The "history too short" statement is on the renewal's answer, the page and the "renewed" audit event, not on the `Offer`: `offers/` was SUST-1's, and re-saving an offer would contradict its recorded `offer.created` event.
- An unknown or another buyer's `standing_order_id` in a request is `invalid-request`. A path id on the standing-order routes is `not-found`, as for offers and orders.
- A renewal orders the top option through `place_order`, with the Idempotency-Key `standing:<offer_id>`. A `policy-blocked`, `offer-stale` or `offer-expired` reaches the caller as on `POST /v1/orders`, and nothing joins the history.
- The tolerance values (25% hotel, 10% ward) are ours and illustrative, like every profile value.
- The demo's synthetic quantities vary around 100 L; the task said "100 L a week". The median is still exactly 100 L.

## Contract changes needed
- `src/tta/contracts/audit.py`, `AuditEventType`: I added `STANDING_ORDER_CREATED` and `STANDING_ORDER_RENEWED`. The file is not on my list, but the task asks for these two events and event types can only be added there. Please keep them, or tell me to move them.
- `RenewalOutcome` and `StandingOrderDetail` live in `tta.standing.models`, not `tta.contracts`. Putting them in `contracts/standing.py` would make an import cycle, because `PolicyContext` imports that file and these two hold an `Offer` and an `Order`. If `/v1/schemas` should list them, add them and the `contracts/standing.py` models to `contracts/schemas.py`.
- Optional: the offer builder could add the drift report's sentence to `Offer.notes` when `request.standing_order_id` is set (`tta.policy.drift.assess_drift`). The offer itself would then also say "too short to judge".

## Not done
- `Offer.notes` does not carry the "too short" statement (see above); offers/ was not mine.
- No MCP tools for standing orders (not asked).
- `src/tta/policy/facts.py` is now 427 lines, over the 400-line rule, after MENU-1's F-09 block (about 35 lines). My change there is 8 lines shorter than before, because `Missing` moved to `reading.py`.
- TDD order: I wrote the policy, store, audit and kitchen tests first and watched them fail. The standing service, REST and page tests came after the code, and passed on their first run apart from expectation fixes.

## Questions written
2, in `AIMO/build/questions/STAND-1.md`: one for Valio (is a customer's order history readable in production?) and one for the team (the tolerance values, and whether price needs its own tolerance).
