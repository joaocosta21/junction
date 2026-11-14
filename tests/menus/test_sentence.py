"""A menu asked for in a sentence becomes the typed request, or a refusal with the question (task CK)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from tta.config import Settings
from tta.contracts.common import DataSource, Unit
from tta.contracts.errors import InvalidRequest
from tta.menus import Recipe
from tta.menus.offered import left_over, money
from tta.menus.sentence import MenuAsk, data_today, dish_list, later_recorded_note, resolve
from tta.valio import ReplayGateway

SATURDAY = date(2026, 11, 14)


def test_a_sentence_becomes_the_typed_request_and_says_what_was_read(recipes: Mapping[str, Recipe]) -> None:
    resolved = resolve(MenuAsk(text="lasagne for 50 and oven pancake for 50 by Monday"), recipes, SATURDAY)

    dishes = [(dish.dish_id, dish.servings) for dish in resolved.request.dishes]
    assert dishes == [("lasagne", 50), ("oven_pancake", 50)]
    assert resolved.request.needed_by == date(2026, 11, 16)
    assert resolved.read_as == "Read as: lasagne, 50 servings; oven pancake, 50 servings; by Monday 16 Nov."


def test_typed_dishes_alone_are_the_request_and_nothing_is_said_to_be_read(recipes: Mapping[str, Recipe]) -> None:
    ask = MenuAsk.model_validate({"dishes": [{"dish_id": "chocolate_cake", "servings": 2}], "require_confirmed": True})

    resolved = resolve(ask, recipes, SATURDAY)

    assert resolved.read_as is None and resolved.request.require_confirmed is True
    assert resolved.request.model_dump() == ask.model_dump(exclude={"text"})


def test_a_sentence_gives_the_day_to_typed_dishes_and_its_other_questions_do_not_stop_them(
    recipes: Mapping[str, Recipe]
) -> None:
    typed = {"dishes": [{"dish_id": "chocolate_cake", "servings": 2}]}

    by_monday = resolve(MenuAsk.model_validate({**typed, "text": "tiramisu by Monday"}), recipes, SATURDAY)
    no_dish = resolve(MenuAsk.model_validate({**typed, "text": "as usual"}), recipes, SATURDAY)

    assert by_monday.request.needed_by is None and by_monday.read_as is None  # the sentence names no dish: not read
    assert no_dish.read_as is None
    with pytest.raises(InvalidRequest, match="names 2 days"):
        resolve(MenuAsk.model_validate({**typed, "text": "chocolate cake on Friday or Monday"}), recipes, SATURDAY)


def test_one_serving_is_said_in_the_singular(recipes: Mapping[str, Recipe]) -> None:
    assert resolve(MenuAsk(text="a chocolate cake for one"), recipes, SATURDAY).read_as == (
        "Read as: chocolate cake, 1 serving."
    )


def test_the_dish_list_names_every_dish_once(recipes: Mapping[str, Recipe]) -> None:
    assert dish_list(recipes).endswith("cheese omelette, berry quark dessert and chocolate cake")
    assert dish_list(recipes).count(",") == len(recipes) - 2


def test_today_is_the_recordings_day_or_the_demo_clocks_in_replay() -> None:
    thursday = datetime.fromisoformat("2026-11-12T14:15:00+02:00")

    assert data_today(Settings.for_tests()) == SATURDAY
    assert data_today(Settings.for_tests(tta_demo_clock=thursday)) == date(2026, 11, 12)
    assert data_today(Settings.for_tests(tta_mode=DataSource.LIVE)) >= SATURDAY - SATURDAY.resolution * 400


def test_no_note_about_a_later_recording_without_a_replayed_offer(capture_demo, capture_sample) -> None:
    joined, alone = ReplayGateway(capture_demo.path), ReplayGateway(capture_sample.path)
    line = SimpleNamespace(product_id="460856")
    replayed = SimpleNamespace(source=DataSource.REPLAY, options=(SimpleNamespace(lines=(line,)),))
    live = SimpleNamespace(source=DataSource.LIVE, options=replayed.options)
    first_only = SimpleNamespace(source=DataSource.REPLAY, options=(SimpleNamespace(
        lines=(SimpleNamespace(product_id="463047"),)),))

    assert later_recorded_note(joined, None) is None and later_recorded_note(joined, live) is None
    assert later_recorded_note(alone, replayed) is None and later_recorded_note(joined, first_only) is None
    assert later_recorded_note(joined, replayed).startswith(
        "1 of the 1 products of this offer have their price and stock from the later recording (460856). 394 of"
    )


def _line(quantity: str, pack: str | None, unit: Unit | None = Unit.KG) -> SimpleNamespace:
    size = SimpleNamespace(value=None if pack is None else Decimal(pack), unit=unit)
    return SimpleNamespace(quantity=Decimal(quantity), pack_size=size)


def test_what_is_left_over_is_worked_out_only_from_a_pack_size_that_is_known_in_the_lines_unit() -> None:
    needed = Decimal("0.4")

    assert left_over([_line("1", "2")], needed, Unit.KG) == (
        " 0.4 kg is needed and the pack holds 2 kg, so 1.6 kg is left over."
    )
    assert left_over([_line("3", "0.2")], needed, Unit.KG) == (
        " 0.4 kg is needed and 3 packs hold 0.6 kg, so 0.2 kg is left over."
    )
    assert left_over([_line("2", "0.2")], needed, Unit.KG) == " 0.4 kg is needed and the packs hold exactly that."
    assert left_over([_line("1", None)], needed, Unit.KG) == ""  # the size is not known: nothing is worked out
    assert left_over([_line("1", "2", Unit.L)], needed, Unit.KG) == ""
    assert left_over([_line("1", "0.2")], needed, Unit.KG) == ""  # a partial fill is said elsewhere
    assert left_over([], needed, Unit.KG) == ""
    assert money(Decimal("1234.5")) == "€1,234.50"
