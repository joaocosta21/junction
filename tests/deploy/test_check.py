"""`deploy/check.py`: the checks run right after a deployment, here against the real gateway in replay (task T14).

The script's HTTP layer is replaced by one that hands each request to the application in memory: no network.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.mcp_surface import TOOL_NAMES
from tta.config import Settings
from tta.contracts.common import DataSource

WARD_TOKEN = "demo-agent-allergy-ward"
EVERY_CHECK = (
    "health", "page", "offer", "order", "audit", "mcp without a token", "mcp tools", "mcp foreign origin",
    "api catalog", "signing key",
)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings.for_tests(tta_env="demo", tta_mode=DataSource.REPLAY, tta_data_dir=tmp_path / "var")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _fetch(check: ModuleType, client: TestClient) -> Any:
    def fetch(method: str, path: str, headers: Mapping[str, str], body: bytes | None) -> Any:
        answer = client.request(method, path, headers=dict(headers), content=body)
        return check.Reply(answer.status_code, answer.headers.get("content-type", ""), answer.content)

    return fetch


def test_every_check_passes_against_the_gateway(check: ModuleType, client: TestClient) -> None:
    results = check.run_checks(_fetch(check, client), expected_mode="replay")

    assert [result.name for result in results] == list(EVERY_CHECK)
    assert all(result.ok for result in results), [result for result in results if not result.ok]
    by_name = {result.name: result.detail for result in results}
    assert "PENDING_APPROVAL" in by_name["order"]  # every order waits for a person (F-10)
    assert "replay" in by_name["offer"]
    assert f"{len(TOOL_NAMES)} tools" in by_name["mcp tools"]  # counted from the surface (13 since L4-2b)
    assert by_name["mcp foreign origin"] == "status 403"  # P12 W3
    assert "/openapi.json" in by_name["api catalog"] and "/mcp/" in by_name["api catalog"]  # P12 W2, before the pages


def test_with_no_order_asked_for_none_is_placed(check: ModuleType, client: TestClient) -> None:
    results = check.run_checks(_fetch(check, client), expected_mode="replay", place_order=False)

    assert [result.name for result in results] == [
        "health", "page", "offer", "mcp without a token", "mcp tools", "mcp foreign origin", "api catalog",
        "signing key",
    ]
    assert all(result.ok for result in results)
    assert client.get("/v1/orders", headers={"Authorization": f"Bearer {WARD_TOKEN}"}).json() == []


def test_a_gateway_in_the_wrong_mode_fails_the_health_check(check: ModuleType, client: TestClient) -> None:
    results = check.run_checks(_fetch(check, client), expected_mode="live", place_order=False)

    health = results[0]
    assert (health.name, health.ok) == ("health", False)
    assert "mode replay (--mode live was asked for)" in health.detail
    assert all(result.ok for result in results[1:])


def test_a_gateway_that_cannot_be_reached_fails_every_check_without_raising(check: ModuleType) -> None:
    def unreachable(method: str, path: str, headers: Mapping[str, str], body: bytes | None) -> Any:
        raise ConnectionRefusedError("connection refused")

    results = check.run_checks(unreachable)

    assert results and not any(result.ok for result in results)
    assert "connection refused" in results[0].detail


@pytest.mark.parametrize("address", ["file:///etc/passwd", "ftp://example.org", "example.org", ""])
def test_only_a_web_address_is_accepted(check: ModuleType, address: str) -> None:
    with pytest.raises(ValueError, match="https://"):
        check.http_fetch(address)


def test_the_report_has_one_line_per_check_and_says_whether_all_passed(check: ModuleType) -> None:
    results = (check.Result("health", True, "ok"), check.Result("page", False, "status 500"))

    assert check.report(results) == "PASS  health: ok\nFAIL  page: status 500\n1 of 2 checks failed."
    # The count comes from the results, never from a typed number.
    assert check.report(results[:1]) == "PASS  health: ok\nAll 1 checks passed."
    assert check.report(results[:1] * 9).endswith("All 9 checks passed.")


def _scripted(check: ModuleType, replies: Mapping[tuple[str, str], Any]) -> Any:
    """Answers each (method, path) as scripted, and anything else with a 500."""

    def fetch(method: str, path: str, headers: Mapping[str, str], body: bytes | None) -> Any:
        return replies.get((method, path.split("?", 1)[0]), check.Reply(500, "text/plain", b"not scripted"))

    return fetch


def _offer(check: ModuleType, options: list[dict[str, Any]]) -> Any:
    body = {"offer_id": "off_1", "source": "live", "options": options}
    return check.Reply(201, "application/json", json.dumps(body).encode())


OPTION = {"option_id": "opt_1", "title": "Best confirmed option", "totals": {"net": 402.0},
          "decision": {"verdict": "AUTO"}}


def test_a_refused_offer_leaves_the_order_and_the_audit_untried(check: ModuleType) -> None:
    results = {result.name: result for result in check.run_checks(_scripted(check, {}))}

    assert [results[name].ok for name in EVERY_CHECK] == [False] * len(EVERY_CHECK)
    assert results["health"].detail == "status 500"
    assert results["offer"].detail.startswith("status 500")
    assert results["order"].detail == "not tried: there is no offer"
    assert results["audit"].detail == "not tried: there is no order"
    assert results["mcp tools"].detail == "initialize: status 500"
    assert results["mcp foreign origin"].detail == "status 500"
    assert results["api catalog"].detail.startswith("status 500")


def test_an_offer_with_no_option_fails_and_no_order_is_tried(check: ModuleType) -> None:
    fetch = _scripted(check, {("POST", "/v1/offers"): _offer(check, [])})

    results = {result.name: result for result in check.run_checks(fetch)}

    assert (results["offer"].ok, results["offer"].detail) == (False, "off_1 has no option (live)")
    assert results["order"].detail == "not tried: there is no offer"


def test_a_refused_order_leaves_the_audit_untried(check: ModuleType) -> None:
    refused = check.Reply(409, "application/problem+json", b'{"type": "offer-stale"}')
    fetch = _scripted(check, {("POST", "/v1/offers"): _offer(check, [OPTION]), ("POST", "/v1/orders"): refused})

    results = {result.name: result for result in check.run_checks(fetch)}

    assert results["offer"].ok
    assert (results["order"].ok, results["order"].detail[:10]) == (False, "status 409")
    assert results["audit"].detail == "not tried: there is no order"


def test_an_answer_that_is_not_the_expected_json_is_a_failed_check(check: ModuleType) -> None:
    garbled = check.Reply(200, "application/json", b"<html>")
    fetch = _scripted(check, {("GET", "/healthz"): garbled})

    health = check.run_checks(fetch, place_order=False)[0]

    assert (health.name, health.ok) == ("health", False)
    assert health.detail.startswith("JSONDecodeError")


def test_a_catalog_that_is_not_the_rfc_9727_linkset_fails(check: ModuleType) -> None:
    page = check.Reply(404, "text/html; charset=utf-8", b"<html>Not found</html>")  # what demo answered before W2
    fetch = _scripted(check, {("GET", "/.well-known/api-catalog"): page})

    catalog = next(r for r in check.run_checks(fetch, place_order=False) if r.name == "api catalog")

    assert (catalog.name, catalog.ok) == ("api catalog", False)
    assert catalog.detail.startswith("status 404")


def test_an_mcp_endpoint_that_serves_a_foreign_origin_fails(check: ModuleType) -> None:
    served = check.Reply(200, "application/json", b'{"result": {"tools": []}}')  # what it answered before W3
    fetch = _scripted(check, {("POST", "/mcp/"): served})

    results = {result.name: result for result in check.run_checks(fetch, place_order=False)}

    assert (results["mcp foreign origin"].ok, results["mcp foreign origin"].detail) == (False, "status 200")


# --- the mode is the link's own unless one is asked for ---------------------------------------------------------------


def test_without_a_mode_the_links_own_mode_is_read_from_healthz_and_said(check: ModuleType, client: TestClient) -> None:
    results = check.run_checks(_fetch(check, client), place_order=False)

    assert results[0].ok
    assert "mode replay (read from /healthz: no --mode was given)" in results[0].detail
    assert check.report(results).endswith(f"All {len(results)} checks passed.")


def test_the_command_line_has_no_default_mode(check: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def noting(fetch: Any, **options: Any) -> tuple[Any, ...]:
        seen.update(options)
        return ()

    monkeypatch.setattr(check, "run_checks", noting)
    monkeypatch.setattr(check, "http_fetch", lambda url: None)

    check.main(["https://example.invalid"])
    assert seen == {"expected_mode": None, "place_order": True}
    check.main(["https://example.invalid", "--mode", "replay", "--no-order"])
    assert seen == {"expected_mode": "replay", "place_order": False}


def test_a_mode_that_is_neither_replay_nor_live_fails(check: ModuleType) -> None:
    body = {"environment": "demo", "mode": "mock", "status": "ok", "source": "x", "audit_head": {"events": 0}}
    fetch = _scripted(check, {("GET", "/healthz"): check.Reply(200, "application/json", json.dumps(body).encode())})

    assert not check.run_checks(fetch, place_order=False)[0].ok


# --- the signing key -------------------------------------------------------------------------------------------------

KEY = {"kty": "OKP", "crv": "Ed25519", "x": "abc", "kid": "kid-1"}


def _signing(check: ModuleType, keys: list[dict[str, Any]], health: dict[str, Any] | None) -> Any:
    key_set = check.Reply(200, "application/json", json.dumps({"keys": keys}).encode())
    replies = {("GET", "/.well-known/jwks.json"): key_set}
    if health is not None:
        replies[("GET", "/healthz")] = check.Reply(200, "application/json", json.dumps(health).encode())
    return check.check_signing_key(_scripted(check, replies))


def test_the_gateways_key_set_holds_one_ed25519_key_and_the_check_says_it_is_a_demo_key(
    check: ModuleType, client: TestClient
) -> None:
    result = check.check_signing_key(_fetch(check, client))  # no TTA_SIGNING_KEY in the test settings

    assert result.ok and result.detail.startswith("one Ed25519 key, kid ")
    assert result.detail.endswith("/healthz says it is a demo key: generated at start, so signatures stop verifying "
                                  "at the next start")


def test_a_key_that_was_set_is_said_so(check: ModuleType) -> None:
    result = _signing(check, [KEY], {"signing": {"key_id": "kid-1", "demo_key": False}})

    assert (result.ok, result.detail) == (True, "one Ed25519 key, kid kid-1; /healthz says it is a key that was set")


@pytest.mark.parametrize(("keys", "health", "detail"), [
    ([], None, "0 key(s), 0 of them Ed25519: one was expected"),
    ([KEY, {**KEY, "kid": "kid-2"}], None, "2 key(s), 2 of them Ed25519: one was expected"),
    ([{"kty": "RSA", "kid": "r"}], None, "1 key(s), 0 of them Ed25519: one was expected"),
    ([KEY], {"signing": {"key_id": "another", "demo_key": True}}, "the key at /healthz is not the key of the key set"),
])
def test_a_key_set_that_is_not_one_ed25519_key_fails(
    check: ModuleType, keys: list[dict[str, Any]], health: dict[str, Any] | None, detail: str
) -> None:
    result = _signing(check, keys, health)

    assert (result.ok, result.detail) == (False, detail)


def test_a_health_answer_that_does_not_say_is_reported_and_no_key_set_fails(check: ModuleType) -> None:
    silent = _signing(check, [KEY], None)
    missing = check.check_signing_key(_scripted(check, {}))

    assert (silent.ok, silent.detail) == (True, "one Ed25519 key, kid kid-1; /healthz does not say whether it is a "
                                                "demo key")
    assert (missing.ok, missing.detail) == (False, "status 500")
