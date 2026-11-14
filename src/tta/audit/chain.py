"""The hash chain that makes the audit trail show tampering.

Each event carries the hash of the event before it and its own hash: SHA-256 over the event's
canonical JSON without the `hash` field. Canonical JSON here means the event as its JSON model
(`model_dump(mode="json")`), keys sorted, no spaces, UTF-8, non-ASCII characters written as they are.
Anyone holding the events can recompute every hash with a JSON library and SHA-256.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from tta.contracts.audit import GENESIS_HASH, AuditEvent, ChainVerification
from tta.contracts.common import JsonDict

EMPTY_SENTENCE = "The audit trail is empty."
CHANGED = "was changed after it was written"
OUT_OF_PLACE = "does not follow the event before it; an event was changed, removed or inserted"


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


def verify_events(events: Sequence[AuditEvent]) -> ChainVerification:
    """Walk the events in the order they were appended and name the first that does not match."""
    total = len(events)
    if total == 0:
        return ChainVerification(ok=True, checked=0, sentence=EMPTY_SENTENCE)
    expected_previous = GENESIS_HASH
    for number, event in enumerate(events, start=1):
        if event.data.previous_hash != expected_previous:
            return _broken(event, number, total, OUT_OF_PLACE)
        if event_hash(event) != event.data.hash:
            return _broken(event, number, total, CHANGED)
        expected_previous = event.data.hash
    return ChainVerification(ok=True, checked=total, sentence=_intact_sentence(total))


def _intact_sentence(total: int) -> str:
    if total == 1:
        return "The audit trail is intact: its only event matches its hash."
    return f"The audit trail is intact: each of its {total} events matches its hash and follows the one before."


def _broken(event: AuditEvent, number: int, total: int, reason: str) -> ChainVerification:
    sentence = (
        f"The audit trail does not verify: event {event.id} (number {number} of {total}) {reason}. "
        "It and every later event cannot be trusted."
    )
    return ChainVerification(ok=False, checked=number, first_bad_event_id=event.id, sentence=sentence)
