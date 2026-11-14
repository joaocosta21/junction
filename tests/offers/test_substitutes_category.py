"""P7-1: a category number is opaque. Unlisted candidates come from the same 5-digit category and nowhere else.

Valio's answer V7 (14 Nov 2026): nobody confirmed that the digits of a category number are levels. Before this
change the search widened to the first 4 and the first 3 digits: coconut cream stood in for milk powder.
All figures: the capture of 14 Nov (769 products), default clock, read offline.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.contracts.common import Identity
from tta.contracts.offer import SubstituteQuery
from tta.offers import OfferDeps, OfferService, find_substitutes
from tta.offers import substitutes as substitutes_module
from tta.offers.substitutes import substitute_distance

MILK_POWDER = "469148"  # category 10405, 14 products: before, rank 1 was 464217 Spice Up! Coconut cream (10401)
PLANT_COOKING = "467622"  # category 10404: before, rank 1 was 465122 AIMO crème fraîche 28% (first 4 digits)
SOFT_SERVE = "471582"  # category 10432: before, rank 1 was an oat drink (first 3 digits)
YOGHURT = "460700"  # for the ward: before, a plant cream and a rice drink were offered for a yoghurt
THIN = (MILK_POWDER, PLANT_COOKING, SOFT_SERVE, "472516", "469216", "465122")


@pytest.mark.parametrize("product_id", THIN)
def test_the_hotel_gets_no_unlisted_candidate_of_another_category(
    service: OfferService, catalog: ProductCatalog, agent_hotel: Identity, product_id: str
) -> None:
    original = catalog.get_product(product_id)

    result = service.find_substitutes(product_id, agent_hotel, SubstituteQuery(needed_by=date(2026, 11, 16)))

    for candidate in result.candidates:
        other = catalog.get_product(candidate.product_id)
        if not candidate.listed_by_supplier:
            assert other.category == original.category, candidate.product_id
            assert candidate.category_distance == 0


@pytest.mark.parametrize("product_id", [YOGHURT, "469363", "460525"])
def test_the_ward_gets_no_plant_drink_for_a_dairy_product(
    service: OfferService, catalog: ProductCatalog, agent_ward: Identity, product_id: str
) -> None:
    original = catalog.get_product(product_id)

    result = service.find_substitutes(product_id, agent_ward, SubstituteQuery(needed_by=date(2026, 11, 16)))

    assert {catalog.get_product(candidate.product_id).category for candidate in result.candidates
            if not candidate.listed_by_supplier} <= {original.category}
    assert not any(candidate.orderable for candidate in result.candidates)
    # Each declares milk. One that Valio lists is shown with its reason; the others are counted in a note
    # (lane L2a-2: the list does not spend its places on products that fail the buyer's allergen rule).
    assert all(candidate.listed_by_supplier for candidate in result.candidates if not candidate.passes)
    assert any("fail the allergen rule and are not shown" in note for note in result.notes)


def test_coconut_cream_no_longer_stands_in_for_milk_powder(service: OfferService, agent_hotel: Identity) -> None:
    result = service.find_substitutes(MILK_POWDER, agent_hotel, SubstituteQuery(needed_by=date(2026, 11, 16)))

    assert "464217" not in {candidate.product_id for candidate in result.candidates}
    assert result.notes[0] == "13 candidates checked for price, availability and allergens."  # the 13 others of 10405


def test_no_unlisted_candidate_of_another_category_in_the_whole_capture(
    service: OfferService, catalog: ProductCatalog, agent_hotel: Identity, capture_demo: Any
) -> None:
    # Every 5th product of the capture (154 searches), hotel profile, default clock.
    strangers = []
    for product_id in sorted(capture_demo.ids)[::5]:
        original = catalog.get_product(product_id)
        result = service.find_substitutes(product_id, agent_hotel, SubstituteQuery())
        strangers.extend(
            (product_id, candidate.product_id)
            for candidate in result.candidates
            if not candidate.listed_by_supplier
            and catalog.get_product(candidate.product_id).category != original.category
        )

    assert strangers == []


def test_distance_is_same_category_or_not_and_never_a_count_of_shared_digits(catalog: ProductCatalog) -> None:
    oat, rice, milk, beef = (catalog.get_product(each) for each in ("473609", "473424", "469363", "466988"))

    assert substitute_distance(oat, rice) == 0  # both 10402
    assert substitute_distance(oat, milk) == 1  # 10402 and 10400 share four digits: still another category
    assert substitute_distance(oat, beef) == 1  # 10402 and 18720 share one


def test_a_pair_valio_lists_from_another_category_is_still_a_candidate(catalog: ProductCatalog) -> None:
    # Whole catalog: 20 of the 249 pairs Valio lists cross a category. They stay in the pool, at distance 1.
    crossing = [
        (product.id, other)
        for product in catalog.products
        for other in catalog.listed_substitutes(product.id)
        if catalog.get_product(other).category != product.category
    ]

    assert len(crossing) == 20
    original, listed = (catalog.get_product(each) for each in crossing[0])
    pool = substitutes_module._pool(original, catalog, frozenset())
    assert (listed, True, 1) in pool
    assert all(product.category == original.category for product, is_listed, _ in pool if not is_listed)


def test_the_pool_still_stops_at_what_one_call_holds(
    catalog: ProductCatalog, fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], policy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No category holds 999 products (the largest, 17300, holds 443), so the limit is lowered to show it holds.
    monkeypatch.setattr(substitutes_module, "MAX_POOL", 5)
    gateway = fake_gateway()

    result = find_substitutes("473609", policy.get_profile("hotel-kitchen"), deps_for(gateway), SubstituteQuery())

    assert [(endpoint, len(ids)) for endpoint, ids, _ in gateway.calls] == [("price", 6), ("availability", 6)]
    assert any("Only the first 5 candidates were checked" in note for note in result.notes)
