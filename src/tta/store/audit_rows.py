"""Reading one stored audit event, whatever its row holds (check C4-F5).

A row whose body is not an audit event of this gateway (somebody inserted or rewrote it behind the gateway's back)
made every read of the trail fail: `GET /v1/audit` and `/healthz` answered 500. Such a row is now read as a
stand-in event that names the row and can never verify, so the chain breaks at it, every reader is told which
event it is, and `/healthz` reports it. Nothing the row holds is shown: it is not the gateway's.

The SQLite store names the stand-in by the row's own columns. The PostgreSQL store reads the body alone, as before
(its statements cannot be run in this build, so they were left as they are): there the stand-in takes the id its
body gives, when it gives one.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from tta.contracts.audit import EVENT_TYPE_PREFIX, SYSTEM_ACTOR, AuditData, AuditEvent

logger = logging.getLogger(__name__)

UNREADABLE_ID = "unreadable"
UNREADABLE_TYPE = f"{EVENT_TYPE_PREFIX}unreadable"
# Never the hash of an event (those are 64 hexadecimal digits), so the stand-in follows nothing: the chain breaks
# at it, whatever the row's own columns claim.
UNREADABLE_PREVIOUS_HASH = "unreadable"
UNREADABLE_SENTENCE = (
    "This stored audit event cannot be read: its record is not an audit event of this gateway, so it was inserted "
    "or changed outside the gateway. Nothing it holds is shown."
)
MAX_ID_CHARACTERS = 100
EPOCH = datetime.fromtimestamp(0, UTC)  # the time of a stand-in whose row states none that can be read


def read_event(
    body: str, *, event_id: str | None = None, event_type: str | None = None, time: str | None = None,
    stored_hash: str | None = None,
) -> AuditEvent:
    """The event of one stored row. A body that is not an audit event becomes the stand-in; the keyword arguments
    are the row's own columns, where the caller read them."""
    try:
        return AuditEvent.model_validate_json(body)
    except ValidationError as error:
        # Logged by the row's id and the number of problems only: the body is not ours and may hold anything.
        logger.error(
            "A stored audit event cannot be read as one (row id %r, %d problems): the chain is reported broken at it.",
            event_id, error.error_count(),
        )
        return _stand_in(_parsed(body), event_id, event_type, time, stored_hash)


def _parsed(body: str) -> dict[str, Any]:
    try:
        found = json.loads(body)
    except ValueError:
        return {}
    return found if isinstance(found, dict) else {}


def _text(*candidates: Any) -> str | None:
    """The first candidate that is a short text; a stand-in never carries more of a row than that."""
    return next(
        (value for value in candidates if isinstance(value, str) and 0 < len(value) <= MAX_ID_CHARACTERS), None
    )


def _moment(*candidates: Any) -> datetime:
    for value in candidates:
        if not isinstance(value, str):
            continue
        try:
            read = datetime.fromisoformat(value)
        except ValueError:
            continue
        return read if read.utcoffset() is not None else read.replace(tzinfo=UTC)
    return EPOCH


def _stand_in(
    found: dict[str, Any], event_id: str | None, event_type: str | None, time: str | None, stored_hash: str | None
) -> AuditEvent:
    data = found.get("data") if isinstance(found.get("data"), dict) else {}
    return AuditEvent(
        id=_text(event_id, found.get("id")) or UNREADABLE_ID,
        type=_text(event_type, found.get("type")) or UNREADABLE_TYPE,
        time=_moment(time, found.get("time")),
        data=AuditData(
            actor=SYSTEM_ACTOR, sentence=UNREADABLE_SENTENCE, supplier_sentence=UNREADABLE_SENTENCE,
            previous_hash=UNREADABLE_PREVIOUS_HASH, hash=_text(stored_hash, data.get("hash")) or "",
        ),
    )
