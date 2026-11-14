"""A witness of the audit trail's head, for a scheduled function on Modal (AP-10, P13 TA-7).

Scores on the 20% "how decisions are logged and auditable". The audit chain proves that no event in the middle was
changed; a trail cut at its end, or rewritten whole, still verifies by itself unless another party holds an
earlier head (`src/tta/audit/chain.py`). This is that other party, in the supplier's seat: it reads the supplier's
view with the supplier's read-only login, notes the head, and at the next run checks that the head it noted is
still where it was.

A head that does not move is not proof of health (S9): a gateway that fell back to another store (SQLite on its
own disk) leaves this trail intact and silent. So each note also holds `moved_at`, the time the head last changed,
and a head that has stayed the same for `STALE_AFTER_HOURS` reads as a warning that says so. It is a warning and
not a failure: a quiet night moves no head either.

Nothing here runs by itself. `check` is pure. `read_head` sends three `SELECT`s over a connection it is given.
`witness_once` joins them around a note store (a `modal.Dict` on Modal, a plain dict in a test). The module
imports no Modal name and no part of the gateway, so the container needs only this file and psycopg.
"""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

SCHEMA_NAME = re.compile(r"[a-z_][a-z0-9_]{0,40}")  # the store's own pattern (src/tta/store/postgres.py)
DEFAULT_SCHEMA = "tta"
VIEW = "audit_supplier"
# Three reads of the supplier's view; `{view}` is the checked schema and the view, quoted by `qualified_view`.
COUNT_AND_LAST = "SELECT count(*), max(seq) FROM {view}"  # noqa: S105 - not a password
HASH_AT = "SELECT hash FROM {view} WHERE seq = %s"
# How long the head may stay the same before the witness says so. Ours: the demo is used through the day, so six
# hours without one audit event is worth a look; it is not a figure of Valio Aimo's.
STALE_AFTER_HOURS = 6


class Finding(StrEnum):
    FIRST = "FIRST"  # nothing was noted before: the head is noted
    SAME = "SAME"  # the head is the one noted last time
    STALE = "STALE"  # the same head for `STALE_AFTER_HOURS` or longer: intact, and nothing new was written
    GROWN = "GROWN"  # events were appended; the noted head is still at its place
    SHORTENED = "SHORTENED"  # the trail holds fewer events than were noted
    REWRITTEN = "REWRITTEN"  # the event at the noted place has another hash, or is gone


@dataclass(frozen=True)
class Head:
    """The end of the trail as the supplier's view shows it. An empty trail has `seq` and `hash` of `None`."""

    count: int
    seq: int | None
    hash: str | None


@dataclass(frozen=True)
class Verdict:
    finding: Finding
    sentence: str

    @property
    def ok(self) -> bool:
        return self.finding not in (Finding.SHORTENED, Finding.REWRITTEN)

    @property
    def warning(self) -> bool:
        """True when the trail is intact but the verdict is not "healthy": it has not moved for too long."""
        return self.finding is Finding.STALE


def check(
    noted: Head | None, head: Head, hash_at_noted_seq: str | None, unmoved_for: timedelta | None = None
) -> Verdict:
    """Compare the head noted at the last run with the trail now. `hash_at_noted_seq` is the hash the trail holds
    today at the noted head's place, or `None` when no event is there. `unmoved_for` is how long the head has been
    the noted one, when that is known."""
    if noted is None:
        return Verdict(Finding.FIRST, f"First run: the head was noted ({_described(head)}).")
    if head.count < noted.count or (noted.seq is not None and (head.seq is None or head.seq < noted.seq)):
        return Verdict(Finding.SHORTENED, (
            f"The audit trail was shortened: {noted.count} events were noted (last number {noted.seq}), and it "
            f"holds {head.count} now (last number {head.seq}). The earlier note is kept."
        ))
    if noted.seq is not None and hash_at_noted_seq != noted.hash:
        return Verdict(Finding.REWRITTEN, (
            f"The audit trail was rewritten: event number {noted.seq} was noted with hash {_short(noted.hash)}, "
            f"and that place holds {_short(hash_at_noted_seq)} now. The earlier note is kept."
        ))
    if (head.count, head.seq, head.hash) == (noted.count, noted.seq, noted.hash):
        if unmoved_for is not None and unmoved_for >= timedelta(hours=STALE_AFTER_HOURS):
            hours = int(unmoved_for.total_seconds() // 3600)
            return Verdict(Finding.STALE, (
                f"No new audit event for {hours} hours: the gateway may be writing elsewhere; check /healthz store. "
                f"The noted head is still at its place ({_described(head)})."
            ))
        return Verdict(Finding.SAME, f"The head is the one noted last time ({_described(head)}).")
    return Verdict(Finding.GROWN, (
        f"{head.count - noted.count} event(s) were appended since the last run and the noted head is still at its "
        f"place ({_described(head)})."
    ))


def _short(value: str | None) -> str:
    return f"{value[:12]}…" if value else "no event"


def _described(head: Head) -> str:
    if head.seq is None:
        return "the trail is empty"
    return f"{head.count} events, last number {head.seq}, hash {_short(head.hash)}"


# --- reading the supplier's view -----------------------------------------------------------------------------------


class Cursor(Protocol):
    def fetchone(self) -> tuple[Any, ...] | None: ...


class Connection(Protocol):
    """What `read_head` needs of a psycopg connection."""

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> Cursor: ...


def qualified_view(schema: str) -> str:
    """`"<schema>".audit_supplier`. Raises `ValueError` for a name the store's pattern refuses: the name is
    checked, so it can be written into the statement."""
    if not SCHEMA_NAME.fullmatch(schema):
        raise ValueError("The schema must be a plain lower-case identifier of at most 41 characters.")
    return f'"{schema}".{VIEW}'


def _hash_at(connection: Connection, view: str, seq: int | None) -> str | None:
    if seq is None:
        return None
    row = connection.execute(HASH_AT.format(view=view), (seq,)).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def read_head(connection: Connection, schema: str, noted_seq: int | None) -> tuple[Head, str | None]:
    """(the head now, the hash now stored at `noted_seq`), read from the supplier's view only."""
    view = qualified_view(schema)
    row = connection.execute(COUNT_AND_LAST.format(view=view)).fetchone()
    count, last = (int(row[0]), row[1]) if row else (0, None)
    seq = int(last) if last is not None else None
    return Head(count=count, seq=seq, hash=_hash_at(connection, view, seq)), _hash_at(connection, view, noted_seq)


# --- the notes -----------------------------------------------------------------------------------------------------


def _noted(value: Any) -> Head | None:
    """The head of a stored note. Raises `ValueError` for a note that cannot be read: a witness that lost its
    note says so instead of starting again as if it were its first run."""
    if value is None:
        return None
    try:
        count, seq, digest = value["count"], value["seq"], value["hash"]
    except (TypeError, KeyError) as error:
        raise ValueError("The witness's earlier note cannot be read.") from error
    if not isinstance(count, int) or not isinstance(seq, int | None) or not isinstance(digest, str | None):
        raise ValueError("The witness's earlier note cannot be read.")
    return Head(count=count, seq=seq, hash=digest)


def _moved_at(value: Any) -> datetime | None:
    """When the noted head last changed: the note's `moved_at`, or its `noted_at` for a note written before that
    field existed. `None` when neither can be read: the witness then cannot say how long, and does not guess."""
    if not isinstance(value, dict):
        return None
    for key in ("moved_at", "noted_at"):
        try:
            moment = datetime.fromisoformat(value[key])
        except (KeyError, TypeError, ValueError):
            continue
        if moment.tzinfo is not None:
            return moment
    return None


def witness_once(
    connection: Connection, notes: MutableMapping[str, Any], schema: str, now: datetime
) -> Verdict:
    """One run: read the note for this schema, read the trail, compare, and note the new head when the trail is
    intact. A shortened or rewritten trail leaves the earlier note as it is: it is the proof. `now` carries its
    offset."""
    earlier = notes.get(schema)
    noted = _noted(earlier)
    head, at_noted = read_head(connection, schema, noted.seq if noted else None)
    moved_at = _moved_at(earlier)
    verdict = check(noted, head, at_noted, now - moved_at if moved_at else None)
    if verdict.ok:
        unmoved = verdict.finding in (Finding.SAME, Finding.STALE) and moved_at is not None
        notes[schema] = {
            **asdict(head), "noted_at": now.isoformat(), "moved_at": (moved_at if unmoved else now).isoformat(),
            "finding": verdict.finding.value,
        }
    return verdict
