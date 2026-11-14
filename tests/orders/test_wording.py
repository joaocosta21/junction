"""The status sentence of an order, as the shop page prints it (`tta.orders.wording`).

P8 M2 and F2: an order only rule F-10 holds back reads "Prepared: confirm to order", then "Confirmed by <name>".
An order another rule sends to a person keeps naming the rule that asked.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tta.contracts.common import ApprovalStatus, ApproverRole, DecisionKind, Verdict
from tta.contracts.order import Approval, ApprovalDecision
from tta.contracts.policy import FiredRule, PolicyDecision
from tta.orders import wording
from tta.policy.human_approval import HUMAN_APPROVAL

NOW = datetime(2026, 11, 14, 2, 52, tzinfo=timezone(timedelta(hours=2)))
ORDER_BY = datetime(2026, 11, 15, 17, 0, tzinfo=timezone(timedelta(hours=2)))
NET = Decimal("402.00")
SPEND_LIMIT = FiredRule(
    rule_id="P-01", title="The order is above the spend limit per order", fixed=False, verdict=Verdict.APPROVAL,
    approver_role=ApproverRole.PURCHASING_MANAGER, sentence="The total is above the limit.",
)


ONE_ROLE = (ApproverRole.PURCHASING_MANAGER,)


def _decision(*fired: FiredRule, roles: tuple[ApproverRole, ...] = ONE_ROLE) -> PolicyDecision:
    return PolicyDecision(
        verdict=Verdict.APPROVAL, fired=fired, required_roles=roles, policy_hash="sha256:" + "0" * 64,
        profile_id="allergy-ward", evaluated_at=NOW, sentence="A decision built for a wording test.",
    )


def _signed(name: str, role: ApproverRole) -> ApprovalDecision:
    return ApprovalDecision(
        approver_id=f"human:{name.lower()}", approver_name=name, roles=(role,), decision=DecisionKind.APPROVE,
        decided_at=NOW,
    )


def _approval(
    *decisions: ApprovalDecision, roles: tuple[ApproverRole, ...] = ONE_ROLE,
    valid_until: datetime | None = ORDER_BY,
) -> Approval:
    return Approval(
        approval_id="apr_1", order_id="ord_1", offer_id="off_1", option_id="opt_1", profile_id="allergy-ward",
        status=ApprovalStatus.PENDING, required_roles=roles, decisions=decisions, created_at=NOW,
        valid_until=valid_until,
    )


def test_an_order_only_f10_holds_back_is_prepared_and_says_who_confirms_by_when() -> None:
    assert wording.waiting(_approval(), _decision(HUMAN_APPROVAL)) == (
        "Prepared: confirm to order. Waiting for the purchasing manager to confirm, by Sunday 15 November 2026 at "
        "17:00 (UTC+02:00) (rule F-10: a person confirms every order)."
    )


def test_a_prepared_order_without_an_order_by_time_names_no_time() -> None:
    assert wording.waiting(_approval(valid_until=None), _decision(HUMAN_APPROVAL)) == (
        "Prepared: confirm to order. Waiting for the purchasing manager to confirm (rule F-10: a person confirms every "
        "order)."
    )


def test_a_prepared_order_one_of_two_named_roles_confirmed_says_who_did_and_who_is_awaited() -> None:
    both = (ApproverRole.PURCHASING_MANAGER, ApproverRole.FINANCE)
    approval = _approval(_signed("Hanna Laine", ApproverRole.PURCHASING_MANAGER), roles=both)

    assert wording.waiting(approval, _decision(HUMAN_APPROVAL, roles=both)) == (
        "Confirmed by Hanna Laine (purchasing manager); still waiting for finance to confirm, by Sunday 15 November "
        "2026 at 17:00 (UTC+02:00) (rule F-10: a person confirms every order)."
    )


def test_an_order_only_f10_held_back_reads_confirmed_by_the_person_who_signed() -> None:
    approval = _approval(_signed("Jussi Nieminen", ApproverRole.PURCHASING_MANAGER))

    assert wording.ordered_with_approval(approval, NET, _decision(HUMAN_APPROVAL)) == (
        "Confirmed by Jussi Nieminen (purchasing manager): ordered for €402.00 net."
    )


def test_an_order_another_rule_sent_to_a_person_still_names_the_rule() -> None:
    decision = _decision(SPEND_LIMIT)

    assert wording.waiting(_approval(), decision) == (
        "Waiting for approval by the purchasing manager, to be decided by Sunday 15 November 2026 at 17:00 "
        "(UTC+02:00): rule P-01 asks for a human."
    )
    assert wording.ordered_with_approval(
        _approval(_signed("Jussi Nieminen", ApproverRole.PURCHASING_MANAGER)), NET, decision
    ) == (
        "Ordered for €402.00 net with approval by Jussi Nieminen (purchasing manager): rule P-01 asked for a human "
        "and was accepted."
    )


def test_an_order_placed_alone_names_no_profile_id() -> None:
    sentence = wording.placed_alone(NET, "my-kitchen")

    assert sentence == (
        "The agent placed this order alone for €402.00 net: no rule asked for a human and every statement of the "
        "offer is confirmed."
    )
