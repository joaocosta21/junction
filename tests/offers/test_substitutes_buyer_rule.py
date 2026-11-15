"""FIX-12b: the substitute list judges each candidate by the buyer's own rules, as the buyer's offer would.

Use case 5 of AIMO/USE-CASES.md: as the allergy ward, `POST /v1/products/473609/substitutes` said "passes: true,
orderable: true" for 475224, which the ward's own offer excludes as ALLERGEN_NOT_STATED.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from tta.contracts.common import AvailabilityState, ExclusionReason, Identity, Unit
from tta.contracts.offer import SubstituteCandidate, SubstituteQuery, SubstituteResult
from tta.contracts.request import PurchaseRequest
from tta.offers import OfferDeps, OfferService
from tta.offers.substitutes import find_substitutes
from tta.policy import RulePolicyEngine

ORIGINAL = "473609"  # an oat drink the ward cannot order: it states nothing about milk
NOT_STATED = "475224"  # states nothing about milk or gluten; the hotel's chosen substitute in scenario 3
DIETITIAN = "a person must decide"


@pytest.fixture(scope="module")
def ward_result(service: OfferService, agent_ward: Identity) -> SubstituteResult:
    return service.find_substitutes(ORIGINAL, agent_ward, SubstituteQuery())


@pytest.fixture(scope="module")
def ward(ward_result: SubstituteResult) -> dict[str, SubstituteCandidate]:
    return {candidate.product_id: candidate for candidate in ward_result.candidates}


def test_a_candidate_the_wards_offer_excludes_cannot_be_ordered_from_the_list_and_says_why_in_the_same_words(
    ward: dict[str, SubstituteCandidate], service: OfferService, agent_ward: Identity,
    make_request: Callable[..., PurchaseRequest],
) -> None:
    offer = service.build_offer(make_request(100, needed_by=None, product_ids=(NOT_STATED,)), agent_ward)
    excluded = next(each for each in offer.excluded if each.product_id == NOT_STATED)
    candidate = ward[NOT_STATED]

    assert excluded.reason is ExclusionReason.ALLERGEN_NOT_STATED
    assert candidate.orderable is False
    assert candidate.reason is ExclusionReason.ALLERGEN_NOT_STATED
    assert excluded.sentence in candidate.sentence
    assert candidate.passes is True  # it adds no allergen: the substitution rule holds, the buyer's rule does not


def test_under_the_wards_confirmed_only_no_candidate_with_an_unconfirmed_quantity_can_be_ordered(
    ward: dict[str, SubstituteCandidate],
) -> None:
    unconfirmed = [
        candidate for candidate in ward.values()
        if candidate.availability is not None
        and candidate.availability.state is AvailabilityState.QUANTITY_NOT_CONFIRMED
    ]

    assert all(not candidate.orderable and candidate.reason is not None for candidate in unconfirmed)


def test_every_candidate_the_ward_can_order_from_the_list_is_kept_by_the_wards_own_offer(
    ward: dict[str, SubstituteCandidate], service: OfferService, agent_ward: Identity,
    make_request: Callable[..., PurchaseRequest],
) -> None:
    orderable = [candidate.product_id for candidate in ward.values() if candidate.orderable]

    for product_id in orderable:
        offer = service.build_offer(make_request(1, Unit.UNIT, needed_by=None, product_ids=(product_id,)), agent_ward)
        assert product_id not in {each.product_id for each in offer.excluded}, product_id
    assert NOT_STATED not in orderable


def test_a_candidate_that_would_go_to_a_dietitian_says_so(
    replay_deps: OfferDeps, policy: RulePolicyEngine
) -> None:
    # The ward's allergen rule without its confirmed-only setting: a product that states nothing about an
    # excluded allergen is then offered, and goes to the dietitian (rule P-04).
    profile = policy.get_profile("allergy-ward").model_copy(update={"require_confirmed": False})

    result = find_substitutes(ORIGINAL, profile, replay_deps, SubstituteQuery(quantity=Decimal(100), unit=Unit.L))
    candidate = next(each for each in result.candidates if each.product_id == NOT_STATED)

    assert candidate.orderable is True
    assert DIETITIAN in candidate.sentence


def test_the_hotel_which_excludes_nothing_and_accepts_unconfirmed_data_reads_the_list_as_before(
    service: OfferService, agent_hotel: Identity
) -> None:
    result = service.find_substitutes(ORIGINAL, agent_hotel, SubstituteQuery())
    hotel = {candidate.product_id: candidate for candidate in result.candidates}

    assert hotel[NOT_STATED].orderable is True
    assert hotel[NOT_STATED].reason is None
    assert DIETITIAN not in hotel[NOT_STATED].sentence
