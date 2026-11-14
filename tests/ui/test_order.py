"""The order page: the record, the statements it relied on, the audit trail for two readers, the hash chain."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.contracts.audit import ChainVerification
from tta.contracts.common import ApprovalStatus

Post = Callable[..., Any]
NOTE = "Agreed with the kitchen on Friday."


def _service(client: TestClient) -> Any:
    """The service of this browser's own order book."""
    sandboxes = client.app.state.parts.sandboxes  # type: ignore[attr-defined]
    return sandboxes.find(client.cookies.get("tta_book") or client.cookies.get("__Host-tta_book")).service


def _approved_order(client: TestClient, run_example: Post, decide: Post, identities: Callable[..., Any]) -> str:
    """Scenario 1, approved by the purchasing manager with a note. Returns the order id."""
    run_example(client, "scenario-1")
    service = _service(client)
    approval = service.list_approvals(identities(client)["human:hotel-purchasing"], ApprovalStatus.PENDING)[0]
    decide(client, approval.approval_id, "APPROVE", option=approval.option_id, note=NOTE)
    return approval.order_id


def test_the_order_page_shows_the_record_and_the_statements_it_relied_on(
    client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    run_example(client, "scenario-2")
    order = only_order(client, "agent:allergy-ward")

    page = client.get(f"/orders/{order.order_id}").text

    assert order.order_id in page
    assert "Waiting for approval" in page
    assert "F-10" in page
    assert "The Valio Aimo mock has no order endpoint" in page  # what ORDERED means here
    assert "464013" in page and "€2.01" in page and "€402.00" in page
    statements = page[page.index('id="reliance"'):page.index('id="trail"')]
    assert "478" in statements  # the stock figure Valio stated
    assert "Monday 16 Nov 2026" in statements and "Sunday 15 Nov 2026 at 17:00" in statements
    assert "no end date" in statements  # a price valid to 31 Dec 9999
    assert "Replay" in statements


def test_the_audit_trail_is_a_timeline_of_sentences_and_the_chain_verifies(
    client: TestClient, run_example: Post, only_order: Callable[..., Any], identities: Callable[..., Any]
) -> None:
    run_example(client, "scenario-2")
    order = only_order(client, "agent:allergy-ward")

    page = client.get(f"/orders/{order.order_id}").text
    trail = page[page.index('id="trail"'):]

    for sentence in ("The request was read as", "looked up price and availability", "built offer",
                     "The rules of profile allergy-ward were checked", "within its authority"):
        assert sentence in trail, sentence
    events = _service(client).get_audit(identities(client)["agent:allergy-ward"], order_id=order.order_id).events
    assert trail.count('class="event"') == len(events) >= 5  # parsed, looked up, offered, policy, placed by the agent
    assert "The hash chain verifies" in trail and "The audit trail is intact" in trail
    assert "Allergy ward agent (demo)" in trail and "The gateway" in trail


def test_the_supplier_view_shows_no_limit_value_no_approver_and_no_note(
    client: TestClient, run_example: Post, decide: Post, identities: Callable[..., Any]
) -> None:
    order_id = _approved_order(client, run_example, decide, identities)

    buyer = client.get(f"/orders/{order_id}").text
    supplier = client.get(f"/orders/{order_id}", params={"view": "supplier"}).text

    for buyer_only in ("€750", "Demo approver Hanna", NOTE, "P-01"):
        assert buyer_only in buyer, buyer_only
        assert buyer_only not in supplier, buyer_only
    assert "A human at the buyer approved order" in supplier
    assert "What Valio Aimo sees" in supplier
    assert "469363" in supplier and "€1,083.39" in supplier  # what was ordered, and the statements relied on
    assert "384" in supplier[supplier.index('id="reliance"'):supplier.index('id="trail"')]
    assert "The hash chain verifies" in supplier


def test_the_two_views_are_one_click_apart(
    client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    run_example(client, "scenario-2")
    path = f"/orders/{only_order(client, 'agent:allergy-ward').order_id}"

    assert f'href="{path}?view=supplier"' in client.get(path).text
    assert f'href="{path}"' in client.get(path, params={"view": "supplier"}).text
    assert client.get(path, params={"view": "someone-else"}).status_code == 422


def test_a_chain_that_does_not_verify_is_said_in_words(
    client: TestClient, run_example: Post, only_order: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_example(client, "scenario-2")
    order = only_order(client, "agent:allergy-ward")
    service = _service(client)
    real = service.get_audit

    def broken(*args: Any, **kwargs: Any) -> Any:
        view = real(*args, **kwargs)
        chain = ChainVerification(ok=False, checked=3, first_bad_event_id="evt_3", sentence="Event 3 was changed.")
        return view.model_copy(update={"chain": chain})

    monkeypatch.setattr(service, "get_audit", broken)

    page = client.get(f"/orders/{order.order_id}").text

    assert "The hash chain does not verify" in page and "Event 3 was changed." in page
    assert "The hash chain verifies" not in page


def test_an_order_nobody_issued_is_a_404_page_in_both_views(client: TestClient) -> None:
    for params in ({}, {"view": "supplier"}):
        response = client.get("/orders/ord_nobody", params=params)
        assert response.status_code == 404
        assert "ord_nobody" not in response.text
    assert client.get("/orders/" + "x" * 65).status_code == 404


def test_a_waiting_order_points_to_the_approvals_page(
    client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    run_example(client, "scenario-1")
    order = only_order(client)

    page = client.get(f"/orders/{order.order_id}").text

    assert "Waiting for approval" in page
    assert 'action="/approvals/as"' in page and "Demo approver Hanna" in page


def test_a_product_name_with_markup_is_rendered_escaped_on_every_page(
    hostile_client: TestClient, run_example: Post, decide: Post, identities: Callable[..., Any], fakes: Any
) -> None:
    escaped = "&lt;script&gt;alert(&#34;name&#34;)&lt;/script&gt;"
    result = run_example(hostile_client, "scenario-1").text
    approvals = hostile_client.get("/approvals").text
    order_id = _approved_order_of(hostile_client, decide, identities)
    pages = {
        "result": result,
        "approvals": approvals,
        "order": hostile_client.get(f"/orders/{order_id}").text,
        "supplier": hostile_client.get(f"/orders/{order_id}", params={"view": "supplier"}).text,
        "ward": run_example(hostile_client, "scenario-2").text,
    }

    for name, page in pages.items():
        assert fakes.HOSTILE_NAME.strip() not in page, name
        assert "<script>alert" not in page, name
        assert escaped in page, name
    assert result.count(escaped) >= 3  # a line of option 1, the alternative, an excluded product


def _approved_order_of(client: TestClient, decide: Post, identities: Callable[..., Any]) -> str:
    service = _service(client)
    approval = service.list_approvals(identities(client)["human:hotel-purchasing"], ApprovalStatus.PENDING)[0]
    decide(client, approval.approval_id, "APPROVE", option=approval.option_id)
    return approval.order_id
