"""A missing fact never passes: it goes to a human by F-03, and never yields AUTO (SPEC section 7)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest

from tta.contracts.common import AllergenRelation, AllergenStrictness, ApproverRole, Verdict
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, FiredRule, PolicyContext, PolicyDecision
from tta.policy import RulePolicyEngine


def _f03(decision: PolicyDecision) -> list[FiredRule]:
    return [rule for rule in decision.fired if rule.rule_id == "F-03"]


def test_an_unknown_day_spend_goes_to_finance_by_f03_and_never_to_auto(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option(), hotel, make_context(day_committed=None))

    assert decision.verdict is Verdict.APPROVAL
    assert decision.rule_ids == ("F-03",)
    assert decision.required_roles == (ApproverRole.FINANCE,)
    f03 = decision.fired[0]
    assert f03.fixed and f03.verdict is Verdict.APPROVAL and f03.product_id is None
    assert f03.facts == {
        "missing_fact": "order.day_net_eur",
        "reason": "today's committed spend did not come with the order context",
        "needed_by": ["P-02"],
    }
    assert f03.sentence == (
        "Today's spend with this order is missing (today's committed spend did not come with the order "
        "context), so rule P-02 cannot be checked."
    )


def test_a_product_that_does_not_say_whether_it_is_sold_by_weight_goes_to_a_human(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    option = make_option((make_line("464744", "Beef chuck", variable_weight=None),))

    decision = engine.evaluate(option, hotel, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    f03 = decision.fired[0]
    assert f03.product_id == "464744"
    assert f03.facts["missing_fact"] == "line.variable_weight" and f03.facts["needed_by"] == ["P-06"]
    assert f03.sentence == (
        "The variable-weight statement of Beef chuck (464744) is missing (the product file does not say "
        "whether it is sold by variable weight), so rule P-06 cannot be checked."
    )


def test_a_missing_allergen_check_under_a_profile_with_exclusions_goes_to_the_dietitian(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option((make_line(allergen_check=None),)), ward, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03",)
    assert decision.required_roles == (ApproverRole.DIETITIAN,)
    f03 = decision.fired[0]
    assert f03.facts["missing_fact"] == "line.allergen_outcomes"
    assert f03.facts["needed_by"] == ["F-02", "P-04"]  # one entry, naming every rule that needed the fact
    assert f03.sentence == (
        "The allergen check of Arla Café milk 1 L UHT (463380) is missing (no allergen check came with this "
        "line), so rules F-02 and P-04 cannot be checked."
    )


def test_an_allergen_check_that_skips_an_excluded_allergen_counts_as_missing(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    only_milk = make_allergen_check({"AM": AllergenRelation.FREE_FROM})

    decision = engine.evaluate(make_option((make_line(allergen_check=only_milk),)), ward, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03",)
    assert decision.fired[0].facts["reason"] == "the allergen check does not cover AW"


def test_an_allergen_check_run_under_a_weaker_rule_than_the_profile_counts_as_missing(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    lenient = make_allergen_check(
        {"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.NOT_STATED},
        strictness=AllergenStrictness.DECLARED_ONLY,
    )

    decision = engine.evaluate(make_option((make_line(allergen_check=lenient),)), ward, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03",)
    assert decision.fired[0].facts["reason"] == "the allergen check was not run under the profile's STRICT rule"


def test_a_declared_allergen_still_blocks_when_part_of_the_check_is_missing(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    only_milk = make_allergen_check({"AM": AllergenRelation.CONTAINS})

    decision = engine.evaluate(make_option((make_line(allergen_check=only_milk),)), ward, make_context())

    assert decision.verdict is Verdict.BLOCK
    assert decision.rule_ids == ("F-02", "F-03")


def test_no_allergen_check_is_not_a_missing_fact_when_nobody_excluded_anything(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option((make_line(allergen_check=None),)), hotel, make_context())

    assert hotel.excluded_allergens == () and decision.verdict is Verdict.AUTO


def test_an_order_without_a_fresh_check_goes_to_a_human(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option(), hotel, make_context(at_order_time=True, revalidation=None))

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03",)
    assert decision.fired[0].facts["missing_fact"] == "revalidation.ok"
    assert decision.fired[0].facts["needed_by"] == ["F-04"]


def test_an_expired_option_blocks_at_order_time_even_without_a_fresh_check(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], now,
) -> None:
    option = make_option(valid_until=now - timedelta(hours=1))

    decision = engine.evaluate(option, hotel, make_context(at_order_time=True, revalidation=None))

    assert decision.verdict is Verdict.BLOCK and decision.rule_ids == ("F-04",)


def test_an_option_without_a_valid_until_cannot_be_ordered_alone(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_revalidation: Callable,
) -> None:
    context = make_context(at_order_time=True, revalidation=make_revalidation())

    decision = engine.evaluate(make_option(valid_until=None), hotel, context)

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-03",)
    assert decision.fired[0].facts["missing_fact"] == "option.expired"


def test_the_order_time_facts_are_not_needed_while_the_offer_is_built(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option(valid_until=None), hotel, make_context(at_order_time=False))

    assert decision.verdict is Verdict.AUTO


def test_every_missing_fact_is_listed_once_per_line_next_to_the_rules_that_fired(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    lines = (make_line("464744", "Beef chuck", variable_weight=None), make_line("466988", "Beef", variable_weight=None))

    decision = engine.evaluate(make_option(lines, net="900.00"), hotel, make_context(day_committed=None))

    assert decision.rule_ids == ("F-03", "F-03", "F-03", "P-01")
    assert [(rule.facts["missing_fact"], rule.product_id) for rule in _f03(decision)] == [
        ("order.day_net_eur", None), ("line.variable_weight", "464744"), ("line.variable_weight", "466988"),
    ]
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER, ApproverRole.FINANCE)


@pytest.mark.parametrize(
    "case",
    ["day spend", "variable weight", "allergen check", "fresh check", "valid until",
     "quantity_claim", "price_claim", "delivery_date_claim"],
)
def test_no_missing_fact_ever_yields_auto(
    case: str, engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable, make_revalidation: Callable,
) -> None:
    check = make_allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.FREE_FROM})
    line = {"allergen_check": None if case == "allergen check" else check,
            "variable_weight": None if case == "variable weight" else False}
    if case.endswith("_claim"):
        line[case] = None  # the line does not carry that claim
    option = make_option((make_line(**line),), valid_until=None) if case == "valid until" else make_option(
        (make_line(**line),)
    )
    context = make_context(
        day_committed=None if case == "day spend" else "0",
        at_order_time=True,
        revalidation=None if case == "fresh check" else make_revalidation(),
    )

    decision = engine.evaluate(option, ward, context)

    assert decision.verdict is Verdict.APPROVAL
    assert "F-03" in decision.rule_ids
