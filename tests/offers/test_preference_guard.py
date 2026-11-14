"""A preference has a price and a floor (review A2b, finding H2; review P2, item W6).

Before, "most reliable" bought any product with a reliability figure over a cheaper one with none, at any price:
a tenderloin with a delivery reliability of 52.4% replaced a flank at 3.8 times the price. Now a figure below the
floor ranks with an unknown one, the premium is stated as a share, and a preferred option that costs more than the
premium a preference may cost comes second, after the cheapest confirmed one. Both thresholds are ours.
Scores on the 20% "how precisely the agent matches what the buyer actually asked for".
Replay over tonight's capture at the recording's own clock (Saturday 14 Nov 2026, 02:52 Helsinki time).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import Identity, OptionKind, Preference, Unit
from tta.contracts.offer import Offer
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers import OfferService
from tta.offers.preference import MAX_PREFERENCE_PREMIUM, RELIABILITY_FLOOR

TENDERLOIN = "463053"  # delivery reliability 0.524, €931.35 for 20 kg
FLANK = "466952"  # no reliability figure, €246.96 for 20 kg
RELIABLE_CREAM, CHEAP_CREAM = "464727", "463797"  # reliability 1.0 at €7.37 per litre; none at €3.31


def by_reliability(quantity: int, unit: Unit, **line: Any) -> PurchaseRequest:
    return PurchaseRequest(
        prefer=Preference.RELIABILITY,
        lines=(RequestLine(text="a test request", quantity=Decimal(quantity), unit=unit, **line),),
    )


@pytest.fixture(scope="module")
def beef(service: OfferService, agent_hotel: Identity) -> Offer:
    return service.build_offer(by_reliability(20, Unit.KG, product_type="beef"), agent_hotel)


@pytest.fixture(scope="module")
def cream(service: OfferService, agent_hotel: Identity) -> Offer:
    return service.build_offer(by_reliability(10, Unit.L, product_type="cream"), agent_hotel)


def test_the_thresholds_are_named_constants() -> None:
    assert (str(RELIABILITY_FLOOR), str(MAX_PREFERENCE_PREMIUM)) == ("0.9", "0.25")


def test_a_known_low_reliability_does_not_beat_an_unknown_one(beef: Offer) -> None:
    first = beef.options[0]

    assert TENDERLOIN not in first.product_ids
    assert first.product_ids == (FLANK,)
    assert first.totals.net == Decimal("246.96")
    assert not any("52.4%" in option.summary for option in beef.options)


def test_the_option_says_that_no_product_reaches_the_floor(beef: Offer) -> None:
    assert (
        "No delivery reliability of 90% or more in Valio Aimo's data for this product; a lower figure ranks with an "
        "unknown one (our threshold)."
    ) in beef.options[0].summary


def test_a_preferred_option_above_the_premium_comes_second(cream: Offer) -> None:
    first, second = cream.options[:2]

    assert (first.kind, first.product_ids, first.totals.net) == (
        OptionKind.CHEAPEST_CONFIRMED, (CHEAP_CREAM,), Decimal("33.10")
    )
    assert (second.kind, second.product_ids, second.totals.net) == (
        OptionKind.BEST_CONFIRMED, (RELIABLE_CREAM,), Decimal("73.70")
    )
    assert (first.rank, second.rank) == (1, 2)


def test_the_gap_is_stated_as_an_amount_and_as_a_share(cream: Offer) -> None:
    first, second = cream.options[:2]

    assert (
        "€40.60 more than the cheapest confirmed option, for a delivery reliability of at least 100% instead of "
        "unknown, a premium of 122.7%."
    ) in second.summary
    assert second.net_above_cheapest == Decimal("40.60")
    assert (
        "Suggested first: the option ranked by delivery reliability costs €40.60 more, a premium of 122.7%, above "
        "the 25% a preference may add before the cheapest option comes first (our threshold)."
    ) in first.summary
    assert second.title == "Confirmed option ranked by delivery reliability"


def test_a_small_premium_keeps_the_preferred_option_first(service: OfferService, agent_hotel: Identity) -> None:
    request = by_reliability(100, Unit.L, product_type="plant_drink", name_terms=("oat",))

    offer = service.build_offer(request, agent_hotel)

    first, second = offer.options[:2]
    assert (first.kind, first.totals.net) == (OptionKind.BEST_CONFIRMED, Decimal("140.00"))
    assert (second.kind, second.totals.net) == (OptionKind.CHEAPEST_CONFIRMED, Decimal("133.00"))
    assert "€7.00 more than the cheapest confirmed option" in first.summary
    assert "a premium of 5.3%." in first.summary
    assert first.net_above_cheapest == Decimal("7.00")
