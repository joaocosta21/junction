"""Valio Aimo's sentence for each event type: what was asked of its data, what was offered and ordered, who
the agent was, and how the order was decided (SPEC section 9; package S4 after Valio's answers of 14 Nov).

Every rule that fired is named with its reason and outcome, and the products considered and left out are
listed (`tta.audit.supplier_decisions`). No sentence here reads a limit value, an allergen exclusion, an
approver's name or id, or a note: a rule's own sentence is never quoted, because it can carry a limit or an
allergen, and a person is named by role only.

As for the buyer, a sentence states only what its context holds and says what is not recorded.
"""

from __future__ import annotations

from tta.audit.phrases import NOTHING_ORDERED, actor_text, capital, joined, label, option_text, request_text
from tta.audit.readers import ROLE_SEPARATOR, supplier_role
from tta.audit.scope import (
    Scope,
    approvals_given,
    confirmed_by,
    distinct_rule_ids,
    option_change,
    placed_within_authority,
    rejection,
    rules_with,
)
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
from tta.audit.standing_sentences import supplier_standing_order_created, supplier_standing_order_renewed
from tta.audit.supplier_decisions import buyers_roles, decision_explained, rules_applied
from tta.contracts.audit import Actor, ActorKind, AuditContext, AuditEventType
from tta.contracts.common import DecisionKind, PlacedBy, Verdict

VERDICT_OUTCOMES = {
    Verdict.AUTO: "the agent may place this order within its authority.",
    Verdict.APPROVAL: "{who} must approve this order.",
    Verdict.BLOCK: "this order cannot be placed.",
}


def _what(scope: Scope) -> str:
    return f": {option_text(scope.option)}" if scope.option else ""


def _acting_human(actor: Actor) -> str:
    """The human who acted, by the roles the gateway knows: never by name or id."""
    role = supplier_role(actor.role) if actor.kind is ActorKind.HUMAN else None
    return buyers_roles(role.split(ROLE_SEPARATOR) if role else ())


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
    decision = scope.decision
    if decision is None:
        return f"The buyer's rules were checked{checked_for(scope)}. {DECISION_NOT_RECORDED}"
    outcome = VERDICT_OUTCOMES[decision.verdict].format(who=buyers_roles(decision.required_roles))
    return f"The buyer's rules were checked for {scope.option_label}: {outcome}{decision_explained(decision)}"


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
    approval, decision = context.approval, scope.decision
    roles = approval.required_roles if approval else decision.required_roles if decision else ()
    what = f" ({option_text(scope.option)})" if scope.option else ""
    return (
        f"The agent could not place {scope.order_label} alone under the buyer's rules. "
        f"The order{what} was sent to {buyers_roles(roles)} for approval."
        f"{rules_applied(rules_with(decision, Verdict.APPROVAL))}"
    )


def _accepted(scope: Scope) -> str:
    accepted = distinct_rule_ids(rules_with(scope.decision, Verdict.APPROVAL))
    if not accepted:
        return ""
    ids = joined(label(rule_id) for rule_id in accepted)
    return f" This approval accepts {'rule' if len(accepted) == 1 else 'rules'} {ids}."


def approval_decided(actor: Actor, context: AuditContext, scope: Scope) -> str:
    decided = context.approval_decision
    if decided is None:
        return f"{capital(_acting_human(actor))} decided on {scope.order_label}."
    who = capital(buyers_roles(decided.roles))
    if decided.decision is DecisionKind.REJECT:
        return f"{who} rejected {scope.order_label}."
    change = option_change(context)
    chose = ""
    if change is not None:
        described = f" ({option_text(change.chosen)})" if change.chosen else ""
        instead = f" instead of {label(change.previous_id)}" if change.previous_id else ""
        chose = f" and chose another option of the same offer: {label(change.chosen_id)}{described}{instead}"
    missing = context.approval.roles_missing if context.approval else ()
    still = f" The order still needs approval by {buyers_roles(missing)}." if missing else ""
    return f"{who} approved {scope.order_label}{chose}.{_accepted(scope)}{still}"


def order_confirmed(actor: Actor, context: AuditContext, scope: Scope) -> str:
    by = confirmed_by(context)
    if by is PlacedBy.AGENT:
        return confirmed_text(context, scope, BY_THE_AGENT)
    if by is PlacedBy.HUMAN_APPROVAL:
        roles = [role for entry in approvals_given(context) for role in entry.roles]
        return confirmed_text(context, scope, f"with approval by {buyers_roles(roles)}")
    return confirmed_text(context, scope, None)


def order_rejected(actor: Actor, context: AuditContext, scope: Scope) -> str:
    decided = rejection(context)
    who = buyers_roles(decided.roles) if decided is not None else _acting_human(actor)
    return f"{capital(scope.order_label)} was rejected by {who}. {NOTHING_ORDERED}"


def order_expired(actor: Actor, context: AuditContext, scope: Scope) -> str:
    missing = context.approval.roles_missing if context.approval else ()
    return (
        f"{capital(scope.order_label)} expired while it waited for approval by {buyers_roles(missing)}. "
        f"{NOTHING_ORDERED}"
    )


def order_blocked(actor: Actor, context: AuditContext, scope: Scope) -> str:
    return (
        f"The buyer's rules blocked the order of {scope.option_of_offer_label}. {NOTHING_ORDERED}"
        f"{rules_applied(rules_with(scope.decision, Verdict.BLOCK))}"
    )


def authorisation_refused(actor: Actor, context: AuditContext, scope: Scope) -> str:
    if actor.kind is ActorKind.AGENT:
        return agent_refused(scope)
    who = capital(_acting_human(actor)) if actor.kind is ActorKind.HUMAN else actor_text(actor)
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
    AuditEventType.STANDING_ORDER_CREATED: supplier_standing_order_created,
    AuditEventType.STANDING_ORDER_RENEWED: supplier_standing_order_renewed,
}


def supplier_sentence(event_type: AuditEventType, actor: Actor, context: AuditContext, scope: Scope) -> str:
    return SUPPLIER_SENTENCES[event_type](actor, context, scope)
