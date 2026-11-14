"""The contents of two products compared from their own ingredient lists (lane FC; the owner's correction of
14 Nov 2026: the formula is the contents, not only the figures). The examples are read from the real product
file; no list of ingredient words decides what counts."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tta.catalog import ProductCatalog
from tta.contracts.product import IngredientStatement, Product
from tta.offers.composition import ContentsCheck, compare_contents, normalise, parse_statement


def _product(*statements: tuple[str, str], key_ingredients: str | None = None) -> Product:
    return Product(
        id="1", category="10401", sales_unit="ST", base_unit="ST", allowed_lot_size=Decimal(1),
        key_ingredients=key_ingredients,
        ingredient_statements=tuple(IngredientStatement(language=language, text=text) for language, text in statements),
    )


def _compare(original: str, other: str) -> ContentsCheck:
    return compare_contents(_product(("en", original)), _product(("en", other)))


def _keys(text: str) -> list[str]:
    return [component.key for component in parse_statement(text)]


# --- reading one statement ---------------------------------------------------------------------------------


def test_a_statement_is_split_at_top_level_commas_and_the_closing_and() -> None:
    components = parse_statement("CREAM, lactase enzyme and stabilizer (carrageenan).")

    assert [each.words for each in components] == ["CREAM", "lactase enzyme", "stabilizer (carrageenan)"]
    assert [each.name for each in components] == ["CREAM", "lactase enzyme", "stabilizer"]
    assert [part.words for part in components[2].parts] == ["carrageenan"]


def test_parentheses_hold_sub_components_at_any_depth() -> None:
    (vitamins,) = parse_statement("vitamins (riboflavin (B2), B12, D2)")

    assert vitamins.key == "vitamin"
    assert [part.key for part in vitamins.parts] == ["riboflavin", "b12", "d2"]
    assert [part.key for part in vitamins.parts[0].parts] == ["b2"]


def test_a_percentage_is_kept_in_the_words_and_left_out_of_the_comparison() -> None:
    plain, in_parentheses, decimal_comma = parse_statement("OAT flour 10 %, OAT flour (10 %), rhubarb 1,5%")

    assert plain.words == "OAT flour 10 %"
    assert plain.key == in_parentheses.key == "oat flour"
    assert in_parentheses.parts == ()  # "(10 %)" is not a sub-component
    assert decimal_comma.key == "rhubarb"  # a comma between two digits does not end a component


def test_an_e_number_is_written_one_way_with_or_without_its_class_name() -> None:
    assert _keys("E 407, E-407, e407, stabiliser E407") == ["e407", "e407", "e407", "stabiliser e407"]
    (with_class,) = parse_statement("stabiliser (E407)")
    assert (with_class.key, [part.key for part in with_class.parts]) == ("stabiliser", ["e407"])
    (with_colon,) = parse_statement("thickener: pectin")
    assert (with_colon.key, [part.key for part in with_colon.parts]) == ("thickener", ["pectin"])


@pytest.mark.parametrize(
    "text",
    [
        "water, ALMOND (2.5%), salt. MAY CONTAIN REMAINS FROM NUTS (NOT PEANUTS).",
        "water, ALMOND (2.5%), salt. Contains naturally occurring sugars.",
        "water, ALMOND (2.5%), salt, may contain traces of nuts",
        "water, ALMOND (2.5%), salt. Origin of almonds: Spain.",
        "water, ALMOND (2.5%), salt. Saattaa sisältää pähkinää.",
    ],
)
def test_a_contains_trailer_and_a_note_after_the_list_are_not_components(text: str) -> None:
    assert _keys(text) == ["water", "almond", "salt"]


def test_a_later_sentence_that_is_a_list_is_read_as_more_of_the_list() -> None:
    assert _keys("Dough: WHEAT flour, water. Filling: rice, MILK, salt, BUTTER.") == [
        "dough", "water", "filling", "milk", "salt", "butter",
    ]


def test_a_line_break_inside_a_list_is_spacing_and_mono_and_diglycerides_is_one_component() -> None:
    text = "pork, salt,\\n spices,\nE471 (mono- and diglycerides of fatty acids)"

    assert _keys(text) == ["pork", "salt", "spice", "e471"]


def test_normalising_is_for_comparison_only() -> None:
    assert normalise("Gluten-free  OATS 10 %") == "gluten free oat"
    assert normalise("Pasteurized") == normalise("pasteurised")
    assert normalise("B12") == "b12"  # a closing "s" is a plural only after a letter


# --- comparing two statements ------------------------------------------------------------------------------


def test_a_component_only_one_list_has_is_a_difference_in_the_labels_own_words() -> None:
    found = _compare("CREAM and stabilizer (carrageenan).", "CREAM, lactase enzyme, stabilizer (carrageenan).")

    assert found.compared and found.differs
    assert found.language == "en"
    assert (found.only_in_original, found.only_in_other) == ((), ("lactase enzyme",))
    assert found.in_both == ("CREAM", "stabilizer (carrageenan)", "carrageenan (in stabilizer)")
    assert found.not_shown_same == ()


def test_the_order_and_the_percentage_of_a_shared_component_are_not_differences() -> None:
    found = _compare("water, OAT flour 10 %, salt", "salt, OAT flour (12 %), water")

    assert found.compared and not found.differs


@pytest.mark.parametrize(
    ("original", "other"),
    [
        ("stabiliser (carrageenan)", "stabilizer (carrageenan)"),  # two spellings
        ("stabiliser (carrageenan)", "carrageenan"),  # the class name in front of what it holds
        ("OAT base (water, OAT)", "water, OAT"),  # a compound and its parts
        ("vegetable oil (rapeseed)", "rapeseed oil"),
        ("vitamins (D, B12)", "vitamin D, vitamin B12"),
        ("modified starches", "modified starch"),  # singular and plural, also in "-es"
        ("Hulled SOYA beans (10.7%)", "Hulled SOYAbeans (10,7%)"),  # 465147 and 471762: spacing
        ("rape seed oil", "rapeseed oil"),
        ("calcium carbonate E170", "calcium carbonate"),  # the label gives the E-number beside the name
        ("calcium carbonate E170", "E 170"),
    ],
)
def test_what_is_the_same_component_written_another_way_is_no_difference(original: str, other: str) -> None:
    found = _compare(original, other)

    assert found.compared and not found.differs, (found.only_in_original, found.only_in_other)


@pytest.mark.parametrize(
    ("original", "other"),
    [
        ("stabiliser (carrageenan)", "stabiliser (gellan gum)"),
        ("stabiliser (E407)", "stabiliser (E412)"),  # the class name never stands for what it holds
        ("vegetable oil (rapeseed)", "vegetable oil (palm)"),
        ("CREAM", "CREAM, salt"),
        ("MILK, vitamin D", "MILK, MILK PRODUCT, vitamin D"),
    ],
)
def test_another_member_of_the_same_class_is_a_difference(original: str, other: str) -> None:
    assert _compare(original, other).differs


def test_wordings_that_may_be_the_same_component_are_said_as_not_shown_and_count_as_a_difference() -> None:
    found = _compare("MILK protein, salt", "MILK proteins concentrate, salt")

    assert found.differs
    assert found.not_shown_same == (("MILK protein", "MILK proteins concentrate"),)
    assert (found.only_in_original, found.only_in_other) == (("MILK protein",), ("MILK proteins concentrate",))


def test_a_component_both_name_and_only_one_opens_is_said_as_a_pair_in_the_labels_words() -> None:
    oil = _compare("water, vegetable oil (rapeseed)", "water, vegetable oil (palm)")
    alias = _compare("vitamins (riboflavin (B2))", "vitamins (riboflavin)")

    assert oil.not_shown_same == (("vegetable oil (rapeseed)", "vegetable oil (palm)"),)
    assert alias.not_shown_same == (("riboflavin (B2)", "riboflavin"),)
    assert alias.differs


def test_the_lists_are_compared_in_a_language_both_have_english_first() -> None:
    english_and_finnish = _product(("en", "CREAM"), ("fi", "KERMA"))
    finnish_only = _product(("fi", "KERMA, suola"))

    assert compare_contents(english_and_finnish, english_and_finnish).language == "en"
    found = compare_contents(english_and_finnish, finnish_only)
    assert (found.language, found.only_in_other) == ("fi", ("suola",))


def test_lists_in_two_languages_or_a_missing_list_cannot_be_compared_and_are_never_the_same() -> None:
    english, finnish, none = _product(("en", "CREAM")), _product(("fi", "KERMA")), _product()

    two_languages = compare_contents(english, finnish)
    assert (two_languages.compared, two_languages.differs) == (False, False)
    assert two_languages.why_not == "the two lists are in different languages"
    assert compare_contents(english, none).why_not == "this product has no ingredient list"
    assert compare_contents(none, english).why_not == "the product asked for has no ingredient list"
    assert compare_contents(_product(("en", "May contain nuts.")), english).why_not == (
        "the ingredient list of the product asked for names no component"
    )


def test_a_product_built_with_the_one_text_only_is_compared_as_a_list_of_unknown_language() -> None:
    found = compare_contents(_product(key_ingredients="CREAM"), _product(key_ingredients="CREAM, salt"))

    assert (found.compared, found.language, found.only_in_other) == (True, "und", ("salt",))
    assert not compare_contents(_product(key_ingredients="CREAM"), _product(("en", "CREAM"))).compared


# --- the real product file ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("original", "other", "only_in_original", "only_in_other"),
    [
        # The mentors' example: a whipping cream with lactase against two without. The figures agree.
        ("469346", "464727", ("lactase enzyme",), ()),
        ("469346", "464194", ("lactase enzyme",), ()),
        ("464727", "465193", (), ()),  # "CREAM and stabilizer (carrageenan)." / "CREAM, stabiliser (carrageenan)."
        ("469363", "462775", (), ()),  # two lactose-free milk drinks of one brand
        ("469363", "464306", ("MILK PRODUCT",), ()),  # the two options of the main demo
        ("473609", "471690", (), ()),  # "OAT flour 10 %" against "OAT flour (10 %)"
        ("464249", "469162", ("CREAM",),
         ("skim MILK", "vegetable oil (rapeseed)", "emulsifier (E472e)", "flavouring", "colour (carotenes)")),
        ("464194", "467142", ("KERMA", "stabilointiaine (karrageeni)"), None),  # compared in Finnish
    ],
)
def test_the_demo_products(
    catalog: ProductCatalog, original: str, other: str, only_in_original: tuple[str, ...],
    only_in_other: tuple[str, ...] | None,
) -> None:
    found = compare_contents(catalog.get_product(original), catalog.get_product(other))

    assert found.compared
    assert found.only_in_original == only_in_original
    assert only_in_other is None or found.only_in_other == only_in_other


def test_the_pairs_valio_lists_by_what_their_ingredient_lists_show(catalog: ProductCatalog) -> None:
    # Whole catalog, the 249 pairs Valio lists: compared and the same, compared and different, not compared
    # (43 originals and 6 substitutes with no list). Of the 140 that differ, 18 differ only in pairs "not shown
    # to be the same" (a wording that may name the same component).
    found = [
        compare_contents(product, catalog.get_product(other))
        for product in catalog.products
        for other in catalog.listed_substitutes(product.id)
    ]
    unsure_only = [
        each for each in found
        if each.differs
        and set(each.only_in_original) <= {mine for mine, _ in each.not_shown_same}
        and set(each.only_in_other) <= {yours for _, yours in each.not_shown_same}
    ]

    assert len(found) == 249
    assert sum(each.compared and not each.differs for each in found) == 60
    assert sum(each.differs for each in found) == 140
    assert sum(not each.compared for each in found) == 49
    assert len(unsure_only) == 18


def test_every_statement_of_the_catalog_can_be_read(catalog: ProductCatalog) -> None:
    # Whole catalog: no statement raises, and nearly every one names a component.
    statements = [each.text for product in catalog.products for each in product.ingredient_statements]
    empty = sum(not parse_statement(text) for text in statements)

    assert len(statements) == 38_330
    assert empty < 60
