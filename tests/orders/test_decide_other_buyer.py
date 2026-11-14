"""`decide` on an approval that is not the caller's own buyer's: answered and recorded like one nobody issued,
and never written into the trail of the buyer it aimed at (SPEC section 9: a buyer does not see other buyers)."""

from __future__ import annotations

import pytest

from tta.contracts.common import Identity, OrderStatus
from tta.contracts.errors import NotAuthorised, NotFound


def test_an_approval_nobody_issued_is_not_found_and_the_attempt_is_in_the_callers_own_trail(
    book, samples, approver_purchasing: Identity
) -> None:
    with pytest.raises(NotFound):
        book.service.decide("apr_made-up <b>", approver_purchasing, samples.approve())

    (refused,) = book.events()
    assert refused.type.endswith("authorisation.refused") and refused.data.actor.id == approver_purchasing.id
    assert (refused.data.profile_id, refused.data.approval_id, refused.data.order_id) == ("hotel-kitchen", None, None)
    assert "No approval has this id" in refused.data.sentence and "made-up" not in refused.model_dump_json()


def test_an_approval_of_another_buyer_is_answered_and_recorded_like_one_nobody_issued(
    book, samples, agent_hotel: Identity, approver_dietitian: Identity
) -> None:
    pending = book.waiting(agent_hotel, samples.above_order_limit())

    for decision in (samples.approve(), samples.reject()):
        with pytest.raises(NotFound) as of_another_buyer:
            book.service.decide(pending.approval_id, approver_dietitian, decision)
    with pytest.raises(NotFound) as unknown:
        book.service.decide("apr_000000000bad", approver_dietitian, samples.approve())

    assert of_another_buyer.value.to_problem() == unknown.value.to_problem()
    assert book.store.get_order(pending.order_id) == pending
    assert book.store.get_approval(pending.approval_id).decisions == ()
    assert book.event_types(pending.order_id) == ["approval.requested"]  # nothing in the trail it aimed at
    assert len(book.store.list_audit_events(profile_id="hotel-kitchen")) == 1
    aimed, _, nobody_issued = book.store.list_audit_events(profile_id=approver_dietitian.profile_id)
    assert aimed.data.actor.id == approver_dietitian.id and aimed.data.approval_id is None
    assert (aimed.data.offer_id, aimed.data.order_id) == (None, None)
    assert aimed.data.sentence == nobody_issued.data.sentence and aimed.data.facts == nobody_issued.data.facts
    assert pending.approval_id not in aimed.model_dump_json() and "hotel" not in aimed.model_dump_json()


def test_an_agent_of_another_buyer_is_refused_and_recorded_in_its_own_trail(
    book, samples, agent_hotel: Identity, agent_ward: Identity
) -> None:
    pending = book.waiting(agent_hotel, samples.above_order_limit())

    with pytest.raises(NotAuthorised):
        book.service.decide(pending.approval_id, agent_ward, samples.approve())

    assert book.event_types(pending.order_id) == ["approval.requested"]
    (refused,) = book.store.list_audit_events(profile_id="allergy-ward")
    assert refused.data.actor.id == agent_ward.id and refused.data.rule_ids == ("F-06",)
    assert refused.data.approval_id is None and pending.approval_id not in refused.model_dump_json()


def test_the_supplier_refused_on_a_buyers_approval_is_in_that_buyers_trail(
    book, samples, agent_hotel: Identity, supplier_reader: Identity
) -> None:
    """The supplier is not another buyer: the buyer whose approval it aimed at sees the attempt."""
    pending = book.waiting(agent_hotel, samples.above_order_limit())

    with pytest.raises(NotAuthorised):
        book.service.decide(pending.approval_id, supplier_reader, samples.approve())

    assert book.event_types(pending.order_id) == ["approval.requested", "authorisation.refused"]
    assert book.events(pending.order_id)[-1].data.actor.id == supplier_reader.id


def test_an_order_whose_offer_is_no_longer_stored_cannot_be_approved_and_keeps_waiting(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = book.waiting(agent_hotel, samples.above_order_limit())
    book.store.save_order(pending.model_copy(update={"offer_id": "off_gone00000000"}))

    with pytest.raises(NotFound) as raised:
        book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    assert raised.value.detail == f"The offer of order {pending.order_id} is no longer stored."
    assert book.store.get_order(pending.order_id).status is OrderStatus.PENDING_APPROVAL
