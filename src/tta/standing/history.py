"""The history rule P-08 reads: a standing order's past renewals, read from the store (task STAND-1).

The offer builder reads it when a request names a standing order, and the order book reads it again at order time
and when an approver decides, so the verdict rests on the same history at every step.
"""

from __future__ import annotations

from collections.abc import Callable

from tta.contracts.common import OrderStatus
from tta.contracts.errors import InvalidRequest
from tta.contracts.ports import Store
from tta.contracts.standing import Renewal, StandingHistory

UNKNOWN_STANDING_ORDER = (
    "No standing order {standing_order_id} is set up for this buyer, so the request cannot renew it. "
    "Send the request without standing_order_id, or set the standing order up first (POST /v1/standing-orders)."
)
# Only a renewal that was ordered is part of what the kitchen usually orders. One that still waits for a person,
# that a person rejected or that expired waiting is not: otherwise the agent's own unapproved requests would move
# the median its next renewal is judged against (review A2a, finding S-1).
COUNTED = OrderStatus.ORDERED

HistoryLookup = Callable[[str, str], StandingHistory]


def standing_history(
    store: Store, profile_id: str, standing_order_id: str, *, excluding_offer_id: str | None = None
) -> StandingHistory:
    """The standing order's past renewals, oldest first. `excluding_offer_id` leaves out the renewal being judged,
    which is already recorded when an approver decides it. Raises `InvalidRequest` for a standing order this buyer
    does not have: another buyer's reads as one nobody set up."""
    standing = store.get_standing_order(standing_order_id)
    if standing is None or standing.profile_id != profile_id:
        raise InvalidRequest(UNKNOWN_STANDING_ORDER.format(standing_order_id=standing_order_id))
    renewals = [
        renewal for renewal in store.list_renewals(standing_order_id)
        if (excluding_offer_id is None or renewal.offer_id != excluding_offer_id) and _counts(store, renewal)
    ]
    return StandingHistory(
        standing_order_id=standing.standing_order_id, name=standing.name, cadence_days=standing.cadence_days,
        renewals=tuple(sorted(renewals, key=lambda renewal: renewal.renewed_at)),  # stable: saved order on a tie
    )


def _counts(store: Store, renewal: Renewal) -> bool:
    """A synthetic renewal, or one whose order was placed. An order that cannot be found is kept: leaving it out
    could only remove a check."""
    if renewal.order_id is None:
        return True
    order = store.get_order(renewal.order_id)
    return order is None or order.status is COUNTED


def history_lookup(store: Store) -> HistoryLookup:
    """`OfferDeps.standing_history` over one store: (profile id, standing order id) -> its history."""
    return lambda profile_id, standing_order_id: standing_history(store, profile_id, standing_order_id)
