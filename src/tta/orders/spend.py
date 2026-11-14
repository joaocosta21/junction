"""The day's spend of one buyer profile (SPEC section 8): what rule P-02 compares with the limit per day."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from tta.contracts.common import OrderStatus
from tta.contracts.order import Order
from tta.contracts.ports import Clock, Store
from tta.orders.records import is_past_order_by

COMMITTED_STATUSES = (OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL)


def _is_committed_today(order: Order, now: datetime) -> bool:
    """Entered in the book on the clock's current date, and not a pending order whose time has already passed."""
    same_day = order.created_at.astimezone(now.tzinfo).date() == now.date()
    return same_day and not is_past_order_by(order, now)


def day_committed_net_eur(
    store: Store, clock: Clock, profile_id: str, *, excluding_order_id: str | None = None
) -> Decimal:
    """Net total of the profile's ORDERED and PENDING_APPROVAL orders on the clock's current date.

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
