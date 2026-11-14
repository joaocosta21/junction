"""The product file loader: 17,546 products into the Product contract, with the two CSV files joined."""

from __future__ import annotations

import json
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.catalog.loader import load_metric, load_products
from tta.config import Settings
from tta.contracts.common import AllergenRelation
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import Catalog

CATALOG_SIZE = 17_546
LOAD_BUDGET_SECONDS = 3.0


def _record(product_id: str = "460001", **overrides: Any) -> dict[str, Any]:
    """A minimal record with every required key of the product file."""
    record: dict[str, Any] = {
        "id": product_id,
        "salesUnit": "ST",
        "baseUnit": "ST",
        "category": "10400",
        "allowedLotSize": 0.01,
        "deleted": False,
        "vendorName": "TEST VENDOR",
        "units": [{"unitId": "ST", "sizeInBaseUnits": 1.0}],
        "deposits": [],
        "synkkaData": {"names": [{"language": "fi", "value": "Testimaito 1 l"}], "classifications": []},
    }
    record.update(overrides)
    return record


def _write_products(tmp_path: Path, records: Any) -> Path:
    path = tmp_path / "products.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def test_loads_all_products_in_under_three_seconds() -> None:
    started = time.perf_counter()
    catalog = ProductCatalog.from_settings(Settings.for_tests())
    elapsed = time.perf_counter() - started

    assert len(catalog.products) == CATALOG_SIZE
    assert elapsed < LOAD_BUDGET_SECONDS


def test_catalog_satisfies_the_catalog_port(catalog: ProductCatalog) -> None:
    assert isinstance(catalog, Catalog)


def test_product_keeps_the_fields_the_system_uses(catalog: ProductCatalog) -> None:
    product = catalog.get_product("464306")

    assert product is not None
    assert product.name_en == "Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free"
    assert product.name_fi == "Valio Hyvä suomalainen Arki® Eila® kevytmaitojuoma 1 l laktoositon"
    assert product.brand == "Valio"
    assert product.vendor_name == "VALIO OY TUORE"
    assert product.category == "10400"
    assert (product.sales_unit, product.base_unit) == ("ST", "ST")
    assert product.sales_unit_gtin == "6408430000487"
    assert product.synkka_gtin == "6408430000487"
    assert {unit.unit_id: unit.size_in_base_units for unit in product.units} == {
        "KRS": Decimal(160), "PAL": Decimal(160), "KI": Decimal(20), "ST": Decimal(1),
    }
    assert product.allowed_lot_size == Decimal("0.01")
    assert product.variable_weight is False
    assert "FREE_FROM_LACTOSE" in product.nutritional_claims
    assert [(s.code, s.relation) for s in product.allergen_statements] == [("AM", AllergenRelation.CONTAINS)]
    assert product.has_allergen_groups is True
    assert product.listed_substitutes == ("465039", "464398", "469363", "464201")
    assert product.country_of_origin == "FI"
    assert product.countries_of_origin == ("246",)
    assert product.deleted is False


def test_unit_conversion_keeps_only_real_volumes_and_weights(catalog: ProductCatalog) -> None:
    milk = catalog.get_product("464306")
    beef = catalog.get_product("464744")

    assert milk is not None and beef is not None
    assert milk.unit_conversions[0].packaging_type == "BASE_UNIT_OR_EACH"
    assert milk.unit_conversions[0].volume_l == Decimal(1)
    assert milk.unit_conversions[0].net_weight_kg == Decimal("1.025")
    # The beef row says volume 3000 GRM: a mass in the volume field (AIMO/docs/PRODUCT-DATA.md section 5).
    assert beef.unit_conversions[0].volume_l is None
    assert beef.unit_conversions[0].net_weight_kg == Decimal(3)


def test_free_from_statements_come_from_the_non_allergen_group(catalog: ProductCatalog) -> None:
    soya_drink = catalog.get_product("464056")

    assert soya_drink is not None
    relations = {statement.code: statement.relation for statement in soya_drink.allergen_statements}
    assert relations["AY"] is AllergenRelation.CONTAINS
    assert relations["AM"] is AllergenRelation.FREE_FROM
    assert relations["AW"] is AllergenRelation.FREE_FROM


def test_missing_facts_stay_none(catalog: ProductCatalog, raw_products: list[dict[str, Any]]) -> None:
    thin_ids = [raw["id"] for raw in raw_products if "variableUnit" not in raw["synkkaData"]]
    no_groups = [raw["id"] for raw in raw_products if not raw["synkkaData"].get("classifications")]

    assert len(thin_ids) == 3_068
    assert all(catalog.get_product(product_id).variable_weight is None for product_id in thin_ids)
    assert len(no_groups) == 11
    assert all(catalog.get_product(product_id).has_allergen_groups is False for product_id in no_groups)
    assert sum(product.variable_weight is True for product in catalog.products) == 632


def test_origin_placeholders_are_not_an_origin(catalog: ProductCatalog, raw_products: list[dict[str, Any]]) -> None:
    placeholder_ids = [raw["id"] for raw in raw_products if raw.get("countryOfOrigin") in ("zy", "xs", "zz")]
    absent_ids = [raw["id"] for raw in raw_products if "countryOfOrigin" not in raw]

    assert len(placeholder_ids) == 195 and len(absent_ids) == 9
    assert all(catalog.get_product(product_id).country_of_origin is None for product_id in placeholder_ids + absent_ids)


def test_deposits_are_loaded(catalog: ProductCatalog) -> None:
    with_deposits = [product for product in catalog.products if product.has_deposits]

    assert len(with_deposits) == 506
    assert sum(len(product.deposits) for product in with_deposits) == 576
    assert {deposit.unit for product in with_deposits for deposit in product.deposits} == {"ST"}


def test_reliability_and_carbon_are_joined_and_never_imputed(catalog: ProductCatalog) -> None:
    with_reliability = [p for p in catalog.products if p.delivery_reliability is not None]
    with_carbon = [p for p in catalog.products if p.carbon_kg_co2e_per_kg is not None]
    first = catalog.get_product("460001")

    assert len(with_reliability) == 4_425
    assert len(with_carbon) == 11_033
    assert first is not None
    assert first.delivery_reliability == Decimal("1.0")
    assert first.carbon_kg_co2e_per_kg == Decimal("1.44")
    assert sum(p.delivery_reliability is None and p.carbon_kg_co2e_per_kg is None for p in catalog.products) > 0


def test_250_listed_substitution_pairs_on_189_products(catalog: ProductCatalog) -> None:
    owners = [product for product in catalog.products if product.listed_substitutes]

    assert len(owners) == 189
    assert sum(len(product.listed_substitutes) for product in owners) == 250


def test_unknown_id_returns_nothing_without_an_exception(catalog: ProductCatalog) -> None:
    assert catalog.get_product("459999") is None
    assert catalog.get_product("") is None
    assert catalog.listed_substitutes("459999") == ()
    assert catalog.same_category("459999", 5) == ()


def test_loader_without_csv_files_leaves_both_metrics_unknown(tmp_path: Path) -> None:
    path = _write_products(tmp_path, [_record()])

    (product,) = load_products(path)

    assert product.id == "460001"
    assert product.name_en is None and product.name_fi == "Testimaito 1 l"
    assert product.delivery_reliability is None and product.carbon_kg_co2e_per_kg is None


def test_missing_product_file_is_reported_by_file_name_only(tmp_path: Path) -> None:
    missing = tmp_path / "secret-folder" / "nothing.json"

    with pytest.raises(SupplierUnavailable) as raised:
        load_products(missing)

    assert "nothing.json" in raised.value.detail
    assert "secret-folder" not in raised.value.detail


@pytest.mark.parametrize(
    "content",
    ["{not json", json.dumps({"id": "460001"}), json.dumps([]), json.dumps(["not a record"])],
    ids=["broken-json", "not-a-list", "empty-list", "record-not-an-object"],
)
def test_malformed_product_file_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "products.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(SupplierUnavailable):
        load_products(path)


@pytest.mark.parametrize(
    "records",
    [
        [{key: value for key, value in _record().items() if key != "category"}],
        [_record(allowedLotSize=0)],
        [_record(allowedLotSize="a lot")],
        [_record(), _record()],
        [_record(synkkaData={"classifications": [
            {"name": "allergen", "values": [{"id": "AM", "unit": "PROBABLY"}]}]})],
        [_record(synkkaData={"classifications": [
            {"name": "nonAllergen", "values": [{"id": "AM", "unit": "CONTAINS"}]}]})],
        [_record(synkkaData={"classifications": [
            {"name": "allergen", "values": [{"id": "AM", "unit": "FREE_FROM"}]}]})],
        [_record(category=10400)],
        [_record(allowedLotSize=float("nan"))],
        [_record(allowedLotSize=True)],
    ],
    ids=[
        "missing-key", "zero-lot", "text-lot", "duplicate-id", "unknown-relation", "non-allergen-not-free-from",
        "allergen-group-free-from", "category-not-text", "lot-not-finite", "lot-boolean",
    ],
)
def test_invalid_record_is_rejected_and_names_the_product(tmp_path: Path, records: list[dict[str, Any]]) -> None:
    path = _write_products(tmp_path, records)

    with pytest.raises(SupplierUnavailable) as raised:
        load_products(path)

    assert "460001" in raised.value.detail


def test_metric_file_is_validated(tmp_path: Path) -> None:
    good = tmp_path / "good.csv"
    good.write_text("productId,deliveryReliability\r\n460001,1.0\r\n460002,0.25\r\n", encoding="utf-8")

    assert load_metric(good, "deliveryReliability", maximum=Decimal(1)) == {
        "460001": Decimal("1.0"), "460002": Decimal("0.25"),
    }


@pytest.mark.parametrize(
    "content",
    [
        "product,deliveryReliability\n460001,1.0\n",
        "productId,deliveryReliability\n460001,high\n",
        "productId,deliveryReliability\n460001,1.5\n",
        "productId,deliveryReliability\n460001,-0.1\n",
        "productId,deliveryReliability\n460001,NaN\n",
        "productId,deliveryReliability\n,1.0\n",
        "productId,deliveryReliability\n460001,1.0\n460001,0.5\n",
    ],
    ids=["header", "not-a-number", "above-maximum", "negative", "nan", "empty-id", "duplicate"],
)
def test_invalid_metric_file_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "metric.csv"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(SupplierUnavailable):
        load_metric(path, "deliveryReliability", maximum=Decimal(1))


def test_missing_metric_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SupplierUnavailable):
        load_metric(tmp_path / "absent.csv", "deliveryReliability", maximum=Decimal(1))
