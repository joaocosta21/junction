"""Every audit event is a CloudEvents 1.0 envelope whose data carries who, why and the hash chain."""

from __future__ import annotations

import re
from datetime import datetime

import pytest

from tta.audit import AuditTrail
from tta.contracts.audit import GENESIS_HASH, AuditContext, AuditEventType
from tta.contracts.common import OrderStatus, PlacedBy
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import AuditSink
from tta.store import SqliteStore

# CloudEvents 1.0.2: REQUIRED attributes, and the naming rule for every attribute (spec.md, "Context Attributes").
REQUIRED_ATTRIBUTES = ("id", "source", "specversion", "type")
ATTRIBUTE_NAME = re.compile(r"^[a-z0-9]{1,20}$")
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _context(samples, event_type: AuditEventType | None = None) -> AuditContext:
    if event_type is AuditEventType.ORDER_PLACED_BY_AGENT:
        # The agent places an order alone only under a decision that asks for nobody.
        placed = samples.order(samples.ward_option(), OrderStatus.ORDERED, placed_by=PlacedBy.AGENT, approval_id=None)
        return AuditContext(order=placed)
    option = samples.partial_option()
    return AuditContext(order=samples.order(option, OrderStatus.PENDING_APPROVAL), approval=samples.approval())


@pytest.mark.parametrize("event_type", list(AuditEventType))
def test_every_envelope_has_the_attributes_cloudevents_requires(
    trail: AuditTrail, samples, event_type: AuditEventType
) -> None:
    event = trail.record(event_type, samples.agent_hotel, _context(samples, event_type))

    envelope = event.model_dump(mode="json")

    for name in REQUIRED_ATTRIBUTES:
        assert isinstance(envelope[name], str) and envelope[name], name
    assert envelope["specversion"] == "1.0"
    assert envelope["type"] == f"tta.v1.{event_type.value}"
    assert envelope["source"] == "/tta/gateway"
    assert envelope["datacontenttype"] == "application/json"
    assert envelope["subject"]
    assert datetime.fromisoformat(envelope["time"]).utcoffset() is not None  # RFC 3339 needs an offset
    assert all(ATTRIBUTE_NAME.match(name) for name in envelope)
    assert isinstance(envelope["data"], dict)


def test_event_ids_are_unique_and_the_time_comes_from_the_clock(trail: AuditTrail, samples, demo_clock) -> None:
    events = [trail.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext()) for _ in range(5)]

    assert len({event.id for event in events}) == 5
    assert all(event.time == demo_clock.now() for event in events)


def test_the_data_holds_actor_sentence_rules_facts_policy_hash_and_both_hashes(trail: AuditTrail, samples) -> None:
    first = trail.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext())
    second = trail.record(AuditEventType.APPROVAL_REQUESTED, samples.agent_hotel, _context(samples))

    assert first.data.previous_hash == GENESIS_HASH
    assert second.data.previous_hash == first.data.hash
    assert HEX_SHA256.match(first.data.hash) and HEX_SHA256.match(second.data.hash)
    assert second.data.actor == samples.agent_hotel
    assert second.data.sentence.startswith("The agent could not place order ord_1 alone")
    assert second.data.rule_ids == ("P-01", "P-03")
    assert second.data.policy_hash == samples.policy_hash
    assert second.data.facts["decision"]["fired"][0]["facts"] == {
        "total_net_eur": "1980.77", "max_order_net_eur": "750.00",
    }
    assert (second.data.profile_id, second.data.offer_id) == ("hotel-kitchen", "off_1")
    assert (second.data.order_id, second.data.approval_id) == ("ord_1", "apr_1")


def test_an_event_is_stored_as_it_was_returned(trail: AuditTrail, store: SqliteStore, samples) -> None:
    event = trail.record(AuditEventType.APPROVAL_REQUESTED, samples.agent_hotel, _context(samples))

    assert store.list_audit_events() == (event,)
    assert store.last_audit_hash() == event.data.hash


@pytest.mark.parametrize(
    ("event_type", "subject"),
    [
        (AuditEventType.ORDER_CONFIRMED, "order/ord_1"),
        (AuditEventType.APPROVAL_DECIDED, "approval/apr_1"),
        (AuditEventType.OFFER_CREATED, "offer/off_1"),
        (AuditEventType.POLICY_EVALUATED, "offer/off_1"),
    ],
)
def test_the_subject_names_what_the_event_is_about(
    trail: AuditTrail, samples, event_type: AuditEventType, subject: str
) -> None:
    assert trail.record(event_type, samples.gateway, _context(samples)).subject == subject


def test_an_event_about_nothing_stored_has_no_subject(trail: AuditTrail, samples) -> None:
    event = trail.record(AuditEventType.REQUEST_RECEIVED, samples.agent_hotel, AuditContext(profile_id="hotel-kitchen"))

    assert event.subject is None
    assert event.data.profile_id == "hotel-kitchen"


def test_the_policy_hash_comes_from_the_engine_when_no_decision_is_known(
    store: SqliteStore, samples, demo_clock
) -> None:
    class Engine:
        def policy_hash(self, profile: BuyerProfile) -> str:
            return "d" * 64 if profile.profile_id == "hotel-kitchen" else "e" * 64

    trail = AuditTrail(store, demo_clock, policy=Engine())

    early = trail.record(AuditEventType.REQUEST_RECEIVED, samples.agent_hotel,
                         AuditContext(profile=samples.hotel_profile()))
    unknown = trail.record(AuditEventType.REQUEST_RECEIVED, samples.agent_hotel, AuditContext())

    assert early.data.policy_hash == "d" * 64
    assert unknown.data.policy_hash is None


def test_caller_facts_are_kept_as_plain_json_values_and_never_replace_a_recorded_object(
    trail: AuditTrail, samples
) -> None:
    order = samples.order(samples.partial_option(), OrderStatus.PENDING_APPROVAL)
    context = AuditContext(order=order, facts={"checked_at": samples.now, "products_looked_up": 35, "order": "x"})

    event = trail.record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, context)

    assert event.data.facts["checked_at"] == "2026-11-14T02:52:00+02:00"
    assert event.data.facts["products_looked_up"] == 35
    assert event.data.facts["order"]["order_id"] == "ord_1"
    assert event.data.supplier_facts["products_looked_up"] == 35
    assert "checked_at" not in event.data.supplier_facts


def test_a_clock_without_an_offset_is_refused(store: SqliteStore, samples) -> None:
    class NaiveClock:
        def now(self) -> datetime:
            return datetime(2026, 11, 14, 2, 52)  # no offset: the point of the test

    with pytest.raises(ValueError, match="offset"):
        AuditTrail(store, NaiveClock()).record(AuditEventType.LOOKUP_PERFORMED, samples.gateway, AuditContext())

    assert store.list_audit_events() == ()


def test_the_trail_implements_the_audit_port_and_can_only_append(trail: AuditTrail) -> None:
    public = sorted(name for name in dir(trail) if not name.startswith("_"))

    assert isinstance(trail, AuditSink)
    assert public == ["head", "record", "verify_chain", "view"]
