"""The product file loader: 17,546 products into the Product contract, with the two CSV files joined."""

from __future__ import annotations

import json
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from tta.allergens import is_known_code
from tta.catalog import ProductCatalog
from tta.catalog.loader import load_metric, load_products
from tta.catalog.product_types import load_product_types
from tta.config import Settings
from tta.contracts.common import AllergenRelation
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import Catalog
from tta.contracts.request import ProductQuery

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


def _allergen_groups(allergen: Any = (), non_allergen: Any = ()) -> dict[str, Any]:
    """A `synkkaData` object with the two allergen groups and nothing else."""
    return {
        "classifications": [
            {"name": "allergen", "values": list(allergen)},
            {"name": "nonAllergen", "values": list(non_allergen)},
        ]
    }


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


def test_a_deleted_product_is_not_returned_by_any_lookup(tmp_path: Path) -> None:
    # The catalog has no deleted product today (0 of 17,546), so the file is hand-built.
    records = [
        _record("460001", substitutions=[{"substituteProduct": "460002"}, {"substituteProduct": "460003"}]),
        _record("460002", deleted=True, substitutions=[{"substituteProduct": "460001"}]),
        _record("460003"),
    ]
    catalog = ProductCatalog(load_products(_write_products(tmp_path, records)), load_product_types())

    by_ids = catalog.search(ProductQuery(product_ids=("460001", "460002", "460003")))

    assert catalog.get_product("460002") is None
    assert catalog.get_product("460001") is not None
    assert catalog.listed_substitutes("460001") == ("460003",)
    assert catalog.listed_substitutes("460002") == ()
    assert [product.id for product in catalog.same_category("460001", 5)] == ["460003"]
    assert catalog.same_category("460002", 5) == ()
    assert [product.id for product in by_ids.products] == ["460001", "460003"]
    assert by_ids.note is not None and "460002" in by_ids.note


def test_the_catalog_has_no_deleted_product(catalog: ProductCatalog) -> None:
    assert sum(product.deleted for product in catalog.products) == 0


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
        [_record(synkkaData=_allergen_groups(allergen=[{"id": "QQ", "unit": "CONTAINS"}]))],
        [_record(synkkaData=_allergen_groups(non_allergen=[{"id": "MILK", "unit": "FREE_FROM"}]))],
        [_record(synkkaData=_allergen_groups(allergen=[{"id": "  ", "unit": "MAY_CONTAIN"}]))],
        [_record(synkkaData=_allergen_groups(allergen=[{"id": 7, "unit": "CONTAINS"}]))],
    ],
    ids=[
        "missing-key", "zero-lot", "text-lot", "duplicate-id", "unknown-relation", "non-allergen-not-free-from",
        "allergen-group-free-from", "category-not-text", "lot-not-finite", "lot-boolean",
        "unknown-allergen-code", "unknown-non-allergen-code", "blank-allergen-code", "allergen-code-not-text",
    ],
)
def test_invalid_record_is_rejected_and_names_the_product(tmp_path: Path, records: list[dict[str, Any]]) -> None:
    path = _write_products(tmp_path, records)

    with pytest.raises(SupplierUnavailable) as raised:
        load_products(path)

    assert "460001" in raised.value.detail


def test_allergen_codes_are_loaded_as_the_code_table_spells_them(tmp_path: Path) -> None:
    # Unnormalised, "am" matches no excluded code and the product passes under DECLARED_ONLY.
    groups = _allergen_groups(
        allergen=[{"id": "am", "unit": "CONTAINS"}, {"id": " GO ", "unit": "MAY_CONTAIN"}],
        non_allergen=[{"id": "aw\n", "unit": "FREE_FROM"}],
    )
    path = _write_products(tmp_path, [_record(synkkaData=groups)])

    (product,) = load_products(path)

    assert [(statement.code, statement.relation) for statement in product.allergen_statements] == [
        ("AM", AllergenRelation.CONTAINS),
        ("GO", AllergenRelation.MAY_CONTAIN),
        ("AW", AllergenRelation.FREE_FROM),
    ]


def test_an_allergen_code_outside_the_code_table_rejects_the_file_and_is_named(tmp_path: Path) -> None:
    groups = _allergen_groups(allergen=[{"id": "AM", "unit": "CONTAINS"}, {"id": "QQ", "unit": "CONTAINS"}])
    path = _write_products(tmp_path, [_record("460001"), _record("460002", synkkaData=groups)])

    with pytest.raises(SupplierUnavailable) as raised:
        load_products(path)

    assert "460002" in raised.value.detail
    assert "'QQ'" in raised.value.detail
    assert "460001" not in raised.value.detail


def test_every_allergen_code_of_the_catalog_is_in_the_code_table(catalog: ProductCatalog) -> None:
    codes = {statement.code for product in catalog.products for statement in product.allergen_statements}

    # Catalog: 44 codes in `allergen` plus `UN`, only in `nonAllergen` (AIMO/docs/SCHEMA-AND-CODES.md section 2).
    assert len(codes) == 45
    assert all(is_known_code(code) for code in codes)


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


def _ingredients(*pairs: tuple[str, Any]) -> dict[str, Any]:
    """A `synkkaData` object with `keyIngredients` in the given languages, and nothing else."""
    return {"keyIngredients": [{"language": language, "value": value} for language, value in pairs]}


@pytest.mark.parametrize(
    ("synkka", "expected"),
    [
        (_ingredients(("fi", "Vesi, MANTELI"), ("en", "Water, ALMOND"), ("sv", "Vatten, MANDEL")), "Water, ALMOND"),
        (_ingredients(("sv", "Vatten, MANDEL"), ("fi", "Vesi, MANTELI")), "Vesi, MANTELI"),
        (_ingredients(("en", "   "), ("fi", " Vesi, MANTELI ")), "Vesi, MANTELI"),
        (_ingredients(("en", "-"), ("fi", "Vesi, KIRNUMAITO")), "Vesi, KIRNUMAITO"),  # as on 467297
        (_ingredients(("en", "."), ("fi", "-")), None),
        (_ingredients(("sv", "Vatten, MANDEL")), None),
        (_ingredients(), None),
        ({}, None),
    ],
    ids=[
        "english-first", "finnish-when-no-english", "blank-english", "placeholder-english", "placeholders-only",
        "swedish-only", "empty-list", "absent",
    ],
)
def test_key_ingredients_are_kept_in_english_else_finnish(
    tmp_path: Path, synkka: dict[str, Any], expected: str | None
) -> None:
    path = _write_products(tmp_path, [_record(synkkaData=synkka)])

    (product,) = load_products(path)

    assert product.key_ingredients == expected


@pytest.mark.parametrize(
    "synkka",
    [_ingredients(("en", 7)), {"keyIngredients": [{"language": "en"}]}, {"keyIngredients": "Water, ALMOND"}],
    ids=["value-not-text", "value-missing", "not-a-list"],
)
def test_malformed_key_ingredients_reject_the_file_and_name_the_product(
    tmp_path: Path, synkka: dict[str, Any]
) -> None:
    path = _write_products(tmp_path, [_record(synkkaData=synkka)])

    with pytest.raises(SupplierUnavailable) as raised:
        load_products(path)

    assert "460001" in raised.value.detail


def test_the_almond_drink_keeps_its_english_ingredient_list(catalog: ProductCatalog) -> None:
    almond_drink = catalog.get_product("465793")

    assert almond_drink is not None and almond_drink.key_ingredients is not None
    assert almond_drink.key_ingredients.startswith("Water, ALMOND (2.5%)")
    assert "MAY CONTAIN REMAINS FROM NUTS" in almond_drink.key_ingredients


def test_key_ingredients_are_kept_for_every_product_that_has_them_in_english_or_finnish(
    catalog: ProductCatalog,
) -> None:
    # Whole catalog: 11,562 products have an English list and 2,427 more a Finnish one only.
    assert sum(product.key_ingredients is not None for product in catalog.products) == 11_562 + 2_427
