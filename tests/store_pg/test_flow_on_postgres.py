"""The whole flow by HTTP with the order book on PostgreSQL: request, offer, order, approval, order, audit; then a
new gateway on the same database finds the order and the trail (what a redeploy does).

Scores on the 30% "full request → lookup → order/approval flow" and the 20% "how decisions are logged".
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from pydantic import SecretStr

from tta.api import create_app, wiring
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.store.postgres import PostgresStore

pytestmark = pytest.mark.live

OPTIONAL_MODULES = ("tta.agent", "tta.api.mcp_surface", "tta.ui.routes")  # the API alone, as in tests/api
MONDAY = "2026-11-16"
SCENARIO_1 = {
    "needed_by": MONDAY,
    "lines": [{"text": "1,000 litres of lactose-free milk by Monday", "product_type": "milk",
               "required_claims": ["FREE_FROM_LACTOSE"], "quantity": 1000, "unit": "L"}],
}
TOKENS = {
    "agent_hotel": "demo-agent-hotel-kitchen", "hotel_purchasing": "demo-approver-hotel-purchasing",
    "hotel_finance": "demo-approver-hotel-finance", "hotel_dietitian": "demo-approver-hotel-dietitian",
}
APPROVER_BY_ROLE = {
    "purchasing_manager": "hotel_purchasing", "finance": "hotel_finance", "dietitian": "hotel_dietitian",
}


def _auth(who: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {TOKENS[who]}"}
    return headers if key is None else {**headers, "Idempotency-Key": key}


@pytest.fixture(autouse=True)
def without_optional_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in OPTIONAL_MODULES:
        monkeypatch.setitem(sys.modules, name, None)


@pytest.fixture(scope="module")
def catalog() -> ProductCatalog:
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture
def on_postgres(
    tmp_path: Path, database_url: SecretStr, pg_schema: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Settings]:
    """Settings with the service's URL; the wiring opens the store in this test's schema."""
    opened: list[PostgresStore] = []

    def open_in_test_schema(settings: Settings) -> PostgresStore:
        assert settings.database_url is not None
        opened.append(PostgresStore(settings.database_url, schema=pg_schema))
        return opened[-1]

    monkeypatch.setattr(wiring, "open_postgres_store", open_in_test_schema)
    yield Settings.for_tests(tta_data_dir=tmp_path / "var", database_url=database_url.get_secret_value())
    for store in opened:
        store.close()


def _order_and_approve(client: TestClient) -> dict[str, Any]:
    offer = client.post("/v1/offers", json=SCENARIO_1, headers=_auth("agent_hotel"))
    assert offer.status_code == 201, offer.text
    chosen = offer.json()["options"][0]
    placed = client.post(
        "/v1/orders", json={"offer_id": offer.json()["offer_id"], "option_id": chosen["option_id"]},
        headers=_auth("agent_hotel", "pg-flow-1"),
    )
    assert placed.status_code == 201, placed.text
    order = placed.json()
    assert order["status"] == "PENDING_APPROVAL"
    queue = client.get("/v1/approvals", params={"status": "pending"}, headers=_auth("hotel_purchasing")).json()
    approval = next(entry for entry in queue if entry["approval_id"] == order["approval_id"])
    for role in approval["required_roles"]:
        decided = client.post(
            f"/v1/approvals/{order['approval_id']}/decision",
            json={"decision": "APPROVE", "note": "Approved for the weekend."}, headers=_auth(APPROVER_BY_ROLE[role]),
        )
        assert decided.status_code == 200, decided.text
        order = decided.json()
    return order


def test_the_flow_runs_on_postgresql_and_a_new_gateway_finds_its_record(
    on_postgres: Settings, catalog: ProductCatalog, admin: psycopg.Connection, pg_schema: str
) -> None:
    parts = build_parts(on_postgres, catalog=catalog)
    assert isinstance(parts.store, PostgresStore) and parts.start_reasons == ()
    with TestClient(create_app(on_postgres, parts=parts)) as client:
        order = _order_and_approve(client)
        head = client.get("/healthz").json()["audit_head"]
    assert order["status"] == "ORDERED" and order["placed_by"] == "HUMAN_APPROVAL"
    assert not on_postgres.db_path.exists()  # nothing went to SQLite

    later = build_parts(on_postgres, catalog=catalog)  # a new process on the same database
    with TestClient(create_app(on_postgres, parts=later)) as client:
        read = client.get(f"/v1/orders/{order['order_id']}", headers=_auth("agent_hotel"))
        audit = client.get("/v1/audit", params={"order_id": order["order_id"]}, headers=_auth("agent_hotel")).json()
        again = client.get("/healthz").json()["audit_head"]

    assert read.status_code == 200 and read.json()["status"] == "ORDERED"
    assert audit["chain"]["ok"] is True and "tta.v1.order.confirmed" in [event["type"] for event in audit["events"]]
    assert again == head
    supplier_rows = admin.execute(
        sql.SQL("SELECT type, sentence FROM {} WHERE order_id = %s ORDER BY seq").format(
            sql.Identifier(pg_schema, "audit_supplier")),
        (order["order_id"],),
    ).fetchall()
    assert [kind for kind, _ in supplier_rows][-1] == "tta.v1.order.confirmed"
    assert all(sentence and "Approved for the weekend" not in sentence for _, sentence in supplier_rows)
    (events,) = admin.execute(
        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(pg_schema, "audit_events"))
    ).fetchone()
    assert events == head["events"]
