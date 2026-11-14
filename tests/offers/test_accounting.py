"""Every candidate of a request is accounted for: in an option, excluded with a reason, or named as not needed.

Under confirmed-only a product that drops out for a quantity or a delivery date Valio's data does not
confirm is an exclusion like any other (SPEC section 5, "Exclusion reason codes").
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pytest

from tta.contracts.common import ExclusionReason, Identity, OptionKind, Unit
from tta.contracts.offer import Offer
from tta.offers import OfferService

A, B = "469363", "462775"  # lactose-free milks of category 10400, 1-litre cartons
UNCONFIRMED = "464306"
PLACEHOLDER = 999_999
CONFIRMED_ONLY_CODES = {ExclusionReason.QUANTITY_NOT_CONFIRMED, ExclusionReason.DELIVERY_DATE_NOT_CONFIRMED}

Build = Callable[..., Offer]


def excluded(offer: Offer) -> dict[str, Any]:
    return {exclusion.product_id: exclusion for exclusion in offer.excluded}


def candidates_offered(offer: Offer) -> set[str]:
    """Products of the options that are candidates of the request: a stand-in is not one."""
    return {line.product_id for option in offer.options for line in option.lines if line.substitute is None}


def named_as_not_needed(offer: Offer) -> int:
    """How many products the notes name as fitting the request and being in no option."""
    pattern = re.compile(r": (\d+) products? fits? the request and (?:is|are) in no option")
    return sum(int(found.group(1)) for found in map(pattern.search, offer.notes) if found)


# --- confirmed-only: what drops out is listed --------------------------------------------------------------

def test_under_confirmed_only_a_quantity_that_is_not_confirmed_is_an_exclusion(
    build: Build, price: Any, stock: Any, make_request: Any
) -> None:
    offer = build(
        [price(UNCONFIRMED, "1.01")], [stock(UNCONFIRMED, PLACEHOLDER)], make_request(100, require_confirmed=True)
    )

    dropped = excluded(offer)[UNCONFIRMED]
    assert offer.options == ()
    assert dropped.reason is ExclusionReason.QUANTITY_NOT_CONFIRMED
    assert "confirmed data only" in dropped.sentence.lower()
    assert "999,999" in dropped.sentence
    # The note that says every product that dropped out is listed is now true.
    assert offer.candidates_considered == len(offer.excluded)
    assert any("listed with its reason" in note for note in offer.notes)


@pytest.mark.parametrize(
    ("line", "words"),
    [({"closing_time": None}, "no order cut-off"), ({"available_date": None}, "no delivery date")],
)
def test_under_confirmed_only_a_delivery_date_that_is_not_confirmed_is_an_exclusion(
    build: Build, price: Any, stock: Any, make_request: Any, best: Any, line: dict[str, Any], words: str
) -> None:
    offer = build(
        [price(A, "2.48"), price(B, "2.57")], [stock(A, 500, **line), stock(B, 500)],
        make_request(100, require_confirmed=True),
    )

    dropped = excluded(offer)[A]
    assert [each.product_id for each in best(offer).lines] == [B]
    assert dropped.reason is ExclusionReason.DELIVERY_DATE_NOT_CONFIRMED
    assert "confirmed data only" in dropped.sentence.lower()
    assert words in dropped.sentence


def test_under_confirmed_only_a_request_with_no_date_does_not_ask_for_a_confirmed_delivery_date(
    build: Build, price: Any, stock: Any, make_request: Any, best: Any
) -> None:
    offer = build(
        [price(A, "2.48")], [stock(A, 500, closing_time=None)],
        make_request(100, require_confirmed=True, needed_by=None),
    )

    assert [each.product_id for each in best(offer).lines] == [A]
    assert A not in excluded(offer)


def test_without_confirmed_only_the_two_codes_are_never_used(
    build: Build, price: Any, stock: Any, make_request: Any
) -> None:
    offer = build(
        [price(UNCONFIRMED, "1.01"), price(A, "2.48")],
        [stock(UNCONFIRMED, PLACEHOLDER), stock(A, 500, closing_time=None)],
        make_request(100),
    )

    assert {option.kind for option in offer.options} == {OptionKind.BEST_CONFIRMED, OptionKind.ALTERNATIVE_UNCONFIRMED}
    assert not CONFIRMED_ONLY_CODES & {exclusion.reason for exclusion in offer.excluded}


# --- products that fit and are not needed ------------------------------------------------------------------

def test_a_product_that_fits_and_is_in_no_option_is_named_in_a_note(
    build: Build, price: Any, stock: Any, make_request: Any, best: Any
) -> None:
    # A covers the 100 litres alone and is cheaper: B fits and is not needed.
    offer = build([price(A, "2.48"), price(B, "2.57")], [stock(A, 500), stock(B, 500)], make_request(100))

    assert [each.product_id for each in best(offer).lines] == [A]
    assert B not in excluded(offer)
    notes = [note for note in offer.notes if B in note]
    assert len(notes) == 1
    assert notes[0].startswith("Request line 1: 1 product fits the request and is in no option")
    assert named_as_not_needed(offer) == 1
    assert offer.candidates_considered == len(candidates_offered(offer)) + len(offer.excluded) + 1


# --- the scenarios: the candidates add up ------------------------------------------------------------------

SCENARIOS = {
    "1 hotel: lactose-free milk": ("agent_hotel", dict(quantity=1000)),
    "2 ward: milk substitute, confirmed only": (
        "agent_ward",
        dict(quantity=200, product_type="plant_drink", exclude_allergens=("AM", "AW"), require_confirmed=True),
    ),
    "3 hotel: the oat drink by id": ("agent_hotel", dict(quantity=100, product_ids=("473609",))),
    "backup hotel: beef chuck": (
        "agent_hotel", dict(quantity=30, unit=Unit.KG, product_type="beef_chuck", needed_by=None),
    ),
    "hotel: lactose-free milk, confirmed only": ("agent_hotel", dict(quantity=1000, require_confirmed=True)),
}


@pytest.mark.parametrize("name", SCENARIOS)
def test_tonight_every_candidate_is_in_an_option_or_excluded_or_named_as_not_needed(
    name: str, service: OfferService, make_request: Any, request: pytest.FixtureRequest
) -> None:
    identity_fixture, asked = SCENARIOS[name]
    identity: Identity = request.getfixturevalue(identity_fixture)

    offer = service.build_offer(make_request(**asked), identity)

    offered, dropped = candidates_offered(offer), set(excluded(offer))
    assert offer.candidates_considered > 0
    assert offered.isdisjoint(dropped)
    assert len(dropped) == len(offer.excluded)  # one reason per product
    assert offer.candidates_considered == len(offered) + len(dropped) + named_as_not_needed(offer)
    if not asked.get("require_confirmed") and identity.profile_id != "allergy-ward":
        assert not CONFIRMED_ONLY_CODES & {exclusion.reason for exclusion in offer.excluded}


def test_tonight_confirmed_only_lists_each_milk_whose_quantity_is_not_confirmed(
    service: OfferService, make_request: Any, agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(1000, require_confirmed=True), agent_hotel)

    unconfirmed = [each for each in offer.excluded if each.reason is ExclusionReason.QUANTITY_NOT_CONFIRMED]
    assert UNCONFIRMED in {each.product_id for each in unconfirmed}  # the alternative of scenario 1
    assert all("confirmed data only" in each.sentence.lower() for each in unconfirmed)
    assert [option.kind for option in offer.options] == [OptionKind.BEST_CONFIRMED]
    assert any(UNCONFIRMED in note and "confirmed data only" in note for note in offer.notes)
