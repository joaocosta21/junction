"""The finder: which products of an approval get evidence, one lookup per product, and a sentence for every
case in which nothing could be found."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import AllergenRelation, Identity
from tta.contracts.offer import OfferOption
from tta.evidence import EvidenceFinder, build_evidence_finder, products_needing_evidence
from tta.evidence.answers import AnswersClient
from tta.evidence.cache import EvidenceCache

Make = Callable[..., Any]


def _elovena_option(make_stack: Make, requests: SimpleNamespace, agent_hotel: Identity) -> OfferOption:
    offer = make_stack(None).service.create_offer(agent_hotel, requests.elovena())
    return offer.options[0]


def test_evidence_is_looked_up_once_per_product(
    make_finder: Make, fake_answers: Make, catalog: ProductCatalog, bodies: SimpleNamespace, ids: SimpleNamespace
) -> None:
    answers = fake_answers(bodies.elovena)
    finder = make_finder(answers)

    first = finder.find_evidence(catalog.get_product(ids.elovena))
    again = finder.find_evidence(catalog.get_product(ids.elovena))

    assert first.found and first == again
    assert answers.asked == [ids.elovena]


def test_without_a_key_only_stored_answers_are_read(
    make_finder: Make, catalog: ProductCatalog, record: Make, bodies: SimpleNamespace, ids: SimpleNamespace,
    empty_cache: EvidenceCache,
) -> None:
    finder = make_finder(None)
    nothing = finder.find_evidence(catalog.get_product(ids.elovena))
    empty_cache.put(record(ids.elovena, bodies.elovena))

    stored = finder.find_evidence(catalog.get_product(ids.elovena))

    assert not nothing.found
    assert nothing.sentence == (
        "No evidence was found on the web for product 469512: no Context.dev key is set, so nothing was looked up."
    )
    assert stored.found


def test_a_failed_lookup_is_said_and_not_stored(
    make_finder: Make, fake_answers: Make, unavailable: Make, catalog: ProductCatalog, ids: SimpleNamespace,
    empty_cache: EvidenceCache,
) -> None:
    answers = fake_answers(error=unavailable("the web search did not answer in time"))
    finder = make_finder(answers)

    evidence = finder.find_evidence(catalog.get_product(ids.elovena))
    finder.find_evidence(catalog.get_product(ids.elovena))

    assert not evidence.found
    assert evidence.retrieved_at is None
    assert evidence.sentence == (
        "No evidence was found on the web for product 469512: the web search did not answer in time."
    )
    assert empty_cache.get(ids.elovena) is None
    assert answers.asked == [ids.elovena, ids.elovena]  # tried again next time


def test_an_answer_without_a_matching_page_is_stored_all_the_same(
    make_finder: Make, fake_answers: Make, catalog: ProductCatalog, bodies: SimpleNamespace, ids: SimpleNamespace,
    empty_cache: EvidenceCache,
) -> None:
    answers = fake_answers(bodies.wrong_product)

    make_finder(answers).find_evidence(catalog.get_product(ids.oddlygood_oat))

    assert empty_cache.get(ids.oddlygood_oat).body == bodies.wrong_product  # it cost credits: never asked twice


def test_a_stored_answer_that_cannot_be_read_is_said(
    make_finder: Make, fake_answers: Make, catalog: ProductCatalog, ids: SimpleNamespace, tmp_path: Path,
) -> None:
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / f"{ids.elovena}.json").write_text("{", encoding="utf-8")

    evidence = make_finder(fake_answers({})).find_evidence(catalog.get_product(ids.elovena))

    assert evidence.sentence.endswith(": the stored result could not be read.")


def test_only_a_line_sent_to_the_dietitian_for_a_missing_statement_gets_evidence(
    make_stack: Make, requests: SimpleNamespace, agent_hotel: Identity, ids: SimpleNamespace
) -> None:
    option = _elovena_option(make_stack, requests, agent_hotel)

    assert products_needing_evidence(option, option.decision) == (ids.elovena,)

    others = tuple(rule for rule in option.decision.fired if rule.rule_id != "P-04")
    no_p04 = option.decision.model_copy(update={"fired": others})
    assert products_needing_evidence(option, no_p04) == ()

    line = option.lines[0]
    stated = line.allergen_check.model_copy(update={"findings": tuple(
        finding.model_copy(update={"relation": AllergenRelation.MAY_CONTAIN})
        for finding in line.allergen_check.findings
    )})
    may_contain = option.model_copy(update={"lines": (line.model_copy(update={"allergen_check": stated}),)})
    assert products_needing_evidence(may_contain, option.decision) == ()

    unchecked = option.model_copy(update={"lines": (line.model_copy(update={"allergen_check": None}),)})
    assert products_needing_evidence(unchecked, option.decision) == ()


def test_for_an_approval_the_finder_answers_one_evidence_per_product(
    make_stack: Make, make_finder: Make, fake_answers: Make, requests: SimpleNamespace, agent_hotel: Identity,
    bodies: SimpleNamespace, ids: SimpleNamespace,
) -> None:
    option = _elovena_option(make_stack, requests, agent_hotel)

    found = make_finder(fake_answers(bodies.elovena)).for_approval(option, option.decision)

    assert [(item.product_id, item.found) for item in found] == [(ids.elovena, True)]


def test_a_product_missing_from_the_catalog_is_said(
    make_stack: Make, make_finder: Make, fake_answers: Make, requests: SimpleNamespace, agent_hotel: Identity,
) -> None:
    option = _elovena_option(make_stack, requests, agent_hotel)
    unknown = "999999999"
    lines = (option.lines[0].model_copy(update={"product_id": unknown}),)
    fired = tuple(rule.model_copy(update={"product_id": unknown}) for rule in option.decision.fired)

    (evidence,) = make_finder(fake_answers({})).for_approval(
        option.model_copy(update={"lines": lines}), option.decision.model_copy(update={"fired": fired})
    )

    assert evidence.sentence == (
        "No evidence was found on the web for product 999999999: the product is not in the catalog."
    )


def test_at_most_three_products_are_looked_up_for_one_approval(
    make_stack: Make, make_finder: Make, fake_answers: Make, requests: SimpleNamespace, agent_hotel: Identity,
    bodies: SimpleNamespace,
) -> None:
    option = _elovena_option(make_stack, requests, agent_hotel)
    answers = fake_answers(bodies.not_found)
    four = ("468465", "469512", "473609", "474864")
    lines = tuple(option.lines[0].model_copy(update={"product_id": pid}) for pid in four)
    fired = tuple(
        option.decision.fired[0].model_copy(update={"product_id": line.product_id}) for line in lines
    )

    found = make_finder(answers).for_approval(
        option.model_copy(update={"lines": lines}), option.decision.model_copy(update={"fired": fired})
    )

    assert len(found) == 4
    assert len(answers.asked) == 3
    assert found[3].sentence == (
        "No evidence was found on the web for product 474864: at most 3 products are looked up for one approval."
    )


def test_without_a_key_the_factory_builds_a_finder_that_asks_nobody(tmp_path: Path, catalog: ProductCatalog) -> None:
    finder = build_evidence_finder(Settings.for_tests(), tmp_path, catalog)
    assert finder is not None and finder._answers is None  # no key: recordings and stored answers only, nobody asked


def test_the_factory_builds_a_finder_over_the_data_directory_and_the_recordings(
    tmp_path: Path, catalog: ProductCatalog, ids: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_call(self: AnswersClient, product: Any) -> None:
        raise AssertionError("a test never calls Context.dev")

    monkeypatch.setattr(AnswersClient, "ask", no_call)
    settings = Settings.for_tests(context_dev_api_key="ctx-test-key-not-real")

    finder = build_evidence_finder(settings, tmp_path, catalog)

    assert isinstance(finder, EvidenceFinder)
    # The demo product is recorded in fixtures/evidence/: it is answered without a call, and nothing is written.
    assert finder.find_evidence(catalog.get_product(ids.elovena)).found
    assert not (tmp_path / "evidence" / f"{ids.elovena}.json").exists()
    finder.close()
