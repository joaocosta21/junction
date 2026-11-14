"""The Aiven proof script with a stand-in connection: nothing here reaches a database or reads `.env`.

The proof (AWARDS-PLAN, AP-5): with the supplier's read-only login, (a) `audit_supplier` answers and the base table
and the buyer's view refuse, (b) an UPDATE and a DELETE of an audit row are refused, (c) the chain's head and
count. The script prints each statement before its result and never a secret.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import psycopg
import pytest
from pydantic import SecretStr

from tta.config import REPO_ROOT

SECRET_URL = "postgres://valio_aimo:not-a-real-password@db.example.invalid:5432/defaultdb?sslmode=require"  # noqa: S105
HEAD_HASH = "ab" * 32


def _load() -> ModuleType:
    path = Path(REPO_ROOT) / "scripts" / "aiven_proof.py"
    spec = importlib.util.spec_from_file_location("aiven_proof", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # a dataclass looks its module up by name
    spec.loader.exec_module(module)
    return module


proof = _load()


class _Cursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


class StandIn:
    """A connection that answers as the supplier's login must: its view answers, everything else is refused."""

    def __init__(self, *, lets_everything_through: bool = False, view_refused: bool = False) -> None:
        self.sent: list[str] = []
        self.closed = False
        self._open = lets_everything_through
        self._view_refused = view_refused

    def execute(self, query: str) -> _Cursor:
        self.sent.append(query)
        if "audit_supplier" in query:
            if self._view_refused:
                raise psycopg.errors.InsufficientPrivilege("permission denied for view audit_supplier")
            if "count(*)" in query:
                return _Cursor([(17, 17)])
            if "hash" in query:
                return _Cursor([(17, HEAD_HASH)])
            return _Cursor([(17, "tta.v1.order.placed", "The agent placed the order within its authority.")])
        if "current_user" in query:
            return _Cursor([("valio_aimo",)])
        if self._open:
            return _Cursor([])
        raise psycopg.errors.InsufficientPrivilege("permission denied for table audit_events")

    def close(self) -> None:
        self.closed = True


def _settings(url: str | None = SECRET_URL) -> Any:
    return proof.ProofSettings.for_tests(supplier_database_url=None if url is None else SecretStr(url))


def _run(*argv: str, connection: StandIn | None = None, url: str | None = SECRET_URL) -> tuple[int, list[str]]:
    lines: list[str] = []
    stand_in = connection or StandIn()
    code = proof.main(list(argv), settings=_settings(url), write=lines.append, open_connection=lambda _url: stand_in)
    return code, lines


def test_the_dry_run_lists_every_statement_and_sends_nothing() -> None:
    connection = StandIn()

    code, lines = _run("--dry-run", connection=connection)

    assert code == proof.EXIT_OK and connection.sent == []
    text = "\n".join(lines)
    assert all(statement.sql in text for statement in proof.statements())
    assert "Dry run: nothing is sent." in lines[0]


def test_the_dry_run_needs_no_url_and_reads_no_settings() -> None:
    lines: list[str] = []

    def never(_url: SecretStr) -> Any:
        raise AssertionError("the dry run opens no connection")

    code = proof.main(["--dry-run"], settings=None, write=lines.append, open_connection=never)

    assert code == proof.EXIT_OK and len(lines) == 1 + 2 * len(proof.statements())


def test_the_statements_cover_the_three_parts_of_the_proof() -> None:
    found = proof.statements("tta")
    by_part = {part: [each for each in found if each.part == part] for part in "abc"}

    assert [(each.expect, "audit_supplier" in each.sql) for each in by_part["a"][1:]] == [
        (proof.Expect.ROWS, True), (proof.Expect.REFUSED, False), (proof.Expect.REFUSED, False),
    ]
    assert "FROM tta.audit_events" in by_part["a"][2].sql and "FROM tta.audit_buyer" in by_part["a"][3].sql
    assert [each.sql.split()[0] for each in by_part["b"]] == ["UPDATE", "DELETE"]
    assert all(each.expect is proof.Expect.REFUSED and each.sql.endswith("WHERE false") for each in by_part["b"])
    assert all(each.expect is proof.Expect.ROWS and "audit_supplier" in each.sql for each in by_part["c"])


def test_a_run_prints_each_statement_before_its_result_and_the_refusals_with_their_sqlstate() -> None:
    connection = StandIn()

    code, lines = _run(connection=connection)

    assert code == proof.EXIT_OK and connection.closed
    assert connection.sent == [statement.sql for statement in proof.statements()]
    update = next(index for index, line in enumerate(lines) if line.strip().startswith("UPDATE"))
    assert lines[update + 1] == (
        "   -> refused by the database: SQLSTATE 42501, InsufficientPrivilege"
    )
    assert f"   -> 17 | {HEAD_HASH}" in lines and "   -> 17 | 17" in lines
    assert lines[-1] == "Every statement did what the proof says."


def test_a_statement_the_database_does_not_refuse_fails_the_proof() -> None:
    code, lines = _run(connection=StandIn(lets_everything_through=True))

    assert code == proof.EXIT_NOT_AS_SAID
    assert sum("NOT AS SAID: the database did not refuse" in line for line in lines) == 4
    assert lines[-1].startswith("NOT AS SAID")


def test_a_view_the_supplier_cannot_read_fails_the_proof() -> None:
    code, lines = _run(connection=StandIn(view_refused=True))

    assert code == proof.EXIT_NOT_AS_SAID
    assert any("NOT AS SAID: an answer was expected" in line and "42501" in line for line in lines)


def test_no_output_carries_the_url_or_the_password() -> None:
    def unreachable(_url: SecretStr) -> Any:
        raise psycopg.OperationalError(f"connection to server at {SECRET_URL} failed")

    lines: list[str] = []
    code = proof.main([], settings=_settings(), write=lines.append, open_connection=unreachable)
    _, ran = _run()

    assert code == proof.EXIT_NOTHING_SENT
    assert lines == ["The database could not be reached (OperationalError). Nothing was sent."]
    for line in (*lines, *ran, repr(_settings())):
        assert "not-a-real-password" not in line and "db.example.invalid" not in line


def test_without_the_suppliers_url_nothing_is_sent() -> None:
    connection = StandIn()

    code, lines = _run(connection=connection, url=None)

    assert code == proof.EXIT_NOTHING_SENT and connection.sent == []
    assert lines == [proof.NO_URL]


@pytest.mark.parametrize("schema", ["tta; DROP TABLE x", "Tta", "a" * 42, ""])
def test_a_schema_that_is_not_a_plain_identifier_is_refused_before_anything_is_sent(schema: str) -> None:
    connection = StandIn()

    code, lines = _run("--schema", schema, connection=connection)

    assert code == proof.EXIT_NOTHING_SENT and connection.sent == []
    assert lines == [proof.BAD_SCHEMA]
    with pytest.raises(ValueError, match="plain lower-case identifier"):
        proof.statements(schema)


def test_another_schema_is_named_in_every_statement_that_reads_the_trail() -> None:
    found = proof.statements("tta_dev")

    assert all("tta_dev.audit_" in each.sql for each in found[1:])
