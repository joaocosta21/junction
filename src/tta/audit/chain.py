"""The hash chain of the audit trail: what it shows, and what it does not.

Each event carries the hash of the event before it (64 zeros for the first) and its own hash: SHA-256 over the
event's canonical JSON without the `hash` field. Canonical JSON here means the event as its JSON model
(`model_dump(mode="json")`), keys sorted, no spaces, UTF-8, non-ASCII characters written as they are.
Anyone holding the events can recompute every hash with a JSON library and SHA-256.

Verification walks the events in the order they were appended and names the first one that does not match:
its content no longer gives its hash, or it does not carry the hash of the event before it. That shows an event
that was changed, removed from anywhere but the end, inserted or moved, unless the hash of every event from
there to the end was recomputed as well.

Verification does not show:
- the newest events being cut off: a trail that lost its last events is a shorter chain that still verifies;
- a rewrite from some event to the end: the hashes use no secret key, so whoever can write the database can
  change an event and recompute its hash and the hash of every event after it;
- who wrote an event: nothing signs it, so whoever can write the database can append one that verifies.

The first two need another party to hold the head of the trail from an earlier moment (how many events, and
the hash of the last one: `AuditTrail.head()`). If the trail later holds fewer events than that, or its event
at that position has another hash, events were removed or rewritten since. This package gives the head; it
does not send it to anyone, and it does not compare a head held elsewhere.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass

from tta.contracts.audit import GENESIS_HASH, AuditEvent, ChainVerification
from tta.contracts.common import JsonDict

EMPTY_SENTENCE = "The audit trail is empty."
CHANGED = "was changed after it was written"
OUT_OF_PLACE = "does not follow the event before it; an event was changed, removed or inserted"
NOT_TRUSTED = "It and every later event cannot be trusted."
EMPTY_VIEW_SENTENCE = "No event is shown here; the chain of the audit trail verifies."
BROKEN_OUTSIDE_THE_VIEW = "The audit trail does not verify: it is broken at an event outside this view."


@dataclass(frozen=True)
class Break:
    """The first event that does not verify: its place in the whole chain (from 1) and what is wrong with it."""

    number: int
    event: AuditEvent
    reason: str


def canonical_json(value: JsonDict) -> bytes:
    """One byte sequence per value: sorted keys, no spaces, UTF-8. A NaN or an infinity is refused."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def event_hash(event: AuditEvent) -> str:
    """SHA-256, in hexadecimal, over the canonical JSON of the event without `data.hash`."""
    envelope = event.model_dump(mode="json")
    data = {name: value for name, value in envelope["data"].items() if name != "hash"}
    return hashlib.sha256(canonical_json({**envelope, "data": data})).hexdigest()


def seal(event: AuditEvent) -> AuditEvent:
    """A copy of the event with its hash filled in."""
    return event.model_copy(update={"data": event.data.model_copy(update={"hash": event_hash(event)})})


def first_break(events: Sequence[AuditEvent]) -> Break | None:
    """Walk the events in the order they were appended; the first that does not match, or none."""
    expected_previous = GENESIS_HASH
    for number, event in enumerate(events, start=1):
        if event.data.previous_hash != expected_previous:
            return Break(number, event, OUT_OF_PLACE)
        if event_hash(event) != event.data.hash:
            return Break(number, event, CHANGED)
        expected_previous = event.data.hash
    return None


def verify_events(events: Sequence[AuditEvent]) -> ChainVerification:
    """The state of the whole chain, for a reader who may see every event: counts and names any of them."""
    total = len(events)
    if total == 0:
        return ChainVerification(ok=True, checked=0, sentence=EMPTY_SENTENCE)
    broken = first_break(events)
    if broken is None:
        return ChainVerification(ok=True, checked=total, sentence=_intact_sentence(total))
    sentence = (
        f"The audit trail does not verify: event {broken.event.id} (number {broken.number} of {total}) "
        f"{broken.reason}. {NOT_TRUSTED}"
    )
    return ChainVerification(ok=False, checked=broken.number, first_bad_event_id=broken.event.id, sentence=sentence)


def verify_view(events: Sequence[AuditEvent], shown: Sequence[AuditEvent]) -> ChainVerification:
    """The state of the chain for a reader who sees only `shown`, a selection of `events`.

    The whole chain is verified, because an event is only as good as the chain before it. The answer counts
    only the events shown, and names the broken event only when it is one of them: nothing here tells one
    buyer how many events another buyer has, or their ids.
    """
    total = len(shown)
    broken = first_break(events)
    if broken is None:
        return ChainVerification(ok=True, checked=total, sentence=_intact_view_sentence(total))
    shown_ids = [event.id for event in shown]
    if broken.event.id in shown_ids:
        place = shown_ids.index(broken.event.id) + 1
        sentence = (
            f"The audit trail does not verify: event {broken.event.id} (number {place} of the {total} shown here) "
            f"{broken.reason}. {NOT_TRUSTED}"
        )
        return ChainVerification(ok=False, checked=total, first_bad_event_id=broken.event.id, sentence=sentence)
    written_after = {event.id for event in events[broken.number:]}
    after = sum(1 for event_id in shown_ids if event_id in written_after)
    sentence = (
        f"{BROKEN_OUTSIDE_THE_VIEW} Events shown here that were written after it cannot be trusted: "
        f"{after} of {total}."
    )
    return ChainVerification(ok=False, checked=total, sentence=sentence)


def _intact_sentence(total: int) -> str:
    if total == 1:
        return "The audit trail is intact: its only event matches its hash."
    return f"The audit trail is intact: each of its {total} events matches its hash and follows the one before."


def _intact_view_sentence(total: int) -> str:
    if total == 0:
        return EMPTY_VIEW_SENTENCE
    if total == 1:
        return "The audit trail is intact: the event shown here matches its hash, and the chain it belongs to verifies."
    return (
        f"The audit trail is intact: each of the {total} events shown here matches its hash, and the chain they "
        "belong to verifies."
    )
