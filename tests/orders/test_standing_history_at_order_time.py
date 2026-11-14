"""At order time and when an approver decides, the policy reads the history of the standing order the offer's
request renews (rule P-08, task STAND-1), without the renewal being decided. A request that renews nothing carries
no history, and that is never a missing fact."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from tta.contracts.audit import AuditEventType
from tta.contracts.common import Identity, Unit
from tta.contracts.errors import InvalidRequest
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.contracts.standing import Renewal, RenewalLine, StandingOrder

STANDING_ID = "so_milk"


def _standing(book) -> StandingOrder:
    request = PurchaseRequest(lines=(RequestLine(text="100 L of milk", quantity=Decimal(100), unit=Unit.L),))
    standing = StandingOrder(
        standing_order_id=STANDING_ID, profile_id="hotel-kitchen", agent_id="agent:hotel-kitchen", name="Milk",
        request=request, created_at=book.clock.now(),
    )
    book.store.save_standing_order(standing)
    for week in range(3):
        line = RenewalLine(request_line_index=0, product_id="463380", quantity=Decimal(100), unit=Unit.L,
                           unit_net_price_eur=Decimal("2.65"))
        book.store.save_renewal(Renewal(
            renewal_id=f"ren_{week}", standing_order_id=STANDING_ID,
            renewed_at=book.clock.now() - timedelta(weeks=3 - week), lines=(line,), synthetic=True,
        ))
    return standing


def _renewing(book, offer):
    renewing = offer.model_copy(update={"request": offer.request.model_copy(update={"standing_order_id": STANDING_ID})})
    book.store.save_offer(renewing)
    return renewing


def test_an_offer_that_renews_nothing_reaches_the_policy_with_no_history(book, samples, agent_hotel: Identity) -> None:
    offer = book.offer(samples.within_authority())

    book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")

    assert book.policy.contexts[-1].standing_history is None


def test_an_offer_that_renews_a_standing_order_reaches_the_policy_with_its_history(
    book, samples, agent_hotel: Identity
) -> None:
    _standing(book)
    offer = _renewing(book, book.offer(samples.within_authority()))

    book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")

    history = book.policy.contexts[-1].standing_history
    assert history is not None and history.standing_order_id == STANDING_ID
    assert [renewal.renewal_id for renewal in history.renewals] == ["ren_0", "ren_1", "ren_2"]


def test_when_an_approver_decides_the_renewal_being_decided_is_not_in_the_history(
    book, samples, agent_hotel: Identity, approver_purchasing: Identity
) -> None:
    _standing(book)
    offer = _renewing(book, book.offer(samples.above_order_limit()))
    order = book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")
    line = RenewalLine(request_line_index=0, product_id="463380", quantity=Decimal(900), unit=Unit.L,
                       unit_net_price_eur=Decimal("2.65"))
    book.store.save_renewal(Renewal(
        renewal_id="ren_this", standing_order_id=STANDING_ID, renewed_at=book.clock.now(), lines=(line,),
        offer_id=offer.offer_id, order_id=order.order_id,
    ))

    book.service.decide(order.approval_id, approver_purchasing, samples.approve())

    history = book.policy.contexts[-1].standing_history
    assert history is not None and "ren_this" not in [renewal.renewal_id for renewal in history.renewals]


def test_a_standing_order_that_is_gone_at_order_time_refuses_the_order_and_records_why(
    book, samples, agent_hotel: Identity
) -> None:
    offer = _renewing(book, book.offer(samples.within_authority()))  # names a standing order nobody set up

    with pytest.raises(InvalidRequest, match="No standing order so_milk is set up for this buyer"):
        book.service.place_order(offer.offer_id, "opt_1", agent_hotel, "key-1")

    assert book.event_types()[-1] == AuditEventType.ORDER_NOT_PLACED.value
