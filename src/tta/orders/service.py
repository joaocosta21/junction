"""The order book: placing an order, deciding an approval, reading both (SPEC section 8).

Scores on the 30% end-to-end flow (the order and approval half), on the 20% "what the agent can decide alone,
what needs human sign-off, and how decisions are logged", and on Core 2 and Core 3.

    request ─► re-check ─► policy ─► AUTO      ─► ORDERED (placed by the agent)
                                  ├─ APPROVAL ─► PENDING_APPROVAL ─► approve ─► re-check ─► ORDERED
                                  │                              ├─ reject ─► REJECTED
                                  │                              └─ "order by" passes ─► EXPIRED
                                  └─ BLOCK    ─► typed error, an audit event, no order

`ORDERED` means recorded in this order book: the mock has no order endpoint. The service decides nothing
itself: the verdict is the policy engine's. Every change of status is written with its audit event in one unit
of work (`outcomes.py`): both are stored, or neither.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from tta.contracts.common import ApprovalStatus, ApproverRole, DecisionKind, Identity, OrderStatus, Verdict
from tta.contracts.errors import InvalidRequest, NotAuthorised, NotFound, OfferExpired, TtaError
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.order import Approval, DecisionRequest, Evidence, Order
from tta.contracts.policy import BuyerProfile, PolicyDecision
from tta.contracts.ports import AuditSink, Clock, OfferRevalidator, PolicyEngine, Store
from tta.orders import access, records, wording
from tta.orders.checking import Attempt, OrderTimeChecker
from tta.orders.outcomes import OutcomeWriter
from tta.orders.records import OrderTimeCheck
from tta.orders.spend import COMMITTED_STATUSES, day_committed_net_eur

# An Idempotency-Key is stored and compared as sent, so its form is bounded: 1 to 100 characters of letters,
# digits, ".", "_", ":" and "-". A UUID fits.
IDEMPOTENCY_KEY_FORM = re.compile(r"[A-Za-z0-9._:-]{1,100}")


class EvidenceFinder(Protocol):
    """Finds evidence outside Valio Aimo's data for the human who decides an approval (task S2, `tta.evidence`).
    It answers a `found=False` evidence with its reason rather than raise when a lookup fails."""

    def for_approval(self, option: OfferOption, decision: PolicyDecision) -> tuple[Evidence, ...]: ...


@dataclass(frozen=True)
class _Asked:
    """What one call of `place_order` asks for."""

    offer_id: str
    option_id: str
    identity: Identity
    idempotency_key: str


@dataclass(frozen=True)
class _Checked:
    """An offer as the book held it when its option passed the order-time check, before anything is written."""

    offer: Offer
    attempt: Attempt
    check: OrderTimeCheck


def _asks_the_same(decision: PolicyDecision, other: PolicyDecision) -> bool:
    """Two decisions with the same verdict, the same rules fired and the same roles asked for."""
    return (decision.verdict, decision.rule_ids, decision.required_roles) == (
        other.verdict, other.rule_ids, other.required_roles
    )


class OrderBookService:
    """Implements the `OrderService` port over the `Store`, `PolicyEngine`, `OfferRevalidator`, `AuditSink`
    and `Clock` ports. The clock is the data clock (server time, pinned in replay): it dates orders, decides
    expiry and bounds the day's spend. The audit sink arrives built and stamps its events itself.
    """

    def __init__(
        self, *, store: Store, policy: PolicyEngine, revalidator: OfferRevalidator, audit: AuditSink, clock: Clock,
        evidence: EvidenceFinder | None = None,
    ) -> None:
        self._store = store
        self._policy = policy
        self._clock = clock
        self._evidence = evidence  # None: no approval carries web evidence
        self._checker = OrderTimeChecker(store, policy, revalidator, audit, clock)
        self._write = OutcomeWriter(store, audit)
        # One writer at a time in this process, and every record is read again inside the lock, so two callers
        # cannot erase each other's change or both pass a limit. The lock is held across the supplier call and
        # protects one process only; the store's `atomic()` keeps what is written consistent beyond that.
        # It is not held while the web is asked for evidence: see `place_order`.
        self._lock = threading.Lock()

    # --- placing an order -----------------------------------------------------------------------------

    def place_order(self, offer_id: str, option_id: str, identity: Identity, idempotency_key: str) -> Order:
        """Raises `OfferStale`, `OfferExpired`, `PolicyBlocked`, `NotAuthorised`, `NotFound`, `InvalidRequest`."""
        if not identity.is_agent:
            raise NotAuthorised(wording.ONLY_AN_AGENT_ORDERS)
        if IDEMPOTENCY_KEY_FORM.fullmatch(idempotency_key) is None:
            raise InvalidRequest(wording.KEY_NOT_VALID if idempotency_key.strip() else wording.KEY_REQUIRED)
        asked = _Asked(offer_id, option_id, identity, idempotency_key)
        with self._lock:
            checked = self._checked_for_placing(asked)
            if isinstance(checked, Order):
                return checked
            if self._evidence is None or checked.check.decision.verdict is Verdict.AUTO:
                return self._record(asked, checked, ())
        # The web is asked with the lock released: a lookup can take up to 40 seconds, and the book's reads and
        # decisions do not wait for it. No outside call sits inside a store transaction either.
        evidence = self._evidence.for_approval(checked.check.option, checked.check.decision)
        with self._lock:
            return self._place_after_lookup(asked, checked, evidence)

    def _checked_for_placing(self, asked: _Asked) -> Order | _Checked:
        """The order this key already placed, or the offer as the book holds it now with its order-time check.
        Called with the lock held. Raises as `place_order` does."""
        first = self._first_order(asked.idempotency_key, asked.identity, asked.offer_id, asked.option_id)
        if first is not None:
            return first
        offer, attempt = self._attempt(asked)
        return _Checked(offer, attempt, self._checker.check(attempt))

    def _attempt(self, asked: _Asked) -> tuple[Offer, Attempt]:
        """The caller's offer, free to be ordered, and who orders which option of it under which profile."""
        offer, option = self._offered(asked.offer_id, asked.option_id, asked.identity)
        self._require_no_order_yet(offer)
        profile = self._policy.get_profile(offer.profile_id)
        return offer, Attempt(access.actor_of(asked.identity), profile, offer.offer_id, option)

    def _place_after_lookup(self, asked: _Asked, before: _Checked, evidence: tuple[Evidence, ...]) -> Order:
        """Write the order once the evidence is in, with the lock held again. Everything the first check rested
        on is read again: the key (another request may have used it meanwhile), the offer, that it has no order
        yet, the profile, the "order by" time, the day's spend and the standing order's history. When any of them
        changed, the order-time check is run again, and the order is written on that check. The evidence is kept
        when the new check asks for the same rules; otherwise it is looked up for the new decision, this once with
        the lock held, so that an approval never carries evidence sought for another decision."""
        first = self._first_order(asked.idempotency_key, asked.identity, asked.offer_id, asked.option_id)
        if first is not None:
            return first
        offer, attempt = self._attempt(asked)
        unchanged = (offer, attempt) == (before.offer, before.attempt)
        if unchanged and self._checker.still_holds(attempt, before.check):
            return self._record(asked, before, evidence)
        again = _Checked(offer, attempt, self._checker.check(attempt))
        if again.check.decision.verdict is Verdict.AUTO:
            return self._record(asked, again, ())
        if not _asks_the_same(again.check.decision, before.check.decision):
            evidence = self._evidence.for_approval(again.check.option, again.check.decision)
        return self._record(asked, again, evidence)

    def _record(self, asked: _Asked, checked: _Checked, evidence: tuple[Evidence, ...]) -> Order:
        """Write the order the check allows: placed by the agent alone, or waiting for a person with its approval."""
        offer, check, agent = checked.offer, checked.check, checked.attempt.actor
        order_id, now = records.new_order_id(), self._clock.now()
        if check.decision.verdict is Verdict.AUTO:
            order = records.placed_by_agent(order_id, offer, check, asked.identity, asked.idempotency_key, now)
            self._write.placed_alone(order, check, agent)
            return order
        order, approval = records.awaiting_approval(
            order_id, offer, check, asked.identity, asked.idempotency_key, now, evidence=evidence
        )
        self._write.sent_to_a_human(order, approval, check, agent)
        return order

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
        """The caller's own buyer's offer and its option. Another buyer's offer is answered like one nobody issued."""
        offer = self._store.get_offer(offer_id)
        if offer is None or access.is_of_another_buyer(identity, offer.profile_id):
            raise NotFound(wording.NO_SUCH_OFFER)
        option = offer.option(option_id)
        if option is None:
            raise NotFound(wording.NO_SUCH_OPTION.format(offer_id=offer.offer_id))
        return offer, option

    def _require_no_order_yet(self, offer: Offer) -> None:
        """An offer answers one request: while an order of it waits or is ORDERED, no second order is placed on
        it, whatever the option or the key. After a rejection or an expiry the offer can be ordered again."""
        committed = self._store.list_orders(profile_id=offer.profile_id, statuses=COMMITTED_STATUSES)
        for order in committed:
            if order.offer_id != offer.offer_id:
                continue
            standing = self._current(order)  # a waiting order past its time expires here and frees the offer
            if standing.status in COMMITTED_STATUSES:
                raise InvalidRequest(
                    wording.offer_already_ordered(standing), offer_id=offer.offer_id, order_id=standing.order_id
                )

    # --- deciding an approval -------------------------------------------------------------------------

    def decide(self, approval_id: str, identity: Identity, decision: DecisionRequest) -> Order:
        """Raises `NotAuthorised` (with an audit event), `NotFound` (with one when no approval of the caller's
        own buyer has this id), `InvalidRequest`, `OfferExpired`, `OfferStale`, `PolicyBlocked`."""
        with self._lock:
            approval = self._store.get_approval(approval_id)
            if approval is not None and access.is_of_another_buyer(identity, approval.profile_id):
                approval = None  # another buyer's approval is treated like one nobody issued, from here on
            reason = access.why_not_an_approver(identity)
            if reason is not None:
                raise self._refused(identity, approval, NotAuthorised(reason))
            if approval is None:
                raise self._refused(identity, None, NotFound(wording.NO_SUCH_APPROVAL))
            profile = self._policy.get_profile(approval.profile_id)
            roles = access.roles_that_count(identity, profile)
            if not roles:
                not_listed = wording.APPROVER_NOT_LISTED.format(profile_id=profile.display_name)
                raise self._refused(identity, approval, NotAuthorised(not_listed))
            order = self._still_waiting(approval)
            if decision.decision is DecisionKind.REJECT:
                return self._reject(order, approval, identity, roles, decision)
            return self._approve(order, approval, profile, identity, roles, decision)

    def _refused(self, identity: Identity, approval: Approval | None, error: TtaError) -> TtaError:
        """Record the attempt, then hand back the error. With no approval of the caller's own buyer, the attempt
        is filed under the caller's own buyer only, and the id it sent is not written down: the trail holds no
        text a refused caller chose, and no buyer reads another buyer's attempts."""
        facts = {} if identity.is_agent else {"reason": error.detail}
        self._write.refused(access.actor_of(identity), approval, identity.profile_id, facts)
        return error

    def _still_waiting(self, approval: Approval) -> Order:
        """The order of this approval, still open for a decision; otherwise the typed error. An order past its
        time is marked EXPIRED here, with its event, before the error is raised."""
        order = self._current(self._order_of(approval))
        if order.status is OrderStatus.EXPIRED:
            deadline = wording.deadline_of(order, approval)
            raise OfferExpired(
                wording.order_by_passed(order, deadline), order_id=order.order_id, offer_id=order.offer_id,
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
        """A rejection asks the supplier nothing, so it is checked against the roles the approval still waits for."""
        if not set(roles) & set(approval.roles_missing):
            refusal = NotAuthorised(wording.role_not_missing(approval.roles_missing, roles))
            raise self._refused(approver, approval, refusal)
        if request.option_id is not None:
            raise InvalidRequest(wording.REJECTION_CHOOSES_NO_OPTION)
        now = self._clock.now()
        entry = records.decision_entry(approver, roles, request, None, now)
        rejected, closed = records.rejected(order, approval, entry, now)
        self._write.rejected(order, rejected, closed, entry, access.actor_of(approver))
        return rejected

    def _approve(
        self, order: Order, approval: Approval, profile: BuyerProfile, approver: Identity,
        roles: tuple[ApproverRole, ...], request: DecisionRequest,
    ) -> Order:
        """One human approves the proposed option or another option of the same offer. The option is checked
        again at order time first: BLOCK still blocks, and the roles are those the policy asks for now. Only
        then is the approver held against the roles that decision still needs."""
        offer = self._offer_of(order)
        option = self._chosen(order, offer, request.option_id)
        attempt = Attempt(access.actor_of(approver), profile, order.offer_id, option, order)
        check = records.signed_by_a_named_role(self._checked(attempt), approval, roles)
        needed = records.roles_still_needed(approval, check)
        if needed and not set(roles) & set(needed):
            raise self._refused(approver, approval, NotAuthorised(wording.role_not_missing(needed, roles)))
        now = self._clock.now()
        other_option = check.option.option_id != approval.option_id
        chosen_id = check.option.option_id if other_option else None
        entry = records.decision_entry(approver, roles, request, chosen_id, now)
        changed, signed = records.approved(order, approval, check, entry, now, offer.time_now)
        self._write.approved(order, changed, signed, entry, check, attempt.actor)
        return changed

    def _checked(self, attempt: Attempt) -> OrderTimeCheck:
        """The order-time check of a waiting order. When it finds the proposed option expired and the order's own
        time has passed by then (the supplier call takes time), the order is marked EXPIRED in this same call."""
        try:
            return self._checker.check(attempt)
        except OfferExpired:
            if attempt.order is not None and attempt.option.option_id == attempt.order.option_id:
                self._current(attempt.order)
            raise

    def _offer_of(self, order: Order) -> Offer:
        offer = self._store.get_offer(order.offer_id)
        if offer is None:
            raise NotFound(wording.OFFER_NOT_IN_STORE.format(order_id=order.order_id))
        return offer

    def _chosen(self, order: Order, offer: Offer, option_id: str | None) -> OfferOption:
        """The option proposed, or another option of the same offer when the approver names one."""
        if option_id is None or option_id == order.option_id:
            return order.option
        option = offer.option(option_id)
        if option is None:
            raise NotFound(wording.NO_SUCH_OPTION.format(offer_id=order.offer_id))
        return option

    # --- reading --------------------------------------------------------------------------------------

    def get_order(self, order_id: str, identity: Identity) -> Order:
        """Another buyer's order is answered like one nobody issued: `not-found` for both."""
        access.require_buyer_side(identity)
        with self._lock:
            order = self._store.get_order(order_id)
            if order is None or access.is_of_another_buyer(identity, order.profile_id):
                raise NotFound(wording.NO_SUCH_ORDER)
            return self._current(order)

    def get_approval(self, approval_id: str, identity: Identity) -> Approval:
        """Another buyer's approval is answered like one nobody issued: `not-found` for both."""
        access.require_buyer_side(identity)
        with self._lock:
            approval = self._store.get_approval(approval_id)
            if approval is None or access.is_of_another_buyer(identity, approval.profile_id):
                raise NotFound(wording.NO_SUCH_APPROVAL)
            current = self._current(self._order_of(approval))
            # Past its time, the order expired just now and the approval with it: read the approval again.
            return self._store.get_approval(approval_id) if current.status is OrderStatus.EXPIRED else approval

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
        """The order as it stands now. A waiting order past its time becomes EXPIRED here, with its approval and
        one audit event, in one unit of work. Called with the lock held."""
        if order.status is not OrderStatus.PENDING_APPROVAL:
            return order
        now = self._clock.now()
        approval = self._store.get_approval(order.approval_id) if order.approval_id is not None else None
        if not records.is_overdue(order, approval, now):
            return order
        expired, closed = records.expired(order, approval, now)
        self._write.expired(expired, closed)
        return expired
