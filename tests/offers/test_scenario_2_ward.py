"""Scenario 2 (SPEC section 13): allergy ward, "200 litres of a milk substitute by Monday; no milk, no gluten;
confirmed data only". The path where the agent may order alone."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from tta.allergens import check_exclusions
from tta.catalog import ProductCatalog
from tta.contracts.common import (
    AllergenRelation,
    AllergenStrictness,
    AvailabilityState,
    CheckResult,
    ClaimStatus,
    ConstraintKind,
    ExclusionReason,
    Identity,
    OptionKind,
    Unit,
    Verdict,
)
from tta.contracts.offer import Offer
from tta.contracts.request import ProductQuery
from tta.offers import OfferService

EXCLUDED = ("AM", "AW")


@pytest.fixture(scope="module")
def offer(service: OfferService, make_request: Callable[..., object], agent_ward: Identity) -> Offer:
    request = make_request(
        200, Unit.L, product_type="plant_drink", exclude_allergens=EXCLUDED, require_confirmed=True,
        text="200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only",
    )
    return service.build_offer(request, agent_ward)


def test_every_product_declaring_milk_or_gluten_is_excluded_as_allergen_declared(
    offer: Offer, catalog: ProductCatalog
) -> None:
    candidates = catalog.search(ProductQuery(product_type="plant_drink")).products
    declaring = {
        product.id
        for product in candidates
        if check_exclusions(product.allergen_statements, EXCLUDED, AllergenStrictness.STRICT).declares_excluded
    }
    stated_directly = {
        product.id
        for product in candidates
        for statement in product.allergen_statements
        if statement.code in EXCLUDED and statement.relation is AllergenRelation.CONTAINS
    }
    reasons = {exclusion.product_id: exclusion.reason for exclusion in offer.excluded}

    assert stated_directly and stated_directly <= declaring
    assert "468319" in declaring  # Oatly iKaffe: declares gluten cereals, silent on milk
    for product_id in declaring:  # whatever the product's availability state is
        assert reasons[product_id] is ExclusionReason.ALLERGEN_DECLARED
    assert {pid for pid, reason in reasons.items() if reason is ExclusionReason.ALLERGEN_DECLARED} == declaring


def test_there_is_one_option_and_it_covers_the_whole_quantity(offer: Offer) -> None:
    assert len(offer.options) == 1
    option = offer.options[0]

    assert option.kind is OptionKind.BEST_CONFIRMED
    assert option.fill_ratio == 1
    assert option.coverage[0].fill_ratio == 1
    assert option.coverage[0].covered == Decimal(200)
    assert option.coverage[0].missing == 0
    assert option.coverage[0].unit is Unit.L


def test_the_chosen_product_states_free_from_for_both_allergens(offer: Offer, catalog: ProductCatalog) -> None:
    for line in offer.options[0].lines:
        check = line.allergen_check
        stated = {
            statement.code: statement.relation for statement in catalog.get_product(line.product_id).allergen_statements
        }

        assert check is not None
        assert check.strictness is AllergenStrictness.STRICT
        assert {finding.excluded_code: finding.relation for finding in check.findings} == {
            "AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.FREE_FROM,
        }
        assert stated["AM"] is AllergenRelation.FREE_FROM
        assert stated["AW"] is AllergenRelation.FREE_FROM


def test_every_claim_the_order_depends_on_is_confirmed(offer: Offer) -> None:
    option = offer.options[0]

    assert all(line.confirmed_for_order(dated=True) for line in option.lines)
    assert all(line.availability.state is AvailabilityState.CONFIRMED for line in option.lines)
    confirmed_only = [check for check in option.constraint_checks if check.kind is ConstraintKind.CONFIRMED_ONLY]
    assert [check.result for check in confirmed_only] == [CheckResult.MET]


def test_each_excluded_allergen_has_a_met_constraint_check(offer: Offer) -> None:
    allergen_checks = {
        check.subject: check.result
        for check in offer.options[0].constraint_checks
        if check.kind is ConstraintKind.ALLERGEN
    }

    assert allergen_checks == {"AM": CheckResult.MET, "AW": CheckResult.MET}


def test_products_with_unsettled_allergen_data_are_left_out_under_confirmed_only(offer: Offer) -> None:
    reasons = {exclusion.product_id: exclusion for exclusion in offer.excluded}

    # 469512 Elovena oat drink barista: declares oats, silent on milk. Confirmed in stock and cheaper.
    assert reasons["469512"].reason is ExclusionReason.ALLERGEN_NOT_STATED
    assert "confirmed data only" in reasons["469512"].sentence.lower()
    for line in offer.options[0].lines:
        allergens = next(check for check in line.claims if check.claim.value == "allergens")
        assert allergens.status is ClaimStatus.CONFIRMED


def test_the_agent_may_order_alone(offer: Offer) -> None:
    decision = offer.options[0].decision

    assert decision is not None
    assert decision.verdict is Verdict.AUTO
    assert decision.fired == ()
    assert decision.required_roles == ()


def test_the_profile_alone_makes_the_offer_confirmed_only(
    service: OfferService, make_request: Callable[..., object], agent_ward: Identity
) -> None:
    request = make_request(200, Unit.L, product_type="plant_drink", require_confirmed=False)

    offer = service.build_offer(request, agent_ward)

    assert [option.kind for option in offer.options] == [OptionKind.BEST_CONFIRMED]
    assert any(exclusion.reason is ExclusionReason.ALLERGEN_NOT_STATED for exclusion in offer.excluded)
    assert any(
        check.kind is ConstraintKind.CONFIRMED_ONLY and check.result is CheckResult.MET
        for check in offer.options[0].constraint_checks
    )


def test_tonight_the_cheapest_confirmed_product_that_covers_200_litres_is_chosen(offer: Offer) -> None:
    lines = offer.options[0].lines

    # 464013 Alpro No Sugars Soya drink 1 L: 478 confirmed at 2.01. Friday's 464056 (2.14) is dearer tonight.
    assert [(line.product_id, line.quantity, line.unit_net_price) for line in lines] == [
        ("464013", Decimal(200), Decimal("2.01"))
    ]
    assert offer.options[0].totals.net == Decimal("402.00")
