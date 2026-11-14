"""The checks to run right after a deployment (docs/DEPLOY.md, task T14). Standard library only.

    .venv/bin/python deploy/check.py https://<workspace>--trusted-trade-agents.modal.run

1. `GET /healthz`: answers, `environment` is demo, `mode` is the one expected (live by default).
2. `GET /`: the request page answers as HTML.
3. Scenario 2 by HTTP as the allergy ward's demo agent: `POST /v1/offers` answers 201 with at least one option.
4. Unless `--no-order`: `POST /v1/orders` on the first option answers 201, ordered or sent for approval, then the
   order's audit trail says its hash chain verifies. The order is a record in the demo's order book, which commits
   nobody, but it counts against the ward's illustrative spend limit for the day: run this step once a day.
5. `POST /mcp/` without a token is refused with 401; with the ward's token `initialize` and `tools/list` answer.
6. `POST /mcp/` with the ward's token and the `Origin` of a foreign site is refused with 403 (MCP revision 2026-07-28,
   Streamable HTTP; P12 W3).
7. `GET /.well-known/api-catalog` answers an RFC 9727 linkset (`application/linkset+json`) that links the OpenAPI
   document and the MCP endpoint (P12 W2).

The token sent is the public demonstration token of `src/tta/api/demo_tokens.yaml`. Exit status 0 when all pass.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

WARD_TOKEN = "demo-agent-allergy-ward"  # noqa: S105 - public by design (src/tta/api/demo_tokens.yaml)
TIMEOUT_SECONDS = 120.0  # a cold start loads the catalog; Modal answers a request for at most 150 s
MCP_PROTOCOL_VERSION = "2025-11-25"
MCP_ACCEPT = "application/json, text/event-stream"
SCENARIO_2 = {
    "needed_by": "2026-11-16",
    "require_confirmed": True,
    "lines": [{
        "text": "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only",
        "product_type": "plant_drink",
        "quantity": 200,
        "unit": "L",
        "exclude_allergens": ["AM", "AW"],
    }],
}
ORDER_STATUSES = ("ORDERED", "PENDING_APPROVAL")
FOREIGN_ORIGIN = "https://deploy-check.invalid"  # a name that can never be a real site (RFC 2606, ".invalid")
API_CATALOG = "/.well-known/api-catalog"
LINKSET = "application/linkset+json"
WEB_SCHEMES = ("https://", "http://")
FAILURES = (OSError, ValueError, KeyError, TypeError, IndexError)  # a failed check is reported, never raised


@dataclass(frozen=True)
class Reply:
    status: int
    content_type: str
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)


@dataclass(frozen=True)
class Result:
    name: str
    ok: bool
    detail: str


Fetch = Callable[[str, str, Mapping[str, str], bytes | None], Reply]  # method, path, headers, body


def http_fetch(base_url: str, timeout_seconds: float = TIMEOUT_SECONDS) -> Fetch:
    if not base_url.startswith(WEB_SCHEMES):
        raise ValueError("The address of the deployment starts with https:// (or http:// for a local run).")
    root = base_url.rstrip("/")

    def fetch(method: str, path: str, headers: Mapping[str, str], body: bytes | None) -> Reply:
        request = urllib.request.Request(root + path, data=body, headers=dict(headers), method=method)  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as answer:  # noqa: S310 - scheme checked
                return Reply(answer.status, answer.headers.get("Content-Type", ""), answer.read())
        except urllib.error.HTTPError as error:
            return Reply(error.code, error.headers.get("Content-Type", ""), error.read())

    return fetch


def _json_headers(token: str | None = None, **extra: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json", **extra}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _post(fetch: Fetch, path: str, payload: object, headers: Mapping[str, str]) -> Reply:
    return fetch("POST", path, headers, json.dumps(payload).encode("utf-8"))


def check_health(fetch: Fetch, expected_mode: str) -> Result:
    reply = fetch("GET", "/healthz", {"Accept": "application/json"}, None)
    if reply.status != 200:
        return Result("health", False, f"status {reply.status}")
    health = reply.json()
    settings = health.get("settings", {})
    reasons = "; ".join(health.get("reasons") or ())
    detail = (
        f"environment {health['environment']}, mode {health['mode']}, status {health['status']}"
        f"{f' ({reasons})' if reasons else ''}, source {health['source']}, "
        f"valio_key_set {settings.get('valio_key_set')}, gemini_key_set {settings.get('gemini_key_set')}, "
        f"audit events {health['audit_head']['events']}"
    )
    ok = health["environment"] == "demo" and health["mode"] == expected_mode
    return Result("health", ok, detail)


def check_page(fetch: Fetch) -> Result:
    reply = fetch("GET", "/", {"Accept": "text/html"}, None)
    ok = reply.status == 200 and reply.content_type.startswith("text/html") and b"Trusted Trade Agents" in reply.body
    return Result("page", ok, f"status {reply.status}, {reply.content_type}, {len(reply.body):,} bytes")


def check_offer(fetch: Fetch) -> tuple[Result, dict[str, Any] | None]:
    reply = _post(fetch, "/v1/offers", SCENARIO_2, _json_headers(WARD_TOKEN))
    if reply.status != 201:
        return Result("offer", False, f"status {reply.status}: {reply.body[:300]!r}"), None
    offer = reply.json()
    if not offer["options"]:
        return Result("offer", False, f"{offer['offer_id']} has no option ({offer['source']})"), None
    first = offer["options"][0]
    detail = (
        f"{offer['offer_id']}, source {offer['source']}, {len(offer['options'])} option(s), first "
        f"{first['option_id']} {first['title']!r} €{first['totals']['net']} net, verdict {first['decision']['verdict']}"
    )
    return Result("offer", True, detail), offer


def check_order(fetch: Fetch, offer: Mapping[str, Any]) -> tuple[Result, str | None]:
    choice = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"]}
    key = f"deploy-check-{int(time.time())}"
    reply = _post(fetch, "/v1/orders", choice, _json_headers(WARD_TOKEN, **{"Idempotency-Key": key}))
    if reply.status != 201:
        return Result("order", False, f"status {reply.status}: {reply.body[:300]!r}"), None
    order = reply.json()
    ok = order["status"] in ORDER_STATUSES
    detail = f"{order['order_id']} {order['status']} by {order['placed_by']}, source {order['source']}"
    return Result("order", ok, detail), order["order_id"]


def check_audit(fetch: Fetch, order_id: str) -> Result:
    reply = fetch("GET", f"/v1/audit?order_id={order_id}", _json_headers(WARD_TOKEN), None)
    if reply.status != 200:
        return Result("audit", False, f"status {reply.status}")
    trail = reply.json()
    chain = trail["chain"]
    return Result("audit", bool(chain["ok"]), f"{len(trail['events'])} events: {chain['sentence']}")


def _initialize() -> dict[str, Any]:
    return {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": MCP_PROTOCOL_VERSION, "capabilities": {},
                   "clientInfo": {"name": "deploy-check", "version": "1"}},
    }


def check_mcp_refused(fetch: Fetch) -> Result:
    reply = _post(fetch, "/mcp/", _initialize(), {"Content-Type": "application/json", "Accept": MCP_ACCEPT})
    return Result("mcp without a token", reply.status == 401, f"status {reply.status}")


def check_mcp_tools(fetch: Fetch) -> Result:
    headers = _json_headers(WARD_TOKEN, Accept=MCP_ACCEPT)
    started = _post(fetch, "/mcp/", _initialize(), headers)
    if started.status != 200:
        return Result("mcp tools", False, f"initialize: status {started.status}")
    server = started.json()["result"]["serverInfo"]["name"]
    listing = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    listed = _post(fetch, "/mcp/", listing, {**headers, "MCP-Protocol-Version": MCP_PROTOCOL_VERSION})
    if listed.status != 200:
        return Result("mcp tools", False, f"tools/list: status {listed.status}")
    names = [tool["name"] for tool in listed.json()["result"]["tools"]]
    return Result("mcp tools", bool(names), f"server {server}, {len(names)} tools: {', '.join(names)}")


def check_mcp_origin(fetch: Fetch) -> Result:
    headers = _json_headers(WARD_TOKEN, Accept=MCP_ACCEPT, Origin=FOREIGN_ORIGIN)
    reply = _post(fetch, "/mcp/", {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}, headers)
    return Result("mcp foreign origin", reply.status == 403, f"status {reply.status}")


def check_api_catalog(fetch: Fetch) -> Result:
    reply = fetch("GET", API_CATALOG, {"Accept": LINKSET}, None)
    if reply.status != 200 or not reply.content_type.startswith(LINKSET):
        return Result("api catalog", False, f"status {reply.status}, {reply.content_type}")
    links = [link["href"] for context in reply.json()["linkset"] for name, targets in context.items()
             if name != "anchor" for link in targets]
    found = [href for href in links if href.endswith(("/openapi.json", "/mcp/"))]
    return Result("api catalog", len(found) == 2, f"{len(links)} links, among them {', '.join(found) or 'none'}")


def _guarded(name: str, step: Callable[[], Any]) -> Any:
    """The step's own answer, or a failed result naming what went wrong."""
    try:
        return step()
    except FAILURES as error:
        return Result(name, False, f"{type(error).__name__}: {error}")


def _unpack(answer: Any) -> tuple[Result, Any]:
    """A step that returns a result and a value: a failed step has no value."""
    return (answer, None) if isinstance(answer, Result) else answer


def run_checks(fetch: Fetch, *, expected_mode: str = "live", place_order: bool = True) -> tuple[Result, ...]:
    results = [
        _guarded("health", lambda: check_health(fetch, expected_mode)),
        _guarded("page", lambda: check_page(fetch)),
    ]
    offer_result, offer = _unpack(_guarded("offer", lambda: check_offer(fetch)))
    results.append(offer_result)
    if place_order:
        if offer is None:
            results.append(Result("order", False, "not tried: there is no offer"))
            results.append(Result("audit", False, "not tried: there is no order"))
        else:
            order_result, order_id = _unpack(_guarded("order", lambda: check_order(fetch, offer)))
            results.append(order_result)
            results.append(
                _guarded("audit", lambda: check_audit(fetch, order_id)) if order_id
                else Result("audit", False, "not tried: there is no order")
            )
    results.append(_guarded("mcp without a token", lambda: check_mcp_refused(fetch)))
    results.append(_guarded("mcp tools", lambda: check_mcp_tools(fetch)))
    results.append(_guarded("mcp foreign origin", lambda: check_mcp_origin(fetch)))
    results.append(_guarded("api catalog", lambda: check_api_catalog(fetch)))
    return tuple(results)


def report(results: Sequence[Result]) -> str:
    lines = [f"{'PASS' if result.ok else 'FAIL'}  {result.name}: {result.detail}" for result in results]
    failed = sum(not result.ok for result in results)
    lines.append("All checks passed." if not failed else f"{failed} of {len(results)} checks failed.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a deployment of the gateway.")
    parser.add_argument("url", help="the address of the deployment, for example https://<workspace>--...modal.run")
    parser.add_argument("--mode", default="live", choices=("live", "replay"), help="the mode /healthz should show")
    parser.add_argument("--no-order", action="store_true", help="stop after the offer: place no order")
    arguments = parser.parse_args(argv)
    results = run_checks(http_fetch(arguments.url), expected_mode=arguments.mode, place_order=not arguments.no_order)
    print(report(results))
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
