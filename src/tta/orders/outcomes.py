"""Every outcome of the order book as one unit of work (SPEC section 8).

Scores on the 20% "how decisions are logged and auditable": an order, its approval, its idempotency key and its
audit events are stored together or not at all (`Store.atomic()`). When any write of an outcome fails, the audit
event included, nothing of that outcome is stored and the failure reaches the caller, who can send the same
request again.
"""

from __future__ import annotations

from tta.contracts.audit import SYSTEM_ACTOR, Actor, AuditContext, AuditEventType
from tta.contracts.common import JsonDict, OrderStatus
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.order import Approval, ApprovalDecision, Order
from tta.contracts.ports import AuditSink, Store
from tta.orders import wording
from tta.orders.records import OrderTimeCheck


class OutcomeWriter:
    """Writes each change of the order book inside one `atomic()` block of the store."""

    def __init__(self, store: Store, audit: AuditSink) -> None:
        self._store = store
        self._audit = audit

    def placed_alone(self, order: Order, check: OrderTimeCheck, agent: Actor) -> None:
        with self._store.atomic():
            self._bind_key(order)
            self._store.save_order(order)
            self._audit.record(
                AuditEventType.ORDER_PLACED_BY_AGENT, agent,
                AuditContext(order=order, decision=order.decision, revalidation=check.revalidation),
            )

    def sent_to_a_human(self, order: Order, approval: Approval, check: OrderTimeCheck, agent: Actor) -> None:
        with self._store.atomic():
            self._bind_key(order)
            self._store.save_order(order)
            self._store.save_approval(approval)
            self._audit.record(AuditEventType.APPROVAL_REQUESTED, agent, AuditContext(
                order=order, approval=approval, decision=order.decision, revalidation=check.revalidation,
            ))
            for found in (item for item in approval.evidence if item.found):  # task S2: its link and hash
                self._audit.record(
                    AuditEventType.EVIDENCE_ATTACHED, SYSTEM_ACTOR, AuditContext(approval=approval, evidence=found)
                )

    def approved(
        self, before: Order, changed: Order, signed: Approval, entry: ApprovalDecision, check: OrderTimeCheck,
        approver: Actor,
    ) -> None:
        """One human's approval, and the confirmation when it completed the order."""
        with self._store.atomic():
            self._store.save_order(changed)
            self._store.save_approval(signed)
            # The order as the human saw it, the approval as it is now: the sentence says what was chosen
            # instead of what, and which roles are still missing.
            self._audit.record(AuditEventType.APPROVAL_DECIDED, approver, AuditContext(
                order=before, approval=signed, approval_decision=entry, decision=check.decision,
                option=check.option if entry.option_id is not None else None,
            ))
            if changed.status is OrderStatus.ORDERED:
                self._audit.record(AuditEventType.ORDER_CONFIRMED, SYSTEM_ACTOR, AuditContext(
                    order=changed, approval=signed, decision=check.decision, revalidation=check.revalidation,
                ))

    def rejected(
        self, before: Order, rejected: Order, closed: Approval, entry: ApprovalDecision, approver: Actor
    ) -> None:
        with self._store.atomic():
            self._store.save_order(rejected)
            self._store.save_approval(closed)
            self._audit.record(AuditEventType.APPROVAL_DECIDED, approver, AuditContext(
                order=before, approval=closed, approval_decision=entry, decision=before.decision,
            ))
            self._audit.record(AuditEventType.ORDER_REJECTED, SYSTEM_ACTOR, AuditContext(
                order=rejected, approval=closed, approval_decision=entry, decision=rejected.decision,
            ))

    def expired(self, expired: Order, closed: Approval | None) -> None:
        with self._store.atomic():
            self._store.save_order(expired)
            if closed is not None:
                self._store.save_approval(closed)
            self._audit.record(
                AuditEventType.ORDER_EXPIRED, SYSTEM_ACTOR,
                AuditContext(order=expired, approval=closed, decision=expired.decision),
            )

    def refused(self, caller: Actor, approval: Approval | None, own_profile_id: str | None, facts: JsonDict) -> None:
        """An attempt to decide that was refused. With an approval it is filed with that approval; without one
        only under the caller's own buyer, and the id the caller sent is not written down."""
        context = (
            AuditContext(approval=approval, facts=facts) if approval is not None
            else AuditContext(profile_id=own_profile_id, facts=facts)
        )
        with self._store.atomic():
            self._audit.record(AuditEventType.AUTHORISATION_REFUSED, caller, context)

    def _bind_key(self, order: Order) -> None:
        """Bind the order's Idempotency-Key to it, in the scope of its agent. A key that another writer bound
        to another order since this request looked it up ends the block: nothing of this order is stored."""
        bound = self._store.remember_idempotency_key(order.idempotency_key, order.agent_id, order.order_id)
        if bound != order.order_id:
            raise SupplierUnavailable(wording.KEY_BOUND_MEANWHILE)
