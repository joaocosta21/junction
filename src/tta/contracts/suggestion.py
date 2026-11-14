"""A suggestion computed from a customer's past orders or from the catalog (P15 section 4.5).

A suggestion never changes an order. It is not a line of any option and is in no total. Accepting it means posting
its `accept_request` to `POST /v1/offers`: a new offer, which meets every rule again and waits for a person's
confirmation like any other (PLAN section 2, rule 9). No model picks, ranks or words a suggestion: counts and
medians in the gateway, thresholds by name (`tta.suggestions.thresholds`), the evidence in the answer so an outside
agent can recompute it.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from tta.contracts.availability import AvailabilityAssessment
from tta.contracts.common import Contract, Money, Number, Quantity, Ratio, Unit, UnitPrice
from tta.contracts.request import MAX_QUANTITY, MAX_REQUEST_LINES, ProductId, PurchaseRequest
from tta.contracts.standing import StandingOrderId

MAX_ID_LENGTH = 120
MAX_SENTENCE_LENGTH = 1000
MAX_EVIDENCE_VALUES = 200
SuggestionId = Annotated[str, StringConstraints(min_length=1, max_length=MAX_ID_LENGTH, pattern=r"^[A-Za-z0-9_-]+$")]


class SuggestionKind(StrEnum):
    """What a suggestion says, in the order a list shows them (runbook, "Suggestions": the forgotten item, the usual
    product and quantity, a cheaper product with the same formula, a larger pack, a trend)."""

    FORGOTTEN_ITEM = "FORGOTTEN_ITEM"  # usually ordered with a product of the request, and not in it
    USUAL_PRODUCT = "USUAL_PRODUCT"  # the product the customer orders for a product type
    USUAL_QUANTITY = "USUAL_QUANTITY"  # the median quantity of the customer's last orders of a product
    CHEAPER_SAME_FORMULA = "CHEAPER_SAME_FORMULA"  # P10 F6, built with the formula measure
    LARGER_PACK = "LARGER_PACK"  # the same product in a larger pack, cheaper per litre or kilogram
    QUANTITY_TREND = "QUANTITY_TREND"  # a standing order's product ordered more, or less, week after week
    REORDER_DUE = "REORDER_DUE"  # P15 R8; not in the runbook's order, so placed last


KIND_ORDER: tuple[SuggestionKind, ...] = tuple(SuggestionKind)


class Serves(StrEnum):
    """Whose interest a suggestion serves. A supplier's suggestion is shown last and apart (P15 section 4.2)."""

    BUYER = "BUYER"
    SUPPLIER = "SUPPLIER"


class EvidenceSource(StrEnum):
    SYNTHETIC_HISTORY = "SYNTHETIC_HISTORY"  # a customer file written for the demonstration
    ORDER_BOOK = "ORDER_BOOK"  # orders placed through this gateway
    CATALOG = "CATALOG"  # facts of the product file and the supplier's prices, no history
    SUPPLIER = "SUPPLIER"


class SuggestionEvidence(Contract):
    """What a suggestion was computed from, so that anyone can compute it again."""

    source: EvidenceSource
    synthetic: bool = Field(description="True when the orders counted were made up for the demonstration")
    orders_considered: int = Field(ge=0, description="The past orders the count or the median was taken over")
    orders_matching: int = Field(ge=0, description="Of those, the orders that hold what the suggestion is about")
    first_order: date | None = None
    last_order: date | None = None
    values: tuple[Number, ...] = Field(
        default=(), max_length=MAX_EVIDENCE_VALUES, description="The figures a median or a price was taken from"
    )
    thresholds: dict[str, Number] = Field(default_factory=dict, description="Each named threshold passed, by name")

    @model_validator(mode="after")
    def _matching_within_considered(self) -> SuggestionEvidence:
        if self.orders_matching > self.orders_considered:
            raise ValueError("orders_matching cannot exceed orders_considered")
        return self


class SuggestionEffect(Contract):
    """What accepting would change in money. Before tax, in EUR."""

    net_change_eur: Money | None = Field(default=None, description="Negative: the order costs less")
    measure: Unit | None = Field(default=None, description="L or KG: the measure of the two unit prices")
    unit_price_before_eur: UnitPrice | None = Field(default=None, description="EUR per litre or kilogram")
    unit_price_after_eur: UnitPrice | None = None
    saving_ratio: Ratio | None = Field(default=None, ge=-1, le=1, description="1 - after / before, per measure")


class Suggestion(Contract):
    """One suggestion: a product and a quantity, one sentence with its numbers, and what it rests on."""

    suggestion_id: SuggestionId = Field(description="Stable for one buyer, kind and product (suggestion_id_for)")
    kind: SuggestionKind
    serves: Serves = Serves.BUYER
    customer_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    request_line_index: int | None = Field(
        default=None, ge=0, lt=MAX_REQUEST_LINES, description="The request line it is about; None: a new line"
    )
    standing_order_id: StandingOrderId | None = Field(default=None, description="Set for a standing order's trend")
    product_id: ProductId
    name: str = Field(min_length=1, max_length=MAX_SENTENCE_LENGTH)
    quantity: Quantity = Field(gt=0, le=MAX_QUANTITY)
    unit: Unit
    replaces_product_id: ProductId | None = None
    sentence: str = Field(min_length=1, max_length=MAX_SENTENCE_LENGTH)
    evidence: SuggestionEvidence
    effect: SuggestionEffect | None = None
    availability: AvailabilityAssessment | None = None
    stock_confirmed: bool | None = Field(default=None, description="None: not looked up yet")
    checks: tuple[str, ...] = Field(default=(), description="The allergen, claim and formula sentences of the guard")
    accept_request: PurchaseRequest | None = Field(
        default=None, description="The amended request to post to POST /v1/offers to accept; None: no request to amend"
    )


def suggestion_id_for(customer_id: str, kind: SuggestionKind, product_id: str) -> str:
    """The id of a suggestion: the same for the same buyer, kind and product, so a dismissal is found again."""
    return f"sug_{kind.value.lower()}_{product_id}_{customer_id}"
