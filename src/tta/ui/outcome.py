"""The last line of a result: what happened to the request, in a headline and one sentence.

Scores on the 30% "request -> lookup -> order/approval flow" and the 20% "what the agent can decide alone,
what needs human sign-off": the page ends on "Ordered by the agent" or "Sent for approval", with the
gateway's own sentence for why. Nothing is decided here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tta.contracts.common import ApproverRole, OrderStatus, PlacedBy
from tta.contracts.offer import Offer
from tta.contracts.order import Approval, Order
from tta.ui.run import RunRecord
from tta.ui.view import BAD, OK, WARN, words

ORDERED_BY_AGENT = "Ordered by the agent"
ORDERED_WITH_APPROVAL = "Ordered with human approval"
SENT_FOR_APPROVAL = "Sent for approval"
REJECTED = "Rejected by a human"
EXPIRED = "Expired before a human decided"
NOT_ORDERED = "No order was placed"
NOTHING_TO_ORDER = "Nothing to order"
NO_OPTION = "No option could be built from Valio Aimo's data for this request. The reasons are listed above."
NO_ORDER_YET = "No order has been placed on this offer."
# A waiting order that one person has already signed (A4 H2): the headline says so, or Approve looks undone.
PARTLY_APPROVED = "Approved by {signed}; waiting for {missing}"
ROLE_NAMES = {
    ApproverRole.PURCHASING_MANAGER: "the purchasing manager",
    ApproverRole.FINANCE: "finance",
    ApproverRole.DIETITIAN: "the dietitian",
}

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


def _roles(roles: Sequence[ApproverRole]) -> str:
    return " and ".join(ROLE_NAMES.get(role, words(role)) for role in roles)


def outcome_of_order(order: Order, approval: Approval | None = None) -> Outcome:
    """The headline for an order's state, with the gateway's sentence for it. `approval`: the waiting order's
    approval, which says who has signed already and who is still needed."""
    if order.status is OrderStatus.ORDERED:
        by_agent = order.placed_by is PlacedBy.AGENT
        return Outcome(ORDERED_BY_AGENT if by_agent else ORDERED_WITH_APPROVAL, OK, order.status_sentence)
    if order.status is OrderStatus.PENDING_APPROVAL and approval is not None and approval.roles_obtained:
        signed, missing = _roles(approval.roles_obtained), _roles(approval.roles_missing)
        return Outcome(PARTLY_APPROVED.format(signed=signed, missing=missing), WARN, order.status_sentence)
    headline, tone = _HEADLINES.get(order.status, (NOT_ORDERED, BAD))
    return Outcome(headline, tone, order.status_sentence)


def outcome_of_run(
    offer: Offer, order: Order | None, record: RunRecord | None, approval: Approval | None = None
) -> Outcome:
    """What happened to a request: its order when there is one, otherwise why there is none."""
    if order is not None:
        return outcome_of_order(order, approval)
    if not offer.options:
        return Outcome(NOTHING_TO_ORDER, BAD, NO_OPTION)
    if record is not None and record.not_ordered is not None:
        refusal = record.not_ordered
        return Outcome(NOT_ORDERED, BAD, f"{refusal.title}. {refusal.detail}")
    if record is not None and record.agent_run is not None:
        return Outcome(NOT_ORDERED, BAD, record.agent_run.report)
    return Outcome(NOT_ORDERED, BAD, NO_ORDER_YET)
