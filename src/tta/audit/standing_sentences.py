"""The sentences of the two standing-order events (task STAND-1), for the buyer and for Valio Aimo.

What the context carries (`tta.standing.service` writes it):

    standing_order.created   request · facts: standing_order_id, standing_order_name, cadence_days, synthetic_renewals
    standing_order.renewed   order (when one was placed) · offer_id · facts: standing_order_id, standing_order_name,
                             drift_sentence, drift (the report), renewal_id

The buyer reads the drift found, in the words of the report the policy judged, and the outcome. The supplier reads
that a standing order was set up or renewed, the ids and every rule that fired by id, title and outcome (package
S4): neither the buyer's name for it nor the drift, whose sentence states the buyer's tolerance, a limit.
"""

from __future__ import annotations

from tta.audit.phrases import actor_text, count, ended, label, quoted, request_text, roles_text
from tta.audit.scope import Scope, only_confirmation_asked
from tta.audit.supplier_decisions import rules_applied
from tta.contracts.audit import Actor, ActorKind, AuditContext
from tta.contracts.common import OrderStatus, PlacedBy

STANDING_ORDER_FAMILY = "standing_order"  # the CloudEvents type family and the subject's kind
SYNTHETIC_NOTE = (
    "{count} made up for the demonstration, marked synthetic: the Valio Aimo mock has no order history."
)
NO_ORDER = " No order was placed."


def _fact(context: AuditContext, name: str) -> str | None:
    value = context.facts.get(name)
    return value if isinstance(value, str) and value.strip() else None


def _standing_label(context: AuditContext) -> str:
    standing_id = _fact(context, "standing_order_id")
    return f"standing order {label(standing_id)}" if standing_id else "a standing order"


def _named(context: AuditContext) -> str:
    name = _fact(context, "standing_order_name")
    return f", {quoted(name)}" if name else ""


def _cadence(context: AuditContext) -> str:
    days = context.facts.get("cadence_days")
    return f", renewed every {count(days, 'day')}" if type(days) is int else ""


def _synthetic(context: AuditContext) -> str:
    synthetic = context.facts.get("synthetic_renewals")
    if type(synthetic) is not int or synthetic <= 0:
        return ""
    renewals = count(synthetic, "past renewal")
    return " It starts with " + SYNTHETIC_NOTE.format(count=renewals)


def standing_order_created(actor: Actor, context: AuditContext, scope: Scope) -> str:
    what = f": {request_text(context.request, with_exclusions=True)}" if context.request is not None else ""
    named = f"{_standing_label(context)}{_named(context)}{_cadence(context)}"
    return f"{actor_text(actor)} set up {named}{what}.{_synthetic(context)}"


def _outcome(context: AuditContext) -> str:
    order = context.order
    if order is None:
        return NO_ORDER
    if order.status is OrderStatus.ORDERED and order.placed_by is PlacedBy.AGENT:
        return f" Order {order.order_id} was placed by the agent within its authority."
    if order.status is OrderStatus.PENDING_APPROVAL:
        roles = order.decision.required_roles if order.decision is not None else ()
        who = roles_text(roles) if roles else "a human"
        if only_confirmation_asked(order.decision):  # F-10 alone: prepared by the agent, a person confirms it
            return f" Order {order.order_id} is prepared and waits for {who} to confirm it."
        return f" Order {order.order_id} waits for approval by {who}."
    return f" Order {order.order_id} is {order.status.value.lower().replace('_', ' ')}."


def standing_order_renewed(actor: Actor, context: AuditContext, scope: Scope) -> str:
    drift = _fact(context, "drift_sentence")
    found = f" {ended(drift)}" if drift else ""
    offer = f" as offer {scope.offer_id}" if scope.offer_id else ""
    named = _named(context)
    renewed = f"{_standing_label(context)}{named}{',' if named and offer else ''}{offer}"
    return f"{actor_text(actor)} renewed {renewed}.{found}{_outcome(context)}"


def supplier_standing_order_created(actor: Actor, context: AuditContext, scope: Scope) -> str:
    who = "The buyer's agent" if actor.kind is ActorKind.AGENT else "The buyer"
    return f"{who} set up a standing order."


def supplier_standing_order_renewed(actor: Actor, context: AuditContext, scope: Scope) -> str:
    who = "The buyer's agent" if actor.kind is ActorKind.AGENT else "The buyer"
    offer = f" as offer {scope.offer_id}" if scope.offer_id else ""
    order = context.order
    placed = f" Order {order.order_id} is {order.status.value.lower().replace('_', ' ')}." if order else NO_ORDER
    rules = ""
    if scope.decision is not None:
        rules = rules_applied(scope.decision.fired, scope.own_dietitian, one_line=scope.has_one_line)
    return f"{who} renewed a standing order{offer}.{placed}{rules}"
