"""What the gateway sets for one HTTP request is what the tool serving that request sees.

Scores on the 20% "autonomy and controls": the service counts calls per visitor through a context variable
that a middleware of the gateway sets (`tta.api.limits`). The service functions run on a worker thread of
the MCP SDK, so this is checked here, on the surface alone, with a stand-in service.
"""

from __future__ import annotations

from contextvars import ContextVar

import httpx2
import pytest
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client
from starlette.types import Receive, Scope, Send

from tta.api.hooks import SurfaceContext
from tta.api.mcp_surface import create_surface
from tta.config import Settings
from tta.contracts.common import Identity
from tta.contracts.errors import NotFound

pytestmark = pytest.mark.anyio

VISITOR_HEADER = b"x-visitor"
visitor: ContextVar[str] = ContextVar("visitor", default="nobody")


class TellsTheVisitor:
    """Stands in for the gateway service: answers every authority question with the visitor it sees."""

    def get_authority(self, identity: Identity) -> None:
        raise NotFound(f"{identity.id} asks as {visitor.get()}")


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_a_context_variable_set_for_the_request_reaches_the_tool_that_serves_it(
    settings: Settings, agent_ward: Identity, mode: str
) -> None:
    context = SurfaceContext(
        settings=settings, service=TellsTheVisitor(),  # type: ignore[arg-type]
        identify=lambda token: agent_ward if token == "the-ward-token" else None,
    )
    surface = create_surface(context)

    async def gateway(scope: Scope, receive: Receive, send: Send) -> None:
        """As a middleware of the gateway does: set the variable, then hand the request to the surface."""
        reset = visitor.set(dict(scope["headers"]).get(VISITOR_HEADER, b"nobody").decode())
        try:
            await surface(scope, receive, send)
        finally:
            visitor.reset(reset)

    async def ask(name: str) -> str:
        headers = {"Authorization": "Bearer the-ward-token", VISITOR_HEADER.decode(): name}
        async with (
            httpx2.AsyncClient(transport=httpx2.ASGITransport(app=gateway), headers=headers) as http,
            Client(streamable_http_client("http://gateway.test/", http_client=http), mode=mode) as client,
        ):
            first = await client.call_tool("get_authority")
            second = await client.call_tool("get_authority")
        return f"{first.structured_content['detail']} | {second.structured_content['detail']}"

    async with surface.router.lifespan_context(surface):
        seen = [await ask("visitor-a"), await ask("visitor-b"), await ask("visitor-a")]

    assert seen == [
        "agent:allergy-ward asks as visitor-a | agent:allergy-ward asks as visitor-a",
        "agent:allergy-ward asks as visitor-b | agent:allergy-ward asks as visitor-b",
        "agent:allergy-ward asks as visitor-a | agent:allergy-ward asks as visitor-a",
    ]
