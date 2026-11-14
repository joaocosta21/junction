"""The deployed audit trail must still verify after a redeploy (AWARDS-PLAN.md, AP-2).

`tta.audit.chain.event_hash` recomputes each hash from the event's model, so a field added to, removed from or
renamed on `AuditEvent`, `AuditData` or `Actor`, even with a default, changes the canonical JSON of every event
already stored: the whole stored trail would then read "does not verify", and the database refuses to delete it.

Each event below is one stored row, written as the JSON a database holds, one per event type. The hashes were
computed with the committed code, not with the working tree: `git archive 34ee9ea src` (HEAD on 14 Nov 2026) and
`git archive 8163d5d src` (the commit deployed on PostgreSQL) give the same 17 hashes and the same head.
A test that goes red here means stored events no longer verify: undo the change to the hashed shape, do not
update the constants.
"""

from __future__ import annotations

import pytest

from tta.audit.chain import event_hash, first_break, seal
from tta.contracts.audit import GENESIS_HASH, AuditEvent, AuditEventType

SHAPE_CHANGED = "the hashed shape of an audit event changed: events already stored would no longer verify"
PINNED_HASHES = {
    "request.received": "e79ed7c4cc2ae1f48ef6377f14117b0803e649890be7999861d8e6883e6f1169",
    "request.parsed": "4e0e9a1711b2a8eca020090c9d22beb522b9daa74e60800d25b865f638f81c58",
    "lookup.performed": "b1babfa48675081c1e592089203d082a5f7227fb8baae63cece6799216650b29",
    "offer.created": "1e9d5ee79a6c9aeafa3ab2ad5653f41ea04e75734b2d61fc6b32978a9fbb9344",
    "policy.evaluated": "79bd72cc9931b0ed0cbebdaa5ba21c07436a0487e2e8625e9a4cc47a9d8bbe3b",
    "order.placed_by_agent": "fd3e491e55e8ccd80360cecb8d9bebdc39511d94ba4f4f6951db4e496930c1ad",
    "approval.requested": "06aa421bed037b7bc2d7ab766ee024d53a7b29a32f0ad267f53b5d8fb536b779",
    "approval.decided": "7574749930ebf4b17c5772b1409730d9fa1db706d0930b7e671435694e440258",
    "order.confirmed": "d9b10d26bccf3be0ed027a59d917e4f8586a497cf728ea1120fdb537ef361662",
    "order.rejected": "2cc59e27e9c6f85d3000c1e7463ded5c6194a88349e5c156fcf093caa1d1dfd3",
    "order.expired": "5325c3c86ac97792ee78caaa6b4b993128d398066d134ed0a6c63e5392bd28e6",
    "order.blocked": "ab16fe107dc8d89b7ec354ed0ef90fa03b2b1f485278d5cf9717e0076dbb1f9a",
    "order.not_placed": "fdf9795fe52d1e40ffa2fc2d821d2958c57580a8278a31022d681cb09c752328",
    "authorisation.refused": "289951d3f0412604abffd73e689b9a0f44b31733a94b8d67eb5a0f38bed3cec8",
    "evidence.attached": "8b58aed0fe0604c9dee87c11289c6e40313f3051662165211c6f0c28307adf7b",
    "standing_order.created": "f89888ce78972889b2e0002fb49e3a70a8a4f34a061640b73777298093c636e8",
    "standing_order.renewed": "f983f422908c8cf082cbfeabee5f9a583227eaa6e55f34a9a4ac3c63975c61ff",
}
CHAIN_HEAD = "cc30f1c378310c730c423e4341e9c9617d75cb7e690c9b9643480bda48ebadb7"
ACTORS = (
    {"kind": "agent", "id": "agent:hotel-kitchen", "role": None, "display_name": "Hotel kitchen agent"},
    {"kind": "human", "id": "human:maija", "role": "purchasing_manager", "display_name": "Maija Virtanen"},
    {"kind": "system", "id": "gateway", "role": None, "display_name": "The gateway"},
)


def stored_row(number: int, event_type: str) -> dict:
    """One event as the store holds it: every field of the envelope and of `data`, with fixed values."""
    with_ids = number % 2 == 0
    return {
        "specversion": "1.0",
        "id": f"00000000-0000-4000-8000-{number:012d}",
        "source": "/tta/gateway",
        "type": f"tta.v1.{event_type}",
        "time": f"2026-11-14T11:{number:02d}:00+02:00",
        "subject": f"order/ord_{number}" if with_ids else None,
        "datacontenttype": "application/json",
        "data": {
            "actor": ACTORS[number % len(ACTORS)],
            "sentence": f"Buyer's sentence {number}: €1,980.77 net, 74.9% of “1,000 litres”.",
            "supplier_sentence": f"Supplier's sentence {number}: a human at the buyer.",
            "profile_id": "hotel-kitchen" if with_ids else None,
            "offer_id": f"off_{number}",
            "order_id": f"ord_{number}" if with_ids else None,
            "approval_id": f"apr_{number}" if number % 3 == 0 else None,
            "rule_ids": ["F-01", "P-01"] if with_ids else [],
            "facts": {"total_net_eur": 1980.77, "lines": [{"product_id": "463380", "quantity": 698.0}], "n": number},
            "supplier_facts": {"decision": {"verdict": "APPROVAL", "rule_ids": ["F-01"]}} if with_ids else {},
            "policy_hash": "c" * 64 if with_ids else None,
            "previous_hash": GENESIS_HASH,
            "hash": "",
        },
    }


def stored_events() -> list[AuditEvent]:
    return [AuditEvent.model_validate(stored_row(number, kind)) for number, kind in enumerate(PINNED_HASHES)]


def chained(events: list[AuditEvent]) -> list[AuditEvent]:
    chain: list[AuditEvent] = []
    for event in events:
        previous = chain[-1].data.hash if chain else GENESIS_HASH
        chain.append(seal(event.model_copy(update={"data": event.data.model_copy(update={"previous_hash": previous})})))
    return chain


def test_every_event_type_stored_so_far_still_exists() -> None:
    """A type added later (it has no stored event yet) needs no pin; a type renamed or removed is a stored row
    whose `type` nothing reads any more."""
    assert set(PINNED_HASHES) <= {kind.value for kind in AuditEventType}
    assert len(PINNED_HASHES) == 17


@pytest.mark.parametrize(("number", "event_type"), list(enumerate(PINNED_HASHES)), ids=lambda value: str(value))
def test_a_stored_event_still_gives_the_hash_it_was_stored_with(number: int, event_type: str) -> None:
    event = AuditEvent.model_validate(stored_row(number, event_type))

    assert event_hash(event) == PINNED_HASHES[event_type], SHAPE_CHANGED


def test_a_stored_row_is_read_back_field_for_field() -> None:
    """Nothing is dropped or added on the way in and out: the stored JSON is what is hashed."""
    for number, event_type in enumerate(PINNED_HASHES):
        row = stored_row(number, event_type)

        assert AuditEvent.model_validate(row).model_dump(mode="json") == row


def test_a_stored_chain_still_verifies_and_keeps_its_head() -> None:
    chain = chained(stored_events())

    assert first_break(chain) is None
    assert chain[-1].data.hash == CHAIN_HEAD, SHAPE_CHANGED
