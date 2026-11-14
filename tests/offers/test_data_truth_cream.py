""""10 L cream" is cream: the vegetable-fat blends of category 10401 are their own type (FIX-12a).

Before this fix the offer picked 463975, "Arla Pro Ruoka 1 L 15% lactose free vegetable mix"
(AIMO/USE-CASES.md, use case 1).
"""

from __future__ import annotations

from collections.abc import Callable

from tta.contracts.common import Identity, Unit
from tta.offers import OfferService

# Category 10401; the three Rama Professional products name vegetable oils in their Finnish ingredient lists.
VEGETABLE_FAT_BLENDS = {"462703", "463254", "463299", "463975", "469160", "469162", "467142", "467173", "467297"}
Build = Callable[..., object]


def test_ten_litres_of_cream_offers_no_vegetable_fat_blend(
    service: OfferService, make_request: Build, agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(10, Unit.L, product_type="cream", text="10 L cream"), agent_hotel)

    offered = {line.product_id for option in offer.options for line in option.lines}
    looked_at = offered | {exclusion.product_id for exclusion in offer.excluded}
    assert offer.options
    assert not offered & VEGETABLE_FAT_BLENDS
    assert not looked_at & VEGETABLE_FAT_BLENDS


def test_a_buyer_who_wants_a_blend_asks_for_vegetable_cream(
    service: OfferService, make_request: Build, agent_hotel: Identity
) -> None:
    request = make_request(10, Unit.L, product_type="vegetable_cream", text="10 L cooking cream alternative")

    offer = service.build_offer(request, agent_hotel)

    looked_at = {line.product_id for option in offer.options for line in option.lines}
    looked_at |= {exclusion.product_id for exclusion in offer.excluded}
    assert looked_at <= VEGETABLE_FAT_BLENDS
