"""What the agent learns about where the recipe matters, per customer and product (lane LF).

Scores on the 20% "solving the problem and user need" (a substitute that keeps the recipe where this customer needs
it, with nobody repeating "for baking") and on the 20% "autonomy and controls" (what was learned is said with its
source and evidence, and a person's own decision outranks everything else). Pure: nothing here reads a store.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tta.contracts.customer import Customer
from tta.contracts.request import PurchaseRequest
from tta.customers import shipped_customer, shipped_customers
from tta.customers.learned import (
    ACCEPTANCES_TO_UNLEARN,
    WORDS_MIN_REQUESTS,
    WORDS_MIN_SHARE,
    LearnedSource,
    Past,
    PastAsk,
    PastDecision,
    SubstituteDecision,
    apply_learned,
    learn,
    learned_for_usual,
    summary_of,
)

WHIPPING, COOKING, HOTEL_MILK = "469346", "463797", "469363"
NAMES = {WHIPPING: "Arla Pro Whipping cream", COOKING: "Arla Pro Cooking cream", HOTEL_MILK: "Arla milk"}
THIRD, FIFTH, NINTH = (datetime(2026, 11, day, 10, 0, tzinfo=UTC) for day in (3, 5, 9))


@pytest.fixture(scope="module")
def hotel() -> Customer:
    found = shipped_customer("hotel-kitchen")
    assert found is not None
    return found


def _decision(kind: SubstituteDecision, at: datetime, product_id: str = COOKING) -> PastDecision:
    return PastDecision(product_id=product_id, kind=kind, decided_at=at, approval_id=f"apr_{at.day}")


def _ask(at: datetime, said: bool, product_id: str = HOTEL_MILK) -> PastAsk:
    return PastAsk(asked_at=at, product_ids=(product_id,), product_type=None, said_use=said)


# --- (c) how they use it: the customer file's mark, which is synthetic -----------------------------------------


def test_an_ingredient_of_the_customer_file_matters_and_the_sentence_says_it_is_synthetic(hotel: Customer) -> None:
    finding = learn(hotel, COOKING, name=NAMES[COOKING])

    assert finding.matters is True and finding.source is LearnedSource.USE and finding.synthetic is True
    assert finding.sentence == (
        "You use Arla Pro Cooking cream (463797) as an ingredient, so a substitute must keep its recipe. "
        "Learned from your customer file, which is synthetic."
    )
    assert finding.evidence["use"] == "INGREDIENT" and finding.evidence["basis"] == "PRODUCT"
    assert finding.evidence["past_orders_with_it"] == 7  # of the file's 8 weeks


def test_a_product_served_as_it_is_need_not_keep_its_recipe(hotel: Customer) -> None:
    finding = learn(hotel, HOTEL_MILK, name=NAMES[HOTEL_MILK])

    assert finding.matters is False and finding.source is LearnedSource.USE
    assert "You serve Arla milk (469363) as it is" in finding.sentence and "synthetic" in finding.sentence


def test_a_product_that_is_not_usual_takes_the_use_of_the_usual_products_of_its_type(hotel: Customer) -> None:
    finding = learn(hotel, WHIPPING, product_type="cream", name=NAMES[WHIPPING], names=NAMES)

    assert finding.matters is True and finding.source is LearnedSource.USE
    assert finding.evidence["basis"] == "PRODUCT_TYPE" and finding.evidence["usual_product_ids"] == [COOKING]
    assert finding.sentence == (
        "You use cream as an ingredient (Arla Pro Cooking cream (463797)), so a substitute for Arla Pro Whipping "
        "cream (469346) must keep its recipe. Learned from your customer file, which is synthetic."
    )


def test_nothing_is_learned_for_a_product_the_customer_never_met(hotel: Customer) -> None:
    finding = learn(hotel, "464013", product_type="plant_drink")

    assert finding.matters is None and finding.source is None
    assert finding.sentence.startswith("Nothing learned yet for product 464013")


def test_without_a_customer_file_only_decisions_and_words_can_teach() -> None:
    assert learn(None, COOKING).matters is None
    past = Past(decisions=(_decision(SubstituteDecision.REJECTED, THIRD),))
    assert learn(None, COOKING, past).matters is True


# --- (a) their own decisions ----------------------------------------------------------------------------------


def test_a_rejected_substitute_outranks_the_use_mark_and_names_the_day(hotel: Customer) -> None:
    past = Past(decisions=(_decision(SubstituteDecision.REJECTED, THIRD, HOTEL_MILK),))

    finding = learn(hotel, HOTEL_MILK, past, name=NAMES[HOTEL_MILK])

    assert finding.matters is True and finding.source is LearnedSource.DECISION and finding.synthetic is False
    assert finding.sentence == (
        "You rejected a substitute with different ingredients for Arla milk (469363) on 3 November 2026, so "
        "substitutes must keep its recipe."
    )
    assert finding.evidence["rejected"] == 1 and finding.evidence["approval_ids"] == ["apr_3"]
    assert "not_recorded" in finding.evidence  # why the person rejected is not in the store


def test_choosing_another_option_over_the_substitute_counts_like_a_rejection(hotel: Customer) -> None:
    past = Past(decisions=(_decision(SubstituteDecision.CHOSE_ANOTHER, FIFTH, HOTEL_MILK),))

    finding = learn(hotel, HOTEL_MILK, past, name=NAMES[HOTEL_MILK])

    assert finding.matters is True and finding.source is LearnedSource.DECISION
    assert "You chose another option over a substitute with different ingredients" in finding.sentence
    assert "5 November 2026" in finding.sentence


def test_accepting_a_formula_changing_substitute_twice_shows_it_does_not_matter(hotel: Customer) -> None:
    assert ACCEPTANCES_TO_UNLEARN == 2
    once = Past(decisions=(_decision(SubstituteDecision.ACCEPTED, THIRD),))
    twice = Past(decisions=(*once.decisions, _decision(SubstituteDecision.ACCEPTED, FIFTH)))

    assert learn(hotel, COOKING, once).source is LearnedSource.USE  # one acceptance teaches nothing yet
    finding = learn(hotel, COOKING, twice, name=NAMES[COOKING])
    assert finding.matters is False and finding.source is LearnedSource.DECISION
    assert finding.sentence == (
        "You accepted a substitute with different ingredients for Arla Pro Cooking cream (463797) 2 times, last "
        "on 5 November 2026, so a substitute need not keep its recipe."
    )


def test_a_later_decision_outranks_an_earlier_one(hotel: Customer) -> None:
    accepted_twice = (_decision(SubstituteDecision.ACCEPTED, THIRD), _decision(SubstituteDecision.ACCEPTED, FIFTH))
    then_rejected = Past(decisions=(*accepted_twice, _decision(SubstituteDecision.REJECTED, NINTH)))
    rejected_then_one_acceptance = Past(decisions=(
        _decision(SubstituteDecision.REJECTED, THIRD), _decision(SubstituteDecision.ACCEPTED, FIFTH)))

    assert learn(hotel, COOKING, then_rejected).matters is True
    still = learn(hotel, COOKING, rejected_then_one_acceptance)
    assert still.matters is True and still.source is LearnedSource.DECISION  # one acceptance does not undo it
    assert still.evidence["accepted_since"] == 1


def test_decisions_are_read_in_time_order_whatever_order_they_arrive_in(hotel: Customer) -> None:
    late, early = _decision(SubstituteDecision.REJECTED, NINTH), _decision(SubstituteDecision.ACCEPTED, THIRD)
    past = Past(decisions=(late, early))

    assert learn(hotel, COOKING, past).evidence["last_decided_at"] == NINTH.isoformat()


# --- (b) their own words --------------------------------------------------------------------------------------


def test_past_requests_that_said_a_use_outrank_the_use_mark(hotel: Customer) -> None:
    assert (WORDS_MIN_REQUESTS, str(WORDS_MIN_SHARE)) == (2, "0.5")
    past = Past(asks=(_ask(THIRD, True), _ask(FIFTH, False), _ask(NINTH, True)))

    finding = learn(hotel, HOTEL_MILK, past, name=NAMES[HOTEL_MILK])

    assert finding.matters is True and finding.source is LearnedSource.WORDS and finding.synthetic is False
    assert finding.sentence == (
        "2 of your 3 past requests for Arla milk (469363) said the recipe matters, so a substitute must keep its "
        "recipe."
    )
    assert finding.evidence == {"requests": 3, "said_recipe_matters": 2, "min_share": "0.5", "min_requests": 2,
                                "last_said_at": NINTH.isoformat()}


def test_one_request_or_too_small_a_share_teaches_nothing(hotel: Customer) -> None:
    one = Past(asks=(_ask(THIRD, True),))
    few = Past(asks=(_ask(THIRD, True), _ask(FIFTH, False), _ask(NINTH, False)))

    assert learn(hotel, HOTEL_MILK, one).source is LearnedSource.USE
    assert learn(hotel, HOTEL_MILK, few).source is LearnedSource.USE


def test_a_request_by_type_counts_for_the_usual_product_of_that_type(hotel: Customer) -> None:
    by_type = PastAsk(asked_at=THIRD, product_ids=(), product_type="milk", said_use=True)
    past = Past(asks=(by_type, PastAsk(asked_at=FIFTH, product_ids=(), product_type="milk", said_use=True)))

    assert learn(hotel, HOTEL_MILK, past).source is LearnedSource.WORDS


def test_a_decision_outranks_words(hotel: Customer) -> None:
    past = Past(
        decisions=tuple(_decision(SubstituteDecision.ACCEPTED, at, HOTEL_MILK) for at in (THIRD, FIFTH)),
        asks=(_ask(THIRD, True), _ask(FIFTH, True)),
    )

    finding = learn(hotel, HOTEL_MILK, past)

    assert finding.source is LearnedSource.DECISION and finding.matters is False


# --- every customer, from the files alone -----------------------------------------------------------------------


def test_from_the_files_alone_everything_learned_rests_on_the_use_mark() -> None:
    learned = {
        customer_id: {each.product_id: (each.matters, each.source) for each in learned_for_usual(customer)}
        for customer_id, customer in shipped_customers().items()
    }

    use = LearnedSource.USE
    assert learned["hotel-kitchen"] == {
        "469363": (False, use), "463797": (True, use), "464615": (False, use), "463203": (False, use),
        "466988": (True, use)}
    assert learned["school-kitchen"] == {
        "462775": (False, use), "470863": (False, use), "464517": (False, use), "466988": (True, use),
        "463254": (True, use)}
    assert learned["allergy-ward"] == {"464013": (False, use), "473424": (False, use)}
    assert learned["bakery-cafe"] == {
        "469346": (True, use), "464727": (True, use), "463380": (False, use), "468319": (False, use)}


def test_the_summary_names_what_was_learned_and_from_what(hotel: Customer) -> None:
    findings = learned_for_usual(hotel, names={COOKING: "Arla Pro Cooking cream", "466988": "Beef chuck"})

    assert summary_of(findings) == (
        "Learned so far: Arla Pro Cooking cream, Beef chuck (you use them as ingredients). From your customer file, "
        "which is synthetic."
    )
    assert summary_of(()) == "Nothing learned yet: no decision, request or customer file says where the recipe matters."


# --- applying it to a request -----------------------------------------------------------------------------------


def _request(**line: object) -> PurchaseRequest:
    return PurchaseRequest.model_validate({"lines": [{"text": "", "quantity": 100, "unit": "L", **line}]})


def _type_of(product_id: str) -> str | None:
    return {WHIPPING: "cream"}.get(product_id)


def test_a_line_naming_an_ingredient_gets_keep_formula_and_a_note_saying_where_it_came_from(hotel: Customer) -> None:
    request = _request(product_ids=[COOKING])

    prepared = apply_learned(request, hotel, Past(), type_of=_type_of, names=NAMES)

    assert prepared.request.lines[0].keep_formula is True and request.lines[0].keep_formula is None
    assert prepared.original is request
    (applied,) = prepared.applied
    assert (applied.line, applied.product_id, applied.finding.source) == (1, COOKING, LearnedSource.USE)
    assert prepared.notes == (
        "Request line 1: You use Arla Pro Cooking cream (463797) as an ingredient, so a substitute must keep its "
        "recipe. Learned from your customer file, which is synthetic. The gateway applied this; your request did "
        "not say it. Change this in Settings.",
    )


def test_a_line_naming_another_product_of_an_ingredient_type_gets_it_too(hotel: Customer) -> None:
    prepared = apply_learned(_request(product_ids=[WHIPPING]), hotel, Past(), type_of=_type_of, names=NAMES)

    assert prepared.request.lines[0].keep_formula is True
    assert prepared.applied[0].finding.evidence["basis"] == "PRODUCT_TYPE"


def test_a_line_naming_only_a_type_takes_the_usual_product_of_that_type(hotel: Customer) -> None:
    cream = apply_learned(_request(product_type="cream"), hotel, Past(), type_of=_type_of, names=NAMES)
    milk = apply_learned(_request(product_type="milk"), hotel, Past(), type_of=_type_of, names=NAMES)

    assert cream.request.lines[0].keep_formula is True and cream.applied[0].product_id == COOKING
    assert milk.applied == () and milk.request == _request(product_type="milk")


def test_a_line_that_already_says_so_and_a_served_product_are_left_as_they_are(hotel: Customer) -> None:
    said = _request(product_ids=[COOKING], keep_formula=True)
    served = _request(product_ids=[HOTEL_MILK])

    assert apply_learned(said, hotel, Past(), type_of=_type_of).applied == ()
    assert apply_learned(served, hotel, Past(), type_of=_type_of).request is served


def test_a_decision_that_it_does_not_matter_stops_the_use_mark_from_being_applied(hotel: Customer) -> None:
    past = Past(decisions=tuple(_decision(SubstituteDecision.ACCEPTED, at) for at in (THIRD, FIFTH)))

    assert apply_learned(_request(product_ids=[COOKING]), hotel, past, type_of=_type_of).applied == ()


def test_the_facts_for_the_audit_trail_say_the_gateway_applied_it_with_its_source(hotel: Customer) -> None:
    prepared = apply_learned(_request(product_ids=[COOKING]), hotel, Past(), type_of=_type_of, names=NAMES)

    (fact,) = prepared.facts
    assert fact["line"] == 1 and fact["product_id"] == COOKING and fact["keep_formula"] is True
    assert fact["applied_by"] == "gateway" and fact["source"] == "USE" and fact["synthetic"] is True
    assert fact["evidence"]["use"] == "INGREDIENT" and fact["sentence"].startswith("You use Arla Pro Cooking cream")
