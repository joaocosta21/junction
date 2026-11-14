"""The recipe table: dishes, their ingredients per serving, each ingredient's role and its alternatives (task MENU-1).

The table is ours and illustrative (`recipes.yaml`). It is checked when it is loaded: every product type must be
a key of the product-type table, a product type has one unit everywhere, and an alternative is another product
type with a reason. A table that fails a check does not load.

`named_products` (task CK) names an ingredient the product-type table does not hold yet by the ids of the products
that are it. A recipe uses its key as a product type; the request line then names those products by id
(`product_ids_of`). A key the product-type table also holds is the table's: the list here is then ignored.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator, Mapping
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from tta.catalog.product_types import PRODUCT_TYPES_FILE, load_product_types
from tta.contracts.common import Unit
from tta.contracts.menu import Alternative, Choice, Ingredient, Recipe
from tta.contracts.request import MAX_PRODUCT_IDS

RECIPES_PATH = Path(__file__).resolve().parent / "recipes.yaml"
MAX_NAME_LENGTH = 60  # of a name in `also_called`
__all__ = [
    "RECIPES_PATH", "Alternative", "Choice", "Ingredient", "Recipe", "RecipeLoadError", "RecipeTable",
    "dish_names", "load_recipes", "product_ids_of", "shipped_recipes", "unit_of",
]


class RecipeLoadError(ValueError):
    """The recipe table cannot be used. `problems` lists every reason."""

    def __init__(self, problems: Iterable[str]) -> None:
        self.problems = tuple(problems)
        super().__init__("The recipe table cannot be loaded: " + "; ".join(self.problems))


class RecipeTable(Mapping[str, Recipe]):
    """The checked recipes by dish id, read-only, with the ingredients that are named by product ids."""

    def __init__(
        self, recipes: Mapping[str, Recipe], named_products: Mapping[str, tuple[str, ...]],
        also_called: Mapping[str, tuple[str, ...]] | None = None,
    ) -> None:
        self._recipes = dict(recipes)
        self._named = dict(named_products)
        self._also_called = dict(also_called or {})

    def __getitem__(self, dish_id: str) -> Recipe:
        return self._recipes[dish_id]

    def __iter__(self) -> Iterator[str]:
        return iter(self._recipes)

    def __len__(self) -> int:
        return len(self._recipes)

    @property
    def named_products(self) -> Mapping[str, tuple[str, ...]]:
        """Product ids by the key a recipe uses as a product type, for the keys the product-type table lacks."""
        return dict(self._named)

    @property
    def also_called(self) -> Mapping[str, tuple[str, ...]]:
        """Other names a person may write for a dish, by dish id (`recipes.yaml`, `also_called`)."""
        return dict(self._also_called)


def product_ids_of(recipes: Mapping[str, Recipe], product_type: str) -> tuple[str, ...]:
    """The product ids a request line names for this ingredient; empty when it is a product type of the
    product-type table, which the request line then names by its key."""
    named = recipes.named_products if isinstance(recipes, RecipeTable) else {}
    return named.get(product_type, ())


def dish_names(recipes: Mapping[str, Recipe]) -> dict[str, tuple[str, ...]]:
    """The names each dish goes by in a sentence: the words of its id ("chocolate cake"), its name before any
    bracket ("Salmon with rice and cream sauce"), and the table's `also_called` names. First name first."""
    also = recipes.also_called if isinstance(recipes, RecipeTable) else {}
    names: dict[str, tuple[str, ...]] = {}
    for dish_id, recipe in recipes.items():
        own = (dish_id.replace("_", " "), recipe.name.split("(")[0].strip(), *also.get(dish_id, ()))
        names[dish_id] = tuple(dict.fromkeys(name.casefold() for name in own if name))
    return names


def _also_called(data: Mapping[str, object], recipes: Mapping[str, Recipe]) -> dict[str, tuple[str, ...]]:
    """The `also_called` section. Raises `RecipeLoadError` for a dish the table lacks, a name that is no plain
    text, and a name two dishes share: a sentence must name one dish."""
    raw = data.get("also_called") or {}
    if not isinstance(raw, dict):
        raise RecipeLoadError(["`also_called` is a mapping of a dish id to its other names"])
    problems: list[str] = []
    also: dict[str, tuple[str, ...]] = {}
    for dish_id, names in raw.items():
        plain = isinstance(names, list) and all(
            isinstance(name, str) and 0 < len(name.strip()) <= MAX_NAME_LENGTH for name in names
        )
        if str(dish_id) not in recipes or not plain:
            problems.append(f"also_called.{dish_id}: a dish of the table with a list of names")
            continue
        also[str(dish_id)] = tuple(name.strip() for name in names)
    owners: dict[str, str] = {}
    for dish_id, names in dish_names(RecipeTable(recipes, {}, also)).items():
        for name in names:
            if owners.setdefault(name, dish_id) != dish_id:
                problems.append(f"also_called: '{name}' names both {owners[name]} and {dish_id}")
    if problems:
        raise RecipeLoadError(problems)
    return also


def _named_products(data: Mapping[str, object], known_types: Collection[str]) -> dict[str, tuple[str, ...]]:
    """The `named_products` section. Raises `RecipeLoadError` for an entry that is not a list of product ids."""
    raw = data.get("named_products") or {}
    if not isinstance(raw, dict):
        raise RecipeLoadError(["`named_products` is a mapping of a key to its product ids"])
    named: dict[str, tuple[str, ...]] = {}
    problems: list[str] = []
    for key, entry in raw.items():
        ids = entry.get("product_ids") if isinstance(entry, dict) else None
        plain = isinstance(ids, list) and 0 < len(ids) <= MAX_PRODUCT_IDS and all(
            isinstance(each, str) and each.isalnum() for each in ids
        )
        if not plain:
            problems.append(f"named_products.{key}: `product_ids` is a list of product ids, each in quotes")
        elif str(key) not in known_types:  # the product-type table wins once it holds the key
            named[str(key)] = tuple(dict.fromkeys(ids))
    if problems:
        raise RecipeLoadError(problems)
    return named


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


def load_recipes(known_types: Collection[str], path: Path = RECIPES_PATH) -> RecipeTable:
    """The checked recipe table, by dish id. Raises `RecipeLoadError` listing every problem."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RecipeLoadError([f"{path.name} cannot be read: {type(error).__name__}"]) from error
    recipes = _parse(data)
    named = _named_products(data, known_types)
    problems = _check(recipes, (*known_types, *named))
    if problems:
        raise RecipeLoadError(problems)
    return RecipeTable(recipes, named, _also_called(data, recipes))


def unit_of(recipes: Mapping[str, Recipe], product_type: str) -> Unit | None:
    """The one unit the table uses for a product type; None when no recipe uses it."""
    for recipe in recipes.values():
        for ingredient in recipe.ingredients:
            for choice in (ingredient, *ingredient.alternatives):
                if choice.product_type == product_type:
                    return choice.unit
    return None


@lru_cache(maxsize=1)
def shipped_recipes() -> RecipeTable:
    """The shipped table, checked against the shipped product-type table. Raises `RecipeLoadError`."""
    return load_recipes(tuple(load_product_types(PRODUCT_TYPES_FILE)))
