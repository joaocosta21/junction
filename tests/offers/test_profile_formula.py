"""Decision B35: the bakery's profile ("the formula matters") ranks and labels substitutes exactly as a request
line that says so. Hand-built answers over the real catalog for the creams; the recording for crème fraîche."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import Identity, IdentityKind, OptionKind, Unit
from tta.contracts.offer import Offer, OfferOption
from tta.offers import OfferDeps, OfferService

# As in test_stand_in_formula.py: VALIO keeps the formula of CREAM, COOKING (10 % fat) does not.
CREAM, VALIO, COOKING = "469346", "464194", "463797"
PLACEHOLDER = 999_999  # the amount Valio reports when it does not know the stock
CREME_FRAICHE, TZATZIKI = "477055", "470260"
NOT_KEPT = "Alternative: a substitute that does not keep the formula"
USUAL = "With a substitute for a product that cannot be supplied in full"


@pytest.fixture(scope="module")
def agent_bakery() -> Identity:
    return Identity(kind=IdentityKind.AGENT, id="agent:bakery-cafe", display_name="Bakery agent",
                    profile_id="bakery-cafe")


@pytest.fixture
def serve(fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps]) -> Callable[..., OfferService]:
    def build(prices: Any, lines: Any) -> OfferService:
        return OfferService(deps_for(fake_gateway(prices, lines)))

    return build


def of_kind(offer: Offer, kind: OptionKind) -> OfferOption | None:
    return next((option for option in offer.options if option.kind is kind), None)


def test_the_bakery_gets_the_formula_keeper_first_without_saying_the_word(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_bakery: Identity
) -> None:
    service = serve(
        [price(CREAM, "5.77"), price(COOKING, "3.31"), price(VALIO, "3.91")],
        [stock(CREAM, 48), stock(COOKING, 500), stock(VALIO, PLACEHOLDER)],
    )

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(CREAM,)), agent_bakery)

    with_substitute = of_kind(offer, OptionKind.SUBSTITUTE)
    assert [(line.product_id, line.quantity) for line in with_substitute.lines] == [(CREAM, 48), (VALIO, 52)]
    assert with_substitute.title.startswith("With a substitute")
    assert COOKING not in {line.product_id for option in offer.options for line in option.lines}
    assert "F-11" not in with_substitute.decision.rule_ids


def test_the_bakery_with_no_formula_keeper_gets_a_labelled_alternative_and_the_offer_says_who_says_so(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_bakery: Identity, agent_hotel: Identity
) -> None:
    service = serve([price(CREAM, "5.77"), price(COOKING, "3.31")], [stock(CREAM, None), stock(COOKING, 500)])
    request = make_request(100, Unit.L, product_ids=(CREAM,))

    offer = service.build_offer(request, agent_bakery)
    for_the_hotel = service.build_offer(request, agent_hotel)

    assert [option.title for option in offer.options] == [NOT_KEPT]
    option = offer.options[0]
    assert "F-11" in option.decision.rule_ids
    assert "Kallio Bakery's profile says the formula matters" in option.summary
    assert "The request says the formula matters" not in option.summary
    assert any("Kallio Bakery's profile says the formula matters" in note for note in offer.notes)
    # The request did not say so: the offer line keeps the request's own word, and the rule names the profile.
    assert option.lines[0].keep_formula is None
    assert "Kallio Bakery uses its products as ingredients" in option.decision.sentence
    # A buyer whose profile does not say so sees the same substitute as the usual option.
    assert [each.title for each in for_the_hotel.options] == [USUAL]
    assert "F-11" not in for_the_hotel.options[0].decision.rule_ids


def test_the_requests_own_word_is_still_named_as_the_requests(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_bakery: Identity
) -> None:
    service = serve([price(CREAM, "5.77"), price(COOKING, "3.31")], [stock(CREAM, None), stock(COOKING, 500)])

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(CREAM,), keep_formula=True), agent_bakery)

    assert [option.title for option in offer.options] == [NOT_KEPT]
    assert "The request says the formula matters" in offer.options[0].summary
    assert any("the request says the formula matters" in note for note in offer.notes)


@pytest.mark.parametrize("keep_formula", [None, True], ids=["the profile's word", "the request's word too"])
def test_the_recording_40_kg_of_creme_fraiche_for_the_bakery_names_the_tzatziki_as_the_alternative(
    service: OfferService, make_request: Any, agent_bakery: Identity, keep_formula: bool | None
) -> None:
    """Before B35 the tzatziki was the suggestion unless the request repeated the word."""
    request = make_request(40, Unit.KG, product_ids=(CREME_FRAICHE,), keep_formula=keep_formula)

    offer = service.build_offer(request, agent_bakery)

    first, second = offer.options
    assert (first.kind, first.title) == (OptionKind.ALTERNATIVE_UNCONFIRMED, "Alternative: quantity not confirmed")
    assert [(line.product_id, line.quantity) for line in first.lines] == [(CREME_FRAICHE, 20)]
    assert first.totals.net == Decimal("214.40") and first.decision.rule_ids == ("F-01",)
    assert (second.kind, second.title) == (OptionKind.SUBSTITUTE, NOT_KEPT)
    assert [(line.product_id, line.quantity) for line in second.lines] == [(TZATZIKI, 20)]
    assert second.totals.net == Decimal("240.40") and "F-11" in second.decision.rule_ids
