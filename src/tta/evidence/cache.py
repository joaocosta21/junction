"""Every Context.dev answer stored by product id, so that a product is looked up once (task S2).

Context.dev charges a cached answer as much as a fresh one (CONTEXTDEV-TECH-CHALLENGE.md), so the gateway keeps
its own: one JSON file per product, `<directory>/<product id>.json`, holding what was sent, what came back and
when. Recordings (`fixtures/evidence/`, the same format) stand behind the store and are never written to: the
demo products are answered from them, so replay shows the same card on every run.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from tta.evidence import wording
from tta.evidence.answers import AnswerRecord, EvidenceUnavailable

# Valio Aimo product ids are digits (AIMO/docs/PRODUCT-DATA.md); anything else never becomes a file name.
PRODUCT_ID = re.compile(r"[A-Za-z0-9]{1,32}")
SUFFIX = ".json"


def _file_name(product_id: str) -> str:
    if PRODUCT_ID.fullmatch(product_id) is None:
        raise EvidenceUnavailable(wording.STORED_UNREADABLE)
    return f"{product_id}{SUFFIX}"


def _read(path: Path) -> AnswerRecord | None:
    if not path.is_file():
        return None
    try:
        return AnswerRecord.from_json(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        raise EvidenceUnavailable(wording.STORED_UNREADABLE) from error


class EvidenceCache:
    """Answers stored in `directory`, with read-only `recorded` answers behind them."""

    def __init__(self, directory: Path, recorded: Path | None = None) -> None:
        self._directory = directory
        self._recorded = recorded

    @property
    def directory(self) -> Path:
        return self._directory

    def get(self, product_id: str) -> AnswerRecord | None:
        """The stored answer, else the recorded one, else `None`. Raises `EvidenceUnavailable` for a file that
        cannot be read."""
        name = _file_name(product_id)
        stored = _read(self._directory / name)
        if stored is not None or self._recorded is None:
            return stored
        return _read(self._recorded / name)

    def put(self, record: AnswerRecord) -> None:
        """Write the answer whole, or not at all: a reader never sees half a file."""
        self._directory.mkdir(parents=True, exist_ok=True)
        target = self._directory / _file_name(record.product_id)
        text = json.dumps(record.to_json(), indent=2, ensure_ascii=False, sort_keys=False) + "\n"
        handle, temporary = tempfile.mkstemp(dir=self._directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(text)
            os.replace(temporary, target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
