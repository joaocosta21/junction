"""The facts of rule P-02: the day's spend of the buyer, this order included, and its parts.

A waiting order counts toward the limit per day (AIMO/PLAN.md, decision 9). So that the person who signs can tell
a day of orders from a day of requests nobody has approved yet (review A4, finding H2), the sentence says what is
ordered, what is waiting for a person and what this order adds, when the caller says how much is waiting
(`PolicyContext.day_waiting_net_eur`). Without it the sentence says the total only; the verdict never depends on it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from tta.contracts.common import round_money
from tta.policy.reading import Missing, Reading
from tta.policy.text import format_money

if TYPE_CHECKING:  # facts.py imports this module; OrderScope is only named in annotations
    from tta.policy.facts import OrderScope

DAY_NET_SAID = "€{total} before tax"
DAY_NET_PARTS = " (€{ordered} ordered, €{waiting} waiting for a person, and this order's €{this})"


def _day_committed(scope: OrderScope) -> Reading:
    committed = scope.context.day_committed_net_eur
    if committed is None:
        return Missing("today's committed spend did not come with the order context")
    return round_money(committed)


def _day_net(scope: OrderScope) -> Reading:
    committed = scope.context.day_committed_net_eur
    if committed is None:
        return Missing("today's committed spend did not come with the order context")
    return round_money(committed + scope.option.totals.net)


def _day_waiting(scope: OrderScope) -> Reading:
    """The part of the day's committed spend that waits for a person; missing when the caller did not say, or
    said a figure that cannot be a part of the day's spend."""
    committed, waiting = scope.context.day_committed_net_eur, scope.context.day_waiting_net_eur
    if committed is None or waiting is None:
        return Missing("how much of today's spend is waiting for a person did not come with the order context")
    if not Decimal(0) <= waiting <= committed:
        return Missing("the waiting part of today's spend is not a part of it")
    return round_money(waiting)


def _day_net_said(scope: OrderScope) -> Reading:
    """Rule P-02's figure as a person reads it: the day's spend with this order, and its parts when the waiting
    part is known (review A4, finding H2): ordered, waiting for a person, and this order."""
    total, waiting = _day_net(scope), _day_waiting(scope)
    if isinstance(total, Missing):
        return total
    said = DAY_NET_SAID.format(total=format_money(total))
    if isinstance(waiting, Missing):
        return said
    ordered = round_money(scope.context.day_committed_net_eur or Decimal(0)) - waiting
    return said + DAY_NET_PARTS.format(
        ordered=format_money(ordered), waiting=format_money(waiting), this=format_money(scope.option.totals.net)
    )


DAY_FACTS: Mapping[str, Callable[[OrderScope], Reading]] = {
    "context.day_committed_net_eur": _day_committed,
    "context.day_waiting_net_eur": _day_waiting,
    "order.day_net_eur": _day_net,
    "order.day_net_said": _day_net_said,
}
