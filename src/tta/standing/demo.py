"""The demonstration's standing orders and their past renewals, built from the customer files (P1 C3).

Each of the four customers has a file in `tta.customers` with its standing orders (`customer.standing_orders`) and
its past orders (`customer.history`). A standing order is set up from them once: its request holds one line per
stored product, and every past order that holds one of those products becomes a past renewal, at the quantity
ordered then. Everything is SYNTHETIC and says so (`Renewal.synthetic`): the Valio Aimo mock has no order history.
A past order states a price only where it differs from the recording's; an empty price means the recording's.

The hotel's order keeps its id, `so_demo_hotel_milk`: "Weekly lactose-free milk, hotel kitchen", 100 L of 469363 a
week, with a median of 100 L over its last 6 renewals. Renewed at 100 L it is usual; at 290 L it is the anomaly
rule P-08 flags. The school's order stores 60 L of oat drink against a rising history: the trend's example
(`tta.suggestions.standing_order_trends`).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, time, timedelta
from decimal import Decimal

from tta.contracts.common import Identity, Unit
from tta.contracts.customer import Customer, CustomerStandingOrder
from tta.contracts.errors import InvalidRequest, SupplierUnavailable
from tta.contracts.ports import ValioGateway
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.contracts.standing import Renewal, RenewalLine, StandingOrder
from tta.customers import shipped_customer
from tta.standing.service import StandingOrders

DEMO_STANDING_ORDER_ID = "so_demo_hotel_milk"
DEMO_PROFILE_ID = "hotel-kitchen"
STANDING_ORDER_ID_PREFIX = "so_"
RENEWAL_ID_PREFIX = "ren_"
WEEKLY = 7
DELIVERED_AT = time(12, 0)  # a past order of a customer file has a date and no hour: read as noon
UNIT_WORDS = {Unit.L: "litres", Unit.KG: "kg", Unit.UNIT: "sales units"}
NO_PRICE = (
    "The recorded capture holds no price for product {product_id}, so the demonstration's history cannot be built "
    "from it. Nothing was set up."
)
NO_CUSTOMER = "No customer file holds the standing order {standing_order_id} for {profile_id}."


def _hotel_entry() -> tuple[Customer, CustomerStandingOrder]:
    customer = shipped_customer(DEMO_PROFILE_ID)
    entry = None if customer is None else _entry(customer, DEMO_STANDING_ORDER_ID)
    if customer is None or entry is None:
        raise InvalidRequest(NO_CUSTOMER.format(standing_order_id=DEMO_STANDING_ORDER_ID, profile_id=DEMO_PROFILE_ID))
    return customer, entry


def _entry(customer: Customer, standing_order_id: str) -> CustomerStandingOrder | None:
    return next((each for each in customer.standing_orders if each.standing_order_id == standing_order_id), None)


def _unit(customer: Customer, product_id: str) -> Unit:
    usual = customer.usual_product(product_id)
    if usual is None:  # the customer contract refuses such a file; kept so a wrong object fails loudly
        raise InvalidRequest(f"Product {product_id} of a standing order is not a usual product of the customer.")
    return usual.unit


def _amount(quantity: Decimal, unit: Unit) -> str:
    return f"{quantity.normalize():f} {UNIT_WORDS[unit]}"


def _every(cadence_days: int) -> str:
    return "every week" if cadence_days == WEEKLY else f"every {cadence_days} days"


def standing_request(customer: Customer, entry: CustomerStandingOrder) -> PurchaseRequest:
    """The request a standing order of a customer file renews: one line per stored product, in its usual unit."""
    lines = tuple(
        RequestLine(
            text=f"{_amount(line.quantity, _unit(customer, line.product_id))} of product {line.product_id}, "
                 f"{_every(entry.cadence_days)}",
            product_ids=(line.product_id,), quantity=line.quantity, unit=_unit(customer, line.product_id),
        )
        for line in entry.lines
    )
    return PurchaseRequest(lines=lines)


def past_renewals(customer: Customer, entry: CustomerStandingOrder, prices: Mapping[str, Decimal],
                  now: datetime) -> tuple[Renewal, ...]:
    """The customer's past orders as the standing order's renewals, oldest first: each order delivered before `now`
    that holds a stored product, with that product's quantity. `prices`: the recording's net price per sales
    unit, used wherever the past order states none."""
    index_of = {line.product_id: index for index, line in enumerate(entry.lines)}
    stem = entry.standing_order_id.removeprefix(STANDING_ORDER_ID_PREFIX)
    renewals: list[Renewal] = []
    for order in customer.history:
        renewed_at = datetime.combine(order.delivered_on, DELIVERED_AT, tzinfo=now.tzinfo)
        lines = tuple(
            RenewalLine(request_line_index=index_of[product_id], product_id=product_id, quantity=quantity,
                        unit=_unit(customer, product_id),
                        unit_net_price_eur=order.prices.get(product_id, prices[product_id]))
            for product_id, quantity in order.quantities.items() if product_id in index_of
        )
        if not lines or renewed_at >= now:
            continue
        renewals.append(Renewal(
            renewal_id=f"{RENEWAL_ID_PREFIX}{stem}_{len(renewals) + 1}",
            standing_order_id=entry.standing_order_id, renewed_at=renewed_at,
            lines=tuple(sorted(lines, key=lambda line: line.request_line_index)), synthetic=True,
        ))
    return tuple(renewals)


def standing_order_of(customer: Customer, entry: CustomerStandingOrder, agent_id: str,
                      renewals: tuple[Renewal, ...], now: datetime) -> StandingOrder:
    """The standing order as the store keeps it, created one cadence before its first renewal."""
    first = renewals[0].renewed_at if renewals else now
    return StandingOrder(
        standing_order_id=entry.standing_order_id, profile_id=customer.customer_id, agent_id=agent_id,
        name=entry.name, request=standing_request(customer, entry), cadence_days=entry.cadence_days,
        created_at=first - timedelta(days=entry.cadence_days),
    )


def _capture_prices(customer: Customer, entry: CustomerStandingOrder, prices: ValioGateway) -> dict[str, Decimal]:
    ids = [line.product_id for line in entry.lines]
    found = prices.price(ids).by_id()
    by_id: dict[str, Decimal] = {}
    for product_id in ids:
        line = found.get(product_id)
        if line is None or not line.has_price or line.catalog_price is None:
            raise SupplierUnavailable(NO_PRICE.format(product_id=product_id))
        by_id[product_id] = line.catalog_price.value
    return by_id


def _set_up(standing: StandingOrders, identity: Identity, customer: Customer, entry: CustomerStandingOrder,
            prices: ValioGateway) -> StandingOrder:
    existing = standing.find(identity, entry.standing_order_id)
    if existing is not None:
        return existing
    now = standing.now()
    renewals = past_renewals(customer, entry, _capture_prices(customer, entry, prices), now)
    order = standing_order_of(customer, entry, identity.id, renewals, now)
    return standing.set_up(identity, order, renewals)


def load_customer_standing_orders(standing: StandingOrders, identity: Identity, prices: ValioGateway,
                                  customer: Customer | None = None) -> tuple[StandingOrder, ...]:
    """Set up every standing order of the customer file for its agent, once: one that is there already is
    returned as it is. `customer`: the shipped file of the agent's profile when not given; a buyer without a
    file gets none. `prices` is the recorded capture (`tta.valio.ReplayGateway`). Raises `NotAuthorised` for an
    identity that is not this customer's agent."""
    found = customer if customer is not None else shipped_customer(identity.profile_id or "")
    if found is None:
        return ()
    return tuple(_set_up(standing, identity, found, entry, prices) for entry in found.standing_orders)


def load_demo(standing: StandingOrders, identity: Identity, prices: ValioGateway) -> StandingOrder:
    """Set up the hotel kitchen's standing order `so_demo_hotel_milk` for its agent, once."""
    customer, entry = _hotel_entry()
    return _set_up(standing, identity, customer, entry, prices)


def _hotel_weeks() -> tuple[Decimal, ...]:
    customer, entry = _hotel_entry()
    product_id = entry.lines[0].product_id
    return tuple(order.quantities[product_id] for order in customer.history if product_id in order.quantities)


DEMO_NAME = _hotel_entry()[1].name
DEMO_PRODUCT_ID = _hotel_entry()[1].lines[0].product_id
DEMO_LITRES = _hotel_entry()[1].lines[0].quantity
SYNTHETIC_WEEKS = _hotel_weeks()  # the hotel's milk in its past orders, oldest first; the last 6 have a median of 100 L


def demo_request() -> PurchaseRequest:
    """The request of the hotel's standing order."""
    return standing_request(*_hotel_entry())
