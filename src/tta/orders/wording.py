"""Sentences of the order book: the status sentence of an order, error details and reasons for a refusal.

Plain English, short, with the number and the reason. Built from templates, never by a model. The phrases
(money, dates, roles) are the audit trail's, so an order and its trail read alike.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from tta.audit.phrases import ended, joined, moment, money, person, roles_text
from tta.contracts.common import ApproverRole, DecisionKind, Verdict
from tta.contracts.order import Approval, ApprovalDecision, Order
from tta.contracts.policy import PolicyDecision

ONLY_AN_AGENT_ORDERS = "Only a buyer's agent may place an order."
KEY_REQUIRED = "An order needs an Idempotency-Key, so that a retry cannot place a second order."
KEY_USED_FOR_ANOTHER_ORDER = (
    "This Idempotency-Key was already used for another order ({order_id}). Send a new key for a new order."
)
OFFER_OF_ANOTHER_BUYER = "This offer was made for another buyer."
NO_SUCH_OFFER = "No offer has this id."
NO_SUCH_OPTION = "Offer {offer_id} has no option with this id."
NO_SUCH_ORDER = "No order has this id."
NO_SUCH_APPROVAL = "No approval has this id."
ORDER_NOT_IN_BOOK = "The order of approval {approval_id} is not in the order book."
SUPPLIER_READS_THE_AUDIT_VIEW = (
    "The supplier reads no order and no approval here; the audit trail has a view for the supplier."
)
OF_ANOTHER_BUYER = "This belongs to another buyer."
AGENT_CANNOT_DECIDE = "An agent cannot approve or reject an order (F-06). A human with the role asked for decides."
ONLY_AN_APPROVER_DECIDES = "Only an approver of the buyer may decide an approval."
APPROVER_OF_ANOTHER_BUYER = "This approver belongs to another buyer."
APPROVER_NOT_LISTED = "This approver is not listed for any of its roles in profile {profile_id}."
ALREADY_DECIDED = "Approval {approval_id} is closed: order {order_id} is already {status}. It cannot be decided again."
REJECTION_CHOOSES_NO_OPTION = "A rejection cannot choose another option. Approve with the option, or reject without it."
FRESH_OFFER_NEEDED = "Ask for a fresh offer."
ORDER_BY_PASSED = (
    "Order {order_id} expired: it had to be decided by {deadline} and the approval was not complete. "
    "Nothing was ordered. Ask for a fresh offer."
)


def _asking(decision: PolicyDecision) -> tuple[str, ...]:
    """The ids of the rules that ask for a human, each once, in the order they fired."""
    return tuple(dict.fromkeys(rule.rule_id for rule in decision.fired if rule.verdict is Verdict.APPROVAL))


def _approvers(approval: Approval) -> str:
    given = (entry for entry in approval.decisions if entry.decision is DecisionKind.APPROVE)
    return joined(person(entry.approver_name, entry.roles) for entry in given)


def placed_alone(net: Decimal, profile_id: str) -> str:
    return f"The agent placed this order alone for {money(net)} net: no rule of profile {profile_id} asked for a human."


def waiting(approval: Approval, decision: PolicyDecision) -> str:
    approvers = _approvers(approval)
    start = f"Approved by {approvers}; still waiting" if approvers else "Waiting"
    deadline = f", to be decided by {moment(approval.valid_until)}" if approval.valid_until else ""
    rules = _asking(decision)
    why = f"{'rule' if len(rules) == 1 else 'rules'} {joined(rules)} {'asks' if len(rules) == 1 else 'ask'}"
    return f"{start} for approval by {roles_text(approval.roles_missing)}{deadline}: {why} for a human."


def ordered_with_approval(approval: Approval, net: Decimal, decision: PolicyDecision) -> str:
    rules = _asking(decision)
    why = ""
    if rules:
        named, verb = ("rule", "was") if len(rules) == 1 else ("rules", "were")
        why = f": {named} {joined(rules)} asked for a human and {verb} accepted"
    return f"Ordered for {money(net)} net with approval by {_approvers(approval)}{why}."


def rejected(entry: ApprovalDecision) -> str:
    return f"Rejected by {person(entry.approver_name, entry.roles)}: nothing was ordered."


def expired(order: Order, approval: Approval | None) -> str:
    missing = roles_text(approval.roles_missing) if approval is not None and approval.roles_missing else "a human"
    deadline = order.option.valid_until
    when = f" on {moment(deadline)}" if deadline is not None else ""
    return f"Expired{when} without approval by {missing}: nothing was ordered."


def order_by_passed(order: Order) -> str:
    deadline = order.option.valid_until
    return ORDER_BY_PASSED.format(order_id=order.order_id, deadline=moment(deadline) if deadline else "its time")


def already_decided(approval: Approval, order: Order) -> str:
    return ALREADY_DECIDED.format(
        approval_id=approval.approval_id, order_id=order.order_id, status=order.status.value.lower()
    )


def no_longer_as_offered(rule_sentence: str) -> str:
    """The policy's own sentence for F-04, then what to do next."""
    return f"{ended(rule_sentence)} {FRESH_OFFER_NEEDED}"


def role_not_missing(approval: Approval, roles: Sequence[ApproverRole]) -> str:
    return (
        f"The approval still needs {roles_text(approval.roles_missing)}; this approver counts for "
        f"{roles_text(roles)} and holds none of them."
    )
