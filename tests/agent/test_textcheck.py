"""What the buyer's text itself says, read without a model: the facts a model's reading is held to (task FIX-9).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": a number, a unit, a day,
an allergen or a product number the reading gives must be one the text gives.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tta.agent import days
from tta.agent.days import helsinki_date, named_dates
from tta.agent.textcheck import TextFacts
from tta.contracts.common import Unit

SATURDAY = date(2026, 11, 14)  # the date of tonight's capture
SUNDAY, MONDAY = date(2026, 11, 15), date(2026, 11, 16)


def _facts(text: str, today: date = SATURDAY) -> TextFacts:
    return TextFacts.of(text, today)


# --- numbers ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("1,000 litres of milk", Decimal(1000)),
        ("1 000 litres of milk", Decimal(1000)),
        ("1 000 litres of milk", Decimal(1000)),
        ("1000 litres of milk", Decimal(1000)),
        ("1000l of milk", Decimal(1000)),
        ("1.5 kg of butter", Decimal("1.5")),
        ("1,5 kg of butter", Decimal("1.5")),
        ("12.5 kg of ketchup", Decimal("12.5")),
        ("1,000.50 litres", Decimal("1000.50")),
        ("a thousand litres of oat drink", Decimal(1000)),
        ("two hundred litres of oat drink", Decimal(200)),
        ("twenty-five kilos of flour", Decimal(25)),
        ("one case of tomatoes", Decimal(1)),
    ],
)
def test_a_number_is_found_however_it_is_written(text: str, value: Decimal) -> None:
    assert value in _facts(text).numbers


def test_a_number_that_is_not_in_the_text_is_not_found() -> None:
    numbers = _facts("1,000 litres of lactose-free milk by Monday").numbers

    assert Decimal(10000) not in numbers and Decimal(100) not in numbers


def test_a_text_with_no_number_has_none() -> None:
    assert _facts("Some milk for Monday").numbers == frozenset()


# --- units ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "unit"),
    [
        ("200 litres", Unit.L), ("200 liters", Unit.L), ("200 l", Unit.L), ("200L", Unit.L), ("200 litraa", Unit.L),
        ("10 kg", Unit.KG), ("10kg", Unit.KG), ("10 kilos", Unit.KG), ("10 kiloa", Unit.KG),
        ("40 units", Unit.UNIT), ("40 pieces", Unit.UNIT), ("40 packs", Unit.UNIT), ("40 cartons", Unit.UNIT),
        ("40 cases", Unit.UNIT), ("40 kpl", Unit.UNIT),
    ],
)
def test_a_unit_word_names_its_unit(text: str, unit: Unit) -> None:
    assert _facts(text).units == {unit}


def test_a_text_with_no_unit_word_names_no_unit() -> None:
    assert _facts("40 of product 464013").units == frozenset()


# --- allergens the text excludes --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "codes"),
    [
        ("no milk, no gluten", {"AM", "AW"}),
        ("without milk or gluten", {"AM", "AW"}),
        ("milk-free and gluten free", {"AM", "AW"}),
        ("free from eggs, nuts and sesame", {"AE", "AN", "AS"}),
        ("allergic to eggs", {"AE"}),
        ("for a peanut allergy", {"AP"}),
        ("no traces of tree nuts", {"AN"}),
        ("dairy-free", {"AM"}),
        ("no soya", {"AY"}),
        ("ilman maitoa", {"AM"}),
        ("maidoton ja gluteeniton", {"AM", "AW"}),
    ],
)
def test_an_exclusion_is_found_however_it_is_said(text: str, codes: set[str]) -> None:
    assert _facts(f"20 litres of oat drink, {text}").excluded == codes


@pytest.mark.parametrize(
    "text",
    [
        "1,000 litres of lactose-free milk by Monday",  # a claim, never an allergen exclusion
        "200 litres of a milk substitute by Monday",
        "10 kg of butter, no later than Monday",
        "10 litres of milk, no sugar",
    ],
)
def test_a_claim_or_a_mention_is_not_an_exclusion(text: str) -> None:
    assert _facts(text).excluded == frozenset()


# --- confirmed data, product numbers ----------------------------------------------------------------------


def test_confirmed_data_is_asked_for_only_when_the_text_says_so() -> None:
    assert _facts("200 litres; confirmed data only").asks_for_confirmed is True
    assert _facts("200 litres of oat drink").asks_for_confirmed is False


def test_a_product_number_is_a_whole_token_never_a_piece_of_a_number() -> None:
    tokens = _facts("1,000 units of product 464013, and 12 of 464014,464020 (or #470187)").id_tokens

    assert {"464013", "464014", "464020", "470187"} <= tokens
    assert "1" not in tokens and "000" not in tokens and "4640" not in tokens


# --- the calendar rule ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "today", "expected"),
    [
        ("by Monday", SATURDAY, (MONDAY,)),
        ("by Monday", SUNDAY, (MONDAY,)),
        ("by Monday", MONDAY, (date(2026, 11, 23),)),  # the first such day after today
        ("next Friday", SATURDAY, (date(2026, 11, 20),)),
        ("for today", SATURDAY, (SATURDAY,)),
        ("for tomorrow", SATURDAY, (SUNDAY,)),
        ("the day after tomorrow", SATURDAY, (MONDAY,)),
        ("maanantaiksi", SATURDAY, (MONDAY,)),
        ("by 2026-11-20", SATURDAY, (date(2026, 11, 20),)),
        ("by 20.11.", SATURDAY, (date(2026, 11, 20),)),
        ("by 20.11.2026", SATURDAY, (date(2026, 11, 20),)),
        ("by 20/11/2026", SATURDAY, (date(2026, 11, 20),)),
        ("by 20 November", SATURDAY, (date(2026, 11, 20),)),
        ("by November 20th", SATURDAY, (date(2026, 11, 20),)),
        ("by 3 January", SATURDAY, (date(2027, 1, 3),)),  # no year: the next such date
        ("1.5 kg of butter, 1/2 litre of cream", SATURDAY, ()),  # a decimal or a fraction is not a date
        ("10 litres of milk", SATURDAY, ()),
        ("sun-dried tomatoes", SATURDAY, ()),
    ],
)
def test_the_day_a_text_names_follows_the_parsers_calendar_rule(
    text: str, today: date, expected: tuple[date, ...]
) -> None:
    assert named_dates(text, today) == expected


def test_today_is_the_date_in_helsinki() -> None:
    # 23:30 UTC on Friday 13 Nov is already Saturday 14 Nov in Helsinki (UTC+2 in winter).
    assert helsinki_date(datetime(2026, 11, 13, 23, 30, tzinfo=UTC)) == SATURDAY
    assert helsinki_date(datetime(2026, 11, 14, 2, 52, tzinfo=timezone(timedelta(hours=2)))) == SATURDAY
    # In summer Helsinki is UTC+3: 21:30 UTC on 1 Jul is 00:30 on 2 Jul.
    assert helsinki_date(datetime(2026, 7, 1, 21, 30, tzinfo=UTC)) == date(2026, 7, 2)


@pytest.mark.parametrize(
    "instant",
    [datetime(2026, 3, 29, 0, 59, tzinfo=UTC), datetime(2026, 3, 29, 1, 0, tzinfo=UTC),
     datetime(2026, 10, 25, 0, 59, tzinfo=UTC), datetime(2026, 10, 25, 1, 0, tzinfo=UTC),
     datetime(2026, 11, 13, 22, 30, tzinfo=UTC), datetime(2026, 6, 30, 21, 30, tzinfo=UTC)],
)
def test_without_the_time_zone_database_the_eu_rule_gives_the_same_offset(instant: datetime) -> None:
    assert days.eu_helsinki_offset(instant) == instant.astimezone(days.helsinki_zone()).utcoffset()


def test_a_time_with_no_offset_has_no_date_in_helsinki() -> None:
    with pytest.raises(ValueError):
        helsinki_date(datetime(2026, 11, 14, 12, 0))


def test_a_date_that_does_not_exist_is_not_named() -> None:
    assert named_dates("by 31.2. or by 30 February", SATURDAY) == ()


def test_without_the_time_zone_database_helsinki_falls_back_on_the_eu_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(key: str) -> None:
        raise days.ZoneInfoNotFoundError(key)

    monkeypatch.setattr(days, "ZoneInfo", missing)
    assert days.helsinki_zone.__wrapped__() is None
    monkeypatch.setattr(days, "helsinki_zone", lambda: None)

    assert helsinki_date(datetime(2026, 11, 13, 23, 30, tzinfo=UTC)) == SATURDAY
    assert helsinki_date(datetime(2026, 7, 1, 21, 30, tzinfo=UTC)) == date(2026, 7, 2)
