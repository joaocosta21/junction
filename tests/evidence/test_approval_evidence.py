"""Evidence in the approval itself: attached when a product goes to the dietitian because it states nothing about
an excluded allergen, named in the approval's reasons, recorded in the audit trail, returned by the API, and
never a reason for any status or verdict to change."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from tta.contracts.audit import EVENT_TYPE_PREFIX
from tta.contracts.common import (
    ApprovalStatus,
    ApproverRole,
    AuditReader,
    DecisionKind,
    Identity,
    IdentityKind,
    OrderStatus,
    PlacedBy,
    Unit,
    Verdict,
)
from tta.contracts.order import DecisionRequest, Order
from tta.contracts.request import PurchaseRequest, RequestLine

Make = Callable[..., Any]
EVIDENCE_EVENT = f"{EVENT_TYPE_PREFIX}evidence.attached"
# Since L2b of 14 Nov the safe substitute 473424 comes first (F-10, purchasing manager); the dietitian's case is
# Elovena 469512 itself, whose data does not rule out milk (P-04): the option with this title.
NOT_RULED_OUT = "Alternative: allergen not ruled out"
ELOVENA_ID = "469512"


def _place(stack: SimpleNamespace, agent: Identity, request: Any, key: str = "s2-1") -> Order:
    offer = stack.service.create_offer(agent, request)
    return stack.service.place_order(agent, offer.offer_id, offer.options[0].option_id, key)


def _place_not_ruled_out(stack: SimpleNamespace, agent: Identity, request: Any, key: str = "s2-1") -> Order:
    """Order the option of Elovena 469512 itself, found by its product and title, never by its place."""
    offer = stack.service.create_offer(agent, request)
    option = next(
        option for option in offer.options
        if option.title == NOT_RULED_OUT and [line.product_id for line in option.lines] == [ELOVENA_ID]
    )
    return stack.service.place_order(agent, offer.offer_id, option.option_id, key)


def _events(stack: SimpleNamespace, who: Identity, order_id: str, reader: AuditReader = AuditReader.BUYER) -> Any:
    return stack.service.get_audit(who, reader=reader, order_id=order_id).events


def test_an_approval_for_an_unstated_allergen_carries_the_evidence_and_names_it(
    make_stack: Make, make_finder: Make, fake_answers: Make, requests: SimpleNamespace, agent_hotel: Identity,
    hotel_dietitian: Identity, bodies: SimpleNamespace, ids: SimpleNamespace,
) -> None:
    stack = make_stack(make_finder(fake_answers(bodies.elovena)))

    order = _place_not_ruled_out(stack, agent_hotel, requests.elovena())

    assert order.status is OrderStatus.PENDING_APPROVAL
    approval = stack.orders.get_approval(order.approval_id, hotel_dietitian)
    assert approval.required_roles == (ApproverRole.DIETITIAN,)
    (evidence,) = approval.evidence
    assert (evidence.product_id, evidence.found, evidence.source_url) == (ids.elovena, True, bodies.elovena_url)
    assert approval.reasons[0].startswith("Elovena 1l oat drink barista (469512) does not rule out")  # P-04, as before
    assert approval.reasons[1] == (
        "Web evidence for product 469512 is attached for the dietitian, and it is not Valio Aimo's data: "
        "The manufacturer's page “Elovena Kaurajuoma kahviin” on elovena.fi says: contains KAURA; free from "
        "Gluteeniton, Laktoositon, Maidoton, Kananmunaton. Asked about milk (AM): Valio Aimo's data states nothing; "
        "the page says free from, in its words “Maidoton”. It changes no verdict: a human decides."
    )


def test_the_api_list_of_approvals_returns_the_evidence(
    make_stack: Make, make_finder: Make, fake_answers: Make, requests: SimpleNamespace, agent_hotel: Identity,
    hotel_dietitian: Identity, bodies: SimpleNamespace,
) -> None:
    stack = make_stack(make_finder(fake_answers(bodies.elovena)))
    _place_not_ruled_out(stack, agent_hotel, requests.elovena())

    (approval,) = stack.service.list_approvals(hotel_dietitian, ApprovalStatus.PENDING)
    dumped = approval.model_dump(mode="json")

    assert dumped["evidence"][0]["source_url"] == bodies.elovena_url
    assert dumped["evidence"][0]["free_from"] == ["Gluteeniton", "Laktoositon", "Maidoton", "Kananmunaton"]


def test_one_audit_event_records_the_link_and_the_hash_and_the_supplier_sees_neither(
    make_stack: Make, make_finder: Make, fake_answers: Make, requests: SimpleNamespace, agent_hotel: Identity,
    bodies: SimpleNamespace, supplier_reader: Identity,
) -> None:
    stack = make_stack(make_finder(fake_answers(bodies.elovena)))
    order = _place_not_ruled_out(stack, agent_hotel, requests.elovena())

    events = _events(stack, agent_hotel, order.order_id)
    attached = [event for event in events if event.type == EVIDENCE_EVENT]
    supplier = [e for e in _events(stack, supplier_reader, order.order_id, AuditReader.SUPPLIER)
                if e.type == EVIDENCE_EVENT]

    assert [event.type.removeprefix(EVENT_TYPE_PREFIX) for event in events][-2:] == [
        "approval.requested", "evidence.attached",
    ]
    (event,) = attached
    assert event.actor.kind.value == "system"
    assert event.facts["evidence"]["source_url"] == bodies.elovena_url
    assert len(event.facts["evidence"]["content_hash"]) == 64
    assert "It changes no status and no verdict." in event.sentence
    (seen,) = supplier
    assert bodies.elovena_url not in str(seen.model_dump())
    assert "Maidoton" not in str(seen.model_dump())
    assert stack.audit.verify_chain().ok


@pytest.mark.parametrize("failure", ["timeout", "success-false", "no-key"])
def test_without_evidence_the_approval_still_works_and_a_sentence_says_so(
    make_stack: Make, make_finder: Make, fake_answers: Make, unavailable: Make, requests: SimpleNamespace,
    agent_hotel: Identity, hotel_dietitian: Identity, bodies: SimpleNamespace, failure: str,
) -> None:
    answers = {
        "timeout": fake_answers(error=unavailable("the web search did not answer in time")),
        "success-false": fake_answers({**bodies.elovena, "success": False}),
        "no-key": None,
    }[failure]
    stack = make_stack(make_finder(answers))

    order = _place_not_ruled_out(stack, agent_hotel, requests.elovena())
    (approval,) = stack.service.list_approvals(hotel_dietitian, ApprovalStatus.PENDING)

    (evidence,) = approval.evidence
    assert not evidence.found
    assert evidence.sentence.startswith("No evidence was found on the web for product 469512: ")
    assert len(approval.reasons) == 1  # only the rule's own reason
    assert EVIDENCE_EVENT not in [event.type for event in _events(stack, agent_hotel, order.order_id)]
    decided = stack.service.decide_approval(
        hotel_dietitian, approval.approval_id, DecisionRequest(decision=DecisionKind.APPROVE, note="Checked.")
    )
    assert (decided.status, decided.placed_by) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)


def test_without_a_finder_nothing_is_attached(
    make_stack: Make, requests: SimpleNamespace, agent_hotel: Identity, hotel_dietitian: Identity,
) -> None:
    stack = make_stack(None)

    _place_not_ruled_out(stack, agent_hotel, requests.elovena())
    (approval,) = stack.service.list_approvals(hotel_dietitian, ApprovalStatus.PENDING)

    assert approval.evidence == ()
    assert len(approval.reasons) == 1


def test_the_verdict_and_every_status_are_the_same_with_and_without_evidence(
    make_stack: Make, make_finder: Make, fake_answers: Make, requests: SimpleNamespace, agent_hotel: Identity,
    hotel_dietitian: Identity, bodies: SimpleNamespace,
) -> None:
    with_evidence = make_stack(make_finder(fake_answers(bodies.elovena)))
    without = make_stack(None)

    placed = [_place_not_ruled_out(stack, agent_hotel, requests.elovena()) for stack in (with_evidence, without)]
    stacks = (with_evidence, without)
    pending = [stack.service.list_approvals(hotel_dietitian, ApprovalStatus.PENDING)[0] for stack in stacks]
    decided = [
        stack.service.decide_approval(
            hotel_dietitian, approval.approval_id, DecisionRequest(decision=DecisionKind.APPROVE)
        )
        for stack, approval in zip(stacks, pending, strict=True)
    ]

    for one, other in (placed, decided):
        assert one.status is other.status
        assert one.decision.verdict is other.decision.verdict is (Verdict.APPROVAL)
        assert one.decision.model_dump(exclude={"evaluated_at"}) == other.decision.model_dump(exclude={"evaluated_at"})
        assert one.option.model_dump(exclude={"decision"}) == other.option.model_dump(exclude={"decision"})
        claims = [[(claim.claim, claim.status) for claim in line.claims] for line in one.option.lines]
        assert claims == [[(claim.claim, claim.status) for claim in line.claims] for line in other.option.lines]
        assert one.option.lines[0].allergen_check == other.option.lines[0].allergen_check
    assert pending[0].required_roles == pending[1].required_roles
    assert pending[0].status is pending[1].status is ApprovalStatus.PENDING
    assert decided[0].status is OrderStatus.ORDERED


def test_an_order_that_waits_only_for_a_person_to_confirm_asks_for_no_evidence(
    make_stack: Make, make_finder: Make, fake_answers: Make, agent_ward: Identity,
) -> None:
    answers = fake_answers({})
    stack = make_stack(make_finder(answers))
    text = "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"
    request = PurchaseRequest(needed_by=date(2026, 11, 16), require_confirmed=True, lines=(RequestLine(
        text=text, product_type="plant_drink", quantity=Decimal(200), unit=Unit.L, exclude_allergens=("AM", "AW"),
    ),))

    order = _place(stack, agent_ward, request)

    assert order.status is OrderStatus.PENDING_APPROVAL  # F-10 alone: no allergen doubt, so nothing to look up
    assert answers.asked == []


def test_a_waiting_order_keeps_its_evidence_reason_while_a_second_role_is_missing(
    make_stack: Make, make_finder: Make, fake_answers: Make, agent_hotel: Identity, bodies: SimpleNamespace,
    requests: SimpleNamespace,
) -> None:
    """Oddlygood oat drink 1 l: quantity not confirmed (F-01, purchasing manager) and no milk statement (P-04)."""
    body = {**bodies.elovena, "json_content": {
        **bodies.elovena["json_content"], "product_name_on_page": "Oddlygood® kaurajuoma 1 l UHT gluteeniton",
        "page_title": "Oddlygood® kaurajuoma 1 l UHT gluteeniton",
    }}
    stack = make_stack(make_finder(fake_answers(body)))
    request = requests.elovena()
    line = request.lines[0].model_copy(update={"product_ids": ("468465",), "quantity": Decimal(200)})
    offer = stack.service.create_offer(agent_hotel, request.model_copy(update={"lines": (line,)}))
    unconfirmed = next(option for option in offer.options if option.lines[0].product_id == "468465")
    order = stack.service.place_order(agent_hotel, offer.offer_id, unconfirmed.option_id, "s2-two-roles")
    purchasing = Identity(kind=IdentityKind.APPROVER, id="human:hotel-purchasing", display_name="Demo Hanna",
                          profile_id="hotel-kitchen", roles=(ApproverRole.PURCHASING_MANAGER,))

    stack.service.decide_approval(purchasing, order.approval_id, DecisionRequest(decision=DecisionKind.APPROVE))
    (approval,) = stack.service.list_approvals(purchasing, ApprovalStatus.PENDING)

    assert approval.roles_missing == (ApproverRole.DIETITIAN,)
    assert approval.evidence[0].found
    assert approval.reasons[-1].startswith("Web evidence for product 468465 is attached for the dietitian")
