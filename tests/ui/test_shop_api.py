"""The shop's JSON routes (`/shop/api`): each kitchen of the shop on its own demo book, under the same rules.

Scores on the 30% demo (the shop runs request -> offer -> order -> approval -> audit through these routes) and
the 20% "autonomy and controls" (a kitchen's limits set in the shop are the ones the policy engine applies, the
agent still cannot approve, and the audit trail names the person who signed).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import tta.ui
from tta.contracts.errors import InvalidRequest
from tta.ui.shop_api import SHOP_KITCHENS

API = "/shop/api"
CREAM = {  # 10 L of whipping cream by Monday: some €30-60 in the recordings
    "needed_by": "2026-11-16",
    "lines": [{"text": "10 litres of whipping cream", "product_type": "cream", "quantity": 10, "unit": "L"}],
}
BAKERY = {
    "display_name": "Kallio Bakery",
    "auto_order_enabled": False,
    "max_order_net_eur": 300,
    "max_daily_net_eur": 1000,
    "min_fill_ratio": 1,
    "excluded_allergens": [],
    "allergen_strictness": "DECLARED_ONLY",
    "substitution_without_approval": "SAME_CATEGORY",
    "variable_weight": "APPROVAL",
    "deposits": "APPROVAL",
    "require_confirmed": False,
    "standing_order_drift_ratio": 0.15,
}

MONDAY = "2026-11-16"
KITCHENS_JS = Path(tta.ui.__file__).parent / "static" / "shop" / "js" / "kitchens.js"
# What the shop page sends for each of its four customers: the `PROFILE_SETTINGS` block of kitchens.js, which
# equals the profile files (tests/ui/test_shop_customers.py). Copied here by hand, so a change to the page shows up
# as a moved pin: `test_the_settings_copied_here_are_those_the_page_sends` holds the two together.
_BASE = {"auto_order_enabled": False, "variable_weight": "APPROVAL", "deposits": "APPROVAL",
         "standing_order_drift_ratio": 0.25, "formula_matters": False, "formula_mode": "LEARN",
         "max_preference_premium_ratio": None}
SHOP_CUSTOMERS: dict[str, dict[str, Any]] = {
    "school": {
        **_BASE, "display_name": "Kilo School", "max_order_net_eur": 250, "max_daily_net_eur": 800,
        "min_fill_ratio": 1, "excluded_allergens": ["AN", "AP", "AS"], "allergen_strictness": "STRICT",
        "allergen_strictness_by_code": {"AN": "STRICT", "AP": "STRICT", "AS": "STRICT"},
        "substitution_without_approval": "LISTED_BY_SUPPLIER", "require_confirmed": False,
    },
    "ward": {
        **_BASE, "display_name": "City Hospital, Ward 4", "max_order_net_eur": 500, "max_daily_net_eur": 1500,
        "min_fill_ratio": 1, "excluded_allergens": ["AM", "AW"], "allergen_strictness": "STRICT",
        "allergen_strictness_by_code": {"AM": "STRICT", "AW": "STRICT"},
        "substitution_without_approval": "NONE", "require_confirmed": True,
        "standing_order_drift_ratio": 0.1, "max_preference_premium_ratio": 0.1,
    },
    "hotel": {
        **_BASE, "display_name": "Harbourside Hotel", "max_order_net_eur": 750, "max_daily_net_eur": 3000,
        "min_fill_ratio": 0.9, "excluded_allergens": [], "allergen_strictness": None,
        "allergen_strictness_by_code": {}, "substitution_without_approval": "SAME_CATEGORY",
        "require_confirmed": False,
    },
    "bakery": {
        **_BASE, "display_name": "Kallio Bakery", "max_order_net_eur": 300, "max_daily_net_eur": 1000,
        "min_fill_ratio": 1, "excluded_allergens": [], "allergen_strictness": None,
        "allergen_strictness_by_code": {}, "substitution_without_approval": "NONE",
        "require_confirmed": False, "formula_matters": True, "formula_mode": "ALWAYS",
        "max_preference_premium_ratio": 0.1,
    },
}
# One of each customer's own example buttons: an order inside that customer's limits, with every statement
# confirmed in the recording (measured at the recording's own clock, Saturday 14 Nov 2026 02:52).
SHOP_EXAMPLES: dict[str, dict[str, Any]] = {
    "school": {"text": "40 litres of lactose-free milk by Monday", "product_type": "milk",
               "required_claims": ["FREE_FROM_LACTOSE"], "quantity": 40, "unit": "L"},
    "ward": {"text": "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only",
             "product_type": "plant_drink", "quantity": 200, "unit": "L", "exclude_allergens": ["AM", "AW"]},
    "hotel": {"text": "30 litres of cream by Monday", "product_type": "cream", "quantity": 30, "unit": "L"},
    "bakery": {"text": "10 litres of milk by Monday", "product_type": "milk", "quantity": 10, "unit": "L"},
}


def _headers(kitchen: str = "bakery") -> dict[str, str]:
    return {"X-Shop-Request": "1", "X-Shop-Kitchen": kitchen}


def _call(client: TestClient, method: str, path: str, kitchen: str = "bakery", **kwargs: Any) -> Any:
    return client.request(method, API + path, headers=_headers(kitchen), **kwargs)


def _set_up(client: TestClient, kitchen: str = "bakery", **change: Any) -> Any:
    return _call(client, "PUT", "/kitchen", kitchen, json={**BAKERY, **change})


def test_the_shop_page_is_served(client: TestClient) -> None:
    answer = client.get("/shop")
    assert answer.status_code == 200
    assert "/static/shop/js/main.js" in answer.text


def test_a_call_without_the_shop_header_is_refused(client: TestClient) -> None:
    answer = client.get(API + "/kitchen", headers={"X-Shop-Kitchen": "bakery"})
    assert answer.status_code == 403
    assert answer.headers["content-type"].startswith("application/problem+json")


def test_a_cross_site_call_is_refused(client: TestClient) -> None:
    answer = client.get(API + "/kitchen", headers={**_headers(), "Sec-Fetch-Site": "cross-site"})
    assert answer.status_code == 403


def test_a_call_must_name_a_well_formed_kitchen(client: TestClient) -> None:
    for kitchen in ("", "Bakery", "../x", "a" * 30):
        answer = client.get(API + "/kitchen", headers={"X-Shop-Request": "1", "X-Shop-Kitchen": kitchen})
        assert answer.status_code == 400, kitchen


def test_kitchen_settings_are_checked_like_a_profile_file(client: TestClient) -> None:
    assert _set_up(client).status_code == 200
    refused = _set_up(client, max_order_net_eur=-5)
    assert refused.status_code == 422
    fixed = _set_up(client, profile_id="someone-else")  # set by the gateway, never by the page
    assert fixed.status_code == 422


def test_the_kitchen_limit_decides_the_verdict(client: TestClient) -> None:
    _set_up(client, max_order_net_eur=10)
    offer = _call(client, "POST", "/offers", json=CREAM).json()
    first = offer["options"][0]
    assert first["totals"]["net"] > 10
    assert "P-01" in [rule["rule_id"] for rule in first["decision"]["fired"]]

    _set_up(client, max_order_net_eur=100)
    again = _call(client, "POST", "/offers", json=CREAM).json()["options"][0]
    assert "P-01" not in [rule["rule_id"] for rule in again["decision"]["fired"]]


def test_each_kitchen_has_a_book_of_its_own(client: TestClient) -> None:
    _set_up(client, "bakery", max_order_net_eur=100)
    _set_up(client, "school", max_order_net_eur=50)
    offer = _call(client, "POST", "/offers", "bakery", json=CREAM).json()
    first = offer["options"][0]
    order = _call(
        client,
        "POST",
        "/orders",
        "bakery",
        json={
            "offer_id": offer["offer_id"],
            "option_id": first["option_id"],
            "key": "test.bakery.1",
        },
    ).json()
    assert order["status"] == "PENDING_APPROVAL"  # every order needs a person (F-10), inside the limit too
    assert [o["order_id"] for o in _call(client, "GET", "/orders", "bakery").json()] == [order["order_id"]]
    assert _call(client, "GET", "/orders", "school").json() == []


def test_an_approval_signed_in_the_shop_names_the_person_in_the_trail(client: TestClient) -> None:
    _set_up(client, max_order_net_eur=10)
    offer = _call(client, "POST", "/offers", json=CREAM).json()
    first = offer["options"][0]
    order = _call(
        client,
        "POST",
        "/orders",
        json={
            "offer_id": offer["offer_id"],
            "option_id": first["option_id"],
            "key": "test.bakery.2",
        },
    ).json()
    assert order["status"] == "PENDING_APPROVAL"
    approvals = _call(client, "GET", "/approvals").json()
    assert [a["order_id"] for a in approvals] == [order["order_id"]]

    decided = _call(
        client,
        "POST",
        f"/approvals/{approvals[0]['approval_id']}/decision",
        json={
            "role": "purchasing_manager",
            "name": "Marko Heikkinen, Kallio Bakery",
            "decision": {"decision": "APPROVE", "note": "Fine for Monday"},
        },
    ).json()
    assert decided["status"] == "ORDERED"
    assert "Marko Heikkinen, Kallio Bakery" in decided["status_sentence"]

    buyer = _call(client, "GET", f"/audit?order_id={order['order_id']}&reader=buyer").json()
    supplier = _call(client, "GET", f"/audit?order_id={order['order_id']}&reader=supplier").json()
    assert buyer["chain"]["ok"] and supplier["chain"]["ok"]
    assert any("Marko Heikkinen" in event["sentence"] for event in buyer["events"])
    assert not any("Marko Heikkinen" in event["sentence"] for event in supplier["events"])


def test_a_signer_name_with_markup_is_refused(client: TestClient) -> None:
    answer = _call(
        client,
        "POST",
        "/approvals/apr_x/decision",
        json={
            "role": "purchasing_manager",
            "name": "<script>",
            "decision": {"decision": "APPROVE"},
        },
    )
    assert answer.status_code == 422


def test_starting_again_empties_only_that_kitchen(client: TestClient) -> None:
    _set_up(client, max_order_net_eur=100)
    offer = _call(client, "POST", "/offers", json=CREAM).json()
    _call(
        client,
        "POST",
        "/orders",
        json={
            "offer_id": offer["offer_id"],
            "option_id": offer["options"][0]["option_id"],
            "key": "test.bakery.3",
        },
    )
    assert _call(client, "GET", "/orders").json()
    assert _call(client, "POST", "/start-again").json() == {"ok": True}
    assert _call(client, "GET", "/orders").json() == []


def test_a_kitchen_can_set_a_rule_per_allergen(client: TestClient) -> None:
    answer = _set_up(
        client,
        excluded_allergens=["AP", "AS"],
        allergen_strictness="DECLARED_ONLY",
        allergen_strictness_by_code={"AP": "STRICT"},
    )
    assert answer.status_code == 200
    profile = answer.json()["profile"]
    assert profile["allergen_strictness_by_code"] == {"AP": "STRICT"}

    stray = _set_up(client, excluded_allergens=["AS"], allergen_strictness_by_code={"AP": "STRICT"})
    assert stray.status_code == 422


# --- no order without a person, for each of the shop's four customers ---------------------------------------

def _order_example(client: TestClient, kitchen: str, key: str) -> dict[str, Any]:
    """The customer's example request, offered and ordered as the page does it: the first option."""
    request = {"needed_by": MONDAY, "lines": [SHOP_EXAMPLES[kitchen]]}
    offered = _call(client, "POST", "/offers", kitchen, json=request)
    assert offered.status_code == 200, offered.text
    offer = offered.json()
    body = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"], "key": key}
    placed = _call(client, "POST", "/orders", kitchen, json=body)
    assert placed.status_code == 200, placed.text
    return placed.json()


def test_the_shop_page_ships_with_ordering_alone_and_sending_alone_switched_off(
    shop_profile_settings: dict[str, dict[str, Any]],
) -> None:
    script = KITCHENS_JS.read_text(encoding="utf-8")

    assert all(settings["auto_order_enabled"] is False for settings in shop_profile_settings.values())
    assert '"auto_order_enabled": true' not in script and "auto_order_enabled: true" not in script
    assert "autoSend: true" not in script
    assert all(settings["auto_order_enabled"] is False for settings in SHOP_CUSTOMERS.values())


def test_the_settings_copied_here_are_those_the_page_sends(shop_profile_settings: dict[str, dict[str, Any]]) -> None:
    assert {SHOP_KITCHENS[short]: settings for short, settings in SHOP_CUSTOMERS.items()} == shop_profile_settings


@pytest.mark.parametrize("kitchen", sorted(SHOP_CUSTOMERS))
def test_each_of_the_four_customers_settings_is_accepted_and_no_order_is_placed_without_a_decision(
    kitchen: str, client: TestClient
) -> None:
    saved = _call(client, "PUT", "/kitchen", kitchen, json=SHOP_CUSTOMERS[kitchen])
    assert saved.status_code == 200, saved.text
    assert saved.json()["profile"]["auto_order_enabled"] is False

    order = _order_example(client, kitchen, f"test.{kitchen}.four")

    assert (order["status"], order["placed_by"]) == ("PENDING_APPROVAL", None)
    assert order["decision"]["verdict"] == "APPROVAL" and order["decision"]["required_roles"]
    waiting = _call(client, "GET", "/approvals", kitchen).json()
    assert [approval["order_id"] for approval in waiting] == [order["order_id"]]
    trail = _call(client, "GET", f"/audit?order_id={order['order_id']}&reader=buyer", kitchen).json()
    assert not any(event["type"].endswith("order.placed_by_agent") for event in trail["events"])


def test_a_customer_who_switches_ordering_alone_on_gets_a_fully_confirmed_order_placed_by_the_agent(
    client: TestClient,
) -> None:
    """The buyer's own choice, off by default: the ward's 200 litres, every statement confirmed, no rule fired."""
    saved = _call(client, "PUT", "/kitchen", "ward", json={**SHOP_CUSTOMERS["ward"], "auto_order_enabled": True})
    assert saved.status_code == 200, saved.text

    order = _order_example(client, "ward", "test.ward.alone")

    assert (order["status"], order["placed_by"]) == ("ORDERED", "AGENT")
    assert (order["decision"]["verdict"], order["decision"]["fired"]) == ("AUTO", [])
    assert order["option"]["totals"]["net"] == 402.0
    assert [(line["product_id"], line["quantity"]) for line in order["option"]["lines"]] == [("464013", 200)]
    assert _call(client, "GET", "/approvals", "ward").json() == []


# --- the shop's back end (C2 F3, F7; the reader's question; the approval's fields) ---------------------------

MILK_1000 = {  # the brief's sentence as the ward's page would send it: milk is excluded for the ward
    "needed_by": MONDAY,
    "lines": [{"text": "1,000 litres of lactose-free milk by Monday", "product_type": "milk",
               "required_claims": ["FREE_FROM_LACTOSE"], "quantity": 1000, "unit": "L"}],
}
NOT_RECEIVED = "settings-not-received"


class AskingParser:
    """A reader that cannot read the sentence and asks back, with the lists and objects of its question."""

    model_id = "asking-reader"

    def parse_request(self, text: str, identity: Any) -> Any:
        raise InvalidRequest(
            "How much milk, and by when?", missing=["quantity", "needed_by"],
            question={"text": "How much milk, and by when?", "fields": ["quantity", "needed_by"]},
        )


def _sign(client: TestClient, approval_id: str, role: str, kitchen: str = "bakery", **body: Any) -> Any:
    decision = {"role": role, "decision": {"decision": "APPROVE"}, **body}
    return _call(client, "POST", f"/approvals/{approval_id}/decision", kitchen, json=decision)


def _waiting_cream(client: TestClient, kitchen: str = "bakery", **change: Any) -> dict[str, Any]:
    """The 10 L of cream offered and ordered in a kitchen set up with these limits: it waits for a person."""
    _set_up(client, kitchen, **change)
    offer = _call(client, "POST", "/offers", kitchen, json=CREAM).json()
    body = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"], "key": f"t.{kitchen}"}
    order = _call(client, "POST", "/orders", kitchen, json=body).json()
    assert order["status"] == "PENDING_APPROVAL", order
    return _call(client, "GET", "/approvals", kitchen).json()[0]


def test_a_book_whose_settings_never_arrived_answers_409_and_never_the_hotels_defaults(client: TestClient) -> None:
    """Without its settings the ward's book is a copy of the hotel's: no allergen excluded, so milk is offered."""
    order = {"offer_id": "off_x", "option_id": "opt_1", "key": "t.ward.1"}
    refused = [
        _call(client, "GET", "/kitchen", "ward"),
        _call(client, "POST", "/read", "ward", json={"text": "1,000 litres of lactose-free milk by Monday"}),
        _call(client, "POST", "/offers", "ward", json=MILK_1000),
        _call(client, "POST", "/orders", "ward", json=order),
    ]

    for answer in refused:
        assert answer.status_code == 409, answer.text
        assert answer.json()["type"] == NOT_RECEIVED
        assert "limits and allergen rules" in answer.json()["detail"]
    assert _call(client, "GET", "/orders", "ward").json() == []  # the records still read

    assert _call(client, "PUT", "/kitchen", "ward", json=SHOP_CUSTOMERS["ward"]).status_code == 200
    offered = _call(client, "POST", "/offers", "ward", json=MILK_1000)
    assert offered.status_code == 200 and offered.json()["options"] == []  # milk is the ward's excluded allergen

    _call(client, "POST", "/start-again", "ward")
    assert _call(client, "POST", "/offers", "ward", json=MILK_1000).status_code == 409


def test_a_call_must_name_one_of_the_four_customers(client: TestClient) -> None:
    for kitchen in ("canteen", "my-kitchen", "hotel2"):
        answer = client.get(API + "/kitchen", headers=_headers(kitchen))
        assert answer.status_code == 400, kitchen
        assert "school, ward, hotel or bakery" in answer.json()["detail"]


def test_a_customer_is_one_book_by_its_short_name_or_its_customer_id(client: TestClient) -> None:
    assert _call(client, "PUT", "/kitchen", "school", json=SHOP_CUSTOMERS["school"]).status_code == 200

    by_id = _call(client, "GET", "/kitchen", "school-kitchen")

    assert by_id.status_code == 200
    assert by_id.json()["profile"]["display_name"] == "Kilo School"


def test_the_signer_is_one_of_the_customers_people(client: TestClient) -> None:
    approval = _waiting_cream(client, max_order_net_eur=10)
    path = approval["approval_id"]

    for stranger in ("The gateway", "Hanna Laine, Harbourside Hotel", "Hanna Laine"):
        refused = _sign(client, path, "purchasing_manager", name=stranger)
        assert refused.status_code == 422, stranger
        assert "Marko Heikkinen" in refused.json()["detail"]
    # The bakery's owner is its dietitian too (decision B27), so the role has a person; this approval does not ask
    # the dietitian, and the gateway refuses the signature.
    not_asked = _sign(client, path, "dietitian")
    assert not_asked.status_code == 403, not_asked.text

    signed = _sign(client, path, "purchasing_manager")  # no name sent: the customer's own person signs
    assert signed.status_code == 200, signed.text
    assert "Marko Heikkinen, Kallio Bakery" in signed.json()["status_sentence"]


@pytest.mark.parametrize("name", ["Päivi Korhonen", "Päivi Korhonen, Kilo School"])
def test_the_page_may_send_the_persons_name_alone_or_with_the_customer(client: TestClient, name: str) -> None:
    school = {**SHOP_CUSTOMERS["school"], "max_order_net_eur": 10, "max_daily_net_eur": 10}
    approval = _waiting_cream(client, "school", **school)

    signed = _sign(client, approval["approval_id"], "finance", "school", name=name)

    assert signed.status_code == 200, signed.text
    trail = _call(client, "GET", f"/audit?order_id={approval['order_id']}&reader=buyer", "school").json()
    assert any("Päivi Korhonen, Kilo School" in event["sentence"] for event in trail["events"])


def test_an_approval_keeps_required_roles_and_the_roles_of_each_decision(client: TestClient) -> None:
    """The page works out "Decide as …" from these two fields (A4 H2): their names stay as they are."""
    approval = _waiting_cream(client, max_order_net_eur=10, max_daily_net_eur=10)
    assert approval["required_roles"] == ["purchasing_manager", "finance"]

    # One person confirms: the owner holds both roles, so his one confirmation signs both (tests/ui/
    # test_shop_one_person.py); each role is still a decision of its own in the approval's record.
    assert _sign(client, approval["approval_id"], "purchasing_manager").json()["status"] == "ORDERED"
    decided = _call(client, "GET", "/approvals?pending=false", "bakery").json()[0]

    assert decided["required_roles"] == ["purchasing_manager", "finance"]
    assert [decision["roles"] for decision in decided["decisions"]] == [["purchasing_manager"], ["finance"]]


def test_a_readers_question_reaches_the_page_with_its_lists_and_objects(
    make_client: Callable[..., TestClient],
) -> None:
    asking = make_client(request_parser=AskingParser())
    _set_up(asking)

    answer = _call(asking, "POST", "/read", json={"text": "milk for the weekend"})

    assert answer.status_code == 422
    problem = answer.json()
    assert problem["detail"] == "How much milk, and by when?"
    assert problem["missing"] == ["quantity", "needed_by"]
    assert problem["question"] == {"text": "How much milk, and by when?", "fields": ["quantity", "needed_by"]}


def test_an_offer_reads_back_in_its_own_book_and_in_no_other(client: TestClient) -> None:
    """The approvals page reads the offer of a waiting order to offer its first option, the safe product (R6)."""
    _set_up(client)
    made = _call(client, "POST", "/offers", json=CREAM).json()

    again = _call(client, "GET", f"/offers/{made['offer_id']}")

    assert again.status_code == 200
    assert [option["option_id"] for option in again.json()["options"]] == [o["option_id"] for o in made["options"]]
    _call(client, "PUT", "/kitchen", "school", json=SHOP_CUSTOMERS["school"])
    elsewhere = _call(client, "GET", f"/offers/{made['offer_id']}", "school")
    assert elsewhere.status_code == 404 and elsewhere.headers["content-type"].startswith("application/problem+json")


# --- suggestions and the customer, for the shop's selected customer (L4-2d) ----------------------------------

HOTEL_MILK = {"needed_by": MONDAY, "lines": [
    {"text": "100 L of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}]}
SCHOOL_WEEK = {"needed_by": MONDAY, "lines": [
    {"text": "120 L of milk 462775", "product_ids": ["462775"], "quantity": 120, "unit": "L"},
    {"text": "60 L of oat drink 470863", "product_ids": ["470863"], "quantity": 60, "unit": "L"}]}


def _shop_offer(client: TestClient, kitchen: str, request: dict[str, Any]) -> dict[str, Any]:
    saved = _call(client, "PUT", "/kitchen", kitchen, json=SHOP_CUSTOMERS[kitchen])
    assert saved.status_code == 200, saved.text
    offered = _call(client, "POST", "/offers", kitchen, json=request)
    assert offered.status_code == 200, offered.text
    return offered.json()


def test_the_suggestions_route_passes_the_offers_suggestions_through(client: TestClient) -> None:
    offer = _shop_offer(client, "hotel", HOTEL_MILK)

    answer = _call(client, "GET", f"/suggestions?offer_id={offer['offer_id']}", "hotel")

    assert answer.status_code == 200, answer.text
    found = answer.json()
    assert found["offer_id"] == offer["offer_id"] and found["suggestions"] == offer["suggestions"]
    # Valio Aimo's own suggestion stays silent for the hotel's usual request (decision B50): only the forgotten item.
    assert [(each["kind"], each["product_id"]) for each in found["suggestions"]] == [("FORGOTTEN_ITEM", "463797")]
    assert found["note"].startswith("Suggestions never add themselves to an order")


def test_accepting_in_the_shop_is_a_new_offer_and_nothing_is_ordered(client: TestClient) -> None:
    offer = _shop_offer(client, "hotel", HOTEL_MILK)

    accepted = _call(client, "POST", "/offers", "hotel", json=offer["suggestions"][0]["accept_request"])

    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["options"][0]["totals"]["net"] == 281.1  # €248.00 + €33.10 of cooking cream
    assert _call(client, "GET", "/orders", "hotel").json() == []


def test_the_suggestions_route_says_why_not_under_the_schools_own_settings(client: TestClient) -> None:
    offer = _shop_offer(client, "school", SCHOOL_WEEK)

    found = _call(client, "GET", f"/suggestions?offer_id={offer['offer_id']}", "school").json()

    why_not = {each["product_id"]: each for each in found["dropped"]}
    assert "464517" in why_not  # the school's forgotten yoghurt states nothing on nuts or sesame
    assert "tree nuts (AN)" in why_not["464517"]["sentence"] and why_not["464517"]["summary"]
    assert "464517" not in [each["product_id"] for each in found["suggestions"]]


def test_the_suggestions_of_another_customers_offer_or_of_no_offer_are_not_found(client: TestClient) -> None:
    offer = _shop_offer(client, "hotel", HOTEL_MILK)

    assert _call(client, "GET", f"/suggestions?offer_id={offer['offer_id']}", "bakery").status_code == 404
    assert _call(client, "GET", "/suggestions?offer_id=off_nobody", "hotel").status_code == 404
    assert _call(client, "GET", "/suggestions", "hotel").status_code == 422
    assert client.get(API + f"/suggestions?offer_id={offer['offer_id']}",
                      headers={"X-Shop-Kitchen": "hotel"}).status_code == 403


@pytest.mark.parametrize("kitchen", sorted(SHOP_KITCHENS))
def test_the_customer_route_answers_the_shops_selected_customer(kitchen: str, client: TestClient) -> None:
    answer = _call(client, "GET", "/customer", kitchen)

    assert answer.status_code == 200, answer.text
    found = answer.json()
    assert found["customer"]["customer_id"] == SHOP_KITCHENS[kitchen]
    assert found["customer"]["people"] and found["customer"]["history"] and found["customer"]["usual"]
    assert found["synthetic"] is True and found["note"].startswith("Synthetic:")
    # Before the shop sent its settings the limits are the customer's profile file, never the hotel's copy.
    assert found["limits"]["max_order_net_eur"] == SHOP_CUSTOMERS[kitchen]["max_order_net_eur"]


def test_the_customer_route_shows_the_limits_the_shop_set(client: TestClient) -> None:
    _call(client, "PUT", "/kitchen", "school", json={**SHOP_CUSTOMERS["school"], "max_order_net_eur": 90})

    found = _call(client, "GET", "/customer", "school").json()

    assert found["limits"]["max_order_net_eur"] == 90 and found["display_name"] == "Kilo School"


# --- the Python review: the guard first, and no call on the event loop ---------------------------------------


@pytest.mark.parametrize("path", ["/read", "/offers", "/orders", "/approvals/apr_x/decision"])
def test_a_caller_without_the_shop_header_gets_its_403_whatever_the_body(client: TestClient, path: str) -> None:
    for content in (b"not json", b"[]", b'{"unknown": 1}'):
        answer = client.post(API + path, content=content, headers={"X-Shop-Kitchen": "bakery"})
        assert answer.status_code == 403, (path, content, answer.text)


def test_two_offers_of_the_shop_are_served_at_the_same_time(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both calls must be inside the gateway at once: a handler that ran it on the event loop would hold the second
    request until the first had answered, and the barrier would break."""
    import threading

    from tta.api.service import Gateway

    assert _set_up(client).status_code == 200
    together = threading.Barrier(2, timeout=20)

    def waits_for_the_other(self: Any, identity: Any, request: Any) -> Any:
        together.wait()
        raise InvalidRequest("Both calls were inside the gateway at the same time.")

    monkeypatch.setattr(Gateway, "create_offer", waits_for_the_other)
    answers: list[Any] = []
    callers = [threading.Thread(target=lambda: answers.append(_call(client, "POST", "/offers", json=CREAM)))
               for _ in range(2)]
    for caller in callers:
        caller.start()
    for caller in callers:
        caller.join(timeout=30)

    assert not together.broken
    assert [answer.status_code for answer in answers] == [422, 422], [answer.text for answer in answers]
    assert all("at the same time" in answer.json()["detail"] for answer in answers)
