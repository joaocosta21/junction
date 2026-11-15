"""Review finding C3-F2, decision B65: the words of a name that say what kind of product it is.

Every figure is a count over the whole catalog (17,546 products), inside the product's own category.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tta.catalog import ProductCatalog
from tta.catalog.kind_words import (
    KindWords,
    count_category_words,
    kind_words,
    missing_kind_words,
    shared_weight,
)
from tta.contracts.product import Product

YOLK, OTHER_YOLK, EGG_WHITE, WHOLE_EGG = "469500", "475366", "475374", "475201"  # category 10592, 21 products
COCOA_POWDER, VAN_HOUTEN, DRINKING_CHOCOLATE, COCOA_DRINK_POWDER = "475703", "470594", "475204", "461042"
BICARBONATE, OTHER_BICARBONATE, BAKING_POWDER, BILBERRY_FILLING = "465668", "476713", "466228", "469116"
GUANAJA, MANJARI, SUGAR_STRANDS = "462859", "462889", "476667"
PANNA_COTTA, CREME_BRULEE = "471006", "471124"
BRISKET, OTHER_BRISKET, FLANK = "469890", "474852", "466952"  # category 18720, type beef (raw)
TENDERLOIN, OTHER_TENDERLOIN, SAME_MARK_STRIPLOIN = "473463", "463059", "464152"


def _kind(catalog: ProductCatalog, product_id: str, *, of_one_type: bool = False) -> KindWords:
    product = catalog.get_product(product_id)
    counts = count_category_words((product, *catalog.same_category(product_id)))
    return kind_words(product, counts, of_one_type=of_one_type)


def _missing(catalog: ProductCatalog, kind: KindWords, other_id: str) -> tuple[str, ...]:
    return missing_kind_words(kind, catalog.get_product(other_id))


def _named(english: str, finnish: str, brand: str, product_id: str) -> Product:
    return Product(
        id=product_id, name_en=english, name_fi=finnish, brand=brand, category="99999", sales_unit="ST",
        base_unit="ST", allowed_lot_size=Decimal(1),
    )


def test_the_part_of_the_egg_is_the_kind_word_and_not_the_words_most_egg_products_carry(
    catalog: ProductCatalog,
) -> None:
    kind = _kind(catalog, YOLK)

    # "egg" is in 17 of the 21 names and "barn" in 11: they say the category. "Long Life" is in no other name.
    assert [written for _, written in kind.english] == ["yolk"]
    assert _missing(catalog, kind, OTHER_YOLK) == ()
    assert _missing(catalog, kind, EGG_WHITE) == ("yolk",)
    assert _missing(catalog, kind, WHOLE_EGG) == ("yolk",)


def test_cocoa_powder_is_not_a_cocoa_drink_powder(catalog: ProductCatalog) -> None:
    kind = _kind(catalog, COCOA_POWDER)

    # "Cacao" is read as "cocoa"; the Finnish name adds "kaakaojauhe", which "kaakaojuomajauhe" (a drink
    # powder) is not.
    assert [word for word, _ in kind.english] == ["cocoa", "powder"]
    assert [word for word, _ in kind.finnish] == ["kaakaojauhe"]
    assert _missing(catalog, kind, VAN_HOUTEN) == ()
    assert _missing(catalog, kind, DRINKING_CHOCOLATE) == ("cocoa", "powder")
    assert _missing(catalog, kind, COCOA_DRINK_POWDER) == ("kaakaojauhe",)  # "Fazer Cocoa drink powder"


def test_baking_powder_and_a_bilberry_filling_are_not_sodium_bicarbonate(catalog: ProductCatalog) -> None:
    kind = _kind(catalog, BICARBONATE)

    assert _missing(catalog, kind, OTHER_BICARBONATE) == ()  # "Bicarbonate of soda", "Sooda" inside "Ruokasooda"
    assert _missing(catalog, kind, BAKING_POWDER) == ("Bicarbonate",)
    assert _missing(catalog, kind, BILBERRY_FILLING) == ("Bicarbonate",)


def test_a_variety_name_no_other_product_carries_is_not_asked_of_a_candidate(catalog: ProductCatalog) -> None:
    kind = _kind(catalog, GUANAJA)

    assert [written for _, written in kind.english] == ["dark"]  # not "Guanaja": 1 name; "chocolate": 32 names
    assert _missing(catalog, kind, MANJARI) == ()  # another dark couverture of the brand
    # Finnish joins words: "tumma suklaa" is carried by "TUMMA SUKLAANAPPI" (466730, dark chocolate buttons).
    assert [word for word, _ in kind.finnish] == ["tumma", "suklaa"]
    assert _missing(catalog, kind, "466730") == ()
    assert _missing(catalog, kind, SUGAR_STRANDS) == ("dark",)  # "Chocolate sugar strands"


def test_a_product_nothing_in_its_category_resembles_has_no_candidate(catalog: ProductCatalog) -> None:
    kind = _kind(catalog, PANNA_COTTA)

    # No telling word: "Panna" and "Cotta" are in no other name of category 10432, so they are what a
    # candidate would have to carry.
    assert [written for _, written in kind.english] == ["Panna", "Cotta"]
    assert all(
        missing_kind_words(kind, other) == ("Panna", "Cotta") for other in catalog.same_category(PANNA_COTTA)
    )
    assert _missing(catalog, kind, CREME_BRULEE) == ("Panna", "Cotta")


def test_raw_meat_is_read_more_loosely_and_the_cut_outweighs_a_producers_mark(catalog: ProductCatalog) -> None:
    brisket = _kind(catalog, BRISKET, of_one_type=True)
    tenderloin = _kind(catalog, TENDERLOIN, of_one_type=True)

    assert brisket.every is False
    assert _missing(catalog, brisket, OTHER_BRISKET) == ()
    assert _missing(catalog, brisket, FLANK) == ("Brisket",)  # the names share no telling word
    # "Atria Guaranteed Tender Beef Tenderloin": another cut with the same mark stays a candidate, after
    # every tenderloin. "Tenderloin" is a word of 11 brands, "Guaranteed" of 2.
    assert _missing(catalog, tenderloin, SAME_MARK_STRIPLOIN) == ()
    other, striploin = catalog.get_product(OTHER_TENDERLOIN), catalog.get_product(SAME_MARK_STRIPLOIN)
    assert shared_weight(tenderloin, other) > shared_weight(tenderloin, striploin) > 0


def test_a_plural_carries_the_kind_word() -> None:
    original = _named("Kesä beetroot burgers 2 kg", "Kesä punajuuripihvit 2 kg", "Kesä", "1")
    same = _named("Talvi beetroot burger 500 g", "Talvi punajuuripihvi 500 g", "Talvi", "2")
    other = _named("Talvi carrot burger 500 g", "Talvi porkkanapihvi 500 g", "Talvi", "3")
    filler = [_named(f"Syksy soup {index}", f"Syksy keitto {index}", "Syksy", str(index)) for index in range(10, 16)]
    kind = kind_words(original, count_category_words((original, same, other, *filler)))

    assert [word for word, _ in kind.english] == ["beetroot", "burger"]  # "burgers" is counted without its ending
    assert missing_kind_words(kind, same) == ()
    assert missing_kind_words(kind, other) == ("beetroot",)


@pytest.mark.parametrize("product_id", [YOLK, COCOA_POWDER, BICARBONATE, GUANAJA, PANNA_COTTA])
def test_a_product_carries_its_own_kind_words(catalog: ProductCatalog, product_id: str) -> None:
    assert missing_kind_words(_kind(catalog, product_id), catalog.get_product(product_id)) == ()
