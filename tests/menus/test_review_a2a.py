"""The findings of review A2a on the menu planner, each as the review reproduced it (M-1 to M-5), in replay over
tonight's capture at the recording's clock (Saturday 14 Nov 2026 02:52, Helsinki).

M-1  a menu of more than 5 product types is planned when the gateway offers `create_menu_offer`
M-2  a stand-in names the allergens its product declares, and which of them the recipe's own type does not
M-3  an ingredient that cannot be sourced stays in the final offer with nothing offered, so the rules see it
M-4  a line fails only when no option of the first offer covers it; the recipe's own ingredient is kept
M-5  an ingredient that is only missing from the demo's recording says so, not "in time"
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Any

import pytest

from tta.api.limits import RateLimit, call_limits
from tta.api.sandbox import KITCHEN_AGENT
from tta.api.wiring import Parts, wire
from tta.contracts.common import Identity, OptionKind, OrderStatus, Verdict
from tta.contracts.errors import InvalidRequest
from tta.contracts.menu import IngredientStatus, MenuPlan, MenuRequest
from tta.contracts.offer import Offer
from tta.contracts.request import PurchaseRequest
from tta.menus import Recipe, plan_menu

MONDAY = "2026-11-16"
LASAGNE_AND_PANCAKE = {
    "dishes": [{"dish_id": "lasagne", "servings": 50}, {"dish_id": "oven_pancake", "servings": 50}],
    "stock": [], "needed_by": MONDAY, "require_confirmed": False,
}


class WithMenuOffers:
    """The gateway of `parts`, plus `create_menu_offer`: an offer under the contract's limit of 20 lines instead
    of the demonstration's 5. (Lane L4b owns `tta.api.service`; until its `Gateway` has the method, this stands
    in for it.) Counts the offers a plan asks for."""

    def __init__(self, parts: Parts) -> None:
        self._capped = parts.service
        self._free, _ = wire(
            catalog=parts.catalog, policy=parts.policy, gateway=parts.gateway, clock=parts.clock, store=parts.store,
            limiter=call_limits(True, RateLimit(calls=1000)), max_request_lines=None,
        )
        self.requests: list[PurchaseRequest] = []

    def create_menu_offer(self, identity: Identity, request: PurchaseRequest) -> Offer:
        self.requests.append(request)
        return self._free.create_offer(identity, request)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._capped, name)


def _ingredient(plan: MenuPlan, dish_id: str, product_type: str) -> Any:
    dish = next(dish for dish in plan.dishes if dish.dish_id == dish_id)
    return next(each for each in dish.ingredients if each.recipe_product_type == product_type)


# --- M-1 ----------------------------------------------------------------------------------------------------


def test_m1_a_menu_of_seven_product_types_is_planned_through_the_gateways_menu_offers(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    service = WithMenuOffers(parts)

    plan = plan_menu(service, agent_hotel, menu(**LASAGNE_AND_PANCAKE), recipes)

    assert len(service.requests[0].lines) == 7  # the first offer: pasta, minced meat, milk, cheese, flour, eggs, sugar
    assert plan.offer_id is not None and len(plan.offers_asked) == len(service.requests) <= 3
    assert _ingredient(plan, "lasagne", "milk").status is IngredientStatus.ORDERED_AS_IN_RECIPE


def test_m1_a_gateway_without_menu_offers_keeps_its_own_limit_of_lines(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    if hasattr(parts.service, "create_menu_offer"):
        pytest.skip("the gateway has menu offers: its own limit no longer applies to a plan")

    with pytest.raises(InvalidRequest, match="at most 5 lines; this one has 7"):
        plan_menu(parts.service, agent_hotel, menu(**LASAGNE_AND_PANCAKE), recipes)


def test_m1_a_menu_of_more_lines_than_one_offer_holds_is_refused_in_plain_words(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest]
) -> None:
    table = _recipes_of_many_types(parts, 21)
    request = menu(dishes=[{"dish_id": "everything", "servings": 10}], stock=[])

    with pytest.raises(InvalidRequest, match="needs 21 request lines; one offer holds at most 20"):
        plan_menu(WithMenuOffers(parts), agent_hotel, request, table)


def _recipes_of_many_types(parts: Parts, count: int) -> Mapping[str, Recipe]:
    types = sorted(parts.catalog.product_type_keys())[:count]
    assert len(types) == count
    ingredients = [
        {"product_type": kind, "per_serving": "0.1", "unit": "KG", "role": "an ingredient"} for kind in types
    ]
    recipe = {"dish_id": "everything", "name": "Everything", "ingredients": ingredients}
    return {"everything": Recipe.model_validate(recipe)}


# --- M-2 ----------------------------------------------------------------------------------------------------


def test_m2_a_stand_in_names_the_allergens_it_declares_and_the_ones_the_recipes_type_does_not(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    """The review's case: rice porridge for 5,000, confirmed only. Milk covers 38% (435 of 1,150 L), so an oat
    drink stands in: 1,500 x 464320 Oatly iKaffe, which declares gluten cereals (AW) and oats (GO). Milk does not."""
    request = menu(dishes=[{"dish_id": "rice_porridge", "servings": 5000}], stock=[])

    plan = plan_menu(parts.service, agent_hotel, request, recipes)

    milk = _ingredient(plan, "rice_porridge", "milk")
    assert milk.status is IngredientStatus.STANDS_IN and milk.product_type == "plant_drink"
    offer = parts.service.get_offer(agent_hotel, plan.offer_id)
    assert [line.product_id for line in offer.options[0].lines if line.stands_in_for == "milk"] == ["464320"]
    assert "Allergens: Oatly iKaffe Oat drink 1L (464320) declares" in milk.sentence
    assert "(AW)" in milk.sentence and "(GO)" in milk.sentence
    assert "The recipe's milk does not declare them" in milk.sentence
    assert "check the dish against the guests' allergies" in milk.sentence
    assert any("464320" in note and "(AW)" in note for note in plan.notes)  # said once more where the plan sums up


def test_m2_a_stand_in_that_declares_nothing_new_says_so(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    """The demo's last-minute event: a Valio yoghurt (464615) stands in for quark. Both declare milk (AM)."""
    plan = plan_menu(parts.service, agent_hotel, menu(), recipes)

    quark = _ingredient(plan, "berry_quark_dessert", "quark")
    assert quark.status is IngredientStatus.STANDS_IN
    assert "(464615) declares" in quark.sentence and "(AM)" in quark.sentence
    assert "as the recipe's quark (maitorahka) does" in quark.sentence
    assert "does not declare them" not in quark.sentence


# --- M-3 ----------------------------------------------------------------------------------------------------


def test_m3_an_unsourced_ingredient_stays_in_the_final_offer_and_the_rules_send_the_rest_to_a_person(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    """The review's case was an oven pancake for 50: eggs, flour and sugar were not in the recording, the final
    offer was milk alone and no rule knew three ingredients were missing. Since the baking recording was joined
    (task CK) the pancake is fully sourced, so the case is a macaroni casserole for 50: pasta and minced meat are
    in neither recording, milk and eggs are."""
    request = menu(dishes=[{"dish_id": "macaroni_casserole", "servings": 50}], stock=[], require_confirmed=False)

    plan = plan_menu(parts.service, agent_hotel, request, recipes)

    assert {item.product_type for item in plan.cannot_be_sourced} == {"pasta", "minced_meat"}
    offer = parts.service.get_offer(agent_hotel, plan.offer_id)
    assert [line.product_type for line in offer.request.lines] == ["pasta", "minced_meat", "milk", "eggs"]
    top = offer.options[0]
    # 8 x 463047 milk. It was 60.44 with 1 x 466032, a scrambled egg mix: since lane FIX-O1 (commit 904d6d2) the
    # eggs type holds the plain product only, and no egg has confirmed stock: eggs are in the second option, with a
    # quantity that is not confirmed (2 x 467880). Re-pinned by lane FP-M on 15 Nov 2026, the recording's clock.
    assert top.totals.net == Decimal("16.08") and top.fill_ratio == 0
    assert [line.product_id for line in offer.options[1].lines] == ["469477", "467880"]
    assert top.decision.verdict is Verdict.APPROVAL
    assert {"F-07", "P-03"} <= set(top.decision.rule_ids)  # the date is not met for every line; fill below minimum
    meat = _ingredient(plan, "macaroni_casserole", "minced_meat")
    assert meat.status is IngredientStatus.CANNOT_BE_SOURCED and meat.request_line_index == 1
    assert len(plan.offers_asked) == 2  # ham was tried for the minced meat; nothing replaced, the first offer stays
    assert any("2 ingredients cannot be sourced (pasta and minced meat)" in note for note in plan.notes)
    assert any("stay in the offer with nothing offered" in note for note in plan.notes)


def test_m3_with_ordering_alone_switched_on_the_incomplete_menu_still_waits_for_a_person(
    parts: Parts, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    """A browser's own kitchen, started from the hotel's profile, with the buyer's setting switched on."""
    book = parts.sandboxes.open("m3")
    book.kitchen.start_from("hotel-kitchen")
    book.kitchen.set_up({**book.kitchen.settings, "auto_order_enabled": True})
    request = menu(dishes=[{"dish_id": "macaroni_casserole", "servings": 50}], stock=[], require_confirmed=False)

    plan = plan_menu(book.service, KITCHEN_AGENT, request, recipes)
    order = book.service.place_order(KITCHEN_AGENT, plan.offer_id, "opt_1", "menu-m3")
    reasons = " ".join(rule.sentence for rule in order.decision.fired)

    assert book.kitchen.profile.auto_order_enabled is True
    assert order.status is OrderStatus.PENDING_APPROVAL and order.placed_by is None
    assert {"F-07", "P-03"} <= set(order.decision.rule_ids)
    # The person reads which ingredients the order leaves out (the rules' sentences were reworded on 15 Nov 2026:
    # they name what is missing, where they said "0 of 4 kg of pasta").
    assert "Nothing is offered for pasta, minced meat and eggs" in reasons


# --- M-4 ----------------------------------------------------------------------------------------------------


def test_m4_without_confirmed_only_the_recipes_own_quark_is_kept_because_an_option_offers_it(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    """The review's case: the demo menu without "confirmed only". Option 2 of the first offer holds 3 x 477044
    Valio quark 5 kg; before, the plan said no quark could be offered and ordered yoghurt in its place."""
    plan = plan_menu(parts.service, agent_hotel, menu(require_confirmed=False), recipes)

    quark = _ingredient(plan, "berry_quark_dessert", "quark")
    assert quark.status is IngredientStatus.ORDERED_AS_IN_RECIPE and quark.product_type == "quark"
    assert len(plan.offers_asked) == 1 and plan.cannot_be_sourced == ()
    offer = parts.service.get_offer(agent_hotel, plan.offer_id)
    unconfirmed = next(option for option in offer.options if option.kind is OptionKind.ALTERNATIVE_UNCONFIRMED)
    assert "477044" in unconfirmed.product_ids
    # Lane FIX-M (review row C3-F8): the reason in words, no share of a line.
    assert (
        "It is not in option 1 (Best confirmed option (partial fill)): it has no confirmed stock that can arrive by "
        "Monday 16 Nov."
    ) in quark.sentence  # 6 of the 10 plain quarks are past their order cut-off; the other 4 have no confirmed stock
    assert "Option 2 offers 3 × " in quark.sentence and "covers 0%" not in quark.sentence
    assert all(line.stands_in_for is None for line in plan.lines)


def test_m4_with_confirmed_only_nothing_changes_yoghurt_still_stands_in(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    plan = plan_menu(parts.service, agent_hotel, menu(), recipes)

    assert _ingredient(plan, "berry_quark_dessert", "quark").status is IngredientStatus.STANDS_IN
    assert parts.service.get_offer(agent_hotel, plan.offer_id).options[0].totals.net == Decimal("476.48")


# --- M-5 ----------------------------------------------------------------------------------------------------


def test_m5_an_ingredient_that_is_only_missing_from_the_recording_says_so(
    parts: Parts, agent_hotel: Identity, menu: Callable[..., MenuRequest], recipes: Mapping[str, Recipe]
) -> None:
    request = menu(dishes=[{"dish_id": "macaroni_casserole", "servings": 50}], stock=[], require_confirmed=False)

    plan = plan_menu(parts.service, agent_hotel, request, recipes)

    sentences = {item.product_type: item.sentence for item in plan.cannot_be_sourced}
    assert sentences["pasta"].startswith(
        "Cannot be sourced in this demo: pasta (macaroni): none of its 15 products is in this demo's recording of "
        "Valio Aimo's data, so no price or stock is known for it"
    )
    assert "by Mon 16 Nov 2026" not in sentences["pasta"]  # it is not about the date
    # Before the baking recording was joined (task CK) sugar showed a line with another reason too ("3 portion
    # pack, 37 not in this demo's recording"), which kept the date. No recipe line mixes the two reasons now.
