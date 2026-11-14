"""Standing orders: a kitchen's recurring order, its past renewals, and the drift found before a renewal (task STAND-1).

Valio Aimo's example scenario, verbatim: "Standing order drift detection: the agent learns a kitchen's recurring
weekly order and flags anomalies (portion counts creeping up, cost drifting) before auto-renewing it." Rule P-08
reads the history (`StandingHistory`); the renewal shows what it found (`DriftReport`). This module imports no offer,
order or policy contract, because `PolicyContext` carries a `StandingHistory`; the service's answers that hold an
offer or an order are in `tta.standing.models`.

The Valio Aimo mock has no order history. A renewal made up for the demonstration says so: `synthetic` is true.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from tta.contracts.common import Contract, Number, Quantity, Ratio, Unit, UnitPrice
from tta.contracts.request import MAX_ID_LENGTH, MAX_QUANTITY, MAX_QUANTITY_DECIMALS, MAX_REQUEST_LINES, PurchaseRequest

MAX_STANDING_ORDER_ID_LENGTH = MAX_ID_LENGTH * 2  # as PurchaseRequest.standing_order_id
MAX_NAME_LENGTH = 120
MAX_CADENCE_DAYS = 366
DEFAULT_CADENCE_DAYS = 7  # weekly, as in Valio Aimo's scenario
MAX_RENEWAL_LINES = 100  # products of one renewal: far above the lines of a request
MAX_RECORD_ID_LENGTH = 64  # an id the gateway issued (tta.contracts.order)


def _plain_name(value: str) -> str:
    """A name is one line of text: no control or format character."""
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError("a name may not contain control or format characters")
    return value


StandingOrderId = Annotated[
    str, StringConstraints(min_length=1, max_length=MAX_STANDING_ORDER_ID_LENGTH, pattern=r"^[A-Za-z0-9_-]+$")
]
RecordId = Annotated[str, StringConstraints(min_length=1, max_length=MAX_RECORD_ID_LENGTH, pattern=r"^[A-Za-z0-9_-]+$")]
StandingOrderName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_NAME_LENGTH, strip_whitespace=True),
    AfterValidator(_plain_name),
]
ThisWeek = Annotated[Quantity, Field(gt=0, le=MAX_QUANTITY, decimal_places=MAX_QUANTITY_DECIMALS)]


class StandingOrder(Contract):
    """A recurring order of one buyer: the typed request it renews, every `cadence_days`."""

    standing_order_id: StandingOrderId
    profile_id: str
    agent_id: str
    name: StandingOrderName = Field(description="The buyer's own name for it, kept as data")
    request: PurchaseRequest = Field(description="The request each renewal sends again; it names no standing order")
    cadence_days: int = Field(default=DEFAULT_CADENCE_DAYS, ge=1, le=MAX_CADENCE_DAYS)
    created_at: datetime

    @model_validator(mode="after")
    def _request_is_the_template(self) -> StandingOrder:
        if self.request.standing_order_id is not None:
            raise ValueError("the request of a standing order names no standing order: a renewal sets it")
        return self


class RenewalLine(Contract):
    """One product of one past renewal."""

    request_line_index: int = Field(ge=0, lt=MAX_REQUEST_LINES)
    product_id: Annotated[str, StringConstraints(min_length=1, max_length=MAX_ID_LENGTH, pattern=r"^[A-Za-z0-9]+$")]
    quantity: Quantity = Field(gt=0, le=MAX_QUANTITY, description="What this product covered of the request line")
    unit: Unit = Field(description="The unit of the request line")
    unit_net_price_eur: UnitPrice = Field(ge=0, description="EUR before tax per sales unit")


class Renewal(Contract):
    """One past renewal of a standing order: what was ordered, at which price."""

    renewal_id: RecordId
    standing_order_id: StandingOrderId
    renewed_at: datetime
    lines: tuple[RenewalLine, ...] = Field(min_length=1, max_length=MAX_RENEWAL_LINES)
    offer_id: RecordId | None = None
    order_id: RecordId | None = None  # set when an order exists; a synthetic renewal has none
    synthetic: bool = Field(
        default=False, description="Made up for the demonstration: the Valio Aimo mock has no order history"
    )


class StandingHistory(Contract):
    """What rule P-08 reads: the standing order a request renews and its past renewals, oldest first.

    The renewal being judged is never one of them. Only a renewal whose order was placed counts: one that still
    waits for a person, was rejected or expired is left out.
    """

    standing_order_id: StandingOrderId
    name: str
    cadence_days: int = Field(default=DEFAULT_CADENCE_DAYS, ge=1, le=MAX_CADENCE_DAYS)
    renewals: tuple[Renewal, ...] = ()


class DriftKind(StrEnum):
    QUANTITY = "QUANTITY"  # the quantity asked for on a request line
    UNIT_PRICE = "UNIT_PRICE"  # the net price per sales unit of a product


class DriftCheck(Contract):
    """One comparison of this renewal with the median of the same line's last renewals."""

    kind: DriftKind
    request_line_index: int = Field(ge=0)
    product_id: str | None = None  # set for a unit price
    this_renewal: Number
    median: Number
    unit: str  # L, kg or units for a quantity; the sales unit for a unit price
    renewals: int = Field(ge=0, description="How many past renewals the median is taken over")
    drift_ratio: Ratio = Field(ge=0, description="|this renewal - median| / median")
    over_tolerance: bool
    sentence: str


class DriftReport(Contract):
    """What the history says about one renewal. Built by the policy package from the history P-08 reads."""

    standing_order_id: str
    judged: bool = Field(description="False when the history is too short: rule P-08 then does not fire")
    tolerance: Ratio | None = None  # the profile's standing_order_drift_ratio; None when the profile sets none
    checks: tuple[DriftCheck, ...] = ()
    not_compared: tuple[str, ...] = ()  # lines with too short a history, as clauses
    synthetic_renewals: int = Field(default=0, ge=0, description="Synthetic renewals among those compared")
    sentence: str


class NewStandingOrder(Contract):
    """Body of POST /v1/standing-orders."""

    name: StandingOrderName
    request: PurchaseRequest
    cadence_days: int = Field(default=DEFAULT_CADENCE_DAYS, ge=1, le=MAX_CADENCE_DAYS)


class RenewStandingOrder(Contract):
    """Body of POST /v1/standing-orders/{id}/renew. No quantities: the stored ones."""

    quantities: tuple[ThisWeek, ...] | None = Field(
        default=None, max_length=MAX_REQUEST_LINES,
        description="This week's quantity of each request line, in the line's unit and order",
    )
