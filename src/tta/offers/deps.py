"""What the offer package depends on: ports only, and one look at price and availability.

T09 wires the real implementations; a test passes fakes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from tta.contracts.availability import AvailabilityLine, PriceLine
from tta.contracts.common import DataSource
from tta.contracts.ports import Catalog, Clock, PolicyEngine, ValioGateway


@dataclass(frozen=True)
class OfferDeps:
    """`day_spend` answers the net EUR a buyer profile has committed today (ORDERED and PENDING_APPROVAL)."""

    catalog: Catalog
    gateway: ValioGateway
    policy: PolicyEngine
    clock: Clock
    day_spend: Callable[[str], Decimal]


@dataclass(frozen=True)
class Lookup:
    """One answer of the price endpoint and one of the availability endpoint, by product id."""

    prices: Mapping[str, PriceLine]
    availability: Mapping[str, AvailabilityLine]
    now: datetime  # `timeNow` of the availability answer: the clock every cut-off is compared with
    source: DataSource

    def price(self, product_id: str) -> PriceLine | None:
        return self.prices.get(product_id)

    def line(self, product_id: str) -> AvailabilityLine:
        """A product the answer leaves out reads as the API answers an unknown id: no schedule line
        (AIMO/docs/API.md section 8.5)."""
        return self.availability.get(product_id) or AvailabilityLine(product_id=product_id, sales_block=False)


def look_up(deps: OfferDeps, product_ids: Iterable[str], *, fresh: bool = False) -> Lookup:
    """One price call and one availability call for the ids (SPEC section 5, step 1). No id: no call.

    `fresh=True` is for the re-check before an order: it must not read a cached answer.
    """
    ids = tuple(dict.fromkeys(product_ids))
    if not ids:
        return Lookup(prices={}, availability={}, now=deps.clock.now(), source=deps.gateway.source)
    prices = deps.gateway.price(ids, fresh=fresh)
    availability = deps.gateway.availability(ids, fresh=fresh)
    return Lookup(
        prices=prices.by_id(), availability=availability.by_id(), now=availability.time_now, source=availability.source
    )
