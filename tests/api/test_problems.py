"""Every typed error leaves as an RFC 9457 problem with its stable type and status (SPEC section 2).

Scores on the 15% "open, documented standards rather than a proprietary format".
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from tta.api.wiring import Parts
from tta.contracts.allergen import AllergenCheck, AllergenFinding
from tta.contracts.common import AllergenOutcome, AllergenRelation, AllergenStrictness
from tta.contracts.errors import ALL_ERRORS, PROBLEM_CONTENT_TYPE
from tta.contracts.offer import Offer

Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]
Problem = Callable[..., dict[str, Any]]

MARKER = "<script>alert('caller text')</script>"


def test_the_tests_below_cover_every_typed_error() -> None:
    covered = {
        "invalid-request", "not-authorised", "unknown-product", "not-found", "offer-expired", "offer-stale",
        "policy-blocked", "supplier-unavailable", "rate-limited",
    }

    assert {error.slug for error in ALL_ERRORS} == covered


def test_invalid_request_lists_the_fields_and_never_echoes_a_value(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    line = {
        "text": "milk", "quantity": -5, "unit": MARKER, "product_ids": [MARKER], MARKER: 1, "made_up_by_the_caller": 1,
    }

    response = client.post("/v1/offers", json={"needed_by": MARKER, "lines": [line]}, headers=auth("agent_hotel"))

    problem = assert_problem(response, "invalid-request", 422)
    fields = {error["field"] for error in problem["errors"]}
    assert {"body.needed_by", "body.lines.0.quantity", "body.lines.0.unit", "body.lines.0.product_ids.0"} <= fields
    assert all(error["problem"] for error in problem["errors"])
    # A field the request does not have is named by where it sits, never by the key the caller made up.
    unknown = [error for error in problem["errors"] if error["field"] == "body.lines.0"]
    assert [error["problem"] for error in unknown] == ["a field this request does not have"] * 2
    assert "made_up" not in response.text
    assert "caller text" not in response.text
    assert "script" not in response.text


def test_a_body_that_is_not_json_is_an_invalid_request(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    headers = {**auth("agent_hotel"), "Content-Type": "application/json"}

    response = client.post("/v1/offers", content=b'{"lines": [' + MARKER.encode(), headers=headers)

    assert_problem(response, "invalid-request", 422)
    assert "caller text" not in response.text


def test_an_exclusion_without_a_strictness_is_an_invalid_request(
    client: TestClient, auth: Auth, scenario_1: dict[str, Any], assert_problem: Problem
) -> None:
    # hotel-kitchen sets no strictness, so a request that excludes an allergen must say how strict (SPEC section 3).
    line = {**scenario_1["lines"][0], "exclude_allergens": ["AM"]}

    response = client.post("/v1/offers", json={**scenario_1, "lines": [line]}, headers=auth("agent_hotel"))

    assert_problem(response, "invalid-request", 422)


def test_not_authorised_is_401_without_a_token_and_403_for_the_wrong_caller(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    assert_problem(client.get("/v1/approvals"), "not-authorised", 401)
    assert_problem(client.get("/v1/approvals", headers=auth("agent_hotel")), "not-authorised", 403)


def test_unknown_product_is_404(client: TestClient, auth: Auth, assert_problem: Problem) -> None:
    read = client.get("/v1/products/000000", headers=auth("agent_hotel"))
    substitutes = client.post("/v1/products/000000/substitutes", json={}, headers=auth("agent_hotel"))
    named = {"lines": [{"text": "this one", "product_ids": ["000000"], "quantity": 1, "unit": "UNIT"}]}
    offer = client.post("/v1/offers", json=named, headers=auth("agent_hotel"))

    assert_problem(read, "unknown-product", 404)
    assert_problem(substitutes, "unknown-product", 404)
    assert_problem(offer, "unknown-product", 404)


def test_a_product_id_that_is_not_an_id_is_an_invalid_request(
    client: TestClient, auth: Auth, assert_problem: Problem
) -> None:
    response = client.get("/v1/products/46%3Cb%3E4013", headers=auth("agent_hotel"))

    assert_problem(response, "invalid-request", 422)


def test_not_found_is_404_for_an_id_nobody_issued(client: TestClient, auth: Auth, assert_problem: Problem) -> None:
    decision = {"decision": "APPROVE"}
    order = {"offer_id": "off_nobody", "option_id": "opt_1"}

    assert_problem(client.get("/v1/offers/off_nobody", headers=auth("agent_hotel")), "not-found", 404)
    assert_problem(client.get("/v1/orders/ord_nobody", headers=auth("agent_hotel")), "not-found", 404)
    assert_problem(client.post("/v1/orders", json=order, headers=auth("agent_hotel", "k-1")), "not-found", 404)
    assert_problem(
        client.post("/v1/approvals/apr_nobody/decision", json=decision, headers=auth("hotel_purchasing")),
        "not-found", 404,
    )
    assert_problem(
        client.get("/v1/audit", params={"offer_id": "off_nobody"}, headers=auth("agent_hotel")), "not-found", 404
    )


def test_offer_stale_is_409_and_names_a_fresh_offer(
    changing_client: TestClient, changing: Any, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow,
    assert_problem: Problem,
) -> None:
    offer = make_offer(changing_client, "agent_ward", scenario_2)
    body = {"offer_id": offer["offer_id"], "option_id": "opt_1"}
    changing.price_rise = Decimal("0.10")

    response = changing_client.post("/v1/orders", json=body, headers=auth("agent_ward", "key-1"))

    problem = assert_problem(response, "offer-stale", 409)
    assert problem["changes"]
    assert problem["offer_id"] == offer["offer_id"]
    assert problem["fresh_offer_id"] != offer["offer_id"]
    fresh = changing_client.get(f"/v1/offers/{problem['fresh_offer_id']}", headers=auth("agent_ward"))
    assert fresh.status_code == 200
    assert fresh.json()["request"] == offer["request"]
    assert changing_client.get("/v1/orders", headers=auth("agent_ward")).json() == []
    # The fresh offer has a trail of its own, which starts with the request as it was received.
    trail = changing_client.get(
        "/v1/audit", params={"offer_id": problem["fresh_offer_id"]}, headers=auth("agent_ward")
    ).json()
    assert [event["type"] for event in trail["events"]].count("tta.v1.request.received") == 1
    assert trail["events"][0]["type"] == "tta.v1.request.received"
    # The fresh offer can be ordered: the flow does not get stuck.
    again = {"offer_id": fresh.json()["offer_id"], "option_id": fresh.json()["options"][0]["option_id"]}
    assert changing_client.post("/v1/orders", json=again, headers=auth("agent_ward", "key-2")).status_code == 201


def test_offer_expired_is_409_and_names_a_fresh_offer(
    changing_client: TestClient, changing: Any, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow,
    assert_problem: Problem,
) -> None:
    offer = make_offer(changing_client, "agent_ward", scenario_2)
    body = {"offer_id": offer["offer_id"], "option_id": "opt_1"}
    changing.hours_later = 96  # past every cut-off of the capture

    response = changing_client.post("/v1/orders", json=body, headers=auth("agent_ward", "key-1"))

    problem = assert_problem(response, "offer-expired", 409)
    fresh = changing_client.get(f"/v1/offers/{problem['fresh_offer_id']}", headers=auth("agent_ward"))
    assert fresh.status_code == 200
    assert fresh.json()["offer_id"] != offer["offer_id"]
    view = changing_client.get("/v1/audit", params={"offer_id": offer["offer_id"]}, headers=auth("agent_ward"))
    assert "tta.v1.order.not_placed" in [event["type"] for event in view.json()["events"]]


def test_a_stale_offer_is_still_409_when_no_fresh_offer_can_be_built(
    changing_client: TestClient, changing: Any, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow,
    assert_problem: Problem, monkeypatch: Any,
) -> None:
    offer = make_offer(changing_client, "agent_ward", scenario_2)
    body = {"offer_id": offer["offer_id"], "option_id": "opt_1"}
    changing.price_rise = Decimal("0.10")
    genuine = changing.price

    def fails_after_the_recheck(product_ids: Any, *, fresh: bool = False) -> Any:
        if not fresh:
            changing.down = True
        return genuine(product_ids, fresh=fresh)

    monkeypatch.setattr(changing, "price", fails_after_the_recheck)

    response = changing_client.post("/v1/orders", json=body, headers=auth("agent_ward", "key-1"))

    problem = assert_problem(response, "offer-stale", 409)
    assert "fresh_offer_id" not in problem


def _declaring_milk(parts: Parts, offer_id: str) -> None:
    """Change the stored offer so that its first line declares an excluded allergen: only rule F-02 can stop it."""
    offer = parts.store.get_offer(offer_id)
    assert isinstance(offer, Offer)
    option = offer.options[0]
    finding = AllergenFinding(
        excluded_code="AM", relation=AllergenRelation.CONTAINS, outcome=AllergenOutcome.REJECT,
        sentence="The product declares milk (AM).",
    )
    check = AllergenCheck(
        outcome=AllergenOutcome.REJECT, strictness=AllergenStrictness.STRICT, findings=(finding,), all_explicit=True
    )
    line = option.lines[0].model_copy(update={"allergen_check": check})
    changed = option.model_copy(update={"lines": (line, *option.lines[1:])})
    parts.store.save_offer(offer.model_copy(update={"options": (changed, *offer.options[1:])}))


def test_policy_blocked_is_422_and_no_order_exists(
    client: TestClient, parts: Parts, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow,
    assert_problem: Problem,
) -> None:
    offer = make_offer(client, "agent_ward", scenario_2)
    _declaring_milk(parts, offer["offer_id"])
    body = {"offer_id": offer["offer_id"], "option_id": "opt_1"}

    response = client.post("/v1/orders", json=body, headers=auth("agent_ward", "key-1"))

    problem = assert_problem(response, "policy-blocked", 422)
    assert "F-02" in problem["rule_ids"]
    assert client.get("/v1/orders", headers=auth("agent_ward")).json() == []
    view = client.get("/v1/audit", params={"offer_id": offer["offer_id"]}, headers=auth("agent_ward")).json()
    assert "tta.v1.order.blocked" in [event["type"] for event in view["events"]]


def test_supplier_unavailable_is_503(
    changing_client: TestClient, changing: Any, auth: Auth, scenario_2: dict[str, Any], assert_problem: Problem
) -> None:
    changing.down = True

    response = changing_client.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))

    assert_problem(response, "supplier-unavailable", 503)


def test_an_unexpected_fault_is_a_500_problem_with_no_detail_of_the_fault(
    changing_client: TestClient, changing: Any, auth: Auth, scenario_2: dict[str, Any]
) -> None:
    changing.broken = True

    response = changing_client.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))

    assert response.status_code == 500
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    assert response.json() == {
        "type": "about:blank", "title": "Internal Server Error", "status": 500,
        "detail": "The gateway could not complete this request. Nothing in this answer can be relied on.",
    }
    assert "do-not-show" not in response.text
    assert "Traceback" not in response.text


def test_a_path_or_method_the_gateway_does_not_have_is_a_problem_too(client: TestClient, auth: Auth) -> None:
    missing = client.get("/v1/no-such-thing", headers=auth("agent_hotel"))
    wrong_method = client.delete("/v1/orders", headers=auth("agent_hotel"))

    assert (missing.status_code, wrong_method.status_code) == (404, 405)
    for response in (missing, wrong_method):
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        assert response.json()["type"] == "about:blank"
        assert response.json()["status"] == response.status_code


def test_a_problem_never_repeats_the_path_or_the_id_the_caller_sent(client: TestClient, auth: Auth) -> None:
    unknown_id = client.get("/v1/orders/ord_nobody", headers=auth("agent_hotel"))
    unknown_path = client.get("/v1/made-up-by-the-caller", headers=auth("agent_hotel"))

    assert "ord_nobody" not in unknown_id.text
    assert "made-up" not in unknown_path.text
    assert "instance" not in unknown_id.json()


def test_a_contract_model_that_does_not_validate_below_the_route_is_an_invalid_request(
    settings: Any, catalog: Any, auth: Auth, assert_problem: Problem
) -> None:
    from tta.api import create_app
    from tta.api.wiring import build_parts
    from tta.contracts.request import PurchaseRequest

    class Parser:
        def parse_request(self, text: str, identity: Any) -> PurchaseRequest:
            return PurchaseRequest.model_validate({"lines": [{"text": text, "quantity": MARKER, "unit": "L"}]})

    parts = build_parts(settings, catalog=catalog, request_parser=Parser())
    with TestClient(create_app(settings, parts=parts)) as client:
        response = client.post("/v1/requests/parse", json={"text": "milk"}, headers=auth("agent_hotel"))

    problem = assert_problem(response, "invalid-request", 422)
    assert problem["errors"][0]["field"] == "lines.0.quantity"
    assert "caller text" not in response.text


def test_a_contract_model_that_does_not_validate_where_no_caller_input_is_read_is_our_fault_and_a_500(
    changing_client: TestClient, changing: Any, auth: Auth, scenario_2: dict[str, Any], monkeypatch: Any,
    caplog: Any,
) -> None:
    from pydantic import ValidationError

    from tta.contracts.availability import PriceResponse

    def answers_with_a_broken_model(product_ids: Any, *, fresh: bool = False) -> Any:
        return PriceResponse.model_validate({"currency": MARKER, "lines": "do-not-show-this-to-a-caller"})

    monkeypatch.setattr(changing, "price", answers_with_a_broken_model)

    with caplog.at_level("ERROR", logger="tta.api.errors"):
        response = changing_client.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))

    # The request was valid: reporting this as `invalid-request` would send the caller looking for its own mistake.
    assert response.status_code == 500
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    assert response.json() == {
        "type": "about:blank", "title": "Internal Server Error", "status": 500,
        "detail": "The gateway could not complete this request. Nothing in this answer can be relied on.",
    }
    assert "do-not-show" not in response.text and "caller text" not in response.text
    # The fault itself, with its trace, is in the log.
    assert any(
        record.exc_info is not None and isinstance(record.exc_info[1], ValidationError) for record in caplog.records
    )


def test_a_model_that_does_not_validate_inside_an_agent_run_is_a_500_too(
    settings: Any, catalog: Any, auth: Auth
) -> None:
    from tta.api import create_app
    from tta.api.wiring import build_parts
    from tta.contracts.agent import AgentRun

    class Runner:
        def run_agent(self, text: str, identity: Any, tools: Any) -> AgentRun:
            return AgentRun.model_validate({"text": text, "steps": MARKER})

    parts = build_parts(settings, catalog=catalog, agent_runner=Runner())
    with TestClient(create_app(settings, parts=parts), raise_server_exceptions=False) as client:
        response = client.post("/v1/agent/run", json={"text": "milk"}, headers=auth("agent_hotel"))

    assert response.status_code == 500
    assert response.json()["type"] == "about:blank"
    assert "caller text" not in response.text


def test_the_published_interface_is_built_once(client: TestClient) -> None:
    assert client.get("/openapi.json").json() == client.get("/openapi.json").json()
