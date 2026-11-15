"""Review finding C3-F3: a product type a recipe uses holds only what a cook would accept for that word.

A ward menu ("oven pancake for 30") ordered an egg glaze spray as eggs, because the type was two whole
categories. Every figure is a count over the whole catalog (17,546 products), made on 15 Nov 2026.
"""

from __future__ import annotations

import pytest

from tta.catalog import ProductCatalog
from tta.catalog.kinds import product_types_of
from tta.contracts.request import MAX_PRODUCT_IDS, ProductQuery

GLAZE_SPRAY, MAYONNAISE_BASE, QUAIL_EGGS = "468206", "468127", "463692"
YOLK, EGG_WHITE, ALBUMEN_POWDER, BOILED, SCRAMBLED, EGG_SPREAD = (
    "469500", "475374", "467309", "464700", "466032", "471280",
)
SHELL_EGGS, LIQUID_WHOLE_EGG = "468445", "475201"


def _of_type(catalog: ProductCatalog, key: str) -> set[str]:
    return {product.id for product in catalog.search(ProductQuery(product_type=key, limit=MAX_PRODUCT_IDS)).products}


def test_eggs_are_hens_eggs_in_the_shell_and_liquid_whole_egg(catalog: ProductCatalog) -> None:
    eggs = _of_type(catalog, "eggs")

    assert len(eggs) == 13  # 30 before: both categories whole
    assert {SHELL_EGGS, LIQUID_WHOLE_EGG} <= eggs
    assert not {
        GLAZE_SPRAY, MAYONNAISE_BASE, QUAIL_EGGS, YOLK, EGG_WHITE, ALBUMEN_POWDER, BOILED, SCRAMBLED, EGG_SPREAD,
    } & eggs
    assert sum(catalog.get_product(product_id).category == "10590" for product_id in eggs) == 8


def test_a_variety_is_not_the_plain_product_and_is_found_when_the_request_names_it(
    catalog: ProductCatalog,
) -> None:
    assert product_types_of(catalog.get_product(GLAZE_SPRAY)) == ()
    assert product_types_of(catalog.get_product(YOLK)) == ()

    def found(key: str, *terms: str) -> set[str]:
        query = ProductQuery(product_type=key, name_terms=terms, limit=MAX_PRODUCT_IDS)
        return {product.id for product in catalog.search(query).products}

    # "rye flour", "icing sugar", "clarified butter", "boiled eggs": the type with the word a buyer adds.
    assert {"461568", "466973", "470310"} <= found("flour", "rye")
    assert found("sugar", "icing") == {"460793", "461706"}
    assert found("butter", "clarified") == {"472127"}
    assert {"464700", "468413", "469340"} == found("eggs", "boiled")
    assert {"469500", "475366", "468239"} == found("eggs", "yolk")
    # A name term that names no variety finds the plain products only: the recipe's "sugar (granulated)" is no
    # longer raw cane sugar 461329 ("Rawsugar Granulated"), and "butter (unsalted)" not the laminating butter.
    assert "461329" not in found("sugar", "granulated") and "460334" in found("sugar", "granulated")
    assert found("butter", "unsalted") == {"464411", "464205"}
    assert found("eggs", "whole") == {"468269", "468520", "475201", "475357"}


def test_a_request_that_names_a_variety_still_names_the_type() -> None:
    # The variety terms are no exclude terms: the reader of sentences (`tta.agent.typenames`) leaves a type
    # unnamed when the words hold one of its exclude terms, and "rye flour" must stay a request for flour.
    from tta.catalog.product_types import load_product_types

    table = load_product_types()

    assert table["flour"].exclude_terms == () and "rye" in table["flour"].variety_terms
    assert table["sugar"].exclude_terms == () and "icing" in table["sugar"].variety_terms
    assert table["eggs"].exclude_terms == () and {"yolk", "white", "glaze", "mayo"} <= set(table["eggs"].variety_terms)
    assert table["butter"].exclude_terms == ("plant",)


@pytest.mark.parametrize(
    ("key", "count", "inside", "outside"),
    [
        # white sugar in grains; not jam sugar (pectin), icing sugar, cubes, sticks, syrup, raw cane sugar
        ("sugar", 9, {"463161", "460334", "460325"}, {"460270", "461706", "462172", "468765", "461646", "461329"}),
        # plain wheat flour; not breadcrumbs, rye, rice, chickpea or a gluten-free mix
        ("flour", 21, {"460791", "460856", "467080"}, {"460613", "461568", "473206", "464343", "473319"}),
        # butter; not clarified, brown or laminating butter
        ("butter", 15, {"464411", "464205", "475797"}, {"472127", "475708", "474681", "464761"}),
        # cream; not a flavoured cooking cream, the sweet chili one, or whipped cream in a spray can
        ("cream", 32, {"469346", "463797", "464194"}, {"463825", "468521", "473847", "462652"}),
    ],
)
def test_a_recipe_type_holds_what_a_cook_accepts_for_the_word(
    catalog: ProductCatalog, key: str, count: int, inside: set[str], outside: set[str]
) -> None:
    products = _of_type(catalog, key)

    assert len(products) == count
    assert inside <= products
    assert not outside & products


def test_every_flour_of_the_type_is_wheat_flour(catalog: ProductCatalog) -> None:
    for product_id in _of_type(catalog, "flour"):
        product = catalog.get_product(product_id)
        names = f"{product.name_en} {product.name_fi}".casefold()
        assert "wheat" in names or "vehnä" in names, product_id


def test_milk_holds_no_product_a_cook_would_send_back(catalog: ProductCatalog) -> None:
    # Checked by reading the 74 names on 15 Nov 2026: milk and lactose-free milk drinks of every fat level.
    # No flavoured milk, no sour milk, no milk for coffee, no ready drink.
    milk = _of_type(catalog, "milk")

    assert len(milk) == 74
    for product_id in milk:
        english = (catalog.get_product(product_id).name_en or "").casefold()
        assert "milk" in english, product_id
        assert not any(word in english for word in ("chocolate", "vanilla", "coffee", "sour")), product_id
