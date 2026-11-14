"""The menu page: say the dish in a sentence or choose dishes and servings, enter the kitchen's stock and the date,
plan; then the plan per dish and ingredient, the final offer's options with their verdicts and who confirms, and
an order button (task MENU-1; the sentence box, task CK).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" and the 15% exceptions:
an ingredient that cannot arrive in time is replaced through the recipe's logic, and the page says what stands
in for what and why. Ordering is the normal flow: `place_order` on the final offer, within the agent's authority
or to a human. Everything is read from and written to the browser session's own order book.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import FastAPI, Form
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from tta.contracts.common import AllergenStrictness, Identity, Unit
from tta.contracts.errors import TtaError
from tta.contracts.menu import RECIPES_NOTE, IngredientStatus, MenuPlan, Recipe
from tta.contracts.offer import Offer
from tta.menus import shipped_recipes
from tta.menus.sentence import MenuAsk, plan_from_ask
from tta.ui import security
from tta.ui.run import Problem
from tta.ui.run import order_key as idempotency_key
from tta.ui.site import RECORD_ID, UNPROCESSABLE, Site, page_error

TEMPLATE = "menu.html"
MENU_PATH, PLAN_PATH, ORDER_PATH = "/menu", "/menu/plan", "/menu/order"
SERVINGS, STOCK = "servings__", "stock__"
SEE_OTHER = 303
# The demo case of the hand-back: a booking on Saturday night for a dinner on Monday, confirmed stock only.
BAKERY_AGENT = "agent:bakery-cafe"
CAKE_SENTENCE = "I want to make a chocolate cake for 20 people by Monday"
EXAMPLES: Mapping[str, Mapping[str, str]] = {
    # Task CK: the bakery asks in a sentence. `who` chooses the bakery's agent for the example.
    "cake": {"who": BAKERY_AGENT, "text": CAKE_SENTENCE},
    "event": {
        f"{SERVINGS}beef_stew": "120", f"{SERVINGS}berry_quark_dessert": "120", f"{STOCK}butter": "3",
        f"{STOCK}sugar": "2", "needed_by": "2026-11-16", "require_confirmed": "yes",
    },
}
STATUS_MARKS: Mapping[IngredientStatus, tuple[str, str]] = {
    IngredientStatus.IN_STOCK: ("ok", "In stock"),
    IngredientStatus.ORDERED_AS_IN_RECIPE: ("ok", "Ordered as in the recipe"),
    IngredientStatus.STANDS_IN: ("warn", "Stands in"),
    IngredientStatus.CANNOT_BE_SOURCED: ("bad", "Cannot be sourced"),
}
NOT_A_DEMO_AGENT = "Choose who is asking: one of the demo agents."
MAX_SENTENCE = 500  # as `tta.agent.dishes.MAX_TEXT`
NOT_SERVINGS = "Servings are a whole number, 0 to leave a dish out: '{value}' for {dish} is not."
NOT_STOCK = "The stock of {product_type} is a number of {unit}, 0 or more: '{value}' is not."
NOT_A_DATE = "The date is written as on the date field, for example 2026-11-16: '{value}' is not."
NOT_VALID = "The menu cannot be planned: {why}"
NO_SUCH_OPTION = ("No such option", "Choose one of the options of the plan's offer.")


@dataclass(frozen=True)
class StockField:
    product_type: str
    unit: Unit


@dataclass(frozen=True)
class PlanView:
    """A plan as the page shows it, with its final offer read as the agent that asked."""

    plan: MenuPlan
    offer: Offer | None
    asker: Identity
    order_key: str
    # Who confirms each option, by option id: the buyer's people who hold a role the decision asks for.
    confirmers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class MenuForm:
    """What the form sent, kept as typed so that a refusal shows it again."""

    who: str = ""
    values: Mapping[str, str] = field(default_factory=dict)

    def get(self, name: str) -> str:
        return self.values.get(name, "").strip()


class FormProblem(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.problem = Problem(title="The menu was not planned", detail=detail, status=UNPROCESSABLE)


def _stock_fields(recipes: Mapping[str, Recipe]) -> tuple[StockField, ...]:
    """Every product type a recipe asks for, with its unit, in alphabetical order."""
    ingredients = (ingredient for recipe in recipes.values() for ingredient in recipe.ingredients)
    units = {ingredient.product_type: ingredient.unit for ingredient in ingredients}
    return tuple(StockField(kind, units[kind]) for kind in sorted(units))


def _servings(form: MenuForm, recipes: Mapping[str, Recipe]) -> list[dict[str, Any]]:
    dishes = []
    for dish_id, recipe in recipes.items():
        value = form.get(SERVINGS + dish_id)
        if value in ("", "0"):
            continue
        if not value.isdigit():
            raise FormProblem(NOT_SERVINGS.format(value=value[:20], dish=recipe.name))
        dishes.append({"dish_id": dish_id, "servings": int(value)})
    return dishes  # may be empty: the sentence then names the dishes, or the gateway says none was named


def _stock(form: MenuForm, recipes: Mapping[str, Recipe]) -> list[dict[str, Any]]:
    stock = []
    for entry in _stock_fields(recipes):
        value = form.get(STOCK + entry.product_type)
        if value in ("", "0"):
            continue
        try:
            quantity = Decimal(value)
        except InvalidOperation:
            quantity = Decimal(-1)
        if not quantity.is_finite() or quantity < 0:
            words = entry.product_type.replace("_", " ")
            raise FormProblem(NOT_STOCK.format(product_type=words, unit=entry.unit.value, value=value[:20]))
        stock.append({"product_type": entry.product_type, "quantity": quantity, "unit": entry.unit})
    return stock


def _needed_by(form: MenuForm) -> date | None:
    value = form.get("needed_by")
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise FormProblem(NOT_A_DATE.format(value=value[:20])) from error


def _read(site: Site, form: MenuForm, recipes: Mapping[str, Recipe]) -> tuple[Identity, MenuAsk]:
    asker = site.agent(form.who)
    if asker is None:
        raise FormProblem(NOT_A_DEMO_AGENT)
    strictness = form.get("allergen_strictness")
    body = {
        "text": form.get("text")[:MAX_SENTENCE] or None, "dishes": _servings(form, recipes),
        "stock": _stock(form, recipes), "needed_by": _needed_by(form),
        "require_confirmed": form.get("require_confirmed") == "yes",
        "exclude_allergens": [code.upper() for code in form.get("exclude_allergens").replace(",", " ").split()],
        "allergen_strictness": AllergenStrictness(strictness) if strictness in AllergenStrictness else None,
    }
    try:
        return asker, MenuAsk.model_validate(body)
    except ValidationError as error:
        raise FormProblem(NOT_VALID.format(why=error.errors()[0]["msg"])) from error


def _plan(site: Site, request: Request, asker: Identity, menu: MenuAsk, recipes: Mapping[str, Recipe]) -> PlanView:
    """Raises `InvalidRequest` when neither the sentence nor the form names a dish, or the sentence leaves a
    question open: the page shows the question."""
    service = site.own_book(request).service
    plan = plan_from_ask(service, asker, menu, recipes, site.settings)
    offer = service.get_offer(asker, plan.offer_id) if plan.offer_id is not None else None
    return PlanView(
        plan=plan, offer=offer, asker=asker, order_key=security.new_token(), confirmers=_confirmers(site, offer),
    )


def _confirmers(site: Site, offer: Offer | None) -> dict[str, tuple[str, ...]]:
    """The demo people of the offer's buyer who hold a role an option's decision asks for, by option id."""
    if offer is None:
        return {}
    return {
        option.option_id: tuple(dict.fromkeys(
            holder.display_name for holder in site.holders(offer.profile_id, option.decision.required_roles)
        ))
        for option in offer.options if option.decision is not None
    }


def _page(
    site: Site, request: Request, recipes: Mapping[str, Recipe], form: MenuForm, *, view: PlanView | None = None,
    problem: Problem | None = None,
) -> HTMLResponse:
    status = problem.status if problem is not None else 200
    return site.render(
        request, TEMPLATE, status=status, agents=site.agents, asker=site.agent(form.who) or site.chosen_agent(request),
        recipes=tuple(recipes.values()), stock_fields=_stock_fields(recipes), form=form, view=view, problem=problem,
        status_marks=STATUS_MARKS, recipes_note=RECIPES_NOTE, servings_prefix=SERVINGS, stock_prefix=STOCK,
    )


def _order(site: Site, request: Request, who: str, offer: str, option: str, key: str) -> Response:
    asker = site.agent(who)
    if asker is None or not RECORD_ID.fullmatch(offer) or not RECORD_ID.fullmatch(key):
        raise page_error(UNPROCESSABLE, *NO_SUCH_OPTION)
    if not option.startswith("opt_") or not option[4:].isdigit():
        raise page_error(UNPROCESSABLE, *NO_SUCH_OPTION)
    placed = site.own_book(request).service.place_order(asker, offer, option, idempotency_key(key))
    return RedirectResponse(f"/orders/{placed.order_id}", status_code=SEE_OTHER)


def add_routes(app: FastAPI, site: Site, recipes: Mapping[str, Recipe] | None = None) -> None:
    """The menu page over the shipped recipes, or over `recipes`. Raises `RecipeLoadError` for a broken table."""
    table = recipes if recipes is not None else shipped_recipes()

    @app.get(MENU_PATH, response_class=HTMLResponse)
    def menu(request: Request, example: str = "") -> HTMLResponse:
        filled = EXAMPLES.get(example, {})
        who = filled.get("who") or site.chosen_agent(request).id
        return _page(site, request, table, MenuForm(who=who, values=filled))

    @app.post(PLAN_PATH, response_class=HTMLResponse)
    async def plan(request: Request) -> Response:
        sent = {key: value for key, value in (await request.form()).items() if isinstance(value, str)}
        site.check_form(request, sent.get("csrf", ""))
        form = MenuForm(who=sent.get("who", ""), values=sent)
        try:
            asker, menu_request = _read(site, form, table)
            view = await run_in_threadpool(_plan, site, request, asker, menu_request, table)
        except FormProblem as refused:
            return _page(site, request, table, form, problem=refused.problem)
        except TtaError as error:
            return _page(site, request, table, form, problem=Problem.of(error))
        response = _page(site, request, table, form, view=view)
        security.set_session_cookie(response, request, security.AGENT_COOKIE, asker.id)
        return response

    @app.post(ORDER_PATH, response_class=HTMLResponse)
    def order(
        request: Request,
        csrf: Annotated[str, Form()] = "",
        who: Annotated[str, Form()] = "",
        offer: Annotated[str, Form()] = "",
        option: Annotated[str, Form()] = "",
        order_key: Annotated[str, Form()] = "",
    ) -> Response:
        site.check_form(request, csrf)
        return _order(site, request, who, offer, option, order_key)
