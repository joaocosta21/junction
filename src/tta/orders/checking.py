"""The check every order passes just before it is placed: a fresh look at price and availability, then the policy.

Scores on the 20% "autonomy and controls" and the 15% exceptions: an option that expired or changed since the
offer, or that the policy blocks, is refused with a typed error and an audit event, and changes nothing.
The verdict is the policy engine's; nothing here decides.
"""

from __future__ import annotations

from dataclasses import dataclass

from tta.contracts.audit import Actor, AuditContext, AuditEventType
from tta.contracts.availability import RevalidationResult
from tta.contracts.common import JsonDict, Verdict
from tta.contracts.errors import OfferExpired, OfferStale, PolicyBlocked, SupplierUnavailable, TtaError
from tta.contracts.offer import OfferOption
from tta.contracts.order import Order
from tta.contracts.policy import BuyerProfile, FiredRule, PolicyContext
from tta.contracts.ports import AuditSink, Clock, OfferRevalidator, PolicyEngine, Store
from tta.orders import wording
from tta.orders.records import OrderTimeCheck
from tta.orders.spend import day_committed_net_eur

# F-04 of src/tta/policy/rules.yaml: the option expired or changed before the order. Its facts say which.
STALE_RULE_ID = "F-04"
EXPIRY_FACTS = ("option.expired", "revalidation.expired")


@dataclass(frozen=True)
class Attempt:
    """Who tries to order which option, for which buyer; and the waiting order it would change, when there is one."""

    actor: Actor
    profile: BuyerProfile
    offer_id: str
    option: OfferOption
    order: Order | None = None  # set when an approver decides an order that already waits

    @property
    def ids(self) -> JsonDict:
        """Extension members of a problem response: what the caller needs to find the offer and the order again."""
        found = {"offer_id": self.offer_id, "option_id": self.option.option_id}
        return {**found, "order_id": self.order.order_id} if self.order is not None else found


class OrderTimeChecker:
    """Re-check, then policy with `at_order_time` set. Returns the check, or records why not and raises."""

    def __init__(
        self, store: Store, policy: PolicyEngine, revalidator: OfferRevalidator, audit: AuditSink, clock: Clock
    ) -> None:
        self._store = store
        self._policy = policy
        self._revalidator = revalidator
        self._audit = audit
        self._clock = clock

    def check(self, attempt: Attempt) -> OrderTimeCheck:
        """Raises `OfferStale`, `OfferExpired`, `PolicyBlocked` or `SupplierUnavailable`, each after one audit event."""
        revalidation = self._fresh_look(attempt)
        committed = day_committed_net_eur(
            self._store, self._clock, attempt.profile.profile_id,
            excluding_order_id=attempt.order.order_id if attempt.order is not None else None,
        )
        context = PolicyContext(
            now=self._clock.now(), day_committed_net_eur=committed, at_order_time=True, revalidation=revalidation
        )
        decision = self._policy.evaluate(attempt.option, attempt.profile, context)
        check = OrderTimeCheck(
            option=attempt.option.model_copy(update={"decision": decision}), decision=decision,
            revalidation=revalidation,
        )
        if decision.verdict is Verdict.BLOCK:
            raise self._refusal(attempt, check)
        return check

    def _fresh_look(self, attempt: Attempt) -> RevalidationResult:
        try:
            return self._revalidator.revalidate(attempt.option)
        except SupplierUnavailable:
            # No policy ran, so the event carries no decision: the offer's own verdict is not this attempt's.
            self._record(AuditEventType.ORDER_NOT_PLACED, attempt, None)
            raise

    def _refusal(self, attempt: Attempt, check: OrderTimeCheck) -> TtaError:
        """The typed error for a BLOCK: stale or expired when F-04 fired (SPEC section 8), otherwise blocked."""
        stale = next((rule for rule in check.decision.fired if rule.rule_id == STALE_RULE_ID), None)
        if stale is None:
            self._record(AuditEventType.ORDER_BLOCKED, attempt, check)
            return _blocked(attempt, check)
        self._record(AuditEventType.ORDER_NOT_PLACED, attempt, check)
        return _no_longer_as_offered(attempt, check, stale)

    def _record(self, event_type: AuditEventType, attempt: Attempt, check: OrderTimeCheck | None) -> None:
        order = attempt.order
        self._audit.record(event_type, attempt.actor, AuditContext(
            profile_id=attempt.profile.profile_id,
            offer_id=attempt.offer_id,
            order_id=order.order_id if order is not None else None,
            approval_id=order.approval_id if order is not None else None,
            option=check.option if check is not None else attempt.option.model_copy(update={"decision": None}),
            decision=check.decision if check is not None else None,
            revalidation=check.revalidation if check is not None else None,
        ))


def _blocked(attempt: Attempt, check: OrderTimeCheck) -> PolicyBlocked:
    blocking = [rule for rule in check.decision.fired if rule.verdict is Verdict.BLOCK]
    return PolicyBlocked(
        check.decision.sentence, **attempt.ids,
        rule_ids=list(dict.fromkeys(rule.rule_id for rule in blocking)),
        reasons=[rule.sentence for rule in blocking],
    )


def _no_longer_as_offered(attempt: Attempt, check: OrderTimeCheck, stale: FiredRule) -> TtaError:
    detail = wording.no_longer_as_offered(stale.sentence)
    if any(stale.facts.get(fact) is True for fact in EXPIRY_FACTS):
        deadline = attempt.option.valid_until
        return OfferExpired(detail, **attempt.ids, valid_until=deadline.isoformat() if deadline else None)
    changes = [change.model_dump(mode="json") for change in check.revalidation.changes]
    return OfferStale(detail, **attempt.ids, changes=changes)
