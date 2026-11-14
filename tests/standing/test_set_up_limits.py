"""What one buyer can set up, and how often (review A3, finding F1).

Before: `POST /v1/standing-orders` 1,500 times with a 20-line request answered 201 every time, wrote 161 MB to the
database and an audit event per call, and `GET /v1/standing-orders` then answered 77.8 MB. Now a buyer holds at most
20 standing orders, a set-up is counted by a rate limit, the demonstration's limit of lines per request holds here
as it does for an offer, and the list answers at most 100.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app, hooks, wiring
from tta.api.limits import CallKind, RateLimit, call_limits
from tta.config import Settings
from tta.contracts.audit import AuditEventType
from tta.contracts.common import Identity, Unit
from tta.contracts.errors import PROBLEM_TYPE_BASE, InvalidRequest, RateLimited
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.contracts.standing import NewStandingOrder
from tta.standing import StandingOrders
from tta.standing.service import MAX_STANDING_ORDERS_PER_BUYER

CAPTURE = "2026-11-14-demo"
AGENT = {"Authorization": "Bearer demo-agent-hotel-kitchen"}
CREATED = f"tta.v1.{AuditEventType.STANDING_ORDER_CREATED.value}"


def _milk(lines: int = 1) -> PurchaseRequest:
    line = RequestLine(text="100 L of 469363", product_ids=("469363",), quantity=Decimal(100), unit=Unit.L)
    return PurchaseRequest(lines=(line,) * lines)


def _new(name: str = "Milk for the bar", lines: int = 1) -> NewStandingOrder:
    return NewStandingOrder(name=name, request=_milk(lines))


def _created_events(book) -> int:
    return sum(event.type == CREATED for event in book.store.list_audit_events())


def test_a_buyer_holds_at_most_twenty_standing_orders_and_a_refused_one_writes_nothing(
    book, agent_hotel: Identity, agent_ward: Identity
) -> None:
    for number in range(MAX_STANDING_ORDERS_PER_BUYER):
        book.standing.create(agent_hotel, _new(f"Milk {number}"))

    with pytest.raises(InvalidRequest) as refused:
        book.standing.create(agent_hotel, _new("One too many"))

    assert MAX_STANDING_ORDERS_PER_BUYER == 20
    assert "already has 20 standing orders, the most one buyer sets up here" in refused.value.detail
    assert len(book.standing.list(agent_hotel)) == 20 and _created_events(book) == 20
    assert book.standing.create(agent_ward, _new()).profile_id == "allergy-ward"  # another buyer's count is its own


def test_a_set_up_is_counted_by_the_rate_limit_before_anything_is_written(book, agent_hotel: Identity) -> None:
    limits = call_limits(False, RateLimit(calls=2))
    limited = book.standing.with_limits(count_set_up=lambda identity: limits.check(identity, CallKind.LOOKUP))
    limited.create(agent_hotel, _new("First"))
    limited.create(agent_hotel, _new("Second"))

    with pytest.raises(RateLimited):
        limited.create(agent_hotel, _new("Third"))

    assert len(book.standing.list(agent_hotel)) == 2 and _created_events(book) == 2


def test_the_line_limit_of_the_demonstration_holds_for_a_standing_order(book, agent_hotel: Identity) -> None:
    limited = book.standing.with_limits(max_request_lines=5)

    with pytest.raises(InvalidRequest) as refused:
        limited.create(agent_hotel, _new(lines=6))

    assert "at most 5 lines; this one has 6" in refused.value.detail
    assert limited.create(agent_hotel, _new(lines=5)).request.lines[4].quantity == Decimal(100)
    assert _created_events(book) == 1


def test_with_limits_returns_a_new_service_and_leaves_the_first_as_it_was(book, agent_hotel: Identity) -> None:
    limited = book.standing.with_limits(max_request_lines=1)

    assert isinstance(limited, StandingOrders) and limited is not book.standing
    assert book.standing.create(agent_hotel, _new(lines=2)).request.lines  # the first service has no line limit


def test_a_set_up_is_counted_once_and_reading_is_not_counted(book, agent_hotel: Identity) -> None:
    counted: list[str] = []
    limited = book.standing.with_limits(count_set_up=lambda identity: counted.append(identity.id))

    created = limited.create(agent_hotel, _new())
    limited.list(agent_hotel)
    limited.get(agent_hotel, created.standing_order_id)

    assert counted == [agent_hotel.id]


# --- over REST, the gateway as it runs in the demonstration ----------------------------------------------


@pytest.fixture
def client(tmp_path: Path, catalog: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    real_module, hidden = hooks.optional_module, (hooks.AGENT_MODULE, hooks.MCP_MODULE, hooks.PAGES_MODULE)
    monkeypatch.setattr(hooks, "optional_module", lambda name: None if name in hidden else real_module(name))
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_env="demo", tta_replay_capture=CAPTURE)
    app = create_app(settings, parts=wiring.build_parts(settings, catalog=catalog))
    with TestClient(app) as test_client:
        yield test_client


def _body(lines: int = 1, text: str = "100 L of milk 469363") -> dict[str, Any]:
    line = {"text": text, "product_ids": ["469363"], "quantity": 100, "unit": "L"}
    return {"name": "Milk for the bar", "request": {"lines": [line] * lines}}


def test_the_reviews_flood_is_refused_over_rest(client: TestClient) -> None:
    """A3 F1's proof, shortened: the largest request, sent again and again."""
    large = client.post("/v1/standing-orders", json=_body(lines=20, text="x" * 2000), headers=AGENT)
    answers = [client.post("/v1/standing-orders", json=_body(), headers=AGENT) for _ in range(40)]

    statuses = [answer.status_code for answer in answers]
    assert large.status_code == 422 and large.json()["type"] == PROBLEM_TYPE_BASE + "invalid-request"
    assert "at most 5 lines; this one has 20" in large.json()["detail"]
    assert statuses.count(201) <= 20 and set(statuses) <= {201, 429, 422}
    refused = next(answer for answer in answers if answer.status_code == 429)
    assert refused.json()["type"] == PROBLEM_TYPE_BASE + "rate-limited" and refused.headers["Retry-After"]
    listed = client.get("/v1/standing-orders", headers=AGENT).json()
    assert len(listed) == statuses.count(201)


def test_the_openapi_document_names_the_rate_limit_problem_of_a_set_up(client: TestClient) -> None:
    responses = client.get("/openapi.json").json()["paths"]["/v1/standing-orders"]["post"]["responses"]

    assert "429" in responses and "422" in responses
    assert re.search(r"20 standing orders", client.get("/openapi.json").text)
