"""Live price and availability with a fall-back to the replay capture (SPEC section 10, task T09).

Scores on the 30% "working end-to-end demo": the flow survives the mock API being down or its call budget
running out. It is never silent about it: every answer states its own source, an offer carries that source,
and `/healthz` shows the one in use.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Protocol

from tta.contracts.availability import AvailabilityResponse, PriceResponse
from tta.contracts.common import DataSource
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import Clock, ValioGateway

# Below this many calls left in the budget the live API is not asked any more: what is left is kept for the
# re-checks of orders already under way (task T09).
MIN_CALLS_REMAINING = 10
# After a failure the capture answers for this long before the live API is tried again. One lookup is a
# price call and an availability call: the pause keeps both on one source, and keeps a request from
# waiting through the live client's retries every time while the API is down.
RETRY_LIVE_AFTER_SECONDS = 30.0

logger = logging.getLogger(__name__)


class LiveGateway(ValioGateway, Protocol):
    """What the fall-back needs of the live client (`tta.valio.ValioClient`)."""

    @property
    def clock(self) -> Clock: ...

    @property
    def calls_remaining(self) -> int: ...


class ReplayingGateway(ValioGateway, Protocol):
    """What the fall-back needs of the capture (`tta.valio.ReplayGateway`)."""

    @property
    def clock(self) -> Clock: ...


class _SourceClock:
    """The data clock: the capture's pinned time after a replayed answer, the live clock otherwise."""

    def __init__(self, gateway: FallbackGateway) -> None:
        self._gateway = gateway

    def now(self) -> datetime:
        return self._gateway.clock_of_last_answer().now()


class FallbackGateway:
    """The `ValioGateway` port over the live client, answering from the capture when the live API cannot."""

    def __init__(
        self,
        live: LiveGateway,
        replay: ReplayingGateway,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._live = live
        self._replay = replay
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._live_paused_until: float | None = None
        self._last_source = DataSource.LIVE if self._budget_allows_live() else DataSource.REPLAY

    @property
    def source(self) -> DataSource:
        """Where the last answer came from; before any answer, where the budget lets the first one come from."""
        return self._last_source

    @property
    def clock(self) -> Clock:
        return _SourceClock(self)

    def clock_of_last_answer(self) -> Clock:
        return self._replay.clock if self._last_source is DataSource.REPLAY else self._live.clock

    def close(self) -> None:
        """Close the live client's connection, when it has one to close."""
        close = getattr(self._live, "close", None)
        if callable(close):
            close()

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        return self._ask(lambda gateway: gateway.price(product_ids, fresh=fresh))

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:
        return self._ask(lambda gateway: gateway.availability(product_ids, fresh=fresh))

    def _ask[Answer: (PriceResponse, AvailabilityResponse)](self, call: Callable[[ValioGateway], Answer]) -> Answer:
        if self._live_can_be_asked():
            try:
                answer = call(self._live)
            except SupplierUnavailable as error:
                # The detail of this error never holds the key (tta.valio.client).
                logger.warning(
                    "The live supplier API did not answer (%s). Answering from the replay capture for %.0f seconds.",
                    error.detail, RETRY_LIVE_AFTER_SECONDS,
                )
                self._pause_live()
            else:
                self._last_source = DataSource.LIVE
                return answer
        answer = call(self._replay)  # raises `SupplierUnavailable` itself when the capture cannot be used
        self._last_source = DataSource.REPLAY
        return answer

    def _budget_allows_live(self) -> bool:
        return self._live.calls_remaining >= MIN_CALLS_REMAINING

    def _live_can_be_asked(self) -> bool:
        with self._lock:
            paused_until = self._live_paused_until
            if paused_until is not None and self._monotonic() < paused_until:
                return False
            self._live_paused_until = None
        if self._budget_allows_live():
            return True
        if self._last_source is DataSource.LIVE:
            logger.warning(
                "Fewer than %d calls are left in the supplier call budget. Answering from the replay capture.",
                MIN_CALLS_REMAINING,
            )
        return False

    def _pause_live(self) -> None:
        with self._lock:
            self._live_paused_until = self._monotonic() + RETRY_LIVE_AFTER_SECONDS
