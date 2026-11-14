"""The rule-based reader reads common sentences without a model, says so, and reads nothing else (task FALLBACK-1).

Scores on the 30% "working end-to-end demo": with no model and no recording, a common sentence still runs the
whole flow. And on the 20% "decisions logged and auditable": every such reading and run names the fixed rules.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.agent.fallback import RULES_RAN_WITHOUT_KEY
from tta.agent.labels import RULES_WITHOUT_KEY, reading_sentence, rules_sentence
from tta.agent.model import AnswerSource, ExtractCall, TurnCall
from tta.agent.parser import ModelRequestParser
from tta.agent.rules_model import RULE_BASED_MODEL_ID, RuleModel, top_option
from tta.agent.rules_reader import NotReadByRules
from tta.api import create_app
from tta.api.wiring import Parts
from tta.config import Settings
from tta.contracts.agent import ReadingSource
from tta.contracts.common import AllergenStrictness, Identity, OrderStatus, Preference, Unit
from tta.contracts.errors import InvalidRequest, SupplierUnavailable
from tta.contracts.ports import Clock
from tta.contracts.request import PurchaseRequest

BRIEF = (
    "I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on "
    "price and availability."
)
WARD_OAT = "200 litres of oat drink, no milk, no gluten, strict, by Monday"
SATURDAY, SUNDAY, MONDAY = date(2026, 11, 14), date(2026, 11, 15), date(2026, 11, 16)
HOTEL_TOKEN = {"Authorization": "Bearer demo-agent-hotel-kitchen"}
SEND_THE_TYPED_REQUEST = "Send the typed request to POST /v1/offers instead."

Read = Callable[[str, Identity], PurchaseRequest]


class Counting:
    """The rule model, counting its answers: a reading that failed the text check would be asked for twice."""

    def __init__(self, model: RuleModel) -> None:
        self._model = model
        self.extracts = 0
        self.model_id, self.recorded = model.model_id, model.recorded

    def label_for(self, request_text: str) -> str:
        return self._model.label_for(request_text)

    def answer_source(self, request_text: str) -> AnswerSource:
        return self._model.answer_source(request_text)

    def extract(self, call: ExtractCall) -> str:
        self.extracts += 1
        return self._model.extract(call)

    def next_turn(self, call: TurnCall) -> Any:
        return self._model.next_turn(call)


@pytest.fixture(scope="session")
def rule_model(product_type_keys: tuple[str, ...]) -> RuleModel:
    return RuleModel.for_keys(product_type_keys)


@pytest.fixture
def counting(rule_model: RuleModel) -> Counting:
    return Counting(rule_model)


@pytest.fixture
def rules_parser(make_parser: Callable[..., ModelRequestParser], counting: Counting, demo_clock: Clock) -> Any:
    return make_parser(counting, demo_clock)


# --- what it reads ----------------------------------------------------------------------------------------


def test_the_briefs_own_sentence_reads_as_its_recording_does(
    rules_parser: ModelRequestParser, counting: Counting, agent_hotel: Identity
) -> None:
    reading = rules_parser.read(BRIEF, agent_hotel)

    line = reading.request.lines[0]
    assert (line.product_type, line.quantity, line.unit, line.required_claims) == (
        "milk", Decimal(1000), Unit.L, ("FREE_FROM_LACTOSE",)
    )
    assert (line.exclude_allergens, line.name_terms, reading.request.needed_by) == ((), (), MONDAY)
    assert reading.request.prefer is Preference.PRICE and reading.request.require_confirmed is False
    assert (reading.source, reading.model, reading.sentence) == (
        ReadingSource.RULE_BASED, RULE_BASED_MODEL_ID,
        # how the comma of "1,000" was read is said since the review of 14 Nov 2026 (finding P6)
        'Read by fixed rules, not by a model. "1,000" is read as 1000 (a comma before three digits groups thousands '
        'here); for 1 write "1".',
    )
    assert counting.extracts == 1  # the proposal passed the text check at once


def test_the_ward_sentence_reads_with_its_exclusions_and_strictness(
    rules_parser: ModelRequestParser, agent_hotel: Identity
) -> None:
    line = rules_parser.parse_request(WARD_OAT, agent_hotel).lines[0]

    assert (line.product_type, line.name_terms, line.quantity) == ("plant_drink", ("oat",), Decimal(200))
    assert line.exclude_allergens == ("AM", "AW") and line.allergen_strictness is AllergenStrictness.STRICT


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 000 l of milk tomorrow", {"product_type": "milk", "quantity": Decimal(1000), "unit": Unit.L}),
        ("1.5 kg of butter", {"product_type": "butter", "quantity": Decimal("1.5"), "unit": Unit.KG}),
        ("2,5 kilos of quark", {"product_type": "quark", "quantity": Decimal("2.5"), "unit": Unit.KG}),
        ("12 bottles of mineral water", {"product_type": "mineral_water", "quantity": 12, "unit": Unit.UNIT}),
        ("30 packs of butter", {"product_type": "butter", "unit": Unit.UNIT}),
        ("50 kg of beef chuck", {"product_type": "beef_chuck", "name_terms": ()}),
        ("10 kg of sour milk", {"product_type": "sour_milk"}),
        ("120 l of 464056", {"product_type": None, "product_ids": ("464056",)}),
        ("20 kg of organic minced beef", {"product_type": "beef", "name_terms": ("minced",),
                                          "required_labels": ("EU_ORGANIC_FARMING",)}),
        ("40 kg of MSC fresh fish", {"product_type": "fresh_fish",
                                     "required_labels": ("MARINE_STEWARDSHIP_COUNCIL_LABEL",)}),
        ("5 kg of nut-free bread, strict", {"exclude_allergens": ("AN",), "allergen_strictness": "STRICT"}),
        ("100 litres of oat drink without milk, declared only", {"allergen_strictness": "DECLARED_ONLY"}),
    ],
)
def test_a_common_line_is_read(rules_parser: ModelRequestParser, agent_hotel: Identity, text: str,
                               expected: dict[str, Any]) -> None:
    line = rules_parser.parse_request(text, agent_hotel).lines[0]

    assert {name: getattr(line, name) for name in expected} == expected


def test_several_lines_keep_their_own_claims_and_labels_and_share_the_rest(
    rules_parser: ModelRequestParser, agent_hotel: Identity
) -> None:
    text = "50 kg of organic beef chuck and 1 000 l of lactose-free milk; 20 kg of cheese by tomorrow, lowest carbon"

    request = rules_parser.parse_request(text, agent_hotel)

    assert [line.product_type for line in request.lines] == ["beef_chuck", "milk", "cheese"]
    assert [line.required_labels for line in request.lines] == [("EU_ORGANIC_FARMING",), (), ()]
    assert [line.required_claims for line in request.lines] == [(), ("FREE_FROM_LACTOSE",), ()]
    assert (request.needed_by, request.prefer) == (SUNDAY, Preference.LOWER_CARBON)


@pytest.mark.parametrize(
    ("text", "prefer"),
    [("200 l of oat drink as soon as possible", Preference.EARLIEST),
     ("200 l of oat drink, most reliable", Preference.RELIABILITY),
     ("200 l of the cheapest oat drink", Preference.PRICE)],
)
def test_a_preference_is_read_from_its_words(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str, prefer: Preference
) -> None:
    request = rules_parser.parse_request(text, agent_hotel)

    assert request.prefer is prefer and request.lines[0].name_terms == ("oat",)  # "cheapest" is not a term


def test_confirmed_only_and_a_date_are_read_for_the_whole_request(
    rules_parser: ModelRequestParser, agent_hotel: Identity
) -> None:
    request = rules_parser.parse_request("464056: 120 l by 20.11. Confirmed only.", agent_hotel)

    assert request.require_confirmed is True and request.needed_by == date(2026, 11, 20)
    assert request.lines[0].product_ids == ("464056",) and request.lines[0].quantity == 120


def test_an_exclusion_with_no_strictness_word_reads_strict_when_the_profile_sets_no_rule_either(
    rules_parser: ModelRequestParser, agent_hotel: Identity, agent_ward: Identity
) -> None:
    hotel = rules_parser.parse_request("200 litres of oat drink, no milk", agent_hotel)

    assert hotel.lines[0].allergen_strictness is AllergenStrictness.STRICT  # the safe reading (replan P4 M3)
    assert rules_parser.parse_request("200 litres of oat drink, no milk", agent_ward).lines[0].allergen_strictness \
        is None  # the ward's profile sets STRICT itself


def test_gluten_free_is_both_the_claim_and_the_exclusion_the_text_check_holds(
    rules_parser: ModelRequestParser, agent_ward: Identity
) -> None:
    line = rules_parser.parse_request("30 kg gluten-free bread", agent_ward).lines[0]

    assert line.required_claims == ("FREE_FROM_GLUTEN",) and line.exclude_allergens == ("AW",)


# --- what it refuses --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("Some milk for Monday", "milk is named with no quantity in digits and unit"),
        ("a thousand litres of milk", "milk is named with no quantity in digits and unit"),
        ("200 oat drinks by Monday", "plant drink is named with no quantity in digits and unit"),
        ("200 litres of something nice", "line 1 names no product type of the table"),
        ("1000 litres of milk and some cheese", "cheese is named with no quantity"),
        ("20 kg of a butter substitute by Monday", "a substitute"),  # a milk substitute is the plant drink
        ("10 kg of sugar-free butter", "excludes something the allergen table does not name"),
        ("1.5 kg of cream cheese", "more than one product type (cheese, cream)"),
        ("200 x 1 l of milk", "a number besides its quantity"),
        ("200 l of milk 100 l of cream", "more than one quantity"),
        ("200 l of milk by Monday or Tuesday", "more than one day"),
        ("200 l of milk by 2025-01-05", "a day before today"),
        ("200 l of milk, cheapest, as soon as possible", "more than one preference"),
        ("200 l of oat drink, no milk, strict, declared only", "both strict and declared only"),
        ("2000000 l of milk", "at most 1,000,000"),
        # Finnish: the rules read English only, and say so (review C2-8; `tta.agent.language`)
        ("1000 litraa laktoositonta maitoa maanantaiksi", "it looks like Finnish"),
    ],
)
def test_a_text_it_cannot_read_fully_is_refused_naming_what(
    rules_parser: ModelRequestParser, agent_hotel: Identity, text: str, why: str
) -> None:
    with pytest.raises(NotReadByRules) as refused:
        rules_parser.read(text, agent_hotel)

    assert why in refused.value.why and isinstance(refused.value, SupplierUnavailable)


def test_it_never_guesses_a_quantity(rule_model: RuleModel) -> None:
    for text in ("milk by Monday", "a case of milk", "oat drink, 200", "lots of cheese"):
        with pytest.raises(NotReadByRules):
            rule_model.extract(ExtractCall(system="", text=text, schema={}, today=SATURDAY))


def test_the_answer_is_json_with_the_quantity_as_its_digits(rule_model: RuleModel) -> None:
    answer = json.loads(rule_model.extract(ExtractCall(system="", text="1.25 kg of butter", schema={}, today=SATURDAY)))

    assert answer["lines"][0]["quantity"] == "1.25" and answer["prefer"] is None


def test_a_call_without_the_day_is_refused(rule_model: RuleModel) -> None:
    with pytest.raises(ValueError, match="date"):
        rule_model.extract(ExtractCall(system="", text="1 l of milk", schema={}))


# --- who it says read it ----------------------------------------------------------------------------------


def test_the_sentences_name_the_rules_and_why_they_read() -> None:
    assert reading_sentence(AnswerSource(ReadingSource.RULE_BASED, RULE_BASED_MODEL_ID)) == (
        "Read by fixed rules, not by a model."
    )
    assert rules_sentence(key_set=True) == "Read by fixed rules, not by a model: Gemini did not answer."
    assert rules_sentence(key_set=False) == RULES_WITHOUT_KEY


# --- the fixed run ----------------------------------------------------------------------------------------


def _result(name: str, result: dict[str, Any], *, error: bool = False) -> dict[str, Any]:
    step = {"type": "function_result", "name": name, "call_id": "c",
            "result": [{"type": "text", "text": json.dumps(result)}]}
    return {**step, "is_error": True} if error else step


def test_the_run_orders_the_option_ranked_one_of_its_offer(rule_model: RuleModel) -> None:
    history = (_result("create_offer", {"options": [{"option_id": "opt_2", "rank": 2},
                                                    {"option_id": "opt_1", "rank": 1}]}),)
    turns = [rule_model.next_turn(TurnCall(system="", request_text="t", history=history, tools=(), turn=number))
             for number in (1, 2, 3, 4)]

    assert [[(call.name, call.arguments) for call in turn.calls] for turn in turns] == [
        [("get_authority", {})], [("create_offer", {})], [("place_order", {"option_id": "opt_1"})], []
    ]


@pytest.mark.parametrize(
    "history",
    [(), (_result("create_offer", {"options": []}),), (_result("create_offer", {"error": "x"}, error=True),),
     ({"type": "function_result", "name": "create_offer", "result": [{"type": "text", "text": "not json"}]},)],
)
def test_with_no_option_to_order_the_run_orders_nothing(history: tuple[dict[str, Any], ...]) -> None:
    assert top_option(history) is None


def test_with_no_key_an_unrecorded_sentence_runs_the_whole_flow_by_the_rules(
    parts: Parts, agent_hotel: Identity
) -> None:
    run = parts.service.run_agent(agent_hotel, "300 litres of oat drink by Monday")

    assert (run.model, run.recorded) == (RULE_BASED_MODEL_ID, False)
    assert [step.tool for step in run.steps] == ["get_authority", "create_offer", "place_order"]
    assert run.order_status in (OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL)
    assert run.report.startswith(RULES_RAN_WITHOUT_KEY)
    assert parts.service.get_order(agent_hotel, run.order_id).option.option_id == "opt_1"


def test_a_rules_run_whose_offer_has_no_option_orders_nothing_and_says_so(
    parts: Parts, agent_hotel: Identity
) -> None:
    # Pork: 106 products in the catalog, none in tonight's recording. Butter no longer serves here: the baking
    # recording joined to the demo recording holds it, and a run for butter prepares an order.
    run = parts.service.run_agent(agent_hotel, "10 kg of pork by Monday")

    assert [step.tool for step in run.steps] == ["get_authority", "create_offer"] and run.order_id is None
    assert "The agent stopped after 2 steps without an order." in run.report and "No order was placed." in run.report
    assert "106 candidates checked: 106 not in recording." in run.report  # it says why, with the count


# --- through the gateway with no key ----------------------------------------------------------------------


def test_with_no_key_a_recorded_sentence_is_still_read_from_its_recording(
    parts: Parts, agent_hotel: Identity, texts: dict[str, str]
) -> None:
    reading = parts.service.read_request(agent_hotel, texts["scenario_1"])

    assert reading.source is not ReadingSource.RULE_BASED


def test_with_no_key_an_unrecorded_sentence_is_read_by_the_rules_and_says_why(
    parts: Parts, agent_hotel: Identity, agent_ward: Identity, texts: dict[str, str]
) -> None:
    reading = parts.service.read_request(agent_hotel, WARD_OAT)
    # Recorded for the hotel kitchen only: for the ward, the rules read it.
    other_profile = parts.service.read_request(agent_ward, texts["scenario_1"])

    assert (reading.source, reading.sentence) == (ReadingSource.RULE_BASED, RULES_WITHOUT_KEY)
    assert other_profile.source is ReadingSource.RULE_BASED


def test_with_no_key_a_text_the_rules_cannot_read_is_asked_about_naming_what_was_missing(
    parts: Parts, agent_hotel: Identity
) -> None:
    """Replan A2b M1: it used to be `supplier-unavailable` (503). Nothing is out of reach: a person is asked."""
    with pytest.raises(InvalidRequest) as refused:
        parts.service.read_request(agent_hotel, "a sentence nobody recorded")
    with pytest.raises(InvalidRequest) as run_refused:
        parts.service.run_agent(agent_hotel, "Some cheese for Friday")

    assert refused.value.detail == (
        "The fixed rules did not read this request, and nothing was guessed: it gives no quantity in digits with a "
        "unit, such as 200 litres. How much is needed, and of what? For example: 200 litres of oat drink by Monday."
    )
    assert "cheese is named with no quantity" in run_refused.value.detail
    assert run_refused.value.extensions["question"].startswith("What quantity of cheese is needed?")
    assert not isinstance(refused.value, SupplierUnavailable)


def test_the_parse_route_names_the_rules_in_its_headers(
    settings: Settings, parts: Parts, without_other_surfaces: None
) -> None:
    with TestClient(create_app(settings, parts=parts)) as client:
        response = client.post("/v1/requests/parse", json={"text": WARD_OAT}, headers=HOTEL_TOKEN)
        ran = client.post("/v1/agent/run", json={"text": "300 litres of oat drink by Monday"}, headers=HOTEL_TOKEN)

    assert response.status_code == 200
    assert (response.headers["TTA-Read-By"], response.headers["TTA-Reading-Source"]) == ("rule-based", "rule-based")
    assert ran.status_code == 200 and ran.json()["model"] == "rule-based"
