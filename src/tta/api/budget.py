"""How much one address and one demonstration token may store in a day (review H2).

Scores on the 30% "working end-to-end demo" (the public link keeps working) and on the 15% "credible path toward
production": the audit trail is append-only, so what is written stays. The windows of one minute
(`tta.api.limits`) bound how fast one address writes; this bounds how much it has written by the end of the day.

In dev and demo only, where the tokens are public. Counted in bytes: the JSON of every audit event written and of
every offer stored while a call of that address and that token is served. Kept in memory for one process: a
restart starts the count again. A day is a UTC day. The values are ours and illustrative.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, date, datetime, timedelta

from tta.api.limits import current_client_key
from tta.audit import AuditTrail
from tta.contracts.audit import Actor, AuditContext, AuditEvent, AuditEventType
from tta.contracts.errors import RateLimited
from tta.contracts.ports import Clock, PolicyEngine, Store

BYTES_PER_MEGABYTE = 1_000_000
# One address: about 1,700 offers like scenario 1 (59 kB each, measured offline 14 Nov) or 400 of the largest a
# demonstration request can make (about 240 kB): a room on one network is served for a day, and one address at
# its cap of 60 offers a minute is stopped after about seven minutes instead of writing 0.9 GB an hour.
MAX_STORED_MEGABYTES_PER_ADDRESS_PER_DAY = 100
# One demonstration token, whoever sends it: four addresses at their budget fill it, as four addresses fill a
# ceiling of `tta.api.limits`, so one or two callers cannot stop a token for everybody.
ADDRESSES_THAT_FILL_A_TOKEN = 4
MAX_STORED_MEGABYTES_PER_TOKEN_PER_DAY = ADDRESSES_THAT_FILL_A_TOKEN * MAX_STORED_MEGABYTES_PER_ADDRESS_PER_DAY
SECONDS_PER_HOUR, SECONDS_PER_MINUTE = 3600, 60

ADDRESS_BUDGET_SPENT = (
    "This demonstration stores at most {limit} MB a day of offers and audit events for one address, and that much "
    "was stored today. Reading still works. The count starts again at 00:00 UTC, in {wait}."
)
SHARED_BUDGET_SPENT = (
    "This demonstration stores at most {limit} MB a day of offers and audit events for one demonstration token, "
    "for everybody who sends it together, and that much was stored today. Reading still works, and the other "
    "demonstration tokens are not affected. The count starts again at 00:00 UTC, in {wait}."
)

# The token whose call is being served, set when the call is checked: what is written after that is its.
_charged_token: ContextVar[str | None] = ContextVar("tta_charged_token", default=None)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _wait_words(seconds: int) -> str:
    hours, minutes = seconds // SECONDS_PER_HOUR, (seconds % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE
    if hours:
        return f"{hours} h {minutes} min"
    return f"{max(1, minutes)} min"


class StorageBudget:
    """Bytes stored per UTC day, by address and by token. `check` refuses a call that writes once a budget is
    spent; `charge` counts what a served call wrote and never refuses, so nothing is half written."""

    def __init__(
        self,
        *,
        per_address_bytes: int = MAX_STORED_MEGABYTES_PER_ADDRESS_PER_DAY * BYTES_PER_MEGABYTE,
        per_token_bytes: int = MAX_STORED_MEGABYTES_PER_TOKEN_PER_DAY * BYTES_PER_MEGABYTE,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._limits = {"address": per_address_bytes, "token": per_token_bytes}
        self._now = now
        self._lock = threading.Lock()  # routes run in a thread pool
        self._day: date | None = None
        self._stored: dict[tuple[str, str], int] = {}

    def check(self, token_id: str) -> None:
        """Raise `RateLimited`, saying when the count starts again, when this address or this token has stored
        its day's budget. Otherwise remember the token: what the call writes is charged to it and its address."""
        now = self._now()
        keys = (("address", current_client_key(), ADDRESS_BUDGET_SPENT), ("token", token_id, SHARED_BUDGET_SPENT))
        with self._lock:
            self._start_day(now.date())
            spent = next((key for key in keys if self._stored.get(key[:2], 0) >= self._limits[key[0]]), None)
        if spent is not None:
            midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
            wait = max(1, int((midnight - now).total_seconds()))
            limit = self._limits[spent[0]] / BYTES_PER_MEGABYTE
            raise RateLimited(spent[2].format(limit=f"{limit:g}", wait=_wait_words(wait)), retry_after_seconds=wait)
        _charged_token.set(token_id)

    def charge(self, size: int) -> None:
        """Count bytes just stored for the address and the token of the call being served. Outside a checked
        call (the gateway's own writes at start) nothing is counted."""
        token_id = _charged_token.get()
        if token_id is None:
            return
        with self._lock:
            self._start_day(self._now().date())
            for key in (("address", current_client_key()), ("token", token_id)):
                self._stored[key] = self._stored.get(key, 0) + size

    def stored(self, kind: str, key: str) -> int:
        """Bytes counted today for one address (`kind` "address") or one token ("token")."""
        with self._lock:
            self._start_day(self._now().date())
            return self._stored.get((kind, key), 0)

    def _start_day(self, today: date) -> None:
        if self._day != today:
            self._day, self._stored = today, {}


class MeteredAudit(AuditTrail):
    """The audit trail, with the size of every event it writes charged to the day's budget. Everything else is
    the trail's own: views, verification, the head."""

    def __init__(self, store: Store, clock: Clock, budget: StorageBudget, policy: PolicyEngine | None = None) -> None:
        super().__init__(store, clock, policy=policy)
        self._budget = budget

    def record(self, event_type: AuditEventType, actor: Actor, context: AuditContext) -> AuditEvent:
        event = super().record(event_type, actor, context)
        self._budget.charge(len(event.model_dump_json().encode("utf-8")))
        return event
