"""The allergen rules on the real catalog, read through the catalog loader (T02).

Skipped while `tta.catalog.loader` does not exist. Every figure here is from the whole catalog
(17,546 products), not from a sample.
"""

from __future__ import annotations

import pytest

from tta.allergens import check_exclusions, check_substitute
from tta.config import Settings
from tta.contracts.common import AllergenOutcome, AllergenRelation, AllergenStrictness
from tta.contracts.product import Product

loader = pytest.importorskip("tta.catalog.loader")

MILK_CATEGORY = "10400"
LACTOSE_FREE_CLAIM = "FREE_FROM_LACTOSE"  # a nutritional claim: never an input to the allergen rules
LACTOSE_FREE_MILKS = 35  # AIMO/FINDINGS.md section 2, the canonical request
LISTED_SUBSTITUTES = 249  # 250 pairs, one product lists itself (AIMO/FINDINGS.md section 5)
FAILING_LISTED_SUBSTITUTES = 37  # AIMO/PLAN.md, scenario 3 in numbers
FAILING_WITH_DATA_ON_THE_ORIGINAL = 20

SOYA_DRINK = "464056"
OAT_DRINK_WITH_GLUTEN = "468319"
GLUTEN_FREE_OAT_DRINK = "473609"


@pytest.fixture(scope="module")
def products() -> dict[str, Product]:
    loaded = loader.load_products(Settings.for_tests().tta_product_file)
    return {product.id: product for product in loaded}


@pytest.mark.parametrize("strictness", list(AllergenStrictness))
def test_all_lactose_free_milks_are_rejected_for_milk(
    products: dict[str, Product], strictness: AllergenStrictness
) -> None:
    lactose_free_milks = [
        product
        for product in products.values()
        if product.category == MILK_CATEGORY and LACTOSE_FREE_CLAIM in product.nutritional_claims
    ]

    outcomes = [
        check_exclusions(product.allergen_statements, ["AM"], strictness).outcome for product in lactose_free_milks
    ]

    assert len(lactose_free_milks) == LACTOSE_FREE_MILKS
    assert outcomes == [AllergenOutcome.REJECT] * LACTOSE_FREE_MILKS


def test_the_soya_drink_passes_with_milk_and_gluten_excluded_under_strict(products: dict[str, Product]) -> None:
    check = check_exclusions(products[SOYA_DRINK].allergen_statements, ["AM", "AW"], AllergenStrictness.STRICT)

    assert check.outcome is AllergenOutcome.PASS
    assert check.all_explicit
    assert [finding.relation for finding in check.findings] == [AllergenRelation.FREE_FROM] * 2


def test_the_oat_drink_that_declares_gluten_cereals_is_rejected(products: dict[str, Product]) -> None:
    statements = products[OAT_DRINK_WITH_GLUTEN].allergen_statements

    check = check_exclusions(statements, ["AM", "AW"], AllergenStrictness.STRICT)

    rejected = [finding.excluded_code for finding in check.findings if finding.outcome is AllergenOutcome.REJECT]
    assert check.outcome is AllergenOutcome.REJECT
    assert rejected == ["AW"]


def test_the_gluten_free_oat_drink_goes_to_a_human_when_gluten_is_excluded(products: dict[str, Product]) -> None:
    statements = products[GLUTEN_FREE_OAT_DRINK].allergen_statements

    check = check_exclusions(statements, ["AW"], AllergenStrictness.DECLARED_ONLY)

    assert check.outcome is AllergenOutcome.TO_HUMAN
    assert check.findings[0].matched_code == "GO"


def test_the_listed_substitute_with_the_same_declarations_passes(products: dict[str, Product]) -> None:
    original = products[GLUTEN_FREE_OAT_DRINK]

    check = check_substitute(original.allergen_statements, products["471690"].allergen_statements)

    assert check.passes


@pytest.mark.parametrize("substitute_id", ["471881", "464320"])
def test_the_listed_substitutes_that_add_gluten_cereals_fail(products: dict[str, Product], substitute_id: str) -> None:
    original = products[GLUTEN_FREE_OAT_DRINK]

    check = check_substitute(original.allergen_statements, products[substitute_id].allergen_statements)

    assert not check.passes
    assert [(statement.code, statement.relation) for statement in check.added] == [("AW", AllergenRelation.CONTAINS)]


def test_how_many_listed_substitutes_fail_the_substitution_rule(products: dict[str, Product]) -> None:
    pairs = [
        (product, products[substitute_id])
        for product in products.values()
        for substitute_id in product.listed_substitutes
        if substitute_id != product.id
    ]

    failing = [
        original
        for original, substitute in pairs
        if not check_substitute(original.allergen_statements, substitute.allergen_statements).passes
    ]

    assert len(pairs) == LISTED_SUBSTITUTES
    assert len(failing) == FAILING_LISTED_SUBSTITUTES
    assert sum(1 for original in failing if original.allergen_statements) == FAILING_WITH_DATA_ON_THE_ORIGINAL


def test_the_rules_run_over_every_product_without_an_error(products: dict[str, Product]) -> None:
    outcomes = {
        check_exclusions(product.allergen_statements, ["AM", "AW"], strictness).outcome
        for product in products.values()
        for strictness in AllergenStrictness
    }

    assert outcomes == set(AllergenOutcome)
