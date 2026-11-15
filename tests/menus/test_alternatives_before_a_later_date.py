"""A recipe's alternatives are tried before a later date is offered (lane FP-M), in replay.

Scores on the 15% "robustness to exception situations": the brief's own example, "an unexpected booking for
tomorrow", is answered "through recipe logic rather than a simple SKU swap". When nothing of a request can arrive
by the date asked, the offers code holds the same products for their earliest date (decision B67,
`tta.offers.later`). The planner read those options as cover and no longer asked for the alternatives. A line
now counts only when its products arrive by the day asked; the later date is what is left when no alternative
arrives in time either.

Measured offline on 15 Nov 2026 at the demo clock (Thu 12 Nov 2026 14:15 Helsinki): for Friday 13 Nov nothing
arrives in the recording, whatever is tried (every ingredient and every alternative of the nine dishes was asked
for). So the first two tests are the recording's, and the third is CONSTRUCTED: a gateway that answers a
stand-in's request with Monday's products and says they arrive on the Friday asked.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from tta.api.limits import RateLimit
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import Identity
from tta.contracts.menu import IngredientStatus, MenuRequest
from tta.contracts.offer import Offer
from tta.contracts.request import PurchaseRequest
from tta.menus import Recipe, plan_menu
from tta.menus.plan import best_fill_of, in_time_fill_of
from tta.menus.sentence import MenuAsk, resolve

MONDAY, FRIDAY = date(2026, 11, 16), date(2026, 11, 13)
DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
HELD_FOR_MONDAY = (
    "Beef chuck, cream and butter cannot arrive by Friday 13 Nov: the offer holds them for Monday 16 Nov, and a "
    "person must accept the later date."
)


@pytest.fixture
def demo_parts(tmp_path: Path, catalog: ProductCatalog) -> Iterator[Parts]:
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_demo_clock=DEMO_CLOCK)
    built = build_parts(settings, catalog=catalog, rate_limit=RateLimit(calls=1000))
    yield built
    built.close()


def test_a_line_held_for_a_later_day_covers_nothing_by_the_day_asked(
    demo_parts: Parts, agent_hotel: Identity, recipes: Mapping[str, Recipe]
) -> None:
    request = resolve(MenuAsk(text="beef stew for 80 for tomorrow"), recipes, DEMO_CLOCK.date()).request
    plan = plan_menu(demo_parts.service, agent_hotel, request, recipes)

    first = demo_parts.service.get_offer(agent_hotel, plan.offers_asked[0])

    assert [best_fill_of(first, index) for index in range(3)] == [Decimal(1)] * 3  # held, for Monday
    assert [in_time_fill_of(first, index, FRIDAY) for index in range(3)] == [Decimal(0)] * 3
    assert [in_time_fill_of(first, index, MONDAY) for index in range(3)] == [Decimal(1)] * 3
    assert [in_time_fill_of(first, index, None) for index in range(3)] == [Decimal(1)] * 3  # no day asked


def test_for_tomorrow_the_alternatives_are_asked_for_and_only_then_the_later_date_is_offered(
    demo_parts: Parts, agent_hotel: Identity, recipes: Mapping[str, Recipe]
) -> None:
    """The recording's answer. Beef brisket, vegetable cream and milk cannot arrive by Friday either (pork and
    olive oil are not in the recording), so the plan is the first offer: the recipe's own products for Monday."""
    request = resolve(MenuAsk(text="beef stew for 80 for tomorrow"), recipes, DEMO_CLOCK.date()).request

    plan = plan_menu(demo_parts.service, agent_hotel, request, recipes)

    assert request.needed_by == FRIDAY
    assert len(plan.offers_asked) == 2 and plan.offer_id == plan.offers_asked[0]
    probe = demo_parts.service.get_offer(agent_hotel, plan.offers_asked[1])
    assert [(line.product_type, line.stands_in_for) for line in probe.request.lines] == [
        ("beef", "beef_chuck"), ("vegetable_cream", "cream"), ("olive_oil", "butter"),
        ("pork", "beef_chuck"), ("milk", "cream"),
    ]
    assert probe.options == ()
    assert {each.status for each in plan.dishes[0].ingredients} == {IngredientStatus.ORDERED_AS_IN_RECIPE}
    assert [each.earliest_date for each in plan.dishes[0].ingredients] == [MONDAY] * 3
    assert plan.cannot_be_sourced == () and HELD_FOR_MONDAY in plan.notes


class _StandInsArriveOnTheDayAsked:
    """CONSTRUCTED. A gateway where the products that stand in for a recipe's ingredient arrive on the day asked:
    a request whose lines stand in is answered with Monday's products, each said to arrive on the day asked. A
    request for the recipe's own products is answered as the recording answers it."""

    def __init__(self, service: object) -> None:
        self._service = service

    def __getattr__(self, name: str) -> object:
        return getattr(self._service, name)

    def create_menu_offer(self, identity: Identity, request: PurchaseRequest) -> Offer:
        if all(line.stands_in_for is None for line in request.lines):
            return self._service.create_menu_offer(identity, request)
        offer = self._service.create_menu_offer(identity, request.model_copy(update={"needed_by": MONDAY}))
        return offer.model_copy(update={"options": tuple(
            option.model_copy(update={"lines": tuple(
                line.model_copy(update={
                    "availability": line.availability.model_copy(update={"available_date": request.needed_by}),
                })
                for line in option.lines
            )})
            for option in offer.options
        )})


def test_an_alternative_that_arrives_in_time_is_taken_before_the_recipes_own_product_for_a_later_date(
    demo_parts: Parts, agent_hotel: Identity, recipes: Mapping[str, Recipe]
) -> None:
    """Constructed: quark for Friday is held for Monday by the recording; the natural yoghurt arrives on Friday
    because the gateway of this test says so. The kitchen holds the cream and the sugar."""
    request = MenuRequest.model_validate({
        "dishes": [{"dish_id": "berry_quark_dessert", "servings": 40}],
        "stock": [{"product_type": "cream", "quantity": 50, "unit": "L"},
                  {"product_type": "sugar", "quantity": 50, "unit": "KG"}],
        "needed_by": FRIDAY.isoformat(),
    })

    plan = plan_menu(_StandInsArriveOnTheDayAsked(demo_parts.service), agent_hotel, request, recipes)

    quark = next(each for each in plan.dishes[0].ingredients if each.recipe_product_type == "quark")
    assert len(plan.offers_asked) == 3
    assert quark.status is IngredientStatus.STANDS_IN and quark.product_type == "yoghurt"
    assert quark.earliest_date is None and "It arrives on" not in quark.sentence
    assert (
        "Quark (maitorahka): none of 10 products can be offered by Fri 13 Nov 2026 (10 delivered too late), and the "
        "earliest it could arrive is Monday 16 Nov."
    ) in quark.sentence
    assert "only 100%" not in quark.sentence
    assert plan.cannot_be_sourced == () and not any("cannot arrive by" in note for note in plan.notes)
