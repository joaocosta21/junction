"""The facts of rule P-01: the spend limit one order is judged against, and where it came from (lane FP-B).

A buyer who writes "under €1,000" names the most to spend on that one request (`PurchaseRequest.max_net_eur`,
euros before tax, as every total and every limit here). The limit rule P-01 reads is the lower of the buyer's own
limit per order and that amount. So the amount can only add a check: it never raises the buyer's limit, it is not
the limit per day (rule P-02 reads the profile alone), and it removes no option from an offer. Where the two are
equal the buyer's own limit is the one named.

The engine sees the option and not the request, so the amount is read from the request as the buyer sent it
(`tta.policy.formula_facts.request_as_sent`): the gateway holds it while it builds an offer, and the order book
while an order is placed. With no request at hand nothing was named, and the buyer's own limit applies as before.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from tta.policy.formula_facts import sent_request
from tta.policy.reading import Missing, Reading
from tta.policy.text import format_limit, plain_name

if TYPE_CHECKING:  # facts.py imports this module; OrderScope is only named in annotations
    from tta.policy.facts import OrderScope

NO_AMOUNT_NAMED = "the request names no amount as the most to spend"
FROM_THE_PROFILE = "the buyer's limit per order"
FROM_THE_REQUEST = "the amount the request names"
# Rule P-01's words for the limit an option is above, read after "the total of €1,083.39 before tax is above ".
PROFILE_LIMIT = "the €{limit} limit per order of {buyer}"
NAMED_AMOUNT = "the €{amount} you named for this request"
# The words of the sentence of an order the agent may place alone, read after "… before tax is within ".
WITHIN_PROFILE_LIMIT = "the €{limit} limit per order"
WITHIN_BOTH = WITHIN_PROFILE_LIMIT + " and " + NAMED_AMOUNT


def _named(_: OrderScope) -> Decimal | None:
    request = sent_request()
    return request.max_net_eur if request is not None else None


def _named_amount(scope: OrderScope) -> Reading:
    amount = _named(scope)
    return Missing(NO_AMOUNT_NAMED) if amount is None else amount


def _decides(scope: OrderScope) -> bool:
    """Whether the named amount is the limit in force: only when it is below the buyer's own."""
    amount = _named(scope)
    return amount is not None and amount < scope.profile.max_order_net_eur


def _limit(scope: OrderScope) -> Reading:
    amount = _named(scope)
    return amount if amount is not None and _decides(scope) else scope.profile.max_order_net_eur


def _source(scope: OrderScope) -> Reading:
    return FROM_THE_REQUEST if _decides(scope) else FROM_THE_PROFILE


def _limit_said(scope: OrderScope) -> Reading:
    amount = _named(scope)
    if amount is not None and _decides(scope):
        return NAMED_AMOUNT.format(amount=format_limit(amount))
    return PROFILE_LIMIT.format(
        limit=format_limit(scope.profile.max_order_net_eur), buyer=plain_name(scope.profile.display_name)
    )


def _within_said(scope: OrderScope) -> Reading:
    amount, limit = _named(scope), format_limit(scope.profile.max_order_net_eur)
    if amount is None:
        return WITHIN_PROFILE_LIMIT.format(limit=limit)
    return WITHIN_BOTH.format(limit=limit, amount=format_limit(amount))


SPEND_LIMIT_FACTS: Mapping[str, Callable[[OrderScope], Reading]] = {
    "request.max_net_eur": _named_amount,
    "order.spend_limit_net_eur": _limit,
    "order.spend_limit_source": _source,
    "order.spend_limit_said": _limit_said,
    "order.within_spend_limit_said": _within_said,
}
