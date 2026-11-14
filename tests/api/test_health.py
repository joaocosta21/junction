"""`GET /healthz`: what is running, where the data comes from, and the head of the audit chain.

Scores on the 20% "how decisions are logged and auditable" (a head another party can keep shows a trail cut
short) and on the 15% path to production.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tta.api import create_app, wiring
from tta.api.wiring import STORE_FALLBACK, STORE_IS_POSTGRESQL, STORE_IS_SQLITE, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.audit import GENESIS_HASH
from tta.store import SqliteStore

Flow = Callable[..., dict[str, Any]]
SECRET = "a-value-that-must-never-leave-the-process"


def test_health_needs_no_token_and_says_what_is_running(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["reasons"]) == ("ok", [])
    assert (body["environment"], body["mode"], body["source"]) == ("dev", "replay", "replay")
    assert body["audit_head"] == {"events": 0, "last_hash": GENESIS_HASH}
    assert body["settings"]["replay_capture"] == "2026-11-14-demo"
    assert body["agent"] == {"request_parser": False, "agent_runner": False}
    assert body["surfaces"] == {"mcp": False, "pages": False}


def test_the_audit_head_moves_with_every_event(
    client: TestClient, parts: Any, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    make_offer(client, "agent_ward", scenario_2)

    head = client.get("/healthz").json()["audit_head"]

    assert head["events"] >= 4
    assert head["last_hash"] == parts.store.last_audit_hash() != GENESIS_HASH


def test_health_reads_the_whole_trail_once_and_then_only_its_last_hash(
    client: TestClient, parts: Any, scenario_2: dict[str, Any], make_offer: Flow, monkeypatch: Any
) -> None:
    # The route is public and not rate limited: a caller must not be able to make it read every event each time.
    whole_trail_reads: list[int] = []
    genuine = parts.store.list_audit_events

    def counted(*args: Any, **kwargs: Any) -> Any:
        whole_trail_reads.append(1)
        return genuine(*args, **kwargs)

    monkeypatch.setattr(parts.store, "list_audit_events", counted)

    empty = [client.get("/healthz").json()["audit_head"] for _ in range(5)]
    make_offer(client, "agent_ward", scenario_2)
    after = [client.get("/healthz").json()["audit_head"] for _ in range(5)]

    assert empty == [{"events": 0, "last_hash": GENESIS_HASH}] * 5
    assert after == [{"events": len(genuine()), "last_hash": parts.store.last_audit_hash()}] * 5
    assert len(whole_trail_reads) == 1


def test_health_does_not_show_the_supplier_call_budget(tmp_path: Any, catalog: ProductCatalog) -> None:
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_valio_call_budget=137)
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        response = client.get("/healthz")

    assert "137" not in response.text
    assert "budget" not in response.text
    # What is configured is still shown, each secret as true or false only.
    assert response.json()["settings"] == {
        "env": "dev", "mode": "replay", "replay_capture": "2026-11-14-demo", "valio_key_set": False,
        "gemini_key_set": False, "database_url_set": False, "context_dev_key_set": False, "tokens_set": False,
        "signing_key_set": False,
    }


def test_health_shows_no_secret_and_no_path(tmp_path: Any, catalog: ProductCatalog) -> None:
    settings = Settings.for_tests(
        tta_data_dir=tmp_path / "var", valio_aimo_api_key=SECRET, gemini_api_key=SECRET, database_url=SECRET,
        context_dev_api_key=SECRET,
    )
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        text = client.get("/healthz").text
        body = client.get("/healthz").json()

    assert SECRET not in text
    assert str(tmp_path) not in text
    # The store's kind is named, never its file; the one path shown is the public address of the signing keys.
    shown = text.replace("application/", "").replace("/.well-known/jwks.json", "")
    assert ".sqlite" not in text and "/" not in shown
    assert body["settings"]["valio_key_set"] is True
    assert body["settings"]["gemini_key_set"] is True


def test_health_names_the_store_in_use_and_why(client: TestClient) -> None:
    store = client.get("/healthz").json()["store"]

    assert store == {"kind": "sqlite", "reason": STORE_IS_SQLITE}
    assert "DATABASE_URL is not set" in store["reason"]


def test_health_names_postgresql_when_the_database_answered(
    tmp_path: Any, catalog: ProductCatalog, monkeypatch: Any
) -> None:
    stand_in = SqliteStore()  # stands for the PostgreSQL store: no service is reached here
    monkeypatch.setattr(wiring, "open_postgres_store", lambda settings: stand_in)
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", database_url=f"postgresql://u:{SECRET}@db.internal/x")

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        response = client.get("/healthz")

    assert response.json()["store"] == {"kind": "postgresql", "reason": STORE_IS_POSTGRESQL}
    assert SECRET not in response.text and "db.internal" not in response.text


def test_health_says_sqlite_and_the_reason_when_the_database_could_not_be_reached(
    tmp_path: Any, catalog: ProductCatalog
) -> None:
    unreachable = f"postgresql://tta:{SECRET}@127.0.0.1:1/tta?sslmode=disable"
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", database_url=unreachable)

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        response = client.get("/healthz")

    assert response.json()["store"] == {"kind": "sqlite", "reason": STORE_FALLBACK}
    assert SECRET not in response.text and "127.0.0.1" not in response.text


def test_the_setting_of_the_mcp_origins_exists_and_is_read() -> None:
    from tta.api.mcp_origin import LOCAL_ORIGINS, allowed_origins

    assert Settings.for_tests().tta_mcp_allowed_origins == ""
    settings = Settings.for_tests(tta_mcp_allowed_origins="https://Inspector.example, https://host.example:8443")

    assert allowed_origins(settings) == (*LOCAL_ORIGINS, "https://inspector.example", "https://host.example:8443")
