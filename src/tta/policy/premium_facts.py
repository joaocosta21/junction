"""The facts of rule P-09: what an option ranked by a preference costs above the cheapest confirmed option.

The offer puts the amount on the preferred option (`OfferOption.net_above_cheapest`) whenever a cheaper confirmed
option stands next to it; None there means no preference was asked or it costs nothing, which is 0, never a
missing fact. The share is taken of the cheapest option's net total, as the offer takes it when it ranks
(`tta.offers.preference`).

And the facts of rule P-05's second condition (decision B60): what a substitute costs above the product it
replaces. The offer line carries what the product asked for would have cost for the same content
(`SubstituteInfo.original_net`). The share a substitute may cost more without a person is the one the profile
sets for a preference, and `MAX_PREFERENCE_PREMIUM_RATIO` (25%) where it sets none: the value is ours, labelled
so, and no Valio Aimo limit. A cost that is not known is never read as "not dearer": the rule fires and says so.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from tta.contracts.common import round_money
from tta.contracts.offer import OfferLine
from tta.contracts.policy import MAX_PREFERENCE_PREMIUM_RATIO, BuyerProfile
from tta.policy.reading import Missing, Reading
from tta.policy.text import format_money, format_ratio

if TYPE_CHECKING:  # facts.py imports this module; OrderScope is only named in annotations
    from tta.policy.facts import OrderScope, ScopeTable

NOTHING = Decimal(0)
NO_LIMIT = "the profile sets no limit on what a preference may cost"
NO_CHEAPEST_TOTAL = "the cheapest confirmed option has no net total to take a share of"
NO_SUBSTITUTE = "the line replaces no product"
NO_ORIGINAL_NET = "the offer does not say what the product asked for would have cost"
# The two clauses of rule P-05 about the price, each read after "<substitute> replaces <product>, ".
COSTS_MORE = "and the substitute costs €{more} more than the product you asked for ({share} more): a person decides"
COST_NOT_KNOWN = (
    "and what the product you asked for would have cost is not known, so the two prices cannot be compared: a "
    "person decides"
)


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


def _original_net(line: OfferLine) -> Decimal | None:
    """What the product asked for would have cost for the content of the line; None when it replaces nothing,
    the offer does not say, or says nothing above zero (no share can be taken of it)."""
    net = line.substitute.original_net if line.substitute is not None else None
    return net if net is not None and net > 0 else None


def _original_net_known(_: OrderScope, line: OfferLine) -> Reading:
    return Missing(NO_SUBSTITUTE) if line.substitute is None else _original_net(line) is not None


def _net_above_original(_: OrderScope, line: OfferLine) -> Reading:
    """What the substitute costs more, before tax; 0 when it costs the same or less."""
    original = _original_net(line)
    if original is None:
        return Missing(NO_SUBSTITUTE if line.substitute is None else NO_ORIGINAL_NET)
    return max(round_money(line.net - original), NOTHING)


def _substitute_premium_ratio(scope: OrderScope, line: OfferLine) -> Reading:
    """`_net_above_original` as a share of what the product asked for would have cost."""
    more, original = _net_above_original(scope, line), _original_net(line)
    return more if isinstance(more, Missing) or original is None else more / original


def substitute_limit(profile: BuyerProfile) -> Decimal:
    """The share a substitute may cost more without a person: the profile's own for a preference, else 25%."""
    ratio = profile.max_preference_premium_ratio
    return MAX_PREFERENCE_PREMIUM_RATIO if ratio is None else ratio


def price_said(scope: OrderScope, line: OfferLine) -> str | None:
    """Rule P-05's clause about the price of a substitute; None when its price sends it to nobody."""
    if line.substitute is None:
        return None
    more, share = _net_above_original(scope, line), _substitute_premium_ratio(scope, line)
    if isinstance(more, Missing) or isinstance(share, Missing):
        return COST_NOT_KNOWN
    if not isinstance(more, Decimal) or not isinstance(share, Decimal) or share <= substitute_limit(scope.profile):
        return None
    return COSTS_MORE.format(more=format_money(more), share=format_ratio(share))


PREMIUM_LINE_FACTS: Mapping[str, Callable[[OrderScope, OfferLine], Reading]] = {
    "line.substitute_original_net_known": _original_net_known,
    "line.substitute_net_above_original": _net_above_original,
    "line.substitute_premium_ratio": _substitute_premium_ratio,
}
PREMIUM_ORDER_FACTS: Mapping[str, Callable[[OrderScope], Reading]] = {
    "option.net_above_cheapest": _net_above_cheapest,
    "option.preference_premium_ratio": _premium_ratio,
}
PREMIUM_PROFILE_FACTS: Mapping[str, Callable[[BuyerProfile, ScopeTable], Reading]] = {
    "profile.limits_preference_premium": lambda profile, _: profile.max_preference_premium_ratio is not None,
    "profile.max_preference_premium_ratio": _limit,
    "profile.max_substitute_premium_ratio": lambda profile, _: substitute_limit(profile),
}
