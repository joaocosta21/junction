"""Valio Aimo's sentence for each event type: what was asked of its data, what was offered and ordered, who
the agent was, and how the order was decided (SPEC section 9; package S4 after Valio's answers of 14 Nov).

Every rule that fired is named with its reason and outcome, and the products considered and left out are
listed (`tta.audit.supplier_decisions`). No sentence here reads a limit value, an allergen exclusion, an
approver's name or id, or a note: a rule's own sentence is never quoted, because it can carry a limit or an
allergen. A person is never named: one person confirms, so whoever orders is "a person of the buyer" whatever
roles her token holds, and a role is said only of a second person, the dietitian of the ward and of the school
(`who_is_asked`, `who_signed`).

As for the buyer, a sentence states only what its context holds and says what is not recorded.
"""

from __future__ import annotations

from tta.audit.phrases import NOTHING_ORDERED, actor_text, capital, joined, label, option_text, request_text
from tta.audit.readers import (
    EVIDENCE_PRODUCT_NOT_SHOWN,
    ROLE_SEPARATOR,
    SUPPLIER_READER,
    is_supplier_reader,
    supplier_role,
)
from tta.audit.scope import (
    Scope,
    approvals_given,
    confirmed_by,
    distinct_rule_ids,
    only_confirmation_asked,
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
from tta.audit.settings_sentences import supplier_settings_changed
from tta.audit.standing_sentences import supplier_standing_order_created, supplier_standing_order_renewed
from tta.audit.suggestion_sentences import supplier_suggestion_accepted, supplier_suggestions_shown
from tta.audit.supplier_decisions import (
    BUYERS_DIETITIAN,
    PERSON_OF_BUYER,
    decision_explained,
    rules_applied,
    who_is_asked,
    who_signed,
)
from tta.contracts.audit import Actor, ActorKind, AuditContext, AuditEventType
from tta.contracts.common import ApproverRole, DecisionKind, PlacedBy, Verdict
from tta.contracts.order import ApprovalDecision

VERDICT_OUTCOMES = {
    Verdict.AUTO: "the agent may place this order within its authority.",
    Verdict.APPROVAL: "{who} must approve this order.",
    Verdict.BLOCK: "this order cannot be placed.",
}


def _what(scope: Scope) -> str:
    return f": {option_text(scope.option)}" if scope.option else ""


def _acting_human(actor: Actor, scope: Scope) -> str:
    """The human who acted, by the roles the gateway knows: never by name or id. Valio Aimo's own token is
    not a person at the buyer and is named as what it is."""
    if is_supplier_reader(actor):
        return SUPPLIER_READER
    role = supplier_role(actor.role) if actor.kind is ActorKind.HUMAN else None
    return who_signed(role.split(ROLE_SEPARATOR) if role else (), scope.own_dietitian)


def _signer(decided: ApprovalDecision, context: AuditContext, scope: Scope) -> str:
    """Who signed one decision. A signature for the dietitian's role alone is the dietitian's, unless the same
    person signed this approval for another role as well: the shop page signs role by role under the name of the
    customer's person (`tta.ui.shop_api`), and one name is one person. The name itself is never said."""
    said = who_signed(decided.roles, scope.own_dietitian)
    if said != BUYERS_DIETITIAN or context.approval is None:
        return said
    also_as_buyer = any(
        entry.approver_name == decided.approver_name and set(entry.roles) != {ApproverRole.DIETITIAN}
        for entry in context.approval.decisions
    )
    return PERSON_OF_BUYER if also_as_buyer else said


def _signers(context: AuditContext, scope: Scope) -> str:
    """Everybody who approved, each person once: "a person of the buyer and the buyer's dietitian"."""
    roles_by_name: dict[str, tuple[ApproverRole, ...]] = {}
    for entry in approvals_given(context):
        held = roles_by_name.get(entry.approver_name, ())
        roles_by_name = {**roles_by_name, entry.approver_name: (*held, *entry.roles)}
    said = dict.fromkeys(who_signed(roles, scope.own_dietitian) for roles in roles_by_name.values())
    return joined(sorted(said, key=lambda who: who == BUYERS_DIETITIAN))


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
    asked = who_is_asked(decision.required_roles, scope.own_dietitian)
    outcome = VERDICT_OUTCOMES[decision.verdict].format(who=asked)
    explained = decision_explained(decision, scope.own_dietitian, one_line=scope.has_one_line)
    return f"The buyer's rules were checked for {scope.option_label}: {outcome}{explained}"


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
        f"The order{what} was sent to {who_is_asked(roles, scope.own_dietitian)} for approval."
        f"{rules_applied(rules_with(decision, Verdict.APPROVAL), scope.own_dietitian, one_line=scope.has_one_line)}"
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
        return f"{capital(_acting_human(actor, scope))} decided on {scope.order_label}."
    who = capital(_signer(decided, context, scope))
    if decided.decision is DecisionKind.REJECT:
        return f"{who} rejected {scope.order_label}."
    change = option_change(context)
    chose = ""
    if change is not None:
        described = f" ({option_text(change.chosen)})" if change.chosen else ""
        instead = f" instead of {label(change.previous_id)}" if change.previous_id else ""
        chose = f" and chose another option of the same offer: {label(change.chosen_id)}{described}{instead}"
    missing = context.approval.roles_missing if context.approval else ()
    asked = who_is_asked(missing, scope.own_dietitian)
    still = f" The order still needs approval by {asked}." if missing else ""
    return f"{who} approved {scope.order_label}{chose}.{_accepted(scope)}{still}"


def order_confirmed(actor: Actor, context: AuditContext, scope: Scope) -> str:
    by = confirmed_by(context)
    if by is PlacedBy.AGENT:
        return confirmed_text(context, scope, BY_THE_AGENT)
    if by is PlacedBy.HUMAN_APPROVAL:
        how = "confirmed" if only_confirmation_asked(scope.decision) else "with approval"
        return confirmed_text(context, scope, f"{how} by {_signers(context, scope) or who_signed(())}")
    return confirmed_text(context, scope, None)


def order_rejected(actor: Actor, context: AuditContext, scope: Scope) -> str:
    decided = rejection(context)
    who = _signer(decided, context, scope) if decided is not None else _acting_human(actor, scope)
    return f"{capital(scope.order_label)} was rejected by {who}. {NOTHING_ORDERED}"


def order_expired(actor: Actor, context: AuditContext, scope: Scope) -> str:
    missing = context.approval.roles_missing if context.approval else ()
    return (
        f"{capital(scope.order_label)} expired while it waited for approval by "
        f"{who_is_asked(missing, scope.own_dietitian)}. "
        f"{NOTHING_ORDERED}"
    )


def order_blocked(actor: Actor, context: AuditContext, scope: Scope) -> str:
    return (
        f"The buyer's rules blocked the order of {scope.option_of_offer_label}. {NOTHING_ORDERED}"
        f"{rules_applied(rules_with(scope.decision, Verdict.BLOCK), scope.own_dietitian, one_line=scope.has_one_line)}"
    )


def authorisation_refused(actor: Actor, context: AuditContext, scope: Scope) -> str:
    if actor.kind is ActorKind.AGENT:
        return agent_refused(scope)
    who = capital(_acting_human(actor, scope)) if actor.kind is ActorKind.HUMAN else actor_text(actor)
    return f"{who} was refused on {scope.approval_label}: this caller may not decide it."


def evidence_attached(actor: Actor, context: AuditContext, scope: Scope) -> str:
    # Evidence is attached for a product rule P-04 sent to a person: this step does not name that product to
    # Valio Aimo, as the rule's own line does not (`tta.audit.readers.MASKED_BY_RULE`).
    return f"Evidence from outside Valio Aimo's data was {EVIDENCE_PRODUCT_NOT_SHOWN} and no verdict."


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
    AuditEventType.SUGGESTIONS_SHOWN: supplier_suggestions_shown,
    AuditEventType.SUGGESTION_ACCEPTED: supplier_suggestion_accepted,
    AuditEventType.SETTINGS_CHANGED: supplier_settings_changed,
}


def supplier_sentence(event_type: AuditEventType, actor: Actor, context: AuditContext, scope: Scope) -> str:
    return SUPPLIER_SENTENCES[event_type](actor, context, scope)
