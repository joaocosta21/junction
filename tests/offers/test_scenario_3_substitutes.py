"""Scenario 3 (SPEC section 13): the substitutes Valio lists for 473609, checked against the substitution rule."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from tta.contracts.common import AvailabilityState, DataSource, ExclusionReason, Identity
from tta.contracts.errors import NotAuthorised, UnknownProduct
from tta.contracts.offer import SubstituteCandidate, SubstituteQuery, SubstituteResult
from tta.offers import OfferDeps, OfferService, find_substitutes
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


def test_the_listed_substitute_that_passes_is_ranked_by_its_formula_like_any_other(
    result: SubstituteResult, by_id: dict[str, SubstituteCandidate]
) -> None:
    # 471690 is listed by Valio and its figures are per 100 g against the original's per 100 ml. Both are
    # drinks, so the figures are compared as they stand: fat 1.5 g against 3 g, a different formula. A listed
    # pair gets no exemption from the formula; it comes first here because every other candidate that passes
    # also has a different formula, and it is the one Valio lists.
    passing = [candidate.product_id for candidate in result.candidates if candidate.passes]

    assert passing[0] == PASSES
    assert by_id[PASSES].gives_up.startswith(
        "Not a like-for-like replacement: a different formula (fat 1.5 g, not 3 g). Compared with "
    )
    assert "Different formula: fat 1.5 g, not 3 g, per 100 g against per 100 ml." in by_id[PASSES].gives_up
    # Before, the first three were the same brand's flavoured barista drinks (pumpkin spice, gingerbread, nutty
    # vanilla): the nutrition panel cannot tell a flavour. A flavoured drink no longer replaces a plain one.
    assert not {"472879", "474957", "474724"} & set(by_id)
    assert any("11 flavoured where the original is not" in note for note in result.notes)
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


def test_among_those_that_pass_none_loses_a_dietary_claim_while_a_keeper_can_be_ordered(
    result: SubstituteResult,
) -> None:
    passing = [candidate for candidate in result.candidates if candidate.passes]

    assert passing
    assert not any(candidate.claims_lost for candidate in passing)
    assert any("held back as a last resort" in note for note in result.notes)


def test_tonight_the_best_orderable_substitute_is_the_barista_oat_drink_that_keeps_every_dietary_claim(
    result: SubstituteResult, by_id: dict[str, SubstituteCandidate]
) -> None:
    best = next(candidate for candidate in result.candidates if candidate.orderable)

    # 475224 Fazer Aito Professional Barista Oat drink: gluten-free and vegan like the original; confirmed,
    # +0.37. It lacks FREE_FROM_PRESERVATIVES, which is not a dietary claim: named, and no reason to rank lower.
    assert best.product_id == "475224"
    assert best.claims_lost == ()
    assert str(best.price_difference) == "0.37"
    assert "FREE_FROM_PRESERVATIVES" in best.gives_up
    assert "FREE_FROM_PRESERVATIVES" not in best.sentence
    # 473424 Alpro Rice drink 1 L keeps all three claims and costs more (+0.99): it no longer comes first.
    rice = by_id["473424"]
    assert rice.claims_lost == ()
    assert rice.passes is True and rice.orderable is True
    assert rice.rank > best.rank
    assert by_id[PASSES].claims_lost == ()


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


def test_losing_a_claim_does_not_reorder_the_candidates_that_fail_the_allergen_rule(
    result: SubstituteResult, by_id: dict[str, SubstituteCandidate]
) -> None:
    failing = [candidate.product_id for candidate in result.candidates if not candidate.passes]

    # Claims only order the candidates that pass. Between the two that fail the formula decides: 471881 is the
    # same product in a 0.5 l pack, 464320 another brand that also loses a claim. Neither can be ordered.
    assert by_id["464320"].claims_lost and not by_id["471881"].claims_lost
    assert failing[:2] == ["471881", "464320"]
    assert not by_id["471881"].orderable and not by_id["464320"].orderable


# --- lane L2a-2: the list, the replaceable check and the price per litre -----------------------------------

def test_an_unlisted_candidate_that_fails_the_allergen_rule_is_counted_and_not_shown(
    result: SubstituteResult,
) -> None:
    failing = [candidate for candidate in result.candidates if not candidate.passes]

    # The two Valio lists are shown with the reason; the 29 of the category that add gluten or another
    # allergen take no place in the list (default clock, hotel).
    assert {candidate.product_id for candidate in failing} == set(FAIL)
    assert all(candidate.listed_by_supplier for candidate in failing)
    assert (
        "29 candidates of the same category that Valio does not list fail the allergen rule and are not shown: "
        "each adds an allergen or declares one this buyer excludes."
    ) in result.notes


def test_each_candidate_carries_the_replaceable_check_its_sentence_starts_with(result: SubstituteResult) -> None:
    for candidate in result.candidates:
        assert candidate.replaceable is not None
        assert candidate.gives_up.startswith(candidate.replaceable.sentence)


def test_the_price_difference_per_litre_compares_a_case_with_a_carton(
    by_id: dict[str, SubstituteCandidate]
) -> None:
    case, carton = by_id[PASSES], by_id["475224"]

    # 471690 is a case of 10 litres at EUR 15.55; the original is a 1-litre carton at EUR 1.37.
    assert case.price_difference == Decimal("14.18")  # per sales unit: a case against a carton
    assert case.price_difference_per_requested_unit == Decimal("0.185")  # 1.555 a litre against 1.37
    assert carton.price_difference_per_requested_unit == carton.price_difference == Decimal("0.37")
    assert "it costs €0.19 more per L" in case.gives_up


def test_no_price_difference_per_litre_when_the_two_sizes_are_not_in_the_same_measure(
    fake_gateway: Callable[..., object], deps_for: Callable[..., OfferDeps], policy: object,
    price: Callable[..., object], stock: Callable[..., object],
) -> None:
    # Hand-built: the comparison price of 462775 is per kilogram, the original's per litre. A weight is never
    # turned into a volume, so there is no figure per litre to compare.
    gateway = fake_gateway(
        [price("469363", "2.48"), price("462775", "2.57", measure="KG")],
        [stock("469363", 500), stock("462775", 500)],
    )

    found = find_substitutes("469363", policy.get_profile("hotel-kitchen"), deps_for(gateway), SubstituteQuery())

    other = next(candidate for candidate in found.candidates if candidate.product_id == "462775")
    assert other.price_difference == Decimal("0.09")
    assert other.price_difference_per_requested_unit is None
