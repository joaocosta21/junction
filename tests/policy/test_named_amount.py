"""An amount the request names is a spend limit for that one request, tighter than the buyer's own (lane FP-B).

Scores on the 20% "autonomy and controls": rule P-01 judges an option against the lower of the buyer's limit per
order and the amount the request names (`PurchaseRequest.max_net_eur`, euros before tax). The amount can only
add a check: it never raises the buyer's limit, it is not the limit per day, and it removes no option. The engine
sees the option and not the request, so whoever holds the request as the buyer sent it says so for the length of
one evaluation (`tta.policy.formula_facts.request_as_sent`), as the gateway does when it builds an offer and when
an order is placed.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from tta.contracts.common import ApproverRole, Unit, Verdict
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, FiredRule, PolicyContext, PolicyDecision
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.policy import RulePolicyEngine
from tta.policy.formula_facts import request_as_sent


def _request(amount: str | None) -> PurchaseRequest:
    line = RequestLine(text="200 litres of lactose-free milk", product_type="milk", quantity=Decimal(200),
                       unit=Unit.L)
    return PurchaseRequest(lines=(line,), **({} if amount is None else {"max_net_eur": Decimal(amount)}))


@pytest.fixture
def milk_496(
    make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
) -> OfferOption:
    """200 x 469363 at 2.48: €496.00 before tax, every claim confirmed, the date met."""
    one = make_line("469363", "Lactose-free milk 1L", quantity="200", unit_net_price="2.48")
    return make_option((one,), net="496.00")


@pytest.fixture
def judge(
    engine: RulePolicyEngine, make_context: Callable[..., PolicyContext]
) -> Callable[[OfferOption, BuyerProfile, str | None], PolicyDecision]:
    def judged(option: OfferOption, profile: BuyerProfile, amount: str | None) -> PolicyDecision:
        with request_as_sent(_request(amount)):
            return engine.evaluate(option, profile, make_context())

    return judged


@pytest.fixture
def alone(hotel: BuyerProfile) -> BuyerProfile:
    """The hotel as a buyer who switched ordering alone on. Nothing else differs from the shipped file."""
    return hotel.model_copy(update={"auto_order_enabled": True})


def _spend_rule(decision: PolicyDecision) -> FiredRule:
    return next(rule for rule in decision.fired if rule.rule_id == "P-01")


def test_an_option_above_the_named_amount_goes_to_a_person_and_the_sentence_says_which_limit(
    judge: Callable[..., PolicyDecision], alone: BuyerProfile, milk_496: OfferOption
) -> None:
    decision = judge(milk_496, alone, "400")

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-01",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert _spend_rule(decision).sentence == (
        "The total of €496.00 before tax is above the €400 you named for this request."
    )
    assert decision.sentence == (
        "The agent cannot place this order alone: the total of €496.00 before tax is above the €400 you named for "
        "this request (P-01). It needs the purchasing manager."
    )


def test_the_decision_carries_the_amount_and_where_the_limit_came_from(
    judge: Callable[..., PolicyDecision], alone: BuyerProfile, milk_496: OfferOption
) -> None:
    facts = _spend_rule(judge(milk_496, alone, "400")).facts

    assert facts["option.net_eur"] == 496.0
    assert facts["request.max_net_eur"] == 400.0 and facts["profile.max_order_net_eur"] == 750.0
    assert facts["order.spend_limit_net_eur"] == 400.0
    assert facts["order.spend_limit_source"] == "the amount the request names"


def test_an_option_within_both_limits_is_ordered_alone_and_the_sentence_names_both(
    judge: Callable[..., PolicyDecision], alone: BuyerProfile, milk_496: OfferOption
) -> None:
    decision = judge(milk_496, alone, "600")

    assert decision.verdict is Verdict.AUTO and decision.fired == ()
    assert (
        "the total of €496.00 before tax is within the €750 limit per order and the €600 you named for this "
        "request;" in decision.sentence
    )


def test_with_no_amount_named_nothing_changes(
    judge: Callable[..., PolicyDecision], engine: RulePolicyEngine, alone: BuyerProfile, milk_496: OfferOption,
    make_context: Callable[..., PolicyContext],
) -> None:
    named_none = judge(milk_496, alone, None)
    nobody_said = engine.evaluate(milk_496, alone, make_context())  # no request as sent at all

    assert named_none == nobody_said and named_none.verdict is Verdict.AUTO
    assert "the total of €496.00 before tax is within the €750 limit per order;" in named_none.sentence


def test_the_amount_never_raises_the_buyers_own_limit(
    judge: Callable[..., PolicyDecision], alone: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption],
) -> None:
    one = make_line("469363", "Lactose-free milk 1L", quantity="400", unit_net_price="2.48")
    dear = make_option((one,), net="992.00")

    decision = judge(dear, alone, "5000")

    assert decision.rule_ids == ("P-01",)
    assert _spend_rule(decision).sentence == (  # today's sentence, word for word
        "The total of €992.00 before tax is above the €750 limit per order of Harbourside Hotel."
    )
    facts = _spend_rule(decision).facts
    assert facts["order.spend_limit_net_eur"] == 750.0 and facts["request.max_net_eur"] == 5000.0
    assert facts["order.spend_limit_source"] == "the buyer's limit per order"


def test_above_both_limits_the_lower_one_is_named(
    judge: Callable[..., PolicyDecision], alone: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption],
) -> None:
    one = make_line("469363", "Lactose-free milk 1L", quantity="400", unit_net_price="2.48")
    dear = make_option((one,), net="992.00")

    assert _spend_rule(judge(dear, alone, "600")).sentence == (
        "The total of €992.00 before tax is above the €600 you named for this request."
    )
    assert _spend_rule(judge(dear, alone, "750")).sentence == (  # the same amount: the buyer's own is said
        "The total of €992.00 before tax is above the €750 limit per order of Harbourside Hotel."
    )


def test_a_total_equal_to_the_named_amount_is_within_it(
    judge: Callable[..., PolicyDecision], alone: BuyerProfile, milk_496: OfferOption
) -> None:
    assert judge(milk_496, alone, "496").verdict is Verdict.AUTO
    assert judge(milk_496, alone, "495.99").rule_ids == ("P-01",)


def test_the_amount_is_not_the_limit_per_day(
    engine: RulePolicyEngine, alone: BuyerProfile, milk_496: OfferOption, make_context: Callable[..., PolicyContext]
) -> None:
    """€2,000 already committed today: €2,496.00 with this order, within the hotel's €3,000 per day, whatever
    amount the request names."""
    with request_as_sent(_request("600")):
        decision = engine.evaluate(milk_496, alone, make_context("2000"))

    assert decision.verdict is Verdict.AUTO


def test_with_ordering_alone_off_the_named_amount_is_still_the_reason_given(
    judge: Callable[..., PolicyDecision], hotel: BuyerProfile, milk_496: OfferOption
) -> None:
    decision = judge(milk_496, hotel, "400")

    assert decision.verdict is Verdict.APPROVAL and "P-01" in decision.rule_ids
    assert "above the €400 you named for this request" in decision.sentence


def test_what_the_agent_may_do_alone_is_described_as_before(engine: RulePolicyEngine, hotel: BuyerProfile) -> None:
    """GET /v1/authority describes the buyer's settings: an amount is a request's, so nothing moves there."""
    rule = next(rule for rule in engine.describe_authority(hotel).rules if rule.rule_id == "P-01")

    assert rule.sentence == "An order above €750 before tax goes to the purchasing manager."
