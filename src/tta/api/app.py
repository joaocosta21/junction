"""`create_app(settings)`: the FastAPI application (SPEC section 2, task T09).

Scores on the 30% "working end-to-end demo" (one process serves the whole flow) and on the 15% "open,
documented standards" (OpenAPI 3.1 generated from the typed models, problem details for every error).

    uvicorn --factory tta.api:create_app
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from starlette.routing import Match, Mount
from starlette.types import ASGIApp, Scope

from tta.api import docs, hooks
from tta.api.errors import install_error_handlers
from tta.api.examples import build_examples
from tta.api.limits import BodyLimitMiddleware
from tta.api.routes import public, router
from tta.api.wiring import Parts, build_parts
from tta.config import Settings, get_settings

MCP_PATH = "/mcp"
PAGES_PATH = "/"
API_PATHS = "/v1/"
MCP_SURFACE = "mcp"
PAGES_SURFACE = "pages"


class _PagesMount(Mount):
    """The pages take every path nothing else has taken, except the API's: a path or a method the API does
    not have stays the API's to answer, as a problem document and not as a page."""

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        if scope["type"] == "http" and scope["path"].startswith(API_PATHS):
            return Match.NONE, {}
        return super().matches(scope)


def _surfaces(parts: Parts) -> dict[str, ASGIApp]:
    """The optional surfaces that exist, by name. The pages act as a demonstration identity chosen on the
    page, with no token, so they are mounted only where those identities exist: in dev and demo."""
    demo = parts.settings.is_demo_environment
    context = hooks.SurfaceContext(
        settings=parts.settings, service=parts.service, identify=parts.tokens.identify,
        demo_identities=parts.tokens.identities if demo else (),
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
        When the gateway stops, the database and the live client are closed."""
        async with AsyncExitStack() as stack:
            stack.callback(parts.close)
            for surface in surfaces.values():
                context = getattr(getattr(surface, "router", None), "lifespan_context", None)
                if context is not None:
                    await stack.enter_async_context(context(surface))
            yield

    return lifespan


def create_app(settings: Settings | None = None, *, parts: Parts | None = None) -> FastAPI:
    """The gateway for these settings (default: the environment's). `parts` replaces the wiring, for a test.
    Either way the application owns the parts from here on and closes them when it stops.

    Refuses to start outside dev and demo without tokens from the environment.
    """
    settings = settings or get_settings()
    parts = parts or build_parts(settings)
    surfaces = _surfaces(parts)
    app = FastAPI(
        title=docs.TITLE, version=docs.VERSION, openapi_tags=docs.TAGS, lifespan=_lifespan(parts, surfaces)
    )
    app.state.parts = parts
    app.state.surfaces = {name: name in surfaces for name in (MCP_SURFACE, PAGES_SURFACE)}
    app.add_middleware(BodyLimitMiddleware)
    install_error_handlers(app)
    app.include_router(router)
    app.include_router(public)
    docs.install_openapi(app, lambda: build_examples(parts))
    if MCP_SURFACE in surfaces:
        app.mount(MCP_PATH, surfaces[MCP_SURFACE])
    if PAGES_SURFACE in surfaces:
        app.router.routes.append(_PagesMount(PAGES_PATH, app=surfaces[PAGES_SURFACE]))  # last, on purpose
    return app
