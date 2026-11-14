"""The pack for a small need (lane FC2, found by the chocolate-cake lane): among the products that pass every
check and cover the line, the one with the lowest total for the quantity asked comes first, whole packs counted;
the price per kilogram or litre only breaks a tie. The same rule for confirmed stock and for a product whose
quantity Valio does not confirm. Hand-built answers over the real catalog."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import Identity, OptionKind, Unit
from tta.contracts.offer import Offer, OfferOption
from tta.offers import OfferDeps, OfferService

SACK, HALF_KILO = "460460", "461329"  # granulated sugar: a 25 kg sack and a 500 g pack
PLACEHOLDER = 999_999  # the amount Valio reports when it does not know the stock
MILK, CHEAP_MILK = "469363", "464306"  # lactose-free milks, 1 litre each: scenario 1's two


@pytest.fixture
def serve(fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps]) -> Callable[..., OfferService]:
    def build(prices: Any, lines: Any) -> OfferService:
        return OfferService(deps_for(fake_gateway(prices, lines)))

    return build


def of_kind(offer: Offer, kind: OptionKind) -> OfferOption:
    return next(option for option in offer.options if option.kind is kind)


def sugar(price: Any) -> list[Any]:
    # The recorded prices: €24.27 the sack (€0.97 per kg) and €1.98 the pack (€3.96 per kg).
    return [
        price(SACK, "24.27", per_measure="0.9708", measure="KG"),
        price(HALF_KILO, "1.98", per_measure="3.96", measure="KG"),
    ]


def test_an_unconfirmed_alternative_for_a_small_need_is_the_pack_with_the_lowest_total(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    # 0.4 kg of sugar for a cake of 20 servings. Before: the 25 kg sack, €24.27, because it is cheaper per kg.
    service = serve(sugar(price), [stock(SACK, PLACEHOLDER), stock(HALF_KILO, PLACEHOLDER)])

    offer = service.build_offer(make_request("0.4", Unit.KG, product_ids=(SACK, HALF_KILO)), agent_hotel)

    (line,) = of_kind(offer, OptionKind.ALTERNATIVE_UNCONFIRMED).lines
    assert (line.product_id, line.quantity, line.net) == (HALF_KILO, 1, Decimal("1.98"))


def test_confirmed_stock_follows_the_same_rule(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve(sugar(price), [stock(SACK, 40), stock(HALF_KILO, 40)])

    offer = service.build_offer(make_request("0.4", Unit.KG, product_ids=(SACK, HALF_KILO)), agent_hotel)

    (line,) = of_kind(offer, OptionKind.BEST_CONFIRMED).lines
    assert (line.product_id, line.quantity, line.net) == (HALF_KILO, 1, Decimal("1.98"))


@pytest.mark.parametrize("state", [PLACEHOLDER, 40], ids=["quantity not confirmed", "confirmed"])
def test_for_a_large_need_the_lowest_total_is_the_sack(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity, state: int
) -> None:
    # 20 kg: one sack at €24.27 against 40 packs at €79.20. Whole packs are counted.
    service = serve(sugar(price), [stock(SACK, state), stock(HALF_KILO, state)])

    offer = service.build_offer(make_request(20, Unit.KG, product_ids=(SACK, HALF_KILO)), agent_hotel)

    kind = OptionKind.BEST_CONFIRMED if state == 40 else OptionKind.ALTERNATIVE_UNCONFIRMED  # noqa: PLR2004
    (line,) = of_kind(offer, kind).lines
    assert (line.product_id, line.quantity, line.net) == (SACK, 1, Decimal("24.27"))


def test_the_price_per_unit_breaks_a_tie_of_totals(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    # Both cost €2.00 for 0.4 kg: one sack or one pack. The sack holds more for the money.
    service = serve(
        [
            price(SACK, "2.00", per_measure="0.08", measure="KG"),
            price(HALF_KILO, "2.00", per_measure="4", measure="KG"),
        ],
        [stock(SACK, PLACEHOLDER), stock(HALF_KILO, PLACEHOLDER)],
    )

    offer = service.build_offer(make_request("0.4", Unit.KG, product_ids=(SACK, HALF_KILO)), agent_hotel)

    assert of_kind(offer, OptionKind.ALTERNATIVE_UNCONFIRMED).lines[0].product_id == SACK


def test_scenario_1s_alternative_is_unchanged_for_1000_litres(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    # The recording, its own clock. For a large quantity of equal packs the lowest total and the lowest price
    # per litre agree: 1,000 of 464306 at €1.01.
    offer = service.build_offer(make_request(1000), agent_hotel)

    best, alternative = of_kind(offer, OptionKind.BEST_CONFIRMED), of_kind(offer, OptionKind.ALTERNATIVE_UNCONFIRMED)
    assert (best.coverage[0].covered, str(best.totals.net)) == (435, "1083.39")
    assert [(line.product_id, line.quantity) for line in alternative.lines] == [(CHEAP_MILK, 1000)]
    assert str(alternative.totals.net) == "1010.00"
