"""The demonstration's standing order: "Weekly lactose-free milk, hotel kitchen", 100 L of 469363 a week, with six
past renewals that are SYNTHETIC (task STAND-1).

The Valio Aimo mock has no order history, so the six weeks are made up here and every one says so (`synthetic`).
Their price is the one the capture gives for 469363; their quantities vary around 100 L, as a kitchen's do, with a
median of exactly 100 L. Renewed at 100 L the order is usual; at 290 L it is the anomaly rule P-08 flags.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from tta.contracts.common import Identity, Unit
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import ValioGateway
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.contracts.standing import Renewal, RenewalLine, StandingOrder
from tta.standing.service import StandingOrders

DEMO_STANDING_ORDER_ID = "so_demo_hotel_milk"
DEMO_NAME = "Weekly lactose-free milk, hotel kitchen"
DEMO_PROFILE_ID = "hotel-kitchen"
DEMO_PRODUCT_ID = "469363"  # lactose-free milk 1 l, confirmed in tonight's capture (AIMO/build/AGENT-RULES.md)
DEMO_LITRES = Decimal(100)
DEMO_TEXT = "100 litres of lactose-free milk, product 469363, every week"
WEEKLY = 7
SYNTHETIC_WEEKS = tuple(Decimal(litres) for litres in (100, 96, 104, 100, 98, 102))  # oldest first; median 100 L
NO_PRICE = (
    "The recorded capture holds no price for product {product_id}, so the demonstration's history cannot be built "
    "from it. Nothing was set up."
)


def demo_request() -> PurchaseRequest:
    line = RequestLine(text=DEMO_TEXT, product_ids=(DEMO_PRODUCT_ID,), quantity=DEMO_LITRES, unit=Unit.L)
    return PurchaseRequest(lines=(line,))


def _capture_price(prices: ValioGateway) -> Decimal:
    found = prices.price([DEMO_PRODUCT_ID]).by_id().get(DEMO_PRODUCT_ID)
    if found is None or not found.has_price or found.catalog_price is None:
        raise SupplierUnavailable(NO_PRICE.format(product_id=DEMO_PRODUCT_ID))
    return found.catalog_price.value


def load_demo(standing: StandingOrders, identity: Identity, prices: ValioGateway) -> StandingOrder:
    """Set up the demonstration's standing order for the hotel kitchen's agent, once: when it is there already, it
    is returned as it is. `prices` is the recorded capture (`tta.valio.ReplayGateway`)."""
    existing = standing.find(identity, DEMO_STANDING_ORDER_ID)
    if existing is not None:
        return existing
    price, now = _capture_price(prices), standing.now()
    weeks = len(SYNTHETIC_WEEKS)
    history = tuple(
        Renewal(
            renewal_id=f"ren_demo_{week + 1}", standing_order_id=DEMO_STANDING_ORDER_ID,
            renewed_at=now - timedelta(days=WEEKLY * (weeks - week)),
            lines=(RenewalLine(request_line_index=0, product_id=DEMO_PRODUCT_ID, quantity=litres, unit=Unit.L,
                               unit_net_price_eur=price),),
            synthetic=True,
        )
        for week, litres in enumerate(SYNTHETIC_WEEKS)
    )
    order = StandingOrder(
        standing_order_id=DEMO_STANDING_ORDER_ID, profile_id=DEMO_PROFILE_ID, agent_id=identity.id, name=DEMO_NAME,
        request=demo_request(), cadence_days=WEEKLY, created_at=now - timedelta(days=WEEKLY * (weeks + 1)),
    )
    return standing.set_up(identity, order, history)
