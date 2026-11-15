"""What every page shares: the demo identities, who is chosen, the visitor's order book, the templates, the
form token.

Scores on the 20% "autonomy and controls": a page acts as one demonstration identity (an agent or a human
approver) chosen on the page and kept in a cookie, and calls the gateway's service as that identity. The
service decides what that identity may do, exactly as it does for a bearer token. The service is the one of
the browser session's own order book (task FIX-10, finding 1): read from with `book`, written to with
`own_book`, which builds the book on its first use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from starlette.requests import Request
from starlette.responses import HTMLResponse

from tta.api.sandbox import Sandbox, Sandboxes
from tta.api.service import Gateway
from tta.audit.phrases import moment
from tta.config import Settings
from tta.contracts.common import ApprovalStatus, ApproverRole, DataSource, Identity, OrderStatus
from tta.contracts.order import Approval, Order
from tta.ui import security, view
from tta.ui.run import Problem, RunLog, RunLogs

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"
RECORD_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")  # an id the gateway issued (tta.contracts.order.RecordId)

FORBIDDEN, NOT_FOUND, UNPROCESSABLE, CONFLICT = 403, 404, 422, 409
FORM_OUT_OF_DATE = Problem(
    title="This form is out of date",
    detail="Nothing was changed. Go back, reload the page and try again.",
    status=FORBIDDEN,
)
OWN_BOOK = "Your own demo order book: nothing you do here is seen by other visitors, and it commits nobody."
MODE_LABELS = {
    DataSource.REPLAY: "Replay: recorded Valio Aimo data, clock pinned to the recording",
    DataSource.LIVE: "Live: Valio Aimo mock API. Each offer says where its data came from",
}
# With a demo clock in force (TTA_DEMO_CLOCK, replay only) the clock is not the recording's: the label says which.
DEMO_CLOCK_LABEL = "Replay: recorded Valio Aimo data, demo clock set to {now} (we chose it; the log keeps real time)"


GEMINI = "Gemini"


def model_asked(settings: Settings) -> str | None:
    """The language model that is asked first to read a sentence, by the name the pages give it, as `/healthz`
    names the active reader (`agent_reader`): the model of the OpenAI-compatible endpoint when that provider is set
    up, Gemini when its key is set, and None when no model is asked (the demonstration and the public link)."""
    if not settings.has_agent_model:
        return None
    return settings.tta_agent_model if settings.has_agent_endpoint else GEMINI


def mode_label(settings: Settings) -> str:
    """The line every page shows about where the data comes from and which clock judges the deadlines."""
    if settings.demo_clock is not None:
        return DEMO_CLOCK_LABEL.format(now=moment(settings.demo_clock))
    return MODE_LABELS[settings.tta_mode]


class PageError(Exception):
    """A page that cannot be shown, or a form that cannot be accepted. Rendered as the error page."""

    def __init__(self, problem: Problem) -> None:
        super().__init__(problem.detail)
        self.problem = problem


def page_error(status: int, title: str, detail: str) -> PageError:
    return PageError(Problem(title=title, detail=detail, status=status))


def _environment() -> Environment:
    """Templates with every value escaped. A missing value is an error, never an empty space on the page."""
    environment = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters.update(
        money=view.money, unit_price=view.unit_price, quantity=view.quantity, percent=view.percent,
        day=view.day, moment=view.moment, clock_time=view.clock_time, valid_to=view.valid_to,
        words=view.words, tone=view.tone, run_label=view.run_label, can_be_ordered=view.can_be_ordered,
    )
    environment.globals.update(glyphs=view.GLYPHS)
    return environment


@dataclass(frozen=True)
class Site:
    """The pages' shared state: built once by `create_surface`, read by every route."""

    settings: Settings
    sandboxes: Sandboxes
    identities: tuple[Identity, ...]
    run_logs: RunLogs = field(default_factory=RunLogs)
    templates: Environment = field(default_factory=_environment)

    @property
    def agents(self) -> tuple[Identity, ...]:
        return tuple(identity for identity in self.identities if identity.is_agent)

    @property
    def approvers(self) -> tuple[Identity, ...]:
        return tuple(identity for identity in self.identities if identity.is_approver)

    def book(self, request: Request) -> Sandbox:
        """The order book of this browser session for reading: its own, or the blank one when it has none yet."""
        return self.sandboxes.find(security.book_key(request)) or self.sandboxes.blank()

    def own_book(self, request: Request) -> Sandbox:
        """The order book of this browser session for writing, built empty on its first use."""
        return self.sandboxes.open(security.book_key(request))

    def runs(self, book: Sandbox) -> RunLog:
        """The runs of this book: how each request was read, the agent's steps, the substitutes."""
        return self.run_logs.of(book)

    def agent(self, identity_id: str | None) -> Identity | None:
        return next((identity for identity in self.agents if identity.id == identity_id), None)

    def approver(self, identity_id: str | None) -> Identity | None:
        return next((identity for identity in self.approvers if identity.id == identity_id), None)

    def chosen_agent(self, request: Request) -> Identity:
        """The demo agent of the cookie; the first one when the cookie names nobody."""
        return self.agent(request.cookies.get(security.AGENT_COOKIE)) or self.agents[0]

    def chosen_approver(self, request: Request) -> Identity:
        return self.approver(request.cookies.get(security.APPROVER_COOKIE)) or self.approvers[0]

    def agents_chosen_first(self, request: Request) -> tuple[Identity, ...]:
        """Every demo agent, the chosen one first: an offer or an order is read as the agent of its buyer."""
        chosen = self.chosen_agent(request)
        return (chosen, *(agent for agent in self.agents if agent.id != chosen.id))

    def holders(self, profile_id: str, roles: tuple[ApproverRole, ...]) -> tuple[Identity, ...]:
        """The demo approvers of a buyer who hold one of these roles, in the order the roles are given."""
        return tuple(
            approver for role in roles for approver in self.approvers
            if approver.profile_id == profile_id and role in approver.roles
        )

    def waiting_approval(self, service: Gateway, order: Order | None) -> Approval | None:
        """The approval a waiting order waits on, read as a demo approver of its buyer; `None` for any other order,
        or when no demo approver of its buyer can read it."""
        if order is None or order.status is not OrderStatus.PENDING_APPROVAL or order.approval_id is None:
            return None
        reader = next((one for one in self.approvers if one.profile_id == order.profile_id), None)
        if reader is None:
            return None
        pending = service.list_approvals(reader, ApprovalStatus.PENDING)
        return next((one for one in pending if one.approval_id == order.approval_id), None)

    def decider(self, approval: Approval | None) -> Identity | None:
        """A demo approver who holds a role the approval still needs (A4 H2): never one who has signed already.
        `None` when nobody is still needed, or the approval cannot be read."""
        if approval is None:
            return None
        return next(iter(self.holders(approval.profile_id, approval.roles_missing)), None)

    def check_form(self, request: Request, submitted: str) -> None:
        """Refuse a form that does not carry this session's token (cross-site request forgery)."""
        if not security.token_matches(request, submitted):
            raise PageError(FORM_OUT_OF_DATE)

    def check_session(self, request: Request) -> None:
        """Refuse a form from a browser that holds no form token yet, before its body is read (A3 F5): a form whose
        token is in a large body is checked once more by `check_form` after reading."""
        if security.session_token(request) is None:
            raise PageError(FORM_OUT_OF_DATE)

    def render(self, request: Request, template: str, status: int = 200, **context: Any) -> HTMLResponse:
        """One page. Sets the session's form token when the browser has none yet."""
        token = security.session_token(request)
        is_new = token is None
        token = token or security.new_token()
        html = self.templates.get_template(template).render(
            csrf=token, mode_label=mode_label(self.settings), path=request.url.path, own_book=OWN_BOOK,
            live_model=model_asked(self.settings), **context,
        )
        response = HTMLResponse(html, status_code=status)
        if is_new:
            security.set_session_cookie(response, request, security.csrf_cookie_name(request), token)
        return response

    def render_problem(self, request: Request, problem: Problem) -> HTMLResponse:
        return self.render(request, "error.html", status=problem.status, problem=problem)
