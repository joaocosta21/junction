"""Helpers for the availability tests: recorded entries of the mock API as contract models, and hand-built lines.

The Valio client (T01) owns the real parser. These few lines only let the tests read a recorded
entry without depending on another package.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.availability import verify
from tta.contracts.availability import AvailabilityLine, ClaimCheck, PriceAmount, PriceLine, ScheduleLine
from tta.contracts.common import ClaimName
from tta.contracts.product import Product

LineParser = Callable[[dict[str, Any]], AvailabilityLine]
PriceParser = Callable[[dict[str, Any]], PriceLine]
LineBuilder = Callable[..., AvailabilityLine]
PriceBuilder = Callable[..., PriceLine]
ProductBuilder = Callable[..., Product]
ClaimOf = Callable[..., ClaimCheck]

DEMO_NOW = datetime.fromisoformat("2026-11-14T02:52:45+02:00")  # timeNow of tonight's capture
OPEN_CUTOFF = datetime.fromisoformat("2026-11-15T17:00:00+02:00")
DELIVERY_DAY = date(2026, 11, 16)
VALID_FROM = datetime.fromisoformat("2026-01-13T00:00:00+02:00")
OPEN_ENDED = datetime.fromisoformat("9999-12-31T00:00:00+02:00")  # validTo of a price with no end date


def _schedule_line(raw: dict[str, Any]) -> ScheduleLine:
    available_date = raw.get("availableDate")
    return ScheduleLine(
        sales_block=raw["salesBlock"],
        available_amount=Decimal(str(raw["availableAmount"])),
        available_date=date.fromisoformat(available_date) if available_date else None,
        sales_unit=raw["salesUnit"],
    )


def _availability_line(raw: dict[str, Any]) -> AvailabilityLine:
    schedule_lines = raw.get("scheduleLines") or []
    closing_time = raw.get("closingTime")
    return AvailabilityLine(
        product_id=raw["productId"],
        sales_block=raw["salesBlock"],
        closing_time=datetime.fromisoformat(closing_time) if closing_time else None,
        logistic_model=raw.get("logisticModel"),
        schedule_line=_schedule_line(schedule_lines[0]) if schedule_lines else None,
    )


def _price_amount(raw: dict[str, Any] | None) -> PriceAmount | None:
    if raw is None:
        return None
    return PriceAmount(
        value=Decimal(str(raw["value"])),
        value_with_tax=Decimal(str(raw["valueWithTax"])),
        valid_from=datetime.fromisoformat(raw["validFrom"]),
        valid_to=datetime.fromisoformat(raw["validTo"]),
        currency=raw["currency"],
    )


def _price_line(raw: dict[str, Any]) -> PriceLine:
    return PriceLine(
        product_id=raw["productId"],
        error=raw["error"],
        net_price_found=raw["netPriceFound"],
        catalog_price=_price_amount(raw.get("catalogPrice")),
    )


def _build_line(
    amount: int | str | None = 100,
    *,
    closing_time: datetime | None = OPEN_CUTOFF,
    available_date: date | None = DELIVERY_DAY,
    sales_block: bool = False,
    line_block: bool = False,
    logistic_model: str | None = "Stock",
    sales_unit: str = "ST",
) -> AvailabilityLine:
    """A hand-built line. `amount=None` leaves the schedule line out, as the API does for an undeliverable product."""
    schedule = None
    if amount is not None:
        schedule = ScheduleLine(
            sales_block=line_block, available_amount=Decimal(amount), available_date=available_date,
            sales_unit=sales_unit,
        )
    return AvailabilityLine(
        product_id="000001", sales_block=sales_block, closing_time=closing_time, logistic_model=logistic_model,
        schedule_line=schedule,
    )


def _build_price(value: str = "2.48", valid_to: datetime = OPEN_ENDED, currency: str = "EUR") -> PriceLine:
    amount = PriceAmount(
        value=Decimal(value), value_with_tax=Decimal(value), valid_from=VALID_FROM, valid_to=valid_to,
        currency=currency,
    )
    return PriceLine(product_id="000001", error=False, catalog_price=amount)


def _build_product(**overrides: Any) -> Product:
    values: dict[str, Any] = dict(
        id="000001", name_en="Test product", category="10400", sales_unit="ST", base_unit="ST",
        allowed_lot_size=Decimal(1), country_of_origin="fi",
    )
    return Product(**{**values, **overrides})


@pytest.fixture(scope="session")
def to_line() -> LineParser:
    """Turns one recorded /api/availability entry into the contract model, raw values kept."""
    return _availability_line


@pytest.fixture(scope="session")
def to_price() -> PriceParser:
    """Turns one recorded /api/price entry into the contract model."""
    return _price_line


@pytest.fixture(scope="session")
def build_line() -> LineBuilder:
    return _build_line


@pytest.fixture(scope="session")
def build_product() -> ProductBuilder:
    return _build_product


@pytest.fixture(scope="session")
def build_price() -> PriceBuilder:
    return _build_price


@pytest.fixture(scope="session")
def claim_of() -> ClaimOf:
    """Runs `verify` with neutral defaults, on the clock of tonight's capture, and returns the check of one claim."""

    def run(claim: ClaimName, line: AvailabilityLine, *, now: datetime = DEMO_NOW, **overrides: Any) -> ClaimCheck:
        arguments: dict[str, Any] = dict(price=_build_price(), product=_build_product(), quantity=None,
                                         needed_by=None, allergen_outcome=None)
        arguments.update(overrides)
        checks = verify(line, arguments.pop("price"), arguments.pop("product"), now=now, **arguments)
        return next(check for check in checks if check.claim is claim)

    return run
