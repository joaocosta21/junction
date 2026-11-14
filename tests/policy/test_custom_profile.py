"""A buyer profile that is not a file: set up on the pages ("My kitchen", task FEAT-1).

Scores on the 20% "autonomy and controls": the buyer sets what its agent may decide alone, checked exactly as a
profile file is, so a value out of range or a setting that names a fixed rule is refused, and the profile is
in force only inside the call that carries it: it never shadows a profile file and is never seen outside.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import Verdict
from tta.contracts.errors import NotAuthorised
from tta.contracts.offer import OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy import PolicyLoadError, RulePolicyEngine, profile_in_force

CUSTOM_ID = "my-kitchen"


@pytest.fixture
def custom_data(profile_data: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    """The hotel kitchen's settings under another id, as a page would send them."""
    return {**profile_data("hotel-kitchen"), "profile_id": CUSTOM_ID, "display_name": "My kitchen"}


def test_a_custom_profile_is_checked_like_a_file_and_comes_back_as_the_contract(
    engine: RulePolicyEngine, custom_data: dict[str, Any]
) -> None:
    profile = engine.check_custom_profile({**custom_data, "max_order_net_eur": 3000})

    assert isinstance(profile, BuyerProfile)
    assert (profile.profile_id, profile.max_order_net_eur) == (CUSTOM_ID, Decimal(3000))


@pytest.mark.parametrize(
    ("change", "named"),
    [
        ({"F-01": "off"}, "fixed rule F-01"),
        ({"display_name": "f-07"}, "fixed rule F-07"),
        ({"rules": []}, "unknown setting rules"),
        ({"max_order_net_eur": -1}, "max_order_net_eur"),
        ({"min_fill_ratio": "1.5"}, "min_fill_ratio"),
        ({"excluded_allergens": ["milk"], "allergen_strictness": "STRICT"}, "excluded_allergens"),
        ({"excluded_allergens": ["AM"], "allergen_strictness": None}, "allergen_strictness"),
        ({"profile_id": "hotel-kitchen"}, "profile_id"),
    ],
)
def test_a_custom_profile_that_a_file_could_not_be_is_refused_with_what_is_wrong(
    engine: RulePolicyEngine, custom_data: dict[str, Any], change: dict[str, Any], named: str
) -> None:
    with pytest.raises(PolicyLoadError) as refused:
        engine.check_custom_profile({**custom_data, **change})

    assert named in str(refused.value)


def test_a_custom_profile_is_found_only_while_it_is_in_force(
    engine: RulePolicyEngine, custom_data: dict[str, Any]
) -> None:
    profile = engine.check_custom_profile(custom_data)

    with pytest.raises(NotAuthorised):
        engine.get_profile(CUSTOM_ID)
    with profile_in_force(profile):
        assert engine.get_profile(CUSTOM_ID) is profile
        assert RulePolicyEngine.from_files().get_profile(CUSTOM_ID) is profile  # every engine of the process
    with pytest.raises(NotAuthorised):
        engine.get_profile(CUSTOM_ID)
    assert CUSTOM_ID not in engine.profile_ids()


def test_a_profile_in_force_never_shadows_a_profile_file(engine: RulePolicyEngine, hotel: BuyerProfile) -> None:
    impostor = hotel.model_copy(update={"max_order_net_eur": Decimal(100_000)})

    with profile_in_force(impostor):
        assert engine.get_profile("hotel-kitchen") == hotel


def test_the_engine_judges_a_custom_profile_with_its_own_limits_and_its_own_hash(
    engine: RulePolicyEngine, hotel: BuyerProfile, custom_data: dict[str, Any],
    make_option: Callable[..., OfferOption], now: datetime,
) -> None:
    option = make_option(net="2580.64")
    context = PolicyContext(now=now, day_committed_net_eur=Decimal(0))
    above = engine.check_custom_profile({**custom_data, "max_order_net_eur": 750})
    within = engine.check_custom_profile({**custom_data, "max_order_net_eur": 3000})

    to_a_human = engine.evaluate(option, above, context)
    alone = engine.evaluate(option, within, context)

    assert (to_a_human.verdict, to_a_human.rule_ids, to_a_human.profile_id) == (Verdict.APPROVAL, ("P-01",), CUSTOM_ID)
    assert alone.verdict is Verdict.AUTO
    assert len({engine.policy_hash(hotel), alone.policy_hash, to_a_human.policy_hash}) == 3
