"""The MCP endpoint takes POST only (task FIX-10, finding 9).

With no session there is no event stream to open and no session to end, so `GET` and `DELETE` are answered 405
before the SDK sees them: a `GET` would otherwise hold its connection open until the client leaves.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from tta.api.errors import problem_response, status_problem

# Mounted at /mcp by `create_app`, so the endpoint is the root of the mounted application: /mcp/.
ENDPOINT_PATH = "/"
METHOD_NOT_ALLOWED = 405
ONLY_POST = "POST"
REFUSED_METHODS = frozenset({"GET", "DELETE"})  # the event stream and the end of a session: neither exists here
POST_ONLY = (
    "The MCP endpoint takes POST only: every call is one JSON-RPC request answered with one JSON body. "
    "There is no event stream and no session to end."
)


def _endpoint_path(scope: Scope) -> str:
    """The path inside the mounted application: the endpoint is its root, whatever the mount's own path."""
    root = scope.get("root_path", "")
    path: str = scope["path"]
    return (path[len(root):] if root and path.startswith(root) else path) or ENDPOINT_PATH


class PostOnly:
    """Answers `GET` and `DELETE` on the endpoint with 405 and `Allow: POST` before the SDK, which would open
    an event stream for a `GET`. Other paths of the surface are left to the SDK."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        refused = scope["type"] == "http" and scope["method"] in REFUSED_METHODS
        if refused and _endpoint_path(scope) == ENDPOINT_PATH:
            refusal = problem_response(status_problem(METHOD_NOT_ALLOWED, POST_ONLY), headers={"Allow": ONLY_POST})
            await refusal(scope, receive, send)
            return
        await self._app(scope, receive, send)
