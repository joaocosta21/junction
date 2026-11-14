"""The call budget is a file in `var/`: it counts across restarts and writers, and fails closed (SPEC section 10)."""

from __future__ import annotations

import errno
import fcntl
import json
import logging
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tta.contracts.errors import SupplierUnavailable
from tta.valio import CallBudget

WRITERS = 8
SPENDS_PER_WRITER = 100


def spend_from_several_writers(path: Path, limit: int) -> list[int]:
    """Each writer builds its own `CallBudget` on the one file, as two processes would. Returns calls allowed each."""
    start = threading.Barrier(WRITERS)

    def write(_: int) -> int:
        budget = CallBudget(path, limit=limit)
        start.wait()
        allowed = 0
        for _ in range(SPENDS_PER_WRITER):
            try:
                budget.spend("price")
            except SupplierUnavailable:
                continue
            allowed += 1
        return allowed

    with ThreadPoolExecutor(max_workers=WRITERS) as pool:
        return list(pool.map(write, range(WRITERS)))


def test_nothing_is_spent_before_the_first_call(tmp_path: Path) -> None:
    budget = CallBudget(tmp_path / "var" / "budget.json", limit=3)

    assert budget.used == 0
    assert budget.remaining() == 3


def test_spending_counts_up_and_is_written_to_the_file(tmp_path: Path) -> None:
    path = tmp_path / "var" / "budget.json"
    budget = CallBudget(path, limit=3)

    budget.spend("price")
    budget.spend("availability")

    assert json.loads(path.read_text(encoding="utf-8"))["used"] == 2
    assert CallBudget(path, limit=3).remaining() == 1


def test_a_spent_budget_raises_and_counts_no_further(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    budget = CallBudget(path, limit=1)
    budget.spend("price")

    with pytest.raises(SupplierUnavailable):
        budget.spend("price")

    assert budget.used == 1
    assert budget.remaining() == 0


def test_a_spent_budget_tells_the_caller_little_and_the_log_the_rest(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="tta.valio.budget")
    budget = CallBudget(tmp_path / "budget.json", limit=1)
    budget.spend("price")

    with pytest.raises(SupplierUnavailable) as raised:
        budget.spend("availability")

    # The detail becomes a public problem response: no count, no setting, no file of ours.
    assert "cannot be asked right now" in raised.value.detail
    for ours in ("1 of 1", "TTA_VALIO_CALL_BUDGET", "budget"):
        assert ours not in raised.value.detail
    (record,) = caplog.records
    assert record.levelno == logging.WARNING
    assert "1 of 1" in record.getMessage()
    assert "TTA_VALIO_CALL_BUDGET" in record.getMessage()
    assert "/availability" in record.getMessage()


def test_a_budget_of_zero_allows_no_call(tmp_path: Path) -> None:
    with pytest.raises(SupplierUnavailable):
        CallBudget(tmp_path / "budget.json", limit=0).spend("price")


@pytest.mark.parametrize("text", ["", "not json", "[]", '{"used": -1}', '{"used": true}', '{"used": "3"}', "{}"])
def test_a_budget_file_that_cannot_be_read_stops_every_call(tmp_path: Path, text: str) -> None:
    path = tmp_path / "budget.json"
    path.write_text(text, encoding="utf-8")
    budget = CallBudget(path, limit=100)

    with pytest.raises(SupplierUnavailable) as raised:
        budget.spend("price")

    assert "budget" in raised.value.detail
    assert path.read_text(encoding="utf-8") == text  # never reset to zero behind anyone's back


def test_a_budget_that_cannot_be_saved_stops_the_call(tmp_path: Path) -> None:
    (tmp_path / "var").write_text("a file where the folder should be", encoding="utf-8")
    budget = CallBudget(tmp_path / "var" / "budget.json", limit=3)

    with pytest.raises(SupplierUnavailable) as raised:
        budget.spend("price")

    assert "could not be saved" in raised.value.detail


def test_writers_with_their_own_budget_object_lose_no_count(tmp_path: Path) -> None:
    path = tmp_path / "var" / "budget.json"

    allowed = spend_from_several_writers(path, limit=10_000)

    assert allowed == [SPENDS_PER_WRITER] * WRITERS
    assert CallBudget(path, limit=10_000).used == WRITERS * SPENDS_PER_WRITER


def test_several_writers_together_stop_exactly_at_the_limit(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    limit = 500

    allowed = spend_from_several_writers(path, limit=limit)

    assert sum(allowed) == limit
    assert CallBudget(path, limit=limit).used == limit


def test_spending_leaves_only_the_count_and_its_lock_file(tmp_path: Path) -> None:
    path = tmp_path / "var" / "budget.json"

    spend_from_several_writers(path, limit=10_000)

    assert sorted(entry.name for entry in path.parent.iterdir()) == ["budget.json", "budget.json.lock"]


def test_a_count_that_cannot_be_put_in_place_stops_the_call_and_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "budget.json"
    budget = CallBudget(path, limit=3)
    budget.spend("price")

    def refuse(*_: object) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(os, "replace", refuse)

    with pytest.raises(SupplierUnavailable) as raised:
        budget.spend("price")

    assert "could not be saved" in raised.value.detail
    assert budget.used == 1
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["budget.json", "budget.json.lock"]


@pytest.mark.parametrize(("module", "function"), [(fcntl, "flock"), (tempfile, "mkstemp")])
def test_a_lock_or_a_temporary_file_that_cannot_be_had_stops_the_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module: object, function: str
) -> None:
    path = tmp_path / "budget.json"
    budget = CallBudget(path, limit=3)
    budget.spend("price")

    def refuse(*_: object, **__: object) -> None:
        raise OSError(errno.ENOLCK, "No locks available")

    monkeypatch.setattr(module, function, refuse)

    with pytest.raises(SupplierUnavailable) as raised:
        budget.spend("price")

    assert "could not be saved" in raised.value.detail
    assert budget.used == 1


def test_remaining_counts_down_and_never_goes_below_zero(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    budget = CallBudget(path, limit=2)

    budget.spend("price")
    left_after_one = budget.remaining()
    path.write_text(json.dumps({"used": 5}), encoding="utf-8")  # another writer with a higher limit

    assert left_after_one == 1
    assert budget.remaining() == 0


def test_remaining_is_zero_when_the_count_cannot_be_read(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="tta.valio.budget")
    path = tmp_path / "budget.json"
    path.write_text("not json", encoding="utf-8")

    left = CallBudget(path, limit=100).remaining()

    assert left == 0  # no call can be made, so none is left: the caller can turn to replay
    assert path.read_text(encoding="utf-8") == "not json"
    assert [record.levelno for record in caplog.records] == [logging.WARNING]


def test_the_budget_of_the_settings_lives_in_the_data_directory(settings) -> None:
    budget = CallBudget.for_settings(settings)

    budget.spend("price")

    assert (settings.tta_data_dir / "valio_call_budget.json").is_file()
    assert budget.remaining() == settings.tta_valio_call_budget - 1
