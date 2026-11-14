"""`decide`: who may decide, approve and reject, two roles, another option, the re-check before ORDERED."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from tta.contracts.common import (
    ApprovalStatus,
    ApproverRole,
    DecisionKind,
    Identity,
    OrderStatus,
    PlacedBy,
    Verdict,
)
from tta.contracts.errors import (
    InvalidRequest,
    NotAuthorised,
    NotFound,
    OfferExpired,
    OfferStale,
    PolicyBlocked,
    SupplierUnavailable,
)
from tta.contracts.order import Approval, DecisionRequest, Order

PURCHASING = ApproverRole.PURCHASING_MANAGER
FINANCE = ApproverRole.FINANCE


def _pending(book, samples, agent: Identity, *options, profile_id: str = "hotel-kitchen") -> Order:
    """An order waiting for a human, placed on the first option of a new offer."""
    offer = book.offer(*(options or (samples.above_order_limit(),)), profile_id=profile_id)
    order = book.service.place_order(offer.offer_id, offer.options[0].option_id, agent, f"key-{offer.offer_id}")
    assert order.status is OrderStatus.PENDING_APPROVAL
    return order


def _approval(book, order: Order) -> Approval:
    return book.store.get_approval(order.approval_id)


def test_an_approval_by_the_role_asked_for_orders_after_a_fresh_check(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)
    book.clock.advance(timedelta(hours=1))

    order = book.service.decide(pending.approval_id, approver_purchasing, samples.approve(note="Weekly volume."))

    assert order.status is OrderStatus.ORDERED and order.placed_by is PlacedBy.HUMAN_APPROVAL
    assert order.order_id == pending.order_id and order.option_id == "opt_1"
    assert order.created_at == pending.created_at and order.updated_at == book.clock.now()
    assert order.reliance[0].time_now == samples.now  # when Valio stated the figures: the offer's data time
    assert order.reliance[0].rechecked_at == book.clock.now()
    assert order.status_sentence == (
        "Ordered for €2,650.00 net with approval by Purchasing manager (demo) (purchasing manager): "
        "rule P-01 asked for a human and was accepted."
    )
    approval = _approval(book, order)
    assert approval.status is ApprovalStatus.APPROVED and approval.roles_missing == ()
    (decided,) = approval.decisions
    assert (decided.approver_id, decided.approver_name) == (approver_purchasing.id, approver_purchasing.display_name)
    assert decided.roles == (PURCHASING,) and decided.decision is DecisionKind.APPROVE
    assert (decided.option_id, decided.note, decided.decided_at) == (None, "Weekly volume.", book.clock.now())
    assert len(book.revalidator.calls) == 2
    assert book.event_types(order.order_id) == ["approval.requested", "approval.decided", "order.confirmed"]
    assert book.store.get_order(order.order_id) == order


def test_a_rejection_closes_the_order_and_nothing_is_ordered(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)

    order = book.service.decide(pending.approval_id, approver_purchasing, samples.reject(note="Too much."))

    assert order.status is OrderStatus.REJECTED and order.placed_by is None
    assert order.status_sentence == (
        "Rejected by Purchasing manager (demo) (purchasing manager): nothing was ordered."
    )
    approval = _approval(book, order)
    assert approval.status is ApprovalStatus.REJECTED
    assert approval.decisions[0].decision is DecisionKind.REJECT and approval.decisions[0].note == "Too much."
    assert len(book.revalidator.calls) == 1  # a rejection needs no fresh look at price and availability
    assert book.event_types(order.order_id) == ["approval.requested", "approval.decided", "order.rejected"]


def test_with_two_roles_required_the_first_approver_leaves_it_pending_and_the_second_completes_it(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity, approver_finance: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel, samples.above_daily_limit())
    assert _approval(book, pending).required_roles == (PURCHASING, FINANCE)

    after_first = book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    assert after_first.status is OrderStatus.PENDING_APPROVAL and after_first.placed_by is None
    waiting = _approval(book, after_first)
    assert waiting.status is ApprovalStatus.PENDING
    assert (waiting.roles_obtained, waiting.roles_missing) == ((PURCHASING,), (FINANCE,))
    assert after_first.status_sentence == (
        "Approved by Purchasing manager (demo) (purchasing manager); still waiting for approval by finance, "
        "to be decided by Sunday 15 November 2026 at 17:00 (UTC+02:00): rules P-01 and P-02 ask for a human."
    )

    after_second = book.service.decide(pending.approval_id, approver_finance, samples.approve())

    assert after_second.status is OrderStatus.ORDERED and after_second.placed_by is PlacedBy.HUMAN_APPROVAL
    done = _approval(book, after_second)
    assert done.status is ApprovalStatus.APPROVED
    assert [decision.approver_id for decision in done.decisions] == [approver_purchasing.id, approver_finance.id]
    assert book.event_types(pending.order_id) == [
        "approval.requested", "approval.decided", "approval.decided", "order.confirmed",
    ]


def test_the_approver_picks_the_unconfirmed_alternative_and_f01_is_recorded_as_approved_by_that_human(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel, samples.above_order_limit("opt_1"), samples.unconfirmed("opt_2"))

    order = book.service.decide(pending.approval_id, approver_purchasing, samples.approve(option_id="opt_2"))

    assert order.status is OrderStatus.ORDERED and order.placed_by is PlacedBy.HUMAN_APPROVAL
    assert order.option_id == "opt_2" and order.option.option_id == "opt_2"
    assert order.option.totals.net == Decimal("1010.00")
    assert order.decision.verdict is Verdict.APPROVAL and order.decision.rule_ids == ("F-01", "P-01")
    assert [statement.product_id for statement in order.reliance] == ["464306"]
    assert [option.option_id for option in book.revalidator.calls] == ["opt_1", "opt_2"]
    assert book.policy.contexts[-1].at_order_time is True
    approval = _approval(book, order)
    assert approval.status is ApprovalStatus.APPROVED and approval.option_id == "opt_2"
    assert approval.decisions[0].option_id == "opt_2" and approval.decisions[0].approver_id == approver_purchasing.id
    decided = next(event for event in book.events(order.order_id) if event.type.endswith("approval.decided"))
    assert decided.data.actor.id == approver_purchasing.id and "F-01" in decided.data.rule_ids
    assert "chose another option of the same offer: opt_2" in decided.data.sentence
    assert "instead of opt_1" in decided.data.sentence and "F-01" in decided.data.sentence


def test_naming_the_option_already_proposed_is_not_a_change(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)

    order = book.service.decide(pending.approval_id, approver_purchasing, samples.approve(option_id="opt_1"))

    assert order.status is OrderStatus.ORDERED and _approval(book, order).decisions[0].option_id is None


def test_choosing_an_option_the_policy_blocks_still_blocks_and_the_order_keeps_waiting(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel, samples.above_order_limit("opt_1"), samples.adds_allergen("opt_3"))

    with pytest.raises(PolicyBlocked) as raised:
        book.service.decide(pending.approval_id, approver_purchasing, samples.approve(option_id="opt_3"))

    assert raised.value.extensions["rule_ids"] == ["F-05"]
    assert book.store.get_order(pending.order_id) == pending
    assert _approval(book, pending).decisions == ()
    assert book.event_types(pending.order_id) == ["approval.requested", "order.blocked"]
    blocked = book.events(pending.order_id)[-1]
    assert blocked.data.actor.id == approver_purchasing.id and blocked.data.rule_ids == ("F-05",)


def test_choosing_an_option_the_offer_does_not_hold_is_not_found(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)

    with pytest.raises(NotFound):
        book.service.decide(pending.approval_id, approver_purchasing, samples.approve(option_id="opt_9"))

    assert book.store.get_order(pending.order_id) == pending


def test_choosing_another_option_starts_the_approval_again_on_that_option(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity, approver_finance: Identity
) -> None:
    lines = (samples.line("463380", "1300", "2.65"),)
    pending = _pending(book, samples, agent_hotel, samples.above_daily_limit("opt_1"), samples.option("opt_2", lines))
    book.service.decide(pending.approval_id, approver_finance, samples.approve())

    order = book.service.decide(pending.approval_id, approver_purchasing, samples.approve(option_id="opt_2"))

    approval = _approval(book, order)
    assert order.status is OrderStatus.PENDING_APPROVAL and order.option_id == "opt_2"
    assert [decision.approver_id for decision in approval.decisions] == [approver_purchasing.id]
    assert approval.roles_missing == (FINANCE,)  # finance approved €3,180.00, not the €3,445.00 now proposed


def test_the_order_being_decided_is_not_counted_twice_in_the_days_spend(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)

    order = book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    assert book.policy.contexts[-1].day_committed_net_eur == 0
    assert order.decision.rule_ids == ("P-01",)  # counted twice, €5,300.00 would cross the limit per day (P-02)


def test_a_role_the_policy_asks_for_only_at_approval_time_is_added_before_the_order_can_go_ahead(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity, approver_finance: Identity
) -> None:
    first = _pending(book, samples, agent_hotel)  # €2,650.00: the purchasing manager (P-01)
    second = _pending(book, samples, agent_hotel, samples.option("opt_1", (samples.line("463380", "250", "2.80"),)))
    assert _approval(book, first).required_roles == (PURCHASING,)
    assert _approval(book, second).required_roles == (FINANCE,)  # €700.00 more is above €3,000 a day (P-02)
    assert book.service.decide(second.approval_id, approver_finance, samples.approve()).status is OrderStatus.ORDERED

    still_waiting = book.service.decide(first.approval_id, approver_purchasing, samples.approve())

    assert still_waiting.status is OrderStatus.PENDING_APPROVAL
    assert still_waiting.decision.rule_ids == ("P-01", "P-02")
    waiting = _approval(book, first)
    assert waiting.required_roles == (PURCHASING, FINANCE) and waiting.roles_missing == (FINANCE,)
    # P-01, P-02, and why the day is full: the order that finance approved in between (review A4, finding H2).
    assert len(waiting.reasons) == 3
    assert "today's spend of this buyer is €700.00 before tax: €700.00 ordered and €0.00 waiting" in waiting.reasons[2]
    assert book.service.decide(first.approval_id, approver_finance, samples.approve()).status is OrderStatus.ORDERED


def test_a_rule_that_no_longer_holds_at_approval_time_is_not_asked_of_the_human(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity, approver_finance: Identity
) -> None:
    first = _pending(book, samples, agent_hotel)  # €2,650.00 waiting
    second = _pending(book, samples, agent_hotel, samples.option("opt_1", (samples.line("463380", "250", "2.80"),)))
    assert second.decision.rule_ids == ("P-02",)  # €700.00 more would pass €3,000 a day
    book.service.decide(first.approval_id, approver_purchasing, samples.reject())

    order = book.service.decide(second.approval_id, approver_finance, samples.approve())

    # The spend rule no longer holds, so only F-10 is left: it asks for a person, and the role the approval
    # names is one. Finance completes the approval it was asked for.
    assert order.status is OrderStatus.ORDERED and order.placed_by is PlacedBy.HUMAN_APPROVAL
    assert order.decision.rule_ids == ("F-10",) and _approval(book, order).required_roles == (FINANCE,)
    assert order.decision.sentence == (
        "Prepared: confirm to order. The agent prepares the order, a person confirms it (F-10): a role this "
        "approval already names confirms."
    )
    assert order.status_sentence == (
        "Confirmed by Finance (demo) (finance): ordered for €700.00 net."
    )


def test_only_the_roles_the_profile_lists_for_the_approver_are_signed(
    book, samples, agent_hotel: Identity, approver_finance: Identity
) -> None:
    both_in_token = samples.approver("human:hotel-purchasing", "hotel-kitchen", PURCHASING, FINANCE)
    pending = _pending(book, samples, agent_hotel, samples.above_daily_limit())

    order = book.service.decide(pending.approval_id, both_in_token, samples.approve())

    approval = _approval(book, order)
    assert order.status is OrderStatus.PENDING_APPROVAL
    assert approval.decisions[0].roles == (PURCHASING,) and approval.roles_missing == (FINANCE,)
    assert book.service.decide(pending.approval_id, approver_finance, samples.approve()).status is OrderStatus.ORDERED


def test_every_evaluation_of_the_policy_is_at_order_time_with_a_fresh_check(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity, approver_finance: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel, samples.above_daily_limit("opt_1"), samples.unconfirmed("opt_2"))
    book.service.decide(pending.approval_id, approver_finance, samples.approve())
    book.service.decide(pending.approval_id, approver_purchasing, samples.approve(option_id="opt_2"))

    assert len(book.policy.contexts) == len(book.revalidator.calls) == 3
    assert all(context.at_order_time and context.revalidation is not None for context in book.policy.contexts)
    assert all(context.day_committed_net_eur is not None for context in book.policy.contexts)


def test_a_retry_of_the_order_after_the_approver_chose_another_option_returns_that_order(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel, samples.above_order_limit("opt_1"), samples.unconfirmed("opt_2"))
    ordered = book.service.decide(pending.approval_id, approver_purchasing, samples.approve(option_id="opt_2"))

    again = book.service.place_order(pending.offer_id, "opt_1", agent_hotel, pending.idempotency_key)

    assert again == ordered and again.option_id == "opt_2" and len(book.store.list_orders()) == 1


def test_an_agent_cannot_decide_and_the_attempt_is_recorded(book, samples, agent_hotel: Identity) -> None:
    pending = _pending(book, samples, agent_hotel)

    with pytest.raises(NotAuthorised):
        book.service.decide(pending.approval_id, agent_hotel, samples.approve())

    assert book.store.get_order(pending.order_id) == pending and _approval(book, pending).decisions == ()
    assert book.event_types(pending.order_id) == ["approval.requested", "authorisation.refused"]
    refused = book.events(pending.order_id)[-1]
    assert refused.data.actor.id == agent_hotel.id and refused.data.rule_ids == ("F-06",)
    assert refused.data.approval_id == pending.approval_id and "F-06" in refused.data.sentence


def test_an_agent_on_an_approval_nobody_issued_is_refused_and_recorded_without_the_id_it_sent(
    book, samples, agent_hotel: Identity
) -> None:
    with pytest.raises(NotAuthorised):
        book.service.decide("apr_made-up <b>", agent_hotel, samples.approve())

    (refused,) = book.events()
    assert refused.type.endswith("authorisation.refused") and refused.data.approval_id is None
    assert refused.data.profile_id == "hotel-kitchen" and "made-up" not in refused.model_dump_json()


def test_the_supplier_on_an_approval_nobody_issued_is_refused_before_any_lookup(
    book, samples, supplier_reader: Identity
) -> None:
    with pytest.raises(NotAuthorised):
        book.service.decide("apr_000000000bad", supplier_reader, samples.approve())

    (refused,) = book.events()
    assert refused.type.endswith("authorisation.refused") and refused.data.profile_id is None


@pytest.mark.parametrize(
    ("caller", "reason"),
    [
        ("approver_intern", "not listed"),
        ("approver_finance", "holds none of them"),
        ("supplier_reader", "Only an approver"),
    ],
    ids=["not listed in the profile", "role not asked for", "supplier reader"],
)
def test_a_caller_who_may_not_decide_is_refused_and_the_attempt_is_recorded(
    caller: str, reason: str, book, samples, agent_hotel: Identity, request: pytest.FixtureRequest
) -> None:
    identity = request.getfixturevalue(caller)
    pending = _pending(book, samples, agent_hotel)

    for decision in (samples.approve(), samples.reject()):
        with pytest.raises(NotAuthorised):
            book.service.decide(pending.approval_id, identity, decision)

    assert book.store.get_order(pending.order_id) == pending and _approval(book, pending).decisions == ()
    assert book.event_types(pending.order_id) == [
        "approval.requested", "authorisation.refused", "authorisation.refused",
    ]
    refused = book.events(pending.order_id)[-1]
    assert refused.data.actor.id == identity.id and refused.data.rule_ids == ()
    assert reason in refused.data.facts["reason"] and reason in refused.data.sentence


def test_an_approver_who_already_gave_their_role_cannot_decide_again(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel, samples.above_daily_limit())
    book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    with pytest.raises(NotAuthorised):
        book.service.decide(pending.approval_id, approver_purchasing, samples.reject())

    assert book.store.get_order(pending.order_id).status is OrderStatus.PENDING_APPROVAL


def test_an_approval_already_decided_cannot_be_decided_again(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)
    ordered = book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    with pytest.raises(InvalidRequest) as raised:
        book.service.decide(pending.approval_id, approver_purchasing, samples.reject())

    assert f"order {pending.order_id} is already ordered" in raised.value.detail
    assert book.store.get_order(pending.order_id) == ordered


def test_a_rejection_cannot_choose_an_option(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel, samples.above_order_limit("opt_1"), samples.unconfirmed("opt_2"))

    with pytest.raises(InvalidRequest):
        book.service.decide(
            pending.approval_id, approver_purchasing, DecisionRequest(decision=DecisionKind.REJECT, option_id="opt_2")
        )

    assert book.store.get_order(pending.order_id) == pending


def test_a_price_that_changed_before_the_approval_is_offer_stale_and_the_order_keeps_waiting(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)
    book.revalidator.result = samples.price_changed()

    with pytest.raises(OfferStale) as raised:
        book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    assert raised.value.extensions["order_id"] == pending.order_id
    assert book.store.get_order(pending.order_id) == pending and _approval(book, pending).decisions == ()
    assert book.event_types(pending.order_id) == ["approval.requested", "order.not_placed"]
    assert book.events(pending.order_id)[-1].data.actor.id == approver_purchasing.id


def test_an_approval_after_the_order_by_time_expires_the_order_instead(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)
    book.clock.advance(timedelta(days=3))

    with pytest.raises(OfferExpired) as raised:
        book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    assert raised.value.extensions["order_id"] == pending.order_id
    assert book.store.get_order(pending.order_id).status is OrderStatus.EXPIRED
    assert _approval(book, pending).status is ApprovalStatus.EXPIRED and _approval(book, pending).decisions == ()
    assert book.event_types(pending.order_id) == ["approval.requested", "order.expired"]


def test_an_expired_option_cannot_be_chosen_by_an_approver_either(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    soon = samples.now + timedelta(hours=1)
    pending = _pending(
        book, samples, agent_hotel, samples.above_order_limit("opt_1"), samples.unconfirmed("opt_2", valid_until=soon)
    )
    book.clock.advance(timedelta(hours=2))

    with pytest.raises(OfferExpired):
        book.service.decide(pending.approval_id, approver_purchasing, samples.approve(option_id="opt_2"))

    assert book.store.get_order(pending.order_id) == pending
    assert book.event_types(pending.order_id) == ["approval.requested", "order.not_placed"]


def test_when_the_fresh_check_cannot_reach_the_supplier_the_approval_stays_open(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)
    book.revalidator.error = SupplierUnavailable("The Valio Aimo API did not answer.")

    with pytest.raises(SupplierUnavailable):
        book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    assert book.store.get_order(pending.order_id) == pending and _approval(book, pending).decisions == ()
    assert book.event_types(pending.order_id) == ["approval.requested", "order.not_placed"]


def test_an_approval_whose_order_is_not_in_the_book_is_not_found(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _pending(book, samples, agent_hotel)
    orphan = _approval(book, pending).model_copy(update={"approval_id": "apr_orphan000000", "order_id": "ord_gone"})
    book.store.save_approval(orphan)

    with pytest.raises(NotFound):
        book.service.decide(orphan.approval_id, approver_purchasing, samples.approve())


def test_when_only_f10_is_left_one_of_two_named_roles_completes_the_approval(
    book, samples, agent_hotel: Identity, approver_finance: Identity
) -> None:
    """Review finding P9. The approval names the purchasing manager (P-01) and finance (P-02). Finance approves
    the small option instead: no limit holds for it, only F-10 is left, and one signature of a role the approval
    names completes it. Before, both named roles still had to sign."""
    big, small = samples.above_daily_limit("opt_1"), samples.within_authority("opt_2")
    pending = _pending(book, samples, agent_hotel, big, small)
    assert _approval(book, pending).required_roles == (PURCHASING, FINANCE)

    order = book.service.decide(pending.approval_id, approver_finance, samples.approve(option_id="opt_2"))

    approval = _approval(book, order)
    assert order.status is OrderStatus.ORDERED and order.placed_by is PlacedBy.HUMAN_APPROVAL
    assert order.decision.rule_ids == ("F-10",) and order.decision.required_roles == (FINANCE,)
    assert approval.status is ApprovalStatus.APPROVED and approval.roles_missing == ()
    assert order.decision.sentence == (
        "Prepared: confirm to order. The agent prepares the order, a person confirms it (F-10): a role this "
        "approval already names confirms."
    )
    assert order.status_sentence == "Confirmed by Finance (demo) (finance): ordered for €265.00 net."
