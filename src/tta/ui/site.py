"""What every page shares: the demo identities, who is chosen, the templates, the form token.

Scores on the 20% "autonomy and controls": a page acts as one demonstration identity (an agent or a human
approver) chosen on the page and kept in a cookie, and calls the gateway's service as that identity. The
service decides what that identity may do, exactly as it does for a bearer token.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from starlette.requests import Request
from starlette.responses import HTMLResponse

from tta.api.service import Gateway
from tta.config import Settings
from tta.contracts.common import ApproverRole, DataSource, Identity
from tta.ui import security, view
from tta.ui.run import Problem, RunLog

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
MODE_LABELS = {
    DataSource.REPLAY: "Replay: recorded Valio Aimo data, clock pinned to the recording",
    DataSource.LIVE: "Live: Valio Aimo mock API. Each offer says where its data came from",
}


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
        words=view.words, tone=view.tone,
    )
    environment.globals.update(glyphs=view.GLYPHS)
    return environment


@dataclass(frozen=True)
class Site:
    """The pages' shared state: built once by `create_surface`, read by every route."""

    settings: Settings
    service: Gateway
    identities: tuple[Identity, ...]
    runs: RunLog = field(default_factory=RunLog)
    templates: Environment = field(default_factory=_environment)

    @property
    def agents(self) -> tuple[Identity, ...]:
        return tuple(identity for identity in self.identities if identity.is_agent)

    @property
    def approvers(self) -> tuple[Identity, ...]:
        return tuple(identity for identity in self.identities if identity.is_approver)

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

    def check_form(self, request: Request, submitted: str) -> None:
        """Refuse a form that does not carry this session's token (cross-site request forgery)."""
        if not security.token_matches(request, submitted):
            raise PageError(FORM_OUT_OF_DATE)

    def render(self, request: Request, template: str, status: int = 200, **context: Any) -> HTMLResponse:
        """One page. Sets the session's form token when the browser has none yet."""
        token = security.session_token(request)
        is_new = token is None
        token = token or security.new_token()
        html = self.templates.get_template(template).render(
            csrf=token, mode_label=MODE_LABELS[self.settings.tta_mode], path=request.url.path, **context
        )
        response = HTMLResponse(html, status_code=status)
        if is_new:
            security.set_session_cookie(response, request, security.csrf_cookie_name(request), token)
        return response

    def render_problem(self, request: Request, problem: Problem) -> HTMLResponse:
        return self.render(request, "error.html", status=problem.status, problem=problem)
