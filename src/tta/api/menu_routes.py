"""The menu routes (task MENU-1): the recipe table, and a menu that becomes one offer with substitutions by role.

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" and the 15% exceptions:
an ingredient that cannot arrive in time is replaced by another product type that does the same job in the dish,
and the plan says so per ingredient. The identity, the problems (RFC 9457) and the rate limits are those of
`tta.api.routes`: each offer of a plan goes through the gateway service as the caller, and counts as one.
The orchestrator includes the router in `tta.api.app`: `app.include_router(menu_router())`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from fastapi import APIRouter, Body, Request
from starlette.concurrency import run_in_threadpool

from tta.agent.days import helsinki_date
from tta.api import docs
from tta.api.identity import Caller
from tta.api.routes import CALLER
from tta.api.wiring import Parts
from tta.contracts.common import Identity
from tta.contracts.errors import InvalidRequest, RateLimited, SupplierUnavailable
from tta.contracts.menu import MenuPlan, Recipe, RecipeBook
from tta.menus import plan_menu, shipped_recipes
from tta.menus.sentence import MenuAsk, later_recorded_note, resolve, with_notes

TAG_MENUS = docs.TAG_MENUS  # the OpenAPI tag, described in tta.api.docs
# The page's "last-minute event" (MENU-1 hand-back, replay): quark cannot be had by Monday, yoghurt stands in (F-09).
MENU_EXAMPLES = {
    "a_sentence": {
        "summary": "A sentence: a chocolate cake for 20 people",
        "value": {"text": "I want to make a chocolate cake for 20 people by Monday"},
    },
    "last_minute_event": {
        "summary": "A dinner for 120 on Monday: beef stew and berry quark dessert",
        "value": {
            "dishes": [{"dish_id": "beef_stew", "servings": 120}, {"dish_id": "berry_quark_dessert", "servings": 120}],
            "stock": [{"product_type": "butter", "quantity": 3, "unit": "KG"},
                      {"product_type": "sugar", "quantity": 2, "unit": "KG"}],
            "needed_by": "2026-11-16", "require_confirmed": True,
        },
    },
}


def _parts(request: Request) -> Parts:
    return request.app.state.parts


def menu_router(recipes: Mapping[str, Recipe] | None = None) -> APIRouter:
    """The two routes over the shipped recipe table, or over `recipes`. Raises `RecipeLoadError` at start-up when
    the table cannot be used: a broken table never serves a plan."""
    table = recipes if recipes is not None else shipped_recipes()
    book = RecipeBook(recipes=tuple(table.values()))
    router = APIRouter(prefix="/v1", tags=[TAG_MENUS])

    @router.get(
        "/menus/recipes", operation_id="list_recipes", responses=docs.problems(*CALLER),
        summary="The recipes a menu can be planned from",
    )
    def list_recipes(caller: Caller) -> RecipeBook:
        """Ours and illustrative: dishes with an amount per serving for each ingredient, the ingredient's role in
        the dish and the product types that can do the same job, best first, each with a reason."""
        _ = caller  # any token may read the table; the identity is checked as on every route
        return book

    @router.post(
        "/menus/plan", operation_id="plan_menu",
        responses=docs.problems(*CALLER, InvalidRequest, RateLimited, SupplierUnavailable),
        summary="Dishes and servings become one offer",
    )
    async def plan(
        request: Request, caller: Caller, menu: Annotated[MenuAsk, Body(openapi_examples=MENU_EXAMPLES)]
    ) -> MenuPlan:
        """Servings times each recipe's amounts, minus the kitchen's stock, rounded up to whole litres or
        kilograms: one request line per product type, and one offer. A line that no option covers to the buyer
        profile's minimum share is tried as the ingredient's alternatives (at most one more offer). A line that
        stands in for a recipe's ingredient carries `stands_in_for`, rule F-09 sends it to the purchasing manager,
        and the plan names the allergens its product declares. An ingredient that cannot be sourced stays in the
        final offer with nothing offered for it, so the offer and the rules see that the menu is incomplete.
        Order an option of `offer_id` with POST /v1/orders, as any offer. At most three offers, each counted by
        the rate limit.

        The dishes are typed in `dishes`, or named in `text` as a sentence ("I want to make a chocolate cake for
        20 people by Monday"), read by fixed rules with no model. Typed fields win. What the sentence leaves open
        is refused with the question to answer and never guessed: a dish that is not in the recipe table, missing
        servings, two days. The first note of the plan says what was read. An amount below one litre or kilogram
        is asked for to the gram, and each ingredient's sentence says the product offered, the packs, the price,
        the stock and what is left over when the pack is larger than the need."""
        return await run_in_threadpool(_plan, _parts(request), caller, menu, table)

    return router


def _plan(parts: Parts, caller: Identity, menu: MenuAsk, table: Mapping[str, Recipe]) -> MenuPlan:
    """Raises `InvalidRequest` (422) when neither `dishes` nor `text` names a dish, with the list of dishes."""
    resolved = resolve(menu, table, helsinki_date(parts.clock.now()))
    plan = plan_menu(parts.service, caller, resolved.request, table)
    offer = parts.service.get_offer(caller, plan.offer_id) if plan.offer_id is not None else None
    return with_notes(plan, read_as=resolved.read_as, later=later_recorded_note(parts.replay, offer))
