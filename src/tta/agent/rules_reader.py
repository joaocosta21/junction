"""The rule-based reader: common purchase sentences read by fixed rules when no model answers (task FALLBACK-1).

Scores on the 30% "working end-to-end demo": with Gemini out of reach and no recording of a sentence, the gateway
used to answer `supplier-unavailable`. These rules read the common shapes, say so (`ReadingSource.RULE_BASED`),
and read nothing else. Deterministic: no model, no network.
- Lines are split on "and" ("ja", "och"), commas, semicolons, sentence ends and new lines. A part with a quantity
  is a line; any other part speaks for the whole request ("no milk", "by Monday").
- A quantity is digits followed by a unit word of the text check (`tta.agent.textcheck`): "1,000", "1 000", "1000",
  "1.5", "1,5". Groups of three digits after a separator are thousands. A quantity is never guessed: a part that
  names a product with no digits and unit, or a line with a second number, is not read.
- The product is a key of the product-type table ("plant_drink" as "plant drink") or one of its name terms
  ("drink", "juoma"), in English, Finnish or Swedish where the table has them (`catalog/product_types.yaml`): the
  word itself, its plural, or the start of a word for a term of five letters or more. A type whose exclude term
  the line holds is not named ("sour milk" is not milk); one named inside a longer one is the longer ("beef
  chuck"). Two types left: not read. The one word right before the type narrows it ("oat drink"). A 6-digit
  product number names a product too.
- Claims, certificate labels, preferences and strictness are the words of `tta.agent.wording`; exclusions, confirmed
  data and product numbers those of the text check; days those of `tta.agent.days`. A claim or a label said in a
  line is that line's, said elsewhere every line's. Every exclusion is every line's, as the text check holds it.
  An exclusion with no strictness word stays without one: the parser asks for it, as it does for a model.
- Not read: a substitute ("a milk substitute"), an exclusion of something the allergen table lacks ("no sugar"),
  two days, a day before today, two preferences, both "strict" and "declared only".
The answer has the model's shape, so the parser's text check and conversion run on it unchanged: `RuleModel`
implements `AgentModel`. A text these rules cannot read is refused with `NotReadByRules`, which names what they
could not read.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from tta.agent.days import date_spans, named_dates
from tta.agent.textcheck import (
    CONFIRMED,
    DIGIT_RUN,
    SEPARATOR,
    WORD,
    all_thousands,
    exclusion_triggers,
    exclusions,
    id_tokens,
    unit_of,
)
from tta.agent.wording import SUBSTITUTE, Span, claims_in, labels_in, preferences_in, strictness_in
from tta.catalog import ProductType
from tta.contracts.common import JsonDict, Unit
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.request import MAX_QUANTITY, MAX_QUANTITY_DECIMALS, MAX_REQUEST_LINES

LONG_TERM = 5  # a term this long also names a word it starts ("juomaa", "drinks"); a shorter one only itself
MIN_NARROWING_LETTERS = 3
ONE_SEPARATOR_GROUPS = 2  # "1.5": the digits on either side of one separator
PRODUCT_ID = re.compile(r"\d{6}")  # a Valio product number has six digits (AIMO/FINDINGS.md section 2)
_BREAK = re.compile(r"[;\n!?]|,(?!\d)|(?<!\d),|\.(?=\s|$)|\b(?:and|ja|och)\b")
_NOT_A_TERM = frozenset({
    "a", "an", "the", "of", "some", "any", "our", "your", "my", "for", "by", "on", "to", "in", "at", "with", "need",
    "needs", "want", "please", "order", "send", "get", "buy", "deliver", "delivered", "also", "more", "extra",
    "next", "this", "that", "these", "those", "total", "about", "approx", "around", "only", "data", "stock",
})
_ALLOWED_AFTER_NO = frozenset({"later"})  # "no later than Monday" names a day, not an exclusion

NOTHING_TO_READ = "it gives no quantity in digits with a unit, such as 200 litres"
NO_QUANTITY_FOR = "{what} is named with no quantity in digits and unit"
NO_PRODUCT = "line {line} names no product type of the table and no 6-digit product number"
TWO_TYPES = "line {line} names more than one product type ({types})"
TWO_QUANTITIES = "line {line} gives more than one quantity; separate lines with and, a comma or a semicolon"
ANOTHER_NUMBER = "line {line} gives a number besides its quantity"
UNREADABLE_NUMBER = "line {line} gives a quantity that is not read as one number ({run})"
OUT_OF_RANGE = "line {line} asks for a quantity above zero, at most {most:,} with at most {places} decimals"
TOO_MANY_LINES = "it asks for more than {most} lines"
A_SUBSTITUTE = "it asks for a substitute, which only a model reads"
UNREAD_EXCLUSION = 'it excludes something the allergen table does not name ("{words}")'
TWO_DAYS = "it names more than one day"
PAST_DAY = "it names a day before today"
TWO_PREFERENCES = "it names more than one preference ({names})"
TWO_STRICTNESSES = "it says both strict and declared only"
RULES_CANNOT_READ = "The fixed rules cannot read this text: {why}."


class NotReadByRules(SupplierUnavailable):
    """The rules cannot read the text. `why` names what they could not read, for the sentence of the fallback."""

    def __init__(self, why: str) -> None:
        super().__init__(RULES_CANNOT_READ.format(why=why))
        self.why = why


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


@dataclass(frozen=True)
class _Text:
    """One buyer's text as the rules see it: casefolded, its words with where they start, its parts."""

    folded: str
    words: tuple[str, ...]
    starts: tuple[int, ...]
    parts: tuple[Span, ...]
    today: date

    @classmethod
    def of(cls, text: str, today: date) -> _Text:
        folded = text.casefold()
        found = list(WORD.finditer(folded))
        cuts = [0, *(position for match in _BREAK.finditer(folded) for position in match.span()), len(folded)]
        parts = tuple((start, end) for start, end in zip(cuts[::2], cuts[1::2], strict=True) if start < end)
        return cls(folded, tuple(match.group() for match in found), tuple(match.start() for match in found),
                   parts, today)

    def indices_in(self, span: Span) -> tuple[int, ...]:
        return tuple(index for index, start in enumerate(self.starts) if span[0] <= start < span[1])


@dataclass(frozen=True)
class _Part:
    """One part of the text: a line when it gives a quantity."""

    span: Span
    indices: tuple[int, ...]  # the indices of its words
    quantity: tuple[str, Unit] | None  # the digits and the unit
    product_ids: tuple[str, ...]
    other_numbers: tuple[str, ...]
    quantities: int


def _names(word: str, term: str) -> bool:
    if word in (term, f"{term}s", f"{term}es") or term == f"{word}s":
        return True
    return len(term) >= LONG_TERM and word.startswith(term)


def _phrase_at(words: Sequence[tuple[int, str]], phrase: tuple[str, ...]) -> frozenset[int]:
    """The indices of every place the phrase stands, its words next to each other."""
    found: set[int] = set()
    for at in range(len(words) - len(phrase) + 1):
        window = words[at:at + len(phrase)]
        next_to_each_other = window[-1][0] - window[0][0] == len(phrase) - 1
        if next_to_each_other and all(_names(word, term) for (_, word), term in zip(window, phrase, strict=True)):
            found.update(index for index, _ in window)
    return frozenset(found)


def _types_named(words: Sequence[tuple[int, str]], table: Sequence[TypeNames]) -> dict[str, frozenset[int]]:
    """Each type the words name, with the indices of the words that name it."""
    named: dict[str, frozenset[int]] = {}
    for entry in table:
        covered = frozenset().union(*(_phrase_at(words, phrase) for phrase in entry.names if phrase))
        if covered and not any(_phrase_at(words, phrase) for phrase in entry.excluded if phrase):
            named[entry.key] = covered
    return {key: covered for key, covered in named.items() if not any(covered < other for other in named.values())}


@dataclass(frozen=True)
class _Context:
    """What every line of one text shares."""

    seen: _Text
    excluding: frozenset[int]  # the words that say an exclusion
    used: frozenset[int]  # the words that already say something (`_used`)
    shared: tuple[Span, ...]  # the parts that speak for every line
    excluded: tuple[str, ...]  # the GS1 codes the text excludes
    strictness: str | None


class RuleReader:
    """Reads a text into the model's proposal by the rules above, or raises `NotReadByRules`."""

    def __init__(self, table: Sequence[TypeNames]) -> None:
        self._table = tuple(table)

    def proposal(self, text: str, today: date) -> JsonDict:
        seen = _Text.of(text, today)
        excluded, excluding = exclusions(seen.words)
        _refuse_what_is_not_read(seen, excluding)
        parts = [_part(seen, span) for span in seen.parts]
        for part in parts:
            if part.quantity is None:
                self._refuse_a_product_without_quantity(seen, part, excluding)
        lines = [part for part in parts if part.quantity is not None]
        if not lines:
            raise NotReadByRules(NOTHING_TO_READ)
        if len(lines) > MAX_REQUEST_LINES:
            raise NotReadByRules(TOO_MANY_LINES.format(most=MAX_REQUEST_LINES))
        context = _Context(
            seen=seen, excluding=excluding, used=_used(seen, excluding),
            shared=tuple(part.span for part in parts if part.quantity is None), excluded=tuple(sorted(excluded)),
            strictness=next((strictness.value for strictness, _ in strictness_in(seen.folded)), None),
        )
        return {**_request_facts(seen), "lines": [self._line(context, number, line)
                                                  for number, line in enumerate(lines, start=1)]}

    def _named(self, seen: _Text, part: _Part, excluding: frozenset[int]) -> dict[str, frozenset[int]]:
        """The types the part names, leaving out the words of an exclusion: "no milk" names no milk."""
        return _types_named([(index, seen.words[index]) for index in part.indices if index not in excluding],
                            self._table)

    def _refuse_a_product_without_quantity(self, seen: _Text, part: _Part, excluding: frozenset[int]) -> None:
        what = next(iter(sorted(self._named(seen, part, excluding))), None) or next(iter(part.product_ids), None)
        if what is not None:
            raise NotReadByRules(NO_QUANTITY_FOR.format(what=what.replace("_", " ")))

    def _line(self, context: _Context, number: int, part: _Part) -> JsonDict:
        if part.quantities > 1:
            raise NotReadByRules(TWO_QUANTITIES.format(line=number))
        if part.other_numbers:
            raise NotReadByRules(ANOTHER_NUMBER.format(line=number))
        named = self._named(context.seen, part, context.excluding)
        if len(named) > 1:
            raise NotReadByRules(TWO_TYPES.format(line=number, types=", ".join(sorted(named))))
        if not named and not part.product_ids:
            raise NotReadByRules(NO_PRODUCT.format(line=number))
        key, covered = next(iter(named.items()), (None, frozenset[int]()))
        digits, unit = part.quantity or ("", Unit.UNIT)
        folded = context.seen.folded
        return {
            "product_type": key, "product_ids": list(part.product_ids),
            "name_terms": _narrowing(context.seen, part, min(covered, default=None), context.used | covered),
            "required_claims": _said_for(claims_in(folded), part.span, context.shared),
            "quantity": str(_quantity(digits, number)), "unit": unit.value,
            "exclude_allergens": list(context.excluded), "allergen_strictness": context.strictness, "pack": None,
            "required_labels": _said_for(labels_in(folded), part.span, context.shared),
        }


def _within(position: int, span: Span) -> bool:
    return span[0] <= position < span[1]


def _said_for(found: Sequence[tuple[str, Span]], line: Span, shared: Sequence[Span]) -> list[str]:
    """The codes said in this line or in a part that speaks for every line, each once, in the order said."""
    codes = [code for code, (start, _) in found if _within(start, line) or any(_within(start, at) for at in shared)]
    return list(dict.fromkeys(codes))


def _refuse_what_is_not_read(seen: _Text, excluding: frozenset[int]) -> None:
    if SUBSTITUTE.search(seen.folded):
        raise NotReadByRules(A_SUBSTITUTE)
    claimed = {index for _, span in claims_in(seen.folded) for index in seen.indices_in(span)}
    for index in sorted(exclusion_triggers(seen.words) - excluding - claimed):
        following = seen.words[index + 1] if index + 1 < len(seen.words) else ""
        if following not in _ALLOWED_AFTER_NO:
            said = " ".join(seen.words[max(index - 1, 0):index + 2])
            raise NotReadByRules(UNREAD_EXCLUSION.format(words=said))
    days = named_dates(seen.folded, seen.today)
    if len(days) > 1:
        raise NotReadByRules(TWO_DAYS)
    if days and days[0] < seen.today:
        raise NotReadByRules(PAST_DAY)
    preferences = {preference for preference, _ in preferences_in(seen.folded)}
    if len(preferences) > 1:
        raise NotReadByRules(TWO_PREFERENCES.format(names=", ".join(sorted(preferences))))
    if len({strictness for strictness, _ in strictness_in(seen.folded)}) > 1:
        raise NotReadByRules(TWO_STRICTNESSES)


def _used(seen: _Text, excluding: frozenset[int]) -> frozenset[int]:
    """The words that already say something: none of them narrows a product type."""
    spans = [span for found in (claims_in, labels_in, preferences_in, strictness_in) for _, span in found(seen.folded)]
    spans += [match.span() for match in CONFIRMED.finditer(seen.folded)]
    said = {index for span in spans for index in seen.indices_in(span)}
    dated = {index for index, word in enumerate(seen.words) if named_dates(word, seen.today)}
    units = {index for index, word in enumerate(seen.words) if unit_of(word) is not None}
    return frozenset(said | dated | units | excluding)


def _request_facts(seen: _Text) -> JsonDict:
    days = named_dates(seen.folded, seen.today)
    preference = next((preference.value for preference, _ in preferences_in(seen.folded)), None)
    return {
        "needed_by": days[0].isoformat() if days else None,
        "require_confirmed": CONFIRMED.search(seen.folded) is not None,
        "prefer": preference,
    }


def _narrowing(seen: _Text, part: _Part, first: int | None, used: frozenset[int]) -> list[str]:
    """The one word right before the type's own words, when it says nothing else: "oat" of "oat drink"."""
    if first is None or first - 1 not in part.indices or first - 1 in used:
        return []
    word = seen.words[first - 1]
    return [] if len(word) < MIN_NARROWING_LETTERS or word in _NOT_A_TERM else [word]


def _part(seen: _Text, span: Span) -> _Part:
    """A part's numbers: the quantity (digits followed by a unit word), product numbers and any other number."""
    in_dates = date_spans(seen.folded)
    tokens = id_tokens(seen.folded)
    pairs: list[tuple[str, Unit]] = []
    product_ids: list[str] = []
    others: list[str] = []
    for match in DIGIT_RUN.finditer(seen.folded, span[0], span[1]):
        if any(start <= match.start() < end for start, end in in_dates):
            continue
        unit = _unit_after(seen, match.end(), span)
        if unit is not None:
            pairs.append((match.group(), unit))
        elif PRODUCT_ID.fullmatch(match.group()) and match.group() in tokens:
            product_ids.append(match.group())
        else:
            others.append(match.group())
    return _Part(span=span, indices=seen.indices_in(span), quantity=pairs[0] if pairs else None,
                 product_ids=tuple(dict.fromkeys(product_ids)), other_numbers=tuple(others), quantities=len(pairs))


def _unit_after(seen: _Text, end: int, span: Span) -> Unit | None:
    """The unit the word right after the digits names ("200 litres", "200l"), or `None`."""
    index = next((index for index, start in enumerate(seen.starts) if start >= end), None)
    if index is None or seen.starts[index] >= span[1] or seen.folded[end:seen.starts[index]].strip():
        return None
    return unit_of(seen.words[index])


def _quantity(digits: str, line: int) -> Decimal:
    """The number the digits give: thousands grouped by a separator and three digits, or one decimal separator."""
    groups, separators = SEPARATOR.split(digits), SEPARATOR.findall(digits)
    if not separators:
        value = Decimal(digits)
    elif all_thousands(groups):
        value = Decimal("".join(groups))
    elif separators[-1] in ".," and (len(groups) == ONE_SEPARATOR_GROUPS or all_thousands(groups[:-1])):
        value = Decimal(f"{''.join(groups[:-1])}.{groups[-1]}")
    else:
        raise NotReadByRules(UNREADABLE_NUMBER.format(line=line, run=digits))
    exponent = value.as_tuple().exponent
    places = -exponent if isinstance(exponent, int) and exponent < 0 else 0
    if not Decimal(0) < value <= MAX_QUANTITY or places > MAX_QUANTITY_DECIMALS:
        raise NotReadByRules(OUT_OF_RANGE.format(line=line, most=MAX_QUANTITY, places=MAX_QUANTITY_DECIMALS))
    return value
