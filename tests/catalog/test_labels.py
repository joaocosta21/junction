"""Certificate labels (task SUST-1): the `packagingMarkedLabel` group without its storage temperatures.

Scores on the brief's optional direction "the certificates/sustainability labels already shown in the webshop"
and on the 20% "how precisely the agent matches what the buyer asked for": a buyer can require a label.
Counts are over the whole catalog (17,546 products), AIMO/docs/SCHEMA-AND-CODES.md section 2.5.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.catalog.loader import load_products
from tta.contracts.errors import InvalidRequest, SupplierUnavailable
from tta.contracts.request import ProductQuery

TEMPERATURES = ("warmTemperature", "coolTemperature", "freezeTemperature")
ORGANIC = "EU_ORGANIC_FARMING"
ORGANIC_OAT_DRINK = "460825"  # Oatly Oat Drink Organic 1L, confirmed in tonight's capture


def _record(product_id: str, labels: Any) -> dict[str, Any]:
    return {
        "id": product_id,
        "salesUnit": "ST",
        "baseUnit": "ST",
        "category": "10402",
        "allowedLotSize": 1,
        "deleted": False,
        "units": [{"unitId": "ST", "sizeInBaseUnits": 1.0}],
        "synkkaData": {
            "names": [{"language": "en", "value": "Test oat drink 1 l"}],
            "classifications": [{"name": "packagingMarkedLabel", "values": [{"id": label} for label in labels]}],
        },
    }


def _load(tmp_path: Path, *records: dict[str, Any]) -> Any:
    path = tmp_path / "products.json"
    path.write_text(json.dumps(list(records)), encoding="utf-8")
    return load_products(path)


def test_the_loader_keeps_certificate_labels_and_leaves_out_storage_temperatures(tmp_path: Path) -> None:
    (product,) = _load(tmp_path, _record("460001", ["coolTemperature", ORGANIC, "SVANEN", ORGANIC]))

    assert product.labels == (ORGANIC, "SVANEN")


def test_a_product_without_the_group_has_no_label(tmp_path: Path) -> None:
    record = _record("460001", [])
    record["synkkaData"]["classifications"] = []

    (product,) = _load(tmp_path, record)

    assert product.labels == ()


@pytest.mark.parametrize("label", ["organic farming", "eu_organic", "", 7, "A" * 61])
def test_a_label_that_is_not_a_label_code_rejects_the_file(tmp_path: Path, label: Any) -> None:
    with pytest.raises(SupplierUnavailable, match="460002"):
        _load(tmp_path, _record("460001", [ORGANIC]), _record("460002", [label]))


def test_the_catalog_counts_match_the_code_table(catalog: ProductCatalog) -> None:
    counts: dict[str, int] = {}
    for product in catalog.products:
        for label in product.labels:
            counts[label] = counts.get(label, 0) + 1

    assert not set(TEMPERATURES) & set(counts)
    assert len(counts) == 16
    assert counts[ORGANIC] == 456
    assert counts["SVANEN"] == 362
    assert counts["MARINE_STEWARDSHIP_COUNCIL_LABEL"] == 104
    assert counts["FAIR_TRADE_MARK"] == 92


def test_the_organic_oat_drink_carries_its_label(catalog: ProductCatalog) -> None:
    product = catalog.get_product(ORGANIC_OAT_DRINK)

    assert product is not None
    assert product.labels == (ORGANIC,)


def test_a_search_can_require_a_label(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(product_type="plant_drink", required_labels=(ORGANIC,)))

    assert ORGANIC_OAT_DRINK in {product.id for product in result.products}
    assert all(ORGANIC in product.labels for product in result.products)
    assert result.total < catalog.search(ProductQuery(product_type="plant_drink")).total


def test_a_label_alone_is_a_search_and_its_case_does_not_matter(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(required_labels=(" eu_organic_farming ",), limit=1000))

    assert result.total == 456


def test_a_label_no_product_carries_is_named_in_the_note(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(product_type="plant_drink", required_labels=("NOT_A_LABEL",)))

    assert result.total == 0
    assert result.note is not None
    assert "No product carries the label NOT_A_LABEL" in result.note
    assert ORGANIC in result.note


def test_a_search_with_no_filter_names_labels_among_the_filters(catalog: ProductCatalog) -> None:
    with pytest.raises(InvalidRequest, match="required_labels"):
        catalog.search(ProductQuery())
