"""The MCP surface takes the same bearer identity as the REST routes, and nothing runs without one.

Scores on the 20% "autonomy and controls": what a caller may do follows from its token on every transport.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import anyio
import httpx
import httpx2
import pytest
from mcp.client import Client
from mcp.shared.exceptions import MCPError

from tta.api.hooks import SurfaceContext
from tta.api.mcp_surface import build_server, create_surface
from tta.api.wiring import Parts
from tta.config import Settings
from tta.contracts.common import Identity
from tta.contracts.errors import PROBLEM_TYPE_BASE

pytestmark = pytest.mark.anyio

Connect = Callable[..., AbstractAsyncContextManager[Client]]
Headers = dict[str, str]
Rpc = Callable[..., dict[str, Any]]

UNAUTHORIZED = 401
CALLS_AT_ONCE = 24
NOT_AUTHORISED = PROBLEM_TYPE_BASE + "not-authorised"
NOT_FOUND = PROBLEM_TYPE_BASE + "not-found"


async def test_a_call_without_a_token_is_refused_before_any_tool_runs(
    rest: httpx.AsyncClient, parts: Parts, mcp_path: str, rpc: Rpc, scenario_2: dict[str, Any]
) -> None:
    call = rpc("tools/call", {"name": "get_offer", "arguments": {"request": scenario_2}})

    response = await rest.post(mcp_path, json=call)

    assert response.status_code == UNAUTHORIZED
    assert response.headers["www-authenticate"].startswith("Bearer")
    assert "resource_metadata" not in response.headers["www-authenticate"]  # no OAuth server is advertised
    assert "result" not in response.json()
    assert parts.audit.head()[0] == 0  # no offer was built: the trail is still empty
    assert parts.store.list_orders() == ()


async def test_a_token_nobody_issued_is_refused(
    rest: httpx.AsyncClient, parts: Parts, mcp_path: str, rpc: Rpc, auth: Callable[[str], Headers]
) -> None:
    call = rpc("tools/call", {"name": "get_authority", "arguments": {}})

    response = await rest.post(mcp_path, json=call, headers=auth("nobody"))

    assert response.status_code == UNAUTHORIZED
    assert "a-token-nobody-issued" not in response.text
    assert parts.audit.head()[0] == 0


@pytest.mark.parametrize("method", ["initialize", "tools/list", "server/discover"])
async def test_nothing_of_the_surface_is_readable_without_a_token(
    rest: httpx.AsyncClient, mcp_path: str, rpc: Rpc, method: str
) -> None:
    response = await rest.post(mcp_path, json=rpc(method))

    assert response.status_code == UNAUTHORIZED


async def test_a_raw_call_with_a_token_is_answered_as_plain_json(
    rest: httpx.AsyncClient, mcp_path: str, rpc: Rpc, auth: Callable[[str], Headers]
) -> None:
    headers = {**auth("agent_ward"), "Accept": "application/json, text/event-stream"}

    response = await rest.post(mcp_path, json=rpc("tools/list"), headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert len(response.json()["result"]["tools"]) == 8
    assert "mcp-session-id" not in response.headers  # no session is kept: any replica can answer the next call


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_each_call_acts_as_the_identity_of_its_own_token(connect: Connect, mode: str) -> None:
    async with connect("agent_hotel", mode) as hotel, connect("agent_ward", mode) as ward:
        seen = [
            (await client.call_tool("get_authority")).structured_content["profile"]["profile_id"]
            for client in (hotel, ward, hotel, ward)
        ]

    assert seen == ["hotel-kitchen", "allergy-ward", "hotel-kitchen", "allergy-ward"]


async def test_calls_served_at_the_same_time_keep_their_own_identities(connect: Connect) -> None:
    seen: dict[int, str] = {}

    async def ask(number: int, client: Client) -> None:
        answer = await client.call_tool("get_authority")
        seen[number] = answer.structured_content["profile"]["profile_id"]

    async with connect("agent_hotel") as hotel, connect("agent_ward") as ward, anyio.create_task_group() as group:
        for number in range(CALLS_AT_ONCE):
            group.start_soon(ask, number, hotel if number % 2 == 0 else ward)

    expected = {n: "hotel-kitchen" if n % 2 == 0 else "allergy-ward" for n in range(CALLS_AT_ONCE)}
    assert seen == expected


async def test_no_oauth_metadata_is_published(rest: httpx.AsyncClient, auth: Callable[[str], Headers]) -> None:
    # Tokens are handed out outside the protocol: the surface names no authorization server to anybody.
    for path in ("/mcp/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"):
        response = await rest.get(path, headers=auth("agent_ward"))
        assert response.status_code == 404, path
        assert "tta.example" not in response.text, path


async def test_another_buyers_offer_answers_as_an_id_nobody_issued(
    connect: Connect, scenario_2: dict[str, Any]
) -> None:
    async with connect("agent_ward") as ward, connect("agent_hotel") as hotel:
        offer = (await ward.call_tool("get_offer", {"request": scenario_2})).structured_content
        option_id = offer["options"][0]["option_id"]
        order = await hotel.call_tool(
            "place_order", {"offer_id": offer["offer_id"], "option_id": option_id, "idempotency_key": "mcp-other-1"}
        )
        trail = await hotel.call_tool("get_audit", {"offer_id": offer["offer_id"]})

    assert order.is_error and order.structured_content["type"] == NOT_FOUND
    assert trail.is_error and trail.structured_content["type"] == NOT_FOUND


async def test_an_approver_cannot_place_an_order_over_mcp(connect: Connect, scenario_2: dict[str, Any]) -> None:
    async with connect("agent_ward") as agent, connect("ward_purchasing") as approver:
        offer = (await agent.call_tool("get_offer", {"request": scenario_2})).structured_content
        option_id = offer["options"][0]["option_id"]
        refused = await approver.call_tool(
            "place_order", {"offer_id": offer["offer_id"], "option_id": option_id, "idempotency_key": "mcp-approver-1"}
        )
        read = await approver.call_tool("get_authority")

    assert refused.is_error and refused.structured_content["type"] == NOT_AUTHORISED
    assert refused.structured_content["status"] == 403
    assert not read.is_error and read.structured_content["profile"]["profile_id"] == "allergy-ward"


async def test_the_supplier_reads_its_view_of_the_audit_trail_and_nothing_else(
    connect: Connect, scenario_2: dict[str, Any]
) -> None:
    async with connect("agent_ward") as agent, connect("supplier") as supplier:
        await agent.call_tool("get_offer", {"request": scenario_2})
        trail = await supplier.call_tool("get_audit")
        buyers_view = await supplier.call_tool("get_audit", {"reader": "buyer"})
        authority = await supplier.call_tool("get_authority")
        search = await supplier.call_tool("search_products", {"query": {"product_type": "milk"}})

    assert not trail.is_error
    assert trail.structured_content["reader"] == "supplier" and trail.structured_content["events"]
    for refused in (buyers_view, authority, search):
        assert refused.is_error and refused.structured_content["type"] == NOT_AUTHORISED


async def test_a_tool_reached_without_the_http_layer_still_refuses_a_caller_with_no_identity(parts: Parts) -> None:
    # In memory there is no HTTP request and so no bearer token: the tool itself must refuse.
    context = SurfaceContext(settings=parts.settings, service=parts.service, identify=parts.tokens.identify)

    async with Client(build_server(context)) as client:
        listed = await client.list_tools()
        answer = await client.call_tool("get_authority")

    assert len(listed.tools) == 8
    assert answer.is_error
    assert answer.structured_content["type"] == NOT_AUTHORISED
    assert answer.structured_content["status"] == UNAUTHORIZED


def test_building_the_server_does_not_make_the_process_log_more(parts: Parts, monkeypatch: pytest.MonkeyPatch) -> None:
    # The SDK sets up logging for the whole process when a server is built, if nothing has yet.
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", logging.WARNING)
    context = SurfaceContext(settings=parts.settings, service=parts.service, identify=parts.tokens.identify)

    build_server(context)

    assert root.level == logging.WARNING  # what Python logs by default: no INFO line of any package appears


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_the_official_client_cannot_open_a_session_without_a_token(
    connect: Connect, parts: Parts, mode: str
) -> None:
    with pytest.RaisesGroup(MCPError, flatten_subgroups=True):
        async with connect(None, mode) as client:
            await client.list_tools()

    assert parts.audit.head()[0] == 0


async def test_a_token_the_registry_no_longer_knows_when_the_tool_runs_is_refused(
    settings: Settings, agent_ward: Identity
) -> None:
    # The transport checks the token first; the tool asks the registry again and believes only that answer.
    answers = iter([agent_ward])  # known at the first question, unknown at every later one

    class NeverReached:
        def get_authority(self, identity: Identity) -> None:
            raise AssertionError("the service was called without an identity")

    context = SurfaceContext(
        settings=settings, service=NeverReached(),  # type: ignore[arg-type]
        identify=lambda token: next(answers, None),
    )
    surface = create_surface(context)
    http = httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=surface), headers={"Authorization": "Bearer a-token-about-to-go"}
    )
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_authority", "arguments": {}}}

    async with surface.router.lifespan_context(surface), http:
        response = await http.post(
            "http://gateway.test/", json=call, headers={"Accept": "application/json, text/event-stream"}
        )

    result = response.json()["result"]
    assert result["isError"] is True
    assert result["structuredContent"]["type"] == NOT_AUTHORISED
    assert result["structuredContent"]["status"] == UNAUTHORIZED
