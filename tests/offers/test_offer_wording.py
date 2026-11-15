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
# Cheese is in neither recording. Butter served here until the baking recording was joined (task CK).
CHEESE = RequestLine(text="10 kg cheese", product_type="cheese", quantity=Decimal(10), unit=Unit.KG)
MILK_AND_CHEESE = PurchaseRequest(needed_by=MONDAY, lines=(MILK, CHEESE))
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
def milk_and_cheese(service: OfferService, agent_hotel: Identity) -> Offer:
    """Replay: the milk is in tonight's capture, no cheese is, in either recording."""
    return service.build_offer(MILK_AND_CHEESE, agent_hotel)

# The headline (the first option's summary) says what the product type milk left out (B0's leftover, lane L2b).
COFFEE = " Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk."
COFFEE_LINE_1 = " Request line 1:" + COFFEE


# --- coverage per line ----------------------------------------------------------------------------------------

def test_a_two_line_offer_says_how_many_items_it_covers_in_full_and_names_only_what_falls_short(
    milk_and_cheese: Offer,
) -> None:
    option = of_kind(milk_and_cheese, OptionKind.BEST_CONFIRMED)

    # The line covered in full (milk) is not listed; the one with nothing is named by its own words.
    assert option.summary == (
        "1 confirmed product covers 1 of the 2 items asked for in full, for €248.00 before tax. "
        "Nothing with confirmed stock for cheese." + COFFEE_LINE_1
    )
    assert "least covered" not in option.summary and "request line 2" not in option.summary


def test_the_unconfirmed_alternative_says_the_same_of_its_lines(milk_and_cheese: Offer) -> None:
    option = of_kind(milk_and_cheese, OptionKind.ALTERNATIVE_UNCONFIRMED)

    assert "(464306) for 1 of the 2 items asked for in full, €101.00 before tax." in option.summary
    # This option holds a product whose quantity is not confirmed, so it does not speak of confirmed stock.
    assert option.summary.endswith("Nothing is offered for cheese.")


def test_p03_names_the_least_covered_line_and_what_each_line_gets_while_the_ratio_stays_the_lowest(
    milk_and_cheese: Offer,
) -> None:
    option = of_kind(milk_and_cheese, OptionKind.BEST_CONFIRMED)
    rule = p03(option)

    # Re-pinned to the sentence rule P-03 gives since lane FIX-P (before: "Only 0% of the quantity of request
    # line 2 is covered, below the 90% minimum (covered: 0 of 10 kg of cheese, request line 2; ...)").
    assert rule.sentence == (
        "1 of the 2 items asked for are covered in full; nothing is offered for cheese; Harbourside Hotel asks "
        "for at least 90% of every item."
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
        # Lane L2a-2 (P10 item F11): two products fill the line and differ in formula, and the option says so.
        " Arla Milkdrink 1L lactose free fat free UHT Suomesta (462775) differs in formula from Arla Semi skimmed "
        "milkdrink 1 L UHT lactose free Suomesta (469363), which fills the same request line: fat 0 g, not 1.5 g."
        + COFFEE
    )
    assert p03(option).sentence == (
        "Only 29% of the requested quantity is covered, below the 90% minimum (covered: 435 of 1,500 L)."
    )


def test_a_line_with_nothing_is_named_and_a_line_covered_in_part_keeps_its_amounts(
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
        "2 confirmed products cover 1 of the 3 items asked for in full, for €160.80 before tax. "
        "Nothing with confirmed stock for 'oat drink'. Covered in part: 60 of 100 L of milk." + COFFEE_LINE_1
    )
    assert p03(option).facts["option.fill_ratio"] == 0.0  # the rule still judges the least covered line


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
        "2 confirmed products cover all 2 items asked for in full, for €260.00 before tax." + COFFEE_LINE_1
    )


def test_no_line_in_full_reads_none(
    serve: Callable[..., OfferService], price: Any, stock: Any, agent_hotel: Identity
) -> None:
    request = PurchaseRequest(
        needed_by=MONDAY,
        lines=(MILK, RequestLine(text="10 L of 462775", product_ids=(B,), quantity=Decimal(10), unit=Unit.L)),
    )
    offer = serve([price(A, "2.48"), price(B, "2.57")], [stock(A, 50), stock(B, 5)]).build_offer(request, agent_hotel)

    # The milk line takes both milks (55 L), so nothing is left for the line that names 462775 by id; a line that
    # names only product ids is never said as a list of ids.
    assert offer.options[0].summary.startswith(
        "2 confirmed products cover none of the 2 items asked for in full, for €136.85 before tax. Nothing with "
        "confirmed stock for the product named on line 2. Covered in part: 55 of 100 L of milk."
    )


def test_lines_that_share_their_words_also_say_their_line_and_ids_are_never_listed(
    serve: Callable[..., OfferService], price: Any, stock: Any, agent_hotel: Identity
) -> None:
    request = PurchaseRequest(
        needed_by=MONDAY,
        lines=(
            MILK, MILK.model_copy(update={"quantity": Decimal(40)}),
            RequestLine(text="two by id", product_ids=(REGULAR, NO_PRICE), quantity=Decimal(10), unit=Unit.L),
        ),
    )

    offer = serve([price(A, "2.48")], [stock(A, 100)]).build_offer(request, agent_hotel)

    assert (
        "Nothing with confirmed stock for milk (line 2) and the products named on line 3."
    ) in of_kind(offer, OptionKind.BEST_CONFIRMED).summary


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

    # Since decision B67 the earliest date is also offered, as options for a person
    # (tests/offers/test_later_date.py); the note still names the date and the products that make it.
    assert offer.options
    assert all(option.title.startswith("Alternative: delivered Monday 16 Nov") for option in offer.options)
    assert late  # every delivery date in tonight's capture is Monday 16 Nov (AIMO/USE-CASES.md, use case 2)
    assert (
        f"The earliest delivery date in Valio's data for a product that otherwise fits is Monday 16 Nov, "
        f"for {len(late)} products: {', '.join(late[:10])}"
    ) in note
    assert not any(note.startswith("No option can be offered") for note in offer.notes)


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
