"""Which language model the buyer's agent asks, and whether its last call got an answer (task AG).

Scores on the 15% "clear visibility of assumptions": `/healthz` can say which provider and model are configured
and whether the model answered the last time it was asked, without a call of its own and without the key or the
address. `reachable` is `None` until the first call of this process, then `True` or `False` after each call.
One memory per process (`PROCESS_STATUS`), shared by the parser and the runner; safe from several threads.
"""

from __future__ import annotations

import threading
from typing import Any

from tta.config import Settings


class ModelStatus:
    """Whether the model answered the last call. Nothing else is kept: no address, no key, no text."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reachable: bool | None = None

    def note(self, *, reachable: bool) -> None:
        with self._lock:
            self._reachable = reachable

    @property
    def reachable(self) -> bool | None:
        with self._lock:
            return self._reachable

    def clear(self) -> None:
        with self._lock:
            self._reachable = None


PROCESS_STATUS = ModelStatus()


def agent_status(settings: Settings, status: ModelStatus = PROCESS_STATUS) -> dict[str, Any]:
    """`{"provider": …, "model": …, "reachable": …}` for `/healthz`: the provider chosen, the model name when a
    model is asked at all, and whether its last call was answered (`None` before the first call, and always when
    no model is asked). Never the key, never the address."""
    from tta.agent.gemini import chosen_model  # imported here: the Gemini SDK is not needed to say "none"

    if settings.has_agent_endpoint:
        return {"provider": settings.tta_agent_provider, "model": settings.tta_agent_model,
                "reachable": status.reachable}
    if settings.has_gemini_key:
        return {"provider": "gemini", "model": chosen_model(settings), "reachable": status.reachable}
    return {"provider": "none", "model": None, "reachable": None}
