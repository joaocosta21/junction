"""Orders and approvals (SPEC section 8)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from tta.contracts.common import (
    ApprovalStatus,
    ApproverRole,
    AvailabilityState,
    Contract,
    DataSource,
    DecisionKind,
    JsonDict,
    Number,
    OrderStatus,
    PlacedBy,
    UnitPrice,
)
from tta.contracts.offer import OfferOption, Proof
from tta.contracts.policy import PolicyDecision

MAX_NOTE_LENGTH = 1000
MAX_RECORD_ID_LENGTH = 64

# An id the gateway issued (offer, option, order, approval), as a caller sends it back.
RecordId = Annotated[str, StringConstraints(min_length=1, max_length=MAX_RECORD_ID_LENGTH, pattern=r"^[A-Za-z0-9_-]+$")]

# The mock has no order endpoint, by design. The order record says so (SPEC section 8).
ORDER_RECORD_NOTE = (
    "Recorded in the gateway's order book. The Valio Aimo mock has no order endpoint; this record "
    "holds everything a supplier order message would need. It commits nobody."
)


class PlaceOrderRequest(Contract):
    """Body of POST /v1/orders. The buyer profile is never a field: it comes from the caller's token."""

    offer_id: RecordId
    option_id: RecordId


class DecisionRequest(Contract):
    """Body of POST /v1/approvals/{id}/decision."""

    decision: DecisionKind
    option_id: RecordId | None = Field(default=None, description="Another option of the same offer, when approving")
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)


class RelianceStatement(Contract):
    """What Valio's data said about one line when the order was checked. Kept with the order."""

    product_id: str
    unit_net_price: UnitPrice
    price_valid_to: datetime | None = None
    availability_state: AvailabilityState
    available_amount: Number | None = None  # None when the quantity is not confirmed
    available_date: date | None = None
    closing_time: datetime | None = None
    time_now: datetime  # the server time at which Valio stated these figures (the offer's data time)
    rechecked_at: datetime | None = None  # the re-check before the order found them still sufficient
    source: DataSource


class Evidence(Contract):
    """Something found outside Valio's data, shown to the approver. It never changes a status or a verdict."""

    product_id: str
    found: bool
    source_url: str | None = None
    page_title: str | None = None
    product_name_on_page: str | None = None
    contains: tuple[str, ...] = ()
    may_contain: tuple[str, ...] = ()
    free_from: tuple[str, ...] = ()
    retrieved_at: datetime | None = None
    content_hash: str | None = None
    sentence: str


class ApprovalDecision(Contract):
    """One human's decision on an approval."""

    approver_id: str
    approver_name: str
    roles: tuple[ApproverRole, ...]
    decision: DecisionKind
    option_id: str | None = None  # the option this human chose, when not the one first asked for
    note: str | None = None
    decided_at: datetime


class Approval(Contract):
    approval_id: str
    order_id: str
    offer_id: str
    option_id: str  # the option currently proposed
    profile_id: str
    status: ApprovalStatus
    required_roles: tuple[ApproverRole, ...]
    reasons: tuple[str, ...] = ()  # one sentence per rule that asks for a human
    decisions: tuple[ApprovalDecision, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    created_at: datetime
    valid_until: datetime | None = None  # "order by": after this the order expires

    @property
    def roles_obtained(self) -> tuple[ApproverRole, ...]:
        held = {
            role
            for decision in self.decisions
            if decision.decision is DecisionKind.APPROVE
            for role in decision.roles
        }
        return tuple(role for role in self.required_roles if role in held)

    @property
    def roles_missing(self) -> tuple[ApproverRole, ...]:
        obtained = set(self.roles_obtained)
        return tuple(role for role in self.required_roles if role not in obtained)


class Order(Contract):
    order_id: str
    offer_id: str
    option_id: str
    profile_id: str
    agent_id: str
    status: OrderStatus
    placed_by: PlacedBy | None = None  # set once the order is ORDERED
    option: OfferOption  # the option as ordered, kept whole
    decision: PolicyDecision  # the policy decision in force for this order
    approval_id: str | None = None
    reliance: tuple[RelianceStatement, ...] = ()
    idempotency_key: str | None = None
    created_at: datetime
    updated_at: datetime
    status_sentence: str  # one sentence: what happened to this order and why
    record_note: str = ORDER_RECORD_NOTE
    source: DataSource
    extra: JsonDict = Field(default_factory=dict)
    # Set on the copy a REST route or an MCP tool answers (`tta.api.signing`); never stored, never in the trail.
    proof: Proof | None = Field(default=None, description="The gateway's signature of this record without `proof`")
