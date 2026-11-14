"""Fixtures for the offer tests: the real catalog and policy over tonight's capture, and a hand-built gateway.

Every helper is a fixture, because test modules cannot import from one another (`--import-mode=importlib`).
No test here calls a live service.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.availability import (
    AvailabilityLine,
    AvailabilityResponse,
    PriceAmount,
    PriceLine,
    PriceResponse,
    ScheduleLine,
)
from tta.contracts.common import DataSource, Unit
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.ports import ValioGateway
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers import OfferDeps, OfferService
from tta.policy import RulePolicyEngine
from tta.valio import ReplayGateway

NOW = datetime.fromisoformat("2026-11-14T02:52:45+02:00")  # timeNow of tonight's capture
OPEN_CUTOFF = datetime.fromisoformat("2026-11-15T17:00:00+02:00")
MONDAY = date(2026, 11, 16)
VALID_FROM = datetime.fromisoformat("2026-01-13T00:00:00+02:00")
OPEN_ENDED = datetime.fromisoformat("9999-12-31T00:00:00+02:00")  # validTo of a price with no end date
NO_SPEND = Decimal(0)

PriceBuilder = Callable[..., PriceLine]
StockBuilder = Callable[..., AvailabilityLine]
RequestBuilder = Callable[..., PurchaseRequest]


class FakeGateway:
    """A hand-built `ValioGateway`: answers from the lines a test gives it and logs every call.

    An id it was not given reads as the mock API answers an unknown id: no price, no schedule line.
    """

    def __init__(self, prices: Iterable[PriceLine], lines: Iterable[AvailabilityLine], time_now: datetime) -> None:
        self._prices = {line.product_id: line for line in prices}
        self._lines = {line.product_id: line for line in lines}
        self.time_now = time_now
        self.calls: list[tuple[str, tuple[str, ...], bool]] = []

    @property
    def source(self) -> DataSource:
        return DataSource.REPLAY

    def now(self) -> datetime:
        return self.time_now

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        self.calls.append(("price", tuple(product_ids), fresh))
        lines = tuple(
            self._prices.get(product_id) or PriceLine(product_id=product_id, error=True)
            for product_id in dict.fromkeys(product_ids)
        )
        return PriceResponse(currency="EUR", lines=lines, source=DataSource.REPLAY, retrieved_at=self.time_now)

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:
        self.calls.append(("availability", tuple(product_ids), fresh))
        lines = tuple(
            self._lines.get(product_id) or AvailabilityLine(product_id=product_id, sales_block=False)
            for product_id in dict.fromkeys(product_ids)
        )
        return AvailabilityResponse(time_now=self.time_now, lines=lines, source=DataSource.REPLAY)


class CountingGateway:
    """Wraps a gateway and logs every call, so a test can count them."""

    def __init__(self, inner: ValioGateway) -> None:
        self._inner = inner
        self.clock = getattr(inner, "clock", inner)
        self.calls: list[tuple[str, int, bool]] = []

    @property
    def source(self) -> DataSource:
        return self._inner.source

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        self.calls.append(("price", len(product_ids), fresh))
        return self._inner.price(product_ids, fresh=fresh)

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:
        self.calls.append(("availability", len(product_ids), fresh))
        return self._inner.availability(product_ids, fresh=fresh)


def _amount(value: str, valid_from: datetime, valid_to: datetime, currency: str, tax_rate: str) -> PriceAmount:
    net = Decimal(value)
    return PriceAmount(
        value=net, value_with_tax=net * (1 + Decimal(tax_rate) / 100), valid_from=valid_from, valid_to=valid_to,
        currency=currency,
    )


def _price(
    product_id: str,
    value: str,
    *,
    per_measure: str | None = None,
    measure: str = "L",
    tax_rate: str | None = "13.5",
    valid_from: datetime = VALID_FROM,
    valid_to: datetime = OPEN_ENDED,
    currency: str = "EUR",
) -> PriceLine:
    """A hand-built price. `per_measure` is the comparison price (per litre or kg); by default the price itself."""
    rate = tax_rate or "0"
    return PriceLine(
        product_id=product_id,
        error=False,
        catalog_price=_amount(value, valid_from, valid_to, currency, rate),
        comparison_price=_amount(per_measure or value, valid_from, valid_to, currency, rate),
        comparison_unit=measure,
        tax_rate=Decimal(tax_rate) if tax_rate is not None else None,
    )


def _stock(
    product_id: str,
    amount: int | str | None,
    *,
    closing_time: datetime | None = OPEN_CUTOFF,
    available_date: date | None = MONDAY,
    sales_unit: str = "ST",
    sales_block: bool = False,
    logistic_model: str | None = "Stock",
) -> AvailabilityLine:
    """A hand-built availability line. `amount=None` leaves the schedule line out (cannot be delivered)."""
    schedule = None
    if amount is not None:
        schedule = ScheduleLine(
            sales_block=False, available_amount=Decimal(amount), available_date=available_date, sales_unit=sales_unit
        )
    return AvailabilityLine(
        product_id=product_id, sales_block=sales_block, closing_time=closing_time, logistic_model=logistic_model,
        schedule_line=schedule,
    )


def _request(
    quantity: int | str = 1000,
    unit: Unit = Unit.L,
    *,
    needed_by: date | None = MONDAY,
    require_confirmed: bool = False,
    **line: Any,
) -> PurchaseRequest:
    """A one-line request. Without other filters it asks for lactose-free milk."""
    if not any(key in line for key in ("product_type", "product_ids", "name_terms")):
        line = {"product_type": "milk", "required_claims": ("FREE_FROM_LACTOSE",), **line}
    line.setdefault("text", "a test request")
    return PurchaseRequest(
        needed_by=needed_by,
        require_confirmed=require_confirmed,
        lines=(RequestLine(quantity=Decimal(quantity), unit=unit, **line),),
    )


@pytest.fixture(scope="session")
def catalog() -> ProductCatalog:
    """The real catalog (17,546 products), built once per test session."""
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture(scope="session")
def replay() -> ReplayGateway:
    return ReplayGateway(Settings.for_tests().replay_capture_dir)


@pytest.fixture(scope="session")
def policy() -> RulePolicyEngine:
    return RulePolicyEngine.from_files()


@pytest.fixture(scope="session")
def now() -> datetime:
    return NOW


@pytest.fixture(scope="session")
def monday() -> date:
    return MONDAY


@pytest.fixture(scope="session")
def open_cutoff() -> datetime:
    return OPEN_CUTOFF


@pytest.fixture(scope="session")
def price() -> PriceBuilder:
    return _price


@pytest.fixture(scope="session")
def stock() -> StockBuilder:
    return _stock


@pytest.fixture(scope="session")
def make_request() -> RequestBuilder:
    return _request


@pytest.fixture(scope="session")
def fake_gateway() -> Callable[..., FakeGateway]:
    def build(
        prices: Iterable[PriceLine] = (), lines: Iterable[AvailabilityLine] = (), time_now: datetime = NOW
    ) -> FakeGateway:
        return FakeGateway(prices, lines, time_now)

    return build


@pytest.fixture(scope="session")
def counting() -> Callable[[ValioGateway], CountingGateway]:
    return CountingGateway


@pytest.fixture(scope="session")
def deps_for(catalog: ProductCatalog, policy: RulePolicyEngine) -> Callable[..., OfferDeps]:
    """Dependencies over the real catalog and policy, with the gateway and the day's spend a test chooses."""

    def build(gateway: Any, day_spend: Decimal = NO_SPEND) -> OfferDeps:
        clock = gateway.clock if hasattr(gateway, "clock") else gateway
        return OfferDeps(
            catalog=catalog, gateway=gateway, policy=policy, clock=clock, day_spend=lambda _profile_id: day_spend
        )

    return build


@pytest.fixture(scope="session")
def replay_deps(deps_for: Callable[..., OfferDeps], replay: ReplayGateway) -> OfferDeps:
    return deps_for(replay)


@pytest.fixture(scope="session")
def service(replay_deps: OfferDeps) -> OfferService:
    """The offer service in replay over tonight's capture, with nothing spent today."""
    return OfferService(replay_deps)


@pytest.fixture(scope="session")
def option_of() -> Callable[..., OfferOption | None]:
    def find(offer: Offer, kind: str) -> OfferOption | None:
        return next((option for option in offer.options if option.kind.value == kind), None)

    return find


@pytest.fixture(scope="session")
def build(
    fake_gateway: Callable[..., FakeGateway],
    deps_for: Callable[..., OfferDeps],
    agent_hotel: Any,
) -> Callable[..., Offer]:
    """Build an offer from hand-built prices and availability lines; for the hotel kitchen unless told otherwise."""

    def run(prices: Any, lines: Any, request: PurchaseRequest | None = None, **options: Any) -> Offer:
        identity = options.pop("identity", agent_hotel)
        time_now = options.pop("time_now", NOW)
        deps = deps_for(fake_gateway(prices, lines, time_now), **options)
        return OfferService(deps).build_offer(request or _request(1000), identity)

    return run


@pytest.fixture(scope="session")
def best() -> Callable[[Offer], OfferOption]:
    """The BEST_CONFIRMED option of an offer."""

    def find(offer: Offer) -> OfferOption:
        return next(option for option in offer.options if option.kind.value == "BEST_CONFIRMED")

    return find


@pytest.fixture(scope="session")
def reasons() -> Callable[[Offer], dict[str, Any]]:
    """Exclusion reason by product id."""

    def collect(offer: Offer) -> dict[str, Any]:
        return {exclusion.product_id: exclusion.reason for exclusion in offer.excluded}

    return collect
