"""The PostgreSQL store against the real service: each test in a schema of its own, `tta_test_<random>_<n>`, which
the test creates through the store and drops afterwards, with the roles named after it.

A test that needs the service is marked `live`. It runs only when the run selects live tests (`-m live`) and
`DATABASE_URL` is set; it is skipped otherwise, and says why. The URL is read through `tta.config` and never printed:
a connection that fails is reported by the class of its error only, because libpq's own message names the host and,
for a malformed URL, can repeat the password.
"""

from __future__ import annotations

import itertools
import secrets
from collections.abc import Callable, Iterator

import psycopg
import pytest
from psycopg import sql
from pydantic import SecretStr

from tta.config import get_settings
from tta.store.postgres import PostgresStore

SESSION_PREFIX = f"tta_test_{secrets.token_hex(4)}"
_numbers = itertools.count(1)
NOT_SELECTED = "a live test of the PostgreSQL service: run it with -m live"
NO_URL = "DATABASE_URL is not set"
OUR_SCHEMAS = "SELECT nspname FROM pg_namespace WHERE starts_with(nspname, %s)"
OUR_ROLES = "SELECT rolname FROM pg_roles WHERE starts_with(rolname, %s)"


def live_skip_reason(config: pytest.Config) -> str | None:
    """Why a live test does not run here, or None when it does. `.env` is read only once live tests are selected."""
    if "live" not in (config.getoption("markexpr") or ""):
        return NOT_SELECTED
    if not get_settings().has_database_url:
        return NO_URL
    return None


def _connect(url: SecretStr) -> psycopg.Connection | str:
    """A connection, or the class name of the error that refused it (never its text)."""
    try:
        return psycopg.connect(url.get_secret_value(), autocommit=True, connect_timeout=10)
    except psycopg.Error as error:
        return type(error).__name__


def drop_ours(connection: psycopg.Connection, prefix: str) -> None:
    """Drop every schema, then every role, whose name starts with `prefix`: only what this session created."""
    for (name,) in connection.execute(OUR_SCHEMAS, (prefix,)).fetchall():
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
    for (name,) in connection.execute(OUR_ROLES, (prefix,)).fetchall():
        connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(name)))


@pytest.fixture(scope="session")
def database_url(request: pytest.FixtureRequest) -> SecretStr:
    reason = live_skip_reason(request.config)
    if reason is not None:
        pytest.skip(reason)
    url = get_settings().database_url
    assert url is not None
    return url


@pytest.fixture(scope="session")
def admin(database_url: SecretStr) -> Iterator[psycopg.Connection]:
    """A connection of the test session itself, for what "another program" does and for cleaning up."""
    connection = _connect(database_url)
    if isinstance(connection, str):
        pytest.fail(f"The PostgreSQL service refused the connection ({connection}).", pytrace=False)
    yield connection
    drop_ours(connection, f"{SESSION_PREFIX}_")  # whatever a test's own clean-up left behind
    connection.close()


@pytest.fixture
def pg_schema(admin: psycopg.Connection) -> Iterator[str]:
    """A schema name of this test. The store creates the schema; it is dropped, with its roles, afterwards."""
    name = f"{SESSION_PREFIX}_{next(_numbers)}"
    yield name
    drop_ours(admin, name)


@pytest.fixture
def open_pg(database_url: SecretStr, pg_schema: str) -> Iterator[Callable[[], PostgresStore]]:
    """Open a store on this test's schema; every store opened is closed before the schema is dropped."""
    opened: list[PostgresStore] = []

    def open_store() -> PostgresStore:
        opened.append(PostgresStore(database_url, schema=pg_schema))
        return opened[-1]

    yield open_store
    for store in opened:
        store.close()


@pytest.fixture
def pg_store(open_pg: Callable[[], PostgresStore]) -> PostgresStore:
    return open_pg()


@pytest.fixture
def connect_as(database_url: SecretStr) -> Iterator[Callable[[str, str], psycopg.Connection]]:
    """Connect to the service as another login: the same address and database, another user and password."""
    opened: list[psycopg.Connection] = []

    def connect(user: str, password: str) -> psycopg.Connection:
        conninfo = psycopg.conninfo.make_conninfo(database_url.get_secret_value(), user=user, password=password)
        connection = _connect(SecretStr(conninfo))
        if isinstance(connection, str):
            pytest.fail(f"The login {user} was refused ({connection}).", pytrace=False)
        opened.append(connection)
        return connection

    yield connect
    for connection in opened:
        connection.close()
