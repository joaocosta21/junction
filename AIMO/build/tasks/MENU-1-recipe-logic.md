# MENU-1 — Recipe logic: a menu becomes an order, with substitutions by the ingredient's role

Scores on the 20% "how precisely the agent matches what the buyer actually asked for, with the least manual correction needed", the 15% robustness ("partial availability, substitutions and delivery constraints"), and three of Valio's example scenarios, verbatim:
- "Need → recipe → order: a chef plans next week's menu around a seasonal ingredient. The agent suggests recipes, works out what's missing from stock, and places the order."
- "Last-minute event: an unexpected booking for tomorrow. The agent identifies what the recipes require, flags what can't be sourced in time, and proposes substitutions through recipe logic rather than a simple SKU swap."
- "Supplier stock-out: a key product runs out mid-week. The agent proposes a recipe-compatible substitute before the kitchen notices the gap, and explains the trade-off."

Hand back by **15:30**. Other agents work at the same time on the delivery and sustainability comparison (SUST-1, in `offers/` and `catalog/`), standing orders (STAND-1, in `policy/` and `store/`) and a rule-based reader (FALLBACK-1, in `agent/`).

## What exists
- A typed multi-line `PurchaseRequest` already gives one offer, one order and one approval for several products (`AIMO/USE-CASES.md` §1: beef chuck + cream + milk → €319.20). Substitutes are found only for lines that name product ids (`offers/planning.py`); a product-type line never gets one.
- 31 product types in `src/tta/catalog/product_types.yaml` (dairy, meat, fish, chicken, rice, pasta, flour, eggs, bread, oils, drinks; **no vegetables**).
- Since `d4ad9b7`: `RequestLine.stands_in_for` ("The product type of a recipe this line replaces, set by the menu planner when recipe logic chose another ingredient (rule F-09: such a line goes to a human)"). Nothing reads it yet.
- The policy context, profiles and the "Your kitchen" page are STAND-1's this afternoon; the rule file is shared (see "Owns").

## Build
1. **Recipes, ours and labelled so:** `src/tta/menus/recipes.yaml`, about 8 dishes a hotel or school kitchen cooks (for example beef stew, creamy chicken pasta, salmon with rice, pancakes, macaroni cheese, rice porridge, lasagne, a vegetarian dish), each with servings-based amounts per ingredient (`product_type`, amount per serving, unit) and, per ingredient, its **role** in the dish and an ordered list of alternative product types that do the same job, each with a one-line reason ("a vegetable-fat cream thickens the sauce the same way; it is not dairy"). Amounts are illustrative: say so in the file and on the page. If a dish needs a product type that does not exist (vegetables), add it to `product_types.yaml` only after checking the catalog has such products (category and names), with its tests; otherwise leave the ingredient out and say so.
2. **Contract** `src/tta/contracts/menu.py` (new): a menu request (dishes with servings, kitchen stock per product type, needed-by date, allergen exclusions and strictness, `require_confirmed`), and a menu plan (per dish and ingredient: needed, in stock, to order; the product type used, primary or alternative with its reason; what cannot be sourced in time and why; the offer id).
3. **Planner** `src/tta/menus/` (new package):
   - expand dishes × servings, add up per product type, subtract kitchen stock, round up to the unit; one `RequestLine` per product type, its `text` naming the dishes it is for;
   - ask for one offer through `GatewayService.create_offer` (the caller's identity and profile, as any request);
   - for a line the top option cannot cover (nothing deliverable by the needed-by date, or a fill below the profile's minimum), try the role's next alternative product type; the replacement line carries `stands_in_for` = the recipe's own product type; at most one more offer for the replaced lines, then the final offer with all lines;
   - the plan says, per ingredient, what was found, what stands in for what and why, and what cannot be sourced in time; ordering is the normal `place_order` on the final offer (within authority or to a human).
4. **Rule F-09** in `src/tta/policy/rules.yaml`, **fixed**: a line with `stands_in_for` set goes to a human (purchasing manager), with a sentence naming both product types and the role. Its fact (`line.stands_in_for`) in `policy/facts.py` as the other line facts are. Update the tests that pin the list of fixed rules.
5. **REST** in a new module `src/tta/api/menu_routes.py` (an `APIRouter` under `/v1`): `GET /v1/menus/recipes`, `POST /v1/menus/plan`. Same identity, errors (RFC 9457) and rate limits as `api/routes.py` (import its dependencies; do not edit it). Export a function the orchestrator includes in `api/app.py`.
6. **Page** `src/tta/ui/menu_page.py` + `templates/menu.html`: choose dishes and servings, enter kitchen stock and the date, plan; show the plan per dish and ingredient (alternatives and what cannot arrive in time marked), the final offer's options with their verdicts, and an order button that uses the normal flow (as the request page does). Export `add_routes(app, site)` as the other page modules do; the orchestrator registers it and adds the menu link.
7. **The demo case:** a "last-minute event" that shows one ingredient replaced by its role because the primary cannot arrive in time in the capture `2026-11-14-demo`, verified in replay. Find a real one (for example a cream whose products are past their cut-off, or a protein); if none exists, say so and show the closest case.

## Owns (exception to AGENT-RULES rule 1: these contract files are yours for this task)
- `src/tta/contracts/menu.py` (new)
- `src/tta/menus/` (new), `src/tta/api/menu_routes.py` (new), `src/tta/ui/menu_page.py` (new), `src/tta/ui/templates/menu*.html` (new)
- `src/tta/catalog/product_types.yaml` (additions only) and its tests in `tests/catalog/test_product_types.py`
- In `src/tta/policy/rules.yaml` and `src/tta/policy/facts.py`: **only your F-09 block and the `line.stands_in_for` fact.** STAND-1 adds rule P-08 and its facts to the same files at the same time: re-read the file right before each edit, change only your own lines, never rewrite a whole file.
- tests: `tests/menus/` (new), and the policy tests that pin the fixed rules
- `AIMO/build/handback/MENU-1.md`, `AIMO/build/questions/MENU-1.md`

Not yours: `src/tta/offers/` (SUST-1), the rest of `src/tta/policy/` (STAND-1), `src/tta/agent/` (FALLBACK-1), `api/app.py`, `api/routes.py`, `api/wiring.py`, `api/sandbox.py`, `ui/routes.py`, `templates/base.html`, the MCP surface, docs. Say in the hand-back exactly what the orchestrator must add and where.

## Checks before hand-back
- `.venv/bin/python -m pytest tests/menus tests/policy tests/catalog -q -p no:cacheprovider` (set `COVERAGE_FILE` to a scratch path) all pass.
- `.venv/bin/ruff check` on every file you touched.
- In the hand-back: the demo case run in replay (dishes, servings, stock, the plan, the alternatives with their reasons, the offer totals and verdicts, F-09's sentence).
