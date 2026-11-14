"""The published interface: generated OpenAPI with examples from the scenarios, and the JSON Schemas
(SPEC section 2). Scores on the 15% "open, documented standards rather than a proprietary format"."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, TypeAdapter

from tta.api import create_app
from tta.api.audit_pages import AuditPage
from tta.api.schema_export import exported_models
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.agent import AgentRun, ParseRequestBody
from tta.contracts.common import Verdict
from tta.contracts.errors import PROBLEM_CONTENT_TYPE, ProblemDetails
from tta.contracts.offer import Offer, SubstituteQuery, SubstituteResult
from tta.contracts.order import Approval, DecisionRequest, Order, PlaceOrderRequest
from tta.contracts.policy import Authority
from tta.contracts.product import Product, SearchResult
from tta.contracts.request import ProductQuery, PurchaseRequest
from tta.contracts.schemas import all_models
from tta.contracts.standing import NewStandingOrder, RenewStandingOrder
from tta.menus.sentence import MenuAsk

# SPEC section 2, plus the order list the pages need (task note) and the health check.
ROUTES = {
    ("get", "/v1/authority"): "get_authority",
    ("post", "/v1/products/search"): "search_products",
    ("get", "/v1/products/{product_id}"): "get_product",
    ("post", "/v1/products/{product_id}/substitutes"): "find_substitutes",
    ("post", "/v1/offers"): "create_offer",
    ("get", "/v1/offers/{offer_id}"): "get_offer",
    ("post", "/v1/orders"): "place_order",
    ("get", "/v1/orders"): "list_orders",
    ("get", "/v1/orders/{order_id}"): "get_order",
    ("get", "/v1/approvals"): "list_approvals",
    ("post", "/v1/approvals/{approval_id}/decision"): "decide_approval",
    ("get", "/v1/audit"): "get_audit",
    ("post", "/v1/requests/parse"): "parse_request",
    ("post", "/v1/requests/read-image"): "read_image",  # task T18: a multipart form, tested in test_read_image.py
    ("post", "/v1/agent/run"): "run_agent",
    ("get", "/v1/menus/recipes"): "list_recipes",  # task MENU-1
    ("post", "/v1/menus/plan"): "plan_menu",
    ("post", "/v1/standing-orders"): "create_standing_order",  # task STAND-1
    ("get", "/v1/standing-orders"): "list_standing_orders",
    ("get", "/v1/standing-orders/{standing_order_id}"): "get_standing_order",
    ("post", "/v1/standing-orders/{standing_order_id}/renew"): "renew_standing_order",
    ("get", "/v1/schemas"): "get_schemas",
    ("get", "/healthz"): "get_health",
    ("get", "/.well-known/api-catalog"): "get_api_catalog",  # P12 W2: RFC 9727
    ("head", "/.well-known/api-catalog"): "head_api_catalog",
    ("get", "/llms.txt"): "get_llms_txt",
    ("get", "/v1/customers"): "list_customers",  # task L4-2b: the customer files (review C2 F5)
    ("get", "/v1/customers/{customer_id}"): "get_customer",
    ("get", "/v1/insights"): "get_insights",  # lane BO: Valio Aimo's back office, the supplier's token only
    ("get", "/.well-known/jwks.json"): "get_signing_keys",  # P12 W8: the key offers and orders are signed with
}
PUBLIC = {"get_schemas", "get_health", "get_api_catalog", "head_api_catalog", "get_llms_txt", "get_signing_keys"}
REQUEST_MODELS: dict[str, Any] = {
    "search_products": ProductQuery,
    "find_substitutes": SubstituteQuery,
    "create_offer": PurchaseRequest,
    "plan_menu": MenuAsk,  # the typed menu request, or a sentence, or both (lane U5)
    "create_standing_order": NewStandingOrder,
    "renew_standing_order": RenewStandingOrder,
    "place_order": PlaceOrderRequest,
    "decide_approval": DecisionRequest,
    "parse_request": ParseRequestBody,
    "run_agent": ParseRequestBody,
}
RESPONSE_MODELS: dict[str, Any] = {
    "get_authority": Authority,
    "search_products": SearchResult,
    "get_product": Product,
    "find_substitutes": SubstituteResult,
    "create_offer": Offer,
    "get_offer": Offer,
    "place_order": Order,
    "list_orders": tuple[Order, ...],
    "get_order": Order,
    "list_approvals": tuple[Approval, ...],
    "decide_approval": Order,
    "get_audit": AuditPage,
    "parse_request": PurchaseRequest,
    "run_agent": AgentRun,
}


@pytest.fixture(scope="module")
def document(catalog: ProductCatalog, tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    settings = Settings.for_tests(tta_data_dir=tmp_path_factory.mktemp("openapi") / "var")
    app = create_app(settings, parts=build_parts(settings, catalog=catalog))
    with TestClient(app) as client:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        yield response.json()


def _operations(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        operation["operationId"]: operation
        for methods in document["paths"].values()
        for operation in methods.values()
    }


def _examples(media: dict[str, Any]) -> list[Any]:
    return [example["value"] for example in media.get("examples", {}).values()]


def test_the_document_is_openapi_3_1_and_says_what_the_gateway_is(document: dict[str, Any]) -> None:
    assert document["openapi"].startswith("3.1")
    assert document["info"]["title"] == "Trusted Trade Agents gateway"
    description = document["info"]["description"]
    for phrase in ("fixed prices", "human", "public by design", "illustrative", "RFC 9457", "CloudEvents"):
        assert phrase in description, phrase


def test_the_document_lists_every_route_of_the_specification(document: dict[str, Any]) -> None:
    listed = {
        (method, path): operation["operationId"]
        for path, methods in document["paths"].items()
        for method, operation in methods.items()
    }

    assert listed == ROUTES


def test_every_route_but_the_public_ones_asks_for_the_bearer_token(document: dict[str, Any]) -> None:
    scheme = document["components"]["securitySchemes"]["bearerAuth"]
    assert (scheme["type"], scheme["scheme"]) == ("http", "bearer")
    assert "public by design" in scheme["description"]

    for name, operation in _operations(document).items():
        if name in PUBLIC:
            assert "security" not in operation, name
        else:
            assert operation["security"] == [{"bearerAuth": []}], name


def test_every_route_has_a_tag_that_names_what_the_brief_asks_for(document: dict[str, Any]) -> None:
    described = {tag["name"]: tag["description"] for tag in document["tags"]}

    assert {"Core 1: lookup", "Core 2: offer and order", "Core 3: authority and approval"} <= set(described)
    assert all(described.values())
    for name, operation in _operations(document).items():
        assert len(operation["tags"]) == 1 and operation["tags"][0] in described, name
        assert operation["summary"] and operation["description"], name


def test_every_request_body_has_an_example_that_its_contract_accepts(document: dict[str, Any]) -> None:
    operations = _operations(document)

    for name, model in REQUEST_MODELS.items():
        examples = _examples(operations[name]["requestBody"]["content"]["application/json"])
        assert examples, name
        for example in examples:
            model.model_validate(example)
    with_json = {
        name for name, operation in operations.items()
        if "application/json" in operation.get("requestBody", {}).get("content", {})
    }
    assert with_json == set(REQUEST_MODELS)


def test_every_answer_has_an_example_taken_from_the_scenarios(document: dict[str, Any]) -> None:
    operations = _operations(document)

    for name, model in RESPONSE_MODELS.items():
        success = next(code for code in operations[name]["responses"] if code.startswith("2"))
        examples = _examples(operations[name]["responses"][success]["content"]["application/json"])
        assert examples, name
        adapter = TypeAdapter(model)
        for example in examples:
            adapter.validate_python(example) if not _is_model(model) else model.model_validate(example)


def _is_model(model: Any) -> bool:
    return isinstance(model, type) and issubclass(model, BaseModel)


def test_the_examples_tell_the_two_scenarios(document: dict[str, Any]) -> None:
    operations = _operations(document)
    offer = Offer.model_validate(_examples(operations["create_offer"]["responses"]["201"]["content"][
        "application/json"])[0])
    order = Order.model_validate(_examples(operations["place_order"]["responses"]["201"]["content"][
        "application/json"])[0])
    approvals = _examples(operations["list_approvals"]["responses"]["200"]["content"]["application/json"])[0]
    audit = operations["get_audit"]["responses"]["200"]["content"]["application/json"]["examples"]

    assert offer.profile_id == "allergy-ward"
    assert offer.options[0].decision is not None and offer.options[0].decision.verdict is Verdict.APPROVAL
    assert order.status.value == "PENDING_APPROVAL" and order.placed_by is None
    assert approvals and approvals[0]["profile_id"] == "hotel-kitchen"
    assert {"buyer", "supplier"} <= set(audit)
    assert audit["supplier"]["value"]["reader"] == "supplier"


def test_every_problem_a_route_can_answer_is_documented_as_problem_json(document: dict[str, Any]) -> None:
    assert document["components"]["schemas"]["ProblemDetails"]["properties"].keys() >= {"type", "title", "status"}
    for name, operation in _operations(document).items():
        problems = {code: answer for code, answer in operation["responses"].items() if code[0] in "45"}
        if name in PUBLIC:
            continue
        assert {"401", "403"} <= set(problems), name
        for code, answer in problems.items():
            media = answer["content"][PROBLEM_CONTENT_TYPE]
            assert media["schema"] == {"$ref": "#/components/schemas/ProblemDetails"}, (name, code)
            for example in _examples(media):
                assert ProblemDetails.model_validate(example).status == int(code), (name, code)
    assert "HTTPValidationError" not in document["components"]["schemas"]


def test_the_order_route_documents_its_idempotency_key(document: dict[str, Any]) -> None:
    header = next(
        parameter for parameter in _operations(document)["place_order"]["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )

    assert header["in"] == "header"
    assert header["required"] is True
    assert header["schema"]["maxLength"] == 102  # 100 characters, or the same in double quotation marks


def test_the_examples_are_built_once_at_start_up_and_off_the_event_loop(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tta.api import app as app_module

    genuine = app_module.build_examples
    builds: list[bool] = []

    def watched(parts: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            builds.append(False)  # no event loop runs in this thread: a worker thread
        else:
            builds.append(True)
        return genuine(parts)

    monkeypatch.setattr(app_module, "build_examples", watched)
    app = create_app(settings, parts=build_parts(settings, catalog=catalog))
    assert builds == []  # not while the application is put together

    with TestClient(app) as client:
        assert builds == [False]  # at start-up, before the first request
        documents = [client.get("/openapi.json") for _ in range(3)]

    assert [document.status_code for document in documents] == [200, 200, 200]
    assert builds == [False]  # a request for the document builds nothing
    examples = documents[0].json()["paths"]["/v1/offers"]["post"]["requestBody"]["content"]["application/json"]
    assert set(examples["examples"]) == {"scenario_1", "scenario_2"}
    assert "could not be built" not in documents[0].json()["info"]["description"]


def test_a_document_asked_for_without_a_running_application_still_has_its_examples(
    settings: Settings, catalog: ProductCatalog
) -> None:
    # A script that exports the document calls `app.openapi()` and never starts the application.
    parts = build_parts(settings, catalog=catalog)
    try:
        document = create_app(settings, parts=parts).openapi()
    finally:
        parts.close()

    assert document["paths"]["/v1/offers"]["post"]["responses"]["201"]["content"]["application/json"]["examples"]


def test_the_document_is_served_without_the_example_of_a_scenario_that_failed_and_says_so(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    parts = build_parts(settings, catalog=catalog)
    genuine = parts.replay.availability

    def broken_for_the_plant_drinks(product_ids: Any, *, fresh: bool = False) -> Any:
        if "464013" in product_ids:  # scenario 2 and scenario 3 look at it
            raise RuntimeError("a fault with the text do-not-show-this-to-a-reader")
        return genuine(product_ids, fresh=fresh)

    monkeypatch.setattr(parts.replay, "availability", broken_for_the_plant_drinks)

    with TestClient(create_app(settings, parts=parts)) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200  # never a 500 for the document
    document = response.json()
    offers = document["paths"]["/v1/offers"]["post"]["responses"]["201"]["content"]["application/json"]["examples"]
    assert set(offers) == {"scenario_1"}
    description = document["info"]["description"]
    assert "could not be built" in description and "scenario 2" in description.lower()
    assert "do-not-show" not in response.text


def test_the_schemas_route_returns_every_contract_model_without_a_token(client: TestClient) -> None:
    response = client.get("/v1/schemas")

    assert response.status_code == 200
    schemas = response.json()
    assert set(schemas) == set(exported_models())  # the core models, and the menu and standing-order ones
    assert set(all_models()) < set(schemas)
    assert len(schemas) >= 59
    assert schemas["Offer"]["properties"]["options"]
    assert schemas["AuditEvent"]["properties"]["specversion"]


def test_the_interactive_documentation_is_served(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200


def test_the_parse_route_says_what_the_fixed_rules_reader_answers(document: dict[str, Any]) -> None:
    # Since L1 of 14 Nov: an exclusion with no strictness is read as STRICT, and an unreadable text is 422 with
    # `question`, `not_read` and `read_by`, not `supplier-unavailable`.
    text = " ".join(_operations(document)["parse_request"]["description"].split())

    for phrase in ("`question`", "`not_read`", "`read_by`", "read as STRICT", "`invalid-request` (422)"):
        assert phrase in text, phrase
    assert "an allergen exclusion with no strictness, is reported as `invalid-request`" not in text
    assert "while no parser is running" not in text
