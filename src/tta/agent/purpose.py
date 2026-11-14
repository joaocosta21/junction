"""Whether a buyer's words say the formula matters: "for baking", "for cakes", "for whipping" (replan P10, option a).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" and the 15% "substitutions
beyond the happy path". Valio Aimo, 14 Nov 2026: for everyday milk the formula does not matter, but for baking
and cakes the contents of the product can make a difference, "so you really need to consider it". The request's
words are one of the three things that decide (with the customer's profile and a recipe line).

A pure function over the text: no model, no catalog, nothing guessed. It reads a use only when the words give it
as a purpose, after "for", "in" or "into", or as a verb after "to": "cream for whipping", "milk for baking",
"butter for the cakes", "cream to whip". A place or a recipient is not a purpose: "to the dessert kitchen", "for
the pastry chef" say where the goods go, not what is done with them. A product's own name is not a purpose:
"whipping cream" and "baking chocolate" say nothing about what the buyer will do with it. A negated purpose ("not
for baking") is not one. English only: the Finnish and Swedish words were not checked with a speaker, so none is
in the table.
Wired into the reading since wave 2: `tta.agent.rules_reader` sets `keep_formula` on the line the words belong
to, and `tta.agent.notes` writes the sentence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# The uses of `P10-formula.md` (row a): baking, pastry, whipping, sauce, cake, foam, a recipe. Each with the word
# forms a kitchen writes, and the verbs that may follow "to" ("to whip", "to bake"). The list is ours.
_USES: tuple[tuple[str, str, str | None], ...] = (
    ("baking", r"bak(?:e|es|ing)|pastr(?:y|ies)|dough", r"bakes?"),
    ("cakes", r"(?:cheese|cup)?cakes?|muffins?|desserts?", None),
    ("whipping", r"whip(?:ping|ped)?|foam(?:ing)?|frothing|froth", r"whip|foam|froth"),
    ("sauce", r"sauces?", None),
    ("recipe", r"recipes?", None),
)
_OWN = r"(?:a|an|the|our|my|some)"
# A place or a recipient is not a use: "to the dessert kitchen", "for the pastry chef", "in the dessert fridge".
_PLACES = (
    r"kitchens?|sections?|stations?|teams?|chefs?|cooks?|departments?|dept|bar|rooms?|counters?|shop|staff|crew|"
    r"fridges?|freezers?|trolley|shelf|shelves|store|storage|area|door|unit|line"
)
_NEGATED = re.compile(r"\b(?:not|never|no)\s+(?:\w+\s+)?$|n['’]t\s+(?:\w+\s+)?$")


def purpose_pattern(words: str, verbs: str | None = None) -> re.Pattern[str]:
    """The words said as a purpose: after "for", "in" or "into" ("for the cakes", "for making a sauce"); after
    "to" only as a verb ("to whip") or behind "make" ("to make a sauce"), because "to the dessert kitchen" says
    where the goods go. Never when a place or a recipient follows."""
    after_to = rf"(?:make|making)\s+(?:{_OWN}\s+)?(?:{words})" + (rf"|(?:{verbs})" if verbs else "")
    said = rf"\b(?:for|in|into)\s+(?:(?:{_OWN}|making|make)\s+){{0,2}}(?:{words})|\bto\s+(?:{after_to})"
    return re.compile(rf"(?:{said})\b(?!\s+(?:{_PLACES})\b)")


def said_as_purpose(pattern: re.Pattern[str], text: str) -> list[tuple[int, str]]:
    """Where the text says the pattern's words as a purpose, and the buyer's own words there, casefolded. A
    negated purpose ("not for baking") is not one."""
    folded = text.casefold()
    return [(match.start(), " ".join(match.group().split())) for match in pattern.finditer(folded)
            if not _NEGATED.search(folded[:match.start()])]


_PATTERNS = tuple((use, purpose_pattern(words, verbs)) for use, words, verbs in _USES)
_USE_WORD = re.compile("|".join(words for _, words, _ in _USES))


def is_use_word(word: str) -> bool:
    """True for a word that names a use on its own: "desserts" of "for cakes and desserts"."""
    return _USE_WORD.fullmatch(word.casefold()) is not None


def spans_of(pattern: re.Pattern[str], text: str) -> list[tuple[int, int]]:
    """Where the casefolded text says the pattern's words as a purpose, negated or not."""
    return [match.span() for match in pattern.finditer(text.casefold())]


def purpose_spans(text: str) -> list[tuple[int, int]]:
    """Where the text names a use for which the formula matters."""
    return [span for _, pattern in _PATTERNS for span in spans_of(pattern, text)]

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


def formula_uses(text: str) -> tuple[FormulaUse, ...]:
    """Every use the text names as a purpose, in the order said."""
    found = [(start, use, said) for use, pattern in _PATTERNS for start, said in said_as_purpose(pattern, text)]
    return tuple(FormulaUse(use=use, said=said) for _, use, said in sorted(found))


def formula_use(text: str) -> FormulaUse | None:
    """The first use the text names as a purpose, or `None` when it names none."""
    return next(iter(formula_uses(text)), None)


def formula_matters(text: str) -> bool:
    """True when the buyer's words say what the product is for and the formula matters for that use."""
    return formula_use(text) is not None
