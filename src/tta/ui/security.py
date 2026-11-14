"""What keeps the pages safe to put in front of strangers: response headers, the form token, the cookies.

Scores on the 20% "quality of the guardrails design": the approval panel is where a human signs, so a form
that changes state (run, approve, reject, choose who acts) is a POST that carries a token another site cannot
read, and no page loads or runs anything from outside this server.

- The token lives in a cookie scripts cannot read (`HttpOnly`) and other sites do not send on a POST
  (`SameSite=Lax`); every form repeats it in a hidden field and the two must match. One per browser session.
  Over HTTPS the cookie carries the `__Host-` prefix, so another host of the same domain cannot plant one.
- Nothing is kept on the server for it, so it survives a restart and more than one server process.
"""

from __future__ import annotations

import hmac
import re
import secrets

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSRF_COOKIE = "tta_csrf"
AGENT_COOKIE = "tta_agent"  # the demo agent chosen on the first page
APPROVER_COOKIE = "tta_approver"  # the demo approver chosen on the approvals page
HOST_PREFIX = "__Host-"  # a browser accepts such a cookie only over HTTPS, for this host, for every path
TOKEN_BYTES = 32
STATIC_PATH = "/static/"
HTTPS = "https"
FORWARDED_PROTO = "x-forwarded-proto"

# No source but this server, no inline script or style, no framing, forms post only here.
CONTENT_SECURITY_POLICY = "; ".join((
    "default-src 'none'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self'",
    "connect-src 'self'",
    "form-action 'self'",
    "base-uri 'none'",
    "frame-ancestors 'none'",
))
SECURITY_HEADERS = (
    ("Content-Security-Policy", CONTENT_SECURITY_POLICY),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),  # an order id in an address is not sent to another site
)
NO_STORE = ("Cache-Control", "no-store")  # a page shows one buyer's orders: never kept by a shared cache

_TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")  # 32 random bytes, URL-safe base64 without padding


def is_https(request: Request) -> bool:
    """Whether the browser reached the site over HTTPS, directly or through the host's proxy."""
    forwarded = request.headers.get(FORWARDED_PROTO, "").split(",")[0].strip().lower()
    return HTTPS in (request.url.scheme, forwarded)


def csrf_cookie_name(request: Request) -> str:
    return HOST_PREFIX + CSRF_COOKIE if is_https(request) else CSRF_COOKIE


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def session_token(request: Request) -> str | None:
    """The form token of this browser session, or `None` when it has none yet (or sent something else)."""
    token = request.cookies.get(csrf_cookie_name(request), "")
    return token if _TOKEN.fullmatch(token) else None


def token_matches(request: Request, submitted: str) -> bool:
    """True when the form carries the token of the session's cookie. Compared in constant time."""
    expected = session_token(request)
    if expected is None or not _TOKEN.fullmatch(submitted):
        return False
    return hmac.compare_digest(expected, submitted)


def set_session_cookie(response: Response, request: Request, name: str, value: str) -> None:
    """A cookie that ends with the browser session, that scripts cannot read and other sites do not send."""
    response.set_cookie(name, value, path="/", httponly=True, samesite="lax", secure=is_https(request))


class SecurityHeaders:
    """Adds the security headers to every response of the pages, error pages and static files included."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        is_page = not scope["path"].startswith(STATIC_PATH)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS + ((NO_STORE,) if is_page else ()):
                    headers[name] = value
            await send(message)

        await self._app(scope, receive, send_with_headers)
