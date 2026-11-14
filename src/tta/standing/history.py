"""The history rule P-08 reads: a standing order's past renewals, read from the store (task STAND-1).

The offer builder reads it when a request names a standing order, and the order book reads it again at order time
and when an approver decides, so the verdict rests on the same history at every step.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum

from tta.contracts.common import OrderStatus
from tta.contracts.errors import InvalidRequest
from tta.contracts.ports import Store
from tta.contracts.standing import Renewal, StandingHistory, StandingOrder

UNKNOWN_STANDING_ORDER = (
    "No standing order {standing_order_id} is set up for this buyer, so the request cannot renew it. "
    "Send the request without standing_order_id, or set the standing order up first (POST /v1/standing-orders)."
)
# Only a renewal that was ordered is part of what the kitchen usually orders. One that still waits for a person,
# that a person rejected or that expired waiting is not: otherwise the agent's own unapproved requests would move
# the median its next renewal is judged against (review A2a, finding S-1).
COUNTED = OrderStatus.ORDERED
# A renewal that names an order the book does not hold is left out of the history, and this says how many were.
NOT_COUNTED_ONE = "1 past renewal has no order record and was not counted."
NOT_COUNTED_MANY = "{count} past renewals have no order record and were not counted."

logger = logging.getLogger(__name__)

HistoryLookup = Callable[[str, str], StandingHistory]


def standing_history(
    store: Store, profile_id: str, standing_order_id: str, *, excluding_offer_id: str | None = None
) -> StandingHistory:
    """The standing order's past renewals, oldest first. `excluding_offer_id` leaves out the renewal being judged,
    which is already recorded when an approver decides it. Raises `InvalidRequest` for a standing order this buyer
    does not have: another buyer's reads as one nobody set up."""
    standing = _own(store, profile_id, standing_order_id)
    renewals = [
        renewal for renewal in _past(store, standing_order_id, excluding_offer_id)
        if _standing_of(store, renewal) is _Standing.COUNTED
    ]
    return StandingHistory(
        standing_order_id=standing.standing_order_id, name=standing.name, cadence_days=standing.cadence_days,
        renewals=tuple(sorted(renewals, key=lambda renewal: renewal.renewed_at)),  # stable: saved order on a tie
    )


def renewals_without_order(
    store: Store, profile_id: str, standing_order_id: str, *, excluding_offer_id: str | None = None
) -> int:
    """How many past renewals name an order the book does not hold. `standing_history` leaves each of them out;
    `not_counted_note` says so. Raises `InvalidRequest` as `standing_history` does."""
    _own(store, profile_id, standing_order_id)
    missing = [
        renewal for renewal in _past(store, standing_order_id, excluding_offer_id)
        if _standing_of(store, renewal) is _Standing.NO_ORDER_RECORD
    ]
    if missing:
        logger.warning(
            "Standing order %s: %d past renewal(s) name an order that is not in the order book; not counted.",
            standing_order_id, len(missing),
        )
    return len(missing)


def not_counted_note(without_order: int) -> str | None:
    """`1 past renewal has no order record and was not counted.` None when every order was found."""
    if without_order <= 0:
        return None
    return NOT_COUNTED_ONE if without_order == 1 else NOT_COUNTED_MANY.format(count=without_order)


def _own(store: Store, profile_id: str, standing_order_id: str) -> StandingOrder:
    standing = store.get_standing_order(standing_order_id)
    if standing is None or standing.profile_id != profile_id:
        raise InvalidRequest(UNKNOWN_STANDING_ORDER.format(standing_order_id=standing_order_id))
    return standing


def _past(store: Store, standing_order_id: str, excluding_offer_id: str | None) -> list[Renewal]:
    return [
        renewal for renewal in store.list_renewals(standing_order_id)
        if excluding_offer_id is None or renewal.offer_id != excluding_offer_id
    ]


class _Standing(Enum):
    COUNTED = "counted"  # a synthetic renewal, or one whose order is found and ORDERED
    NOT_ORDERED = "not ordered"  # its order waits, was rejected or expired
    NO_ORDER_RECORD = "no order record"  # it names an order the book does not hold


def _standing_of(store: Store, renewal: Renewal) -> _Standing:
    """Whether a renewal is part of what the kitchen usually orders. A renewal that names an order which cannot
    be found is not: nothing shows it was ever ordered (review finding P12)."""
    if renewal.order_id is None:
        return _Standing.COUNTED
    order = store.get_order(renewal.order_id)
    if order is None:
        return _Standing.NO_ORDER_RECORD
    return _Standing.COUNTED if order.status is COUNTED else _Standing.NOT_ORDERED


def history_lookup(store: Store) -> HistoryLookup:
    """`OfferDeps.standing_history` over one store: (profile id, standing order id) -> its history."""
    return lambda profile_id, standing_order_id: standing_history(store, profile_id, standing_order_id)
