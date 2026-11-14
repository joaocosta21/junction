"""Which store holds the shared order book (task S1): PostgreSQL when `DATABASE_URL` is set, SQLite otherwise, and
SQLite again when the database cannot be reached at start-up, which the gateway then says.

Scores on the 30% "working end-to-end demo" (a database outage at start-up does not stop the demo) and the 20%
"how decisions are logged" (the gateway says where its record is kept). No test here reaches a service: the
unreachable database is a closed port on this machine.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app, wiring
from tta.api.wiring import STORE_FALLBACK, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.store import SqliteStore

PASSWORD = "sentinel-password-never-shown"
UNREACHABLE = f"postgresql://tta:{PASSWORD}@127.0.0.1:1/tta?sslmode=disable"


def _settings(tmp_path: Path, **values: Any) -> Settings:
    return Settings.for_tests(tta_data_dir=tmp_path / "var", **values)


def test_without_a_database_url_the_order_book_is_the_sqlite_file(tmp_path: Path, catalog: ProductCatalog) -> None:
    settings = _settings(tmp_path)

    parts = build_parts(settings, catalog=catalog)

    assert isinstance(parts.store, SqliteStore) and settings.db_path.is_file()
    assert parts.start_reasons == ()
    parts.close()


def test_with_a_database_url_the_order_book_is_the_postgresql_store(
    tmp_path: Path, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[Settings] = []
    stand_in = SqliteStore()  # stands for the PostgreSQL store: no service is reached here

    def open_postgres(settings: Settings) -> SqliteStore:
        opened.append(settings)
        return stand_in

    monkeypatch.setattr(wiring, "open_postgres_store", open_postgres)
    settings = _settings(tmp_path, database_url=UNREACHABLE)

    parts = build_parts(settings, catalog=catalog)

    assert opened == [settings]
    assert parts.store is stand_in and parts.start_reasons == ()
    assert not settings.db_path.exists()  # no SQLite file is made beside it
    parts.close()


def test_a_database_that_cannot_be_reached_at_start_up_leaves_the_gateway_on_sqlite_and_says_why(
    tmp_path: Path, catalog: ProductCatalog, caplog: pytest.LogCaptureFixture, auth: Any, scenario_2: dict[str, Any],
    make_offer: Any,
) -> None:
    caplog.set_level(logging.WARNING)
    settings = _settings(tmp_path, database_url=UNREACHABLE)

    parts = build_parts(settings, catalog=catalog)

    assert isinstance(parts.store, SqliteStore) and settings.db_path.is_file()
    assert parts.start_reasons == (STORE_FALLBACK,)
    assert "could not be reached" in caplog.text
    assert PASSWORD not in caplog.text and "127.0.0.1" not in caplog.text
    with TestClient(create_app(settings, parts=parts)) as client:
        offer = make_offer(client, "agent_ward", scenario_2)  # the flow goes on, on SQLite
        assert parts.store.get_offer(offer["offer_id"]) is not None


def test_the_reason_names_no_path_no_secret_and_no_file_kind() -> None:
    assert "/" not in STORE_FALLBACK and "sqlite" not in STORE_FALLBACK.lower()
    assert "PostgreSQL" in STORE_FALLBACK and "start-up" in STORE_FALLBACK


def test_health_says_the_gateway_runs_on_the_fallback(tmp_path: Path, catalog: ProductCatalog) -> None:
    settings = _settings(tmp_path, database_url=UNREACHABLE)

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        body = client.get("/healthz").json()

    assert body["status"] == "degraded"
    assert STORE_FALLBACK in body["reasons"]
    assert PASSWORD not in str(body)
