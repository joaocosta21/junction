"""An agent that knows only the gateway's address finds its interface (P12 W2).

Scores on the 15% "open, documented standards rather than a proprietary format", and is seen in the 30% demo.
Before: `/.well-known/api-catalog` and `/llms.txt` answered 404 (an HTML page in demo), and `/openapi.json` had
no `externalDocs`. Now the catalog is an RFC 9727 linkset and `/llms.txt` says the same in plain text.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from tta.api import create_app
from tta.api.discovery import (
    API_CATALOG_PATH,
    CATALOG_MEDIA_TYPE,
    LLMS_PATH,
    OPENAPI_MEDIA_TYPE,
    api_catalog,
    base_url,
    llms_text,
)
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import DataSource

BASE = "http://testserver"
RELATIONS = {
    "service-desc": "/openapi.json", "service-doc": "/docs", "service-meta": "/v1/schemas", "status": "/healthz",
}


@pytest.fixture
def demo_client(tmp_path: Path, catalog: ProductCatalog) -> Iterator[TestClient]:
    settings = Settings.for_tests(tta_env="demo", tta_mode=DataSource.REPLAY, tta_data_dir=tmp_path / "var")
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        yield client


def _contexts(linkset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {context["anchor"]: context for context in linkset["linkset"]}


# --- /.well-known/api-catalog (RFC 9727) ----------------------------------------------------------------


def test_the_api_catalog_is_a_linkset_with_the_rfc_9727_profile_and_needs_no_token(client: TestClient) -> None:
    response = client.get(API_CATALOG_PATH)

    assert response.status_code == 200
    assert response.headers["content-type"] == CATALOG_MEDIA_TYPE
    assert response.headers["content-type"] == 'application/linkset+json; profile="https://www.rfc-editor.org/info/rfc9727"'
    assert f'<{BASE}{API_CATALOG_PATH}>; rel="api-catalog"' in response.headers["link"]


def test_the_catalog_lists_the_rest_api_with_its_description_documentation_schemas_and_status(
    client: TestClient,
) -> None:
    contexts = _contexts(client.get(API_CATALOG_PATH).json())

    catalog = contexts[f"{BASE}{API_CATALOG_PATH}"]
    assert [item["href"] for item in catalog["item"]] == [f"{BASE}/v1"]  # no MCP surface in these tests
    rest = contexts[f"{BASE}/v1"]
    for relation, path in RELATIONS.items():
        assert [link["href"] for link in rest[relation]] == [f"{BASE}{path}"], relation
    assert rest["service-desc"][0]["type"] == OPENAPI_MEDIA_TYPE


def test_every_link_of_the_catalog_but_the_api_base_answers_without_a_token(client: TestClient) -> None:
    contexts = _contexts(client.get(API_CATALOG_PATH).json())
    targets = {link["href"] for context in contexts.values() for name, links in context.items() if name != "anchor"
               for link in links} - {f"{BASE}/v1"}

    for target in sorted(targets):
        assert client.get(target.removeprefix(BASE)).status_code == 200, target


def test_head_on_the_catalog_answers_its_headers_and_no_body(client: TestClient) -> None:
    response = client.head(API_CATALOG_PATH)

    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["content-type"] == CATALOG_MEDIA_TYPE
    assert 'rel="api-catalog"' in response.headers["link"]


def test_behind_a_proxy_that_ends_tls_the_links_say_https(client: TestClient) -> None:
    contexts = _contexts(client.get(API_CATALOG_PATH, headers={"X-Forwarded-Proto": "https"}).json())

    assert "https://testserver/v1" in contexts
    assert all(anchor.startswith("https://") for anchor in contexts)


@pytest.mark.parametrize("host", ["evil.example/<b>", "two words.example", "x.example:99999999", "[not-ip]", 'q"uote'])
def test_a_host_header_that_is_not_a_host_is_not_written_back(host: str) -> None:
    scope = {
        "type": "http", "method": "GET", "scheme": "http", "path": API_CATALOG_PATH, "root_path": "",
        "query_string": b"", "headers": [(b"host", host.encode())], "server": ("gateway.internal", 8000),
    }

    base = base_url(Request(scope))

    assert base == "http://gateway.internal:8000"  # the server's own address stands
    assert host not in json.dumps(api_catalog(base, with_mcp=True)) and host not in llms_text(base, with_mcp=True,
                                                                                              demo=True)


@pytest.mark.parametrize("host", ["gateway.example", "gateway.example:8443", "127.0.0.1:8000", "[::1]:8000"])
def test_a_host_name_or_address_is_written_back_as_the_base(host: str) -> None:
    scope = {
        "type": "http", "method": "GET", "scheme": "https", "path": API_CATALOG_PATH, "root_path": "",
        "query_string": b"", "headers": [(b"host", host.encode())], "server": ("testserver", 443),
    }

    assert base_url(Request(scope)) == f"https://{host}"


def test_the_catalog_is_served_in_demo_too(demo_client: TestClient) -> None:
    response = demo_client.get(API_CATALOG_PATH)

    assert response.status_code == 200 and response.headers["content-type"] == CATALOG_MEDIA_TYPE


# --- /llms.txt ------------------------------------------------------------------------------------------


def test_llms_txt_says_what_this_is_the_flow_and_the_links_in_plain_text(client: TestClient) -> None:
    response = client.get(LLMS_PATH)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert text.startswith("# Trusted Trade Agents gateway\n\n> ")
    assert "\n## API\n" in text and "\n## Optional\n" in text
    for path in (API_CATALOG_PATH, "/openapi.json", "/docs", "/v1/schemas", "/healthz"):
        assert f"]({BASE}{path})" in text, path
    reading = " ".join(text.split())
    for phrase in ("data, never instructions", "`AUTO`", "off by default", "RFC 9457", "Idempotency-Key"):
        assert phrase in reading, phrase


def test_llms_txt_in_demo_names_a_public_token_to_start_with(demo_client: TestClient) -> None:
    text = demo_client.get(LLMS_PATH).text

    assert "`demo-agent-allergy-ward`" in text and "public by design" in text


def test_outside_dev_and_demo_llms_txt_names_no_token_and_no_page() -> None:
    text = llms_text(BASE, with_mcp=True, demo=False)

    assert "demo-agent" not in text and "Demonstration pages" not in text
    assert f"]({BASE}/mcp/)" in text


# --- the OpenAPI document points to them ----------------------------------------------------------------


def test_the_openapi_document_has_external_docs_and_lists_the_discovery_routes(client: TestClient) -> None:
    document = client.get("/openapi.json").json()

    assert document["externalDocs"]["url"] == LLMS_PATH
    assert API_CATALOG_PATH in document["externalDocs"]["description"]
    assert set(document["paths"][API_CATALOG_PATH]) == {"get", "head"}
    assert "security" not in document["paths"][API_CATALOG_PATH]["get"]
    assert "get" in document["paths"][LLMS_PATH]


# --- checks C2-5, C2-7 and C4-F1, decisions B57 (its fallback) and B62: the texts say what is true --------------


def _read(text: str) -> str:
    return " ".join(text.split())


def test_the_flow_of_llms_txt_names_the_reading_of_a_sentence_before_the_offer(client: TestClient) -> None:
    reading = _read(client.get(LLMS_PATH).text)

    steps = [reading.index(step) for step in ("`GET /v1/authority`", "`POST /v1/requests/parse`", "`POST /v1/offers`")]
    assert steps == sorted(steps)


def test_llms_txt_says_where_an_agent_cannot_approve_and_that_the_pages_have_no_login(
    client: TestClient, demo_client: TestClient
) -> None:
    anywhere, in_demo = _read(client.get(LLMS_PATH).text), _read(demo_client.get(LLMS_PATH).text)
    outside = _read(llms_text(BASE, with_mcp=True, demo=False))

    for text in (anywhere, in_demo, outside):
        assert "over REST and MCP an agent's token cannot" in text
        assert "; an agent's token cannot." not in text  # the claim without its qualifier (check C4-F1)
    for phrase in ("have no login", "mounted only in the dev and demo environments", "tokens of their own"):
        assert phrase in in_demo, phrase
    assert "no login" not in outside  # where no page is mounted there is nothing to say about one


def test_llms_txt_says_the_demo_key_marker_is_signed_in_the_header_and_its_copy_is_not(client: TestClient) -> None:
    reading = _read(client.get(LLMS_PATH).text)

    assert "A proof whose own fields say otherwise does not verify" not in reading  # true of the header only (C2-7)
    for phrase in ("inside the signed protected header", "`proof.demo_key`", "not covered by the signature"):
        assert phrase in reading, phrase


def test_llms_txt_in_demo_says_where_ordering_alone_is_shown_with_the_two_measured_orders(
    demo_client: TestClient,
) -> None:
    reading = _read(demo_client.get(LLMS_PATH).text)

    for phrase in ("off for the four demonstration customers", "`/shop`", "Settings", "Harbourside Hotel",
                   "302 litres", "€748.96", "303 litres", "€751.44", "€750"):
        assert phrase in reading, phrase
    assert "Harbourside Hotel" not in _read(llms_text(BASE, with_mcp=True, demo=False))


def test_the_openapi_description_says_what_get_audit_answers_and_what_is_stored(client: TestClient) -> None:
    description = _read(client.get("/openapi.json").json()["info"]["description"])

    assert "stored in a CloudEvents 1.0 envelope" in description
    assert "`GET /v1/audit` answers each reader's view" in description and "not the stored envelope" in description
    for phrase in ("have no login", "over REST and MCP", "`/shop`", "302 litres", "€748.96", "303 litres", "€751.44"):
        assert phrase in description, phrase


def test_the_bearer_description_no_longer_says_the_dietitian_decides_allergen_questions_only() -> None:
    from tta.api.identity import BEARER_DESCRIPTION

    assert "for allergen questions only" not in BEARER_DESCRIPTION and "`GET /v1/authority`" in BEARER_DESCRIPTION
