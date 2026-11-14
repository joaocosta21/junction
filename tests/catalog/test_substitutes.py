"""Substitute seeds: the pairs Valio lists, and the products of the same category."""

from __future__ import annotations

import pytest

from tta.catalog import ProductCatalog
from tta.contracts.errors import InvalidRequest

OAT_DRINK = "473609"  # category 10402, lists three substitutes


def test_listed_substitutes_in_file_order(catalog: ProductCatalog) -> None:
    assert catalog.listed_substitutes(OAT_DRINK) == ("471690", "471881", "464320")
    assert catalog.listed_substitutes("464744") == ()


def test_a_product_is_never_its_own_substitute(catalog: ProductCatalog) -> None:
    looped = catalog.get_product("471661")

    assert looped is not None
    assert looped.listed_substitutes == ("471661",)  # the file lists it as its own substitute
    assert catalog.listed_substitutes("471661") == ()


def test_every_listed_substitute_is_a_catalog_product(catalog: ProductCatalog) -> None:
    for product in catalog.products:
        for substitute_id in catalog.listed_substitutes(product.id):
            assert catalog.get_product(substitute_id) is not None


def test_same_category_by_five_four_and_three_digits(catalog: ProductCatalog) -> None:
    five = catalog.same_category(OAT_DRINK, 5)
    four = catalog.same_category(OAT_DRINK, 4)
    three = catalog.same_category(OAT_DRINK, 3)

    assert len(five) == 65  # the 66 products of category 10402 without the product itself
    assert all(product.category == "10402" for product in five)
    assert all(product.category.startswith("1040") for product in four)
    assert all(product.category.startswith("104") for product in three)
    assert {p.id for p in five} < {p.id for p in four} < {p.id for p in three}
    for products in (five, four, three):
        ids = [product.id for product in products]
        assert OAT_DRINK not in ids
        assert ids == sorted(ids)


@pytest.mark.parametrize("digits", [0, 6, -1])
def test_same_category_needs_one_to_five_digits(catalog: ProductCatalog, digits: int) -> None:
    with pytest.raises(InvalidRequest):
        catalog.same_category(OAT_DRINK, digits)
