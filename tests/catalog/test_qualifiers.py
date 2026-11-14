"""The qualifiers measured from the catalog (lane FC2, decision B49): which words, of which kind, and why."""

from __future__ import annotations

from decimal import Decimal

from tta.catalog import ProductCatalog
from tta.catalog.qualifiers import (
    NO_QUALIFIERS,
    ORIGIN_OR_FARMING,
    PROCESSING_OR_DESCRIPTION,
    Qualifiers,
    current_qualifiers,
    derive_qualifiers,
    no_qualifiers,
    provide_qualifiers,
)
from tta.contracts.product import IngredientStatement, Product


def _product(product_id: str, text: str, labels: tuple[str, ...] = ()) -> Product:
    return Product(
        id=product_id, category="10400", sales_unit="ST", base_unit="ST", allowed_lot_size=Decimal(1),
        ingredient_statements=(IngredientStatement(language="en", text=text),), labels=labels,
    )


def test_the_words_of_origin_and_farming_are_found_from_the_catalog_not_typed(catalog: ProductCatalog) -> None:
    # Whole catalog, every language, 38,330 statements. Nine words, each on the strength of a certificate.
    found = catalog.qualifiers

    assert found.origin_words == {
        "organic", "finnish", "luomu", "suomalainen", "ekologisk", "ekologiska", "ekologiskt", "finsk", "finskt",
    }
    assert len(found.found) == 89


def test_each_qualifier_carries_what_was_measured_of_it(catalog: ProductCatalog) -> None:
    by_word = {each.word: each for each in catalog.qualifiers.found}

    organic, finnish, pasteurised = by_word["organic"], by_word["finnish"], by_word["pasteurised"]
    assert (organic.heads, organic.alone, organic.products, organic.label) == (179, 3, 157, "EU_ORGANIC_FARMING")
    assert round(float(organic.label_share), 2) == 0.93
    assert (finnish.heads, finnish.label, finnish.kind) == (87, "GOODS_FROM_FINLAND_BLUE_SWAN", ORIGIN_OR_FARMING)
    # The nearest word that is not one: 55% of its products carry a Finnish-origin mark, under two in three.
    assert round(float(pasteurised.label_share), 2) == 0.55
    assert pasteurised.kind == PROCESSING_OR_DESCRIPTION


def test_words_of_processing_are_qualifiers_of_the_other_kind(catalog: ProductCatalog) -> None:
    kinds = {each.word: each.kind for each in catalog.qualifiers.found}

    for word in ("dried", "pasteurised", "concentrated", "modified", "smoked", "kuivattu", "pastöroitu"):
        assert kinds[word] == PROCESSING_OR_DESCRIPTION, word


def test_a_word_that_is_a_component_by_itself_is_not_a_qualifier(catalog: ProductCatalog) -> None:
    words = {each.word for each in catalog.qualifiers.found}

    # Each opens the name of many components ("wheat flour", "milk protein") and is one itself.
    assert not words & {"wheat", "milk", "salt", "stabiliser", "apple", "white"}


def test_a_place_is_what_the_statements_name_after_the_word_for_origin(catalog: ProductCatalog) -> None:
    places = catalog.qualifiers.places

    assert {"finland", "eu", "non eu", "suomi", "muu kuin eu", "greece", "italy"} <= places
    assert not places & {"rye", "råg", "milk", "wheat", "pork"}  # each follows "origin of …" and is a component


def test_what_is_read_as_origin_only(catalog: ProductCatalog) -> None:
    table = catalog.qualifiers

    assert table.without_origin("organic cream") == "cream"
    assert table.without_origin("dried organic apple") == "dried apple"
    assert table.without_origin("wheat flour finland") == "wheat flour"
    assert table.without_origin("pasteurised milk") == "pasteurised milk"
    assert table.without_origin("organic") == "organic"  # nothing else: left as it is
    assert table.says_origin_only("eu") and table.says_origin_only("origin finland")
    assert not table.says_origin_only("rapeseed") and not table.says_origin_only("")


def test_the_table_is_measured_from_the_products_given() -> None:
    # Twenty products write "alpine" in front of components other products name without it, and carry one mark.
    heads = ("cream", "milk", "butter", "oat", "rye", "barley", "honey", "apple", "pear", "plum", "cherry", "carrot")
    marked = [_product(f"1{index:05d}", f"alpine {heads[index % 12]}, water", ("ALPINE_MARK",)) for index in range(24)]
    plain = [_product(f"2{index:05d}", f"{head}, salt. Origin: Alps.") for index, head in enumerate(heads)]

    found = derive_qualifiers([*marked, *plain])

    assert found.origin_words == {"alpine"}
    assert found.places == {"alp"}
    assert found.found[0].heads == 12


def test_without_the_certificate_the_same_word_is_not_of_origin() -> None:
    heads = ("cream", "milk", "butter", "oat", "rye", "barley", "honey", "apple", "pear", "plum", "cherry", "carrot")
    unmarked = [_product(f"1{index:05d}", f"alpine {heads[index % 12]}, water") for index in range(24)]
    plain = [_product(f"2{index:05d}", f"{head}, salt") for index, head in enumerate(heads)]

    found = derive_qualifiers([*unmarked, *plain])

    assert found.origin_words == frozenset()
    assert [each.kind for each in found.found] == [PROCESSING_OR_DESCRIPTION]


def test_the_provider_is_filled_by_a_loaded_catalog_and_can_be_set_back(catalog: ProductCatalog) -> None:
    assert current_qualifiers() is catalog.qualifiers  # the conftest gives a test that uses the catalog its table

    provide_qualifiers(no_qualifiers)
    assert current_qualifiers() is NO_QUALIFIERS

    provide_qualifiers(lambda: Qualifiers(origin_words=frozenset({"alpine"})))
    assert current_qualifiers().origin_words == {"alpine"}


def test_a_test_without_the_catalog_starts_with_no_qualifiers() -> None:
    assert current_qualifiers() is NO_QUALIFIERS
