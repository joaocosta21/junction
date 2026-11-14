"""The menu request and the menu plan: dishes and servings become one offer, with substitutions by an ingredient's
role in the dish (task MENU-1).

The recipes are ours and illustrative (`tta.menus`, `recipes.yaml`): Valio Aimo publishes none. The plan says per
dish and ingredient what is needed, what the kitchen holds, what is ordered, which product type stands in for
which and why, and what cannot be sourced in time. The order itself is the normal flow on the final offer.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from tta.contracts.common import AllergenStrictness, Contract, Quantity, Unit
from tta.contracts.request import MAX_ALLERGEN_CODES, MAX_QUANTITY, MAX_QUANTITY_DECIMALS, MAX_TERMS, Term

MAX_DISHES = 10
MAX_SERVINGS = 5000  # a large event; keeps every amount far below the contract's MAX_QUANTITY
MAX_STOCK_ENTRIES = 40
MAX_OFFERS_PER_PLAN = 3  # the first offer, one more for the replaced lines, the final offer
MAX_PER_SERVING = Decimal(5)  # kg or L for one serving: far above any real dish
MAX_TEXT = 200
ORDERABLE_UNITS = frozenset({Unit.L, Unit.KG})
RECIPES_NOTE = (
    "The recipes and their amounts per serving are ours and illustrative, not Valio Aimo's. The product-type table "
    "has no vegetables, fruit or herbs, so each dish lists those under left_out instead of ordering them."
)


# --- the recipe table (GET /v1/menus/recipes) ------------------------------------------------------------------

class Choice(Contract):
    """A product type an ingredient can be bought as, with the words its name must have."""

    product_type: Term
    name_terms: tuple[Term, ...] = Field(default=(), max_length=MAX_TERMS)
    per_serving: Quantity = Field(gt=0, le=MAX_PER_SERVING)
    unit: Unit

    @field_validator("unit")
    @classmethod
    def _orderable(cls, unit: Unit) -> Unit:
        if unit not in ORDERABLE_UNITS:
            raise ValueError("a recipe amount is in L or KG")
        return unit

    @property
    def key(self) -> tuple[str, tuple[str, ...]]:
        return self.product_type, self.name_terms


class Alternative(Choice):
    reason: str = Field(min_length=1, max_length=MAX_TEXT)


class Ingredient(Choice):
    role: str = Field(min_length=1, max_length=MAX_TEXT)
    alternatives: tuple[Alternative, ...] = ()


class Recipe(Contract):
    dish_id: str
    name: str = Field(min_length=1, max_length=MAX_TEXT)
    ingredients: tuple[Ingredient, ...] = Field(min_length=1)
    left_out: tuple[str, ...] = ()


class RecipeBook(Contract):
    """Answer of GET /v1/menus/recipes."""

    recipes: tuple[Recipe, ...]
    illustrative: bool = True
    note: str = RECIPES_NOTE


# --- the menu request and its plan (POST /v1/menus/plan) -------------------------------------------------------


class DishOrder(Contract):
    """One dish of the menu and how many servings of it the kitchen cooks."""

    dish_id: Term = Field(description="A key of GET /v1/menus/recipes")
    servings: int = Field(ge=1, le=MAX_SERVINGS)


class KitchenStock(Contract):
    """What the kitchen already holds of one product type, in the unit the recipes use for it."""

    product_type: Term
    quantity: Quantity = Field(ge=0, le=MAX_QUANTITY, decimal_places=MAX_QUANTITY_DECIMALS)
    unit: Unit


class MenuRequest(Contract):
    """Body of POST /v1/menus/plan."""

    dishes: tuple[DishOrder, ...] = Field(min_length=1, max_length=MAX_DISHES)
    stock: tuple[KitchenStock, ...] = Field(default=(), max_length=MAX_STOCK_ENTRIES)
    needed_by: date | None = Field(default=None, description="The date the goods are needed")
    exclude_allergens: tuple[Term, ...] = Field(
        default=(), max_length=MAX_ALLERGEN_CODES,
        description="GS1 codes excluded for every ingredient, added to the profile's exclusions",
    )
    allergen_strictness: AllergenStrictness | None = Field(
        default=None, description="Required when there is any exclusion and the profile sets none"
    )
    require_confirmed: bool = Field(
        default=False, description="Offer only products whose every claim is confirmed (stock, price, date)"
    )

    @model_validator(mode="after")
    def _each_once(self) -> MenuRequest:
        dishes = [dish.dish_id for dish in self.dishes]
        if len(set(dishes)) < len(dishes):
            raise ValueError("a dish is listed once, with all its servings")
        stocked = [entry.product_type for entry in self.stock]
        if len(set(stocked)) < len(stocked):
            raise ValueError("the stock of a product type is given once")
        return self


class IngredientStatus(StrEnum):
    IN_STOCK = "IN_STOCK"  # the kitchen holds all of it: nothing is ordered
    ORDERED_AS_IN_RECIPE = "ORDERED_AS_IN_RECIPE"  # the recipe's own product type is in the final offer
    STANDS_IN = "STANDS_IN"  # an alternative product type that does the same job is in the final offer
    CANNOT_BE_SOURCED = "CANNOT_BE_SOURCED"  # neither the recipe's type nor an alternative can be offered in time


class IngredientPlan(Contract):
    """One ingredient of one dish."""

    recipe_product_type: str  # what the recipe asks for
    role: str  # the job it does in the dish
    needed: Quantity  # servings x amount per serving, in `unit`
    in_stock: Quantity  # the part the kitchen's stock covers (stock goes to the dishes in menu order)
    to_order: Quantity  # needed minus in stock, before the line is rounded up to whole units
    unit: Unit
    status: IngredientStatus
    product_type: str | None = None  # the type ordered: the recipe's own or its alternative; None when nothing is
    alternative_reason: str | None = None  # why the alternative does the same job, and what changes
    request_line_index: int | None = Field(default=None, ge=0)  # its line in the final offer
    sentence: str  # one sentence a person can read


class DishPlan(Contract):
    dish_id: str
    name: str
    servings: int
    ingredients: tuple[IngredientPlan, ...]
    left_out: tuple[str, ...] = ()  # ingredients the recipe file leaves out, e.g. vegetables, with why


class LinePlan(Contract):
    """One request line of the final offer, or one the kitchen's stock made unnecessary."""

    product_type: str
    name_terms: tuple[str, ...] = ()  # words the product name must have, as on the request line
    unit: Unit
    needed: Quantity  # over every dish this line serves
    in_stock: Quantity
    to_order: Quantity  # rounded up to whole units of `unit`; 0 when the stock covers it
    dishes: tuple[str, ...]
    stands_in_for: str | None = None  # the recipe's product type this line replaces (rule F-09)
    request_line_index: int | None = Field(default=None, ge=0)  # None when nothing is ordered


class Unsourced(Contract):
    """An ingredient that neither its recipe's product type nor an alternative can supply in time."""

    product_type: str  # the recipe's product type
    unit: Unit
    quantity: Quantity  # what was to be ordered
    dishes: tuple[str, ...]
    tried: tuple[str, ...] = ()  # the alternative product types tried, in the role's order
    sentence: str  # why: what the offers found for the recipe's type and for each alternative


class MenuPlan(Contract):
    """Answer of POST /v1/menus/plan."""

    request: MenuRequest
    dishes: tuple[DishPlan, ...]
    lines: tuple[LinePlan, ...]
    cannot_be_sourced: tuple[Unsourced, ...] = ()
    offer_id: str | None = None  # the final offer; order one of its options with POST /v1/orders
    offers_asked: tuple[str, ...] = Field(default=(), max_length=MAX_OFFERS_PER_PLAN)  # every offer, in order
    illustrative: bool = True  # the recipes and their amounts are ours, not Valio Aimo's
    notes: tuple[str, ...] = ()
