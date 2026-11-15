"""What an event is about: the ids, the option and the policy decision, read from the objects in its context."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from tta.contracts.audit import AuditContext
from tta.contracts.common import ApproverRole, DecisionKind, PlacedBy, Verdict
from tta.contracts.offer import OfferOption
from tta.contracts.order import ApprovalDecision
from tta.contracts.policy import BuyerProfile, FiredRule, PolicyDecision
from tta.policy.human_approval import HUMAN_APPROVAL, has_own


@dataclass(frozen=True)
class Scope:
    profile_id: str | None
    offer_id: str | None
    order_id: str | None
    approval_id: str | None
    option: OfferOption | None
    decision: PolicyDecision | None
    # The buyer's name as its profile gives it (`BuyerProfile.display_name`), for the buyer's sentences only. It
    # is not a field of the event: None when neither the context nor the policy engine of the trail has it.
    profile_name: str | None = None
    # Whether the buyer has a dietitian of its own: somebody holds that role who is not the person who orders (the
    # ward, the school). False where one person holds every role (the hotel, the bakery). For Valio Aimo's
    # sentences only, which name a role of a second person and no other; None when the profile is not known.
    own_dietitian: bool | None = None
    # The buyer profile itself, for the buyer's sentences: who really decides a role's question at this buyer, and
    # whether more than one person can sign there (`tta.policy.human_approval`). Not a field of the event either.
    profile: BuyerProfile | None = None

    @property
    def has_one_line(self) -> bool:
        """Whether the option the event is about holds one product. That product is then the order's line, which
        other steps of the trail name: a sentence for Valio Aimo cannot claim it is hidden."""
        return self.option is not None and len(self.option.lines) == 1

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


def has_own_dietitian(profile: BuyerProfile) -> bool:
    """Whether somebody holds the dietitian's role who does not hold the purchasing manager's: the policy's own
    answer (`tta.policy.human_approval.has_own`), so the log and the rules read one buyer alike."""
    return has_own(profile, ApproverRole.DIETITIAN)


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
        profile_name=context.profile.display_name if context.profile else None,
        own_dietitian=has_own_dietitian(context.profile) if context.profile else None,
        profile=context.profile,
    )


def rules_with(decision: PolicyDecision | None, verdict: Verdict) -> tuple[FiredRule, ...]:
    """Every firing with this verdict. A rule about a line fires once for each line it holds on."""
    if decision is None:
        return ()
    return tuple(rule for rule in decision.fired if rule.verdict is verdict)


def distinct_rule_ids(rules: Iterable[FiredRule]) -> tuple[str, ...]:
    """Each rule id once, in the order the rules fired."""
    return tuple(dict.fromkeys(rule.rule_id for rule in rules))


def only_confirmation_asked(decision: PolicyDecision | None) -> bool:
    """True when F-10 is the only rule that asked for a person: the order was prepared and a person confirmed
    it, which is not the approval of an exception (`tta.orders.wording` says the same of the order)."""
    return distinct_rule_ids(rules_with(decision, Verdict.APPROVAL)) == (HUMAN_APPROVAL.rule_id,)


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


def placed_within_authority(scope: Scope) -> bool:
    """True when a recorded decision lets the agent act alone; False when no decision is recorded.

    A decision that asks for a human or blocks cannot stand behind an order the agent placed alone:
    recording one is a fault in the caller, and no event is written.
    """
    decision = scope.decision
    if decision is None:
        return False
    if decision.verdict is not Verdict.AUTO:
        raise ValueError(
            f"An order.placed_by_agent event was given a policy decision whose verdict is {decision.verdict.value}: "
            "the agent places an order alone only under the verdict AUTO. No event was recorded."
        )
    return True


def confirmed_by(context: AuditContext) -> PlacedBy | None:
    """Who the context shows confirmed the order: approvals given, else what the order record says, else nothing."""
    if approvals_given(context):
        return PlacedBy.HUMAN_APPROVAL
    return context.order.placed_by if context.order else None
