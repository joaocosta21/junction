"""P-02 says both parts of the day's spend (review A4, finding H2; L4a's item 3): what is ordered and what is
waiting for a person. A waiting order counts (PLAN decision 9), and the person who signs can tell a day of orders
from a day of requests nobody has approved yet. Without the waiting part the sentence says the total only."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from tta.contracts.common import ApproverRole, Verdict
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy import RulePolicyEngine
from tta.policy.facts import OrderScope, read_fact
from tta.policy.reading import Missing

TOTAL_ONLY = (
    "With this order today's spend would reach €3,772.17 before tax, above the €3,000 limit per day of "
    "Harbourside Hotel."
)


@pytest.fixture
def third_of_the_day(make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption]) -> OfferOption:
    """Scenario 1's €1,083.39 asked for a third time while the first two still wait: €2,688.78 before it.
    (L4a measured €3,772.17 with €2,688.78 waiting, at the default clock; the figures here are hand-built.)"""
    return make_option((make_line(quantity="435", unit_net_price="2.49"),), net="1083.39")


def _p02(engine: RulePolicyEngine, option: OfferOption, profile: BuyerProfile, context: PolicyContext):
    decision = engine.evaluate(option, profile, context)
    return decision, next(rule for rule in decision.fired if rule.rule_id == "P-02")


def test_p02_says_what_is_ordered_what_is_waiting_and_what_this_order_adds(
    engine: RulePolicyEngine, hotel: BuyerProfile, third_of_the_day: OfferOption,
    make_context: Callable[..., PolicyContext],
) -> None:
    decision, p02 = _p02(engine, third_of_the_day, hotel, make_context("2688.78", day_waiting="2688.78"))

    assert decision.verdict is Verdict.APPROVAL and ApproverRole.FINANCE in decision.required_roles
    assert p02.sentence == (
        "With this order today's spend would reach €3,772.17 before tax (€0.00 ordered, €2,688.78 waiting for a "
        "person, and this order's €1,083.39), above the €3,000 limit per day of Harbourside Hotel."
    )
    assert p02.facts["order.day_net_eur"] == 3772.17
    assert p02.facts["context.day_committed_net_eur"] == 2688.78
    assert p02.facts["context.day_waiting_net_eur"] == 2688.78


def test_the_parts_add_up_when_some_of_the_day_is_ordered(
    engine: RulePolicyEngine, hotel: BuyerProfile, third_of_the_day: OfferOption,
    make_context: Callable[..., PolicyContext],
) -> None:
    _, p02 = _p02(engine, third_of_the_day, hotel, make_context("2688.78", day_waiting="1083.39"))

    assert "(€1,605.39 ordered, €1,083.39 waiting for a person, and this order's €1,083.39)" in p02.sentence


def test_without_the_waiting_part_p02_says_the_total_only_and_still_fires(
    engine: RulePolicyEngine, hotel: BuyerProfile, third_of_the_day: OfferOption,
    make_context: Callable[..., PolicyContext],
) -> None:
    decision, p02 = _p02(engine, third_of_the_day, hotel, make_context("2688.78"))

    assert p02.sentence == TOTAL_ONLY
    assert "F-03" not in decision.rule_ids  # the waiting part is never a missing fact
    assert p02.facts["context.day_waiting_net_eur"] is None


@pytest.mark.parametrize("waiting", ["3000.00", "-1.00"], ids=["more than the day's spend", "negative"])
def test_a_waiting_part_that_cannot_be_part_of_the_days_spend_is_not_said(
    engine: RulePolicyEngine, hotel: BuyerProfile, third_of_the_day: OfferOption,
    make_context: Callable[..., PolicyContext], waiting: str,
) -> None:
    _, p02 = _p02(engine, third_of_the_day, hotel, make_context("2688.78", day_waiting=waiting))

    assert p02.sentence == TOTAL_ONLY


def test_the_waiting_part_changes_no_verdict(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    small = make_option((make_line(),), net="265.00")

    with_parts = engine.evaluate(small, hotel, make_context("2000.00", day_waiting="2000.00"))
    without = engine.evaluate(small, hotel, make_context("2000.00"))

    assert with_parts.rule_ids == without.rule_ids == ("F-10",)
    assert with_parts.sentence == without.sentence


def test_the_fact_is_missing_without_the_days_spend(
    hotel: BuyerProfile, third_of_the_day: OfferOption, make_context: Callable[..., PolicyContext],
) -> None:
    scope = OrderScope(third_of_the_day, hotel, make_context(None), {})

    assert isinstance(read_fact("order.day_net_said", scope), Missing)
    assert isinstance(read_fact("context.day_waiting_net_eur", scope), Missing)
    known = OrderScope(third_of_the_day, hotel, make_context("10", day_waiting="4"), {})
    assert read_fact("context.day_waiting_net_eur", known) == Decimal("4.00")
