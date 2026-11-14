"""`create_app(settings)`: the FastAPI application (SPEC section 2, tasks T09 and FIX-8).

Scores on the 30% "working end-to-end demo" (one process serves the whole flow) and on the 15% "open,
documented standards" (OpenAPI 3.1 generated from the typed models, problem details for every error).

    uvicorn --factory tta.api:create_app
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from starlette.routing import Match, Mount
from starlette.types import ASGIApp, Scope

from tta.api import docs, hooks
from tta.api.customer_routes import customer_router
from tta.api.discovery import discovery
from tta.api.docs_pages import install_docs_pages
from tta.api.errors import install_error_handlers
from tta.api.examples import build_examples
from tta.api.headers import SecurityHeadersMiddleware, is_api_path
from tta.api.health import public
from tta.api.keys import keys
from tta.api.limits import ClientKeyMiddleware
from tta.api.menu_routes import menu_router
from tta.api.routes import router
from tta.api.standing_routes import include_standing_routes, with_set_up_limits
from tta.api.uploads import UploadBodyLimit
from tta.api.wiring import Parts, build_parts, close_each
from tta.config import Settings, get_settings
from tta.contracts.errors import TtaError
from tta.standing import StandingOrders
from tta.standing.demo import load_customer_standing_orders

MCP_PATH = "/mcp"
PAGES_PATH = "/"
MCP_SURFACE = "mcp"
PAGES_SURFACE = "pages"

logger = logging.getLogger(__name__)


class _McpMount(Mount):
    """The MCP endpoint is the root of the mounted surface. A mount takes `/mcp/` and what is under it; this
    one also takes the exact path `/mcp`, as that same root: an MCP host is given `https://<host>/mcp`. There
    is no redirect, because a redirected POST is lost behind a proxy that ends TLS, and the pages never see
    the path."""

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        if scope["type"] != "http" or scope["path"] != self.path:
            return super().matches(scope)
        root = self.path + "/"
        match, child = super().matches({**scope, "path": root})
        # The surface is handed the path with the slash, so that its own router finds its root.
        return match, {**child, "path": root, "raw_path": root.encode()}


class _PagesMount(Mount):
    """The pages take every path nothing else has taken, except the API's (`/v1` and all under it): a path
    or a method the API does not have stays the API's to answer, as a problem document and not as a page."""

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        if scope["type"] == "http" and is_api_path(scope["path"]):
            return Match.NONE, {}
        return super().matches(scope)


def _surfaces(parts: Parts, standing: StandingOrders) -> dict[str, ASGIApp]:
    """The optional surfaces that exist, by name. The pages act as a demonstration identity chosen on the
    page, with no token, in an order book of the visitor's own, so they are mounted only where those
    identities and books exist: in dev and demo."""
    demo = parts.settings.is_demo_environment
    context = hooks.SurfaceContext(
        settings=parts.settings, service=parts.service, identify=parts.tokens.identify,
        demo_identities=parts.tokens.identities if demo else (), sandboxes=parts.sandboxes if demo else None,
        standing=standing, signer=parts.signer,
    )
    found: dict[str, ASGIApp] = {}
    mcp = hooks.surface(hooks.MCP_MODULE, context)
    if mcp is not None:
        found[MCP_SURFACE] = mcp
    pages = hooks.surface(hooks.PAGES_MODULE, context) if demo else None
    if pages is not None:
        found[PAGES_SURFACE] = pages
    return found


def _lifespan(parts: Parts, surfaces: dict[str, ASGIApp]) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """A mounted application's own lifespan does not run by itself; the MCP session manager needs it.
        The examples of `/openapi.json` are built here, once, in a worker thread: a request for the document
        runs no scenario on the event loop. When the gateway stops, the database and the live client are closed."""
        async with AsyncExitStack() as stack:
            stack.callback(parts.close)
            app.state.examples = await run_in_threadpool(build_examples, parts)
            for surface in surfaces.values():
                context = getattr(getattr(surface, "router", None), "lifespan_context", None)
                if context is not None:
                    await stack.enter_async_context(context(surface))
            yield

    return lifespan


STANDING_ORDERS_NOT_SET_UP = "the standing orders of {profile_id} were not set up at start"


def load_customers_standing_orders(parts: Parts, standing: StandingOrders) -> tuple[str, ...]:
    """In dev and demo (and unless `TTA_CUSTOMER_STANDING_ORDERS` is false), set up the standing orders of each
    demo agent's customer file in the shared book, with their synthetic past renewals (P1 C3): the trend and rule
    P-08 then have a history to read. Once: an order that is there already, from an earlier start on the same
    database, is left as it is. A customer whose history cannot be built (the recording holds no price for a
    product) is logged and skipped: the gateway starts without that customer's standing orders. Returns one reason
    per customer skipped, for `/healthz`."""
    if not parts.settings.is_demo_environment or not parts.settings.tta_customer_standing_orders:
        return ()
    skipped: list[str] = []
    for identity in parts.tokens.identities:
        if not identity.is_agent:
            continue
        try:
            load_customer_standing_orders(standing, identity, parts.replay)
        except TtaError as error:
            logger.warning("The standing orders of %s were not set up at start: %s", identity.profile_id, error.detail)
            skipped.append(STANDING_ORDERS_NOT_SET_UP.format(profile_id=identity.profile_id))
    return tuple(skipped)


def _application(parts: Parts) -> FastAPI:
    # Standing orders, drift checked before each renewal (task STAND-1): one service for REST and the MCP tools.
    unlimited = StandingOrders(store=parts.store, audit=parts.audit, gateway=parts.service, clock=parts.clock)
    start_reasons = load_customers_standing_orders(parts, unlimited)  # the gateway's own set-up: not rate-limited
    standing = with_set_up_limits(unlimited, parts.settings)
    surfaces = _surfaces(parts, standing)
    app = FastAPI(
        title=docs.TITLE, version=docs.VERSION, openapi_tags=docs.TAGS, lifespan=_lifespan(parts, surfaces),
        docs_url=None, redoc_url=None,  # `tta.api.docs_pages` serves both, pinned and under a policy
    )
    app.state.parts = parts
    app.state.start_reasons = start_reasons  # what the start skipped, for `/healthz`
    app.state.surfaces = {name: name in surfaces for name in (MCP_SURFACE, PAGES_SURFACE)}
    app.state.examples = None  # set when the application starts
    # The last one added is the outermost: the headers cover what the two inside it answer themselves.
    app.add_middleware(UploadBodyLimit)  # the body limit, with room for one photo on the routes that take one
    app.add_middleware(ClientKeyMiddleware, trusted_proxy_hops=parts.settings.tta_trusted_proxy_hops)
    app.add_middleware(SecurityHeadersMiddleware)
    install_error_handlers(app)
    app.include_router(router)
    app.include_router(menu_router())  # recipes and menus (task MENU-1)
    app.include_router(customer_router)  # who the caller's customer is (review C2, finding F5)
    app.include_router(public)
    app.include_router(keys)  # /.well-known/jwks.json: the key offers and orders are signed with (P12 W8)
    app.include_router(discovery)  # /.well-known/api-catalog (RFC 9727) and /llms.txt, before the pages (P12 W2)
    include_standing_routes(app, standing)
    install_docs_pages(app)
    # Without a running application (a script that exports the document) the examples are built when asked for.
    docs.install_openapi(app, lambda: app.state.examples or build_examples(parts))
    if MCP_SURFACE in surfaces:
        app.router.routes.append(_McpMount(MCP_PATH, app=surfaces[MCP_SURFACE]))
    if PAGES_SURFACE in surfaces:
        app.router.routes.append(_PagesMount(PAGES_PATH, app=surfaces[PAGES_SURFACE]))  # last, on purpose
    return app


def create_app(settings: Settings | None = None, *, parts: Parts | None = None) -> FastAPI:
    """The gateway for these settings (default: the environment's). `parts` replaces the wiring, for a test.
    Either way the application owns the parts from here on: it closes them when it stops, and also when it
    cannot be put together (a surface that is there without its hook).

    Refuses to start outside dev and demo without tokens from the environment.
    """
    settings = settings or get_settings()
    parts = parts or build_parts(settings)
    try:
        return _application(parts)
    except BaseException:
        close_each(parts.opened)  # a close that fails is logged; the error that stopped the start is raised
        raise
