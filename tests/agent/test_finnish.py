"""Orders written in Finnish (and Swedish) read like the English scenarios, held to the same text check (task T18).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": Valio Aimo's customers
write Finnish. The rule of the text check is unchanged; only its tables know more words.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from tta.agent.days import named_dates
from tta.agent.parser import ModelRequestParser
from tta.agent.recorded import RecordedModel
from tta.agent.textcheck import TextFacts
from tta.contracts.common import Identity, Unit
from tta.contracts.errors import InvalidRequest
from tta.contracts.ports import Clock
from tta.contracts.request import PurchaseRequest

SATURDAY = date(2026, 11, 14)  # the date of tonight's capture
SUNDAY, MONDAY, TUESDAY = date(2026, 11, 15), date(2026, 11, 16), date(2026, 11, 17)
WEDNESDAY, FRIDAY = date(2026, 11, 18), date(2026, 11, 20)
MakeParser = Callable[..., ModelRequestParser]
Proposal = Callable[..., str]


def _without_words(request: PurchaseRequest) -> dict[str, Any]:
    """The typed request without the buyer's own words, which differ by language."""
    return request.model_dump(exclude={"lines": {"__all__": {"text"}}})


def _facts(text: str) -> TextFacts:
    return TextFacts.of(text, SATURDAY)


# --- the two Finnish sentences, from the recordings ---------------------------------------------------------


@pytest.mark.parametrize(
    ("finnish", "english", "asker"),
    [("finnish_1", "scenario_1", "agent_hotel"), ("finnish_2", "scenario_2", "agent_ward")],
)
def test_a_finnish_sentence_reads_to_the_same_typed_request_as_its_english_scenario(
    recorded_model: RecordedModel, make_parser: MakeParser, demo_clock: Clock, texts: dict[str, str],
    request: pytest.FixtureRequest, finnish: str, english: str, asker: str,
) -> None:
    parser = make_parser(recorded_model, demo_clock)
    identity: Identity = request.getfixturevalue(asker)

    in_finnish = parser.read(texts[finnish], identity)
    in_english = parser.read(texts[english], identity)

    assert _without_words(in_finnish.request) == _without_words(in_english.request)
    assert all(line.text == texts[finnish] for line in in_finnish.request.lines)
    assert in_finnish.request.needed_by == MONDAY


def test_the_finnish_sentences_say_by_themselves_what_their_readings_say(texts: dict[str, str]) -> None:
    milk, plant_drink = _facts(texts["finnish_1"]), _facts(texts["finnish_2"])

    assert (milk.numbers, milk.units, milk.excluded, milk.dates) == (
        frozenset({Decimal(1000)}), frozenset({Unit.L}), frozenset(), (MONDAY,)
    )
    assert not milk.asks_for_confirmed  # "laktoositonta" is a claim, never an allergen exclusion
    assert (plant_drink.numbers, plant_drink.units, plant_drink.excluded, plant_drink.dates) == (
        frozenset({Decimal(200)}), frozenset({Unit.L}), frozenset({"AM", "AW"}), (MONDAY,)
    )
    assert plant_drink.asks_for_confirmed


def test_a_finnish_sentence_whose_reading_has_the_wrong_quantity_is_refused(
    scripted: Any, make_parser: MakeParser, proposal: Proposal, demo_clock: Clock, agent_hotel: Identity,
    texts: dict[str, str],
) -> None:
    wrong = proposal(quantity=100, required_claims=["FREE_FROM_LACTOSE"])
    model = scripted(extracts=[wrong, wrong])

    with pytest.raises(InvalidRequest) as refused:
        make_parser(model, demo_clock).read(texts["finnish_1"], agent_hotel)

    assert refused.value.extensions["faults"] == ["lines[0].quantity"]
    assert "the reading did not match the text" in refused.value.detail
    assert len(model.extract_calls) == 2  # asked once more, as for any answer that does not validate


def test_a_finnish_sentence_whose_reading_leaves_out_an_exclusion_is_refused(
    scripted: Any, make_parser: MakeParser, proposal: Proposal, demo_clock: Clock, agent_ward: Identity,
    texts: dict[str, str],
) -> None:
    only_milk = proposal(product_type="plant_drink", quantity=200, exclude_allergens=["AM"], require_confirmed=True)

    with pytest.raises(InvalidRequest) as refused:
        make_parser(scripted(extracts=[only_milk, only_milk]), demo_clock).read(texts["finnish_2"], agent_ward)

    assert refused.value.extensions["faults"] == ["lines[0].exclude_allergens"]


# --- days -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "day"),
    [
        ("maitoa maanantaiksi", MONDAY),
        ("maitoa maanantaihin mennessä", MONDAY),
        ("maitoa maanantaina", MONDAY),
        ("Maito laktoositon 1000 l — ma", MONDAY),
        ("Maito 1000 l, ma.", MONDAY),
        ("MA: maito 1000 l", MONDAY),
        ("kerma 10 l ti", TUESDAY),
        ("kerma 10 l ke", WEDNESDAY),
        ("kerma 10 l pe", FRIDAY),
        ("kerma 10 l su", SUNDAY),
        ("200 liter havredryck till måndag", MONDAY),
        ("200 liter havredryck på fredag", FRIDAY),
        ("200 liter havredryck senast måndagen", MONDAY),
    ],
)
def test_a_finnish_or_swedish_weekday_is_the_first_such_day_after_today(text: str, day: date) -> None:
    assert named_dates(text, SATURDAY) == (day,)


@pytest.mark.parametrize(
    "text",
    ["10 kg of chicken, allergic to eggs", "the a la carte menu needs 5 kg of butter", "laktoositon maito 10 l"],
)
def test_two_letter_words_that_are_also_english_or_french_are_not_read_as_days(text: str) -> None:
    assert named_dates(text, SATURDAY) == ()  # "to" and "la" stand for Thursday and Saturday only in Finnish


@pytest.mark.parametrize(
    ("text", "day"),
    [("leveranser 3 mars", date(2027, 3, 3)), ("1 maj", date(2027, 5, 1)), ("20 november", FRIDAY),
     ("20. marraskuuta", FRIDAY), ("16.11.", MONDAY)],
)
def test_swedish_and_finnish_months_are_read(text: str, day: date) -> None:
    assert named_dates(text, SATURDAY) == (day,)


# --- units, exclusions and confirmed data -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "unit"),
    [
        ("1000 litraa maitoa", Unit.L), ("5 litran pakkaus", Unit.L), ("200 liter havredryck", Unit.L),
        ("10 kiloa voita", Unit.KG), ("10 kilo smör", Unit.KG),
        ("12 kpl jogurttia", Unit.UNIT), ("6 pakkausta", Unit.UNIT), ("3 laatikkoa", Unit.UNIT),
        ("4 säkkiä jauhoja", Unit.UNIT), ("2 kartonkia", Unit.UNIT), ("12 styck", Unit.UNIT),
        ("6 förpackningar", Unit.UNIT), ("4 flaskor", Unit.UNIT),
    ],
)
def test_finnish_and_swedish_unit_words_are_read(text: str, unit: Unit) -> None:
    assert unit in _facts(text).units


@pytest.mark.parametrize(
    ("text", "codes"),
    [
        ("maidotonta kasvijuomaa", {"AM"}),
        ("maidoton ja gluteeniton", {"AM", "AW"}),
        ("gluteenitonta leipää", {"AW"}),
        ("ei pähkinöitä", {"AN"}),
        ("pähkinätön", {"AN"}),
        ("ei maitoa eikä kananmunaa", {"AM", "AE"}),
        ("ilman gluteenia", {"AW"}),
        ("gluteenivapaa leipä", {"AW"}),
        ("maitovapaa", {"AM"}),
        ("ei selleriä, ei sinappia", {"BC", "BM"}),
        ("mantelitonta", {"SA"}),
        ("mjölkfri havredryck", {"AM"}),
        ("glutenfri och nötfri", {"AW", "AN"}),
        ("utan mjölk och ägg", {"AM", "AE"}),
        ("inga nötter", {"AN"}),
        ("ingen soja", {"AY"}),
        ("fri från gluten", {"AW"}),
    ],
)
def test_finnish_and_swedish_exclusions_are_read(text: str, codes: set[str]) -> None:
    assert _facts(text).excluded == frozenset(codes)


@pytest.mark.parametrize(
    "text",
    ["laktoositon maito", "laktoositonta maitoa", "laktosfri mjölk", "maito 1000 l", "mjölk 200 liter"],
)
def test_lactose_free_and_plain_milk_are_not_exclusions_in_finnish_or_swedish(text: str) -> None:
    assert _facts(text).excluded == frozenset()


@pytest.mark.parametrize(
    ("text", "asks"),
    [
        ("vain vahvistetut tiedot", True), ("vain varmistetut tiedot", True), ("endast bekräftade uppgifter", True),
        ("bekräftad lagerstatus", True), ("maitoa maanantaiksi", False), ("havredryck till måndag", False),
    ],
)
def test_asking_for_confirmed_data_is_read_in_finnish_and_swedish(text: str, asks: bool) -> None:
    assert _facts(text).asks_for_confirmed is asks


@pytest.mark.parametrize(("text", "value"), [("1 000 litraa", Decimal(1000)), ("1,5 kiloa", Decimal("1.5"))])
def test_finnish_numbers_written_as_digits_are_read(text: str, value: Decimal) -> None:
    assert value in _facts(text).numbers
