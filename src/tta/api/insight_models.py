"""The answer of `GET /v1/insights` (lane BO): Valio Aimo's figures of one order book, typed for OpenAPI.

Every block carries one sentence in plain words and how each of its figures was counted (`counted`), so a page can
show "How is this counted?". Euros are net, before tax. How the figures are computed: `tta.api.insights`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from tta.contracts.common import Contract, Money, Quantity, Ratio


class HowCounted(Contract):
    figure: str = Field(description="The figure or group of figures, as a page would title it")
    how: str = Field(description="Which steps of the audit trail it is counted from, in plain words")


class Demand(Contract):
    """Demand through the agent channel."""

    requests: int
    offers: int
    orders_prepared: int = Field(description="Orders placed or sent to a person, whatever became of them")
    confirmed_by_person: int
    placed_by_agent: int = Field(description="Orders the agent placed alone, within its authority")
    waiting: int = Field(description="Orders still waiting for a person at the buyer")
    rejected: int
    expired: int
    confirmed_net_eur: Money = Field(description="Net value of the orders confirmed by a person or placed alone")
    waiting_net_eur: Money
    sentence: str
    counted: tuple[HowCounted, ...]


class KindRow(Contract):
    """One kind of suggestion."""

    kind: str = Field(description="`SuggestionKind`, for example FORGOTTEN_ITEM")
    label: str
    own: bool = Field(description="Valio Aimo's own suggestion, shown apart from those of the buyer's history")
    shown: int
    accepted: int
    ordered: int = Field(description="Accepted, and the amended offer ended in a confirmed order")
    added_net_eur: Money
    saved_net_eur: Money


class SuggestionFigures(Contract):
    shown: int
    accepted: int
    ordered: int
    acceptance_rate: Ratio | None = Field(description="Accepted over shown; null when none was shown")
    added_net_eur: Money = Field(description="Net value accepted suggestions added to baskets")
    saved_net_eur: Money = Field(description="Net value accepted suggestions took off baskets: a cheaper product "
                                             "or pack. A service to the buyer, never netted against `added`")
    not_valued: int = Field(description="Accepted suggestions whose two offers do not let the change be valued")
    by_kind: tuple[KindRow, ...]
    own_silent: str = Field(description="Why no count of Valio Aimo's own suggestion staying silent is given")
    sentence: str
    counted: tuple[HowCounted, ...]


class ReasonCount(Contract):
    reason: str = Field(description="QUANTITY_NOT_CONFIRMED, CUTOFF_PASSED, NOT_DELIVERABLE or OUT_OF_STOCK")
    label: str
    products: int = Field(description="Products that matched the request and that this reason kept out")


class Shortfall(Contract):
    """One product type, in one unit: what was asked for and what confirmed stock covered."""

    label: str = Field(description="The product type with its claims, or the product, in Valio Aimo's own terms")
    unit: str
    requests: int = Field(description="Requested lines that were not fully confirmed")
    asked: Quantity
    confirmed: Quantity
    not_confirmed: Quantity
    value_net_eur: Money | None = Field(description="The quantity not confirmed at the offered price; null when "
                                                    "there is no offered price to value it at")
    reasons: tuple[ReasonCount, ...]
    sentence: str


class UnitTotal(Contract):
    unit: str
    quantity: Quantity


class MissedProduct(Contract):
    product_id: str
    name: str | None
    times: int = Field(description="Offers in which it matched a request and could not be offered as confirmed")
    reason: str
    reason_label: str


class Substitutes(Contract):
    offered: int
    accepted: int = Field(description="Orders with a substitute line that a person confirmed")
    refused: int = Field(description="Orders with a substitute line that a person rejected")


class Missed(Contract):
    """Sales not made: the quantity asked for that confirmed stock did not cover."""

    shortfalls: tuple[Shortfall, ...]
    not_confirmed: tuple[UnitTotal, ...] = Field(description="The quantity not confirmed, per unit")
    value_net_eur: Money
    top_products: tuple[MissedProduct, ...]
    substitutes: Substitutes
    sentence: str
    counted: tuple[HowCounted, ...]


class Insights(Contract):
    """Answer of GET /v1/insights: what the agent channel brought Valio Aimo, and where it is losing sales."""

    period: str = Field(description="`today` or `all`")
    as_of: datetime = Field(description="The clock in force when the figures were counted")
    period_sentence: str
    note: str = Field(description="What the figures rest on: synthetic customers, where prices come from")
    never_here: str = Field(description="What of a buyer's own is not in any figure")
    empty: bool = Field(description="No request, offer or order in the period: show `empty_sentence`, not zeros")
    empty_sentence: str
    demand: Demand
    suggestions: SuggestionFigures
    missed: Missed
