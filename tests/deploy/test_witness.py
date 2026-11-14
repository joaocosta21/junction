"""AP-10: the witness of the audit head. The check is pure and has four cases; the reads go through a stand-in
connection; nothing is scheduled without `SUPPLIER_DATABASE_URL`. No test connects to a database or to Modal."""

from __future__ import annotations

import importlib.util
import logging
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import ModuleType, SimpleNamespace
from typing import Any

import modal
import pytest

import tta.config
from tta.config import REPO_ROOT, Settings

DEPLOY_DIR = REPO_ROOT / "deploy"
NOW = datetime(2026, 11, 15, 8, 0, tzinfo=UTC)
URL = "postgres://valio_aimo:sentinel-password@db.example:5432/defaultdb?sslmode=require"
A, B, C = "a" * 64, "b" * 64, "c" * 64


def _load(name: str, file: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, DEPLOY_DIR / file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def witness() -> Iterator[ModuleType]:
    """Loaded under the name the container imports it by, so `run_witness` finds the same module."""
    module = _load("witness", "witness.py")
    yield module
    sys.modules.pop("witness", None)


class Trail:
    """Stands for a connection to the supplier's view: (seq, hash) rows, and every statement it was sent."""

    def __init__(self, rows: list[tuple[int, str]]) -> None:
        self.rows, self.statements, self.closed = rows, [], False

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> SimpleNamespace:
        self.statements.append(query)
        if query.startswith("SELECT count(*)"):
            row: tuple[Any, ...] | None = (len(self.rows), max((seq for seq, _ in self.rows), default=None))
        else:
            row = next(((digest,) for seq, digest in self.rows if params and seq == params[0]), None)
        return SimpleNamespace(fetchone=lambda: row)

    def close(self) -> None:
        self.closed = True


# --- the pure check: the four cases of the plan, and the first run -------------------------------------------------


def test_the_same_head_is_fine(witness: ModuleType) -> None:
    head = witness.Head(3, 3, C)

    verdict = witness.check(head, head, C)

    assert (verdict.finding, verdict.ok) == (witness.Finding.SAME, True)
    assert verdict.sentence == "The head is the one noted last time (3 events, last number 3, hash cccccccccccc…)."


def test_a_grown_trail_is_fine_when_the_noted_head_is_still_at_its_place(witness: ModuleType) -> None:
    verdict = witness.check(witness.Head(2, 2, B), witness.Head(5, 5, C), B)

    assert (verdict.finding, verdict.ok) == (witness.Finding.GROWN, True)
    assert verdict.sentence.startswith("3 event(s) were appended since the last run and the noted head is still")


@pytest.mark.parametrize("now", [(2, 2, B), (0, None, None), (3, 2, B)])
def test_a_shortened_trail_is_found(witness: ModuleType, now: tuple[Any, ...]) -> None:
    verdict = witness.check(witness.Head(3, 3, C), witness.Head(*now), None)

    assert (verdict.finding, verdict.ok) == (witness.Finding.SHORTENED, False)
    assert verdict.sentence.startswith("The audit trail was shortened: 3 events were noted (last number 3)")


@pytest.mark.parametrize("at_noted", [A, None])
def test_a_rewritten_row_is_found_even_when_the_trail_grew(witness: ModuleType, at_noted: str | None) -> None:
    verdict = witness.check(witness.Head(2, 2, B), witness.Head(4, 4, C), at_noted)

    assert (verdict.finding, verdict.ok) == (witness.Finding.REWRITTEN, False)
    assert "event number 2 was noted with hash bbbbbbbbbbbb…" in verdict.sentence


def test_the_first_run_notes_the_head_and_an_empty_trail_is_a_head_too(witness: ModuleType) -> None:
    assert witness.check(None, witness.Head(2, 2, B), None).finding is witness.Finding.FIRST
    empty = witness.Head(0, None, None)
    assert witness.check(None, empty, None).sentence == "First run: the head was noted (the trail is empty)."
    assert witness.check(empty, empty, None).finding is witness.Finding.SAME
    assert witness.check(empty, witness.Head(1, 1, A), None).finding is witness.Finding.GROWN


# --- reading the view and keeping the note -------------------------------------------------------------------------


def test_one_run_reads_only_the_suppliers_view_and_notes_the_head(witness: ModuleType) -> None:
    trail, notes = Trail([(1, A), (2, B)]), {}

    verdict = witness.witness_once(trail, notes, "tta", NOW)

    assert verdict.finding is witness.Finding.FIRST
    assert notes == {"tta": {
        "count": 2, "seq": 2, "hash": B, "noted_at": NOW.isoformat(), "moved_at": NOW.isoformat(), "finding": "FIRST",
    }}
    assert all('FROM "tta".audit_supplier' in statement for statement in trail.statements)
    assert all(statement.startswith("SELECT ") for statement in trail.statements)  # a reader: it writes nothing


def test_run_after_run_the_note_follows_an_intact_trail(witness: ModuleType) -> None:
    notes: dict[str, Any] = {}
    witness.witness_once(Trail([(1, A), (2, B)]), notes, "tta", NOW)

    same = witness.witness_once(Trail([(1, A), (2, B)]), notes, "tta", NOW)
    grown = witness.witness_once(Trail([(1, A), (2, B), (3, C)]), notes, "tta", NOW)

    assert (same.finding, grown.finding) == (witness.Finding.SAME, witness.Finding.GROWN)
    assert (notes["tta"]["seq"], notes["tta"]["hash"]) == (3, C)


@pytest.mark.parametrize(("rows", "finding"), [
    ([(1, A)], "SHORTENED"),  # cut at its end
    ([(1, A), (2, C)], "REWRITTEN"),  # the noted event replaced
    ([(1, C), (2, C), (3, C)], "REWRITTEN"),  # rewritten whole and longer
])
def test_a_trail_that_was_cut_or_rewritten_keeps_the_earlier_note(
    witness: ModuleType, rows: list[tuple[int, str]], finding: str
) -> None:
    notes: dict[str, Any] = {}
    witness.witness_once(Trail([(1, A), (2, B)]), notes, "tta", NOW)
    before = dict(notes["tta"])

    verdict = witness.witness_once(Trail(rows), notes, "tta", NOW)

    assert (verdict.finding.value, verdict.ok) == (finding, False)
    assert notes["tta"] == before  # the proof is not overwritten


def test_each_schema_has_its_own_note(witness: ModuleType) -> None:
    notes: dict[str, Any] = {}
    witness.witness_once(Trail([(1, A), (2, B)]), notes, "tta", NOW)

    fresh = witness.witness_once(Trail([]), notes, "tta_nov15", NOW)

    assert fresh.finding is witness.Finding.FIRST and set(notes) == {"tta", "tta_nov15"}


@pytest.mark.parametrize("schema", ['tta"; DROP TABLE x; --', "Tta", "", "t" * 42])
def test_a_schema_name_that_is_not_plain_is_refused_before_any_statement(witness: ModuleType, schema: str) -> None:
    trail = Trail([])

    with pytest.raises(ValueError, match="plain lower-case identifier"):
        witness.witness_once(trail, {}, schema, NOW)
    assert trail.statements == []


@pytest.mark.parametrize("note", ["text", {"count": 1}, {"count": "1", "seq": 1, "hash": A}])
def test_a_note_that_cannot_be_read_is_said_and_not_taken_for_a_first_run(witness: ModuleType, note: Any) -> None:
    with pytest.raises(ValueError, match="earlier note cannot be read"):
        witness.witness_once(Trail([(1, A)]), {"tta": note}, "tta", NOW)


# --- in deploy/modal_app.py ----------------------------------------------------------------------------------------


def test_without_the_suppliers_login_no_witness_exists_and_nothing_is_scheduled(modal_app: ModuleType) -> None:
    assert modal_app.WITNESS_WANTED is False
    assert not hasattr(modal_app, "witness_audit_head")
    assert modal_app.witness_secret_values(Settings.for_tests(), {}) == {}
    assert modal_app.witness_is_wanted(is_local=True, secret_env={}, environ={"SUPPLIER_DATABASE_URL": URL}) is False
    assert modal_app.witness_is_wanted(is_local=False, secret_env={}, environ={}) is False
    assert modal_app.witness_is_wanted(is_local=False, secret_env={}, environ={"SUPPLIER_DATABASE_URL": " "}) is False


@pytest.fixture
def modal_app_with_the_login(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    monkeypatch.setattr(tta.config, "get_settings", Settings.for_tests)
    monkeypatch.setenv("SUPPLIER_DATABASE_URL", URL)
    module = _load("tta_deploy_modal_app_witness", "modal_app.py")
    yield module
    sys.modules.pop("tta_deploy_modal_app_witness", None)


def test_with_the_suppliers_login_the_witness_is_a_scheduled_function_with_a_secret_of_its_own(
    modal_app_with_the_login: ModuleType,
) -> None:
    module = modal_app_with_the_login

    assert module.WITNESS_WANTED is True
    assert isinstance(module.witness_audit_head, modal.Function)
    assert module.WITNESS_ENV == {"SUPPLIER_DATABASE_URL": URL}
    assert "SUPPLIER_DATABASE_URL" not in module.secret_values(Settings.for_tests())  # never in the gateway's Secret
    assert "SUPPLIER_DATABASE_URL" not in module.IMAGE_ENV and URL not in str(module.IMAGE_ENV)


def test_the_witness_reads_the_schema_the_deployment_chose(modal_app: ModuleType) -> None:
    chosen = SimpleNamespace(supplier_database_url=URL, tta_db_schema="tta_nov15")

    assert modal_app.witness_secret_values(chosen, {}) == {"SUPPLIER_DATABASE_URL": URL, "TTA_DB_SCHEMA": "tta_nov15"}
    assert modal_app.witness_secret_values(Settings.for_tests(), {"SUPPLIER_DATABASE_URL": f" {URL} "}) == {
        "SUPPLIER_DATABASE_URL": URL,
    }


def test_inside_the_container_the_witness_is_defined_from_the_environment_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def must_not_be_called() -> Settings:
        raise AssertionError("settings were read inside the container")

    monkeypatch.setattr(tta.config, "get_settings", must_not_be_called)
    monkeypatch.setattr(modal, "is_local", lambda: False)
    monkeypatch.setenv("SUPPLIER_DATABASE_URL", URL)
    try:
        module = _load("tta_deploy_modal_app_witness_remote", "modal_app.py")
        assert module.WITNESS_WANTED is True and module.WITNESS_ENV == {}
        assert isinstance(module.witness_audit_head, modal.Function)
    finally:
        sys.modules.pop("tta_deploy_modal_app_witness_remote", None)


def test_a_run_notes_the_head_in_the_given_store_and_closes_its_connection(
    modal_app: ModuleType, witness: ModuleType, caplog: pytest.LogCaptureFixture
) -> None:
    trail, notes = Trail([(1, A), (2, B)]), {}

    with caplog.at_level(logging.INFO):
        sentence = modal_app.run_witness(lambda: trail, notes, {"TTA_DB_SCHEMA": "tta_nov15"})

    assert sentence.startswith("First run: the head was noted (2 events, last number 2")
    assert trail.closed and set(notes) == {"tta_nov15"}
    assert "Audit witness, schema tta_nov15: First run" in caplog.text


def test_a_run_that_finds_the_trail_cut_fails_loudly_and_names_no_login(
    modal_app: ModuleType, witness: ModuleType, caplog: pytest.LogCaptureFixture
) -> None:
    notes: dict[str, Any] = {}
    modal_app.run_witness(lambda: Trail([(1, A), (2, B)]), notes, {})
    cut = Trail([(1, A)])

    with pytest.raises(RuntimeError, match="The audit trail was shortened") as failed:
        modal_app.run_witness(lambda: cut, notes, {"SUPPLIER_DATABASE_URL": URL})

    assert cut.closed and notes["tta"]["seq"] == 2
    assert "sentinel-password" not in str(failed.value) and "sentinel-password" not in caplog.text


def test_the_notes_are_kept_through_a_modal_dict(modal_app: ModuleType) -> None:
    kept: dict[str, Any] = {}
    store = SimpleNamespace(get=kept.get, put=kept.__setitem__, keys=kept.keys, len=lambda: len(kept))
    notes = modal_app.DictNotes(store)

    notes["tta"] = {"count": 1}

    assert (notes.get("tta"), notes.get("other"), list(notes), len(notes)) == ({"count": 1}, None, ["tta"], 1)
    with pytest.raises(TypeError, match="never removed"):
        del notes["tta"]


# --- S9: a head that does not move is not proof of health -------------------------------------------------------


def _hours(count: float) -> datetime:
    return NOW + timedelta(hours=count)


def test_the_same_head_within_the_threshold_is_healthy_and_keeps_the_time_it_last_moved(witness: ModuleType) -> None:
    notes: dict[str, Any] = {}
    witness.witness_once(Trail([(1, A)]), notes, "tta", NOW)

    verdict = witness.witness_once(Trail([(1, A)]), notes, "tta", _hours(5.9))

    assert (verdict.finding, verdict.ok, verdict.warning) == (witness.Finding.SAME, True, False)
    assert (notes["tta"]["moved_at"], notes["tta"]["noted_at"]) == (NOW.isoformat(), _hours(5.9).isoformat())


def test_a_head_that_has_not_moved_for_six_hours_is_a_warning_that_says_so(witness: ModuleType) -> None:
    notes: dict[str, Any] = {}
    witness.witness_once(Trail([(1, A)]), notes, "tta", NOW)
    for hour in range(1, 6):  # the hourly runs in between do not restart the clock
        witness.witness_once(Trail([(1, A)]), notes, "tta", _hours(hour))

    verdict = witness.witness_once(Trail([(1, A)]), notes, "tta", _hours(6))

    assert witness.STALE_AFTER_HOURS == 6
    assert (verdict.finding, verdict.ok, verdict.warning) == (witness.Finding.STALE, True, True)
    assert verdict.sentence == (
        "No new audit event for 6 hours: the gateway may be writing elsewhere; check /healthz store. The noted head "
        "is still at its place (1 events, last number 1, hash aaaaaaaaaaaa…)."
    )
    assert notes["tta"]["moved_at"] == NOW.isoformat() and notes["tta"]["finding"] == "STALE"


def test_a_new_event_ends_the_warning_and_restarts_the_clock(witness: ModuleType) -> None:
    notes: dict[str, Any] = {}
    witness.witness_once(Trail([(1, A)]), notes, "tta", NOW)
    witness.witness_once(Trail([(1, A)]), notes, "tta", _hours(7))

    grown = witness.witness_once(Trail([(1, A), (2, B)]), notes, "tta", _hours(8))
    same = witness.witness_once(Trail([(1, A), (2, B)]), notes, "tta", _hours(13))

    assert (grown.finding, same.finding) == (witness.Finding.GROWN, witness.Finding.SAME)
    assert notes["tta"]["moved_at"] == _hours(8).isoformat()


def test_a_stale_trail_that_was_also_cut_is_still_found_cut(witness: ModuleType) -> None:
    notes: dict[str, Any] = {}
    witness.witness_once(Trail([(1, A), (2, B)]), notes, "tta", NOW)

    verdict = witness.witness_once(Trail([(1, A)]), notes, "tta", _hours(9))

    assert (verdict.finding, verdict.ok, verdict.warning) == (witness.Finding.SHORTENED, False, False)


def test_a_note_written_before_the_field_existed_counts_from_its_noted_time(witness: ModuleType) -> None:
    notes: dict[str, Any] = {"tta": {"count": 1, "seq": 1, "hash": A, "noted_at": NOW.isoformat(), "finding": "SAME"}}

    verdict = witness.witness_once(Trail([(1, A)]), notes, "tta", _hours(6))

    assert verdict.finding is witness.Finding.STALE and notes["tta"]["moved_at"] == NOW.isoformat()


def test_a_note_with_no_readable_time_is_not_guessed_stale_and_starts_counting_now(witness: ModuleType) -> None:
    notes: dict[str, Any] = {"tta": {"count": 1, "seq": 1, "hash": A, "noted_at": "yesterday"}}

    verdict = witness.witness_once(Trail([(1, A)]), notes, "tta", _hours(100))

    assert verdict.finding is witness.Finding.SAME and notes["tta"]["moved_at"] == _hours(100).isoformat()


def test_the_scheduled_run_logs_the_warning_and_does_not_fail(
    modal_app: ModuleType, witness: ModuleType, caplog: pytest.LogCaptureFixture
) -> None:
    long_ago = (datetime.now(UTC) - timedelta(hours=7)).isoformat()
    notes: dict[str, Any] = {"tta": {"count": 1, "seq": 1, "hash": A, "noted_at": long_ago, "moved_at": long_ago}}

    with caplog.at_level(logging.INFO):
        sentence = modal_app.run_witness(lambda: Trail([(1, A)]), notes, {})

    assert sentence.startswith("No new audit event for 7 hours: the gateway may be writing elsewhere; check /healthz")
    assert [record.levelname for record in caplog.records if "Audit witness" in record.message] == ["WARNING"]
