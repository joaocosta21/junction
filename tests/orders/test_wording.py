"""The status sentence of an order, as the shop page prints it (`tta.orders.wording`).

P8 M2 and F2: an order only rule F-10 holds back reads "Prepared: confirm to order", then "Confirmed by <name>".
An order another rule sends to a person keeps naming the rule that asked.

A person who decided is named by name; a role follows only where the caller passes the profile of a buyer at which
more than one person can sign (`test_confirmation_names.py`). These call the wording with no profile.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tta.contracts.common import ApprovalStatus, ApproverRole, DecisionKind, Verdict
from tta.contracts.order import Approval, ApprovalDecision
from tta.contracts.policy import FiredRule, PolicyDecision
from tta.orders import wording
from tta.policy import RulePolicyEngine
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
        "Confirmed by Hanna Laine; still waiting for finance to confirm, by Sunday 15 November 2026 at 17:00 "
        "(UTC+02:00) (rule F-10: a person confirms every order)."
    )


def test_an_order_only_f10_held_back_reads_confirmed_by_the_person_who_signed() -> None:
    approval = _approval(_signed("Jussi Nieminen", ApproverRole.PURCHASING_MANAGER))

    assert wording.ordered_with_approval(approval, NET, _decision(HUMAN_APPROVAL)) == (
        "Confirmed by Jussi Nieminen: ordered for €402.00 net."
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
        "Ordered for €402.00 net with approval by Jussi Nieminen: rule P-01 asked for a human and was accepted."
    )


def test_an_order_placed_alone_says_why_it_was_allowed_and_names_the_buyer_not_its_profile_id(
    engine: RulePolicyEngine,
) -> None:
    ward = engine.get_profile("allergy-ward")

    sentence = wording.placed_alone(NET, ward, Decimal("830.00"))

    assert sentence == (
        "The agent placed this order alone for €402.00 net. That was allowed: ordering alone is switched on for City "
        "Hospital, Ward 4; the total of €402.00 is within the €500 limit per order; today's spend with this order "
        "is €830.00 of the €1,500 limit per day; every statement of the offer is confirmed; and no rule asked for a "
        "person."
    )
    assert "allergy-ward" not in sentence and not re.search(r"\b[FP]-\d\d\b", sentence)  # no id of any kind


def test_an_order_placed_alone_states_only_what_the_caller_knows() -> None:
    """A value the caller does not have leaves its clause out: it is never guessed."""
    assert wording.placed_alone(NET) == (
        "The agent placed this order alone for €402.00 net. That was allowed: every statement of the offer is "
        "confirmed; and no rule asked for a person."
    )
