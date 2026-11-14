"""Fixtures of the Valio client tests: a fake of the mock API built on recorded captures, and a fake time.

No test here reaches the network: every client is given an `httpx.MockTransport`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from tta.config import Settings
from tta.contracts.common import DataSource
from tta.valio import LiveClock, ValioClient

SENTINEL_KEY = "sentinel-valio-key-0123456789"
BASE_URL = "https://valio.test/api"

Handler = Callable[[httpx.Request], httpx.Response]


FAKE_TIME_START = 1_000.0
FAKE_WALL_CLOCK_START = datetime(2026, 11, 14, 0, 0, 0, tzinfo=UTC)


class FakeTime:
    """A monotonic clock, a wall clock and a sleep that advance together, so no test waits."""

    def __init__(self) -> None:
        self.current = FAKE_TIME_START
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.current

    def utc_now(self) -> datetime:
        return FAKE_WALL_CLOCK_START + timedelta(seconds=self.current - FAKE_TIME_START)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += seconds

    def advance(self, seconds: float) -> None:
        self.current += seconds


def unknown_entry(endpoint: str, product_id: str) -> dict[str, Any]:
    """What the mock API answers for an id it does not know (AIMO/docs/API.md section 8.5)."""
    if endpoint == "price":
        return {"productId": product_id, "quantity": 1.0, "netPriceFound": False, "error": True}
    return {"productId": product_id, "salesBlock": False, "scheduleLines": []}


class FakeValioApi:
    """Answers `/price` and `/availability` the way the mock API does, from a capture's recorded entries."""

    def __init__(self, capture: Any) -> None:
        self._entries = {endpoint: capture.lines(endpoint) for endpoint in ("price", "availability")}
        self._heads = {
            endpoint: {key: value for key, value in capture.bodies(endpoint)[0].items() if key != "products"}
            for endpoint in ("price", "availability")
        }
        self._heads["availability"]["timeNow"] = capture.manifest["time_now"]
        self.requests: list[httpx.Request] = []
        self.texts: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        endpoint = request.url.path.rsplit("/", 1)[-1]
        ids = json.loads(request.content)["products"]
        products = [self._entries[endpoint].get(pid) or unknown_entry(endpoint, pid) for pid in ids]
        text = json.dumps({**self._heads[endpoint], "products": products})
        self.texts.append(text)
        return httpx.Response(200, text=text, headers={"content-type": "application/json"})

    def sent_ids(self) -> list[list[str]]:
        return [json.loads(request.content)["products"] for request in self.requests]


@pytest.fixture
def sentinel_key() -> str:
    return SENTINEL_KEY


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


@pytest.fixture
def live_settings(tmp_path: Path) -> Settings:
    """Live-mode settings with a private data directory and a sentinel in place of the key."""
    return Settings.for_tests(
        tta_mode=DataSource.LIVE,
        tta_data_dir=tmp_path / "var",
        valio_aimo_api_key=SENTINEL_KEY,
        valio_aimo_base_url=BASE_URL,
    )


@pytest.fixture
def make_api() -> Callable[[Any], FakeValioApi]:
    return FakeValioApi


@pytest.fixture
def fake_api(capture_demo: Any) -> FakeValioApi:
    return FakeValioApi(capture_demo)


@pytest.fixture
def make_client(live_settings: Settings, fake_time: FakeTime) -> Callable[..., ValioClient]:
    """Build a client whose HTTP calls go to `handler` and whose waits cost no time."""

    def build(handler: Handler, settings: Settings | None = None) -> ValioClient:
        return ValioClient(
            settings or live_settings,
            transport=httpx.MockTransport(handler),
            clock=LiveClock(utc_now=fake_time.utc_now),
            sleep=fake_time.sleep,
            monotonic=fake_time.monotonic,
        )

    return build
