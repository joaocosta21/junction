"""Two sentences that misled (checks of 15 Nov 2026, rows C2-4 and C3-F7).

C2-4: "21 products fit the request and are in no option, because the options take the cheapest products that
cover the quantity" stood beside "565 L missing" and read as stock left unused. All 21 have a quantity Valio does
not confirm; the note now says so, and that the cheapest of them is the alternative shown. Confirmed stock that
is not needed keeps the sentence it had.

C3-F7: "69.72727272727272727272727273 sales units of the 100". What a stand-in covers of a request in pieces is
its content divided by the content of one piece asked for; it is now stated to the three places a quantity is
written with, rounded down.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from tta.config import Settings
from tta.contracts.common import ConstraintKind, Identity, OptionKind, Unit
from tta.contracts.offer import Offer
from tta.offers import OfferDeps, OfferService
from tta.valio import ReplayGateway

DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
A, B = "469363", "462775"  # lactose-free milks, 1-litre cartons
CHEAPEST_UNCONFIRMED, DEARER_UNCONFIRMED = "464306", "464401"  # plain lactose-free milks of Valio
PLACEHOLDER = 999_999
CREAM_1_75_L = "465193"  # Valio food service whipping cream 1,75 l lactose free
CREAM_1_L = "469346"  # Arla Pro Whipping cream 1 L UHT lactose free
LONG_FIGURE = re.compile(r"\d\.\d{4,}")  # more decimals than a quantity is written with

Build = Callable[..., Offer]


def unused_notes(offer: Offer) -> list[str]:
    return [note for note in offer.notes if "in no option" in note]


# --- C2-4: the note about products in no option ---------------------------------------------------------------

def test_at_the_demo_clock_the_21_products_are_said_to_have_a_quantity_valio_does_not_confirm(
    deps_for: Callable[..., OfferDeps], make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    deps = deps_for(ReplayGateway(Settings.for_tests().replay_capture_dir, demo_clock=DEMO_CLOCK))

    offer = OfferService(deps).build_offer(make_request(1000), agent_hotel)

    assert unused_notes(offer) == [
        "Request line 1: 21 products fit the request and are in no option because Valio does not confirm their "
        "quantity: 462921, 463038, 463335, 463779, 464073, 464119, 464179, 464198, 464201, 464398 and 11 more. The "
        "cheapest product whose quantity is not confirmed, 464306, is the alternative shown."
    ]
    assert not any("because the options take the cheapest products" in note for note in offer.notes)


def test_at_the_recordings_clock_the_same_is_said_of_its_6_products(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(1000), agent_hotel)

    assert unused_notes(offer) == [
        "Request line 1: 6 products fit the request and are in no option because Valio does not confirm their "
        "quantity: 463335, 463779, 464073, 464201, 464398, 464401. The cheapest product whose quantity is not "
        "confirmed, 464306, is the alternative shown."
    ]


def test_confirmed_stock_that_is_not_needed_and_a_quantity_that_is_not_confirmed_get_a_note_each(
    build: Build, price: Any, stock: Any, make_request: Any
) -> None:
    # A covers the 100 litres alone and is cheaper than B. Two more milks have no confirmed quantity: the cheaper
    # of them is the alternative shown, the other is in no option.
    offer = build(
        [price(A, "2.48"), price(B, "2.57"), price(CHEAPEST_UNCONFIRMED, "1.01"), price(DEARER_UNCONFIRMED, "1.10")],
        [stock(A, 500), stock(B, 500), stock(CHEAPEST_UNCONFIRMED, PLACEHOLDER),
         stock(DEARER_UNCONFIRMED, PLACEHOLDER)],
        make_request(100),
    )

    assert unused_notes(offer) == [
        "Request line 1: 1 product fits the request and is in no option, because the options take the cheapest "
        f"products that cover the quantity: {B}.",
        "Request line 1: 1 product fits the request and is in no option because Valio does not confirm its "
        f"quantity: {DEARER_UNCONFIRMED}. The cheapest product whose quantity is not confirmed, "
        f"{CHEAPEST_UNCONFIRMED}, is the alternative shown.",
    ]


def test_no_alternative_is_named_when_none_is_shown(build: Build, price: Any, stock: Any, make_request: Any) -> None:
    # The unconfirmed milk costs more than the confirmed stock that covers the quantity, so it is not offered
    # (review P2, item W4): the note says why it is in no option and names no alternative.
    offer = build(
        [price(A, "2.48"), price(DEARER_UNCONFIRMED, "3.10")], [stock(A, 500), stock(DEARER_UNCONFIRMED, PLACEHOLDER)],
        make_request(100),
    )

    assert [option.kind for option in offer.options] == [OptionKind.BEST_CONFIRMED]
    assert unused_notes(offer) == [
        "Request line 1: 1 product fits the request and is in no option because Valio does not confirm its "
        f"quantity: {DEARER_UNCONFIRMED}."
    ]


# --- C3-F7: what a stand-in covers of a request in pieces -------------------------------------------------------

def test_what_a_stand_in_covers_of_a_request_in_pieces_is_stated_to_three_places(
    build: Build, price: Any, stock: Any, make_request: Any
) -> None:
    # 100 pieces of a 1.75 L cream that cannot be delivered; 100 one-litre cartons stand in: 100 L of the 175 L,
    # which is 57.142857... pieces. Before, the sentences carried all 28 digits.
    offer = build(
        [price(CREAM_1_75_L, "5.25", per_measure="3.00"), price(CREAM_1_L, "5.77")],
        [stock(CREAM_1_75_L, None), stock(CREAM_1_L, 100)],
        make_request(100, Unit.UNIT, product_ids=(CREAM_1_75_L,)),
    )

    option = next(each for each in offer.options if any(line.substitute for line in each.lines))
    line = option.lines[0]
    quantity = next(check for check in option.constraint_checks if check.kind is ConstraintKind.QUANTITY)
    assert (line.product_id, line.quantity, line.covers) == (CREAM_1_L, 100, Decimal("57.142"))
    assert (option.coverage[0].covered, option.coverage[0].missing) == (Decimal("57.142"), Decimal("42.858"))
    assert "57.142 sales units of the 100 sales units asked for (42.858 sales units missing)" in option.summary
    assert quantity.sentence == (
        "57.142 sales units of the 100 sales units asked for are covered; 42.858 sales units are missing."
    )
    said = (option.summary, option.decision.sentence, *(check.sentence for check in option.constraint_checks))
    assert not any(LONG_FIGURE.search(sentence) for sentence in said)


def test_a_whole_number_of_pieces_is_stated_as_it_was(build: Build, price: Any, stock: Any, make_request: Any) -> None:
    offer = build(
        [price(A, "2.48"), price(B, "2.57")], [stock(A, None), stock(B, 500)],
        make_request(100, Unit.UNIT, product_ids=(A,)),
    )

    line = next(each for each in offer.options if any(line.substitute for line in each.lines)).lines[0]
    assert (line.product_id, line.quantity, line.covers) == (B, 100, 100)
    assert str(line.covers) in ("100", "1E+2")  # not re-written as 100.000
