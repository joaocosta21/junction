"""Live mode with a fall-back to the replay capture (SPEC section 10, task T09).

Scores on the 30% "working end-to-end demo": the flow survives the mock API being down or the call budget
being spent, and every answer still says where it came from.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.fallback import MIN_CALLS_REMAINING, RETRY_LIVE_AFTER_SECONDS, FallbackGateway
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.availability import AvailabilityResponse, PriceResponse
from tta.contracts.common import DataSource
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import ValioGateway
from tta.valio import ReplayGateway

LIVE_NOW = datetime(2026, 11, 14, 9, 30, tzinfo=UTC)
IDS = ("464013", "469363")
Auth = Callable[..., dict[str, str]]


class FakeLive:
    """Stands in for the live client: answers with the source `live`, or fails, and counts its calls."""

    def __init__(self, calls_remaining: int = 100) -> None:
        self.calls_remaining = calls_remaining
        self.down = False
        self.calls = 0

    @property
    def source(self) -> DataSource:
        return DataSource.LIVE

    @property
    def clock(self) -> FakeLive:
        return self

    def now(self) -> datetime:
        return LIVE_NOW

    def _answer(self) -> None:
        self.calls += 1
        if self.down:
            raise SupplierUnavailable("The supplier cannot be asked right now, so no call was made.")

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        self._answer()
        return PriceResponse(currency="EUR", source=DataSource.LIVE, retrieved_at=LIVE_NOW)

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:
        self._answer()
        return AvailabilityResponse(time_now=LIVE_NOW, source=DataSource.LIVE)


class FakeTime:
    def __init__(self) -> None:
        self.seconds = 500.0

    def __call__(self) -> float:
        return self.seconds


@pytest.fixture(scope="module")
def replay() -> ReplayGateway:
    return ReplayGateway(Settings.for_tests().replay_capture_dir)


@pytest.fixture
def time() -> FakeTime:
    return FakeTime()


def test_the_fall_back_satisfies_the_gateway_port(replay: ReplayGateway) -> None:
    assert isinstance(FallbackGateway(FakeLive(), replay), ValioGateway)


def test_while_the_live_api_answers_the_answer_and_the_clock_are_live(replay: ReplayGateway) -> None:
    live = FakeLive()
    gateway = FallbackGateway(live, replay)

    price = gateway.price(IDS)
    availability = gateway.availability(IDS, fresh=True)

    assert (price.source, availability.source) == (DataSource.LIVE, DataSource.LIVE)
    assert gateway.source is DataSource.LIVE
    assert gateway.clock.now() == LIVE_NOW
    assert live.calls == 2


def test_when_the_live_api_fails_the_capture_answers_and_the_clock_is_pinned_to_it(
    replay: ReplayGateway, time: FakeTime
) -> None:
    live = FakeLive()
    gateway = FallbackGateway(live, replay, monotonic=time)
    live.down = True

    availability = gateway.availability(IDS)
    price = gateway.price(IDS)

    assert availability.source is DataSource.REPLAY
    assert availability == replay.availability(IDS)
    assert price == replay.price(IDS)
    assert gateway.source is DataSource.REPLAY
    assert gateway.clock.now() == replay.time_now
    # The price call right after did not go to the live API: one lookup never mixes the two sources.
    assert live.calls == 1


def test_the_live_api_is_asked_again_after_a_pause_and_the_clock_follows(
    replay: ReplayGateway, time: FakeTime
) -> None:
    live = FakeLive()
    gateway = FallbackGateway(live, replay, monotonic=time)
    live.down = True
    gateway.price(IDS)
    live.down = False

    time.seconds += RETRY_LIVE_AFTER_SECONDS - 1
    still = gateway.price(IDS)
    time.seconds += 2
    back = gateway.price(IDS)

    assert still.source is DataSource.REPLAY
    assert back.source is DataSource.LIVE
    assert gateway.source is DataSource.LIVE
    assert gateway.clock.now() == LIVE_NOW


@pytest.mark.parametrize(
    ("remaining", "expected"),
    [(MIN_CALLS_REMAINING, DataSource.LIVE), (MIN_CALLS_REMAINING - 1, DataSource.REPLAY), (0, DataSource.REPLAY)],
)
def test_with_fewer_than_ten_calls_left_the_capture_answers_and_no_call_is_spent(
    replay: ReplayGateway, remaining: int, expected: DataSource
) -> None:
    live = FakeLive(calls_remaining=remaining)
    gateway = FallbackGateway(live, replay)

    assert MIN_CALLS_REMAINING == 10
    assert gateway.source is expected  # before any answer: where the next one would come from
    assert gateway.availability(IDS).source is expected
    assert live.calls == (1 if expected is DataSource.LIVE else 0)


def test_when_the_budget_runs_low_between_two_answers_the_capture_takes_over_and_it_is_logged(
    replay: ReplayGateway, caplog: pytest.LogCaptureFixture
) -> None:
    live = FakeLive()
    gateway = FallbackGateway(live, replay)
    first = gateway.price(IDS)
    live.calls_remaining = MIN_CALLS_REMAINING - 1

    with caplog.at_level("WARNING", logger="tta.api.fallback"):
        second = gateway.price(IDS)
        third = gateway.price(IDS)

    assert (first.source, second.source, third.source) == (DataSource.LIVE, DataSource.REPLAY, DataSource.REPLAY)
    assert live.calls == 1
    assert caplog.text.count("call budget") == 1  # said once, when the source changes


def test_a_failing_capture_is_reported_and_not_hidden(replay: ReplayGateway, monkeypatch: Any) -> None:
    live = FakeLive()
    live.down = True
    gateway = FallbackGateway(live, replay)

    def unusable(product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        raise SupplierUnavailable("The replay capture cannot be used.")

    monkeypatch.setattr(replay, "price", unusable)

    with pytest.raises(SupplierUnavailable):
        gateway.price(IDS)


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
    assert offer.json()["options"][0]["decision"]["verdict"] == "AUTO"
    assert (health["mode"], health["source"]) == ("live", "replay")


def test_in_live_mode_with_an_address_that_cannot_be_used_the_app_runs_on_the_capture(
    tmp_path: Any, catalog: ProductCatalog
) -> None:
    settings = Settings.for_tests(
        tta_mode="live", tta_data_dir=tmp_path / "var", valio_aimo_base_url="http://not-encrypted.example/api"
    )

    parts = build_parts(settings, catalog=catalog)

    assert parts.gateway.source is DataSource.REPLAY
