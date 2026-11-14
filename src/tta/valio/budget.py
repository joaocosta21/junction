"""The call budget of the Valio API, kept in a file so it holds across restarts (SPEC section 10).

Rate limits are undisclosed and the organisers ask for narrow queries (AIMO/docs/API.md section 2),
so the gateway stops itself at a fixed number of calls.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from tta.config import Settings
from tta.contracts.errors import SupplierUnavailable

BUDGET_FILE_NAME = "valio_call_budget.json"

logger = logging.getLogger(__name__)


class CallBudget:
    """Counts every call sent to the Valio API and refuses the next one once the limit is reached.

    The file is the only state, so two clients over the same data directory share one budget.
    A file that cannot be read stops every call: the count is never reset silently.
    """

    def __init__(self, path: Path, limit: int) -> None:
        self._path = path
        self._limit = limit

    @classmethod
    def for_settings(cls, settings: Settings) -> CallBudget:
        return cls(settings.tta_data_dir / BUDGET_FILE_NAME, settings.tta_valio_call_budget)

    @property
    def used(self) -> int:
        if not self._path.exists():
            return 0
        try:
            stored = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise SupplierUnavailable(self._unreadable()) from error
        used = stored.get("used") if isinstance(stored, dict) else None
        if type(used) is not int or used < 0:
            raise SupplierUnavailable(self._unreadable())
        return used

    @property
    def remaining(self) -> int:
        return max(self._limit - self.used, 0)

    def spend(self, endpoint: str) -> None:
        """Count one call, before it is sent. Raises `SupplierUnavailable` when the budget is spent."""
        used = self.used
        if used >= self._limit:
            raise SupplierUnavailable(
                f"The call budget for the Valio API is spent: {used} of {self._limit} calls used, so /{endpoint} "
                "was not called. Raise TTA_VALIO_CALL_BUDGET or switch to replay."
            )
        self._write(used + 1)
        logger.info("Valio call budget: %d of %d used (/%s)", used + 1, self._limit, endpoint)

    def _write(self, used: int) -> None:
        temporary = self._path.with_suffix(".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps({"used": used}) + "\n", encoding="utf-8")
            os.replace(temporary, self._path)
        except OSError as error:
            raise SupplierUnavailable(
                f"The call budget for the Valio API could not be saved to {self._path.name} "
                f"({error.strerror}), so no call was made."
            ) from error

    def _unreadable(self) -> str:
        return (
            f"The call budget file {self._path.name} for the Valio API cannot be read, so no call was made. "
            "Correct or delete the file."
        )
