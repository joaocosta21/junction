"""Rule P-05, second condition (decision B60): a substitute that costs more than the product asked for by more
than the buyer accepts goes to a person, whatever the substitution scope.

Found on the running system: with ordering alone switched on, the hotel's agent could order a substitute judged
replaceable at any price under the spend limits (469330 replaced by 469363, 1.71 against 2.48 euros a litre, 45%
more), and no rule fired. The offer line now carries what the product asked for would have cost for the same
content (`SubstituteInfo.original_net`); the share accepted is the one a preference may add (P-09), and 25% where
the profile sets none. A price that is not known is never read as "not dearer".
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import ApproverRole, Verdict
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy import RulePolicyEngine

Decide = Callable[..., Any]


@pytest.fixture
def alone(hotel: BuyerProfile) -> BuyerProfile:
    """The hotel with ordering alone switched on: the same category is accepted without a person, and the
    profile sets no premium of its own."""
    assert hotel.max_preference_premium_ratio is None
    return hotel.model_copy(update={"auto_order_enabled": True})


@pytest.fixture
def decide(
    engine: RulePolicyEngine, make_line: Callable[..., OfferLine], make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext], make_substitute: Callable[..., Any],
) -> Decide:
    """The decision on 100 litres of a same-category substitute judged replaceable, at `unit_net_price`, where
    the product asked for would have cost `original_net`."""

    def run(profile: BuyerProfile, unit_net_price: str, original_net: str | None, **substitute: Any) -> Any:
        info = make_substitute(listed=False, original_net=original_net, **substitute)
        line = make_line("469363", "Arla Semi skimmed milkdrink 1 L", unit_net_price=unit_net_price,
                         substitute=info)
        return engine.evaluate(make_option([line], net=str(line.net)), profile, make_context())

    return run


def test_a_substitute_45_percent_dearer_is_not_ordered_alone(alone: BuyerProfile, decide: Decide) -> None:
    decision = decide(alone, "2.48", "170.80")

    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-05",)
    assert decision.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert decision.fired[0].sentence == (
        "Arla Semi skimmed milkdrink 1 L (469363) replaces Oddlygood Barista oat drink (473609), and the "
        "substitute costs €77.20 more than the product you asked for (45.1% more): a person decides."
    )
    facts = decision.fired[0].facts
    assert facts["line.substitute_original_net_known"] is True
    assert facts["line.substitute_net_above_original"] == 77.2
    assert facts["line.substitute_premium_ratio"] == pytest.approx(0.452, abs=0.0005)
    assert facts["profile.max_substitute_premium_ratio"] == 0.25
    assert facts["line.substitute_scope"] == "SAME_CATEGORY"  # the scope is one the hotel accepts


@pytest.mark.parametrize(
    ("original_net", "fires"),
    [("198.40", False), ("198.39", True), ("248.00", False), ("300.00", False)],
    ids=["exactly 25% more", "a cent above", "the same price", "cheaper"],
)
def test_where_the_profile_sets_no_premium_a_quarter_more_is_accepted(
    original_net: str, fires: bool, alone: BuyerProfile, decide: Decide
) -> None:
    decision = decide(alone, "2.48", original_net)

    assert (decision.rule_ids == ("P-05",)) is fires
    assert decision.verdict is (Verdict.APPROVAL if fires else Verdict.AUTO)


def test_the_share_is_the_one_the_profile_sets_for_a_preference(alone: BuyerProfile, decide: Decide) -> None:
    a_tenth = alone.model_copy(update={"max_preference_premium_ratio": Decimal("0.1")})

    assert decide(a_tenth, "2.20", "200.00").verdict is Verdict.AUTO  # exactly 10% more
    decision = decide(a_tenth, "2.21", "200.00")
    assert decision.rule_ids == ("P-05",)
    assert decision.fired[0].sentence.endswith(
        "and the substitute costs €21.00 more than the product you asked for (10.5% more): a person decides."
    )
    assert decision.fired[0].facts["profile.max_substitute_premium_ratio"] == 0.1


def test_a_price_that_is_not_known_is_said_and_a_person_decides(alone: BuyerProfile, decide: Decide) -> None:
    decision = decide(alone, "2.48", None)

    # Not rule F-03 and its "missing fact": the rule fires itself and says it in plain words.
    assert decision.verdict is Verdict.APPROVAL and decision.rule_ids == ("P-05",)
    assert decision.fired[0].sentence == (
        "Arla Semi skimmed milkdrink 1 L (469363) replaces Oddlygood Barista oat drink (473609), and what the "
        "product you asked for would have cost is not known, so the two prices cannot be compared: a person "
        "decides."
    )
    assert decision.fired[0].facts["line.substitute_original_net_known"] is False
    assert decision.fired[0].facts["line.substitute_premium_ratio"] is None


def test_a_scope_the_buyer_does_not_accept_reads_as_before_and_the_figures_are_kept(
    ward: BuyerProfile, decide: Decide
) -> None:
    decision = decide(ward, "2.48", "170.80")

    fired = next(rule for rule in decision.fired if rule.rule_id == "P-05")
    assert fired.sentence == (
        "Arla Semi skimmed milkdrink 1 L (469363) replaces Oddlygood Barista oat drink (473609), a substitute "
        "that City Hospital, Ward 4 does not accept without a human."
    )
    assert fired.facts["line.substitute_net_above_original"] == 77.2  # for the audit trail


def test_a_line_that_replaces_nothing_is_not_judged_by_it(
    engine: RulePolicyEngine, alone: BuyerProfile, make_option: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    decision = engine.evaluate(make_option(), alone, make_context())

    assert decision.verdict is Verdict.AUTO and decision.fired == ()


def test_the_settings_say_what_a_substitute_may_cost(engine: RulePolicyEngine, alone: BuyerProfile,
                                                     ward: BuyerProfile) -> None:
    def said(profile: BuyerProfile) -> str:
        return next(rule.sentence for rule in engine.describe_authority(profile).rules if rule.rule_id == "P-05")

    assert said(alone).endswith(
        "A substitute that costs more than 25% above what the product it replaces would have cost, or whose "
        "price cannot be compared with it, goes to the purchasing manager."
    )
    assert "more than 10% above" in said(alone.model_copy(update={"max_preference_premium_ratio": Decimal("0.1")}))
    assert said(ward) == "Every substitute goes to the purchasing manager."  # true as it stood: nothing to add
