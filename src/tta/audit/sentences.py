"""The buyer's sentence for each event type of SPEC section 9: one template each, never written by a model.

Every sentence is for a person who was not there: it says who acted, on what, the numbers and the reason.
Rule sentences are quoted from the policy decision, so the audit trail and the policy cannot disagree.

A sentence states only what its context holds. Where the object a clause needs is absent, the clause is left
out and the sentence says what is not recorded; it never fills the gap with the usual case.
"""

from __future__ import annotations

from collections.abc import Callable

from tta.audit.phrases import (
    MAX_NAME_CHARACTERS,
    NOTHING_ORDERED,
    RECHECKED,
    RECORDED,
    actor_text,
    capital,
    count,
    coverage_text,
    ended,
    joined,
    label,
    moment,
    option_kind_text,
    option_text,
    person,
    plain,
    quoted,
    request_text,
    roles_text,
    rule_lines,
    source_text,
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
from tta.audit.standing_sentences import standing_order_created, standing_order_renewed
from tta.audit.supplier_decisions import left_out
from tta.contracts.audit import Actor, ActorKind, AuditContext, AuditEventType
from tta.contracts.common import DataSource, DecisionKind, PlacedBy, Verdict
from tta.contracts.offer import Offer
from tta.contracts.order import ApprovalDecision

SentenceBuilder = Callable[[Actor, AuditContext, Scope], str]

DECISION_NOT_RECORDED = "The decision is not recorded."
DECISION_BEHIND_NOT_RECORDED = "The policy decision behind it is not recorded."
HOW_CONFIRMED_NOT_RECORDED = "How it was confirmed is not recorded."
APPROVER_NOT_RECORDED = "Who approved is not recorded."
BY_THE_AGENT = "placed by the agent within its authority"


def _note(decided: ApprovalDecision | None) -> str:
    return f" Note: {quoted(decided.note)}" if decided is not None and decided.note else ""


def _what(scope: Scope) -> str:
    return f": {option_text(scope.option)}" if scope.option else ""


def recorded_note(context: AuditContext) -> str:
    """ "The order is recorded in the gateway's order book", said only of an order record the event carries."""
    return f" {RECORDED}" if context.order is not None else ""


def checked_for(scope: Scope) -> str:
    return f" for {scope.option_label}" if scope.option else ""


def buyer_name(scope: Scope) -> str | None:
    """Harbourside Hotel: the buyer by the name its profile gives it, read as data (a visitor may have typed
    it). "profile hotel-kitchen" when the name is not known; None when the event names no profile."""
    if scope.profile_name:
        return plain(scope.profile_name, MAX_NAME_CHARACTERS)
    return f"profile {scope.profile_id}" if scope.profile_id else None


def request_received(actor: Actor, context: AuditContext, scope: Scope) -> str:
    buyer = buyer_name(scope)
    profile = f" for {buyer}" if buyer else ""
    verb = "received" if actor.kind is ActorKind.SYSTEM else "sent"
    start = f"{actor_text(actor)} {verb} a request{profile}"
    text = context.facts.get("text")
    if isinstance(text, str) and text.strip():
        return f"{start}: {quoted(text)}."
    if context.request is not None:
        return f"{start}: {request_text(context.request, with_exclusions=True)}."
    return f"{start}."


def request_parsed(actor: Actor, context: AuditContext, scope: Scope) -> str:
    if context.request is None:
        return "The request was read into a typed request."
    return f"The request was read as: {request_text(context.request, with_exclusions=True)}."


def data_source(context: AuditContext) -> DataSource | None:
    if context.offer is not None:
        return context.offer.source
    stated = context.facts.get("source")
    return DataSource(stated) if stated in tuple(DataSource) else None


def lookup_performed(actor: Actor, context: AuditContext, scope: Scope) -> str:
    """The same for both readers: it is about Valio Aimo's data."""
    looked_up = context.facts.get("products_looked_up")
    if looked_up is None and context.offer is not None:
        looked_up = context.offer.candidates_considered
    products = f" of {count(looked_up, 'product')}" if type(looked_up) is int else ""
    return f"The gateway looked up price and availability{products} in {source_text(data_source(context))}."


def offer_text(offer: Offer, for_buyer: bool) -> str:
    """The supplier's version leaves out the notes, which can name an excluded allergen, and ends with the
    products considered and left out, by reason (`tta.audit.supplier_decisions.left_out`)."""
    start = f"The gateway built offer {offer.offer_id} from {source_text(offer.source)}: "
    candidates = count(offer.candidates_considered, "candidate")
    excluded = f", {count(len(offer.excluded), 'product')} excluded with a reason" if for_buyer else ""
    dropped = "" if for_buyer else left_out(offer)
    if not offer.options:
        notes = "".join(f" {ended(note)}" for note in offer.notes) if for_buyer else ""
        return f"{start}no option fits the request; {candidates}{excluded}.{notes}{dropped}"
    options = " ".join(
        f"Option {option.rank} ({option_kind_text(option, for_buyer)}): {option_text(option)}, "
        f"{coverage_text(option)}."
        for option in offer.options
    )
    return f"{start}{count(len(offer.options), 'option')} from {candidates}{excluded}. {options}{dropped}"


def offer_created(actor: Actor, context: AuditContext, scope: Scope) -> str:
    if context.offer is None:
        return f"The gateway built {f'offer {scope.offer_id}' if scope.offer_id else 'an offer'}."
    return offer_text(context.offer, for_buyer=True)


def policy_evaluated(actor: Actor, context: AuditContext, scope: Scope) -> str:
    """Which rules were checked on what, then the decision's own sentence: the engine wrote it from its template
    with the totals and limits it read, so it is quoted, not rebuilt."""
    decision = scope.decision
    if decision is None:
        return f"The rules were checked{checked_for(scope)}. {DECISION_NOT_RECORDED}"
    whose = buyer_name(scope) or f"profile {decision.profile_id}"
    checked = f"The rules of {whose} were checked for {scope.option_label}."
    return f"{checked} {ended(decision.sentence)}"


def order_placed_by_agent(actor: Actor, context: AuditContext, scope: Scope) -> str:
    """ "Within its authority" and "no rule asked for a human" are said only under a recorded AUTO decision.
    Raises `ValueError` for a decision with any other verdict."""
    if not placed_within_authority(scope):
        return (
            f"The agent placed {scope.order_label} alone{_what(scope)}. {DECISION_BEHIND_NOT_RECORDED}"
            f"{recorded_note(context)}"
        )
    buyer = buyer_name(scope)
    profile = f" under the rules of {buyer}" if buyer else ""
    return (
        f"The agent placed {scope.order_label} alone, within its authority{profile}{_what(scope)}. "
        f"No rule asked for a human.{recorded_note(context)}"
    )


def approval_requested(actor: Actor, context: AuditContext, scope: Scope) -> str:
    approval, decision = context.approval, scope.decision
    asking = rules_with(decision, Verdict.APPROVAL)
    why = "."
    if asking:
        rules = count(len(distinct_rule_ids(asking)), "rule asks", "rules ask")
        why = f", because {rules} for a human. {rule_lines(asking)}"
    roles = approval.required_roles if approval else decision.required_roles if decision else ()
    what = f" ({option_text(scope.option)})" if scope.option else ""
    deadline = f", to be decided by {moment(approval.valid_until)}" if approval and approval.valid_until else ""
    return (
        f"The agent could not place {scope.order_label} alone{why} "
        f"The order{what} was sent to {roles_text(roles) if roles else 'a human'}{deadline}."
    )


def _accepted(scope: Scope) -> str:
    accepted = distinct_rule_ids(rules_with(scope.decision, Verdict.APPROVAL))
    if not accepted:
        return ""
    return f" This approval accepts {'rule' if len(accepted) == 1 else 'rules'} {joined(accepted)}."


def approval_decided(actor: Actor, context: AuditContext, scope: Scope) -> str:
    decided = context.approval_decision
    if decided is None:
        return f"{actor_text(actor)} decided on {scope.order_label}."
    who = person(decided.approver_name, decided.roles)
    if decided.decision is DecisionKind.REJECT:
        return f"{who} rejected {scope.order_label}.{_note(decided)}"
    change = option_change(context)
    chose = ""
    if change is not None:
        described = f" ({option_text(change.chosen)})" if change.chosen else ""
        instead = f" instead of {change.previous_id}" if change.previous_id else ""
        chose = f" and chose another option of the same offer: {change.chosen_id}{described}{instead}"
    missing = context.approval.roles_missing if context.approval else ()
    still = f" The order still needs approval by {roles_text(missing)}." if missing else ""
    return f"{who} approved {scope.order_label}{chose}.{_accepted(scope)}{still}{_note(decided)}"


def confirmed_text(context: AuditContext, scope: Scope, how: str | None, not_recorded: str | None = None) -> str:
    """Order ord_1 is ordered, <how>: <what>. <what is not recorded> <the re-check> <the order book>.

    `how` is None when the context does not show how the order was confirmed; the sentence then says so.
    """
    manner = f", {how}" if how else ""
    gap = not_recorded if how else HOW_CONFIRMED_NOT_RECORDED
    missing = f" {gap}" if gap else ""
    checked = f" {RECHECKED}" if context.revalidation is not None and context.revalidation.ok else ""
    return f"{capital(scope.order_label)} is ordered{manner}{_what(scope)}.{missing}{checked}{recorded_note(context)}"


def order_confirmed(actor: Actor, context: AuditContext, scope: Scope) -> str:
    by = confirmed_by(context)
    if by is PlacedBy.AGENT:
        return confirmed_text(context, scope, BY_THE_AGENT)
    if by is None:
        return confirmed_text(context, scope, None)
    approvers = joined(person(entry.approver_name, entry.roles) for entry in approvals_given(context))
    # Under F-10 alone the agent prepared the order and a person confirmed it: no exception was approved.
    confirmed = only_confirmation_asked(scope.decision)
    if approvers:
        return confirmed_text(context, scope, f"{'confirmed' if confirmed else 'with approval'} by {approvers}")
    how = "confirmed by a human" if confirmed else "with human approval"
    return confirmed_text(context, scope, how, APPROVER_NOT_RECORDED)


def order_rejected(actor: Actor, context: AuditContext, scope: Scope) -> str:
    decided = rejection(context)
    if decided is not None:
        who = person(decided.approver_name, decided.roles)
    else:
        who = actor_text(actor) if actor.kind is ActorKind.HUMAN else "a human"
    return f"{capital(scope.order_label)} was rejected by {who}. {NOTHING_ORDERED}{_note(decided)}"


def order_expired(actor: Actor, context: AuditContext, scope: Scope) -> str:
    approval = context.approval
    missing = roles_text(approval.roles_missing) if approval and approval.roles_missing else "a human"
    deadline = (approval.valid_until if approval else None) or (scope.option.valid_until if scope.option else None)
    when = f" on {moment(deadline)}," if deadline else ""
    return (
        f"{capital(scope.order_label)} expired without a decision: the approval by {missing} was still missing"
        f"{when} when the offer stopped being valid. {NOTHING_ORDERED}"
    )


def order_blocked(actor: Actor, context: AuditContext, scope: Scope) -> str:
    buyer = buyer_name(scope)
    whose = f"The rules of {buyer}" if buyer else "The rules"
    blocking = rules_with(scope.decision, Verdict.BLOCK)
    rules = f" {rule_lines(blocking)}" if blocking else ""
    return (
        f"{whose} blocked the order of {scope.option_of_offer_label}: it cannot be placed, even with approval."
        f"{rules} {NOTHING_ORDERED}"
    )


def order_not_placed(actor: Actor, context: AuditContext, scope: Scope) -> str:
    """The same for both readers: it is about what Valio Aimo's data said at order time."""
    revalidation = context.revalidation
    if revalidation is None:
        reason = "the offer could not be confirmed against fresh price and availability."
    elif revalidation.expired:
        reason = (
            'the offer is no longer valid, because its "order by" time, a price validity or a cut-off has passed.'
        )
    else:
        changes = "".join(f" {ended(change.sentence)}" for change in revalidation.changes)
        reason = f"price or availability changed since the offer was made.{changes}"
    label = scope.option_of_offer_label
    return f"The order of {label} was not placed: {reason} The buyer's agent can ask for a fresh offer."


def agent_refused(scope: Scope) -> str:
    """The same for both readers: the agent's identity and its authority are visible to both."""
    return f"The agent tried to decide {scope.approval_label} and was refused: an agent cannot approve an order (F-06)."


def authorisation_refused(actor: Actor, context: AuditContext, scope: Scope) -> str:
    if actor.kind is ActorKind.AGENT:
        return agent_refused(scope)
    stated = context.facts.get("reason")
    reason = f" {ended(stated)}" if isinstance(stated, str) and stated.strip() else ""
    return f"{actor_text(actor)} was refused on {scope.approval_label}: this caller may not decide it.{reason}"


def evidence_attached(actor: Actor, context: AuditContext, scope: Scope) -> str:
    evidence = context.evidence
    found = f" for product {label(evidence.product_id)}: {ended(evidence.sentence)}" if evidence else "."
    return (
        f"Evidence from outside Valio Aimo's data was attached to {scope.approval_label}{found} "
        "It changes no status and no verdict."
    )


BUYER_SENTENCES: dict[AuditEventType, SentenceBuilder] = {
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
    AuditEventType.STANDING_ORDER_CREATED: standing_order_created,
    AuditEventType.STANDING_ORDER_RENEWED: standing_order_renewed,
}


def buyer_sentence(event_type: AuditEventType, actor: Actor, context: AuditContext, scope: Scope) -> str:
    return BUYER_SENTENCES[event_type](actor, context, scope)
