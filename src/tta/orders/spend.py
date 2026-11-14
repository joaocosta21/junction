"""The day's spend of one buyer profile (SPEC section 8): what rule P-02 compares with the limit per day.

A waiting order counts (AIMO/PLAN.md, decision 9): otherwise the limit per day could be passed by orders that all
wait for a human. So that a person can tell a day of orders from a day of requests nobody has approved yet (review
A4, finding H2), the spend is kept in its two parts, and an approval that P-02 asks for says both.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from tta.audit.phrases import money
from tta.contracts.common import OrderStatus
from tta.contracts.order import Order
from tta.contracts.ports import Clock, Store
from tta.orders.records import is_past_order_by

COMMITTED_STATUSES = (OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL)
DAY_SENTENCE = (
    "Before this order, today's spend of this buyer is {committed} before tax: {ordered} ordered and {waiting} "
    "waiting for approval. A waiting order counts until a person rejects it or its time to decide passes."
)


@dataclass(frozen=True)
class DaySpend:
    """Net EUR of one profile's orders on the clock's current date, in its two parts."""

    ordered: Decimal  # ORDERED today: by the agent alone or with a person's approval
    waiting: Decimal  # PENDING_APPROVAL, created today, still in time to be decided

    @property
    def committed(self) -> Decimal:
        """What rule P-02 adds this order to."""
        return self.ordered + self.waiting

    @property
    def sentence(self) -> str:
        return DAY_SENTENCE.format(
            committed=money(self.committed), ordered=money(self.ordered), waiting=money(self.waiting)
        )


def _committed_at(order: Order) -> datetime:
    """When the order's amount was committed: an ORDERED order when it became ORDERED, a waiting one when it
    was created. An ORDERED order is never changed again in this book, so its `updated_at` is that moment."""
    return order.updated_at if order.status is OrderStatus.ORDERED else order.created_at


def _is_committed_today(order: Order, now: datetime) -> bool:
    """Committed on the clock's current date, in the clock's offset, and not a waiting order whose "order by"
    time has already passed. (A waiting order with no "order by" time has 24 hours from its creation, so it
    cannot run out on the day it counts.)"""
    same_day = _committed_at(order).astimezone(now.tzinfo).date() == now.date()
    return same_day and not is_past_order_by(order, now)


def day_spend(store: Store, clock: Clock, profile_id: str, *, excluding_order_id: str | None = None) -> DaySpend:
    """The profile's ORDERED and PENDING_APPROVAL orders on the clock's current date, each part summed.

    An ORDERED order counts on the date it became ORDERED: created on one day and approved on the next, it is
    spend of the day it was approved. A waiting order counts on the date it was created.
    `excluding_order_id` leaves out the order being decided, which would otherwise be counted twice.
    """
    now = clock.now()
    today = [
        order for order in store.list_orders(profile_id=profile_id, statuses=COMMITTED_STATUSES)
        if order.order_id != excluding_order_id and _is_committed_today(order, now)
    ]
    ordered = sum((order.option.totals.net for order in today if order.status is OrderStatus.ORDERED), Decimal(0))
    waiting = sum((order.option.totals.net for order in today if order.status is not OrderStatus.ORDERED), Decimal(0))
    return DaySpend(ordered=ordered, waiting=waiting)


def day_committed_net_eur(
    store: Store, clock: Clock, profile_id: str, *, excluding_order_id: str | None = None
) -> Decimal:
    """Net total of the profile's ORDERED and PENDING_APPROVAL orders on the clock's current date: `day_spend`
    as one figure. A pending order counts, or the limit per day could be passed by orders that all wait for a
    human."""
    return day_spend(store, clock, profile_id, excluding_order_id=excluding_order_id).committed
