"""The past orders one buyer's suggestions are computed from (P15 R2).

Tonight the only source is the buyer's customer file, which is synthetic (`history_of`). The same object can later
be built from the orders placed through the gateway (`EvidenceSource.ORDER_BOOK`, `synthetic=False`), so an order
placed in the demo counts in the next suggestion (P15 DECISION 6).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from tta.contracts.common import Unit
from tta.contracts.customer import Customer, PastOrder, UsualProduct
from tta.contracts.suggestion import EvidenceSource


@dataclass(frozen=True)
class OrderHistory:
    """One buyer's past orders, oldest first, and what is known of each product in them."""

    customer_id: str
    orders: tuple[PastOrder, ...]
    usual: Mapping[str, UsualProduct]
    names: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    source: EvidenceSource = EvidenceSource.SYNTHETIC_HISTORY
    synthetic: bool = True

    def last(self, count: int) -> tuple[PastOrder, ...]:
        """The newest `count` orders, oldest first."""
        return self.orders[-count:] if count > 0 else ()

    def orders_with(self, product_id: str) -> tuple[PastOrder, ...]:
        """Every order that holds the product, oldest first."""
        return tuple(order for order in self.orders if product_id in order.quantities)

    def type_of(self, product_id: str) -> str | None:
        usual = self.usual.get(product_id)
        return usual.product_type if usual is not None else None

    def unit_of(self, product_id: str) -> Unit | None:
        usual = self.usual.get(product_id)
        return usual.unit if usual is not None else None

    def name_of(self, product_id: str) -> str:
        return self.names.get(product_id) or f"product {product_id}"

    def label(self, product_id: str) -> str:
        """How a sentence names a product: "Arla milk (469363)", or "product 469363" without a name."""
        name = self.names.get(product_id)
        return f"{name} ({product_id})" if name else f"product {product_id}"


def history_of(customer: Customer, names: Mapping[str, str] | None = None) -> OrderHistory:
    """The history of a customer file. `names` are product names by id, from the catalog, for the sentences."""
    return OrderHistory(
        customer_id=customer.customer_id,
        orders=customer.history,
        usual=MappingProxyType({usual.product_id: usual for usual in customer.usual}),
        names=MappingProxyType(dict(names or {})),
        source=EvidenceSource.SYNTHETIC_HISTORY,
        synthetic=customer.synthetic,
    )
