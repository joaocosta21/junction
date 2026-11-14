"""A page counts as evidence only when it names this product: the brand, and no word of its own that the product's
English or Finnish name does not carry (pack sizes aside)."""

from __future__ import annotations

import pytest

from tta.catalog import ProductCatalog
from tta.evidence.matching import names_match

FAZER_PROFESSIONAL = "475224"
ODDLYGOOD_BARISTA = "473609"


@pytest.mark.parametrize(
    ("product_id", "page_name", "url"),
    [
        ("469512", "Elovena Kaurajuoma kahviin", "https://elovena.fi/tuotteet/elovena-kaurajuoma-kahviin/"),
        ("468465", "Oddlygood® kaurajuoma 1 l UHT gluteeniton", "https://www.oddlygood.com/fi/tuotteet/x/"),
        (ODDLYGOOD_BARISTA, "Oddlygood® Barista oat drink 1 l UHT gluten free", "https://www.oddlygood.com/uk/x/"),
        (FAZER_PROFESSIONAL, "Fazer Aito Professional Barista Oat Drink 1L UHT", "https://www.fazer.com/en/x/"),
        (FAZER_PROFESSIONAL, "Fazer Aito Professional Barista Kaurajuoma 1L UHT", "https://www.fazer.fi/x/"),
        # The brand is in the address, not in the page's name.
        ("469512", "Oat drink barista", "https://elovena.nl/producten/oat-drink-barista/"),
    ],
)
def test_a_page_that_names_the_product_matches(
    catalog: ProductCatalog, product_id: str, page_name: str, url: str
) -> None:
    assert names_match(page_name, None, url, catalog.get_product(product_id))


@pytest.mark.parametrize(
    ("product_id", "page_name", "url"),
    [
        # Asked for the plain oat drink, the answer was the Barista drink: a word the product does not carry.
        ("468465", "Oddlygood® Barista oat drink 1 l UHT gluten free", "https://www.oddlygood.com/uk/x/"),
        # The international recipe of another Fazer barista drink.
        (FAZER_PROFESSIONAL, "Fazer Aito Oat Drink Barista 1L UHT (INT)", "https://www.fazeraito.com/x/"),
        # Too little of the product's name.
        (ODDLYGOOD_BARISTA, "Oddlygood® oat", "https://www.oddlygood.com/x/"),
        # Another brand.
        ("469512", "Oatly Kaurajuoma kahviin", "https://www.oatly.com/x/"),
        # Nothing to compare.
        ("469512", "", "https://elovena.fi/x/"),
        ("469512", "® 1 l", "https://elovena.fi/x/"),
    ],
)
def test_a_page_for_another_product_does_not_match(
    catalog: ProductCatalog, product_id: str, page_name: str, url: str
) -> None:
    assert not names_match(page_name, None, url, catalog.get_product(product_id))


def test_the_page_title_can_carry_the_brand(catalog: ProductCatalog) -> None:
    product = catalog.get_product("469512")

    assert names_match("Kaurajuoma kahviin", "Elovena Kaurajuoma kahviin", "https://example.org/x", product)
    assert not names_match("Kaurajuoma kahviin", "Kaurajuoma kahviin", "https://example.org/x", product)


def test_a_product_without_a_brand_is_matched_on_its_name_alone(catalog: ProductCatalog) -> None:
    product = catalog.get_product("469512").model_copy(update={"brand": None})

    assert names_match("Elovena Kaurajuoma kahviin", None, "https://example.org/x", product)
