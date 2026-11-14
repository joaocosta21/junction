"""A form submission orders at most once, whatever breaks (task FIX-10, finding 4).

Scores on the 30% "working end-to-end demo" and the 20% "controls": a visitor who sends a form again after an
error page must see the first result, never a second order.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tta.contracts.agent import AgentRun
from tta.contracts.common import Identity, OrderStatus
from tta.contracts.ports import GatewayService
from tta.ui import run as run_module
from tta.ui.examples import EXAMPLES
from tta.ui.run import order_key

MakeClient = Callable[..., TestClient]
SCENARIO_2 = EXAMPLES[1]


class AgentThatBreaksAfterItsOrder:
    """Places the order of scenario 2 through the gateway, then fails with an error the runner never expected."""

    def __init__(self) -> None:
        self.runs = 0

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        self.runs += 1
        offer = tools.create_offer(identity, SCENARIO_2.request)
        tools.place_order(identity, offer.offer_id, offer.options[0].option_id, f"agent-{self.runs}")
        raise ValueError("Failed to parse response as JSON. Raw response: <html>")


def test_the_pages_order_with_a_key_derived_from_the_forms_run_key(
    client: TestClient, form_fields: Callable[..., Any], only_order: Callable[..., Any]
) -> None:
    fields = form_fields(client)

    client.post("/run", data={**fields, "example": "scenario-2"})

    assert only_order(client, "agent:allergy-ward").idempotency_key == order_key(fields["run_key"])


def test_a_run_that_breaks_after_the_agents_order_shows_the_order_and_a_resend_shows_it_again(
    make_client: MakeClient, form_fields: Callable[..., Any], orders: Callable[..., Any]
) -> None:
    runner = AgentThatBreaksAfterItsOrder()
    client = make_client(agent_runner=runner)
    form = {**form_fields(client), "text": SCENARIO_2.text, "who": "agent:allergy-ward"}

    first = client.post("/run", data=form)
    again = client.post("/run", data=form)

    placed = orders(client, "agent:allergy-ward")
    assert runner.runs == 1 and len(placed) == 1 and placed[0].status is OrderStatus.PENDING_APPROVAL
    assert first.status_code == again.status_code == 200 and first.url == again.url
    assert "Sent for approval" in again.text and "stopped on an error (ValueError)" in again.text
    assert "Raw response" not in again.text


def test_a_form_the_page_has_forgotten_still_cannot_order_twice(
    client: TestClient, form_fields: Callable[..., Any], orders: Callable[..., Any], monkeypatch: Any
) -> None:
    monkeypatch.setattr(run_module, "RUNS_PER_VISITOR", 1)  # the page remembers one run per visitor
    form = {**form_fields(client), "example": "scenario-2"}
    client.post("/run", data=form)
    client.post("/run", data={**form_fields(client), "example": "scenario-1"})  # pushes the first out

    resent = client.post("/run", data=form)

    assert len(orders(client, "agent:allergy-ward")) == 1  # the order book knows the key: no second order
    assert "No order was placed" in resent.text
