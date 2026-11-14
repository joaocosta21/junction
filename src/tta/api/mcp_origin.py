"""The `Origin` check of the MCP endpoint (P12 W3).

Scores on the 15% "open, documented standards rather than a proprietary format". The Streamable HTTP transport
of MCP revision 2026-07-28 says: "If the `Origin` header is present and invalid, servers MUST respond with HTTP
403 Forbidden". A browser sends `Origin` with every POST a web page makes, so this keeps a page of another site,
or a site rebound to this address by DNS, from calling the tools with a token it holds. An agent or a program
sends no `Origin` and is served as before.

The SDK's own check (`TransportSecuritySettings`) checks the Host header too, and the gateway is served behind
a proxy that sets Host, so that check stays off and this one is used. Allowed: a page on the machine itself, any
port (the MCP Inspector runs at http://localhost:6274), and the origins of the setting `TTA_MCP_ALLOWED_ORIGINS`,
comma-separated. `tta.config` does not declare that setting yet: until it does, the attribute is absent and only
the local origins are allowed (hand-back L4b, "Needed from another lane").
"""

from __future__ import annotations

from collections.abc import Sequence

from starlette.types import ASGIApp, Receive, Scope, Send

from tta.api.errors import problem_response, status_problem
from tta.config import Settings

ORIGIN_HEADER = b"origin"
ORIGINS_SETTING = "tta_mcp_allowed_origins"  # the field of `tta.config.Settings` that `allowed_origins` reads
SEPARATOR = ","
ANY_PORT = ":*"
LOCAL_ORIGINS = ("http://localhost:*", "http://127.0.0.1:*", "http://[::1]:*")  # pages on this machine
FORBIDDEN = 403
ORIGIN_REFUSED = (
    "The MCP endpoint takes no request from a web page of this origin: an Origin header that is present must "
    "name an origin this server allows (MCP revision 2026-07-28, Streamable HTTP: 403 Forbidden). A request "
    "with no Origin header, from an agent or a program, is served."
)


def allowed_origins(settings: Settings) -> tuple[str, ...]:
    """The local origins, then those of the setting, in its order. A blank entry is skipped. The field is read by
    its name: a renamed setting fails here, loudly, and never reads as "no origin configured"."""
    listed = tuple(
        entry.strip().lower() for entry in settings.tta_mcp_allowed_origins.split(SEPARATOR) if entry.strip()
    )
    return (*LOCAL_ORIGINS, *listed)


def _on_any_port(origin: str, base: str) -> bool:
    """True for the base origin itself and for the base with a port of digits."""
    if origin == base:
        return True
    port = origin.removeprefix(base + ":")
    return port != origin and port.isascii() and port.isdigit()


def is_allowed_origin(origin: str, allowed: Sequence[str]) -> bool:
    """True when the origin is one of `allowed`; an entry that ends with `:*` allows any port of its base.
    Scheme and host are compared without case, as browsers write them in lower case anyway."""
    origin = origin.strip().lower()
    for listed in (entry.lower() for entry in allowed):
        if listed.endswith(ANY_PORT) and _on_any_port(origin, listed.removesuffix(ANY_PORT)):
            return True
        if origin == listed:
            return True
    return False


class OriginCheck:
    """Answers 403 with a problem document when a request carries an `Origin` the surface does not allow.
    Every `Origin` line is checked; a request with none passes. Outermost: before the bearer check."""

    def __init__(self, app: ASGIApp, *, allowed: Sequence[str] = LOCAL_ORIGINS) -> None:
        self._app = app
        self._allowed = tuple(allowed)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            origins = [value.decode("latin-1") for name, value in scope.get("headers", ()) if name == ORIGIN_HEADER]
            if any(not is_allowed_origin(origin, self._allowed) for origin in origins):
                await problem_response(status_problem(FORBIDDEN, ORIGIN_REFUSED))(scope, receive, send)
                return
        await self._app(scope, receive, send)
