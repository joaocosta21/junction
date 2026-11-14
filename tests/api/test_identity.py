"""Who is calling: bearer tokens, the three kinds of identity, and what each may not do (SPEC section 2).

Scores on the 20% "what the agent can decide alone, what needs human sign-off".
"""

from __future__ import annotations

import hmac
import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.identity import TokenRegistry, load_tokens
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import Identity, IdentityKind

Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]
Problem = Callable[..., dict[str, Any]]

PUBLIC_PATHS = {"/v1/schemas"}
PROFILE_IDS = ("allergy-ward", "hotel-kitchen")
ENV_TOKEN = "an-environment-token-of-forty-characters"
ENV_TOKENS = json.dumps({
    ENV_TOKEN: {
        "kind": "AGENT", "id": "agent:canteen", "display_name": "Canteen agent", "profile_id": "hotel-kitchen",
    },
})


def _protected_routes(client: TestClient) -> list[tuple[str, str]]:
    """Every method and path under /v1 that the published interface lists, with a value in each placeholder."""
    paths = client.get("/openapi.json").json()["paths"]
    return [
        (method.upper(), path.replace("{product_id}", "464013").replace("{", "").replace("}", ""))
        for path, methods in paths.items()
        if path.startswith("/v1/") and path not in PUBLIC_PATHS
        for method in methods
    ]


def test_every_route_under_v1_but_the_schemas_refuses_a_call_without_a_token(
    client: TestClient, assert_problem: Problem
) -> None:
    routes = _protected_routes(client)

    assert len(routes) >= 14
    for method, path in routes:
        response = client.request(method, path)
        body = assert_problem(response, "not-authorised", 401)
        assert response.headers["www-authenticate"] == "Bearer", (method, path)
        assert body["title"] == "Authentication is required"


@pytest.mark.parametrize("header", ["Bearer not-a-token-anyone-issued", "Basic ZGVtbzpkZW1v", "Bearer", ""])
def test_a_token_nobody_issued_is_refused_and_never_repeated(
    client: TestClient, assert_problem: Problem, header: str
) -> None:
    response = client.get("/v1/authority", headers={"Authorization": header})

    assert_problem(response, "not-authorised", 401)
    assert "not-a-token-anyone-issued" not in response.text


def test_an_agent_token_on_the_approval_routes_is_refused_and_the_attempt_is_recorded(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow, place_order: Flow,
    assert_problem: Problem,
) -> None:
    order = place_order(client, "agent_hotel", make_offer(client, "agent_hotel", scenario_1), "key-1")

    listed = client.get("/v1/approvals", headers=auth("agent_hotel"))
    decided = client.post(
        f"/v1/approvals/{order['approval_id']}/decision", json={"decision": "APPROVE"}, headers=auth("agent_hotel")
    )

    assert_problem(listed, "not-authorised", 403)
    assert "F-06" in assert_problem(decided, "not-authorised", 403)["detail"]
    assert client.get(f"/v1/orders/{order['order_id']}", headers=auth("agent_hotel")).json()["status"] == (
        "PENDING_APPROVAL"
    )
    view = client.get("/v1/audit", params={"order_id": order["order_id"]}, headers=auth("agent_hotel")).json()
    refused = [event for event in view["events"] if event["type"] == "tta.v1.authorisation.refused"]
    assert len(refused) == 1
    assert refused[0]["rule_ids"] == ["F-06"]


def test_an_approver_token_can_neither_ask_for_an_offer_nor_place_an_order(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow, assert_problem: Problem
) -> None:
    offer = make_offer(client, "agent_hotel", scenario_1)
    body = {"offer_id": offer["offer_id"], "option_id": "opt_1"}

    asked = client.post("/v1/offers", json=scenario_1, headers=auth("hotel_purchasing"))
    placed = client.post("/v1/orders", json=body, headers=auth("hotel_purchasing", "key-1"))

    assert_problem(asked, "not-authorised", 403)
    assert_problem(placed, "not-authorised", 403)
    assert client.get("/v1/orders", headers=auth("agent_hotel")).json() == []


def test_an_approver_reads_the_offer_it_is_asked_to_decide_on(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow
) -> None:
    offer = make_offer(client, "agent_hotel", scenario_1)

    response = client.get(f"/v1/offers/{offer['offer_id']}", headers=auth("hotel_purchasing"))

    assert response.status_code == 200
    assert response.json()["offer_id"] == offer["offer_id"]


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/v1/authority", None),
        ("POST", "/v1/products/search", {"product_type": "milk"}),
        ("GET", "/v1/products/464013", None),
        ("POST", "/v1/products/473609/substitutes", {}),
        ("POST", "/v1/offers", "scenario"),
        ("GET", "/v1/offers/off_any", None),
        ("POST", "/v1/orders", {"offer_id": "off_any", "option_id": "opt_1"}),
        ("GET", "/v1/orders", None),
        ("GET", "/v1/orders/ord_any", None),
        ("GET", "/v1/approvals", None),
        ("POST", "/v1/approvals/apr_any/decision", {"decision": "REJECT"}),
        ("POST", "/v1/requests/parse", {"text": "milk"}),
        ("POST", "/v1/agent/run", {"text": "milk"}),
    ],
)
def test_the_supplier_token_opens_nothing_but_the_audit_trail(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], assert_problem: Problem, method: str, path: str,
    body: Any,
) -> None:
    sent = scenario_1 if body == "scenario" else body

    response = client.request(method, path, json=sent, headers=auth("supplier", "key-1"))

    assert_problem(response, "not-authorised", 403)


def test_an_agent_cannot_name_another_profile_in_a_body(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any], assert_problem: Problem
) -> None:
    named = {**scenario_2, "profile_id": "hotel-kitchen"}

    offer = client.post("/v1/offers", json=named, headers=auth("agent_ward"))
    order = client.post(
        "/v1/orders", json={"offer_id": "off_1", "option_id": "opt_1", "profile_id": "hotel-kitchen"},
        headers=auth("agent_ward", "key-1"),
    )

    assert_problem(offer, "invalid-request", 422)
    assert_problem(order, "invalid-request", 422)


def test_a_profile_named_in_the_query_changes_nothing(client: TestClient, auth: Auth) -> None:
    response = client.get("/v1/authority", params={"profile_id": "hotel-kitchen"}, headers=auth("agent_ward"))

    assert response.json()["profile"]["profile_id"] == "allergy-ward"


def _property_names(schema: Any, document: dict[str, Any], seen: set[str]) -> set[str]:
    """Every property name of a JSON Schema, following its references."""
    if isinstance(schema, list):
        return set().union(*(_property_names(item, document, seen) for item in schema))
    if not isinstance(schema, dict):
        return set()
    reference = schema.get("$ref")
    if isinstance(reference, str):
        if reference in seen:
            return set()
        seen.add(reference)
        return _property_names(document["components"]["schemas"][reference.rsplit("/", 1)[-1]], document, seen)
    names = set(schema.get("properties", {}))
    return names.union(*(_property_names(value, document, seen) for value in schema.values()))


def test_no_route_accepts_a_profile_id_as_a_parameter_or_in_its_request_body(client: TestClient) -> None:
    document = client.get("/openapi.json").json()
    operations = [
        operation
        for path, methods in document["paths"].items() if path.startswith("/v1/")
        for operation in methods.values()
    ]

    assert len(operations) >= 14
    for operation in operations:
        parameters = {parameter["name"] for parameter in operation.get("parameters", [])}
        content = operation.get("requestBody", {}).get("content", {})
        fields = set().union(*(_property_names(media.get("schema"), document, set()) for media in content.values()))
        assert not {name for name in parameters | fields if "profile" in name.lower()}, operation["operationId"]


def test_an_agent_cannot_reach_another_buyers_offer_or_order(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow, place_order: Flow,
    assert_problem: Problem,
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)
    order = place_order(client, "agent_ward", offer, "key-1")
    body = {"offer_id": offer["offer_id"], "option_id": "opt_1"}

    # Another buyer's id answers as an id nobody issued: the two cannot be told apart.
    unknown = assert_problem(client.get("/v1/offers/off_nobody", headers=auth("agent_hotel")), "not-found", 404)
    read = assert_problem(
        client.get(f"/v1/offers/{offer['offer_id']}", headers=auth("agent_hotel")), "not-found", 404
    )
    assert read == unknown
    assert_problem(client.get(f"/v1/orders/{order['order_id']}", headers=auth("agent_hotel")), "not-found", 404)
    assert_problem(client.post("/v1/orders", json=body, headers=auth("agent_hotel", "key-2")), "not-found", 404)
    assert_problem(
        client.get("/v1/audit", params={"order_id": order["order_id"]}, headers=auth("agent_hotel")),
        "not-found", 404,
    )
    assert client.get("/v1/orders", headers=auth("agent_hotel")).json() == []


# --- where the tokens come from -----------------------------------------------------------------------


def test_demo_tokens_are_loaded_in_dev_and_demo_only(catalog: ProductCatalog, settings: Settings) -> None:
    for environment in ("dev", "demo"):
        registry = load_tokens(Settings.for_tests(tta_env=environment), PROFILE_IDS)
        kinds = [identity.kind for identity in registry.identities]
        assert kinds.count(IdentityKind.AGENT) == 2
        assert kinds.count(IdentityKind.APPROVER) == 6
        assert kinds.count(IdentityKind.SUPPLIER) == 1

    production = load_tokens(Settings.for_tests(tta_env="prod", tta_tokens=ENV_TOKENS), PROFILE_IDS)
    assert [identity.id for identity in production.identities] == ["agent:canteen"]
    assert production.identify("demo-agent-hotel-kitchen") is None


def test_outside_dev_and_demo_the_tokens_come_from_the_environment(
    tmp_path: Any, catalog: ProductCatalog, tokens: dict[str, str]
) -> None:
    settings = Settings.for_tests(tta_env="prod", tta_tokens=ENV_TOKENS, tta_data_dir=tmp_path / "var")
    app = create_app(settings, parts=build_parts(settings, catalog=catalog))

    with TestClient(app) as client:
        demo = client.get("/v1/authority", headers={"Authorization": f"Bearer {tokens['agent_hotel']}"})
        issued = client.get("/v1/authority", headers={"Authorization": f"Bearer {ENV_TOKEN}"})

    assert demo.status_code == 401
    assert issued.status_code == 200
    assert issued.json()["profile"]["profile_id"] == "hotel-kitchen"


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "not json at all, with a-secret-looking-value",
        json.dumps(["a-secret-looking-value"]),
        json.dumps({}),
        json.dumps({"": {"kind": "SUPPLIER", "id": "s", "display_name": "S"}}),
        json.dumps({"a-secret-looking-value": {"kind": "AGENT", "id": "agent:x", "display_name": "X"}}),
        json.dumps({"a-secret-looking-value": {
            "kind": "AGENT", "id": "agent:x", "display_name": "X", "profile_id": "no-such-profile",
        }}),
    ],
)
def test_outside_dev_and_demo_the_app_refuses_to_start_without_usable_tokens(
    tmp_path: Any, catalog: ProductCatalog, value: str | None
) -> None:
    settings = Settings.for_tests(tta_env="prod", tta_tokens=value, tta_data_dir=tmp_path / "var")

    with pytest.raises(RuntimeError) as refused:
        build_parts(settings, catalog=catalog)

    assert "TTA_TOKENS" in str(refused.value)
    assert "a-secret-looking-value" not in str(refused.value)


def _identity(identity_id: str) -> dict[str, str]:
    return {"kind": "SUPPLIER", "id": identity_id, "display_name": "A reader"}


def _refused(value: str) -> str:
    with pytest.raises(RuntimeError) as refused:
        load_tokens(Settings.for_tests(tta_env="prod", tta_tokens=value), PROFILE_IDS)
    return str(refused.value)


def test_a_token_from_the_environment_shorter_than_24_characters_stops_the_start() -> None:
    short, long_enough = "only-23-characters-long", "this-one-has-24-letters!"
    assert (len(short), len(long_enough)) == (23, 24)

    message = _refused(json.dumps({ENV_TOKEN: _identity("supplier:a"), short: _identity("supplier:b")}))

    assert "entry 2" in message and "24" in message
    assert short not in message and ENV_TOKEN not in message
    accepted = load_tokens(
        Settings.for_tests(tta_env="prod", tta_tokens=json.dumps({long_enough: _identity("supplier:a")})), PROFILE_IDS
    )
    assert accepted.identify(long_enough) is not None


def test_a_token_mapped_twice_stops_the_start_and_only_positions_are_named() -> None:
    # A JSON object may repeat a key; the parser would silently keep the last one.
    first, other, again = (json.dumps(_identity(f"supplier:{name}")) for name in ("a", "b", "c"))
    text = f'{{"{ENV_TOKEN}": {first}, "another-token-from-the-environment": {other}, "{ENV_TOKEN}": {again}}}'

    message = _refused(text)

    assert "entries 1 and 3" in message and "same token" in message
    assert ENV_TOKEN not in message and "another-token" not in message


def test_two_tokens_with_the_same_identity_id_stop_the_start() -> None:
    tokens = {
        ENV_TOKEN: _identity("supplier:a"),
        "another-token-from-the-environment": _identity("supplier:b"),
        "a-third-token-from-the-environment": _identity("supplier:a"),
    }

    message = _refused(json.dumps(tokens))

    assert "entries 1 and 3" in message and "same identity id" in message
    assert all(token not in message for token in tokens)


def test_an_identity_that_repeats_a_field_stops_the_start() -> None:
    text = f'{{"{ENV_TOKEN}": {{"kind": "SUPPLIER", "id": "supplier:a", "id": "supplier:b", "display_name": "X"}}}}'

    message = _refused(text)

    assert "entry 1" in message
    assert ENV_TOKEN not in message


def test_the_demonstration_tokens_are_not_held_to_the_length_of_a_secret() -> None:
    registry = load_tokens(Settings.for_tests(tta_env="demo"), PROFILE_IDS)

    assert registry.identify("demo-agent-allergy-ward") is not None  # 23 characters, and public by design


def test_every_known_token_is_compared_in_constant_time(monkeypatch: pytest.MonkeyPatch) -> None:
    supplier = Identity(kind=IdentityKind.SUPPLIER, id="supplier:one", display_name="One")
    other = Identity(kind=IdentityKind.SUPPLIER, id="supplier:two", display_name="Two")
    registry = TokenRegistry({"first-token": supplier, "second-token": other})
    compared: list[int] = []
    genuine = hmac.compare_digest

    def counting(left: bytes, right: bytes) -> bool:
        compared.append(len(left))
        return genuine(left, right)

    monkeypatch.setattr("tta.api.identity.hmac.compare_digest", counting)

    assert registry.identify("first-token") == supplier
    assert registry.identify("first-toke") is None
    assert registry.identify("") is None
    # No early exit: both tokens are compared on every call, hit or miss, on digests of one length.
    assert len(compared) == 6
    assert len(set(compared)) == 1
