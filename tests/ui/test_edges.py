"""What the pages do when the gateway refuses, when a form is sent twice at once, when data is not as expected."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.contracts.audit import Actor, ActorKind, AuditView, AuditViewEvent, ChainVerification
from tta.contracts.common import AuditReader, OrderStatus
from tta.contracts.errors import NotFound, PolicyBlocked, RateLimited
from tta.ui import request_page, routes, view
from tta.ui.markdown import render
from tta.ui.order_page import supplier_record
from tta.ui.security import SecurityHeaders

Post = Callable[..., Any]


def _raising(error: Exception) -> Callable[..., Any]:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise error

    return refuse


def test_an_order_the_policy_blocks_is_shown_as_not_placed_next_to_the_offer(
    client: TestClient, run_example: Post, own_book: Callable[..., Any], orders: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = PolicyBlocked("A line declares an allergen the buyer excludes (F-02).")
    monkeypatch.setattr(own_book(client).service, "place_order", _raising(blocked))

    response = run_example(client, "scenario-2")
    outcome = response.text[response.text.index('id="outcome"'):]

    assert response.status_code == 200 and "Best confirmed option" in response.text
    assert "No order was placed" in outcome
    assert "A line declares an allergen the buyer excludes (F-02)." in outcome
    assert "Ordered by the agent" not in response.text
    assert orders(client, "agent:allergy-ward") == ()


def test_substitutes_the_gateway_refuses_to_list_do_not_hide_the_offer(
    client: TestClient, run_example: Post, own_book: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    refused = _raising(RateLimited("Too many searches right now."))
    monkeypatch.setattr(own_book(client).service, "find_substitutes", refused)

    page = run_example(client, "scenario-3").text

    assert "Too many searches right now." in page[page.index('id="substitutes"'):page.index('id="excluded"')]
    assert "With a substitute" in page and "Sent for approval" in page


def test_a_refusal_of_the_gateway_while_a_page_is_built_is_an_error_page(
    client: TestClient, own_book: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(own_book(client).service, "list_approvals", _raising(RateLimited("Too many calls right now.")))

    response = client.get("/approvals")

    assert response.status_code == 429
    assert "Too many requests" in response.text and "Too many calls right now." in response.text
    assert "content-security-policy" in response.headers


def test_an_example_nobody_wrote_is_refused(client: TestClient, run_example: Post) -> None:
    assert run_example(client, "scenario-9").status_code == 422


def test_a_file_where_a_text_belongs_is_refused_as_a_form_that_is_not_valid(
    client: TestClient, form_fields: Callable[..., Any]
) -> None:
    fields = form_fields(client)

    response = client.post("/run", data=fields, files={"text": ("request.txt", b"1,000 litres", "text/plain")})

    assert response.status_code == 422
    assert "The form is not valid" in response.text and "Nothing was changed" in response.text


def test_a_form_sent_again_while_it_is_still_running_runs_once(
    client: TestClient, form_fields: Callable[..., Any], only_order: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fields = {**form_fields(client), "example": "scenario-2"}
    real, second = request_page.run_request, []

    def run_and_click_again(*args: Any, **kwargs: Any) -> Any:
        second.append(client.post("/run", data=fields))  # the double click arrives while the first still runs
        return real(*args, **kwargs)

    monkeypatch.setattr(request_page, "run_request", run_and_click_again)

    first = client.post("/run", data=fields)

    assert first.status_code == 200 and "Sent for approval" in first.text
    assert [response.status_code for response in second] == [409]
    assert "already running" in second[0].text
    assert only_order(client, "agent:allergy-ward").status is OrderStatus.PENDING_APPROVAL


def test_a_run_that_breaks_on_an_unexpected_fault_is_not_run_again_by_the_same_form(
    client: TestClient, form_fields: Callable[..., Any], orders: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Whether the fault came before or after an order, a resend must not order again (task FIX-10, finding 4).
    fields = {**form_fields(client), "example": "scenario-2"}
    real = request_page.run_request
    monkeypatch.setattr(request_page, "run_request", _raising(RuntimeError("a fault nobody expected")))
    with pytest.raises(RuntimeError):
        client.post("/run", data=fields)
    monkeypatch.setattr(request_page, "run_request", real)

    again = client.post("/run", data=fields)

    assert again.status_code == 200 and "stopped on an unexpected fault" in again.text
    assert "a fault nobody expected" not in again.text
    assert orders(client, "agent:allergy-ward") == ()
    fresh = client.post("/run", data={**form_fields(client), "example": "scenario-2"})  # a new form runs
    assert "Sent for approval" in fresh.text


def test_a_card_whose_offer_can_no_longer_be_read_still_takes_a_decision(
    client: TestClient, run_example: Post, book: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_example(client, "scenario-1")
    monkeypatch.setattr(book(client).service, "get_offer", _raising(NotFound("No offer has this id.")))

    page = client.get("/approvals").text

    assert "can no longer be read" in page
    assert 'value="APPROVE"' in page and 'name="option"' not in page


def test_an_approval_id_that_is_not_an_id_is_a_404(client: TestClient, form_fields: Callable[..., Any]) -> None:
    fields = form_fields(client, "/approvals")

    response = client.post("/approvals/not an id!/decision", data={"csrf": fields["csrf"], "decision": "APPROVE"})

    assert response.status_code == 404


def test_a_document_too_large_to_be_the_assumptions_page_is_not_shown(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = tmp_path / "ASSUMPTIONS.md"
    document.write_text("# Far too long\n" + "x" * routes.MAX_DOCUMENT_BYTES, encoding="utf-8")
    monkeypatch.setattr(routes, "ASSUMPTIONS_FILE", document)

    page = client.get("/assumptions").text

    assert "Far too long" not in page and "has not been written yet" not in page
    assert "larger than 512 KiB" in page and "docs/ASSUMPTIONS.md" in page


def _view(*facts: dict[str, Any]) -> AuditView:
    events = tuple(
        AuditViewEvent(
            id=f"evt_{number}", type="tta.v1.order.confirmed", time=datetime(2026, 11, 14, tzinfo=UTC),
            actor=Actor(kind=ActorKind.SYSTEM, id="gateway"), sentence="A sentence.", facts=fact, hash="0" * 64,
        )
        for number, fact in enumerate(facts)
    )
    chain = ChainVerification(ok=True, checked=len(events), sentence="Intact.")
    return AuditView(reader=AuditReader.SUPPLIER, events=events, chain=chain)


def test_the_suppliers_record_is_the_newest_state_of_the_order_in_its_view_of_the_trail() -> None:
    older = {"order": {"order_id": "ord_1", "status": "PENDING_APPROVAL"}}
    newer = {"order": {
        "order_id": "ord_1", "status": "ORDERED", "placed_by": "HUMAN_APPROVAL", "a_field_added_later": 1,
        "reliance": [{"product_id": "469363", "unit_net_price": 2.48, "available_amount": None}],
        "option": {"lines": [{"product_id": "469363", "quantity": 384.0, "net": 952.32}], "totals": {"net": 952.32}},
    }}

    record = supplier_record(_view(older, newer, {"approval": {"status": "APPROVED"}}))

    assert record is not None and record.status is OrderStatus.ORDERED
    assert record.reliance[0].unit_net_price == Decimal("2.48") and record.reliance[0].available_amount is None
    assert record.option is not None and record.option.lines[0].net == Decimal("952.32")


def test_a_trail_without_a_readable_order_gives_no_record_rather_than_a_guess() -> None:
    assert supplier_record(_view()) is None
    assert supplier_record(_view({"offer": {}}, {"order": "not an object"})) is None
    assert supplier_record(_view({"order": {"order_id": "ord_1", "status": "SOMETHING_ELSE"}})) is None


def test_the_order_page_says_so_when_the_suppliers_view_carries_no_record(
    client: TestClient, run_example: Post, only_order: Callable[..., Any], book: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_example(client, "scenario-2")
    order = only_order(client, "agent:allergy-ward")
    monkeypatch.setattr(book(client).service, "get_audit", lambda *args, **kwargs: _view())

    page = client.get(f"/orders/{order.order_id}", params={"view": "supplier"}).text

    assert "carries no state of this order that can be read" in page
    assert "No statement is recorded" in page and "The trail has no event for this order" in page


def test_nested_lists_follow_the_indentation() -> None:
    html = render("- fixed rules\n    - F-01\n    - F-02\n- profile rules\n\n1. first\n- another kind\n")

    assert "<ul><li>fixed rules<ul><li>F-01</li><li>F-02</li></ul></li><li>profile rules</li></ul>" in html
    assert "<ol><li>first</li></ol>\n<ul><li>another kind</li></ul>" in html
    assert render("- an item\nplain text right after") == "<ul><li>an item</li></ul>\n<p>plain text right after</p>"


def test_what_is_not_stated_is_written_as_not_stated() -> None:
    for written in (view.unit_price(None), view.percent(None), view.clock_time(None), view.money(None)):
        assert written == "not stated"
    assert view.moment(datetime(2026, 11, 14, 2, 52)) == "Saturday 14 Nov 2026 at 02:52 (no time zone stated)"
    assert view.quantity(Decimal("0.000")) == "0"


def test_the_header_middleware_leaves_what_is_not_a_request_alone() -> None:
    seen: list[str] = []

    async def inner(scope: Any, receive: Any, send: Any) -> None:
        seen.append(scope["type"])

    asyncio.run(SecurityHeaders(inner)({"type": "lifespan"}, None, None))  # type: ignore[arg-type]

    assert seen == ["lifespan"]

