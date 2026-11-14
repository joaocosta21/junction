"""The two clocks behind the `Clock` port (SPEC section 10).

Cut-offs are compared with the Valio server's time, not with this machine's: `timeNow` is Helsinki
time and comes with every availability answer (AIMO/docs/API.md section 6.1).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_offset(instant: datetime) -> None:
    if instant.utcoffset() is None:
        raise ValueError("a clock needs a time with an offset, not a naive one")


@dataclass(frozen=True)
class PinnedClock:
    """Always answers the instant it was pinned to, for example a capture's `timeNow`."""

    instant: datetime

    def __post_init__(self) -> None:
        _require_offset(self.instant)

    def now(self) -> datetime:
        return self.instant


class LiveClock:
    """The server's time as last told, and UTC now until the first answer.

    Between two answers the last `timeNow` is carried forward by the time that has passed since
    it was seen, so an approval still expires when nobody calls the API for a while. The time
    passed is read from this machine's wall clock, which keeps counting while the machine sleeps.
    """

    def __init__(self, utc_now: Callable[[], datetime] = _utc_now) -> None:
        self._utc_now = utc_now
        self._anchor: tuple[datetime, datetime] | None = None  # (server time, our UTC time when it was seen)

    def observe(self, time_now: datetime) -> None:
        """Take the `timeNow` of a response that has just arrived as the current server time."""
        _require_offset(time_now)
        self._anchor = (time_now, self._utc_now())

    def now(self) -> datetime:
        anchor = self._anchor
        if anchor is None:
            return self._utc_now()
        server_time, seen_at = anchor
        return server_time + (self._utc_now() - seen_at)
