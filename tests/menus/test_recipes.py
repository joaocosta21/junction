"""The recipe table: ours, illustrative, checked when it loads (task MENU-1)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from tta.catalog import ProductCatalog
from tta.contracts.common import Unit
from tta.menus import RECIPES_PATH, Recipe, RecipeLoadError, load_recipes
from tta.menus.recipes import unit_of

MIN_DISHES = 8
GOOD_DISH = """
dishes:
  stew:
    name: Stew
    ingredients:
      - product_type: beef_chuck
        per_serving: 0.2
        unit: KG
        role: the meat
        alternatives:
          - product_type: pork
            reason: Pork braises the same way.
"""
_ROAST = """
  roast:
    name: Roast
    ingredients:
      - product_type: pork
        per_serving: 0.2
        unit: KG
        role: the meat
"""


def test_the_shipped_table_has_eight_dishes_or_more_each_with_roles_and_reasoned_alternatives(
    recipes: Mapping[str, Recipe],
) -> None:
    assert len(recipes) >= MIN_DISHES
    with_alternatives = 0
    for recipe in recipes.values():
        assert recipe.name and recipe.ingredients
        for ingredient in recipe.ingredients:
            assert ingredient.role and ingredient.per_serving > 0
            for alternative in ingredient.alternatives:
                with_alternatives += 1
                assert alternative.reason.endswith(".") and alternative.product_type != ingredient.product_type
    assert with_alternatives >= MIN_DISHES


def test_the_table_says_it_is_ours_and_illustrative_and_why_vegetables_are_left_out(
    recipes: Mapping[str, Recipe],
) -> None:
    header = RECIPES_PATH.read_text(encoding="utf-8").split("dishes:")[0]

    assert "OURS AND ILLUSTRATIVE" in header and "Valio Aimo publishes no recipes" in header
    assert "no vegetables" in recipes["beef_stew"].left_out[0]


def test_a_vegetarian_dish_is_on_the_menu(recipes: Mapping[str, Recipe]) -> None:
    meat = {"beef_chuck", "beef", "pork", "chicken", "minced_meat", "ham", "sausage", "fresh_fish"}

    vegetarian = [
        recipe for recipe in recipes.values()
        if not any(ingredient.product_type in meat for ingredient in recipe.ingredients)
    ]

    assert any("vegetarian" in recipe.name.lower() for recipe in vegetarian)


def test_a_product_type_has_one_unit_everywhere(recipes: Mapping[str, Recipe]) -> None:
    assert unit_of(recipes, "cream") is Unit.L
    assert unit_of(recipes, "beef_chuck") is Unit.KG
    assert unit_of(recipes, "olive_oil") is Unit.L  # given by the alternative itself
    assert unit_of(recipes, "carrot") is None


def test_an_alternative_takes_the_ingredients_amount_unless_it_gives_its_own(recipes: Mapping[str, Recipe]) -> None:
    quark = recipes["berry_quark_dessert"].ingredients[0]

    assert quark.alternatives[0].per_serving == quark.per_serving and quark.alternatives[0].unit is quark.unit


@pytest.mark.parametrize(
    ("content", "problem"),
    [
        ("dishes: [unclosed", "cannot be read"),
        ("", "a mapping `dishes`"),
        ("dishes: {}", "a mapping `dishes`"),
        ("dishes:\n  stew: 5\n", "a dish is a mapping"),
        (GOOD_DISH.replace("beef_chuck", "carrot"), "'carrot' is not a product type"),
        (GOOD_DISH.replace("product_type: pork", "product_type: beef_chuck"), "must be other product types"),
        (GOOD_DISH.replace("per_serving: 0.2", "per_serving: 0"), "stew:"),
        (GOOD_DISH.replace("unit: KG", "unit: UNIT"), "L or KG"),
        (GOOD_DISH.replace("            reason: Pork braises the same way.\n", ""), "stew:"),
        (GOOD_DISH + _ROAST.replace("unit: KG", "unit: L"), "'pork' is in KG elsewhere"),
        (GOOD_DISH + GOOD_DISH.split("ingredients:\n")[1].replace("pork", "beef"), "listed twice"),
    ],
    ids=["broken yaml", "empty", "no dish", "not a mapping", "unknown type", "alternative is the same type",
         "no amount", "sales units", "no reason", "two units", "listed twice"],
)
def test_a_broken_table_does_not_load(
    content: str, problem: str, tmp_path: Path, catalog: ProductCatalog
) -> None:
    path = tmp_path / "recipes.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(RecipeLoadError) as raised:
        load_recipes(catalog.product_type_keys(), path)

    assert any(problem in each for each in raised.value.problems), raised.value.problems


def test_a_missing_file_does_not_load(tmp_path: Path) -> None:
    with pytest.raises(RecipeLoadError, match="cannot be read: FileNotFoundError"):
        load_recipes(("milk",), tmp_path / "none.yaml")


def test_a_good_table_loads(tmp_path: Path, catalog: ProductCatalog) -> None:
    path = tmp_path / "recipes.yaml"
    path.write_text(GOOD_DISH, encoding="utf-8")

    recipes = load_recipes(catalog.product_type_keys(), path)

    assert recipes["stew"].ingredients[0].alternatives[0].product_type == "pork"
