"""`create_surface(context)`: the pages, mounted by the gateway at `/` in the dev and demo environments.

Scores on the 30% "working end-to-end demo" (the visible half of the flow) and on the 20% "autonomy and
controls" (the human approval panel, the readable audit trail). Server-rendered Jinja2, plain CSS, a little
plain JavaScript, no external asset: the venue network may fail.

The pages call `context.service` and nothing below it, as the demonstration identity chosen on the page.

    /                 paste a request, choose who is asking, run; the offer and what happened to it
    /approvals        pending approvals as cards; approve (choosing an option) or reject with a note
    /orders/{id}      the order record, the statements it relied on, the audit trail for two readers
    /assumptions      docs/ASSUMPTIONS.md, when it exists
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from markupsafe import Markup
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.staticfiles import StaticFiles

from tta.api.hooks import SurfaceContext
from tta.config import REPO_ROOT
from tta.contracts.errors import TtaError
from tta.ui import approvals_page, order_page, request_page
from tta.ui.markdown import render as render_markdown
from tta.ui.run import Problem
from tta.ui.security import SecurityHeaders
from tta.ui.site import NOT_FOUND, STATIC_DIR, UNPROCESSABLE, PageError, Site

ASSUMPTIONS_FILE = REPO_ROOT / "docs" / "ASSUMPTIONS.md"
ASSUMPTIONS_NAME = "docs/ASSUMPTIONS.md"
MAX_DOCUMENT_BYTES = 512 * 1024  # the document is a file like any other: bounded before it is read
NO_IDENTITIES = (
    "The pages act as one of the demonstration identities, and none was given: they need at least one demo "
    "agent and one demo approver (TTA_ENV dev or demo)."
)
PAGE_NOT_FOUND = Problem(title="No such page", detail="This address is not a page of the gateway.", status=NOT_FOUND)
FORM_NOT_VALID = Problem(
    title="The form is not valid", detail="A field is missing or not valid. Nothing was changed.", status=UNPROCESSABLE
)
HTTP_TITLES = {405: "This address does not take this kind of request"}
REQUEST_REFUSED = "The gateway did not accept this request."

logger = logging.getLogger(__name__)


def _assumptions() -> Markup | None:
    """The assumptions document as markup, or `None` when it is not there (or is not a document we show)."""
    if not ASSUMPTIONS_FILE.is_file():
        return None
    if ASSUMPTIONS_FILE.stat().st_size > MAX_DOCUMENT_BYTES:
        logger.warning("%s is larger than %d bytes and is not shown.", ASSUMPTIONS_NAME, MAX_DOCUMENT_BYTES)
        return None
    # `render_markdown` escapes every character of the file; only its own structure is markup.
    return Markup(render_markdown(ASSUMPTIONS_FILE.read_text(encoding="utf-8")))  # noqa: S704


def _install_error_pages(app: FastAPI, site: Site) -> None:
    """Every refusal as a page: a title, one sentence, the status. Never the address or the text sent."""

    @app.exception_handler(PageError)
    def page_error(request: Request, error: PageError) -> HTMLResponse:
        return site.render_problem(request, error.problem)

    @app.exception_handler(TtaError)
    def gateway_error(request: Request, error: TtaError) -> HTMLResponse:
        return site.render_problem(request, Problem.of(error))

    @app.exception_handler(RequestValidationError)
    def not_valid(request: Request, error: RequestValidationError) -> HTMLResponse:
        return site.render_problem(request, FORM_NOT_VALID)

    @app.exception_handler(HTTPException)
    def http_error(request: Request, error: HTTPException) -> HTMLResponse:
        if error.status_code == NOT_FOUND:
            return site.render_problem(request, PAGE_NOT_FOUND)
        title = HTTP_TITLES.get(error.status_code, REQUEST_REFUSED)
        return site.render_problem(request, Problem(title=title, detail=REQUEST_REFUSED, status=error.status_code))


def create_surface(context: SurfaceContext) -> FastAPI:
    """The pages as an ASGI application. Raises `ValueError` without the demonstration identities."""
    site = Site(settings=context.settings, service=context.service, identities=tuple(context.demo_identities))
    if not site.agents or not site.approvers:
        raise ValueError(NO_IDENTITIES)
    app = FastAPI(title="Trusted Trade Agents: pages", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SecurityHeaders)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    _install_error_pages(app, site)
    request_page.add_routes(app, site)
    approvals_page.add_routes(app, site)
    order_page.add_routes(app, site)

    @app.get("/assumptions", response_class=HTMLResponse)
    def assumptions(request: Request) -> HTMLResponse:
        return site.render(request, "assumptions.html", document=_assumptions(), document_name=ASSUMPTIONS_NAME)

    return app
