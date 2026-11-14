"""The answers of the standing-order service that hold an offer or an order (task STAND-1).

They live here rather than in `tta.contracts.standing`, which `PolicyContext` imports and which therefore may not
import the offer or the order contract.
"""

from __future__ import annotations

from tta.contracts.common import Contract
from tta.contracts.offer import Offer
from tta.contracts.order import Order
from tta.contracts.standing import DriftReport, Renewal, StandingOrder


class StandingOrderDetail(Contract):
    """Answer of GET /v1/standing-orders/{id}: the standing order and every renewal it has, oldest first. A renewal
    made up for the demonstration says so (`synthetic`)."""

    standing_order: StandingOrder
    renewals: tuple[Renewal, ...] = ()


class RenewalOutcome(Contract):
    """Answer of a renewal: the offer built from the stored request, the drift found, and the order placed."""

    standing_order: StandingOrder
    offer: Offer
    option_id: str | None = None  # the top option, the one ordered; None when no option fits
    order: Order | None = None
    drift: DriftReport | None = None  # None when no option fits: there is nothing to compare
    renewal: Renewal | None = None  # recorded in the history when an order exists
    sentence: str
