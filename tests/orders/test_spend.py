"""The day's spend per profile: ORDERED and PENDING_APPROVAL orders on the clock's current date (SPEC section 8)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from tta.contracts.common import ApproverRole, Identity, OrderStatus, Verdict
from tta.orders import day_committed_net_eur


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
