"""What two product names say differently, without a word list for the difference itself (review finding S11).

A product line names its variants in its names: two products of one brand whose names differ only in a word the
reader does not know ("Tiramisu", "Delight", "high heat") are variants of each other, and nothing in the data
says they are the same in a kitchen. So a word the reader does not know is never read as "no difference":
`name_difference` gives the words, and the substitute check says them (`tta.offers.substitutes`).

A word is known when a list of ours explains it: a size, the brand, a flavour or a use (`tta.catalog.kinds`),
a word of the product type's own table, or one of `_EXPLAINED_ELSEWHERE` (pack, storage, a nutritional claim,
origin: each has a check of its own); or when the other product's ingredient list names it. **The lists are
ours.** A word missing from them makes a difference that is said to a person; it cannot make one disappear.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from tta.catalog.kinds import known_word_pattern, type_terms_of
from tta.catalog.text import normalise
from tta.contracts.product import Product

# A size, a count or a number: "1", "5000", "6x1l", "500g", "20mm", "e900" (an estimated weight), "L180" (an
# egg size with its count). The pack size has its own check.
_SIZE = re.compile(r"^(?:[a-z]|approx|appr|ca)?\d|^(?:g|kg|ml|cl|dl|l|mm|cm|m|x|kpl|pcs|pc|st)$")
# Words that are no variant of a product, in English and Finnish. Ours. Pack, sales-channel ("food service")
# and storage words: the pack size and the availability are checked on their own. Claim words: the dietary
# claims are compared code by code, and "organic" is a certificate label a request can require.
# Fat words ("whole", "semi skimmed", "light"): the formula check compares the fat in grams, and where it has
# no figures the verdict already says the formula cannot be compared.
_EXPLAINED_ELSEWHERE = frozenset({
    # joining words
    "a", "an", "and", "the", "with", "without", "in", "of", "for", "to", "from", "on", "or", "no", "non", "ja",
    "ei", "ilman", "tai", "sis",
    # pack
    "pack", "package", "pkt", "box", "bag", "bags", "bottle", "can", "carton", "tetra", "tray", "cup", "tub",
    "bucket", "jar", "pouch", "portion", "portions", "multipack", "multipackage", "homepackage", "case", "ca",
    "approx", "appr", "about", "n", "novobox", "bib", "refill", "refil", "täyttöpakkaus", "pakkaus", "kotipakkaus",
    "monipakkaus", "rasia", "pussi", "pullo", "tölkki", "annos", "laatikko", "prk",
    # sales channel
    "food", "service", "foodservice", "suurtalous", "catering", "horeca",
    # storage
    "uht", "esl", "frozen", "deepfrozen", "fresh", "chilled", "pakaste", "pakastettu", "tuore",
    # claims and labels
    "lactose", "lactosefree", "laktoositon", "free", "low", "vähälaktoosinen", "hyla", "gluten", "glutenfree",
    "gluteeniton", "vegan", "vegaaninen", "added", "sugar", "lisättyä", "sokeria", "organic", "luomu",
    # origin
    "suomesta", "suomi", "finland", "finnish", "kotimainen",
    # fat
    "whole", "semi", "skimmed", "fat", "light", "lite", "täys", "kevyt", "rasvaton", "vähärasvainen", "rasvaa",
})
# Our threshold: a word this long that sits inside a word of the other name is the same word ("maitojauhe" in
# "rasvaton maitojauhe", "milk" is too short to be looked for inside "buttermilk").
SHARED_INSIDE_MIN_LENGTH = 5
INGREDIENT_MIN_LENGTH = 3  # ours: "oat" is the shortest ingredient word worth matching
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)?")


@dataclass(frozen=True)
class NameDifference:
    """The words in which two names of one brand differ, as the names write them, in name order."""

    original_words: tuple[str, ...]  # in the original's name and not in the other's
    words: tuple[str, ...]  # in the other's name and not in the original's


def _folded(words: Iterable[str]) -> frozenset[str]:
    return frozenset(normalise(word) for word in words)


def _without_marks(word: str) -> str:
    """ "crème fraîche" as "creme fraiche": the catalog writes both. Only for comparing two names."""
    return "".join(mark for mark in unicodedata.normalize("NFKD", word) if not unicodedata.combining(mark))


def _plain(word: str) -> str:
    return _without_marks(normalise(word))


def _brand_words(*products: Product) -> frozenset[str]:
    return frozenset(word for product in products for word in normalise(product.brand).split())


def _words(name: str, drop: frozenset[str]) -> tuple[str, ...]:
    """The words of a name as written, without sizes, brand words and words explained elsewhere."""
    kept = []
    for word in _WORD.findall(name):
        folded = normalise(word)
        if not folded or _SIZE.match(folded) or folded in drop or folded in _EXPLAINED_ELSEWHERE:
            continue
        kept.append(word)
    return tuple(kept)


def _is_ingredient(word: str, product: Product) -> bool:
    """The product's ingredient list names the word ("Oat" and "OATS 10%"): what one name spells out and the
    other leaves unsaid is then no difference between the two."""
    folded = normalise(word)
    if len(folded) < INGREDIENT_MIN_LENGTH:
        return False
    return any(
        len(each) >= INGREDIENT_MIN_LENGTH and (each.startswith(folded) or folded.startswith(each))
        for each in normalise(product.key_ingredients).split()
    )


def _unknown(name: str, product: Product, other: Product, drop: frozenset[str]) -> tuple[str, ...]:
    """The words of the product's name that nothing explains: no list of ours, no word of its product type's
    table, no ingredient of the other product."""
    terms = type_terms_of(product)
    return tuple(
        word for word in _words(known_word_pattern().sub(" ", name), drop)
        if not any(normalise(word).startswith(term) for term in terms) and not _is_ingredient(word, other)
    )


def _languages(original: Product, other: Product) -> tuple[tuple[str, str], ...]:
    """The pairs of names in one language, English first; empty when the two share no language."""
    pairs = ((original.name_en, other.name_en), (original.name_fi, other.name_fi))
    return tuple((mine, theirs) for mine, theirs in pairs if mine and theirs)


def _difference(original: Product, other: Product, names: tuple[str, str]) -> NameDifference | None:
    drop = _brand_words(original, other)
    mine, theirs = _words(names[0], drop), _words(names[1], drop)
    # Joined without spaces, so "milkdrink" is found in "milk drink" and "milk" in "milkdrink".
    my_text = "".join(_plain(word) for word in mine)
    their_text = "".join(_plain(word) for word in theirs)
    unexplained = [
        word for word in _unknown(names[0], original, other, drop) if _plain(word) not in their_text
    ] + [word for word in _unknown(names[1], other, original, drop) if _plain(word) not in my_text]
    if not unexplained:
        return None
    return NameDifference(
        original_words=tuple(dict.fromkeys(word for word in mine if _plain(word) not in their_text)),
        words=tuple(dict.fromkeys(word for word in theirs if _plain(word) not in my_text)),
    )


def name_difference(original: Product, other: Product) -> NameDifference | None:
    """The words in which the names of two products of one brand differ, when at least one of them is a word
    no list of ours explains; `None` when the names differ in nothing unexplained.

    The difference must show in every language both products are named in: a variant is named in both
    ("Delight", "high heat"), while a name that only spells the product out in one language ("Oatly iKaffe"
    and "Oatly iKaffe Oat drink", both "kaurajuoma" in Finnish) is the same product. The words given are the
    English ones when there are any.

    `None` also when either product states no brand, the brands differ, or the names share no language: two
    brands name their products differently, so their words say nothing about variants.
    """
    brand = normalise(original.brand)
    languages = _languages(original, other)
    if not brand or brand != normalise(other.brand) or not languages:
        return None
    found = [_difference(original, other, names) for names in languages]
    return found[0] if all(each is not None for each in found) else None


def _product_words(product: Product, drop: frozenset[str]) -> frozenset[str]:
    names = f"{product.name_en or ''} {product.name_fi or ''}"
    return frozenset(_without_marks(word) for word in _folded(_words(names, drop)))


def shares_a_product_word(original: Product, other: Product) -> bool:
    """The two names, English and Finnish, have at least one word in common that is no size, no brand and no
    word explained elsewhere. A word of `SHARED_INSIDE_MIN_LENGTH` letters or more also counts when it sits
    inside a word of the other name, because Finnish joins words."""
    drop = _brand_words(original, other)
    mine, theirs = _product_words(original, drop), _product_words(other, drop)
    if mine & theirs:
        return True
    return any(
        len(short) >= SHARED_INSIDE_MIN_LENGTH and short in long
        for a in mine for b in theirs for short, long in ((a, b), (b, a))
    )
