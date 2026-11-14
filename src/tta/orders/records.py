"""The order and approval records and every change of state, as pure functions: each returns new objects.

Scores on the 30% flow (the order record is the end of request → lookup → order) and on Core 2: the record
keeps the statements the order relied on and says that the mock has no order endpoint (SPEC section 8).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime

from tta.contracts.availability import RevalidationResult
from tta.contracts.common import (
    ApprovalStatus,
    ApproverRole,
    Identity,
    OrderStatus,
    PlacedBy,
    Verdict,
)
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.order import Approval, ApprovalDecision, DecisionRequest, Order, RelianceStatement
from tta.contracts.policy import PolicyDecision
from tta.orders import wording

ORDER_ID_PREFIX = "ord_"
APPROVAL_ID_PREFIX = "apr_"
ID_RANDOM_BYTES = 6  # 12 hex characters
# Kept on the order so a retry with the same Idempotency-Key can be told from a reuse of the key for
# something else, also after an approver chose another option.
REQUESTED_OPTION_KEY = "requested_option_id"


@dataclass(frozen=True)
class OrderTimeCheck:
    """One option as it stood just before the order: the fresh look at Valio's data and the policy's answer."""

    option: OfferOption  # carries `decision`
    decision: PolicyDecision
    revalidation: RevalidationResult


def new_order_id() -> str:
    return f"{ORDER_ID_PREFIX}{secrets.token_hex(ID_RANDOM_BYTES)}"


def new_approval_id() -> str:
    return f"{APPROVAL_ID_PREFIX}{secrets.token_hex(ID_RANDOM_BYTES)}"


def is_past_order_by(order: Order, now: datetime) -> bool:
    """A pending order whose "order by" time has passed. At that very instant it can still be decided."""
    deadline = order.option.valid_until
    return order.status is OrderStatus.PENDING_APPROVAL and deadline is not None and deadline < now


def reliance_statements(check: OrderTimeCheck) -> tuple[RelianceStatement, ...]:
    """What Valio's data said about each line when the order was checked: the fresh look confirmed the offer's
    statements, so they are kept as the offer gave them, with the time and source of the check."""
    return tuple(
        RelianceStatement(
            product_id=line.product_id,
            unit_net_price=line.unit_net_price,
            price_valid_to=line.price_valid_to,
            availability_state=line.availability.state,
            available_amount=line.availability.usable_amount,  # None unless confirmed: a placeholder is no amount
            available_date=line.availability.available_date,
            closing_time=line.availability.closing_time,
            time_now=check.revalidation.checked_at,
            source=check.revalidation.source,
        )
        for line in check.option.lines
    )


def approval_reasons(decision: PolicyDecision) -> tuple[str, ...]:
    """One sentence per rule that asks for a human, as the policy wrote them."""
    return tuple(rule.sentence for rule in decision.fired if rule.verdict is Verdict.APPROVAL)


def placed_by_agent(
    order_id: str, offer: Offer, check: OrderTimeCheck, agent: Identity, idempotency_key: str, now: datetime,
) -> Order:
    """The order the agent placed alone: no rule asked for a human."""
    return Order(
        order_id=order_id, offer_id=offer.offer_id, option_id=check.option.option_id, profile_id=offer.profile_id,
        agent_id=agent.id, status=OrderStatus.ORDERED, placed_by=PlacedBy.AGENT, option=check.option,
        decision=check.decision, reliance=reliance_statements(check), idempotency_key=idempotency_key,
        created_at=now, updated_at=now,
        status_sentence=wording.placed_alone(check.option.totals.net, offer.profile_id),
        source=check.revalidation.source, extra={REQUESTED_OPTION_KEY: check.option.option_id},
    )


def awaiting_approval(
    order_id: str, offer: Offer, check: OrderTimeCheck, agent: Identity, idempotency_key: str, now: datetime,
) -> tuple[Order, Approval]:
    """The order that waits for a human, and the approval that names the roles it needs."""
    approval = Approval(
        approval_id=new_approval_id(), order_id=order_id, offer_id=offer.offer_id,
        option_id=check.option.option_id, profile_id=offer.profile_id, status=ApprovalStatus.PENDING,
        required_roles=check.decision.required_roles, reasons=approval_reasons(check.decision), created_at=now,
        valid_until=check.option.valid_until,
    )
    # The same record as an order placed alone, in the state of one that waits.
    order = placed_by_agent(order_id, offer, check, agent, idempotency_key, now).model_copy(update={
        "status": OrderStatus.PENDING_APPROVAL, "placed_by": None, "approval_id": approval.approval_id,
        "status_sentence": wording.waiting(approval, check.decision),
    })
    return order, approval


def decision_entry(
    approver: Identity, roles: tuple[ApproverRole, ...], request: DecisionRequest, chosen_option_id: str | None,
    now: datetime,
) -> ApprovalDecision:
    """One human's decision. `roles` are the ones that count for this buyer; `chosen_option_id` is set only
    when the human picked another option than the one proposed."""
    return ApprovalDecision(
        approver_id=approver.id, approver_name=approver.display_name, roles=roles, decision=request.decision,
        option_id=chosen_option_id, note=request.note, decided_at=now,
    )


def approved(
    order: Order, approval: Approval, check: OrderTimeCheck, entry: ApprovalDecision, now: datetime,
) -> tuple[Order, Approval]:
    """The order and approval after one human approved `check.option`: ORDERED once no role is missing.

    The roles are those the policy asks for now. Approvals given for another option do not carry over:
    choosing another option starts the approval again with this human's decision.
    """
    other_option = check.option.option_id != approval.option_id
    signed = approval.model_copy(update={
        "option_id": check.option.option_id,
        "required_roles": check.decision.required_roles,
        "reasons": approval_reasons(check.decision),
        "decisions": (entry,) if other_option else (*approval.decisions, entry),
        "valid_until": check.option.valid_until,
    })
    complete = not signed.roles_missing
    if complete:
        signed = signed.model_copy(update={"status": ApprovalStatus.APPROVED})
    sentence = (
        wording.ordered_with_approval(signed, check.option.totals.net, check.decision)
        if complete else wording.waiting(signed, check.decision)
    )
    changed = order.model_copy(update={
        "option_id": check.option.option_id, "option": check.option, "decision": check.decision,
        "reliance": reliance_statements(check), "source": check.revalidation.source,
        "status": OrderStatus.ORDERED if complete else OrderStatus.PENDING_APPROVAL,
        "placed_by": PlacedBy.HUMAN_APPROVAL if complete else None, "updated_at": now, "status_sentence": sentence,
    })
    return changed, signed


def rejected(order: Order, approval: Approval, entry: ApprovalDecision, now: datetime) -> tuple[Order, Approval]:
    """The order and approval after one human rejected it. Nothing was ordered."""
    closed = approval.model_copy(update={"status": ApprovalStatus.REJECTED, "decisions": (*approval.decisions, entry)})
    changed = order.model_copy(update={
        "status": OrderStatus.REJECTED, "updated_at": now, "status_sentence": wording.rejected(entry),
    })
    return changed, closed


def expired(order: Order, approval: Approval | None, now: datetime) -> tuple[Order, Approval | None]:
    """The order after its "order by" time passed without a complete approval. Nothing was ordered."""
    closed = approval.model_copy(update={"status": ApprovalStatus.EXPIRED}) if approval is not None else None
    changed = order.model_copy(update={
        "status": OrderStatus.EXPIRED, "updated_at": now, "status_sentence": wording.expired(order, approval),
    })
    return changed, closed
