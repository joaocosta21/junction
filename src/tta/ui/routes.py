"""`create_surface(context)`: the pages, mounted by the gateway at `/` in the dev and demo environments.

Scores on the 30% "working end-to-end demo" (the visible half of the flow) and on the 20% "autonomy and
controls" (the human approval panel, the readable audit trail). Server-rendered Jinja2, plain CSS, a little
plain JavaScript, no external asset: the venue network may fail.

The pages call the gateway's service and nothing below it, as the demonstration identity chosen on the page,
in an order book of the browser session's own (`context.sandboxes`, task FIX-10): nothing a visitor does is
seen by another, and every visitor starts from an empty book.

    /                 paste a request, choose who is asking, run; the offer and what happened to it
    /approvals        pending approvals as cards; approve (choosing an option) or reject with a note
    /orders/{id}      the order record, the statements it relied on, the audit trail for two readers
    /assumptions      docs/ASSUMPTIONS.md, when it exists
    /kitchen          "Your kitchen": what My kitchen agent may decide alone, in this browser's book (FEAT-1)
    POST /start-again empties the visitor's own order book
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI, Form
from fastapi.exceptions import RequestValidationError
from markupsafe import Markup
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles

from tta.api.hooks import SurfaceContext
from tta.api.sandbox import KITCHEN_IDENTITIES
from tta.config import REPO_ROOT
from tta.contracts.errors import TtaError
from tta.ui import approvals_page, kitchen_page, order_page, request_page, security
from tta.ui.markdown import render as render_markdown
from tta.ui.run import Problem
from tta.ui.security import BookCookie, SecurityHeaders
from tta.ui.site import NOT_FOUND, STATIC_DIR, UNPROCESSABLE, PageError, Site

ASSUMPTIONS_FILE = REPO_ROOT / "docs" / "ASSUMPTIONS.md"
ASSUMPTIONS_NAME = "docs/ASSUMPTIONS.md"
MAX_DOCUMENT_KIB = 512
MAX_DOCUMENT_BYTES = MAX_DOCUMENT_KIB * 1024  # the document is a file like any other: bounded before it is read
SEE_OTHER = 303
NO_IDENTITIES = (
    "The pages act as one of the demonstration identities, and none was given: they need at least one demo "
    "agent and one demo approver (TTA_ENV dev or demo)."
)
NO_BOOKS = "The pages keep each visitor's orders in an order book of its own, and none was given (TTA_ENV dev or demo)."
PAGE_NOT_FOUND = Problem(title="No such page", detail="This address is not a page of the gateway.", status=NOT_FOUND)
FORM_NOT_VALID = Problem(
    title="The form is not valid", detail="A field is missing or not valid. Nothing was changed.", status=UNPROCESSABLE
)
HTTP_TITLES = {405: "This address does not take this kind of request"}
REQUEST_REFUSED = "The gateway did not accept this request."

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Document:
    """The assumptions document as the page shows it: its markup, or why there is none (task FIX-10, 14)."""

    markup: Markup | None = None
    too_large: bool = False  # it is there, and larger than the page shows


def _assumptions() -> Document:
    """The assumptions document: rendered, missing, or too large to show. Each case is said as it is."""
    if not ASSUMPTIONS_FILE.is_file():
        return Document()
    if ASSUMPTIONS_FILE.stat().st_size > MAX_DOCUMENT_BYTES:
        logger.warning("%s is larger than %d bytes and is not shown.", ASSUMPTIONS_NAME, MAX_DOCUMENT_BYTES)
        return Document(too_large=True)
    # `render_markdown` escapes every character of the file; only its own structure is markup.
    return Document(markup=Markup(render_markdown(ASSUMPTIONS_FILE.read_text(encoding="utf-8"))))  # noqa: S704


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
    """The pages as an ASGI application. Raises `ValueError` without the demonstration identities or the
    visitors' order books."""
    identities = tuple(context.demo_identities)
    if not any(one.is_agent for one in identities) or not any(one.is_approver for one in identities):
        raise ValueError(NO_IDENTITIES)
    identities = (*identities, *KITCHEN_IDENTITIES)  # My kitchen's agent and approvers (task FEAT-1)
    if context.sandboxes is None:
        raise ValueError(NO_BOOKS)
    site = Site(settings=context.settings, sandboxes=context.sandboxes, identities=identities)
    app = FastAPI(title="Trusted Trade Agents: pages", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BookCookie)
    app.add_middleware(SecurityHeaders)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    _install_error_pages(app, site)
    request_page.add_routes(app, site)
    approvals_page.add_routes(app, site)
    order_page.add_routes(app, site)
    kitchen_page.add_routes(app, site)

    @app.get("/assumptions", response_class=HTMLResponse)
    def assumptions(request: Request) -> HTMLResponse:
        return site.render(
            request, "assumptions.html", document=_assumptions(), document_name=ASSUMPTIONS_NAME,
            max_document_kib=MAX_DOCUMENT_KIB,
        )

    @app.post("/start-again", response_class=HTMLResponse)
    def start_again(request: Request, csrf: Annotated[str, Form()] = "") -> Response:
        """Empty this browser's order book: its orders, approvals, trail and runs. No other book changes."""
        site.check_form(request, csrf)
        site.sandboxes.drop(security.book_key(request))
        return RedirectResponse("/", status_code=SEE_OTHER)

    return app
