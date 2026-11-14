"""`place_order`: re-check, policy, then ORDERED, PENDING_APPROVAL or a typed error (SPEC section 8)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from tta.contracts.common import (
    ApprovalStatus,
    ApproverRole,
    DataSource,
    Identity,
    OrderStatus,
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
from tta.contracts.order import ORDER_RECORD_NOTE
from tta.contracts.ports import OrderService

KEY = "key-1"


def test_the_service_satisfies_the_order_service_port(book) -> None:
    assert isinstance(book.service, OrderService)


def test_an_option_within_authority_still_waits_for_human_approval(
    book, samples, agent_hotel: Identity
) -> None:
    offer = book.offer(samples.within_authority())

    order = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert order.status is OrderStatus.PENDING_APPROVAL and order.placed_by is None
    approval = book.store.get_approval(order.approval_id)
    assert approval is not None and approval.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert order.decision.verdict is Verdict.APPROVAL and order.option.decision == order.decision
    assert (order.offer_id, order.option_id, order.profile_id) == (offer.offer_id, "opt_1", "hotel-kitchen")
    assert order.agent_id == agent_hotel.id and order.idempotency_key == KEY
    assert order.order_id.startswith("ord_") and len(order.order_id) == len("ord_") + 12
    assert order.created_at == order.updated_at == book.clock.now()
    assert "F-10" in order.status_sentence
    assert book.store.get_order(order.order_id) == order
    assert book.event_types() == ["approval.requested"]


def test_the_order_record_keeps_the_statements_it_relied_on_and_says_the_mock_has_no_order_endpoint(
    book, samples, agent_hotel: Identity
) -> None:
    lines = (samples.line("463380", "60", "2.65"), samples.line("462775", "40", "2.57"))
    offer = book.offer(samples.option("opt_1", lines))

    order = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert order.record_note.startswith(ORDER_RECORD_NOTE) and "no order endpoint" in order.record_note
    # P16: one sentence on payment, the same on an order that waits and on one that is placed.
    assert order.record_note.endswith(
        "No payment is taken here: the buyer is assumed to be a Valio Aimo credit customer, invoiced after "
        "delivery for what is delivered."
    )
    assert [statement.product_id for statement in order.reliance] == ["463380", "462775"]
    first = order.reliance[0]
    assert (first.unit_net_price, first.price_valid_to) == (lines[0].unit_net_price, lines[0].price_valid_to)
    assert first.availability_state is lines[0].availability.state
    assert first.available_amount == lines[0].availability.usable_amount
    assert (first.available_date, first.closing_time) == (samples.monday, samples.order_by)
    assert first.time_now == offer.time_now and first.rechecked_at == book.clock.now()
    assert first.source is DataSource.REPLAY and order.source is DataSource.REPLAY


def test_a_statement_says_when_valio_stated_the_figures_and_when_the_re_check_found_them_still_sufficient(
    book, samples, agent_hotel: Identity
) -> None:
    offer = book.offer(samples.within_authority())
    book.clock.advance(timedelta(minutes=20))  # the agent orders 20 minutes after the offer was built

    order = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    (statement,) = order.reliance
    assert statement.time_now == offer.time_now == samples.now
    assert statement.rechecked_at == book.clock.now() == samples.now + timedelta(minutes=20)


def test_an_unconfirmed_line_is_relied_on_without_an_amount(book, samples, agent_hotel: Identity) -> None:
    offer = book.offer(samples.unconfirmed("opt_1"))

    order = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert order.reliance[0].available_amount is None


def test_an_option_above_the_limit_waits_for_the_purchasing_manager(book, samples, agent_hotel: Identity) -> None:
    offer = book.offer(samples.above_order_limit())

    order = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert order.status is OrderStatus.PENDING_APPROVAL and order.placed_by is None
    assert order.decision.verdict is Verdict.APPROVAL and order.decision.rule_ids == ("P-01",)
    approval = book.store.get_approval(order.approval_id)
    assert approval.approval_id.startswith("apr_") and len(approval.approval_id) == len("apr_") + 12
    assert approval.status is ApprovalStatus.PENDING and approval.decisions == ()
    assert (approval.order_id, approval.offer_id, approval.option_id) == (order.order_id, offer.offer_id, "opt_1")
    assert approval.required_roles == (ApproverRole.PURCHASING_MANAGER,)
    assert approval.reasons == tuple(rule.sentence for rule in order.decision.fired)
    assert approval.valid_until == samples.order_by and approval.profile_id == "hotel-kitchen"
    assert order.status_sentence == (
        "Waiting for approval by the purchasing manager, to be decided by Sunday 15 November 2026 at 17:00 "
        "(UTC+02:00): rule P-01 asks for a human."
    )
    assert book.event_types(order.order_id) == ["approval.requested"]


def test_the_policy_is_always_asked_at_order_time_with_the_fresh_check_and_the_days_spend(
    book, samples, agent_hotel: Identity
) -> None:
    offer = book.offer(samples.within_authority())

    book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    (context,) = book.policy.contexts
    assert context.at_order_time is True and context.now == book.clock.now()
    assert context.revalidation is not None and context.revalidation.ok
    assert context.day_committed_net_eur == 0
    assert [option.option_id for option in book.revalidator.calls] == ["opt_1"]


def test_a_changed_price_at_order_time_is_offer_stale_and_no_order_is_created(
    book, samples, agent_hotel: Identity
) -> None:
    offer = book.offer(samples.within_authority())
    book.revalidator.result = samples.price_changed()

    with pytest.raises(OfferStale) as raised:
        book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert "463380" in raised.value.detail and raised.value.detail.endswith("Ask for a fresh offer.")
    assert raised.value.extensions["changes"] == [{
        "product_id": "463380", "field": "price", "before": "2.65", "after": "2.80",
        "sentence": "The price of 463380 changed from €2.65 to €2.80.",
    }]
    assert (raised.value.extensions["offer_id"], raised.value.extensions["option_id"]) == (offer.offer_id, "opt_1")
    assert book.store.list_orders() == () and book.store.list_approvals() == ()
    assert book.event_types() == ["order.not_placed"]
    (event,) = book.events()
    assert event.data.offer_id == offer.offer_id and event.data.order_id is None
    assert event.data.rule_ids == ("F-04",) and event.data.actor.id == agent_hotel.id


def test_an_option_past_its_valid_until_cannot_be_ordered(book, samples, agent_hotel: Identity) -> None:
    offer = book.offer(samples.within_authority(valid_until=samples.now - timedelta(minutes=1)))

    with pytest.raises(OfferExpired) as raised:
        book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert raised.value.detail.endswith("Ask for a fresh offer.")
    assert raised.value.extensions["valid_until"] == "2026-11-14T02:51:00+02:00"
    assert book.store.list_orders() == () and book.event_types() == ["order.not_placed"]


def test_a_cut_off_that_passed_since_the_offer_is_offer_expired(book, samples, agent_hotel: Identity) -> None:
    offer = book.offer(samples.within_authority())
    book.revalidator.result = samples.cutoff_passed()

    with pytest.raises(OfferExpired):
        book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert book.store.list_orders() == () and book.event_types() == ["order.not_placed"]


@pytest.mark.parametrize(
    ("build", "profile_id", "agent", "rule_id"),
    [("ward_declares_milk", "allergy-ward", "agent_ward", "F-02"), ("adds_allergen", "hotel-kitchen", "agent_hotel",
                                                                    "F-05")],
    ids=["declares an excluded allergen", "substitute adds an allergen"],
)
def test_a_blocked_option_is_policy_blocked_with_no_order_and_one_audit_event(
    build: str, profile_id: str, agent: str, rule_id: str, book, samples, request: pytest.FixtureRequest
) -> None:
    identity = request.getfixturevalue(agent)
    offer = book.offer(getattr(samples, build)("opt_1"), profile_id=profile_id)

    with pytest.raises(PolicyBlocked) as raised:
        book.service.place_order(offer.offer_id, "opt_1", identity, KEY)

    assert raised.value.detail.startswith("This order cannot be placed, even with approval:")
    assert raised.value.extensions["rule_ids"] == [rule_id]
    assert len(raised.value.extensions["reasons"]) == 1
    assert book.store.list_orders() == () and book.store.list_approvals() == ()
    (event,) = book.events()
    assert event.type == "tta.v1.order.blocked" and event.data.rule_ids == (rule_id,)
    assert event.data.offer_id == offer.offer_id and event.data.profile_id == profile_id


def test_a_ward_order_with_every_excluded_allergen_stated_free_from_is_placed_by_the_agent(
    book, samples, agent_ward: Identity
) -> None:
    offer = book.offer(samples.ward_safe(), profile_id="allergy-ward")

    order = book.service.place_order(offer.offer_id, "opt_1", agent_ward, KEY)

    assert order.status is OrderStatus.PENDING_APPROVAL and order.profile_id == "allergy-ward"


def test_the_same_key_twice_returns_the_first_order_and_creates_nothing(book, samples, agent_hotel: Identity) -> None:
    offer = book.offer(samples.above_order_limit())
    first = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    second = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert second == first
    assert len(book.store.list_orders()) == 1 and len(book.store.list_approvals()) == 1
    assert len(book.revalidator.calls) == 1 and book.event_types() == ["approval.requested"]


def test_another_key_on_another_offer_places_another_order(book, samples, agent_hotel: Identity) -> None:
    offers = (book.offer(samples.within_authority()), book.offer(samples.within_authority()))

    first = book.service.place_order(offers[0].offer_id, "opt_1", agent_hotel, "key-1")
    second = book.service.place_order(offers[1].offer_id, "opt_1", agent_hotel, "key-2")

    assert first.order_id != second.order_id and len(book.store.list_orders()) == 2


def test_the_same_key_for_another_option_or_offer_is_refused_and_does_not_return_the_first_order(
    book, samples, agent_hotel: Identity
) -> None:
    offer = book.offer(samples.within_authority("opt_1"), samples.unconfirmed("opt_2"))
    other = book.offer(samples.within_authority("opt_1"))
    first = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    for offer_id, option_id in ((offer.offer_id, "opt_2"), (other.offer_id, "opt_1")):
        with pytest.raises(InvalidRequest) as raised:
            book.service.place_order(offer_id, option_id, agent_hotel, KEY)
        assert "already used for another order" in raised.value.detail

    assert book.store.list_orders() == (first,) and len(book.revalidator.calls) == 1


def test_a_key_belongs_to_the_agent_that_sent_it(book, samples, agent_hotel: Identity, agent_ward: Identity) -> None:
    hotel_offer = book.offer(samples.within_authority())
    ward_offer = book.offer(samples.ward_safe(), profile_id="allergy-ward")

    hotel_order = book.service.place_order(hotel_offer.offer_id, "opt_1", agent_hotel, KEY)
    ward_order = book.service.place_order(ward_offer.offer_id, "opt_1", agent_ward, KEY)

    assert hotel_order.order_id != ward_order.order_id and ward_order.profile_id == "allergy-ward"


def test_a_key_is_free_again_after_an_attempt_that_placed_nothing(book, samples, agent_hotel: Identity) -> None:
    offer = book.offer(samples.within_authority())
    book.revalidator.result = samples.price_changed()
    with pytest.raises(OfferStale):
        book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)
    book.revalidator.result = None

    order = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert order.status is OrderStatus.PENDING_APPROVAL and book.store.list_orders() == (order,)


@pytest.mark.parametrize("key", ["", "   "])
def test_a_blank_idempotency_key_is_invalid(key: str, book, samples, agent_hotel: Identity) -> None:
    offer = book.offer(samples.within_authority())

    with pytest.raises(InvalidRequest):
        book.service.place_order(offer.offer_id, "opt_1", agent_hotel, key)

    assert book.store.list_orders() == () and book.revalidator.calls == []


@pytest.mark.parametrize("caller", ["approver_purchasing", "supplier_reader"])
def test_only_an_agent_may_place_an_order(caller: str, book, samples, request: pytest.FixtureRequest) -> None:
    offer = book.offer(samples.within_authority())

    with pytest.raises(NotAuthorised):
        book.service.place_order(offer.offer_id, "opt_1", request.getfixturevalue(caller), KEY)

    assert book.store.list_orders() == () and book.revalidator.calls == []


def test_an_offer_made_for_another_buyer_is_answered_like_an_offer_nobody_issued(
    book, samples, agent_ward: Identity
) -> None:
    offer = book.offer(samples.within_authority(), profile_id="hotel-kitchen")

    with pytest.raises(NotFound) as of_another_buyer:
        book.service.place_order(offer.offer_id, "opt_1", agent_ward, KEY)
    with pytest.raises(NotFound) as unknown:
        book.service.place_order("off_000000000bad", "opt_1", agent_ward, KEY)

    assert of_another_buyer.value.to_problem() == unknown.value.to_problem()
    assert book.store.list_orders() == () and book.revalidator.calls == [] and book.events() == ()


def test_an_offer_or_option_nobody_issued_is_not_found(book, samples, agent_hotel: Identity) -> None:
    offer = book.offer(samples.within_authority())

    with pytest.raises(NotFound):
        book.service.place_order("off_000000000bad", "opt_1", agent_hotel, KEY)
    with pytest.raises(NotFound):
        book.service.place_order(offer.offer_id, "opt_9", agent_hotel, KEY)

    assert book.store.list_orders() == () and book.events() == ()


def test_when_the_fresh_check_cannot_reach_the_supplier_nothing_is_ordered_and_the_attempt_is_recorded(
    book, samples, agent_hotel: Identity
) -> None:
    offer = book.offer(samples.within_authority())
    book.revalidator.error = SupplierUnavailable("The Valio Aimo API did not answer.")

    with pytest.raises(SupplierUnavailable):
        book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert book.store.list_orders() == () and book.event_types() == ["order.not_placed"]
    assert book.policy.contexts == []
    assert book.events()[0].data.facts["error_type"] == "SupplierUnavailable"


@pytest.mark.parametrize("failing", ["revalidator", "policy"], ids=["the fresh look fails", "the policy fails"])
def test_any_failure_of_the_check_is_recorded_by_its_type_only_and_reaches_the_caller(
    failing: str, book, samples, agent_hotel: Identity
) -> None:
    offer = book.offer(samples.within_authority())
    failure = RuntimeError("a text that must stay out of the trail")
    getattr(book, failing).error = failure

    with pytest.raises(RuntimeError) as raised:
        book.service.place_order(offer.offer_id, "opt_1", agent_hotel, KEY)

    assert raised.value is failure
    assert book.store.list_orders() == () and book.store.order_id_for_key(KEY, agent_hotel.id) is None
    (event,) = book.events()
    assert event.type == "tta.v1.order.not_placed" and event.data.facts["error_type"] == "RuntimeError"
    assert "must stay out" not in event.model_dump_json()
    assert (event.data.offer_id, event.data.actor.id) == (offer.offer_id, agent_hotel.id)
    assert event.data.rule_ids == () and "decision" not in event.data.facts
