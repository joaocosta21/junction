"""The call budget of the Valio API, kept in a file so it holds across restarts (SPEC section 10).

Rate limits are undisclosed and the organisers ask for narrow queries (AIMO/docs/API.md section 2),
so the gateway stops itself at a fixed number of calls.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import IO

from tta.config import Settings
from tta.contracts.errors import SupplierUnavailable

BUDGET_FILE_NAME = "valio_call_budget.json"
LOCK_SUFFIX = ".lock"
TEMPORARY_SUFFIX = ".tmp"
# What a caller is told when no call may be sent. It becomes the `detail` of a public problem
# response, so it names no setting, count or file of ours: those go to the log.
SUPPLIER_NOT_ASKED = "The supplier cannot be asked right now, so no call was made."

logger = logging.getLogger(__name__)


class CallBudget:
    """Counts every call sent to the Valio API and refuses the next one once the limit is reached.

    The file is the only state, so every client, process and script over the same data directory
    shares one budget; a lock file next to the count lets one of them count at a time.
    A file that cannot be read stops every call: the count is never reset silently.
    """

    def __init__(self, path: Path, limit: int) -> None:
        self._path = path
        self._lock_path = path.with_name(path.name + LOCK_SUFFIX)
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

    def remaining(self) -> int:
        """How many calls may still be sent. Zero when the count cannot be read: no call can be made then."""
        try:
            used = self.used
        except SupplierUnavailable as error:
            logger.warning("Valio call budget: no call is left, because the count cannot be read (%s)", error.detail)
            return 0
        return max(self._limit - used, 0)

    def spend(self, endpoint: str) -> None:
        """Count one call, before it is sent. Raises `SupplierUnavailable` when the budget is spent."""
        with self._exclusive():
            used = self.used
            if used >= self._limit:
                logger.warning(
                    "Valio call budget spent: %d of %d calls used, so /%s was not called. "
                    "Raise TTA_VALIO_CALL_BUDGET or switch to replay.",
                    used, self._limit, endpoint,
                )
                raise SupplierUnavailable(SUPPLIER_NOT_ASKED)
            self._write(used + 1)
        logger.info("Valio call budget: %d of %d used (/%s)", used + 1, self._limit, endpoint)

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        """Hold the lock file while the count is read and written, so no writer counts over another."""
        lock = self._open_locked()
        try:
            yield
        finally:
            lock.close()  # closing the file gives the lock back

    def _open_locked(self) -> IO[bytes]:
        """Open the lock file and wait for it. Every spend opens it anew, so the lock also holds between threads."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            lock = self._lock_path.open("ab")
        except OSError as error:
            raise self._unsaved(error) from error
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
        except OSError as error:
            lock.close()
            raise self._unsaved(error) from error
        return lock

    def _write(self, used: int) -> None:
        """Put the new count in place in one step: a reader sees the old count or the new one, never half a file."""
        temporary: str | None = None
        try:
            descriptor, temporary = tempfile.mkstemp(
                dir=self._path.parent, prefix=f"{self._path.name}.", suffix=TEMPORARY_SUFFIX
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"used": used}) + "\n")
            os.replace(temporary, self._path)
        except OSError as error:
            if temporary is not None:
                with suppress(OSError):  # the failure reported is the one above, not the clean-up's
                    os.unlink(temporary)
            raise self._unsaved(error) from error

    def _unsaved(self, error: OSError) -> SupplierUnavailable:
        return SupplierUnavailable(
            f"The call budget for the Valio API could not be saved to {self._path.name} "
            f"({error.strerror}), so no call was made."
        )

    def _unreadable(self) -> str:
        return (
            f"The call budget file {self._path.name} for the Valio API cannot be read, so no call was made. "
            "Correct or delete the file."
        )
