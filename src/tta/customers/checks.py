"""The customer files against the product file and a recording (P1 section 5.3).

Each check gives one sentence per problem; an empty answer means the file holds. Where each one runs (corrected
after review finding S14, which found that nothing called these at start-up although this text said so):

- `type_problems`: every load. It needs only the product-type table, so `load_customers` always runs it and
  refuses a file that names a product type the table does not have.
- `catalog_problems`: a load that is given a catalog (`load_customers(directory, catalog=...)`). It makes no
  supplier call: every product id is in the product file and is of the product type the file says. The catalog
  takes about a second and 0.6 GB, so a load without one skips it. `tests/customers` runs it over the four shipped
  files. The gateway does not pass its catalog yet: that call is in `tta.api`, which this task did not own.
- `customer_problems` and `states_at`: these need recorded prices or availability, so they run in the tests only
  (`tests/customers/test_against_catalog.py`), never at start-up.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from tta.availability.states import classify
from tta.catalog.kinds import is_product_type
from tta.contracts.availability import AvailabilityAssessment, AvailabilityResponse, PriceLine, PriceResponse
from tta.contracts.common import Unit
from tta.contracts.customer import Customer, UsualProduct
from tta.contracts.errors import InvalidRequest
from tta.contracts.ports import Catalog
from tta.contracts.product import Product
from tta.contracts.request import ProductQuery

UNIT_WORDS = {Unit.L: "L", Unit.KG: "kg", Unit.UNIT: "units"}


class PriceSource(Protocol):
    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse: ...


class AvailabilitySource(Protocol):
    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse: ...


def type_problems(customer: Customer) -> tuple[str, ...]:
    """Every usual product whose product type the product-type table does not have, in file order."""
    return tuple(
        f"{customer.customer_id}: {usual.product_type} (for {usual.product_id}) is not a product type of the catalog"
        for usual in customer.usual if not is_product_type(usual.product_type)
    )


def catalog_problems(customer: Customer, catalog: Catalog) -> tuple[str, ...]:
    """Every usual product that is not in the product file, or is not of the product type the file says, in
    file order. No supplier call. A type the table does not have is `type_problems`' to say."""
    problems: list[str] = []
    for usual in customer.usual:
        if catalog.get_product(usual.product_id) is None:
            problems.append(f"{customer.customer_id}: {usual.product_id} is not in the catalog, or is marked deleted")
        elif is_product_type(usual.product_type) and (problem := _type_problem(usual, catalog)) is not None:
            problems.append(f"{customer.customer_id}: {problem}")
    return tuple(problems)


def customer_problems(customer: Customer, catalog: Catalog, prices: PriceSource) -> tuple[str, ...]:
    """Every problem of one customer file against the catalog and the recorded prices, in file order."""
    by_id = prices.price([usual.product_id for usual in customer.usual]).by_id()
    problems: list[str] = []
    products: dict[str, Product] = {}
    for usual in customer.usual:
        product = catalog.get_product(usual.product_id)
        if product is None:
            problems.append(f"{customer.customer_id}: {usual.product_id} is not in the catalog, or is marked deleted")
            continue
        products[usual.product_id] = product
        problems.extend(f"{customer.customer_id}: {problem}"
                        for problem in _usual_problems(usual, product, catalog, by_id.get(usual.product_id)))
    problems.extend(_lot_problems(customer, products, catalog, by_id))
    return tuple(problems)


def states_at(customer: Customer, availability: AvailabilitySource, now: datetime) -> dict[str, AvailabilityAssessment]:
    """The availability state of every usual product at the clock given, by product id, in file order."""
    lines = availability.availability([usual.product_id for usual in customer.usual]).by_id()
    return {usual.product_id: classify(lines[usual.product_id], now) for usual in customer.usual}


def _usual_problems(usual: UsualProduct, product: Product, catalog: Catalog, price: PriceLine | None) -> list[str]:
    problems: list[str] = []
    type_problem = _type_problem(usual, catalog)
    if type_problem is not None:
        problems.append(type_problem)
    priced = price if price is not None and price.has_price else None
    if priced is None:
        problems.append(f"{usual.product_id} has no price in the recording")
    if usual.unit is not Unit.UNIT and not catalog.pack_size(product, priced, usual.unit).is_known:
        problems.append(f"{usual.product_id} has no known size per sales unit in {usual.unit.value}")
    return problems


def _type_problem(usual: UsualProduct, catalog: Catalog) -> str | None:
    query = ProductQuery(product_type=usual.product_type, product_ids=(usual.product_id,))
    try:
        found = catalog.search(query)
    except InvalidRequest:
        return f"{usual.product_type} is not a product type"
    if not any(product.id == usual.product_id for product in found.products):
        return f"{usual.product_id} is not of the product type {usual.product_type}"
    return None


def _lot_problems(customer: Customer, products: Mapping[str, Product], catalog: Catalog,
                  prices: Mapping[str, PriceLine]) -> list[str]:
    """Every quantity of the file must be a whole number of the product's lots, in sales units."""
    quantities = [(order.delivered_on.isoformat(), product_id, quantity)
                  for order in customer.history for product_id, quantity in order.quantities.items()]
    quantities += [(f"the standing order {standing.standing_order_id}", line.product_id, line.quantity)
                   for standing in customer.standing_orders for line in standing.lines]
    problems: list[str] = []
    for where, product_id, quantity in quantities:
        usual, product = customer.usual_product(product_id), products.get(product_id)
        if usual is None or product is None:
            continue  # a product the catalog lacks is already a problem; a non-usual one cannot load
        units = _sales_units(quantity, usual, product, catalog, prices.get(product_id))
        if units is not None and catalog.round_to_lot(product, units) != units:
            preposition = "in" if where.startswith("the standing order") else "on"
            problems.append(f"{customer.customer_id}: {quantity.normalize():f} {UNIT_WORDS[usual.unit]} of "
                            f"{product_id} {preposition} {where} is not a whole number of lots")
    return problems


def _sales_units(quantity: Decimal, usual: UsualProduct, product: Product, catalog: Catalog,
                 price: PriceLine | None) -> Decimal | None:
    """The quantity in sales units, or None when the pack size is not known (already a problem)."""
    if usual.unit is Unit.UNIT:
        return quantity
    priced = price if price is not None and price.has_price else None
    size = catalog.pack_size(product, priced, usual.unit)
    if not size.is_known or not size.value:
        return None
    return quantity / size.value
