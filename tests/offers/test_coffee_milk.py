"""Coffee milk is its own product type, and the offer says so (review P9a, items M1 and A1).

Valio Aimo, 14 Nov 2026, asked whether a buyer who asks for milk accepts milk for coffee: "no be explicit".
Before, Arla Cafè milk (463380) supplied 565 of the 1,000 litres of the main request. Now a request for milk
gets no milk for coffee and no flavoured milk, and a note on the offer says that and how to ask for it. Since
decision B56 (15 Nov) one more option, the last, completes the confirmed milk with it as a named substitute that a
person confirms (tests/offers/test_completed_option.py): it never fills a request for milk as milk.
Replay over tonight's capture at the recording's own clock (Saturday 14 Nov 2026, 02:52 Helsinki time).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from tta.contracts.common import AvailabilityState, Identity, OptionKind
from tta.contracts.offer import Offer, OfferOption
from tta.offers import OfferService

COFFEE_MILKS = {"462626", "463380", "464237", "473142"}  # the four milks for coffee of category 10400
NOTE = (
    "Request line 1: Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee "
    "milk. It is offered only as a named substitute, or when coffee milk is asked for by name "
    "(product type coffee_milk)."
)


@pytest.fixture(scope="module")
def milk(service: OfferService, make_request: Callable[..., object], agent_hotel: Identity) -> Offer:
    """Scenario 1: 1,000 litres of lactose-free milk by Monday, for the hotel kitchen."""
    return service.build_offer(make_request(1000), agent_hotel)


def test_a_request_for_milk_is_offered_coffee_milk_only_as_a_named_substitute(milk: Offer) -> None:
    as_milk = {line.product_id for option in milk.options for line in option.lines if line.substitute is None}
    stand_ins = {line.product_id for option in milk.options for line in option.lines if line.substitute is not None}
    excluded = {exclusion.product_id for exclusion in milk.excluded}

    assert not as_milk & COFFEE_MILKS
    assert stand_ins == {"463380"}  # only in the last option, named as a substitute (decision B56)
    assert not any(line.substitute for option in milk.options[:2] for line in option.lines)
    assert not excluded & COFFEE_MILKS  # they are not candidates at all: another product type
    assert milk.candidates_considered == 26  # 30 lactose-free milks before, 4 of them for coffee


def test_the_offer_says_that_coffee_milk_was_left_out_and_how_to_ask_for_it(milk: Offer) -> None:
    assert milk.notes[0] == NOTE


def test_scenario_1_without_coffee_milk_is_a_partial_fill_of_435_litres(
    milk: Offer, option_of: Callable[..., OfferOption | None]
) -> None:
    best, alternative = milk.options[0], option_of(milk, "ALTERNATIVE_UNCONFIRMED")

    assert best.kind is OptionKind.BEST_CONFIRMED
    assert [(line.product_id, line.quantity) for line in best.lines] == [("469363", 384), ("462775", 51)]
    assert all(line.availability.state is AvailabilityState.CONFIRMED for line in best.lines)
    assert (best.coverage[0].covered, best.coverage[0].missing) == (435, 565)
    assert (best.fill_ratio, best.totals.net) == (Decimal("0.435"), Decimal("1083.39"))
    assert best.decision.rule_ids == ("P-01", "P-03")  # above the hotel's limit and below its minimum fill
    assert alternative is not None
    assert [(line.product_id, line.quantity) for line in alternative.lines] == [("464306", 1000)]
    assert alternative.totals.net == Decimal("1010.00")
    assert alternative.decision.rule_ids == ("F-01", "P-01")


def test_a_request_for_coffee_milk_by_its_own_type_gets_coffee_milk_and_no_note(
    service: OfferService, make_request: Callable[..., object], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(100, product_type="coffee_milk"), agent_hotel)

    offered = {line.product_id for option in offer.options for line in option.lines}
    assert offered and offered <= COFFEE_MILKS
    assert "463380" in offered  # Arla Cafè milk: 698 units confirmed in the recording
    assert not any("Coffee milk was left out" in note for note in offer.notes)


def test_a_type_with_nothing_to_say_adds_no_note(
    service: OfferService, make_request: Callable[..., object], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(10, product_type="cream"), agent_hotel)

    assert not any("left out:" in note for note in offer.notes)
