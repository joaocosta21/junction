"""The offer reads the product's own ingredient list as a statement (SPEC section 6; FIX-12a).

465793, Alpro Barista Almond drink, states tree nuts (AN) FREE_FROM, while its ingredient list names ALMOND
and says "MAY CONTAIN REMAINS FROM NUTS". Before this fix the ward's offer for it was AUTO, €47.60
(AIMO/USE-CASES.md, use case 5, hole 1).
"""

from __future__ import annotations

from collections.abc import Callable

from tta.contracts.common import (
    AllergenOutcome,
    AllergenRelation,
    AllergenStrictness,
    ApproverRole,
    ClaimName,
    ClaimStatus,
    ExclusionReason,
    Identity,
    Unit,
    Verdict,
)
from tta.offers import OfferService

ALMOND_DRINK = "465793"
Build = Callable[..., object]


def _request(make_request: Build, **extra: object) -> object:
    return make_request(
        20, Unit.L, product_ids=(ALMOND_DRINK,), exclude_allergens=("AN",),
        allergen_strictness=AllergenStrictness.STRICT, text="20 litres of the almond drink, no tree nuts", **extra,
    )


def test_the_almond_drink_goes_to_a_dietitian_and_is_never_ordered_alone(
    service: OfferService, make_request: Build, agent_hotel: Identity
) -> None:
    offer = service.build_offer(_request(make_request), agent_hotel)

    with_it = [option for option in offer.options if ALMOND_DRINK in {line.product_id for line in option.lines}]
    assert with_it
    for option in with_it:
        assert option.decision is not None
        assert option.decision.verdict is not Verdict.AUTO
        assert ApproverRole.DIETITIAN in option.decision.required_roles
        assert "P-04" in option.decision.rule_ids
        line = next(line for line in option.lines if line.product_id == ALMOND_DRINK)
        claims = {claim.claim: claim for claim in line.claims}
        assert claims[ClaimName.ALLERGENS].status is ClaimStatus.UNKNOWN


def test_the_finding_quotes_the_ingredient_words_and_the_declaration(
    service: OfferService, make_request: Build, agent_hotel: Identity
) -> None:
    offer = service.build_offer(_request(make_request), agent_hotel)

    line = next(line for option in offer.options for line in option.lines if line.product_id == ALMOND_DRINK)
    assert line.allergen_check is not None
    (finding,) = line.allergen_check.findings
    assert finding.outcome is AllergenOutcome.TO_HUMAN
    assert finding.relation is AllergenRelation.MAY_CONTAIN
    assert '"ALMOND"' in finding.sentence
    assert "MAY CONTAIN REMAINS FROM NUTS" in finding.sentence
    assert "states it is free from tree nuts (AN)" in finding.sentence


def test_under_confirmed_only_the_ward_excludes_it_with_the_same_sentence(
    service: OfferService, make_request: Build, agent_ward: Identity
) -> None:
    offer = service.build_offer(_request(make_request, require_confirmed=True), agent_ward)

    assert not any(
        option.decision is not None and option.decision.verdict is Verdict.AUTO
        for option in offer.options
        if ALMOND_DRINK in {line.product_id for line in option.lines}
    )
    exclusion = next(exclusion for exclusion in offer.excluded if exclusion.product_id == ALMOND_DRINK)
    assert exclusion.reason is ExclusionReason.ALLERGEN_NOT_STATED
    assert '"ALMOND"' in exclusion.sentence
