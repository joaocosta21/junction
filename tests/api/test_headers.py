"""Security headers on every response (task FIX-8, finding 13).

Scores on the 15% "credible path toward production": no answer is sniffed into another type, no address of
ours is sent on as a referrer, and nothing under `/v1` is kept by a cache.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route

from tta.api import create_app
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings

Auth = Callable[..., dict[str, str]]
PAGE_POLICY = "default-src 'self'"
PAGE_HEADERS = {"Content-Security-Policy": PAGE_POLICY, "Referrer-Policy": "origin", "Cache-Control": "max-age=60"}


def _has_the_two(response: Any) -> None:
    assert response.headers.get_list("x-content-type-options") == ["nosniff"], response.url
    assert response.headers.get_list("referrer-policy") == ["no-referrer"], response.url


def test_every_answer_of_the_api_says_nosniff_no_referrer_and_no_store(
    client: TestClient, auth: Auth, scenario_2: dict[str, Any]
) -> None:
    answers = [
        client.get("/v1/schemas"),
        client.get("/v1/authority", headers=auth("agent_ward")),
        client.post("/v1/offers", json=scenario_2, headers=auth("agent_ward")),
        client.get("/v1/authority"),  # 401
        client.get("/v1/approvals", headers=auth("agent_ward")),  # 403
        client.get("/v1/no-such-thing"),  # 404
        client.get("/v1"),  # the API's own path without a slash
        client.delete("/v1/orders"),  # 405
        client.post("/v1/offers", json={}, headers=auth("agent_ward")),  # 422
        client.post("/v1/offers", content=b"x" * 70_000, headers=auth("agent_ward")),  # 413, from the body limit
        client.post("/v1/offers", content=b"{}", headers={**auth("agent_ward"), "Content-Length": "many"}),
    ]

    assert [answer.status_code for answer in answers] == [200, 200, 201, 401, 403, 404, 404, 405, 422, 413, 400]
    for answer in answers:
        _has_the_two(answer)
        assert answer.headers.get_list("cache-control") == ["no-store"], answer.url


def test_answers_outside_v1_say_nosniff_and_no_referrer_and_may_be_cached(client: TestClient) -> None:
    for path in ("/healthz", "/openapi.json", "/docs", "/no-such-page"):
        answer = client.get(path)
        _has_the_two(answer)
        assert "no-store" not in answer.headers.get("cache-control", ""), path


def test_an_unexpected_fault_carries_the_headers_too(
    changing_client: TestClient, changing: Any, auth: Auth, scenario_2: dict[str, Any]
) -> None:
    changing.broken = True

    answer = changing_client.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))

    assert answer.status_code == 500
    _has_the_two(answer)
    assert answer.headers.get_list("cache-control") == ["no-store"]


@pytest.fixture
def with_surfaces(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """The app with a page surface that sets its own Content-Security-Policy and a referrer policy of its own."""

    def create_surface(context: Any) -> Starlette:
        async def page(request: Request) -> HTMLResponse:
            return HTMLResponse("<p>a page</p>", headers=PAGE_HEADERS)

        return Starlette(routes=[Route("/", page), Route("/{rest:path}", page)])

    for name in ("tta.api.mcp_surface", "tta.ui.routes"):
        module = types.ModuleType(name)
        module.create_surface = create_surface  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, name, module)
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        yield client


@pytest.mark.parametrize("path", ["/", "/approvals", "/mcp/"])
def test_the_mounted_surfaces_get_the_two_headers_and_keep_their_own(with_surfaces: TestClient, path: str) -> None:
    answer = with_surfaces.get(path)

    assert answer.text == "<p>a page</p>"
    _has_the_two(answer)  # one value each: the surface's own referrer policy is replaced, not doubled
    assert answer.headers["content-security-policy"] == PAGE_POLICY
    assert answer.headers["cache-control"] == "max-age=60"  # not under /v1: the surface decides
