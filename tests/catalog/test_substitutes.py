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


def test_same_category_is_the_whole_five_digit_code(catalog: ProductCatalog) -> None:
    same = catalog.same_category(OAT_DRINK)

    assert len(same) == 65  # the 66 products of category 10402 without the product itself
    assert all(product.category == "10402" for product in same)
    ids = [product.id for product in same]
    assert OAT_DRINK not in ids
    assert ids == sorted(ids)
    assert catalog.same_category(OAT_DRINK, 5) == same  # a caller that still names all five digits


@pytest.mark.parametrize("digits", [4, 3, 1, 0, 6, -1])
def test_a_category_is_never_compared_on_fewer_digits(catalog: ProductCatalog, digits: int) -> None:
    # Valio did not confirm that the digits are levels (answer V7): a prefix is not a product relation.
    with pytest.raises(InvalidRequest):
        catalog.same_category(OAT_DRINK, digits)
