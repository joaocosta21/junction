"""Security headers on every response (task FIX-8, finding 13).

Scores on the 15% "credible path toward production". Every response says `X-Content-Type-Options: nosniff`
and `Referrer-Policy: no-referrer`; every response under `/v1` also says `Cache-Control: no-store`, so that
no offer, order or audit trail is kept by a cache between the gateway and the caller. The pages set their
own Content-Security-Policy.
"""

from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

API_ROOT = "/v1"  # the API's own prefix: this exact path and everything under it
EVERY_RESPONSE = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
API_RESPONSE = {"Cache-Control": "no-store"}


def is_api_path(path: str) -> bool:
    """True for `/v1` and for every path under `/v1/`; false for a path that only starts the same (`/v1x`)."""
    return path == API_ROOT or path.startswith(API_ROOT + "/")


def security_headers(path: str) -> dict[str, str]:
    """The headers a response to this path carries."""
    return {**EVERY_RESPONSE, **API_RESPONSE} if is_api_path(path) else dict(EVERY_RESPONSE)


class SecurityHeadersMiddleware:
    """Sets the headers on every response that passes: the API's own, the body limit's refusals and the
    mounted surfaces'. A value a surface set for one of these headers is replaced, never doubled. The answer
    to an unexpected fault is sent outside every middleware, so its handler adds the same headers itself."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        wanted = security_headers(scope["path"])

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                headers = MutableHeaders(scope=message)
                for name, value in wanted.items():
                    headers[name] = value
            await send(message)

        await self._app(scope, receive, with_headers)
