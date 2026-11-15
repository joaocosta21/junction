"""The order and approval records and every change of state, as pure functions: each returns new objects.

Scores on the 30% flow (the order record is the end of request → lookup → order) and on Core 2: the record
keeps the statements the order relied on and says that the mock has no order endpoint (SPEC section 8).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from tta.contracts.availability import RevalidationResult
from tta.contracts.common import (
    ApprovalStatus,
    ApproverRole,
    DecisionKind,
    Identity,
    OrderStatus,
    PlacedBy,
    Verdict,
)
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.order import (
    ORDER_RECORD_NOTE,
    Approval,
    ApprovalDecision,
    DecisionRequest,
    Evidence,
    Order,
    RelianceStatement,
)
from tta.contracts.policy import BuyerProfile, PolicyDecision
from tta.contracts.standing import StandingHistory
from tta.orders import wording
from tta.policy.human_approval import let_a_named_role_sign

if TYPE_CHECKING:
    from tta.orders.spend import DaySpend  # spend imports this module

ORDER_ID_PREFIX = "ord_"
DAY_RULE_ID = "P-02"  # src/tta/policy/rules.yaml: the day's spend would pass the limit per day
APPROVAL_ID_PREFIX = "apr_"
ID_RANDOM_BYTES = 6  # 12 hex characters
# Kept on the order so a retry with the same Idempotency-Key can be told from a reuse of the key for
# something else, also after an approver chose another option.
REQUESTED_OPTION_KEY = "requested_option_id"
# An option with no "order by" time of its own: its approval must be decided within this time, so that no
# order waits for ever. Ours, not Valio's.
HOURS_TO_DECIDE_WITHOUT_ORDER_BY = 24
# The payment position on every order record (AIMO/build/replan/P16-payments.md, PAY-2). Valio Aimo's site names
# two kinds of wholesale customer: a credit customer pays by invoice, a "Pay Now" customer pays when ordering.
# That the demo buyers are credit customers is our assumption, and the sentence says so. "For what is delivered"
# is Valio Aimo's answer of 14 Nov on goods sold by weight (BOOTH-NOW Q16).
NO_PAYMENT_NOTE = (
    "No payment is taken here: the buyer is assumed to be a Valio Aimo credit customer, invoiced after delivery "
    "for what is delivered."
)
RECORD_NOTE = f"{ORDER_RECORD_NOTE} {NO_PAYMENT_NOTE}"


@dataclass(frozen=True)
class OrderTimeCheck:
    """One option as it stood just before the order: the fresh look at Valio's data and the policy's answer."""

    option: OfferOption  # carries `decision`
    decision: PolicyDecision
    revalidation: RevalidationResult
    day: DaySpend | None = None  # the day's spend the policy judged on, this order left out
    standing: StandingHistory | None = None  # the history rule P-08 judged on; None when nothing is renewed


def new_order_id() -> str:
    return f"{ORDER_ID_PREFIX}{secrets.token_hex(ID_RANDOM_BYTES)}"


def new_approval_id() -> str:
    return f"{APPROVAL_ID_PREFIX}{secrets.token_hex(ID_RANDOM_BYTES)}"


def is_past_order_by(order: Order, now: datetime) -> bool:
    """A pending order whose "order by" time has passed. A time equal to the clock has passed: at that very
    instant the order can no longer be decided, as in the policy (F-04), availability and the offer re-check."""
    deadline = order.option.valid_until
    return order.status is OrderStatus.PENDING_APPROVAL and deadline is not None and deadline <= now


def decide_by(option: OfferOption, approval_created_at: datetime) -> datetime:
    """Until when an approval of this option can be decided: the option's "order by" time, or 24 hours after the
    approval was created when the option has none."""
    return option.valid_until or approval_created_at + timedelta(hours=HOURS_TO_DECIDE_WITHOUT_ORDER_BY)


def is_overdue(order: Order, approval: Approval | None, now: datetime) -> bool:
    """A waiting order past its time: the option's "order by" time, or the approval's own when the option has none.

    The comparison itself is `is_past_order_by`'s, so there is one boundary for both.
    """
    if order.option.valid_until is not None or approval is None:
        return is_past_order_by(order, now)
    dated = order.option.model_copy(update={"valid_until": approval.valid_until})
    return is_past_order_by(order.model_copy(update={"option": dated}), now)


def signed_by_a_named_role(
    check: OrderTimeCheck, approval: Approval, signer_roles: tuple[ApproverRole, ...]
) -> OrderTimeCheck:
    """The check as it holds for this signer: when F-10 is the only rule left at decision time, one signature of
    a role the approval already names completes it, whatever other roles the approval named
    (`tta.policy.human_approval.let_a_named_role_sign`)."""
    decision = let_a_named_role_sign(check.decision, approval.required_roles, signer_roles)
    if decision is check.decision:
        return check
    return replace(check, option=check.option.model_copy(update={"decision": decision}), decision=decision)


def roles_still_needed(approval: Approval, check: OrderTimeCheck) -> tuple[ApproverRole, ...]:
    """The roles the order-time decision asks for and nobody has given yet. An approval given for another
    option than the one checked does not count."""
    same_option = check.option.option_id == approval.option_id
    given = {
        role
        for entry in approval.decisions
        if same_option and entry.decision is DecisionKind.APPROVE
        for role in entry.roles
    }
    return tuple(role for role in check.decision.required_roles if role not in given)


def reliance_statements(check: OrderTimeCheck, stated_at: datetime) -> tuple[RelianceStatement, ...]:
    """What Valio's data said about each line, as the offer gave it. `stated_at` is the offer's data time, when
    Valio stated the figures; `rechecked_at` is the fresh look before the order that found them still sufficient."""
    return tuple(
        RelianceStatement(
            product_id=line.product_id,
            unit_net_price=line.unit_net_price,
            price_valid_to=line.price_valid_to,
            availability_state=line.availability.state,
            available_amount=line.availability.usable_amount,  # None unless confirmed: a placeholder is no amount
            available_date=line.availability.available_date,
            closing_time=line.availability.closing_time,
            time_now=stated_at,
            rechecked_at=check.revalidation.checked_at,
            source=check.revalidation.source,
        )
        for line in check.option.lines
    )


def approval_reasons(decision: PolicyDecision) -> tuple[str, ...]:
    """One sentence per rule that asks for a human, as the policy wrote them."""
    return tuple(rule.sentence for rule in decision.fired if rule.verdict is Verdict.APPROVAL)


def day_reasons(check: OrderTimeCheck) -> tuple[str, ...]:
    """When the limit per day asks for a human (P-02): how much of the day is ordered and how much is waiting, so
    the person can tell a day of orders from a day of requests nobody has approved yet (review A4, finding H2)."""
    held_back = any(
        rule.rule_id == DAY_RULE_ID and rule.verdict is Verdict.APPROVAL for rule in check.decision.fired
    )
    return (check.day.sentence,) if held_back and check.day is not None else ()


def evidence_reasons(evidence: tuple[Evidence, ...], option: OfferOption) -> tuple[str, ...]:
    """One sentence per piece of web evidence found for a product of this option (task S2). Evidence that found
    nothing is shown on the card, not listed as a reason."""
    in_option = set(option.product_ids)
    return tuple(
        wording.EVIDENCE_REASON.format(product_id=item.product_id, sentence=item.sentence)
        for item in evidence
        if item.found and item.product_id in in_option
    )


def placed_by_agent(
    order_id: str, offer: Offer, check: OrderTimeCheck, agent: Identity, idempotency_key: str, now: datetime,
    profile: BuyerProfile | None = None,
) -> Order:
    """The order the agent placed alone: no rule asked for a human. Its status sentence says why it was allowed,
    from the buyer's profile and the day's spend the order-time check judged on."""
    net = check.option.totals.net
    day_net = check.day.committed + net if check.day is not None else None
    return Order(
        order_id=order_id, offer_id=offer.offer_id, option_id=check.option.option_id, profile_id=offer.profile_id,
        agent_id=agent.id, status=OrderStatus.ORDERED, placed_by=PlacedBy.AGENT, option=check.option,
        decision=check.decision, reliance=reliance_statements(check, offer.time_now), idempotency_key=idempotency_key,
        created_at=now, updated_at=now,
        status_sentence=wording.placed_alone(net, profile, day_net),
        source=check.revalidation.source, extra={REQUESTED_OPTION_KEY: check.option.option_id},
        record_note=RECORD_NOTE,
    )


def awaiting_approval(
    order_id: str, offer: Offer, check: OrderTimeCheck, agent: Identity, idempotency_key: str, now: datetime,
    evidence: tuple[Evidence, ...] = (), profile: BuyerProfile | None = None,
) -> tuple[Order, Approval]:
    """The order that waits for a human, and the approval that names the roles it needs. `evidence` was found
    outside Valio Aimo's data for the human to read; it changes no role and no verdict. `profile` is the buyer's:
    the status sentence names who really decides there."""
    reasons = (*approval_reasons(check.decision), *day_reasons(check), *evidence_reasons(evidence, check.option))
    approval = Approval(
        approval_id=new_approval_id(), order_id=order_id, offer_id=offer.offer_id,
        option_id=check.option.option_id, profile_id=offer.profile_id, status=ApprovalStatus.PENDING,
        required_roles=check.decision.required_roles, reasons=reasons, evidence=evidence, created_at=now,
        valid_until=decide_by(check.option, now),
    )
    # The same record as an order placed alone, in the state of one that waits.
    order = placed_by_agent(order_id, offer, check, agent, idempotency_key, now).model_copy(update={
        "status": OrderStatus.PENDING_APPROVAL, "placed_by": None, "approval_id": approval.approval_id,
        "status_sentence": wording.waiting(approval, check.decision, profile),
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
    stated_at: datetime, profile: BuyerProfile | None = None,
) -> tuple[Order, Approval]:
    """The order and approval after one human approved `check.option`: ORDERED once no role is missing.

    The roles are those the policy asks for now. Approvals given for another option do not carry over:
    choosing another option starts the approval again with this human's decision. `stated_at` is the data
    time of the offer, for the statements the order relies on.
    """
    other_option = check.option.option_id != approval.option_id
    signed = approval.model_copy(update={
        "option_id": check.option.option_id,
        "required_roles": check.decision.required_roles,
        "reasons": (
            *approval_reasons(check.decision), *day_reasons(check),
            *evidence_reasons(approval.evidence, check.option),
        ),
        "decisions": (entry,) if other_option else (*approval.decisions, entry),
        "valid_until": decide_by(check.option, approval.created_at),
    })
    complete = not signed.roles_missing
    if complete:
        signed = signed.model_copy(update={"status": ApprovalStatus.APPROVED})
    sentence = (
        wording.ordered_with_approval(signed, check.option.totals.net, check.decision, profile)
        if complete else wording.waiting(signed, check.decision, profile)
    )
    changed = order.model_copy(update={
        "option_id": check.option.option_id, "option": check.option, "decision": check.decision,
        "reliance": reliance_statements(check, stated_at), "source": check.revalidation.source,
        "status": OrderStatus.ORDERED if complete else OrderStatus.PENDING_APPROVAL,
        "placed_by": PlacedBy.HUMAN_APPROVAL if complete else None, "updated_at": now, "status_sentence": sentence,
    })
    return changed, signed


def rejected(
    order: Order, approval: Approval, entry: ApprovalDecision, now: datetime, profile: BuyerProfile | None = None,
) -> tuple[Order, Approval]:
    """The order and approval after one human rejected it. Nothing was ordered."""
    closed = approval.model_copy(update={"status": ApprovalStatus.REJECTED, "decisions": (*approval.decisions, entry)})
    changed = order.model_copy(update={
        "status": OrderStatus.REJECTED, "updated_at": now,
        "status_sentence": wording.rejected(entry, approval.required_roles, profile),
    })
    return changed, closed


def expired(
    order: Order, approval: Approval | None, now: datetime, profile: BuyerProfile | None = None,
) -> tuple[Order, Approval | None]:
    """The order after its "order by" time passed without a complete approval. Nothing was ordered."""
    closed = approval.model_copy(update={"status": ApprovalStatus.EXPIRED}) if approval is not None else None
    changed = order.model_copy(update={
        "status": OrderStatus.EXPIRED, "updated_at": now,
        "status_sentence": wording.expired(order, approval, profile),
    })
    return changed, closed
