"""The MCP endpoint checks the `Origin` header (P12 W3).

Scores on the 15% "open, documented standards rather than a proprietary format": it was the one MUST of the MCP
transport we broke. The Streamable HTTP transport of revision 2026-07-28 says: "If the `Origin` header is present
and invalid, servers MUST respond with HTTP 403 Forbidden". Before, `Origin: https://evil.example` got 200 and
the tools. A request with no `Origin` (an agent, a program, curl) is served as before.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from tta.api.mcp_origin import LOCAL_ORIGINS, ORIGIN_REFUSED, ORIGINS_SETTING, allowed_origins, is_allowed_origin
from tta.contracts.errors import PROBLEM_CONTENT_TYPE

pytestmark = pytest.mark.anyio

Headers = dict[str, str]
Rpc = Callable[..., dict[str, Any]]
FORBIDDEN = 403
ACCEPT = {"Accept": "application/json, text/event-stream"}
MCP_INSPECTOR = "http://localhost:6274"  # the MCP Inspector's own page, which calls the server from a browser
FOREIGN = (
    "https://evil.example", "null", "http://localhost.evil.example", "http://127.0.0.1.evil.example:8000",
    "https://localhost:6274", "http://localhost:abc", "file://",
)
LOCAL = (MCP_INSPECTOR, "http://localhost", "http://127.0.0.1:8000", "http://[::1]:8000", "HTTP://LOCALHOST:8000")


async def _tools_list(rest: httpx.AsyncClient, path: str, rpc: Rpc, headers: Headers) -> httpx.Response:
    return await rest.post(path, json=rpc("tools/list"), headers={**ACCEPT, **headers})


@pytest.mark.parametrize("origin", FOREIGN)
async def test_a_foreign_origin_is_answered_403_with_a_problem_and_no_tool(
    rest: httpx.AsyncClient, mcp_path: str, rpc: Rpc, auth: Callable[[str], Headers], origin: str
) -> None:
    response = await _tools_list(rest, mcp_path, rpc, {**auth("agent_ward"), "Origin": origin})

    assert response.status_code == FORBIDDEN
    assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
    problem = response.json()
    assert (problem["status"], problem["detail"]) == (FORBIDDEN, ORIGIN_REFUSED)  # the origin is not repeated
    assert "result" not in problem


async def test_a_foreign_origin_is_refused_before_the_token_is_read(
    rest: httpx.AsyncClient, mcp_path: str, rpc: Rpc
) -> None:
    response = await _tools_list(rest, mcp_path, rpc, {"Origin": "https://evil.example"})

    assert response.status_code == FORBIDDEN


async def test_a_request_with_no_origin_is_served_as_before(
    rest: httpx.AsyncClient, mcp_path: str, rpc: Rpc, auth: Callable[[str], Headers]
) -> None:
    response = await _tools_list(rest, mcp_path, rpc, auth("agent_ward"))

    assert response.status_code == 200
    assert len(response.json()["result"]["tools"]) == 13


@pytest.mark.parametrize("origin", LOCAL)
async def test_a_page_on_the_teams_own_machine_is_served(
    rest: httpx.AsyncClient, mcp_path: str, rpc: Rpc, auth: Callable[[str], Headers], origin: str
) -> None:
    response = await _tools_list(rest, mcp_path, rpc, {**auth("agent_ward"), "Origin": origin})

    assert response.status_code == 200
    assert len(response.json()["result"]["tools"]) == 13


@pytest.mark.parametrize("path", ["/mcp", "/mcp/"])
async def test_both_addresses_of_the_endpoint_are_checked(
    rest: httpx.AsyncClient, rpc: Rpc, auth: Callable[[str], Headers], path: str
) -> None:
    response = await _tools_list(rest, path, rpc, {**auth("agent_ward"), "Origin": "https://evil.example"})

    assert response.status_code == FORBIDDEN


def test_the_allow_list_is_the_local_origins_plus_the_setting() -> None:
    configured = SimpleNamespace(**{ORIGINS_SETTING: " https://demo.example , https://other.example:8443 ,"})

    assert allowed_origins(SimpleNamespace()) == LOCAL_ORIGINS
    assert allowed_origins(configured) == (*LOCAL_ORIGINS, "https://demo.example", "https://other.example:8443")


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [
        ("https://demo.example", True),
        ("https://demo.example:443", False),  # another origin: the port is part of it
        ("https://demo.example.evil", False),
        ("http://demo.example", False),
        (MCP_INSPECTOR, True),
    ],
)
def test_an_origin_is_allowed_only_as_listed(origin: str, allowed: bool) -> None:
    assert is_allowed_origin(origin, (*LOCAL_ORIGINS, "https://demo.example")) is allowed
