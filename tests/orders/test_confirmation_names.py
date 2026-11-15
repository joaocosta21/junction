"""The confirmation sentence names the person, not their roles (decision B61, after one-person confirmation B54).

"Confirmed by Demo approver Hanna (purchasing manager, finance and dietitian)" listed three roles of one person.
The hotel's and the bakery's person who orders holds every role, so the list is noise there: the sentence names the
person. A role follows in brackets only at a customer where more than one person can sign (the ward and the school),
and then only the role this decision was asked of that person. A sentence that waits names who really decides at
that customer. Sentences already stored are not rewritten: these are built when an order changes state.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from tta.contracts.common import ApprovalStatus, ApproverRole, DecisionKind, Identity, OrderStatus, Verdict
from tta.contracts.order import Approval, ApprovalDecision
from tta.contracts.policy import FiredRule, PolicyDecision
from tta.orders import wording
from tta.policy import RulePolicyEngine

PURCHASING, FINANCE, DIETITIAN = ApproverRole.PURCHASING_MANAGER, ApproverRole.FINANCE, ApproverRole.DIETITIAN
WARD = "allergy-ward"
NOW = datetime(2026, 11, 14, 2, 52, tzinfo=timezone(timedelta(hours=2)))
BY = "to be decided by Sunday 15 November 2026 at 17:00 (UTC+02:00)"


# --- through the order book -----------------------------------------------------------------------------------


def test_at_the_hotel_a_confirmed_order_names_the_person_and_no_role(
    book: Any, samples: Any, agent_hotel: Identity, approver_hotel_buyer: Identity
) -> None:
    waiting = book.waiting(agent_hotel, samples.within_authority())

    order = book.service.decide(waiting.approval_id, approver_hotel_buyer, samples.approve())

    assert order.status is OrderStatus.ORDERED and order.decision.rule_ids == ("F-10",)
    assert order.status_sentence == "Confirmed by Hotel buyer (demo): ordered for €265.00 net."


def test_at_the_hotel_an_approval_of_two_roles_names_the_person_once_and_no_role(
    book: Any, samples: Any, agent_hotel: Identity, approver_hotel_buyer: Identity
) -> None:
    waiting = book.waiting(agent_hotel, samples.above_daily_limit())
    # Who really decides at the hotel: its one person, named by the role every hotel sentence already uses.
    assert waiting.status_sentence == (
        f"Waiting for approval by the purchasing manager, {BY}: rules P-01 and P-02 ask for a human."
    )

    order = book.service.decide(waiting.approval_id, approver_hotel_buyer, samples.approve())

    assert book.store.get_approval(order.approval_id).required_roles == (PURCHASING, FINANCE)  # the data is as before
    assert order.status_sentence == (
        "Ordered for €3,180.00 net with approval by Hotel buyer (demo): rules P-01 and P-02 asked for a human and "
        "were accepted."
    )


def test_at_the_hotel_a_rejection_names_the_person_and_no_role(
    book: Any, samples: Any, agent_hotel: Identity, approver_hotel_buyer: Identity
) -> None:
    waiting = book.waiting(agent_hotel, samples.above_order_limit())

    order = book.service.decide(waiting.approval_id, approver_hotel_buyer, samples.reject())

    assert order.status_sentence == "Rejected by Hotel buyer (demo): nothing was ordered."


def test_at_the_hotel_an_allergen_question_waits_for_the_purchasing_manager_not_for_a_dietitian(
    book: Any, samples: Any, agent_hotel: Identity, approver_hotel_buyer: Identity
) -> None:
    """The hotel has no dietitian: its one person holds that role. The data still names the role asked."""
    waiting = book.waiting(agent_hotel, samples.ward_question())

    assert book.store.get_approval(waiting.approval_id).required_roles == (DIETITIAN,)
    assert waiting.status_sentence == (
        f"Waiting for approval by the purchasing manager, {BY}: rule P-04 asks for a human."
    )
    order = book.service.decide(waiting.approval_id, approver_hotel_buyer, samples.approve())
    assert order.status_sentence == (
        "Ordered for €428.00 net with approval by Hotel buyer (demo): rule P-04 asked for a human and was accepted."
    )


def test_at_the_ward_the_person_is_named_with_the_one_role_the_decision_was_asked_of_them(
    book: Any, samples: Any, agent_ward: Identity, approver_ward_purchasing: Identity, approver_dietitian: Identity
) -> None:
    """Two people can sign at the ward. The person who orders also holds finance's role; it was not asked."""
    waiting = book.waiting(agent_ward, samples.ward_question_above_limit(), profile_id=WARD)
    assert waiting.status_sentence == (
        f"Waiting for approval by the purchasing manager and the dietitian, {BY}: rules P-01 and P-04 ask for a human."
    )

    after_first = book.service.decide(waiting.approval_id, approver_ward_purchasing, samples.approve())
    after_second = book.service.decide(waiting.approval_id, approver_dietitian, samples.approve())

    assert after_first.status_sentence == (
        f"Approved by Ward purchasing (demo) (purchasing manager); still waiting for approval by the dietitian, {BY}: "
        "rules P-01 and P-04 ask for a human."
    )
    assert after_second.status_sentence == (
        "Ordered for €642.00 net with approval by Ward purchasing (demo) (purchasing manager) and Dietitian (demo) "
        "(dietitian): rules P-01 and P-04 asked for a human and were accepted."
    )


def test_at_the_ward_a_spend_stop_of_two_roles_is_one_persons_and_reads_as_the_purchasing_managers(
    book: Any, samples: Any, agent_ward: Identity, approver_ward_purchasing: Identity
) -> None:
    """P-01 and P-02 name the purchasing manager and finance; at the ward one person holds both."""
    book.waiting(agent_ward, samples.ward_safe(), profile_id=WARD)  # €428.00 of the day already waits
    waiting = book.waiting(agent_ward, samples.ward_fills_the_day(), profile_id=WARD)
    assert book.store.get_approval(waiting.approval_id).required_roles == (PURCHASING, FINANCE)
    assert waiting.status_sentence == (
        f"Waiting for approval by the purchasing manager, {BY}: rules P-01 and P-02 ask for a human."
    )

    order = book.service.decide(waiting.approval_id, approver_ward_purchasing, samples.approve())

    assert order.status_sentence == (
        "Ordered for €1,112.80 net with approval by Ward purchasing (demo) (purchasing manager): rules P-01 and "
        "P-02 asked for a human and were accepted."
    )


def test_at_the_ward_a_rejection_by_the_dietitian_says_so(
    book: Any, samples: Any, agent_ward: Identity, approver_dietitian: Identity
) -> None:
    waiting = book.waiting(agent_ward, samples.ward_question(), profile_id=WARD)

    order = book.service.decide(waiting.approval_id, approver_dietitian, samples.reject())

    assert order.status_sentence == "Rejected by Dietitian (demo) (dietitian): nothing was ordered."


def test_an_allergen_question_nobody_answered_expires_naming_who_really_decides_at_that_customer(
    book: Any, samples: Any, agent_hotel: Identity, agent_ward: Identity
) -> None:
    at_the_hotel = book.waiting(agent_hotel, samples.ward_question())
    at_the_ward = book.waiting(agent_ward, samples.ward_question(), profile_id=WARD)
    book.clock.advance(timedelta(days=3))

    hotel = book.service.get_order(at_the_hotel.order_id, agent_hotel)
    ward = book.service.get_order(at_the_ward.order_id, agent_ward)

    assert hotel.status is OrderStatus.EXPIRED and ward.status is OrderStatus.EXPIRED
    when = "Expired on Sunday 15 November 2026 at 17:00 (UTC+02:00) without approval by"
    assert hotel.status_sentence == f"{when} the purchasing manager: nothing was ordered."
    assert ward.status_sentence == f"{when} the dietitian: nothing was ordered."


# --- the wording itself -----------------------------------------------------------------------------------------


def _decision(*rule_ids: str, roles: tuple[ApproverRole, ...]) -> PolicyDecision:
    fired = tuple(
        FiredRule(rule_id=rule_id, title="A rule", fixed=False, verdict=Verdict.APPROVAL, approver_role=roles[0],
                  sentence="A reason.")
        for rule_id in rule_ids
    )
    return PolicyDecision(
        verdict=Verdict.APPROVAL, fired=fired, required_roles=roles, policy_hash="sha256:" + "0" * 64,
        profile_id="my-kitchen", evaluated_at=NOW, sentence="A decision built for a wording test.",
    )


def _signed(name: str, approver_id: str, *roles: ApproverRole) -> ApprovalDecision:
    return ApprovalDecision(
        approver_id=approver_id, approver_name=name, roles=roles, decision=DecisionKind.APPROVE, decided_at=NOW,
    )


def _approval(*decisions: ApprovalDecision, roles: tuple[ApproverRole, ...]) -> Approval:
    return Approval(
        approval_id="apr_1", order_id="ord_1", offer_id="off_1", option_id="opt_1", profile_id="my-kitchen",
        status=ApprovalStatus.PENDING, required_roles=roles, decisions=decisions, created_at=NOW,
    )


def test_one_person_who_signed_two_roles_under_two_identities_is_named_once(engine: RulePolicyEngine) -> None:
    """The shop page signs role by role with one identity per role, each under the name of the customer's person."""
    ward = engine.get_profile(WARD)
    roles = (PURCHASING, DIETITIAN)
    approval = _approval(
        _signed("Hanna Laine, Harbourside Hotel", "human:my-kitchen-purchasing", PURCHASING),
        _signed("Hanna Laine, Harbourside Hotel", "human:my-kitchen-dietitian", DIETITIAN), roles=roles,
    )

    sentence = wording.ordered_with_approval(approval, Decimal("208.00"), _decision("P-01", "P-04", roles=roles), ward)

    assert sentence == (
        "Ordered for €208.00 net with approval by Hanna Laine, Harbourside Hotel (purchasing manager and dietitian): "
        "rules P-01 and P-04 asked for a human and were accepted."
    )


def test_without_a_profile_the_sentence_names_the_person_and_no_role() -> None:
    """A caller that does not say whose order it is gets the name alone: a role is added only on knowledge."""
    approval = _approval(_signed("Jussi Nieminen", "human:ward-purchasing", PURCHASING, FINANCE), roles=(PURCHASING,))

    assert wording.ordered_with_approval(approval, Decimal("402.00"), _decision("P-01", roles=(PURCHASING,))) == (
        "Ordered for €402.00 net with approval by Jussi Nieminen: rule P-01 asked for a human and was accepted."
    )
