"""FIX-12b: an offer with several request lines says what each line gets, and a dated request that nothing can
meet names the earliest delivery date and the products that would make it."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import ExclusionReason, Identity, OptionKind, Unit
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.policy import FiredRule
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers import OfferDeps, OfferService
from tta.offers.wording import line_words

A, B = "469363", "462775"  # lactose-free milks, 1-litre cartons
NO_PRICE = "463380"  # a third lactose-free milk; given no price below
REGULAR = "463149"  # Valio Plus skimmed milk 1 l: not lactose-free, so the milk line never takes it
MONDAY = date(2026, 11, 16)
SUNDAY = date(2026, 11, 15)
TUESDAY = date(2026, 11, 17)
WEDNESDAY = date(2026, 11, 18)
MILK = RequestLine(
    text="100 L lactose-free milk", product_type="milk", required_claims=("FREE_FROM_LACTOSE",),
    quantity=Decimal(100), unit=Unit.L,
)
BUTTER = RequestLine(text="10 kg butter", product_type="butter", quantity=Decimal(10), unit=Unit.KG)
MILK_AND_BUTTER = PurchaseRequest(needed_by=MONDAY, lines=(MILK, BUTTER))
LATE_NOTE = "Request line 1: nothing can arrive by Sunday 15 Nov."


def p03(option: OfferOption) -> FiredRule:
    assert option.decision is not None
    return next(rule for rule in option.decision.fired if rule.rule_id == "P-03")


def of_kind(offer: Offer, kind: OptionKind) -> OfferOption:
    return next(option for option in offer.options if option.kind is kind)


@pytest.fixture
def serve(fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps]) -> Callable[..., OfferService]:
    def build(prices: Any, lines: Any) -> OfferService:
        return OfferService(deps_for(fake_gateway(prices, lines)))

    return build


@pytest.fixture(scope="module")
def milk_and_butter(service: OfferService, agent_hotel: Identity) -> Offer:
    """Replay: the milk is in tonight's capture, no butter is."""
    return service.build_offer(MILK_AND_BUTTER, agent_hotel)

# The headline (the first option's summary) says what the product type milk left out (B0's leftover, lane L2b).
COFFEE = " Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk."
COFFEE_LINE_1 = " Request line 1:" + COFFEE


# --- coverage per line ----------------------------------------------------------------------------------------

def test_a_two_line_offer_says_how_many_lines_it_covers_in_full_and_what_each_line_gets(
    milk_and_butter: Offer,
) -> None:
    option = of_kind(milk_and_butter, OptionKind.BEST_CONFIRMED)

    assert option.summary == (
        "1 confirmed product covers 1 of the 2 request lines in full, for €248.00 before tax. "
        "Covered: 0 of 10 kg of butter, request line 2; 100 of 100 L of milk, request line 1." + COFFEE_LINE_1
    )
    assert "least covered" not in option.summary


def test_the_unconfirmed_alternative_says_the_same_of_its_lines(milk_and_butter: Offer) -> None:
    option = of_kind(milk_and_butter, OptionKind.ALTERNATIVE_UNCONFIRMED)

    assert "(464306) for 1 of the 2 request lines in full, €101.00 before tax." in option.summary
    assert option.summary.endswith(
        "Covered: 0 of 10 kg of butter, request line 2; 100 of 100 L of milk, request line 1."
    )


def test_p03_names_the_least_covered_line_and_what_each_line_gets_while_the_ratio_stays_the_lowest(
    milk_and_butter: Offer,
) -> None:
    option = of_kind(milk_and_butter, OptionKind.BEST_CONFIRMED)
    rule = p03(option)

    assert rule.sentence == (
        "Only 0% of the quantity of request line 2 is covered, below the 90% minimum "
        "(covered: 0 of 10 kg of butter, request line 2; 100 of 100 L of milk, request line 1)."
    )
    assert "of the requested quantity" not in rule.sentence
    assert option.fill_ratio == 0
    assert rule.facts["option.fill_ratio"] == 0.0


def test_a_one_line_partial_fill_keeps_its_wording_and_gains_the_amounts(
    service: OfferService, make_request: Callable[..., PurchaseRequest], agent_hotel: Identity
) -> None:
    option = service.build_offer(make_request(1500), agent_hotel).options[0]

    assert option.summary == (
        "2 confirmed products cover 435 L of the 1,500 L asked for (1,065 L missing), for €1,083.39 before tax."
        + COFFEE
    )
    assert p03(option).sentence == (
        "Only 29% of the requested quantity is covered, below the 90% minimum (covered: 435 of 1,500 L)."
    )


def test_each_line_is_named_by_type_by_product_or_by_name_term_with_the_short_lines_first(
    serve: Callable[..., OfferService], price: Any, stock: Any, agent_hotel: Identity
) -> None:
    request = PurchaseRequest(
        needed_by=MONDAY,
        lines=(
            MILK,
            RequestLine(text="10 L of 463149", product_ids=(REGULAR,), quantity=Decimal(10), unit=Unit.L),
            RequestLine(text="5 L oat drink", name_terms=("oat", "drink"), quantity=Decimal(5), unit=Unit.L),
        ),
    )
    prices = [price(A, "2.48"), price(REGULAR, "1.20")]
    offer = serve(prices, [stock(A, 60), stock(REGULAR, 100)]).build_offer(request, agent_hotel)
    option = of_kind(offer, OptionKind.BEST_CONFIRMED)

    assert option.summary == (
        "2 confirmed products cover 1 of the 3 request lines in full, for €160.80 before tax. "
        "Covered: 0 of 5 L of 'oat drink', request line 3; 60 of 100 L of milk, request line 1; "
        "10 of 10 L of product 463149, request line 2." + COFFEE_LINE_1
    )
    assert p03(option).sentence.startswith("Only 0% of the quantity of request line 3 is covered")


def test_an_option_that_covers_every_line_in_full_reads_as_before(
    serve: Callable[..., OfferService], price: Any, stock: Any, agent_hotel: Identity
) -> None:
    request = PurchaseRequest(
        needed_by=MONDAY,
        lines=(MILK, RequestLine(text="10 L of 463149", product_ids=(REGULAR,), quantity=Decimal(10), unit=Unit.L)),
    )
    prices = [price(A, "2.48"), price(REGULAR, "1.20")]
    offer = serve(prices, [stock(A, 500), stock(REGULAR, 100)]).build_offer(request, agent_hotel)

    assert offer.options[0].summary == (
        "2 confirmed products cover all 2 request lines in full, for €260.00 before tax." + COFFEE_LINE_1
    )


def test_no_line_in_full_reads_none(
    serve: Callable[..., OfferService], price: Any, stock: Any, agent_hotel: Identity
) -> None:
    request = PurchaseRequest(
        needed_by=MONDAY,
        lines=(MILK, RequestLine(text="10 L of 462775", product_ids=(B,), quantity=Decimal(10), unit=Unit.L)),
    )
    offer = serve([price(A, "2.48"), price(B, "2.57")], [stock(A, 50), stock(B, 5)]).build_offer(request, agent_hotel)

    assert "2 confirmed products cover none of the 2 request lines in full" in offer.options[0].summary


@pytest.mark.parametrize(
    ("line", "words"),
    [
        (RequestLine(text="x", product_type="beef_chuck", name_terms=("ignored",), quantity=1, unit=Unit.KG),
         "beef chuck"),
        (RequestLine(text="x", name_terms=("oat", "oat", "barista"), quantity=1, unit=Unit.L), "'oat barista'"),
        (RequestLine(text="x", product_ids=(A,), quantity=1, unit=Unit.L), f"product {A}"),
        (RequestLine(text="x", product_ids=(A, B, A, NO_PRICE), quantity=1, unit=Unit.L),
         f"products {A}, {B} and {NO_PRICE}"),
        (RequestLine(text="x", quantity=1, unit=Unit.L), ""),
    ],
)
def test_a_request_line_is_named_as_the_policy_names_it(line: RequestLine, words: str) -> None:
    assert line_words(line) == words


# --- the earliest date when nothing arrives in time -----------------------------------------------------------

def test_a_request_for_tomorrow_that_nothing_meets_names_the_earliest_date_and_the_products(
    service: OfferService, make_request: Callable[..., PurchaseRequest], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(100, needed_by=SUNDAY), agent_hotel)
    late = [each.product_id for each in offer.excluded if each.reason is ExclusionReason.LATE_FOR_NEEDED_BY]

    note = next(note for note in offer.notes if note.startswith(LATE_NOTE))

    assert offer.options == ()
    assert late  # every delivery date in tonight's capture is Monday 16 Nov (AIMO/USE-CASES.md, use case 2)
    assert (
        f"The earliest delivery date in Valio's data for a product that otherwise fits is Monday 16 Nov, "
        f"for {len(late)} products: {', '.join(late[:10])}"
    ) in note
    assert offer.notes[-1].startswith("No option can be offered")


def test_the_earliest_date_names_only_the_products_that_make_it_and_otherwise_fit(
    serve: Callable[..., OfferService], price: Any, stock: Any, make_request: Callable[..., PurchaseRequest],
    agent_hotel: Identity,
) -> None:
    prices = [price(A, "2.48"), price(B, "2.57")]  # NO_PRICE has no price: late, and it could not be offered anyway
    lines = [
        stock(A, 500, available_date=TUESDAY), stock(B, 500, available_date=WEDNESDAY),
        stock(NO_PRICE, 500, available_date=MONDAY),
    ]
    offer = serve(prices, lines).build_offer(make_request(100, needed_by=SUNDAY), agent_hotel)

    note = next(note for note in offer.notes if note.startswith(LATE_NOTE))

    assert note == (
        f"{LATE_NOTE} The earliest delivery date in Valio's data for a product that otherwise fits is "
        f"Tuesday 17 Nov, for 1 product: {A}."
    )


def test_no_earliest_date_note_when_a_product_arrives_in_time_or_the_request_has_no_date(
    serve: Callable[..., OfferService], price: Any, stock: Any, make_request: Callable[..., PurchaseRequest],
    agent_hotel: Identity,
) -> None:
    prices = [price(A, "2.48"), price(B, "2.57")]
    lines = [stock(A, 500, available_date=SUNDAY), stock(B, 500, available_date=TUESDAY)]

    in_time = serve(prices, lines).build_offer(make_request(100, needed_by=SUNDAY), agent_hotel)
    undated = serve(prices, lines).build_offer(make_request(100, needed_by=None), agent_hotel)

    assert in_time.options and undated.options
    assert not any("nothing can arrive" in note for note in (*in_time.notes, *undated.notes))


def test_no_earliest_date_note_when_no_late_product_would_fit_at_its_own_date(
    serve: Callable[..., OfferService], price: Any, stock: Any, make_request: Callable[..., PurchaseRequest],
    agent_hotel: Identity,
) -> None:
    # Under confirmed-only, a product whose quantity is not confirmed drops out at any date.
    lines = [stock(A, 999999, available_date=TUESDAY, logistic_model="Terminal")]
    request = make_request(100, needed_by=SUNDAY, require_confirmed=True)

    offer = serve([price(A, "2.48")], lines).build_offer(request, agent_hotel)

    assert offer.options == ()
    assert not any("nothing can arrive" in note for note in offer.notes)
