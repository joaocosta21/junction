"""The two clocks behind the `Clock` port (SPEC section 10).

Cut-offs are compared with the Valio server's time, not with this machine's: `timeNow` is Helsinki
time and comes with every availability answer (AIMO/docs/API.md section 6.1). That answer is
untrusted input and the clock decides cut-offs and expiry, so an answer can move the clock forward
only, and only when it states a time close to this machine's own.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from tta.contracts.errors import SupplierUnavailable

# The furthest a `timeNow` may be from this machine's UTC time and still be believed.
MAX_SERVER_TIME_DIFFERENCE_HOURS = 12
MAX_SERVER_TIME_DIFFERENCE = timedelta(hours=MAX_SERVER_TIME_DIFFERENCE_HOURS)
NO_LEAD = timedelta(0)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _offset(instant: datetime) -> timedelta:
    offset = instant.utcoffset()
    if offset is None:
        raise ValueError("a clock needs a time with an offset, not a naive one")
    return offset


@dataclass(frozen=True)
class PinnedClock:
    """Always answers the instant it was pinned to, for example a capture's `timeNow`."""

    instant: datetime

    def __post_init__(self) -> None:
        _offset(self.instant)

    def now(self) -> datetime:
        return self.instant


class LiveClock:
    """The server's time as last told, carried forward, and UTC now until the first answer.

    The clock reads this machine's UTC time plus the furthest ahead of it that any answer has put
    the server, in the offset of the last answer. So between two answers the server's time is
    carried forward by the time that has passed (this machine's wall clock, which keeps counting
    while the machine sleeps), and an approval still expires when nobody calls the API for a while.

    The clock never reads earlier than it did: an answer that states an earlier time than the
    clock already reads, the first answer included, changes the offset and nothing else. An answer
    that states a time more than 12 hours from this machine's is refused.
    """

    def __init__(self, utc_now: Callable[[], datetime] = _utc_now) -> None:
        self._utc_now = utc_now
        self._lock = threading.Lock()  # two answers at once must not undo each other's step forward
        self._reading: tuple[timedelta, timezone] = (NO_LEAD, UTC)  # (the server's lead over us, its offset)

    def observe(self, time_now: datetime) -> None:
        """Take the `timeNow` of an answer that has just arrived. Raises `SupplierUnavailable` when it is far off."""
        zone = timezone(_offset(time_now))
        lead = time_now - self._utc_now()
        if abs(lead) > MAX_SERVER_TIME_DIFFERENCE:
            logger.warning(
                "Valio timeNow refused: it is %.0f seconds from this machine's UTC time, and at most %d hours "
                "are believed. Check this machine's clock.",
                lead.total_seconds(), MAX_SERVER_TIME_DIFFERENCE_HOURS,
            )
            raise SupplierUnavailable(
                f"The Valio API answer states a server time more than {MAX_SERVER_TIME_DIFFERENCE_HOURS} hours "
                "from this gateway's own, so it was not used."
            )
        with self._lock:
            self._reading = (max(lead, self._reading[0]), zone)

    def now(self) -> datetime:
        lead, zone = self._reading
        return (self._utc_now() + lead).astimezone(zone)
