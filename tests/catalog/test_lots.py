"""Lot rounding: a quantity in sales units goes up to the product's step, in Decimal."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tta.catalog import ProductCatalog
from tta.contracts.errors import InvalidRequest
from tta.contracts.product import Product


def _product(catalog: ProductCatalog, product_id: str) -> Product:
    product = catalog.get_product(product_id)
    assert product is not None
    return product


def test_step_of_one_and_a_half(catalog: ProductCatalog) -> None:
    ham = _product(catalog, "462356")  # sold per KG in pieces of about 1.5 kg

    assert ham.allowed_lot_size == Decimal("1.5")
    assert catalog.round_to_lot(ham, Decimal(4)) == Decimal("4.5")
    assert catalog.round_to_lot(ham, Decimal("4.5")) == Decimal("4.5")
    assert catalog.round_to_lot(ham, Decimal("0.1")) == Decimal("1.5")


def test_step_of_three_kilograms(catalog: ProductCatalog) -> None:
    beef = _product(catalog, "464744")

    assert beef.allowed_lot_size == Decimal(3)
    assert catalog.round_to_lot(beef, Decimal(30)) == Decimal(30)
    assert catalog.round_to_lot(beef, Decimal(31)) == Decimal(33)


def test_fractional_steps_stay_exact_multiples(catalog: ProductCatalog) -> None:
    fractional = [p for p in catalog.products if p.allowed_lot_size not in (Decimal("0.01"), Decimal(1))]

    assert len(fractional) > 600
    for product in fractional:
        rounded = catalog.round_to_lot(product, Decimal("10.3"))
        assert rounded >= Decimal("10.3")
        assert rounded % product.allowed_lot_size == 0
        assert rounded - product.allowed_lot_size < Decimal("10.3")


def test_countable_unit_without_a_real_step_goes_up_to_whole_units(catalog: ProductCatalog) -> None:
    carton = _product(catalog, "464306")  # sales unit ST, allowedLotSize 0.01: no constraint in the file

    assert catalog.round_to_lot(carton, Decimal("99.85")) == Decimal(100)
    assert catalog.round_to_lot(carton, Decimal(1000)) == Decimal(1000)
    # 1,000 litres in 20-litre units: the answer reads "50", never "5E+1".
    assert str(catalog.round_to_lot(carton, Decimal(1000) / Decimal("20.0"))) == "50"


def test_weight_unit_without_a_real_step_keeps_ten_gram_steps(catalog: ProductCatalog) -> None:
    cucumber = _product(catalog, "460012")  # sales unit KG, allowedLotSize 0.01

    assert cucumber.sales_unit == "KG"
    assert catalog.round_to_lot(cucumber, Decimal("2.345")) == Decimal("2.35")
    assert catalog.round_to_lot(cucumber, Decimal("2.34")) == Decimal("2.34")


@pytest.mark.parametrize("quantity", [Decimal(0), Decimal(-1), Decimal("NaN"), Decimal("Infinity")])
def test_quantity_must_be_a_positive_number(catalog: ProductCatalog, quantity: Decimal) -> None:
    with pytest.raises(InvalidRequest):
        catalog.round_to_lot(_product(catalog, "464306"), quantity)
