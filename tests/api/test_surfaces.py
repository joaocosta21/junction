"""The hooks for the MCP surface (T11) and the pages (T12): mounted when their modules exist, with the
API's own paths kept from the pages. The request parser and the buyer agent: `test_hooks.py`."""

from __future__ import annotations

import sys
import types
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from tta.api import create_app
from tta.api.hooks import SurfaceContext
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings

Auth = Callable[..., dict[str, str]]


def _surface(name: str, started: list[str], contexts: list[SurfaceContext]) -> types.ModuleType:
    def create_surface(context: SurfaceContext) -> Starlette:
        contexts.append(context)

        @asynccontextmanager
        async def lifespan(app: Starlette) -> AsyncIterator[None]:
            started.append(f"{name} started")
            yield
            started.append(f"{name} stopped")

        async def page(request: Request) -> PlainTextResponse:
            return PlainTextResponse(f"{name} at {request.url.path}")

        return Starlette(routes=[Route("/", page), Route("/{rest:path}", page)], lifespan=lifespan)

    module = types.ModuleType(name)
    module.create_surface = create_surface  # type: ignore[attr-defined]
    return module


def test_without_the_optional_modules_nothing_is_mounted(client: TestClient) -> None:
    assert client.get("/mcp/").status_code == 404
    assert client.get("/").status_code == 404
    assert client.get("/healthz").json()["surfaces"] == {"mcp": False, "pages": False}


def test_the_mcp_surface_and_the_pages_are_mounted_when_their_modules_exist(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch, auth: Auth
) -> None:
    started: list[str] = []
    contexts: list[SurfaceContext] = []
    monkeypatch.setitem(sys.modules, "tta.api.mcp_surface", _surface("mcp", started, contexts))
    monkeypatch.setitem(sys.modules, "tta.ui.routes", _surface("pages", started, contexts))
    parts = build_parts(settings, catalog=catalog)

    with TestClient(create_app(settings, parts=parts)) as client:
        assert client.get("/mcp/").text == "mcp at /mcp/"
        assert client.get("/").text == "pages at /"
        assert client.get("/approvals").text == "pages at /approvals"
        # The API keeps its own paths, also for a path or a method it does not have.
        assert client.get("/healthz").json()["surfaces"] == {"mcp": True, "pages": True}
        assert client.get("/v1/schemas").status_code == 200
        assert client.get("/v1/authority", headers=auth("agent_hotel")).status_code == 200
        assert client.get("/openapi.json").status_code == 200
        for response, status in ((client.get("/v1/no-such-thing"), 404), (client.delete("/v1/orders"), 405)):
            assert response.status_code == status
            assert response.headers["content-type"] == "application/problem+json"
        assert started == ["mcp started", "pages started"]
    assert started[2:] == ["pages stopped", "mcp stopped"]

    assert len(contexts) == 2
    for context in contexts:
        assert context.service is parts.service
        assert context.settings is settings
        assert context.identify("demo-agent-hotel-kitchen") == parts.tokens.identify("demo-agent-hotel-kitchen")
        assert context.identify("nobody") is None
        # Four agents, six people (one person confirms: the hotel's and the bakery's one person, the ward's and
        # the school's person who orders and their dietitian) and the supplier.
        assert len(context.demo_identities) == 11
        assert context.standing is not None  # the standing orders the REST routes serve, for the MCP tools


def test_the_path_v1_without_a_slash_belongs_to_the_api_and_not_to_the_pages(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "tta.ui.routes", _surface("pages", [], []))

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        bare = client.get("/v1", follow_redirects=False)
        with_slash = client.get("/v1/", follow_redirects=False)
        lookalike = client.get("/v1x")

    for response in (bare, with_slash):
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"
        assert "pages" not in response.text
    assert lookalike.text == "pages at /v1x"  # only the API's own prefix is kept from the pages


@pytest.mark.parametrize("with_pages", [True, False])
def test_the_path_mcp_without_a_slash_is_the_mcp_endpoint_itself_with_no_redirect(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch, with_pages: bool
) -> None:
    # An MCP host is given `https://<host>/mcp`. A redirect of its POST is lost behind a proxy that ends TLS,
    # and the pages must not answer it either: the exact path is the root of the mounted surface.
    monkeypatch.setitem(sys.modules, "tta.api.mcp_surface", _surface("mcp", [], []))
    if with_pages:
        monkeypatch.setitem(sys.modules, "tta.ui.routes", _surface("pages", [], []))

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        bare = client.get("/mcp", follow_redirects=False)
        with_slash = client.get("/mcp/", follow_redirects=False)
        below = client.get("/mcp/messages", follow_redirects=False)
        lookalike = client.get("/mcpx", follow_redirects=False)

    assert (bare.status_code, bare.text) == (200, "mcp at /mcp/")  # the surface sees its own root
    assert (with_slash.status_code, with_slash.text) == (200, "mcp at /mcp/")
    assert below.text == "mcp at /mcp/messages"
    # Only the exact path is the surface's: a path that merely starts the same is not.
    assert (lookalike.status_code, lookalike.text) == ((200, "pages at /mcpx") if with_pages else (404, lookalike.text))
    assert "mcp at" not in lookalike.text


@pytest.fixture
def the_real_mcp_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lets `tta.api.mcp_surface` (task T11) be imported for one test: the other tests of this folder see it
    as not installed (`conftest.py`)."""
    monkeypatch.delitem(sys.modules, "tta.api.mcp_surface")


@pytest.mark.parametrize("with_pages", [True, False])
@pytest.mark.parametrize("path", ["/mcp", "/mcp/"])
def test_a_post_without_a_token_to_mcp_with_or_without_the_slash_is_refused_by_the_mcp_surface(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch, the_real_mcp_surface: None,
    with_pages: bool, path: str,
) -> None:
    if with_pages:
        monkeypatch.setitem(sys.modules, "tta.ui.routes", _surface("pages", [], []))
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    headers = {"Accept": "application/json, text/event-stream"}

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        surfaces = client.get("/healthz").json()["surfaces"]
        response = client.post(path, json=call, headers=headers, follow_redirects=False)

    assert surfaces == {"mcp": True, "pages": with_pages}
    # The MCP SDK's own refusal (RFC 6750), not a redirect, not a page and not the REST routes' problem document.
    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"].startswith("Bearer")
    assert response.json()["error"] == "invalid_token"
    assert response.headers["content-type"] != "application/problem+json"


def test_outside_dev_and_demo_the_pages_are_not_mounted_and_no_demo_identity_is_handed_out(
    tmp_path: Any, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    contexts: list[SurfaceContext] = []
    monkeypatch.setitem(sys.modules, "tta.api.mcp_surface", _surface("mcp", [], contexts))
    monkeypatch.setitem(sys.modules, "tta.ui.routes", _surface("pages", [], contexts))
    tokens = '{"a-token-from-the-environment": {"kind": "SUPPLIER", "id": "supplier:x", "display_name": "X"}}'
    settings = Settings.for_tests(tta_env="prod", tta_tokens=tokens, tta_data_dir=tmp_path / "var")

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        assert client.get("/").status_code == 404
        assert client.get("/mcp/").status_code == 200
        assert client.get("/healthz").json()["surfaces"] == {"mcp": True, "pages": False}

    assert [context.demo_identities for context in contexts] == [()]


def test_an_optional_module_without_its_hook_stops_the_start(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "tta.ui.routes", types.ModuleType("tta.ui.routes"))

    with pytest.raises(RuntimeError, match="create_surface"):
        create_app(settings, parts=build_parts(settings, catalog=catalog))


def test_a_surface_that_is_a_bare_asgi_callable_is_mounted_too(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def bare(scope: Any, receive: Any, send: Any) -> None:
        await PlainTextResponse("bare")(scope, receive, send)

    module = types.ModuleType("tta.api.mcp_surface")
    module.create_surface = lambda context: bare  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tta.api.mcp_surface", module)

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        assert client.get("/mcp/").text == "bare"


def test_an_optional_module_that_exists_but_cannot_be_imported_stops_the_start(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    from tta.api import hooks

    def broken(name: str) -> Any:
        raise ModuleNotFoundError("No module named 'something_it_needs'", name="something_it_needs")

    monkeypatch.setattr(hooks.importlib, "import_module", broken)

    with pytest.raises(ModuleNotFoundError, match="something_it_needs"):
        hooks.optional_module("tta.ui.routes")
