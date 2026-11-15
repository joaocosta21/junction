"""The product-type table: our own short table from a key to categories, name terms and claims."""

from __future__ import annotations

from pathlib import Path

import pytest

from tta.catalog import ProductCatalog
from tta.catalog.product_types import PRODUCT_TYPES_FILE, load_product_types
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.request import ProductQuery

REQUIRED_KEYS = {"milk", "plant_drink", "beef_chuck"}
CREAM_EXCLUDE_TERMS = ("vegetable", "kasvirasva", "alternative", "rama professional", "quark", "mousse")
# Review finding C3-F3, 15 Nov 2026: varieties of cream, found through the type only when a request names them.
CREAM_VARIETY_TERMS = ("flavoured", "sweet chili", "spray", "whipped", "kermavaahto")
# Category 10401: the vegetable-fat blends. Each ingredient list (in Finnish for the three Rama products,
# whose English list reads "-") names a vegetable oil or fat.
VEGETABLE_FAT_WORDS = ("vegetable", "rapeseed", "kasvirasv", "kasviöljy", "palmuöljy")
VEGETABLE_FAT_BLENDS = {"462703", "463254", "463299", "463975", "469160", "469162", "467142", "467173", "467297"}
MAX_PRODUCT_IDS = 1000


def test_table_has_the_demo_types_and_twenty_to_thirty_two_entries(catalog: ProductCatalog) -> None:
    keys = catalog.product_type_keys()

    assert set(keys) >= REQUIRED_KEYS
    assert 20 <= len(keys) <= 32  # 31 until coffee milk became a type of its own (14 Nov 2026)
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
        "milk:\n  categories: ['10400']\n  exclude_terms: ['sour', ' - ']\n  products: 1\n  derived_from: x\n",
        "milk:\n  categories: ['10400']\n  exclude_terms: sour\n  products: 1\n  derived_from: x\n",
    ],
    ids=[
        "broken-yaml", "not-a-mapping", "no-category", "no-derivation", "unknown-field", "empty",
        "entry-not-a-mapping", "key-given-twice", "category-not-quoted", "blank-exclude-term",
        "exclude-terms-not-a-list",
    ],
)
def test_invalid_table_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "product_types.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(SupplierUnavailable):
        load_product_types(path)


def test_exclude_terms_are_read_from_the_table(tmp_path: Path) -> None:
    path = tmp_path / "product_types.yaml"
    path.write_text(
        "milk:\n  categories: ['10400']\n  exclude_terms: ['sour', 'piimä']\n  products: 1\n  derived_from: x\n",
        encoding="utf-8",
    )

    assert load_product_types(path)["milk"].exclude_terms == ("sour", "piimä")
    assert load_product_types(PRODUCT_TYPES_FILE)["cream"].exclude_terms == CREAM_EXCLUDE_TERMS
    assert load_product_types(PRODUCT_TYPES_FILE)["cream"].variety_terms == CREAM_VARIETY_TERMS


def test_missing_table_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SupplierUnavailable):
        load_product_types(tmp_path / "absent.yaml")


def test_cream_leaves_out_the_vegetable_fat_blends(catalog: ProductCatalog) -> None:
    cream = catalog.search(ProductQuery(product_type="cream", limit=MAX_PRODUCT_IDS))
    blends = catalog.search(ProductQuery(product_type="vegetable_cream", limit=MAX_PRODUCT_IDS))

    assert not VEGETABLE_FAT_BLENDS & {product.id for product in cream.products}
    assert {product.id for product in blends.products} == VEGETABLE_FAT_BLENDS
    # Category 10401, whole catalog: 53 products, of which a quark and a protein mousse are of neither type;
    # since 15 Nov 2026 the 7 flavoured cooking creams and the 3 whipped creams in a spray can are varieties
    # of cream, which a request for plain "cream" does not find.
    assert cream.total + blends.total == 53 - 2 - 10


def test_every_vegetable_fat_blend_names_a_vegetable_fat_in_its_ingredient_list(catalog: ProductCatalog) -> None:
    for product_id in VEGETABLE_FAT_BLENDS:
        product = catalog.get_product(product_id)
        assert product is not None and product.key_ingredients is not None
        text = product.key_ingredients.casefold()
        assert any(word in text for word in VEGETABLE_FAT_WORDS), product_id


def _of_type(catalog: ProductCatalog, key: str) -> set[str]:
    return {product.id for product in catalog.search(ProductQuery(product_type=key, limit=MAX_PRODUCT_IDS)).products}


def test_butter_holds_no_plant_based_block_and_cream_no_quark_or_mousse(catalog: ProductCatalog) -> None:
    # Whole catalog. 471792 Eleplant "plant power" is filed in the butter category 10500 and carries VEGAN;
    # 473205 is a layered quark and 473461 a protein mousse, both filed in the cream category 10401.
    butter, cream = _of_type(catalog, "butter"), _of_type(catalog, "cream")

    assert "471792" not in butter
    assert len(butter) == 15  # 19 before 15 Nov 2026: clarified (2), brown and laminating butter are varieties
    assert all("VEGAN" not in catalog.get_product(product_id).nutritional_claims for product_id in butter)
    assert not {"473205", "473461"} & cream
    assert len(cream) == 32  # 42 before 15 Nov 2026
    assert {"464194", "464249", "469346"} <= cream  # whipping and cooking creams stay
    assert {"464411", "464205", "475797"} <= butter  # unsalted and salted butter stay
    # What a cook would not accept for "butter" in a recipe is found only when the request names it.
    assert not {"464761", "472127", "475708", "474681"} & butter  # laminating, clarified (2), brown
