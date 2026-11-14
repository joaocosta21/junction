"""Fixtures of the catalog tests: the real catalog, loaded once, and captured price lines as contract models."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.availability import PriceAmount, PriceLine


def _amount(raw: dict[str, Any] | None) -> PriceAmount | None:
    if raw is None:
        return None
    return PriceAmount(
        value=Decimal(str(raw["value"])),
        value_with_tax=Decimal(str(raw["valueWithTax"])),
        valid_from=datetime.fromisoformat(raw["validFrom"]),
        valid_to=datetime.fromisoformat(raw["validTo"]),
        currency=raw["currency"],
    )


def price_line(raw: dict[str, Any]) -> PriceLine:
    """A captured /api/price entry as the contract model. Optional fields are absent, never null."""
    return PriceLine(
        product_id=raw["productId"],
        error=raw["error"],
        net_price_found=raw.get("netPriceFound", False),
        catalog_price=_amount(raw.get("catalogPrice")),
        list_price=_amount(raw.get("listPrice")),
        comparison_price=_amount(raw.get("comparisonPrice")),
        comparison_unit=raw.get("comparisonUnit"),
    )


@pytest.fixture(scope="session")
def catalog() -> ProductCatalog:
    """The real product file with both CSV files joined. Loaded once per session."""
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture(scope="session")
def demo_price(capture_demo: Any) -> Callable[[str], PriceLine]:
    lines = capture_demo.lines("price")
    return lambda product_id: price_line(lines[product_id])


@pytest.fixture(scope="session")
def demo_price_lines(capture_demo: Any) -> dict[str, PriceLine]:
    return {product_id: price_line(raw) for product_id, raw in capture_demo.lines("price").items()}


@pytest.fixture(scope="session")
def sample_price(capture_sample: Any) -> Callable[[str], PriceLine]:
    lines = capture_sample.lines("price")
    return lambda product_id: price_line(lines[product_id])
