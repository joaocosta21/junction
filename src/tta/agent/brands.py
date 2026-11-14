"""The brands of Valio Aimo's catalog a buyer may name: "Arla whipping cream" is Arla's (decision B39).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": a brand word used to be
left out without a word, so "Arla lactose-free whipping cream" came back as any brand's. A brand said in a line
is kept as a name term the product must carry, and the reading's sentence says so (`tta.agent.notes`).

The typed request has no brand field, so the brand travels as a name term. That works because the catalog's
names start with the brand: measured on the product file (17,546 products), every one of the 61 products of
brand "Arla" has "Arla" in its name. A brand term also returns the brand's own lines ("Arla Pro", "Arla Lempi"),
whose names start with the same word.

The list is built from the catalog (`Product.brand`), with a minimum of care. All thresholds are ours:
- one or two whole words of letters, at least 3 letters in all, matched whole and case-insensitively;
- at least 3 products of the brand carry it in their name, so the term returns them;
- at least 4 of every 5 products the term returns are of that brand or of a line of it (its brand starts with the
  same words): this leaves out a brand that is also an everyday word of product names ("Fresh", "Classic",
  "Pizza", "Royal"), and with them some real brands whose name other brands' products carry ("Paulig");
- not a word the reader already reads (a product type, an allergen, a claim, a label, a unit, a day, a use), and
  not one of the few everyday words below.
A word that is no brand of the list is left as it was: not asked about (asking about every adjective would refuse
ordinary sentences).
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from itertools import accumulate
from pathlib import Path

from tta.agent.days import named_dates
from tta.agent.parts import NOT_A_TERM
from tta.agent.purpose import formula_matters
from tta.agent.textcheck import CONFIRMED, WORD, allergen_mentions, exclusion_triggers, unit_of
from tta.agent.typenames import TypeNames, types_named
from tta.agent.usual import says_usual
from tta.agent.wording import claims_in, labels_in, preferences_in, strictness_in
from tta.catalog.loader import load_products
from tta.catalog.text import FINNISH_ANYWHERE_MIN_LENGTH, ProductNames, names_of, normalise
from tta.contracts.product import Product

MAX_BRAND_WORDS = 2
MIN_BRAND_LETTERS = 3
MIN_BRAND_PRODUCTS = 3
# Of the products a brand term returns, the share that must be of that brand or of a line of it: 4 of every 5.
MIN_SHARE_OF_RETURNED = (4, 5)
# Brands of the catalog that pass every count above and are everyday words of a request. Ours; "heti" is Finnish
# for "at once".
EVERYDAY_WORDS = frozenset({"always", "look", "true", "unlimited", "smiling", "mission", "heti"})
_ANY_DAY = date(2026, 1, 1)  # only whether a word names a day matters here, not which

Phrase = tuple[str, ...]


@dataclass(frozen=True)
class Brands:
    """The brands the reader knows: their casefolded words and the catalog's own spelling."""

    spelling: Mapping[Phrase, str] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.spelling)

    def spellings(self) -> frozenset[str]:
        return frozenset(self.spelling.values())

    def found(self, words: Sequence[str], skipping: Collection[int] = ()) -> dict[int, str]:
        """Each word that is part of a brand, by its index, with the brand's spelling. A two-word brand wins
        over the one-word brand it starts with ("Arla Pro" over "Arla"). A word of `skipping` is never one."""
        found: dict[int, str] = {}
        for length in range(MAX_BRAND_WORDS, 0, -1):
            for at in range(len(words) - length + 1):
                indices = range(at, at + length)
                brand = self.spelling.get(tuple(words[at:at + length]))
                if brand is not None and not any(index in found or index in skipping for index in indices):
                    found.update(dict.fromkeys(indices, brand))
        return found


NO_BRANDS = Brands()


def _reader_reads(phrase: Phrase, table: Sequence[TypeNames], known: Collection[str]) -> bool:
    """True when the reader already takes one of the words for something else."""
    text = " ".join(phrase)
    if any(word in known or word in NOT_A_TERM or word in EVERYDAY_WORDS or unit_of(word) for word in phrase):
        return True
    if types_named(list(enumerate(phrase)), table) or allergen_mentions(phrase) or exclusion_triggers(phrase):
        return True
    said = (claims_in, labels_in, preferences_in, strictness_in)
    if any(found(text) for found in said) or CONFIRMED.search(text) or named_dates(text, _ANY_DAY):
        return True
    return says_usual(text) or formula_matters(f"for {text}")


class _Returned:
    """Which products a name term returns, as `tta.catalog.text.ProductNames.has` decides it, for many terms: one
    search through all the names instead of one per product (17,546 products by some 600 brands)."""

    def __init__(self, names: Sequence[ProductNames]) -> None:
        self._english = _Blob([name.english for name in names])
        self._finnish = _Blob([name.finnish for name in names])

    def by(self, term: str) -> frozenset[int]:
        """The positions of the products whose English name has a word starting with the term, or whose Finnish
        name holds it (a term under four letters must start a Finnish word too)."""
        in_finnish = term if len(term) >= FINNISH_ANYWHERE_MIN_LENGTH else f" {term}"
        return self._english.holding(f" {term}") | self._finnish.holding(in_finnish)


class _Blob:
    """Many one-line texts as one, so a word is looked for once in all of them."""

    def __init__(self, texts: Sequence[str]) -> None:
        self._text = "\n".join(texts)
        self._starts = list(accumulate((len(text) + 1 for text in texts), initial=0))[:-1]

    def holding(self, needle: str) -> frozenset[int]:
        found: set[int] = set()
        at = self._text.find(needle)
        while at >= 0:
            found.add(bisect_right(self._starts, at) - 1)
            at = self._text.find(needle, at + 1)
        return frozenset(found)


def _specific(phrase: Phrase, own: Collection[int], returned: frozenset[int],
              brand_words: Sequence[Phrase]) -> bool:
    """Enough of the brand's products carry it in the name, and what the term returns is mostly the brand's."""
    if len(returned & frozenset(own)) < MIN_BRAND_PRODUCTS:
        return False
    of_the_brand = sum(brand_words[position][:len(phrase)] == phrase for position in returned)
    part, whole = MIN_SHARE_OF_RETURNED
    return of_the_brand * whole >= len(returned) * part


def catalog_brands(products: Iterable[Product], table: Sequence[TypeNames], known: Collection[str] = ()) -> Brands:
    """The brands of these products by the rules above. `table` and `known` are what the reader already reads:
    the product types' words and its own plain words."""
    active = [product for product in products if not product.deleted]
    returned = _Returned([names_of(product) for product in active])
    brand_words = [tuple(normalise(product.brand).split()) for product in active]
    own: defaultdict[Phrase, list[int]] = defaultdict(list)
    for position, words in enumerate(brand_words):
        own[words].append(position)
    spelling: dict[Phrase, str] = {}
    for phrase, members in sorted(own.items()):
        text = " ".join(phrase)
        whole_words = tuple(WORD.findall(text)) == phrase and 1 <= len(phrase) <= MAX_BRAND_WORDS
        if not whole_words or len(text.replace(" ", "")) < MIN_BRAND_LETTERS or len(members) < MIN_BRAND_PRODUCTS:
            continue
        if _reader_reads(phrase, table, known) or not _specific(phrase, members, returned.by(text), brand_words):
            continue
        written = Counter((active[position].brand or "").strip() for position in members)
        spelling[phrase] = min(written, key=lambda brand: (-written[brand], brand))  # the most used spelling
    return Brands(spelling)


def products_of(product_file: Path) -> tuple[Product, ...]:
    """The products of the product file. The brand and the names only: no comparison file is needed."""
    return tuple(load_products(product_file))
