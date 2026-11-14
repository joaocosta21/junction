"""How a buyer's words name a product type of the table (task FALLBACK-1; replan A2b C3).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for". A type is named by its key
("plant_drink" as "plant drink") or one of its name terms, in English, Finnish or Swedish where the table has them
(`catalog/product_types.yaml`): the word itself, its plural, or, for a term of five letters or more, the term with
an ending ("juomaa", "drinks"). A longer word is another product and names nothing: "buttermilk" is not butter,
"cheesecake" not cheese, "breadcrumbs" not bread (each was read as the shorter type before 14 Nov 2026). A type
whose exclude term the words hold is not named ("sour milk" is not milk); one named inside a longer one is the
longer ("beef chuck", "coffee milk").
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tta.agent.textcheck import WORD
from tta.catalog import ProductType

LONG_TERM = 5  # a term this long also names itself with an ending ("juomaa", "drinks"); a shorter one only itself
# The endings a long term may carry: English plurals, Finnish cases and plurals, Swedish definite and plural forms.
# A longer word is another product ("buttermilk", "cheesecake", "breadcrumbs"; replan A2b C3).
_ENDINGS = frozenset({
    "s", "es", "a", "ä", "aa", "ää", "n", "t", "ta", "tä", "ja", "jä", "ssa", "ssä", "sta", "stä", "lla", "llä",
    "lta", "ltä", "lle", "ksi", "na", "nä", "en", "et", "ar", "or",
})


@dataclass(frozen=True)
class TypeNames:
    """How a buyer's words name one product type: its key and name terms, and the terms that rule it out."""

    key: str
    names: tuple[tuple[str, ...], ...]
    excluded: tuple[tuple[str, ...], ...]


def _phrase(term: str) -> tuple[str, ...]:
    return tuple(WORD.findall(term.casefold()))


def type_names(product_types: Mapping[str, ProductType], keys: Sequence[str]) -> tuple[TypeNames, ...]:
    """The words of the table's types for these keys; a key the table does not hold has none."""
    return tuple(
        TypeNames(
            key=key,
            names=(_phrase(key.replace("_", " ")), *(_phrase(term) for term in entry.name_terms)),
            excluded=tuple(_phrase(term) for term in entry.exclude_terms),
        )
        for key in keys
        if (entry := product_types.get(key)) is not None
    )


def _names(word: str, term: str) -> bool:
    if word in (term, f"{term}s", f"{term}es") or term == f"{word}s":
        return True
    return len(term) >= LONG_TERM and word.startswith(term) and word[len(term):] in _ENDINGS


def _phrase_at(words: Sequence[tuple[int, str]], phrase: tuple[str, ...]) -> frozenset[int]:
    """The indices of every place the phrase stands, its words next to each other."""
    found: set[int] = set()
    for at in range(len(words) - len(phrase) + 1):
        window = words[at:at + len(phrase)]
        next_to_each_other = window[-1][0] - window[0][0] == len(phrase) - 1
        if next_to_each_other and all(_names(word, term) for (_, word), term in zip(window, phrase, strict=True)):
            found.update(index for index, _ in window)
    return frozenset(found)


def types_named(words: Sequence[tuple[int, str]], table: Sequence[TypeNames]) -> dict[str, frozenset[int]]:
    """Each type the words name, with the indices of the words that name it."""
    named: dict[str, frozenset[int]] = {}
    for entry in table:
        covered = frozenset().union(*(_phrase_at(words, phrase) for phrase in entry.names if phrase))
        if covered and not any(_phrase_at(words, phrase) for phrase in entry.excluded if phrase):
            named[entry.key] = covered
    return {key: covered for key, covered in named.items() if not any(covered < other for other in named.values())}
