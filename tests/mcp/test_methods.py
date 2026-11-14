"""The MCP endpoint answers POST only: no event stream is held open (task FIX-10, finding 9).

Scores on the 30% "working end-to-end demo": in stateless mode a GET opened the SDK's event stream and held
the connection until the client left, so a few hundred of them would tie up the public demo.
"""

from __future__ import annotations

from typing import Any

import anyio
import pytest
from fastapi import FastAPI

from tta.contracts.errors import PROBLEM_CONTENT_TYPE

pytestmark = pytest.mark.anyio

NOT_ALLOWED = 405
AT_ONCE_SECONDS = 2.0
HEADERS = [
    (b"host", b"demo.example"), (b"authorization", b"Bearer demo-agent-hotel-kitchen"),
    (b"accept", b"text/event-stream"),
]


async def _answer(app: FastAPI, method: str, path: str) -> dict[str, Any]:
    """Send one request straight to the application, with a client that never hangs up, and return the start of
    the answer. Raises `TimeoutError` when the application keeps the request open."""
    answer: dict[str, Any] = {}
    body_sent = anyio.Event()
    never = anyio.Event()

    async def receive() -> dict[str, Any]:
        if not body_sent.is_set():
            body_sent.set()
            return {"type": "http.request", "body": b"", "more_body": False}
        await never.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            answer["status"] = message["status"]
            answer["headers"] = {name.decode(): value.decode() for name, value in message["headers"]}

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "https",
        "path": path, "raw_path": path.encode(), "root_path": "", "query_string": b"", "headers": HEADERS,
        "client": ("93.184.216.34", 1000), "server": ("demo.example", 443),
    }
    with anyio.fail_after(AT_ONCE_SECONDS):
        await app(scope, receive, send)
    return answer


@pytest.mark.parametrize("method", ["GET", "DELETE"])
@pytest.mark.parametrize("path", ["/mcp", "/mcp/"])
async def test_get_and_delete_on_the_mcp_endpoint_are_answered_405_at_once(
    running_app: FastAPI, method: str, path: str
) -> None:
    answer = await _answer(running_app, method, path)

    assert answer["status"] == NOT_ALLOWED
    assert answer["headers"]["allow"] == "POST"
    assert answer["headers"]["content-type"] == PROBLEM_CONTENT_TYPE


async def test_a_post_still_reaches_the_sdk(running_app: FastAPI) -> None:
    answer = await _answer(running_app, "POST", "/mcp/")

    assert answer["status"] != NOT_ALLOWED  # the SDK answers it (here: the body is not JSON-RPC)
