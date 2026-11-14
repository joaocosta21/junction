"""`GET /healthz`: what is running, where the data comes from, and the head of the audit chain.

Scores on the 20% "how decisions are logged and auditable" (a head another party can keep shows a trail cut
short) and on the 15% path to production.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

import tta.api.app as app_module
from tta.api import create_app, wiring
from tta.api.wiring import STORE_FALLBACK, STORE_IS_POSTGRESQL, STORE_IS_SQLITE, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.audit import GENESIS_HASH
from tta.contracts.errors import SupplierUnavailable
from tta.store import SqliteStore

Flow = Callable[..., dict[str, Any]]
SECRET = "a-value-that-must-never-leave-the-process"


def test_health_needs_no_token_and_says_what_is_running(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["reasons"]) == ("ok", [])
    assert (body["environment"], body["mode"], body["source"]) == ("dev", "replay", "replay")
    assert body["audit_head"] == {"events": 0, "last_hash": GENESIS_HASH}
    assert body["settings"]["replay_capture"] == "2026-11-14-demo"
    assert body["agent"] == {"request_parser": False, "agent_runner": False}
    # No agent package in these tests, so nothing reads a sentence.
    assert (body["agent_reader"]["kind"], body["agent_reader"]["model"]) == ("none", None)
    assert body["surfaces"] == {"mcp": False, "pages": False}


def test_the_audit_head_moves_with_every_event(
    client: TestClient, parts: Any, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    make_offer(client, "agent_ward", scenario_2)

    head = client.get("/healthz").json()["audit_head"]

    assert head["events"] >= 4
    assert head["last_hash"] == parts.store.last_audit_hash() != GENESIS_HASH


def test_health_reads_the_whole_trail_once_and_then_only_its_last_hash(
    client: TestClient, parts: Any, scenario_2: dict[str, Any], make_offer: Flow, monkeypatch: Any
) -> None:
    # The route is public and not rate limited: a caller must not be able to make it read every event each time.
    whole_trail_reads: list[int] = []
    genuine = parts.store.list_audit_events

    def counted(*args: Any, **kwargs: Any) -> Any:
        # A read of one offer's or one buyer's events (the suggestions do both when an offer is made) is not a
        # read of the whole trail: only a call that names no offer, order, approval or buyer is counted.
        if not args and all(value is None for value in kwargs.values()):
            whole_trail_reads.append(1)
        return genuine(*args, **kwargs)

    monkeypatch.setattr(parts.store, "list_audit_events", counted)

    empty = [client.get("/healthz").json()["audit_head"] for _ in range(5)]
    make_offer(client, "agent_ward", scenario_2)
    after = [client.get("/healthz").json()["audit_head"] for _ in range(5)]

    assert empty == [{"events": 0, "last_hash": GENESIS_HASH}] * 5
    assert after == [{"events": len(genuine()), "last_hash": parts.store.last_audit_hash()}] * 5
    assert len(whole_trail_reads) == 1


@pytest.mark.parametrize(
    ("given", "installed", "kind", "model"),
    [
        ({}, True, "fixed_rules", None),
        ({}, False, "none", None),
        # `TTA_AGENT_PROVIDER=none` with a Gemini key: Gemini is asked first, as `tta.agent` builds it.
        ({"gemini_api_key": SECRET}, True, "gemini", None),
        ({"gemini_api_key": SECRET, "tta_gemini_model": "gemini-x"}, True, "gemini", "gemini-x"),
        ({"gemini_api_key": SECRET, "tta_agent_provider": "openai_compatible",
          "tta_agent_base_url": "https://example.invalid/v1", "tta_agent_model": "qwen"}, True,
         "openai_compatible", "qwen"),
        # The provider is chosen and its address is missing: no endpoint is asked, and no key means no Gemini.
        ({"tta_agent_provider": "openai_compatible", "tta_agent_model": "qwen"}, True, "fixed_rules", None),
    ],
)
def test_health_says_which_reader_of_sentences_is_in_use_from_the_settings_alone(
    tmp_path: Any, given: dict[str, Any], installed: bool, kind: str, model: str | None
) -> None:
    from tta.api.health import READER_SENTENCES, _agent_reader

    reader = _agent_reader(Settings.for_tests(tta_data_dir=tmp_path / "var", **given), installed=installed)

    assert (reader.kind, reader.model, reader.sentence) == (kind, model, READER_SENTENCES[kind])
    assert SECRET not in reader.model_dump_json() and "example.invalid" not in reader.model_dump_json()


def test_health_does_not_show_the_supplier_call_budget(tmp_path: Any, catalog: ProductCatalog) -> None:
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_valio_call_budget=137)
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        response = client.get("/healthz")

    assert "137" not in response.text
    assert "budget" not in response.text
    # What is configured is still shown, each secret as true or false only.
    assert response.json()["settings"] == {
        "env": "dev", "mode": "replay", "replay_capture": "2026-11-14-demo", "valio_key_set": False,
        "gemini_key_set": False, "agent_provider": "none", "agent_model": None, "agent_base_url_set": False,
        "agent_key_set": False, "database_url_set": False, "context_dev_key_set": False, "tokens_set": False,
        "signing_key_set": False, "supplier_suggestions": True, "customer_standing_orders": False,
    }


def test_health_shows_no_secret_and_no_path(tmp_path: Any, catalog: ProductCatalog) -> None:
    settings = Settings.for_tests(
        tta_data_dir=tmp_path / "var", valio_aimo_api_key=SECRET, gemini_api_key=SECRET, database_url=SECRET,
        context_dev_api_key=SECRET,
    )
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        text = client.get("/healthz").text
        body = client.get("/healthz").json()

    assert SECRET not in text
    assert str(tmp_path) not in text
    # The store's kind is named, never its file; the one path shown is the public address of the signing keys.
    shown = text.replace("application/", "").replace("/.well-known/jwks.json", "")
    assert ".sqlite" not in text and "/" not in shown
    assert body["settings"]["valio_key_set"] is True
    assert body["settings"]["gemini_key_set"] is True


def test_health_names_the_store_in_use_and_why(client: TestClient) -> None:
    store = client.get("/healthz").json()["store"]

    assert store == {"kind": "sqlite", "reason": STORE_IS_SQLITE}
    assert "DATABASE_URL is not set" in store["reason"]


def test_health_names_postgresql_when_the_database_answered(
    tmp_path: Any, catalog: ProductCatalog, monkeypatch: Any
) -> None:
    stand_in = SqliteStore()  # stands for the PostgreSQL store: no service is reached here
    monkeypatch.setattr(wiring, "open_postgres_store", lambda settings: stand_in)
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", database_url=f"postgresql://u:{SECRET}@db.internal/x")

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        response = client.get("/healthz")

    assert response.json()["store"] == {"kind": "postgresql", "reason": STORE_IS_POSTGRESQL}
    assert SECRET not in response.text and "db.internal" not in response.text


def test_health_says_sqlite_and_the_reason_when_the_database_could_not_be_reached(
    tmp_path: Any, catalog: ProductCatalog
) -> None:
    unreachable = f"postgresql://tta:{SECRET}@127.0.0.1:1/tta?sslmode=disable"
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", database_url=unreachable)

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        response = client.get("/healthz")

    assert response.json()["store"] == {"kind": "sqlite", "reason": STORE_FALLBACK}
    assert SECRET not in response.text and "127.0.0.1" not in response.text


def test_the_setting_of_the_mcp_origins_exists_and_is_read() -> None:
    from tta.api.mcp_origin import LOCAL_ORIGINS, allowed_origins

    assert Settings.for_tests().tta_mcp_allowed_origins == ""
    settings = Settings.for_tests(tta_mcp_allowed_origins="https://Inspector.example, https://host.example:8443")

    assert allowed_origins(settings) == (*LOCAL_ORIGINS, "https://inspector.example", "https://host.example:8443")


# --- review S7, S8, S13: what /healthz says about a demo key and about what the start skipped ----------------


def test_a_demo_signing_key_is_a_notice_in_dev_and_leaves_the_status_ok(client: TestClient) -> None:
    answer = client.get("/healthz")

    body = answer.json()
    assert answer.status_code == 200 and (body["status"], body["reasons"]) == ("ok", [])
    assert body["notices"] == ["offers and orders are signed with a demo key that changes at every start"]


def test_outside_dev_and_demo_a_demo_signing_key_degrades_the_gateway_and_answers_503(
    tmp_path: Any, catalog: ProductCatalog
) -> None:
    tokens = ('{"prod-agent-token-of-32-characters-x": {"kind": "AGENT", "id": "agent:hotel-kitchen", '
              '"display_name": "Hotel agent", "profile_id": "hotel-kitchen"}}')
    settings = Settings.for_tests(tta_env="prod", tta_data_dir=tmp_path / "var", tta_tokens=tokens)
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        answer = client.get("/healthz")

    body = answer.json()
    assert answer.status_code == 503 and body["status"] == "degraded" and body["notices"] == []
    assert body["reasons"] == ["offers and orders are signed with a demo key that changes at every start"]


def test_a_customer_whose_standing_orders_cannot_be_set_up_at_start_is_named_in_the_reasons(
    tmp_path: Any, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_price(standing: Any, identity: Any, prices: Any) -> Any:
        if identity.profile_id == "school-kitchen":
            raise SupplierUnavailable("The recorded capture holds no price for product 470863.")
        return ()

    monkeypatch.setattr(app_module, "load_customer_standing_orders", no_price)
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_customer_standing_orders=True)
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        answer = client.get("/healthz")

    assert answer.status_code == 200 and answer.json()["status"] == "degraded"
    assert answer.json()["reasons"] == ["the standing orders of school-kitchen were not set up at start"]


# --- who the rate limiter takes the caller for (earlier review F3, a check after the deploy) -------------


def test_in_dev_health_says_how_many_proxy_hops_are_trusted_and_the_callers_address_family_never_the_address(
    app: Any,
) -> None:
    with TestClient(app, client=("203.0.113.7", 50000)) as one:  # the app stops when this block ends
        two, six = TestClient(app, client=("203.0.113.8", 50000)), TestClient(app, client=("2001:db8:1:2::9", 50000))
        first, again, other, ipv6 = one.get("/healthz"), one.get("/healthz"), two.get("/healthz"), six.get("/healthz")

    seen = first.json()["rate_limit_caller"]
    assert (seen["trusted_proxy_hops"], seen["address_family"], seen["forwarded_for_entries"]) == (0, "IPv4", 0)
    assert "203.0.113" not in first.text and "2001:db8" not in ipv6.text
    assert ipv6.json()["rate_limit_caller"]["address_family"] == "IPv6"
    # The bucket label is the same for one address and differs between two: two networks that read the same
    # label share one window.
    assert seen["bucket"] == again.json()["rate_limit_caller"]["bucket"] != other.json()["rate_limit_caller"]["bucket"]
    assert "share" in seen["sentence"] and "0 prox" in seen["sentence"]


def test_the_forwarded_header_is_counted_and_believed_only_as_far_as_the_setting_says(
    tmp_path: Any, catalog: ProductCatalog
) -> None:
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_trusted_proxy_hops=1)
    app = create_app(settings, parts=build_parts(settings, catalog=catalog))

    with TestClient(app, client=("10.0.0.1", 50000)) as proxied:
        one = proxied.get("/healthz", headers={"X-Forwarded-For": "198.51.100.4"}).json()["rate_limit_caller"]
        two = proxied.get("/healthz", headers={"X-Forwarded-For": "198.51.100.5"}).json()["rate_limit_caller"]

    assert (one["trusted_proxy_hops"], one["forwarded_for_entries"], one["address_family"]) == (1, 1, "IPv4")
    assert one["bucket"] != two["bucket"]  # one peer, two visitors: the forwarded entry is what is counted


def test_outside_dev_and_demo_health_says_nothing_about_the_caller(tmp_path: Any, catalog: ProductCatalog) -> None:
    tokens = '{"an-environment-token-of-forty-characters": {"kind": "AGENT", "id": "agent:x", "display_name": "X", ' \
             '"profile_id": "hotel-kitchen"}}'
    settings = Settings.for_tests(tta_env="prod", tta_tokens=tokens, tta_data_dir=tmp_path / "var")

    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        body = client.get("/healthz").json()

    assert body["rate_limit_caller"] is None
