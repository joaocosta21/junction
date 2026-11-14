"""Qualifiers: the words of an ingredient list that say where or how an ingredient was farmed, found from the
catalog's own statements when it is loaded (decision B49). Nothing here is a list of ingredients or countries.

**What is measured** (whole catalog, every language; `derive_qualifiers`):

1. *A qualifier, not a component.* A word that opens the name of many different components, each of which the
   catalog also names without it ("organic" in front of 179 English components: "organic cream" and "cream",
   "organic oats" and "oats"), and that rarely stands as a component by itself (`MIN_HEADS`, `MAX_ALONE_SHARE`).
   "wheat" opens many names too ("wheat flour", "wheat starch") and is a component by itself: not a qualifier.
2. *Of origin or farming, by the product data.* A qualifier is of origin or farming when the packs of the
   products that use it carry one same certificate (`packagingMarkedLabel`: an organic-farming mark, a
   Finnish-origin mark) on at least `MIN_LABEL_SHARE` of them: the word says what the certificate says.
   Measured: "organic" 93% EU_ORGANIC_FARMING, "luomu" 74%, "Finnish" 73% and "suomalainen" 71%
   GOODS_FROM_FINLAND_BLUE_SWAN; the next word is "pasteurised" at 55% and it is not one. Every other
   qualifier ("dried", "pasteurised", "smoked", "concentrated", "red") is a word of processing or description:
   it can change how an ingredient behaves, so it stays part of the component's name.
3. *A place.* What the statements themselves name after the word for origin ("Origin: EU and non-EU.",
   "Alkuperä: Suomi") at least `MIN_PLACE_MENTIONS` times is a place; a place in brackets behind a component
   ("WHEAT (EU)") or as the last word of its name says its origin.

**Typed by hand, and why:** only `ORIGIN_MARKERS`, the word for "origin" in the three main languages of the
file. It is label grammar, like the word that closes a list, and no place and no ingredient is typed.

The comparison (`tta.offers.composition`) reads the table through `current_qualifiers()`. The catalog fills it
when it is loaded from the product file (`provide_qualifiers`); a comparison can be given a table explicitly,
and without either the table is empty and every word stays part of its component.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from fractions import Fraction

from tta.catalog.ingredient_list import CONJUNCTIONS, Component, normalise, parse_statement
from tta.contracts.product import Product

# Ours, chosen from the distribution (whole catalog, every language, 14 Nov 2026): 3,797 words open a component
# name whose rest is a component too; 3,293 of them for fewer than 5 heads, 180 for 12 or more, and 89 of those
# rarely stand alone. From 12 up the list is adjectives; between 8 and 11 a brand name, "food", "other" and
# "with" come in. The words of origin or farming found have 26 heads or more, so the choice between 8 and 25
# changes only the list of processing words, which changes no comparison.
MIN_HEADS = 12
# Ours. A qualifier stands alone as a component less than once per two heads: "organic" 3 times against 179
# heads, "red" 12 against 46; "white" (31 against 35) and "wheat" (402 against 34) are components.
MAX_ALONE_SHARE = Fraction(1, 2)
# Ours. Two in three of the products that use the word carry one same certificate. Measured gap: 71% to 55%.
MIN_LABEL_SHARE = Fraction(2, 3)
MIN_PRODUCTS = 20  # ours: a share of fewer products than this says nothing
MIN_PLACE_MENTIONS = 3  # ours: named after the word for origin at least this many times
MAX_PLACE_WORDS = 3
# Label grammar, not places: the word for "origin" in English, Finnish and Swedish, as a statement writes it.
ORIGIN_MARKERS = ("origin", "alkuperä", "alkuperämaa", "ursprung", "ursprungsland")

ORIGIN_OR_FARMING = "origin or farming"
PROCESSING_OR_DESCRIPTION = "processing or description"

_AFTER_MARKER = re.compile(rf"\b(?:{'|'.join(ORIGIN_MARKERS)})\b([^.;()\[\]]{{1,60}})", re.IGNORECASE)
_SAYS = re.compile(r":|\bis\b|\bon\b|\bär\b", re.IGNORECASE)
_BETWEEN_PLACES = re.compile(rf"/|,|\s(?:{'|'.join(CONJUNCTIONS)})\s", re.IGNORECASE)
_MARKER_KEYS = frozenset(normalise(each) for each in ORIGIN_MARKERS)


@dataclass(frozen=True)
class Qualifier:
    """One word the catalog shows to be a qualifier, with what was measured of it."""

    word: str  # normalised, as it is compared
    heads: int  # different components it stands in front of, each also named without it
    alone: int  # times it is a component by itself
    products: int  # products whose statements use it so
    label: str | None  # the certificate most of those products carry
    label_share: Fraction  # the share of them that carry it
    kind: str  # ORIGIN_OR_FARMING or PROCESSING_OR_DESCRIPTION


@dataclass(frozen=True)
class Qualifiers:
    """The table a comparison reads. Empty: every word stays part of its component."""

    origin_words: frozenset[str] = frozenset()  # qualifiers of origin or farming, normalised
    places: frozenset[str] = frozenset()  # normalised: "finland", "eu", "non eu"
    found: tuple[Qualifier, ...] = ()  # every qualifier measured, of both kinds, most heads first

    def without_origin(self, key: str) -> str:
        """The normalised name without its words of origin or farming and without a place at its end. A name
        that is nothing else ("organic" alone, "Finland" alone) is returned as it is."""
        words = [word for word in key.split() if word not in self.origin_words]
        for size in range(min(MAX_PLACE_WORDS, len(words) - 1), 0, -1):
            if " ".join(words[-size:]) in self.places:
                words = words[:-size]
                break
        return " ".join(words) or key

    def says_origin_only(self, key: str) -> bool:
        """Whether what stands in brackets behind a component says only where it comes from: "EU",
        "origin Finland", "Finnish"."""
        words = [word for word in key.split() if word not in _MARKER_KEYS and word not in self.origin_words]
        return bool(key) and (not words or " ".join(words) in self.places)


NO_QUALIFIERS = Qualifiers()


def no_qualifiers() -> Qualifiers:
    """The provider before any catalog is loaded, and the one a test sets to start clean."""
    return NO_QUALIFIERS


_provider: Callable[[], Qualifiers] = no_qualifiers


def provide_qualifiers(provider: Callable[[], Qualifiers]) -> None:
    """Name where the comparison reads its table from. The catalog calls this when it is loaded."""
    global _provider  # noqa: PLW0603 - the one module-level provider; tests reset it in their conftest
    _provider = provider


def current_qualifiers() -> Qualifiers:
    return _provider()


def derive_qualifiers(products: Iterable[Product]) -> Qualifiers:
    """The table, measured from every ingredient statement of the products given."""
    names: Counter[str] = Counter()
    listed: Counter[str] = Counter()  # as a component of the list itself, not in another's brackets
    users: defaultdict[str, set[str]] = defaultdict(set)
    places: Counter[str] = Counter()
    labels: dict[str, tuple[str, ...]] = {}
    for product in products:
        labels[product.id] = product.labels
        for statement in product.ingredient_statements:
            places.update(_places_named(statement.text))
            components = parse_statement(statement.text)
            listed.update(each.key for each in components if each.key)
            for key in _keys(components):
                names[key] += 1
                users[key].add(product.id)
    found = _qualifiers(names, users, labels)
    return Qualifiers(
        origin_words=frozenset(each.word for each in found if each.kind == ORIGIN_OR_FARMING),
        # A place is no component: "rye" follows the word for origin too ("origin of the rye"), and is listed.
        places=frozenset(
            place for place, count in places.items() if count >= MIN_PLACE_MENTIONS and listed[place] < count
        ),
        found=found,
    )


def _keys(components: tuple[Component, ...]) -> list[str]:
    return [key for each in components for key in ((each.key,) if each.key else ()) + tuple(_keys(each.parts))]


def _places_named(text: str) -> list[str]:
    """ "Origin: EU and non-EU" -> ["eu", "non eu"]; "Origin of oats is Finland" -> ["finland"]. What follows the
    marker without ":" or "is" is read only when it is short ("origin Finland"), never "origin of pork"."""
    found = []
    for match in _AFTER_MARKER.finditer(text):
        after = _SAYS.split(match.group(1))
        if len(after) == 1 and normalise(after[0]).startswith("of "):
            continue
        for piece in _BETWEEN_PLACES.split(after[-1]):
            key = normalise(piece)
            if key and len(key.split()) <= MAX_PLACE_WORDS and not any(letter.isdigit() for letter in key):
                found.append(key)
    return found


def _qualifiers(
    names: Counter[str], users: dict[str, set[str]], labels: dict[str, tuple[str, ...]]
) -> tuple[Qualifier, ...]:
    heads: defaultdict[str, set[str]] = defaultdict(set)
    using: defaultdict[str, set[str]] = defaultdict(set)
    for key in names:
        word, _, rest = key.partition(" ")
        if rest in names:
            heads[word].add(rest)
            using[word] |= users[key]
    found = [
        _measured(word, len(rests), names.get(word, 0), using[word], labels)
        for word, rests in heads.items()
        if len(rests) >= MIN_HEADS and names.get(word, 0) < len(rests) * MAX_ALONE_SHARE
    ]
    return tuple(sorted(found, key=lambda each: (-each.heads, each.word)))


def _measured(word: str, heads: int, alone: int, using: set[str], labels: dict[str, tuple[str, ...]]) -> Qualifier:
    carried = Counter(label for product_id in using for label in set(labels[product_id]))
    label, count = carried.most_common(1)[0] if carried else (None, 0)
    share = Fraction(count, len(using))
    of_origin = len(using) >= MIN_PRODUCTS and share >= MIN_LABEL_SHARE
    return Qualifier(
        word=word, heads=heads, alone=alone, products=len(using), label=label, label_share=share,
        kind=ORIGIN_OR_FARMING if of_origin else PROCESSING_OR_DESCRIPTION,
    )
