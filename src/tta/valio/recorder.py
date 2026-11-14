"""Writes every live answer of the Valio API to disk in the capture format of `fixtures/valio/` (SPEC section 10).

A recording folder can be handed to `ReplayGateway` as it is. Only the response body, the ids
asked for and the server time are written: never the key, never a request header.
"""

from __future__ import annotations

import itertools
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from tta.config import Settings
from tta.valio.parsing import ENDPOINTS
from tta.valio.replay import MANIFEST_NAME  # the recorder writes what the replay reads

RECORDINGS_DIR_NAME = "recordings"
IDS_NAME = "ids.json"


@dataclass(frozen=True)
class _Recorded:
    file: str
    endpoint: str
    ids: tuple[str, ...]
    time_now: datetime


_SESSION_NUMBERS = itertools.count(1)


def _new_session_name() -> str:
    """UTC start time, process id and a number: no two recorders write to the same folder."""
    return f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}-{next(_SESSION_NUMBERS)}"


class Recorder:
    """One folder per recorder: `<endpoint>-<n>.json` bodies, `ids.json` and `manifest.json`."""

    def __init__(self, root: Path, session: str | None = None) -> None:
        self._session_dir = root / (session or _new_session_name())
        self._recorded: tuple[_Recorded, ...] = ()

    @classmethod
    def for_settings(cls, settings: Settings) -> Recorder:
        return cls(settings.tta_data_dir / RECORDINGS_DIR_NAME)

    @property
    def session_dir(self) -> Path:
        return self._session_dir

    def record(self, endpoint: str, ids: Sequence[str], body_text: str, time_now: datetime) -> Path:
        """Write one body exactly as it arrived and bring the manifest up to date. Raises `OSError`.

        `time_now` is the server time of the answer. /api/price states none, so the caller passes
        the clock's time at retrieval.
        """
        number = 1 + sum(1 for entry in self._recorded if entry.endpoint == endpoint)
        name = f"{endpoint}-{number}.json"
        self._session_dir.mkdir(parents=True, exist_ok=True)
        path = self._session_dir / name
        path.write_bytes(body_text.encode("utf-8"))
        self._recorded = (*self._recorded, _Recorded(name, endpoint, tuple(ids), time_now))
        self._write_index()
        return path

    def _write_index(self) -> None:
        ids = sorted({product_id for entry in self._recorded for product_id in entry.ids})
        manifest = {
            "capture": self._session_dir.name,
            "time_now": max(entry.time_now for entry in self._recorded).isoformat(),
            "product_count": len(ids),
            "calls": len(self._recorded),
            "files": {
                endpoint: [entry.file for entry in self._recorded if entry.endpoint == endpoint]
                for endpoint in ENDPOINTS
            },
            "requests": [
                {"file": entry.file, "endpoint": entry.endpoint, "ids": list(entry.ids),
                 "time_now": entry.time_now.isoformat()}
                for entry in self._recorded
            ],
        }
        (self._session_dir / IDS_NAME).write_text(json.dumps(ids), encoding="utf-8")
        (self._session_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
