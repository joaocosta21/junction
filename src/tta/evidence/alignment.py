"""What a page found on the web answers for each allergen an order excludes (AP-9, AWARDS-PLAN section 2.4).

Scores on the 20% controls and the 20% precision: the person who signs reads, per excluded allergen, what Valio
Aimo's data says and what the page says, in the page's own words, instead of three lists to search.

Stricter only. An answer is shown beside the question; a page that names an excluded allergen adds a reason to
check. Nothing here changes a status, a finding or a verdict, and "free from" on a page never makes a product safe.

How a page's words are read:
- A term of the page's `contains` or `may_contain` list is read with the catalog's own ingredient reader
  (`tta.allergens.ingredients.ingredient_mentions`), plus the few words below that reader does not hold.
- A term of the `free_from` list is read with the small table below, because the ingredient reader skips free-from
  wordings on purpose and its Finnish "maito" does not match "Maidoton".
- An excluded family is named by one of its members ("almond" for tree nuts) and by its own word. A page that is
  free from a family is free from its members; free from one member says nothing about the family.
- Oats asked about the gluten cereals are read as the allergen rule reads them (`tta.allergens.statements`): not
  ruled out, unless the page says gluten-free.
- A term no table reads is never guessed: the allergen is then answered "the page's words could not be matched".
- An entry of the page that could not be read at all (`reading._terms` counts them) may have named anything: every
  allergen the read terms do not name is then answered "some of the page's words could not be read, so nothing is
  concluded", never "not named" and never "free from". A page whose three lists are empty "lists nothing".
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from enum import StrEnum

from tta.allergens.codes import GLUTEN_CEREALS_CODE, OATS_CODE, describe, members_of, parent_of
from tta.allergens.ingredients import ingredient_mentions
from tta.contracts.allergen import AllergenFinding
from tta.contracts.common import AllergenOutcome, AllergenRelation, Contract
from tta.contracts.order import Evidence
from tta.evidence import wording

# Words the ingredient reader does not hold (GS1 code -> English whole words, Finnish word starts).
_EXTRA_ENGLISH: dict[str, tuple[str, ...]] = {"AP": ("peanut", "peanuts"), "ML": ("lactose",)}
_EXTRA_FINNISH: dict[str, tuple[str, ...]] = {"AP": ("maapähkin",), "ML": ("laktoosi",)}
# The free-from table: GS1 code -> (English whole words, Finnish word starts). "maido" reads "Maidoton".
_FREE_ENGLISH: dict[str, tuple[str, ...]] = {
    "AM": ("milk", "dairy"), "ML": ("lactose",), "AW": ("gluten",), "AE": ("egg", "eggs"),
    "AN": ("nut", "nuts", "tree nut", "tree nuts"), "AP": ("peanut", "peanuts"), "AY": ("soy", "soya"),
    "AS": ("sesame",), "AF": ("fish",), "UW": ("wheat",), "BM": ("mustard",), "BC": ("celery",),
}
_FREE_FINNISH: dict[str, tuple[str, ...]] = {
    "AM": ("maido", "maito"), "ML": ("laktoosi",), "AW": ("gluteeni",), "AE": ("kananmuna", "muna"),
    "AN": ("pähkinä",), "AP": ("maapähkinä",), "AY": ("soija",), "AS": ("seesami",), "AF": ("kala",),
    "UW": ("vehnä",), "BM": ("sinap",), "BC": ("selleri",),
}
_FREE_SUFFIX = re.compile(r"[\s-]*free\b|\w*(?:ton|tön|ttom|ttöm)", re.IGNORECASE)  # "peanut-free", "laktoositon"
_VALIO = {
    AllergenRelation.NOT_STATED: wording.VALIO_STATES_NOTHING,
    AllergenRelation.UNDECLARED: wording.VALIO_UNDECLARED,
    AllergenRelation.MAY_CONTAIN: wording.VALIO_NOT_RULED_OUT,
    AllergenRelation.CONTAINS: wording.VALIO_CONTAINS,
    AllergenRelation.FREE_FROM: wording.VALIO_FREE_FROM,
}


class PageAnswer(StrEnum):
    """What the page says about one excluded allergen, the strictest first."""

    CONTAINS = "CONTAINS"
    MAY_CONTAIN = "MAY_CONTAIN"
    FREE_FROM = "FREE_FROM"
    NOT_NAMED = "NOT_NAMED"  # every word of the page was read, and none names this allergen
    NOTHING_LISTED = "NOTHING_LISTED"  # the page's three lists are empty: it says nothing about any allergen
    # The page has words no table reads, or entries that could not be read at all (S2): nothing is concluded.
    UNMATCHED = "UNMATCHED"


class AllergenAnswer(Contract):
    """One excluded allergen of one product: Valio Aimo's statement beside the page's, in the page's words."""

    product_id: str
    excluded_code: str
    allergen: str  # "milk (AM)"
    valio: AllergenRelation
    page: PageAnswer
    page_words: tuple[str, ...] = ()  # the terms of the page the answer rests on, as the page wrote them
    sentence: str

    @property
    def names_excluded(self) -> bool:
        """True when the page names the excluded allergen under contains or may contain."""
        return self.page in (PageAnswer.CONTAINS, PageAnswer.MAY_CONTAIN)


Words = dict[str, tuple[str, ...]]


def _pattern(english: Words, finnish: Words) -> list[tuple[re.Pattern[str], str]]:
    patterns = []
    for code, words in english.items():
        joined = "|".join(r"\s+".join(re.escape(part) for part in word.split()) for word in words)
        patterns.append((re.compile(rf"(?<!\w)(?:{joined})(?!\w)", re.IGNORECASE), code))
    for code, stems in finnish.items():
        joined = "|".join(re.escape(stem) for stem in stems)
        patterns.append((re.compile(rf"(?<!\w)(?:{joined})", re.IGNORECASE), code))
    return patterns


_EXTRA = _pattern(_EXTRA_ENGLISH, _EXTRA_FINNISH)
_FREE = _pattern(_FREE_ENGLISH, _FREE_FINNISH)


def _named(term: str) -> tuple[frozenset[str], frozenset[str]]:
    """(codes the term names, codes it names only as "may contain") for a term of `contains` or `may_contain`."""
    mentions = ingredient_mentions(term)
    certain = {mention.code for mention in mentions if not mention.may_contain}
    maybe = {mention.code for mention in mentions if mention.may_contain}
    for pattern, code in _EXTRA:
        if any(not _FREE_SUFFIX.match(term, match.end()) for match in pattern.finditer(term)):
            certain.add(code)
    return frozenset(certain), frozenset(maybe - certain)


def _freed(term: str) -> frozenset[str]:
    """The codes a term of the `free_from` list is about."""
    return frozenset(code for pattern, code in _FREE if pattern.search(term))


def _asked_codes(code: str) -> frozenset[str]:
    """The codes that name the excluded allergen on a page: itself, its members and its family."""
    family = parent_of(code)
    return frozenset({code, *members_of(code), *([family] if family else [])})


def _is_oats_only(code: str, named: Iterable[str]) -> bool:
    return code == GLUTEN_CEREALS_CODE and set(named) & _asked_codes(code) == {OATS_CODE}


class _Page:
    """The three lists of one page, each term read once."""

    def __init__(self, evidence: Evidence, unread_entries: int = 0) -> None:
        self.unread_entries = unread_entries  # entries of the lists that `reading` could not read
        self.contains = tuple((term, *_named(term)) for term in evidence.contains)
        self.may_contain = tuple((term, *_named(term)) for term in evidence.may_contain)
        self.free_from = tuple((term, _freed(term)) for term in evidence.free_from)

    def unread(self) -> tuple[str, ...]:
        """The terms no table reads."""
        listed = [term for term, certain, maybe in (*self.contains, *self.may_contain) if not certain | maybe]
        return (*listed, *(term for term, codes in self.free_from if not codes))

    def lists_nothing(self) -> bool:
        return not (self.contains or self.may_contain or self.free_from)

    def naming(self, asked: frozenset[str]) -> tuple[tuple[str, ...], tuple[str, ...], frozenset[str]]:
        """(terms under contains, terms under may contain, the codes those terms name) for the asked codes."""
        sure = tuple(term for term, certain, _ in self.contains if certain & asked)
        maybe = tuple(term for term, certain, may in self.contains if may & asked and not certain & asked)
        maybe += tuple(term for term, certain, may in self.may_contain if (certain | may) & asked)
        codes = frozenset().union(*(certain | may for _, certain, may in (*self.contains, *self.may_contain)))
        return sure, maybe, codes & asked

    def free(self, code: str) -> tuple[str, ...]:
        """The free-from terms about this allergen or about its whole family."""
        covering = {code, parent_of(code)} - {None}
        return tuple(term for term, codes in self.free_from if codes & covering)


def _quoted(terms: Sequence[str]) -> str:
    return ", ".join(terms)


def _page_answer(code: str, page: _Page, allergen: str) -> tuple[PageAnswer, tuple[str, ...], str]:
    sure, maybe, named = page.naming(_asked_codes(code))
    free = page.free(code)
    also = wording.ALSO_FREE_FROM.format(words=_quoted(free)) if free else ""
    if (sure or maybe) and _is_oats_only(code, named):
        if free:
            return PageAnswer.FREE_FROM, free, wording.PAGE_FREE_FROM.format(words=_quoted(free))
        return PageAnswer.MAY_CONTAIN, sure + maybe, wording.PAGE_OATS.format(words=_quoted(sure + maybe))
    if sure:
        return PageAnswer.CONTAINS, sure, wording.PAGE_CONTAINS.format(words=_quoted(sure)) + also
    if maybe:
        return PageAnswer.MAY_CONTAIN, maybe, wording.PAGE_MAY_CONTAIN.format(words=_quoted(maybe)) + also
    if page.unread_entries:
        # An entry that was not read may name this allergen: neither "free from" nor "not named" is said.
        return PageAnswer.UNMATCHED, (), wording.PAGE_UNREAD.format(allergen=allergen)
    if free:
        return PageAnswer.FREE_FROM, free, wording.PAGE_FREE_FROM.format(words=_quoted(free))
    unread = page.unread()
    if unread:
        return PageAnswer.UNMATCHED, unread, wording.PAGE_UNMATCHED.format(words=_quoted(unread))
    if page.lists_nothing():
        return PageAnswer.NOTHING_LISTED, (), wording.PAGE_LISTS_NOTHING
    return PageAnswer.NOT_NAMED, (), wording.PAGE_NOT_NAMED


def align(
    evidence: Evidence, findings: Sequence[AllergenFinding], unread_entries: int = 0
) -> tuple[AllergenAnswer, ...]:
    """One answer per excluded allergen the product was sent to a person for. Empty when no page was found: a
    page that is missing answers nothing. `unread_entries` is the count `reading.read_page` gives."""
    if not evidence.found:
        return ()
    page = _Page(evidence, unread_entries)
    answers = []
    for finding in findings:
        if finding.outcome is not AllergenOutcome.TO_HUMAN:
            continue
        allergen = describe(finding.excluded_code)
        answer, words, said = _page_answer(finding.excluded_code, page, allergen)
        answers.append(AllergenAnswer(
            product_id=evidence.product_id, excluded_code=finding.excluded_code, allergen=allergen,
            valio=finding.relation, page=answer, page_words=words,
            sentence=wording.ASKED.format(allergen=allergen, valio=_VALIO[finding.relation], page=said),
        ))
    return tuple(answers)


def reason_for_the_signer(answers: Sequence[AllergenAnswer]) -> str | None:
    """The reason a page adds when it names an excluded allergen; `None` when it names none."""
    named = tuple(dict.fromkeys(answer.allergen for answer in answers if answer.names_excluded))
    return wording.PAGE_NAMES_EXCLUDED.format(allergens=" and ".join(named)) if named else None


def with_answers(evidence: Evidence, findings: Sequence[AllergenFinding], unread_entries: int = 0) -> Evidence:
    """The evidence with its sentence extended by the answers and, when the page names an excluded allergen, by
    the reason. The lists, the link and the hash stay as they were read."""
    answers = align(evidence, findings, unread_entries)
    if not answers:
        return evidence
    reason = reason_for_the_signer(answers)
    parts = (evidence.sentence, *(answer.sentence for answer in answers), *([reason] if reason else []))
    return evidence.model_copy(update={"sentence": " ".join(parts)})
