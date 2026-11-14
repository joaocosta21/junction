"""AP-9: the evidence answers the question that was asked, per excluded allergen, in the page's own words; a page
that names an excluded allergen adds a reason; a word that matches nothing is never guessed; nothing gets safer."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tta.contracts.allergen import AllergenFinding
from tta.contracts.common import AllergenOutcome, AllergenRelation, ApprovalStatus, Identity, Verdict
from tta.contracts.order import Evidence
from tta.evidence.alignment import PageAnswer, align, reason_for_the_signer, with_answers
from tta.evidence.cache import EvidenceCache

Make = Callable[..., Any]
NOT_RULED_OUT = "Alternative: allergen not ruled out"
REASON_START = "The page names "


def _finding(code: str, relation: AllergenRelation = AllergenRelation.NOT_STATED,
             outcome: AllergenOutcome = AllergenOutcome.TO_HUMAN) -> AllergenFinding:
    return AllergenFinding(excluded_code=code, relation=relation, outcome=outcome, sentence="test")


Terms = tuple[str, ...]


def _page(contains: Terms = (), may_contain: Terms = (), free_from: Terms = ()) -> Evidence:
    return Evidence(
        product_id="1", found=True, source_url="https://example.test/p", product_name_on_page="P",
        contains=contains, may_contain=may_contain, free_from=free_from, sentence="The page says something.",
    )


ELOVENA = _page(contains=("KAURA",), free_from=("Gluteeniton", "Laktoositon", "Maidoton", "Kananmunaton"))


def test_the_recorded_elovena_page_with_milk_excluded_reads_free_from_in_its_own_word() -> None:
    (answer,) = align(ELOVENA, (_finding("AM"),))

    assert (answer.page, answer.page_words, answer.valio) == (
        PageAnswer.FREE_FROM, ("Maidoton",), AllergenRelation.NOT_STATED,
    )
    assert answer.sentence == (
        "Asked about milk (AM): Valio Aimo's data states nothing; the page says free from, in its words “Maidoton”."
    )
    assert not answer.names_excluded and reason_for_the_signer((answer,)) is None


def test_lactose_free_on_the_page_is_not_read_as_free_from_milk() -> None:
    (answer,) = align(_page(free_from=("Laktoositon",)), (_finding("AM"),))

    assert answer.page is PageAnswer.NOT_NAMED
    assert answer.sentence.endswith("the page does not name it.")


def test_a_page_that_names_an_excluded_allergen_adds_a_reason_for_the_person_who_signs() -> None:
    page = _page(contains=("Pähkinät",))

    (answer,) = align(page, (_finding("AN"),))
    extended = with_answers(page, (_finding("AN"),))

    assert (answer.page, answer.page_words, answer.names_excluded) == (PageAnswer.CONTAINS, ("Pähkinät",), True)
    assert extended.sentence == (
        "The page says something. Asked about tree nuts (AN): Valio Aimo's data states nothing; the page says it "
        "contains it, in its words “Pähkinät”. The page names tree nuts (AN), which this order excludes: check the "
        "product before approving. What a page says can add a doubt and never removes one."
    )
    assert (extended.contains, extended.found, extended.content_hash) == (page.contains, True, page.content_hash)


@pytest.mark.parametrize(("page", "code", "expected", "words"), [
    (_page(contains=("ALMOND",)), "AN", PageAnswer.CONTAINS, ("ALMOND",)),  # a member names its family
    (_page(contains=("nuts",)), "SA", PageAnswer.CONTAINS, ("nuts",)),  # the family names its member
    (_page(may_contain=("Saattaa sisältää pähkinää",)), "AN", PageAnswer.MAY_CONTAIN, ("Saattaa sisältää pähkinää",)),
    (_page(contains=("may contain traces of nuts",)), "AN", PageAnswer.MAY_CONTAIN, ("may contain traces of nuts",)),
    (_page(contains=("peanuts",)), "AP", PageAnswer.CONTAINS, ("peanuts",)),
    (_page(contains=("peanuts",)), "AN", PageAnswer.NOT_NAMED, ()),  # a peanut is not a tree nut
    (_page(contains=("coconut",)), "AN", PageAnswer.UNMATCHED, ("coconut",)),  # read as no allergen: never guessed
    (_page(free_from=("nut-free",)), "SA", PageAnswer.FREE_FROM, ("nut-free",)),  # free from the whole family
    # One member says nothing of the family, and the free-from table does not hold the word: never guessed.
    (_page(free_from=("almond-free",)), "AN", PageAnswer.UNMATCHED, ("almond-free",)),
    (_page(free_from=("lactose-free",)), "AM", PageAnswer.NOT_NAMED, ()),
    (_page(free_from=("peanut-free",)), "AN", PageAnswer.NOT_NAMED, ()),
    (_page(free_from=("ei sisällä maitoa",)), "AM", PageAnswer.FREE_FROM, ("ei sisällä maitoa",)),
    (_page(free_from=("milk-free",)), "AM", PageAnswer.FREE_FROM, ("milk-free",)),
    (_page(contains=("Maito",), free_from=("Maidoton",)), "AM", PageAnswer.CONTAINS, ("Maito",)),  # strictest wins
    (_page(contains=("KAURA",)), "AW", PageAnswer.MAY_CONTAIN, ("KAURA",)),  # oats, and no gluten-free wording
    (_page(contains=("gluteeniton kaura",), free_from=("Gluteeniton",)), "AW", PageAnswer.FREE_FROM, ("Gluteeniton",)),
    (_page(contains=("VEHNÄ",), free_from=("Gluteeniton",)), "AW", PageAnswer.CONTAINS, ("VEHNÄ",)),
    (_page(), "AM", PageAnswer.NOTHING_LISTED, ()),  # empty lists: "lists nothing", never "does not name it"
])
def test_how_a_pages_words_answer_one_excluded_allergen(
    page: Evidence, code: str, expected: PageAnswer, words: tuple[str, ...]
) -> None:
    (answer,) = align(page, (_finding(code),))

    assert (answer.page, answer.page_words) == (expected, words)


def test_a_word_that_matches_nothing_is_never_guessed() -> None:
    (answer,) = align(_page(contains=("Sisältää luontaisia ainesosia",)), (_finding("AM"),))

    assert answer.page is PageAnswer.UNMATCHED
    assert answer.sentence == (
        "Asked about milk (AM): Valio Aimo's data states nothing; the page's words could not be matched to this "
        "allergen (“Sisältää luontaisia ainesosia”), so nothing is read from them."
    )
    assert reason_for_the_signer((answer,)) is None


def test_one_answer_per_allergen_that_went_to_a_person_and_none_for_one_that_passed() -> None:
    findings = (
        _finding("AN"), _finding("AP", AllergenRelation.MAY_CONTAIN),
        _finding("AS", AllergenRelation.FREE_FROM, AllergenOutcome.PASS),
    )

    answers = align(_page(contains=("Pähkinät", "maapähkinä")), findings)

    assert [(a.excluded_code, a.page, a.valio) for a in answers] == [
        ("AN", PageAnswer.CONTAINS, AllergenRelation.NOT_STATED),
        ("AP", PageAnswer.CONTAINS, AllergenRelation.MAY_CONTAIN),
    ]
    assert "Valio Aimo's data does not rule it out" in answers[1].sentence
    assert reason_for_the_signer(answers).startswith("The page names tree nuts (AN) and peanuts (AP), which")


def test_a_page_that_was_not_found_answers_nothing() -> None:
    missing = Evidence(product_id="1", found=False, sentence="No evidence was found.")

    assert align(missing, (_finding("AM"),)) == ()
    assert with_answers(missing, (_finding("AM"),)) is missing


def test_a_page_that_names_the_excluded_allergen_reaches_the_approvals_reasons_and_changes_no_verdict(
    make_stack: Make, make_finder: Make, fake_answers: Make, requests: SimpleNamespace, agent_hotel: Identity,
    hotel_dietitian: Identity, bodies: SimpleNamespace, tmp_path: Path,
) -> None:
    """Stricter only: the same order with a page that says "contains milk" and with one that says "milk-free"."""
    def body(contains: list[str], free_from: list[str]) -> dict[str, Any]:
        content = {**bodies.elovena["json_content"], "contains": contains, "free_from": free_from}
        return {**bodies.elovena, "json_content": content}

    orders, approvals = [], []
    for index, answer in enumerate((body(["KAURA", "Maito"], []), body(["KAURA"], ["Maidoton"]))):
        stack = make_stack(make_finder(fake_answers(answer), EvidenceCache(tmp_path / str(index))))
        offer = stack.service.create_offer(agent_hotel, requests.elovena())
        option = next(option for option in offer.options if option.title == NOT_RULED_OUT)
        orders.append(stack.service.place_order(agent_hotel, offer.offer_id, option.option_id, "ap9"))
        approvals.append(stack.service.list_approvals(hotel_dietitian, ApprovalStatus.PENDING)[0])

    names, frees = approvals
    assert REASON_START + "milk (AM), which this order excludes" in names.reasons[-1]
    assert REASON_START not in " ".join(frees.reasons)
    assert "the page says free from, in its words “Maidoton”" in frees.reasons[-1]
    for order, approval in zip(orders, approvals, strict=True):  # a page clears nothing and blocks nothing
        assert order.decision.verdict is Verdict.APPROVAL
        assert approval.status is ApprovalStatus.PENDING
        assert order.option.lines[0].allergen_check.findings[0].relation is AllergenRelation.NOT_STATED
    assert orders[0].decision.model_dump(exclude={"evaluated_at"}) == orders[1].decision.model_dump(
        exclude={"evaluated_at"}
    )
    assert names.required_roles == frees.required_roles


# --- S2: entries of the page that could not be read ------------------------------------------------------------------

UNREAD = "some of the page's words could not be read, so nothing is concluded about {allergen}."


@pytest.mark.parametrize("page", [
    _page(),  # the only entry was unreadable: the lists are empty, and that is not "lists nothing"
    _page(contains=("KAURA",)),  # would read "does not name it"
    _page(free_from=("Maidoton",)),  # would read "free from": an unread entry may say "contains milk"
])
def test_with_an_unread_entry_the_page_is_never_answered_not_named_or_free_from(page: Evidence) -> None:
    (answer,) = align(page, (_finding("AM"),), unread_entries=1)

    assert (answer.page, answer.page_words) == (PageAnswer.UNMATCHED, ())
    assert answer.sentence == "Asked about milk (AM): Valio Aimo's data states nothing; " + UNREAD.format(
        allergen="milk (AM)"
    )
    assert not answer.names_excluded


def test_an_unread_entry_never_hides_an_allergen_the_read_terms_name() -> None:
    (answer,) = align(_page(contains=("Maito",)), (_finding("AM"),), unread_entries=2)

    assert (answer.page, answer.page_words) == (PageAnswer.CONTAINS, ("Maito",))


def test_empty_lists_read_lists_nothing() -> None:
    (answer,) = align(_page(), (_finding("AM"),))

    assert answer.page is PageAnswer.NOTHING_LISTED
    assert answer.sentence == (
        "Asked about milk (AM): Valio Aimo's data states nothing; the page lists nothing under contains, may "
        "contain or free from, so it says nothing about it."
    )


def test_with_answers_carries_the_count_into_the_sentence() -> None:
    answered = with_answers(_page(contains=("KAURA",)), (_finding("AM"),), unread_entries=1)

    assert answered.sentence.endswith(UNREAD.format(allergen="milk (AM)"))
