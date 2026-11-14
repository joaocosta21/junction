"""P9b B7-1 with D4: a substitute that loses a dietary claim is a last resort.

Valio, answer B7 (14 Nov 2026): "yes and only in the last case"; clarified at 14:51: only when every product
that keeps the dietary restriction is gone, and "it is better to not have gluten if you are unsure". So a
claim-losing candidate is held back while one that keeps every dietary claim can be ordered, and when it is
shown it still goes to a human (rule F-08). The safe product wins.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import Any

from tta.catalog import ProductCatalog
from tta.contracts.common import Identity, OptionKind, Unit, Verdict
from tta.contracts.offer import SubstituteQuery
from tta.contracts.product import Product
from tta.offers import OfferDeps, OfferService, find_substitutes
from tta.offers.substitute_wording import LAST_RESORT
from tta.offers.substitutes import COVERED_BY, claims_lost, claims_not_carried

ORIGINAL = "473609"  # Oddlygood Barista oat drink: FREE_FROM_GLUTEN, FREE_FROM_PRESERVATIVES, VEGAN
BARISTA_OAT = "475224"  # keeps both dietary claims
ALMOND = "465793"  # Alpro Barista Almond drink: lacks VEGAN
LACTOSE_FREE_MILK = "469363"
LOW_LACTOSE_MILK = "463047"  # Arla whole milk, LOW_LACTOSE
REGULAR_MILK = "463149"


def _product(*claims: str) -> Product:
    return Product(
        id="1", category="10402", sales_unit="ST", base_unit="ST", allowed_lot_size=Decimal(1),
        nutritional_claims=claims,
    )


def test_lactose_free_keeps_low_lactose_and_vegan_keeps_vegetarian_and_nothing_else_is_covered() -> None:
    assert {"LOW_LACTOSE": frozenset({"FREE_FROM_LACTOSE"}), "VEGETARIAN": frozenset({"VEGAN"})} == COVERED_BY
    assert claims_lost(_product("LOW_LACTOSE"), _product("FREE_FROM_LACTOSE")) == ()
    assert claims_lost(_product("VEGETARIAN"), _product("VEGAN")) == ()
    assert claims_not_carried(_product("LOW_LACTOSE", "VEGETARIAN"), _product("FREE_FROM_LACTOSE", "VEGAN")) == ()
    # The cover goes one way only, and gluten-free does not cover wheat-free.
    assert claims_lost(_product("FREE_FROM_LACTOSE"), _product("LOW_LACTOSE")) == ("FREE_FROM_LACTOSE",)
    assert claims_lost(_product("VEGAN"), _product("VEGETARIAN")) == ("VEGAN",)
    assert claims_lost(_product("FREE_FROM_WHEAT"), _product("FREE_FROM_GLUTEN")) == ("FREE_FROM_WHEAT",)
    assert claims_lost(_product("FREE_FROM_GLUTEN"), _product("FREE_FROM_WHEAT")) == ("FREE_FROM_GLUTEN",)


def test_a_lactose_free_milk_does_not_lose_the_low_lactose_claim_of_the_milk_it_replaces(
    catalog: ProductCatalog,
) -> None:
    low, free = catalog.get_product(LOW_LACTOSE_MILK), catalog.get_product(LACTOSE_FREE_MILK)

    assert "LOW_LACTOSE" in low.nutritional_claims and "LOW_LACTOSE" not in free.nutritional_claims
    assert claims_lost(low, free) == ()  # before: ("LOW_LACTOSE",), a needless F-08 approval
    assert claims_lost(low, catalog.get_product(REGULAR_MILK)) == ("LOW_LACTOSE",)


def test_the_safer_lactose_free_milk_is_offered_for_a_low_lactose_one_and_not_held_back(
    service: OfferService, agent_hotel: Identity
) -> None:
    result = service.find_substitutes(LOW_LACTOSE_MILK, agent_hotel, SubstituteQuery())

    by_id = {candidate.product_id: candidate for candidate in result.candidates}
    assert by_id[LACTOSE_FREE_MILK].orderable and by_id[LACTOSE_FREE_MILK].claims_lost == ()
    assert "LOW_LACTOSE" not in by_id[LACTOSE_FREE_MILK].gives_up
    assert all(not candidate.claims_lost for candidate in result.candidates if candidate.passes)


def test_while_a_keeper_can_be_ordered_no_claim_losing_candidate_is_shown(
    service: OfferService, agent_hotel: Identity
) -> None:
    result = service.find_substitutes(ORIGINAL, agent_hotel, SubstituteQuery())

    passing = [candidate for candidate in result.candidates if candidate.passes]
    keepers = [candidate.product_id for candidate in result.candidates if candidate.orderable]
    # Default clock: before, 5 claim-losing candidates were shown as orderable beside the keepers (465793 lacks
    # VEGAN; 468359, 468887, 460394 and 462322 lack FREE_FROM_GLUTEN).
    assert all(candidate.claims_lost == () for candidate in passing)
    assert keepers == ["475224", "469512", "473424", "468465"]
    assert not {"465793", "468359", "468887", "460394", "462322"} & {each.product_id for each in result.candidates}
    assert (
        "13 candidates that lack a dietary claim of the original are held back as a last resort: 4 that keep "
        "every dietary claim can be ordered."
    ) in result.notes
    assert not any(LAST_RESORT in candidate.sentence for candidate in result.candidates)
    # A candidate that fails the allergen rule is not held back: it is shown with its reason and cannot be ordered.
    oatly = next(candidate for candidate in result.candidates if candidate.product_id == "464320")
    assert oatly.claims_lost == ("FREE_FROM_GLUTEN",) and not oatly.orderable


def test_one_held_back_candidate_is_said_in_the_singular(
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], policy: Any, price: Any, stock: Any,
    catalog: ProductCatalog,
) -> None:
    class TwoCandidates:
        """The real catalog, with a category of two candidates."""

        def __getattr__(self, name: str) -> Any:
            return getattr(catalog, name)

        def same_category(self, product_id: str, digits: int = 5) -> tuple[Product, ...]:
            return tuple(catalog.get_product(each) for each in (BARISTA_OAT, ALMOND))

        def listed_substitutes(self, product_id: str) -> tuple[str, ...]:
            return ()

    gateway = fake_gateway(
        [price(ORIGINAL, "1.37"), price(BARISTA_OAT, "1.74"), price(ALMOND, "1.20")],
        [stock(ORIGINAL, None), stock(BARISTA_OAT, 500), stock(ALMOND, 500)],
    )
    deps = replace(deps_for(gateway), catalog=TwoCandidates())

    result = find_substitutes(ORIGINAL, policy.get_profile("hotel-kitchen"), deps, SubstituteQuery())

    assert [candidate.product_id for candidate in result.candidates] == [BARISTA_OAT]
    assert (
        "1 candidate that lacks a dietary claim of the original is held back as a last resort: 1 that keeps "
        "every dietary claim can be ordered."
    ) in result.notes


def test_when_no_keeper_can_be_ordered_the_loser_is_shown_as_a_last_resort_and_goes_to_a_person(
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], policy: Any, price: Any, stock: Any,
    make_request: Callable[..., Any], agent_hotel: Identity,
) -> None:
    # Only the almond drink can be had: every candidate that keeps VEGAN and FREE_FROM_GLUTEN has no schedule line.
    deps = deps_for(fake_gateway([price(ORIGINAL, "1.37"), price(ALMOND, "1.20")],
                                 [stock(ORIGINAL, None), stock(ALMOND, 500)]))

    result = find_substitutes(ORIGINAL, policy.get_profile("hotel-kitchen"), deps, SubstituteQuery())
    offer = OfferService(deps).build_offer(make_request(100, Unit.L, product_ids=(ORIGINAL,)), agent_hotel)

    orderable = [candidate for candidate in result.candidates if candidate.orderable]
    assert [(candidate.product_id, candidate.claims_lost) for candidate in orderable] == [(ALMOND, ("VEGAN",))]
    assert orderable[0].sentence.endswith(
        "It does not carry the original's nutritional claim VEGAN. Last resort: no candidate that keeps every "
        "dietary claim of the original can be ordered, so a person decides whether this one will do."
    )
    assert not any("held back" in note for note in result.notes)
    option = next(each for each in offer.options if each.kind is OptionKind.SUBSTITUTE)
    assert [(line.product_id, line.substitute.claims_lost) for line in option.lines] == [(ALMOND, ("VEGAN",))]
    assert option.decision.verdict is Verdict.APPROVAL
    assert "F-08" in option.decision.rule_ids  # the last resort still goes to a person


def test_the_offer_cannot_take_a_claim_losing_stand_in_while_a_keeper_can_be_ordered(
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], policy: Any, price: Any, stock: Any,
    make_request: Callable[..., Any], agent_hotel: Identity,
) -> None:
    # The keeper has 10 L confirmed of the 100 L asked for; the cheaper almond drink has 500 and lacks VEGAN.
    deps = deps_for(fake_gateway(
        [price(ORIGINAL, "1.37"), price(BARISTA_OAT, "1.74"), price(ALMOND, "1.20")],
        [stock(ORIGINAL, None), stock(BARISTA_OAT, 10), stock(ALMOND, 500)],
    ))

    offer = OfferService(deps).build_offer(make_request(100, Unit.L, product_ids=(ORIGINAL,)), agent_hotel)

    taken = {line.product_id for option in offer.options for line in option.lines}
    assert ALMOND not in taken
    assert BARISTA_OAT in taken
