"""Wordings the fixed rules ask about instead of reading (replan A2b C1, C3, C4, H1, L2; A5 #5).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for". The review of 14 Nov 2026
ran each of these offline and got an order the buyer did not ask for: "not lactose-free" read as lactose-free,
"must not contain gluten" read with no exclusion, "milk chocolate" read as milk, "within 3 days" read with no
date. Valio Aimo's answer the same day: when not sure, flag it and ask. Each check raises `NotReadByRules` with
what was not read and the question to put; none of them changes a reading.
- a claim, a label, a preference or a day with "not", "non", "never" or "n't" within two words before it; a claim
  or a label with "or" before it; a day with "after", "from" or "since" right before it, or "at the earliest"
  right after it (a day is read only as the day the goods are needed by); "does not matter";
- words that change how much is needed without giving the number: "the same again", "twice", "each", "per day";
- a deadline the calendar rule (`tta.agent.days`) does not know: "within", "week", "weekend", "days", "month";
- a word that names an allergen, or speaks of an allergy, outside an exclusion the rules read and outside the
  product's own name ("soy drink", "peanut butter");
- a word right after the product type that the rules do not know ("milk chocolate");
- a case, a box, a crate or a tray (how many packs it holds differs by product) unless the line names the product
  by its number, and a portion (Valio's data gives no portion size).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from tta.agent.days import date_spans, named_dates
from tta.agent.textcheck import ALLERGY_WORD, OUTER_PACK_WORDS, PORTION_WORDS, allergen_mentions
from tta.agent.unread import NotReadByRules
from tta.agent.wording import Span, claims_in, labels_in, preferences_in

WORDS_BEFORE = 2  # how far before a wording a negation is looked for
_NEGATORS = frozenset({"not", "non", "never", "inte", "ej"})
_EITHER = frozenset({"or", "tai", "eller"})
_NOT_BY_A_DAY = frozenset({"after", "from", "since"})
_AT_THE_EARLIEST = re.compile(r"^\W*at the earliest\b")
_NO_MATTER = re.compile(
    r"(?:\b[^\W\d_]+\s+){0,2}(?:\b(?:does|do|is|are)\s+not|\b(?:doesn|don|isn|aren)\W?t|\bnot)\s+"
    r"(?:matter|important|needed|required|necessary)\b|\b(?:don\W?t|do not) care\b"
)
_DEADLINE = re.compile(
    r"\bwithin\b|\bweeks?\b|\bweekends?\b|\bdays\b|\bfortnight\b|\bmonths?\b|\bend of\b|\bhours?\b|\bago\b"
    r"|\bviik\w*|\bveck\w*|\bkuukau\w*"
)

_CHANGED_AMOUNT = re.compile(
    r"\bsame again\b|\bthe same\b|\bagain\b|\btwice\b|\beach\b|\bper\b|\bevery\b|\bdaily\b"
    r"|\bweekly\b|\btimes\b"
)

NEGATED = 'it says "{said}", and the rules cannot tell whether "{what}" is wanted or not'
ASK_WANTED = 'Is "{what}" wanted, yes or no? Write only what is wanted; leave out what is not.'
EITHER_OR = 'it says "{said}", and the rules cannot ask for one or the other'
ASK_WHICH = "Which is required: both, or which one? Write only what every product must carry."
NOT_BY_THAT_DAY = 'it says "{said}", and the rules read a day only as the day the goods are needed by'
ASK_BY_WHICH_DAY = 'By which day are the goods needed at the latest? Write it as "by Monday" or "by 20.11.".'
NO_MATTER = 'it says "{said}", and the rules read only what is wanted'
ASK_WHAT_MATTERS = "What should decide between products: price, earliest delivery, reliability or carbon footprint?"
CHANGED_AMOUNT = 'it says "{said}", which changes how much is needed in a way the rules do not read'
ASK_THE_TOTAL = "What is the whole quantity for this one delivery? Write it as one number with its unit, per product."
UNREAD_DEADLINE = 'it gives a deadline the rules do not read ("{said}")'
ASK_A_DAY = 'By which day are the goods needed? Name a weekday or a date, for example "by Monday" or "by 20.11.".'
ALLERGEN_LEFT_UNSAID = (
    'it names "{word}" in a wording the rules do not read, and an allergen is never left out by a guess'
)
ASK_EXCLUDE = 'Must products with {word} be left out? Then write "no {word}".'
ASK_WHICH_ALLERGEN = 'Which allergen must be left out? Write it as "no milk", "no gluten" or "no nuts".'
UNKNOWN_PRODUCT_WORD = 'line {line} says "{said}", and the rules know "{known}" and not "{word}"'
ASK_WHICH_PRODUCT = (
    'Is "{said}" the product? The rules would read plain {known}. Name a product type the gateway knows, or give '
    "the 6-digit product number."
)
OUTER_PACK = "line {line} asks for {said}, and how much a {word} holds differs by product"
PORTION = "line {line} asks for {said}, and how much a portion is differs by product: Valio's data gives no size"
ASK_AMOUNT = "How many litres, kilograms or single packs is that? Write the quantity in one of those units."
ASK_AMOUNT_OR_NUMBER = (
    "How many litres, kilograms or single packs is that? Write the quantity in one of those units, or name the "
    "product by its 6-digit number."
)


@dataclass(frozen=True)
class Seen:
    """The casefolded text, its words and where each starts, and the words that say an exclusion the rules read."""

    folded: str
    words: Sequence[str]
    starts: Sequence[int]
    excluding: frozenset[int]
    today: date

    def first_word_at(self, position: int) -> int:
        return next((index for index, start in enumerate(self.starts) if start >= position), len(self.words))

    def before(self, position: int) -> list[int]:
        """The indices of the words right before this position that say no exclusion."""
        first = self.first_word_at(position)
        return [index for index in range(max(first - WORDS_BEFORE, 0), first) if index not in self.excluding]

    def said(self, index: int, end: int) -> str:
        return self.folded[self.starts[index]:end]


def _day_spans(seen: Seen) -> list[Span]:
    words = [(start, start + len(word)) for word, start in zip(seen.words, seen.starts, strict=True)
             if named_dates(word, seen.today)]
    return [*words, *date_spans(seen.folded)]


def _negator(seen: Seen, span: Span) -> int | None:
    """The index of a "not", "non", "never" or "n't" within two words before the wording."""
    for index in seen.before(span[0]):
        word = seen.words[index]
        if word in _NEGATORS or (word == "t" and index > 0 and seen.words[index - 1].endswith("n")):
            return index - 1 if word == "t" else index
    return None


def refuse_negations(seen: Seen) -> None:
    """A claim, a label, a preference or a day said with a negation, an "or", or as "not before"."""
    wanted = [span for found in (claims_in, labels_in, preferences_in) for _, span in found(seen.folded)]
    for span in sorted(wanted):
        what = seen.folded[span[0]:span[1]]
        negator = _negator(seen, span)
        if negator is not None:
            raise NotReadByRules(NEGATED.format(said=seen.said(negator, span[1]), what=what),
                                 ASK_WANTED.format(what=what))
    for span in sorted(span for found in (claims_in, labels_in) for _, span in found(seen.folded)):
        either = next((index for index in seen.before(span[0]) if seen.words[index] in _EITHER), None)
        if either is not None:
            raise NotReadByRules(EITHER_OR.format(said=seen.said(either, span[1])), ASK_WHICH)
    for span in sorted(_day_spans(seen)):
        _refuse_a_day_that_is_no_deadline(seen, span)
    unimportant = _NO_MATTER.search(seen.folded)
    if unimportant is not None:
        raise NotReadByRules(NO_MATTER.format(said=unimportant.group().strip()), ASK_WHAT_MATTERS)


def _refuse_a_day_that_is_no_deadline(seen: Seen, span: Span) -> None:
    negator = _negator(seen, span)
    first = seen.first_word_at(span[0])
    if negator is None and first > 0 and seen.words[first - 1] in _NOT_BY_A_DAY:
        negator = first - 1
    if negator is not None:
        raise NotReadByRules(NOT_BY_THAT_DAY.format(said=seen.said(negator, span[1])), ASK_BY_WHICH_DAY)
    after = _AT_THE_EARLIEST.match(seen.folded[span[1]:])
    if after is not None:
        said = seen.folded[span[0]:span[1] + after.end()]
        raise NotReadByRules(NOT_BY_THAT_DAY.format(said=said), ASK_BY_WHICH_DAY)


def refuse_an_unread_deadline(seen: Seen) -> None:
    """"Within 3 days", "by the end of next week": the calendar rule knows a weekday and a date, nothing else."""
    found = _DEADLINE.search(seen.folded)
    if found is not None:
        raise NotReadByRules(UNREAD_DEADLINE.format(said=found.group()), ASK_A_DAY)


def refuse_a_changed_amount(seen: Seen) -> None:
    """"And the same again for the canteen", "twice", "per day": the quantity asked for is not the number given."""
    found = _CHANGED_AMOUNT.search(seen.folded)
    if found is not None:
        raise NotReadByRules(CHANGED_AMOUNT.format(said=found.group()), ASK_THE_TOTAL)


def refuse_an_allergen_left_unsaid(seen: Seen, product_words: frozenset[int]) -> None:
    """A word of the allergen table, or "allergy" and the like, that is neither part of an exclusion the rules
    read nor one of the words that name a line's product."""
    mentions = allergen_mentions(seen.words)
    for index in sorted(set(mentions) - seen.excluding - product_words):
        word = mentions[index]
        ask = ASK_WHICH_ALLERGEN if ALLERGY_WORD.match(word) else ASK_EXCLUDE.format(word=word)
        raise NotReadByRules(ALLERGEN_LEFT_UNSAID.format(word=word), ask)


def unknown_product_word(line: int, known: str, word: str) -> NotReadByRules:
    """The refusal for "milk chocolate": the rules know the type word and not the word after it."""
    said = f"{known} {word}"
    return NotReadByRules(UNKNOWN_PRODUCT_WORD.format(line=line, said=said, known=known, word=word),
                          ASK_WHICH_PRODUCT.format(said=said, known=known))


def refuse_a_pack_of_unknown_size(line: int, digits: str, unit_word: str | None, *, numbered: bool) -> None:
    """A case, a box, a crate or a tray of a product not named by its number, and a portion of anything."""
    said = f"{digits} {unit_word}"
    if unit_word in PORTION_WORDS:
        raise NotReadByRules(PORTION.format(line=line, said=said), ASK_AMOUNT)
    if unit_word in OUTER_PACK_WORDS and not numbered:
        singular = unit_word.removesuffix("es" if unit_word.endswith("xes") else "s")
        raise NotReadByRules(OUTER_PACK.format(line=line, said=said, word=singular), ASK_AMOUNT_OR_NUMBER)
