"""An amount of money in the sentence is read as the most to spend on that one request (lane FP-B).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": "1,000 litres of lactose-free
milk by Monday, under €1,000" used to be refused, because the typed request had no place for the amount. It has one
now (`PurchaseRequest.max_net_eur`, euros before tax), the reading says how the amount is used, and whatever is
not clearly one amount in euros with a word that makes it a limit is still asked about, never guessed. Clock: the
recording's instant, Saturday 14 Nov 2026. No model is called, except the scripted one of the last tests.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from tta.agent.brands import Brands
from tta.agent.held import ask_whoever_reads
from tta.agent.parser import ModelRequestParser, ReadingFailedChecks
from tta.agent.rules_model import RuleModel
from tta.agent.unread import NotReadByRules
from tta.contracts.agent import Reading
from tta.contracts.common import AllergenStrictness, Identity, IdentityKind, Unit
from tta.contracts.ports import Clock

SATURDAY, MONDAY = date(2026, 11, 14), date(2026, 11, 16)
HOTEL = "hotel-kitchen"
READ_BY_RULES = "Read by fixed rules, not by a model."
NO_RULE: dict[str, AllergenStrictness] = {}
AGENT = Identity(kind=IdentityKind.AGENT, id=f"agent:{HOTEL}", display_name=HOTEL, profile_id=HOTEL)
USED = "is read as the most to spend on this request, before tax: an option above it goes to a person."


@pytest.fixture(scope="module")
def rules(product_type_keys: tuple[str, ...], demo_clock: Clock, brands: Brands) -> ModelRequestParser:
    return ModelRequestParser(
        model=RuleModel.for_keys(product_type_keys, brands), clock=demo_clock, product_type_keys=product_type_keys,
        profile_strictness=NO_RULE.get, brands=brands,
    )


def _read(rules: ModelRequestParser, text: str) -> Reading:
    return rules.read(text, AGENT)


def _asked(rules: ModelRequestParser, text: str) -> NotReadByRules:
    with pytest.raises(NotReadByRules) as refused:
        rules.read(text, AGENT)
    return refused.value


def _says(reading: Reading) -> str:
    return reading.sentence.removeprefix(READ_BY_RULES).strip()


# --- 1. read -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "amount"),
    [
        ("1,000 litres of lactose-free milk by Monday, under €1,000", "1000"),
        ("1,000 litres of lactose-free milk by Monday, max 1000 euros", "1000"),
        ("1,000 litres of lactose-free milk by Monday with a budget of €1,000", "1000"),
        ("1,000 litres of lactose-free milk by Monday, no more than €1,000", "1000"),
        ("1,000 litres of lactose-free milk by Monday within a budget of 1,000 euros", "1000"),
        ("1,000 litres of lactose-free milk by Monday for less than 800 €", "800"),
        ("1,000 litres of lactose-free milk by Monday, at most 1 000 €", "1000"),
        ("1,000 litres of lactose-free milk by Monday, not above EUR 1000", "1000"),
        ("1,000 litres of lactose-free milk by Monday, up to 999,50 €", "999.50"),
        ("1,000 litres of lactose-free milk by Monday, below €999.50", "999.50"),
        ("1,000 litres of lactose-free milk by Monday, a budget of 1000", "1000"),
        ("1,000 litres of lactose-free milk by Monday, budget: 1000 eur", "1000"),
        ("1,000 litres of lactose-free milk by Monday, our budget is €1,000", "1000"),
        ("1,000 litres of lactose-free milk by Monday, the total must stay under €1,000", "1000"),
        ("1,000 litres of lactose-free milk by Monday with a €1,000 budget", "1000"),
        ("1,000 litres of lactose-free milk by Monday, 1000 euros max", "1000"),
        ("Under €1,000: 1,000 litres of lactose-free milk by Monday", "1000"),
    ],
)
def test_an_amount_in_euros_with_a_limit_word_is_the_most_to_spend_on_the_request(
    rules: ModelRequestParser, text: str, amount: str
) -> None:
    request = _read(rules, text).request
    line = request.lines[0]

    assert request.max_net_eur == Decimal(amount)
    # Nothing else of the reading moves: the product, the quantity, the claim and the day are the brief's own.
    assert (line.product_type, line.quantity, line.unit) == ("milk", Decimal(1000), Unit.L)
    assert line.required_claims == ("FREE_FROM_LACTOSE",) and line.name_terms == () and line.exclude_allergens == ()
    assert request.needed_by == MONDAY and len(request.lines) == 1


def test_the_reading_says_the_amount_and_how_it_is_used(rules: ModelRequestParser) -> None:
    said = _says(_read(rules, "200 litres of lactose-free milk by Monday, under €400"))

    assert said == f"€400 {USED}"


def test_an_amount_with_cents_is_said_with_its_cents(rules: ModelRequestParser) -> None:
    said = _says(_read(rules, "200 litres of lactose-free milk by Monday, up to 399,50 €"))

    assert said == f"€399.50 {USED}"


def test_a_request_with_no_amount_carries_none_and_says_nothing_about_one(rules: ModelRequestParser) -> None:
    reading = _read(rules, "200 litres of lactose-free milk by Monday")

    assert reading.request.max_net_eur is None and "most to spend" not in reading.sentence


def test_the_amount_is_for_the_whole_request_of_several_lines(rules: ModelRequestParser) -> None:
    request = _read(rules, "200 litres of milk and 5 kg of butter by Monday, under €600").request

    assert request.max_net_eur == Decimal(600)
    assert [(line.product_type, line.quantity) for line in request.lines] == [
        ("milk", Decimal(200)), ("butter", Decimal(5)),
    ]


def test_the_words_of_the_amount_are_not_taken_for_an_exclusion_a_deadline_or_a_product(
    rules: ModelRequestParser,
) -> None:
    """ "No more than" is no exclusion, "within" no deadline, and "under" names no product after "milk"."""
    for text in ("200 litres of milk no more than €400", "200 litres of milk within a budget of €400",
                 "200 litres of milk under €400"):
        request = _read(rules, text).request

        assert request.max_net_eur == Decimal(400) and request.lines[0].name_terms == ()
        assert request.lines[0].exclude_allergens == () and request.needed_by is None


# --- 2. still asked about ------------------------------------------------------------------------------------

TOTALS = "every option of the offer states its total before tax."


@pytest.mark.parametrize(
    ("text", "why", "ask"),
    [
        (
            "200 litres of milk under €2 a litre",
            'it gives an amount of money per unit ("€2 a litre"), and a limit on a unit price is not applied',
            'What is the most to spend on the whole request, before tax? Write it as "under €400". Every option of '
            "the offer states each product's unit price and its total before tax.",
        ),
        (
            "200 litres of milk, max 2 euros per litre",
            'it gives an amount of money per unit ("2 euros per litre"), and a limit on a unit price is not applied',
            'What is the most to spend on the whole request, before tax? Write it as "under €400". Every option of '
            "the offer states each product's unit price and its total before tax.",
        ),
        (
            "200 litres of milk under €400 and 5 kg of butter under €50",
            'it gives more than one amount of money ("€400" and "€50")',
            "Which one amount is the most to spend on the whole request, before tax? Write it once, as "
            '"under €400". A limit per product is not applied.',
        ),
        (
            "200 litres of milk under $400",
            'it gives an amount of money in a currency other than the euro ("$400"), and every price here is in '
            "euros",
            'What is the most to spend on this request in euros, before tax? Write it as "under €400".',
        ),
        (
            "200 litres of milk, max 4000 kr",
            'it gives an amount of money in a currency other than the euro ("4000 kr"), and every price here is in '
            "euros",
            'What is the most to spend on this request in euros, before tax? Write it as "under €400".',
        ),
        (
            "200 litres of milk for €400",
            'it gives an amount of money ("€400") without saying that it is the most to spend',
            'Is €400 the most to spend on this request, before tax? Then write "under €400". A price is not '
            f"agreed in a request: {TOTALS}",
        ),
        (
            "200 litres of milk, at least €400",
            'it gives an amount of money ("€400") without saying that it is the most to spend',
            'Is €400 the most to spend on this request, before tax? Then write "under €400". A price is not '
            f"agreed in a request: {TOTALS}",
        ),
        (
            "200 litres of milk, no less than 400 euros",
            'it gives an amount of money ("400 euros") without saying that it is the most to spend',
            'Is 400 euros the most to spend on this request, before tax? Then write "under 400 euros". A price is '
            f"not agreed in a request: {TOTALS}",
        ),
        (
            "200 litres of milk under €1.000",
            'it gives an amount of money that is not read as one number ("€1.000")',
            'What is the most to spend on this request, in euros before tax? Write it in plain digits, for example '
            '"under €1000" or "under €999.50".',
        ),
        (
            "200 litres of milk under €0",
            'it gives an amount of money that is not read as one number ("€0")',
            'What is the most to spend on this request, in euros before tax? Write it in plain digits, for example '
            '"under €1000" or "under €999.50".',
        ),
    ],
)
def test_an_amount_of_money_that_is_not_clearly_the_most_to_spend_is_asked_about(
    rules: ModelRequestParser, text: str, why: str, ask: str
) -> None:
    refused = _asked(rules, text)

    assert (refused.why, refused.ask) == (why, ask)


def test_a_number_with_no_currency_and_no_budget_word_is_asked_about_as_a_number(rules: ModelRequestParser) -> None:
    assert _asked(rules, "200 litres of milk, max 400").ask.startswith("What does 400 stand for?")


def test_an_order_taken_back_is_named_before_its_amount(rules: ModelRequestParser) -> None:
    assert '"cancel"' in _asked(rules, "200 litres of milk, cancel the order of €1,000").why


# --- 3. whoever reads ----------------------------------------------------------------------------------------


def test_a_clear_amount_is_not_asked_about_whoever_reads() -> None:
    ask_whoever_reads("200 litres of milk no more than €400", SATURDAY)
    ask_whoever_reads("200 litres of milk within a budget of €400", SATURDAY)


@pytest.mark.parametrize(
    "text",
    ["200 litres of milk under €2 a litre", "200 litres of milk for €400", "200 litres of milk under $400",
     "200 litres of milk under €400 or €500"],
)
def test_an_unclear_amount_is_asked_about_whoever_reads(text: str) -> None:
    with pytest.raises(NotReadByRules, match="amount of money"):
        ask_whoever_reads(text, SATURDAY)


def _answer(**request: Any) -> str:
    line = {
        "product_type": "milk", "product_ids": [], "name_terms": [], "required_claims": [], "quantity": 200,
        "unit": "L", "exclude_allergens": [], "allergen_strictness": None, "pack": None, "required_labels": [],
        "keep_formula": None,
    }
    return json.dumps({"needed_by": None, "require_confirmed": False, "prefer": None, "lines": [line], **request})


def _model_parser(scripted: Any, demo_clock: Clock, *answers: str) -> ModelRequestParser:
    return ModelRequestParser(
        model=scripted(extracts=list(answers)), clock=demo_clock, product_type_keys=("milk", "butter"),
        profile_strictness=NO_RULE.get, held_to_words=True,
    )


def test_a_models_reading_carries_the_amount_the_text_states(scripted: Any, demo_clock: Clock) -> None:
    parser = _model_parser(scripted, demo_clock, _answer(max_net_eur=400))

    reading = parser.read("200 litres of milk under €400", AGENT)

    assert reading.request.max_net_eur == Decimal(400) and reading.sentence.endswith(f"€400 {USED}")


def test_a_budget_the_text_does_not_state_does_not_pass(scripted: Any, demo_clock: Clock) -> None:
    parser = _model_parser(scripted, demo_clock, _answer(max_net_eur=400), _answer(max_net_eur=400))

    with pytest.raises(ReadingFailedChecks, match="max_net_eur: the reading did not match the text: the text "
                                                  "states no such amount as the most to spend"):
        parser.read("200 litres of milk", AGENT)


def test_another_amount_than_the_one_the_text_states_does_not_pass(scripted: Any, demo_clock: Clock) -> None:
    parser = _model_parser(scripted, demo_clock, _answer(max_net_eur=4000), _answer(max_net_eur=4000))

    with pytest.raises(ReadingFailedChecks, match="max_net_eur"):
        parser.read("200 litres of milk under €400", AGENT)


def test_the_amount_is_not_a_number_a_line_may_take_for_its_quantity(scripted: Any, demo_clock: Clock) -> None:
    taken = json.loads(_answer(max_net_eur=400))
    taken["lines"][0]["quantity"] = 400
    parser = _model_parser(scripted, demo_clock, json.dumps(taken), json.dumps(taken))

    with pytest.raises(ReadingFailedChecks, match="quantity: the reading did not match the text"):
        parser.read("200 litres of milk under €400", AGENT)


def test_an_amount_the_text_states_and_the_reading_leaves_out_does_not_pass(
    scripted: Any, demo_clock: Clock
) -> None:
    parser = _model_parser(scripted, demo_clock, _answer(), _answer())

    with pytest.raises(ReadingFailedChecks, match="max_net_eur: the reading did not match the text: the text "
                                                  "states an amount of money the reading leaves out"):
        parser.read("200 litres of milk under €400", AGENT)


def test_an_answer_made_before_the_field_existed_reads_as_no_amount(scripted: Any, demo_clock: Clock) -> None:
    parser = _model_parser(scripted, demo_clock, _answer())

    assert parser.read("200 litres of milk", AGENT).request.max_net_eur is None
