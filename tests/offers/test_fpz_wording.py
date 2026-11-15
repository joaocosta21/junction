"""Lane FP-Z, items 3, 4 and 5: three sentences of an option's summary that said something untrue or unreadable.

Scores on the 20% "solving the problem and user need" (the answer says precisely what is offered for what was
asked) and on the 15% "robustness to exception situations" (the unconfirmed alternative and the substitute are
described as what they are). Words only: no test here pins a decision, a limit or what is offered.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.contracts.common import Identity, OptionKind, Unit
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers import OfferDeps, OfferService

MONDAY = date(2026, 11, 16)
A, B = "469363", "462775"  # lactose-free milks, 1-litre cartons
CREAM = "463797"  # Arla Pro Cooking cream 10% 1 L UHT lactose free: the hotel's suggested "forgotten item"
MILK = RequestLine(
    text="100 litres of lactose-free milk by Monday", product_type="milk", required_claims=("FREE_FROM_LACTOSE",),
    quantity=Decimal(100), unit=Unit.L,
)
CREAM_BY_ID = RequestLine(text="10 L of 463797", product_ids=(CREAM,), quantity=Decimal(10), unit=Unit.L)
CHEESE = RequestLine(text="10 kg cheese", product_type="cheese", quantity=Decimal(10), unit=Unit.KG)
UNCONFIRMED = "Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free (464306)"
COFFEE = (
    "Milk made for coffee is not offered as milk: it appears only as a named substitute, or when coffee milk is "
    "asked for by name (product type coffee_milk)."
)


def of_kind(offer: Offer, kind: OptionKind) -> OfferOption:
    return next(option for option in offer.options if option.kind is kind)


@pytest.fixture(scope="module")
def milk_and_cream(service: OfferService, agent_hotel: Identity) -> Offer:
    """The hotel's 100 L of lactose-free milk with the suggested cooking cream added, as "Add" sends it."""
    return service.build_offer(PurchaseRequest(needed_by=MONDAY, lines=(MILK, CREAM_BY_ID)), agent_hotel)


# --- 3. the unconfirmed alternative of several lines says which product is for which item ---------------------------


def test_the_alternative_of_a_two_line_request_names_each_product_with_the_item_it_fills(milk_and_cream: Offer) -> None:
    option = of_kind(milk_and_cream, OptionKind.ALTERNATIVE_UNCONFIRMED)

    assert {line.product_id for line in option.lines} == {"464306", CREAM}
    assert option.summary.startswith(
        f"{UNCONFIRMED} for the 100 L of milk, and from confirmed stock the 10 L of Arla Pro Cooking cream 10% 1 L "
        "UHT lactose free (463797): all 2 items asked for in full, €134.10 before tax. Valio does not confirm the "
        "quantity in stock of 464306, so a human must approve this option."
    )
    # Before: one product "for all 2 items asked for in full", though it fills one of them.
    assert "(464306) for all 2 items" not in option.summary


def test_the_alternative_names_only_the_item_its_product_fills_when_nothing_is_offered_for_the_other(
    service: OfferService, agent_hotel: Identity
) -> None:
    offer = service.build_offer(PurchaseRequest(needed_by=MONDAY, lines=(MILK, CHEESE)), agent_hotel)
    option = of_kind(offer, OptionKind.ALTERNATIVE_UNCONFIRMED)

    assert option.summary.startswith(
        f"{UNCONFIRMED} for the 100 L of milk: 1 of the 2 items asked for in full, €101.00 before tax. Valio does "
        "not confirm the quantity in stock, so a human must approve this option."
    )
    assert option.summary.endswith("Nothing is offered for cheese.")


def test_the_alternative_of_a_one_line_request_reads_as_before(service: OfferService, agent_hotel: Identity) -> None:
    offer = service.build_offer(PurchaseRequest(needed_by=MONDAY, lines=(MILK,)), agent_hotel)

    assert of_kind(offer, OptionKind.ALTERNATIVE_UNCONFIRMED).summary == (
        f"{UNCONFIRMED} for the 100 L asked for, €101.00 before tax. Valio does not confirm the quantity in stock, "
        "so a human must approve this option."
    )


def test_an_item_the_option_fills_in_part_says_how_much_of_it(
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], price: Any, stock: Any, agent_hotel: Identity
) -> None:
    """The milk whose quantity is not confirmed fills the milk line; only 4 of the 10 L of cream are in stock."""
    gateway = fake_gateway(
        [price(A, "2.48"), price(B, "2.57"), price(CREAM, "3.31")],
        [stock(A, 60), stock(B, 999999), stock(CREAM, 4)],
    )
    offer = OfferService(deps_for(gateway)).build_offer(
        PurchaseRequest(needed_by=MONDAY, lines=(MILK, CREAM_BY_ID)), agent_hotel
    )

    assert of_kind(offer, OptionKind.ALTERNATIVE_UNCONFIRMED).summary.startswith(
        "Arla Milkdrink 1L lactose free fat free UHT Suomesta (462775) for the 100 L of milk, and from confirmed "
        "stock 4 L of the 10 L of Arla Pro Cooking cream 10% 1 L UHT lactose free (463797): 1 of the 2 items asked "
        "for in full, €270.24 before tax. Valio does not confirm the quantity in stock of 462775, so a human must "
        "approve this option."
    )


def test_an_alternative_whose_every_product_is_unconfirmed_names_no_product_twice(
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], price: Any, stock: Any, agent_hotel: Identity
) -> None:
    gateway = fake_gateway(
        [price(A, "2.48"), price(B, "2.57"), price(CREAM, "3.31")],
        [stock(A, 60), stock(B, 999999), stock(CREAM, 999999)],
    )
    offer = OfferService(deps_for(gateway)).build_offer(
        PurchaseRequest(needed_by=MONDAY, lines=(MILK, CREAM_BY_ID)), agent_hotel
    )

    assert of_kind(offer, OptionKind.ALTERNATIVE_UNCONFIRMED).summary == (
        "Arla Milkdrink 1L lactose free fat free UHT Suomesta (462775) for the 100 L of milk and the 10 L of Arla "
        "Pro Cooking cream 10% 1 L UHT lactose free (463797): all 2 items asked for in full, €290.10 before tax. "
        "Valio does not confirm the quantity in stock, so a human must approve this option."
    )


# --- 4. a note in the headline names its line by the line's own words, never by number ------------------------------


def test_the_headline_of_a_request_of_several_lines_names_the_line_by_its_words(milk_and_cream: Offer) -> None:
    headline = milk_and_cream.options[0].summary

    assert headline == (
        f"2 confirmed products cover all 2 items asked for in full, for €281.10 before tax. For milk: {COFFEE}"
    )
    assert all("Request line" not in option.summary for option in milk_and_cream.options)
    # The offer's notes keep the line's number: programs read it there (tta.customers.learned, tta.menus.earliest).
    assert milk_and_cream.notes[0] == f"Request line 1: {COFFEE}"


def test_the_headline_of_a_request_of_one_line_says_nothing_before_the_note(
    service: OfferService, agent_hotel: Identity
) -> None:
    offer = service.build_offer(PurchaseRequest(needed_by=MONDAY, lines=(MILK,)), agent_hotel)

    assert offer.options[0].summary == (
        f"1 confirmed product covers the 100 L asked for, for €248.00 before tax. {COFFEE}"
    )


# --- 5. the milk note is one sentence that is true above an option that offers a café milk --------------------------


def test_the_milk_note_is_one_sentence_and_does_not_say_coffee_milk_is_never_offered(catalog: ProductCatalog) -> None:
    note = catalog.product_type_note("milk")

    assert note == COFFEE
    assert note.count(". ") == 0  # one sentence: the headline carries all of it
    assert "left out" not in note and "gets no milk for coffee" not in note


def test_the_headline_stays_true_beside_the_option_that_names_a_cafe_milk_as_a_substitute(
    service: OfferService, make_request: Callable[..., PurchaseRequest], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(1000), agent_hotel)
    substitute = of_kind(offer, OptionKind.SUBSTITUTE)

    assert offer.options[0].summary.endswith(COFFEE)
    assert "Arla Cafè milk 1 L UHT lactose free (463380)" in substitute.summary  # offered, as a named substitute
