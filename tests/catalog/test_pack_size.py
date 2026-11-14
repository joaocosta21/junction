"""Pack size (litres or kg per sales unit) and the portion-pack detector."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from tta.catalog import ProductCatalog
from tta.catalog.pack import PORTION_MAX_KG, PORTION_MAX_LITRES
from tta.contracts.availability import PriceLine
from tta.contracts.common import PackSizeSource, Unit
from tta.contracts.product import Product, UnitConversion, UnitSize

PriceOf = Callable[[str], PriceLine]


def _product(catalog: ProductCatalog, product_id: str) -> Product:
    product = catalog.get_product(product_id)
    assert product is not None
    return product


def _without_comparison(price: PriceLine) -> PriceLine:
    return price.model_copy(update={"comparison_price": None, "comparison_unit": None})


def test_one_litre_carton_is_one_litre_from_the_captured_price(catalog: ProductCatalog, demo_price: PriceOf) -> None:
    pack = catalog.pack_size(_product(catalog, "464306"), demo_price("464306"), Unit.L)

    assert pack.value == Decimal(1)
    assert pack.unit is Unit.L
    assert pack.source is PackSizeSource.PRICE_RATIO
    assert pack.is_known


def test_portion_pack_is_detected_and_a_litre_carton_is_not(catalog: ProductCatalog) -> None:
    assert catalog.is_portion_pack(_product(catalog, "463203")) is True
    assert catalog.is_portion_pack(_product(catalog, "464306")) is False


def test_portion_pack_reports_its_inner_units(catalog: ProductCatalog, demo_price: PriceOf) -> None:
    pack = catalog.pack_size(_product(catalog, "463203"), demo_price("463203"), Unit.L)

    # 15.09 / 7.55 = 1.9987: the rounded prices allow 1.9974 to 2.0000 and the product file says 2 litres.
    assert pack.value == Decimal(2)
    assert pack.source is PackSizeSource.PRICE_RATIO
    assert pack.inner_units == 100
    assert pack.inner_unit_size == Decimal("0.02")


def test_price_ratio_is_cleared_of_rounding_when_the_product_file_agrees(
    catalog: ProductCatalog, demo_price: PriceOf
) -> None:
    # 8.75 / 0.88 = 9.943 for a 10-litre box; taken as is, 1,000 litres would need 101 boxes instead of 100.
    pack = catalog.pack_size(_product(catalog, "460396"), demo_price("460396"), Unit.L)

    assert pack.value == Decimal(10)
    assert pack.source is PackSizeSource.PRICE_RATIO


def test_price_ratio_wins_when_the_product_file_disagrees(catalog: ProductCatalog, sample_price: PriceOf) -> None:
    # 460657: the file sells a case of ten 1 L cartons, the API prices one carton (AIMO/FINDINGS.md section 1).
    # Its conversion row carries no volume, so without a price the figure comes from the name: 10 x "1 L".
    product = _product(catalog, "460657")

    priced = catalog.pack_size(product, sample_price("460657"), Unit.L)
    unpriced = catalog.pack_size(product, None, Unit.L)

    assert (priced.value, priced.source) == (Decimal(1), PackSizeSource.PRICE_RATIO)
    assert (unpriced.value, unpriced.source) == (Decimal(10), PackSizeSource.NAME)


def test_no_comparison_price_falls_through_to_the_unit_conversion(catalog: ProductCatalog, demo_price: PriceOf) -> None:
    product = _product(catalog, "464306")

    for price in (_without_comparison(demo_price("464306")), None):
        pack = catalog.pack_size(product, price, Unit.L)

        assert pack.value == Decimal(1)
        assert pack.source is PackSizeSource.UNIT_CONVERSION


def test_no_unit_conversion_falls_through_to_the_name(catalog: ProductCatalog, demo_price: PriceOf) -> None:
    # 462626 "Valio coffee milk 5 dl lactose free": a case of 10, and its conversion row carries no volume.
    product = _product(catalog, "462626")

    named = catalog.pack_size(product, None, Unit.L)
    priced = catalog.pack_size(product, demo_price("462626"), Unit.L)

    assert (named.value, named.unit, named.source) == (Decimal(5), Unit.L, PackSizeSource.NAME)
    assert (named.inner_units, named.inner_unit_size) == (10, Decimal("0.5"))
    assert (priced.value, priced.source) == (Decimal(5), PackSizeSource.PRICE_RATIO)


def test_product_with_no_source_at_all_is_unknown(catalog: ProductCatalog, demo_price: PriceOf) -> None:
    # 475044 has a captured price without a comparison price, no conversion row and no size in its name.
    pack = catalog.pack_size(_product(catalog, "475044"), demo_price("475044"), Unit.L)

    assert pack.value is None and pack.unit is None
    assert pack.source is PackSizeSource.UNKNOWN
    assert not pack.is_known


def test_captured_lines_without_a_comparison_price_never_claim_the_price_ratio(
    catalog: ProductCatalog, demo_price_lines: dict[str, PriceLine]
) -> None:
    without = [line for line in demo_price_lines.values() if line.has_price and line.comparison_price is None]

    assert len(without) == 7
    for line in without:
        pack = catalog.pack_size(_product(catalog, line.product_id), line, Unit.UNIT)
        assert pack.source is not PackSizeSource.PRICE_RATIO


def test_product_sold_by_the_kilogram_is_one_kilogram_per_sales_unit(
    catalog: ProductCatalog, demo_price: PriceOf
) -> None:
    beef = _product(catalog, "464744")  # "Evryday c3kg Beef Chuck roll": sold per KG in pieces of about 3 kg

    priced = catalog.pack_size(beef, demo_price("464744"), Unit.KG)
    unpriced = catalog.pack_size(beef, None, Unit.KG)

    assert (priced.value, priced.unit, priced.source) == (Decimal(1), Unit.KG, PackSizeSource.PRICE_RATIO)
    assert (unpriced.value, unpriced.unit, unpriced.source) == (Decimal(1), Unit.KG, PackSizeSource.UNIT_CONVERSION)
    assert catalog.is_portion_pack(beef) is False


def test_litres_are_never_derived_from_a_weight(catalog: ProductCatalog, demo_price: PriceOf) -> None:
    beef = catalog.pack_size(_product(catalog, "464744"), demo_price("464744"), Unit.L)
    milk_in_kg = catalog.pack_size(_product(catalog, "464306"), demo_price("464306"), Unit.KG)

    assert beef.source is PackSizeSource.UNKNOWN
    # The comparison price of the milk is per litre; its net weight comes from the product file instead.
    assert (milk_in_kg.value, milk_in_kg.source) == (Decimal("1.025"), PackSizeSource.UNIT_CONVERSION)


def test_request_in_sales_units_reports_the_measure_the_price_compares_in(
    catalog: ProductCatalog, demo_price: PriceOf
) -> None:
    milk = catalog.pack_size(_product(catalog, "464306"), demo_price("464306"), Unit.UNIT)
    beef = catalog.pack_size(_product(catalog, "464744"), demo_price("464744"), Unit.UNIT)
    unpriced_milk = catalog.pack_size(_product(catalog, "464306"), None, Unit.UNIT)

    assert (milk.value, milk.unit) == (Decimal(1), Unit.L)
    assert (beef.value, beef.unit) == (Decimal(1), Unit.KG)
    assert (unpriced_milk.value, unpriced_milk.unit) == (Decimal(1), Unit.L)


def test_price_line_with_an_error_is_ignored(catalog: ProductCatalog, demo_price: PriceOf) -> None:
    failed = demo_price("464306").model_copy(update={"error": True})

    pack = catalog.pack_size(_product(catalog, "464306"), failed, Unit.L)

    assert pack.source is PackSizeSource.UNIT_CONVERSION


@pytest.mark.parametrize(
    ("catalog_price", "comparison_price"),
    [(Decimal("2.48"), Decimal("0.005")), (Decimal("0.00"), Decimal("2.48")), (Decimal("0.01"), Decimal("100.00"))],
    ids=["comparison-of-half-a-cent", "free-product", "ratio-rounds-to-zero"],
)
def test_price_that_cannot_give_a_size_is_ignored(
    catalog: ProductCatalog, demo_price: PriceOf, catalog_price: Decimal, comparison_price: Decimal
) -> None:
    captured = demo_price("464306")
    assert captured.catalog_price is not None and captured.comparison_price is not None
    price = captured.model_copy(update={
        "catalog_price": captured.catalog_price.model_copy(update={"value": catalog_price}),
        "comparison_price": captured.comparison_price.model_copy(update={"value": comparison_price}),
    })

    pack = catalog.pack_size(_product(catalog, "464306"), price, Unit.L)

    assert (pack.value, pack.source) == (Decimal(1), PackSizeSource.UNIT_CONVERSION)


def _synthetic(**overrides: object) -> Product:
    fields: dict[str, object] = {
        "id": "999001",
        "name_en": "Test butter",
        "category": "10500",
        "sales_unit": "KI",
        "base_unit": "ST",
        "sales_unit_gtin": "111",
        "synkka_gtin": "222",
        "units": (
            UnitSize(unit_id="KI", size_in_base_units=Decimal(200), gtin="111"),
            UnitSize(unit_id="ST", size_in_base_units=Decimal(1), gtin="222"),
        ),
        "allowed_lot_size": Decimal("0.01"),
    }
    fields.update(overrides)
    return Product(**fields)


def test_conversion_row_of_the_base_unit_is_multiplied_up_to_the_sales_unit(catalog: ProductCatalog) -> None:
    butter = _synthetic(
        unit_conversions=(UnitConversion(packaging_type="BASE_UNIT_OR_EACH", net_weight_kg=Decimal("0.01")),)
    )

    pack = catalog.pack_size(butter, None, Unit.KG)

    assert (pack.value, pack.source) == (Decimal(2), PackSizeSource.UNIT_CONVERSION)
    assert (pack.inner_units, pack.inner_unit_size) == (200, Decimal("0.01"))
    assert catalog.is_portion_pack(butter) is True


def test_conversion_row_of_the_case_is_used_as_it_is(catalog: ProductCatalog) -> None:
    case = _synthetic(unit_conversions=(UnitConversion(packaging_type="CASE", net_weight_kg=Decimal(2)),))

    pack = catalog.pack_size(case, None, Unit.KG)

    assert (pack.value, pack.inner_units, pack.inner_unit_size) == (Decimal(2), 200, Decimal("0.01"))


def test_sales_unit_missing_from_the_unit_rows_gives_no_size(catalog: ProductCatalog) -> None:
    orphan = _synthetic(
        name_en="Butter 500 g",
        sales_unit="PAK",
        unit_conversions=(UnitConversion(packaging_type="BASE_UNIT_OR_EACH", net_weight_kg=Decimal("0.5")),),
    )
    empty_unit = _synthetic(
        name_en="Butter 500 g",
        units=(
            UnitSize(unit_id="KI", size_in_base_units=Decimal(0), gtin="111"),
            UnitSize(unit_id="ST", size_in_base_units=Decimal(1), gtin="222"),
        ),
    )

    for product in (orphan, empty_unit):
        assert catalog.pack_size(product, None, Unit.KG).source is PackSizeSource.UNKNOWN
        assert catalog.is_portion_pack(product) is False


def test_conversion_row_that_cannot_be_tied_to_a_unit_is_not_used(catalog: ProductCatalog) -> None:
    unknown_gtin = _synthetic(
        synkka_gtin="333",
        unit_conversions=(UnitConversion(packaging_type="BASE_UNIT_OR_EACH", net_weight_kg=Decimal("0.01")),),
    )
    pallet = _synthetic(unit_conversions=(UnitConversion(packaging_type="PALLET", net_weight_kg=Decimal(400)),))

    assert catalog.pack_size(unknown_gtin, None, Unit.KG).source is PackSizeSource.UNKNOWN
    assert catalog.pack_size(pallet, None, Unit.KG).source is PackSizeSource.UNKNOWN


@pytest.mark.parametrize(
    ("name", "units_per_case", "expected"),
    [
        ("Butter portions 200x10g", 200, Decimal(2)),
        ("Butter portions 200 × 10 g", 200, Decimal(2)),
        ("Butter 500 g", 4, Decimal(2)),
        ("Butter 0,5kg", 4, Decimal(2)),
        ("4 x Butter 500 g", 4, Decimal(2)),
        ("6 x Butter 500 g", 4, None),
        ("Butter 20x100g", 4, None),
        ("Butter 500 g in a 2 kg box", 4, None),
        ("Butter 82% fat", 4, None),
        ("Butter 45x60cm sheet", 4, None),
    ],
    ids=[
        "multipack", "multipack-spaced", "single", "decimal-comma", "prefix-agrees", "prefix-disagrees",
        "multipack-disagrees", "two-sizes", "no-size", "dimensions",
    ],
)
def test_size_read_from_the_name(
    catalog: ProductCatalog, name: str, units_per_case: int, expected: Decimal | None
) -> None:
    product = _synthetic(
        name_en=name,
        units=(
            UnitSize(unit_id="KI", size_in_base_units=Decimal(units_per_case), gtin="111"),
            UnitSize(unit_id="ST", size_in_base_units=Decimal(1), gtin="222"),
        ),
    )

    pack = catalog.pack_size(product, None, Unit.KG)

    assert pack.value == expected
    assert pack.source is (PackSizeSource.NAME if expected is not None else PackSizeSource.UNKNOWN)


def test_finnish_name_is_read_when_there_is_no_english_one(catalog: ProductCatalog) -> None:
    product = _synthetic(name_en=None, name_fi="Voi 500 g", sales_unit="ST", sales_unit_gtin="222")

    pack = catalog.pack_size(product, None, Unit.KG)

    assert (pack.value, pack.source) == (Decimal("0.5"), PackSizeSource.NAME)


@pytest.mark.parametrize(
    ("name", "is_portion"),
    [
        ("Coffee cream 100x2 cl", True),
        ("Coffee cream 100x5 cl", True),
        ("Coffee cream 100x6 cl", False),
        ("Jam portions 100x25g", True),
        ("Butter portions 100x50g", True),
        ("Butter portions 100x51g", False),
        ("Bay leaf 30 g", False),  # one small item sold on its own is not a pack of portions
        ("Something without a size", False),
    ],
)
def test_portion_pack_threshold(catalog: ProductCatalog, name: str, is_portion: bool) -> None:
    product = _synthetic(name_en=name, sales_unit="ST", sales_unit_gtin="222")

    assert catalog.is_portion_pack(product) is is_portion
    assert Decimal("0.05") == PORTION_MAX_LITRES == PORTION_MAX_KG
