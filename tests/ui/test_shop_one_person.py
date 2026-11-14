"""One person confirms: the shop's customers hold the roles so that one click is the whole confirmation, and a
second person signs only where a kitchen really has one, for what is theirs (the dietitian of the ward and the school).

Scores on the 20% "autonomy and controls" (the guardrail stays: every rule still stops the order and the log still
says who decided what and why; an agent still cannot approve) and on the 30% demo (the order ends ORDERED in one
step where one person holds every role asked). Through the shop's routes in replay, at the recording's own clock.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

import tta.api
from tta.customers import shipped_customers
from tta.policy import RulePolicyEngine

API = "/shop/api"
MONDAY = "2026-11-16"
ROLES = ("purchasing_manager", "finance", "dietitian")
ONE_PERSON = ("hotel-kitchen", "bakery-cafe")  # the person who orders holds every role
WITH_A_DIETITIAN = ("allergy-ward", "school-kitchen")  # a second person, for allergen questions only
CUSTOMER_OF = {"hotel": "hotel-kitchen", "ward": "allergy-ward", "school": "school-kitchen", "bakery": "bakery-cafe"}
# The hotel's own example of the page: Valio Aimo's data states nothing about milk for 469512.
OAT = {
    "needed_by": MONDAY,
    "lines": [{"text": "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk",
               "product_ids": ["469512"], "quantity": 100, "unit": "L", "exclude_allergens": ["AM"],
               "allergen_strictness": "STRICT"}],
}
CREAM = {
    "needed_by": MONDAY,
    "lines": [{"text": "10 litres of whipping cream", "product_type": "cream", "quantity": 10, "unit": "L"}],
}
DOUBTFUL = "469512"  # the option the dietitian is asked about (rule P-04)
DOUBTFUL_AND_UNCONFIRMED = "473609"  # asks the purchasing manager (F-01) and the dietitian (P-04)


def _call(client: TestClient, method: str, path: str, kitchen: str, **kwargs: Any) -> Any:
    return client.request(method, API + path, headers={"X-Shop-Request": "1", "X-Shop-Kitchen": kitchen}, **kwargs)


def _set_up(client: TestClient, kitchen: str, settings: dict[str, dict[str, Any]], **change: Any) -> None:
    saved = _call(client, "PUT", "/kitchen", kitchen, json={**settings[CUSTOMER_OF[kitchen]], **change})
    assert saved.status_code == 200, saved.text


def _waiting(client: TestClient, kitchen: str, request: dict[str, Any], product_id: str | None = None) -> Any:
    """The request offered and ordered as the page does it; the option of `product_id`, else the first. The approval."""
    offer = _call(client, "POST", "/offers", kitchen, json=request).json()
    option = next(
        one for one in offer["options"]
        if product_id is None or [line["product_id"] for line in one["lines"]] == [product_id]
    )
    body = {"offer_id": offer["offer_id"], "option_id": option["option_id"], "key": f"one.{kitchen}.{product_id}"}
    order = _call(client, "POST", "/orders", kitchen, json=body).json()
    assert order["status"] == "PENDING_APPROVAL", order
    waiting = _call(client, "GET", "/approvals", kitchen).json()
    return next(one for one in waiting if one["order_id"] == order["order_id"])


def _confirm(client: TestClient, kitchen: str, approval: dict[str, Any], role: str, name: str, note: str = "") -> Any:
    body = {"role": role, "name": name, "decision": {"decision": "APPROVE", "note": note or None}}
    return _call(client, "POST", f"/approvals/{approval['approval_id']}/decision", kitchen, json=body)


def _trail(client: TestClient, kitchen: str, order_id: str) -> list[str]:
    trail = _call(client, "GET", f"/audit?order_id={order_id}&reader=buyer", kitchen).json()
    assert trail["chain"]["ok"]
    return [event["sentence"] for event in trail["events"]]


# --- who holds which role -------------------------------------------------------------------------------------


@pytest.mark.parametrize("customer_id", sorted(shipped_customers()))
def test_no_customer_has_a_separate_finance_person(customer_id: str) -> None:
    customer = shipped_customers()[customer_id]

    assert customer.people["finance"] == customer.people["purchasing_manager"] == customer.contact.name


@pytest.mark.parametrize("customer_id", ONE_PERSON)
def test_the_person_who_orders_holds_every_role_at_the_hotel_and_the_bakery(customer_id: str) -> None:
    customer = shipped_customers()[customer_id]

    assert {role: customer.people[role] for role in ROLES} == dict.fromkeys(ROLES, customer.contact.name)


@pytest.mark.parametrize("customer_id", WITH_A_DIETITIAN)
def test_the_ward_and_the_school_keep_one_other_person_the_dietitian(customer_id: str) -> None:
    customer = shipped_customers()[customer_id]

    assert customer.people["dietitian"] != customer.contact.name
    assert len(set(customer.people.values())) == 2


@pytest.mark.parametrize("customer_id", sorted(shipped_customers()))
def test_the_profile_and_the_demo_identities_name_the_same_people_as_the_customer_file(customer_id: str) -> None:
    """One identity per person: who holds a role in the customer file holds it in the profile and in the token."""
    people = shipped_customers()[customer_id].people
    approvers = RulePolicyEngine.from_files().get_profile(customer_id).approver_roles
    tokens = yaml.safe_load((Path(tta.api.__file__).parent / "demo_tokens.yaml").read_text(encoding="utf-8"))
    roles_of = {
        one["id"]: sorted(one["roles"])
        for one in tokens.values() if one["kind"] == "APPROVER" and one["profile_id"] == customer_id
    }

    assert len(roles_of) == len(set(people.values()))  # as many identities as people
    by_role = {role.value: ids for role, ids in approvers.items()}
    assert all(len(ids) == 1 for ids in by_role.values()), by_role
    for one, held in roles_of.items():
        assert held == sorted(role for role, ids in by_role.items() if list(ids) == [one])
    same_person = {role: by_role[role][0] for role in ROLES}
    for first in ROLES:
        for second in ROLES:
            assert (same_person[first] == same_person[second]) == (people[first] == people[second]), (first, second)


# --- the hotel: one confirmation, whatever rule asked -------------------------------------------------------------


def test_the_hotels_allergen_question_is_decided_by_hanna_in_one_confirmation(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _set_up(client, "hotel", shop_profile_settings)
    approval = _waiting(client, "hotel", OAT, DOUBTFUL)
    assert approval["required_roles"] == ["dietitian"]

    confirmed = _confirm(client, "hotel", approval, "dietitian", "Hanna Laine", "Used anyway after checking.")

    assert confirmed.status_code == 200, confirmed.text
    order = confirmed.json()
    assert order["status"] == "ORDERED"
    assert "Hanna Laine, Harbourside Hotel" in order["status_sentence"]
    sentences = _trail(client, "hotel", order["order_id"])
    assert any("says nothing about milk" in sentence and "P-04" in sentence for sentence in sentences)  # what was asked
    assert any("Hanna Laine, Harbourside Hotel" in sentence and "dietitian" in sentence for sentence in sentences)
    assert _call(client, "GET", "/approvals", "hotel").json() == []


def test_one_confirmation_signs_every_role_hanna_holds(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    """The quantity is not confirmed (the purchasing manager's question) and milk is not ruled out (the
    dietitian's): two roles, one person, one click."""
    _set_up(client, "hotel", shop_profile_settings)
    approval = _waiting(client, "hotel", OAT, DOUBTFUL_AND_UNCONFIRMED)
    assert approval["required_roles"] == ["purchasing_manager", "dietitian"]

    confirmed = _confirm(client, "hotel", approval, "purchasing_manager", "Hanna Laine")

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "ORDERED"
    decided = _call(client, "GET", "/approvals?pending=false", "hotel").json()[0]
    assert sorted(role for decision in decided["decisions"] for role in decision["roles"]) == [
        "dietitian", "purchasing_manager",
    ]
    assert {decision["approver_name"] for decision in decided["decisions"]} == {"Hanna Laine, Harbourside Hotel"}


def test_an_order_over_the_hotels_daily_limit_is_confirmed_by_hanna_alone(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _set_up(client, "hotel", shop_profile_settings, max_daily_net_eur=10)
    approval = _waiting(client, "hotel", CREAM)
    assert "finance" in approval["required_roles"]  # the limit still stops the order
    assert any("above the €10 limit per day" in reason for reason in approval["reasons"])  # and says why

    confirmed = _confirm(client, "hotel", approval, approval["required_roles"][0], "Hanna Laine")

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "ORDERED"
    assert "Hanna Laine, Harbourside Hotel" in confirmed.json()["status_sentence"]


# --- the ward and the school: the dietitian's question waits for the dietitian --------------------------------


@pytest.mark.parametrize(
    ("kitchen", "change", "buyer", "dietitian", "customer"),
    [
        # Under the ward's own "confirmed data only", a product that says nothing about milk is not offered at all.
        ("ward", {"require_confirmed": False}, "Jussi Nieminen", "Sari Lehto", "City Hospital, Ward 4"),
        ("school", {}, "Päivi Korhonen", "Riikka Mäkelä", "Kilo School"),
    ],
)
def test_an_allergen_question_waits_for_the_dietitian_and_the_buyer_cannot_complete_it(
    kitchen: str, change: dict[str, Any], buyer: str, dietitian: str, customer: str,
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]],
) -> None:
    _set_up(client, kitchen, shop_profile_settings, **change)
    approval = _waiting(client, kitchen, OAT, DOUBTFUL)
    assert approval["required_roles"] == ["dietitian"]

    as_dietitian = _confirm(client, kitchen, approval, "dietitian", buyer)
    own_role = _confirm(client, kitchen, approval, "purchasing_manager", buyer)

    assert as_dietitian.status_code == 422 and dietitian in as_dietitian.json()["detail"]
    assert own_role.status_code == 403, own_role.text
    still = _call(client, "GET", "/approvals", kitchen).json()
    assert [one["approval_id"] for one in still] == [approval["approval_id"]] and still[0]["decisions"] == []

    decided = _confirm(client, kitchen, approval, "dietitian", dietitian)
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "ORDERED"
    assert f"{dietitian}, {customer}" in decided.json()["status_sentence"]


def test_the_buyers_confirmation_signs_their_part_and_the_order_waits_for_the_dietitian(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _set_up(client, "school", shop_profile_settings)
    approval = _waiting(client, "school", OAT, DOUBTFUL_AND_UNCONFIRMED)
    assert approval["required_roles"] == ["purchasing_manager", "dietitian"]

    sent = _confirm(client, "school", approval, "purchasing_manager", "Päivi Korhonen")

    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "PENDING_APPROVAL"
    waiting = _call(client, "GET", "/approvals", "school").json()[0]
    assert [decision["roles"] for decision in waiting["decisions"]] == [["purchasing_manager"]]


@pytest.mark.parametrize(("kitchen", "buyer"), [("ward", "Jussi Nieminen"), ("school", "Päivi Korhonen")])
def test_a_daily_limit_is_decided_by_the_person_who_orders_also_where_there_is_a_dietitian(
    kitchen: str, buyer: str, client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _set_up(client, kitchen, shop_profile_settings, max_daily_net_eur=10, excluded_allergens=[],
            allergen_strictness=None, allergen_strictness_by_code={}, require_confirmed=False)
    approval = _waiting(client, kitchen, CREAM)
    assert "finance" in approval["required_roles"] and "dietitian" not in approval["required_roles"]

    confirmed = _confirm(client, kitchen, approval, approval["required_roles"][0], buyer)

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "ORDERED"


# --- the bakery: unchanged (decision B27) ------------------------------------------------------------------------


def test_the_bakerys_owner_still_confirms_alone(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _set_up(client, "bakery", shop_profile_settings)
    approval = _waiting(client, "bakery", OAT, DOUBTFUL)
    assert approval["required_roles"] == ["dietitian"]

    confirmed = _confirm(client, "bakery", approval, "dietitian", "Marko Heikkinen")

    assert confirmed.json()["status"] == "ORDERED"
    assert "Marko Heikkinen, Kallio Bakery" in confirmed.json()["status_sentence"]


def test_a_rejection_is_one_decision_and_nothing_is_ordered(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    _set_up(client, "hotel", shop_profile_settings)
    approval = _waiting(client, "hotel", OAT, DOUBTFUL_AND_UNCONFIRMED)
    body = {"role": "dietitian", "name": "Hanna Laine", "decision": {"decision": "REJECT", "note": "Left out."}}

    rejected = _call(client, "POST", f"/approvals/{approval['approval_id']}/decision", "hotel", json=body)

    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "REJECTED"
    assert len(_call(client, "GET", "/approvals?pending=false", "hotel").json()[0]["decisions"]) == 1


# --- the page: the question comes to the person, and nothing else about roles is shown --------------------------

SHOP_JS = Path(tta.api.__file__).parent.parent / "ui" / "static" / "shop" / "js"


def _read(name: str) -> str:
    return (SHOP_JS / name).read_text(encoding="utf-8")


def test_the_request_page_asks_the_persons_own_question_and_sends_another_persons_by_name() -> None:
    assistant, question = _read("views/assistant.js"), _read("views/question.js")

    for words in ("Needs your decision", "This needs ${andList(others.map(personWords))}", "Send to ${names}"):
        assert words in assistant, words
    for choice in ("Take the safe product", "Use it anyway", "Leave it out"):
        assert question.count(choice) >= 2, choice  # on the result (ownQuestion) and on the other person's card
    assert "ownQuestion(turn, option, off)" in assistant
    # No role is shown as a label on the request page: the person signed in is "you", anybody else is named.
    assert "ROLES" not in assistant and "roleName" not in assistant


def test_the_waiting_page_lists_what_waits_for_someone_else_with_one_demonstration_control() -> None:
    page, frame = _read("views/approvals.js"), _read("main.js")

    assert "<h1>Waiting for someone else</h1>" in page and "Who signs what" not in page
    assert page.count('data-act="act-as"') == 1
    assert "Decide as ${other.name}, ${roleOf(other)} (demonstration)" in page
    assert "Approve as" not in page and "ROLES" not in page
    # The menu entry: its count, and no entry at all when nothing waits.
    assert '["approvals", "#/approvals", "Waiting for someone else"]' in frame
    assert "approvals.waitingCount()" in frame and '? "" // nothing waits for anybody' in frame


def test_the_page_signs_once_and_the_gateway_signs_every_role_the_person_holds() -> None:
    signing = _read("views/assistant.js").split("async function signMine", 1)[1].split("async function place", 1)[0]

    assert signing.count("api().decide(") == 1 and "for (" not in signing
