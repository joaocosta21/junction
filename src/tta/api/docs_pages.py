"""`/docs` (Swagger UI) and `/redoc` (ReDoc): exact versions from one CDN, checked by hash (task FIX-10, 13).

Scores on the 15% "credible path toward production". These pages are served on the same origin as the
demonstration pages, so a script they load is trusted like the pages' own. FastAPI's defaults load
`swagger-ui-dist@5` (whatever the CDN serves as 5 today) and a favicon from another host. Here each asset
names an exact version and carries the hash of that file (subresource integrity: the browser refuses a file
that differs), and a Content-Security-Policy allows that CDN and nothing else, with no framing.

The hashes are SHA-384 of the files as jsDelivr served them on 14 Nov 2026; jsDelivr's own index lists the
same SHA-256 for each. Swagger UI 5.32.15 was published on 4 Sep 2026, ReDoc 2.5.4 on 10 Sep 2026.
"""

from __future__ import annotations

import base64
import hashlib

from fastapi import FastAPI
from starlette.responses import HTMLResponse

CDN = "https://cdn.jsdelivr.net"
SWAGGER_UI_VERSION = "5.32.15"
REDOC_VERSION = "2.5.4"
SWAGGER_JS = f"{CDN}/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}/swagger-ui-bundle.js"
SWAGGER_JS_SHA384 = "sha384-m7zaGj7MPzU+G4lz2eyy73GxK9bbRDr9bB2CSdj8wodg2wu/Wnt6wsoLP3JD+RS9"
SWAGGER_CSS = f"{CDN}/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}/swagger-ui.css"
SWAGGER_CSS_SHA384 = "sha384-fgyWYkUAamzuI8mJFu/xpRP0JWCJRwkwUwsYDoOYVHUJ8NQE5cENn8ib3ppwFFSX"
REDOC_JS = f"{CDN}/npm/redoc@{REDOC_VERSION}/bundles/redoc.standalone.js"
REDOC_JS_SHA384 = "sha384-w447zOpYfw/1Tv/5AK9NfHTlQIqE3RVR6KY62jCyy9zNDgO64cMwGGP1Fj0zJVf5"

DOCS_PATH = "/docs"
REDOC_PATH = "/redoc"
NO_FAVICON = "data:,"  # the browser asks no other host, and this gateway, for an icon

# The one inline script: Swagger UI's start, with FastAPI's default parameters. `validatorUrl: null` keeps
# Swagger UI from sending the document to its public validator, another host.
SWAGGER_START = (
    "SwaggerUIBundle({url: '{openapi_url}', dom_id: '#swagger-ui', layout: 'BaseLayout', deepLinking: true, "
    "showExtensions: true, showCommonExtensions: true, validatorUrl: null, "
    "presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset]});"
)

SWAGGER_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="icon" href="{favicon}">
<link rel="stylesheet" href="{css}" integrity="{css_hash}" crossorigin="anonymous">
</head>
<body>
<div id="swagger-ui"></div>
<script src="{js}" integrity="{js_hash}" crossorigin="anonymous"></script>
<script>{start}</script>
</body>
</html>
"""

REDOC_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="icon" href="{favicon}">
</head>
<body>
<redoc spec-url="{openapi_url}"></redoc>
<script src="{js}" integrity="{js_hash}" crossorigin="anonymous"></script>
</body>
</html>
"""


def _policy(*directives: str) -> str:
    return "; ".join(directives)


def _inline_hash(script: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"


def swagger_page(openapi_url: str, title: str) -> HTMLResponse:
    """Swagger UI. Its stylesheet sets some styles inline, so styles may be inline; scripts may not."""
    start = SWAGGER_START.replace("{openapi_url}", openapi_url)
    html = SWAGGER_PAGE.format(
        title=title, favicon=NO_FAVICON, css=SWAGGER_CSS, css_hash=SWAGGER_CSS_SHA384, js=SWAGGER_JS,
        js_hash=SWAGGER_JS_SHA384, start=start,
    )
    policy = _policy(
        "default-src 'none'", f"script-src {CDN} {_inline_hash(start)}", f"style-src {CDN} 'unsafe-inline'",
        "img-src 'self' data:", "connect-src 'self'", "form-action 'none'", "base-uri 'none'", "frame-ancestors 'none'",
    )
    return HTMLResponse(html, headers={"Content-Security-Policy": policy})


def redoc_page(openapi_url: str, title: str) -> HTMLResponse:
    """ReDoc. It writes its styles at run time and runs its search in a worker it builds from a blob."""
    html = REDOC_PAGE.format(
        title=title, favicon=NO_FAVICON, openapi_url=openapi_url, js=REDOC_JS, js_hash=REDOC_JS_SHA384,
    )
    policy = _policy(
        "default-src 'none'", f"script-src {CDN}", "style-src 'unsafe-inline'", "img-src 'self' data:",
        "connect-src 'self'", "worker-src blob:", "form-action 'none'", "base-uri 'none'", "frame-ancestors 'none'",
    )
    return HTMLResponse(html, headers={"Content-Security-Policy": policy})


def install_docs_pages(app: FastAPI) -> None:
    """The two pages, in place of FastAPI's (create the app with `docs_url=None, redoc_url=None`)."""
    openapi_url = app.openapi_url or "/openapi.json"

    @app.get(DOCS_PATH, include_in_schema=False)
    def docs() -> HTMLResponse:
        return swagger_page(openapi_url, f"{app.title}: interactive document")

    @app.get(REDOC_PATH, include_in_schema=False)
    def redoc() -> HTMLResponse:
        return redoc_page(openapi_url, f"{app.title}: reference")
