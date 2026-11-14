"""The call budget is a file in `var/`: it counts across restarts and fails closed (SPEC section 10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tta.contracts.errors import SupplierUnavailable
from tta.valio import CallBudget


def test_nothing_is_spent_before_the_first_call(tmp_path: Path) -> None:
    budget = CallBudget(tmp_path / "var" / "budget.json", limit=3)

    assert budget.used == 0
    assert budget.remaining == 3


def test_spending_counts_up_and_is_written_to_the_file(tmp_path: Path) -> None:
    path = tmp_path / "var" / "budget.json"
    budget = CallBudget(path, limit=3)

    budget.spend("price")
    budget.spend("availability")

    assert json.loads(path.read_text(encoding="utf-8"))["used"] == 2
    assert CallBudget(path, limit=3).remaining == 1


def test_a_spent_budget_raises_and_counts_no_further(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    budget = CallBudget(path, limit=1)
    budget.spend("price")

    with pytest.raises(SupplierUnavailable) as raised:
        budget.spend("price")

    assert "1 of 1" in raised.value.detail
    assert budget.used == 1


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


def test_the_budget_of_the_settings_lives_in_the_data_directory(settings) -> None:
    budget = CallBudget.for_settings(settings)

    budget.spend("price")

    assert (settings.tta_data_dir / "valio_call_budget.json").is_file()
    assert budget.remaining == settings.tta_valio_call_budget - 1
