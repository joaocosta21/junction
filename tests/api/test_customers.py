"""The two new customers at the gateway, and the route that says who a token's customer is (task L4-2b).

Scores on the 20% "autonomy and controls" (each customer has its own agent and its own people, and nobody reads
another customer) and the 20% "solving the problem and user need" (the page and an agent read one customer file).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from tta.api.customers import SYNTHETIC_NOTE
from tta.api.identity import BEARER_DESCRIPTION, DEMO_TOKEN_NAMES, DEMO_TOKENS_PATH
from tta.contracts.common import ApproverRole
from tta.customers import shipped_customers
from tta.policy import RulePolicyEngine

Headers = dict[str, str]
AGENTS = {
    "hotel-kitchen": "demo-agent-hotel-kitchen", "allergy-ward": "demo-agent-allergy-ward",
    "school-kitchen": "demo-agent-school-kitchen", "bakery-cafe": "demo-agent-bakery-cafe",
}
# One person confirms: the school's kitchen manager also decides a spend-limit stop (no separate finance signer);
# the dietitian is the one other person, for allergen questions.
SCHOOL_PEOPLE = (
    ("demo-approver-school-purchasing", "purchasing_manager"), ("demo-approver-school-purchasing", "finance"),
    ("demo-approver-school-dietitian", "dietitian"),
)
OWNER = "demo-approver-bakery-owner"
CREAM_WITHOUT_NUTS = {
    "lines": [{
        "text": "10 litres of whipping cream, no tree nuts", "product_ids": ["469346"], "quantity": 10, "unit": "L",
        "exclude_allergens": ["AN"],
    }],
}


def _bearer(token: str, key: str | None = None) -> Headers:
    headers = {"Authorization": f"Bearer {token}"}
    return headers if key is None else {**headers, "Idempotency-Key": key}


def _demo_tokens() -> dict[str, dict[str, Any]]:
    return yaml.safe_load(DEMO_TOKENS_PATH.read_text(encoding="utf-8"))


# --- tokens ---------------------------------------------------------------------------------------------


def test_every_customer_has_an_agent_bound_to_its_own_profile(client: TestClient) -> None:
    for profile_id, token in AGENTS.items():
        authority = client.get("/v1/authority", headers=_bearer(token))

        assert authority.status_code == 200, token
        assert authority.json()["profile"]["profile_id"] == profile_id


def test_every_person_a_profile_names_has_a_demonstration_identity_with_that_role() -> None:
    identities = {entry["id"]: entry for entry in _demo_tokens().values()}
    engine = RulePolicyEngine.from_files()

    for profile_id in engine.profile_ids():
        for role, people in engine.get_profile(profile_id).approver_roles.items():
            for person in people:
                assert identities[person]["profile_id"] == profile_id, person
                assert role.value in identities[person]["roles"], (person, role)


def test_the_people_are_named_after_the_customer_files() -> None:
    tokens, customers = _demo_tokens(), shipped_customers()

    for token, entry in tokens.items():
        if entry["kind"] != "APPROVER":
            continue
        people = customers[entry["profile_id"]].people
        first_names = {people[ApproverRole(role)].split()[0] for role in entry["roles"] if ApproverRole(role) in people}
        assert any(name in entry["display_name"] for name in first_names), token


def test_the_documented_token_list_is_the_token_file() -> None:
    assert tuple(_demo_tokens()) == DEMO_TOKEN_NAMES and len(DEMO_TOKEN_NAMES) == 11
    for name in DEMO_TOKEN_NAMES:
        assert f"`{name}`" in BEARER_DESCRIPTION


def test_llms_txt_names_the_two_new_agents(client: TestClient) -> None:
    text = client.get("/llms.txt").text

    assert "`demo-agent-school-kitchen`" in text and "`demo-agent-bakery-cafe`" in text
    assert "15 identities" in text and "GET /v1/customers" in text


@pytest.mark.parametrize(("token", "role"), SCHOOL_PEOPLE)
def test_the_schools_people_read_the_schools_approval_queue(client: TestClient, token: str, role: str) -> None:
    assert client.get("/v1/approvals", headers=_bearer(token)).status_code == 200
    assert role in _demo_tokens()[token]["roles"]


# --- decision B27 ---------------------------------------------------------------------------------------


def test_the_bakery_profile_gives_the_owner_the_dietitians_role() -> None:
    roles = RulePolicyEngine.from_files().get_profile("bakery-cafe").approver_roles

    assert roles[ApproverRole.DIETITIAN] == ("human:bakery-owner",)
    assert set(_demo_tokens()[OWNER]["roles"]) == {"purchasing_manager", "finance", "dietitian"}


def test_a_bakery_order_with_an_allergen_doubt_is_completed_by_the_owner(client: TestClient) -> None:
    offer = client.post("/v1/offers", json=CREAM_WITHOUT_NUTS, headers=_bearer(AGENTS["bakery-cafe"])).json()
    option = offer["options"][0]
    assert "dietitian" in option["decision"]["required_roles"]  # no statement rules tree nuts out: P-04
    body = {"offer_id": offer["offer_id"], "option_id": option["option_id"]}
    waiting = client.post("/v1/orders", json=body, headers=_bearer(AGENTS["bakery-cafe"], "bakery-b27")).json()
    assert waiting["status"] == "PENDING_APPROVAL"

    queue = client.get("/v1/approvals", headers=_bearer(OWNER)).json()
    decided = client.post(
        f"/v1/approvals/{queue[0]['approval_id']}/decision", json={"decision": "APPROVE"}, headers=_bearer(OWNER)
    )

    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "ORDERED"
    assert "dietitian" in decided.json()["status_sentence"]


# --- GET /v1/customers ----------------------------------------------------------------------------------


@pytest.mark.parametrize("customer_id", sorted(AGENTS))
def test_an_agent_reads_its_own_customer_as_the_file_holds_it(client: TestClient, customer_id: str) -> None:
    answer = client.get(f"/v1/customers/{customer_id}", headers=_bearer(AGENTS[customer_id]))

    assert answer.status_code == 200, answer.text
    body, customer = answer.json(), shipped_customers()[customer_id]
    assert body["customer"] == customer.model_dump(mode="json")
    assert body["customer"]["synthetic"] is True and body["synthetic"] is True and body["note"] == SYNTHETIC_NOTE
    assert body["customer"]["history"] and body["customer"]["usual"] and body["customer"]["people"]
    profile = RulePolicyEngine.from_files().get_profile(customer_id)
    assert body["display_name"] == profile.display_name == customer.name
    assert body["limits"]["max_order_net_eur"] == float(profile.max_order_net_eur)
    assert body["limits"]["max_daily_net_eur"] == float(profile.max_daily_net_eur)
    assert body["limits"]["auto_order_enabled"] is False and body["limits"]["illustrative"] is True


def test_the_list_holds_the_callers_own_customer_only(client: TestClient) -> None:
    for token in (AGENTS["bakery-cafe"], OWNER):  # the agent and a person of the customer read the same
        listed = client.get("/v1/customers", headers=_bearer(token))

        assert listed.status_code == 200
        assert [view["customer"]["customer_id"] for view in listed.json()] == ["bakery-cafe"]
    bakery = client.get("/v1/customers", headers=_bearer(OWNER)).json()[0]
    assert bakery["limits"]["formula_matters"] is True and bakery["limits"]["max_order_net_eur"] == 300.0


def test_another_customers_id_answers_as_an_id_nobody_has(
    client: TestClient, assert_problem: Callable[..., dict[str, Any]]
) -> None:
    other = client.get("/v1/customers/hotel-kitchen", headers=_bearer(AGENTS["bakery-cafe"]))
    nobody = client.get("/v1/customers/no-such-customer", headers=_bearer(AGENTS["bakery-cafe"]))

    assert assert_problem(other, "not-found", 404)["detail"] == assert_problem(nobody, "not-found", 404)["detail"]
    assert "Harbourside" not in other.text


def test_the_supplier_reads_no_customer(client: TestClient, assert_problem: Callable[..., dict[str, Any]]) -> None:
    supplier = _bearer("demo-supplier-valio-aimo")

    for path in ("/v1/customers", "/v1/customers/hotel-kitchen"):
        problem = assert_problem(client.get(path, headers=supplier), "not-authorised", 403)
        assert "the buyer's own" in problem["detail"]


def test_the_route_needs_a_token_and_a_plain_id(
    client: TestClient, assert_problem: Callable[..., dict[str, Any]]
) -> None:
    assert_problem(client.get("/v1/customers"), "not-authorised", 401)
    assert_problem(client.get("/v1/customers/Hotel Kitchen", headers=_bearer(AGENTS["hotel-kitchen"])),
                   "invalid-request", 422)


def test_the_customer_is_typed_in_openapi_and_in_the_schemas(client: TestClient) -> None:
    document, schemas = client.get("/openapi.json").json(), client.get("/v1/schemas").json()

    answer = document["paths"]["/v1/customers/{customer_id}"]["get"]["responses"]["200"]
    assert answer["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/CustomerView"}
    assert {"customer", "display_name", "limits", "synthetic", "note"} <= set(schemas["CustomerView"]["properties"])
    for name in ("Customer", "CustomerLimits", "PastOrder", "UsualProduct", "CustomerStandingOrder"):
        assert schemas[name]["$schema"].endswith("2020-12/schema"), name
