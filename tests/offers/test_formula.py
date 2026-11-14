"""The formula measure (P10 F2): two products in, a `FormulaCheck` out. The examples are those of
AIMO/build/replan/P10-formula.md section 2.3, read from the real product file. The tolerances are ours.

Lane FC (the owner's correction of 14 Nov 2026): the contents decide first, the figures second. A component only
one ingredient list has is a different formula even when the six figures agree (`tta.offers.composition`)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tta.catalog import ProductCatalog
from tta.catalog.kinds import drink_evidence
from tta.catalog.qualifiers import NO_QUALIFIERS
from tta.contracts.product import (
    FormulaCheck,
    FormulaOutcome,
    IngredientStatement,
    Nutrition,
    NutritionBasis,
    Product,
    UnitConversion,
)
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


def _product(product_id: str = "1", brand: str | None = "Valio", ingredients: str | None = "CREAM",
             category: str = "10401", **figures: str) -> Product:
    six = {"fat": "36", "saturated_fat": "23", "protein": "2.2", "carbohydrate": "2.9", "sugars": "2.9", "salt": "0.06"}
    basis = figures.pop("basis", "G")
    values = {name: Decimal(value) for name, value in {**six, **figures}.items() if value is not None}
    return Product(
        id=product_id, category=category, sales_unit="ST", base_unit="ST", allowed_lot_size=Decimal(1), brand=brand,
        key_ingredients=ingredients, nutrition=Nutrition(basis=NutritionBasis(basis), **values),
    )


def _in(language: str, text: str, product_id: str = "1") -> Product:
    """A cream whose one ingredient statement is in the given language, as the loader would build it."""
    statement = IngredientStatement(language=language, text=text)
    return _product(product_id, ingredients=text, category="10500").model_copy(
        update={"ingredient_statements": (statement,)}
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
        # Valio 38 against Arla Pro 36: 2 g of 38 is 5%, and only Arla Pro's list names lactase enzyme.
        # Before lane FC: OTHER, on the figures alone.
        ("464194", "469346", DIFFERENT),
        ("469549", "476927", OTHER),  # Valio semi skimmed against Arla semi skimmed
        # The two options of the main demo: the figures agree, and only 469363 names "MILK PRODUCT". Before: OTHER.
        ("469363", "464306", DIFFERENT),
        ("469363", "462775", DIFFERENT),  # the same list, fat 0 g against 1.5 g
        ("464727", "465193", OTHER),  # Arla whipping cream against Valio food service whipping cream: cheaper
        ("464194", "464249", DIFFERENT),  # whipping 38 against cooking 15, same brand
        ("469549", "469556", DIFFERENT),  # semi skimmed 1.5 against whole 3.5: the floor stays under 1.5 g
        ("464194", "467142", DIFFERENT),  # Rama Professional Whipping 30%, per 100 ml: two creams, so compared
        ("464249", "469162", DIFFERENT),  # cooking cream 15% against the vegetable-oil alternative 15%
        ("464411", "476849", DIFFERENT),  # butter against a butter and rapeseed-oil blend
        ("464411", "475797", DIFFERENT),  # unsalted butter 0.02 against salted 1.4
        ("473609", "468465", DIFFERENT),  # barista oat drink 3.0 against the plain one 1.0
        ("473609", "471690", DIFFERENT),  # listed by Valio, fat 1.5 against 3.0: two drinks, so compared
        # Listed by Valio, per 100 ml against per 100 g and not read as drinks: the figures cannot be compared,
        # and the two Finnish lists differ (hardened vegetable oils against an oat base). Before: NOT_KNOWN.
        ("469288", "470341", DIFFERENT),
        ("464249", "463797", DIFFERENT),  # listed by Valio: fat 10, not 15
        ("469346", "463975", DIFFERENT),  # Arla Pro whipping cream 36 against the 15% vegetable mix
    ],
)
def test_the_examples_of_the_proposal(check, original: str, other: str, outcome: FormulaOutcome) -> None:  # noqa: ANN001
    found = check(original, other)

    assert found.outcome is outcome, found.sentence


def test_for_two_drinks_figures_per_100_g_are_compared_with_figures_per_100_ml_and_the_sentence_says_so(
    check,  # noqa: ANN001
) -> None:
    # Before: NOT_KNOWN, "The formula cannot be compared: ... As stated: fat 1.5 g per 100 g, not 3 g per 100 ml."
    found = check("473609", "471690")  # scenario 3: Barista oat drink and its listed substitute, both plant drinks

    assert found.outcome is DIFFERENT
    assert found.mixed_basis is True
    assert found.basis is None  # there is no one basis to name
    assert found.sentence == (
        "Different formula: fat 1.5 g, not 3 g, per 100 g against per 100 ml. The two ingredient lists name the "
        "same components. Figures per 100 g compared with per 100 ml as they stand: for a drink the two are "
        "about 3% apart (our rule)."
    )
    assert found.contents_compared and (found.only_in_original, found.only_in_other) == ((), ())
    assert [each.nutrient for each in found.differences if not each.within_tolerance] == ["fat"]


def test_for_anything_that_is_not_a_drink_grams_are_never_read_as_millilitres(check) -> None:  # noqa: ANN001
    # 465655 is a juice concentrate (1+7): no product type of ours, and its file states no weight for a volume.
    # Before lane FC: NOT_KNOWN. The figures still cannot be compared; the two ingredient lists differ.
    found = check("465655", "465623")

    assert found.outcome is DIFFERENT
    assert found.mixed_basis is False
    assert found.sentence.startswith(
        "Different contents: this product's ingredient list names Cranberry juice concentrate (icke EU) and "
        "lingonberry juice concentrate (non EU,EU), which the list of the product asked for does not; the "
        "ingredient list of the product asked for names Sugar, water, apple and 5 more, which this "
        "product's does not. The nutrition figures cannot be compared: the figures of the product asked for are "
        "per 100 ml and this product's are per 100 g. As stated: fat 0.1 g per 100 g, not 4 g per 100 ml;"
    )
    assert found.differences == ()  # no difference is claimed across two bases


def test_grams_against_millilitres_with_the_same_contents_stays_not_known() -> None:
    butter = _product(category="10500")  # not a drink

    found = compare_formula(butter, _product("2", basis="ML", category="10500"))

    assert found.outcome is NOT_KNOWN
    assert found.contents_compared
    assert found.sentence == (
        "The formula cannot be compared: the figures of the product asked for are per 100 g and this product's "
        "are per 100 ml."
    )


def test_two_drinks_on_two_bases_within_tolerance_keep_the_formula_and_are_never_the_same_product() -> None:
    per_g = _product()  # category 10401 with no name: product type cream, read as a drink
    equal = compare_formula(per_g, _product("2", basis="ML"))
    close = compare_formula(per_g, _product("2", basis="ML", fat="35"))
    other_brand = compare_formula(per_g, _product("2", basis="ML", brand="Arla"))

    assert [each.outcome for each in (equal, close, other_brand)] == [BRAND, BRAND, OTHER]
    assert all(each.mixed_basis and each.keeps_formula for each in (equal, close, other_brand))
    assert equal.sentence == (
        "Same formula within our tolerance of 15% or 1 g per nutrient (salt 0.25 g): the six nutrition figures "
        "are equal as stated, per 100 ml against per 100 g. The two ingredient lists name the same components. "
        "Figures per 100 g compared with per 100 ml as they stand: for a drink the two are about 3% apart (our rule)."
    )
    assert "fat 35 g against 36 g, per 100 ml against per 100 g." in close.sentence


def test_a_drink_is_read_from_the_weight_of_a_litre_and_else_from_the_product_type(catalog: ProductCatalog) -> None:
    oil = _product(category="10531").model_copy(  # an olive oil: 0.92 kg per litre in its file
        update={"unit_conversions": (UnitConversion(
            packaging_type="BASE_UNIT_OR_EACH", volume_l=Decimal(1), net_weight_kg=Decimal("0.92")),)}
    )

    assert drink_evidence(catalog.get_product("473609")) == "one litre weighs about a kilogram in the product data"
    assert drink_evidence(catalog.get_product("471690")) == "product type plant drink"  # no weight for a volume
    assert drink_evidence(catalog.get_product("469148")) is None  # milk powder
    assert drink_evidence(oil) is None
    assert compare_formula(oil, _product("2", basis="ML", category="10531")).outcome is NOT_KNOWN


def test_a_different_formula_names_the_components_first_and_the_figures_after(check) -> None:  # noqa: ANN001
    found = check("469346", "463975")

    assert found.sentence == (
        "Different contents: this product's ingredient list names Skimmed MILK (Finland), water, "
        "rapeseed oil and 5 more, which the list of the product asked for does not; the ingredient list of the "
        "product asked for names CREAM, lactase enzyme and stabilizer (carrageenan), which this product's "
        "does not. Figures outside our tolerance: fat 15 g, not 36 g; saturated fat 1.3 g, not 23 g; "
        "carbohydrate 4.9 g, not 2.9 g per 100 g."
    )
    assert found.only_in_original == ("CREAM", "lactase enzyme", "stabilizer (carrageenan)")
    assert found.only_in_other == (
        "Skimmed MILK (Finland)", "water", "rapeseed oil", "modified maize", "tapioca starch", "emulsifier (E472e)",
        "flavouring", "colour (beta-carotene)",
    )
    assert found.fat_source_differs is True  # still filled for the policy facts and the mixed-order sentence
    assert [(each.nutrient, each.within_tolerance) for each in found.differences] == [
        ("fat", False), ("saturated_fat", False), ("protein", True), ("carbohydrate", False), ("sugars", True),
    ]
    assert not found.keeps_formula


def test_the_same_fat_figure_from_another_fat_source_is_a_different_formula(check) -> None:  # noqa: ANN001
    found = check("464249", "469162")  # both 15% fat, same brand, same category

    assert found.outcome is DIFFERENT
    assert "saturated fat 1.4 g, not 8.8 g" in found.sentence
    assert "vegetable oil (rapeseed)" in found.sentence
    assert found.only_in_original == ("CREAM",)


def test_the_figures_agree_and_one_list_names_an_enzyme_the_other_lacks(check) -> None:  # noqa: ANN001
    # The mentors' example (14 Nov 2026). 469346: "CREAM, lactase enzyme, stabilizer (carrageenan)."; 464727:
    # "CREAM and stabilizer (carrageenan)."; 464194: "CREAM, stabiliser (carrageenan)". Before lane FC all three
    # kept the formula on the figures alone.
    arla, valio, reverse = check("469346", "464727"), check("469346", "464194"), check("464194", "469346")

    assert [each.outcome for each in (arla, valio, reverse)] == [DIFFERENT] * 3
    assert not any(each.keeps_formula for each in (arla, valio, reverse))
    assert all(each.contents_compared for each in (arla, valio, reverse))
    assert all(each.within_tolerance for each in arla.differences)
    assert (arla.only_in_original, arla.only_in_other) == (("lactase enzyme",), ())
    assert (reverse.only_in_original, reverse.only_in_other) == ((), ("lactase enzyme",))
    assert valio.sentence == (
        "Different contents: the ingredient list of the product asked for names lactase enzyme, which this "
        "product's does not. The six nutrition figures are within our tolerance of 15% or 1 g per nutrient "
        "(salt 0.25 g)."
    )
    assert reverse.sentence.startswith(
        "Different contents: this product's ingredient list names lactase enzyme, which the list of the "
        "product asked for does not."
    )


def test_a_wording_that_may_be_the_same_component_is_said_as_not_shown_and_does_not_keep_the_formula(
    check,  # noqa: ANN001
) -> None:
    found = check("469556", "469401")  # Valio whole milk "MILK" against Arla whole milk "Pasteurized MILK"

    assert found.outcome is DIFFERENT
    assert found.sentence == (
        "Different contents: Pasteurized MILK against MILK: not shown to be the same. The six nutrition "
        "figures are within our tolerance of 15% or 1 g per nutrient (salt 0.25 g)."
    )
    assert (found.only_in_original, found.only_in_other) == (("MILK",), ("Pasteurized MILK",))


def test_a_formula_within_tolerance_names_the_figures_and_says_the_tolerance_is_ours(check) -> None:  # noqa: ANN001
    found = check("464727", "465193")  # Arla whipping cream asked for, Valio food service whipping cream offered

    assert found.outcome is OTHER
    assert found.keeps_formula
    assert found.sentence == (
        "Same formula within our tolerance of 15% or 1 g per nutrient (salt 0.25 g): saturated fat 21 g against "
        "23 g; protein 2.2 g against 2 g; salt 0.07 g against 0.1 g per 100 g. The two ingredient lists name the "
        "same components."
    )
    assert found.contents_compared and (found.only_in_original, found.only_in_other) == ((), ())


def test_equal_figures_and_the_same_brand_read_as_the_same_product(check) -> None:  # noqa: ANN001
    found = check("464194", "463837")

    assert found.differences == ()
    assert found.sentence == (
        "The data shows no difference in formula: same brand, and the six nutrition figures per 100 g are equal. "
        "The two ingredient lists name the same components."
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
    original = _product(category="10500")  # butter: not a drink
    no_figures = original.model_copy(update={"id": "2", "nutrition": None})

    missing = compare_formula(original, no_figures)
    partial = compare_formula(original, _product("2", salt=None, category="10500"))
    per_ml = compare_formula(original, _product("2", basis="ML", category="10500"))
    no_list = compare_formula(original, _product("2", ingredients=None, category="10500"))
    far_and_no_list = compare_formula(original, _product("2", fat="15", ingredients=None, category="10500"))

    assert [each.outcome for each in (missing, partial, per_ml, no_list)] == [NOT_KNOWN] * 4
    assert not any(each.keeps_formula for each in (missing, partial, per_ml, no_list))
    assert missing.sentence == "The formula cannot be compared: this product has no nutrition figures per 100 g or ml."
    assert "salt" in partial.sentence
    assert no_list.sentence == (
        "The formula cannot be compared: the figures agree within our tolerance of 15% or 1 g per nutrient (salt "
        "0.25 g), but the ingredient lists cannot be compared (this product has no ingredient list), so the "
        "formula is not shown to be the same."
    )
    assert no_list.contents_compared is False
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
        # A lecithin is an emulsifier, not a fat source. Before: 465028, a skimmed milk powder, read as
        # "another fat source" against the same powder in a 20 kg bag.
        ("skimmed MILK, emulsifier (rapeseed lecitin), vitamin D.", False),
        ("sugar, cocoa butter, whole MILK powder, emulsifier (sunflower lecithin)", False),
        ("rasvaton MAITO, emulgointiaine (auringonkukkalesitiini)", False),
        ("MILK, rapeseed oil, emulsifier (sunflower lecithin)", True),  # the oil still counts
    ],
)
def test_the_fat_source_words_in_english_and_finnish(text: str, names: bool) -> None:
    # The one word list left: it decides only between two lists with no language in common, and fills
    # `fat_source_differs` for the policy facts and the mixed-order sentence.
    assert names_vegetable_fat(text) is names


def test_two_lists_with_no_language_in_common_are_not_known_unless_the_words_show_another_fat_source() -> None:
    english = _in("en", "CREAM, salt")
    finnish = _in("fi", "KERMA, suola", "2")
    finnish_blend = _in("fi", "rasvaton MAITO, vesi, kasviöljyt (rapsi, rypsi)", "2")

    unknown, by_words = compare_formula(english, finnish), compare_formula(english, finnish_blend)

    assert (unknown.outcome, unknown.contents_compared) == (NOT_KNOWN, False)
    assert unknown.sentence == (
        "The formula cannot be compared: the figures agree within our tolerance of 15% or 1 g per nutrient (salt "
        "0.25 g), but the ingredient lists cannot be compared (the two lists are in different languages), so the "
        "formula is not shown to be the same."
    )
    assert (by_words.outcome, by_words.contents_compared, by_words.fat_source_differs) == (DIFFERENT, False, True)
    assert by_words.sentence == (
        "Different formula: the six nutrition figures are within our tolerance of 15% or 1 g per nutrient (salt "
        "0.25 g). Its ingredient list names a vegetable oil or fat; the original's does not."
    )


def test_listed_by_valio_does_not_mean_the_same_formula(catalog: ProductCatalog) -> None:
    # Whole catalog: the pairs Valio lists (a product that lists itself left out), by outcome. Our measure.
    # Before lane FC, on the figures and the fat-source words: 41 / 26 / 33 kept (100), 68 differed, 81 not known.
    # Of those 100, 50 have a component only one ingredient list names (8 of them only as a wording "not shown
    # to be the same"); 28 pairs with no comparable figures now differ by their lists.
    # Lane FC2 (words of origin and farming read from the catalog): 146 different became 145 and 10 of another
    # brand 11, by 468876 with 462281 ("Finnish chicken fillet" against "chicken fillet").
    outcomes = [
        compare_formula(product, catalog.get_product(other)).outcome
        for product in catalog.products
        for other in catalog.listed_substitutes(product.id)
    ]

    assert len(outcomes) == 249
    assert {outcome: outcomes.count(outcome) for outcome in FormulaOutcome} == {
        SAME: 38, BRAND: 2, OTHER: 11, DIFFERENT: 145, NOT_KNOWN: 53,
    }


def test_a_word_of_origin_keeps_the_formula_and_the_sentence_says_which_ingredient(catalog: ProductCatalog) -> None:
    # Lane FC2, decision B49. Valio lists 462281 for 468876; the lists differ by the word "Finnish" alone.
    found = compare_formula(catalog.get_product("468876"), catalog.get_product("462281"))

    assert found.outcome is OTHER
    assert found.keeps_formula
    assert found.sentence.endswith(
        "The two ingredient lists name the same components. Read as the same ingredient, a word of origin or "
        "farming apart: Finnish chicken fillet against chicken fillet."
    )


def test_an_explicit_table_overrides_the_catalogs(catalog: ProductCatalog) -> None:
    found = compare_formula(catalog.get_product("468876"), catalog.get_product("462281"), NO_QUALIFIERS)

    assert found.outcome is DIFFERENT
    assert "not shown to be the same" in found.sentence
