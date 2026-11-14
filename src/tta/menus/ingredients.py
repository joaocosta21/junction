"""A sentence that names an ingredient where a dish was expected (lane FIX-M).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for". The brief's first scenario is
a chef who plans a menu around an ingredient. We have ten illustrative recipes and no notion of season, and none is
invented here. Such a sentence is still refused with the question to answer, because the person names the dish and
its servings; the refusal now helps:
- it names an ingredient of the recipe table ("around cream", "eggs for 40"): the dishes of ours that use it;
- it is built "around" something no recipe of ours uses: said plainly, in the person's own words, with every dish;
- neither: the question as before.
An ingredient is a product type the recipes themselves ask for, read as whole words; a plural "s" is allowed. Nothing
is planned, and nothing is matched to a near word.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from tta.contracts.errors import InvalidRequest
from tta.contracts.menu import MAX_SERVINGS, Recipe
from tta.menus.plan import ILLUSTRATIVE
from tta.menus.recipes import dish_names
from tta.menus.wording import THE_DISHES, joined, type_words

NO_DISH_NAMED = "The sentence names no dish of the recipe table. " + THE_DISHES
WITH = "With {ingredient} we have: {dishes}."
NAME_ONE = 'Name one with its servings, for example "{dish} for {servings}".'
NO_RECIPE_USES = 'No recipe of ours uses "{what}". ' + THE_DISHES
EXAMPLE_SERVINGS = 20
MAX_WORDS, MAX_LENGTH = 4, 40  # of what a sentence is built around, when it is quoted back
_WORD = re.compile(r"[^\W\d_]+")
_NUMBER = re.compile(r"(?<![\d.,])\d+(?![\d.,])")
_AROUND = re.compile(r"\b(?:around|using|featuring|based on)\s+(?P<what>[^\d,.;:!?()\"]+)", re.IGNORECASE)
_LEAD_IN = re.compile(r"^(?:(?:a|an|the|some|our|fresh|seasonal|local)\s+)+", re.IGNORECASE)
_AFTER = re.compile(r"\s+(?:for|by|on|and|with|next|this)\b.*$", re.IGNORECASE)
_PLAIN = re.compile(r"[^\W\d_]+(?:[ '-][^\W\d_]+)*")


def _stem(word: str) -> str:
    """`eggs` and `egg` read alike: a plural "s" is dropped from a word of more than three letters."""
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(_stem(word) for word in _WORD.findall(text.casefold()))


def dishes_by_ingredient(recipes: Mapping[str, Recipe]) -> dict[str, tuple[str, ...]]:
    """`cream` to the dishes whose recipe asks for it, each by its first name, in the table's order. Only what a
    recipe itself asks for: a product type that is an alternative alone is not an ingredient of the dish."""
    names = dish_names(recipes)
    found: dict[str, list[str]] = {}
    for dish_id, recipe in recipes.items():
        for ingredient in recipe.ingredients:
            dishes = found.setdefault(type_words(ingredient.product_type), [])
            if names[dish_id][0] not in dishes:
                dishes.append(names[dish_id][0])
    return {ingredient: tuple(dishes) for ingredient, dishes in found.items()}


def _holds(tokens: Sequence[str], words: Sequence[str]) -> bool:
    return any(tuple(tokens[start:start + len(words)]) == tuple(words) for start in range(len(tokens)))


def ingredients_in(text: str, recipes: Mapping[str, Recipe]) -> dict[str, tuple[str, ...]]:
    """The ingredients of the recipe table the text names, with their dishes, in the table's order."""
    tokens = _tokens(text)
    return {
        ingredient: dishes for ingredient, dishes in dishes_by_ingredient(recipes).items()
        if _holds(tokens, _tokens(ingredient))
    }


def _example_servings(text: str) -> int:
    """The one whole number of the sentence, when it could be a number of servings; else 20."""
    numbers = [int(number) for number in _NUMBER.findall(text)]
    return numbers[0] if len(numbers) == 1 and 1 <= numbers[0] <= MAX_SERVINGS else EXAMPLE_SERVINGS


def _with(text: str, found: Mapping[str, tuple[str, ...]]) -> InvalidRequest:
    said = [WITH.format(ingredient=ingredient, dishes=joined(dishes)) for ingredient, dishes in found.items()]
    first = next(iter(found.values()))[0]
    said.append(NAME_ONE.format(dish=first, servings=_example_servings(text)))
    dishes = list(dict.fromkeys(dish for each in found.values() for dish in each))
    return InvalidRequest(
        " ".join((*said, ILLUSTRATIVE)), ingredients_named=list(found), dishes_that_use_them=dishes,
    )


def _built_around(text: str) -> str | None:
    """What the sentence is built around ("around chanterelles"), as written: at most four plain words."""
    found = _AROUND.search(text)
    if found is None:
        return None
    what = _AFTER.sub("", _LEAD_IN.sub("", found["what"].strip())).strip()
    plain = _PLAIN.fullmatch(what) is not None and len(what) <= MAX_LENGTH and len(what.split()) <= MAX_WORDS
    return what if plain else None


def no_dish_named(text: str, recipes: Mapping[str, Recipe], dishes: str) -> InvalidRequest:
    """The refusal of a sentence that names no dish of the table. `dishes`: the list of every dish, in words.
    The problem says what it found beside the sentence, for a page or an agent: `ingredients_named` with
    `dishes_that_use_them`, or `built_around`."""
    found = ingredients_in(text, recipes)
    if found:
        return _with(text, found)
    what = _built_around(text)
    if what is not None:  # the person's own words: not an ingredient of ours, so it is not listed as one
        return InvalidRequest(f"{NO_RECIPE_USES.format(what=what, dishes=dishes)} {ILLUSTRATIVE}", built_around=what)
    return InvalidRequest(NO_DISH_NAMED.format(dishes=dishes))


def named_as_a_dish(unknown: Sequence[str], text: str, recipes: Mapping[str, Recipe]) -> InvalidRequest | None:
    """The refusal when every unknown "dish" of the sentence is an ingredient of ours ("eggs for 40"): the dishes
    that use it. None when one of them is anything else: the reader's own answer about an unknown dish stands."""
    by_tokens = {_tokens(ingredient): ingredient for ingredient in dishes_by_ingredient(recipes)}
    named = [by_tokens.get(_tokens(name)) for name in unknown]
    if not named or any(ingredient is None for ingredient in named):
        return None
    every = dishes_by_ingredient(recipes)
    return _with(text, {ingredient: every[ingredient] for ingredient in dict.fromkeys(named)})
