"""The hole L2a-R found, on the recording: with ordering alone switched on, a plain cooking cream was ordered by
the agent alone in place of a flavoured one. Rule F-12 closed it; since decision B65 the plain cream is no
candidate at all."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from tta.contracts.common import Identity, Unit, Verdict
from tta.contracts.policy import BuyerProfile
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


def test_a_plain_cream_no_longer_stands_in_for_a_flavoured_one_even_with_ordering_alone_on(
    replay_deps: Any, policy: RulePolicyEngine, make_request: Any, agent_hotel: Identity
) -> None:
    """Before decision B65 the plain cooking cream 463797 stood in for the three-cheese one as a last resort and
    rule F-12 sent it to a person (the hole L2a-R found: without the rule the agent ordered it alone). Since B65
    a product that is another kind by its name is no candidate at all: nothing stands in, so nothing can be
    ordered alone, and the offer says so. Rule F-12 itself is pinned in `tests/policy/test_last_resort.py`."""
    alone = _OrdersAlone(policy)
    service = OfferService(replace(replay_deps, policy=alone))

    offer = service.build_offer(make_request(10, Unit.UNIT, product_ids=(THREE_CHEESES,)), agent_hotel)

    assert not any(line.substitute is not None for option in offer.options for line in option.lines)
    assert PLAIN_COOKING_CREAM not in {line.product_id for option in offer.options for line in option.lines}
    assert not any(option.decision.verdict is Verdict.AUTO for option in offer.options)
    assert (
        "Request line 1: no substitute for Valio Keittiön flavoured cooking cream 2,5 dl three cheeses UHT lactose "
        "free (463830) passes the allergen rules, fits the request and can be ordered; 0 candidates ranked."
    ) in offer.notes
