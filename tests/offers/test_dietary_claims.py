"""Which lost claims count: the dietary ones order the substitutes and reach rule F-08; the others are named."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tta.catalog import ProductCatalog
from tta.contracts.common import Identity, OptionKind, Unit, Verdict
from tta.contracts.offer import SubstituteQuery
from tta.offers import OfferDeps, OfferService, find_substitutes
from tta.offers.substitutes import DIETARY_CLAIMS, claims_lost

ORIGINAL = "473609"  # Oddlygood Barista oat drink: FREE_FROM_GLUTEN, FREE_FROM_PRESERVATIVES, VEGAN
BARISTA_OAT = "475224"  # lacks FREE_FROM_PRESERVATIVES only
RICE = "473424"  # keeps every claim of the original
ALMOND = "465793"  # Alpro Barista Almond drink: lacks VEGAN (dietary) and FREE_FROM_PRESERVATIVES (not dietary)
REGULAR_MILK = "463149"  # neither gluten-free nor vegan


def test_only_dietary_claims_count_as_lost(catalog: ProductCatalog) -> None:
    oat_barista = catalog.get_product(ORIGINAL)

    assert frozenset(
        {"FREE_FROM_LACTOSE", "LOW_LACTOSE", "FREE_FROM_GLUTEN", "FREE_FROM_WHEAT", "FREE_FROM_EGGS",
         "FREE_FROM_SOY", "VEGAN", "VEGETARIAN"}
    ) == DIETARY_CLAIMS
    assert claims_lost(oat_barista, catalog.get_product(BARISTA_OAT)) == ()
    assert claims_lost(oat_barista, catalog.get_product("464320")) == ("FREE_FROM_GLUTEN",)  # and preservatives
    assert claims_lost(oat_barista, catalog.get_product(REGULAR_MILK)) == ("FREE_FROM_GLUTEN", "VEGAN")


def test_a_claim_that_is_not_dietary_is_named_and_changes_neither_rank_nor_verdict(
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], policy: Any, price: Any, stock: Any,
    make_request: Any, agent_hotel: Identity,
) -> None:
    # The barista oat drink is cheaper; the rice drink keeps every claim. Preservatives do not decide.
    prices = [price(ORIGINAL, "1.37"), price(BARISTA_OAT, "1.74"), price(RICE, "2.36"), price(ALMOND, "1.20")]
    lines = [stock(ORIGINAL, None), stock(BARISTA_OAT, 500), stock(RICE, 500), stock(ALMOND, 500)]
    deps = deps_for(fake_gateway(prices, lines))

    result = find_substitutes(ORIGINAL, policy.get_profile("hotel-kitchen"), deps, SubstituteQuery())
    offer = OfferService(deps).build_offer(make_request(100, Unit.L, product_ids=(ORIGINAL,)), agent_hotel)

    orderable = [candidate for candidate in result.candidates if candidate.orderable]
    # The almond drink is the cheapest and comes last: it loses a dietary claim.
    assert [(candidate.product_id, candidate.claims_lost) for candidate in orderable] == [
        (BARISTA_OAT, ()), (RICE, ()), (ALMOND, ("VEGAN",)),
    ]
    assert "FREE_FROM_PRESERVATIVES" in orderable[0].gives_up
    assert "FREE_FROM_PRESERVATIVES" not in orderable[0].sentence
    almond = orderable[2]
    assert "claims FREE_FROM_PRESERVATIVES, VEGAN" in almond.gives_up  # everything given up is named
    assert "claim VEGAN" in almond.sentence  # the sentence names what changes the rank and the verdict
    assert "FREE_FROM_PRESERVATIVES" not in almond.sentence
    option = next(each for each in offer.options if each.kind is OptionKind.SUBSTITUTE)
    assert [(line.product_id, line.substitute.claims_lost) for line in option.lines] == [(BARISTA_OAT, ())]
    assert "FREE_FROM_PRESERVATIVES" in option.lines[0].substitute.gives_up
    assert option.decision.verdict is Verdict.AUTO
    assert "F-08" not in option.decision.rule_ids
