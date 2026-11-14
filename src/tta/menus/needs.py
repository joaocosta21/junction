"""From dishes and servings to request lines: expand, take the kitchen's stock off, add up, round up (task MENU-1).

A `Use` is one ingredient of one dish. A `Need` is one request line: the uses bought as one product type, the
recipe's own or an alternative that does the same job. Stock is taken off per product type, dish by dish in menu
order; what is left is ordered, rounded up to whole litres or kilograms.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from tta.contracts.errors import InvalidRequest
from tta.contracts.menu import MenuRequest
from tta.contracts.request import MAX_ROLE_LENGTH, MAX_TEXT_LENGTH, PurchaseRequest, RequestLine
from tta.menus.recipes import Choice, Ingredient, Recipe, unit_of
from tta.menus.wording import amount_words, choice_words, dish_words

ZERO = Decimal(0)
WHOLE = Decimal(1)
UNKNOWN_DISH = "No recipe has the id '{dish_id}'. GET /v1/menus/recipes lists the dishes."
WRONG_STOCK_UNIT = "The recipes use {unit} for {product_type}, so its stock must be given in {unit}, not {given}."


@dataclass(frozen=True)
class Use:
    """One ingredient of one dish, with the part of it the kitchen's stock covers."""

    recipe: Recipe
    servings: int
    ingredient: Ingredient
    needed: Decimal
    in_stock: Decimal

    @property
    def use_id(self) -> tuple[str, str, tuple[str, ...]]:
        """A dish lists an ingredient once (`tta.menus.recipes`), so this names one use."""
        return self.recipe.dish_id, self.ingredient.product_type, self.ingredient.name_terms

    @property
    def to_order(self) -> Decimal:
        return self.needed - self.in_stock

    def amount_as(self, choice: Choice) -> Decimal:
        """What this use needs when bought as `choice`: its amount per serving, for the part not in stock."""
        if self.needed == ZERO:
            return ZERO
        return choice.per_serving * self.servings * self.to_order / self.needed


@dataclass(frozen=True)
class Need:
    """One request line: uses bought as one product type, each with the choice (and so the amount per serving) it
    is bought as. `stands_in_for` is the recipe's product type when the choice is an alternative."""

    choice: Choice
    parts: tuple[tuple[Use, Choice], ...]
    stands_in_for: str | None = None

    @property
    def uses(self) -> tuple[Use, ...]:
        return tuple(use for use, _ in self.parts)

    @property
    def amount(self) -> Decimal:
        return sum((use.amount_as(choice) for use, choice in self.parts), ZERO)

    @property
    def quantity(self) -> Decimal:
        """Rounded up to whole litres or kilograms, and at least one."""
        return max(self.amount.to_integral_value(rounding=ROUND_CEILING), WHOLE)

    @property
    def key(self) -> tuple[str, tuple[str, ...], str | None]:
        return self.choice.product_type, self.choice.name_terms, self.stands_in_for


def _recipe(recipes: Mapping[str, Recipe], dish_id: str) -> Recipe:
    recipe = recipes.get(dish_id)
    if recipe is None:
        raise InvalidRequest(UNKNOWN_DISH.format(dish_id=dish_id))
    return recipe


def _stock(request: MenuRequest, recipes: Mapping[str, Recipe]) -> dict[str, Decimal]:
    """The kitchen's stock by product type. Raises `InvalidRequest` for a unit the recipes do not use."""
    stock: dict[str, Decimal] = {}
    for entry in request.stock:
        unit = unit_of(recipes, entry.product_type)
        if unit is not None and unit is not entry.unit:
            raise InvalidRequest(WRONG_STOCK_UNIT.format(
                unit=unit.value, product_type=entry.product_type, given=entry.unit.value
            ))
        stock[entry.product_type] = entry.quantity
    return stock


def expand(request: MenuRequest, recipes: Mapping[str, Recipe]) -> tuple[Use, ...]:
    """Every ingredient of every dish, in menu order, with the stock taken off dish by dish."""
    left = _stock(request, recipes)
    uses: list[Use] = []
    for dish in request.dishes:
        recipe = _recipe(recipes, dish.dish_id)
        for ingredient in recipe.ingredients:
            needed = ingredient.per_serving * dish.servings
            taken = min(left.get(ingredient.product_type, ZERO), needed)
            left[ingredient.product_type] = left.get(ingredient.product_type, ZERO) - taken
            uses.append(Use(recipe, dish.servings, ingredient, needed, taken))
    return tuple(uses)


def group(uses: Iterable[Use], choose: Callable[[Use], tuple[Choice, str | None]]) -> tuple[Need, ...]:
    """The uses that still need ordering, one need per choice, in the order they first appear."""
    grouped: dict[tuple[str, tuple[str, ...], str | None], Need] = {}
    for use in uses:
        if use.to_order <= ZERO:
            continue
        choice, stands_in_for = choose(use)
        key = (choice.product_type, choice.name_terms, stands_in_for)
        grouped[key] = add_to(grouped.get(key), use, choice, stands_in_for)
    return tuple(grouped.values())


def add_to(need: Need | None, use: Use, choice: Choice, stands_in_for: str | None) -> Need:
    """A new need with one more use; a new need of one use when there is none yet."""
    if need is None:
        return Need(choice, ((use, choice),), stands_in_for)
    return Need(need.choice, (*need.parts, (use, choice)), need.stands_in_for)


def as_recipe(use: Use) -> tuple[Choice, str | None]:
    """A use bought as the recipe asks."""
    return use.ingredient, None


def _text(need: Need) -> str:
    dishes = dish_words(need.uses)
    bought = f"{amount_words(need.quantity, need.choice.unit)} {choice_words(need.choice)} for {dishes}"
    if need.stands_in_for is None:
        return bought[:MAX_TEXT_LENGTH]
    ingredient = need.uses[0].ingredient
    roles = "; ".join(dict.fromkeys(use.ingredient.role for use in need.uses))
    return f"{bought}, in place of {choice_words(ingredient)}: {roles}"[:MAX_TEXT_LENGTH]


def _role(need: Need) -> str | None:
    """The job of the recipe's ingredient, for rule F-09's sentence; None when the line stands in for nothing."""
    if need.stands_in_for is None:
        return None
    return "; ".join(dict.fromkeys(use.ingredient.role for use in need.uses))[:MAX_ROLE_LENGTH]


def purchase_request(request: MenuRequest, needs: Sequence[Need]) -> PurchaseRequest:
    """The typed request of these needs, with the menu's date, exclusions and confirmed-only setting."""
    lines = tuple(
        RequestLine(
            text=_text(need), product_type=need.choice.product_type, name_terms=need.choice.name_terms,
            quantity=need.quantity, unit=need.choice.unit, exclude_allergens=request.exclude_allergens,
            allergen_strictness=request.allergen_strictness, stands_in_for=need.stands_in_for,
            stands_in_role=_role(need),
        )
        for need in needs
    )
    return PurchaseRequest(needed_by=request.needed_by, require_confirmed=request.require_confirmed, lines=lines)
