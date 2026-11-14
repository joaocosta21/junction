"""The recipe table: dishes, their ingredients per serving, each ingredient's role and its alternatives (task MENU-1).

The table is ours and illustrative (`recipes.yaml`). It is checked when it is loaded: every product type must be
a key of the product-type table, a product type has one unit everywhere, and an alternative is another product
type with a reason. A table that fails a check does not load.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

import yaml
from pydantic import ValidationError

from tta.catalog.product_types import PRODUCT_TYPES_FILE, load_product_types
from tta.contracts.common import Unit
from tta.contracts.menu import Alternative, Choice, Ingredient, Recipe

RECIPES_PATH = Path(__file__).resolve().parent / "recipes.yaml"
__all__ = [
    "RECIPES_PATH", "Alternative", "Choice", "Ingredient", "Recipe", "RecipeLoadError", "load_recipes",
    "shipped_recipes", "unit_of",
]


class RecipeLoadError(ValueError):
    """The recipe table cannot be used. `problems` lists every reason."""

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems = tuple(problems)
        super().__init__("The recipe table cannot be loaded: " + "; ".join(self.problems))


def _alternative(raw: Mapping[str, object], ingredient: Mapping[str, object]) -> dict[str, object]:
    """An alternative takes the ingredient's amount and unit unless it gives its own."""
    return {"per_serving": ingredient.get("per_serving"), "unit": ingredient.get("unit"), **raw}


def _recipe(dish_id: str, raw: Mapping[str, object]) -> Recipe:
    ingredients = []
    for ingredient in raw.get("ingredients") or ():
        alternatives = [_alternative(each, ingredient) for each in ingredient.get("alternatives") or ()]
        ingredients.append({**ingredient, "alternatives": alternatives})
    return Recipe.model_validate({**raw, "dish_id": dish_id, "ingredients": ingredients})


def _parse(data: object) -> dict[str, Recipe]:
    if not isinstance(data, dict) or not isinstance(data.get("dishes"), dict) or not data["dishes"]:
        raise RecipeLoadError(["the file must hold a mapping `dishes` of at least one dish"])
    recipes: dict[str, Recipe] = {}
    problems: list[str] = []
    for dish_id, raw in data["dishes"].items():
        if not isinstance(raw, dict):
            problems.append(f"{dish_id}: a dish is a mapping")
            continue
        try:
            recipes[str(dish_id)] = _recipe(str(dish_id), raw)
        except (ValidationError, AttributeError, TypeError) as error:
            problems.append(f"{dish_id}: {error}")
    if problems:
        raise RecipeLoadError(problems)
    return recipes


def _check(recipes: Mapping[str, Recipe], known_types: Collection[str]) -> list[str]:
    problems: list[str] = []
    units: dict[str, Unit] = {}
    for recipe in recipes.values():
        for ingredient in recipe.ingredients:
            for choice in (ingredient, *ingredient.alternatives):
                if choice.product_type not in known_types:
                    problems.append(f"{recipe.dish_id}: '{choice.product_type}' is not a product type")
                unit = units.setdefault(choice.product_type, choice.unit)
                if unit is not choice.unit:
                    problems.append(f"{recipe.dish_id}: '{choice.product_type}' is in {unit.value} elsewhere")
            types = [alternative.product_type for alternative in ingredient.alternatives]
            if ingredient.product_type in types or len(set(types)) < len(types):
                problems.append(
                    f"{recipe.dish_id}: the alternatives of '{ingredient.product_type}' must be other product types"
                )
        if len({ingredient.key for ingredient in recipe.ingredients}) < len(recipe.ingredients):
            problems.append(f"{recipe.dish_id}: an ingredient is listed twice")
    return problems


def load_recipes(known_types: Collection[str], path: Path = RECIPES_PATH) -> Mapping[str, Recipe]:
    """The checked recipe table, by dish id. Raises `RecipeLoadError` listing every problem."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RecipeLoadError([f"{path.name} cannot be read: {type(error).__name__}"]) from error
    recipes = _parse(data)
    problems = _check(recipes, known_types)
    if problems:
        raise RecipeLoadError(problems)
    return MappingProxyType(recipes)


def unit_of(recipes: Mapping[str, Recipe], product_type: str) -> Unit | None:
    """The one unit the table uses for a product type; None when no recipe uses it."""
    for recipe in recipes.values():
        for ingredient in recipe.ingredients:
            for choice in (ingredient, *ingredient.alternatives):
                if choice.product_type == product_type:
                    return choice.unit
    return None


@lru_cache(maxsize=1)
def shipped_recipes() -> Mapping[str, Recipe]:
    """The shipped table, checked against the shipped product-type table. Raises `RecipeLoadError`."""
    return load_recipes(tuple(load_product_types(PRODUCT_TYPES_FILE)))
