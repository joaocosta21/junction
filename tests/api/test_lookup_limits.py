"""Catalog reads are counted, and a search names few name terms in the demonstration (review M3).

Scores on the 30% "working end-to-end demo": a search costs processor time, so one caller may not ask for it
without end; and on the 15% "credible path toward production".
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.limits import RateLimit
from tta.api.service import MAX_DEMO_NAME_TERMS
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import Identity
from tta.contracts.request import ProductQuery

Auth = Callable[..., dict[str, str]]
Problem = Callable[..., dict[str, Any]]
MILK = {"product_type": "milk"}
ENV_TOKEN = "an-environment-token-of-forty-characters"
ENV_TOKENS = json.dumps({
    ENV_TOKEN: {"kind": "AGENT", "id": "agent:canteen", "display_name": "Canteen agent", "profile_id": "hotel-kitchen"},
})


@pytest.fixture
def two_a_minute(settings: Settings, catalog: ProductCatalog) -> Iterator[tuple[TestClient, Parts]]:
    parts = build_parts(settings, catalog=catalog, rate_limit=RateLimit(calls=2, window_seconds=60))
    with TestClient(create_app(settings, parts=parts)) as client:
        yield client, parts


def test_a_search_counts_against_the_lookup_window(
    two_a_minute: tuple[TestClient, Parts], auth: Auth, assert_problem: Problem
) -> None:
    client, _ = two_a_minute
    answers = [client.post("/v1/products/search", json=MILK, headers=auth("agent_hotel")) for _ in range(3)]

    assert [answer.status_code for answer in answers[:2]] == [200, 200]
    problem = assert_problem(answers[2], "rate-limited", 429)
    assert "searches and reads of the catalog" in problem["detail"] and int(answers[2].headers["Retry-After"]) > 0


def test_reading_one_product_counts_against_the_same_window_as_an_offer(
    two_a_minute: tuple[TestClient, Parts], auth: Auth, scenario_1: dict[str, Any], assert_problem: Problem
) -> None:
    client, _ = two_a_minute
    read = client.get("/v1/products/469363", headers=auth("agent_hotel"))
    offer = client.post("/v1/offers", json=scenario_1, headers=auth("agent_hotel"))
    refused = client.get("/v1/products/469363", headers=auth("agent_hotel"))

    assert (read.status_code, offer.status_code) == (200, 201)
    assert_problem(refused, "rate-limited", 429)


def test_the_gateways_own_parts_read_the_catalog_without_being_counted(
    two_a_minute: tuple[TestClient, Parts], agent_hotel: Identity
) -> None:
    # The menu planner and the pages call the service itself: their call is counted where it begins.
    _, parts = two_a_minute

    for _ in range(5):
        assert parts.service.search_products(agent_hotel, ProductQuery(product_type="milk")).total > 0
        assert parts.service.get_product(agent_hotel, "469363").id == "469363"


def test_in_the_demonstration_a_search_names_at_most_four_name_terms(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    assert MAX_DEMO_NAME_TERMS == 4

    four = client.post("/v1/products/search", json={"name_terms": ["milk", "lactose", "free", "1"]},
                       headers=auth("agent_hotel"))
    five = client.post("/v1/products/search", json={"name_terms": ["milk", "lactose", "free", "1", "l"]},
                       headers=auth("agent_hotel"))

    assert four.status_code == 200
    problem = assert_problem(five, "invalid-request", 422)
    assert "at most 4 name terms" in problem["detail"] and "this one names 5" in problem["detail"]


def test_outside_the_demonstration_a_search_may_name_the_contracts_ten(tmp_path: Any, catalog: ProductCatalog) -> None:
    settings = Settings.for_tests(tta_env="prod", tta_tokens=ENV_TOKENS, tta_data_dir=tmp_path / "var")

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        ten = client.post("/v1/products/search", json={"name_terms": [f"word{n}" for n in range(10)]},
                          headers={"Authorization": f"Bearer {ENV_TOKEN}"})

    assert ten.status_code == 200
