"""The fixed-rules reader asks instead of guessing, and never drops an exclusion (replan R4 and S8).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" and on Valio Aimo's answer
of 14 Nov 2026: "if you are not sure you need to flag it to the user to ask for his input". Each case below is a
reproduction of `AIMO/build/replan/A2b-review-preference-reader.md` (C1 to C4, H1, H3, M1, L2), of
`A5-rubric-score.md` #5, of `P2-scenarios.md` 2.5 item 7 or of `P4-noisy-data.md` M3. Clock: the recording's
instant, Saturday 14 Nov 2026.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from tta.agent.days import named_dates
from tta.agent.parser import ModelRequestParser
from tta.agent.rules_model import RuleModel
from tta.agent.rules_reader import NotReadByRules
from tta.agent.textcheck import TextFacts
from tta.api.wiring import Parts
from tta.contracts.agent import ReadingSource
from tta.contracts.common import AllergenStrictness, Identity, Preference, Unit
from tta.contracts.errors import InvalidRequest, SupplierUnavailable
from tta.contracts.ports import Clock

SATURDAY = date(2026, 11, 14)


@pytest.fixture(scope="session")
def rule_model(product_type_keys: tuple[str, ...]) -> RuleModel:
    return RuleModel.for_keys(product_type_keys)


@pytest.fixture
def rules_parser(make_parser: Callable[..., ModelRequestParser], rule_model: RuleModel, demo_clock: Clock) -> Any:
    return make_parser(rule_model, demo_clock)


def _refused(parser: ModelRequestParser, text: str, identity: Identity) -> NotReadByRules:
    with pytest.raises(NotReadByRules) as refused:
        parser.read(text, identity)
    return refused.value


# --- C1: an exclusion is never dropped -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "codes"),
    [
        ("30 kg of bread, must not contain sesame, strict", ("AS",)),
        ("30 kg of bread for a guest with gluten intolerance, strict", ("AW",)),
        ("20 kg of rice, nothing with soy, strict", ("AY",)),
        ("30 kg of bread, the patient is allergic: sesame, strict", ("AS",)),
        ("20 kg of rice, cannot have peanuts, strict", ("AP",)),
        ("20 kg of rice, can't have peanuts, strict", ("AP",)),
        ("30 kg of bread for coeliac patients, strict", ("AW",)),
        ("100 litres of oat drink, must not contain gluten, strict", ("AW",)),
        ("100 litres of oat drink, may not contain milk or soy, strict", ("AM", "AY")),
    ],
)
def test_an_exclusion_said_in_other_words_is_read(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str, codes: tuple[str, ...]
) -> None:
    line = rules_parser.parse_request(text, agent_hotel).lines[0]

    assert line.exclude_allergens == codes and line.allergen_strictness is AllergenStrictness.STRICT


@pytest.mark.parametrize(
    ("text", "named"),
    [
        ("30 kg of bread, sesame is a problem for one guest", "sesame"),
        ("200 litres of oat drink for the soy table", "soy"),
        ("30 kg of bread, one guest reacts to nuts", "nuts"),
        ("30 kg of bread, mind the allergies", "allergies"),
        ("100 litres of oat drink for a lactose intolerant guest", "intolerant"),
        ("100 litres of oat drink, we have an allergic guest", "allergic"),
    ],
)
def test_an_allergen_named_with_no_wording_the_rules_read_is_asked_about_never_dropped(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str, named: str
) -> None:
    refused = _refused(rules_parser, text, agent_hotel)

    assert named in refused.why and "?" in refused.ask


@pytest.mark.parametrize(
    "text",
    ["200 litres of soy drink", "10 kg of peanut butter", "20 litres of almond drink by Monday",
     "1,000 litres of lactose-free milk by Monday", "10 kg of rye bread"],
)
def test_an_allergen_word_that_names_the_product_is_not_an_exclusion_and_is_not_asked_about(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str
) -> None:
    assert rules_parser.parse_request(text, agent_hotel).lines[0].exclude_allergens == ()


def test_the_text_check_holds_a_model_to_the_same_new_wordings() -> None:
    facts = TextFacts.of("30 kg of bread, must not contain sesame; cannot have peanuts; for coeliac patients",
                         SATURDAY)

    assert facts.excluded == {"AS", "AP", "AW"}


# --- C2: a decimal is never read as thousands ------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "quantity"),
    [
        ("0.100 l of oat drink", Decimal("0.1")),
        ("0.500 kg of butter", Decimal("0.5")),
        ("0,250 kg of cheese", Decimal("0.25")),
        ("1,000 litres of milk", Decimal(1000)),
        ("1 000 l of milk", Decimal(1000)),
        ("1.5 kg of butter", Decimal("1.5")),
        ("1,5 kg of butter", Decimal("1.5")),
        ("1.000.000 l of milk", Decimal(1_000_000)),
    ],
)
def test_a_leading_zero_is_a_decimal_and_a_comma_or_a_space_still_groups_thousands(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str, quantity: Decimal
) -> None:
    assert rules_parser.parse_request(text, agent_hotel).lines[0].quantity == quantity


@pytest.mark.parametrize("text", ["1.250 kg of cheese", "1.000 litres of milk by Monday"])
def test_a_dot_before_three_digits_can_be_read_two_ways_and_is_asked(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str
) -> None:
    refused = _refused(rules_parser, text, agent_hotel)

    assert "two ways" in refused.why and " or " in refused.ask


def test_the_text_check_does_not_let_a_model_read_a_leading_zero_as_thousands() -> None:
    assert TextFacts.of("0.100 l of oat drink", SATURDAY).numbers == {Decimal("0.100")}


# --- C3: a longer product word is not the type it starts with or contains --------------------------------


@pytest.mark.parametrize(
    ("text", "word"),
    [
        ("10 kg of milk chocolate", "chocolate"),
        ("5 kg of milk powder", "powder"),
    ],
)
def test_a_word_right_after_the_product_type_that_the_rules_do_not_know_is_asked_about(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str, word: str
) -> None:
    refused = _refused(rules_parser, text, agent_hotel)

    assert word in refused.why and "?" in refused.ask


@pytest.mark.parametrize("text", ["10 litres of buttermilk", "5 kg of cheesecake", "10 kg of breadcrumbs"])
def test_a_longer_word_is_not_read_as_the_type_it_starts_with(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str
) -> None:
    assert "no product type" in _refused(rules_parser, text, agent_hotel).why


@pytest.mark.parametrize(
    ("text", "product_type"),
    [("200 l kaurajuomaa", None), ("200 litres of oat drinks", "plant_drink"), ("20 kg of cheeses", "cheese"),
     ("200 l juomaa", "plant_drink"), ("100 litres of milk for baking by Monday", "milk"),
     ("100 litres of milk delivered Monday", "milk"), ("100 litres of milk please", "milk")],
)
def test_an_inflected_type_word_and_a_plain_word_after_it_still_read(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str, product_type: str | None
) -> None:
    if product_type is None:
        assert "no product type" in _refused(rules_parser, text, agent_hotel).why
        return
    assert rules_parser.parse_request(text, agent_hotel).lines[0].product_type == product_type


# --- C4: a negated claim, label, preference or day is not read as the requirement ------------------------


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("100 litres of milk, not lactose-free", "not lactose-free"),
        ("200 litres of non-organic milk", "non-organic"),
        ("100 litres of oat drink, reliability does not matter", "reliability does not matter"),
        ("100 litres of oat drink, price doesn't matter", "price doesn't matter"),
        ("100 litres of oat drink by Monday at the earliest", "monday at the earliest"),
        ("200 litres of oat drink, not before Wednesday", "not before wednesday"),
        ("200 litres of oat drink after Wednesday", "after wednesday"),
        ("10 kg of coffee, fair trade or organic", "or organic"),
        ("100 litres of oat drink by Monday, not the cheapest", "not the cheapest"),
        ("100 litres of milk, never organic", "never organic"),
    ],
)
def test_a_negated_or_either_or_wording_is_asked_about(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str, said: str
) -> None:
    refused = _refused(rules_parser, text, agent_hotel)

    assert (said in refused.why or said.split()[0] in refused.why) and "?" in refused.ask


def test_plain_wordings_next_to_an_exclusion_still_read(
    rules_parser: ModelRequestParser, agent_hotel: Identity
) -> None:
    request = rules_parser.parse_request(
        "200 litres of organic oat drink, no milk or gluten, strict, most reliable, no later than Monday", agent_hotel
    )

    assert request.prefer is Preference.RELIABILITY and request.needed_by == date(2026, 11, 16)
    assert request.lines[0].exclude_allergens == ("AM", "AW")
    assert request.lines[0].required_labels == ("EU_ORGANIC_FARMING",)


# --- H1: a deadline the rules do not know is asked about; a date just past is past ------------------------


@pytest.mark.parametrize(
    "text",
    ["200 litres of oat drink, within 3 days", "200 litres of oat drink by the end of next week",
     "200 litres of oat drink this weekend", "200 litres of oat drink in 3 days", "200 l of oat drink next month"],
)
def test_a_deadline_the_rules_do_not_know_is_asked_about(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str
) -> None:
    refused = _refused(rules_parser, text, agent_hotel)

    assert "deadline" in refused.why and "?" in refused.ask


@pytest.mark.parametrize("text", ["200 litres of oat drink by 10.11.", "200 litres of oat drink yesterday",
                                  "200 litres of oat drink by 10 November"])
def test_a_day_just_past_is_a_past_day_not_next_year(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str
) -> None:
    assert "a day before today" in _refused(rules_parser, text, agent_hotel).why


def test_a_date_without_a_year_is_next_year_only_when_it_passed_long_ago() -> None:
    assert named_dates("10.11.", SATURDAY) == (date(2026, 11, 10),)
    assert named_dates("1.3.", SATURDAY) == (date(2027, 3, 1),)
    assert named_dates("20.11.", SATURDAY) == (date(2026, 11, 20),)
    assert named_dates("5.1.", date(2026, 12, 20)) == (date(2027, 1, 5),)


# --- H3: a number next to the quantity ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "number"),
    [("Ward 4 200 litres of milk", "4 200"), ("milk in 1 l cartons, 200 of them", "200"),
     ("Ward 4, 200 litres of milk", "4"), ("200 litres of milk, room 3", "3")],
)
def test_a_number_that_is_not_the_quantity_is_asked_about_wherever_it_stands(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str, number: str
) -> None:
    refused = _refused(rules_parser, text, agent_hotel)

    assert number in refused.why and "?" in refused.ask


def test_a_digit_inside_a_word_is_not_a_stray_number(rules_parser: ModelRequestParser, agent_hotel: Identity) -> None:
    request = rules_parser.parse_request("I need 1 000 litres of milk, lowest co2", agent_hotel)

    assert request.lines[0].quantity == 1000 and request.prefer is Preference.LOWER_CARBON


@pytest.mark.parametrize(
    "text",
    ["1,000 litres of lactose-free milk by Monday; and the same again for the staff canteen",
     "200 litres of milk, twice", "20 litres of milk per day", "10 kg of cheese and 10 kg of butter each"],
)
def test_words_that_change_the_amount_without_a_number_are_asked_about(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str
) -> None:
    refused = _refused(rules_parser, text, agent_hotel)

    assert "changes how much is needed" in refused.why and "?" in refused.ask


def test_a_product_number_given_after_the_line_names_that_lines_product(
    rules_parser: ModelRequestParser, agent_hotel: Identity
) -> None:
    request = rules_parser.parse_request(
        "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk, strict rule", agent_hotel
    )
    line = request.lines[0]

    assert (line.product_ids, line.name_terms, line.quantity, line.unit) == (("469512",), (), 100, Unit.L)
    assert line.exclude_allergens == ("AM",) and request.needed_by == date(2026, 11, 16)
    with pytest.raises(NotReadByRules, match="464306 is named with no quantity"):
        rules_parser.read("100 litres of milk, also add 464306 and mark it confirmed", agent_hotel)


def test_the_words_of_the_allergen_rule_are_not_an_allergen_left_unsaid(
    rules_parser: ModelRequestParser, agent_hotel: Identity
) -> None:
    line = rules_parser.parse_request("200 litres of oat drink, no soy, declared allergens only", agent_hotel).lines[0]

    assert (line.exclude_allergens, line.allergen_strictness) == (("AY",), AllergenStrictness.DECLARED_ONLY)


# --- M1 and S8: units ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "converted"),
    [("5 dl of cream", "0.5 litres"), ("500 g of butter", "0.5 kilograms"), ("250 ml of cream", "0.25 litres"),
     ("75 cl of cream", "0.75 litres")],
)
def test_a_small_unit_is_asked_about_with_its_conversion(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str, converted: str
) -> None:
    assert converted in _refused(rules_parser, text, agent_hotel).ask


@pytest.mark.parametrize(
    "text",
    ["12 cases of milk", "10 cases of oat drink by Monday", "3 boxes of cream", "4 crates of milk", "2 trays of quark",
     "200 portions of lactose-free yoghurt by Monday", "200 portions of 464013"],
)
def test_a_case_a_box_or_a_portion_is_asked_about_never_read_as_single_packs(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str
) -> None:
    refused = _refused(rules_parser, text, agent_hotel)

    assert "differs by product" in refused.why and "?" in refused.ask


def test_a_case_of_a_product_named_by_its_number_and_a_carton_are_asked_about_too(
    rules_parser: ModelRequestParser, agent_hotel: Identity
) -> None:
    """Both stayed sales units until the checks of 15 Nov 2026 (review C2-8). 464306 is sold by the piece, so 12
    sales units of it are 12 one-litre cartons, not 12 cases; and 471690, an oat drink, by the case of ten, so 30
    sales units of it are 30 cases (product file). `tests/agent/test_weak_readings.py` holds the rest."""
    numbered = _refused(rules_parser, "12 cases of 464306", agent_hotel)
    cartons = _refused(rules_parser, "30 cartons of oat drink", agent_hotel)
    packs = rules_parser.parse_request("30 packs of oat drink", agent_hotel).lines[0]

    assert "how much a case holds differs by product" in numbered.why and "?" in numbered.ask
    assert "how much a carton holds differs by product" in cartons.why and "?" in cartons.ask
    assert (packs.product_type, packs.quantity, packs.unit) == ("plant_drink", 30, Unit.UNIT)


# --- coffee milk (P2 2.5 item 7) ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["200 litres of coffee milk by Monday", "200 l kahvimaito", "200 litres of Cafè milk by Monday",
     "200 litres of lactose-free coffee milk"],
)
def test_coffee_milk_is_read_as_its_own_type(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str
) -> None:
    line = rules_parser.parse_request(text, agent_hotel).lines[0]

    assert (line.product_type, line.quantity, line.unit, line.name_terms) == ("coffee_milk", 200, Unit.L, ())


def test_milk_for_coffee_is_asked_about_and_plain_milk_stays_milk(
    rules_parser: ModelRequestParser, agent_hotel: Identity
) -> None:
    refused = _refused(rules_parser, "200 litres of milk for coffee", agent_hotel)

    assert "coffee milk" in refused.ask
    assert rules_parser.parse_request("200 litres of milk", agent_hotel).lines[0].product_type == "milk"


# --- P4 M3: no allergen rule given reads as strict, and says so -------------------------------------------


def test_an_exclusion_with_no_rule_at_all_reads_strict_and_the_reading_says_so(
    rules_parser: ModelRequestParser, agent_hotel: Identity
) -> None:
    reading = rules_parser.read("50 litres of gluten-free oat drink by Monday", agent_hotel)
    line = reading.request.lines[0]

    assert line.exclude_allergens == ("AW",) and line.allergen_strictness is AllergenStrictness.STRICT
    assert "No allergen rule was given" in reading.sentence and "strict, the safe reading" in reading.sentence
    assert "gluten" in reading.sentence


def test_a_rule_the_text_or_the_profile_gives_is_kept_and_nothing_is_said(
    rules_parser: ModelRequestParser, agent_hotel: Identity, agent_ward: Identity
) -> None:
    said = rules_parser.read("50 litres of oat drink, no gluten, declared only", agent_hotel)
    profile = rules_parser.read("50 litres of oat drink, no gluten", agent_ward)
    none = rules_parser.read("50 litres of oat drink", agent_hotel)

    assert said.request.lines[0].allergen_strictness is AllergenStrictness.DECLARED_ONLY
    assert profile.request.lines[0].allergen_strictness is None  # the ward's own rule applies
    assert none.request.lines[0].allergen_strictness is None
    assert all("No allergen rule" not in reading.sentence for reading in (said, profile, none))


# --- M1: with no model, what the rules cannot read is a question (422), not "service unavailable" (503) ----


def test_with_no_key_a_text_the_rules_cannot_read_is_a_question_to_the_person(
    parts: Parts, agent_hotel: Identity
) -> None:
    with pytest.raises(InvalidRequest) as asked:
        parts.service.read_request(agent_hotel, "5 dl of cream")
    with pytest.raises(InvalidRequest) as run_asked:
        parts.service.run_agent(agent_hotel, "Ward 4 200 litres of milk")

    detail = asked.value.detail
    assert not isinstance(asked.value, SupplierUnavailable) and asked.value.status_code == 422
    assert "nothing was guessed" in detail and "0.5 litres" in detail
    assert asked.value.extensions["question"] in detail and asked.value.extensions["read_by"] == "rule-based"
    assert "4 200" in run_asked.value.detail


def test_with_no_key_the_safe_strict_reading_travels_with_the_rules_sentence(
    parts: Parts, agent_hotel: Identity
) -> None:
    reading = parts.service.read_request(agent_hotel, "50 litres of gluten-free oat drink by Monday")

    assert reading.source is ReadingSource.RULE_BASED
    assert reading.sentence.startswith("Read by fixed rules, not by a model: no Gemini key is set.")
    assert "No allergen rule was given" in reading.sentence


# --- end to end, in replay at the recording's instant: the review's orders are no longer made --------------


def _offered(parts: Parts, identity: Identity, text: str) -> set[str]:
    offer = parts.service.create_offer(identity, parts.service.read_request(identity, text).request)
    return {line.product_id for option in offer.options for line in option.lines}


def test_must_not_contain_gluten_never_offers_the_oat_drink_that_declares_gluten(
    parts: Parts, agent_hotel: Identity
) -> None:
    """A2b C1: the same words used to end in 100 x 472145 ordered by the agent alone, a product that declares
    gluten (AW). Said either way, neither 472145 nor 470863 is offered."""
    declares_gluten = {"472145", "470863"}
    said_plainly = _offered(parts, agent_hotel, "100 litres of oat drink, no gluten, strict")
    said_otherwise = _offered(parts, agent_hotel, "100 litres of oat drink, must not contain gluten, strict")

    assert said_otherwise == said_plainly and not said_otherwise & declares_gluten
    assert "472145" in _offered(parts, agent_hotel, "100 litres of oat drink")  # it is offered when nothing is said


@pytest.mark.parametrize(
    "text",
    ["0.100 l of oat drink", "10 kg of milk chocolate", "100 litres of milk, not lactose-free",
     "200 litres of oat drink by 10.11.", "Ward 4 200 litres of milk", "100 litres of oat drink, reliability "
     "does not matter"],
)
def test_the_reviews_wrong_orders_are_not_placed(parts: Parts, agent_hotel: Identity, text: str) -> None:
    """A2b C2, C3, C4, H1, H3: each ended in an order, or an approval request, for something not asked for."""
    try:
        run = parts.service.run_agent(agent_hotel, text)
    except InvalidRequest as asked:
        assert asked.extensions["question"]
        return
    request = parts.service.read_request(agent_hotel, text).request  # only "0.100 l" is read: as 0.1 litres

    assert text == "0.100 l of oat drink" and request.lines[0].quantity == Decimal("0.1")
    ordered = [] if run.order_id is None else parts.service.get_order(agent_hotel, run.order_id).option.lines
    assert all(line.quantity == 1 for line in ordered)  # one pack covers 0.1 litres: never 100 of them


@pytest.mark.parametrize(
    ("digits", "why"),
    [("0.100.000", "not read as one number"), ("1.5.25", "not read as one number"), ("2000000", "at most 1,000,000"),
     ("0,0005", "at most 3 decimals"), ("1 5,5", "not read as one number")],
)
def test_digits_that_give_no_one_number_are_asked_about(
    rules_parser: ModelRequestParser, agent_hotel: Identity, digits: str, why: str
) -> None:
    refused = _refused(rules_parser, f"{digits} l of milk", agent_hotel)

    assert why in refused.why and "?" in refused.ask


def test_a_small_unit_with_digits_that_read_two_ways_is_asked_for_in_a_larger_unit(
    rules_parser: ModelRequestParser, agent_hotel: Identity
) -> None:
    refused = _refused(rules_parser, "1.250 g of butter", agent_hotel)

    assert '"g"' in refused.why and refused.ask == "What is the quantity in litres, kilograms or packs?"
