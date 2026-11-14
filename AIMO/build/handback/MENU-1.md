# MENU-1 — partly done

The planner, recipes, contract, REST routes, page and rule F-09 are built and tested. One gap is outside my files: **F-09 cannot fire in the running system yet.** `OfferLine` does not carry `stands_in_for`, and the policy engine sees only the offer option, never the request. The contract change below closes the gap. Until it lands, the demo offer's verdict is APPROVAL because of P-06 alone, and F-09 is not shown. With the change, F-09 fires: I checked this on the real demo offer (sentence below).

## Built
- `src/tta/contracts/menu.py` (new): `MenuRequest` (dishes and servings, kitchen stock per product type, `needed_by`, exclusions and strictness, `require_confirmed`). `MenuPlan` (per dish and ingredient: needed, in stock, to order, the status, the type used, the alternative's reason, the request line; lines; what cannot be sourced and why; `offer_id`; every offer asked). The recipe shapes `Choice`, `Alternative`, `Ingredient`, `Recipe` and `RecipeBook`.
- `src/tta/menus/recipes.yaml` (new): 9 dishes. Beef stew, creamy chicken pasta, salmon with rice, oven pancake, macaroni casserole, rice porridge, lasagne, a vegetarian cheese omelette, berry quark dessert. Each ingredient has an amount per serving, a role, optional name terms (`maitorahka`, `whipping`, `natural`, `grated`…) and ordered alternatives, each with a one-line reason. The header says the table is ours and illustrative.
- `src/tta/menus/recipes.py`: loads and checks the table (known product types, one unit per type, alternatives are other types, no duplicate ingredient), plus `shipped_recipes()`.
- `src/tta/menus/needs.py`: dishes × servings, minus stock (dish by dish in menu order), summed per product type plus name terms, rounded up to whole L/kg (at least 1). Builds the `PurchaseRequest` (date, exclusions, confirmed-only, `stands_in_for`).
- `src/tta/menus/planner.py`: `plan_menu(service, identity, menu, recipes)`. Agents only. Asks for at most 3 offers through `GatewayService.create_offer`: the recipe's types; then the alternatives of each line whose top option covers less than the profile's `min_fill_ratio` (best alternative first for every ingredient, at most 5 lines); then the final offer.
- `src/tta/menus/plan.py`, `src/tta/menus/wording.py`: build the plan and its sentences (why each line failed, counted by exclusion reason, delivery-time reasons first).
- `src/tta/api/menu_routes.py` (new): `menu_router()` → `GET /v1/menus/recipes` (`list_recipes`) and `POST /v1/menus/plan` (`plan_menu`). Same `Caller`, problems and limits as `api/routes.py`; each offer of a plan counts against the rate limit.
- `src/tta/ui/menu_page.py` and `templates/menu.html` (new): `/menu` (with `?example=event`), `POST /menu/plan` and `POST /menu/order`.
  - The page shows the plan per dish and ingredient (stand-ins and "cannot arrive in time" marked), the request lines, and the final offer's options with verdicts and rules.
  - The order button calls the normal `place_order` with a per-render idempotency key, then redirects to `/orders/{id}`.
  - `add_routes(app, site)` is exported.
- Rule **F-09** (`rules.yaml`: the F-09 block and the fact `line.stands_in_for`): fixed, line scope, APPROVAL, purchasing manager. The condition is `ne ""`, because `not_empty` only reads lists.
- `src/tta/policy/facts.py`: `_stands_in_for` and its `LINE_FACTS` entry. The fact reads like "yoghurt in place of the recipe's quark, whose role is …". It takes the line's own type from the option's PRODUCT_TYPE check and neutralises every part with `plain_name`. A line that stands in for nothing reads "", which is never a missing fact. The reader uses `getattr` for `stands_in_for` and `stands_in_role` until `OfferLine` has those fields; a comment says so.
- `src/tta/policy/validation.py`: **one line outside my listed files.** F-09 is pinned in `FIXED_RULES`, because a fixed rule is not fixed without that pin. STAND-1 does not touch that mapping.
- Tests:
  - `tests/menus/` (new): `conftest.py`, `test_recipes.py`, `test_needs.py`, `test_planner.py`, `test_routes.py`, `test_menu_page.py`.
  - `tests/policy/test_stands_in_for.py` (new).
  - The lists of fixed rules are updated in `test_rulebook.py`, `test_authority.py`, `test_profiles.py` (`FIXED_IDS`) and `test_names.py` (F-09 names a product).
- `product_types.yaml`: not touched (see Not done).

## Tests
```
COVERAGE_FILE=<scratch> .venv/bin/python -m pytest tests/menus tests/policy tests/catalog -q -p no:cacheprovider --cov=tta.menus --cov=tta.api.menu_routes --cov=tta.ui.menu_page --cov=tta.contracts.menu --cov-report=term-missing
src/tta/api/menu_routes.py      29      0      0      0   100%
src/tta/contracts/menu.py      115      0      6      0   100%
src/tta/menus/__init__.py        3      0      0      0   100%
src/tta/menus/needs.py          97      1     20      1    98%   48
src/tta/menus/plan.py          130      5     30      4    94%   43, 68, 78-79, 123
src/tta/menus/planner.py        75      1     24      2    97%   77, 112->115
src/tta/menus/recipes.py        77      0     34      0   100%
src/tta/menus/wording.py        40      1      6      1    96%   86
src/tta/ui/menu_page.py        143      6     22      2    95%   122-123, 154-155, 180, 182
TOTAL                          709     14    142     10    97%
650 passed in 16.28s
.venv/bin/ruff check <every file touched>
All checks passed!
```
As a read-only check that F-09 breaks nothing next door, I also ran `tests/api tests/ui tests/e2e tests/audit tests/orders`: `964 passed, 1 xfailed`. The xfail is SUST-1/STAND-1's.

Test order: I wrote the F-09 tests first and watched them fail. The route and page tests came before their modules. The planner and needs tests came after the planner code (time), and passed on the first run.

### The demo case, run in replay (capture `2026-11-14-demo`, profile `hotel-kitchen`)
**The request.** "Last-minute event": a booking on Saturday night for a dinner on Monday.
- Beef stew, 120 servings, and berry quark dessert (marjarahka), 120 servings.
- Kitchen stock: butter 3 kg, sugar 2 kg.
- Needed by 2026-11-16, confirmed only.

**The plan, per ingredient**
| Dish | Ingredient | Needed | In stock | To order | What happens |
|---|---|---|---|---|---|
| Beef stew | beef chuck | 21.6 kg | 0 | 21.6 kg | ordered as in the recipe, line 1 |
| Beef stew | cream | 3.6 L | 0 | 3.6 L | ordered as in the recipe, line 2 |
| Beef stew | butter | 1.2 kg | 1.2 kg | 0 | in stock |
| Berry quark dessert | quark (maitorahka) | 12 kg | 0 | 12 kg | **stands in** as yoghurt (natural), line 4 |
| Berry quark dessert | cream (whipping) | 3.6 L | 0 | 3.6 L | ordered as in the recipe, line 3 |
| Berry quark dessert | sugar | 1.2 kg | 1.2 kg | 0 | in stock |

The quark line's sentence: "Yoghurt (natural) stands in for quark (maitorahka), the thick, tangy base of the dessert. Quark (maitorahka): none of 10 products can be offered by Mon 16 Nov 2026 (6 order cut-off passed, 4 quantity not confirmed (confirmed data only was asked for)). A thick natural yoghurt gives the same tangy base; the dessert is runnier and has less protein."

**The offers (3)**
1. The recipe's types. Coverage of its top option: chuck 1, cream 1, quark 0, whipping cream 1.
2. Yoghurt (natural), 12 kg. Coverage 1.
3. The final offer, with 4 lines. Line 4: "12 kg yoghurt (natural) for Berry quark dessert (marjarahka) (120 servings), in place of quark (maitorahka): the thick, tangy base of the dessert", with `stands_in_for: quark`.

**The final offer's option 1 (BEST_CONFIRMED, all lines CONFIRMED):** €476.48 net, €540.81 gross.
| Line | Product | Quantity | Net |
|---|---|---|---|
| 1 | 466988 Well Beef Beef Chuck roll n 3 kg | 24 kg | €405.12 |
| 2 | 463797 Arla Pro Cooking cream 10% | 4 | €13.24 |
| 3 | 469346 Arla Pro Whipping cream | 4 | €23.08 |
| 4 | 464615 Valio A+ greek natural yoghurt 1 kg | 12 | €35.04 |

**The verdict today:** APPROVAL, P-06 only: "…Well Beef Beef Chuck roll n 3 kg (466988) is sold by variable weight… (P-06). It needs the purchasing manager." Placing the order gives PENDING_APPROVAL.

**F-09's sentence**, from the same offer with line 4 carrying the requested fields (`stands_in_for` = quark, `stands_in_role`):
"The agent cannot place this order alone: Valio A+™ greek natural yoghurt 1 kg lactose free (464615) stands in for an ingredient of a recipe: yoghurt in place of the recipe's quark, whose role is the thick, tangy base of the dessert, so a person checks that the dish still works (F-09) and Well Beef Beef Chuck roll n 3 kg (466988) is sold by variable weight, so its final price is not fixed in advance (P-06). It needs the purchasing manager."

**How close this is to "cannot arrive in time":** in this capture, no recipe ingredient has all its products past the cut-off. Quark is the closest real case: 6 of the 10 products cannot arrive by Monday, and the other 4 have no confirmed stock. So the case needs "confirmed only", a fair setting for an event on Monday. Without it, the top option is the unconfirmed quark, which F-01 sends to a human, and no stand-in is tried.

A second real case is in the tests: 3,000 servings of creamy chicken pasta need 240 L of cream. Only about 199 L of confirmed cream can arrive by Monday (83%, below the 90% minimum), so vegetable cream (500 L confirmed) stands in.

## Assumptions
- Recipes and amounts are ours and illustrative, and the file, the API (`RecipeBook.note`, `MenuPlan.illustrative`) and the page say so.
- No vegetables, fruit, berries or herbs. The product-type table has none, so dishes list them under `left_out`. I did not check the catalog for vegetable categories.
- A line "cannot be covered" when its top option covers less than the profile's `min_fill_ratio`, or when there is no option (a share of 0). A late product is already excluded by the offer.
- An alternative replaces the whole of a failed ingredient's to-order amount, not only what is missing.
- A failed line that no alternative fixes stays in the final offer when its primary covered more than 0 (P-03 then asks a human). At 0 it leaves the final offer and appears under "cannot be sourced", so the rest can be ordered.
- Kitchen stock is per product type, in the recipes' unit for it. It goes to dishes in menu order and to the recipe's own type only, never to an alternative's. Stock given for a type no dish uses is noted.
- The menu's exclusions and strictness go onto every request line. The planner never removes a profile exclusion.
- The second offer holds at most 5 lines (`MAX_PROBE_LINES`, matching the demo gateway's `MAX_DEMO_REQUEST_LINES`). A menu whose first or final offer needs more than 5 lines gets the gateway's `invalid-request` ("at most 5 lines"), shown on the page.
- A demo plan uses up to 3 of the caller's 20 lookups per 60 seconds.
- A request line's `text` is written by the planner: the quantity, the type, the dishes and, for a stand-in, what it replaces and its role.
- Two lines of the same type with different name terms stay separate (cooking cream for the stew, whipping cream for the dessert).
- The alternatives of one ingredient must be other product types, so F-09 always names two different types. That is why salmon has no trout alternative.

## Contract changes needed
1. **`OfferLine.stands_in_for: str | None = None`** (`contracts/offer.py`). The recipe's product type this line replaces, copied from its request line. Without it, F-09 can never fire: the policy reads only the option, and the request is not in it.
2. **`OfferLine.stands_in_role: str | None = None`** and **`RequestLine.stands_in_role: str | None = Field(default=None, max_length=200)`**, "the job the recipe's ingredient does in the dish, set by the menu planner with stands_in_for". Needed for F-09's sentence to name the role, as the task asks. Without it, F-09 still fires and names both types.
3. Plumbing in `offers/`:
   - Add `stands_in_for` and `stands_in_role` to `Need` (`offers/candidates.py`).
   - Set both in `need_for` from `line`.
   - Pass both in `offers/lines.py::line_for` (`stands_in_for=need.stands_in_for, stands_in_role=need.stands_in_role`).
   - In `offers/substitutes.py:111`, leave both `None`.
4. After 2: in `src/tta/menus/needs.py::purchase_request`, add `stands_in_role="; ".join(dict.fromkeys(use.ingredient.role for use in need.uses)) if need.stands_in_for else None`. Once 1 is in, `getattr` in `policy/facts.py::_stand_in_field` may become plain attribute access.
5. After 1, `test_planner.py::test_the_final_offer_holds_every_line_confirmed_and_the_stand_in_goes_to_a_human` flips to expect F-09 on its own. The `RecipeLine` subclasses in `test_stands_in_for.py` and `test_names.py` become redundant but harmless.

## For the orchestrator to add
- `src/tta/api/app.py::_application`: `from tta.api.menu_routes import TAG_MENUS, menu_router`, and `app.include_router(menu_router())` right after `app.include_router(router)`. Optionally add `{"name": TAG_MENUS, "description": "Optional direction of the brief: substitutions through recipe logic"}` to `docs.TAGS`.
- `src/tta/ui/routes.py::create_surface`: `from tta.ui import menu_page`, then `menu_page.add_routes(app, site)` after `kitchen_page.add_routes(app, site)`.
- `templates/base.html` nav: `<a href="/menu"{% if path == "/menu" %} aria-current="page"{% endif %}>Menu</a>`.
- The page needs nothing from the sandboxes beyond what `Site` already gives.
- Optional:
  - In `rules.yaml` `authority.summary`, extend the "Always to a human" sentence with "a product type that recipe logic chose in place of a recipe's own ingredient". I left the shared line alone.
  - Add F-09 to `FIXED_SHOWN` in `tests/ui/test_kitchen_page.py` (STAND-1's).
  - Styles for `.menu-plan` and `.menu-form` in `static/app.css`. I added none; the page uses existing classes otherwise.
  - An MCP tool `plan_menu` over the same function.

## Not done
- **F-09 in the running flow:** waits for contract change 1 and its plumbing in `offers/`, which are not mine.
- **Vegetables:** not added to `product_types.yaml`. That needs a catalog count and category check plus test changes; the table test pins 20–31 entries and the table has 31. Dishes say what they leave out instead.
- No MCP tool, no CSS, no docs page.

## Questions written
1, `AIMO/build/questions/MENU-1.md` (for Valio: is there any data on which products do the same job in a dish).
