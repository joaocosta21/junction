"""Scenario 1 (SPEC section 13): hotel kitchen, "1,000 litres of lactose-free milk by Monday".

Replay over tonight's capture with the clock pinned to its `timeNow`. The structure must hold whatever
the stock is; the last tests pin what tonight's capture selects.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

import pytest

from tta.contracts.availability import QUANTITY_NOT_CONFIRMED_THRESHOLD
from tta.contracts.common import (
    AvailabilityState,
    ClaimName,
    ConstraintKind,
    DataSource,
    ExclusionReason,
    Identity,
    OptionKind,
    Verdict,
)
from tta.contracts.offer import Offer, OfferOption
from tta.offers import OfferDeps, OfferService

PORTION_PACK_ID = "463203"
CLAIMS_IN_ORDER = (
    ClaimName.PRICE, ClaimName.QUANTITY, ClaimName.DELIVERY_DATE, ClaimName.ALLERGENS, ClaimName.ORIGIN
)


@pytest.fixture(scope="module")
def offer(service: OfferService, make_request: Callable[..., object], agent_hotel: Identity) -> Offer:
    return service.build_offer(make_request(1000), agent_hotel)


def test_option_1_is_the_best_confirmed_option_and_holds_confirmed_lines_only(offer: Offer) -> None:
    first = offer.options[0]

    assert first.option_id == "opt_1"
    assert first.rank == 1
    assert first.kind is OptionKind.BEST_CONFIRMED
    assert all(line.availability.state is AvailabilityState.CONFIRMED for line in first.lines)
    assert all(line.quantity <= line.availability.usable_amount for line in first.lines)


def test_an_unconfirmed_alternative_exists_as_a_full_option(
    offer: Offer, option_of: Callable[..., OfferOption | None]
) -> None:
    alternative = option_of(offer, "ALTERNATIVE_UNCONFIRMED")

    assert alternative is not None
    assert alternative.rank > 1
    assert [line.availability.state for line in alternative.lines] == [AvailabilityState.QUANTITY_NOT_CONFIRMED]
    assert alternative.totals.net > 0
    assert alternative.decision is not None
    assert alternative.decision.verdict is Verdict.APPROVAL  # F-01: ordering it always needs a human
    assert "F-01" in alternative.decision.rule_ids


def test_the_portion_pack_is_excluded_as_a_portion_pack(offer: Offer) -> None:
    excluded = {exclusion.product_id: exclusion for exclusion in offer.excluded}

    assert excluded[PORTION_PACK_ID].reason is ExclusionReason.PORTION_PACK
    assert PORTION_PACK_ID not in {line.product_id for option in offer.options for line in option.lines}


def test_every_excluded_product_has_a_reason_and_a_sentence(offer: Offer) -> None:
    assert offer.excluded
    for exclusion in offer.excluded:
        assert isinstance(exclusion.reason, ExclusionReason)
        assert exclusion.sentence.strip().endswith(".")
        assert exclusion.name
    ids = [exclusion.product_id for exclusion in offer.excluded]
    assert len(ids) == len(set(ids))  # one reason per product


def test_no_offered_product_is_also_excluded(offer: Offer) -> None:
    offered = {line.product_id for option in offer.options for line in option.lines}
    excluded = {exclusion.product_id for exclusion in offer.excluded}

    assert offered.isdisjoint(excluded)
    assert offer.candidates_considered >= len(offered | excluded)


def test_each_thing_the_buyer_asked_for_has_a_constraint_check(offer: Offer) -> None:
    for option in offer.options:
        asked = {(check.kind, check.subject) for check in option.constraint_checks}
        kinds = {check.kind for check in option.constraint_checks}

        assert (ConstraintKind.PRODUCT_TYPE, "milk") in asked
        assert (ConstraintKind.CLAIM, "FREE_FROM_LACTOSE") in asked
        assert (ConstraintKind.NEEDED_BY, "2026-11-16") in asked
        assert {ConstraintKind.QUANTITY, ConstraintKind.PACK} <= kinds
        assert all(check.sentence.strip() for check in option.constraint_checks)


def test_every_line_carries_the_five_claims_in_order(offer: Offer) -> None:
    for option in offer.options:
        for line in option.lines:
            assert tuple(check.claim for check in line.claims) == CLAIMS_IN_ORDER


def test_no_placeholder_amount_is_a_quantity_or_enters_a_total(offer: Offer) -> None:
    for option in offer.options:
        for line in option.lines:
            assert line.quantity < QUANTITY_NOT_CONFIRMED_THRESHOLD
            assert line.net == (line.quantity * line.unit_net_price).quantize(Decimal("0.01"))
        assert option.totals.net == sum(line.net for line in option.lines)
        assert option.coverage[0].covered <= option.coverage[0].requested


def test_totals_add_tax_from_the_price_answer(offer: Offer) -> None:
    first = offer.options[0]

    for line in first.lines:
        assert line.tax_rate == Decimal("13.5")
        assert line.tax == (line.net * Decimal("0.135")).quantize(Decimal("0.01"))
        assert line.gross == line.net + line.tax
    assert first.totals.gross == first.totals.net + first.totals.tax
    assert first.totals.currency == "EUR"
    assert first.totals.is_ceiling is False
    assert first.totals.excludes_deposits is False


def test_valid_until_is_the_earliest_price_validity_and_cut_off_of_the_lines(offer: Offer) -> None:
    for option in offer.options:
        moments = [line.price_valid_to for line in option.lines] + [
            line.availability.closing_time for line in option.lines
        ]

        assert option.valid_until == min(moment for moment in moments if moment is not None)
    assert offer.options[0].valid_until == datetime.fromisoformat("2026-11-15T17:00:00+02:00")


def test_the_offer_says_where_its_data_came_from(offer: Offer, now: datetime, agent_hotel: Identity) -> None:
    assert re.fullmatch(r"off_[0-9a-f]{12}", offer.offer_id)
    assert offer.source is DataSource.REPLAY
    assert offer.time_now == now
    assert offer.profile_id == "hotel-kitchen"
    assert offer.agent_id == agent_hotel.id
    assert [option.option_id for option in offer.options] == [f"opt_{n}" for n in range(1, len(offer.options) + 1)]
    assert [option.rank for option in offer.options] == list(range(1, len(offer.options) + 1))
    assert len(offer.options) <= 3


def test_the_offer_costs_one_price_call_and_one_availability_call(
    replay: object,
    counting: Callable[..., object],
    deps_for: Callable[..., OfferDeps],
    make_request: Callable[..., object],
    agent_hotel: Identity,
) -> None:
    gateway = counting(replay)

    OfferService(deps_for(gateway)).build_offer(make_request(1000), agent_hotel)

    assert sorted(endpoint for endpoint, _, _ in gateway.calls) == ["availability", "price"]
    assert all(fresh is False for _, _, fresh in gateway.calls)


def test_every_option_carries_the_policy_verdict_with_the_rules_named(offer: Offer) -> None:
    for option in offer.options:
        assert option.decision is not None
        assert option.decision.profile_id == "hotel-kitchen"
        assert option.decision.sentence.strip()
    first = offer.options[0].decision

    assert first.verdict is Verdict.APPROVAL  # above the 750 EUR limit per order of hotel-kitchen
    assert "P-01" in first.rule_ids


def test_tonight_two_confirmed_milks_cover_435_of_the_1000_litres_cheapest_first(offer: Offer) -> None:
    """Until 14 Nov a third line, 565 x 463380 Arla Cafè milk, filled the rest for €2,580.64 in all. Milk for
    coffee is now a product type of its own, so the confirmed stock of plain milk is all there is: 435 litres."""
    first = offer.options[0]

    assert [(line.product_id, line.quantity) for line in first.lines] == [
        ("469363", Decimal(384)), ("462775", Decimal(51)),
    ]
    assert first.totals.net == Decimal("1083.39")
    assert first.fill_ratio == Decimal("0.435")
    assert first.is_partial is True
    assert first.coverage[0].missing == 565


def test_tonight_the_cheapest_unconfirmed_milk_is_the_alternative(
    offer: Offer, option_of: Callable[..., OfferOption | None]
) -> None:
    alternative = option_of(offer, "ALTERNATIVE_UNCONFIRMED")

    assert alternative is not None
    assert [(line.product_id, line.quantity) for line in alternative.lines] == [("464306", Decimal(1000))]
    assert alternative.totals.net == Decimal("1010.00")
    assert alternative.lines[0].availability.usable_amount is None


def test_tonight_the_product_priced_per_kilogram_drops_out_with_pack_size_unknown(offer: Offer) -> None:
    excluded = {exclusion.product_id: exclusion.reason for exclusion in offer.excluded}

    # 472492 is priced per kg and has no volume; the catalog may also stop listing it as milk.
    assert excluded.get("472492", ExclusionReason.PACK_SIZE_UNKNOWN) is ExclusionReason.PACK_SIZE_UNKNOWN
    assert excluded["464440"] is ExclusionReason.NOT_DELIVERABLE
    assert excluded["464179"] is ExclusionReason.CUTOFF_PASSED
