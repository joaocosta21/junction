"""No unconfirmed alternative that costs more than the confirmed option (review P2, item W4).

An alternative whose quantity Valio does not confirm is worth a person's time only when it gives something: a lower
price, or more of what was asked. Scores on the 20% "how precisely the agent matches … with the least manual
correction". Replay over tonight's capture at the recording's own clock (Saturday 14 Nov 2026, 02:52 Helsinki time).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from tta.contracts.common import AvailabilityState, Identity, OptionKind, Unit
from tta.contracts.offer import Offer, OfferOption
from tta.offers import OfferService

DEAR_BRISKET = "467014"  # Well Beef Marbled Brisket: quantity not confirmed, €382.20 for 20 kg


def unconfirmed_options(offer: Offer) -> list[OfferOption]:
    return [
        option for option in offer.options
        if any(line.availability.state is AvailabilityState.QUANTITY_NOT_CONFIRMED for line in option.lines)
    ]


def test_an_unconfirmed_product_dearer_than_the_confirmed_option_is_not_an_alternative(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(20, Unit.KG, needed_by=None, product_type="beef"), agent_hotel)

    assert offer.options[0].kind is OptionKind.BEST_CONFIRMED
    assert offer.options[0].totals.net == Decimal("246.96")
    assert unconfirmed_options(offer) == []
    assert (
        "Request line 1: 467014, whose quantity Valio does not confirm, would cost €382.20, not less than the "
        "€246.96 of confirmed stock that covers the whole quantity, so it is not offered as an alternative."
    ) in offer.notes


def test_a_cheaper_unconfirmed_product_stays_an_alternative(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(10, needed_by=None, product_type="cream"), agent_hotel)

    (alternative,) = unconfirmed_options(offer)
    assert alternative.totals.net == Decimal("26.30")
    assert alternative.totals.net < offer.options[0].totals.net


def test_a_dearer_unconfirmed_product_stays_when_confirmed_stock_falls_short(
    build: Callable[..., Offer], price: Callable[..., Any], stock: Callable[..., Any], make_request: Callable[..., Any]
) -> None:
    """It gives the buyer more of what was asked: 100 L against the 40 L confirmed."""
    prices = [price("469363", "2.00"), price("464306", "3.00")]
    lines = [stock("469363", 40), stock("464306", 999999, logistic_model="Terminal")]

    offer = build(prices, lines, make_request(100))

    (alternative,) = unconfirmed_options(offer)
    assert offer.options[0].is_partial
    assert alternative.totals.net == Decimal("300.00")
