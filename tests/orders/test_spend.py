"""The day's spend per profile: ORDERED and PENDING_APPROVAL orders on the clock's current date (SPEC section 8)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from tta.contracts.common import ApproverRole, Identity, OrderStatus, Verdict
from tta.offers.deps import spend_parts
from tta.orders import day_committed_net_eur
from tta.orders.spend import day_spend


def _place(book, agent: Identity, option, key: str, profile_id: str = "hotel-kitchen"):
    offer = book.offer(option, profile_id=profile_id)
    return book.service.place_order(offer.offer_id, option.option_id, agent, key)


def test_nothing_ordered_today_is_zero(book) -> None:
    assert day_committed_net_eur(book.store, book.clock, "hotel-kitchen") == Decimal(0)


def test_the_days_spend_counts_ordered_and_pending_orders_of_the_profile(
    book, samples, agent_hotel: Identity, agent_ward: Identity, approver_purchasing: Identity
) -> None:
    _place(book, agent_hotel, samples.within_authority(), "ordered")  # €265.00, ORDERED
    _place(book, agent_hotel, samples.above_order_limit(), "pending")  # €2,650.00, PENDING_APPROVAL
    rejected = _place(book, agent_hotel, samples.unconfirmed("opt_1"), "rejected")  # €1,010.00, then REJECTED
    book.service.decide(rejected.approval_id, approver_purchasing, samples.reject())
    _place(book, agent_ward, samples.ward_safe(), "ward", profile_id="allergy-ward")  # €428.00, another buyer

    assert day_committed_net_eur(book.store, book.clock, "hotel-kitchen") == Decimal("2915.00")
    assert book.service.day_committed_net_eur("hotel-kitchen") == Decimal("2915.00")
    assert book.service.day_committed_net_eur("allergy-ward") == Decimal("428.00")


def test_an_order_can_be_left_out_of_the_days_spend(book, samples, agent_hotel: Identity) -> None:
    _place(book, agent_hotel, samples.within_authority(), "a")
    pending = _place(book, agent_hotel, samples.above_order_limit(), "b")

    committed = day_committed_net_eur(book.store, book.clock, "hotel-kitchen", excluding_order_id=pending.order_id)

    assert committed == Decimal("265.00")


def test_an_order_of_another_day_is_not_counted(book, samples, agent_hotel: Identity) -> None:
    _place(book, agent_hotel, samples.within_authority(), "yesterday")
    book.clock.advance(timedelta(hours=22))  # Sunday 15 Nov, 00:52: a new day on the clock

    assert book.service.day_committed_net_eur("hotel-kitchen") == Decimal(0)


def test_the_day_is_the_clocks_day_whatever_offset_an_order_was_stamped_with(
    book, samples, agent_hotel: Identity
) -> None:
    order = _place(book, agent_hotel, samples.within_authority(), "a")
    from datetime import UTC  # Saturday 02:52 in Helsinki is Saturday 00:52 UTC: the same instant, the same day

    restamped = {"created_at": order.created_at.astimezone(UTC), "updated_at": order.updated_at.astimezone(UTC)}
    book.store.save_order(order.model_copy(update=restamped))

    assert book.service.day_committed_net_eur("hotel-kitchen") == Decimal("265.00")


def test_an_order_approved_on_a_later_day_is_spend_of_the_day_it_became_ordered(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _place(book, agent_hotel, samples.above_order_limit(), "a")  # Saturday 02:52, waits for a human
    assert book.service.day_committed_net_eur("hotel-kitchen") == Decimal("2650.00")
    book.clock.advance(timedelta(hours=22))  # Sunday 00:52

    assert book.service.day_committed_net_eur("hotel-kitchen") == Decimal(0)  # it waits since Saturday

    ordered = book.service.decide(pending.approval_id, approver_purchasing, samples.approve())

    assert ordered.status is OrderStatus.ORDERED and ordered.created_at == samples.now
    assert book.service.day_committed_net_eur("hotel-kitchen") == Decimal("2650.00")  # ordered on Sunday


def test_the_next_order_of_that_day_meets_the_limit_per_day_with_the_order_approved_that_day(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _place(book, agent_hotel, samples.above_order_limit(), "a")  # created on Saturday
    book.clock.advance(timedelta(hours=22))
    book.service.decide(pending.approval_id, approver_purchasing, samples.approve())  # ORDERED on Sunday

    second = _place(book, agent_hotel, samples.option("opt_1", (samples.line("463380", "250", "2.80"),)), "b")

    assert book.policy.contexts[-1].day_committed_net_eur == Decimal("2650.00")
    assert second.decision.rule_ids == ("P-02",)  # €700.00 more is above €3,000 on Sunday


def test_an_order_that_became_ordered_yesterday_is_not_spend_of_today(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    pending = _place(book, agent_hotel, samples.above_order_limit(), "a")
    book.service.decide(pending.approval_id, approver_purchasing, samples.approve())  # ORDERED on Saturday
    book.clock.advance(timedelta(hours=22))

    assert book.service.day_committed_net_eur("hotel-kitchen") == Decimal(0)


def test_a_pending_order_past_its_order_by_time_no_longer_counts_even_before_it_is_read(
    book, samples, agent_hotel: Identity
) -> None:
    soon = samples.now + timedelta(hours=1)
    pending = _place(book, agent_hotel, samples.above_order_limit(valid_until=soon), "a")
    book.clock.advance(timedelta(hours=2))

    assert book.service.day_committed_net_eur("hotel-kitchen") == Decimal(0)
    assert book.store.get_order(pending.order_id).status is OrderStatus.PENDING_APPROVAL  # a read that writes nothing


def test_the_second_order_of_the_day_crosses_the_daily_limit_and_goes_to_finance_by_p02(
    book, samples, agent_hotel: Identity
) -> None:
    first = _place(book, agent_hotel, samples.above_order_limit(), "first")  # €2,650.00 of €3,000 a day
    within_order_limit = samples.option("opt_1", (samples.line("463380", "250", "2.80"),))  # €700.00

    second = _place(book, agent_hotel, within_order_limit, "second")

    assert first.decision.rule_ids == ("P-01",)
    assert second.status is OrderStatus.PENDING_APPROVAL
    assert second.decision.verdict is Verdict.APPROVAL and second.decision.rule_ids == ("P-02",)
    assert second.decision.required_roles == (ApproverRole.FINANCE,)
    assert book.policy.contexts[-1].day_committed_net_eur == Decimal("2650.00")
    assert book.store.get_approval(second.approval_id).required_roles == (ApproverRole.FINANCE,)


# --- what is ordered and what is waiting (review A4, finding H2; PLAN decision 9) ---------------------------


def test_the_days_spend_is_split_into_what_is_ordered_and_what_is_waiting(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    approved = _place(book, agent_hotel, samples.within_authority(), "ordered")  # €265.00, approved below
    book.service.decide(approved.approval_id, approver_purchasing, samples.approve())
    waiting = _place(book, agent_hotel, samples.above_order_limit(), "pending")  # €2,650.00, PENDING_APPROVAL

    day = day_spend(book.store, book.clock, "hotel-kitchen")
    without = day_spend(book.store, book.clock, "hotel-kitchen", excluding_order_id=waiting.order_id)

    assert (day.ordered, day.waiting, day.committed) == (Decimal("265.00"), Decimal("2650.00"), Decimal("2915.00"))
    assert (without.ordered, without.waiting) == (Decimal("265.00"), Decimal(0))
    assert day.committed == day_committed_net_eur(book.store, book.clock, "hotel-kitchen")
    assert day.sentence == (
        "Before this order, today's spend of this buyer is €2,915.00 before tax: €265.00 ordered and €2,650.00 "
        "waiting for approval. A waiting order counts until a person rejects it or its time to decide passes."
    )


def test_the_days_spend_is_what_the_offer_takes_in_its_two_parts(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    """`OfferDeps.day_spend` may answer a `DaySpend`: the offer reads its total and its waiting part, and rule
    P-02's sentence then says both (`tta.offers.deps.spend_parts`)."""
    approved = _place(book, agent_hotel, samples.within_authority(), "ordered")  # €265.00, approved below
    book.service.decide(approved.approval_id, approver_purchasing, samples.approve())
    _place(book, agent_hotel, samples.above_order_limit(), "pending")  # €2,650.00, PENDING_APPROVAL

    day = day_spend(book.store, book.clock, "hotel-kitchen")

    assert spend_parts(day) == (Decimal("2915.00"), Decimal("2650.00"))
    assert spend_parts(day.committed) == (Decimal("2915.00"), None)  # one figure, as before: the total only


def test_an_order_sent_to_finance_for_the_day_says_how_much_is_ordered_and_how_much_is_waiting(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    """The review's case: nothing was ordered, the day was full of orders nobody had approved, and the sentence
    only said "today's spend would reach"."""
    first = _place(book, agent_hotel, samples.above_order_limit(), "first")  # €2,650.00, waits (P-01)
    second = _place(book, agent_hotel, samples.option("opt_1", (samples.line("463380", "250", "2.80"),)), "second")

    reasons = book.store.get_approval(second.approval_id).reasons
    assert second.decision.rule_ids == ("P-02",) and len(reasons) == 2
    assert reasons[1] == (
        "Before this order, today's spend of this buyer is €2,650.00 before tax: €0.00 ordered and €2,650.00 "
        "waiting for approval. A waiting order counts until a person rejects it or its time to decide passes."
    )
    # An order the day's limit does not hold back says nothing about the day.
    assert all("today's spend of this buyer" not in reason for reason in book.store.get_approval(
        first.approval_id).reasons)


def test_once_the_waiting_order_is_rejected_the_next_order_of_the_day_no_longer_goes_to_finance(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    first = _place(book, agent_hotel, samples.above_order_limit(), "first")
    book.service.decide(first.approval_id, approver_purchasing, samples.reject())

    second = _place(book, agent_hotel, samples.option("opt_1", (samples.line("463380", "250", "2.80"),)), "second")

    assert "P-02" not in second.decision.rule_ids
    assert book.policy.contexts[-1].day_committed_net_eur == Decimal(0)
