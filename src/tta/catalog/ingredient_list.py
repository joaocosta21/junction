"""One ingredient statement read as a label is written: its components, and the form each is compared in.

The text is data of the product file and is only read. The rules are the grammar of a label, not a list of
ingredients (moved here from `tta.offers.composition` by lane FC2, unchanged, so that the catalog can read its
own statements when it derives the qualifiers, `tta.catalog.qualifiers`):

- The first sentence is the list. A later sentence is a note ("Origin of oats: Finland.") and is not compared,
  unless it is a list itself (two top-level commas or more). A sentence or a component that opens with
  "contains" or "may contain" (`TRAILER_OPENERS`) is an allergen note, never a component.
- Components are split at top-level commas, semicolons and the closing "and" (`CONJUNCTIONS`); parentheses and
  square brackets hold the sub-components of the component before them; "thickener: pectin" is read as
  "thickener (pectin)".
- Each component keeps its own words. For comparison only: case, spacing, hyphens, footnote marks and
  percentages are dropped, an E-number is written one way ("E 407", "E-407", "e407"; "E340(ii)", "E340ii"), a
  closing "s" is dropped from each word (singular against plural) and "z" reads as "s". Where a label
  gives an E-number beside its name ("calcium carbonate E170"), either one names the component.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Label grammar, not ingredients: the word that closes a list, in the languages of the file's statements.
CONJUNCTIONS = ("and", "ja", "sekä", "och", "samt", "og", "und")
# Label grammar: what opens an allergen note. "contains" also opens "contains naturally occurring sugars".
TRAILER_OPENERS = (
    "may contain", "may also contain", "may include", "contains", "contain", "saattaa sisältää", "voi sisältää",
    "sisältää", "kan innehålla", "innehåller",
)
LIST_SENTENCE_COMMAS = 2  # a later sentence with this many top-level commas is read as more of the list

_OPEN, _CLOSE = "([{", ")]}"
_PERCENT = re.compile(r"(?:[<>≥≤~]|min\.?|max\.?|vähintään|enintään)?\s*\d+(?:[.,]\d+)?\s*%")
_E_NUMBER = re.compile(r"\be[\s-]?(\d{3,4}(?:[a-z]|[ivx]{1,4})?)\b")
_E_KEY = re.compile(r"e\d{3,4}[a-z]{0,4}")
# "E340(ii)" is one E-number with its subclass, not a component "E340" that holds "ii": read as "E340ii".
_E_SUBCLASS = re.compile(r"\b(E[\s-]?\d{3,4})\s?\(([ivx]{1,4})\)", re.IGNORECASE)
_NOT_A_WORD = re.compile(r"[^\w]+")
_CONJUNCTION = re.compile(rf"(?<![-‐])\s+(?:{'|'.join(CONJUNCTIONS)}|&)\s+", re.IGNORECASE)
_TRAILER = re.compile(rf"(?:{'|'.join(TRAILER_OPENERS)})\b", re.IGNORECASE)
_EDGES = " \t\r\n.,;:*¹²³•-–\u200e"
_NO_BREAK_SPACE = "\u00a0"
# A line break inside a statement, real or written out as backslash-n (176 English statements, whole catalog):
# labels wrap in the middle of a list, so it is spacing, not the end of a sentence.
_LINE_BREAK = re.compile(r"\\n|[\r\n]+")
_MIN_WORD_FOR_SINGULAR = 4


@dataclass(frozen=True)
class Component:
    """One component of an ingredient list: its own words, its form for comparison, its sub-components."""

    words: str  # as the label writes it, with what stands in its parentheses
    name: str  # the words in front of the parentheses, as written
    key: str  # `name`, normalised for comparison only
    parts: tuple[Component, ...] = ()



def parse_statement(text: str) -> tuple[Component, ...]:
    """The components of one ingredient statement, in the label's order."""
    text = _E_SUBCLASS.sub(r"\1\2", _LINE_BREAK.sub(" ", text.replace(_NO_BREAK_SPACE, " ")))
    sentences = _sentences(text)
    kept = [
        sentence for index, sentence in enumerate(sentences)
        if not _TRAILER.match(sentence.lstrip(_EDGES))
        and (index == 0 or len(_split(sentence, ",;")) > LIST_SENTENCE_COMMAS)
    ]
    return tuple(component for sentence in kept for component in _components(sentence))


def _sentences(text: str) -> list[str]:
    """The text cut at each full stop outside parentheses. A full stop ends a sentence only when a space
    follows it, so a decimal point ("1.5 %") is not one."""
    found, depth, start = [], 0, 0
    for index, character in enumerate(text):
        depth = _depth(depth, character)
        if depth:
            continue
        if character == "." and text[index + 1: index + 2].isspace():
            found.append(text[start:index])
            start = index + 1
    found.append(text[start:])
    return [each for each in found if each.strip(_EDGES)]


def _depth(depth: int, character: str) -> int:
    if character in _OPEN:
        return depth + 1
    return max(depth - 1, 0) if character in _CLOSE else depth


def _split(text: str, separators: str) -> list[str]:
    """The text cut at each separator outside parentheses. A comma between two digits is a decimal comma."""
    found, depth, start = [], 0, 0
    for index, character in enumerate(text):
        depth = _depth(depth, character)
        if depth or character not in separators:
            continue
        if character == "," and text[index - 1: index].isdigit() and text[index + 1: index + 2].isdigit():
            continue
        found.append(text[start:index])
        start = index + 1
    found.append(text[start:])
    return found


def _components(text: str) -> list[Component]:
    pieces = [last for piece in _split(text, ",;") for last in _at_conjunctions(piece)]
    return [component for piece in pieces if (component := _component(piece)) is not None]


def _at_conjunctions(text: str) -> list[str]:
    """ "CREAM and stabiliser (carrageenan)" is two components; "mono- and diglycerides" is one."""
    found, start = [], 0
    for match in _CONJUNCTION.finditer(text):
        if _depth_at(text, match.start()) == 0:
            found.append(text[start:match.start()])
            start = match.end()
    found.append(text[start:])
    return found


def _depth_at(text: str, end: int) -> int:
    depth = 0
    for character in text[:end]:
        depth = _depth(depth, character)
    return depth


def _component(text: str) -> Component | None:
    """One piece of a list: the words in front, then what its parentheses (or its colon) hold."""
    words = " ".join(text.split()).strip(_EDGES)
    if not words or _TRAILER.match(words):
        return None
    name, inner = _name_and_inner(words)
    parts = tuple(_components(inner)) if inner else ()
    key = normalise(name)
    if not key:
        # Nothing in front of the parentheses ("(10 %)" alone, or "(water, OAT)"): its parts stand for it.
        return Component(words=words, name=words, key="", parts=parts) if parts else None
    return Component(words=words, name=name.strip(_EDGES), key=key, parts=parts)


def _name_and_inner(words: str) -> tuple[str, str]:
    """ "stabiliser (carrageenan)" -> ("stabiliser", "carrageenan"). What follows the parentheses stays in the
    name ("OAT flour (10 %) wholegrain"); every parenthesis of the piece is read as its sub-components."""
    name, inner, depth, start = [], [], 0, 0
    for index, character in enumerate(words):
        if character in _OPEN:
            if depth == 0:
                name.append(words[start:index])
                start = index + 1
            depth += 1
        elif character in _CLOSE and depth:
            depth -= 1
            if depth == 0:
                inner.append(words[start:index])
                start = index + 1
    (inner if depth else name).append(words[start:])  # a parenthesis the label never closes
    in_front = " ".join(" ".join(name).split())
    if not inner and ":" in in_front:
        head, _, rest = in_front.partition(":")
        if head.strip() and rest.strip():
            return head, rest
    return in_front, ", ".join(inner)


def normalise(words: str) -> str:
    """The words as they are compared: never shown to a person."""
    text = _E_NUMBER.sub(r"e\1", _PERCENT.sub(" ", words.casefold()))
    return " ".join(_singular(word).replace("z", "s") for word in _NOT_A_WORD.sub(" ", text).split())


def forms(key: str) -> set[str]:
    """Every form under which a key is matched: without its spaces ("soya beans", "SOYAbeans"; "rape seed",
    "rapeseed"), where the label gives an E-number beside a name ("calcium carbonate E170") each alone, and
    with the plural in "-es" undone."""
    if not key:
        return set()
    words = key.split()
    numbers = [word for word in words if _E_KEY.fullmatch(word)]
    forms = {key}
    if numbers and len(numbers) < len(words):
        forms |= {*numbers, " ".join(word for word in words if word not in numbers)}
    return {spelling for form in forms for spelling in spellings(form)}


def spellings(form: str) -> set[str]:
    """Without spaces, and with the plural in "-es" undone: "starches" was read as "starche" and "olives" as
    "olive", so both are tried."""
    return {form.replace(" ", ""), "".join(_without_e(word) for word in form.split())}


def _without_e(word: str) -> str:
    return word[:-1] if len(word) > _MIN_WORD_FOR_SINGULAR and word.endswith("e") else word


def _singular(word: str) -> str:
    return word[:-1] if len(word) >= _MIN_WORD_FOR_SINGULAR and word.endswith("s") and not word[-2].isdigit() else word
