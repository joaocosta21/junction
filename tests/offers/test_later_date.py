"""Decision B67: a dated request that nothing meets is answered with the earliest date as a labelled alternative.

"1,000 litres of lactose-free milk by tomorrow" ended in no option and a note that named Monday. Now the same
products are offered for the earliest date they can be delivered, in options that say so and that rule F-07
sends to a person, who accepts the later date or does not. Scores on the 15% "robustness to exception
situations" (the brief's second scenario, the last-minute event).
Replay over the capture of 14 Nov: at the recording's clock (Sat 14 Nov 02:52) "tomorrow" is Sunday 15 Nov, at
the demo clock (Thu 12 Nov 14:15) it is Friday 13 Nov. Every delivery date of the recording is Monday 16 Nov.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from tta.config import Settings
from tta.contracts.common import (
    AvailabilityState,
    CheckResult,
    ClaimName,
    ClaimStatus,
    ConstraintKind,
    ExclusionReason,
    Identity,
    OptionKind,
    Unit,
    Verdict,
)
from tta.contracts.offer import Offer
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers import OfferDeps, OfferService
from tta.valio import ReplayGateway

DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
A, B = "469363", "462775"  # lactose-free milks, 1-litre cartons
UNCONFIRMED = "464306"
FRIDAY, SUNDAY, MONDAY, TUESDAY, WEDNESDAY = (date(2026, 11, day) for day in (13, 15, 16, 17, 18))
PLACEHOLDER = 999_999
FIRST_NOTE = (
    "Nothing can arrive by Sunday 15 Nov. The options are for delivery on Monday 16 Nov, 1 day later than asked: "
    "a person must accept the later date."
)

Build = Callable[..., Offer]


def delivery_claims(offer: Offer) -> set[ClaimStatus]:
    return {
        check.status for option in offer.options for line in option.lines for check in line.claims
        if check.claim is ClaimName.DELIVERY_DATE
    }


def test_for_tomorrow_the_earliest_date_is_offered_as_a_labelled_alternative(
    service: OfferService, make_request: Callable[..., PurchaseRequest], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(1000, needed_by=SUNDAY), agent_hotel)

    first, second = offer.options
    assert {option.kind for option in offer.options} == {OptionKind.ALTERNATIVE_UNCONFIRMED}
    assert first.title == "Alternative: delivered Monday 16 Nov, 1 day later than asked (partial fill)"
    assert first.summary.startswith(
        "Nothing can arrive by Sunday 15 Nov. Delivered Monday 16 Nov, 1 day later than asked: 2 confirmed products "
        "cover 435 L of the 1,000 L asked for (565 L missing), for €1,083.39 before tax. A person must accept the "
        "later date."
    )
    assert [(line.product_id, line.quantity) for line in first.lines] == [(A, 384), (B, 51)]
    assert second.title == "Alternative: delivered Monday 16 Nov, 1 day later than asked, quantity not confirmed"
    assert second.summary.startswith(
        "Nothing can arrive by Sunday 15 Nov. Delivered Monday 16 Nov, 1 day later than asked: Valio Hyvä "
        "suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free (464306) for the 1,000 L asked for, "
        "€1,010.00 before tax."
    )
    assert second.summary.endswith("so a human must approve this option. A person must accept the later date.")


def test_at_the_demo_clock_tomorrow_is_friday_and_monday_is_three_days_later(
    deps_for: Callable[..., OfferDeps], make_request: Callable[..., PurchaseRequest], agent_hotel: Identity
) -> None:
    deps = deps_for(ReplayGateway(Settings.for_tests().replay_capture_dir, demo_clock=DEMO_CLOCK))

    offer = OfferService(deps).build_offer(make_request(1000, needed_by=FRIDAY), agent_hotel)

    assert [option.title for option in offer.options] == [
        "Alternative: delivered Monday 16 Nov, 3 days later than asked (partial fill)",
        "Alternative: delivered Monday 16 Nov, 3 days later than asked, quantity not confirmed",
    ]
    assert offer.options[0].summary.startswith(
        "Nothing can arrive by Friday 13 Nov. Delivered Monday 16 Nov, 3 days later than asked: 2 confirmed "
        "products cover 435 L of the 1,000 L asked for (565 L missing), for €1,083.39 before tax."
    )
    assert offer.notes[0] == (
        "Nothing can arrive by Friday 13 Nov. The options are for delivery on Monday 16 Nov, 3 days later than "
        "asked: a person must accept the later date."
    )


def test_every_later_option_goes_to_a_person_under_the_rule_for_a_date_that_is_not_met(
    service: OfferService, make_request: Callable[..., PurchaseRequest], agent_hotel: Identity, policy: Any,
    replay_deps: OfferDeps,
) -> None:
    from tta.offers import build_offer

    alone = policy.get_profile("hotel-kitchen").model_copy(
        update={"auto_order_enabled": True, "max_order_net_eur": Decimal(100_000),
                "max_daily_net_eur": Decimal(100_000), "min_fill_ratio": Decimal("0.1")}
    )
    offers = (
        service.build_offer(make_request(1000, needed_by=SUNDAY), agent_hotel),
        build_offer(make_request(1000, needed_by=SUNDAY), alone, replay_deps, agent_id="agent:hotel-kitchen"),
    )

    for offer in offers:
        assert offer.options
        assert delivery_claims(offer) == {ClaimStatus.RULED_OUT}
        for option in offer.options:
            needed_by = next(check for check in option.constraint_checks if check.kind is ConstraintKind.NEEDED_BY)
            assert (needed_by.result, needed_by.sentence) == (
                CheckResult.NOT_MET, "A product offered cannot be delivered by Sunday 15 Nov.",
            )
            assert option.decision.verdict is Verdict.APPROVAL
            assert "F-07" in option.decision.rule_ids
            assert "the needed-by date 2026-11-15 is not met for this option" in option.decision.sentence


def test_the_first_note_says_what_cannot_arrive_and_what_can_and_the_reasons_stay(
    service: OfferService, make_request: Callable[..., PurchaseRequest], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(100, needed_by=SUNDAY), agent_hotel)
    late = [each.product_id for each in offer.excluded if each.reason is ExclusionReason.LATE_FOR_NEEDED_BY]

    assert offer.notes[0] == FIRST_NOTE
    assert f"Request line 1: no product can arrive by the date asked. {offer.candidates_considered} candidates" in (
        " ".join(offer.notes)
    )
    # The products stay listed as late for the date asked: that is still why the request as asked has no option.
    assert {line.product_id for option in offer.options for line in option.lines} <= set(late)
    assert any(
        note.startswith("Request line 1: nothing can arrive by Sunday 15 Nov. The earliest delivery date in Valio's "
                        "data for a product that otherwise fits is Monday 16 Nov, for ")
        for note in offer.notes
    )
    assert not any(note.startswith("No option can be offered") for note in offer.notes)


def test_only_the_products_of_the_earliest_date_are_offered(
    build: Build, price: Any, stock: Any, make_request: Callable[..., PurchaseRequest]
) -> None:
    offer = build(
        [price(A, "2.48"), price(B, "2.57")],
        [stock(A, 500, available_date=TUESDAY), stock(B, 500, available_date=WEDNESDAY)],
        make_request(100, needed_by=SUNDAY),
    )

    (only,) = offer.options
    assert [(line.product_id, line.availability.available_date) for line in only.lines] == [(A, TUESDAY)]
    assert only.title == "Alternative: delivered Tuesday 17 Nov, 2 days later than asked"
    assert only.lines[0].availability.state is AvailabilityState.CONFIRMED


def test_a_request_that_something_meets_in_time_is_answered_as_before(
    build: Build, price: Any, stock: Any, make_request: Callable[..., PurchaseRequest]
) -> None:
    offer = build(
        [price(A, "2.48"), price(B, "2.57")],
        [stock(A, 50, available_date=SUNDAY), stock(B, 500, available_date=TUESDAY)],
        make_request(100, needed_by=SUNDAY),
    )

    assert [(option.kind, option.title) for option in offer.options] == [
        (OptionKind.BEST_CONFIRMED, "Best confirmed option (partial fill)"),
    ]
    assert [line.product_id for line in offer.options[0].lines] == [A]
    assert not any(note.startswith("Nothing can arrive") for note in offer.notes)


def test_confirmed_data_only_gets_no_later_option_and_the_first_note_names_the_date_and_the_request_to_send(
    build: Build, price: Any, stock: Any, make_request: Callable[..., PurchaseRequest]
) -> None:
    offer = build(
        [price(A, "2.48")], [stock(A, 500, available_date=TUESDAY)],
        make_request(100, needed_by=SUNDAY, require_confirmed=True),
    )

    assert offer.options == ()
    assert offer.notes[0] == (
        "Nothing can arrive by Sunday 15 Nov. The earliest date on which a product that otherwise fits can be "
        "delivered is Tuesday 17 Nov: send the same request with needed_by 2026-11-17 to be offered it."
    )
    assert offer.notes[-1].startswith("No option can be offered")


def test_a_line_that_stands_in_for_a_recipes_ingredient_gets_no_later_option(
    build: Build, price: Any, stock: Any
) -> None:
    """The menu planner asks whether an alternative can be had in time: a late one must not read as one."""
    line = RequestLine(
        text="100 L lactose-free milk in place of cream", product_type="milk",
        required_claims=("FREE_FROM_LACTOSE",), quantity=Decimal(100), unit=Unit.L, stands_in_for="cream",
        stands_in_role="the liquid of the sauce",
    )

    offer = build(
        [price(A, "2.48")], [stock(A, 500, available_date=TUESDAY)],
        PurchaseRequest(needed_by=SUNDAY, lines=(line,)),
    )

    assert offer.options == ()
    assert offer.notes[0].startswith("Nothing can arrive by Sunday 15 Nov. The earliest date on which")


def test_no_later_option_and_no_first_note_when_no_late_product_would_fit_on_its_own_date(
    build: Build, price: Any, stock: Any, make_request: Callable[..., PurchaseRequest]
) -> None:
    # No price: late, and it could not be offered on any date.
    offer = build([], [stock(A, 500, available_date=TUESDAY)], make_request(100, needed_by=SUNDAY))

    assert offer.options == ()
    assert not any(note.startswith("Nothing can arrive") for note in offer.notes)


def test_a_request_of_two_lines_that_are_both_late_is_offered_for_the_day_the_last_one_arrives(
    build: Build, price: Any, stock: Any
) -> None:
    milk = RequestLine(text="100 L lactose-free milk", product_type="milk", required_claims=("FREE_FROM_LACTOSE",),
                       quantity=Decimal(100), unit=Unit.L)
    other = RequestLine(text="50 L of 462775", product_ids=(B,), quantity=Decimal(50), unit=Unit.L)

    offer = build(
        [price(A, "2.48"), price(B, "2.57")],
        [stock(A, 500, available_date=TUESDAY), stock(B, 50, available_date=WEDNESDAY)],
        PurchaseRequest(needed_by=SUNDAY, lines=(milk, other)),
    )

    (only,) = offer.options
    assert [(line.request_line_index, line.product_id) for line in only.lines] == [(0, A), (1, B)]
    assert only.title == "Alternative: delivered by Wednesday 18 Nov, 3 days later than asked"
    assert offer.notes[0] == (
        "Nothing can arrive by Sunday 15 Nov. The options are for delivery between Tuesday 17 Nov and Wednesday 18 "
        "Nov, 3 days later than asked: a person must accept the later date."
    )
