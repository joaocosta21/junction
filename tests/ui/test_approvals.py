"""The human approval panel: why a human is needed, the options, the "order by" time, approve or reject."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape

from tta.contracts.common import AllergenOutcome, AllergenStrictness, ApprovalStatus, OrderStatus, PlacedBy, Unit
from tta.contracts.offer import Offer, OfferOption
from tta.contracts.request import PurchaseRequest, RequestLine

Post = Callable[..., Any]
Identities = Callable[..., Any]
HANNA = "human:hotel-purchasing"
NOTE = 'Use the cheaper one <img src=x onerror="alert(1)">'
MONDAY = date(2026, 11, 16)
# The ward asks for an oat drink it cannot order (it states nothing about milk): the offer is a substitute (P-05).
WARD_SUBSTITUTE = PurchaseRequest(
    needed_by=MONDAY,
    lines=(RequestLine(text="100 L of 473609", product_ids=("473609",), quantity=Decimal(100), unit=Unit.L),),
)
# The hotel excludes milk and gluten for one request: 475224 states nothing about milk and declares oats (P-04).
HOTEL_NO_MILK_NO_GLUTEN = PurchaseRequest(
    needed_by=MONDAY,
    lines=(
        RequestLine(
            text="100 L of 475224, no milk, no gluten", product_ids=("475224",), quantity=Decimal(100), unit=Unit.L,
            exclude_allergens=("AM", "AW"), allergen_strictness=AllergenStrictness.STRICT,
        ),
    ),
)
# The ward asks for a rice drink it can order: the purchasing manager confirms, and nothing asks the dietitian.
WARD_PLAIN = PurchaseRequest(
    needed_by=MONDAY,
    lines=(RequestLine(text="100 L of 473424", product_ids=("473424",), quantity=Decimal(100), unit=Unit.L),),
)
HOSTILE = '<script>alert("trade-off")</script>'
DOUBTFUL = "475224"  # the product of HOTEL_NO_MILK_NO_GLUTEN whose milk is not ruled out


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
    assert "Best confirmed option" in page and "€1,083.39" in page
    assert "Alternative: quantity not confirmed" in page and "€1,010.00" in page
    # Since FIX-O2 a third option completes the confirmed part with a substitute from confirmed stock.
    assert "Alternative: confirmed stock, completed with a substitute" in page and "€2,580.64" in page
    assert page.count('name="option"') == 3
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
    client: TestClient, act_as: Post, decide: Post, identities: Identities, own_book: Callable[..., Any],
    only_order: Callable[..., Any],
) -> None:
    # Since SIMP the hotel's one person holds every role, so the buyer with two people is the ward. Since FIX-P a
    # substitute that is not like for like asks its dietitian too, so the order here is of the product asked for:
    # it asks the purchasing manager (Jussi) alone, and the dietitian (Sari) does not hold that role.
    _order_as(client, identities, own_book, "agent:allergy-ward", WARD_PLAIN)
    approval = _pending(client, identities, "human:ward-purchasing")
    assert [role.value for role in approval.required_roles] == ["purchasing_manager"]
    queue = act_as(client, "human:ward-dietitian").text

    response = decide(client, approval.approval_id, "APPROVE", option=approval.option_id)

    assert "Switch to Demo approver Jussi (purchasing manager, finance)" in queue  # who holds the role that is missing
    assert 'value="APPROVE"' not in queue  # no decision is offered to an approver the gateway would refuse
    assert response.status_code == 403
    assert "still needs the purchasing manager" in response.text
    assert only_order(client, "agent:allergy-ward").status is OrderStatus.PENDING_APPROVAL


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
    # Task FIX-10, finding 6: the card was shown to Hanna; another tab then switched this browser to Sari. (The
    # hotel has one person since SIMP, so the other approver is another buyer's.)
    run_example(client, "scenario-1")
    approval = _pending(client, identities)
    act_as(client, "human:ward-dietitian")

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


# --- FIX-12b: the facts behind the rules, above the buttons -------------------------------------------------

def _order_as(client: TestClient, identities: Identities, own_book: Callable[..., Any], agent_id: str,
              request: PurchaseRequest, product_id: str | None = None) -> Offer:
    """An order placed in this browser's book by the agent, through the gateway's own functions: of the first
    option, or of the option that holds `product_id`."""
    service = own_book(client).service
    agent = identities(client)[agent_id]
    offer = service.create_offer(agent, request)
    option = offer.options[0] if product_id is None else _holding(offer, product_id)
    order = service.place_order(agent, offer.offer_id, option.option_id, f"fix12b-{agent_id}")
    assert order.status is OrderStatus.PENDING_APPROVAL
    return offer


def _holding(offer: Offer, product_id: str) -> OfferOption:
    """The option with a line of this product. Since L2b the safe option comes first, and the product whose
    allergen is not ruled out is the option titled "Alternative: allergen not ruled out"."""
    return next(option for option in offer.options if any(line.product_id == product_id for line in option.lines))


def _before_the_buttons(page: str, text: str) -> bool:
    form = page.index('class="decision"')
    return form < page.index(text) < page.index('value="APPROVE"')


def test_a_substitute_card_shows_what_is_given_up_above_the_buttons(
    client: TestClient, identities: Identities, own_book: Callable[..., Any], act_as: Post
) -> None:
    offer = _order_as(client, identities, own_book, "agent:allergy-ward", WARD_SUBSTITUTE)
    substitute = offer.options[0].lines[0].substitute
    assert substitute is not None

    page = act_as(client, "human:ward-purchasing").text

    assert _before_the_buttons(page, str(escape(substitute.gives_up)))
    assert _before_the_buttons(page, "In place of")
    assert "Claims it loses" not in page  # the rice drink keeps every dietary claim of the oat drink


def test_a_card_sent_to_the_dietitian_shows_the_allergen_findings_above_the_buttons(
    client: TestClient, identities: Identities, own_book: Callable[..., Any], act_as: Post
) -> None:
    offer = _order_as(client, identities, own_book, "agent:hotel-kitchen", HOTEL_NO_MILK_NO_GLUTEN, DOUBTFUL)
    check = _holding(offer, DOUBTFUL).lines[0].allergen_check
    assert check is not None
    to_human = [finding.sentence for finding in check.findings if finding.outcome is AllergenOutcome.TO_HUMAN]

    page = act_as(client, HANNA).text  # one person confirms at the hotel: Hanna holds the dietitian's role too

    assert len(to_human) == 2
    assert all(_before_the_buttons(page, str(escape(sentence))) for sentence in to_human)


def test_an_option_whose_lines_need_no_human_shows_no_trade_off(
    client: TestClient, run_example: Post
) -> None:
    run_example(client, "scenario-1")

    page = client.get("/approvals").text
    first, second, third = (card.split("</label>")[0] for card in page.split('<label class="option ')[1:])

    # Options 1 and 2 hold the products asked for. Since FIX-O2 option 3 holds a substitute, and only it says so.
    for card in (first, second):
        assert "In place of" not in card and "a person must decide" not in card and "trade-off" not in card
    assert 'value="opt_3"' in third and "In place of" in third and "Not a like-for-like replacement" in third


@pytest.mark.parametrize("field", ["gives_up", "claims_lost", "finding"])
def test_the_trade_off_is_escaped(
    field: str, client: TestClient, identities: Identities, own_book: Callable[..., Any], act_as: Post,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = WARD_SUBSTITUTE if field != "finding" else HOTEL_NO_MILK_NO_GLUTEN
    agent = "agent:allergy-ward" if field != "finding" else "agent:hotel-kitchen"
    approver = "human:ward-purchasing" if field != "finding" else HANNA
    offer = _order_as(client, identities, own_book, agent, request, DOUBTFUL if field == "finding" else None)
    service = own_book(client).service
    monkeypatch.setattr(service, "get_offer", lambda _identity, _offer_id: _hostile(offer, field))

    page = act_as(client, approver).text

    assert HOSTILE not in page
    assert _before_the_buttons(page, str(escape(HOSTILE)))


def _hostile(offer: Offer, field: str) -> Offer:
    """The offer with hostile text in one fact the card shows: text from the product file is untrusted."""
    option = _holding(offer, DOUBTFUL) if field == "finding" else offer.options[0]
    line = option.lines[0]
    if field == "finding":
        assert line.allergen_check is not None
        findings = tuple(
            finding.model_copy(update={"sentence": HOSTILE}) for finding in line.allergen_check.findings
        )
        check = line.allergen_check.model_copy(update={"findings": findings})
        changed = line.model_copy(update={"allergen_check": check})
    else:
        assert line.substitute is not None
        value: Any = HOSTILE if field == "gives_up" else (HOSTILE,)
        changed = line.model_copy(update={"substitute": line.substitute.model_copy(update={field: value})})
    return offer.model_copy(update={"options": (option.model_copy(update={"lines": (changed,)}),)})
