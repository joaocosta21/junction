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
- A word that only says where or how an ingredient was farmed is not a difference (decision B49): "organic
  CREAM" against "CREAM", "WHEAT (EU)" against "WHEAT (Finland)". Which words those are is measured from the
  catalog (`tta.catalog.qualifiers`), not typed; each such pair is carried in `same_but_for_origin` so that a
  sentence can say it. A word of processing ("pasteurised", "dried") stays part of the name: it is the same
  only when both lists carry it.
- The two lists must be in the same language (English, else Finnish, else any other both have). No shared
  language, or a product with no list: the contents cannot be compared.
"""

from __future__ import annotations

from dataclasses import dataclass

from tta.catalog.ingredient_list import Component, forms, normalise, parse_statement, spellings
from tta.catalog.qualifiers import Qualifiers, current_qualifiers
from tta.contracts.product import Product

# The languages a comparison prefers, in order; any other language both products carry comes after.
PREFERRED_LANGUAGES = ("en", "fi")
# For a product built without `ingredient_statements` (a test, an older record): the language is not known.
UNKNOWN_LANGUAGE = "und"


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
    # (the original's words, the other's): read as the same component, a word of origin or farming apart.
    same_but_for_origin: tuple[tuple[str, str], ...] = ()

    @property
    def differs(self) -> bool:
        return bool(self.only_in_original or self.only_in_other)


def statements_of(product: Product) -> dict[str, str]:
    """The product's ingredient statements by language, as the file gives them."""
    if product.ingredient_statements:
        return {each.language: each.text for each in product.ingredient_statements}
    return {UNKNOWN_LANGUAGE: product.key_ingredients} if product.key_ingredients else {}


def compare_contents(original: Product, other: Product, qualifiers: Qualifiers | None = None) -> ContentsCheck:
    """What the two ingredient lists show: the components only one has, and the ones both have. `qualifiers`:
    the words of origin and farming; left out, the table of the loaded catalog (`current_qualifiers`)."""
    table = current_qualifiers() if qualifiers is None else qualifiers
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
    return _compare(first, second, language, table)



# --- comparing two statements ------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Atom:
    """One component or sub-component, with every form under which the other list may name it."""

    component: Component
    parent: Component | None
    keys: frozenset[str]
    origin_said: bool = False  # its words say an origin or a way of farming, which is not compared

    @property
    def said(self) -> str:
        """In the label's own words; a sub-component names the component it stands under."""
        return self.component.words if self.parent is None else f"{self.component.words} (in {self.parent.name})"


def _without_origin_tails(
    components: tuple[Component, ...], table: Qualifiers, lost: set[int]
) -> tuple[Component, ...]:
    """The components without what their brackets say of origin only ("WHEAT (EU)" is "WHEAT"); the words
    stay as the label writes them. `lost` collects the components a tail was taken from."""
    found = []
    for component in components:
        kept = tuple(part for part in component.parts if part.parts or not table.says_origin_only(part.key))
        pruned = Component(
            words=component.words, name=component.name, key=component.key,
            parts=_without_origin_tails(kept, table, lost),
        )
        if len(kept) != len(component.parts):
            lost.add(id(pruned))
        found.append(pruned)
    return tuple(found)


def _atoms(
    components: tuple[Component, ...], table: Qualifiers, lost: set[int], parent: Component | None = None
) -> list[_Atom]:
    found: list[_Atom] = []
    for component in components:
        plain = table.without_origin(component.key)
        keys = forms(plain)
        if parent is not None and parent.key and plain:
            # "vegetable oil (rapeseed)" is "rapeseed oil"; "vitamins (D)" is "vitamin D".
            # Spellings only: an E-number under a class name ("stabiliser (E407)") never names the class.
            keys |= spellings(f"{plain} {parent.key.split()[-1]}")
            keys |= spellings(f"{parent.key} {plain}")
        origin_said = plain != component.key or id(component) in lost
        found.append(_Atom(component=component, parent=parent, keys=frozenset(keys), origin_said=origin_said))
        found.extend(_atoms(component.parts, table, lost, component))
    return found


def _compare(
    first: tuple[Component, ...], second: tuple[Component, ...], language: str, table: Qualifiers
) -> ContentsCheck:
    lost: set[int] = set()
    ours = _atoms(_without_origin_tails(first, table, lost), table, lost)
    theirs = _atoms(_without_origin_tails(second, table, lost), table, lost)
    our_keys = frozenset(key for atom in ours for key in atom.keys)
    their_keys = frozenset(key for atom in theirs for key in atom.keys)
    only_ours, refined_ours = _unmatched(ours, theirs, their_keys)
    only_theirs, refined_theirs = _unmatched(theirs, ours, our_keys)
    within = [
        (mine.said, yours.said) for mine in only_ours for yours in only_theirs if _one_within_the_other(mine, yours)
    ]
    pairs = list(dict.fromkeys([*within, *refined_ours, *((mine, yours) for yours, mine in refined_theirs)]))
    only_in_original = _once([*(atom.said for atom in only_ours), *(mine for mine, _ in pairs)])
    only_in_other = _once([*(atom.said for atom in only_theirs), *(yours for _, yours in pairs)])
    return ContentsCheck(
        compared=True, language=language, only_in_original=only_in_original, only_in_other=only_in_other,
        in_both=_once([atom.said for atom in ours if atom.keys & their_keys]), not_shown_same=tuple(pairs),
        # A pair already said as "not shown to be the same" is not also said as the same.
        same_but_for_origin=tuple(
            (mine, yours) for mine, yours in _same_but_for_origin(ours, theirs)
            if mine not in only_in_original and yours not in only_in_other
        ),
    )


def _same_but_for_origin(ours: list[_Atom], theirs: list[_Atom]) -> tuple[tuple[str, str], ...]:
    """The components both lists name where one says an origin or a way of farming the other does not."""
    found = []
    for mine in ours:
        yours = next((each for each in theirs if each.keys & mine.keys), None)
        if yours is None or not (mine.origin_said or yours.origin_said):
            continue
        if normalise(mine.component.words) != normalise(yours.component.words):
            found.append((mine.said, yours.said))
    return tuple(dict.fromkeys(found))


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
