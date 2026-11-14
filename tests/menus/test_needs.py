"""Dishes x servings, minus the kitchen's stock, added up per product type, rounded up: the request lines."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal

import pytest

from tta.contracts.common import AllergenStrictness, Unit
from tta.contracts.errors import InvalidRequest
from tta.contracts.menu import MenuRequest
from tta.menus import Recipe
from tta.menus.needs import as_recipe, expand, group, purchase_request


def _by_type(menu: MenuRequest, recipes: Mapping[str, Recipe]) -> dict[tuple[str, tuple[str, ...]], Decimal]:
    return {
        (need.choice.product_type, need.choice.name_terms): need.quantity
        for need in group(expand(menu, recipes), as_recipe)
    }


def test_servings_times_amounts_minus_stock_rounded_up_to_whole_units(
    menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    quantities = _by_type(menu(), recipes)

    # 120 x 0.18 kg chuck = 21.6 -> 22; 120 x 0.03 L cream = 3.6 -> 4, twice (cooking and whipping); quark 12 kg.
    assert quantities == {
        ("beef_chuck", ()): Decimal(22), ("cream", ()): Decimal(4), ("quark", ("maitorahka",)): Decimal(12),
        ("cream", ("whipping",)): Decimal(4),
    }  # butter (1.2 kg) and sugar (1.2 kg) are in stock


def test_stock_goes_to_the_dishes_in_menu_order_and_only_the_rest_is_ordered(
    menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    request = menu(
        dishes=[{"dish_id": "rice_porridge", "servings": 10}, {"dish_id": "oven_pancake", "servings": 10}],
        stock=[{"product_type": "milk", "quantity": 4, "unit": "L"}],
    )

    uses = {use.recipe.dish_id: use for use in expand(request, recipes) if use.ingredient.product_type == "milk"}

    assert (uses["rice_porridge"].needed, uses["rice_porridge"].in_stock) == (Decimal("3.0"), Decimal("3.0"))
    assert (uses["oven_pancake"].needed, uses["oven_pancake"].in_stock) == (Decimal("1.50"), Decimal("1.0"))
    assert _by_type(request, recipes)[("milk", ())] == Decimal(1)  # 0.5 L rounded up


def test_a_line_is_never_below_one_unit(menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]) -> None:
    request = menu(dishes=[{"dish_id": "cheese_omelette", "servings": 1}], stock=[])

    assert _by_type(request, recipes)[("milk", ())] == Decimal(1)  # 0.03 L


def test_an_unknown_dish_or_a_stock_in_another_unit_is_an_invalid_request(
    menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    with pytest.raises(InvalidRequest, match="No recipe has the id 'pizza'"):
        expand(menu(dishes=[{"dish_id": "pizza", "servings": 10}]), recipes)
    with pytest.raises(InvalidRequest, match="must be given in KG, not L"):
        expand(menu(stock=[{"product_type": "butter", "quantity": 3, "unit": "L"}]), recipes)


def test_a_menu_lists_a_dish_once_and_a_stock_once() -> None:
    with pytest.raises(ValueError, match="a dish is listed once"):
        MenuRequest.model_validate({"dishes": [{"dish_id": "lasagne", "servings": 1}] * 2})
    with pytest.raises(ValueError, match="the stock of a product type is given once"):
        MenuRequest.model_validate({
            "dishes": [{"dish_id": "lasagne", "servings": 1}],
            "stock": [{"product_type": "milk", "quantity": 1, "unit": "L"}] * 2,
        })


def test_the_request_lines_name_their_dishes_and_carry_the_menus_date_and_exclusions(
    menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    request = menu(exclude_allergens=["AM"], allergen_strictness=AllergenStrictness.STRICT)

    purchase = purchase_request(request, group(expand(request, recipes), as_recipe))

    assert purchase.needed_by == request.needed_by and purchase.require_confirmed
    first = purchase.lines[0]
    assert first.text == "22 kg beef chuck for Beef stew (120 servings)"
    assert (first.product_type, first.unit, first.stands_in_for) == ("beef_chuck", Unit.KG, None)
    assert all(line.exclude_allergens == ("AM",) for line in purchase.lines)
    assert all(line.allergen_strictness is AllergenStrictness.STRICT for line in purchase.lines)
    assert purchase.lines[2].name_terms == ("maitorahka",)


def test_a_stand_in_line_names_the_recipe_type_it_replaces_and_the_role(
    menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    uses = [use for use in expand(menu(), recipes) if use.ingredient.product_type == "quark"]
    yoghurt = uses[0].ingredient.alternatives[0]

    need = group(uses, lambda use: (yoghurt, use.ingredient.product_type))[0]
    line = purchase_request(menu(), (need,)).lines[0]

    assert line.stands_in_for == "quark" and line.product_type == "yoghurt" and line.name_terms == ("natural",)
    assert line.text == (
        "12 kg yoghurt (natural) for Berry quark dessert (marjarahka) (120 servings), in place of quark "
        "(maitorahka): the thick, tangy base of the dessert"
    )
