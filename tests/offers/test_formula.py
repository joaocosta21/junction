"""The formula measure (P10 F2): two products in, a `FormulaCheck` out. The examples are those of
AIMO/build/replan/P10-formula.md section 2.3, read from the real product file. The tolerances are ours."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tta.catalog import ProductCatalog
from tta.contracts.product import FormulaCheck, FormulaOutcome, Nutrition, NutritionBasis, Product
from tta.offers.formula import (
    ABSOLUTE_TOLERANCE_G,
    RELATIVE_TOLERANCE,
    SALT_TOLERANCE_G,
    compare_formula,
    names_vegetable_fat,
)

SAME, BRAND, OTHER = (
    FormulaOutcome.SAME_PRODUCT_OTHER_PACK, FormulaOutcome.SAME_BRAND, FormulaOutcome.OTHER_BRAND
)
DIFFERENT, NOT_KNOWN = FormulaOutcome.DIFFERENT, FormulaOutcome.NOT_KNOWN


@pytest.fixture(scope="module")
def check(catalog: ProductCatalog):  # noqa: ANN201
    def run(original_id: str, other_id: str) -> FormulaCheck:
        return compare_formula(catalog.get_product(original_id), catalog.get_product(other_id))

    return run


def _product(product_id: str = "1", brand: str | None = "Valio", ingredients: str | None = "CREAM", **figures: str
             ) -> Product:
    six = {"fat": "36", "saturated_fat": "23", "protein": "2.2", "carbohydrate": "2.9", "sugars": "2.9", "salt": "0.06"}
    basis = figures.pop("basis", "G")
    values = {name: Decimal(value) for name, value in {**six, **figures}.items() if value is not None}
    return Product(
        id=product_id, category="10401", sales_unit="ST", base_unit="ST", allowed_lot_size=Decimal(1), brand=brand,
        key_ingredients=ingredients, nutrition=Nutrition(basis=NutritionBasis(basis), **values),
    )


def test_the_tolerances_are_named_values() -> None:
    assert Decimal("0.15") == RELATIVE_TOLERANCE
    assert Decimal("1.0") == ABSOLUTE_TOLERANCE_G
    assert Decimal("0.25") == SALT_TOLERANCE_G


@pytest.mark.parametrize(
    ("original", "other", "outcome"),
    [
        ("464194", "463837", SAME),  # Valio whipping cream 1 l and 2 dl: the six values are equal
        ("464194", "463366", SAME),  # and 10 l
        ("464249", "463828", SAME),  # Valio cooking cream 15% 1 l and 2 dl
        ("464194", "469346", OTHER),  # Valio 38 against Arla Pro 36: 2 g of 38 is 5%
        ("469549", "476927", OTHER),  # Valio semi skimmed against Arla semi skimmed
        ("469363", "464306", OTHER),  # the two options of the main demo
        ("464727", "465193", OTHER),  # Arla whipping cream against Valio food service whipping cream: cheaper
        ("464194", "464249", DIFFERENT),  # whipping 38 against cooking 15, same brand
        ("469549", "469556", DIFFERENT),  # semi skimmed 1.5 against whole 3.5: the floor stays under 1.5 g
        ("464194", "467142", NOT_KNOWN),  # Rama Professional Whipping 30%: per 100 ml against per 100 g
        ("464249", "469162", DIFFERENT),  # cooking cream 15% against the vegetable-oil alternative 15%
        ("464411", "476849", DIFFERENT),  # butter against a butter and rapeseed-oil blend
        ("464411", "475797", DIFFERENT),  # unsalted butter 0.02 against salted 1.4
        ("473609", "468465", DIFFERENT),  # barista oat drink 3.0 against the plain one 1.0
        ("473609", "471690", NOT_KNOWN),  # listed by Valio, fat 1.5 against 3.0: per 100 g against per 100 ml
        ("464249", "463797", DIFFERENT),  # listed by Valio: fat 10, not 15
        ("469346", "463975", DIFFERENT),  # Arla Pro whipping cream 36 against the 15% vegetable mix
    ],
)
def test_the_examples_of_the_proposal(check, original: str, other: str, outcome: FormulaOutcome) -> None:  # noqa: ANN001
    found = check(original, other)

    assert found.outcome is outcome, found.sentence


def test_figures_per_100_g_are_never_compared_with_figures_per_100_ml(check) -> None:  # noqa: ANN001
    found = check("473609", "471690")  # scenario 3: Barista oat drink and its listed substitute

    assert found.outcome is NOT_KNOWN
    assert found.sentence == (
        "The formula cannot be compared: the figures of the product asked for are per 100 ml and this product's "
        "are per 100 g. As stated: fat 1.5 g per 100 g, not 3 g per 100 ml."
    )
    assert found.differences == ()  # no difference is claimed across two bases


def test_a_different_formula_is_said_in_numbers(check) -> None:  # noqa: ANN001
    found = check("469346", "463975")

    assert found.sentence == (
        "Different formula: fat 15 g, not 36 g; saturated fat 1.3 g, not 23 g; carbohydrate 4.9 g, not 2.9 g "
        "per 100 g. Its ingredient list names a vegetable oil or fat; the original's does not."
    )
    assert found.fat_source_differs is True
    assert [(each.nutrient, each.within_tolerance) for each in found.differences] == [
        ("fat", False), ("saturated_fat", False), ("protein", True), ("carbohydrate", False), ("sugars", True),
    ]
    assert not found.keeps_formula


def test_the_same_fat_figure_from_another_fat_source_is_a_different_formula(check) -> None:  # noqa: ANN001
    found = check("464249", "469162")  # both 15% fat, same brand, same category

    assert found.outcome is DIFFERENT
    assert "saturated fat 1.4 g, not 8.8 g" in found.sentence
    assert "names a vegetable oil or fat" in found.sentence


def test_a_formula_within_tolerance_names_the_figures_and_says_the_tolerance_is_ours(check) -> None:  # noqa: ANN001
    found = check("469346", "464194")  # Arla Pro 36 asked for, Valio 38 offered

    assert found.outcome is OTHER
    assert found.keeps_formula
    assert found.sentence == (
        "Same formula within our tolerance of 15% or 1 g per nutrient (salt 0.25 g): fat 38 g against 36 g; "
        "saturated fat 22 g against 23 g; protein 2 g against 2.2 g; carbohydrate 2.8 g against 2.9 g; "
        "sugars 2.8 g against 2.9 g; salt 0.07 g against 0.06 g per 100 g."
    )


def test_equal_figures_and_the_same_brand_read_as_the_same_product(check) -> None:  # noqa: ANN001
    found = check("464194", "463837")

    assert found.differences == ()
    assert found.sentence == (
        "The data shows no difference in formula: same brand, and the six nutrition figures per 100 g are equal."
    )


def test_the_formula_never_sees_a_lost_dietary_claim(check) -> None:  # noqa: ANN001
    # 469126 Valio whipping cream lactose free -> 469050 Valio Keittiön whipping cream: six equal values, same
    # brand, and FREE_FROM_LACTOSE is gone. The dietary gate, not this measure, must catch it.
    assert check("469126", "469050").keeps_formula


def test_each_figure_may_differ_by_15_percent_or_1_gram_whichever_is_larger() -> None:
    original = _product()

    assert compare_formula(original, _product("2", fat="41.4")).outcome is BRAND  # 15% of 36 is 5.4
    assert compare_formula(original, _product("2", fat="41.5")).outcome is DIFFERENT
    assert compare_formula(original, _product("2", protein="3.2")).outcome is BRAND  # 1.0 g floor
    assert compare_formula(original, _product("2", protein="3.3")).outcome is DIFFERENT
    assert compare_formula(original, _product("2", salt="0.31")).outcome is BRAND  # salt: 0.25 g
    assert compare_formula(original, _product("2", salt="0.32")).outcome is DIFFERENT


def test_another_brand_or_a_brand_that_is_not_stated_is_never_the_same_brand() -> None:
    original = _product()

    assert compare_formula(original, _product("2")).outcome is SAME
    assert compare_formula(original, _product("2", fat="37")).outcome is BRAND
    assert compare_formula(original, _product("2", brand="Arla")).outcome is OTHER
    assert compare_formula(original, _product("2", brand=None)).outcome is OTHER
    assert compare_formula(_product(brand=None), _product("2", brand=None)).outcome is OTHER


def test_missing_data_is_not_known_and_never_the_same(catalog: ProductCatalog) -> None:
    original = _product()
    no_figures = original.model_copy(update={"id": "2", "nutrition": None})

    missing = compare_formula(original, no_figures)
    partial = compare_formula(original, _product("2", salt=None))
    per_ml = compare_formula(original, _product("2", basis="ML"))
    no_list = compare_formula(original, _product("2", ingredients=None))
    far_and_no_list = compare_formula(original, _product("2", fat="15", ingredients=None))

    assert [each.outcome for each in (missing, partial, per_ml, no_list)] == [NOT_KNOWN] * 4
    assert not any(each.keeps_formula for each in (missing, partial, per_ml, no_list))
    assert missing.sentence == "The formula cannot be compared: this product has no nutrition figures per 100 g or ml."
    assert "salt" in partial.sentence
    assert no_list.sentence == (
        "The formula cannot be compared: the nutrition figures agree, but this product's ingredient list is missing."
    )
    assert far_and_no_list.outcome is DIFFERENT  # the figures alone already tell
    assert compare_formula(no_figures, original).sentence == (
        "The formula cannot be compared: the product asked for has no nutrition figures per 100 g or ml."
    )


@pytest.mark.parametrize(
    ("text", "names"),
    [
        ("CREAM, stabiliser (carrageenan)", False),
        ("skim MILK, water, vegetable oil (rapeseed), modified starches", True),
        ("KIRNUMAITO, vesi, kokonaan kovetettu palmuöljy#, kookosöljy", True),
        ("rasvaton MAITO, vesi, kasviöljyt (rapsi, rypsi)", True),
        ("BUTTER, rapeseed oil, water, salt and vitamin D.", True),
        ("Vegetable oils and fats (coconut, rapeseed, shea)", True),
        ("MILK, vitamin A (retinyl palmitate), vitamin D", False),  # "palm" inside another word
        ("water, OAT, sunflower oil", True),
        ("Water, OATS 10%, rape seed oil, acidity regulator", True),  # 464320 Oatly iKaffe spells it in two words
        ("KERMA, stabilointiaine (karrageeni)", False),
    ],
)
def test_the_fat_source_words_in_english_and_finnish(text: str, names: bool) -> None:
    assert names_vegetable_fat(text) is names


def test_listed_by_valio_does_not_mean_the_same_formula(catalog: ProductCatalog) -> None:
    # Whole catalog: the pairs Valio lists (a product that lists itself left out), by outcome. Our measure.
    # The proposal's draft counted 34 / 71 / 77 for the last three: it compared per 100 g with per 100 ml.
    outcomes = [
        compare_formula(product, catalog.get_product(other)).outcome
        for product in catalog.products
        for other in catalog.listed_substitutes(product.id)
    ]

    assert len(outcomes) == 249
    assert {outcome: outcomes.count(outcome) for outcome in FormulaOutcome} == {
        SAME: 41, BRAND: 26, OTHER: 33, DIFFERENT: 67, NOT_KNOWN: 82,
    }
