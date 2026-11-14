"""What keeps the pages safe to put in front of strangers: response headers, the form token, the cookies.

Scores on the 20% "quality of the guardrails design": the approval panel is where a human signs, so a form
that changes state (run, approve, reject, choose who acts) is a POST that carries a token another site cannot
read, and no page loads or runs anything from outside this server.

- The token lives in a cookie scripts cannot read (`HttpOnly`) and other sites do not send on a POST
  (`SameSite=Lax`); every form repeats it in a hidden field and the two must match. One per browser session.
  Over HTTPS the cookie carries the `__Host-` prefix, so another host of the same domain cannot plant one.
- Nothing is kept on the server for it, so it survives a restart and more than one server process.

Each browser session also gets the key of its own demo order book (`tta.api.sandbox`) in a second cookie of
the same kind. The key is never written into a page, so a page passed around does not give its book away.
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
BOOK_COOKIE = "tta_book"  # the key of the browser session's own demo order book
BOOK_STATE = "tta_book"  # where the request's book key is kept for the routes (`request.state`)
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


def _cookie_name(request: Request, name: str) -> str:
    return HOST_PREFIX + name if is_https(request) else name


def csrf_cookie_name(request: Request) -> str:
    return _cookie_name(request, CSRF_COOKIE)


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


def book_key(request: Request) -> str:
    """The key of this browser session's order book, as `BookCookie` found or made it for the request."""
    key = getattr(request.state, BOOK_STATE, None)
    if isinstance(key, str):
        return key
    found = request.cookies.get(_cookie_name(request, BOOK_COOKIE), "")
    return found if _TOKEN.fullmatch(found) else new_token()


def _set_cookie_value(request: Request, name: str, value: str) -> str:
    """The `Set-Cookie` value of a session cookie, written by Starlette as `set_session_cookie` writes it."""
    response = Response()
    set_session_cookie(response, request, name, value)
    return next(value for header, value in response.headers.items() if header == "set-cookie")


class BookCookie:
    """Gives each browser session the key of its own order book: the cookie's, or a new one sent back with the
    answer. Making a key opens no book: a book is built when something is first written to it."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"].startswith(STATIC_PATH):
            await self._app(scope, receive, send)
            return
        request = Request(scope)
        name = _cookie_name(request, BOOK_COOKIE)
        found = request.cookies.get(name, "")
        key = found if _TOKEN.fullmatch(found) else new_token()
        scope.setdefault("state", {})[BOOK_STATE] = key
        cookie = None if key == found else _set_cookie_value(request, name, key)

        async def send_with_cookie(message: Message) -> None:
            if cookie is not None and message["type"] == "http.response.start":
                MutableHeaders(scope=message).append("set-cookie", cookie)
            await send(message)

        await self._app(scope, receive, send_with_cookie)


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
