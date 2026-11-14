"""A buyer's preference ranks the confirmed option; the cheapest confirmed one stays on the table (task SUST-1).

Scores on the brief's optional direction "Delivery time & sustainability comparison: not just price, but delivery
reliability and the certificates/sustainability labels" and on the 20% "how precisely the agent matches what the
buyer actually asked for". Replay over tonight's capture, or hand-built prices and stock over the real catalog.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import Identity, OptionKind, Preference, Unit
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers import OfferService

MONDAY = date(2026, 11, 16)
TUESDAY = date(2026, 11, 17)
OAT_TEXT = "100 litres of oat drink by Monday, most reliable delivery"
RELIABLE_OAT = "470863"  # Oatly Oat Drink Semi 1L: €1.40, delivery reliability 1.0, 1,414 confirmed
CHEAP_OAT = "472145"  # Oatly No Sugars Oat Drink 1L: €1.33, no reliability value, 131 confirmed
MILK_A, MILK_B = "469363", "462775"  # lactose-free milks of category 10400, carbon 1.1 kg CO2e per kg
SOYA = "464013"  # Alpro No Sugars Soya drink 1L, category 10402: carbon 0.435, reliability 1.0
SOYA_ORIGINAL = "460509"  # Alpro Soya drink, Original 1L: reliability 0.967


def oat_request(prefer: Preference = Preference.PRICE) -> PurchaseRequest:
    return PurchaseRequest(
        needed_by=MONDAY,
        prefer=prefer,
        lines=(RequestLine(
            text=OAT_TEXT, product_type="plant_drink", name_terms=("oat",), quantity=Decimal(100), unit=Unit.L,
        ),),
    )


def kinds(offer: Offer) -> list[OptionKind]:
    return [option.kind for option in offer.options]


@pytest.fixture(scope="module")
def by_price(service: OfferService, agent_hotel: Identity) -> Offer:
    return service.build_offer(oat_request(), agent_hotel)


@pytest.fixture(scope="module")
def by_reliability(service: OfferService, agent_hotel: Identity) -> Offer:
    return service.build_offer(oat_request(Preference.RELIABILITY), agent_hotel)


def test_by_price_the_cheapest_oat_drink_is_first_and_there_is_no_cheapest_option(by_price: Offer) -> None:
    first = by_price.options[0]

    assert first.kind is OptionKind.BEST_CONFIRMED
    assert first.product_ids == (CHEAP_OAT,)
    assert first.totals.net == Decimal("133.00")
    assert first.title == "Best confirmed option"
    assert OptionKind.CHEAPEST_CONFIRMED not in kinds(by_price)


def test_by_reliability_the_reliable_oat_drink_is_first(by_reliability: Offer) -> None:
    first = by_reliability.options[0]

    assert first.kind is OptionKind.BEST_CONFIRMED
    assert first.product_ids == (RELIABLE_OAT,)
    assert first.totals.net == Decimal("140.00")
    assert first.title == "Best confirmed option, ranked by delivery reliability"
    assert first.lines[0].delivery_reliability == Decimal(1)


def test_the_cheapest_confirmed_option_comes_second_with_the_trade_off(by_reliability: Offer) -> None:
    first, second = by_reliability.options[:2]

    assert second.kind is OptionKind.CHEAPEST_CONFIRMED
    assert second.rank == 2
    assert second.product_ids == (CHEAP_OAT,)
    assert second.totals.net == Decimal("133.00")
    assert second.title == "Cheapest confirmed option"
    assert "€7.00 more than the cheapest confirmed option" in first.summary
    assert "delivery reliability of at least 100% instead of unknown" in first.summary
    assert "€7.00 less" in second.summary
    assert second.decision is not None


def test_a_preference_keeps_at_most_four_options(by_reliability: Offer) -> None:
    assert len(by_reliability.options) <= 4
    assert kinds(by_reliability).count(OptionKind.CHEAPEST_CONFIRMED) == 1


def test_the_comparison_of_each_option(by_reliability: Offer) -> None:
    first, second = by_reliability.options[:2]

    assert first.comparison is not None and second.comparison is not None
    assert first.comparison.earliest_delivery == first.comparison.latest_delivery == MONDAY
    assert first.comparison.lowest_reliability == Decimal(1)
    assert first.comparison.reliability_unknown_lines == 0
    assert second.comparison.lowest_reliability is None
    assert second.comparison.reliability_unknown_lines == 1
    # 100 L at 0.435 kg CO2e per kg, a litre counted as a kilogram
    assert first.comparison.carbon_kg_co2e == pytest.approx(Decimal("43.5"))
    assert "unknown for 1 line" in second.comparison.sentence


def test_price_is_the_default_and_changes_nothing(
    service: OfferService, make_request: Callable[..., PurchaseRequest], agent_hotel: Identity
) -> None:
    default = service.build_offer(make_request(1000), agent_hotel)
    by_price = service.build_offer(make_request(1000).model_copy(update={"prefer": Preference.PRICE}), agent_hotel)

    assert [(o.kind, o.product_ids, o.totals.net, o.title) for o in by_price.options] == [
        (o.kind, o.product_ids, o.totals.net, o.title) for o in default.options
    ]
    assert default.options[0].totals.net == Decimal("2580.64")


def test_a_key_no_product_has_falls_back_to_price_and_says_how_many_lines_had_no_value(
    service: OfferService, make_request: Callable[..., PurchaseRequest], agent_hotel: Identity
) -> None:
    request = make_request(1000).model_copy(update={"prefer": Preference.RELIABILITY})

    offer = service.build_offer(request, agent_hotel)
    first = offer.options[0]

    assert first.totals.net == Decimal("2580.64")
    assert first.title == "Best confirmed option, ranked by delivery reliability"
    assert "No delivery reliability in Valio Aimo's data for 3 of the 3 lines" in first.summary
    assert OptionKind.CHEAPEST_CONFIRMED not in kinds(offer)


def test_lines_carry_reliability_carbon_and_labels_from_their_product(
    service: OfferService, make_request: Callable[..., PurchaseRequest], agent_hotel: Identity
) -> None:
    first = service.build_offer(make_request(1000), agent_hotel).options[0]
    by_id = {line.product_id: line for line in first.lines}

    assert by_id[MILK_A].delivery_reliability is None
    assert by_id[MILK_A].carbon_kg_co2e_per_kg == Decimal("1.1")
    assert by_id[MILK_A].labels == ("GOODS_FROM_FINLAND_BLUE_SWAN",)
    assert by_id[MILK_B].labels == ("FINNISH_HEART_SYMBOL", "GOODS_FROM_FINLAND_BLUE_SWAN")
    assert first.comparison is not None
    assert first.comparison.labels_on_every_line == ("GOODS_FROM_FINLAND_BLUE_SWAN",)
    assert first.comparison.carbon_kg_co2e == pytest.approx(Decimal("1100"))


def test_earliest_takes_the_earlier_delivery_date_first(
    build: Callable[..., Offer], price: Any, stock: Any, make_request: Callable[..., PurchaseRequest]
) -> None:
    prices = [price(MILK_A, "2.48"), price(MILK_B, "2.57")]
    lines = [stock(MILK_A, 500, available_date=TUESDAY), stock(MILK_B, 500, available_date=MONDAY)]
    request = make_request(30, needed_by=None).model_copy(update={"prefer": Preference.EARLIEST})

    offer = build(prices, lines, request)
    first, second = offer.options[:2]

    assert first.product_ids == (MILK_B,)
    assert first.title == "Best confirmed option, ranked by earliest delivery"
    assert second.kind is OptionKind.CHEAPEST_CONFIRMED
    assert second.product_ids == (MILK_A,)
    assert "€2.70 more than the cheapest confirmed option, for delivery by Monday 16 Nov instead of Tuesday 17 Nov" in (
        first.summary
    )


def test_lower_carbon_takes_the_lower_footprint_first(
    build: Callable[..., Offer], price: Any, stock: Any, make_request: Callable[..., PurchaseRequest]
) -> None:
    prices = [price(MILK_A, "2.48"), price(SOYA, "2.60")]
    lines = [stock(MILK_A, 500), stock(SOYA, 500)]
    request = make_request(50, product_ids=(MILK_A, SOYA)).model_copy(update={"prefer": Preference.LOWER_CARBON})

    offer = build(prices, lines, request)
    first, second = offer.options[:2]

    assert first.product_ids == (SOYA,)
    assert first.title == "Best confirmed option, ranked by lowest carbon footprint"
    assert second.product_ids == (MILK_A,)
    assert first.comparison is not None and second.comparison is not None
    assert first.comparison.carbon_kg_co2e == pytest.approx(Decimal("21.75"))
    assert second.comparison.carbon_kg_co2e == pytest.approx(Decimal("55"))
    assert "for about 21.75 kg CO2e instead of about 55 kg CO2e" in first.summary


def test_no_cheapest_option_when_the_preferred_one_costs_the_same(
    build: Callable[..., Offer], price: Any, stock: Any, make_request: Callable[..., PurchaseRequest]
) -> None:
    prices = [price(SOYA, "2.01"), price(SOYA_ORIGINAL, "2.01")]
    lines = [stock(SOYA, 500), stock(SOYA_ORIGINAL, 500)]
    by_price = make_request(100, product_ids=(SOYA, SOYA_ORIGINAL))
    by_reliability = by_price.model_copy(update={"prefer": Preference.RELIABILITY})

    cheapest_first = build(prices, lines, by_price).options[0]
    preferred = build(prices, lines, by_reliability)

    assert cheapest_first.product_ids == (SOYA_ORIGINAL,)
    assert preferred.options[0].product_ids == (SOYA,)
    assert OptionKind.CHEAPEST_CONFIRMED not in kinds(preferred)


def test_between_options_that_fit_alike_the_preferred_one_is_on_top(by_reliability: Offer) -> None:
    top: OfferOption = by_reliability.options[0]

    assert top.kind is OptionKind.BEST_CONFIRMED
    assert all(option.rank > top.rank for option in by_reliability.options[1:])


def test_a_preference_never_outranks_a_constraint_the_preferred_pick_misses(
    build: Callable[..., Offer], price: Any, stock: Any, make_request: Callable[..., PurchaseRequest]
) -> None:
    """The buyer names two products and requires the organic label: the reliable one lacks it, so the cheaper
    organic one, which meets every constraint, is first."""
    organic = "460825"  # carries EU_ORGANIC_FARMING, no reliability value
    prices = [price(RELIABLE_OAT, "1.40"), price(organic, "1.30")]
    lines = [stock(RELIABLE_OAT, 500), stock(organic, 500)]
    request = make_request(
        100, product_ids=(RELIABLE_OAT, organic), required_labels=("EU_ORGANIC_FARMING",)
    ).model_copy(update={"prefer": Preference.RELIABILITY})

    first, second = build(prices, lines, request).options[:2]

    assert (first.kind, first.product_ids) == (OptionKind.CHEAPEST_CONFIRMED, (organic,))
    assert (second.kind, second.product_ids) == (OptionKind.BEST_CONFIRMED, (RELIABLE_OAT,))
    assert "€10.00 more than the cheapest confirmed option" in second.summary
