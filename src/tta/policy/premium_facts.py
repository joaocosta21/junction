"""The facts of rule P-09: what an option ranked by a preference costs above the cheapest confirmed option.

The offer puts the amount on the preferred option (`OfferOption.net_above_cheapest`) whenever a cheaper confirmed
option stands next to it; None there means no preference was asked or it costs nothing, which is 0, never a
missing fact. The share is taken of the cheapest option's net total, as the offer takes it when it ranks
(`tta.offers.preference`).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from tta.contracts.common import round_money
from tta.contracts.policy import BuyerProfile
from tta.policy.reading import Missing, Reading

if TYPE_CHECKING:  # facts.py imports this module; OrderScope is only named in annotations
    from tta.policy.facts import OrderScope, ScopeTable

NOTHING = Decimal(0)
NO_LIMIT = "the profile sets no limit on what a preference may cost"
NO_CHEAPEST_TOTAL = "the cheapest confirmed option has no net total to take a share of"


def _net_above_cheapest(scope: OrderScope) -> Reading:
    more = scope.option.net_above_cheapest
    return NOTHING if more is None else round_money(more)


def _premium_ratio(scope: OrderScope) -> Reading:
    more = scope.option.net_above_cheapest
    if more is None or more <= 0:
        return NOTHING
    cheapest = scope.option.totals.net - more
    return more / cheapest if cheapest > 0 else Missing(NO_CHEAPEST_TOTAL)


def _limit(profile: BuyerProfile, _: ScopeTable) -> Reading:
    ratio = profile.max_preference_premium_ratio
    return Missing(NO_LIMIT) if ratio is None else ratio


PREMIUM_ORDER_FACTS: Mapping[str, Callable[[OrderScope], Reading]] = {
    "option.net_above_cheapest": _net_above_cheapest,
    "option.preference_premium_ratio": _premium_ratio,
}
PREMIUM_PROFILE_FACTS: Mapping[str, Callable[[BuyerProfile, ScopeTable], Reading]] = {
    "profile.limits_preference_premium": lambda profile, _: profile.max_preference_premium_ratio is not None,
    "profile.max_preference_premium_ratio": _limit,
}
