"""What kind of product one is, read from the product file: product types, flavour, use, drink.

Every word list is ours. The counts are of the whole catalog (17,546 products) and are recounted on every run,
so a change to a word list that catches plain products shows here.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

import pytest

from tta.catalog import ProductCatalog
from tta.catalog.kinds import (
    DRINK_TYPES,
    drink_evidence,
    flavour_words,
    flavours_of,
    is_drink,
    is_other_use,
    is_same_type,
    product_types_of,
    type_words,
    use_words,
    uses_of,
)
from tta.catalog.product_types import load_product_types
from tta.contracts.product import Product
from tta.contracts.request import ProductQuery


def _named(english: str, finnish: str | None = None, category: str = "99999") -> Product:
    return Product(
        id="1", name_en=english, name_fi=finnish, category=category, sales_unit="ST", base_unit="ST",
        allowed_lot_size=Decimal(1),
    )


@pytest.mark.parametrize(
    ("product_id", "flavours"),
    [
        ("473609", ()),  # Oddlygood Barista oat drink: plain
        ("471690", ()),  # Barista "Delight": a lighter recipe, no flavour named
        ("474724", ("nut", "vanilla")),  # Barista "nutty vanilla"
        ("471424", ("hazelnut",)),
        ("472387", ("caramel",)),
        ("472879", ("pumpkin spice",)),
        ("474957", ("gingerbread",)),  # only the Finnish name says it in Finnish: "piparkakku"
        ("473142", ("vanilla",)),  # Valio coffee milk drink vanilla
        # Review finding S11: each of these read as "not flavoured" before.
        ("470974", ("raisin", "rum")),  # Ingman Rum & Raisin ice cream
        ("469651", ("tiramisu",)),  # Carte d'Or Tiramisu ice cream
        ("462635", ("cookies and cream",)),  # GelatoLAB "Cookies Cream"
        ("464837", ("cookies and cream",)),  # Ingman Scooping Oreo
        ("466173", ("cookies and cream",)),
        ("468099", ("cookies and cream",)),
        ("468714", ("cookies and cream",)),  # "Cookies and cream", "Keksimuru"
        ("470927", ("cookies and cream",)),
        ("460458", ("tutti frutti",)),  # Heartbrand Rainbow/Tutti Frutti
        ("467755", ("tutti frutti",)),  # Fazer "TuttiFrutti"
        ("468764", ("tutti frutti",)),
        ("460304", ("honey",)),  # Hunajainen SAM Kesäkukka Hunaja: a honey
        ("466611", ()),  # the same brand's agave syrup: "Hunajainen" is the brand, not a flavour
        ("460103", ()),  # "TOMATO HONEY": a tomato variety
        ("461067", ("melon",)),  # honeydew melons
        ("466257", ()),  # a paper cup printed "Coca Cola"
        ("476949", ("cola",)),
        ("464237", ()),  # Valio coffee milk: made for coffee, and coffee is not its flavour
        ("463047", ()),  # Arla whole milk
        ("469346", ()),  # Arla Pro whipping cream
        ("463830", ("flavoured",)),  # "flavoured cooking cream ... three cheeses": no flavour of our list named
        ("464715", ("lemon",)),  # flavoured cooking cream lemon and pepper
        ("476665", ("strawberry",)),  # Valiojogurtti strawberry, the name half in Finnish
        ("461087", ()),  # Paulig Juhla Mokka ground coffee: "mokka" on a coffee is no flavour
        ("474759", ()),  # Mozzarella Fior di Latte
        ("460170", ()),  # PLUM TOMATO / TOMAATTI LUUMU
        ("462545", ()),  # CHERRYTOMATOES / KIRSIKKATOMAATTI
        ("460189", ()),  # CAPSICUM ORANGE: a colour
        ("470634", ()),  # chicken thigh steak Thaibasil-Lemongrass ("sitruunaruoho")
        ("466357", ()),  # fructose ("hedelmäsokeri", fruit sugar)
    ],
)
def test_the_flavour_is_read_from_the_english_and_the_finnish_name(
    catalog: ProductCatalog, product_id: str, flavours: tuple[str, ...]
) -> None:
    assert flavours_of(catalog.get_product(product_id)) == flavours


def test_flavour_words_are_whole_english_words_and_starts_of_finnish_words() -> None:
    assert flavours_of(_named("Oat drink", "Kaurajuoma mansikkainen")) == ("strawberry",)
    assert flavours_of(_named("Mansikkajogurtti")) == ("strawberry",)  # Finnish joins words
    assert flavours_of(_named("Pineapple rings")) == ("pineapple",)  # not also "apple"
    assert flavours_of(_named("Coconut milk")) == ("coconut",)  # not also "nut"
    assert flavours_of(_named("Butternut squash, nutmeg, doughnut")) == ()
    assert flavours_of(_named("Caramelised onion")) == ()
    assert flavours_of(_named("Unflavoured yoghurt", "Maustamaton jogurtti")) == ()
    assert flavours_of(_named("Pesto nut free", "Pesto pähkinätön")) == ()
    assert flavours_of(_named("Seasoned chicken", "Maustettu broileri")) == ("flavoured",)
    assert flavours_of(_named("Strawberry flavoured drink")) == ("strawberry",)  # the named flavour is enough
    assert flavours_of(_named("Berry mix")) == ("berry",)
    assert flavours_of(_named("Strawberry and berry mix")) == ("strawberry",)  # a named berry drops "berry"
    assert flavours_of(_named("Chocolate Mocha cereal")) == ("chocolate", "coffee")
    assert flavour_words(("lemon", "orange", "sea buckthorn")) == "lemon, orange and sea buckthorn"
    assert flavour_words(("nut", "vanilla")) == "nut and vanilla"


def test_how_many_products_the_flavour_reading_marks_and_where(catalog: ProductCatalog) -> None:
    marked = [product for product in catalog.products if flavours_of(product)]
    by_type: Counter[str] = Counter()
    for product in marked:
        by_type.update(product_types_of(product))

    assert len(catalog.products) == 17546
    # 3,465 before review finding S11 added the dessert, sweet and drink flavours (rum and raisin, tiramisu,
    # cookies and cream, tutti frutti, honey, cola, earl grey and the rest).
    assert len(marked) == 3715
    # The product types where it marks more than a handful: all are sold in flavours. The 10 chickens are
    # honey-marinated ones.
    assert {key: count for key, count in by_type.items() if count > 6} == {
        "ice_cream": 309, "yoghurt": 110, "soft_drink": 101, "juice": 85, "tea": 56, "quark": 36,
        "plant_drink": 22, "mineral_water": 20, "chicken": 10,
    }
    # Plain kinds stay plain: no milk, coffee, butter, egg, rice, pasta, sausage or minced meat is marked.
    for plain in ("milk", "sour_milk", "coffee", "butter", "eggs", "rice", "pasta", "sausage", "minced_meat",
                  "vegetable_cream", "beef_chuck"):
        assert by_type[plain] == 0, plain
    assert by_type["cream"] == 6  # the six "flavoured cooking cream" of Valio Keittiön
    assert by_type["coffee_milk"] == 1  # 473142, vanilla


@pytest.mark.parametrize(
    ("product_id", "uses"),
    [
        ("473609", ("coffee",)),  # "Barista"
        ("469512", ("coffee",)),  # Elovena oat drink barista / "kaurajuoma kahviin"
        ("464320", ("coffee",)),  # Oatly iKaffe
        ("464237", ("coffee",)),  # Valio coffee milk / "kahvimaito"
        ("463380", ("coffee",)),  # Arla Cafè milk
        ("463442", ("coffee",)),  # Valio coffee cream / "kahvikerma"
        ("468465", ()),  # Oddlygood oat drink, for drinking
        ("469346", ("whipping",)),  # Arla Pro Whipping cream / "Vispikerma"
        ("464249", ("cooking",)),  # Valio cooking cream / "ruokakerma"
        ("463047", ()),
        ("462028", ()),  # a cleansing agent "for coffee machines"
    ],
)
def test_the_use_is_read_from_the_name(catalog: ProductCatalog, product_id: str, uses: tuple[str, ...]) -> None:
    assert uses_of(catalog.get_product(product_id)) == uses


def test_use_words_and_which_use_is_another_use() -> None:
    assert use_words(("coffee",)) == "made for coffee"
    assert use_words(("cooking", "whipping")) == "made for cooking and made for whipping"
    assert is_other_use(("coffee",), ()) is True  # a drinking oat drink for a barista one
    assert is_other_use((), ("coffee",)) is True
    assert is_other_use(("whipping",), ("cooking",)) is True
    assert is_other_use(("whipping",), ("cooking", "whipping")) is False  # made for both stands in for whipping
    assert is_other_use((), ()) is False


def test_the_product_types_of_a_product_are_those_the_search_finds_it_under(catalog: ProductCatalog) -> None:
    by_key: Counter[str] = Counter()
    for product in catalog.products:
        by_key.update(product_types_of(product))

    table = load_product_types()
    assert dict(by_key) == {key: entry.products for key, entry in table.items()}
    for key in ("milk", "coffee_milk", "cream", "vegetable_cream", "plant_drink", "beef_chuck"):
        found = catalog.search(ProductQuery(product_type=key, limit=1000)).products
        assert {product.id for product in found} == {
            product.id for product in catalog.products if key in product_types_of(product)
        }


def test_coffee_milk_is_not_milk_and_a_chuck_steak_is_beef(catalog: ProductCatalog) -> None:
    assert product_types_of(catalog.get_product("463047")) == ("milk",)
    assert product_types_of(catalog.get_product("463380")) == ("coffee_milk",)
    assert product_types_of(catalog.get_product("469346")) == ("cream",)
    assert product_types_of(catalog.get_product("469162")) == ("vegetable_cream",)
    assert product_types_of(catalog.get_product("469148")) == ()  # milk powder: no type of ours
    assert is_same_type(("milk",), ("coffee_milk",)) is False
    assert is_same_type(("beef",), ("beef", "beef_chuck")) is True  # a chuck steak for beef
    assert is_same_type(("beef", "beef_chuck"), ("beef",)) is False  # not any beef for a chuck steak
    assert type_words(("coffee_milk",)) == "coffee milk"


def test_a_drink_is_read_from_the_weight_of_a_litre_and_else_from_the_product_type(catalog: ProductCatalog) -> None:
    assert set(load_product_types()) >= DRINK_TYPES
    assert drink_evidence(catalog.get_product("473609")) == "one litre weighs about a kilogram in the product data"
    assert drink_evidence(catalog.get_product("471690")) == "product type plant drink"
    assert is_drink(catalog.get_product("469346")) is True  # whipping cream: 0.994 kg per litre
    assert is_drink(catalog.get_product("469148")) is False  # milk powder
    assert is_drink(catalog.get_product("465655")) is False  # a juice concentrate 1+7: no type, no weight for a volume
    assert sum(is_drink(product) for product in catalog.products) == 855
