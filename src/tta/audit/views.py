"""The audit trail as one reader sees it (SPEC section 9)."""

from __future__ import annotations

from collections.abc import Sequence

from tta.audit.readers import shown_facts, shown_sentence, supplier_actor, supplier_rule_ids
from tta.contracts.audit import AuditEvent, AuditViewEvent
from tta.contracts.common import AuditReader
from tta.contracts.errors import InvalidRequest

UNKNOWN_READER = "The audit trail has two readers: buyer and supplier."
BUYER_NEEDS_A_SCOPE = (
    "A buyer's view needs an order, an offer or a buyer profile: a buyer never sees another buyer's events."
)


def check_view(
    reader: AuditReader | str, order_id: str | None, offer_id: str | None, profile_id: str | None
) -> AuditReader:
    """The reader as the enum, or `InvalidRequest`. A buyer's view over every buyer is refused."""
    try:
        known = AuditReader(reader)
    except ValueError as error:
        raise InvalidRequest(UNKNOWN_READER) from error
    if known is AuditReader.BUYER and not (order_id or offer_id or profile_id):
        raise InvalidRequest(BUYER_NEEDS_A_SCOPE)
    return known


def select(
    events: Sequence[AuditEvent], order_id: str | None, offer_id: str | None, profile_id: str | None
) -> tuple[AuditEvent, ...]:
    """The events of one buyer, order or offer, in the order they were appended. Every filter given must hold.

    The trail of an order starts before the order exists: it includes the events of the order's offer
    that belong to no order (the offer, the policy check), and leaves out other orders of the same offer.
    """
    chosen = [event for event in events if profile_id is None or event.data.profile_id == profile_id]
    if order_id is not None:
        offers = {event.data.offer_id for event in chosen if event.data.order_id == order_id and event.data.offer_id}
        chosen = [
            event for event in chosen
            if event.data.order_id == order_id or (event.data.order_id is None and event.data.offer_id in offers)
        ]
    if offer_id is not None:
        chosen = [event for event in chosen if event.data.offer_id == offer_id]
    return tuple(chosen)


def project(event: AuditEvent, reader: AuditReader) -> AuditViewEvent:
    """One event for one reader. Only the buyer gets the full event; any other reader gets the supplier's
    sentence and facts and no approver's identity, with the counts an older event still holds masked
    (`tta.audit.readers.shown_facts`)."""
    data = event.data
    if reader is AuditReader.BUYER:
        return AuditViewEvent(
            id=event.id, type=event.type, time=event.time, actor=data.actor, sentence=data.sentence,
            rule_ids=data.rule_ids, facts=data.facts, hash=data.hash,
        )
    return AuditViewEvent(
        id=event.id, type=event.type, time=event.time, actor=supplier_actor(data.actor),
        sentence=shown_sentence(data.supplier_sentence), rule_ids=supplier_rule_ids(data.rule_ids),
        facts=shown_facts(data.supplier_facts), hash=data.hash,
    )
