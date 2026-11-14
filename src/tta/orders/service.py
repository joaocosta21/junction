"""The order book: placing an order, deciding an approval, reading both (SPEC section 8).

Scores on the 30% end-to-end flow (the order and approval half), on the 20% "what the agent can decide alone,
what needs human sign-off, and how decisions are logged", and on Core 2 and Core 3.

    request ─► re-check ─► policy ─► AUTO      ─► ORDERED (placed by the agent)
                                  ├─ APPROVAL ─► PENDING_APPROVAL ─► approve ─► re-check ─► ORDERED
                                  │                              ├─ reject ─► REJECTED
                                  │                              └─ "order by" passes ─► EXPIRED
                                  └─ BLOCK    ─► typed error, an audit event, no order

`ORDERED` means recorded in this order book: the mock has no order endpoint. The service decides nothing
itself: the verdict is the policy engine's, and every change of status writes its audit event in the same call.
"""

from __future__ import annotations

import threading
from decimal import Decimal

from tta.contracts.audit import SYSTEM_ACTOR, AuditContext, AuditEventType
from tta.contracts.common import ApprovalStatus, ApproverRole, DecisionKind, Identity, OrderStatus, Verdict
from tta.contracts.errors import InvalidRequest, NotAuthorised, NotFound, OfferExpired
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.order import Approval, DecisionRequest, Order
from tta.contracts.ports import AuditSink, Clock, OfferRevalidator, PolicyEngine, Store
from tta.orders import access, records, wording
from tta.orders.checking import Attempt, OrderTimeChecker
from tta.orders.records import OrderTimeCheck
from tta.orders.spend import day_committed_net_eur


class OrderBookService:
    """Implements the `OrderService` port over the `Store`, `PolicyEngine`, `OfferRevalidator`, `AuditSink`
    and `Clock` ports. The clock is the data clock (server time, pinned in replay): it dates orders, decides
    expiry and bounds the day's spend. The audit sink arrives built and stamps its events itself.
    """

    def __init__(
        self, *, store: Store, policy: PolicyEngine, revalidator: OfferRevalidator, audit: AuditSink, clock: Clock
    ) -> None:
        self._store = store
        self._policy = policy
        self._audit = audit
        self._clock = clock
        self._checker = OrderTimeChecker(store, policy, revalidator, audit, clock)
        # The store saves a whole object by id with no version check. One writer at a time, and every record is
        # read again inside the lock, so two callers cannot erase each other's change or both pass a limit.
        self._lock = threading.Lock()

    # --- placing an order -----------------------------------------------------------------------------

    def place_order(self, offer_id: str, option_id: str, identity: Identity, idempotency_key: str) -> Order:
        """Raises `OfferStale`, `OfferExpired`, `PolicyBlocked`, `NotAuthorised`, `NotFound`, `InvalidRequest`."""
        if not identity.is_agent:
            raise NotAuthorised(wording.ONLY_AN_AGENT_ORDERS)
        if not idempotency_key.strip():
            raise InvalidRequest(wording.KEY_REQUIRED)
        with self._lock:
            first = self._first_order(idempotency_key, identity, offer_id, option_id)
            if first is not None:
                return first
            offer, option = self._offered(offer_id, option_id, identity)
            profile = self._policy.get_profile(offer.profile_id)
            check = self._checker.check(Attempt(access.actor_of(identity), profile, offer.offer_id, option))
            # The id first bound to the key wins, so a retry after a crash completes the same order.
            order_id = self._store.remember_idempotency_key(idempotency_key, identity.id, records.new_order_id())
            if check.decision.verdict is Verdict.AUTO:
                return self._place_alone(order_id, offer, check, identity, idempotency_key)
            return self._send_to_a_human(order_id, offer, check, identity, idempotency_key)

    def _first_order(self, key: str, identity: Identity, offer_id: str, option_id: str) -> Order | None:
        """The order this agent's key already placed. A key reused for another offer or option is refused."""
        order_id = self._store.order_id_for_key(key, identity.id)
        order = self._store.get_order(order_id) if order_id is not None else None
        if order is None:
            return None
        if (order.offer_id, order.extra.get(records.REQUESTED_OPTION_KEY)) != (offer_id, option_id):
            raise InvalidRequest(wording.KEY_USED_FOR_ANOTHER_ORDER.format(order_id=order.order_id))
        return self._current(order)

    def _offered(self, offer_id: str, option_id: str, identity: Identity) -> tuple[Offer, OfferOption]:
        offer = self._store.get_offer(offer_id)
        if offer is None:
            raise NotFound(wording.NO_SUCH_OFFER)
        if offer.profile_id != identity.profile_id:
            raise NotAuthorised(wording.OFFER_OF_ANOTHER_BUYER)
        option = offer.option(option_id)
        if option is None:
            raise NotFound(wording.NO_SUCH_OPTION.format(offer_id=offer.offer_id))
        return offer, option

    def _place_alone(self, order_id: str, offer: Offer, check: OrderTimeCheck, agent: Identity, key: str) -> Order:
        order = records.placed_by_agent(order_id, offer, check, agent, key, self._clock.now())
        self._store.save_order(order)
        self._audit.record(
            AuditEventType.ORDER_PLACED_BY_AGENT, access.actor_of(agent),
            AuditContext(order=order, decision=order.decision, revalidation=check.revalidation),
        )
        return order

    def _send_to_a_human(
        self, order_id: str, offer: Offer, check: OrderTimeCheck, agent: Identity, key: str
    ) -> Order:
        order, approval = records.awaiting_approval(order_id, offer, check, agent, key, self._clock.now())
        self._store.save_order(order)  # the order first: an approval never points at an order that is not there
        self._store.save_approval(approval)
        self._audit.record(
            AuditEventType.APPROVAL_REQUESTED, access.actor_of(agent),
            AuditContext(order=order, approval=approval, decision=order.decision, revalidation=check.revalidation),
        )
        return order

    # --- deciding an approval -------------------------------------------------------------------------

    def decide(self, approval_id: str, identity: Identity, decision: DecisionRequest) -> Order:
        """Raises `NotAuthorised` (with an audit event), `NotFound`, `InvalidRequest`, `OfferExpired`,
        `OfferStale`, `PolicyBlocked`."""
        with self._lock:
            approval = self._store.get_approval(approval_id)
            reason = access.why_not_an_approver(identity)
            if reason is not None:
                raise self._refused(identity, approval, reason)
            if approval is None:
                raise NotFound(wording.NO_SUCH_APPROVAL)
            profile = self._policy.get_profile(approval.profile_id)
            reason = access.why_not_for_this_buyer(identity, profile)
            if reason is not None:
                raise self._refused(identity, approval, reason)
            order = self._still_waiting(approval)
            roles = access.roles_that_count(identity, profile)
            if not set(roles) & set(approval.roles_missing):
                raise self._refused(identity, approval, wording.role_not_missing(approval, roles))
            if decision.decision is DecisionKind.REJECT:
                return self._reject(order, approval, identity, roles, decision)
            option = self._chosen(order, decision.option_id)
            attempt = Attempt(access.actor_of(identity), profile, order.offer_id, option, order)
            return self._approve(attempt, approval, identity, roles, decision)

    def _refused(self, identity: Identity, approval: Approval | None, reason: str) -> NotAuthorised:
        """Record the attempt, then hand back the error. The id a caller sent for an approval nobody issued is
        not written down: the trail holds no text a refused caller chose."""
        facts = {} if identity.is_agent else {"reason": reason}
        context = (
            AuditContext(approval=approval, facts=facts) if approval is not None
            else AuditContext(profile_id=identity.profile_id, facts=facts)
        )
        self._audit.record(AuditEventType.AUTHORISATION_REFUSED, access.actor_of(identity), context)
        return NotAuthorised(reason)

    def _still_waiting(self, approval: Approval) -> Order:
        """The order of this approval, still open for a decision; otherwise the typed error."""
        order = self._current(self._order_of(approval))
        if order.status is OrderStatus.EXPIRED:
            deadline = order.option.valid_until
            raise OfferExpired(
                wording.order_by_passed(order), order_id=order.order_id, offer_id=order.offer_id,
                option_id=order.option_id, valid_until=deadline.isoformat() if deadline else None,
            )
        if order.status is not OrderStatus.PENDING_APPROVAL:
            raise InvalidRequest(wording.already_decided(approval, order))
        return order

    def _order_of(self, approval: Approval) -> Order:
        order = self._store.get_order(approval.order_id)
        if order is None:
            raise NotFound(wording.ORDER_NOT_IN_BOOK.format(approval_id=approval.approval_id))
        return order

    def _reject(
        self, order: Order, approval: Approval, approver: Identity, roles: tuple[ApproverRole, ...],
        request: DecisionRequest,
    ) -> Order:
        if request.option_id is not None:
            raise InvalidRequest(wording.REJECTION_CHOOSES_NO_OPTION)
        now = self._clock.now()
        entry = records.decision_entry(approver, roles, request, None, now)
        rejected, closed = records.rejected(order, approval, entry, now)
        self._store.save_order(rejected)
        self._store.save_approval(closed)
        self._audit.record(
            AuditEventType.APPROVAL_DECIDED, access.actor_of(approver),
            AuditContext(order=order, approval=closed, approval_decision=entry, decision=order.decision),
        )
        self._audit.record(
            AuditEventType.ORDER_REJECTED, SYSTEM_ACTOR,
            AuditContext(order=rejected, approval=closed, approval_decision=entry, decision=rejected.decision),
        )
        return rejected

    def _approve(
        self, attempt: Attempt, approval: Approval, approver: Identity, roles: tuple[ApproverRole, ...],
        request: DecisionRequest,
    ) -> Order:
        """One human approves the proposed option or another option of the same offer. Either way the option is
        checked again at order time: BLOCK still blocks, and the roles are those the policy asks for now."""
        order = attempt.order
        check = self._checker.check(attempt)
        now = self._clock.now()
        other_option = check.option.option_id != approval.option_id
        chosen_id = check.option.option_id if other_option else None
        entry = records.decision_entry(approver, roles, request, chosen_id, now)
        changed, signed = records.approved(order, approval, check, entry, now)
        self._store.save_order(changed)
        self._store.save_approval(signed)
        # The order as the human saw it, the approval as it is now: the sentence says what was chosen instead
        # of what, and which roles are still missing.
        self._audit.record(AuditEventType.APPROVAL_DECIDED, attempt.actor, AuditContext(
            order=order, approval=signed, approval_decision=entry, decision=check.decision,
            option=check.option if other_option else None,
        ))
        if changed.status is OrderStatus.ORDERED:
            self._audit.record(AuditEventType.ORDER_CONFIRMED, SYSTEM_ACTOR, AuditContext(
                order=changed, approval=signed, decision=check.decision, revalidation=check.revalidation,
            ))
        return changed

    def _chosen(self, order: Order, option_id: str | None) -> OfferOption:
        """The option proposed, or another option of the same offer when the approver names one."""
        if option_id is None or option_id == order.option_id:
            return order.option
        offer = self._store.get_offer(order.offer_id)
        option = offer.option(option_id) if offer is not None else None
        if option is None:
            raise NotFound(wording.NO_SUCH_OPTION.format(offer_id=order.offer_id))
        return option

    # --- reading --------------------------------------------------------------------------------------

    def get_order(self, order_id: str, identity: Identity) -> Order:
        access.require_buyer_side(identity)
        with self._lock:
            order = self._store.get_order(order_id)
            if order is None:
                raise NotFound(wording.NO_SUCH_ORDER)
            access.require_same_buyer(identity, order.profile_id)
            return self._current(order)

    def get_approval(self, approval_id: str, identity: Identity) -> Approval:
        access.require_buyer_side(identity)
        with self._lock:
            approval = self._approval(approval_id)
            access.require_same_buyer(identity, approval.profile_id)
            self._current(self._order_of(approval))  # past its time, the order expires here and the approval with it
            return self._approval(approval_id)

    def _approval(self, approval_id: str) -> Approval:
        approval = self._store.get_approval(approval_id)
        if approval is None:
            raise NotFound(wording.NO_SUCH_APPROVAL)
        return approval

    def list_approvals(self, identity: Identity, status: ApprovalStatus | None = None) -> tuple[Approval, ...]:
        """The approvals of the caller's buyer, oldest first. Pending ones past their time expire here first."""
        access.require_buyer_side(identity)
        with self._lock:
            waiting = self._store.list_orders(
                profile_id=identity.profile_id, statuses=(OrderStatus.PENDING_APPROVAL,)
            )
            for order in waiting:
                self._current(order)
            return self._store.list_approvals(profile_id=identity.profile_id, status=status)

    def day_committed_net_eur(self, profile_id: str) -> Decimal:
        """Net total of the profile's ORDERED and PENDING_APPROVAL orders on the clock's current date."""
        return day_committed_net_eur(self._store, self._clock, profile_id)

    # --- expiry ---------------------------------------------------------------------------------------

    def _current(self, order: Order) -> Order:
        """The order as it stands now. A pending order past its "order by" time becomes EXPIRED here, with its
        approval and one audit event. Called with the lock held."""
        now = self._clock.now()
        if not records.is_past_order_by(order, now):
            return order
        approval = self._store.get_approval(order.approval_id) if order.approval_id is not None else None
        expired, closed = records.expired(order, approval, now)
        self._store.save_order(expired)
        if closed is not None:
            self._store.save_approval(closed)
        self._audit.record(
            AuditEventType.ORDER_EXPIRED, SYSTEM_ACTOR,
            AuditContext(order=expired, approval=closed, decision=expired.decision),
        )
        return expired

