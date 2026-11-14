""""Formula matters" and "the usual" in the reading of the fixed rules (replan P10 option a; P1 C4, C5; B8).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": a use the words name sets
`keep_formula` on the line it belongs to and the reading says so; "the usual" is never turned into a product or a
number. And on the 20% "decisions logged and auditable": every such reading says what it took from the words.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from tta.agent.fallback import FallbackParser
from tta.agent.labels import RULES_WITHOUT_KEY
from tta.agent.notes import MILK_SUBSTITUTE_READ, NO_USE_NAMED
from tta.agent.parser import ModelRequestParser
from tta.agent.recorded import RecordedModel
from tta.agent.rules_model import RuleModel
from tta.agent.rules_reader import NotReadByRules
from tta.agent.usual import STANDING_ORDER_PAGE, USUAL_SAID
from tta.contracts.common import Identity
from tta.contracts.errors import InvalidRequest
from tta.contracts.ports import Clock

READ_BY_RULES = "Read by fixed rules, not by a model."


@pytest.fixture
def rules(make_parser: Callable[..., ModelRequestParser], product_type_keys: tuple[str, ...], demo_clock: Clock) -> Any:
    return make_parser(RuleModel.for_keys(product_type_keys), demo_clock)


# --- formula matters ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("20 litres of milk for foaming", "for foaming"),  # "cream for whipping": test_brands_and_variants.py
        ("20 litres of milk for foaming by Monday", "for foaming"),
        ("10 kg of butter for baking", "for baking"),
        ("10 kg of butter by Monday, for cakes", "for cakes"),
        ("100 litres of whipping cream by Monday, for cakes", "for cakes"),
        ("5 litres of cream for the sauce", "for the sauce"),
    ],
)
def test_a_use_the_words_name_sets_keep_formula_and_the_sentence_says_so(
    rules: ModelRequestParser, agent_hotel: Identity, text: str, said: str
) -> None:
    reading = rules.read(text, agent_hotel)

    assert [line.keep_formula for line in reading.request.lines] == [True]
    assert reading.sentence == f'{READ_BY_RULES} Formula matters: the request says "{said}".'


@pytest.mark.parametrize(
    "text",
    [
        "20 litres of whipping cream by Monday",  # a product's own name is not a use
        "10 kg of baking butter",
        "20 litres of cream, not for baking",
        "20 litres of cream not for whipping",
        "20 litres of cream by Monday",
    ],
)
def test_a_product_name_or_a_negated_use_sets_nothing(
    rules: ModelRequestParser, agent_hotel: Identity, text: str
) -> None:
    reading = rules.read(text, agent_hotel)

    assert [line.keep_formula for line in reading.request.lines] == [None]
    assert "keep_formula" not in reading.request.lines[0].model_fields_set  # absent, not false
    assert reading.sentence == READ_BY_RULES


@pytest.mark.parametrize(
    ("text", "marked", "where"),
    [
        ("100 litres of milk and 20 litres of cream for whipping", [None, True], " for line 2"),
        ("10 kg of butter for baking and 100 litres of milk", [True, None], " for line 1"),
        ("100 litres of milk and 20 litres of cream, for whipping", [None, True], " for line 2"),
        ("for baking: 10 kg of butter and 100 litres of milk", [True, None], " for line 1"),
    ],
)
def test_only_the_line_the_words_belong_to_is_marked(
    rules: ModelRequestParser, agent_hotel: Identity, text: str, marked: list[bool | None], where: str
) -> None:
    reading = rules.read(text, agent_hotel)

    assert [line.keep_formula for line in reading.request.lines] == marked
    assert f"Formula matters{where}: the request says " in reading.sentence


def test_two_uses_on_two_lines_are_both_said(rules: ModelRequestParser, agent_hotel: Identity) -> None:
    reading = rules.read("10 kg of butter for baking and 20 litres of cream for whipping", agent_hotel)

    assert [line.keep_formula for line in reading.request.lines] == [True, True]
    assert reading.sentence.endswith('Formula matters: the request says "for baking", "for whipping".')


def test_a_model_that_marks_the_formula_with_no_use_in_the_text_is_refused(
    make_parser: Callable[..., ModelRequestParser], scripted: Any, proposal: Callable[..., str], demo_clock: Clock,
    agent_hotel: Identity,
) -> None:
    answer = proposal(product_type="cream", name_terms=["whipping"], keep_formula=True)
    parser = make_parser(scripted(extracts=[answer, answer]), demo_clock)

    with pytest.raises(InvalidRequest) as refused:
        parser.read("10 litres of whipping cream by Monday", agent_hotel)

    assert NO_USE_NAMED in refused.value.detail and refused.value.extensions["faults"] == ["lines[0].keep_formula"]


def test_a_model_may_mark_the_formula_when_the_text_names_a_use(
    make_parser: Callable[..., ModelRequestParser], scripted: Any, proposal: Callable[..., str], demo_clock: Clock,
    agent_hotel: Identity,
) -> None:
    parser = make_parser(scripted(extracts=[proposal(product_type="cream", keep_formula=True)]), demo_clock)

    reading = parser.read("10 litres of cream for whipping by Monday", agent_hotel)

    assert reading.request.lines[0].keep_formula is True
    assert reading.sentence == 'Read by scripted. Formula matters: the request says "for whipping".'


def test_the_gateways_reader_keeps_every_note_after_its_own_first_sentence(
    make_parser: Callable[..., ModelRequestParser], recorded_model: RecordedModel, product_type_keys: tuple[str, ...],
    demo_clock: Clock, agent_hotel: Identity,
) -> None:
    """With no key the gateway's first sentence is its own; the allergen note and the formula note both stay."""
    reader = FallbackParser(
        live=None, recorded=make_parser(recorded_model, demo_clock), recordings=recorded_model,
        rules=make_parser(RuleModel.for_keys(product_type_keys), demo_clock),
    )

    sentence = reader.read("20 litres of cream for whipping by Monday, no nuts", agent_hotel).sentence

    assert sentence.startswith(f"{RULES_WITHOUT_KEY} No allergen rule was given for ")
    assert sentence.endswith(
        'goes to a person. Cream "for whipping" is read as whipping cream. Formula matters: the request says "for '
        'whipping".'
    )


def test_the_rule_models_answer_carries_keep_formula(product_type_keys: tuple[str, ...], demo_clock: Clock) -> None:
    reader = RuleModel.for_keys(product_type_keys)._reader  # noqa: SLF001 - the proposal itself is what is pinned

    answer = json.loads(json.dumps(reader.proposal("20 litres of cream for whipping", demo_clock.now().date())))

    assert answer["lines"][0]["keep_formula"] is True


# --- the usual ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "product_type", "quantity"),
    [
        ("50 litres of the usual milk by Monday", "milk", 50),
        ("20 litres of our usual cream", "cream", 20),
        ("100 litres of milk, same as usual", "milk", 100),
        ("100 litres of milk by Monday, the same as usual", "milk", 100),
        ("30 litres of cream as usual", "cream", 30),
    ],
)
def test_the_usual_with_a_type_and_a_quantity_is_the_plain_type_and_nothing_is_chosen(
    rules: ModelRequestParser, agent_hotel: Identity, text: str, product_type: str, quantity: int
) -> None:
    reading = rules.read(text, agent_hotel)

    line = reading.request.lines[0]
    assert (line.product_type, line.quantity, line.product_ids, line.name_terms) == (
        product_type, Decimal(quantity), (), ()
    )
    assert reading.sentence == f"{READ_BY_RULES} {USUAL_SAID}"
    assert USUAL_SAID == (
        'The request says "the usual": the usual product is suggested with the offer for you to confirm; nothing '
        "was chosen for you."
    )


@pytest.mark.parametrize("text", ["the usual milk", "the usual amount of milk by Monday", "milk, the usual amount"])
def test_the_usual_amount_is_asked_about_and_the_question_names_the_suggestion(
    rules: ModelRequestParser, agent_hotel: Identity, text: str
) -> None:
    with pytest.raises(NotReadByRules) as asked:
        rules.read(text, agent_hotel)

    assert asked.value.why == 'milk is named with "the usual" and no quantity in digits and unit'
    assert asked.value.ask.startswith('How much milk is needed? "The usual" is not a number')
    assert "your usual quantity is shown as a suggestion for you to confirm" in asked.value.ask


@pytest.mark.parametrize("text", ["the usual order", "the usual, please", "same as usual", "50 litres of the usual"])
def test_the_usual_with_no_product_type_is_asked_about_and_the_question_names_the_standing_order_page(
    rules: ModelRequestParser, agent_hotel: Identity, text: str
) -> None:
    with pytest.raises(NotReadByRules) as asked:
        rules.read(text, agent_hotel)

    assert asked.value.why == 'it says "the usual" and names no product type'
    assert STANDING_ORDER_PAGE == "/standing-orders"
    assert f"the standing-order page ({STANDING_ORDER_PAGE})" in asked.value.ask


def test_the_same_again_is_still_asked_about(rules: ModelRequestParser, agent_hotel: Identity) -> None:
    with pytest.raises(NotReadByRules, match="the same"):
        rules.read("100 litres of milk by Monday; and the same again for the staff canteen", agent_hotel)


# --- a milk substitute --------------------------------------------------------------------------------------


def test_a_milk_substitute_is_the_plant_drink_type_and_the_reading_says_so(
    rules: ModelRequestParser, agent_ward: Identity
) -> None:
    text = "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"

    reading = rules.read(text, agent_ward)

    line = reading.request.lines[0]
    assert (line.product_type, line.name_terms, line.product_ids) == ("plant_drink", (), ())
    assert line.quantity == Decimal(200)
    assert line.exclude_allergens == ("AM", "AW") and reading.request.require_confirmed is True
    assert reading.sentence == f"{READ_BY_RULES} {MILK_SUBSTITUTE_READ}"


@pytest.mark.parametrize("text", ["20 kg of a butter substitute", "200 litres of a milk substitute instead of cream"])
def test_any_other_substitute_is_still_asked_about(rules: ModelRequestParser, agent_hotel: Identity, text: str) -> None:
    with pytest.raises(NotReadByRules, match="a substitute"):
        rules.read(text, agent_hotel)
