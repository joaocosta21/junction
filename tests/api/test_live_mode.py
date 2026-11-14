"""Live mode through the application: one source per offer and per re-check, a health check that says what
is wrong, and a start that fails loudly (SPEC section 10, task FIX-8 findings 1, 2, 3 and 5).

Scores on the 30% "working end-to-end demo" and on the 20% "what an agent can trust".
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.fallback import MIN_CALLS_REMAINING, FallbackGateway
from tta.api.wiring import GatewayConfigurationError, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.valio import ReplayGateway

AVAILABILITY = "availability"
Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]
Problem = Callable[..., dict[str, Any]]
FakeLive = Any  # the stand-in for the live client, from conftest.py


@pytest.fixture
def live_app(tmp_path: Any, catalog: ProductCatalog, live: FakeLive, replay: ReplayGateway) -> Iterator[TestClient]:
    """The app in live mode over the fake live client."""
    settings = Settings.for_tests(tta_mode="live", tta_data_dir=tmp_path / "var")
    parts = build_parts(settings, catalog=catalog, gateway=FallbackGateway(live, replay))
    with TestClient(create_app(settings, parts=parts)) as client:
        yield client


def _unit_prices(offer: dict[str, Any]) -> list[float]:
    return [line["unit_net_price"] for line in offer["options"][0]["lines"]]


def test_a_live_offer_says_live_and_the_health_check_agrees(
    live_app: TestClient, live: FakeLive, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    before = live_app.get("/healthz").json()

    offer = make_offer(live_app, "agent_ward", scenario_2)
    after = live_app.get("/healthz").json()

    assert (before["mode"], before["source"], before["status"]) == ("live", None, "ok")
    assert offer["source"] == "live"
    assert datetime.fromisoformat(offer["time_now"]) == live.NOW
    assert (after["source"], after["status"], after["reasons"]) == ("live", "ok", [])


def test_an_offer_never_mixes_a_live_price_with_replayed_stock(
    live_app: TestClient, live: FakeLive, replay: ReplayGateway, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    live_prices = _unit_prices(make_offer(live_app, "agent_ward", scenario_2))
    live.failing = {AVAILABILITY}

    offer = make_offer(live_app, "agent_ward", scenario_2)
    health = live_app.get("/healthz").json()

    assert offer["source"] == "replay"
    assert datetime.fromisoformat(offer["time_now"]) == replay.time_now
    assert datetime.fromisoformat(offer["created_at"]) == live.NOW  # the data clock stays live
    # The prices are the capture's, not the live ones that were fetched before availability failed.
    assert _unit_prices(offer) == pytest.approx([price - float(live.PRICE_RISE) for price in live_prices])
    assert (health["source"], health["status"]) == ("replay", "degraded")
    assert "live looks are paused after a supplier failure" in health["reasons"]
    assert "answers come from the recorded capture while live mode is asked for" in health["reasons"]


def test_with_exactly_ten_calls_left_the_whole_offer_comes_from_the_capture(
    live_app: TestClient, live: FakeLive, scenario_2: dict[str, Any], make_offer: Flow
) -> None:
    live.calls_remaining = MIN_CALLS_REMAINING

    offer = make_offer(live_app, "agent_ward", scenario_2)
    health = live_app.get("/healthz").json()

    assert offer["source"] == "replay"
    assert live.calls == 0
    assert health["status"] == "degraded"
    assert "the call budget is low" in health["reasons"]


def test_the_recheck_before_an_order_comes_from_one_source_too(
    live_app: TestClient, live: FakeLive, auth: Auth, scenario_2: dict[str, Any], make_offer: Flow,
    assert_problem: Problem,
) -> None:
    offer = make_offer(live_app, "agent_ward", scenario_2)
    body = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"]}
    live.failing = {AVAILABILITY}

    response = live_app.post("/v1/orders", json=body, headers=auth("agent_ward", "key-1"))

    # The re-check fell back to the capture as a whole: its replayed price differs from the live offer's, so
    # the order is refused as stale. A live price with replayed stock would have passed.
    problem = assert_problem(response, "offer-stale", 409)
    assert {change["field"] for change in problem["changes"]} >= {"price"}
    fresh = live_app.get(f"/v1/offers/{problem['fresh_offer_id']}", headers=auth("agent_ward")).json()
    assert fresh["source"] == "replay"


def test_in_live_mode_without_a_key_the_app_answers_from_the_capture_and_says_so(
    tmp_path: Any, catalog: ProductCatalog, auth: Auth, scenario_2: dict[str, Any]
) -> None:
    # No key is set, so the live client refuses before any call is sent: nothing here reaches the network.
    settings = Settings.for_tests(tta_mode="live", tta_data_dir=tmp_path / "var")
    app = create_app(settings, parts=build_parts(settings, catalog=catalog))

    with TestClient(app) as client:
        offer = client.post("/v1/offers", json=scenario_2, headers=auth("agent_ward"))
        health = client.get("/healthz").json()

    assert offer.status_code == 201
    assert offer.json()["source"] == "replay"
    assert offer.json()["options"][0]["decision"]["verdict"] == "APPROVAL"
    assert (health["mode"], health["source"], health["status"]) == ("live", "replay", "degraded")


# --- a configuration error stops the start (finding 3) --------------------------------------------------


def test_in_live_mode_an_address_the_client_refuses_stops_the_start(
    tmp_path: Any, catalog: ProductCatalog, caplog: pytest.LogCaptureFixture
) -> None:
    address = "http://not-encrypted.example/api"
    settings = Settings.for_tests(tta_mode="live", tta_data_dir=tmp_path / "var", valio_aimo_base_url=address)

    with pytest.raises(GatewayConfigurationError) as refused:
        build_parts(settings, catalog=catalog)

    assert "VALIO_AIMO_BASE_URL" in str(refused.value)
    assert "not-encrypted" not in str(refused.value) and "not-encrypted" not in caplog.text
    assert not settings.db_path.exists()  # nothing was opened


def test_in_replay_mode_the_supplier_address_is_not_looked_at(tmp_path: Any, catalog: ProductCatalog) -> None:
    settings = Settings.for_tests(
        tta_data_dir=tmp_path / "var", valio_aimo_base_url="http://not-encrypted.example/api"
    )

    parts = build_parts(settings, catalog=catalog)

    assert isinstance(parts.gateway, ReplayGateway)
    parts.close()
