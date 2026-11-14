"""The order page: the record, the statements it relied on, the audit trail for two readers, the hash chain."""

from __future__ import annotations

import html
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api.sandbox import KITCHEN_APPROVERS
from tta.contracts.audit import ChainVerification
from tta.contracts.common import ApprovalStatus, Unit
from tta.contracts.request import PurchaseRequest, RequestLine

Post = Callable[..., Any]
NOTE = "Agreed with the kitchen on Friday."
SCENARIO_1 = "1,000 litres of lactose-free milk by Monday"
KITCHEN_AGENT = "agent:my-kitchen"
KITCHEN_PURCHASING = "human:my-kitchen-purchasing"  # KITCHEN_APPROVERS[0]


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
    assert "Prepared: confirm to order" in page  # the page's own headline; the gateway's sentence is L3's wording
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
                     "The rules of City Hospital, Ward 4 were checked", "within its authority"):
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
    supplier = html.unescape(client.get(f"/orders/{order_id}", params={"view": "supplier"}).text)

    for buyer_only in ("€750", "Demo approver Hanna", NOTE):
        assert buyer_only in buyer, buyer_only
        assert buyer_only not in supplier, buyer_only
    assert "human:hotel-purchasing" not in supplier and "Hanna" not in supplier
    # Valio reads every rule that fired and its reason (P9b B13), the buyer's amounts masked and a role for a name
    assert "P-01" in supplier and "the amount is not shown" in supplier
    # One person confirms at the hotel (SIMP): Hanna holds the three roles, and the roles stand for her name.
    assert "The buyer's purchasing manager, finance and dietitian approved order" in supplier
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


def _two_signatures(client: TestClient, form_fields: Callable[..., Any], run_text: Post) -> str:
    """Scenario 1 as My kitchen, whose day's limit (€10) asks finance as well as the purchasing manager. Returns
    the offer id."""
    kitchen = {
        **form_fields(client, "/kitchen"), "display_name": "My kitchen", "max_order_net_eur": "750",
        "max_daily_net_eur": "10", "min_fill_ratio": "90", "allergen_strictness": "",
        "substitution_without_approval": "SAME_CATEGORY", "variable_weight": "APPROVAL", "deposits": "APPROVAL",
    }
    assert client.post("/kitchen", data=kitchen, follow_redirects=False).status_code == 303
    result = run_text(client, SCENARIO_1, who=KITCHEN_AGENT)
    return str(result.url).split("offer=")[1].split("#")[0]


def test_after_a_first_signature_the_record_says_who_signed_and_offers_only_a_role_still_needed(
    client: TestClient, form_fields: Callable[..., Any], run_text: Post, act_as: Post, decide: Post
) -> None:
    """A4 H2: after Approve, the record must not look as if Approve did nothing, nor offer the same person again."""
    offer_id = _two_signatures(client, form_fields, run_text)
    act_as(client, KITCHEN_PURCHASING)
    approval = _service(client).list_approvals(KITCHEN_APPROVERS[0], ApprovalStatus.PENDING)[0]
    assert [role.value for role in approval.required_roles] == ["purchasing_manager", "finance"]

    signed = decide(client, approval.approval_id, "APPROVE", option=approval.option_id)
    record = client.get(f"/orders/{approval.order_id}").text
    result = client.get(f"/?offer={offer_id}").text

    assert signed.status_code == 200
    for page in (record, result):
        assert "Approved by the purchasing manager; waiting for finance" in page
        # My kitchen's approvers carry the hotel's one person's name, one per role (`tta.api.sandbox`): the
        # role still needed is offered, and the one already signed is not offered again.
        assert "Decide as Demo approver Hanna, My kitchen (finance)" in page
        assert "Decide as Demo approver Hanna, My kitchen (purchasing manager)" not in page


def test_a_waiting_order_that_nobody_has_signed_still_offers_the_first_role(
    client: TestClient, form_fields: Callable[..., Any], run_text: Post
) -> None:
    offer_id = _two_signatures(client, form_fields, run_text)

    result = client.get(f"/?offer={offer_id}").text

    assert "Sent for approval" in result and "Approved by" not in result
    assert "Decide as Demo approver Hanna, My kitchen (purchasing manager)" in result


def test_valio_reads_how_the_order_was_decided_and_the_products_left_out_with_the_buyers_values_masked(
    client: TestClient, run_example: Post, decide: Post, identities: Callable[..., Any]
) -> None:
    """P9b B13-2: the supplier's page shows the decision as the supplier's trail gives it."""
    order_id = _approved_order(client, run_example, decide, identities)

    supplier = html.unescape(client.get(f"/orders/{order_id}", params={"view": "supplier"}).text)
    decision = supplier[supplier.index('id="decision"'):supplier.index('id="trail"')]

    assert "How the order was decided" in decision
    for rule in ("P-01", "P-03"):
        assert rule in decision, rule
    assert "a rule the buyer set" in decision and "the amount is not shown" in decision
    assert "Signed by the buyer's purchasing manager" in decision
    assert "Products considered and left out" in decision and "464440" in decision  # cannot be delivered
    assert "€750" not in decision and "Hanna" not in decision and NOTE not in decision
    assert "limit amounts and allergen codes are masked" in supplier


class _BeefParser:
    """Reads any sentence as 30 kg of beef chuck 466988, a product sold by variable weight."""

    model_id = "fake-model-1"

    def parse_request(self, text: str, identity: Any) -> Any:
        line = RequestLine(text=text, product_ids=("466988",), quantity=Decimal(30), unit=Unit.KG)
        return PurchaseRequest(needed_by=date(2026, 11, 16), lines=(line,))


def test_a_total_with_a_product_sold_by_weight_reads_as_an_estimate(
    make_client: Callable[..., TestClient], run_text: Post, only_order: Callable[..., Any]
) -> None:
    """P9b Q16-1: Valio Aimo invoices the weight delivered, so the total is not a ceiling."""
    client = make_client(request_parser=_BeefParser())

    result = run_text(client, "30 kg of beef chuck by Monday").text
    order = only_order(client)
    record = client.get(f"/orders/{order.order_id}").text
    kitchen = client.get("/kitchen").text

    estimate = "an estimate: sold by weight, Valio Aimo invoices the weight delivered"
    totals = (  # the page's own lines; the option's summary is the gateway's sentence
        result[result.index('<p class="total">'):result.index('<p class="coverage">')],
        record[record.index('id="lines"'):record.index('id="decision"')],
    )
    assert order.option.totals.is_ceiling
    for total in totals:
        assert "About €" in total and estimate in total
        assert "ceiling" not in total and "never higher" not in total
    assert "is a ceiling" not in kitchen and "Allowed, the total shown as an estimate" in kitchen
