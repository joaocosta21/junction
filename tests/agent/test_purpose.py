"""The buyer's words say when the formula matters: "for baking", "for cakes", "for whipping" (replan P10).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for". Valio Aimo, 14 Nov 2026:
for baking and cakes the contents of the product can make a difference.
"""

from __future__ import annotations

import pytest

from tta.agent.purpose import FormulaUse, formula_matters, formula_use


@pytest.mark.parametrize(
    ("text", "use", "said"),
    [
        ("20 litres of cream for baking by Monday", "baking", "for baking"),
        ("10 kg of butter for cakes", "cakes", "for cakes"),
        ("10 kg of butter for the cakes", "cakes", "for the cakes"),
        ("24 litres of cream for whipping", "whipping", "for whipping"),
        ("24 litres of cream to whip", "whipping", "to whip"),
        ("100 litres of milk FOR BAKING", "baking", "for baking"),
        ("10 litres of cream for a sauce", "sauce", "for a sauce"),
        ("10 litres of cream for making cheesecake", "cakes", "for making cheesecake"),
        ("10 litres of milk for  foaming", "whipping", "for foaming"),
        ("3 kg of quark for the dessert recipe", "cakes", "for the dessert"),
        ("10 litres of cream for desserts", "cakes", "for desserts"),
        ("10 litres of cream for a dessert", "cakes", "for a dessert"),
        ("10 litres of cream in our desserts", "cakes", "in our desserts"),
        ("10 litres of cream to make desserts", "cakes", "to make desserts"),
        ("10 litres of cream to make a sauce", "sauce", "to make a sauce"),
        ("5 kg of butter to bake with", "baking", "to bake"),
        ("5 kg of butter for the pastry, to the kitchen door", "baking", "for the pastry"),
    ],
)
def test_a_use_said_as_a_purpose_means_the_formula_matters(text: str, use: str, said: str) -> None:
    assert formula_use(text) == FormulaUse(use=use, said=said) and formula_matters(text)


@pytest.mark.parametrize(
    "text",
    [
        "1,000 litres of lactose-free milk by Monday",
        "200 litres of milk for the breakfast buffet",
        "24 litres of whipping cream",  # the product's own name, not what the buyer does with it
        "10 kg of baking chocolate",
        "100 litres of milk, not for baking",
        "100 litres of milk, this isn't for baking",
        "50 kg of pancakes",
        "20 litres of milk for Baker Street",
        # A place or a recipient is not a use (the trap L1-2 found): where the goods go, not what is done with them.
        "10 litres of cream to the dessert kitchen",
        "10 litres of cream, deliver to the dessert kitchen",
        "10 litres of cream for the dessert kitchen",
        "10 litres of cream to the dessert",
        "10 litres of cream to the pastry section",
        "5 kg of butter for our pastry kitchen",
        "5 kg of butter for the pastry chef",
        "5 kg of butter for the baking team",
        "10 litres of cream in the dessert fridge",
        "10 litres of cream to the sauce station",
        "",
    ],
)
def test_everyday_words_a_product_name_and_a_negated_purpose_say_nothing(text: str) -> None:
    assert formula_use(text) is None and not formula_matters(text)


def test_the_first_purpose_said_is_the_one_named_and_its_sentence_quotes_the_buyer() -> None:
    use = formula_use("10 l of cream for whipping and 5 kg of butter for baking")

    assert use is not None and use.use == "whipping"
    assert use.sentence == 'Formula matters: the request says "for whipping".'
