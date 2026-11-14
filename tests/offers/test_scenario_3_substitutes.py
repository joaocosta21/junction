"""Scenario 3 (SPEC section 13): the substitutes Valio lists for 473609, checked against the substitution rule."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tta.contracts.common import AvailabilityState, DataSource, ExclusionReason, Identity
from tta.contracts.errors import NotAuthorised, UnknownProduct
from tta.contracts.offer import SubstituteCandidate, SubstituteQuery, SubstituteResult
from tta.offers import OfferDeps, OfferService
from tta.offers.substitutes import MAX_UNLISTED_SHOWN

ORIGINAL = "473609"
PASSES = "471690"
FAIL = ("471881", "464320")


@pytest.fixture(scope="module")
def result(service: OfferService, agent_hotel: Identity) -> SubstituteResult:
    return service.find_substitutes(ORIGINAL, agent_hotel, SubstituteQuery())


@pytest.fixture(scope="module")
def by_id(result: SubstituteResult) -> dict[str, SubstituteCandidate]:
    return {candidate.product_id: candidate for candidate in result.candidates}


def test_the_listed_substitute_that_adds_no_allergen_passes(by_id: dict[str, SubstituteCandidate]) -> None:
    candidate = by_id[PASSES]

    assert candidate.passes is True
    assert candidate.listed_by_supplier is True
    assert candidate.allergen_check.passes is True
    assert candidate.allergen_check.added == ()


@pytest.mark.parametrize("product_id", FAIL)
def test_a_listed_substitute_that_adds_gluten_fails_and_cannot_be_ordered(
    by_id: dict[str, SubstituteCandidate], product_id: str
) -> None:
    candidate = by_id[product_id]

    assert candidate.passes is False
    assert candidate.orderable is False
    assert candidate.reason is ExclusionReason.SUBSTITUTE_ADDS_ALLERGEN
    assert [statement.code for statement in candidate.allergen_check.added] == ["AW"]
    assert "AW" in candidate.sentence
    assert candidate.listed_by_supplier is True


def test_a_failure_stays_unorderable_even_when_it_is_confirmed_in_stock(by_id: dict[str, SubstituteCandidate]) -> None:
    oatly = by_id["464320"]

    assert oatly.availability is not None
    assert oatly.availability.state is AvailabilityState.CONFIRMED  # 39,243 units tonight
    assert oatly.orderable is False


def test_candidates_are_ranked_passing_first_with_a_sentence_each(result: SubstituteResult) -> None:
    candidates = result.candidates

    assert [candidate.rank for candidate in candidates] == list(range(1, len(candidates) + 1))
    passes = [candidate.passes for candidate in candidates]
    assert passes == sorted(passes, reverse=True)
    for candidate in candidates:
        assert candidate.sentence.strip()
        assert candidate.gives_up.strip()
        assert len(candidate.claims) == 5
        assert candidate.orderable is (candidate.reason is None)
        if not candidate.passes:
            assert candidate.orderable is False
    assert ORIGINAL not in {candidate.product_id for candidate in candidates}


def test_the_listed_substitute_that_passes_ranks_first(result: SubstituteResult) -> None:
    assert result.candidates[0].product_id == PASSES
    assert result.original_id == ORIGINAL
    assert result.original_name
    assert result.source is DataSource.REPLAY


def test_tonight_the_passing_listed_substitute_is_past_its_cut_off(by_id: dict[str, SubstituteCandidate]) -> None:
    candidate = by_id[PASSES]

    assert candidate.availability is not None
    assert candidate.availability.state is AvailabilityState.CUTOFF_PASSED
    assert candidate.orderable is False
    assert candidate.reason is ExclusionReason.CUTOFF_PASSED


def test_the_search_widens_to_the_category_when_no_listed_substitute_can_be_ordered(
    result: SubstituteResult,
) -> None:
    unlisted = [candidate for candidate in result.candidates if not candidate.listed_by_supplier]
    orderable = [candidate for candidate in result.candidates if candidate.orderable]

    assert {candidate.product_id for candidate in result.candidates if candidate.listed_by_supplier} == {
        PASSES, *FAIL
    }
    assert 0 < len(unlisted) <= MAX_UNLISTED_SHOWN
    assert all(candidate.category_distance == 0 for candidate in unlisted)
    assert orderable
    assert all(candidate.passes for candidate in orderable)
    assert result.notes


def test_tonight_the_best_orderable_substitute_is_a_gluten_free_barista_oat_drink(result: SubstituteResult) -> None:
    best = next(candidate for candidate in result.candidates if candidate.orderable)

    # 475224 Fazer Aito Professional Barista Oat drink, gluten-free: 1 L like the original, confirmed, +0.37.
    assert best.product_id == "475224"
    assert best.price_difference is not None
    assert str(best.price_difference) == "0.37"


def test_substitutes_cost_one_price_call_and_one_availability_call(
    replay: object, counting: Callable[..., object], deps_for: Callable[..., OfferDeps], agent_hotel: Identity
) -> None:
    gateway = counting(replay)

    OfferService(deps_for(gateway)).find_substitutes(ORIGINAL, agent_hotel, SubstituteQuery())

    assert sorted(endpoint for endpoint, _, _ in gateway.calls) == ["availability", "price"]


def test_an_unknown_product_is_reported_as_unknown(service: OfferService, agent_hotel: Identity) -> None:
    with pytest.raises(UnknownProduct):
        service.find_substitutes("000000", agent_hotel, SubstituteQuery())


def test_a_caller_without_a_buyer_profile_gets_no_substitutes(
    service: OfferService, supplier_reader: Identity
) -> None:
    with pytest.raises(NotAuthorised):
        service.find_substitutes(ORIGINAL, supplier_reader, SubstituteQuery())


def test_the_buyers_own_exclusions_also_fail_a_substitute(service: OfferService, agent_ward: Identity) -> None:
    result = service.find_substitutes(ORIGINAL, agent_ward, SubstituteQuery())
    by_product = {candidate.product_id: candidate for candidate in result.candidates}

    # 464320 adds gluten cereals: the substitution rule is named first. No candidate that declares
    # an allergen the ward excludes can be ordered.
    assert by_product["464320"].reason is ExclusionReason.SUBSTITUTE_ADDS_ALLERGEN
    for candidate in result.candidates:
        if candidate.reason is ExclusionReason.ALLERGEN_DECLARED:
            assert candidate.passes is False
            assert candidate.orderable is False
