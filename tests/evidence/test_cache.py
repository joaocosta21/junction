"""Each answer is stored by product id, so a product is looked up once; recordings stand behind the store."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tta.evidence.answers import AnswerRecord, EvidenceUnavailable
from tta.evidence.cache import EvidenceCache

Record = Callable[[str, dict[str, Any]], AnswerRecord]


def test_a_stored_answer_is_read_back_whole(tmp_path: Path, record: Record, bodies: SimpleNamespace) -> None:
    cache = EvidenceCache(tmp_path / "evidence")
    stored = record("469512", bodies.elovena)

    cache.put(stored)

    assert cache.get("469512") == stored
    assert EvidenceCache(tmp_path / "evidence").get("469512") == stored  # another process reads it too
    assert cache.get("468465") is None


def test_a_recording_answers_when_the_store_has_nothing(
    tmp_path: Path, record: Record, bodies: SimpleNamespace
) -> None:
    EvidenceCache(tmp_path / "recorded").put(record("469512", bodies.elovena))
    cache = EvidenceCache(tmp_path / "evidence", recorded=tmp_path / "recorded")

    assert cache.get("469512") == record("469512", bodies.elovena)
    assert not (tmp_path / "evidence").exists()  # reading a recording writes nothing


def test_the_store_wins_over_a_recording(tmp_path: Path, record: Record, bodies: SimpleNamespace) -> None:
    EvidenceCache(tmp_path / "recorded").put(record("469512", bodies.not_found))
    cache = EvidenceCache(tmp_path / "evidence", recorded=tmp_path / "recorded")
    cache.put(record("469512", bodies.elovena))

    assert cache.get("469512").body == bodies.elovena


@pytest.mark.parametrize("content", ["not json", "[]", json.dumps({"product_id": "469512"})])
def test_a_stored_answer_that_cannot_be_read_is_a_reason(tmp_path: Path, content: str) -> None:
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / "469512.json").write_text(content, encoding="utf-8")

    with pytest.raises(EvidenceUnavailable) as raised:
        EvidenceCache(tmp_path / "evidence").get("469512")

    assert raised.value.reason == "the stored result could not be read"


@pytest.mark.parametrize("product_id", ["../etc/passwd", "a/b", "", "4695 12"])
def test_a_product_id_that_is_not_a_plain_id_is_never_a_file_name(tmp_path: Path, product_id: str) -> None:
    cache = EvidenceCache(tmp_path / "evidence")

    with pytest.raises(EvidenceUnavailable):
        cache.get(product_id)
