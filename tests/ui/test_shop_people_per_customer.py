"""A shop book reads as its customer's people (lane FIX-A1, item 17; decisions B54, B61 and B66).

A book of the shop listed one approver per role, so on the page the hotel read as three people: "the dietitian" for
an allergen doubt, a role in brackets after the name. Under each role a book now lists the approver that stands for
the customer's person who holds it: one for the hotel and the bakery; at the ward and the school the person who
orders and the dietitian. Through the shop's routes in replay, at the recording's own clock.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/shop/api"
MONDAY = "2026-11-16"
CUSTOMER_OF = {"hotel": "hotel-kitchen", "school": "school-kitchen"}
OAT_WITHOUT_MILK = {
    "needed_by": MONDAY,
    "lines": [{"text": "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk",
               "product_ids": ["469512"], "quantity": 100, "unit": "L", "exclude_allergens": ["AM"],
               "allergen_strictness": "STRICT"}],
}
ALMOND_DRINK = {
    "needed_by": MONDAY,
    "lines": [{"text": "20 litres of almond drink 465793 by Monday", "product_ids": ["465793"], "quantity": 20,
               "unit": "L"}],
}
OAT, ALMOND, RICE = "469512", "465793", "473424"


def _call(client: TestClient, method: str, path: str, kitchen: str, **kwargs: Any) -> Any:
    return client.request(method, API + path, headers={"X-Shop-Request": "1", "X-Shop-Kitchen": kitchen}, **kwargs)


def _waiting(client: TestClient, kitchen: str, request: dict[str, Any], product_id: str) -> tuple[Any, Any]:
    """The option that holds `product_id` alone, ordered as the page does it: the order and its approval."""
    offer = _call(client, "POST", "/offers", kitchen, json=request).json()
    option = next(one for one in offer["options"] if [line["product_id"] for line in one["lines"]] == [product_id])
    body = {"offer_id": offer["offer_id"], "option_id": option["option_id"], "key": f"people.{kitchen}.{product_id}"}
    order = _call(client, "POST", "/orders", kitchen, json=body).json()
    assert order["status"] == "PENDING_APPROVAL", order
    approval = next(one for one in _call(client, "GET", "/approvals", kitchen).json()
                    if one["order_id"] == order["order_id"])
    return order, approval


def _decide(client: TestClient, kitchen: str, approval: dict[str, Any], role: str, name: str) -> Any:
    body = {"role": role, "name": name, "decision": {"decision": "APPROVE", "note": None}}
    return _call(client, "POST", f"/approvals/{approval['approval_id']}/decision", kitchen, json=body)


def _log(client: TestClient, kitchen: str, order_id: str, reader: str) -> str:
    trail = _call(client, "GET", f"/audit?order_id={order_id}&reader={reader}", kitchen).json()
    assert trail["chain"]["ok"]
    return " ".join(event["sentence"] for event in trail["events"])


def test_at_the_hotel_an_allergen_doubt_is_one_persons_question_and_nobody_reads_a_dietitian(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    assert _call(client, "PUT", "/kitchen", "hotel", json=shop_profile_settings["hotel-kitchen"]).status_code == 200

    order, approval = _waiting(client, "hotel", OAT_WITHOUT_MILK, OAT)
    confirmed = _decide(client, "hotel", approval, approval["required_roles"][0], "Hanna Laine")

    assert "needs the purchasing manager" in order["decision"]["sentence"]
    assert "dietitian" not in order["decision"]["sentence"] and "dietitian" not in order["status_sentence"]
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "ORDERED"  # one confirmation, one person
    said = confirmed.json()["status_sentence"]
    assert "Hanna Laine" in said and "(" not in said.split("Hanna Laine")[1][:3]  # the name, no role in brackets
    for_the_buyer = _log(client, "hotel", order["order_id"], "buyer")
    assert "was sent to the purchasing manager" in for_the_buyer
    assert "Hanna Laine, Harbourside Hotel approved order" in for_the_buyer
    assert "dietitian" not in for_the_buyer and "Harbourside Hotel (" not in for_the_buyer
    for_valio = _log(client, "hotel", order["order_id"], "supplier")
    assert "A person of the buyer approved order" in for_valio and "was sent to a person of the buyer" in for_valio
    assert "dietitian" not in for_valio and "Hanna" not in for_valio


def test_at_the_school_the_almond_drink_and_a_substitute_of_another_formula_wait_for_the_dietitian(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    assert _call(client, "PUT", "/kitchen", "school", json=shop_profile_settings["school-kitchen"]).status_code == 200

    almond, asked_of_her = _waiting(client, "school", ALMOND_DRINK, ALMOND)
    rice, asked_of_both = _waiting(client, "school", ALMOND_DRINK, RICE)

    assert asked_of_her["required_roles"] == ["dietitian"]
    assert "It needs the dietitian" in almond["decision"]["sentence"]
    # The rice drink would replace the almond drink and is another formula (rule F-12): hers to decide as well.
    assert set(asked_of_both["required_roles"]) == {"purchasing_manager", "dietitian"}
    assert "is not a like-for-like replacement" in rice["decision"]["sentence"]

    # The person who orders cannot answer for her: her own signature leaves the dietitian's part open.
    by_the_buyer = _decide(client, "school", asked_of_both, "purchasing_manager", "Päivi Korhonen")
    assert by_the_buyer.status_code == 200 and by_the_buyer.json()["status"] == "PENDING_APPROVAL"
    as_her_under_the_buyers_name = _decide(client, "school", asked_of_both, "dietitian", "Päivi Korhonen")
    assert as_her_under_the_buyers_name.status_code == 422
    by_her = _decide(client, "school", asked_of_both, "dietitian", "Riikka Mäkelä")
    assert by_her.status_code == 200 and by_her.json()["status"] == "ORDERED"

    for_the_buyer = _log(client, "school", rice["order_id"], "buyer")
    assert "Riikka Mäkelä, Kilo School (dietitian) approved order" in for_the_buyer
    for_valio = _log(client, "school", rice["order_id"], "supplier")
    assert "The buyer's dietitian approved order" in for_valio and "A person of the buyer approved order" in for_valio
    assert "Riikka" not in for_valio and "Päivi" not in for_valio
