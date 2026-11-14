"""A reader of dish sentences (task CK): "I want to make a chocolate cake for 20 people" becomes a dish of the
recipe table, its servings and an optional needed-by day.

Scores on the 20% "how precisely the agent matches what the buyer actually asked for". A pure function: no model,
no catalog, no clock. It is given the dish names of the recipe table and today's date, and nothing is guessed:
- a dish is one of the names given, as whole words (a plural "s" is allowed), the longest name first;
- servings are the number right after the dish ("for 20", "for twenty guests") or right before it
  ("20 servings of"): one whole number in digits, or a number word up to twenty, a ten up to ninety or
  "a hundred". Anything else ("2.5", "20-25", "about 20", "twenty-five") is asked about, never rounded;
- a number is never shared between dishes: "lasagne and oven pancake for 50" asks about the lasagne;
- a dish that is not among the names ("tiramisu for 10") is named as unknown, never matched to a near one;
- the day is read by the request reader's calendar rule (`tta.agent.days`); two days are asked about.
A sentence that names no dish and no "... for N" reads as nothing (`None`).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from tta.agent.days import day_spans, impossible_dates, named_dates
from tta.availability.wording import format_day

MAX_SERVINGS = 5000  # as `tta.contracts.menu.MAX_SERVINGS`
MAX_TEXT = 500
NUMBER_WORDS: Mapping[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}
# Words that may follow the number: who or what is counted. Any other word ends the number without a doubt too;
# these are listed so "for 20 people" and "for twenty guests" read alike.
COUNTED = frozenset({"people", "persons", "person", "guests", "guest", "servings", "serving", "portions", "portion",
                     "pax", "covers", "diners", "eaters", "customers", "kids", "children", "adults"})
SERVING_WORDS = r"(?:servings?|portions?)"
ASK_SERVINGS = 'How many servings of {dish}? Write, for example, "{dish} for 20".'
NOT_A_NUMBER = (
    '"{said}" is not read as a number of servings of {dish}. Write a whole number from 1 to {most:,} in digits, '
    'for example "{dish} for 20".'
)
NAMED_TWICE = "{dish} is named twice ({first} and {second} servings). Name a dish once, with all its servings."
SEVERAL_DAYS = "The sentence names {count} days ({days}). Which day is it needed by?"
NOT_A_DATE = '"{said}" is not a date. Which day is it needed by?'
IN_THE_PAST = "{day} is in the past. Which day is it needed by?"
# What stands before a dish in a sentence and is no part of its name, stripped when an unknown dish is quoted.
_LEAD_IN = re.compile(
    r"^(?:(?:i|we)(?:'d| would)? (?:want|need|like|plan|have)(?: to)?|please|can you|could you|let's|lets|"
    r"make|bake|cook|plan|prepare|order|get|do|to|a|an|the|some|me|us|and|then|also|with|plus)\b[\s,]*"
)
_FOR = re.compile(r"\bfor\s+")
_TOKEN = re.compile(r"[^\s,;!?]+")
_WHOLE = re.compile(r"\d+")
_NUMBER_LIKE = re.compile(r"\d")
_BEFORE_DISH = re.compile(r"(\S+)\s+" + SERVING_WORDS + r"\s+of\s+(?:(?:a|an|the)\s+)?$")
_UNKNOWN_WORDS = 4  # an unknown dish is quoted by at most this many words


@dataclass(frozen=True)
class DishRead:
    """One dish of the table that the sentence names. `servings` None: not said, or not read: see `problems`."""

    dish_id: str
    servings: int | None


@dataclass(frozen=True)
class DishSentence:
    """What a sentence says: its dishes in order, the dish names it gives that are not in the table, the day,
    and every question the sentence leaves open, as a sentence for the person who wrote it."""

    dishes: tuple[DishRead, ...]
    unknown: tuple[str, ...] = ()
    needed_by: date | None = None
    problems: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        """Every dish named is in the table and has its servings, and no question is open."""
        return bool(self.dishes) and not self.unknown and not self.problems


@dataclass(frozen=True)
class _Found:
    dish_id: str
    name: str  # the name as the table gives it, for the questions
    start: int
    end: int


@dataclass(frozen=True)
class _Number:
    value: int | None  # None: said, and not read as one whole number in range
    said: str


def _words(dish_id: str) -> str:
    return dish_id.replace("_", " ")


def _find_dishes(folded: str, names: Mapping[str, Sequence[str]]) -> list[_Found]:
    """Every dish name in the text as whole words, longest name first; a place is taken once."""
    by_length = sorted(
        ((name.casefold().strip(), dish_id) for dish_id, own in names.items() for name in own if name.strip()),
        key=lambda pair: (-len(pair[0]), pair[0]),
    )
    found: list[_Found] = []
    for name, dish_id in by_length:
        for match in re.finditer(r"(?<![^\W_])" + re.escape(name) + r"s?(?![^\W_])", folded):
            if not any(match.start() < each.end and each.start < match.end() for each in found):
                found.append(_Found(dish_id, _words(dish_id), match.start(), match.end()))
    return sorted(found, key=lambda each: each.start)


def _in_range(value: int) -> int | None:
    return value if 1 <= value <= MAX_SERVINGS else None


def _number(tokens: Sequence[str]) -> _Number | None:
    """The number the tokens start with. None: they start with no number at all."""
    if not tokens:
        return None
    first, rest = tokens[0], tokens[1:]
    after = rest[0] if rest else ""
    if first in ("a", "one") and after == "hundred":
        return _Number(NUMBER_WORDS["hundred"], f"{first} hundred") if _ends(rest[1:]) else _Number(
            None, " ".join(tokens[:3])
        )
    if first in ("about", "around", "roughly", "approximately", "some", "almost", "nearly", "over", "under") or (
        first == "a" and after in ("dozen", "couple", "few")
    ):
        said = " ".join(tokens[:2])
        return _Number(None, said) if _NUMBER_LIKE.search(after) or after in NUMBER_WORDS or first == "a" else None
    if _WHOLE.fullmatch(first):
        return _Number(_in_range(int(first)), first) if _ends(rest) else _Number(None, f"{first} {after}")
    if _NUMBER_LIKE.match(first):
        return _Number(None, first)  # 2.5, 1,000 (the comma is kept by the tokens), 20-25
    if first in NUMBER_WORDS:
        return _Number(NUMBER_WORDS[first], first) if _ends(rest) else _Number(None, f"{first} {after}")
    if first.split("-")[0] in NUMBER_WORDS:
        return _Number(None, first)  # twenty-five
    return None


def _ends(rest: Sequence[str]) -> bool:
    """The number is over: the next word is no number and no part of one."""
    return not rest or not (_NUMBER_LIKE.match(rest[0]) or rest[0].split("-")[0] in NUMBER_WORDS)


def _tokens(folded: str, start: int, end: int, days: Sequence[tuple[int, int]]) -> list[str]:
    """The words of `folded[start:end]` up to the first day named ("16 November"): a day's digits are no
    servings. A comma or dot inside a number stays ("1,000", "2.5"), so such a number is asked about."""
    kept = []
    for match in re.finditer(r"[^\s;!?]+", folded[start:end]):
        at = start + match.start()
        if any(day_start <= at < day_end for day_start, day_end in days):
            break  # the day ends what can be a number of servings
        kept.append(match.group().rstrip(",."))
    return kept


def _servings_after(folded: str, start: int, end: int, days: Sequence[tuple[int, int]]) -> _Number | None:
    """The number after the first "for" of `folded[start:end]`."""
    for match in _FOR.finditer(folded, start, end):
        number = _number(_tokens(folded, match.end(), end, days))
        if number is not None:
            return number
    return None


def _servings_before(folded: str, start: int, floor: int) -> _Number | None:
    """`20 servings of <dish>`: the number right before the dish."""
    match = _BEFORE_DISH.search(folded[floor:start])
    return None if match is None else _number([match.group(1).rstrip(",.")])


def _unknown(folded: str, found: Sequence[_Found], days: Sequence[tuple[int, int]]) -> tuple[str, ...]:
    """What stands before a "for <number>" and holds no dish of the table: a dish the table does not have."""
    unknown: list[str] = []
    edges = [0, *(each.end for each in found)]
    for match in _FOR.finditer(folded):
        if _number(_tokens(folded, match.end(), len(folded), days)) is None:
            continue
        floor = max(edge for edge in edges if edge <= match.start())
        if any(each.end == floor and not _FOR.search(folded, each.end, match.start()) for each in found):
            continue  # this "for" gives the servings of the dish before it
        previous = [other.end() for other in _FOR.finditer(folded, floor, match.start())]
        phrase = folded[max([floor, *previous]):match.start()]
        if previous:  # after an earlier "for 10": skip its number and what it counts
            phrase = re.sub(r"^\s*\S+(?:\s+(?:" + "|".join(sorted(COUNTED)) + r"))?", "", phrase)
        phrase = _stripped(phrase)
        if phrase:
            unknown.append(" ".join(phrase.split()[-_UNKNOWN_WORDS:]))
        edges.append(match.end())
    return tuple(dict.fromkeys(unknown))


def _stripped(phrase: str) -> str:
    phrase = phrase.strip(" ,.:;!?")
    while True:
        shorter = _LEAD_IN.sub("", phrase).strip(" ,.:;!?")
        if shorter == phrase:
            return phrase
        phrase = shorter


def _day(text: str, today: date) -> tuple[date | None, tuple[str, ...]]:
    impossible = impossible_dates(text, today)
    if impossible:
        return None, tuple(NOT_A_DATE.format(said=said) for said in impossible)
    days = named_dates(text, today)
    if len(days) > 1:
        return None, (SEVERAL_DAYS.format(count=len(days), days=" and ".join(format_day(day) for day in days)),)
    if days and days[0] < today:
        return None, (IN_THE_PAST.format(day=format_day(days[0])),)
    return (days[0] if days else None), ()


def _dish_problems(found: Sequence[_Found], numbers: Sequence[_Number | None]) -> list[str]:
    problems: list[str] = []
    seen: dict[str, _Number | None] = {}
    for each, number in zip(found, numbers, strict=True):
        if each.dish_id in seen:
            first, second = seen[each.dish_id], number
            problems.append(NAMED_TWICE.format(
                dish=each.name.capitalize(), first=first.said if first else "no", second=second.said if second
                else "no",
            ))
            continue
        seen[each.dish_id] = number
        if number is None:
            problems.append(ASK_SERVINGS.format(dish=each.name))
        elif number.value is None:
            problems.append(NOT_A_NUMBER.format(said=number.said, dish=each.name, most=MAX_SERVINGS))
    return problems


def read_dishes(text: str, names: Mapping[str, Sequence[str]], today: date) -> DishSentence | None:
    """What the sentence says about dishes, against `names` (dish id to the names it goes by). None when it names
    no dish of the table and gives no "<something> for <number>". Text beyond the first 500 characters is not
    read."""
    folded = " ".join(text[:MAX_TEXT].casefold().split())
    found = _find_dishes(folded, names)
    days = day_spans(folded, today)
    unknown = _unknown(folded, found, days) if found or _FOR.search(folded) else ()
    if not found and not unknown:
        return None
    numbers: list[_Number | None] = []
    for index, each in enumerate(found):
        floor = found[index - 1].end if index else 0
        ceiling = found[index + 1].start if index + 1 < len(found) else len(folded)
        numbers.append(_servings_before(folded, each.start, floor) or _servings_after(folded, each.end, ceiling, days))
    needed_by, day_problems = _day(folded, today)
    dishes = tuple(dict.fromkeys(
        DishRead(each.dish_id, number.value if number is not None else None)
        for each, number in zip(found, numbers, strict=True)
    ))
    first_of_each = {dish.dish_id: dish for dish in reversed(dishes)}
    return DishSentence(
        dishes=tuple(first_of_each[dish_id] for dish_id in dict.fromkeys(dish.dish_id for dish in dishes)),
        unknown=unknown, needed_by=needed_by, problems=(*_dish_problems(found, numbers), *day_problems),
    )
