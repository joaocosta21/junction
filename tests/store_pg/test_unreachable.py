"""The PostgreSQL store when the database cannot be reached: a typed error, quickly, that carries no part of the URL.

No service is needed: the addresses below are a closed port on this machine and a malformed URL. libpq's own
message would name the host, and for a malformed URL it repeats the password, so neither may reach the error,
its chain or a log line.
"""

from __future__ import annotations

import logging
import time

import psycopg
import pytest
from pydantic import SecretStr

from tta.config import Settings
from tta.contracts.errors import SupplierUnavailable
from tta.store.postgres import CONNECT_TIMEOUT_SECONDS, PostgresStore, open_postgres_store, schema_for

PASSWORD = "sentinel-password-never-shown"
CLOSED_PORT = SecretStr(f"postgresql://tta:{PASSWORD}@127.0.0.1:1/tta?sslmode=disable")
MALFORMED = SecretStr(f"postgresql://tta:{PASSWORD}@[::1:1/tta")


@pytest.mark.parametrize("url", [CLOSED_PORT, MALFORMED], ids=["closed-port", "malformed"])
def test_a_database_that_cannot_be_reached_is_a_typed_error_that_names_no_part_of_the_url(
    url: SecretStr, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    started = time.monotonic()

    with pytest.raises(SupplierUnavailable) as raised:
        PostgresStore(url)

    error = raised.value
    assert time.monotonic() - started < CONNECT_TIMEOUT_SECONDS + 1
    assert error.status_code == 503 and "database" in error.detail
    assert error.__cause__ is None and error.__suppress_context__  # libpq's message is not chained
    shown = " ".join([str(error), repr(error), error.detail, caplog.text])
    assert PASSWORD not in shown and "127.0.0.1" not in shown and "::1" not in shown
    assert "could not be reached" in caplog.text


@pytest.mark.parametrize("schema", ["", "Tta", "tta; DROP TABLE x", "tta-test", "1tta", "x" * 50])
def test_a_schema_name_that_is_not_a_plain_identifier_is_refused_before_connecting(schema: str) -> None:
    with pytest.raises(ValueError, match="schema"):
        PostgresStore(CLOSED_PORT, schema=schema)


def test_a_client_library_without_pipeline_mode_is_refused_before_connecting(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(psycopg.Pipeline, "is_supported", classmethod(lambda cls: False))

    with pytest.raises(SupplierUnavailable):
        PostgresStore(CLOSED_PORT)

    assert "pipeline" in caplog.text


def test_open_postgres_store_needs_the_url_and_reports_an_unreachable_database_as_a_typed_error() -> None:
    with pytest.raises(SupplierUnavailable):
        open_postgres_store(Settings.for_tests())
    with pytest.raises(SupplierUnavailable):
        open_postgres_store(Settings.for_tests(database_url=CLOSED_PORT.get_secret_value()))


def test_a_local_run_has_a_schema_of_its_own_and_the_deployed_gateway_keeps_tta() -> None:
    assert schema_for(Settings.for_tests(tta_env="dev")) == "tta_dev"
    assert schema_for(Settings.for_tests(tta_env="demo")) == "tta"
    assert schema_for(Settings.for_tests(tta_env="prod")) == "tta"
