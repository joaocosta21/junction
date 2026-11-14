"""Price and availability as the Valio mock API states them, and what we conclude (SPEC section 4).

The wire models keep the raw values. Optional fields are omitted by the API, never null
(AIMO/docs/API.md section 7), so every optional field here defaults to `None`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from tta.contracts.common import (
    AvailabilityState,
    ClaimName,
    ClaimStatus,
    Contract,
    DataSource,
    Number,
    Quantity,
)

# One threshold covers both placeholder rules: Terminal 999999 and the very large Stock values.
# Valio confirmed on 14 Nov 2026 that a very large value means the stock is not known (FINDINGS section 1).
QUANTITY_NOT_CONFIRMED_THRESHOLD = Decimal(999_999)


class PriceAmount(Contract):
    """`Price` of the API: `value` excludes tax, `value_with_tax` includes it."""

    value: Number
    value_with_tax: Number
    valid_from: datetime
    valid_to: datetime
    currency: str


class PriceLine(Contract):
    """One product of a /api/price response. `error` true means no price could be found."""

    product_id: str
    error: bool
    net_price_found: bool = False
    catalog_price: PriceAmount | None = None
    list_price: PriceAmount | None = None
    comparison_price: PriceAmount | None = None
    comparison_unit: str | None = None  # KG or L
    tax_rate: Number | None = None  # percent; authoritative over the product file's vatCode
    tax_value: Number | None = None
    not_in_recording: bool = False  # replay only: no recorded answer for this id; says nothing about Valio

    @property
    def has_price(self) -> bool:
        return not self.error and self.catalog_price is not None


class PriceResponse(Contract):
    currency: str
    pricing_date: datetime | None = None
    lines: tuple[PriceLine, ...] = ()
    source: DataSource
    retrieved_at: datetime | None = None

    def by_id(self) -> dict[str, PriceLine]:
        return {line.product_id: line for line in self.lines}


class ScheduleLine(Contract):
    sales_block: bool
    available_amount: Number  # raw value; a placeholder at or above the threshold is not a quantity
    available_date: date | None = None
    sales_unit: str


class AvailabilityLine(Contract):
    """One product of a /api/availability response. No schedule line: cannot be delivered on any date."""

    product_id: str
    sales_block: bool
    closing_time: datetime | None = None
    logistic_model: str | None = None  # "Stock" or "Terminal"
    schedule_line: ScheduleLine | None = None
    not_in_recording: bool = False  # replay only: no recorded answer for this id; says nothing about Valio


class AvailabilityResponse(Contract):
    time_now: datetime  # server time of the answer; the clock every cut-off is compared with
    requested_date: datetime | None = None
    lines: tuple[AvailabilityLine, ...] = ()
    source: DataSource

    def by_id(self) -> dict[str, AvailabilityLine]:
        return {line.product_id: line for line in self.lines}


class AvailabilityAssessment(Contract):
    """One of the six states for one product, with a sentence written for a buyer."""

    product_id: str
    state: AvailabilityState
    usable_amount: Quantity | None = None  # None unless the state is CONFIRMED: nothing sums a placeholder
    sales_unit: str | None = None
    available_date: date | None = None
    closing_time: datetime | None = None
    logistic_model: str | None = None
    sentence: str

    @property
    def is_orderable_state(self) -> bool:
        return self.state in (AvailabilityState.CONFIRMED, AvailabilityState.QUANTITY_NOT_CONFIRMED)


class ClaimCheck(Contract):
    """Whether Valio's data confirms one claim of an offer line (the trust protocol)."""

    claim: ClaimName
    status: ClaimStatus
    sentence: str


class RevalidationChange(Contract):
    """One thing that differs between the offer and a fresh look at price and availability."""

    product_id: str
    field: str  # "price", "price_validity", "availability_state", "available_amount", "cutoff"
    before: str
    after: str
    sentence: str


class RevalidationResult(Contract):
    """Fresh price and availability for an option's lines, compared with what the offer stated."""

    ok: bool  # True: nothing changed and nothing expired
    expired: bool = False  # the option's valid_until, a price validity or a cut-off has passed
    changes: tuple[RevalidationChange, ...] = ()
    checked_at: datetime
    source: DataSource
