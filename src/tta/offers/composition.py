"""The contents of two products compared: their own ingredient lists, read as a label is written.

Valio's mentors said on 14 Nov 2026 that two products whose nutrition figures agree are not the same formula
when one holds a component the other lacks (lactase in a lactose-free milk, a stabiliser, a vegetable fat). So
the difference is computed from the two lists in front of it, for any product of the catalog, and no list of
"important" words decides what counts: every component one list has and the other lacks is a difference, said
in the label's own words.

How a statement is read (ours; the rules are the grammar of a label, not a list of ingredients):

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

How two lists are compared:

- A component is in both lists when its words, so normalised, are the same; a sub-component also matches as
  "rapeseed oil" when the label writes "vegetable oil (rapeseed)", and as "vitamin D" under "vitamins (D)".
- The order of the components and their percentages are not differences.
- A name in front of parentheses is not a difference when everything inside them is in the other list:
  "stabiliser (carrageenan)" against "carrageenan", "OAT base (water, OAT)" against "water, OAT".
- Anything else that only one list has is a difference. Where the words of one are all among the words of the
  other ("milk protein" against "milk protein concentrate"), or both lists name a component and only one says
  what is in it ("riboflavin (B2)" against "riboflavin", "vegetable oil (rapeseed)" against "vegetable oil
  (palm)"), the pair is said as "not shown to be the same" and still counts as a difference: not sure is never
  read as the same.
- The two lists must be in the same language (English, else Finnish, else any other both have). No shared
  language, or a product with no list: the contents cannot be compared.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tta.contracts.product import Product

# The languages a comparison prefers, in order; any other language both products carry comes after.
PREFERRED_LANGUAGES = ("en", "fi")
# For a product built without `ingredient_statements` (a test, an older record): the language is not known.
UNKNOWN_LANGUAGE = "und"
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


@dataclass(frozen=True)
class ContentsCheck:
    """The ingredient lists of two products, compared. `compared` False: nothing below it says anything."""

    compared: bool
    language: str | None = None  # of the two lists that were compared
    why_not: str = ""  # why they cannot be compared, as the middle of a sentence
    only_in_original: tuple[str, ...] = ()  # in the labels' own words
    only_in_other: tuple[str, ...] = ()
    in_both: tuple[str, ...] = ()  # in the original's words
    # (the original's words, the other's): the words of one are all among the other's. Each is also in the two
    # tuples above: not shown to be the same counts as a difference.
    not_shown_same: tuple[tuple[str, str], ...] = ()

    @property
    def differs(self) -> bool:
        return bool(self.only_in_original or self.only_in_other)


def statements_of(product: Product) -> dict[str, str]:
    """The product's ingredient statements by language, as the file gives them."""
    if product.ingredient_statements:
        return {each.language: each.text for each in product.ingredient_statements}
    return {UNKNOWN_LANGUAGE: product.key_ingredients} if product.key_ingredients else {}


def compare_contents(original: Product, other: Product) -> ContentsCheck:
    """What the two ingredient lists show: the components only one has, and the ones both have."""
    ours, theirs = statements_of(original), statements_of(other)
    for texts, whose in ((ours, "the product asked for has"), (theirs, "this product has")):
        if not texts:
            return ContentsCheck(compared=False, why_not=f"{whose} no ingredient list")
    shared = [each for each in (*PREFERRED_LANGUAGES, *sorted(ours)) if each in ours and each in theirs]
    if not shared:
        return ContentsCheck(compared=False, why_not="the two lists are in different languages")
    language = shared[0]
    first, second = parse_statement(ours[language]), parse_statement(theirs[language])
    for parsed, whose in ((first, "the product asked for"), (second, "this product")):
        if not parsed:
            return ContentsCheck(compared=False, why_not=f"the ingredient list of {whose} names no component")
    return _compare(first, second, language)


# --- reading one statement ---------------------------------------------------------------------------------


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


def _forms(key: str) -> set[str]:
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
    return {spelling for form in forms for spelling in _spellings(form)}


def _spellings(form: str) -> set[str]:
    """Without spaces, and with the plural in "-es" undone: "starches" was read as "starche" and "olives" as
    "olive", so both are tried."""
    return {form.replace(" ", ""), "".join(_without_e(word) for word in form.split())}


def _without_e(word: str) -> str:
    return word[:-1] if len(word) > _MIN_WORD_FOR_SINGULAR and word.endswith("e") else word


def _singular(word: str) -> str:
    return word[:-1] if len(word) >= _MIN_WORD_FOR_SINGULAR and word.endswith("s") and not word[-2].isdigit() else word


# --- comparing two statements ------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Atom:
    """One component or sub-component, with every form under which the other list may name it."""

    component: Component
    parent: Component | None
    keys: frozenset[str]

    @property
    def said(self) -> str:
        """In the label's own words; a sub-component names the component it stands under."""
        return self.component.words if self.parent is None else f"{self.component.words} (in {self.parent.name})"


def _atoms(components: tuple[Component, ...], parent: Component | None = None) -> list[_Atom]:
    found: list[_Atom] = []
    for component in components:
        keys = _forms(component.key)
        if parent is not None and parent.key and component.key:
            # "vegetable oil (rapeseed)" is "rapeseed oil"; "vitamins (D)" is "vitamin D".
            # Spellings only: an E-number under a class name ("stabiliser (E407)") never names the class.
            keys |= _spellings(f"{component.key} {parent.key.split()[-1]}")
            keys |= _spellings(f"{parent.key} {component.key}")
        found.append(_Atom(component=component, parent=parent, keys=frozenset(keys)))
        found.extend(_atoms(component.parts, component))
    return found


def _compare(first: tuple[Component, ...], second: tuple[Component, ...], language: str) -> ContentsCheck:
    ours, theirs = _atoms(first), _atoms(second)
    our_keys = frozenset(key for atom in ours for key in atom.keys)
    their_keys = frozenset(key for atom in theirs for key in atom.keys)
    only_ours, refined_ours = _unmatched(ours, theirs, their_keys)
    only_theirs, refined_theirs = _unmatched(theirs, ours, our_keys)
    within = [
        (mine.said, yours.said) for mine in only_ours for yours in only_theirs if _one_within_the_other(mine, yours)
    ]
    pairs = list(dict.fromkeys([*within, *refined_ours, *((mine, yours) for yours, mine in refined_theirs)]))
    return ContentsCheck(
        compared=True, language=language,
        only_in_original=_once([*(atom.said for atom in only_ours), *(mine for mine, _ in pairs)]),
        only_in_other=_once([*(atom.said for atom in only_theirs), *(yours for _, yours in pairs)]),
        in_both=_once([atom.said for atom in ours if atom.keys & their_keys]), not_shown_same=tuple(pairs),
    )


def _once(said: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(said))


def _unmatched(
    atoms: list[_Atom], others: list[_Atom], other_keys: frozenset[str]
) -> tuple[list[_Atom], list[tuple[str, str]]]:
    """(the atoms the other list does not name, the components it names without what their parentheses hold).

    A component that is a difference as a whole is said once, with what its parentheses hold, and its
    sub-components are not said again. A sub-component the other list lacks under a component it does name
    ("riboflavin (B2)" against "riboflavin"; "vegetable oil (rapeseed)" against "vegetable oil (palm)") is
    said as that pair, each side in its label's words: not shown to be the same.
    """
    resolved = {id(atom.component) for atom in atoms if _resolved(atom.component, atoms, other_keys)}
    named = {id(atom.component): atom for atom in atoms if atom.keys & other_keys}
    different: list[_Atom] = []
    refined: list[tuple[str, str]] = []
    inside: set[int] = set()
    for atom in atoms:  # a parent always comes before its parts
        if id(atom.component) in resolved or id(atom.component) in inside:
            continue
        inside.update(id(each) for each in _descendants(atom.component))
        parent = named.get(id(atom.parent)) if atom.parent is not None else None
        if parent is None:
            different.append(atom)
            continue
        refined.extend(
            (parent.component.words, other.component.words) for other in others if other.keys & parent.keys
        )
    return different, refined


def _descendants(component: Component) -> list[Component]:
    return [each for part in component.parts for each in (part, *_descendants(part))]


def _resolved(component: Component, atoms: list[_Atom], other_keys: frozenset[str]) -> bool:
    """Named by the other list, or a name in front of parentheses whose every sub-component is resolved."""
    keys = next(atom.keys for atom in atoms if atom.component is component)
    if keys & other_keys:
        return True
    return bool(component.parts) and all(_resolved(part, atoms, other_keys) for part in component.parts)


def _one_within_the_other(mine: _Atom, yours: _Atom) -> bool:
    """The words of one are all among the words of the other: maybe the same component, not shown to be."""
    ours, theirs = _all_words(mine.component), _all_words(yours.component)
    return bool(ours and theirs) and (ours <= theirs or theirs <= ours)


def _all_words(component: Component) -> frozenset[str]:
    return frozenset(normalise(component.words).split())
