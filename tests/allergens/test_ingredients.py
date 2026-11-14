"""`ingredient_mentions`: what a product's own ingredient list names (SPEC section 6, "The product's own
ingredient list counts as a statement"). The texts are quoted from the catalog's `keyIngredients`."""

from __future__ import annotations

import pytest

from tta.allergens import IngredientMention, ingredient_mentions

ALMOND_DRINK = (  # 465793, Alpro Barista Almond drink: AN is declared FREE_FROM
    "Water, ALMOND (2.5%), Sugar, Fructose, Acidity regulators (Potassium phosphates), Calcium (Calcium "
    "carbonate), Naturalflavourings, Stabilisers (Gellan gum, Guar gum), Sea salt. MAY CONTAIN REMAINS FROM "
    "NUTS (NOT PEANUTS). Dairy-free and gluten-free. Low sugar."
)


def codes(text: str | None) -> list[str]:
    return [mention.code for mention in ingredient_mentions(text)]


def test_the_almond_drink_names_almond_and_may_contain_nuts() -> None:
    mentions = ingredient_mentions(ALMOND_DRINK)

    assert mentions == (
        IngredientMention(code="SA", words="ALMOND", may_contain=False),
        IngredientMention(code="AN", words="MAY CONTAIN REMAINS FROM NUTS (NOT PEANUTS)", may_contain=True),
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Skimmed MILK, CREAM", ["AM"]),
        ("skimmed milk powder", ["AM"]),
        ("WHEAT flour, RYE flour, BARLEY malt", ["UW", "NR", "GB"]),
        ("OAT base (water, OATS)", ["GO", "GO"]),
        ("gluten", ["AW"]),
        ("whole EGG powder, EGGS", ["AE", "AE"]),
        ("SOYA beans, soy sauce, SOYBEAN oil", ["AY", "AY", "AY"]),
        ("FISH sauce, crustaceans, molluscs", ["AF", "AC", "UM"]),
        ("MUSTARD seeds, CELERY, SESAME seeds, LUPIN flour", ["BM", "BC", "AS", "NL"]),
        ("preservative (sulphites)", ["AU"]),
        ("HAZELNUTS, walnut, CASHEW, PISTACHIO, macadamia", ["SH", "SW", "SC", "ST", "SM"]),
        ("cashew nuts, PECAN NUTS, Brazil nut", ["SC", "SP", "SR"]),  # one nut, not a nut and then "nuts"
        ("nut paste, tree nuts", ["AN", "AN"]),
    ],
)
def test_allergens_are_found_in_capitals_and_by_their_usual_words(text: str, expected: list[str]) -> None:
    assert codes(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "coconut extract, desiccated COCONUT",  # "nut" inside another word is not a nut
        "BUCKWHEAT flour",  # buckwheat is not wheat
        "PEANUTS 46%",  # peanuts are not tree nuts, and not "nuts"
        "nutmeg, butternut squash, doughnut, nutritional yeast",
        "eggplant, shellfish-free, oatmeal-coloured",
        "",
    ],
)
def test_words_inside_other_words_are_not_matches(text: str) -> None:
    assert codes(text) == []


def test_no_text_names_nothing() -> None:
    assert ingredient_mentions(None) == ()


@pytest.mark.parametrize(
    "text",
    [
        "Dairy-free and gluten-free. Low sugar.",
        "GLUTEN FREE",
        "Free from milk and soya.",
        "DOES NOT CONTAIN MILK, GLUTEN OR WHEAT.",
        "Does no contain MILK, GLUTEN or WHEAT.",  # as written on 460509
        "Does not contain gluten.",
        "Contains no milk.",
        "Made without eggs.",
        "egg-free, nut free, milk-free",
    ],
)
def test_a_free_from_wording_in_the_list_is_not_a_mention(text: str) -> None:
    assert codes(text) == []


def test_free_applies_to_the_word_before_it_only() -> None:
    # "gluten free OAT": gluten-free oats are still oats (SPEC section 6, the oats rule).
    assert codes("Oat drink (water, gluten free OAT (Finland))") == ["GO", "GO"]
    # "lactose-free" says nothing about milk: lactose-free milk is milk.
    assert codes("lactose-free MILK") == ["AM"]
    assert codes("fat-free milk") == ["AM"]


@pytest.mark.parametrize(
    ("text", "expected_codes", "phrase"),
    [
        ("WHEAT flour (Finland), water. May contain traces of oats, rye.", ["GO", "NR"],
         "May contain traces of oats, rye"),
        ("MAY CONTAIN TRACES OF EGGS.", ["AE"], "MAY CONTAIN TRACES OF EGGS"),
        ("Can contain milk", ["AM"], "Can contain milk"),
        ("SAATTAA SISÄLTÄÄ JÄÄMIÄ PÄHKINÖISTÄ (EI MAAPÄHKINÄSTÄ).", ["AN"],
         "SAATTAA SISÄLTÄÄ JÄÄMIÄ PÄHKINÖISTÄ (EI MAAPÄHKINÄSTÄ)"),
        ("Voi sisältää seesamia.", ["AS"], "Voi sisältää seesamia"),
    ],
)
def test_a_may_contain_phrase_is_quoted_whole(text: str, expected_codes: list[str], phrase: str) -> None:
    may = [mention for mention in ingredient_mentions(text) if mention.may_contain]

    assert [mention.code for mention in may] == expected_codes
    assert {mention.words for mention in may} == {phrase}


def test_a_may_contain_phrase_ends_with_its_sentence_not_at_a_decimal_point() -> None:
    mentions = ingredient_mentions("May contain 0.5 % hazelnut. EGG yolk.")

    assert mentions == (
        IngredientMention(code="SH", words="May contain 0.5 % hazelnut", may_contain=True),
        IngredientMention(code="AE", words="EGG", may_contain=False),
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("VEHNÄjauho, RUISJAUHO, ohramallas, kaurahiutale", ["UW", "NR", "GB", "GO"]),
        ("MAITO, maitojauhe, KANANMUNA, soijalesitiini", ["AM", "AM", "AE", "AY"]),
        ("MANTELI, PÄHKINÄÄ, seesami, sinappi, selleri, gluteeni, kala", ["SA", "AN", "AS", "BM", "BC", "AW", "AF"]),
    ],
)
def test_finnish_forms_are_found_at_the_start_of_a_word(text: str, expected: list[str]) -> None:
    assert codes(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Maidoton ja gluteeniton.",  # milk-free and gluten-free
        "gluteenittomat, vehnätön, pähkinätön",
        "Ei sisällä gluteenia.",
        "Ei sisälää gluteenia.",  # as written on 462014
        "maitohappo, maitohappobakteeri",  # lactic acid and lactic acid bacteria are not milk
        "kalamata-oliivit, Kalamon olives, kalastus",  # olives and fishing are not fish
        "kookosmaito, maapähkinä, tattari",  # coconut milk, peanut and buckwheat start no allergen word
    ],
)
def test_finnish_words_that_are_not_the_allergen_are_not_mentions(text: str) -> None:
    assert codes(text) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Water, coconut milk 37%", []),
        ("rice milk powder (18%)", []),
        ("SOY MILK (water, shelled SOYA BEANS)", ["AY", "AY"]),
        ("almond milk", ["SA"]),
        ("Pickle Milk-caps, Rufous Milk-caps, white mushrooms", []),  # 460536: a mushroom, not milk
        ("pine nuts, PINE NUT", ["PN", "PN"]),  # pine nuts are their own code, outside the tree-nut family
    ],
)
def test_words_that_name_something_else_are_not_the_allergen(text: str, expected: list[str]) -> None:
    assert codes(text) == expected
