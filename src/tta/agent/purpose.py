"""Whether a buyer's words say the formula matters: "for baking", "for cakes", "for whipping" (replan P10, option a).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" and the 15% "substitutions
beyond the happy path". Valio Aimo, 14 Nov 2026: for everyday milk the formula does not matter, but for baking
and cakes the contents of the product can make a difference, "so you really need to consider it". The request's
words are one of the three things that decide (with the customer's profile and a recipe line).

A pure function over the text: no model, no catalog, nothing guessed. It reads a use only when the words give it
as a purpose, after "for", "to", "in" or "into": "cream for whipping", "milk for baking", "butter for the cakes",
"cream to whip". A product's own name is not a purpose: "whipping cream" and "baking chocolate" say nothing about
what the buyer will do with it. A negated purpose ("not for baking") is not one. English only: the Finnish and
Swedish words were not checked with a speaker, so none is in the table.
Not yet wired into the reading (wave 2): `tta.agent.rules_reader` does not call it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# The uses of `P10-formula.md` (row a): baking, pastry, whipping, sauce, cake, foam, a recipe. Each with the word
# forms a kitchen writes. The list is ours.
_USES: tuple[tuple[str, str], ...] = (
    ("baking", r"bak(?:e|es|ing)|pastr(?:y|ies)|dough"),
    ("cakes", r"(?:cheese|cup)?cakes?|muffins?|desserts?"),
    ("whipping", r"whip(?:ping|ped)?|foam(?:ing)?|frothing|froth"),
    ("sauce", r"sauces?"),
    ("recipe", r"recipes?"),
)
_PURPOSE = r"\b(?:for|to|in|into)\s+(?:(?:a|an|the|our|my|some|making|make)\s+){0,2}"
_PATTERNS = tuple((use, re.compile(rf"{_PURPOSE}(?:{words})\b")) for use, words in _USES)
_NEGATED = re.compile(r"\b(?:not|never|no)\s+(?:\w+\s+)?$|n['’]t\s+(?:\w+\s+)?$")

FORMULA_MATTERS = 'Formula matters: the request says "{said}".'


@dataclass(frozen=True)
class FormulaUse:
    """A use the buyer's words name, for which the product's formula matters."""

    use: str  # "baking", "cakes", "whipping", "sauce" or "recipe"
    said: str  # the buyer's own words, casefolded: "for baking"

    @property
    def sentence(self) -> str:
        """The sentence for a person: 'Formula matters: the request says "for baking".'"""
        return FORMULA_MATTERS.format(said=self.said)


def formula_use(text: str) -> FormulaUse | None:
    """The first use the text names as a purpose, or `None` when it names none."""
    folded = text.casefold()
    found = [(match.start(), use, match.group()) for use, pattern in _PATTERNS for match in pattern.finditer(folded)
             if not _NEGATED.search(folded[:match.start()])]
    if not found:
        return None
    _, use, said = min(found)
    return FormulaUse(use=use, said=" ".join(said.split()))


def formula_matters(text: str) -> bool:
    """True when the buyer's words say what the product is for and the formula matters for that use."""
    return formula_use(text) is not None
