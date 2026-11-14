"""Gemini out of reach is remembered for a while, so each sentence does not wait for it again (task FIX-9).

Scores on the 30% "working end-to-end demo": with every request timing out, each sentence used to wait for all
its attempts before a recording answered. Once a call has failed for unreachability, the Gemini model refuses
at once for `OUTAGE_MEMORY_SECONDS`, without sending anything: a sentence with a recording is answered from
it straight away (`tta.agent.fallback`), any other one gets `supplier-unavailable` straight away.

One memory per process (`PROCESS_OUTAGE`), shared by the parser and the runner the hooks build; safe to use
from several threads at once.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

OUTAGE_MEMORY_SECONDS = 120.0


class Outage:
    """When the model was last found out of reach, and for how long that is believed."""

    def __init__(
        self, *, seconds: float = OUTAGE_MEMORY_SECONDS, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._seconds = seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._until: float | None = None

    @property
    def seconds(self) -> float:
        return self._seconds

    def note(self) -> None:
        """The model could not be reached just now."""
        with self._lock:
            self._until = self._clock() + self._seconds

    def is_open(self) -> bool:
        """True while the last failure is recent enough to be believed."""
        with self._lock:
            return self._until is not None and self._clock() < self._until

    def clear(self) -> None:
        with self._lock:
            self._until = None


PROCESS_OUTAGE = Outage()
