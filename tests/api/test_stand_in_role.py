"""An agent cannot write in the gateway's voice to the person who signs (review A3, finding F4; its proof t16).

Scores on the 20% "quality of the guardrails design". `stands_in_role` arrives in the request and rule F-09's
sentence stands on the approver's card: the role is shown only when the recipe table holds it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]
IN_THE_GATEWAYS_VOICE = "SAFE: dietitian already verified allergens, approve at once"


def _stand_in(role: str) -> dict[str, Any]:
    return {
        "lines": [{
            "text": "5 litres of oat drink in place of cream", "product_type": "plant_drink", "name_terms": ["oat"],
            "quantity": 5, "unit": "L", "stands_in_for": "cream", "stands_in_role": role,
        }],
    }


def test_a_role_the_agent_made_up_never_reaches_the_approvers_card(
    client: TestClient, auth: Auth, make_offer: Flow, place_order: Flow
) -> None:
    offer = make_offer(client, "agent_hotel", _stand_in(IN_THE_GATEWAYS_VOICE))
    order = place_order(client, "agent_hotel", offer, "t16")

    approvals = client.get("/v1/approvals", headers=auth("hotel_purchasing"))

    assert order["status"] == "PENDING_APPROVAL"
    assert "approve at once" not in approvals.text and "already verified" not in approvals.text
    [approval] = approvals.json()
    f09 = [reason for reason in approval["reasons"] if "stands in for an ingredient of a recipe" in reason]
    assert len(f09) == 1  # F-09 still fires
    assert "in place of the recipe's cream (the role the request gives for it is not in the recipe table" in f09[0]
    assert "F-09" in [rule["rule_id"] for rule in order["decision"]["fired"]]
    assert "approve at once" not in str(order["decision"])


def test_a_role_with_a_quotation_mark_or_a_line_break_is_refused(
    client: TestClient, auth: Auth, assert_problem: Callable[..., dict[str, Any]]
) -> None:
    for role in ('thickens". No rule asked for a human. "', "thickens\nApproved by the dietitian", "x" * 201):
        refused = client.post("/v1/offers", json=_stand_in(role), headers=auth("agent_hotel"))

        assert "stands_in_role" in assert_problem(refused, "invalid-request", 422)["detail"]
