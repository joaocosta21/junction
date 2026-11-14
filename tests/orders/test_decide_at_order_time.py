"""`decide` asks the policy first and then whether this approver holds a role the new decision still needs;
an order whose time passes during the check expires in the same call (SPEC section 8)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from tta.contracts.common import (
    AllergenRelation,
    ApprovalStatus,
    ApproverRole,
    AvailabilityState,
    Identity,
    OptionKind,
    OrderStatus,
    PlacedBy,
    Verdict,
)
from tta.contracts.errors import NotAuthorised, OfferExpired
from tta.contracts.order import Order

PURCHASING = ApproverRole.PURCHASING_MANAGER
FINANCE = ApproverRole.FINANCE
DIETITIAN = ApproverRole.DIETITIAN
WARD = "allergy-ward"


def _small_order(samples, option_id: str = "opt_1"):
    """€700.00, within the limit per order: alone it is within authority."""
    return samples.option(option_id, (samples.line("463380", "250", "2.80"),))


def _small_unconfirmed(samples, option_id: str = "opt_2"):
    """€101.00 of a product whose quantity is not confirmed: the purchasing manager decides (F-01)."""
    lines = (samples.line("464306", "100", "1.01", state=AvailabilityState.QUANTITY_NOT_CONFIRMED),)
    return samples.option(option_id, lines, kind=OptionKind.ALTERNATIVE_UNCONFIRMED)


def _waiting_for_finance_only(book, samples, agent: Identity) -> tuple[Order, Order]:
    """€2,650.00 waits for the purchasing manager; €700.00 more crosses €3,000 a day and waits for finance."""
    large = book.waiting(agent, samples.above_order_limit())
    small = book.waiting(agent, _small_order(samples), _small_unconfirmed(samples))
    assert book.store.get_approval(small.approval_id).required_roles == (FINANCE,)
    return large, small


def _ward_waiting_for_the_dietitian_only(book, samples, agent: Identity) -> Order:
    """€428.00 with an allergen question waits for the ward's dietitian (P-04); its other option is €101.00 of
    a safe product whose quantity is not confirmed, which the purchasing manager decides (F-01)."""
    safe = samples.allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.FREE_FROM})
    lines = (samples.line(
        "464306", "100", "1.01", state=AvailabilityState.QUANTITY_NOT_CONFIRMED, allergens=safe,
    ),)
    unconfirmed = samples.option("opt_2", lines, kind=OptionKind.ALTERNATIVE_UNCONFIRMED)
    order = book.waiting(agent, samples.ward_question(), unconfirmed, profile_id=WARD)
    assert book.store.get_approval(order.approval_id).required_roles == (DIETITIAN,)
    return order


def test_an_approver_whose_role_the_policy_asks_for_only_now_is_not_refused(
    book, samples, agent_ward: Identity, approver_ward_purchasing: Identity, approver_dietitian: Identity
) -> None:
    """Two people exist only where a customer has a dietitian (decision B54). The ward's order waits for her
    alone; then the day fills, and the person who orders, whom the approval did not name, is asked too (P-02)."""
    question = _ward_waiting_for_the_dietitian_only(book, samples, agent_ward)
    filler = book.waiting(agent_ward, samples.ward_fills_the_day(), profile_id=WARD)  # €1,112.80 more
    ordered = book.service.decide(filler.approval_id, approver_ward_purchasing, samples.approve())
    assert ordered.status is OrderStatus.ORDERED
    assert book.store.get_approval(question.approval_id).roles_missing == (DIETITIAN,)  # as it was first asked

    after_orderer = book.service.decide(question.approval_id, approver_ward_purchasing, samples.approve())

    approval = book.store.get_approval(question.approval_id)
    assert after_orderer.status is OrderStatus.PENDING_APPROVAL and after_orderer.decision.rule_ids == ("P-02", "P-04")
    assert approval.required_roles == (DIETITIAN, FINANCE) and approval.roles_missing == (DIETITIAN,)
    assert [entry.approver_id for entry in approval.decisions] == [approver_ward_purchasing.id]
    completed = book.service.decide(question.approval_id, approver_dietitian, samples.approve())
    assert completed.status is OrderStatus.ORDERED


def test_the_approver_who_picks_another_option_needs_a_role_that_option_asks_for(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    _, small = _waiting_for_finance_only(book, samples, agent_hotel)

    order = book.service.decide(small.approval_id, approver_purchasing, samples.approve(option_id="opt_2"))

    assert order.status is OrderStatus.ORDERED and order.placed_by is PlacedBy.HUMAN_APPROVAL
    assert order.option_id == "opt_2" and order.decision.rule_ids == ("F-01",)
    approval = book.store.get_approval(small.approval_id)
    assert approval.status is ApprovalStatus.APPROVED and approval.required_roles == (PURCHASING,)


def test_an_approver_who_holds_no_role_the_new_decision_asks_for_is_refused_after_the_check(
    book, samples, agent_ward: Identity, approver_dietitian: Identity
) -> None:
    """The ward's dietitian is asked the allergen question; the option without one is not hers to choose."""
    small = _ward_waiting_for_the_dietitian_only(book, samples, agent_ward)

    with pytest.raises(NotAuthorised) as raised:
        book.service.decide(small.approval_id, approver_dietitian, samples.approve(option_id="opt_2"))

    assert raised.value.detail == (
        "The approval still needs the purchasing manager; this approver counts for the dietitian and holds none "
        "of them."
    )
    assert [option.option_id for option in book.revalidator.calls][-1] == "opt_2"
    assert book.store.get_order(small.order_id) == small
    assert book.store.get_approval(small.approval_id).decisions == ()
    assert book.event_types(small.order_id) == ["approval.requested", "authorisation.refused"]
    assert raised.value.detail in book.events(small.order_id)[-1].data.sentence


def test_when_the_policy_asks_for_nobody_any_more_any_listed_approver_of_the_buyer_completes_the_order(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    large, small = _waiting_for_finance_only(book, samples, agent_hotel)
    book.service.decide(large.approval_id, approver_purchasing, samples.reject())  # the day's spend falls back

    order = book.service.decide(small.approval_id, approver_purchasing, samples.approve())

    assert order.status is OrderStatus.ORDERED and order.placed_by is PlacedBy.HUMAN_APPROVAL
    assert order.decision.verdict is Verdict.APPROVAL
    assert order.decision.rule_ids == ("F-10",)


def test_a_rejection_still_needs_a_role_the_approval_is_waiting_for(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    _, small = _waiting_for_finance_only(book, samples, agent_hotel)
    calls = len(book.revalidator.calls)

    with pytest.raises(NotAuthorised):
        book.service.decide(small.approval_id, approver_purchasing, samples.reject())

    assert len(book.revalidator.calls) == calls  # a rejection asks the supplier nothing
    assert book.store.get_order(small.order_id) == small


def test_an_order_whose_time_passes_while_the_supplier_answers_expires_in_the_same_call(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    soon = samples.now + timedelta(hours=1)
    pending = book.waiting(agent_hotel, samples.above_order_limit(valid_until=soon))
    book.clock.advance(timedelta(minutes=59))
    book.revalidator.during_call = lambda: book.clock.advance(timedelta(minutes=2))

    with pytest.raises(OfferExpired) as raised:
        book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    assert raised.value.extensions["order_id"] == pending.order_id
    expired = book.store.get_order(pending.order_id)
    assert expired.status is OrderStatus.EXPIRED and expired.updated_at == book.clock.now()
    approval = book.store.get_approval(pending.approval_id)
    assert approval.status is ApprovalStatus.EXPIRED and approval.decisions == ()
    assert book.event_types(pending.order_id) == ["approval.requested", "order.not_placed", "order.expired"]


def test_a_chosen_option_whose_time_passes_during_the_check_leaves_the_order_waiting(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    soon = samples.now + timedelta(hours=1)
    expiring = samples.unconfirmed("opt_2", valid_until=soon)
    pending = book.waiting(agent_hotel, samples.above_order_limit("opt_1"), expiring)
    book.clock.advance(timedelta(minutes=59))
    book.revalidator.during_call = lambda: book.clock.advance(timedelta(minutes=2))

    with pytest.raises(OfferExpired):
        book.service.decide(pending.approval_id, approver_purchasing, samples.approve(option_id="opt_2"))

    assert book.store.get_order(pending.order_id) == pending  # its own option is valid until Sunday
    assert book.event_types(pending.order_id) == ["approval.requested", "order.not_placed"]
