"""The day's spend of one buyer profile (SPEC section 8): what rule P-02 compares with the limit per day."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from tta.contracts.common import OrderStatus
from tta.contracts.order import Order
from tta.contracts.ports import Clock, Store
from tta.orders.records import is_past_order_by

COMMITTED_STATUSES = (OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL)


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


def day_committed_net_eur(
    store: Store, clock: Clock, profile_id: str, *, excluding_order_id: str | None = None
) -> Decimal:
    """Net total of the profile's ORDERED and PENDING_APPROVAL orders on the clock's current date.

    An ORDERED order counts on the date it became ORDERED: created on one day and approved on the next, it is
    spend of the day it was approved. A waiting order counts on the date it was created.
    A pending order counts, or the limit per day could be passed by orders that all wait for a human.
    `excluding_order_id` leaves out the order being decided, which would otherwise be counted twice.
    """
    now = clock.now()
    orders = store.list_orders(profile_id=profile_id, statuses=COMMITTED_STATUSES)
    return sum(
        (
            order.option.totals.net
            for order in orders
            if order.order_id != excluding_order_id and _is_committed_today(order, now)
        ),
        Decimal(0),
    )
