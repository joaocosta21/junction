"""The decisions the demo scenarios rest on (SPEC sections 7 and 13, AIMO/PLAN.md sections 2 and 3)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from tta.contracts.common import (
    AllergenRelation,
    ApproverRole,
    AvailabilityState,
    ClaimStatus,
    OptionKind,
    Verdict,
)
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.contracts.ports import PolicyEngine
from tta.policy import RulePolicyEngine


def _canonical_option(make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption]) -> OfferOption:
    """Friday's confirmed suggestion: 698 x 463380 + 51 x 462775 = 749 L of 1,000 L for 1,980.77 before tax."""
    lines = (
        make_line("463380", "Arla Café milk 1 L UHT", quantity="698", unit_net_price="2.65"),
        make_line("462775", "Arla fat-free milk drink 1 L UHT", quantity="51", unit_net_price="2.57"),
    )
    return make_option(lines, net="1980.77", fill_ratio="0.749")


def _ward_option(
    make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption], make_allergen_check: Callable
) -> OfferOption:
    """Scenario 2: 200 x 464056 at 2.14, milk and gluten both FREE_FROM, every claim confirmed."""
    check = make_allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.FREE_FROM})
    line = make_line("464056", "Alpro Barista Soya 1 L", quantity="200", unit_net_price="2.14", allergen_check=check)
    return make_option((line,), net="428.00", fill_ratio="1.0")


def test_the_engine_implements_the_policy_engine_port(engine: RulePolicyEngine) -> None:
    assert isinstance(engine, PolicyEngine)


def test_canonical_option_goes_to_the_purchasing_manager_by_p01_and_p03(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext], now: datetime,
) -> None:
    option = _canonical_option(make_line, make_option)

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL
    assert decision.rule_ids == ("P-01", "P-03")
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert all(not rule.fixed and rule.verdict is Verdict.APPROVAL for rule in decision.fired)
    assert decision.profile_id == "hotel-kitchen"
    assert decision.evaluated_at == now
    assert decision.policy_hash == engine.policy_hash(hotel)


def test_canonical_option_is_explained_in_one_sentence_with_the_numbers_and_the_rules(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(_canonical_option(make_line, make_option), hotel, make_context())

    assert decision.sentence == (
        "The agent cannot place this order alone: the total of €1,980.77 before tax is above the €750 limit "
        "per order of profile hotel-kitchen (P-01) and only 74.9% of the requested quantity is covered, below "
        "the 90% minimum (covered: 749 of 1,000 L) (P-03). It needs the purchasing manager."
    )
    assert decision.fired[0].sentence == (
        "The total of €1,980.77 before tax is above the €750 limit per order of profile hotel-kitchen."
    )
    assert decision.fired[0].facts == {
        "option.net_eur": 1980.77, "profile.max_order_net_eur": 750.0, "profile.profile_id": "hotel-kitchen",
    }
    assert decision.fired[1].facts == {
        "option.fill_ratio": 0.749, "profile.min_fill_ratio": 0.9, "option.least_covered": "the requested quantity",
        "option.coverage_by_line": "749 of 1,000 L",
    }


def test_unconfirmed_alternative_goes_to_a_human_by_f01_and_p01(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    line = make_line(
        "464306", "Lactose-free milk drink 1 L", quantity="1000", unit_net_price="1.01",
        state=AvailabilityState.QUANTITY_NOT_CONFIRMED, quantity_claim=ClaimStatus.UNKNOWN,
    )
    option = make_option((line,), net="1010.00", fill_ratio="1", kind=OptionKind.ALTERNATIVE_UNCONFIRMED)

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL
    assert decision.rule_ids == ("F-01", "P-01")
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    f01 = decision.fired[0]
    assert f01.fixed and f01.product_id == "464306" and f01.approver_role is ApproverRole.PURCHASING_MANAGER
    assert f01.sentence == (
        "The quantity of 1,000 × Lactose-free milk drink 1 L (464306) is not confirmed by Valio Aimo."
    )


def test_tonights_partial_fill_of_435_litres_goes_to_the_purchasing_manager_by_p01_and_p03(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """The capture of 14 Nov confirms 435 L of plain lactose-free milk, cheapest first. Until milk for coffee
    became a product type of its own, 565 x 463380 Arla Cafè milk filled the rest (€2,580.64, P-01 alone)."""
    lines = (
        make_line("469363", "Lactose-free milk 1 L", quantity="384", unit_net_price="2.48"),
        make_line("462775", "Arla fat-free milk drink 1 L UHT", quantity="51", unit_net_price="2.57"),
    )
    option = make_option(lines, net="1083.39", fill_ratio="0.435")

    decision = engine.evaluate(option, hotel, make_context())

    assert sum(line.net for line in lines) == Decimal("1083.39")
    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-01", "P-03")
    assert decision.fired[1].sentence == (
        "Only 43.5% of the requested quantity is covered, below the 90% minimum (covered: 435 of 1,000 L)."
    )
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)


def test_backup_scenario_variable_weight_beef_goes_to_the_purchasing_manager(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """SPEC section 13, backup: 30 kg of 466988 at 16.88 per kg; the total is a ceiling."""
    line = make_line("466988", "Beef chuck", quantity="30", unit_net_price="16.88", variable_weight=True)
    option = make_option((line,), net="506.40", is_ceiling=True)

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-06",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert decision.fired[0].sentence == (
        "Beef chuck (466988) is sold by variable weight, so its final price is not fixed in advance."
    )


def test_ward_order_within_every_limit_is_placed_by_the_agent_alone(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    option = _ward_option(make_line, make_option, make_allergen_check)

    decision = engine.evaluate(option, ward, make_context())

    assert decision.verdict is Verdict.APPROVAL
    assert decision.rule_ids == ("F-10",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert "F-10" in decision.sentence


def test_the_same_ward_order_goes_to_finance_once_the_day_would_pass_1500(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    option = _ward_option(make_line, make_option, make_allergen_check)

    decision = engine.evaluate(option, ward, make_context(day_committed="1100.00"))

    assert decision.verdict is Verdict.APPROVAL
    assert decision.rule_ids == ("P-02",)
    assert decision.required_roles == (ApproverRole.FINANCE,)
    assert decision.fired[0].sentence == (
        "With this order today's spend would reach €1,528.00 before tax, above the €1,500 limit per day of "
        "profile allergy-ward."
    )
    assert decision.fired[0].facts["order.day_net_eur"] == 1528.0


def test_a_day_that_lands_exactly_on_the_limit_does_not_pass_it(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    option = _ward_option(make_line, make_option, make_allergen_check)

    decision = engine.evaluate(option, ward, make_context(day_committed="1072.00"))

    assert decision.verdict is Verdict.APPROVAL


def test_the_most_severe_verdict_wins_and_every_fired_rule_is_listed(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    check = make_allergen_check({"AM": AllergenRelation.CONTAINS, "AW": AllergenRelation.FREE_FROM})
    line = make_line(
        "463380", "Arla Café milk 1 L UHT", quantity="400", allergen_check=check,
        state=AvailabilityState.QUANTITY_NOT_CONFIRMED,
    )
    option = make_option((line,), net="1060.00", fill_ratio="0.8")

    decision = engine.evaluate(option, ward, make_context())

    assert decision.verdict is Verdict.BLOCK
    assert decision.rule_ids == ("F-01", "F-02", "P-01", "P-03")
    assert [rule.verdict for rule in decision.fired] == [
        Verdict.APPROVAL, Verdict.BLOCK, Verdict.APPROVAL, Verdict.APPROVAL,
    ]
    assert decision.required_roles == ()  # nobody can sign off a blocked order
    assert decision.sentence == (
        "This order cannot be placed, even with approval: Arla Café milk 1 L UHT (463380) declares an allergen "
        "this buyer excludes: AM (contains) (F-02)."
    )


def test_roles_of_every_rule_that_asks_for_a_human_are_required(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line(has_deposits=True),), net="900.00")

    decision = engine.evaluate(option, hotel, make_context(day_committed="2500.00"))

    assert decision.rule_ids == ("P-01", "P-02", "P-07")
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER, ApproverRole.FINANCE)
    assert decision.sentence.endswith("It needs the purchasing manager and finance.")


def test_the_same_inputs_give_the_same_decision(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = _canonical_option(make_line, make_option)

    first = engine.evaluate(option, hotel, make_context())
    second = RulePolicyEngine.from_files().evaluate(option, hotel, make_context())

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
