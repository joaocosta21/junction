"""Revalidation: fresh price and availability for an option's lines, and what changed (SPEC section 8, F-04)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import DataSource, Identity, OptionKind, Unit
from tta.contracts.offer import OfferOption
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers import OfferDeps, OfferService, revalidate

A, B = "469363", "462775"
LATER = datetime.fromisoformat("2026-11-14T09:00:00+02:00")
AFTER_CUTOFF = datetime.fromisoformat("2026-11-15T17:00:01+02:00")

Recheck = Callable[..., Any]


@pytest.fixture
def option(
    fake_gateway: Any, deps_for: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> OfferOption:
    """Two confirmed lines: 384 of A at 2.48 and 116 of B at 2.57, built at the capture's time."""
    gateway = fake_gateway([price(A, "2.48"), price(B, "2.57")], [stock(A, 384), stock(B, 300)])
    offer = OfferService(deps_for(gateway)).build_offer(make_request(500), agent_hotel)
    best = next(option for option in offer.options if option.kind is OptionKind.BEST_CONFIRMED)
    assert [(line.product_id, line.quantity) for line in best.lines] == [(A, 384), (B, 116)]
    return best


@pytest.fixture
def recheck(fake_gateway: Any, deps_for: Callable[..., OfferDeps], option: OfferOption) -> Recheck:
    def run(prices: Any, lines: Any, time_now: datetime = LATER) -> Any:
        gateway = fake_gateway(prices, lines, time_now)
        result = revalidate(option, deps_for(gateway))
        return result, gateway

    return run


def test_nothing_changed_is_ok(recheck: Recheck, price: Any, stock: Any) -> None:
    result, _ = recheck([price(A, "2.48"), price(B, "2.57")], [stock(A, 384), stock(B, 600)])

    assert result.ok is True
    assert result.expired is False
    assert result.changes == ()
    assert result.checked_at == LATER
    assert result.source is DataSource.REPLAY


def test_the_recheck_asks_the_supplier_again_for_the_options_products_only(
    recheck: Recheck, price: Any, stock: Any
) -> None:
    _, gateway = recheck([price(A, "2.48"), price(B, "2.57")], [stock(A, 384), stock(B, 600)])

    assert sorted(gateway.calls) == [("availability", (A, B), True), ("price", (A, B), True)]


def test_a_changed_price_is_reported(recheck: Recheck, price: Any, stock: Any) -> None:
    result, _ = recheck([price(A, "2.60"), price(B, "2.57")], [stock(A, 384), stock(B, 600)])

    assert result.ok is False
    assert result.expired is False
    assert [(change.product_id, change.field, change.before, change.after) for change in result.changes] == [
        (A, "price", "€2.48", "€2.60")
    ]
    assert "2.48" in result.changes[0].sentence and "2.60" in result.changes[0].sentence


def test_a_price_that_dropped_is_a_change_too(recheck: Recheck, price: Any, stock: Any) -> None:
    result, _ = recheck([price(A, "2.40"), price(B, "2.57")], [stock(A, 384), stock(B, 600)])

    assert result.ok is False
    assert [(change.product_id, change.field, change.after) for change in result.changes] == [(A, "price", "€2.40")]


def test_a_passed_cut_off_is_reported_and_expires_the_option(recheck: Recheck, price: Any, stock: Any) -> None:
    result, _ = recheck([price(A, "2.48"), price(B, "2.57")], [stock(A, 384), stock(B, 600)], AFTER_CUTOFF)

    assert result.ok is False
    assert result.expired is True
    assert {(change.product_id, change.field) for change in result.changes} == {(A, "cutoff"), (B, "cutoff")}
    assert all(change.after == "passed" for change in result.changes)
    assert "Sunday 15 Nov at 17:00" in result.changes[0].sentence
    assert result.checked_at == AFTER_CUTOFF


def test_a_changed_price_and_a_passed_cut_off_are_both_reported(recheck: Recheck, price: Any, stock: Any) -> None:
    result, _ = recheck([price(A, "2.48"), price(B, "2.99")], [stock(A, 384), stock(B, 600)], AFTER_CUTOFF)

    assert result.expired is True
    assert (B, "price") in {(change.product_id, change.field) for change in result.changes}
    assert (A, "cutoff") in {(change.product_id, change.field) for change in result.changes}


def test_stock_that_no_longer_covers_the_line_is_reported(recheck: Recheck, price: Any, stock: Any) -> None:
    result, _ = recheck([price(A, "2.48"), price(B, "2.57")], [stock(A, 300), stock(B, 600)])

    assert result.ok is False
    assert [(change.product_id, change.field, change.before, change.after) for change in result.changes] == [
        (A, "available_amount", "384 ST", "300 ST")
    ]
    assert "384" in result.changes[0].sentence


def test_stock_that_moved_but_still_covers_the_line_is_not_a_change(recheck: Recheck, price: Any, stock: Any) -> None:
    result, _ = recheck([price(A, "2.48"), price(B, "2.57")], [stock(A, 384), stock(B, 120)])

    assert result.ok is True
    assert result.changes == ()


def test_a_new_availability_state_is_reported(recheck: Recheck, price: Any, stock: Any) -> None:
    result, _ = recheck([price(A, "2.48"), price(B, "2.57")], [stock(A, 384), stock(B, 0)])

    assert [(change.product_id, change.field, change.before, change.after) for change in result.changes] == [
        (B, "availability_state", "confirmed", "out of stock")
    ]
    assert result.ok is False
    assert result.expired is False


def test_a_quantity_that_stops_being_confirmed_is_reported(recheck: Recheck, price: Any, stock: Any) -> None:
    result, _ = recheck([price(A, "2.48"), price(B, "2.57")], [stock(A, 999_999), stock(B, 600)])

    assert [(change.product_id, change.field, change.after) for change in result.changes] == [
        (A, "availability_state", "quantity not confirmed")
    ]


def test_a_moved_cut_off_is_reported_without_expiring_the_option(recheck: Recheck, price: Any, stock: Any) -> None:
    earlier = datetime.fromisoformat("2026-11-15T12:00:00+02:00")
    result, _ = recheck(
        [price(A, "2.48"), price(B, "2.57")], [stock(A, 384, closing_time=earlier), stock(B, 600)]
    )

    assert [(change.product_id, change.field) for change in result.changes] == [(A, "cutoff")]
    assert result.expired is False
    assert result.ok is False


def test_a_price_validity_that_changed_or_ended_is_reported(recheck: Recheck, price: Any, stock: Any) -> None:
    end_of_year = datetime.fromisoformat("2026-12-31T00:00:00+02:00")
    changed, _ = recheck(
        [price(A, "2.48", valid_to=end_of_year), price(B, "2.57")], [stock(A, 384), stock(B, 600)]
    )
    ended, _ = recheck(
        [price(A, "2.48", valid_to=LATER), price(B, "2.57")], [stock(A, 384), stock(B, 600)]
    )

    assert [(change.product_id, change.field) for change in changed.changes] == [(A, "price_validity")]
    assert changed.expired is False
    assert [(change.product_id, change.field) for change in ended.changes] == [(A, "price_validity")]
    assert ended.expired is True


def test_a_price_that_is_gone_is_reported(recheck: Recheck, price: Any, stock: Any) -> None:
    result, _ = recheck([price(B, "2.57")], [stock(A, 384), stock(B, 600)])

    assert [(change.product_id, change.field, change.after) for change in result.changes] == [(A, "price", "no price")]
    assert result.ok is False


def test_an_option_past_its_valid_until_is_expired(
    fake_gateway: Any, deps_for: Any, option: OfferOption, price: Any, stock: Any
) -> None:
    # Valio now shows a later cut-off, but the option was promised only until its own valid_until.
    later_cutoff = datetime.fromisoformat("2026-11-16T17:00:00+02:00")
    gateway = fake_gateway(
        [price(A, "2.48"), price(B, "2.57")],
        [stock(A, 384, closing_time=later_cutoff), stock(B, 600, closing_time=later_cutoff)],
        AFTER_CUTOFF,
    )

    result = revalidate(option, deps_for(gateway))

    assert result.expired is True
    assert result.ok is False


def test_two_lines_of_one_product_are_checked_against_the_stock_together(
    fake_gateway: Any, deps_for: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    request = PurchaseRequest(
        lines=(
            RequestLine(text="first", product_ids=(A,), quantity=Decimal(60), unit=Unit.UNIT),
            RequestLine(text="second", product_ids=(A,), quantity=Decimal(60), unit=Unit.UNIT),
        )
    )
    built = fake_gateway([price(A, "2.48")], [stock(A, 150)])
    offer = OfferService(deps_for(built)).build_offer(request, agent_hotel)
    best = next(option for option in offer.options if option.kind is OptionKind.BEST_CONFIRMED)
    assert [line.quantity for line in best.lines] == [60, 60]

    enough = revalidate(best, deps_for(fake_gateway([price(A, "2.48")], [stock(A, 120)], LATER)))
    short = revalidate(best, deps_for(fake_gateway([price(A, "2.48")], [stock(A, 100)], LATER)))

    assert enough.ok is True
    assert [(change.product_id, change.field) for change in short.changes] == [(A, "available_amount")]


def test_replay_revalidates_tonights_offer_as_unchanged(
    service: OfferService, make_request: Any, agent_hotel: Identity, now: datetime
) -> None:
    offer = service.build_offer(make_request(1000), agent_hotel)

    for option in offer.options:
        result = service.revalidate(option)

        assert result.ok is True
        assert result.changes == ()
        assert result.checked_at == now
        assert result.source is DataSource.REPLAY
