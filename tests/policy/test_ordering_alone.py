"""Ordering alone is a buyer setting, off in every shipped profile (rule F-10, `tta.policy.human_approval`).

Valio Aimo, 14 Nov 2026: "the final submition should always have the input from the user", and of a setting for
automatic orders: "after and if you are 100% sure yes". So: off, every order needs a person; on, the agent orders
alone only what no rule catches, and whatever is not confirmed still goes to a person.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tta.contracts.common import AllergenRelation, ApproverRole, AvailabilityState, CheckResult, ClaimStatus, Verdict
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy import PROFILES_DIR, RulePolicyEngine, load_profiles
from tta.policy.human_approval import HUMAN_APPROVAL, require_human_approval


@pytest.fixture
def alone(ward: BuyerProfile) -> BuyerProfile:
    """The ward as a buyer who switched ordering alone on. Nothing else differs from the shipped file."""
    return ward.model_copy(update={"auto_order_enabled": True})


@pytest.fixture
def ward_200_litres(
    make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption], make_allergen_check: Callable,
) -> Callable[..., OfferOption]:
    """Scenario 2: 200 x 464013 at 2.01, both excluded allergens stated free-from, every claim confirmed."""
    def build(
        *, net: str = "402.00", needed_by: CheckResult | None = CheckResult.MET, **line: object
    ) -> OfferOption:
        check = make_allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.FREE_FROM})
        one = make_line(
            "464013", "Alpro No Sugars Soya drink 1L", quantity="200", unit_net_price="2.01", allergen_check=check,
            **line,
        )
        return make_option((one,), net=net, needed_by=needed_by)

    return build


def test_no_shipped_profile_lets_the_agent_order_alone(engine: RulePolicyEngine) -> None:
    profiles = load_profiles(PROFILES_DIR, frozenset())

    assert profiles and all(profile.auto_order_enabled is False for profile in profiles.values())
    assert all(engine.get_profile(profile_id).auto_order_enabled is False for profile_id in engine.profile_ids())


def test_with_the_setting_off_a_fully_confirmed_order_within_every_limit_needs_the_purchasing_manager(
    engine: RulePolicyEngine, ward: BuyerProfile, ward_200_litres: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(ward_200_litres(), ward, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-10",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert decision.sentence == (
        "Every order needs human approval before it can be confirmed (F-10). It needs the purchasing manager."
    )


def test_with_the_setting_on_and_everything_confirmed_the_ward_orders_its_200_litres_alone(
    engine: RulePolicyEngine, alone: BuyerProfile, ward_200_litres: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(ward_200_litres(), alone, make_context())

    assert decision.verdict is Verdict.AUTO and decision.fired == () and decision.required_roles == ()
    assert decision.sentence == (
        "The agent may place this order alone: the total of €402.00 before tax is within the €500 limit per "
        "order, today's spend would be €402.00 of the €1,500 limit per day of profile allergy-ward, 100% of the "
        "requested quantity is covered, and no rule asks for a human."
    )


@pytest.mark.parametrize(
    ("line", "rule_id"),
    [
        ({"state": AvailabilityState.QUANTITY_NOT_CONFIRMED}, "F-01"),  # Valio's very large stock values
        ({"quantity_claim": None}, "F-03"),  # a fact a rule needs is missing
        ({"price_claim": ClaimStatus.UNKNOWN}, "F-07"),
        ({"delivery_date_claim": ClaimStatus.RULED_OUT}, "F-07"),
        ({"variable_weight": None}, "F-03"),
    ],
)
def test_with_the_setting_on_whatever_is_not_confirmed_still_goes_to_a_person(
    line: dict[str, object], rule_id: str, engine: RulePolicyEngine, alone: BuyerProfile,
    ward_200_litres: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(ward_200_litres(**line), alone, make_context())

    assert decision.verdict is Verdict.APPROVAL and rule_id in decision.rule_ids
    assert "F-10" not in decision.rule_ids and decision.required_roles


@pytest.mark.parametrize(
    ("line", "named"),
    [
        ({"origin_claim": ClaimStatus.UNKNOWN}, "the origin of 464013"),
        ({"origin_claim": None}, "the origin of 464013"),  # a statement the line does not carry is not confirmed
        ({"allergens_claim": ClaimStatus.UNKNOWN}, "the allergen statement of 464013"),
    ],
)
def test_with_the_setting_on_a_statement_no_other_rule_reads_still_keeps_a_person_on_the_order(
    line: dict[str, object], named: str, engine: RulePolicyEngine, alone: BuyerProfile,
    ward_200_litres: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    """Valio Aimo on ordering alone: "after and if you are 100% sure yes". No rule of the file reads the origin
    statement, and the allergen statement only against an exclusion; F-10 does, when the setting is on."""
    decision = engine.evaluate(ward_200_litres(**line), alone, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-10",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert decision.fired[0].facts == {"profile.auto_order_enabled": True, "not_confirmed": [named]}
    assert decision.sentence == (
        "The agent orders alone only when every statement of the offer is confirmed (F-10). "
        f"Not confirmed: {named}. It needs the purchasing manager."
    )


def test_with_the_setting_on_a_request_without_a_date_has_no_confirmed_delivery_date_and_goes_to_a_person(
    engine: RulePolicyEngine, alone: BuyerProfile, ward_200_litres: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    option = ward_200_litres(needed_by=None, delivery_date_claim=ClaimStatus.UNKNOWN)

    decision = engine.evaluate(option, alone, make_context())

    assert decision.rule_ids == ("F-10",) and "the delivery date of 464013" in decision.sentence


def test_with_the_setting_on_an_option_that_does_not_verifiably_meet_the_date_goes_to_a_person(
    engine: RulePolicyEngine, alone: BuyerProfile, ward_200_litres: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(ward_200_litres(needed_by=CheckResult.UNVERIFIED), alone, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("F-07",)


def test_with_the_setting_on_the_buyers_own_limits_still_send_an_order_to_a_person(
    engine: RulePolicyEngine, alone: BuyerProfile, ward_200_litres: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(ward_200_litres(net="500.01"), alone, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-01",)


def test_f10_is_not_added_when_another_rule_already_names_who_signs(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    doubt = make_allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.MAY_CONTAIN})

    decision = engine.evaluate(make_option((make_line(allergen_check=doubt),)), ward, make_context())

    assert decision.rule_ids == ("P-04",) and decision.required_roles == (ApproverRole.DIETITIAN,)


def test_f10_leaves_a_blocked_order_blocked(
    engine: RulePolicyEngine, ward: BuyerProfile, make_line: Callable[..., OfferLine],
    make_option: Callable[..., OfferOption], make_context: Callable[..., PolicyContext],
    make_allergen_check: Callable,
) -> None:
    declared = make_allergen_check({"AM": AllergenRelation.CONTAINS, "AW": AllergenRelation.FREE_FROM})

    decision = engine.evaluate(make_option((make_line(allergen_check=declared),)), ward, make_context())

    assert decision.verdict is Verdict.BLOCK and "F-10" not in decision.rule_ids and decision.required_roles == ()


def test_the_rule_applied_a_second_time_changes_nothing(
    engine: RulePolicyEngine, ward: BuyerProfile, alone: BuyerProfile, ward_200_litres: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    """The order service applies it again at order time (`tta.orders.checking`)."""
    option = ward_200_litres()
    waiting = engine.evaluate(option, ward, make_context())
    free = engine.evaluate(option, alone, make_context())

    assert require_human_approval(waiting, ward, option) == waiting
    assert require_human_approval(free, alone, option) == free
    # A decision that reached the order service as AUTO under a profile with the setting off is still stopped.
    stopped = require_human_approval(free, ward, option)
    assert stopped.verdict is Verdict.APPROVAL and stopped.rule_ids == (HUMAN_APPROVAL.rule_id,)


def test_the_setting_and_the_rule_are_part_of_the_policy_hash(
    engine: RulePolicyEngine, ward: BuyerProfile, alone: BuyerProfile,
) -> None:
    assert engine.policy_hash(ward) != engine.policy_hash(alone)
