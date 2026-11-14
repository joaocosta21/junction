"""`/docs` and `/redoc` load exact, checked versions from one CDN, under a Content-Security-Policy (FIX-10, 13).

Scores on the 15% "credible path toward production": the interactive document is served on the same origin
as the pages, so a script it loads is trusted like the pages' own. It names an exact version, carries the
file's hash (subresource integrity), and the policy allows that CDN and nothing else.
"""

from __future__ import annotations

import base64
import hashlib
import re

import pytest
from fastapi.testclient import TestClient

from tta.api.docs_pages import CDN, REDOC_VERSION, SWAGGER_UI_VERSION

SCRIPT_OR_STYLE = re.compile(r'<(?:script\b[^>]*\bsrc|link rel="stylesheet"[^>]*\bhref)="([^"]+)"[^>]*>', re.IGNORECASE)
INLINE_SCRIPT = re.compile(r"<script>(.*?)</script>", re.DOTALL)
EXACT_VERSION = re.compile(r"@\d+\.\d+\.\d+/")


def _policy(response: object) -> dict[str, list[str]]:
    header = response.headers["content-security-policy"]  # type: ignore[attr-defined]
    return {name: values for name, *values in (part.split() for part in header.split(";") if part.strip())}


@pytest.mark.parametrize("path", ["/docs", "/redoc"])
def test_each_asset_names_an_exact_version_on_the_one_cdn_and_carries_its_hash(client: TestClient, path: str) -> None:
    page = client.get(path)

    assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
    tags = [tag for tag in SCRIPT_OR_STYLE.finditer(page.text)]
    assert tags, path
    for tag in tags:
        address = tag.group(1)
        assert address.startswith(CDN + "/npm/") and EXACT_VERSION.search(address), address
        assert re.search(r'integrity="sha384-[A-Za-z0-9+/]{64}"', tag.group(0)), address
        assert 'crossorigin="anonymous"' in tag.group(0), address
    assert "fastapi.tiangolo.com" not in page.text and "fonts.googleapis.com" not in page.text
    assert '<link rel="icon" href="data:,">' in page.text  # no icon is asked of another host


def test_the_versions_are_pinned() -> None:
    assert (SWAGGER_UI_VERSION, REDOC_VERSION) == ("5.32.15", "2.5.4")


@pytest.mark.parametrize("path", ["/docs", "/redoc"])
def test_the_policy_allows_only_the_cdn_and_no_framing(client: TestClient, path: str) -> None:
    policy = _policy(client.get(path))

    assert policy["default-src"] == ["'none'"]
    assert policy["frame-ancestors"] == ["'none'"] and policy["base-uri"] == ["'none'"]
    hosts = {value for values in policy.values() for value in values if "://" in value}
    assert hosts == {CDN}
    assert policy["connect-src"] == ["'self'"]  # the document itself, and "Try it out" on this gateway
    assert "'unsafe-inline'" not in policy["script-src"]


def test_the_one_inline_script_of_docs_is_allowed_by_its_hash_and_nothing_else_inline(client: TestClient) -> None:
    page = client.get("/docs")
    inline = INLINE_SCRIPT.findall(page.text)
    digest = base64.b64encode(hashlib.sha256(inline[0].encode()).digest()).decode()

    assert len(inline) == 1 and "SwaggerUIBundle" in inline[0]
    assert _policy(page)["script-src"] == [CDN, f"'sha256-{digest}'"]


def test_the_documents_themselves_are_still_served(client: TestClient) -> None:
    assert client.get("/openapi.json").status_code == 200
    assert "/docs" not in client.get("/openapi.json").json()["paths"]
