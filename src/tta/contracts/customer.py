"""A customer of the demonstration: who orders, its usual products and its past orders (P1 C2).

Everything in a customer file is SYNTHETIC. The Valio Aimo mock has no customer model, and Valio's mentors told us
to generate the customer data (AIMO/build/replan/BRIEF.md section 2, V1). `synthetic` is therefore required and
must be true: a file without it does not load, and every screen that shows the data says so.

What a customer file never holds: limits, the allergen rule, the substitution scope or who may approve. Those are
the buyer profile's, in `src/tta/policy/profiles/<customer_id>.yaml`, hashed into the policy hash. A history changes
every week; a policy hash must not (P1 section 5.1).
"""

from __future__ import annotations

import unicodedata
from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from tta.contracts.common import ApproverRole, Contract, Preference, Quantity, Unit, UnitPrice
from tta.contracts.request import MAX_QUANTITY, MAX_QUANTITY_DECIMALS, ProductId, Term
from tta.contracts.standing import DEFAULT_CADENCE_DAYS, MAX_CADENCE_DAYS, StandingOrderId, StandingOrderName

MAX_TEXT = 120  # a name, a title, an address: one short line
MAX_USUAL_PRODUCTS = 50
MAX_PAST_ORDERS = 200  # two orders a week for almost two years: far above the 8 weeks a file holds
MAX_LINES_PER_ORDER = 100
CUSTOMER_ID_PATTERN = r"^[a-z0-9][a-z0-9-]*$"  # the profile id it equals, like "hotel-kitchen"


def _one_line(value: str) -> str:
    """A text of a customer file is one line: no control or format character."""
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ValueError("a text may not contain control or format characters")
    return value


Text = Annotated[
    str, StringConstraints(min_length=1, max_length=MAX_TEXT, strip_whitespace=True), AfterValidator(_one_line)
]
CustomerId = Annotated[str, StringConstraints(min_length=1, max_length=MAX_TEXT, pattern=CUSTOMER_ID_PATTERN)]
OrderedQuantity = Annotated[Quantity, Field(gt=0, le=MAX_QUANTITY, decimal_places=MAX_QUANTITY_DECIMALS)]


class ProductUse(StrEnum):
    """What the customer does with a usual product. It tells whether the formula matters (Valio, V10)."""

    INGREDIENT = "INGREDIENT"  # baked or cooked with: fat, protein and the fat source change the result
    SERVED = "SERVED"  # served as it is, like milk to drink


class Person(Contract):
    """One person of the customer, made up for the demonstration."""

    name: Text
    title: Text


class UsualProduct(Contract):
    """A product the customer orders again and again: the "favourites" of Valio Aimo's webshop."""

    product_id: ProductId
    product_type: Term = Field(description="A key of the product-type table")
    unit: Unit = Field(description="The unit the customer orders it in; every quantity of the file is in this unit")
    use: ProductUse


class PastOrder(Contract):
    """One past delivery: how much of each usual product, in the usual product's unit."""

    delivered_on: date
    quantities: dict[ProductId, OrderedQuantity] = Field(min_length=1, max_length=MAX_LINES_PER_ORDER)
    prices: dict[ProductId, UnitPrice] = Field(
        default_factory=dict,
        description="EUR before tax per sales unit, only where it differs from the recording's price",
    )

    @model_validator(mode="after")
    def _prices_of_ordered_products(self) -> PastOrder:
        stray = sorted(set(self.prices) - set(self.quantities))
        if stray:
            raise ValueError(
                f"the order of {self.delivered_on} gives a price for {', '.join(stray)}, which it does not hold"
            )
        return self


class StandingLine(Contract):
    """One product of a standing order and the quantity it stores, in the usual product's unit."""

    product_id: ProductId
    quantity: OrderedQuantity


class CustomerStandingOrder(Contract):
    """A standing order of the customer, as the gateway sets it up at start-up (P1 C3)."""

    standing_order_id: StandingOrderId
    name: StandingOrderName
    cadence_days: int = Field(default=DEFAULT_CADENCE_DAYS, ge=1, le=MAX_CADENCE_DAYS)
    lines: tuple[StandingLine, ...] = Field(min_length=1, max_length=MAX_LINES_PER_ORDER)


class StockLine(Contract):
    """What the kitchen holds of one product type, for a type that cooks (P1 section 5.1)."""

    product_type: Term
    quantity: Quantity = Field(ge=0, le=MAX_QUANTITY, decimal_places=MAX_QUANTITY_DECIMALS)
    unit: Unit


class Customer(Contract):
    """One customer: who it is, who orders and holds each role, its usual products and its past orders."""

    customer_id: CustomerId = Field(description="Equals the id of its buyer profile")
    synthetic: Literal[True] = Field(description="Made up for the demonstration; a file without it does not load")
    name: Text
    kind: Text = Field(description="The type of customer, like Hotel kitchen")
    detail: Text | None = None
    customer_number: Text | None = None
    address: Text | None = None
    delivery_days: Text | None = None
    contact: Person = Field(description="Who orders: the person the agent prepares orders for")
    people: dict[ApproverRole, Text] = Field(
        min_length=1,
        description="Who holds each role at this customer, by name. Who may approve is the profile's approver_roles",
    )
    prefer: Preference = Field(default=Preference.PRICE, description="Used when a request states no preference")
    usual: tuple[UsualProduct, ...] = Field(min_length=1, max_length=MAX_USUAL_PRODUCTS)
    history: tuple[PastOrder, ...] = Field(default=(), max_length=MAX_PAST_ORDERS, description="Oldest first")
    standing_orders: tuple[CustomerStandingOrder, ...] = ()
    stock_on_hand: tuple[StockLine, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> Customer:
        ids = [usual.product_id for usual in self.usual]
        twice = sorted({product_id for product_id in ids if ids.count(product_id) > 1})
        if twice:
            raise ValueError(f"a usual product is listed twice: {', '.join(twice)}")
        days = [order.delivered_on for order in self.history]
        if any(later <= earlier for earlier, later in zip(days, days[1:], strict=False)):
            raise ValueError("past orders must be oldest first, one per delivery date")
        named = {product_id for order in self.history for product_id in order.quantities}
        named |= {line.product_id for standing in self.standing_orders for line in standing.lines}
        unknown = sorted(named - set(ids))
        if unknown:
            raise ValueError(f"these products are ordered but not listed as usual: {', '.join(unknown)}")
        standing_ids = [standing.standing_order_id for standing in self.standing_orders]
        if len(set(standing_ids)) < len(standing_ids):
            raise ValueError("a standing order id is used twice")
        return self

    def usual_product(self, product_id: str) -> UsualProduct | None:
        """The usual product with this id, or None."""
        return next((usual for usual in self.usual if usual.product_id == product_id), None)
