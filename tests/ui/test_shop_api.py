"""The shop's JSON routes (`/shop/api`): each kitchen of the shop on its own demo book, under the same rules.

Scores on the 30% demo (the shop runs request -> offer -> order -> approval -> audit through these routes) and
the 20% "autonomy and controls" (a kitchen's limits set in the shop are the ones the policy engine applies, the
agent still cannot approve, and the audit trail names the person who signed).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/shop/api"
CREAM = {  # 10 L of whipping cream by Monday: some €30-60 in the recordings
    "needed_by": "2026-11-16",
    "lines": [{"text": "10 litres of whipping cream", "product_type": "cream", "quantity": 10, "unit": "L"}],
}
BAKERY = {
    "display_name": "Kallio Bakery",
    "auto_order_enabled": True,
    "max_order_net_eur": 50,
    "max_daily_net_eur": 400,
    "min_fill_ratio": 1,
    "excluded_allergens": [],
    "allergen_strictness": "DECLARED_ONLY",
    "substitution_without_approval": "SAME_CATEGORY",
    "variable_weight": "APPROVAL",
    "deposits": "APPROVAL",
    "require_confirmed": False,
    "standing_order_drift_ratio": 0.15,
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
