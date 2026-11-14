"""Small conformance fixes to the open standards we name (P12 W7).

Scores on the 15% "open, documented standards rather than a proprietary format". Before: no schema of
`/v1/schemas` declared its dialect, the menu and standing-order models were missing there, `POST /v1/offers` and
`POST /v1/orders` answered 201 with no `Location` (RFC 9110, section 10.2.2), a missing `Idempotency-Key` was 422
where the draft says 400, and the draft's own quoted form of the key (a Structured Field String) was refused.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from types import ModuleType
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from tta.api import create_app, schema_export
from tta.api.idempotency import MAX_KEY_LENGTH
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.schemas import all_models

Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]
Problem = Callable[..., dict[str, Any]]
DIALECT = "https://json-schema.org/draft/2020-12/schema"
MENU_AND_STANDING = (
    "MenuRequest", "MenuPlan", "Recipe", "RecipeBook", "StandingOrder", "Renewal", "DriftReport", "NewStandingOrder",
    "RenewStandingOrder",
)


@pytest.fixture(scope="module")
def document(catalog: ProductCatalog, tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    settings = Settings.for_tests(tta_data_dir=tmp_path_factory.mktemp("conformance") / "var")
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        yield client.get("/openapi.json").json()


# --- JSON Schema: the dialect, and every model ------------------------------------------------------------


def test_every_exported_schema_declares_the_2020_12_dialect(client: TestClient) -> None:
    schemas = client.get("/v1/schemas").json()

    assert schemas and all(schema["$schema"] == DIALECT for schema in schemas.values())


def test_the_menu_and_standing_order_models_are_exported_too(client: TestClient) -> None:
    schemas = client.get("/v1/schemas").json()

    for name in MENU_AND_STANDING:
        assert name in schemas, name
    assert set(all_models()) <= set(schemas)
    assert schemas["MenuPlan"]["type"] == "object" and schemas["StandingOrder"]["properties"]


# --- Location on 201 ------------------------------------------------------------------------------------


def test_a_new_offer_says_where_it_lives_and_that_address_answers_with_it(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any]
) -> None:
    response = client.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))

    assert response.status_code == 201
    offer = response.json()
    assert response.headers["location"] == f"/v1/offers/{offer['offer_id']}"
    assert client.get(response.headers["location"], headers=auth("agent_ward")).json() == offer


def test_a_new_order_says_where_it_lives_and_a_retry_points_to_the_same_order(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)
    body = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"]}

    first = client.post("/v1/orders", json=body, headers=auth("agent_ward", "w7-location"))
    again = client.post("/v1/orders", json=body, headers=auth("agent_ward", "w7-location"))

    assert first.status_code == again.status_code == 201
    order_id = first.json()["order_id"]
    assert first.headers["location"] == again.headers["location"] == f"/v1/orders/{order_id}"
    assert client.get(first.headers["location"], headers=auth("agent_ward")).json()["order_id"] == order_id


def test_the_document_names_the_location_header_of_both_201_answers(document: dict[str, Any]) -> None:
    for path in ("/v1/offers", "/v1/orders"):
        created = document["paths"][path]["post"]["responses"]["201"]
        assert "Location" in created["headers"], path
        assert "content" in created, path  # the body is still documented next to the header


# --- Idempotency-Key: 400 when missing, the quoted form accepted ------------------------------------------


def test_an_order_without_an_idempotency_key_is_a_bad_request_and_places_nothing(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow, assert_problem: Problem
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)
    body = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"]}

    response = client.post("/v1/orders", json=body, headers=auth("agent_ward"))

    problem = assert_problem(response, "invalid-request", 400)
    assert "Idempotency-Key" in problem["detail"]
    assert client.get("/v1/orders", headers=auth("agent_ward")).json() == []


def test_the_quoted_form_of_the_draft_is_the_same_key_as_the_bare_form(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)
    body = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"]}

    quoted = client.post("/v1/orders", json=body, headers=auth("agent_ward", '"8e03978e-40d5-43e8"'))
    bare = client.post("/v1/orders", json=body, headers=auth("agent_ward", "8e03978e-40d5-43e8"))

    assert quoted.status_code == bare.status_code == 201
    assert quoted.json() == bare.json()
    assert len(client.get("/v1/orders", headers=auth("agent_ward")).json()) == 1


@pytest.mark.parametrize("key", ['"', '""', '"unbalanced', 'unbalanced"', '"a b"', '"' + "k" * 101 + '"', '"a\\"b"'])
def test_a_quoted_key_outside_the_allowed_form_is_an_invalid_request(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow, assert_problem: Problem, key: str
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)
    body = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"]}

    response = client.post("/v1/orders", json=body, headers=auth("agent_ward", key))

    problem = assert_problem(response, "invalid-request", 422)
    assert [error["field"] for error in problem["errors"]] == ["header.Idempotency-Key"]
    assert client.get("/v1/orders", headers=auth("agent_ward")).json() == []


def test_the_document_says_the_key_is_required_bare_or_quoted_and_a_missing_one_is_400(
    document: dict[str, Any],
) -> None:
    operation = document["paths"]["/v1/orders"]["post"]
    header = next(parameter for parameter in operation["parameters"] if parameter["name"] == "Idempotency-Key")

    assert header["in"] == "header" and header["required"] is True
    assert header["schema"]["maxLength"] == MAX_KEY_LENGTH + 2  # the key and its two quotation marks
    assert "Structured Field String" in header["description"]
    assert "400" in operation["responses"] and "422" in operation["responses"]


def test_two_models_of_one_name_stop_the_export_rather_than_hide_one(monkeypatch: pytest.MonkeyPatch) -> None:
    other = ModuleType("another_contract_module")
    other.Offer = type("Offer", (BaseModel,), {"__module__": other.__name__})  # type: ignore[attr-defined]
    monkeypatch.setattr(schema_export, "MORE_MODULES", (other,))

    with pytest.raises(ValueError, match="Offer"):
        schema_export.exported_schemas()
