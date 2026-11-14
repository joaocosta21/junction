"""A use that names a variant of the product type: "cream for whipping" is whipping cream (decision B40).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": "20 litres of cream for
whipping" used to be read as plain cream, whose first pick may be a cooking cream. The use narrows the type only
where it names a variant the catalog sells under that word: for cream, "whipping" and "cooking" (category 10401's
names say "whipping cream" and "cooking cream"). "Butter for baking" stays butter: no variant is named. The
variant travels as the name term a buyer's own "whipping cream" gives. The table is ours.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tta.agent.purpose import purpose_pattern, said_as_purpose, spans_of
from tta.agent.textcheck import WORD

# product type -> (the name term of the variant, the use's words, the verbs that may follow "to")
_VARIANTS: Mapping[str, tuple[tuple[str, str, str], ...]] = {
    "cream": (("whipping", r"whip(?:ping|ped)?", r"whip"), ("cooking", r"cook(?:ing)?", r"cook")),
}
_PATTERNS = {
    key: tuple((term, purpose_pattern(words, verbs)) for term, words, verbs in variants)
    for key, variants in _VARIANTS.items()
}
# Variants a buyer names by one word of the product's name. Said in a part of its own after the line ("500 kg of
# butter, unsalted"), the word is that line's name term (review finding S3). The catalog's names carry each:
# butter "unsalted" 3 and "salted" 8 of 19; milk "whole" 10, "semi skimmed" 29 and "skimmed" 46 of 74 (the
# search's "skimmed" also returns the semi-skimmed, as it does for a buyer's own "skimmed milk").
_NAMED: Mapping[str, tuple[str, ...]] = {
    "butter": ("unsalted", "salted"),
    "milk": ("whole", "semi-skimmed", "skimmed"),
}
VARIANT_READ = '{product} "{said}" is read as {term} {product}.'


@dataclass(frozen=True)
class Variant:
    """The variant a use names: its name term and the buyer's own words."""

    product_type: str
    term: str  # "whipping"
    said: str  # "for whipping"

    @property
    def sentence(self) -> str:
        """'Cream "for whipping" is read as whipping cream.'"""
        product = self.product_type.replace("_", " ")
        return VARIANT_READ.format(product=product, said=self.said, term=self.term).capitalize()


def variant_terms(product_type: str | None) -> frozenset[str]:
    """The name terms that are variants of this product type."""
    return frozenset(term for term, _ in _PATTERNS.get(product_type or "", ()))


def variant_for(product_type: str | None, text: str, name_terms: Sequence[str] = ()) -> Variant | None:
    """The variant of this product type the text names as a use, or `None`: when it names none, when it names
    two, or when the line's own words already name a variant ("whipping cream for cooking")."""
    if variant_terms(product_type) & {term.casefold() for term in name_terms}:
        return None
    said = [(term, found[0][1]) for term, pattern in _PATTERNS.get(product_type or "", ())
            if (found := said_as_purpose(pattern, text))]
    if len(said) != 1 or product_type is None:
        return None
    return Variant(product_type=product_type, term=said[0][0], said=said[0][1])


def named_variants(product_type: str | None) -> frozenset[str]:
    """The one-word variants the rules know for this product type."""
    return frozenset(_NAMED.get(product_type or "", ()))


def variant_named(product_type: str | None, words: Sequence[str]) -> str | None:
    """The variant of this product type these words are, and nothing else: ("semi", "skimmed") is
    "semi-skimmed" for milk. `None` for any other words or type."""
    said = tuple(word.casefold() for word in words)
    return next((term for term in _NAMED.get(product_type or "", ()) if tuple(WORD.findall(term)) == said), None)


def variant_spans(product_type: str | None, text: str) -> list[tuple[int, int]]:
    """Where the text names a use that is a variant of this product type ("for cooking")."""
    return [span for _, pattern in _PATTERNS.get(product_type or "", ()) for span in spans_of(pattern, text)]
