"""What an event is about: the ids, the option and the policy decision, read from the objects in its context."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from tta.contracts.audit import AuditContext
from tta.contracts.common import DecisionKind, Verdict
from tta.contracts.offer import OfferOption
from tta.contracts.order import ApprovalDecision
from tta.contracts.policy import FiredRule, PolicyDecision


@dataclass(frozen=True)
class Scope:
    profile_id: str | None
    offer_id: str | None
    order_id: str | None
    approval_id: str | None
    option: OfferOption | None
    decision: PolicyDecision | None

    @property
    def order_label(self) -> str:
        return f"order {self.order_id}" if self.order_id else "the order"

    @property
    def approval_label(self) -> str:
        return f"approval {self.approval_id}" if self.approval_id else "an approval"

    @property
    def option_label(self) -> str:
        return f"option {self.option.option_id}" if self.option else "the option"

    @property
    def option_of_offer_label(self) -> str:
        option = f"option {self.option.option_id}" if self.option else "an option"
        return f"{option} of offer {self.offer_id}" if self.offer_id else option


@dataclass(frozen=True)
class OptionChange:
    """An approver picked another option of the same offer."""

    chosen_id: str
    chosen: OfferOption | None
    previous_id: str | None


def _first(*values: str | None) -> str | None:
    return next((value for value in values if value), None)


def resolve(context: AuditContext) -> Scope:
    """An id given on the context wins; otherwise it is read from the order, approval, offer or decision."""
    order, approval, offer = context.order, context.approval, context.offer
    option = context.option or (order.option if order else None)
    decision = (
        context.decision
        or (context.option.decision if context.option else None)
        or (order.decision if order else None)
    )
    return Scope(
        profile_id=_first(
            context.profile_id,
            context.profile.profile_id if context.profile else None,
            order.profile_id if order else None,
            offer.profile_id if offer else None,
            approval.profile_id if approval else None,
            decision.profile_id if decision else None,
        ),
        offer_id=_first(
            context.offer_id,
            offer.offer_id if offer else None,
            order.offer_id if order else None,
            approval.offer_id if approval else None,
        ),
        order_id=_first(
            context.order_id, order.order_id if order else None, approval.order_id if approval else None
        ),
        approval_id=_first(
            context.approval_id, approval.approval_id if approval else None, order.approval_id if order else None
        ),
        option=option,
        decision=decision,
    )


def rules_with(decision: PolicyDecision | None, verdict: Verdict) -> tuple[FiredRule, ...]:
    """Every firing with this verdict. A rule about a line fires once for each line it holds on."""
    if decision is None:
        return ()
    return tuple(rule for rule in decision.fired if rule.verdict is verdict)


def distinct_rule_ids(rules: Iterable[FiredRule]) -> tuple[str, ...]:
    """Each rule id once, in the order the rules fired."""
    return tuple(dict.fromkeys(rule.rule_id for rule in rules))


def option_change(context: AuditContext) -> OptionChange | None:
    """Set when the approver's decision names an option: the contract fills `option_id` only for another option."""
    decided = context.approval_decision
    if decided is None or decided.option_id is None:
        return None
    chosen_id = decided.option_id
    candidates = (
        context.option,
        context.order.option if context.order else None,
        context.offer.option(chosen_id) if context.offer else None,
    )
    chosen = next((option for option in candidates if option is not None and option.option_id == chosen_id), None)
    previous = (
        context.order.option_id if context.order else None,
        context.approval.option_id if context.approval else None,
    )
    previous_id = next((value for value in previous if value and value != chosen_id), None)
    return OptionChange(chosen_id=chosen_id, chosen=chosen, previous_id=previous_id)


def rejection(context: AuditContext) -> ApprovalDecision | None:
    """The decision that rejected the order: the one on the context, or the last rejection on the approval."""
    decided = context.approval_decision
    if decided is not None and decided.decision is DecisionKind.REJECT:
        return decided
    recorded = context.approval.decisions if context.approval else ()
    return next((entry for entry in reversed(recorded) if entry.decision is DecisionKind.REJECT), None)


def approvals_given(context: AuditContext) -> tuple[ApprovalDecision, ...]:
    recorded = context.approval.decisions if context.approval else ()
    return tuple(entry for entry in recorded if entry.decision is DecisionKind.APPROVE)
