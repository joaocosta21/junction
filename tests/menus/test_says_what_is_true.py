"""A menu plan says what is true (lane FIX-M, review rows C3-F8 and C3-F6), in replay.

C3-F8, scenario 7 of the demo: the bakery's chocolate cake for 20. Its first option holds flour, cocoa powder, milk
and baking powder; sugar, eggs and butter have no confirmed stock and are in the second option only. Nothing is late.
The plan's sentence for that option counts the ingredients covered and names the others with the reason, and never
says a date is not met, a percentage of one request line, or an ingredient by its line number or product ids.

C3-F6, "for tomorrow": at the demo clock (Thu 12 Nov 2026 14:15 Helsinki) a beef stew for Friday 13 Nov cannot be
sourced; each ingredient names the earliest date it could arrive, Monday 16 Nov, in the structure and in words.

Figures measured offline on 15 Nov 2026 on the recordings `2026-11-14-demo` and `2026-11-14-baking`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from tta.api.limits import RateLimit
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import Identity, IdentityKind
from tta.contracts.errors import InvalidRequest
from tta.contracts.menu import IngredientStatus, MenuPlan, MenuRequest
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.request import PurchaseRequest
from tta.menus import Recipe, plan_menu
from tta.menus.earliest import earliest_date
from tta.menus.offered import money
from tta.menus.sentence import MenuAsk, resolve

MONDAY, FRIDAY = date(2026, 11, 16), date(2026, 11, 13)
DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
CLOCKS = {"default": None, "demo": DEMO_CLOCK}
BAKERY = Identity(kind=IdentityKind.AGENT, id="agent:bakery-cafe", display_name="Kallio Bakery agent",
                  profile_id="bakery-cafe")
WRONG_WORDS = ("not met", "0%", "request line", "F-07", "P-03", "466852", "of 0.1 kg")
# Why the bakery's first option holds no sugar, eggs or butter. On Thursday no product of the three has confirmed
# stock. On Saturday a butter is also past its order cut-off for Monday, so "no confirmed stock" is said of the
# butter that can still arrive: a product that misses the day may well have stock.
NOT_IN_THE_FIRST_OPTION = {
    "demo": (
        "Sugar, eggs and butter have no confirmed stock, so they are not in this option; option 2 offers them with "
        "a quantity Valio Aimo has not confirmed."
    ),
    "default": (
        "Sugar and eggs have no confirmed stock, so they are not in this option; option 2 offers them with a "
        "quantity Valio Aimo has not confirmed. Butter has no confirmed stock that can arrive by Monday 16 Nov, so "
        "it is not in this option; option 2 offers it with a quantity Valio Aimo has not confirmed."
    ),
}


@pytest.fixture(params=sorted(CLOCKS))
def clock(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def clocked_parts(tmp_path: Path, catalog: ProductCatalog, clock: str) -> Iterator[Parts]:
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_demo_clock=CLOCKS[clock])
    built = build_parts(settings, catalog=catalog, rate_limit=RateLimit(calls=1000))
    yield built
    built.close()


@pytest.fixture
def demo_parts(tmp_path: Path, catalog: ProductCatalog) -> Iterator[Parts]:
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_demo_clock=DEMO_CLOCK)
    built = build_parts(settings, catalog=catalog, rate_limit=RateLimit(calls=1000))
    yield built
    built.close()


def _menu(dish_id: str, servings: int, needed_by: date) -> MenuRequest:
    return MenuRequest.model_validate(
        {"dishes": [{"dish_id": dish_id, "servings": servings}], "needed_by": needed_by.isoformat()}
    )


def _option_notes(plan: MenuPlan) -> list[str]:
    return [note for note in plan.notes if note.startswith("Option ")]


def _total(option: OfferOption) -> str:
    """The start of an option's note. The title and the totals are the offer's: which product the offers code
    takes, and so the total, is another lane's to decide and is not pinned here."""
    return (
        f"Option {option.rank}, {option.title}: {money(option.totals.net)} before tax, "
        f"{money(option.totals.gross)} with tax."
    )


def _ingredient(plan: MenuPlan, product_type: str):  # noqa: ANN202 - an IngredientPlan
    return next(each for each in plan.dishes[0].ingredients if each.recipe_product_type == product_type)


# --- C3-F8: an option that leaves ingredients out ----------------------------------------------------------------


def test_the_note_of_an_option_that_leaves_ingredients_out_counts_what_is_covered_and_says_why_the_rest_is_not(
    clocked_parts: Parts, recipes: Mapping[str, Recipe], clock: str
) -> None:
    plan = plan_menu(clocked_parts.service, BAKERY, _menu("chocolate_cake", 20, MONDAY), recipes)
    confirmed, alternative = clocked_parts.service.get_offer(BAKERY, plan.offer_id).options[:2]

    first, second = _option_notes(plan)[:2]

    assert confirmed.title == "Best confirmed option (partial fill)" and confirmed.fill_ratio == 0
    assert first == (
        f"{_total(confirmed)} 4 of the 7 ingredients are covered in full: flour, cocoa powder, milk and baking "
        f"powder. {NOT_IN_THE_FIRST_OPTION[clock]} What this option holds arrives by Monday 16 Nov. An order that is "
        "not complete goes to a person. It needs the purchasing manager."
    )
    assert not any(wrong in first for wrong in WRONG_WORDS)
    # The option that holds every ingredient keeps the policy's own sentence: nothing in it was untrue.
    assert alternative.fill_ratio == 1
    assert second == f"{_total(alternative)} {alternative.decision.sentence}"
    assert "is not confirmed by Valio Aimo (F-01)" in second


def test_an_ingredient_only_the_second_option_holds_says_why_in_words_and_no_share_of_a_line(
    clocked_parts: Parts, recipes: Mapping[str, Recipe]
) -> None:
    plan = plan_menu(clocked_parts.service, BAKERY, _menu("chocolate_cake", 20, MONDAY), recipes)

    sugar = _ingredient(plan, "sugar").sentence

    assert sugar.startswith(
        "0.4 kg to order as sugar (granulated), on line 2 of the offer. It is not in option 1 (Best confirmed option "
        "(partial fill)): it has no confirmed stock. The recipe's own ingredient is kept, and a person chooses the "
        "option. Option 2 offers 1 × "
    )
    assert "quantity not confirmed. 0.4 kg is needed and the pack holds " in sugar and sugar.endswith("is left over.")
    assert "covers 0%" not in sugar and "of that line" not in sugar
    assert _ingredient(plan, "flour").sentence.startswith(
        "0.4 kg to order as flour (semi), on line 1 of the offer. Offered: 1 × "
    )


def test_an_ingredient_in_no_option_is_named_with_its_reason_and_the_other_rules_keep_their_sentences(
    parts: Parts, agent_hotel: Identity, recipes: Mapping[str, Recipe]
) -> None:
    """Rice is not in the recording, so no option of the hotel's rice porridge holds it. The second option's milk
    and butter have a quantity Valio Aimo does not confirm: that sentence of the policy stays, word for word."""
    plan = plan_menu(parts.service, agent_hotel, _menu("rice_porridge", 40, MONDAY), recipes)
    confirmed, alternative = parts.service.get_offer(agent_hotel, plan.offer_id).options[:2]
    covered = (
        "2 of the 3 ingredients are covered in full: milk and butter. Rice is not in this demo's recording of Valio "
        "Aimo's data, so no price or stock is known for it: no option offers it. What this option holds arrives by "
        "Monday 16 Nov. An order that is not complete goes to a person."
    )
    unconfirmed = [rule.sentence for rule in alternative.decision.fired if rule.rule_id == "F-01"]

    first, second = _option_notes(plan)[:2]

    assert first == f"{_total(confirmed)} {covered} It needs the purchasing manager."
    assert len(unconfirmed) == 2 and all(each.endswith("is not confirmed by Valio Aimo.") for each in unconfirmed)
    assert second == f"{_total(alternative)} {covered} {' '.join(unconfirmed)} It needs the purchasing manager."
    assert not any(wrong in note for note in (first, second) for wrong in WRONG_WORDS)


def test_an_option_that_holds_every_ingredient_says_what_it_said(
    parts: Parts, agent_hotel: Identity, recipes: Mapping[str, Recipe]
) -> None:
    """The hotel's beef stew for 50 by Monday: one option, every line in full. Its note is the policy's sentence."""
    plan = plan_menu(parts.service, agent_hotel, _menu("beef_stew", 50, MONDAY), recipes)
    offer = parts.service.get_offer(agent_hotel, plan.offer_id)

    notes = _option_notes(plan)

    assert offer.options[0].fill_ratio == 1
    assert notes[0].endswith(offer.options[0].decision.sentence) and "ingredients are covered" not in notes[0]


# --- C3-F6: "for tomorrow" names the earliest date -----------------------------------------------------------------


def test_what_cannot_arrive_tomorrow_names_the_earliest_date_it_could_in_the_structure_and_in_words(
    demo_parts: Parts, agent_hotel: Identity, recipes: Mapping[str, Recipe]
) -> None:
    """Said on Thursday 12 Nov, "beef stew for 80 for tomorrow" is for Friday 13 Nov: nothing arrives by then.
    Whatever the offer does about it, each ingredient names Monday 16 Nov in the structure and in words. The
    exact sentences below are those of an offer that holds nothing for Friday and names the day in a note, as
    the offers code did when this was measured (15 Nov 2026, about 02:30). Once the offer holds the earliest
    date as an option of its own (decision B67, another lane), the ingredients are offered for Monday and say
    so: `test_an_ingredient_offered_for_a_later_day_than_asked_says_the_day_and_that_it_is_later`."""
    request = resolve(MenuAsk(text="beef stew for 80 for tomorrow"), recipes, DEMO_CLOCK.date()).request

    plan = plan_menu(demo_parts.service, agent_hotel, request, recipes)

    assert request.needed_by == FRIDAY
    assert [each.earliest_date for each in plan.dishes[0].ingredients] == [MONDAY] * 3
    assert all("Monday 16 Nov" in each.sentence for each in plan.dishes[0].ingredients)
    if not plan.cannot_be_sourced:  # the offer holds an option for the later date: said per ingredient
        later = "It arrives on Monday 16 Nov, later than the Friday 13 Nov asked for."
        assert all(each.sentence.endswith(later) for each in plan.dishes[0].ingredients)
        assert HELD_FOR_MONDAY in plan.notes
        return
    assert [(item.product_type, item.earliest_date) for item in plan.cannot_be_sourced] == [
        ("beef_chuck", MONDAY), ("cream", MONDAY), ("butter", MONDAY),
    ]
    assert {each.status for each in plan.dishes[0].ingredients} == {IngredientStatus.CANNOT_BE_SOURCED}
    chuck = plan.cannot_be_sourced[0].sentence
    assert chuck.startswith(
        "Cannot be sourced by Fri 13 Nov 2026: beef chuck: none of 7 products can be offered by Fri 13 Nov 2026 (2 "
        "order cut-off passed, 3 not deliverable, 2 delivered too late), and the earliest it could arrive is Monday "
        "16 Nov; beef (brisket): none of 9 products can be offered by Fri 13 Nov 2026 (1 order cut-off passed, 3 not "
        "deliverable, 3 delivered too late, 2 out of stock), and the earliest it could arrive is Monday 16 Nov; pork: "
        "none of its 106 products is in this demo's recording"
    )
    assert _ingredient(plan, "beef_chuck").sentence == chuck
    assert (
        "The earliest date in Valio Aimo's data on which beef chuck, cream and butter could arrive is Monday 16 Nov. "
        "Ask again for that date to get an offer."
    ) in plan.notes


def test_an_ingredient_outside_the_recording_names_no_date(
    parts: Parts, agent_hotel: Identity, recipes: Mapping[str, Recipe]
) -> None:
    plan = plan_menu(parts.service, agent_hotel, _menu("rice_porridge", 40, MONDAY), recipes)

    assert [(item.product_type, item.earliest_date) for item in plan.cannot_be_sourced] == [("rice", None)]
    assert "earliest" not in plan.cannot_be_sourced[0].sentence
    assert not any("earliest date" in note for note in plan.notes)


HELD_FOR_MONDAY = (
    "Beef chuck, cream and butter cannot arrive by Friday 13 Nov: the offer holds them for Monday 16 Nov, and a "
    "person must accept the later date."
)


class _OffersForMonday:
    """A gateway whose offers are built for Monday whatever day was asked: what the plan reads once the offer holds
    the earliest date as an alternative of its own (decision B67, the offers code's side of C3-F6)."""

    def __init__(self, service: object) -> None:
        self._service = service

    def __getattr__(self, name: str) -> object:
        return getattr(self._service, name)

    def create_menu_offer(self, identity: Identity, request: PurchaseRequest) -> Offer:
        return self._service.create_menu_offer(identity, request.model_copy(update={"needed_by": MONDAY}))


def test_an_ingredient_offered_for_a_later_day_than_asked_says_the_day_and_that_it_is_later(
    demo_parts: Parts, agent_hotel: Identity, recipes: Mapping[str, Recipe]
) -> None:
    plan = plan_menu(_OffersForMonday(demo_parts.service), agent_hotel, _menu("beef_stew", 80, FRIDAY), recipes)

    chuck = _ingredient(plan, "beef_chuck")

    assert chuck.status is IngredientStatus.ORDERED_AS_IN_RECIPE and chuck.earliest_date == MONDAY
    assert chuck.sentence.endswith("It arrives on Monday 16 Nov, later than the Friday 13 Nov asked for.")
    assert HELD_FOR_MONDAY in plan.notes


def test_everything_in_time_names_no_later_day(
    parts: Parts, agent_hotel: Identity, recipes: Mapping[str, Recipe]
) -> None:
    plan = plan_menu(parts.service, agent_hotel, _menu("beef_stew", 50, MONDAY), recipes)

    assert [each.earliest_date for each in plan.dishes[0].ingredients] == [None] * 3
    assert not any("later" in note and "cannot arrive" in note for note in plan.notes)
    assert not any("It arrives on" in each.sentence for each in plan.dishes[0].ingredients)


def test_the_earliest_day_of_a_line_with_no_product_is_read_from_the_offers_own_note() -> None:
    """The offer names that day in words only (`tta.offers.builder`), so it is read back from the words: the
    first day after the day asked that is written the same way. Another wording names no day."""
    note = (
        "Request line 2: nothing can arrive by Friday 13 Nov. The earliest delivery date in Valio's data for a "
        "product that otherwise fits is Monday 16 Nov, for 36 products: 461273, 461490 and 34 more."
    )
    offer = SimpleNamespace(options=(), notes=("Request line 1: no product can be offered.", note))
    reworded = SimpleNamespace(options=(), notes=("Request line 2: it could come some day next week.",))

    assert earliest_date(offer, 1, FRIDAY) == MONDAY
    assert earliest_date(offer, 0, FRIDAY) is None and earliest_date(offer, 1, None) is None
    assert earliest_date(reworded, 1, FRIDAY) is None and earliest_date(None, 1, FRIDAY) is None


# --- a sentence that names an ingredient, not a dish ---------------------------------------------------------------

ILLUSTRATIVE = "The recipes and their amounts per serving are ours and illustrative, not Valio Aimo's."


def test_a_sentence_that_names_an_ingredient_gets_the_dishes_of_ours_that_use_it(
    recipes: Mapping[str, Recipe]
) -> None:
    with pytest.raises(InvalidRequest) as refused:
        resolve(MenuAsk(text="plan next week's menu around cream, 60 guests"), recipes, DEMO_CLOCK.date())

    assert refused.value.detail == (
        "With cream we have: beef stew, creamy chicken pasta, salmon with rice and berry quark dessert. Name one "
        'with its servings, for example "beef stew for 60". ' + ILLUSTRATIVE
    )
    assert refused.value.extensions["ingredients_named"] == ["cream"]


def test_a_sentence_built_around_an_ingredient_no_recipe_uses_says_so_and_lists_the_dishes(
    recipes: Mapping[str, Recipe]
) -> None:
    with pytest.raises(InvalidRequest) as refused:
        resolve(MenuAsk(text="plan next week menu around chanterelles, 60 guests"), recipes, DEMO_CLOCK.date())

    assert refused.value.detail.startswith(
        'No recipe of ours uses "chanterelles". The dishes are: beef stew, creamy chicken pasta, '
    )
    assert refused.value.detail.endswith("berry quark dessert and chocolate cake. " + ILLUSTRATIVE)
    assert refused.value.extensions == {"built_around": "chanterelles"}


def test_an_ingredient_written_where_a_dish_goes_gets_its_dishes_and_an_unknown_dish_keeps_its_answer(
    recipes: Mapping[str, Recipe]
) -> None:
    with pytest.raises(InvalidRequest) as eggs:
        resolve(MenuAsk(text="eggs for 40"), recipes, DEMO_CLOCK.date())
    with pytest.raises(InvalidRequest) as tiramisu:
        resolve(MenuAsk(text="tiramisu with cream for 10"), recipes, DEMO_CLOCK.date())

    assert eggs.value.detail == (
        "With eggs we have: oven pancake, macaroni casserole, cheese omelette and chocolate cake. Name one with "
        'its servings, for example "oven pancake for 40". ' + ILLUSTRATIVE
    )
    assert tiramisu.value.detail.startswith('No recipe for "tiramisu with cream" in the recipe table. ')


@pytest.mark.parametrize("text", ["something nice", "what is the weather", "as usual"])
def test_a_sentence_that_names_neither_a_dish_nor_an_ingredient_keeps_its_question(
    recipes: Mapping[str, Recipe], text: str
) -> None:
    with pytest.raises(InvalidRequest) as refused:
        resolve(MenuAsk(text=text), recipes, DEMO_CLOCK.date())

    assert refused.value.detail.startswith("The sentence names no dish of the recipe table. The dishes are: ")
