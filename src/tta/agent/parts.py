"""A buyer's text cut into parts, and the numbers each part gives (task FALLBACK-1; replan A2b H3, M1).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for". A text is split on "and"
("ja", "och"), commas, semicolons, sentence ends and new lines. A part with a quantity (digits followed by a unit
word) is a line; any other part speaks for the whole request. Every number of a part is one of: its quantity, a
6-digit product number, a date, or another number, and another number is never dropped: the reader asks about it
wherever it stands ("Ward 4", "200 of them"). A digit inside a word is no number ("co2").
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date

from tta.agent.asking import Seen
from tta.agent.days import date_spans
from tta.agent.quantity import refuse_a_split_number, small_unit
from tta.agent.textcheck import DIGIT_RUN, SMALL_UNITS, WORD, id_tokens, unit_of
from tta.agent.wording import Span
from tta.contracts.common import Unit

PRODUCT_ID = re.compile(r"\d{6}")  # a Valio product number has six digits (AIMO/FINDINGS.md section 2)
_BREAK = re.compile(r"[;\n!?]|,(?!\d)|(?<!\d),|\.(?=\s|$)|\b(?:and|ja|och)\b")
NOT_A_TERM = frozenset({
    "a", "an", "the", "of", "some", "any", "our", "your", "my", "for", "by", "on", "to", "in", "at", "with", "need",
    "needs", "want", "please", "order", "send", "get", "buy", "deliver", "delivered", "also", "more", "extra",
    "next", "this", "that", "these", "those", "total", "about", "approx", "around", "only", "data", "stock",
})
# Words a number may follow without being part of it: "need 1 200 litres". After any other word a number joined
# by a space is asked about ("Ward 4 200 litres"; replan A2b H3).
_BEFORE_A_NUMBER = NOT_A_TERM | frozenset({
    "i", "we", "us", "me", "like", "require", "requires", "wants", "bring", "is", "are", "add", "another", "have",
})
_NUMBER_WORDS = frozenset({"product", "number", "no", "nr", "id", "item", "article", "tuote", "tuotenumero"})


@dataclass(frozen=True)
class Text:
    """One buyer's text as the rules see it: casefolded, its words with where they start, its parts."""

    folded: str
    words: tuple[str, ...]
    starts: tuple[int, ...]
    parts: tuple[Span, ...]
    today: date

    @classmethod
    def of(cls, text: str, today: date) -> Text:
        folded = text.casefold()
        found = list(WORD.finditer(folded))
        cuts = [0, *(position for match in _BREAK.finditer(folded) for position in match.span()), len(folded)]
        parts = tuple((start, end) for start, end in zip(cuts[::2], cuts[1::2], strict=True) if start < end)
        return cls(folded, tuple(match.group() for match in found), tuple(match.start() for match in found),
                   parts, today)

    def indices_in(self, span: Span) -> tuple[int, ...]:
        return tuple(index for index, start in enumerate(self.starts) if span[0] <= start < span[1])

    def asked(self, excluding: frozenset[int]) -> Seen:
        """The text as the checks of `tta.agent.asking` see it."""
        return Seen(self.folded, self.words, self.starts, excluding, self.today)


@dataclass(frozen=True)
class Part:
    """One part of the text: a line when it gives a quantity."""

    span: Span
    indices: tuple[int, ...]  # the indices of its words
    quantity: tuple[str, Unit] | None  # the digits and the unit
    unit_word: str | None  # the word that named the unit ("cases", "litres")
    product_ids: tuple[str, ...]
    other_numbers: tuple[str, ...]
    quantities: int


def part_of(seen: Text, span: Span) -> Part:
    """A part's numbers: the quantity (digits followed by a unit word), product numbers and any other number."""
    in_dates = date_spans(seen.folded)
    tokens = id_tokens(seen.folded)
    pairs: list[tuple[str, Unit, str]] = []
    product_ids: list[str] = []
    others: list[str] = []
    for match in DIGIT_RUN.finditer(seen.folded, span[0], span[1]):
        inside_a_word = match.start() > 0 and seen.folded[match.start() - 1].isalpha()  # the 2 of "co2"
        if inside_a_word or any(start <= match.start() < end for start, end in in_dates):
            continue
        word = _word_after(seen, match.end(), span)
        unit = unit_of(word) if word is not None else None
        if word in SMALL_UNITS:
            raise small_unit(match.group(), word)
        if unit is not None and word is not None:
            refuse_a_split_number(match.group(), _word_before(seen, match.start(), span), _BEFORE_A_NUMBER)
            pairs.append((match.group(), unit, word))
        elif PRODUCT_ID.fullmatch(match.group()) and match.group() in tokens:
            product_ids.append(match.group())
        else:
            others.append(match.group())
    first = pairs[0] if pairs else None
    return Part(
        span=span, indices=seen.indices_in(span), quantity=(first[0], first[1]) if first else None,
        unit_word=first[2] if first else None, product_ids=tuple(dict.fromkeys(product_ids)),
        other_numbers=tuple(others), quantities=len(pairs),
    )


def _word_after(seen: Text, end: int, span: Span) -> str | None:
    """The word right after the digits ("200 litres", "200l"), or `None` when something else stands between."""
    index = next((index for index, start in enumerate(seen.starts) if start >= end), None)
    if index is None or seen.starts[index] >= span[1] or seen.folded[end:seen.starts[index]].strip():
        return None
    return seen.words[index]


def _word_before(seen: Text, start: int, span: Span) -> str | None:
    """The word of this part right before the digits, with only spaces between ("ward" of "Ward 4 200")."""
    before = [index for index in seen.indices_in(span) if seen.starts[index] < start]
    if not before:
        return None
    word = seen.words[before[-1]]
    return None if seen.folded[seen.starts[before[-1]] + len(word):start].strip() else word


def with_lone_product_numbers(seen: Text, parts: Sequence[Part]) -> list[Part]:
    """"100 litres of oat drink, product 469512, by Monday": a part that only gives a product number names the
    product of the line right before it, when that line names none by number. Any other number-only part stays
    as it is, and is refused as a product with no quantity."""
    joined: list[Part] = []
    for part in parts:
        before = joined[-1] if joined else None
        only_a_number = (
            part.quantity is None and part.product_ids and not part.other_numbers
            and all(seen.words[index] in _NUMBER_WORDS for index in part.indices)
        )
        if only_a_number and before is not None and before.quantity is not None and not before.product_ids:
            joined[-1] = replace(before, product_ids=part.product_ids)
        else:
            joined.append(part)
    return joined
