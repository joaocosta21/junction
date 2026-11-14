"""What a product's own ingredient list names: the allergens in it and its "may contain" phrases (SPEC section 6).

The list is `Product.key_ingredients`, in English or else in Finnish. EU labelling emphasises an allergen in
the list; in the catalog text the emphasis is capitals ("Water, ALMOND (2.5%)"), and many lists also use the
plain word, so a word is found in any case.

How the text is read (the choices are listed in the FIX-12a hand-back):
- English words count only as whole words: "coconut" is not "nut", "buckwheat" is not "wheat", "peanuts"
  is not "nuts". A word with a GS1 code of its own wins over a shorter one ("pine nuts" is PN, not AN).
- Finnish words count at the start of a word, because Finnish joins words ("VEHNÄjauho", wheat flour).
- A free-from wording is not a mention: "gluten-free", "free from milk and soya", "does not contain milk,
  gluten or wheat", "without eggs", the Finnish "-ton"/"-tön" ("gluteeniton") and "ei sisällä".
- A mention inside a "may contain" phrase is quoted with its phrase, up to the end of the sentence.
- A few words that start like an allergen and name something else are left out: plant "milks" ("coconut
  milk"), milk-cap mushrooms, and the Finnish words for lactic acid, Kalamata olives and fishing.

The text is data from the product file: it is matched, quoted short, and never interpreted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

# GS1 code -> English words, whole words in any case (AIMO/docs/SCHEMA-AND-CODES.md for the codes).
_ENGLISH: dict[str, tuple[str, ...]] = {
    "AM": ("milk",),
    "SA": ("almond", "almonds"),
    "SH": ("hazelnut", "hazelnuts"),
    "SW": ("walnut", "walnuts"),
    "SC": ("cashew", "cashews", "cashew nut", "cashew nuts"),
    "SP": ("pecan", "pecans", "pecan nut", "pecan nuts"),
    "ST": ("pistachio", "pistachios"),
    "SM": ("macadamia", "macadamia nut", "macadamia nuts"),
    "SR": ("brazil nut", "brazil nuts"),
    "PN": ("pine nut", "pine nuts"),  # its own GS1 code, not a member of the tree-nut family AN
    "AN": ("nut", "nuts", "tree nuts"),
    "UW": ("wheat",),
    "NR": ("rye",),
    "GB": ("barley",),
    "GO": ("oat", "oats"),
    "AW": ("gluten",),
    "AE": ("egg", "eggs"),
    "AY": ("soy", "soya", "soybean", "soybeans"),
    "AF": ("fish",),
    "AC": ("crustacean", "crustaceans"),
    "BM": ("mustard",),
    "BC": ("celery",),
    "AS": ("sesame",),
    "NL": ("lupin", "lupine"),
    "UM": ("mollusc", "molluscs", "mollusk", "mollusks"),
    "AU": ("sulphite", "sulphites", "sulfite", "sulfites"),
}
# GS1 code -> Finnish word starts. "pähkin", "sinap" and "rukii" also catch the inflected forms
# ("pähkinöistä", "sinapin", "rukiin").
_FINNISH: dict[str, tuple[str, ...]] = {
    "AM": ("maito",),
    "SA": ("manteli",),
    "AN": ("pähkin",),
    "UW": ("vehnä",),
    "NR": ("ruis", "rukii"),
    "GB": ("ohra",),
    "GO": ("kaura",),
    "AW": ("gluteeni",),
    "AE": ("kananmuna",),
    "AY": ("soija",),
    "AF": ("kala",),
    "BM": ("sinap",),
    "BC": ("selleri",),
    "AS": ("seesami",),
}
# Finnish words that start like an allergen and name something else (catalog reading, 14 Nov): lactic acid,
# a milk allergy named in a suitability note, milk-cap mushrooms, olives, calamari, fishing and fish stocks.
_FINNISH_NOT_THE_ALLERGEN = (
    "maitohap", "maitoallerg", "maitoherkkusien", "kalamata", "kalamon", "kalamar", "kalastu", "kalakan",
)
_FINNISH_FREE_FROM = re.compile(r"ton|tön|ttom|ttöm")  # "gluteeniton", "gluteenittomat": gluten-free
# A plant "milk" is not milk: "coconut milk", "rice milk". The plant word itself is still read on its own.
_PLANT_WORDS_BEFORE_MILK = frozenset({"coconut", "coco", "rice", "oat", "soy", "soya", "almond", "cashew", "plant"})
# Words a free-from list may also hold, so that "free from dairy, gluten and nuts" reads as one list.
_OTHER_FREE_FROM_WORDS = ("dairy", "lactose", "peanut", "peanuts")
MAX_QUOTED_LENGTH = 80  # our limit: a phrase quoted from the list stays short enough to read in a sentence

_ENGLISH_CODE = {word: code for code, words in _ENGLISH.items() for word in words}
_FINNISH_STEMS = sorted(((stem, code) for code, stems in _FINNISH.items() for stem in stems), key=lambda s: -len(s[0]))
_ENGLISH_PATTERN = "|".join(
    r"\s+".join(re.escape(part) for part in word.split()) for word in sorted(_ENGLISH_CODE, key=len, reverse=True)
)
_FINNISH_PATTERN = "|".join(re.escape(stem) + r"\w*" for stem, _ in _FINNISH_STEMS)
_ENGLISH_WORD = re.compile(rf"(?<!\w)(?:{_ENGLISH_PATTERN})(?!\w)", re.IGNORECASE)
_FINNISH_WORD = re.compile(rf"(?<!\w)(?:{_FINNISH_PATTERN})", re.IGNORECASE)

_ITEM = rf"(?<!\w)(?:{_ENGLISH_PATTERN}|{_FINNISH_PATTERN}|{'|'.join(_OTHER_FREE_FROM_WORDS)})(?!\w)"
_SEPARATOR = r"\s*(?:,|&|/|\band\b|\bor\b|\bja\b|\btai\b)\s*"
_FREE_FROM_CUE = (
    r"\bfree\s+(?:from|of)|\b(?:does|do)\s+(?:not|no)\s+contain|\bdoesn't\s+contain|\bcontains?\s+no"
    r"|\bwithout|\bno|\bnot|\bei\s+sisäl\w*"
)
_FREE_FROM_LIST = re.compile(rf"(?:{_FREE_FROM_CUE})\s+{_ITEM}(?:{_SEPARATOR}{_ITEM})*", re.IGNORECASE)
_FREE_AFTER = re.compile(r"[\s-]*free\b", re.IGNORECASE)  # "gluten-free", "nut free"
_MILK_CAPS_AFTER = re.compile(r"[\s-]*caps?\b", re.IGNORECASE)  # "Milk-caps": a mushroom
_MAY_CONTAIN = re.compile(
    r"\b(?:may|can|might|could)\s+(?:also\s+)?(?:contain|include)\b|\btraces?\s+of\b"
    r"|\bsaattaa\s+sisältää\b|\bvoi\s+sisältää\b|\bjäämiä\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")  # a decimal point ("2.5%") does not end a sentence
_WORD_BEFORE = re.compile(r"(\w+)[\s-]*$")

Span = tuple[int, int]


@dataclass(frozen=True)
class IngredientMention:
    """One allergen the ingredient list names: its GS1 code and the words that name it.

    `words` is the word as the list writes it ("ALMOND") or, inside a "may contain" phrase, the whole
    phrase, on one line and at most `MAX_QUOTED_LENGTH` characters.
    """

    code: str
    words: str
    may_contain: bool


@lru_cache(maxsize=4096)
def ingredient_mentions(text: str | None) -> tuple[IngredientMention, ...]:
    """Every allergen the text names, in the order it names them; a free-from wording names none."""
    if not text:
        return ()
    free_from = tuple(match.span() for match in _FREE_FROM_LIST.finditer(text))
    may_contain = _may_contain_spans(text)
    mentions = []
    for start, end, code in _words(text):
        if _within(start, end, free_from) or _FREE_AFTER.match(text, end):
            continue
        phrase = next(((first, last) for first, last in may_contain if first <= start < last), None)
        words = text[phrase[0]:phrase[1]] if phrase else text[start:end]
        mentions.append(IngredientMention(code=code, words=_quotable(words), may_contain=phrase is not None))
    return tuple(mentions)


def _words(text: str) -> list[tuple[int, int, str]]:
    """(start, end, code) of every allergen word, English first where an English and a Finnish one overlap."""
    found = [(*match.span(), code) for match in _ENGLISH_WORD.finditer(text) if (code := _english(text, match))]
    taken = [(start, end) for start, end, _ in found]
    for match in _FINNISH_WORD.finditer(text):
        code = _finnish(match.group(0))
        if code is not None and not any(match.start() < end and start < match.end() for start, end in taken):
            found.append((*match.span(), code))
    return sorted(found)


def _english(text: str, match: re.Match[str]) -> str | None:
    code = _ENGLISH_CODE[" ".join(match.group(0).casefold().split())]
    if code != "AM":
        return code
    before = _WORD_BEFORE.search(text, 0, match.start())
    is_plant_milk = before is not None and before.group(1).casefold() in _PLANT_WORDS_BEFORE_MILK
    return None if is_plant_milk or _MILK_CAPS_AFTER.match(text, match.end()) else code


def _finnish(word: str) -> str | None:
    folded = word.casefold()
    if folded.startswith(_FINNISH_NOT_THE_ALLERGEN):
        return None
    stem, code = next(((stem, code) for stem, code in _FINNISH_STEMS if folded.startswith(stem)), ("", None))
    return None if code is None or _FINNISH_FREE_FROM.search(folded, len(stem)) else code


def _may_contain_spans(text: str) -> tuple[Span, ...]:
    """From each "may contain" cue to the end of its sentence."""
    spans = []
    for match in _MAY_CONTAIN.finditer(text):
        end = _SENTENCE_END.search(text, match.end())
        spans.append((match.start(), end.start() if end else len(text)))
    return tuple(spans)


def _within(start: int, end: int, spans: tuple[Span, ...]) -> bool:
    return any(first <= start and end <= last for first, last in spans)


def _quotable(words: str) -> str:
    """On one line, printable, no double quote (the sentence quotes it), cut at a word when too long."""
    flat = "".join(char for char in " ".join(words.split()) if char.isprintable()).replace('"', "'")
    if len(flat) <= MAX_QUOTED_LENGTH:
        return flat
    return flat[:MAX_QUOTED_LENGTH].rsplit(" ", 1)[0] + "…"
