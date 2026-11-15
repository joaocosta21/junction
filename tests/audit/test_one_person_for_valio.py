"""Valio Aimo's view names no role of a person who holds them all (lane FIX-A1, item 8; decisions B54 and B61).

Its sentence for a hotel approval read "The buyer's purchasing manager, finance and dietitian approved order …":
three roles for one person. One person confirms, so Valio Aimo reads "a person of the buyer". A role is named only
where the buyer has a second person and that role is what was asked: the dietitian of the ward and of the school.
Valio Aimo still never reads a name.
"""

from __future__ import annotations

from typing import Any

import pytest

from tta.audit import AuditTrail
from tta.contracts.audit import Actor, ActorKind, AuditContext, AuditEventType
from tta.contracts.common import ApprovalStatus, ApproverRole, DecisionKind, OrderStatus, PlacedBy
from tta.contracts.order import ApprovalDecision
from tta.contracts.policy import BuyerProfile

PM, FIN, DIET = ApproverRole.PURCHASING_MANAGER, ApproverRole.FINANCE, ApproverRole.DIETITIAN
EVERY_ROLE = (PM, FIN, DIET)
HANNA = Actor(kind=ActorKind.HUMAN, id="human:hotel-purchasing", role="purchasing_manager, finance, dietitian",
              display_name="Demo approver Hanna")
SARI = Actor(kind=ActorKind.HUMAN, id="human:ward-dietitian", role="dietitian", display_name="Demo approver Sari")
JUSSI = Actor(kind=ActorKind.HUMAN, id="human:ward-purchasing", role="purchasing_manager, finance",
              display_name="Demo approver Jussi")


def _signed(actor: Actor, roles: tuple[ApproverRole, ...], samples: Any, kind: DecisionKind = DecisionKind.APPROVE,
            name: str | None = None) -> ApprovalDecision:
    return ApprovalDecision(approver_id=actor.id, approver_name=name or str(actor.display_name), roles=roles,
                            decision=kind, decided_at=samples.now)


def _hotel(samples: Any) -> BuyerProfile:
    """One person holds every role, as the hotel's and the bakery's profile files say."""
    return samples.hotel_profile().model_copy(update={"approver_roles": dict.fromkeys(EVERY_ROLE, (HANNA.id,))})


def _ward(samples: Any) -> BuyerProfile:
    """A dietitian of its own, as the ward's and the school's profile files say."""
    return samples.hotel_profile().model_copy(update={
        "profile_id": "allergy-ward", "approver_roles": {PM: (JUSSI.id,), FIN: (JUSSI.id,), DIET: (SARI.id,)},
    })


def _decided(trail: AuditTrail, samples: Any, actor: Actor, decision: ApprovalDecision, profile: BuyerProfile | None,
             required: tuple[ApproverRole, ...] = (PM,), earlier: tuple[ApprovalDecision, ...] = ()) -> str:
    order = samples.order(samples.partial_option(), OrderStatus.PENDING_APPROVAL)
    missing = tuple(role for role in required if not any(role in entry.roles for entry in (*earlier, decision)))
    status = ApprovalStatus.PENDING if missing else ApprovalStatus.APPROVED
    approval = samples.approval(status, (*earlier, decision), roles=required)
    context = AuditContext(order=order, approval=approval, approval_decision=decision, profile=profile)
    return trail.record(AuditEventType.APPROVAL_DECIDED, actor, context).data.supplier_sentence


def test_the_hotels_one_person_is_a_person_of_the_buyer_whatever_roles_her_token_holds(
    trail: AuditTrail, samples: Any
) -> None:
    sentence = _decided(trail, samples, HANNA, _signed(HANNA, EVERY_ROLE, samples), _hotel(samples), EVERY_ROLE)

    assert sentence == "A person of the buyer approved order ord_1. This approval accepts rules P-01 and P-03."
    assert "purchasing manager" not in sentence and "finance" not in sentence and "dietitian" not in sentence
    assert "Hanna" not in sentence


def test_at_the_ward_the_dietitian_is_named_and_the_person_who_orders_is_a_person_of_the_buyer(
    trail: AuditTrail, samples: Any
) -> None:
    ward, both = _ward(samples), (PM, DIET)
    by_the_buyer = _signed(JUSSI, (PM, FIN), samples)

    first = _decided(trail, samples, JUSSI, by_the_buyer, ward, both)
    second = _decided(trail, samples, SARI, _signed(SARI, (DIET,), samples), ward, both, earlier=(by_the_buyer,))

    assert first == (
        "A person of the buyer approved order ord_1. This approval accepts rules P-01 and P-03. "
        "The order still needs approval by the buyer's dietitian."
    )
    assert second == "The buyer's dietitian approved order ord_1. This approval accepts rules P-01 and P-03."
    assert "Sari" not in second and "Jussi" not in first


def test_where_one_person_holds_the_dietitians_role_too_no_dietitian_is_named(trail: AuditTrail, samples: Any) -> None:
    """The hotel over REST: its profile lists the person who orders under the dietitian's role."""
    hotel = _hotel(samples)
    order = samples.order(samples.partial_option(), OrderStatus.PENDING_APPROVAL)
    asked = trail.record(
        AuditEventType.APPROVAL_REQUESTED, samples.agent_hotel,
        AuditContext(order=order, approval=samples.approval(roles=(DIET,)), profile=hotel),
    ).data.supplier_sentence

    assert "was sent to a person of the buyer for approval." in asked and "dietitian" not in asked.split("Rule")[0]


def test_a_signature_for_the_dietitians_role_by_somebody_who_also_signed_as_the_buyer_is_one_person(
    trail: AuditTrail, samples: Any
) -> None:
    """The shop page signs role by role under one name: the second signature is the same person's."""
    ward, both, name = _ward(samples), (PM, DIET), "Hanna Laine, Harbourside Hotel"
    as_buyer = _signed(JUSSI, (PM,), samples, name=name)

    second = _decided(trail, samples, SARI, _signed(SARI, (DIET,), samples, name=name), ward, both, earlier=(as_buyer,))

    assert second == "A person of the buyer approved order ord_1. This approval accepts rules P-01 and P-03."


def test_an_order_confirmed_by_two_people_names_the_dietitian_and_a_person_of_the_buyer(
    trail: AuditTrail, samples: Any
) -> None:
    ward = _ward(samples)
    given = (_signed(JUSSI, (PM, FIN), samples), _signed(SARI, (DIET,), samples))
    approved = samples.approval(ApprovalStatus.APPROVED, given, roles=(PM, DIET))
    ordered = samples.order(samples.partial_option(), OrderStatus.ORDERED, placed_by=PlacedBy.HUMAN_APPROVAL)

    by_two = trail.record(AuditEventType.ORDER_CONFIRMED, samples.gateway,
                          AuditContext(order=ordered, approval=approved, profile=ward)).data.supplier_sentence
    by_one = trail.record(
        AuditEventType.ORDER_CONFIRMED, samples.gateway,
        AuditContext(order=ordered, profile=_hotel(samples),
                     approval=samples.approval(ApprovalStatus.APPROVED, (_signed(HANNA, EVERY_ROLE, samples),))),
    ).data.supplier_sentence

    assert by_two.startswith(
        "Order ord_1 is ordered, with approval by a person of the buyer and the buyer's dietitian: "
    )
    assert by_one.startswith("Order ord_1 is ordered, with approval by a person of the buyer: ")


@pytest.mark.parametrize(("actor", "roles", "who"), [
    (HANNA, EVERY_ROLE, "a person of the buyer"), (SARI, (DIET,), "the buyer's dietitian"),
])
def test_a_rejection_says_who_the_same_way(
    trail: AuditTrail, samples: Any, actor: Actor, roles: tuple[ApproverRole, ...], who: str
) -> None:
    profile = _hotel(samples) if actor is HANNA else _ward(samples)
    decision = _signed(actor, roles, samples, DecisionKind.REJECT)
    order = samples.order(samples.partial_option(), OrderStatus.REJECTED)
    context = AuditContext(order=order, approval=samples.approval(ApprovalStatus.REJECTED, (decision,), roles=roles),
                           approval_decision=decision, profile=profile)

    decided = trail.record(AuditEventType.APPROVAL_DECIDED, actor, context).data.supplier_sentence
    rejected = trail.record(AuditEventType.ORDER_REJECTED, actor, context).data.supplier_sentence

    assert decided == f"{who[0].upper()}{who[1:]} rejected order ord_1."
    assert rejected == f"Order ord_1 was rejected by {who}. Nothing was ordered."


def test_a_rule_line_names_the_dietitian_only_where_she_is_a_second_person(trail: AuditTrail, samples: Any) -> None:
    asks_dietitian = samples.rule("P-04", "A product does not rule out milk.", role=DIET, product_id="469512")
    asks_finance = samples.rule("P-02", "Today's spend is above the limit per day.", role=FIN)
    option = samples.option("opt_1", (samples.line("469512", "100", "1.99"),),
                            samples.decision(asks_finance, asks_dietitian))

    def checked(profile: BuyerProfile) -> str:
        context = AuditContext(offer_id="off_1", option=option, decision=option.decision, profile=profile)
        return trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway, context).data.supplier_sentence

    at_the_hotel, at_the_ward = checked(_hotel(samples)), checked(_ward(samples))

    assert ": a person of the buyer must approve this order." in at_the_hotel
    assert at_the_hotel.count("approval by a person of the buyer.") == 2 and "dietitian" not in at_the_hotel
    assert ": a person of the buyer and the buyer's dietitian must approve this order." in at_the_ward
    assert "approval by the buyer's dietitian." in at_the_ward and "finance" not in at_the_ward
