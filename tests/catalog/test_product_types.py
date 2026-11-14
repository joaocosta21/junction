"""The product-type table: our own short table from a key to categories, name terms and claims."""

from __future__ import annotations

from pathlib import Path

import pytest

from tta.catalog import ProductCatalog
from tta.catalog.product_types import PRODUCT_TYPES_FILE, load_product_types
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.request import ProductQuery

REQUIRED_KEYS = {"milk", "plant_drink", "beef_chuck"}
MAX_PRODUCT_IDS = 1000


def test_table_has_the_demo_types_and_twenty_to_thirty_entries(catalog: ProductCatalog) -> None:
    keys = catalog.product_type_keys()

    assert set(keys) >= REQUIRED_KEYS
    assert 20 <= len(keys) <= 30
    assert list(keys) == sorted(keys)


def test_every_entry_says_how_it_was_derived_and_uses_real_categories(catalog: ProductCatalog) -> None:
    categories = {product.category for product in catalog.products}
    claims = {claim for product in catalog.products for claim in product.nutritional_claims}

    for product_type in load_product_types(PRODUCT_TYPES_FILE).values():
        assert product_type.derived_from.strip(), product_type.key
        assert product_type.categories, product_type.key
        assert set(product_type.categories) <= categories, product_type.key
        assert set(product_type.claims) <= claims, product_type.key


def test_every_entry_finds_the_number_of_products_its_note_states(catalog: ProductCatalog) -> None:
    for product_type in load_product_types(PRODUCT_TYPES_FILE).values():
        result = catalog.search(ProductQuery(product_type=product_type.key, limit=MAX_PRODUCT_IDS))

        assert result.total == product_type.products, product_type.key
        assert 0 < result.total <= MAX_PRODUCT_IDS, product_type.key
        assert str(product_type.products) in product_type.derived_from, product_type.key


@pytest.mark.parametrize(
    "content",
    [
        "milk: [unclosed",
        "- milk\n- cream\n",
        "milk:\n  categories: []\n  products: 1\n  derived_from: none\n",
        "milk:\n  categories: ['10400']\n  products: 1\n",
        "milk:\n  categories: ['10400']\n  products: 1\n  derived_from: x\n  colour: white\n",
        "",
        "milk: 5\n",
        "milk:\n  key: cream\n  categories: ['10400']\n  products: 1\n  derived_from: x\n",
        "milk:\n  categories: [10400]\n  products: 1\n  derived_from: x\n",
    ],
    ids=[
        "broken-yaml", "not-a-mapping", "no-category", "no-derivation", "unknown-field", "empty",
        "entry-not-a-mapping", "key-given-twice", "category-not-quoted",
    ],
)
def test_invalid_table_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "product_types.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(SupplierUnavailable):
        load_product_types(path)


def test_missing_table_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SupplierUnavailable):
        load_product_types(tmp_path / "absent.yaml")
