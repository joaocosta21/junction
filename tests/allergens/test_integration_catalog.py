"""The allergen rules on the real catalog, read through the catalog loader (T02).

Skipped while `tta.catalog.loader` does not exist. Every figure here is from the whole catalog
(17,546 products), not from a sample.
"""

from __future__ import annotations

import pytest

from tta.allergens import check_exclusions, check_substitute, parent_of
from tta.config import Settings
from tta.contracts.common import AllergenOutcome, AllergenRelation, AllergenStrictness
from tta.contracts.product import Product

loader = pytest.importorskip("tta.catalog.loader")

MILK_CATEGORY = "10400"
LACTOSE_FREE_CLAIM = "FREE_FROM_LACTOSE"  # a nutritional claim: never an input to the allergen rules
# Category 10400 with the claim: the 30 milks of the `milk` product type, 4 sour milks and a coffee drink.
LACTOSE_FREE_MILKS = 35
LISTED_SUBSTITUTES = 249  # 250 pairs, one product lists itself (AIMO/FINDINGS.md section 5)
FAILING_LISTED_SUBSTITUTES = 37  # AIMO/PLAN.md, scenario 3 in numbers
FAILING_WITH_DATA_ON_THE_ORIGINAL = 20
RAISED_ON_LISTED_SUBSTITUTES = 0  # no listed pair raises an allergen from MAY_CONTAIN to CONTAINS
DECLARING = (AllergenRelation.CONTAINS, AllergenRelation.MAY_CONTAIN)

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

    checks = [
        (original, check_substitute(original.allergen_statements, substitute.allergen_statements))
        for original, substitute in pairs
    ]
    failing = [original for original, check in checks if not check.passes]
    raised = [
        original.id
        for original, check in checks
        if _declared_codes(original) & {statement.code for statement in check.added}
    ]

    assert len(pairs) == LISTED_SUBSTITUTES
    assert len(failing) == FAILING_LISTED_SUBSTITUTES
    assert sum(1 for original in failing if original.allergen_statements) == FAILING_WITH_DATA_ON_THE_ORIGINAL
    assert len(raised) == RAISED_ON_LISTED_SUBSTITUTES


def _declared_codes(product: Product) -> set[str]:
    return {statement.code for statement in product.allergen_statements if statement.relation in DECLARING}


def test_no_catalog_product_marks_a_member_undeclared_under_its_declared_family(products: dict[str, Product]) -> None:
    # The case of the rule "a member marked UNDECLARED does not hide its declared family": 0 of 17,546 today.
    affected = [
        product.id
        for product in products.values()
        for statement in product.allergen_statements
        if statement.relation is AllergenRelation.UNDECLARED
        and statement.code not in _declared_codes(product)
        and parent_of(statement.code) in _declared_codes(product)
    ]

    assert affected == []


def test_the_rules_run_over_every_product_without_an_error(products: dict[str, Product]) -> None:
    outcomes = {
        check_exclusions(product.allergen_statements, ["AM", "AW"], strictness).outcome
        for product in products.values()
        for strictness in AllergenStrictness
    }

    assert outcomes == set(AllergenOutcome)


ALMOND_DRINK = "465793"  # Alpro Barista Almond drink: AN FREE_FROM, its list names ALMOND (AIMO/USE-CASES.md)
SUGAR_ROSES = "461449"  # Dr. Oetker Pink Roses: AN FREE_FROM, its list says "May contain traces of ALMONDS"


def _with_and_without_the_list(product: Product, excluded: list[str], strictness: AllergenStrictness) -> tuple:
    before = check_exclusions(product.allergen_statements, excluded, strictness).outcome
    after = check_exclusions(product.allergen_statements, excluded, strictness, ingredients=product.key_ingredients)
    return before, after.outcome


@pytest.mark.parametrize("strictness", list(AllergenStrictness))
def test_the_almond_drink_goes_to_a_dietitian_when_tree_nuts_are_excluded(
    products: dict[str, Product], strictness: AllergenStrictness
) -> None:
    almond_drink = products[ALMOND_DRINK]

    before, after = _with_and_without_the_list(almond_drink, ["AN"], strictness)

    assert before is AllergenOutcome.PASS  # the declaration alone: FREE_FROM
    assert after is AllergenOutcome.TO_HUMAN


@pytest.mark.parametrize("excluded", [["AM", "AW"], ["AN"]], ids=["milk-and-gluten", "tree-nuts"])
@pytest.mark.parametrize("strictness", list(AllergenStrictness))
def test_the_ingredient_list_only_ever_sends_a_passing_product_to_a_dietitian(
    products: dict[str, Product], excluded: list[str], strictness: AllergenStrictness
) -> None:
    # Whole catalog. The counts of changed products are reported in AIMO/build/handback/FIX-12a.md; this
    # test checks the direction of every change, not how many there are.
    changes = {
        (before, after)
        for product in products.values()
        for before, after in [_with_and_without_the_list(product, excluded, strictness)]
        if before is not after
    }

    assert changes <= {(AllergenOutcome.PASS, AllergenOutcome.TO_HUMAN)}


def test_both_tree_nut_conflicts_found_by_the_use_case_check_are_sent_to_a_dietitian(
    products: dict[str, Product],
) -> None:
    changed = {
        product.id
        for product in products.values()
        if _with_and_without_the_list(product, ["AN"], AllergenStrictness.STRICT)
        == (AllergenOutcome.PASS, AllergenOutcome.TO_HUMAN)
    }

    assert {ALMOND_DRINK, SUGAR_ROSES} <= changed
