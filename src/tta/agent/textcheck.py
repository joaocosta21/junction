"""What the buyer's text says, read without a model: the facts the model's reading is held to (task FIX-9).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" and the 20% "the model
decides nothing": the parser takes a number, a unit, a day, an exclusion or a product number from the model only
when the text gives it too. The tables below are short and ours; a phrase they do not know never makes a reading
pass, it can only make the parser refuse one or leave a field to the model:
- numbers: "1,000", "1 000", "1000", "1.5", "1,5", and number words such as "a thousand" or "twenty-five";
- unit words in English, Finnish and Swedish, for litres, kilograms and sales units;
- exclusions: "no X", "without X", "free from X", "X-free", "allergic to X", "X allergy"; in Finnish "ei X",
  "ilman X", "X-ton", "X-vapaa"; in Swedish "utan X", "ingen X", "fri från X", "X-fri" (task T18).
  "Lactose-free" ("laktoositon", "laktosfri") is a nutritional claim, never an allergen exclusion
  (AIMO/docs/SCHEMA-AND-CODES.md section 2.4), so lactose is not in the table;
- confirmed data: the word "confirmed", "verified", "vahvistettu", "varmistettu" or "bekräftad";
- product numbers: whole tokens of the text, never a piece of a number such as the "1" of "1,000".
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from tta.agent.days import named_dates
from tta.contracts.common import Unit

THOUSANDS_GROUP = 3  # digits in a group after a thousands separator
HUNDRED, THOUSAND, DOZEN = 100, 1000, 12

_SPACES = "   "  # a space, a no-break space, a narrow no-break space: "1 000"
_DIGIT_RUN = re.compile(rf"\d+(?:[.,{_SPACES}]\d+)*")
_SEPARATOR = re.compile(rf"[.,{_SPACES}]")
_WORD = re.compile(r"[^\W\d_]+")
_ID_TOKEN = re.compile(r"[^\s;:/()\[\]{}#\"'!?]+")
_NUMBER_LIKE = re.compile(r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+[.,]\d{1,2}")  # 1,000 · 1.000,5 · 1,5

_UNIT_WORDS: Mapping[Unit, frozenset[str]] = {
    Unit.L: frozenset({"l", "lt", "ltr", "ltrs", "litre", "litres", "liter", "liters", "litra", "litraa",
                       "litran", "litroja", "litrat", "litern"}),
    Unit.KG: frozenset({"kg", "kgs", "kilo", "kilos", "kilogram", "kilograms", "kilogramme", "kilogrammes",
                        "kiloa", "kilon", "kiloja", "kilogrammaa"}),
    Unit.UNIT: frozenset({
        "unit", "units", "piece", "pieces", "pc", "pcs", "pack", "packs", "package", "packages", "packet",
        "packets", "carton", "cartons", "case", "cases", "box", "boxes", "bottle", "bottles", "can", "cans",
        "tin", "tins", "jar", "jars", "bag", "bags", "tray", "trays", "crate", "crates", "bucket", "buckets",
        "tub", "tubs", "sack", "sacks", "portion", "portions", "kpl", "pkt", "kappale", "kappaletta",
        "pakkaus", "pakkausta", "pakkauksia", "laatikko", "laatikkoa", "pullo", "pulloa", "purkki", "purkkia",
        "pussi", "pussia", "rasia", "rasiaa", "tölkki", "tölkkiä", "kartonki", "kartonkia", "säkki", "säkkiä",
        "ämpäri", "ämpäriä", "annos", "annosta", "styck", "stycken", "förpackning", "förpackningar", "flaska",
        "flaskor", "burk", "burkar", "påse", "påsar", "låda", "lådor", "kartong", "kartonger",
    }),
}

_SMALL_NUMBERS = {
    word: value for value, word in enumerate((
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
        "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
    ))
} | {word: value * 10 for value, word in enumerate(
    ("twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"), start=2
)}
_SCALES = {"hundred": HUNDRED, "thousand": THOUSAND, "dozen": DOZEN}
_ONE_OF_A_SCALE = frozenset({"a", "an"})  # "a thousand"
_NUMBER_JOINER = "and"  # "two hundred and fifty"

# The allergen a word or phrase names (GS1 codes of `tta.allergens`), in English, Finnish and Swedish. Phrases are
# matched longest first.
_ALLERGEN_WORDS: Mapping[tuple[str, ...], str] = {
    **{(word,): "AM" for word in ("milk", "dairy", "maito", "maitoa", "maitotuotteita", "maitotuotteet", "mjölk",
                                  "mjölkprodukter")},
    **{(word,): "AW" for word in ("gluten", "gluteeni", "gluteenia")},
    **{(word,): "UW" for word in ("wheat", "vehnä", "vehnää", "vete")},
    **{(word,): "AE" for word in ("egg", "eggs", "muna", "munaa", "kananmuna", "kananmunaa", "ägg")},
    **{(word,): "AN" for word in ("nut", "nuts", "pähkinä", "pähkinää", "pähkinöitä", "nöt", "nötter")},
    ("tree", "nut"): "AN", ("tree", "nuts"): "AN",
    **{(word,): "AP" for word in ("peanut", "peanuts", "maapähkinä", "maapähkinää", "maapähkinöitä", "jordnöt",
                                  "jordnötter")},
    **{(word,): "AY" for word in ("soy", "soya", "soybean", "soybeans", "soija", "soijaa", "soja")},
    **{(word,): "AS" for word in ("sesame", "seesami", "seesamia", "sesam")},
    **{(word,): "AF" for word in ("fish", "kala", "kalaa", "fisk")},
    **{(word,): "AC" for word in ("crustacean", "crustaceans", "äyriäinen", "äyriäisiä")},
    **{(word,): "UN" for word in ("shellfish", "skaldjur")},
    **{(word,): "UM" for word in ("mollusc", "molluscs", "mollusk", "mollusks", "nilviäinen", "nilviäisiä",
                                  "blötdjur")},
    **{(word,): "BC" for word in ("celery", "selleri", "selleriä")},
    **{(word,): "BM" for word in ("mustard", "sinappi", "sinappia", "senap")},
    **{(word,): "NL" for word in ("lupin", "lupine", "lupiini", "lupiinia")},
    **{(word,): "AU" for word in ("sulphite", "sulphites", "sulfite", "sulfites", "sulfiitti", "sulfiitteja",
                                  "sulfit")},
    **{(word,): "SA" for word in ("almond", "almonds", "manteli", "mantelia", "manteleita", "mandel", "mandlar")},
    **{(word,): "SH" for word in ("hazelnut", "hazelnuts", "hasselpähkinä", "hasselpähkinöitä", "hasselnöt",
                                  "hasselnötter")},
    **{(word,): "SW" for word in ("walnut", "walnuts", "saksanpähkinä", "saksanpähkinöitä", "valnöt", "valnötter")},
    **{(word,): "SC" for word in ("cashew", "cashews", "cashewpähkinä", "cashewpähkinöitä", "cashewnötter")},
    **{(word,): "ST" for word in ("pistachio", "pistachios")},
    **{(word,): "GB" for word in ("barley", "ohra", "ohraa")},
    **{(word,): "NR" for word in ("rye", "ruis", "ruista", "råg")},
}
_LONGEST_PHRASE = max(len(phrase) for phrase in _ALLERGEN_WORDS)
_BEFORE = (("no",), ("without",), ("free", "from"), ("free", "of"), ("allergic", "to"), ("allergy", "to"),
           ("excluding",), ("exclude",), ("avoid",), ("ilman",), ("ei",), ("utan",), ("ingen",), ("inga",),
           ("fri", "från"))
_AFTER = (("free",), ("allergy",), ("allergies",), ("vapaa",), ("fri",), ("fritt",), ("fria",))
_FREE = frozenset({"free", "fri"})
_NOT_AFTER_FREE = frozenset({"from", "of", "från"})  # "milk free from additives" is about the additives
_FILLERS = frozenset({"traces", "trace", "of", "any", "added", "the", "a"})
_LIST_JOINERS = frozenset({"and", "or", "nor", "ja", "tai", "eikä", "och", "eller"})
# One-word exclusions: Finnish "-ton/-tön" adjectives ("maidoton", milk-free; "gluteenittomia", gluten-free ones)
# and "-vapaa" ("gluteenivapaa"); Swedish "-fri" ("mjölkfri", "nötfri"). Each pattern is anchored at the start of
# the word, so "maapähkinätön" is peanut-free and not nut-free.
_FREE_OF_WORDS = (
    (re.compile(r"^(maapähkinä)(ton|tön|tto|ttö|vapa)"), "AP"),
    (re.compile(r"^(maido)(ton|tto)|^maitovapa"), "AM"),
    (re.compile(r"^(gluteeni)(ton|tto|vapa)"), "AW"),
    (re.compile(r"^(vehnä)(tön|ttö|vapa)"), "UW"),
    (re.compile(r"^(pähkinä)(tön|ttö|vapa)"), "AN"),
    (re.compile(r"^(kananmuna|muna)(ton|tto|vapa)"), "AE"),
    (re.compile(r"^(soija)(ton|tto|vapa)"), "AY"),
    (re.compile(r"^(seesami)(ton|tto|vapa)"), "AS"),
    (re.compile(r"^(kala)(ton|tto|vapa)"), "AF"),
    (re.compile(r"^(manteli)(ton|tto)"), "SA"),
    (re.compile(r"^(selleri)(tön|ttö)"), "BC"),
    (re.compile(r"^(sinapi)(ton|tto)"), "BM"),
    (re.compile(r"^(äyriäise)(tön|ttö)"), "AC"),
    (re.compile(r"^mjölkfri"), "AM"),
    (re.compile(r"^glutenfri"), "AW"),
    (re.compile(r"^jordnöts?fri"), "AP"),
    (re.compile(r"^nött?fri"), "AN"),
    (re.compile(r"^äggfri"), "AE"),
    (re.compile(r"^sojafri"), "AY"),
    (re.compile(r"^sesamfri"), "AS"),
    (re.compile(r"^fiskfri"), "AF"),
    (re.compile(r"^vetefri"), "UW"),
)
_CONFIRMED = re.compile(r"\b(confirmed|verified)\b|\bvahvistet|\bvarmistet|\bbekräftad", re.IGNORECASE)


# --- numbers ----------------------------------------------------------------------------------------------


def _all_thousands(groups: Sequence[str]) -> bool:
    return len(groups[0]) <= THOUSANDS_GROUP and all(len(group) == THOUSANDS_GROUP for group in groups[1:])


def _readings_of_run(run: str) -> set[Decimal]:
    """A run of digits and separators read every way it can be: "1,000" is 1000 or, in Finnish, 1.000."""
    groups, separators = _SEPARATOR.split(run), _SEPARATOR.findall(run)
    if not separators:
        return {Decimal(run)}
    readings = set()
    if _all_thousands(groups):  # every separator groups thousands: 1,000 · 1 000 · 1.000.000
        readings.add(Decimal("".join(groups)))
    if separators[-1] in ".," and (len(groups) == 2 or _all_thousands(groups[:-1])):  # the last one is decimal
        readings.add(Decimal(f"{''.join(groups[:-1])}.{groups[-1]}"))
    for part in re.split(f"[{_SPACES}]", run) if any(sep in _SPACES for sep in separators) else ():
        readings |= _readings_of_run(part)  # "2 500" may also be two numbers
    return readings


def _number_words(words: Sequence[str]) -> list[Decimal]:
    """The value of every run of number words: "two hundred and fifty" is 250, "a thousand" 1000."""
    values: list[Decimal] = []
    total = current = 0
    started = False
    for index, word in enumerate(words):
        following = words[index + 1] if index + 1 < len(words) else ""
        if word in _SMALL_NUMBERS or word in _SCALES:
            total, current = _add_number_word(word, total, current)
            started = True
            continue
        if (word in _ONE_OF_A_SCALE and following in _SCALES and not started) or (
            word == _NUMBER_JOINER and started and following in _SMALL_NUMBERS
        ):
            continue  # "a thousand": the scale gives the 1; "two hundred and fifty"
        if started:
            values.append(Decimal(total + current))
        total = current = 0
        started = False
    return [*values, Decimal(total + current)] if started else values


def _add_number_word(word: str, total: int, current: int) -> tuple[int, int]:
    if word in _SMALL_NUMBERS:
        return total, current + _SMALL_NUMBERS[word]
    if word == "thousand":
        return total + (current or 1) * THOUSAND, 0
    return total, (current or 1) * _SCALES[word]


def _numbers(text: str, words: Sequence[str]) -> frozenset[Decimal]:
    found = {value for run in _DIGIT_RUN.findall(text) for value in _readings_of_run(run)}
    return frozenset(found | set(_number_words(words)))


# --- units, exclusions, product numbers -------------------------------------------------------------------


def _units(words: Sequence[str]) -> frozenset[Unit]:
    return frozenset(unit for unit, names in _UNIT_WORDS.items() if names.intersection(words))


def _phrase_at(words: Sequence[str], start: int) -> tuple[str, int] | None:
    """The allergen named at `start` and the number of words that name it, longest phrase first."""
    for length in range(_LONGEST_PHRASE, 0, -1):
        code = _ALLERGEN_WORDS.get(tuple(words[start:start + length]))
        if code is not None:
            return code, length
    return None


def _listed_after(words: Sequence[str], start: int) -> list[str]:
    """The allergens listed from `start`: "traces of milk, eggs or nuts" gives milk, eggs and nuts."""
    codes, index = [], start
    while index < len(words) and words[index] in _FILLERS:
        index += 1
    while index < len(words):
        named = _phrase_at(words, index)
        if named is None:
            break
        codes.append(named[0])
        index += named[1]
        while index < len(words) and words[index] in _LIST_JOINERS:
            index += 1
    return codes


def _named_before_free(words: Sequence[str], after: int) -> bool:
    """True for "milk-free", "gluten free", "nut allergy"; not for "milk free from additives"."""
    follows = words[after:after + 2]
    if not follows or (follows[0],) not in _AFTER:
        return False
    return not (follows[0] in _FREE and follows[1:] and follows[1] in _NOT_AFTER_FREE)


def _excluded(words: Sequence[str]) -> frozenset[str]:
    codes: set[str] = set()
    for index, word in enumerate(words):
        for trigger in _BEFORE:
            if tuple(words[index:index + len(trigger)]) == trigger:
                codes.update(_listed_after(words, index + len(trigger)))
        named = _phrase_at(words, index)
        if named is not None and _named_before_free(words, index + named[1]):
            codes.add(named[0])
        codes.update(code for pattern, code in _FREE_OF_WORDS if pattern.match(word))
    return frozenset(codes)


def _id_tokens(text: str) -> frozenset[str]:
    """Whole tokens: "464013," and "#464013" give 464013; "1,000" is a number and gives no "1"."""
    tokens: set[str] = set()
    for raw in _ID_TOKEN.findall(text):
        token = raw.strip(",.")
        if _NUMBER_LIKE.fullmatch(token):
            continue
        tokens.update(part for part in re.split(r"[,.]", token) if part)
    return frozenset(tokens)


@dataclass(frozen=True)
class TextFacts:
    """What one buyer's text says, by the rules above."""

    numbers: frozenset[Decimal]
    units: frozenset[Unit]
    excluded: frozenset[str]  # GS1 codes of the allergens the text excludes
    asks_for_confirmed: bool
    id_tokens: frozenset[str]
    dates: tuple[date, ...]  # by the parser's calendar rule (`tta.agent.days`)

    @classmethod
    def of(cls, text: str, today: date) -> TextFacts:
        words = _WORD.findall(text.casefold())
        return cls(
            numbers=_numbers(text, words), units=_units(words), excluded=_excluded(words),
            asks_for_confirmed=_CONFIRMED.search(text) is not None, id_tokens=_id_tokens(text),
            dates=named_dates(text, today),
        )
