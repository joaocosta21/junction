"""Audit events in a CloudEvents 1.0 envelope, and the two reader views (SPEC section 9)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from tta.contracts.availability import RevalidationResult
from tta.contracts.common import AuditReader, Contract, JsonDict
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.order import Approval, ApprovalDecision, Evidence, Order
from tta.contracts.policy import BuyerProfile, PolicyDecision
from tta.contracts.request import PurchaseRequest

CLOUDEVENTS_SPEC_VERSION = "1.0"
EVENT_SOURCE = "/tta/gateway"
# CloudEvents asks for a reverse-DNS prefix owned by whoever defines the event. The project owns no
# domain, so the prefix is a plain project name; a deployment replaces it with its own (docs/ASSUMPTIONS.md).
EVENT_TYPE_PREFIX = "tta.v1."
GENESIS_HASH = "0" * 64


class AuditEventType(StrEnum):
    """One event per step (SPEC section 9). The CloudEvents `type` is the prefix plus this value."""

    REQUEST_RECEIVED = "request.received"
    REQUEST_PARSED = "request.parsed"
    LOOKUP_PERFORMED = "lookup.performed"
    OFFER_CREATED = "offer.created"
    POLICY_EVALUATED = "policy.evaluated"
    ORDER_PLACED_BY_AGENT = "order.placed_by_agent"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED = "approval.decided"
    ORDER_CONFIRMED = "order.confirmed"
    ORDER_REJECTED = "order.rejected"
    ORDER_EXPIRED = "order.expired"
    ORDER_BLOCKED = "order.blocked"
    ORDER_NOT_PLACED = "order.not_placed"  # stale or expired at order time
    AUTHORISATION_REFUSED = "authorisation.refused"
    EVIDENCE_ATTACHED = "evidence.attached"
    STANDING_ORDER_CREATED = "standing_order.created"  # task STAND-1
    STANDING_ORDER_RENEWED = "standing_order.renewed"  # with the drift found
    SUGGESTIONS_SHOWN = "suggestions.shown"  # P15 R4a: shown, dropped and held back for one offer
    SUGGESTION_ACCEPTED = "suggestion.accepted"  # P15 R4b: its `accept_request` became a new offer
    SETTINGS_CHANGED = "settings.changed"  # decision B59: a person changed what the buyer's agent may decide alone


class ActorKind(StrEnum):
    AGENT = "agent"
    HUMAN = "human"
    SYSTEM = "system"


class Actor(Contract):
    kind: ActorKind
    id: str
    role: str | None = None
    display_name: str | None = None


SYSTEM_ACTOR = Actor(kind=ActorKind.SYSTEM, id="gateway", display_name="The gateway")


class AuditContext(Contract):
    """The domain objects an event is about. The audit package builds every sentence from these.

    Pass what the event type concerns; leave the rest `None`. `facts` carries small extra values
    (for example the pasted text, or how many products were looked up).
    """

    profile_id: str | None = None
    offer_id: str | None = None
    order_id: str | None = None
    approval_id: str | None = None
    request: PurchaseRequest | None = None
    offer: Offer | None = None
    option: OfferOption | None = None
    order: Order | None = None
    approval: Approval | None = None
    approval_decision: ApprovalDecision | None = None
    decision: PolicyDecision | None = None
    profile: BuyerProfile | None = None
    revalidation: RevalidationResult | None = None
    evidence: Evidence | None = None
    facts: JsonDict = Field(default_factory=dict)


class AuditData(Contract):
    """The `data` of an audit event."""

    actor: Actor
    sentence: str  # for the buyer; built from a template, never by a model
    supplier_sentence: str  # for Valio Aimo: no limit value, no allergen exclusion, no approver name or note
    profile_id: str | None = None
    offer_id: str | None = None
    order_id: str | None = None
    approval_id: str | None = None
    rule_ids: tuple[str, ...] = ()
    facts: JsonDict = Field(default_factory=dict)  # everything the buyer may see
    supplier_facts: JsonDict = Field(default_factory=dict)  # the subset the supplier may see
    policy_hash: str | None = None
    previous_hash: str
    hash: str  # SHA-256 over the canonical JSON of the event without this field


class AuditEvent(Contract):
    """CloudEvents 1.0 envelope. Stored append-only."""

    specversion: str = CLOUDEVENTS_SPEC_VERSION
    id: str
    source: str = EVENT_SOURCE
    type: str
    time: datetime
    subject: str | None = None  # "order/<id>", "offer/<id>" or "approval/<id>"
    datacontenttype: str = "application/json"
    data: AuditData


class AuditViewEvent(Contract):
    """One event as one reader sees it."""

    id: str
    type: str
    time: datetime
    actor: Actor
    sentence: str
    rule_ids: tuple[str, ...] = ()
    facts: JsonDict = Field(default_factory=dict)
    hash: str


class ChainVerification(Contract):
    ok: bool
    checked: int
    first_bad_event_id: str | None = None
    sentence: str


class AuditView(Contract):
    reader: AuditReader
    order_id: str | None = None
    offer_id: str | None = None
    events: tuple[AuditViewEvent, ...] = ()
    chain: ChainVerification
