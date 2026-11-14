"""The audit route and its two readers (SPEC section 9): "a human-readable log for buyer and Valio Aimo".

Scores on the 20% "how decisions are logged and auditable".
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]
Problem = Callable[..., dict[str, Any]]

NOTE = "Approved by phone with the head chef."


@pytest.fixture
def approved(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], make_offer: Flow, place_order: Flow,
    hotel_approver_by_role: dict[str, str],
) -> dict[str, Any]:
    """Scenario 1 up to the approved order."""
    order = place_order(client, "agent_hotel", make_offer(client, "agent_hotel", scenario_1), "key-1")
    approval = client.get("/v1/approvals", headers=auth("hotel_purchasing")).json()[0]
    for role in approval["required_roles"]:
        response = client.post(
            f"/v1/approvals/{approval['approval_id']}/decision", json={"decision": "APPROVE", "note": NOTE},
            headers=auth(hotel_approver_by_role[role]),
        )
        assert response.status_code == 200, response.text
    return order


def test_the_supplier_token_sees_only_the_supplier_view(
    client: TestClient, auth: Auth, approved: dict[str, Any], assert_problem: Problem
) -> None:
    default = client.get("/v1/audit", params={"order_id": approved["order_id"]}, headers=auth("supplier"))
    asked = client.get(
        "/v1/audit", params={"order_id": approved["order_id"], "reader": "supplier"}, headers=auth("supplier")
    )
    as_buyer = client.get(
        "/v1/audit", params={"order_id": approved["order_id"], "reader": "buyer"}, headers=auth("supplier")
    )

    assert default.status_code == 200
    view = default.json()
    assert view == asked.json()
    assert view["reader"] == "supplier"
    assert len(view["events"]) >= 6
    assert_problem(as_buyer, "not-authorised", 403)
    # What Valio Aimo must not see: the buyer's limits, its approver, the note, the pasted words.
    text = json.dumps(view)
    for hidden in (NOTE, "Demo approver", "human:hotel-purchasing", "max_order_net_eur", "P-01",
                   "1,000 litres of lactose-free milk by Monday"):
        assert hidden not in text, hidden
    # What it does see: what was ordered of its data, and that a human approved.
    assert "agent:hotel-kitchen" in text
    assert any("approv" in event["sentence"] for event in view["events"])


def test_the_supplier_reads_every_buyers_events_in_its_own_view(
    client: TestClient, auth: Auth, approved: dict[str, Any], scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    make_offer(client, "agent_ward", scenario_2)

    view = client.get("/v1/audit", headers=auth("supplier")).json()

    assert view["reader"] == "supplier"
    assert len(view["events"]) > len(
        client.get("/v1/audit", params={"order_id": approved["order_id"]}, headers=auth("supplier")).json()["events"]
    )


def test_a_buyer_reads_its_own_trail_and_may_ask_what_the_supplier_sees(
    client: TestClient, auth: Auth, approved: dict[str, Any]
) -> None:
    own = client.get("/v1/audit", params={"order_id": approved["order_id"]}, headers=auth("agent_hotel")).json()
    approver = client.get(
        "/v1/audit", params={"order_id": approved["order_id"]}, headers=auth("hotel_purchasing")
    ).json()
    as_supplier = client.get(
        "/v1/audit", params={"order_id": approved["order_id"], "reader": "supplier"}, headers=auth("agent_hotel")
    ).json()

    assert own["reader"] == "buyer"
    assert own == approver
    assert NOTE in json.dumps(own)
    assert as_supplier["reader"] == "supplier"
    assert NOTE not in json.dumps(as_supplier)
    assert [event["id"] for event in as_supplier["events"]] == [event["id"] for event in own["events"]]


def test_without_an_order_or_offer_a_buyer_sees_its_own_events_and_no_one_elses(
    client: TestClient, auth: Auth, approved: dict[str, Any], scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    ward_offer = make_offer(client, "agent_ward", scenario_2)

    hotel = client.get("/v1/audit", headers=auth("agent_hotel")).json()
    ward = client.get("/v1/audit", headers=auth("agent_ward")).json()

    assert hotel["events"] and ward["events"]
    assert not {event["id"] for event in hotel["events"]} & {event["id"] for event in ward["events"]}
    assert ward_offer["offer_id"] not in json.dumps(hotel)
    assert approved["order_id"] not in json.dumps(ward)


def test_a_reader_nobody_knows_is_an_invalid_request(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    response = client.get("/v1/audit", params={"reader": "everyone"}, headers=auth("agent_hotel"))

    assert_problem(response, "invalid-request", 422)
