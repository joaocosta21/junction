"""Product-name matching for the catalog search (SPEC section 3, step 3).

A term matches a product when its English name or its Finnish name has it. English names are
matched at the start of a word, so "tea" does not find "steak". Finnish names are matched
anywhere, because Finnish joins words: "maito" has to find "kevytmaitojuoma". A term of
fewer than four letters must start a Finnish word too: "tea" is inside 78 Finnish names, 51 of them
on products with no English word starting with "tea" ("kostea", "Flank steak"), and "oil" is inside
the 104 names with "broileri" (catalog counts).
923 Finnish names carry a registered or trade mark sign (AIMO/docs/PRODUCT-DATA.md section 2.1), so
everything that is not a letter or a digit becomes a space before matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tta.contracts.product import Product

_SEPARATORS = re.compile(r"[\W_]+")
FINNISH_ANYWHERE_MIN_LENGTH = 4  # our threshold: shorter terms match too much inside longer words
# Words that, standing right before a word, make it mean something else. Ours, from the whole catalog (14 Nov
# 2026): "semi skimmed" 30 names, "non alcoholic" 33, "non carbonated" 11, "half baked" 1. Before, the name term
# "skimmed" also found every semi-skimmed milk (29 of the 46 milks it returned). "un" covers a name written
# "un-salted"; "unsalted" in one word never matched "salted". A word of degree ("low", "lightly", "pre") is not
# here: a lightly salted butter is salted.
OPPOSITE_BEFORE = frozenset({"semi", "non", "half", "un", "not"})


def normalise(text: str | None) -> str:
    """Casefolded text with every run of other characters turned into one space."""
    return _SEPARATORS.sub(" ", (text or "").casefold()).strip()


@dataclass(frozen=True, slots=True)
class ProductNames:
    """The names of one product, ready for matching against a normalised term."""

    # Both normalised, with a leading space: " term" then finds a word that starts with the term.
    english: str
    finnish: str

    def english_word_starts_with(self, term: str) -> bool:
        """A word of the English name starts with the term, and the word before it does not turn it into its
        opposite: "skimmed" is not in "semi skimmed", "alcoholic" not in "non alcoholic". A term that says the
        qualifier itself ("semi skimmed") matches as it stands."""
        needle = f" {term}"
        start = self.english.find(needle)
        while start != -1:
            before = self.english[:start].rsplit(" ", 1)[-1]
            if before not in OPPOSITE_BEFORE:
                return True
            start = self.english.find(needle, start + 1)
        return False

    def finnish_contains(self, term: str) -> bool:
        if len(term) < FINNISH_ANYWHERE_MIN_LENGTH:
            return f" {term}" in self.finnish
        return term in self.finnish

    def has(self, term: str) -> bool:
        return self.english_word_starts_with(term) or self.finnish_contains(term)

    def has_any(self, terms: tuple[str, ...]) -> bool:
        return any(self.has(term) for term in terms)


def names_of(product: Product) -> ProductNames:
    return ProductNames(english=f" {normalise(product.name_en)}", finnish=f" {normalise(product.name_fi)}")
