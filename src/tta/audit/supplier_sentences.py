"""Valio Aimo's sentence for each event type: what was asked of its data, what was offered and ordered,
who the agent was, and whether it acted within its authority or with human approval (SPEC section 9).

No sentence here reads a limit value, an allergen exclusion, an approver's name or role, or a note.
A rule's own sentence is never quoted, because it can carry a limit; a fixed rule that does not come from
the buyer's limits or exclusions is named with the meaning of SPEC section 7.

As for the buyer, a sentence states only what its context holds and says what is not recorded.
"""

from __future__ import annotations

from tta.audit.phrases import (
    HUMAN_AT_BUYER,
    NOTHING_ORDERED,
    actor_text,
    capital,
    joined,
    label,
    option_text,
    request_text,
)
from tta.audit.readers import SUPPLIER_RULE_MEANINGS, supplier_rule_ids
from tta.audit.scope import Scope, confirmed_by, option_change, placed_within_authority
from tta.audit.sentences import (
    BY_THE_AGENT,
    DECISION_BEHIND_NOT_RECORDED,
    DECISION_NOT_RECORDED,
    SentenceBuilder,
    agent_refused,
    checked_for,
    confirmed_text,
    lookup_performed,
    offer_text,
    order_not_placed,
    recorded_note,
)
from tta.contracts.audit import Actor, ActorKind, AuditContext, AuditEventType
from tta.contracts.common import DecisionKind, PlacedBy, Verdict

VERDICT_OUTCOMES = {
    Verdict.AUTO: "the agent may place this order within its authority.",
    Verdict.APPROVAL: f"{HUMAN_AT_BUYER} must approve this order.",
    Verdict.BLOCK: "this order cannot be placed.",
}


def _what(scope: Scope) -> str:
    return f": {option_text(scope.option)}" if scope.option else ""


def _fixed_rules(scope: Scope) -> str:
    """The fixed rules the supplier may see, each with its meaning. Stated as what happened, not as a fault."""
    visible = supplier_rule_ids(scope.decision.rule_ids) if scope.decision else ()
    if not visible:
        return ""
    named = joined(f"{rule_id} ({SUPPLIER_RULE_MEANINGS[rule_id]})" for rule_id in visible)
    return f" Fixed {'rule' if len(visible) == 1 else 'rules'} that applied: {named}."


def request_received(actor: Actor, context: AuditContext, scope: Scope) -> str:
    if actor.kind is ActorKind.AGENT:
        return "The buyer's agent sent a purchase request."
    return "A purchase request was received."


def request_parsed(actor: Actor, context: AuditContext, scope: Scope) -> str:
    if context.request is None:
        return "The request was read into a typed request."
    return f"The request was read as: {request_text(context.request, with_exclusions=False)}."


def offer_created(actor: Actor, context: AuditContext, scope: Scope) -> str:
    if context.offer is None:
        return f"The gateway built {f'offer {scope.offer_id}' if scope.offer_id else 'an offer'}."
    return offer_text(context.offer, for_buyer=False)


def policy_evaluated(actor: Actor, context: AuditContext, scope: Scope) -> str:
    if scope.decision is None:
        return f"The buyer's rules were checked{checked_for(scope)}. {DECISION_NOT_RECORDED}"
    outcome = VERDICT_OUTCOMES[scope.decision.verdict]
    return f"The buyer's rules were checked for {scope.option_label}: {outcome}{_fixed_rules(scope)}"


def order_placed_by_agent(actor: Actor, context: AuditContext, scope: Scope) -> str:
    """ "Within its authority" is said only under a recorded AUTO decision. Raises `ValueError` for any other."""
    if not placed_within_authority(scope):
        return (
            f"The agent placed {scope.order_label} without human approval{_what(scope)}. "
            f"{DECISION_BEHIND_NOT_RECORDED}{recorded_note(context)}"
        )
    return (
        f"The agent placed {scope.order_label} within its authority, without human approval{_what(scope)}."
        f"{recorded_note(context)}"
    )


def approval_requested(actor: Actor, context: AuditContext, scope: Scope) -> str:
    what = f" ({option_text(scope.option)})" if scope.option else ""
    return (
        f"The agent could not place {scope.order_label} alone under the buyer's rules. "
        f"The order{what} was sent to {HUMAN_AT_BUYER} for approval.{_fixed_rules(scope)}"
    )


def approval_decided(actor: Actor, context: AuditContext, scope: Scope) -> str:
    who = capital(HUMAN_AT_BUYER)
    decided = context.approval_decision
    if decided is None:
        return f"{who} decided on {scope.order_label}."
    if decided.decision is DecisionKind.REJECT:
        return f"{who} rejected {scope.order_label}."
    change = option_change(context)
    if change is None:
        return f"{who} approved {scope.order_label}."
    described = f" ({option_text(change.chosen)})" if change.chosen else ""
    return (
        f"{who} approved {scope.order_label} and chose another option of the same offer: "
        f"{change.chosen_id}{described}."
    )


def order_confirmed(actor: Actor, context: AuditContext, scope: Scope) -> str:
    by = confirmed_by(context)
    if by is PlacedBy.AGENT:
        return confirmed_text(context, scope, BY_THE_AGENT)
    if by is PlacedBy.HUMAN_APPROVAL:
        return confirmed_text(context, scope, f"with approval by {HUMAN_AT_BUYER}")
    return confirmed_text(context, scope, None)


def order_rejected(actor: Actor, context: AuditContext, scope: Scope) -> str:
    return f"{capital(scope.order_label)} was rejected by {HUMAN_AT_BUYER}. {NOTHING_ORDERED}"


def order_expired(actor: Actor, context: AuditContext, scope: Scope) -> str:
    return (
        f"{capital(scope.order_label)} expired while it waited for approval by {HUMAN_AT_BUYER}. {NOTHING_ORDERED}"
    )


def order_blocked(actor: Actor, context: AuditContext, scope: Scope) -> str:
    return (
        f"The buyer's rules blocked the order of {scope.option_of_offer_label}. {NOTHING_ORDERED}"
        f"{_fixed_rules(scope)}"
    )


def authorisation_refused(actor: Actor, context: AuditContext, scope: Scope) -> str:
    if actor.kind is ActorKind.AGENT:
        return agent_refused(scope)
    who = capital(HUMAN_AT_BUYER) if actor.kind is ActorKind.HUMAN else actor_text(actor)
    return f"{who} was refused on {scope.approval_label}: this caller may not decide it."


def evidence_attached(actor: Actor, context: AuditContext, scope: Scope) -> str:
    product = f" for product {label(context.evidence.product_id)}" if context.evidence else ""
    return (
        f"Evidence from outside Valio Aimo's data was attached to an approval{product}. "
        "It changes no status and no verdict."
    )


SUPPLIER_SENTENCES: dict[AuditEventType, SentenceBuilder] = {
    AuditEventType.REQUEST_RECEIVED: request_received,
    AuditEventType.REQUEST_PARSED: request_parsed,
    AuditEventType.LOOKUP_PERFORMED: lookup_performed,
    AuditEventType.OFFER_CREATED: offer_created,
    AuditEventType.POLICY_EVALUATED: policy_evaluated,
    AuditEventType.ORDER_PLACED_BY_AGENT: order_placed_by_agent,
    AuditEventType.APPROVAL_REQUESTED: approval_requested,
    AuditEventType.APPROVAL_DECIDED: approval_decided,
    AuditEventType.ORDER_CONFIRMED: order_confirmed,
    AuditEventType.ORDER_REJECTED: order_rejected,
    AuditEventType.ORDER_EXPIRED: order_expired,
    AuditEventType.ORDER_BLOCKED: order_blocked,
    AuditEventType.ORDER_NOT_PLACED: order_not_placed,
    AuditEventType.AUTHORISATION_REFUSED: authorisation_refused,
    AuditEventType.EVIDENCE_ATTACHED: evidence_attached,
}


def supplier_sentence(event_type: AuditEventType, actor: Actor, context: AuditContext, scope: Scope) -> str:
    return SUPPLIER_SENTENCES[event_type](actor, context, scope)
