"""How fast the public demonstration's database can be grown (task FIX-10, finding 10).

Scores on the 30% "working end-to-end demo" (the public link keeps working) and on the 15% "credible path
toward production": in dev and demo a request has at most five lines, and the audit trail counts an
excluded product once, however many lines exclude it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.service import MAX_DEMO_REQUEST_LINES
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings

Auth = Callable[..., dict[str, str]]
Problem = Callable[..., dict[str, Any]]
MILK = {"text": "milk", "product_type": "milk", "quantity": 1, "unit": "L"}
ENV_TOKEN = "an-environment-token-of-forty-characters"
ENV_TOKENS = json.dumps({
    ENV_TOKEN: {"kind": "AGENT", "id": "agent:canteen", "display_name": "Canteen agent", "profile_id": "hotel-kitchen"},
})


def test_in_the_demonstration_a_request_has_at_most_five_lines(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    assert MAX_DEMO_REQUEST_LINES == 5

    five = client.post("/v1/offers", json={"lines": [MILK] * 5}, headers=auth("agent_hotel"))
    six = client.post("/v1/offers", json={"lines": [MILK] * 6}, headers=auth("agent_hotel"))

    assert five.status_code == 201
    problem = assert_problem(six, "invalid-request", 422)
    assert "at most 5 lines" in problem["detail"] and "this one has 6" in problem["detail"]


def test_outside_the_demonstration_a_request_may_have_the_contracts_twenty_lines(
    tmp_path: Any, catalog: ProductCatalog
) -> None:
    settings = Settings.for_tests(tta_env="prod", tta_tokens=ENV_TOKENS, tta_data_dir=tmp_path / "var")
    app = create_app(settings, parts=build_parts(settings, catalog=catalog))

    with TestClient(app) as client:
        offer = client.post("/v1/offers", json={"lines": [MILK] * 6}, headers={"Authorization": f"Bearer {ENV_TOKEN}"})

    assert offer.status_code == 201


def test_the_audit_trail_counts_an_excluded_product_once_however_many_lines_exclude_it(
    client: TestClient, auth: Auth
) -> None:
    one = client.post("/v1/offers", json={"lines": [MILK]}, headers=auth("agent_hotel")).json()
    three = client.post("/v1/offers", json={"lines": [MILK] * 3}, headers=auth("agent_hotel")).json()
    trail = client.get("/v1/audit", params={"offer_id": three["offer_id"]}, headers=auth("agent_hotel")).json()
    created = next(event for event in trail["events"] if event["type"].endswith("offer.created"))

    distinct = {exclusion["product_id"] for exclusion in three["excluded"]}
    assert len(three["excluded"]) == 3 * len(distinct) == 3 * len(one["excluded"])  # the offer keeps every line's
    assert sum(created["facts"]["offer"]["excluded_by_reason"].values()) == len(distinct)
    assert f"{len(distinct)} products excluded" in created["sentence"]
