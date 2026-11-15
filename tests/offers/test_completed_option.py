"""Decision B56: a partial fill of confirmed stock gets one more option, completed from confirmed stock of the
nearest kind, each completing line named as a substitute and judged as one.

The brief's own sentence, hotel kitchen, "1,000 litres of lactose-free milk by Monday": 435 L of plain
lactose-free milk are confirmed (384 x 469363, 51 x 462775) and 698 L of lactose-free milk made for coffee
(463380, a product type of its own). The first two options stay as they were; a third holds all 1,000 L.
Scores on the 20% "how precisely the agent matches what the buyer asked for", and it is the centre of the demo.
Replay over the capture of 14 Nov, at the recording's clock and at the demo clock (Thu 12 Nov 2026 14:15).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.config import Settings
from tta.contracts.common import (
    AllergenStrictness,
    AvailabilityState,
    CheckResult,
    ConstraintKind,
    Identity,
    IdentityKind,
    OptionKind,
    Unit,
    Verdict,
)
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.product import ReplaceVerdict
from tta.offers import OfferDeps, OfferService, build_offer
from tta.offers.safety import has_doubt
from tta.valio import ReplayGateway

DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
A, B = "469363", "462775"  # plain lactose-free milks: the two with confirmed stock in the recording
UNCONFIRMED = "464306"  # the cheapest plain lactose-free milk; its quantity is not confirmed
ARLA_CAFE = "463380"  # Arla Cafè milk 1 L UHT lactose free: type coffee_milk, states lactose FREE_FROM
VALIO_COFFEE = "464237"  # Valio coffee milk 1 l lactose free UHT: states nothing about lactose as an allergen
PLACEHOLDER = 999_999
TITLE = "Alternative: confirmed stock, completed with a substitute"
FIRST_SUMMARY = (
    "2 confirmed products cover 435 L of the 1,000 L asked for (565 L missing), for €1,083.39 before tax. Arla "
    "Milkdrink 1L lactose free fat free UHT Suomesta (462775) differs in formula from Arla Semi skimmed milkdrink 1 "
    "L UHT lactose free Suomesta (469363), which fills the same request line: fat 0 g, not 1.5 g. Milk made "
    "for coffee is not offered as milk: it appears only as a named substitute, or when coffee milk is asked for by "
    "name (product type coffee_milk)."
)
SECOND_SUMMARY = (
    "Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free (464306) for the 1,000 L asked "
    "for, €1,010.00 before tax. Valio does not confirm the quantity in stock, so a human must approve this option."
)
THIRD_LEAD = (
    "All 1,000 L from confirmed stock, if 565 L may be Arla Cafè milk 1 L UHT lactose free (463380) at €2.65 per L: "
    "€2,580.64 before tax."
)
COMPARED_WITH = " It was compared with Arla Semi skimmed milkdrink 1 L UHT lactose free Suomesta (469363)."

Build = Callable[..., Offer]


@pytest.fixture(scope="module", params=["recording", "demo"])
def milk(
    request: pytest.FixtureRequest, deps_for: Callable[..., OfferDeps], make_request: Callable[..., Any],
    agent_hotel: Identity,
) -> Offer:
    """The brief's sentence for the hotel, at the recording's clock and at the demo clock."""
    clock = DEMO_CLOCK if request.param == "demo" else None
    deps = deps_for(ReplayGateway(Settings.for_tests().replay_capture_dir, demo_clock=clock))
    return OfferService(deps).build_offer(make_request(1000), agent_hotel)


def completed(offer: Offer) -> OfferOption | None:
    return next((option for option in offer.options if option.title.startswith(TITLE)), None)


# --- the brief's sentence -------------------------------------------------------------------------------------

def test_the_first_two_options_are_what_they_were(milk: Offer) -> None:
    first, second = milk.options[:2]

    assert (first.option_id, first.rank, first.kind) == ("opt_1", 1, OptionKind.BEST_CONFIRMED)
    assert (first.title, first.summary) == ("Best confirmed option (partial fill)", FIRST_SUMMARY)
    assert [(line.product_id, line.quantity, line.net) for line in first.lines] == [
        (A, 384, Decimal("952.32")), (B, 51, Decimal("131.07")),
    ]
    assert (first.totals.net, first.fill_ratio) == (Decimal("1083.39"), Decimal("0.435"))
    assert (first.coverage[0].covered, first.coverage[0].missing) == (435, 565)
    assert first.decision.rule_ids == ("P-01", "P-03")
    assert (second.option_id, second.rank, second.kind) == ("opt_2", 2, OptionKind.ALTERNATIVE_UNCONFIRMED)
    assert (second.title, second.summary) == ("Alternative: quantity not confirmed", SECOND_SUMMARY)
    assert [(line.product_id, line.quantity, line.net) for line in second.lines] == [
        (UNCONFIRMED, 1000, Decimal("1010.00")),
    ]
    assert second.decision.rule_ids == ("F-01", "P-01")


def test_a_third_option_holds_all_1000_litres_from_confirmed_stock(milk: Offer) -> None:
    assert len(milk.options) == 3
    third = milk.options[2]

    assert (third.option_id, third.rank, third.kind, third.title) == ("opt_3", 3, OptionKind.SUBSTITUTE, TITLE)
    assert [(line.product_id, line.quantity, line.covers) for line in third.lines] == [
        (A, 384, 384), (B, 51, 51), (ARLA_CAFE, 565, 565),
    ]
    assert all(line.availability.state is AvailabilityState.CONFIRMED for line in third.lines)
    assert all(line.quantity <= line.availability.usable_amount for line in third.lines)
    assert (third.totals.net, third.fill_ratio, third.coverage[0].missing) == (Decimal("2580.64"), 1, 0)
    assert third.lines[2].net == Decimal("1497.25")  # 565 x €2.65


def test_the_third_option_says_in_one_sentence_what_it_is_then_what_differs(milk: Offer) -> None:
    third = milk.options[2]
    stand_in = third.lines[2].substitute

    assert third.summary.startswith(THIRD_LEAD + " " + stand_in.replaceable.sentence + COMPARED_WITH)
    assert "made for coffee" in third.summary and "fat 3 g, not 1.5 g" in third.summary


def test_the_coffee_milk_is_named_as_a_substitute_with_what_differs(milk: Offer) -> None:
    own, stand_in = milk.options[2].lines[:2], milk.options[2].lines[2]
    info = stand_in.substitute

    assert all(line.substitute is None for line in own)
    assert (info.original_id, info.listed_by_supplier, info.claims_lost) == (A, False, ())
    assert info.replaceable.verdict is ReplaceVerdict.NOT_LIKE_FOR_LIKE
    assert (info.replaceable.types, info.replaceable.original_types) == (("coffee_milk",), ("milk",))
    assert info.replaceable.uses == ("coffee",)
    assert info.formula is not None and info.formula.keeps_formula is False
    for said in ("made for coffee", "fat 3 g, not 1.5 g", "€0.17 more per L"):
        assert said in info.gives_up
    # The option says which constraint it does not meet: the product type asked for.
    kind = next(check for check in milk.options[2].constraint_checks if check.kind is ConstraintKind.PRODUCT_TYPE)
    assert (kind.result, kind.sentence) == (CheckResult.NOT_MET, "Not of the product type 'milk': 463380.")


def test_the_third_option_goes_to_a_person_under_the_rule_for_a_substitute(milk: Offer) -> None:
    decision = milk.options[2].decision

    assert decision.verdict is Verdict.APPROVAL
    assert "F-12" in decision.rule_ids  # a substitute that is not a like-for-like replacement
    assert "P-01" in decision.rule_ids  # €2,580.64 is above the hotel's €750 per order


def test_a_person_confirms_it_also_where_the_agent_may_order_alone_and_no_limit_is_passed(
    replay_deps: OfferDeps, make_request: Callable[..., Any], policy: Any
) -> None:
    alone = policy.get_profile("hotel-kitchen").model_copy(
        update={"auto_order_enabled": True, "max_order_net_eur": Decimal(100_000),
                "max_daily_net_eur": Decimal(100_000)}
    )

    offer = build_offer(make_request(1000), alone, replay_deps, agent_id="agent:hotel-kitchen")

    third = completed(offer)
    assert third is not None and third.totals.net == Decimal("2580.64")
    assert third.decision.verdict is Verdict.APPROVAL
    assert "F-12" in third.decision.rule_ids and "P-01" not in third.decision.rule_ids


def test_under_confirmed_data_only_the_completed_option_stays_and_the_unconfirmed_one_goes(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(1000, require_confirmed=True), agent_hotel)

    assert [option.kind for option in offer.options] == [OptionKind.BEST_CONFIRMED, OptionKind.SUBSTITUTE]
    assert offer.options[1].title == TITLE and offer.options[1].fill_ratio == 1
    assert all(line.confirmed_for_order(dated=True) for option in offer.options for line in option.lines)


def test_a_request_met_in_full_gets_no_completed_option_and_no_second_lookup(
    replay: object, counting: Callable[..., Any], deps_for: Callable[..., OfferDeps],
    make_request: Callable[..., Any], agent_hotel: Identity,
) -> None:
    gateway = counting(replay)

    offer = OfferService(deps_for(gateway)).build_offer(make_request(100), agent_hotel)

    assert completed(offer) is None
    assert not any(line.substitute for option in offer.options for line in option.lines)
    assert sorted(endpoint for endpoint, _, _ in gateway.calls) == ["availability", "price"]


# --- when the completed option is offered, with hand-built stock -------------------------------------------------

def test_the_nearest_kind_completes_a_partial_fill_and_is_listed_last(
    build: Build, price: Any, stock: Any, make_request: Any
) -> None:
    offer = build(
        [price(A, "2.48"), price(UNCONFIRMED, "1.01"), price(ARLA_CAFE, "2.65")],
        [stock(A, 300), stock(UNCONFIRMED, PLACEHOLDER), stock(ARLA_CAFE, 800)],
        make_request(1000),
    )

    assert [option.kind for option in offer.options] == [
        OptionKind.BEST_CONFIRMED, OptionKind.ALTERNATIVE_UNCONFIRMED, OptionKind.SUBSTITUTE,
    ]
    last = offer.options[-1]
    assert [(line.product_id, line.quantity) for line in last.lines] == [(A, 300), (ARLA_CAFE, 700)]
    assert last.summary.startswith(
        "All 1,000 L from confirmed stock, if 700 L may be Arla Cafè milk 1 L UHT lactose free (463380) at €2.65 "
        "per L: €2,599.00 before tax."
    )


def test_no_completed_option_when_the_quantity_and_the_buyers_minimum_are_out_of_reach(
    build: Build, price: Any, stock: Any, make_request: Any
) -> None:
    # 300 L confirmed and 100 L of coffee milk: 40% of the 1,000 L, below the hotel's 90%.
    offer = build([price(A, "2.48"), price(ARLA_CAFE, "2.65")], [stock(A, 300), stock(ARLA_CAFE, 100)],
                  make_request(1000))

    assert [option.kind for option in offer.options] == [OptionKind.BEST_CONFIRMED]


def test_a_completion_that_reaches_the_buyers_minimum_is_offered_and_says_what_is_still_missing(
    build: Build, price: Any, stock: Any, make_request: Any
) -> None:
    # 300 L confirmed and 650 L of coffee milk: 95% of the 1,000 L, above the hotel's 90%.
    offer = build([price(A, "2.48"), price(ARLA_CAFE, "2.65")], [stock(A, 300), stock(ARLA_CAFE, 650)],
                  make_request(1000))

    last = offer.options[-1]
    assert (last.title, last.fill_ratio) == (TITLE + " (partial fill)", Decimal("0.95"))
    assert last.summary.startswith(
        "950 L of the 1,000 L asked for (50 L missing) from confirmed stock, if 650 L may be Arla Cafè milk 1 L UHT "
        "lactose free (463380) at €2.65 per L: €2,466.50 before tax."
    )


def test_a_product_whose_quantity_is_not_confirmed_never_completes(
    build: Build, price: Any, stock: Any, make_request: Any
) -> None:
    offer = build(
        [price(A, "2.48"), price(ARLA_CAFE, "2.65")], [stock(A, 300), stock(ARLA_CAFE, PLACEHOLDER)],
        make_request(1000),
    )

    assert completed(offer) is None
    assert ARLA_CAFE not in {line.product_id for option in offer.options for line in option.lines}


def test_a_product_that_lacks_a_claim_the_request_requires_never_completes(
    build: Build, price: Any, stock: Any, make_request: Any
) -> None:
    regular = "463149"  # Valio Plus skimmed milk 1 l: milk, and not lactose-free
    offer = build([price(A, "2.48"), price(regular, "1.10")], [stock(A, 300), stock(regular, 5000)],
                  make_request(1000))

    assert completed(offer) is None


def test_a_request_that_names_its_product_by_id_keeps_its_own_stand_in(
    build: Build, price: Any, stock: Any, make_request: Any
) -> None:
    offer = build(
        [price(A, "2.48"), price(ARLA_CAFE, "2.65")], [stock(A, 300), stock(ARLA_CAFE, 800)],
        make_request(1000, product_ids=(A,)),
    )

    assert completed(offer) is None


def test_an_allergen_the_buyer_excludes_never_comes_in_with_the_completion(
    build: Build, price: Any, stock: Any, make_request: Any
) -> None:
    # Lactose as an allergen code (ML), strict: 469363 and Arla Cafè milk state FREE_FROM; Valio's coffee milk
    # states nothing about it, so its data leaves a doubt and it must not complete the line, whatever its stock.
    excluding = dict(exclude_allergens=("ML",), allergen_strictness=AllergenStrictness.STRICT)
    doubtful_only = build(
        [price(A, "2.48"), price(VALIO_COFFEE, "1.30")], [stock(A, 300), stock(VALIO_COFFEE, 5000)],
        make_request(1000, **excluding),
    )
    with_a_safe_one = build(
        [price(A, "2.48"), price(VALIO_COFFEE, "1.30"), price(ARLA_CAFE, "2.65")],
        [stock(A, 300), stock(VALIO_COFFEE, 5000), stock(ARLA_CAFE, 800)],
        make_request(1000, **excluding),
    )

    assert completed(doubtful_only) is None
    last = completed(with_a_safe_one)
    assert last is not None
    assert [(line.product_id, line.quantity) for line in last.lines] == [(A, 300), (ARLA_CAFE, 700)]
    assert not any(has_doubt(line) for line in last.lines)
    assert VALIO_COFFEE not in {line.product_id for line in last.lines}


def test_where_the_formula_matters_a_product_of_another_formula_never_completes(
    build: Build, price: Any, stock: Any, make_request: Any
) -> None:
    # The bakery's profile says the formula matters on every line; Arla Cafè milk has 3 g of fat, not 1.5 g.
    prices, lines = [price(A, "2.48"), price(ARLA_CAFE, "2.65")], [stock(A, 300), stock(ARLA_CAFE, 800)]
    agent_bakery = Identity(
        kind=IdentityKind.AGENT, id="agent:bakery-cafe", display_name="Bakery agent", profile_id="bakery-cafe"
    )

    bakery = build(prices, lines, make_request(1000), identity=agent_bakery)
    asked = build(prices, lines, make_request(1000, keep_formula=True))

    assert completed(bakery) is None and completed(asked) is None


def test_the_completed_option_never_takes_the_place_of_another_option(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    """Three options were the most an offer held; the completed one is one more, after them."""
    offer = service.build_offer(make_request(1000, unit=Unit.L), agent_hotel)

    assert [option.rank for option in offer.options] == [1, 2, 3]
    assert [option.title.startswith(TITLE) for option in offer.options] == [False, False, True]
