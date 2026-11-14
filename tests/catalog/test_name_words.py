"""Review finding S11: a word the reader does not know is never read as "no difference".

Two products of one brand whose names differ in a word no list of ours explains are variants of each other.
The catalog figures are of the whole product file (17,546 products) and are recounted on every run.
"""

from __future__ import annotations

from decimal import Decimal

from tta.catalog import ProductCatalog
from tta.catalog.name_words import NameDifference, name_difference, shares_a_product_word
from tta.contracts.product import Product


def _named(english: str | None, brand: str | None = "Kesä", finnish: str | None = None) -> Product:
    return Product(
        id="1", name_en=english, name_fi=finnish, brand=brand, category="99999", sales_unit="ST", base_unit="ST",
        allowed_lot_size=Decimal(1),
    )


def test_a_word_no_list_knows_is_a_difference_and_is_given_as_the_name_writes_it() -> None:
    found = name_difference(_named("Kesä Xyzzy Ice Cream 5000 ml"), _named("Kesä Vanilla Ice Cream 5000 ml"))

    assert found == NameDifference(original_words=("Xyzzy",), words=("Vanilla",))


def test_two_flavours_our_lists_know_are_no_unexplained_difference() -> None:
    # The flavour rule judges these; nothing is left unexplained.
    assert name_difference(_named("Kesä Strawberry Ice Cream 5 L"), _named("Kesä Vanilla Ice Cream 5 L")) is None
    assert name_difference(_named("Kesä Rum & Raisin Ice Cream"), _named("Kesä Tiramisu Ice Cream")) is None


def test_sizes_pack_words_claim_words_and_the_brand_are_no_difference() -> None:
    one = _named("Kesä oat drink 1 l UHT gluten free")
    other = _named("6 x Kesä oat drink 250ml tetra, gluten-free, lactose free e900 g")

    assert name_difference(one, other) is None


def test_another_brand_or_no_brand_is_not_judged_by_its_words() -> None:
    assert name_difference(_named("Kesä Xyzzy Ice Cream"), _named("Talvi Vanilla Ice Cream", brand="Talvi")) is None
    assert name_difference(_named("Xyzzy Ice Cream", brand=None), _named("Vanilla Ice Cream", brand=None)) is None


def test_finnish_names_are_read_when_there_is_no_english_one() -> None:
    found = name_difference(
        _named(None, finnish="Kesä mansikkajäätelö 5 l"), _named(None, finnish="Kesä xyzzyjäätelö 5 l")
    )

    # Every differing word is given; "mansikka…" is a flavour of our lists and "xyzzy…" is what nobody explains.
    assert found == NameDifference(original_words=("mansikkajäätelö",), words=("xyzzyjäätelö",))


def test_the_catalogs_own_variants(catalog: ProductCatalog) -> None:
    def difference(original_id: str, other_id: str) -> NameDifference | None:
        return name_difference(catalog.get_product(original_id), catalog.get_product(other_id))

    # Oddlygood Barista oat drink and its "Delight": the pair Valio lists.
    assert difference("473609", "471690") == NameDifference(original_words=(), words=("Delight",))
    # Valio skimmed milk powder "high heat" and "instant".
    assert difference("469148", "462224") == NameDifference(original_words=("high", "heat"), words=("instant",))
    # Nutty vanilla: both words are flavours of our lists, so the flavour rule speaks, not this one.
    assert difference("473609", "474724") is None
    assert difference("473609", "475224") is None  # another brand
    # "Oatly iKaffe 0,5L" and "Oatly iKaffe Oat drink 1,5L": one name spells out what the other leaves unsaid,
    # and the first one's ingredient list says "OATS 10%". The same product in another pack, not a variant.
    assert difference("468319", "473278") is None


def test_a_shared_product_word_is_looked_for_in_both_languages(catalog: ProductCatalog) -> None:
    creme, tzatziki = catalog.get_product("477055"), catalog.get_product("470260")

    assert shares_a_product_word(creme, tzatziki) is False  # "lactose free" is a claim, not a product word
    assert shares_a_product_word(catalog.get_product("469148"), catalog.get_product("462224")) is True
    assert shares_a_product_word(_named("Kesä milk powder", finnish="Kesä maitojauhe"),
                                 _named("Talvi instant", brand="Talvi", finnish="Talvi rasvaton maitojauhe")) is True
    assert shares_a_product_word(_named("Kesä 1 l UHT"), _named("Kesä 2 l UHT")) is False  # nothing but sizes


def test_how_many_listed_pairs_differ_in_an_unexplained_word(catalog: ProductCatalog) -> None:
    pairs = [
        (product, catalog.get_product(other_id))
        for product in catalog.products for other_id in catalog.listed_substitutes(product.id)
    ]
    differing = [1 for product, other in pairs if other is not None and name_difference(product, other)]

    assert len(pairs) == 249
    # 101 of the 249 pairs are of one brand; 46 of those differ in a word nothing explains. Each stays listed
    # (Valio's own judgement) and its sentence says the difference.
    assert len(differing) == 46
