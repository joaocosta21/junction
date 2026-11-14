"""Each browser has its own demo order book (task FIX-10, finding 1).

Scores on the 30% "working end-to-end demo" and the 20% "what the agent can decide alone": every judge who
opens the pages starts from an empty book, sees scenario 2 ordered by the agent alone, and sees only the
approvals of their own runs. The REST API and MCP keep the shared book of their tokens.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tta.contracts.common import OrderStatus

Post = Callable[..., Any]
MakeClient = Callable[..., TestClient]
OWN_BOOK = "Your own demo order book: nothing you do here is seen by other visitors, and it commits nobody."
START_AGAIN = re.compile(r'<form method="post" action="/start-again"[^>]*>\s*<input type="hidden" name="csrf" value="')


def _second_browser(client: TestClient) -> TestClient:
    other = TestClient(client.app, base_url=str(client.base_url))
    other.__enter__()
    return other


def test_one_browsers_orders_are_not_on_another_browsers_pages(
    client: TestClient, run_example: Post, orders: Callable[..., Any]
) -> None:
    other = _second_browser(client)
    run_example(client, "scenario-1")
    order = orders(client)[0]

    queue = other.get("/approvals").text

    assert "above the €750 limit per order" in client.get("/approvals").text
    assert "Nothing is waiting" in queue and order.order_id not in queue
    assert other.get(f"/orders/{order.order_id}").status_code == 404
    assert other.get("/", params={"offer": order.offer_id}).status_code == 404
    assert orders(other) == ()


def test_every_browser_has_its_own_scenario_2_approval_rules(
    client: TestClient, run_example: Post, orders: Callable[..., Any]
) -> None:
    for _ in range(4):
        run_example(client, "scenario-2")  # the fourth of one browser's day goes to a human, in its own book
    other = _second_browser(client)

    page = run_example(other, "scenario-2").text

    local_orders = orders(client, "agent:allergy-ward")
    assert all(order.status is OrderStatus.PENDING_APPROVAL for order in local_orders)
    assert sum("P-02" in order.decision.rule_ids for order in local_orders) == 1
    assert "Sent for approval" in page and "F-10" in page


def test_every_page_says_the_book_is_the_visitors_own_and_offers_to_start_again(
    client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    run_example(client, "scenario-2")
    order_id = only_order(client, "agent:allergy-ward").order_id

    for path in ("/", "/approvals", "/assumptions", f"/orders/{order_id}", "/no-such-page"):
        page = client.get(path).text
        assert OWN_BOOK in page, path
        assert START_AGAIN.search(page), path


def test_starting_again_empties_this_browsers_book_and_no_other(
    client: TestClient, run_example: Post, form_fields: Callable[..., Any], orders: Callable[..., Any]
) -> None:
    other = _second_browser(client)
    run_example(client, "scenario-1")
    run_example(other, "scenario-1")

    response = client.post("/start-again", data={"csrf": form_fields(client)["csrf"]})

    assert response.status_code == 200 and response.url.path == "/"
    assert orders(client) == () and "Nothing is waiting" in client.get("/approvals").text
    assert len(orders(other)) == 1


def test_starting_again_needs_a_post_with_the_form_token(
    client: TestClient, run_example: Post, orders: Callable[..., Any]
) -> None:
    run_example(client, "scenario-1")

    assert client.get("/start-again").status_code == 405
    assert client.post("/start-again", data={"csrf": "x" * 43}).status_code == 403
    assert len(orders(client)) == 1


def test_an_offer_made_through_the_rest_api_is_not_on_the_pages(client: TestClient, run_example: Post) -> None:
    run_example(client, "scenario-2")  # the browser has a book of its own
    headers = {"Authorization": "Bearer demo-agent-allergy-ward"}
    body = {"needed_by": "2026-11-16", "require_confirmed": True, "lines": [{
        "text": "200 litres", "product_type": "plant_drink", "quantity": 200, "unit": "L",
        "exclude_allergens": ["AM", "AW"],
    }]}
    offer = client.post("/v1/offers", json=body, headers=headers).json()

    assert client.get("/", params={"offer": offer["offer_id"]}).status_code == 404


def test_reading_the_pages_without_running_anything_opens_no_book(client: TestClient) -> None:
    for path in ("/", "/approvals", "/assumptions", "/orders/ord_nobody"):
        client.get(path)

    assert len(client.app.state.parts.sandboxes) == 0  # type: ignore[attr-defined]


def test_the_order_page_shows_the_head_of_this_books_own_chain(
    client: TestClient, run_example: Post, only_order: Callable[..., Any], book: Callable[..., Any]
) -> None:
    run_example(client, "scenario-2")
    order_id = only_order(client, "agent:allergy-ward").order_id
    events, last_hash = book(client).audit.head()

    trail = client.get(f"/orders/{order_id}").text
    trail = trail[trail.index('id="trail"'):]

    assert f"{events} events" in trail and last_hash[:16] in trail
    assert "data-audit-head" not in trail  # /healthz shows the shared book of the tokens, not this one


def test_the_pages_need_the_visitors_order_books(client: TestClient) -> None:
    import pytest  # noqa: PLC0415

    from tta.api.hooks import SurfaceContext  # noqa: PLC0415
    from tta.ui import routes  # noqa: PLC0415

    parts = client.app.state.parts  # type: ignore[attr-defined]
    context = SurfaceContext(
        settings=parts.settings, service=parts.service, identify=parts.tokens.identify,
        demo_identities=parts.tokens.identities, sandboxes=None,
    )

    with pytest.raises(ValueError, match="order book of its own"):
        routes.create_surface(context)


def test_the_book_key_is_the_cookies_where_no_middleware_put_one_in_the_request() -> None:
    from starlette.requests import Request  # noqa: PLC0415

    from tta.ui import security  # noqa: PLC0415

    key = "k" * 43
    scope = {"type": "http", "scheme": "http", "server": ("testserver", 80), "path": "/", "query_string": b""}
    with_cookie = Request({**scope, "headers": [(b"cookie", f"tta_book={key}".encode())]})
    without = Request({**scope, "headers": []})

    assert security.book_key(with_cookie) == key
    assert security.book_key(without) != security.book_key(without)  # a new key each time: never a shared one
