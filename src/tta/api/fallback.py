"""Live price and availability with a fall-back to the replay capture (SPEC section 10, tasks T09 and FIX-8).

Scores on the 30% "working end-to-end demo": the flow survives the mock API being down, its call budget
running out, or more visitors than the budget can serve. It is never silent about it: every answer states
its own source, an offer carries that source, and `/healthz` shows the source of the last look and why.

One look is a price call and an availability call. Both are answered by the live API, or, when either
fails or the live API cannot be asked, both by the capture: an offer is never built on two sources.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from tta.api.limits import (
    MAX_LIVE_LOOKS_PER_MINUTE,
    MAX_LIVE_LOOKS_PER_VISITOR_PER_MINUTE,
    SECONDS_PER_MINUTE,
    Counted,
    RateLimit,
    RateLimiter,
    current_client_key,
)
from tta.contracts.availability import AvailabilityResponse, PriceResponse
from tta.contracts.common import DataSource
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import Clock, ValioGateway

# Below this many calls left in the budget the live API is not asked any more (task T09). A look needs
# two calls, so it is asked only while the second one would still be made at or above the floor.
MIN_CALLS_REMAINING = 10
LIVE_CALLS_PER_LOOK = 2
SINGLE_CALL = 1
# After a failure the capture answers for this long before the live API is tried again, so that a request
# does not wait through the live client's retries every time while the API is down.
RETRY_LIVE_AFTER_SECONDS = 30.0
LIVE_LOOKS = "live looks"

# Why the live API is not asked. The budget and the looks a minute are logged once, when they start to hold.
PAUSED = f"it failed less than {RETRY_LIVE_AFTER_SECONDS:.0f} seconds ago"  # said when it failed
BUDGET_LOW = f"fewer than {MIN_CALLS_REMAINING} calls would be left in the supplier call budget"
TOO_MANY_LOOKS = f"more than {MAX_LIVE_LOOKS_PER_MINUTE} looks a minute were asked for"
TOO_MANY_LOOKS_OF_ONE_VISITOR = (
    f"one visitor asked for more than {MAX_LIVE_LOOKS_PER_VISITOR_PER_MINUTE} looks a minute"
)
ALL_LOOKS = RateLimit(calls=MAX_LIVE_LOOKS_PER_MINUTE, window_seconds=SECONDS_PER_MINUTE)
LOOKS_OF_ONE_VISITOR = RateLimit(calls=MAX_LIVE_LOOKS_PER_VISITOR_PER_MINUTE, window_seconds=SECONDS_PER_MINUTE)

logger = logging.getLogger(__name__)


class LiveGateway(ValioGateway, Protocol):
    """What the fall-back needs of the live client (`tta.valio.ValioClient`)."""

    @property
    def clock(self) -> Clock: ...

    @property
    def calls_remaining(self) -> int: ...


@dataclass(frozen=True)
class LookState:
    """What `/healthz` reports of the fall-back, read from memory: no call and no file is touched for it."""

    last_source: DataSource | None  # of the last completed look; `None` before the first one
    live_paused: bool  # the live API failed and is not asked again yet
    budget_low: bool  # as found at the last look


class FallbackGateway:
    """The `ValioGateway` and `PairedLookup` ports over the live client, answering from the capture when the
    live API cannot. The offer package asks through `look_up`; the two single calls are the port's."""

    def __init__(
        self,
        live: LiveGateway,
        replay: ValioGateway,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._live = live
        self._replay = replay
        self._monotonic = monotonic
        self._live_looks = RateLimiter(ALL_LOOKS, monotonic=monotonic)
        self._lock = threading.Lock()  # guards the four fields below; never held while a gateway is asked
        self._live_paused_until: float | None = None
        self._last_source: DataSource | None = None
        self._budget_low = False
        self._not_live_because: str | None = None

    @property
    def source(self) -> DataSource:
        """The source this gateway asks first, and the one its clock belongs to. Each answer states its own
        source; `state()` says where the last look came from."""
        return DataSource.LIVE

    @property
    def clock(self) -> Clock:
        """The data clock of live mode: always the live clock (real time, the supplier's `timeNow` carried
        forward), also while the capture answers. A replayed answer still carries the capture's own time."""
        return self._live.clock

    def state(self) -> LookState:
        with self._lock:
            paused = self._live_paused_until is not None and self._monotonic() < self._live_paused_until
            return LookState(last_source=self._last_source, live_paused=paused, budget_low=self._budget_low)

    def close(self) -> None:
        """Close the live client's connection, when it has one to close."""
        close = getattr(self._live, "close", None)
        if callable(close):
            close()

    def look_up(
        self, product_ids: Sequence[str], *, fresh: bool = False
    ) -> tuple[PriceResponse, AvailabilityResponse]:
        """Price and availability for the same ids, both live or both from the capture."""
        return self._ask(
            lambda gateway: (gateway.price(product_ids, fresh=fresh), gateway.availability(product_ids, fresh=fresh)),
            LIVE_CALLS_PER_LOOK,
        )

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        return self._ask(lambda gateway: gateway.price(product_ids, fresh=fresh), SINGLE_CALL)

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:
        return self._ask(lambda gateway: gateway.availability(product_ids, fresh=fresh), SINGLE_CALL)

    def _ask[Answer](self, ask: Callable[[ValioGateway], Answer], live_calls: int) -> Answer:
        """The whole answer from the live API, or the whole answer from the capture."""
        if self._live_can_be_asked(live_calls):
            try:
                answer = ask(self._live)
            except SupplierUnavailable as error:
                # The detail of this error never holds the key (tta.valio.client).
                logger.warning(
                    "The live supplier API did not answer (%s). Answering from the replay capture for %.0f seconds.",
                    error.detail, RETRY_LIVE_AFTER_SECONDS,
                )
                self._pause_live()
            else:
                self._completed(DataSource.LIVE)
                return answer
        answer = ask(self._replay)  # raises `SupplierUnavailable` itself when the capture cannot be used
        self._completed(DataSource.REPLAY)
        return answer

    def _live_can_be_asked(self, live_calls: int) -> bool:
        reason = self._why_not_live(live_calls)
        with self._lock:
            said, self._not_live_because = self._not_live_because, reason
        if reason not in (None, said, PAUSED):
            logger.warning("The live supplier API is not asked: %s. Answering from the replay capture.", reason)
        return reason is None

    def _why_not_live(self, live_calls: int) -> str | None:
        """The reason the live API is not asked for this look, or `None` after taking one of the minute's looks."""
        with self._lock:
            if self._live_paused_until is not None and self._monotonic() < self._live_paused_until:
                return PAUSED
            self._live_paused_until = None
        budget_low = self._live.calls_remaining - (live_calls - 1) < MIN_CALLS_REMAINING  # reads a file: no lock
        with self._lock:
            self._budget_low = budget_low
        if budget_low:
            return BUDGET_LOW
        # Asked last, so that a look the capture answers anyway does not take one of the minute's live looks.
        # The visitor is the one of the request being served (`tta.api.limits.ClientKeyMiddleware`).
        visitors = Counted(f"{LIVE_LOOKS} {current_client_key()}", LOOKS_OF_ONE_VISITOR)
        full = self._live_looks.full_window((Counted(LIVE_LOOKS, ALL_LOOKS), visitors))
        if full is None:
            return None
        return TOO_MANY_LOOKS_OF_ONE_VISITOR if full is visitors else TOO_MANY_LOOKS

    def _pause_live(self) -> None:
        with self._lock:
            self._live_paused_until = self._monotonic() + RETRY_LIVE_AFTER_SECONDS

    def _completed(self, source: DataSource) -> None:
        with self._lock:
            self._last_source = source
