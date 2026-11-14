"""Rule F-12 on the recording: a last-resort substitute that fires no other rule goes to a person even when the
buyer lets the agent order alone and every statement is confirmed (the hole L2a-R found)."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

from tta.contracts.common import Identity, OptionKind, Unit, Verdict
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.offers import OfferService
from tta.policy import RulePolicyEngine

# A three-cheese cooking cream that cannot be supplied, and the plain cooking cream that stands in for it: same
# category, no allergen added, no claim lost, confirmed stock. Flavoured against plain is all that differs in kind.
THREE_CHEESES, PLAIN_COOKING_CREAM = "463830", "463797"


class _OrdersAlone:
    """The shipped policy, with ordering alone switched on for every profile. Nothing else differs."""

    def __init__(self, inner: RulePolicyEngine) -> None:
        self._inner = inner

    def get_profile(self, profile_id: str) -> BuyerProfile:
        return self._inner.get_profile(profile_id).model_copy(update={"auto_order_enabled": True})

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def test_a_flavour_mismatch_last_resort_is_not_ordered_alone_with_ordering_alone_on(
    replay_deps: Any, policy: RulePolicyEngine, make_request: Any, agent_hotel: Identity
) -> None:
    alone = _OrdersAlone(policy)
    service = OfferService(replace(replay_deps, policy=alone))

    offer = service.build_offer(make_request(10, Unit.UNIT, product_ids=(THREE_CHEESES,)), agent_hotel)

    option = next(each for each in offer.options if each.kind is OptionKind.SUBSTITUTE)
    line = option.lines[0]
    assert line.product_id == PLAIN_COOKING_CREAM and line.substitute.last_resort
    assert line.substitute.claims_lost == () and line.substitute.allergen_check.passes
    assert option.decision.verdict is Verdict.APPROVAL and option.decision.rule_ids == ("F-12",)
    assert option.decision.fired[0].sentence.startswith(
        "Arla Pro Cooking cream 10% 1 L UHT lactose free (463797) would replace Valio Keittiön flavoured cooking "
        "cream 2,5 dl three cheeses UHT lactose free (463830) as a last resort: not flavoured; the product asked "
        "for is flavoured"
    )
    assert option.decision.fired[0].sentence.endswith("A person decides whether it will do.")
    # The same option without the mark is what the agent would have ordered alone before the rule existed.
    unmarked = line.model_copy(update={"substitute": line.substitute.model_copy(update={"last_resort": False})})
    before = policy.evaluate(
        option.model_copy(update={"lines": (unmarked,), "decision": None}), alone.get_profile("hotel-kitchen"),
        PolicyContext(now=offer.time_now, day_committed_net_eur=Decimal(0)),
    )
    assert before.verdict is Verdict.AUTO and before.fired == ()
