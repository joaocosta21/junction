"""The demo clock: an instant we chose, as a setting honoured in replay only (`TTA_DEMO_CLOCK`).

Valio Aimo, 14 Nov 2026: "this is all static data so we can chose the date". With the setting, every offer is
judged against Thursday 12 Nov 2026 14:15 Helsinki time; without it, against the recording's own instant, as
before. The gateway says which of the two is in force. The audit trail keeps the real time either way.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.wiring import GatewayConfigurationError, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import DataSource

HELSINKI = timezone(timedelta(hours=2))
DEMO_CLOCK = "2026-11-12T14:15:00+02:00"
THURSDAY = datetime(2026, 11, 12, 14, 15, tzinfo=HELSINKI)
RECORDED = datetime(2026, 11, 14, 2, 52, 45, tzinfo=HELSINKI)
MONDAY = "2026-11-16"
HOTEL = {"Authorization": "Bearer demo-agent-hotel-kitchen"}


def _client(settings: Settings, catalog: ProductCatalog) -> Iterator[TestClient]:
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        yield client


@pytest.fixture
def thursday(tmp_path: Path, catalog: ProductCatalog) -> Iterator[TestClient]:
    """The demo as it runs with the setting: replay, the `demo` environment, the clock set to Thursday 14:15."""
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_env="demo", tta_demo_clock=DEMO_CLOCK)
    yield from _client(settings, catalog)


@pytest.fixture
def unset(tmp_path: Path, catalog: ProductCatalog) -> Iterator[TestClient]:
    yield from _client(Settings.for_tests(tta_data_dir=tmp_path / "var", tta_env="demo"), catalog)


def _offer(client: TestClient, texts: Any) -> dict[str, Any]:
    response = client.post("/v1/offers", json=texts.milk(1000), headers=HOTEL)
    assert response.status_code == 201, response.text
    return response.json()


def _moment(text: str) -> datetime:
    return datetime.fromisoformat(text)


def test_with_the_setting_an_offer_is_built_against_the_instant_that_was_set(
    thursday: TestClient, texts: Any
) -> None:
    offer = _offer(thursday, texts)

    assert _moment(offer["time_now"]) == THURSDAY
    assert (offer["source"], offer["time_basis"]) == ("replay", "demo_setting")
    assert offer["options"]  # the recorded stock and prices are the same; only the clock moved


def test_with_the_setting_by_monday_is_the_monday_after_that_thursday(thursday: TestClient, texts: Any) -> None:
    response = thursday.post("/v1/requests/parse", json={"text": texts.scenario_1}, headers=HOTEL)

    assert response.status_code == 200, response.text
    assert response.json()["needed_by"] == MONDAY


def test_with_the_setting_no_cut_off_of_thursday_afternoon_has_passed_yet(
    thursday: TestClient, unset: TestClient, texts: Any
) -> None:
    """Thursday 14:15 lies before the 15:00 cut-off of the Terminal products: on the recording's own clock 15 of
    the lactose-free milks are left out because that deadline passed, on the demo clock none of those."""
    def passed(offer: dict[str, Any]) -> int:
        return sum(1 for exclusion in offer["excluded"] if exclusion["reason"] == "CUTOFF_PASSED")

    assert passed(_offer(unset, texts)) > 0
    assert passed(_offer(thursday, texts)) < passed(_offer(unset, texts))


def test_with_the_setting_health_says_which_clock_is_in_force_and_that_it_was_set(thursday: TestClient) -> None:
    clock = thursday.get("/healthz").json()["clock"]

    assert _moment(clock["now"]) == THURSDAY
    assert (clock["basis"], clock["demo_clock_set"]) == ("demo_setting", True)
    assert _moment(clock["recorded_at"]) == RECORDED
    assert clock["sentence"] == (
        "Demo clock: Thursday 12 November 2026 at 14:15 (UTC+02:00), set with TTA_DEMO_CLOCK. Order deadlines are "
        "judged against it. We chose it: Valio Aimo said on 14 Nov 2026 that its test data is static. The data "
        "was recorded on Saturday 14 November 2026 at 02:52 (UTC+02:00). The audit trail is stamped with the real "
        "time."
    )


def test_with_the_setting_the_audit_trail_keeps_the_real_time_and_names_the_basis(
    thursday: TestClient, texts: Any
) -> None:
    before = datetime.now(UTC)
    offer = _offer(thursday, texts)

    view = thursday.get(f"/v1/audit?offer_id={offer['offer_id']}", headers=HOTEL).json()

    stamps = [_moment(event["time"]) for event in view["events"]]
    assert stamps and all(stamp >= before - timedelta(seconds=1) for stamp in stamps)
    looked_up = next(event for event in view["events"] if event["type"].endswith("lookup.performed"))
    assert looked_up["facts"]["time_basis"] == "demo_setting"
    assert _moment(looked_up["facts"]["time_now"]) == THURSDAY


def test_unset_nothing_changes_the_clock_is_the_recordings_instant(unset: TestClient, texts: Any) -> None:
    offer = _offer(unset, texts)
    clock = unset.get("/healthz").json()["clock"]

    assert _moment(offer["time_now"]) == RECORDED and offer["time_basis"] == "recording"
    assert _moment(clock["now"]) == RECORDED
    assert (clock["basis"], clock["demo_clock_set"]) == ("recording", False)
    assert clock["sentence"].startswith(
        "Clock pinned to Saturday 14 November 2026 at 02:52 (UTC+02:00), the moment Valio Aimo's data was recorded."
    )
    parsed = unset.post("/v1/requests/parse", json={"text": texts.scenario_1}, headers=HOTEL).json()
    assert parsed["needed_by"] == MONDAY


def test_a_blank_setting_reads_as_unset() -> None:
    assert Settings.for_tests(tta_demo_clock="  ").tta_demo_clock is None


def test_a_demo_clock_without_an_offset_is_refused() -> None:
    with pytest.raises(ValueError, match="tta_demo_clock"):
        Settings.for_tests(tta_demo_clock="2026-11-12T14:15:00")


def test_the_demo_clock_is_not_honoured_in_live_mode() -> None:
    settings = Settings.for_tests(tta_mode=DataSource.LIVE, tta_demo_clock=DEMO_CLOCK)

    assert settings.tta_demo_clock == THURSDAY and settings.demo_clock is None


def test_outside_dev_and_demo_the_gateway_does_not_start_with_a_demo_clock(
    tmp_path: Path, catalog: ProductCatalog
) -> None:
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_env="prod", tta_demo_clock=DEMO_CLOCK)

    with pytest.raises(GatewayConfigurationError, match="TTA_DEMO_CLOCK is set, but TTA_ENV is neither dev nor demo"):
        build_parts(settings, catalog=catalog)


def test_the_pages_say_which_clock_is_in_force(thursday: TestClient, unset: TestClient) -> None:
    with_the_setting, without = thursday.get("/").text, unset.get("/").text

    assert "demo clock set to Thursday 12 November 2026 at 14:15 (UTC+02:00)" in with_the_setting
    assert "clock pinned to the recording" not in with_the_setting
    assert "clock pinned to the recording" in without and "demo clock" not in without
