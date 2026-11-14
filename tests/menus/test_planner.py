"""The menu planner over tonight's capture, in replay: one offer, alternatives by role, what cannot arrive in time.

The demo case is the last-minute event of `conftest.py`: beef stew and berry quark dessert for 120 each, needed
Monday 16 Nov, confirmed stock only. Plain quark (maitorahka) cannot be had by Monday: 6 of its 10 products are
past their order cut-off and the other 4 have no confirmed stock. A natural yoghurt does the same job.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal

import pytest

from tta.api.wiring import Parts
from tta.contracts.common import AvailabilityState, Identity, OrderStatus, Verdict
from tta.contracts.menu import IngredientStatus, MenuPlan, MenuRequest
from tta.menus import Recipe, plan_menu
from tta.menus.needs import Use
from tta.menus.planner import _probe_needs
from tta.menus.recipes import Alternative, Ingredient

QUARK_NOT_BY_MONDAY = (
    "Quark (maitorahka): none of 10 products can be offered by Mon 16 Nov 2026 (6 order cut-off passed, "
    "4 quantity not confirmed (confirmed data only was asked for))"
)


def _ingredient(plan: MenuPlan, dish_id: str, product_type: str) -> object:
    dish = next(dish for dish in plan.dishes if dish.dish_id == dish_id)
    return next(each for each in dish.ingredients if each.recipe_product_type == product_type)


def test_the_last_minute_event_replaces_quark_by_its_role_and_keeps_the_rest(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    plan = plan_menu(parts.service, agent_hotel, menu(), recipes)

    quark = _ingredient(plan, "berry_quark_dessert", "quark")
    assert quark.status is IngredientStatus.STANDS_IN and quark.product_type == "yoghurt"
    assert quark.alternative_reason.startswith("A thick natural yoghurt gives the same tangy base")
    assert QUARK_NOT_BY_MONDAY in quark.sentence
    assert _ingredient(plan, "beef_stew", "beef_chuck").status is IngredientStatus.ORDERED_AS_IN_RECIPE
    assert _ingredient(plan, "beef_stew", "butter").status is IngredientStatus.IN_STOCK
    assert len(plan.offers_asked) == 3 and plan.offer_id == plan.offers_asked[-1]
    assert plan.illustrative and "illustrative" in plan.notes[0]
    assert plan.cannot_be_sourced == ()
    ordered = [(line.product_type, line.to_order, line.stands_in_for) for line in plan.lines if line.to_order]
    assert ordered == [
        ("beef_chuck", Decimal(22), None), ("cream", Decimal(4), None), ("cream", Decimal(4), None),
        ("yoghurt", Decimal(12), "quark"),
    ]


def test_the_final_offer_holds_every_line_confirmed_and_the_stand_in_goes_to_a_human(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    plan = plan_menu(parts.service, agent_hotel, menu(), recipes)
    offer = parts.service.get_offer(agent_hotel, plan.offer_id)

    assert [line.stands_in_for for line in offer.request.lines] == [None, None, None, "quark"]
    top = offer.options[0]
    assert top.fill_ratio == 1 and top.totals.net == Decimal("476.48")
    assert {line.availability.state for line in top.lines} == {AvailabilityState.CONFIRMED}
    assert top.decision.verdict is Verdict.APPROVAL
    assert "F-09" in top.decision.rule_ids  # the stand-in goes to a human, whatever the profile allows
    stand_in = next(line for line in top.lines if line.stands_in_for is not None)
    assert stand_in.stands_in_for == "quark" and stand_in.stands_in_role
    f09 = next(rule for rule in top.decision.fired if rule.rule_id == "F-09")
    assert "in place of the recipe's quark" in f09.sentence and "whose role is" in f09.sentence


def test_the_plan_orders_through_the_normal_flow(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    plan = plan_menu(parts.service, agent_hotel, menu(), recipes)

    order = parts.service.place_order(agent_hotel, plan.offer_id, "opt_1", "menu-test-1")

    assert order.status is OrderStatus.PENDING_APPROVAL and order.offer_id == plan.offer_id


def test_a_menu_whose_every_line_is_covered_asks_for_one_offer(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    request = menu(dishes=[{"dish_id": "beef_stew", "servings": 50}], require_confirmed=False)

    plan = plan_menu(parts.service, agent_hotel, request, recipes)

    assert len(plan.offers_asked) == 1 and plan.offer_id == plan.offers_asked[0]
    statuses = [each.status for each in plan.dishes[0].ingredients]
    assert statuses == [IngredientStatus.ORDERED_AS_IN_RECIPE] * 2 + [IngredientStatus.IN_STOCK]


def test_an_ingredient_without_a_working_alternative_cannot_be_sourced_and_says_why(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    """Rice and butter are not in the capture, and rice porridge lists no alternative for either."""
    request = menu(dishes=[{"dish_id": "rice_porridge", "servings": 40}], stock=[])

    plan = plan_menu(parts.service, agent_hotel, request, recipes)

    unsourced = {item.product_type: item for item in plan.cannot_be_sourced}
    assert set(unsourced) == {"rice", "butter"}
    assert "not in the recorded capture" in unsourced["rice"].sentence
    assert "the recipe lists no alternative that does the same job" in unsourced["rice"].sentence
    assert _ingredient(plan, "rice_porridge", "rice").status is IngredientStatus.CANNOT_BE_SOURCED
    assert len(plan.offers_asked) == 2  # no second offer: nothing to try; the final offer has milk only
    assert [line.product_type for line in plan.lines if line.request_line_index is not None] == ["milk"]


def test_a_fill_below_the_profiles_minimum_tries_the_next_alternative(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    """3,000 servings need 240 L of cream; about 199 L of confirmed cream can arrive by Monday (83%, below the
    hotel's 90%). 500 L of a vegetable-fat cream can."""
    request = menu(dishes=[{"dish_id": "creamy_chicken_pasta", "servings": 3000}], stock=[])

    plan = plan_menu(parts.service, agent_hotel, request, recipes)

    cream = _ingredient(plan, "creamy_chicken_pasta", "cream")
    assert cream.status is IngredientStatus.STANDS_IN and cream.product_type == "vegetable_cream"
    assert "Cream: only 8" in cream.sentence and "of it can be offered by Mon 16 Nov 2026" in cream.sentence
    tried = {item.product_type: item.tried for item in plan.cannot_be_sourced}
    assert tried == {"chicken": ("pork",), "pasta": ("rice",), "cheese": ()}


def test_everything_in_stock_asks_for_no_offer(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    request = menu(
        dishes=[{"dish_id": "cheese_omelette", "servings": 10}],
        stock=[{"product_type": "eggs", "quantity": 5, "unit": "KG"},
               {"product_type": "milk", "quantity": 5, "unit": "L"},
               {"product_type": "cheese", "quantity": 5, "unit": "KG"},
               {"product_type": "rice", "quantity": 5, "unit": "KG"}],
    )

    plan = plan_menu(parts.service, agent_hotel, request, recipes)

    assert plan.offer_id is None and plan.offers_asked == ()
    assert "nothing is ordered" in " ".join(plan.notes) and "No dish of this menu uses the stock" in plan.notes[-1]
    assert {each.status for each in plan.dishes[0].ingredients} == {IngredientStatus.IN_STOCK}


def test_the_second_offer_takes_best_alternatives_first_and_at_most_five_lines(
    recipes: Mapping[str, Recipe],
) -> None:
    alternatives = tuple(
        Alternative(product_type=kind, per_serving=Decimal("0.1"), unit="KG", reason="Does the same job.")
        for kind in ("pork", "ham", "sausage")
    )
    uses = [
        Use(recipes["beef_stew"], 10, Ingredient(
            product_type=kind, per_serving=Decimal("0.1"), unit="KG", role="the meat", alternatives=alternatives,
        ), Decimal(1), Decimal(0))
        for kind in ("beef_chuck", "beef", "minced_meat")
    ]

    probe = _probe_needs(uses)

    assert len(probe) == 5
    assert [need.key for need in probe[:3]] == [("pork", (), "beef_chuck"), ("pork", (), "beef"),
                                                 ("pork", (), "minced_meat")]
    assert [need.choice.product_type for need in probe[3:]] == ["ham", "ham"]


@pytest.mark.parametrize("servings", [0, 5001])
def test_servings_are_bounded(servings: int) -> None:
    with pytest.raises(ValueError, match="servings"):
        MenuRequest.model_validate({"dishes": [{"dish_id": "lasagne", "servings": servings}]})
