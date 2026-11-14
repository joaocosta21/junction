"""Reading one Context.dev answer into evidence: what is kept, what is dropped, and the sentence that says which."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.evidence.answers import AnswerRecord
from tta.evidence.reading import MAX_TERM_LENGTH, MAX_TERMS, MAX_TEXT_LENGTH, read_answer

Record = Callable[[str, dict[str, Any]], AnswerRecord]


def _with(body: dict[str, Any], **content: Any) -> dict[str, Any]:
    return {**body, "json_content": {**body["json_content"], **content}}


def test_a_matching_page_becomes_evidence_with_its_link_hash_and_time(
    catalog: ProductCatalog, record: Record, bodies: SimpleNamespace, ids: SimpleNamespace
) -> None:
    evidence = read_answer(record(ids.elovena, bodies.elovena), catalog.get_product(ids.elovena))

    assert evidence.found
    assert evidence.product_id == ids.elovena
    assert evidence.source_url == bodies.elovena_url
    assert evidence.product_name_on_page == "Elovena Kaurajuoma kahviin"
    assert evidence.page_title == "Elovena Kaurajuoma kahviin"
    assert evidence.contains == ("KAURA",)
    assert evidence.may_contain == ()
    assert evidence.free_from == ("Gluteeniton", "Laktoositon", "Maidoton", "Kananmunaton")
    assert evidence.retrieved_at == bodies.retrieved_at
    canonical = json.dumps(bodies.elovena["json_content"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert evidence.content_hash == hashlib.sha256(canonical.encode()).hexdigest()
    assert evidence.sentence == (
        "The manufacturer's page “Elovena Kaurajuoma kahviin” on elovena.fi says: contains KAURA; "
        "free from Gluteeniton, Laktoositon, Maidoton, Kananmunaton."
    )


def test_a_page_for_a_different_product_is_dropped(
    catalog: ProductCatalog, record: Record, bodies: SimpleNamespace, ids: SimpleNamespace
) -> None:
    evidence = read_answer(record(ids.oddlygood_oat, bodies.wrong_product), catalog.get_product(ids.oddlygood_oat))

    assert not evidence.found
    assert (evidence.source_url, evidence.contains, evidence.content_hash) == (None, (), None)
    assert evidence.sentence == (
        "No evidence was found on the web for product 468465: the page found is for another product "
        "(“Oddlygood® Barista oat drink 1 l UHT gluten free”), so it was dropped."
    )


def test_no_page_found_is_no_evidence(
    catalog: ProductCatalog, record: Record, bodies: SimpleNamespace, ids: SimpleNamespace
) -> None:
    evidence = read_answer(record(ids.oddlygood_almond, bodies.not_found), catalog.get_product(ids.oddlygood_almond))

    assert not evidence.found
    assert evidence.sentence == (
        "No evidence was found on the web for product 474864: no manufacturer's page of this product was found."
    )


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"success": False}, "the search service reported that this answer failed"),
        ({"partial": True}, "the research stopped before it was complete"),
        ({"json_content": "not an object"}, "the answer could not be read"),
        ({"json_content": None}, "the answer could not be read"),
        ({"sources": "not a list"}, "the answer could not be read"),
    ],
)
def test_a_failed_or_unreadable_answer_is_no_evidence(
    catalog: ProductCatalog, record: Record, bodies: SimpleNamespace, ids: SimpleNamespace,
    change: dict[str, Any], reason: str,
) -> None:
    evidence = read_answer(record(ids.elovena, {**bodies.elovena, **change}), catalog.get_product(ids.elovena))

    assert not evidence.found
    assert evidence.sentence == f"No evidence was found on the web for product 469512: {reason}."


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,hello",
        "ftp://elovena.fi/x",
        "https://user:secret@elovena.fi/x",
        "https:///nohost",
        "",
        None,
        42,
    ],
)
def test_a_link_that_is_not_a_plain_web_address_is_dropped(
    catalog: ProductCatalog, record: Record, bodies: SimpleNamespace, ids: SimpleNamespace, url: Any
) -> None:
    body = {**_with(bodies.elovena, source_url=url), "sources": [url]}

    evidence = read_answer(record(ids.elovena, body), catalog.get_product(ids.elovena))

    assert not evidence.found
    assert evidence.source_url is None


def test_a_link_the_research_did_not_read_is_dropped(
    catalog: ProductCatalog, record: Record, bodies: SimpleNamespace, ids: SimpleNamespace
) -> None:
    body = {**bodies.elovena, "sources": ["https://elovena.fi/another-page/"]}

    evidence = read_answer(record(ids.elovena, body), catalog.get_product(ids.elovena))

    assert not evidence.found
    assert evidence.sentence.endswith(": the answer names no page it read.")


def test_page_text_is_kept_as_text_bounded_in_size_and_free_of_control_characters(
    catalog: ProductCatalog, record: Record, bodies: SimpleNamespace, ids: SimpleNamespace
) -> None:
    long_title = "Elovena Kaurajuoma kahviin " + "x" * (2 * MAX_TEXT_LENGTH)
    terms = [bodies.hostile, "A\u0000B‮C", "y" * (MAX_TERM_LENGTH + 1), 7, None, *[f"t{n}" for n in range(30)]]
    body = _with(bodies.elovena, page_title=long_title, contains=terms, free_from="Maidoton")

    evidence = read_answer(record(ids.elovena, body), catalog.get_product(ids.elovena))

    assert evidence.found
    assert len(evidence.page_title) == MAX_TEXT_LENGTH
    assert evidence.contains[0] == bodies.hostile  # kept as text: the page escapes it
    assert evidence.contains[1] == "ABC"
    assert len(evidence.contains) == MAX_TERMS
    assert all(len(term) <= MAX_TERM_LENGTH for term in evidence.contains)
    assert evidence.free_from == ()  # not a list
