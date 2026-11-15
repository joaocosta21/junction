"""The reader of dish sentences (task CK): "I want to make a chocolate cake for 20 people" becomes a dish, its
servings and an optional day. A pure function over the dish names it is given; nothing is guessed: a dish that is
not in the table is named, servings that are missing or unclear are asked about."""

from __future__ import annotations

from datetime import date

import pytest

from tta.agent.dishes import DishRead, read_dishes

SATURDAY = date(2026, 11, 14)  # the recording's day
THURSDAY = date(2026, 11, 12)  # the demo clock's day
NAMES = {
    "chocolate_cake": ("chocolate cake", "suklaakakku"),
    "lasagne": ("lasagne",),
    "oven_pancake": ("oven pancake", "pannukakku"),
    "cheese_omelette": ("cheese omelette",),
    "berry_quark_dessert": ("berry quark dessert", "marjarahka"),
}


def _read(text: str, today: date = SATURDAY):
    return read_dishes(text, NAMES, today)


@pytest.mark.parametrize(
    ("text", "servings"),
    [
        ("I want to make a chocolate cake for 20 people", 20),
        ("chocolate cake for 20", 20),
        ("Chocolate Cake for 2 people", 2),
        ("a chocolate cake for twenty guests", 20),
        ("I want to make a chocolate cake for two", 2),
        ("chocolate cake for a hundred people", 100),
        ("chocolate cake for fifty", 50),
        ("suklaakakku for 12", 12),
        ("chocolate cakes for 200 servings", 200),
        ("20 servings of chocolate cake", 20),
        ("twelve portions of chocolate cake, please", 12),
    ],
)
def test_a_dish_and_its_servings_are_read(text: str, servings: int) -> None:
    reading = _read(text)

    assert reading.dishes == (DishRead("chocolate_cake", servings),)
    assert reading.unknown == () and reading.problems == () and reading.needed_by is None


def test_a_day_is_read_by_the_calendar_rule_of_the_request_reader() -> None:
    friday = _read("a chocolate cake for twenty guests on Friday")
    monday_from_thursday = _read("chocolate cake for 20 by Monday", THURSDAY)

    assert friday.dishes == (DishRead("chocolate_cake", 20),) and friday.needed_by == date(2026, 11, 20)
    assert monday_from_thursday.needed_by == date(2026, 11, 16)
    assert _read("chocolate cake for 20 by 2026-11-16").needed_by == date(2026, 11, 16)


def test_two_dishes_each_with_its_servings_and_one_day() -> None:
    reading = _read("lasagne for 50 and oven pancake for 50 by Monday")

    assert reading.dishes == (DishRead("lasagne", 50), DishRead("oven_pancake", 50))
    assert reading.needed_by == date(2026, 11, 16) and reading.problems == ()


def test_a_day_of_the_month_is_not_taken_for_servings() -> None:
    reading = _read("chocolate cake for 16 November")

    assert reading.dishes == (DishRead("chocolate_cake", None),)
    assert reading.needed_by == date(2026, 11, 16)
    assert reading.problems == ('How many servings of chocolate cake? Write, for example, "chocolate cake for 20".',)


@pytest.mark.parametrize(
    "text",
    ["what is the weather", "", "1000 litres of lactose-free milk by Monday", "something nice for the team"],
)
def test_a_sentence_that_names_no_dish_reads_as_nothing(text: str) -> None:
    assert _read(text) is None


def test_a_dish_that_is_not_in_the_table_is_named_and_never_matched_to_another() -> None:
    reading = _read("I want to make tiramisu for 10 people")
    both = _read("tiramisu for 10 and chocolate cake for 20")

    assert reading is not None and reading.dishes == () and reading.unknown == ("tiramisu",)
    assert both.dishes == (DishRead("chocolate_cake", 20),) and both.unknown == ("tiramisu",)
    assert _read("cheesecake for 10").unknown == ("cheesecake",)  # not the chocolate cake, not the cheese omelette
    assert _read("I want to bake something for 20").unknown == ("something",)


@pytest.mark.parametrize(
    "text",
    ["I want to make a chocolate cake", "chocolate cake for the team", "chocolate cake on Friday",
     "lasagne and chocolate cake"],
)
def test_missing_servings_are_asked_about(text: str) -> None:
    reading = _read(text)

    assert all(dish.servings is None for dish in reading.dishes)
    assert reading.problems[-1] == (
        'How many servings of chocolate cake? Write, for example, "chocolate cake for 20".'
    )


def test_one_number_after_two_dishes_is_not_shared_between_them() -> None:
    reading = _read("lasagne and oven pancake for 50")

    assert reading.dishes == (DishRead("lasagne", None), DishRead("oven_pancake", 50))
    assert reading.problems == ('How many servings of lasagne? Write, for example, "lasagne for 20".',)


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("chocolate cake for 2.5 people", "2.5"),
        ("chocolate cake for 1,000 people", "1,000"),
        ("chocolate cake for 20-25 people", "20-25"),
        ("chocolate cake for twenty-five people", "twenty-five"),
        ("chocolate cake for twenty five people", "twenty five"),
        ("chocolate cake for about 20 people", "about 20"),
        ("chocolate cake for 0 people", "0"),
        ("chocolate cake for 20000 people", "20000"),
        ("chocolate cake for a dozen people", "a dozen"),
    ],
)
def test_servings_that_are_not_one_whole_number_are_asked_about_never_rounded(text: str, said: str) -> None:
    reading = _read(text)

    assert reading.dishes == (DishRead("chocolate_cake", None),)
    assert reading.problems == (
        f'"{said}" is not read as a number of servings of chocolate cake. Write a whole number from 1 to 5,000 '
        'in digits, for example "chocolate cake for 20".',
    )


def test_a_dish_named_twice_is_asked_about() -> None:
    reading = _read("chocolate cake for 20 and chocolate cake for 30")

    assert reading.problems == (
        "Chocolate cake is named twice (20 and 30 servings). Name a dish once, with all its servings.",
    )


def test_two_days_and_a_day_that_is_no_date_are_asked_about() -> None:
    two = _read("chocolate cake for 20 on Friday or Monday")
    none = _read("chocolate cake for 20 by 31 February")
    past = _read("chocolate cake for 20 by 2026-11-10")

    assert two.needed_by is None and two.problems == (
        "The sentence names 2 days (Monday 16 Nov and Friday 20 Nov). Which day is it needed by?",
    )
    assert none.needed_by is None and none.problems == ('"31 february" is not a date. Which day is it needed by?',)
    assert past.needed_by is None and past.problems == (
        "Tuesday 10 Nov is in the past. Which day is it needed by?",
    )


def test_the_longest_dish_name_wins_and_a_name_inside_another_word_is_not_a_dish() -> None:
    names = {"cake": ("cake",), "chocolate_cake": ("chocolate cake",)}

    assert read_dishes("chocolate cake for 20", names, SATURDAY).dishes == (DishRead("chocolate_cake", 20),)
    assert read_dishes("pancake for 20", names, SATURDAY).dishes == ()


# --- an amount of money (lane FP-B) -------------------------------------------------------------------------


def test_an_amount_of_money_in_a_dish_sentence_is_asked_about_and_never_dropped() -> None:
    """A product request carries the most to spend ("under €100"); a menu plan does not yet, so the dish sentence
    is asked about instead of being planned with the amount left out."""
    reading = _read("I want to make a chocolate cake for 20 people by Monday, under €100")

    assert reading is not None and not reading.is_complete
    assert reading.dishes == (DishRead("chocolate_cake", 20),) and reading.needed_by == date(2026, 11, 16)
    assert reading.problems == (
        'The sentence gives an amount of money ("€100"), and a spend limit is not applied to a menu plan yet. Can '
        "you send it again without the amount? The plan states each option's total before tax, and above your limit "
        "per order or per day a person approves.",
    )


def test_a_dish_sentence_with_no_amount_of_money_is_read_as_before() -> None:
    assert _read("I want to make a chocolate cake for 20 people by Monday").problems == ()
