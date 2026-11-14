"""The pages take no external asset, run no inline script, and change state only through a POST with a token."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

Post = Callable[..., Any]
MakeClient = Callable[..., TestClient]
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)", re.IGNORECASE)
INLINE_HANDLER = re.compile(r"<[^>]+\son[a-z]+\s*=", re.IGNORECASE)
INLINE_STYLE = re.compile(r"<style|<[^>]+\sstyle\s*=", re.IGNORECASE)
# An asset or a form target on another host. A plain link in the assumptions document is not an asset.
EXTERNAL = re.compile(
    r"""<(?:script|img|link|form|iframe|source)\b[^>]*\b(?:src|href|action)\s*=\s*["'](?:https?:)?//""", re.IGNORECASE
)


def _all_pages(client: TestClient, run_example: Post, only_order: Callable[..., Any]) -> dict[str, Any]:
    result = run_example(client, "scenario-1")
    order_id = only_order(client).order_id
    pages = {path: client.get(path) for path in (
        "/", "/approvals", "/assumptions", f"/orders/{order_id}", f"/orders/{order_id}?view=supplier", "/nope",
    )}
    return {**pages, "result": result}


def test_every_page_sets_a_content_security_policy_with_no_external_source_and_no_inline_script(
    client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    for name, response in _all_pages(client, run_example, only_order).items():
        policy = response.headers["content-security-policy"]
        assert "default-src 'none'" in policy, name
        assert "script-src 'self'" in policy and "style-src 'self'" in policy, name
        assert "unsafe-inline" not in policy and "unsafe-eval" not in policy and "http" not in policy, name
        assert "form-action 'self'" in policy and "frame-ancestors 'none'" in policy, name
        assert response.headers["x-content-type-options"] == "nosniff", name
        assert response.headers["referrer-policy"] == "no-referrer", name
        assert response.headers["cache-control"] == "no-store", name


def test_each_security_header_is_sent_once_though_the_api_sets_two_of_them_too(
    client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    for name, response in _all_pages(client, run_example, only_order).items():
        for header in ("content-security-policy", "x-content-type-options", "referrer-policy", "cache-control"):
            assert len(response.headers.get_list(header)) == 1, (name, header)


def test_no_page_carries_inline_script_inline_style_or_an_external_address(
    client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    for name, response in _all_pages(client, run_example, only_order).items():
        assert not INLINE_SCRIPT.search(response.text), name
        assert not INLINE_HANDLER.search(response.text), name
        assert not INLINE_STYLE.search(response.text), name
        assert not EXTERNAL.search(response.text), name
    script = client.get("/static/app.js").text
    assert "eval(" not in script and "innerHTML" not in script


def test_the_form_token_and_the_book_are_cookies_scripts_cannot_read_and_other_sites_do_not_send(
    client: TestClient,
) -> None:
    cookies = client.get("/").headers.get_list("set-cookie")

    assert sorted(cookie.split("=")[0] for cookie in cookies) == ["tta_book", "tta_csrf"]
    for cookie in cookies:
        assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
        assert "Max-Age" not in cookie and "expires" not in cookie.lower()  # it ends with the browser session
    assert "set-cookie" not in client.get("/").headers  # one of each per session, not per page


def test_over_https_the_cookie_is_secure_and_bound_to_the_host(make_client: MakeClient) -> None:
    client = make_client(base_url="https://testserver")

    cookies = client.get("/").headers.get_list("set-cookie")

    assert sorted(cookie.split("=")[0] for cookie in cookies) == ["__Host-tta_book", "__Host-tta_csrf"]
    for cookie in cookies:
        assert "Secure" in cookie and "HttpOnly" in cookie and "Domain" not in cookie


def test_over_https_every_answer_tells_the_browser_to_keep_to_https_for_a_year(make_client: MakeClient) -> None:
    """A3 F6: the pages rely on the host's TLS; the header makes the browser refuse plain HTTP to them."""
    direct = make_client(base_url="https://testserver")
    proxied = make_client()  # behind the host's proxy, which says the browser came over HTTPS

    answers = (
        direct.get("/"), direct.get("/approvals"), direct.get("/nope"), direct.get("/static/app.css"),
        proxied.get("/", headers={"X-Forwarded-Proto": "https"}),
    )

    for answer in answers:
        assert answer.headers.get_list("strict-transport-security") == ["max-age=31536000"], answer.url


def test_over_plain_http_no_answer_carries_the_https_header(client: TestClient) -> None:
    assert "strict-transport-security" not in client.get("/").headers


def test_a_run_without_the_token_or_with_a_wrong_one_is_refused_and_nothing_is_ordered(
    client: TestClient, form_fields: Callable[..., Any], orders: Callable[..., Any]
) -> None:
    fields = form_fields(client)
    sandboxes = client.app.state.parts.sandboxes  # type: ignore[attr-defined]

    missing = client.post("/run", data={"example": "scenario-2"})
    wrong = client.post("/run", data={**fields, "csrf": "y" * 43, "example": "scenario-2"})
    client.cookies.clear()
    no_cookie = client.post("/run", data={**fields, "example": "scenario-2"})

    assert (missing.status_code, wrong.status_code, no_cookie.status_code) == (403, 403, 403)
    assert "Nothing was changed" in wrong.text
    assert orders(client, "agent:allergy-ward") == ()
    assert len(sandboxes) == 0  # a refused form opens no order book


def test_state_changes_only_through_post(client: TestClient) -> None:
    assert client.get("/run").status_code == 405
    assert client.get("/approvals/as").status_code == 405
    assert client.get("/approvals/apr_x/decision").status_code == 405


def test_a_cookie_that_names_nobody_falls_back_to_the_first_demo_identity(client: TestClient) -> None:
    client.cookies.set("tta_agent", "agent:made-up")
    client.cookies.set("tta_approver", "agent:hotel-kitchen")  # an agent is never an approver

    first_page, approvals = client.get("/"), client.get("/approvals")

    assert first_page.status_code == 200 and approvals.status_code == 200
    assert re.search(r'name="who"[^>]*value="agent:hotel-kitchen"[^>]*checked', first_page.text)
    assert re.search(r'<option value="human:hotel-purchasing" selected', approvals.text)
