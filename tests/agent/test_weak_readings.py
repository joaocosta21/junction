"""Five weak readings of the fixed rules are asked about, or said in the reading (REVIEW C2-8 and C4-F9; lane FIX-R).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" and the 20% "what the agent
can decide alone": the reader's claim is that it asks instead of guessing. The checks of 15 Nov 2026 found five
readings that did not hold it. Each test below is one of their reproductions; clock: the recording's instant,
Saturday 14 Nov 2026. No model is called.
- "-5 litres of milk" was read as 5 litres (hotel and school);
- "50 cartons of lactose-free milk" was read as 50 sales units without a word. Of the 91 products of category
  10400 in the product file, 55 have the sales unit `KI` and 33 `ST`, counted on 15 Nov 2026. One sales unit of
  the oat drink 471690 (`KI`) is a case of ten 1-litre packs, one of the milk 464306 (`ST`) a single 1-litre
  pack: a carton is not a sales unit for sure;
- "under €1,000" was answered "What does 1,000 stand for?". Since lane FP-B such an amount is read as the most to
  spend on the request (`tests/agent/test_budget.py`); an amount that is not clearly that is still asked about;
- a Finnish sentence was answered "Which product is needed on line 1?";
- "5 KG of milk" was read as kilograms without a word, and the offer counts one-litre packs.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from tta.agent.brands import Brands
from tta.agent.held import ask_whoever_reads
from tta.agent.measures import LITRE_TYPES
from tta.agent.parser import ModelRequestParser
from tta.agent.rules_model import RuleModel
from tta.agent.unread import NotReadByRules, as_question
from tta.api import create_app
from tta.api.wiring import Parts
from tta.config import Settings
from tta.contracts.agent import Reading
from tta.contracts.common import AllergenStrictness, Identity, IdentityKind, Unit
from tta.contracts.ports import Clock

SATURDAY, MONDAY = date(2026, 11, 14), date(2026, 11, 16)
HOTEL, SCHOOL = "hotel-kitchen", "school-kitchen"
READ_BY_RULES = "Read by fixed rules, not by a model."
ASKED = "The fixed rules did not read this request, and nothing was guessed: "
# The allergen rule of a profile plays no part in these readings: none is set, so nothing here loads the policy.
NO_RULE: dict[str, AllergenStrictness] = {}

MINUS_ASK = (
    'Is 5 litres meant? Then write "5 litres" without the minus sign. Nothing was ordered: the rules only read what '
    "is needed now, never a return or a change to an earlier order."
)
PACK_ASK = "How many litres, kilograms or packs is that? Write the quantity in one of those units."
MONEY_ASK = (
    'Is {said} the most to spend on this request, before tax? Then write "under {said}". A price is not agreed in '
    "a request: every option of the offer states its total before tax."
)
USED = "is read as the most to spend on this request, before tax: an option above it goes to a person."
ENGLISH_ASK = "Can you write it in English? For example: 200 litres of oat drink by Monday."
SALES_UNITS = (
    "A sales unit is the pack Valio Aimo sells a product in: a single pack for some products, a case of several for "
    "others. For an exact amount, write litres or kilograms."
)


@pytest.fixture(scope="module")
def rules(product_type_keys: tuple[str, ...], demo_clock: Clock, brands: Brands) -> ModelRequestParser:
    """The fixed rules behind the parser, with the catalog's brands, as the gateway builds them."""
    return ModelRequestParser(
        model=RuleModel.for_keys(product_type_keys, brands), clock=demo_clock, product_type_keys=product_type_keys,
        profile_strictness=NO_RULE.get, brands=brands,
    )


def _agent(profile: str) -> Identity:
    return Identity(kind=IdentityKind.AGENT, id=f"agent:{profile}", display_name=profile, profile_id=profile)


def _asked(rules: ModelRequestParser, text: str, profile: str = HOTEL) -> NotReadByRules:
    with pytest.raises(NotReadByRules) as refused:
        rules.read(text, _agent(profile))
    return refused.value


def _read(rules: ModelRequestParser, text: str, profile: str = HOTEL) -> Reading:
    return rules.read(text, _agent(profile))


def _says(reading: Reading) -> str:
    """What the reading's sentence says after naming the fixed rules."""
    return reading.sentence.removeprefix(READ_BY_RULES).strip()


# --- 1. a minus is refused (C4-F9) -------------------------------------------------------------------------


@pytest.mark.parametrize("profile", [HOTEL, SCHOOL])
def test_minus_five_litres_is_asked_about_and_never_read_as_five(rules: ModelRequestParser, profile: str) -> None:
    refused = _asked(rules, "-5 litres of milk", profile)

    assert refused.why == 'it gives a number with a minus sign ("-5 litres"), and a quantity to order is above zero'
    assert refused.ask == MINUS_ASK
    assert as_question(refused).detail == f"{ASKED}{refused.why}. {MINUS_ASK}"


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("milk -5 litres", "-5 litres"),
        ("−5 litres of milk", "−5 litres"),  # the minus sign itself
        ("− 5 litres of milk", "− 5 litres"),  # nobody marks a list with it: a space changes nothing
        ("–5 litres of milk", "–5 litres"),  # an en dash typed for a minus
        ("minus 5 litres of milk", "minus 5 litres"),
        ("100 litres of milk and -5 kg of butter", "-5 kg"),
        ("200 litres of milk, -5", "-5"),
        ("-5 dl of cream", "-5 dl"),
    ],
)
def test_a_number_below_zero_is_asked_about_wherever_it_stands(
    rules: ModelRequestParser, text: str, said: str
) -> None:
    refused = _asked(rules, text)

    assert f'("{said}")' in refused.why and "minus sign" in refused.why and "?" in refused.ask


@pytest.mark.parametrize(
    ("text", "quantities"),
    [
        ("- 5 litres of milk", [Decimal(5)]),  # a dash and a space: a list mark
        ("- 5 litres of milk\n- 3 kg of butter", [Decimal(5), Decimal(3)]),
        ("milk - 5 litres", [Decimal(5)]),
        ("5 litres of lactose-free milk", [Decimal(5)]),
        ("100 litres of milk by 2026-11-20", [Decimal(100)]),
    ],
)
def test_a_dash_that_is_no_minus_reads_as_before(
    rules: ModelRequestParser, text: str, quantities: list[Decimal]
) -> None:
    assert [line.quantity for line in _read(rules, text).request.lines] == quantities


def test_a_range_is_still_asked_about_as_a_number_beside_the_quantity(rules: ModelRequestParser) -> None:
    assert "a number besides its quantity (10)" in _asked(rules, "10-12 litres of milk").why


def test_a_minus_is_asked_about_whoever_reads() -> None:
    with pytest.raises(NotReadByRules, match="minus sign"):
        ask_whoever_reads("-5 litres of milk", SATURDAY)


# --- 2. a pack word is asked about, or the reading says what it was taken to be (C2-8) -----------------------


def test_fifty_cartons_is_asked_about_and_never_read_as_fifty_sales_units(rules: ModelRequestParser) -> None:
    refused = _asked(rules, "50 cartons of lactose-free milk")

    assert refused.why == "line 1 asks for 50 cartons, and how much a carton holds differs by product"
    assert refused.ask == PACK_ASK


@pytest.mark.parametrize(
    ("text", "word"),
    [
        ("30 cartons of oat drink", "carton"),
        ("12 cases of milk", "case"),
        ("3 boxes of cream", "box"),
        ("4 crates of milk", "crate"),
        ("2 pallets of milk", "pallet"),
        # 464306 is sold by the piece and 471690 by the case of ten (product file): 12 sales units of the first
        # are 12 cartons, 50 of the second 50 cases. The product's number does not make a container a sales unit.
        ("12 cases of 464306", "case"),
        ("50 cartons of 471690", "carton"),
        ("2 pallets of 464306", "pallet"),
    ],
)
def test_a_container_is_asked_about_with_or_without_a_product_number(
    rules: ModelRequestParser, text: str, word: str
) -> None:
    refused = _asked(rules, text)

    assert f"how much a {word} holds differs by product" in refused.why and refused.ask == PACK_ASK


@pytest.mark.parametrize(
    ("text", "said", "quantity"),
    [
        ("50 packs of lactose-free milk", "50 packs", Decimal(50)),
        ("50 units of 464306", "50 units", Decimal(50)),
        ("12 bottles of mineral water", "12 bottles", Decimal(12)),
        ("1,000 pieces of 464306", "1,000 pieces", Decimal(1000)),
    ],
)
def test_a_quantity_in_packs_is_read_as_sales_units_and_the_reading_says_so(
    rules: ModelRequestParser, text: str, said: str, quantity: Decimal
) -> None:
    reading = _read(rules, text)
    line = reading.request.lines[0]

    assert (line.quantity, line.unit) == (quantity, Unit.UNIT)
    assert f'"{said}" is read as {quantity:f} sales units. {SALES_UNITS}' in _says(reading)


def test_fifty_packs_says_exactly_this(rules: ModelRequestParser) -> None:
    said = _says(_read(rules, "50 packs of lactose-free milk"))

    assert said == f'"50 packs" is read as 50 sales units. {SALES_UNITS}'


def test_a_quantity_in_litres_says_nothing_about_sales_units(rules: ModelRequestParser) -> None:
    assert _says(_read(rules, "50 litres of lactose-free milk")) == ""


# --- 3. a money limit in the sentence (C2-8) ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("1,000 litres of lactose-free milk by Monday for €1,000", "€1,000"),
        ("1,000 litres of lactose-free milk by Monday, 1000 euros", "1000 euros"),
        ("1,000 litres of milk at about €1,000", "€1,000"),
        ("1000 litres of milk, at least 1 000 €", "1 000 €"),
        ("1000 litres of milk for more than EUR 1000", "eur 1000"),
    ],
)
def test_an_amount_of_money_is_asked_about_with_a_sentence_that_helps(
    rules: ModelRequestParser, text: str, said: str
) -> None:
    """An amount with no word that makes it a limit is never dropped and never taken for one: the question says
    how to name the most to spend, and what the offer states either way."""
    refused = _asked(rules, text)

    assert refused.why == f'it gives an amount of money ("{said}") without saying that it is the most to spend'
    assert refused.ask == MONEY_ASK.format(said=said)


@pytest.mark.parametrize(
    ("text", "amount"),
    [
        ("1,000 litres of lactose-free milk by Monday, under €1,000", "€1,000"),
        ("1,000 litres of lactose-free milk by Monday, max 1000 euros", "€1,000"),
        ("1,000 litres of lactose-free milk by Monday with a budget of €1,000", "€1,000"),
        ("1,000 litres of milk under €1,000", "€1,000"),
        ("1000 litres of milk, at most 1 000 €", "€1,000"),
        ("1000 litres of milk for less than EUR 1000", "€1,000"),
        ("1000 litres of milk, a budget of 1000", "€1,000"),
    ],
)
def test_an_amount_named_as_a_limit_is_read_and_the_reading_says_how_it_is_used(
    rules: ModelRequestParser, text: str, amount: str
) -> None:
    """The sentences that were refused until lane FP-B: "a price limit in the sentence is not applied yet"."""
    reading = _read(rules, text)

    assert reading.request.max_net_eur == Decimal(1000)
    assert _says(reading).endswith(f"{amount} {USED}")


@pytest.mark.parametrize(
    "text",
    ["1000 litres of milk by Monday, no more than €1,000", "1000 litres of milk by Monday within a budget of "
     "€1,000", "1000 litres of organic milk, not above €1,000"],
)
def test_the_money_is_read_before_the_words_around_it_are_taken_for_something_else(
    rules: ModelRequestParser, text: str
) -> None:
    """ "No more than" used to be asked about as an exclusion, and "within" as a deadline."""
    assert _read(rules, text).request.max_net_eur == Decimal(1000)


def test_a_number_with_no_currency_and_no_budget_is_asked_about_as_before(rules: ModelRequestParser) -> None:
    refused = _asked(rules, "1000 litres of milk, max 1000")

    assert refused.ask.startswith("What does 1000 stand for?")


def test_a_pallet_named_after_the_euro_is_a_pallet_not_an_amount_of_money(rules: ModelRequestParser) -> None:
    assert "amount of money" not in _asked(rules, "2 EUR pallets of milk").why


def test_an_order_taken_back_is_still_named_first(rules: ModelRequestParser) -> None:
    assert '"cancel"' in _asked(rules, "200 litres of milk, cancel the order of €1,000").why


def test_an_unclear_amount_of_money_is_asked_about_whoever_reads() -> None:
    with pytest.raises(NotReadByRules, match="amount of money"):
        ask_whoever_reads("1,000 litres of milk for €1,000", SATURDAY)


# --- 4. another language (C2-8) ----------------------------------------------------------------------------


def test_a_finnish_sentence_is_answered_that_the_rules_read_english_only(rules: ModelRequestParser) -> None:
    refused = _asked(rules, "Tarvitsen 500 litraa laktoositonta maitoa maanantaiksi")

    assert refused.why == (
        'it looks like Finnish ("tarvitsen", "litraa", "laktoositonta"), and the fixed rules read English only for now'
    )
    assert refused.ask == ENGLISH_ASK


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("200 litraa kaurajuomaa maanantaiksi", "Finnish"),
        ("200 litraa laktoositonta maitoa maanantaiksi", "Finnish"),
        ("Maito laktoositon 1000 l — ma", "Finnish"),
        ("Jag behöver 500 liter laktosfri mjölk till måndag", "Swedish"),
    ],
)
def test_a_sentence_in_finnish_or_swedish_that_the_rules_cannot_read_names_the_language(
    rules: ModelRequestParser, text: str, language: str
) -> None:
    refused = _asked(rules, text)

    assert refused.why.startswith(f"it looks like {language} (") and refused.ask == ENGLISH_ASK


def test_one_foreign_word_in_a_sentence_changes_nothing(rules: ModelRequestParser) -> None:
    """One word is a product's name as often as a language: the question stays the one about the product."""
    assert "no product type" in _asked(rules, "200 l kaurajuomaa").why
    assert "no product type" in _asked(rules, "200 litres of Valio maito").why


def test_what_the_rules_do_read_of_finnish_is_read_as_before(rules: ModelRequestParser) -> None:
    coffee = _read(rules, "200 l kahvimaito").request.lines[0]
    drink = _read(rules, "200 l juomaa maanantaiksi, ei maitoa").request

    assert (coffee.product_type, coffee.quantity) == ("coffee_milk", 200)
    assert (drink.lines[0].product_type, drink.lines[0].exclude_allergens, drink.needed_by) == (
        "plant_drink", ("AM",), MONDAY
    )


def test_an_english_sentence_the_rules_cannot_read_keeps_its_own_question(rules: ModelRequestParser) -> None:
    assert _asked(rules, "20 kg of dragonfruit").ask.startswith("Which product is needed on line 1?")


# --- 5. a unit that does not fit (C2-8) --------------------------------------------------------------------


def test_five_kg_of_milk_is_read_by_weight_and_the_reading_says_so(rules: ModelRequestParser) -> None:
    reading = _read(rules, "5 KG of milk")
    line = reading.request.lines[0]

    assert (line.product_type, line.quantity, line.unit) == ("milk", 5, Unit.KG)
    assert _says(reading) == (
        '5 kg of milk is read by weight, as kilograms and not as litres. If litres are meant, write "5 litres".'
    )


@pytest.mark.parametrize(
    ("text", "note"),
    [
        ("10 kg of cream", "10 kg of cream is read by weight"),
        ("5 kg of oat drink", "5 kg of plant drink is read by weight"),
        ("0,5 kg of sour milk", "0.5 kg of sour milk is read by weight"),
    ],
)
def test_a_drink_asked_for_in_kilograms_says_it_is_read_by_weight(
    rules: ModelRequestParser, text: str, note: str
) -> None:
    assert note in _says(_read(rules, text))


@pytest.mark.parametrize("text", ["5 kg of butter", "5 litres of milk", "20 kg of natural yoghurt", "5 kg of 464306"])
def test_a_unit_that_fits_and_a_product_named_by_number_say_nothing(rules: ModelRequestParser, text: str) -> None:
    assert "by weight" not in _says(_read(rules, text))


def test_every_type_read_by_weight_on_request_is_a_type_of_the_table(product_type_keys: tuple[str, ...]) -> None:
    assert set(product_type_keys) >= LITRE_TYPES


# --- through the gateway, in replay with no key: what a caller of the REST route gets ------------------------

PARSE, RUN = "/v1/requests/parse", "/v1/agent/run"
ASKED_OVER_REST = [
    ("hotel-kitchen", "-5 litres of milk", "Is 5 litres meant?"),
    ("school-kitchen", "-5 litres of milk", "Is 5 litres meant?"),
    ("hotel-kitchen", "50 cartons of lactose-free milk", "How many litres, kilograms or packs is that?"),
    ("hotel-kitchen", "1,000 litres of lactose-free milk by Monday for \u20ac1,000", "Is \u20ac1,000 the most to"),
    ("hotel-kitchen", "Tarvitsen 500 litraa laktoositonta maitoa maanantaiksi", "Can you write it in English?"),
]


def test_over_rest_the_four_sentences_are_questions_and_the_agent_run_orders_nothing(
    settings: Settings, parts: Parts, without_other_surfaces: None
) -> None:
    with TestClient(create_app(settings, parts=parts)) as client:
        for profile, text, question in ASKED_OVER_REST:
            token = {"Authorization": f"Bearer demo-agent-{profile}"}
            read, ran = (client.post(route, json={"text": text}, headers=token) for route in (PARSE, RUN))

            for answer in (read, ran):
                problem = answer.json()
                assert (answer.status_code, problem["read_by"]) == (422, "rule-based"), text
                assert problem["question"].startswith(question) and problem["question"] in problem["detail"]
                assert "nothing was guessed" in problem["detail"]


def test_through_the_gateway_the_two_read_sentences_carry_their_unit_and_say_how_it_was_taken(
    settings: Settings, parts: Parts, without_other_surfaces: None
) -> None:
    """The REST route answers the typed request alone, so there the unit is what states the reading; the reading
    itself (`Reading`, which the shop page shows) says it in words, after naming who read."""
    hotel = _agent(HOTEL)
    with TestClient(create_app(settings, parts=parts)) as client:
        token = {"Authorization": "Bearer demo-agent-hotel-kitchen"}
        by_weight = client.post(PARSE, json={"text": "5 KG of milk"}, headers=token)
        in_packs = client.post(PARSE, json={"text": "50 packs of lactose-free milk"}, headers=token)

    assert (by_weight.status_code, by_weight.json()["lines"][0]["unit"]) == (200, "KG")
    assert (in_packs.status_code, in_packs.json()["lines"][0]["unit"]) == (200, "UNIT")
    assert by_weight.headers["TTA-Read-By"] == in_packs.headers["TTA-Read-By"] == "rule-based"
    assert parts.service.read_request(hotel, "5 KG of milk").sentence == (
        "Read by fixed rules, not by a model: no Gemini key is set. 5 kg of milk is read by weight, as kilograms "
        'and not as litres. If litres are meant, write "5 litres".'
    )
    assert parts.service.read_request(hotel, "50 packs of lactose-free milk").sentence == (
        'Read by fixed rules, not by a model: no Gemini key is set. "50 packs" is read as 50 sales units. '
        + SALES_UNITS
    )
