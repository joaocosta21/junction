"""Plain "milk": regular milk first, a lactose-free product only as a named alternative, and the headline says
that coffee milk was left out (PLAN section 4, decision 6; B0's leftover).

Valio Aimo left the choice to us on 14 Nov 2026 ("what do you think makes the most sense for normal company?").
Scores on the 20% "how precisely the agent matches what the buyer actually asked for". Replay over tonight's
capture at the recording's own clock (Saturday 14 Nov 2026, 02:52 Helsinki time), or hand-built stock.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import Identity
from tta.contracts.offer import Offer
from tta.offers import OfferService

REGULAR = "469549"  # Valio semi skimmed milk 1 l ESL: no lactose claim
LACTOSE_FREE = "469363"  # Arla semi skimmed milk drink, lactose free
LOW_LACTOSE = "463047"  # Arla whole milk, low lactose: 132 confirmed in the recording, €2.01
COFFEE_HEADLINE = " Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk."

Build = Callable[..., Offer]


@pytest.fixture(scope="module")
def plain(service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity) -> Offer:
    """100 litres of milk by Monday: in the recording no regular milk has a confirmed quantity."""
    return service.build_offer(make_request(100, product_type="milk"), agent_hotel)


def test_regular_milk_is_taken_before_a_cheaper_lactose_free_one(
    build: Build, price: Callable[..., Any], stock: Callable[..., Any], make_request: Callable[..., Any]
) -> None:
    prices = [price(REGULAR, "3.00"), price(LACTOSE_FREE, "2.48")]
    lines = [stock(REGULAR, 200), stock(LACTOSE_FREE, 500)]

    offer = build(prices, lines, make_request(100, product_type="milk"))

    assert offer.options[0].product_ids == (REGULAR,)
    assert "named alternative" not in offer.options[0].summary
    assert not any("named alternative" in note for note in offer.notes)


def test_lactose_free_milk_only_fills_what_regular_milk_leaves_and_the_option_names_it(
    build: Build, price: Callable[..., Any], stock: Callable[..., Any], make_request: Callable[..., Any]
) -> None:
    prices = [price(REGULAR, "3.00"), price(LACTOSE_FREE, "2.48")]
    lines = [stock(REGULAR, 200), stock(LACTOSE_FREE, 500)]

    offer = build(prices, lines, make_request(300, product_type="milk"))

    first = offer.options[0]
    assert [(line.product_id, line.covers) for line in first.lines] == [(REGULAR, 200), (LACTOSE_FREE, 100)]
    assert (
        "Arla Semi skimmed milkdrink 1 L UHT lactose free Suomesta (469363) is lactose-free milk, offered as a named "
        "alternative to regular milk: regular milk covers 200 L of the 300 L asked for in this option."
    ) in first.summary


def test_with_no_regular_milk_confirmed_the_headline_names_the_low_lactose_milk(plain: Offer) -> None:
    first = plain.options[0]

    assert first.product_ids == (LOW_LACTOSE,)
    assert first.totals.net == Decimal("201.00")
    assert (
        "(463047) is low-lactose milk, offered as a named alternative to regular milk: regular milk covers 0 L of "
        "the 100 L asked for in this option."
    ) in first.summary


def test_the_offer_notes_say_the_rule_and_name_the_products(plain: Offer) -> None:
    assert (
        "Request line 1: a request for milk is filled with regular milk first. Lactose-free or low-lactose milk is "
        "offered only as a named alternative: 463047."
    ) in plain.notes


def test_the_regular_milk_whose_quantity_is_not_confirmed_is_the_alternative(plain: Offer) -> None:
    second = plain.options[1]

    assert second.product_ids == ("469477",)  # Valio skimmed milk 1 l ESL, €0.88
    assert "named alternative" not in second.summary


def test_a_request_for_lactose_free_milk_gets_no_such_sentence(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(1000), agent_hotel)  # requires the claim FREE_FROM_LACTOSE

    assert not any("named alternative" in option.summary for option in offer.options)
    assert not any("named alternative" in note for note in offer.notes)


def test_the_headline_says_that_coffee_milk_was_left_out(plain: Offer) -> None:
    assert plain.options[0].summary.endswith(COFFEE_HEADLINE)
    assert all(COFFEE_HEADLINE not in option.summary for option in plain.options[1:])  # the headline only


def test_scenario_1_says_it_in_the_headline_too(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(1000), agent_hotel)

    assert offer.options[0].summary == (
        "2 confirmed products cover 435 L of the 1,000 L asked for (565 L missing), for €1,083.39 before tax."
        # Lane L2a-2 (P10 item F11): two products fill the line and differ in formula, and the option says so.
        " Arla Milkdrink 1L lactose free fat free UHT Suomesta (462775) differs in formula from Arla Semi skimmed "
        "milkdrink 1 L UHT lactose free Suomesta (469363), which fills the same request line: fat 0 g, not 1.5 g."
        + COFFEE_HEADLINE
    )


def test_a_type_with_nothing_left_out_adds_nothing_to_the_headline(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(10, product_type="cream"), agent_hotel)

    assert "left out" not in offer.options[0].summary


def test_an_offer_carries_a_list_of_suggestions_that_nothing_fills_yet(plain: Offer) -> None:
    assert plain.suggestions == ()
