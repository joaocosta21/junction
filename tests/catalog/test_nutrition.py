"""Nutrition per 100 g or ml on the product (P10 F1): read as the file states it, never imputed."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.catalog.loader import load_products
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.product import NutritionBasis, Product

WHIPPING_CREAM = "464194"  # Valio whipping cream 1 l: 38 / 22 / 2.0 / 2.8 / 2.8 / 0.07 per 100 g
RAMA_WHIPPING = "467142"  # Rama Professional Whipping 30%: its figures are per 100 ml


def _row(nutrient: str, value: float, **overrides: Any) -> dict[str, Any]:
    row = {"id": nutrient, "value": value, "unit": "GRM", "basisQuantity": 100.0, "basisQuantityUnit": "GRM"}
    return {**row, **overrides}


def _load(tmp_path: Path, rows: list[dict[str, Any]]) -> Product:
    record = {
        "id": "460001", "salesUnit": "ST", "baseUnit": "ST", "category": "10400", "allowedLotSize": 1.0,
        "deleted": False, "units": [{"unitId": "ST", "sizeInBaseUnits": 1.0}],
        "synkkaData": {"names": [{"language": "en", "value": "Test milk 1 l"}], "nutritionalContent": rows},
    }
    path = tmp_path / "products.json"
    path.write_text(json.dumps([record]), encoding="utf-8")
    (product,) = load_products(path)
    return product


def test_the_six_nutrients_of_a_whipping_cream_are_read_per_100_g(catalog: ProductCatalog) -> None:
    nutrition = catalog.get_product(WHIPPING_CREAM).nutrition

    assert nutrition is not None
    assert (nutrition.fat, nutrition.saturated_fat, nutrition.protein) == (38, 22, 2)
    assert (nutrition.carbohydrate, nutrition.sugars) == (Decimal("2.8"), Decimal("2.8"))
    assert nutrition.salt == Decimal("0.07")
    assert nutrition.basis is NutritionBasis.G
    assert nutrition.is_complete


def test_figures_stated_per_100_ml_keep_that_basis(catalog: ProductCatalog) -> None:
    nutrition = catalog.get_product(RAMA_WHIPPING).nutrition

    assert nutrition is not None
    assert nutrition.basis is NutritionBasis.ML
    assert nutrition.fat == Decimal("30.0")


def test_whole_catalog_how_many_products_state_the_six_nutrients(catalog: ProductCatalog) -> None:
    with_any = [product for product in catalog.products if product.nutrition is not None]
    complete = [product for product in with_any if product.nutrition.is_complete]
    dairy = [product for product in catalog.products if product.category.startswith("104")]

    # Whole catalog, 17,546 products: fat, saturated fat, protein, carbohydrate, sugars and salt, all six in
    # grams per 100 g or ml. (The plan's 11,538 counted energy in place of saturated fat.)
    assert len(catalog.products) == 17_546
    assert len(complete) == 11_511
    assert len(with_any) == 12_060
    assert sum(product.nutrition is not None and product.nutrition.is_complete for product in dairy) == 611
    assert len(dairy) == 620


def test_a_row_that_is_not_per_100_g_or_ml_is_not_read(tmp_path: Path) -> None:
    product = _load(tmp_path, [_row("FAT", 3.5, basisQuantity=250.0), _row("PRO-", 3.2, basisQuantityUnit="PTN")])

    assert product.nutrition is None


def test_a_missing_nutrient_stays_unknown_and_the_six_are_then_not_complete(tmp_path: Path) -> None:
    product = _load(tmp_path, [_row("FAT", 3.5), _row("ENER-E14", 64.0, unit="E14")])

    assert product.nutrition is not None
    assert product.nutrition.fat == Decimal("3.5")
    assert product.nutrition.salt is None
    assert not product.nutrition.is_complete


def test_a_value_that_is_not_in_grams_is_not_read_as_grams(tmp_path: Path) -> None:
    product = _load(tmp_path, [_row("FAT", 3.5), _row("SALTEQ", 100.0, unit="MGM")])

    assert product.nutrition is not None
    assert product.nutrition.salt is None


def test_a_nutrient_stated_twice_with_two_values_stays_unknown(tmp_path: Path) -> None:
    product = _load(tmp_path, [_row("FAT", 3.5), _row("FAT", 1.5), _row("PRO-", 3.2), _row("PRO-", 3.2)])

    assert product.nutrition is not None
    assert product.nutrition.fat is None
    assert product.nutrition.protein == Decimal("3.2")


def test_figures_on_both_bases_are_not_mixed(tmp_path: Path) -> None:
    product = _load(tmp_path, [_row("FAT", 3.5), _row("PRO-", 3.2, basisQuantityUnit="MLT")])

    assert product.nutrition is None


def test_a_product_with_no_nutrition_rows_has_none(tmp_path: Path) -> None:
    assert _load(tmp_path, []).nutrition is None


@pytest.mark.parametrize("value", [-1.0, "3.5", None])
def test_a_nutrient_value_that_is_not_a_number_from_zero_up_rejects_the_file(tmp_path: Path, value: Any) -> None:
    with pytest.raises(SupplierUnavailable):
        _load(tmp_path, [_row("FAT", value)])
