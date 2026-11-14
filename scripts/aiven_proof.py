"""The Aiven proof in one command: what Valio Aimo's read-only login can and cannot do on the deployed database.

Usage (from the repository root):
    .venv/bin/python scripts/aiven_proof.py --dry-run      lists every statement and sends nothing
    .venv/bin/python scripts/aiven_proof.py                sends them with the supplier's login

It connects with the supplier's own login, read from `SUPPLIER_DATABASE_URL` through the settings (the same host,
port and database as the gateway's, user `valio_aimo`, a member of `<schema>_supplier`: docs/AIVEN.md section 3),
and prints each statement before its result:

  (a) the supplier reads `audit_supplier`, and is refused on the base table `audit_events` and on `audit_buyer`;
  (b) an UPDATE and a DELETE of an audit row are refused by the database (each is written `WHERE false`, so a
      database that did not refuse it would still change nothing);
  (c) the head of the chain: how many events, the last position and the last hash.

The URL is a secret. It is unwrapped only where the connection is opened; no output carries it. A connection that
fails is reported by the class of its error only, because libpq's own message names the server. The exit code is
0 when every statement did what the proof says, 1 when one did not, 2 when nothing could be sent.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

import psycopg
from pydantic import SecretStr

from tta.config import Settings
from tta.store.postgres import CONNECT_TIMEOUT_SECONDS, DEFAULT_SCHEMA, SCHEMA_NAME

EXIT_OK = 0
EXIT_NOT_AS_SAID = 1
EXIT_NOTHING_SENT = 2
MAX_ROWS_SHOWN = 5
INSUFFICIENT_PRIVILEGE = "42501"  # PostgreSQL's SQLSTATE for "permission denied"
APPLICATION_NAME = "tta-aiven-proof"
NO_URL = (
    "SUPPLIER_DATABASE_URL is not set. Put the supplier login's URL in the environment (docs/AIVEN.md section 3) "
    "or run with --dry-run to list the statements."
)
BAD_SCHEMA = "The schema must be a plain lower-case identifier of at most 41 characters."
UNREACHABLE = "The database could not be reached ({error}). Nothing was sent."

Write = Callable[[str], None]


class ProofSettings(Settings):
    """The gateway's settings plus the supplier login's URL, read the same way (environment, then `.env`)."""

    supplier_database_url: SecretStr | None = None

    @property
    def has_supplier_database_url(self) -> bool:
        return bool(self.supplier_database_url and self.supplier_database_url.get_secret_value().strip())


class Expect(StrEnum):
    ROWS = "answers"
    REFUSED = "refuses it"


@dataclass(frozen=True)
class Statement:
    """One statement of the proof: what it shows, the SQL, and what the database must do with it."""

    part: str
    shows: str
    sql: str
    expect: Expect


class Cursor(Protocol):
    def fetchall(self) -> list[tuple[Any, ...]]: ...


class Connection(Protocol):
    def execute(self, query: str) -> Cursor: ...


def statements(schema: str = DEFAULT_SCHEMA) -> tuple[Statement, ...]:
    """Every statement of the proof, in order. The schema is the only name put into the SQL, and only after it
    matched the store's plain-identifier pattern. Raises `ValueError` otherwise."""
    if not SCHEMA_NAME.fullmatch(schema):
        raise ValueError(BAD_SCHEMA)
    events, buyer, supplier = f"{schema}.audit_events", f"{schema}.audit_buyer", f"{schema}.audit_supplier"
    return (
        Statement("a", "who is connected", "SELECT current_user", Expect.ROWS),
        Statement("a", "the supplier reads its view",
                  f"SELECT seq, type, sentence FROM {supplier} ORDER BY seq DESC LIMIT {MAX_ROWS_SHOWN}",  # noqa: S608
                  Expect.ROWS),
        Statement("a", "the supplier is refused on the base table",
                  f"SELECT seq FROM {events} LIMIT 1", Expect.REFUSED),  # noqa: S608
        Statement("a", "the supplier is refused on the buyer's view",
                  f"SELECT seq FROM {buyer} LIMIT 1", Expect.REFUSED),  # noqa: S608
        Statement("b", "an UPDATE of an audit row is refused",
                  f"UPDATE {events} SET hash = hash WHERE false", Expect.REFUSED),  # noqa: S608
        Statement("b", "a DELETE of an audit row is refused",
                  f"DELETE FROM {events} WHERE false", Expect.REFUSED),  # noqa: S608
        Statement("c", "the chain's count and last position",
                  f"SELECT count(*) AS events, max(seq) AS last_seq FROM {supplier}", Expect.ROWS),  # noqa: S608
        Statement("c", "the chain's head: the hash of the last event",
                  f"SELECT seq, hash FROM {supplier} ORDER BY seq DESC LIMIT 1", Expect.ROWS),  # noqa: S608
    )


def list_statements(schema: str, write: Write) -> None:
    """The dry run: every statement with what it shows and what is expected. Sends nothing."""
    write("Dry run: nothing is sent. The statements of the proof, in order:")
    for number, statement in enumerate(statements(schema), start=1):
        write(f"{number}. ({statement.part}) {statement.shows}. Expected: the database {statement.expect.value}")
        write(f"   {statement.sql};")


def run_proof(connection: Connection, schema: str, write: Write) -> bool:
    """Send every statement, printing it before its result. True when each did what the proof says."""
    as_said = True
    for number, statement in enumerate(statements(schema), start=1):
        write(f"{number}. ({statement.part}) {statement.shows}")
        write(f"   {statement.sql};")
        as_said = _run_one(connection, statement, write) and as_said
    write("Every statement did what the proof says." if as_said else "NOT AS SAID: see the lines marked above.")
    return as_said


def _run_one(connection: Connection, statement: Statement, write: Write) -> bool:
    try:
        rows = connection.execute(statement.sql).fetchall() if statement.expect is Expect.ROWS else None
        if rows is None:
            connection.execute(statement.sql)
    except psycopg.Error as error:
        refused = f"refused by the database: SQLSTATE {error.sqlstate or 'unknown'}, {_message(error)}"
        if statement.expect is Expect.REFUSED:
            write(f"   -> {refused}")
            return True
        write(f"   -> NOT AS SAID: an answer was expected, and the statement was {refused}")
        return False
    if rows is None:
        write("   -> NOT AS SAID: the database did not refuse this statement (it changes nothing: WHERE false)")
        return False
    for row in rows:
        write(f"   -> {' | '.join(str(value) for value in row)}")
    if not rows:
        write("   -> no rows")
    return True


def _message(error: psycopg.Error) -> str:
    """The server's own first line, which names the relation and never the connection."""
    return error.diag.message_primary or type(error).__name__


def connect(url: SecretStr) -> psycopg.Connection[tuple[Any, ...]]:
    """One connection in autocommit, so a refused statement does not stop the next one."""
    return psycopg.connect(url.get_secret_value(), autocommit=True, connect_timeout=CONNECT_TIMEOUT_SECONDS,
                           application_name=APPLICATION_NAME)


def main(argv: Sequence[str] | None = None, *, settings: ProofSettings | None = None,
         write: Write = print, open_connection: Callable[[SecretStr], Any] = connect) -> int:
    parser = argparse.ArgumentParser(description="The Aiven proof: the supplier's read-only login, in SQL.")
    parser.add_argument("--dry-run", action="store_true", help="list every statement and send nothing")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, help=f"the gateway's schema (default {DEFAULT_SCHEMA})")
    arguments = parser.parse_args(argv)
    try:
        statements(arguments.schema)
    except ValueError as error:
        write(str(error))
        return EXIT_NOTHING_SENT
    if arguments.dry_run:
        list_statements(arguments.schema, write)
        return EXIT_OK
    found = settings if settings is not None else ProofSettings()
    if not found.has_supplier_database_url or found.supplier_database_url is None:
        write(NO_URL)
        return EXIT_NOTHING_SENT
    try:
        connection = open_connection(found.supplier_database_url)
    except psycopg.Error as error:
        write(UNREACHABLE.format(error=type(error).__name__))  # libpq's text names the server: the class only
        return EXIT_NOTHING_SENT
    try:
        return EXIT_OK if run_proof(connection, arguments.schema, write) else EXIT_NOT_AS_SAID
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
