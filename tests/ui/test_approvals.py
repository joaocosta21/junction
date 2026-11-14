"""The human approval panel: why a human is needed, the options, the "order by" time, approve or reject."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tta.contracts.common import ApprovalStatus, OrderStatus, PlacedBy

Post = Callable[..., Any]
Identities = Callable[..., Any]
HANNA = "human:hotel-purchasing"
NOTE = 'Use the cheaper one <img src=x onerror="alert(1)">'


def _pending(client: TestClient, identities: Identities, approver_id: str = HANNA) -> Any:
    """The one pending approval of this browser's order book."""
    sandboxes = client.app.state.parts.sandboxes  # type: ignore[attr-defined]
    key = client.cookies.get("tta_book") or client.cookies.get("__Host-tta_book")
    approvals = sandboxes.find(key).service.list_approvals(identities(client)[approver_id], ApprovalStatus.PENDING)
    assert len(approvals) == 1, approvals
    return approvals[0]


def test_approving_on_the_page_changes_the_order_to_ordered(
    client: TestClient, run_example: Post, decide: Post, identities: Identities, only_order: Callable[..., Any]
) -> None:
    run_example(client, "scenario-1")
    assert only_order(client).status is OrderStatus.PENDING_APPROVAL
    approval = _pending(client, identities)

    response = decide(client, approval.approval_id, "APPROVE", option=approval.option_id)

    order = only_order(client)
    assert (order.status, order.placed_by) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)
    assert response.status_code == 200
    assert response.url.path == f"/orders/{order.order_id}"
    assert "Ordered with human approval" in response.text
    assert "Nothing is waiting" in client.get("/approvals").text


def test_a_card_says_why_a_human_is_needed_shows_the_options_and_the_order_by_time(
    client: TestClient, run_example: Post, identities: Identities
) -> None:
    run_example(client, "scenario-1")
    approval = _pending(client, identities)

    page = client.get("/approvals").text

    assert approval.order_id in page
    assert "above the €750 limit per order" in page  # why
    assert "Needs: purchasing manager" in page
    assert "Order by Sunday 15 Nov 2026 at 17:00" in page
    assert "Best confirmed option" in page and "€2,580.64" in page
    assert "Alternative: quantity not confirmed" in page and "€1,010.00" in page
    assert page.count('name="option"') == 2
    assert 'value="opt_1" checked' in page  # the option the agent proposed
    assert 'value="APPROVE"' in page and 'value="REJECT"' in page and 'name="note"' in page


def test_the_approver_may_pick_another_option_of_the_same_offer(
    client: TestClient, run_example: Post, decide: Post, identities: Identities, only_order: Callable[..., Any]
) -> None:
    run_example(client, "scenario-1")
    approval = _pending(client, identities)

    page = decide(client, approval.approval_id, "APPROVE", option="opt_2", note="Cheaper, and we can wait.").text

    order = only_order(client)
    assert (order.status, order.option_id) == (OrderStatus.ORDERED, "opt_2")
    assert "€1,010.00" in page
    assert "Cheaper, and we can wait." in page  # the note, in the buyer's trail


def test_rejecting_with_a_note_rejects_the_order_and_the_note_is_escaped(
    client: TestClient, run_example: Post, decide: Post, identities: Identities, only_order: Callable[..., Any]
) -> None:
    run_example(client, "scenario-1")
    approval = _pending(client, identities)

    page = decide(client, approval.approval_id, "REJECT", option=approval.option_id, note=NOTE).text

    assert only_order(client).status is OrderStatus.REJECTED
    assert "Rejected" in page
    assert "<img src=x" not in page
    assert "Use the cheaper one &lt;img src=x" in page


def test_the_approver_is_chosen_on_the_page_and_kept_in_a_cookie(
    client: TestClient, run_example: Post, act_as: Post
) -> None:
    run_example(client, "scenario-1")

    as_ward = act_as(client, "human:ward-dietitian")

    assert as_ward.status_code == 200 and as_ward.url.path == "/approvals"
    assert as_ward.url.query == b""
    assert client.cookies.get("tta_approver") == "human:ward-dietitian"
    assert "Nothing is waiting" in as_ward.text  # another buyer's approvals are not shown
    assert "above the €750 limit per order" not in as_ward.text
    assert "above the €750 limit per order" in act_as(client, HANNA).text


def test_an_approver_without_the_role_is_refused_and_the_page_says_who_can_decide(
    client: TestClient, run_example: Post, act_as: Post, decide: Post, identities: Identities,
    only_order: Callable[..., Any],
) -> None:
    run_example(client, "scenario-1")
    approval = _pending(client, identities)
    queue = act_as(client, "human:hotel-finance").text

    response = decide(client, approval.approval_id, "APPROVE", option=approval.option_id)

    assert "Switch to Demo approver Hanna (purchasing manager)" in queue  # who holds the role that is missing
    assert 'value="APPROVE"' not in queue  # no decision is offered to an approver the gateway would refuse
    assert response.status_code == 403
    assert "still needs the purchasing manager" in response.text
    assert only_order(client).status is OrderStatus.PENDING_APPROVAL


def test_a_decision_without_the_form_token_is_refused_and_nothing_changes(
    client: TestClient, run_example: Post, identities: Identities, only_order: Callable[..., Any]
) -> None:
    run_example(client, "scenario-1")
    approval = _pending(client, identities)
    path = f"/approvals/{approval.approval_id}/decision"

    missing = client.post(path, data={"decision": "APPROVE", "option": "opt_1"})
    wrong = client.post(path, data={"decision": "APPROVE", "option": "opt_1", "csrf": "x" * 43})

    assert (missing.status_code, wrong.status_code) == (403, 403)
    assert "Nothing was changed" in wrong.text
    assert only_order(client).status is OrderStatus.PENDING_APPROVAL


def test_an_approval_nobody_issued_is_a_404_page(client: TestClient, decide: Post) -> None:
    response = decide(client, "apr_nobody", "APPROVE", option="opt_1")

    assert response.status_code == 404
    assert "apr_nobody" not in response.text


def test_a_decision_that_is_neither_approve_nor_reject_is_refused(
    client: TestClient, run_example: Post, decide: Post, identities: Identities, only_order: Callable[..., Any]
) -> None:
    run_example(client, "scenario-1")
    approval = _pending(client, identities)

    assert decide(client, approval.approval_id, "MAYBE", option="opt_1").status_code == 422
    assert decide(client, approval.approval_id, "APPROVE", option="opt 1; drop").status_code == 422
    assert decide(client, approval.approval_id, "REJECT", note="n" * 1001).status_code == 422
    assert only_order(client).status is OrderStatus.PENDING_APPROVAL


def test_only_a_demo_approver_can_be_chosen_on_the_approvals_page(client: TestClient, act_as: Post) -> None:
    for chosen in ("agent:hotel-kitchen", "supplier:valio-aimo", "human:made-up"):
        assert act_as(client, chosen).status_code == 422, chosen
    assert client.cookies.get("tta_approver") is None


def test_the_result_of_a_request_leads_to_the_approver_who_can_decide(
    client: TestClient, run_example: Post
) -> None:
    page = run_example(client, "scenario-1").text
    outcome = page[page.index('id="outcome"'):]

    assert 'action="/approvals/as"' in outcome
    assert 'name="approver" value="human:hotel-purchasing"' in outcome
    assert "Demo approver Hanna" in outcome


def test_a_card_decided_after_the_approver_was_changed_in_another_tab_is_refused(
    client: TestClient, run_example: Post, decide: Post, identities: Identities, act_as: Post,
    only_order: Callable[..., Any],
) -> None:
    # Task FIX-10, finding 6: the card was shown to Hanna; another tab then switched this browser to Mikko.
    run_example(client, "scenario-1")
    approval = _pending(client, identities)
    act_as(client, "human:hotel-finance")

    switched = decide(client, approval.approval_id, "APPROVE", option=approval.option_id, shown_to=HANNA)
    without = decide(client, approval.approval_id, "APPROVE", option=approval.option_id, shown_to="")

    assert (switched.status_code, without.status_code) == (409, 409)
    assert "changed in another tab" in switched.text and "Nothing was changed" in switched.text
    assert only_order(client).status is OrderStatus.PENDING_APPROVAL
    assert _pending(client, identities).decisions == ()


def test_the_decision_form_carries_the_approver_it_was_shown_to(
    client: TestClient, run_example: Post
) -> None:
    run_example(client, "scenario-1")

    page = client.get("/approvals").text
    form = page[page.index('class="decision"'):]

    assert 'name="shown_to" value="human:hotel-purchasing"' in form
