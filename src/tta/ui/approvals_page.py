"""The human approval panel (SPEC sections 8 and 12).

Scores on the 20% "autonomy and controls": what needs human sign-off, who may sign, and what the human sees
before signing. Each card says why a human is needed, shows every option of the offer, the "order by" time,
and lets the approver approve (choosing an option) or reject with a note. The gateway decides whether this
approver may: an agent is refused (F-06), and so is an approver who holds none of the roles still missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI, Form
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from tta.contracts.common import ApprovalStatus, DecisionKind, Identity
from tta.contracts.errors import NotFound, TtaError
from tta.contracts.offer import Offer
from tta.contracts.order import MAX_NOTE_LENGTH, Approval, DecisionRequest
from tta.ui import security
from tta.ui.run import Problem
from tta.ui.site import NOT_FOUND, RECORD_ID, UNPROCESSABLE, Site, page_error

TEMPLATE = "approvals.html"
SEE_OTHER = 303
NO_SUCH_APPROVAL = ("No such approval", "No approval has this id.")
NOT_A_DEMO_APPROVER = ("Choose who decides", "Approvals are decided by one of the demo approvers on this page.")
NOT_A_DECISION = ("Not a decision", "An approval is approved or rejected. Nothing was changed.")
NOT_AN_OPTION = ("Not an option", "Choose one of the options on the card. Nothing was changed.")
NOTE_TOO_LONG = ("The note is too long", f"A note is at most {MAX_NOTE_LENGTH:,} characters. Nothing was changed.")


@dataclass(frozen=True)
class Card:
    """One pending approval as the chosen approver sees it."""

    approval: Approval
    offer: Offer | None  # the offer the options come from; None when it can no longer be read
    can_decide: bool  # the chosen approver holds a role the approval still needs
    holders: tuple[Identity, ...]  # the demo approvers who hold a role that is still missing


def _card(site: Site, approver: Identity, approval: Approval) -> Card:
    try:
        offer: Offer | None = site.service.get_offer(approver, approval.offer_id)
    except NotFound:
        offer = None
    missing = approval.roles_missing
    return Card(
        approval=approval, offer=offer, can_decide=any(role in approver.roles for role in missing),
        holders=site.holders(approval.profile_id, missing),
    )


def _page(site: Site, request: Request, approver: Identity, problem: Problem | None = None) -> HTMLResponse:
    """The queue of the chosen approver's buyer, oldest first. A refusal of the gateway is shown above it."""
    pending = site.service.list_approvals(approver, ApprovalStatus.PENDING)
    cards = tuple(_card(site, approver, approval) for approval in pending)
    status = 200 if problem is None else problem.status
    return site.render(
        request, TEMPLATE, status=status, approver=approver, approvers=site.approvers, cards=cards, problem=problem,
        max_note_length=MAX_NOTE_LENGTH,
    )


def _decision(decision: str, option: str, note: str) -> DecisionRequest:
    """The form as the contract's decision. An option is sent only with an approval."""
    if decision not in (DecisionKind.APPROVE.value, DecisionKind.REJECT.value):
        raise page_error(UNPROCESSABLE, *NOT_A_DECISION)
    if option and not RECORD_ID.fullmatch(option):
        raise page_error(UNPROCESSABLE, *NOT_AN_OPTION)
    if len(note) > MAX_NOTE_LENGTH:
        raise page_error(UNPROCESSABLE, *NOTE_TOO_LONG)
    kind = DecisionKind(decision)
    chosen = option if option and kind is DecisionKind.APPROVE else None
    return DecisionRequest(decision=kind, option_id=chosen, note=note.strip() or None)


def add_routes(app: FastAPI, site: Site) -> None:
    @app.get("/approvals", response_class=HTMLResponse)
    def approvals(request: Request) -> HTMLResponse:
        return _page(site, request, site.chosen_approver(request))

    @app.post("/approvals/as", response_class=HTMLResponse)
    def act_as(
        request: Request, csrf: Annotated[str, Form()] = "", approver: Annotated[str, Form()] = ""
    ) -> Response:
        """Choose the demo approver. Kept in a cookie, never in the address."""
        site.check_form(request, csrf)
        chosen = site.approver(approver)
        if chosen is None:
            raise page_error(UNPROCESSABLE, *NOT_A_DEMO_APPROVER)
        response = RedirectResponse("/approvals", status_code=SEE_OTHER)
        security.set_session_cookie(response, request, security.APPROVER_COOKIE, chosen.id)
        return response

    @app.post("/approvals/{approval_id}/decision", response_class=HTMLResponse)
    def decide(
        request: Request,
        approval_id: str,
        csrf: Annotated[str, Form()] = "",
        decision: Annotated[str, Form()] = "",
        option: Annotated[str, Form()] = "",
        note: Annotated[str, Form()] = "",
    ) -> Response:
        site.check_form(request, csrf)
        if not RECORD_ID.fullmatch(approval_id):
            raise page_error(NOT_FOUND, *NO_SUCH_APPROVAL)
        approver = site.chosen_approver(request)
        asked = _decision(decision, option, note)
        try:
            order = site.service.decide_approval(approver, approval_id, asked)
        except TtaError as error:
            return _page(site, request, approver, problem=Problem.of(error))
        return RedirectResponse(f"/orders/{order.order_id}", status_code=SEE_OTHER)
