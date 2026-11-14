"""The ingredient statements on the product (lane FC): every one the file gives, with its language, as data."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from tta.catalog import ProductCatalog
from tta.catalog.loader import load_products
from tta.contracts.product import IngredientStatement, Product

ARLA_PRO_WHIPPING_CREAM = "469346"
RAMA_WHIPPING = "467142"  # its English statement is "-": a placeholder, not a list


def _load(tmp_path: Path, entries: list[dict[str, Any]]) -> Product:
    record = {
        "id": "460001", "salesUnit": "ST", "baseUnit": "ST", "category": "10400", "allowedLotSize": 1.0,
        "deleted": False, "units": [{"unitId": "ST", "sizeInBaseUnits": 1.0}],
        "synkkaData": {"names": [{"language": "en", "value": "Test milk 1 l"}], "keyIngredients": entries},
    }
    path = tmp_path / "products.json"
    path.write_text(json.dumps([record]), encoding="utf-8")
    (product,) = load_products(path)
    return product


def test_every_statement_is_kept_with_the_language_the_file_gives_it(catalog: ProductCatalog) -> None:
    # Arrange / Act
    statements = catalog.get_product(ARLA_PRO_WHIPPING_CREAM).ingredient_statements

    # Assert
    assert statements == (
        IngredientStatement(language="en", text="CREAM, lactase enzyme, stabilizer (carrageenan)."),
        IngredientStatement(language="fi", text="KERMA, laktaasientsyymi, stabilointiaine (karrageeni)."),
        IngredientStatement(language="sv", text="GRÄDDE, laktasenzym, stabiliseringsmedel(karragenan)."),
    )


def test_a_placeholder_is_not_a_statement(tmp_path: Path, catalog: ProductCatalog) -> None:
    product = _load(tmp_path, [{"language": "en", "value": " - "}, {"language": "fi", "value": " MAITO, suola "}])

    assert product.ingredient_statements == (IngredientStatement(language="fi", text="MAITO, suola"),)
    assert [each.language for each in catalog.get_product(RAMA_WHIPPING).ingredient_statements] == ["fi", "sv"]


def test_the_first_statement_of_a_language_wins_and_no_statement_is_an_empty_tuple(tmp_path: Path) -> None:
    twice = _load(tmp_path, [{"language": "en", "value": "MILK"}, {"language": "en", "value": "CREAM"}])
    none = _load(tmp_path, [])

    assert twice.ingredient_statements == (IngredientStatement(language="en", text="MILK"),)
    assert twice.key_ingredients == "MILK"
    assert none.ingredient_statements == ()


def test_the_languages_of_the_whole_catalog(catalog: ProductCatalog) -> None:
    # Whole catalog, 17,546 products: which products carry a statement in English, in Finnish, in both, in neither.
    languages = [{each.language for each in product.ingredient_statements} for product in catalog.products]
    both = sum("en" in each and "fi" in each for each in languages)
    english_only = sum("en" in each and "fi" not in each for each in languages)
    finnish_only = sum("fi" in each and "en" not in each for each in languages)
    neither = sum("en" not in each and "fi" not in each for each in languages)

    assert (both, english_only, finnish_only, neither) == (11_560, 2, 2_427, 3_557)
    assert sum(bool(each) for each in languages) == 13_990  # one product has a statement in Swedish only
    assert Counter(language for each in languages for language in each).most_common(3) == [
        ("fi", 13_987), ("sv", 12_545), ("en", 11_562),
    ]


def test_key_ingredients_is_the_english_statement_else_the_finnish_one(catalog: ProductCatalog) -> None:
    for product in catalog.products:
        texts = {each.language: each.text for each in product.ingredient_statements}
        assert product.key_ingredients == texts.get("en", texts.get("fi"))
