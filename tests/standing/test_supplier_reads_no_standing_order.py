"""The supplier's token learns nothing about which standing orders exist (security review, finding L3).

Before: GET /v1/standing-orders/{id} answered 403 for an id that exists and 404 for one that does not, because the
caller was checked after the lookup. Now the caller is checked first: both answer 403.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import hooks, wiring
from tta.api.app import create_app
from tta.config import Settings
from tta.contracts.common import Identity
from tta.contracts.errors import NotAuthorised
from tta.standing.demo import DEMO_STANDING_ORDER_ID, load_demo

AGENT = {"Authorization": "Bearer demo-agent-hotel-kitchen"}
SUPPLIER = {"Authorization": "Bearer demo-supplier-valio-aimo"}
MILK = {"lines": [{"text": "100 L of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}]}


@pytest.mark.parametrize("standing_order_id", [DEMO_STANDING_ORDER_ID, "so_nobody"])
def test_the_supplier_is_refused_the_same_way_for_an_id_that_exists_and_one_that_does_not(
    standing_order_id: str, book, agent_hotel: Identity, supplier_reader: Identity
) -> None:
    load_demo(book.standing, agent_hotel, book.replay)

    with pytest.raises(NotAuthorised):
        book.standing.find(supplier_reader, standing_order_id)
    with pytest.raises(NotAuthorised):
        book.standing.get(supplier_reader, standing_order_id)


def test_over_rest_both_ids_answer_the_supplier_with_the_same_status_and_body(
    tmp_path: Path, catalog: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_module, hidden = hooks.optional_module, (hooks.AGENT_MODULE, hooks.MCP_MODULE)
    monkeypatch.setattr(hooks, "optional_module", lambda name: None if name in hidden else real_module(name))
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_env="demo", tta_replay_capture="2026-11-14-demo")
    app = create_app(settings, parts=wiring.build_parts(settings, catalog=catalog))
    with TestClient(app) as client:
        created = client.post("/v1/standing-orders", json={"name": "Milk", "request": MILK}, headers=AGENT)
        assert created.status_code == 201, created.text
        existing = client.get(f"/v1/standing-orders/{created.json()['standing_order_id']}", headers=SUPPLIER)
        unknown = client.get("/v1/standing-orders/so_nobody", headers=SUPPLIER)

    assert existing.status_code == unknown.status_code == 403
    same = ("type", "title", "status", "detail")
    assert [existing.json().get(key) for key in same] == [unknown.json().get(key) for key in same]
