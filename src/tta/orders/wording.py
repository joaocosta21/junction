"""Sentences of the order book: the status sentence of an order, error details and reasons for a refusal.

Plain English, short, with the number and the reason. Built from templates, never by a model. The phrases
(money, dates, roles) are the audit trail's, so an order and its trail read alike.

Who a sentence names (decision B61, after one-person confirmation B54). A person who decided is named by name. A
role follows in brackets only at a buyer where more than one person can sign (the ward and the school, with their
dietitian), and then only the role that decision was asked of that person. A sentence that waits names who really
decides at that buyer: where the person who orders holds the dietitian's or finance's role, it says the purchasing
manager (`tta.policy.human_approval`). A caller that passes no profile gets names and the roles as they are.
A sentence is written when an order changes state and is stored with it: nothing stored is rewritten.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from tta.audit.phrases import MAX_NAME_CHARACTERS, ended, joined, moment, money, person, plain, roles_text
from tta.contracts.common import ApproverRole, DecisionKind, OrderStatus, Verdict
from tta.contracts.order import Approval, ApprovalDecision, Order
from tta.contracts.policy import BuyerProfile, PolicyDecision
from tta.policy.human_approval import HUMAN_APPROVAL, PREPARED, decided_as, roles_said, several_can_sign
from tta.policy.text import format_limit

ONLY_AN_AGENT_ORDERS = "Only a buyer's agent may place an order."
KEY_REQUIRED = "An order needs an Idempotency-Key, so that a retry cannot place a second order."
KEY_NOT_VALID = (
    'An Idempotency-Key is 1 to 100 characters: letters, digits, ".", "_", ":" and "-". A UUID fits.'
)
KEY_USED_FOR_ANOTHER_ORDER = (
    "This Idempotency-Key was already used for another order ({order_id}). Send a new key for a new order."
)
KEY_BOUND_MEANWHILE = (
    "Another request with this Idempotency-Key was being processed at the same moment. Nothing was ordered by "
    "this one. Send the request again to get the order of that key."
)
OFFER_ALREADY_ORDERED = (
    "Offer {offer_id} already has an order: {order_id}, which is {state}. An offer answers one request; "
    "ask for a fresh offer to order again."
)
ORDER_STATES = {OrderStatus.ORDERED: "ordered", OrderStatus.PENDING_APPROVAL: "waiting for approval"}
NO_SUCH_OFFER = "No offer has this id."
NO_SUCH_OPTION = "Offer {offer_id} has no option with this id."
NO_SUCH_ORDER = "No order has this id."
NO_SUCH_APPROVAL = "No approval has this id."
ORDER_NOT_IN_BOOK = "The order of approval {approval_id} is not in the order book."
OFFER_NOT_IN_STORE = "The offer of order {order_id} is no longer stored."
# Task S2: evidence found on the web, named among the reasons of the approval it was attached to.
EVIDENCE_REASON = (
    "Web evidence for product {product_id} is attached for the dietitian, and it is not Valio Aimo's data: "
    "{sentence} It changes no verdict: a human decides."
)
SUPPLIER_READS_THE_AUDIT_VIEW = (
    "The supplier reads no order and no approval here; the audit trail has a view for the supplier."
)
AGENT_CANNOT_DECIDE = "An agent cannot approve or reject an order (F-06). A human with the role asked for decides."
ONLY_AN_APPROVER_DECIDES = "Only an approver of the buyer may decide an approval."
APPROVER_NOT_LISTED = "This approver is not listed for any of its roles in profile {profile_id}."
ALREADY_DECIDED = "Approval {approval_id} is closed: order {order_id} is already {status}. It cannot be decided again."
REJECTION_CHOOSES_NO_OPTION = "A rejection cannot choose another option. Approve with the option, or reject without it."
FRESH_OFFER_NEEDED = "Ask for a fresh offer."
# Why a prepared order waits, at the end of its status sentence.
CONFIRMATION_RULE = f"rule {HUMAN_APPROVAL.rule_id}: a person confirms every order"
ORDER_BY_PASSED = (
    "Order {order_id} expired: it had to be decided by {deadline} and the approval was not complete. "
    "Nothing was ordered. Ask for a fresh offer."
)
# An order the agent placed alone says why it was allowed, from the values the order-time check read: the buyer's
# setting, the two spend limits, and that nothing asked for a person. No rule id: a person reads it on the order.
PLACED_ALONE = "The agent placed this order alone for {net} net"
ALLOWED = " That was allowed: {reasons}."
ALONE_SWITCHED_ON = "ordering alone is switched on for {buyer}"
ALONE_WITHIN_ORDER_LIMIT = "the total of {net} is within the {limit} limit per order"
ALONE_WITHIN_DAY_LIMIT = "today's spend with this order is {day} of the {limit} limit per day"
ALONE_ALL_CONFIRMED = "every statement of the offer is confirmed"
ALONE_NO_RULE = "no rule asked for a person"


def _asking(decision: PolicyDecision) -> tuple[str, ...]:
    """The ids of the rules that ask for a human, each once, in the order they fired."""
    return tuple(dict.fromkeys(rule.rule_id for rule in decision.fired if rule.verdict is Verdict.APPROVAL))


def _signer(
    name: str, roles: Sequence[ApproverRole], asked: Sequence[ApproverRole], profile: BuyerProfile | None
) -> str:
    """One person who decided, by name. In brackets, at a buyer where more than one person can sign: the roles
    this approval asked of that person, each as it is really decided there (finance's as the purchasing manager's
    where one person holds both)."""
    if profile is None or not several_can_sign(profile):
        return person(name, ())
    theirs = dict.fromkeys(decided_as(profile, role) for role in asked if role in roles)
    return person(name, tuple(theirs))


def _approvers(approval: Approval, profile: BuyerProfile | None = None) -> str:
    """Everybody who approved, each person once. One person can sign under several identities (the shop page
    signs role by role, each under the name of the customer's person): the name is what a reader sees."""
    by_name: dict[str, tuple[ApproverRole, ...]] = {}
    for entry in approval.decisions:
        if entry.decision is DecisionKind.APPROVE:
            by_name = {**by_name, entry.approver_name: (*by_name.get(entry.approver_name, ()), *entry.roles)}
    return joined(_signer(name, roles, approval.required_roles, profile) for name, roles in by_name.items())


def _only_confirmation_is_asked(decision: PolicyDecision) -> bool:
    """True when F-10 is the only rule that asks for a person: the order is prepared and waits to be confirmed."""
    return _asking(decision) == (HUMAN_APPROVAL.rule_id,)


def _limit(value: Decimal) -> str:
    """A limit as the buyer set it: €750, never €750.00."""
    return f"€{format_limit(value)}"


def placed_alone(net: Decimal, profile: BuyerProfile | None = None, day_net: Decimal | None = None) -> str:
    """Why the agent could place this order alone. `profile` is the buyer's in force at the order-time check and
    `day_net` the day's spend that check judged on, this order included; a value the caller does not have leaves
    its clause out, it is never guessed. A buyer is named by its name, never by its profile id."""
    reasons: list[str] = []
    if profile is not None:
        reasons.append(ALONE_SWITCHED_ON.format(buyer=plain(profile.display_name, MAX_NAME_CHARACTERS)))
        reasons.append(ALONE_WITHIN_ORDER_LIMIT.format(net=money(net), limit=_limit(profile.max_order_net_eur)))
        if day_net is not None:
            reasons.append(
                ALONE_WITHIN_DAY_LIMIT.format(day=money(day_net), limit=_limit(profile.max_daily_net_eur))
            )
    reasons.extend((ALONE_ALL_CONFIRMED, f"and {ALONE_NO_RULE}"))
    return PLACED_ALONE.format(net=money(net)) + "." + ALLOWED.format(reasons="; ".join(reasons))


def _prepared(approval: Approval, profile: BuyerProfile | None) -> str:
    approvers = _approvers(approval, profile)
    start = f"Confirmed by {approvers}; still waiting" if approvers else f"{PREPARED} Waiting"
    deadline = f", by {moment(approval.valid_until)}" if approval.valid_until else ""
    return f"{start} for {roles_said(approval.roles_missing, profile)} to confirm{deadline} ({CONFIRMATION_RULE})."


def waiting(approval: Approval, decision: PolicyDecision, profile: BuyerProfile | None = None) -> str:
    if _only_confirmation_is_asked(decision):
        return _prepared(approval, profile)
    approvers = _approvers(approval, profile)
    start = f"Approved by {approvers}; still waiting" if approvers else "Waiting"
    deadline = f", to be decided by {moment(approval.valid_until)}" if approval.valid_until else ""
    rules = _asking(decision)
    why = f"{'rule' if len(rules) == 1 else 'rules'} {joined(rules)} {'asks' if len(rules) == 1 else 'ask'}"
    return f"{start} for approval by {roles_said(approval.roles_missing, profile)}{deadline}: {why} for a human."


def ordered_with_approval(
    approval: Approval, net: Decimal, decision: PolicyDecision, profile: BuyerProfile | None = None
) -> str:
    if _only_confirmation_is_asked(decision):
        return f"Confirmed by {_approvers(approval, profile)}: ordered for {money(net)} net."
    rules = _asking(decision)
    why = ""
    if rules:
        named, verb = ("rule", "was") if len(rules) == 1 else ("rules", "were")
        why = f": {named} {joined(rules)} asked for a human and {verb} accepted"
    return f"Ordered for {money(net)} net with approval by {_approvers(approval, profile)}{why}."


def rejected(
    entry: ApprovalDecision, asked: Sequence[ApproverRole] = (), profile: BuyerProfile | None = None
) -> str:
    """`asked` are the roles the approval named: the one this person was asked for is said where it tells them
    apart from a second signer."""
    return f"Rejected by {_signer(entry.approver_name, entry.roles, asked, profile)}: nothing was ordered."


def deadline_of(order: Order, approval: Approval | None) -> datetime | None:
    """Until when a waiting order can be decided: the time on its approval, else the option's "order by" time."""
    return (approval.valid_until if approval is not None else None) or order.option.valid_until


def expired(order: Order, approval: Approval | None, profile: BuyerProfile | None = None) -> str:
    asked = approval.roles_missing if approval is not None else ()
    missing = roles_said(asked, profile) if asked else "a human"
    deadline = deadline_of(order, approval)
    when = f" on {moment(deadline)}" if deadline is not None else ""
    return f"Expired{when} without approval by {missing}: nothing was ordered."


def order_by_passed(order: Order, deadline: datetime | None) -> str:
    return ORDER_BY_PASSED.format(order_id=order.order_id, deadline=moment(deadline) if deadline else "its time")


def offer_already_ordered(order: Order) -> str:
    return OFFER_ALREADY_ORDERED.format(
        offer_id=order.offer_id, order_id=order.order_id, state=ORDER_STATES[order.status]
    )


def already_decided(approval: Approval, order: Order) -> str:
    return ALREADY_DECIDED.format(
        approval_id=approval.approval_id, order_id=order.order_id, status=order.status.value.lower()
    )


def no_longer_as_offered(rule_sentence: str) -> str:
    """The policy's own sentence for F-04, then what to do next."""
    return f"{ended(rule_sentence)} {FRESH_OFFER_NEEDED}"


def role_not_missing(missing: Sequence[ApproverRole], roles: Sequence[ApproverRole]) -> str:
    """`missing` are the roles still needed: for an approval, those the order-time decision asks for now."""
    return (
        f"The approval still needs {roles_text(missing)}; this approver counts for "
        f"{roles_text(roles)} and holds none of them."
    )
