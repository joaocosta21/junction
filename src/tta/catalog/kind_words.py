"""Which words of a product's name say what kind of product it is (decision B65; review finding C3-F2).

A category number does not say it: category 22601 holds couverture, marzipan, baking powder and a bilberry
filling, and category 10592 holds egg yolk beside egg white. The name says it: "yolk", "brisket", "cocoa powder".
The words are found without a list of them, by counting the names of the product's own category:

- a word that half of the category or more carries says the category, not the product ("egg" is in 17 of the 21
  names of category 10592);
- a word no other name of the category carries cannot be shared by any candidate: a line or variety name
  ("Guanaja", "Long Life"), or the name of a product nothing in the category resembles ("panna cotta");
- the words in between are the telling ones, and the rarest of them are the product's **kind words**: every
  telling word that at most `KIND_WORD_FACTOR` times as many names carry as the rarest one ("yolk", 3 names,
  and not "liquid", 8 names).

Raw meat and fish are read more loosely (`of_one_type=True`), because their product type already says "beef"
and their names carry a producer's own marks beside the cut ("Guaranteed Tender", "square cut"): every telling
word is a kind word there, and a candidate need carry one of them, not all. Which of them it carries then orders
the candidates (`shared_weight`): a word many producers use is the trade's word for the cut ("tenderloin", 11
brands), a word of one or two is a mark ("Guaranteed", 2 brands).

A candidate is the same kind of product, as far as names show, when its name carries every kind word of the
original. Where the original has no telling word and its name has a word of its own, nothing can be shown to be
the same kind: the words of its own are then what a candidate would have to carry, and none does.

The English name decides. The Finnish name adds the kind words of its own that the English name does not repeat
("kaakaojauhe", cocoa powder, where the English "cocoa powder" is also inside "cocoa drink powder"), and decides
alone for a product with no English name.

**Every threshold and list here is ours, not Valio's.** A word wrongly taken as a kind word leaves a product
without a substitute; it cannot put a wrong product in its place.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from tta.catalog.name_words import SHARED_INSIDE_MIN_LENGTH, own_name_words
from tta.catalog.text import normalise
from tta.contracts.product import Product

# Ours. A word that this share of the category's names carries, or more, says the category: 1 in 2.
COMMON_SHARE_PARTS = 2
# Ours. The kind words are the telling words carried by at most this many times the names of the rarest one.
KIND_WORD_FACTOR = 2
# Ours. English plurals are compared without their ending, from this length up: "eggs" and "egg".
PLURAL_MIN_LENGTH = 4
# Ours. A shorter word is a mark or an abbreviation ("LL" for long life), never what a product is.
KIND_WORD_MIN_LENGTH = 3
# Finnish: a word ending in "-nen" joins other words through its stem in "-s" ("keltuainen", yolk, in
# "keltuaismassa", yolk mass).
_FINNISH_NEN, _FINNISH_STEM = "nen", "s"
# One word in two spellings (ours; `tta.catalog.kinds` reads both as the same flavour).
_SAME_WORD: Mapping[str, str] = {"cacao": "cocoa"}


@dataclass(frozen=True)
class WordCounts:
    """Of one language: how many names of the category carry each word, and of how many brands."""

    names: Mapping[str, int]
    brands: Mapping[str, int]


@dataclass(frozen=True)
class CategoryWords:
    """The names of one category counted word by word, English and Finnish apart."""

    size: int
    english: WordCounts
    finnish: WordCounts


@dataclass(frozen=True)
class KindWords:
    """The words a candidate's name must carry to be the same kind of product as the original."""

    english: tuple[tuple[str, str], ...] = ()  # (as compared, as the name writes it), in name order
    finnish: tuple[tuple[str, str], ...] = ()  # only words the English name does not repeat
    every: bool = True  # every kind word must be carried; False: one of them is enough
    # Brands that use each kind word, by the word as compared: what `shared_weight` adds up.
    brands: Mapping[str, int] = field(default_factory=dict)

    @property
    def known(self) -> bool:
        return bool(self.english or self.finnish)


def _compared(word: str) -> str:
    """A word as it is counted and compared: one spelling, no plural ending."""
    word = _SAME_WORD.get(word, word)
    if len(word) >= PLURAL_MIN_LENGTH and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _words_of(product: Product) -> tuple[dict[str, str], dict[str, str]]:
    """({as compared: as written}, the same for the Finnish name), each in name order."""
    english, finnish = own_name_words(product)
    return (
        {_compared(folded): written for folded, written in english},
        {_compared(folded): written for folded, written in finnish},
    )


def count_category_words(products: Iterable[Product]) -> CategoryWords:
    """The counts over the products given: one category, the original included."""
    names: tuple[Counter[str], Counter[str]] = (Counter(), Counter())
    brands: tuple[dict[str, set[str]], dict[str, set[str]]] = ({}, {})
    size = 0
    for product in products:
        size += 1
        # A product that states no brand counts as a producer of its own.
        brand = normalise(product.brand) or f"#{product.id}"
        for language, words in enumerate(_words_of(product)):
            names[language].update(words.keys())  # each name counts a word once
            for word in words:
                brands[language].setdefault(word, set()).add(brand)
    english, finnish = (
        WordCounts(names=names[language], brands={word: len(found) for word, found in brands[language].items()})
        for language in (0, 1)
    )
    return CategoryWords(size=size, english=english, finnish=finnish)


def _telling(words: Mapping[str, str], counts: WordCounts, size: int) -> dict[str, int]:
    """The words of the name that say more than the category and that another name carries, with the number
    of names that carry each."""
    return {
        word: counts.names.get(word, 1) for word in words
        if len(word) >= KIND_WORD_MIN_LENGTH
        and counts.names.get(word, 1) > 1 and counts.names.get(word, 1) * COMMON_SHARE_PARTS < size
    }


def _kind_words(
    words: Mapping[str, str], counts: WordCounts, size: int, *, rarest_only: bool
) -> tuple[tuple[str, str], ...]:
    """The telling words of one name, only the rarest of them under `rarest_only`."""
    telling = _telling(words, counts, size)
    if not telling:
        return ()
    most = min(telling.values()) * KIND_WORD_FACTOR if rarest_only else size
    return tuple((word, words[word]) for word in words if word in telling and telling[word] <= most)


def _own_words(words: Mapping[str, str], counts: WordCounts) -> tuple[tuple[str, str], ...]:
    """The words no other name of the category carries."""
    return tuple((word, written) for word, written in words.items() if counts.names.get(word, 1) <= 1)


def kind_words(product: Product, counts: CategoryWords, *, of_one_type: bool = False) -> KindWords:
    """The kind words of `product`, measured against the names of its category (`count_category_words`).
    `of_one_type`: the product is raw meat or fish of a product type of ours (the module's docstring)."""
    english, finnish = _words_of(product)
    size, strict = counts.size, not of_one_type
    only_finnish = {word: written for word, written in finnish.items() if word not in english}
    in_english = _kind_words(english, counts.english, size, rarest_only=strict)
    in_finnish = _kind_words(only_finnish, counts.finnish, size, rarest_only=strict)
    if strict and not in_english and not in_finnish:
        # No telling word in either name: the words of its own are what a candidate would have to carry.
        in_english = _own_words(english, counts.english)
        in_finnish = () if english else _own_words(finnish, counts.finnish)
    return KindWords(
        english=in_english,
        finnish=in_finnish,
        every=strict,
        brands={
            **{word: counts.finnish.brands.get(word, 1) for word, _ in in_finnish},
            **{word: counts.english.brands.get(word, 1) for word, _ in in_english},
        },
    )


def _carries(words: Iterable[str], kind_word: str, *, joined: bool = False) -> bool:
    """The name has the word, or a longer word that holds it ("suklaa" in "suklaanappi"). A short word must
    stand alone. `joined`, for Finnish, which joins words: a word of the name that sits inside the kind word
    counts too ("sooda" for "ruokasooda"), and so does a word built on the stem of a kind word in "-nen"
    ("valkuaismassa" for "valkuainen"); the English name has already had to carry its own kind words."""
    stem = kind_word[: -len(_FINNISH_NEN)] + _FINNISH_STEM if joined and kind_word.endswith(_FINNISH_NEN) else None
    for word in words:
        if word == kind_word or (len(kind_word) >= SHARED_INSIDE_MIN_LENGTH and kind_word in word):
            return True
        if joined and len(word) >= SHARED_INSIDE_MIN_LENGTH and word in kind_word:
            return True
        if stem is not None and len(stem) >= SHARED_INSIDE_MIN_LENGTH and word.startswith(stem):
            return True
    return False


def missing_kind_words(kind: KindWords, other: Product) -> tuple[str, ...]:
    """The kind words of the original that the name of `other` does not carry, as the original's name writes
    them; empty when it carries them all. The English ones when any is missing, else the Finnish ones, so that
    a sentence names words of one language."""
    english, finnish = _words_of(other)
    if not kind.every:
        if _carried(kind, english, finnish):
            return ()
        return tuple(written for _, written in (kind.english or kind.finnish))
    for required, carried, joined in ((kind.english, english, False), (kind.finnish, finnish, True)):
        missing = tuple(written for word, written in required if not _carries(carried, word, joined=joined))
        if missing:
            return missing
    return ()


def _carried(kind: KindWords, english: Iterable[str], finnish: Iterable[str]) -> tuple[str, ...]:
    """The kind words, as compared, that the two names carry."""
    english, finnish = tuple(english), tuple(finnish)
    return tuple(
        word
        for required, carried in ((kind.english, english), (kind.finnish, finnish))
        for word, _ in required
        if _carries(carried, word)
    )


def shared_weight(kind: KindWords, other: Product) -> int:
    """How much of the original's kind the name of `other` says: the brands that use each kind word it
    carries, added up. More is nearer: the trade's word for a cut outweighs one producer's mark."""
    english, finnish = _words_of(other)
    return sum(kind.brands.get(word, 1) for word in _carried(kind, english, finnish))
