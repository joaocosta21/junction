"""F-07, defence in depth: an option that carries a needed-by check, with a line whose delivery date is UNKNOWN.

The offer gives MET only when the delivery-date claim of every line is CONFIRMED, so the two agree today. The
policy does not rest on that alone: a line that says UNKNOWN under a needed-by check goes to a human by itself.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from tta.contracts.availability import ClaimCheck
from tta.contracts.common import ApproverRole, CheckResult, ClaimName, ClaimStatus, Verdict
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy import RulePolicyEngine

MILK = "Arla Café milk 1 L UHT (463380)"
NOT_CONFIRMED = "the delivery date is not confirmed by Valio Aimo"


def test_a_line_with_an_unknown_delivery_date_goes_to_a_human_although_the_needed_by_check_says_met(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(delivery_date_claim=ClaimStatus.UNKNOWN),), needed_by=CheckResult.MET)

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-07",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    f07 = decision.fired[0]
    assert f07.fixed and f07.product_id == "463380" and f07.approver_role is ApproverRole.PURCHASING_MANAGER
    assert f07.sentence == f"For {MILK} {NOT_CONFIRMED}."
    assert f07.facts == {
        "line.price_claim": "CONFIRMED",
        "line.delivery_date_claim": "UNKNOWN",
        "option.needed_by_check": "MET",
        "line.name": "Arla Café milk 1 L UHT",
        "line.product_id": "463380",
        "line.unconfirmed_reason": NOT_CONFIRMED,
    }


@pytest.mark.parametrize("result", [CheckResult.UNVERIFIED, CheckResult.NOT_MET])
def test_the_line_is_named_next_to_the_option_when_the_needed_by_check_is_not_met_either(
    result: CheckResult, engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    lines = (make_line("462775", "Milk drink"), make_line(delivery_date_claim=ClaimStatus.UNKNOWN))

    decision = engine.evaluate(make_option(lines, needed_by=result), hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL
    assert [(rule.rule_id, rule.product_id) for rule in decision.fired] == [("F-07", "463380"), ("F-07", None)]


@pytest.mark.parametrize("status", [ClaimStatus.UNKNOWN, ClaimStatus.CONFIRMED])
def test_an_option_with_no_needed_by_check_is_unchanged(
    status: ClaimStatus, engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(delivery_date_claim=status),), needed_by=None)

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-10",)


def test_on_an_option_with_no_needed_by_check_the_sentence_gives_the_price_as_the_only_reason(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = make_line(price_claim=ClaimStatus.UNKNOWN, delivery_date_claim=ClaimStatus.UNKNOWN)

    decision = engine.evaluate(make_option((line,), needed_by=None), hotel, make_context())

    assert decision.rule_ids == ("F-07",)
    assert decision.fired[0].sentence == f"For {MILK} the price is not confirmed by Valio Aimo."
    assert decision.fired[0].facts["option.needed_by_check"] == "NOT_ASKED"


def test_a_dated_line_gives_both_reasons_when_neither_price_nor_delivery_date_is_confirmed(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = make_line(price_claim=ClaimStatus.UNKNOWN, delivery_date_claim=ClaimStatus.UNKNOWN)

    decision = engine.evaluate(make_option((line,)), hotel, make_context())

    assert decision.rule_ids == ("F-07",)
    assert decision.fired[0].sentence == f"For {MILK} the price is not confirmed by Valio Aimo and {NOT_CONFIRMED}."


def test_a_confirmed_delivery_date_with_a_second_statement_that_says_unknown_counts_as_unknown(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = make_line()
    extra = ClaimCheck(claim=ClaimName.DELIVERY_DATE, status=ClaimStatus.UNKNOWN, sentence="A second statement.")
    twice = line.model_copy(update={"claims": (*line.claims, extra)})

    decision = engine.evaluate(make_option((twice,)), hotel, make_context())

    assert decision.rule_ids == ("F-07",) and decision.fired[0].facts["line.delivery_date_claim"] == "UNKNOWN"


def test_a_ruled_out_delivery_date_is_still_said_to_be_ruled_out(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(delivery_date_claim=ClaimStatus.RULED_OUT),))

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.rule_ids == ("F-07",)
    assert decision.fired[0].sentence == f"For {MILK} the delivery date is ruled out."


def test_no_profile_setting_lets_the_agent_order_alone_past_an_unknown_delivery_date_of_a_dated_option(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    widest = hotel.model_copy(update={
        "max_order_net_eur": Decimal(10**9), "max_daily_net_eur": Decimal(10**9), "min_fill_ratio": Decimal(0),
    })
    option = make_option((make_line(delivery_date_claim=ClaimStatus.UNKNOWN),))

    decision = engine.evaluate(option, widest, make_context())

    assert decision.rule_ids == ("F-07",) and decision.verdict is Verdict.APPROVAL and decision.fired[0].fixed
