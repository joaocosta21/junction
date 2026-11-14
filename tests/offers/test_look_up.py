"""One look at price and availability comes from one source (SPEC section 5 step 1, review round 3).

Scores on the 20% "what an agent can trust": an offer is never built on a live price and a replayed stock
figure, and neither is the re-check before an order.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

import pytest

from tta.contracts.availability import AvailabilityResponse, PriceResponse
from tta.contracts.common import DataSource, Identity, OptionKind
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import PairedLookup
from tta.offers import OfferDeps, OfferService, revalidate
from tta.offers.deps import look_up

A, B = "469363", "462775"


class PairedGateway:
    """A gateway with the `PairedLookup` port. Its two single calls must never be used when the pair exists."""

    def __init__(self, inner: Any, price_source: DataSource, availability_source: DataSource) -> None:
        self._inner = inner
        self._sources = (price_source, availability_source)
        self.looks: list[tuple[tuple[str, ...], bool]] = []

    @property
    def source(self) -> DataSource:
        return DataSource.LIVE

    def now(self) -> datetime:
        return self._inner.now()

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        raise AssertionError("a gateway with a paired lookup must be asked through it")

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:
        raise AssertionError("a gateway with a paired lookup must be asked through it")

    def look_up(
        self, product_ids: Sequence[str], *, fresh: bool = False
    ) -> tuple[PriceResponse, AvailabilityResponse]:
        self.looks.append((tuple(product_ids), fresh))
        price = self._inner.price(product_ids, fresh=fresh).model_copy(update={"source": self._sources[0]})
        availability = self._inner.availability(product_ids, fresh=fresh).model_copy(
            update={"source": self._sources[1]}
        )
        return price, availability


class TwoSourceGateway:
    """A gateway without the paired port whose two calls answer from two different sources."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    @property
    def source(self) -> DataSource:
        return DataSource.LIVE

    def now(self) -> datetime:
        return self._inner.now()

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        return self._inner.price(product_ids, fresh=fresh).model_copy(update={"source": DataSource.LIVE})

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:
        return self._inner.availability(product_ids, fresh=fresh)  # the fake answers as a replay


@pytest.fixture
def inner(fake_gateway: Any, price: Any, stock: Any) -> Any:
    return fake_gateway([price(A, "2.48"), price(B, "2.57")], [stock(A, 384), stock(B, 300)])


def test_a_gateway_with_a_paired_lookup_is_asked_once_for_both(
    inner: Any, deps_for: Callable[..., OfferDeps]
) -> None:
    gateway = PairedGateway(inner, DataSource.LIVE, DataSource.LIVE)
    assert isinstance(gateway, PairedLookup)

    lookup = look_up(deps_for(gateway), [A, B, A])

    assert gateway.looks == [((A, B), False)]
    assert lookup.source is DataSource.LIVE
    assert lookup.price(A) is not None and lookup.line(B).schedule_line is not None
    assert lookup.now == inner.time_now


def test_a_gateway_without_a_paired_lookup_gets_one_price_call_and_one_availability_call(
    inner: Any, deps_for: Callable[..., OfferDeps]
) -> None:
    assert not isinstance(inner, PairedLookup)

    lookup = look_up(deps_for(inner), [A, B])

    assert inner.calls == [("price", (A, B), False), ("availability", (A, B), False)]
    assert lookup.source is DataSource.REPLAY


@pytest.mark.parametrize(
    ("price_source", "availability_source"),
    [(DataSource.LIVE, DataSource.REPLAY), (DataSource.REPLAY, DataSource.LIVE)],
)
def test_a_pair_from_two_sources_is_refused_whatever_the_paired_lookup_returned(
    inner: Any, deps_for: Callable[..., OfferDeps], price_source: DataSource, availability_source: DataSource
) -> None:
    gateway = PairedGateway(inner, price_source, availability_source)

    with pytest.raises(SupplierUnavailable) as refused:
        look_up(deps_for(gateway), [A])

    assert "live" in refused.value.detail and "replay" in refused.value.detail


def test_two_calls_that_answer_from_two_sources_are_refused(inner: Any, deps_for: Callable[..., OfferDeps]) -> None:
    with pytest.raises(SupplierUnavailable):
        look_up(deps_for(TwoSourceGateway(inner)), [A])


def test_no_offer_is_built_on_a_live_price_and_replayed_stock(
    inner: Any, deps_for: Callable[..., OfferDeps], make_request: Any, agent_hotel: Identity
) -> None:
    service = OfferService(deps_for(TwoSourceGateway(inner)))

    with pytest.raises(SupplierUnavailable):
        service.build_offer(make_request(500), agent_hotel)


def test_with_no_id_a_paired_gateway_is_not_asked(inner: Any, deps_for: Callable[..., OfferDeps]) -> None:
    gateway = PairedGateway(inner, DataSource.LIVE, DataSource.LIVE)

    lookup = look_up(deps_for(gateway), [])

    assert gateway.looks == []
    assert (lookup.prices, lookup.availability) == ({}, {})


def test_the_recheck_before_an_order_goes_through_the_paired_lookup_and_asks_afresh(
    inner: Any, deps_for: Callable[..., OfferDeps], make_request: Any, agent_hotel: Identity
) -> None:
    offer = OfferService(deps_for(inner)).build_offer(make_request(500), agent_hotel)
    option = next(option for option in offer.options if option.kind is OptionKind.BEST_CONFIRMED)
    gateway = PairedGateway(inner, DataSource.LIVE, DataSource.LIVE)

    result = revalidate(option, deps_for(gateway))

    assert gateway.looks == [((A, B), True)]
    assert (result.ok, result.source) == (True, DataSource.LIVE)


def test_the_recheck_refuses_a_pair_from_two_sources(
    inner: Any, deps_for: Callable[..., OfferDeps], make_request: Any, agent_hotel: Identity
) -> None:
    offer = OfferService(deps_for(inner)).build_offer(make_request(500), agent_hotel)
    option = next(option for option in offer.options if option.kind is OptionKind.BEST_CONFIRMED)

    with pytest.raises(SupplierUnavailable):
        revalidate(option, deps_for(PairedGateway(inner, DataSource.LIVE, DataSource.REPLAY)))
