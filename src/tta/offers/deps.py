"""What the offer package depends on: ports only, and one look at price and availability.

T09 wires the real implementations; a test passes fakes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from tta.contracts.availability import AvailabilityLine, AvailabilityResponse, PriceLine, PriceResponse
from tta.contracts.common import ClockBasis, DataSource
from tta.contracts.errors import InvalidRequest, SupplierUnavailable
from tta.contracts.ports import Catalog, Clock, PairedLookup, PolicyEngine, ValioGateway
from tta.contracts.standing import StandingHistory

NO_STANDING_ORDERS = (
    "This gateway keeps no standing orders, so a request cannot renew one. Send it without standing_order_id."
)
TWO_SOURCES = (
    "Price came from the {price} source and availability from the {availability} source. An offer is never "
    "built on two sources, so nothing was looked up. The same request can be sent again."
)


class SpendParts(Protocol):
    """The day's spend in its parts, as `tta.orders.spend.DaySpend` gives it."""

    @property
    def committed(self) -> Decimal: ...  # ORDERED and PENDING_APPROVAL together: what rule P-02 adds the order to

    @property
    def waiting(self) -> Decimal: ...  # the PENDING_APPROVAL part


def spend_parts(spend: Decimal | SpendParts) -> tuple[Decimal, Decimal | None]:
    """(committed, waiting) of what `OfferDeps.day_spend` answered; waiting is None for a single figure."""
    if isinstance(spend, Decimal):
        return spend, None
    return spend.committed, spend.waiting


@dataclass(frozen=True)
class OfferDeps:
    """`day_spend` answers the net EUR a buyer profile has committed today (ORDERED and PENDING_APPROVAL): one
    figure, or the figure in its parts (`SpendParts`), and then rule P-02's sentence says what is ordered and
    what is waiting for a person.

    `standing_history` answers the history of a standing order by (profile id, standing order id) and raises
    `InvalidRequest` for one the profile does not have (`tta.standing.history_lookup`). None: no standing orders
    are wired, and a request that names one is refused, never judged without its history (rule P-08).
    """

    catalog: Catalog
    gateway: ValioGateway
    policy: PolicyEngine
    clock: Clock
    day_spend: Callable[[str], Decimal | SpendParts]
    standing_history: Callable[[str, str], StandingHistory] | None = None


def standing_history_of(deps: OfferDeps, profile_id: str, standing_order_id: str | None) -> StandingHistory | None:
    """What `PolicyContext.standing_history` gets: None for a request that renews nothing (task STAND-1)."""
    if standing_order_id is None:
        return None
    if deps.standing_history is None:
        raise InvalidRequest(NO_STANDING_ORDERS)
    return deps.standing_history(profile_id, standing_order_id)


@dataclass(frozen=True)
class Lookup:
    """One answer of the price endpoint and one of the availability endpoint, by product id."""

    prices: Mapping[str, PriceLine]
    availability: Mapping[str, AvailabilityLine]
    now: datetime  # `timeNow` of the availability answer: the clock every cut-off is compared with
    source: DataSource
    basis: ClockBasis | None = None  # what `now` rests on; None reads as `ClockBasis.of(source)`

    @property
    def time_basis(self) -> ClockBasis:
        return self.basis or ClockBasis.of(self.source)

    def price(self, product_id: str) -> PriceLine | None:
        return self.prices.get(product_id)

    def line(self, product_id: str) -> AvailabilityLine:
        """A product the answer leaves out reads as the API answers an unknown id: no schedule line
        (AIMO/docs/API.md section 8.5)."""
        return self.availability.get(product_id) or AvailabilityLine(product_id=product_id, sales_block=False)


def look_up(deps: OfferDeps, product_ids: Iterable[str], *, fresh: bool = False) -> Lookup:
    """One look at price and availability for the ids, both from one source (SPEC section 5, step 1). No id:
    no call.

    `fresh=True` is for the re-check before an order: it must not read a cached answer.
    Raises `SupplierUnavailable` when the two answers state different sources.
    """
    ids = tuple(dict.fromkeys(product_ids))
    if not ids:
        return Lookup(
            prices={}, availability={}, now=deps.clock.now(), source=deps.gateway.source,
            basis=getattr(deps.gateway, "time_basis", None),
        )
    prices, availability = _pair(deps.gateway, ids, fresh)
    if prices.source is not availability.source:
        raise SupplierUnavailable(
            TWO_SOURCES.format(price=prices.source.value, availability=availability.source.value)
        )
    return Lookup(
        prices=prices.by_id(), availability=availability.by_id(), now=availability.time_now,
        source=availability.source, basis=availability.basis,
    )


def _pair(gateway: ValioGateway, ids: tuple[str, ...], fresh: bool) -> tuple[PriceResponse, AvailabilityResponse]:
    """A gateway that can answer from more than one source is asked for both at once, so that it can keep
    them on one source; any other gateway gets one price call and one availability call."""
    if isinstance(gateway, PairedLookup):
        return gateway.look_up(ids, fresh=fresh)
    return gateway.price(ids, fresh=fresh), gateway.availability(ids, fresh=fresh)
