"""The last line of a result: what happened to the request, in a headline and one sentence.

Scores on the 30% "request -> lookup -> order/approval flow" and the 20% "what the agent can decide alone,
what needs human sign-off": the page ends on "Ordered by the agent" or "Sent for approval", with the
gateway's own sentence for why. Nothing is decided here.
"""

from __future__ import annotations

from dataclasses import dataclass

from tta.contracts.common import OrderStatus, PlacedBy
from tta.contracts.offer import Offer
from tta.contracts.order import Order
from tta.ui.run import RunRecord
from tta.ui.view import BAD, OK, WARN

ORDERED_BY_AGENT = "Ordered by the agent"
ORDERED_WITH_APPROVAL = "Ordered with human approval"
SENT_FOR_APPROVAL = "Sent for approval"
REJECTED = "Rejected by a human"
EXPIRED = "Expired before a human decided"
NOT_ORDERED = "No order was placed"
NOTHING_TO_ORDER = "Nothing to order"
NO_OPTION = "No option could be built from Valio Aimo's data for this request. The reasons are listed above."
NO_ORDER_YET = "No order has been placed on this offer."

_HEADLINES = {
    OrderStatus.PENDING_APPROVAL: (SENT_FOR_APPROVAL, WARN),
    OrderStatus.REJECTED: (REJECTED, BAD),
    OrderStatus.EXPIRED: (EXPIRED, BAD),
}


@dataclass(frozen=True)
class Outcome:
    headline: str
    tone: str  # ok, warn or bad: the mark next to the headline
    sentence: str


def outcome_of_order(order: Order) -> Outcome:
    """The headline for an order's state, with the gateway's sentence for it."""
    if order.status is OrderStatus.ORDERED:
        by_agent = order.placed_by is PlacedBy.AGENT
        return Outcome(ORDERED_BY_AGENT if by_agent else ORDERED_WITH_APPROVAL, OK, order.status_sentence)
    headline, tone = _HEADLINES.get(order.status, (NOT_ORDERED, BAD))
    return Outcome(headline, tone, order.status_sentence)


def outcome_of_run(offer: Offer, order: Order | None, record: RunRecord | None) -> Outcome:
    """What happened to a request: its order when there is one, otherwise why there is none."""
    if order is not None:
        return outcome_of_order(order)
    if not offer.options:
        return Outcome(NOTHING_TO_ORDER, BAD, NO_OPTION)
    if record is not None and record.not_ordered is not None:
        refusal = record.not_ordered
        return Outcome(NOT_ORDERED, BAD, f"{refusal.title}. {refusal.detail}")
    if record is not None and record.agent_run is not None:
        return Outcome(NOT_ORDERED, BAD, record.agent_run.report)
    return Outcome(NOT_ORDERED, BAD, NO_ORDER_YET)
