"""A product outside the recorded copy of Valio's data is never stated as something Valio said (FIX-12a).

Tonight's capture holds categories 104xx and 18720 and five ids: 769 of the 17,546 catalog products. It joins the
recording `2026-11-14-baking` of the same Saturday (394 products: butter, eggs, flour, sugar, cocoa, baking aids;
task CK), so replay answers for 1,163. Every other product reads as `NOT_IN_RECORDING`, never as `NOT_DELIVERABLE`
(SPEC section 5). The tests used butter until it was recorded; cheese (categories 10600, 10602, 10603) is in
neither recording.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from decimal import Decimal

import pytest

from tta.allergens import check_exclusions
from tta.catalog import ProductCatalog
from tta.contracts.common import (
    AllergenStrictness,
    ClaimStatus,
    ExclusionReason,
    Identity,
    OptionKind,
    Unit,
    Verdict,
)
from tta.contracts.offer import Offer, SubstituteQuery
from tta.contracts.request import ProductQuery
from tta.offers import OfferService

NOT_IN_RECORDING_SENTENCE = (
    "Not in the recorded copy of Valio's data used for this demo; a live lookup would answer."
)
CHEESES = 295  # the `cheese` product type; none is in either recording
CHEESE = "460217"  # 20 x Arla Apetina Original white salad cheese bit 200 g
BUTTER = "464411"  # Valio butter 500 g unsalted: in the joined baking recording
Build = Callable[..., object]


@pytest.fixture(scope="module")
def cheese_offer(service: OfferService, make_request: Build, agent_hotel: Identity) -> Offer:
    request = make_request(10, Unit.KG, product_type="cheese", text="10 kg cheese by Monday")
    return service.build_offer(request, agent_hotel)


def test_cheese_in_replay_is_excluded_as_not_in_the_recording_only(cheese_offer: Offer) -> None:
    """4 of the 295 cheeses are portion packs, a fact of the product file that comes before the recording (a bulk
    request leaves them out for that); the other 291 read as not in the recording, and nothing else."""
    assert cheese_offer.options == ()
    assert len(cheese_offer.excluded) == CHEESES
    counts = Counter(exclusion.reason for exclusion in cheese_offer.excluded)
    assert counts == {ExclusionReason.NOT_IN_RECORDING: 291, ExclusionReason.PORTION_PACK: 4}
    outside = [each for each in cheese_offer.excluded if each.reason is ExclusionReason.NOT_IN_RECORDING]
    assert {exclusion.sentence for exclusion in outside} == {NOT_IN_RECORDING_SENTENCE}


def test_butter_is_answered_from_the_joined_recording_and_no_longer_reads_as_outside_it(
    service: OfferService, make_request: Build, agent_hotel: Identity
) -> None:
    """Task CK: a product only the later recording holds is offered like any other."""
    offer = service.build_offer(make_request(10, Unit.KG, product_type="butter", text="10 kg butter"), agent_hotel)

    assert ExclusionReason.NOT_IN_RECORDING not in {exclusion.reason for exclusion in offer.excluded}
    assert BUTTER in {line.product_id for option in offer.options for line in option.lines}


def test_nothing_about_cheese_is_said_in_valios_name(cheese_offer: Offer) -> None:
    sentences = [exclusion.sentence for exclusion in cheese_offer.excluded]

    assert not any("Valio cannot" in sentence or "Valio returned" in sentence for sentence in sentences)


def test_a_fact_of_the_product_file_still_comes_before_the_recording(
    service: OfferService, make_request: Build, agent_ward: Identity, catalog: ProductCatalog
) -> None:
    # The ward excludes milk. A cheese that declares milk is rejected for that, whatever the recording holds;
    # only the others read as not in the recording.
    request = make_request(10, Unit.KG, product_type="cheese", require_confirmed=True, text="10 kg cheese")
    declares_milk = {
        product.id
        for product in catalog.search(ProductQuery(product_type="cheese", limit=1000)).products
        if check_exclusions(product.allergen_statements, ("AM", "AW"), AllergenStrictness.STRICT).declares_excluded
    }

    offer = service.build_offer(request, agent_ward)

    reasons = {exclusion.product_id: exclusion.reason for exclusion in offer.excluded}
    assert offer.options == ()
    assert CHEESE in declares_milk
    assert {product_id for product_id, reason in reasons.items() if reason is ExclusionReason.ALLERGEN_DECLARED} == (
        declares_milk
    )
    assert set(reasons.values()) == {ExclusionReason.ALLERGEN_DECLARED, ExclusionReason.NOT_IN_RECORDING}


def test_substitutes_outside_the_recording_say_so_and_are_not_ruled_out(
    service: OfferService, agent_hotel: Identity
) -> None:
    result = service.find_substitutes(CHEESE, agent_hotel, SubstituteQuery(quantity=Decimal(10), unit=Unit.KG))

    assert result.candidates
    for candidate in result.candidates:
        assert candidate.orderable is False
        assert candidate.reason is ExclusionReason.NOT_IN_RECORDING
        assert candidate.availability is not None
        assert candidate.availability.sentence == NOT_IN_RECORDING_SENTENCE
        claims = {claim.claim.value: claim for claim in candidate.claims}
        for name in ("price", "quantity", "delivery_date"):
            assert claims[name].status is ClaimStatus.UNKNOWN, (candidate.product_id, name)
            assert claims[name].sentence == NOT_IN_RECORDING_SENTENCE


def test_scenario_1_keeps_its_exclusions_and_its_confirmed_option(
    service: OfferService, make_request: Build, agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(1000, text="1,000 litres of lactose-free milk by Monday"), agent_hotel)

    counts = Counter(exclusion.reason for exclusion in offer.excluded)
    assert counts == {
        ExclusionReason.CUTOFF_PASSED: 15, ExclusionReason.PORTION_PACK: 1, ExclusionReason.NOT_DELIVERABLE: 1,
    }
    best = offer.options[0]
    assert best.kind is OptionKind.BEST_CONFIRMED
    assert best.totals.net == Decimal("1083.39")  # 435 L: no coffee milk in a request for milk since 14 Nov


def test_scenario_2_is_unchanged(service: OfferService, make_request: Build, agent_ward: Identity) -> None:
    request = make_request(
        200, Unit.L, product_type="plant_drink", exclude_allergens=("AM", "AW"), require_confirmed=True,
        text="200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only",
    )

    offer = service.build_offer(request, agent_ward)

    counts = Counter(exclusion.reason for exclusion in offer.excluded)
    assert counts == {
        ExclusionReason.ALLERGEN_DECLARED: 18, ExclusionReason.CUTOFF_PASSED: 12,
        ExclusionReason.NOT_DELIVERABLE: 6, ExclusionReason.ALLERGEN_NOT_STATED: 5,
    }
    (option,) = offer.options
    assert [(line.product_id, line.quantity) for line in option.lines] == [("464013", Decimal(200))]
    assert option.totals.net == Decimal("402.00")
    assert option.decision is not None and option.decision.verdict is Verdict.APPROVAL


def test_scenario_3_reads_nothing_outside_the_recording(
    service: OfferService, make_request: Build, agent_hotel: Identity
) -> None:
    request = make_request(100, Unit.L, product_ids=("473609",), text="100 litres of Oddlygood Barista oat drink")

    offer = service.build_offer(request, agent_hotel)
    substitutes = service.find_substitutes("473609", agent_hotel, SubstituteQuery())

    assert ExclusionReason.NOT_IN_RECORDING not in {exclusion.reason for exclusion in offer.excluded}
    assert ExclusionReason.NOT_IN_RECORDING not in {candidate.reason for candidate in substitutes.candidates}
    substitute = next(option for option in offer.options if option.kind is OptionKind.SUBSTITUTE)
    assert [line.product_id for line in substitute.lines] == ["475224"]
    assert substitute.totals.net == Decimal("174.00")
