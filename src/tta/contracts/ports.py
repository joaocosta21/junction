"""Ports: the protocols the packages implement and depend on. Everything is synchronous.

A package depends on the ports it needs, never on another package's concrete class, so every
part can be built and tested on its own with a fake of its neighbours.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractContextManager
from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from tta.contracts.agent import AgentRun, Reading
from tta.contracts.audit import (
    Actor,
    AuditContext,
    AuditEvent,
    AuditEventType,
    AuditView,
    ChainVerification,
)
from tta.contracts.availability import (
    AvailabilityResponse,
    PriceLine,
    PriceResponse,
    RevalidationResult,
)
from tta.contracts.common import ApprovalStatus, AuditReader, DataSource, Identity, OrderStatus, Unit
from tta.contracts.offer import Offer, OfferOption, SubstituteQuery, SubstituteResult
from tta.contracts.order import Approval, DecisionRequest, Order
from tta.contracts.policy import Authority, BuyerProfile, PolicyContext, PolicyDecision
from tta.contracts.product import PackSize, Product, SearchResult
from tta.contracts.request import ProductQuery, PurchaseRequest


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime:
        """Timezone-aware current time.

        Live: the later of this machine's time and the server's `timeNow` as told (a server time more than
        12 hours away is refused); it never moves backwards. Replay: pinned to the capture's `timeNow`.
        """
        ...


@runtime_checkable
class ValioGateway(Protocol):
    """Price and availability from the Valio mock API, live or replayed. Raises `SupplierUnavailable`.

    `fresh=True` asks the supplier again even when a cached answer exists. The re-check before an
    order is placed must pass it: a cached answer cannot show that a price or a stock figure changed.
    """

    @property
    def source(self) -> DataSource: ...

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse: ...

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse: ...


@runtime_checkable
class PairedLookup(Protocol):
    """A supplier gateway that can answer from more than one source (live, or a recorded capture) implements this.

    One look at price and availability must come from one source: an offer is never built on a live price and a
    replayed stock figure. The offer package calls `look_up` when the gateway has it, and two calls otherwise.
    """

    def look_up(
        self, product_ids: Sequence[str], *, fresh: bool = False
    ) -> tuple[PriceResponse, AvailabilityResponse]:
        """Price and availability for the same ids, both from the same source."""
        ...


@runtime_checkable
class Catalog(Protocol):
    """The local product file. Returns candidates; others judge them."""

    def get_product(self, product_id: str) -> Product | None: ...

    def search(self, query: ProductQuery) -> SearchResult: ...

    def product_type_keys(self) -> tuple[str, ...]: ...

    def listed_substitutes(self, product_id: str) -> tuple[str, ...]: ...

    def same_category(self, product_id: str, digits: int) -> tuple[Product, ...]:
        """Other products sharing the first `digits` digits of the category, in a stable order."""
        ...

    def pack_size(self, product: Product, price: PriceLine | None, unit: Unit) -> PackSize:
        """Litres or kg per sales unit: live price ratio, then unit conversions, then the name."""
        ...

    def is_portion_pack(self, product: Product) -> bool: ...

    def round_to_lot(self, product: Product, quantity: Decimal) -> Decimal:
        """Round a quantity in sales units up to the product's allowed lot step."""
        ...


@runtime_checkable
class PolicyEngine(Protocol):
    """Deterministic: no model takes part in a verdict."""

    def get_profile(self, profile_id: str) -> BuyerProfile:
        """Raises `NotAuthorised` for a profile that does not exist."""
        ...

    def profile_ids(self) -> tuple[str, ...]: ...

    def evaluate(self, option: OfferOption, profile: BuyerProfile, context: PolicyContext) -> PolicyDecision: ...

    def describe_authority(self, profile: BuyerProfile) -> Authority: ...

    def policy_hash(self, profile: BuyerProfile) -> str: ...


@runtime_checkable
class OfferBuilder(Protocol):
    def build_offer(self, request: PurchaseRequest, identity: Identity) -> Offer:
        """Never raises for "nothing fits": returns an offer with no options and the reasons."""
        ...

    def find_substitutes(self, product_id: str, identity: Identity, query: SubstituteQuery) -> SubstituteResult: ...


@runtime_checkable
class OfferRevalidator(Protocol):
    def revalidate(self, option: OfferOption) -> RevalidationResult:
        """Fresh price and availability for the option's lines; reports what changed."""
        ...


@runtime_checkable
class Store(Protocol):
    """Repository. `save_*` inserts or replaces by id. Audit events can only be appended."""

    def atomic(self) -> AbstractContextManager[None]:
        """Everything saved or appended inside the `with` block is committed together, or not at all.

        An order's state, its approval, its idempotency key and its audit event are written in one block,
        so a failure between them leaves nothing half-written.
        """
        ...

    def save_offer(self, offer: Offer) -> None: ...

    def get_offer(self, offer_id: str) -> Offer | None: ...

    def save_order(self, order: Order) -> None: ...

    def get_order(self, order_id: str) -> Order | None: ...

    def list_orders(
        self, profile_id: str | None = None, statuses: Sequence[OrderStatus] | None = None
    ) -> tuple[Order, ...]: ...

    def save_approval(self, approval: Approval) -> None: ...

    def get_approval(self, approval_id: str) -> Approval | None: ...

    def list_approvals(
        self, profile_id: str | None = None, status: ApprovalStatus | None = None
    ) -> tuple[Approval, ...]: ...

    def remember_idempotency_key(self, key: str, scope: str, order_id: str) -> str:
        """Bind a key to an order id. Returns the id first bound to this key and scope."""
        ...

    def order_id_for_key(self, key: str, scope: str) -> str | None: ...

    def append_audit_event(self, event: AuditEvent) -> None: ...

    def list_audit_events(
        self, order_id: str | None = None, offer_id: str | None = None, profile_id: str | None = None
    ) -> tuple[AuditEvent, ...]:
        """In the order they were appended. With no filter: every event."""
        ...

    def last_audit_hash(self) -> str | None: ...


@runtime_checkable
class AuditSink(Protocol):
    """Writes one event per step. Sentences come from templates in the audit package."""

    def record(self, event_type: AuditEventType, actor: Actor, context: AuditContext) -> AuditEvent: ...

    def view(
        self, reader: AuditReader, order_id: str | None = None, offer_id: str | None = None,
        profile_id: str | None = None,
    ) -> AuditView: ...

    def verify_chain(self) -> ChainVerification: ...

    def head(self) -> tuple[int, str]:
        """The number of events and the hash of the last one: held by another party, it shows a trail cut short."""
        ...


@runtime_checkable
class OrderService(Protocol):
    def place_order(self, offer_id: str, option_id: str, identity: Identity, idempotency_key: str) -> Order:
        """Raises OfferStale, OfferExpired, PolicyBlocked, NotAuthorised, NotFound."""
        ...

    def decide(self, approval_id: str, identity: Identity, decision: DecisionRequest) -> Order: ...

    def get_order(self, order_id: str, identity: Identity) -> Order: ...

    def get_approval(self, approval_id: str, identity: Identity) -> Approval: ...

    def list_approvals(self, identity: Identity, status: ApprovalStatus | None = None) -> tuple[Approval, ...]: ...

    def day_committed_net_eur(self, profile_id: str) -> Decimal:
        """Net total of the profile's ORDERED and PENDING_APPROVAL orders on the clock's current date."""
        ...


@runtime_checkable
class RequestParser(Protocol):
    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        """Raises `InvalidRequest` naming what is missing; never guesses a quantity or a strictness."""
        ...

    def read(self, text: str, identity: Identity) -> Reading:
        """The same reading as `parse_request`, with who made it (the model now, a recording, a person)."""
        ...


@runtime_checkable
class GatewayService(Protocol):
    """The service functions behind every transport: REST routes, MCP tools, pages and the buyer agent.

    Each takes the caller's identity first and enforces what that identity may do.
    """

    def get_authority(self, identity: Identity) -> Authority: ...

    def search_products(self, identity: Identity, query: ProductQuery) -> SearchResult: ...

    def get_product(self, identity: Identity, product_id: str) -> Product: ...

    def find_substitutes(self, identity: Identity, product_id: str, query: SubstituteQuery) -> SubstituteResult: ...

    def create_offer(self, identity: Identity, request: PurchaseRequest) -> Offer: ...

    def get_offer(self, identity: Identity, offer_id: str) -> Offer: ...

    def place_order(self, identity: Identity, offer_id: str, option_id: str, idempotency_key: str) -> Order: ...

    def get_order(self, identity: Identity, order_id: str) -> Order: ...

    def list_orders(self, identity: Identity) -> tuple[Order, ...]:
        """The orders of the caller's own buyer, newest first."""
        ...

    def list_approvals(self, identity: Identity, status: ApprovalStatus | None = None) -> tuple[Approval, ...]: ...

    def decide_approval(self, identity: Identity, approval_id: str, decision: DecisionRequest) -> Order: ...

    def get_audit(
        self, identity: Identity, reader: AuditReader | None = None, order_id: str | None = None,
        offer_id: str | None = None,
    ) -> AuditView: ...

    def parse_request(self, identity: Identity, text: str) -> PurchaseRequest: ...

    def read_request(self, identity: Identity, text: str) -> Reading:
        """`parse_request` with who read the text; the pages and the parse route show it."""
        ...

    def order_for_offer(self, identity: Identity, offer_id: str) -> Order | None:
        """The live or last order of the caller's own offer, read through the store."""
        ...

    def run_agent(self, identity: Identity, text: str) -> AgentRun: ...


@runtime_checkable
class AgentRunner(Protocol):
    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        """A function-calling loop over the gateway's own functions, capped at MAX_AGENT_STEPS."""
        ...
