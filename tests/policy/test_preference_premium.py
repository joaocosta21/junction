"""P-09: what a preference (most reliable, lowest carbon, earliest) may cost above the cheapest confirmed option.

The offer puts the amount on the option ranked by the preference (`OfferOption.net_above_cheapest`). A profile may
set the share it accepts without a person; above it the option goes to the purchasing manager, and the sentence
states the amount and the share. The setting can be at most the share above which the offer stops ranking the
preferred option first, so the two cannot disagree.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tta.contracts.common import ApproverRole, Verdict
from tta.contracts.offer import OfferOption
from tta.contracts.policy import MAX_PREFERENCE_PREMIUM_RATIO, BuyerProfile, PolicyContext
from tta.offers.preference import MAX_PREFERENCE_PREMIUM
from tta.policy import RulePolicyEngine
from tta.policy.facts import OrderScope, read_fact


@pytest.fixture
def preferred(make_option: Callable[..., OfferOption]) -> Callable[[str, str | None], OfferOption]:
    """An option ranked by a preference: its net total and what it costs above the cheapest confirmed option."""

    def build(net: str, more: str | None) -> OfferOption:
        return make_option(net=net).model_copy(update={"net_above_cheapest": None if more is None else Decimal(more)})

    return build


@pytest.fixture
def a_tenth(hotel: BuyerProfile) -> BuyerProfile:
    return hotel.model_copy(update={"max_preference_premium_ratio": Decimal("0.1")})


def test_a_preference_that_costs_more_than_the_profile_accepts_goes_to_the_purchasing_manager(
    engine: RulePolicyEngine, a_tenth: BuyerProfile, preferred: Callable[[str, str | None], OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(preferred("120.00", "20.00"), a_tenth, make_context())

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-09",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert decision.fired[0].fixed is False
    assert decision.fired[0].sentence == (
        "This option is ranked by the buyer's preference and costs €20.00 more before tax than the cheapest "
        "confirmed option, a premium of 20%, above the 10% that Harbourside Hotel lets a preference add without a "
        "human."
    )
    assert decision.fired[0].facts == {
        "profile.limits_preference_premium": True, "option.preference_premium_ratio": 0.2,
        "profile.max_preference_premium_ratio": 0.1, "option.net_above_cheapest": 20.0,
        "profile.display_name": "Harbourside Hotel",
    }


@pytest.mark.parametrize(
    ("net", "more", "fires"),
    [("110.00", "10.00", False), ("110.01", "10.01", True), ("100.00", None, False), ("100.00", "0.00", False)],
    ids=["exactly the limit", "a cent above", "no preference", "costs nothing"],
)
def test_the_premium_is_a_share_of_the_cheapest_confirmed_option(
    net: str, more: str | None, fires: bool, engine: RulePolicyEngine, a_tenth: BuyerProfile,
    preferred: Callable[[str, str | None], OfferOption], make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(preferred(net, more), a_tenth, make_context())

    assert decision.rule_ids == (("P-09",) if fires else ("F-10",))


def test_a_profile_that_sets_no_limit_changes_no_decision_and_misses_no_fact(
    engine: RulePolicyEngine, hotel: BuyerProfile, preferred: Callable[[str, str | None], OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(preferred("120.00", "60.00"), hotel, make_context())

    assert hotel.max_preference_premium_ratio is None and decision.rule_ids == ("F-10",)


def test_the_ward_and_the_bakery_which_prefer_reliability_accept_a_tenth(engine: RulePolicyEngine) -> None:
    limits = {
        profile_id: engine.get_profile(profile_id).max_preference_premium_ratio for profile_id in engine.profile_ids()
    }

    assert limits == {
        "allergy-ward": Decimal("0.1"), "bakery-cafe": Decimal("0.1"), "hotel-kitchen": None, "school-kitchen": None,
    }


def test_a_profile_cannot_accept_more_than_the_share_above_which_the_offer_ranks_the_cheapest_first(
    hotel: BuyerProfile,
) -> None:
    """One threshold, two effects: up to 25% the preferred option comes first; above it the cheapest does."""
    assert MAX_PREFERENCE_PREMIUM_RATIO == MAX_PREFERENCE_PREMIUM

    at_the_ceiling = {**hotel.model_dump(), "max_preference_premium_ratio": MAX_PREFERENCE_PREMIUM}
    assert BuyerProfile.model_validate(at_the_ceiling).max_preference_premium_ratio == MAX_PREFERENCE_PREMIUM
    with pytest.raises(ValidationError, match="max_preference_premium_ratio"):
        BuyerProfile.model_validate({**at_the_ceiling, "max_preference_premium_ratio": Decimal("0.26")})


def test_a_premium_over_a_cheapest_option_of_nothing_is_a_missing_fact(
    engine: RulePolicyEngine, a_tenth: BuyerProfile, preferred: Callable[[str, str | None], OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    option = preferred("20.00", "20.00")
    scope = OrderScope(option, a_tenth, make_context(), {})

    decision = engine.evaluate(option, a_tenth, make_context())

    assert read_fact("option.net_above_cheapest", scope) == Decimal("20.00")
    assert decision.rule_ids == ("F-03",) and decision.fired[0].facts["needed_by"] == ["P-09"]


def test_authority_states_the_share_or_that_none_is_set(
    engine: RulePolicyEngine, hotel: BuyerProfile, a_tenth: BuyerProfile,
) -> None:
    def sentence(profile: BuyerProfile) -> str:
        return next(rule.sentence for rule in engine.describe_authority(profile).rules if rule.rule_id == "P-09")

    assert sentence(a_tenth) == (
        "An option ranked by a preference (most reliable, lowest carbon, earliest) that costs more than 10% above "
        "the cheapest confirmed option goes to the purchasing manager."
    )
    assert sentence(hotel) == (
        "This profile sets no limit on what a preference may cost. The offer still ranks the cheapest confirmed "
        "option first when a preference costs more than 25% above it (our threshold)."
    )
