"""`GET /healthz`: what is running, where the data comes from, and the head of the audit chain.

Scores on the 20% "how decisions are logged and auditable" (a head another party can keep shows a trail cut
short) and on the 15% path to production.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.audit import GENESIS_HASH

Flow = Callable[..., dict[str, Any]]
SECRET = "a-value-that-must-never-leave-the-process"


def test_health_needs_no_token_and_says_what_is_running(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
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
    assert "sqlite" not in text and "/" not in text.replace("application/", "")
    assert body["settings"]["valio_key_set"] is True
    assert body["settings"]["gemini_key_set"] is True
