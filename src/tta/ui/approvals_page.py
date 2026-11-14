"""The human approval panel (SPEC sections 8 and 12).

Scores on the 20% "autonomy and controls": what needs human sign-off, who may sign, and what the human sees
before signing. Each card says why a human is needed, shows every option of the offer, the "order by" time,
and lets the approver approve (choosing an option) or reject with a note. The gateway decides whether this
approver may: an agent is refused (F-06), and so is an approver who holds none of the roles still missing.

Each line of an option shows the facts behind the rules that name it, above the buttons: the allergen findings that
send it to a human and, for a substitute, what the buyer gives up and the claims it loses (FIX-12b, 4).

A card's form says whom it was shown to. When another tab of the same browser has switched the approver in
the meantime, the decision is refused rather than signed by someone who never saw the card (FIX-10, 6).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI, Form
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from tta.api.service import Gateway
from tta.contracts.common import AllergenOutcome, ApprovalStatus, DecisionKind, Identity
from tta.contracts.errors import NotFound, TtaError
from tta.contracts.offer import Offer, OfferLine, OfferOption, SubstituteInfo
from tta.contracts.order import MAX_NOTE_LENGTH, Approval, DecisionRequest
from tta.ui import security
from tta.ui.run import Problem
from tta.ui.site import CONFLICT, NOT_FOUND, RECORD_ID, UNPROCESSABLE, Site, page_error

TEMPLATE = "approvals.html"
SEE_OTHER = 303
NO_SUCH_APPROVAL = ("No such approval", "No approval has this id.")
NOT_A_DEMO_APPROVER = ("Choose who decides", "Approvals are decided by one of the demo approvers on this page.")
NOT_A_DECISION = ("Not a decision", "An approval is approved or rejected. Nothing was changed.")
NOT_AN_OPTION = ("Not an option", "Choose one of the options on the card. Nothing was changed.")
NOTE_TOO_LONG = ("The note is too long", f"A note is at most {MAX_NOTE_LENGTH:,} characters. Nothing was changed.")
APPROVER_CHANGED = "The approver was changed in another tab"
APPROVER_CHANGED_DETAIL = (
    "This card was shown to {shown}, and this browser now decides as {now}. Nothing was changed: read the card "
    "again below and decide as the approver it shows."
)
SOMEONE_ELSE = "another approver"


@dataclass(frozen=True)
class LineFacts:
    """One line of an option with what the approver accepts by signing it. Every text is data, escaped on the page."""

    line: OfferLine
    to_human: tuple[str, ...]  # the allergen findings that send the line to a human (a dietitian)
    substitute: SubstituteInfo | None  # what a substitute gives up and the claims it loses


@dataclass(frozen=True)
class Card:
    """One pending approval as the chosen approver sees it."""

    approval: Approval
    offer: Offer | None  # the offer the options come from; None when it can no longer be read
    can_decide: bool  # the chosen approver holds a role the approval still needs
    holders: tuple[Identity, ...]  # the demo approvers who hold a role that is still missing
    lines: Mapping[str, tuple[LineFacts, ...]]  # by option id: each line of the option with its facts


def line_facts(option: OfferOption) -> tuple[LineFacts, ...]:
    """The facts behind the rules that name each line: the reasons name the rules, these are what they read."""
    return tuple(
        LineFacts(line=line, to_human=_to_human(line), substitute=line.substitute) for line in option.lines
    )


def _to_human(line: OfferLine) -> tuple[str, ...]:
    check = line.allergen_check
    if check is None:
        return ()
    return tuple(finding.sentence for finding in check.findings if finding.outcome is AllergenOutcome.TO_HUMAN)


def _card(site: Site, service: Gateway, approver: Identity, approval: Approval) -> Card:
    try:
        offer: Offer | None = service.get_offer(approver, approval.offer_id)
    except NotFound:
        offer = None
    missing = approval.roles_missing
    options = offer.options if offer is not None else ()
    return Card(
        approval=approval, offer=offer, can_decide=any(role in approver.roles for role in missing),
        holders=site.holders(approval.profile_id, missing),
        lines={option.option_id: line_facts(option) for option in options},
    )


def _page(site: Site, request: Request, approver: Identity, problem: Problem | None = None) -> HTMLResponse:
    """The queue of the chosen approver's buyer in this browser's book, oldest first. A refusal of the gateway
    is shown above it."""
    service = site.book(request).service
    pending = service.list_approvals(approver, ApprovalStatus.PENDING)
    cards = tuple(_card(site, service, approver, approval) for approval in pending)
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


def _changed_in_another_tab(site: Site, shown_to: str, now: Identity) -> Problem:
    shown = site.approver(shown_to)
    detail = APPROVER_CHANGED_DETAIL.format(
        shown=shown.display_name if shown is not None else SOMEONE_ELSE, now=now.display_name
    )
    return Problem(title=APPROVER_CHANGED, detail=detail, status=CONFLICT)


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
        shown_to: Annotated[str, Form()] = "",
    ) -> Response:
        site.check_form(request, csrf)
        if not RECORD_ID.fullmatch(approval_id):
            raise page_error(NOT_FOUND, *NO_SUCH_APPROVAL)
        approver = site.chosen_approver(request)
        asked = _decision(decision, option, note)
        if shown_to != approver.id:
            return _page(site, request, approver, problem=_changed_in_another_tab(site, shown_to, approver))
        try:
            order = site.own_book(request).service.decide_approval(approver, approval_id, asked)
        except TtaError as error:
            return _page(site, request, approver, problem=Problem.of(error))
        return RedirectResponse(f"/orders/{order.order_id}", status_code=SEE_OTHER)
