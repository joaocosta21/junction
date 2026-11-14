"""Fixtures for the API tests: the app in replay over tonight's capture, a database under `tmp_path`.

Every helper is a fixture, because test modules cannot import from one another (`--import-mode=importlib`).
No test here calls a live service, and nothing reads `.env`.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.availability import AvailabilityResponse, PriceResponse
from tta.contracts.common import DataSource
from tta.contracts.errors import PROBLEM_CONTENT_TYPE, PROBLEM_TYPE_BASE, SupplierUnavailable
from tta.valio import ReplayGateway

MONDAY = "2026-11-16"  # the Monday after tonight's capture (Saturday 14 Nov 2026)
# The demonstration tokens of src/tta/api/demo_tokens.yaml. They are public by design.
TOKENS = {
    "agent_hotel": "demo-agent-hotel-kitchen",
    "agent_ward": "demo-agent-allergy-ward",
    "hotel_purchasing": "demo-approver-hotel-purchasing",
    "ward_dietitian": "demo-approver-ward-dietitian",
    "ward_purchasing": "demo-approver-ward-purchasing",
    "supplier": "demo-supplier-valio-aimo",
}
# One person confirms (decision SIMP): the hotel's buyer holds every role, so each role is decided by her token.
HOTEL_APPROVER_BY_ROLE = dict.fromkeys(("purchasing_manager", "finance", "dietitian"), "hotel_purchasing")
SCENARIO_1 = {
    "needed_by": MONDAY,
    "lines": [{
        "text": "1,000 litres of lactose-free milk by Monday",
        "product_type": "milk",
        "required_claims": ["FREE_FROM_LACTOSE"],
        "quantity": 1000,
        "unit": "L",
    }],
}
SCENARIO_2 = {
    "needed_by": MONDAY,
    "require_confirmed": True,
    "lines": [{
        "text": "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only",
        "product_type": "plant_drink",
        "quantity": 200,
        "unit": "L",
        "exclude_allergens": ["AM", "AW"],
    }],
}

# What other tasks add to the gateway (`tta.api.hooks`). They may or may not have landed.
OPTIONAL_MODULES = ("tta.agent", "tta.api.mcp_surface", "tta.ui.routes")

Headers = dict[str, str]
Auth = Callable[..., Headers]
Flow = Callable[..., dict[str, Any]]


@pytest.fixture(scope="module", autouse=True)
def without_optional_modules() -> Iterator[None]:
    """The API is tested on its own: the buyer agent, the MCP surface and the pages read as not installed,
    whatever their tasks have landed. A test that needs one puts its own stand-in into `sys.modules`.
    Module scope, so that the other test folders of the same run see the real modules again."""
    with pytest.MonkeyPatch.context() as patch:
        for name in OPTIONAL_MODULES:
            patch.setitem(sys.modules, name, None)
        yield


class ChangingGateway:
    """The replay capture behind the `ValioGateway` port, with faults a test can switch on.

    `price_rise` is added to every net price; `hours_later` moves the server time of every answer and of the
    clock; `down` makes every call fail; `broken` raises an error no code expects.
    """

    def __init__(self, replay: ReplayGateway) -> None:
        self._replay = replay
        self.price_rise = Decimal(0)
        self.hours_later = 0
        self.down = False
        self.broken = False
        self.calls = 0

    @property
    def source(self) -> DataSource:
        return DataSource.REPLAY

    @property
    def clock(self) -> ChangingGateway:
        return self

    def now(self) -> datetime:
        return self._replay.time_now + timedelta(hours=self.hours_later)

    def _check(self) -> None:
        self.calls += 1
        if self.broken:
            raise RuntimeError("a fault with the text do-not-show-this-to-a-caller")
        if self.down:
            raise SupplierUnavailable("The supplier cannot be asked right now, so no call was made.")

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        self._check()
        answer = self._replay.price(product_ids, fresh=fresh)
        if not self.price_rise:
            return answer
        lines = tuple(
            line if line.catalog_price is None else line.model_copy(update={
                "catalog_price": line.catalog_price.model_copy(
                    update={"value": line.catalog_price.value + self.price_rise}
                ),
            })
            for line in answer.lines
        )
        return answer.model_copy(update={"lines": lines})

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:
        self._check()
        answer = self._replay.availability(product_ids, fresh=fresh)
        return answer.model_copy(update={"time_now": self.now()})


class FakeLive:
    """Stands in for the live client: the capture's data labelled `live`, every price one euro higher so that
    a live price can be told from a replayed one. A test makes one endpoint or both fail, and counts the calls."""

    NOW = datetime(2026, 11, 14, 9, 30, tzinfo=UTC)
    PRICE_RISE = Decimal("1.00")
    ENDPOINTS = frozenset({"price", "availability"})

    def __init__(self, replay: ReplayGateway, calls_remaining: int = 100) -> None:
        self._replay = replay
        self.calls_remaining = calls_remaining
        self.failing: set[str] = set()
        self.asked: list[str] = []
        self.closed = False

    @property
    def calls(self) -> int:
        return len(self.asked)

    @property
    def down(self) -> bool:
        return self.failing == self.ENDPOINTS

    @down.setter
    def down(self, value: bool) -> None:
        self.failing = set(self.ENDPOINTS) if value else set()

    @property
    def source(self) -> DataSource:
        return DataSource.LIVE

    @property
    def clock(self) -> FakeLive:
        return self

    def now(self) -> datetime:
        return self.NOW

    def close(self) -> None:
        self.closed = True

    def _answer(self, endpoint: str) -> None:
        self.asked.append(endpoint)
        if endpoint in self.failing:
            raise SupplierUnavailable("The supplier cannot be asked right now, so no call was made.")

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        self._answer("price")
        answer = self._replay.price(product_ids, fresh=fresh)
        lines = tuple(
            line if line.catalog_price is None else line.model_copy(update={
                "catalog_price": line.catalog_price.model_copy(
                    update={"value": line.catalog_price.value + self.PRICE_RISE}
                ),
            })
            for line in answer.lines
        )
        return answer.model_copy(update={"lines": lines, "source": DataSource.LIVE, "retrieved_at": self.NOW})

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:
        self._answer("availability")
        answer = self._replay.availability(product_ids, fresh=fresh)
        return answer.model_copy(update={"source": DataSource.LIVE, "time_now": self.NOW})


@pytest.fixture(scope="session")
def replay() -> ReplayGateway:
    """The capture itself. A test that changes one of its methods does it with `monkeypatch`."""
    return ReplayGateway(Settings.for_tests().replay_capture_dir)


@pytest.fixture
def live(replay: ReplayGateway) -> FakeLive:
    return FakeLive(replay)


@pytest.fixture(scope="session")
def catalog() -> ProductCatalog:
    """The real catalog (17,546 products), built once per test session."""
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture
def parts(settings: Settings, catalog: ProductCatalog) -> Iterator[Parts]:
    built = build_parts(settings, catalog=catalog)
    yield built
    built.close()


@pytest.fixture
def app(settings: Settings, parts: Parts) -> FastAPI:
    return create_app(settings, parts=parts)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def changing(settings: Settings) -> ChangingGateway:
    return ChangingGateway(ReplayGateway(settings.replay_capture_dir))


@pytest.fixture
def changing_client(settings: Settings, catalog: ProductCatalog, changing: ChangingGateway) -> Iterator[TestClient]:
    """A client over a gateway whose answers a test can change between the offer and the order."""
    app = create_app(settings, parts=build_parts(settings, catalog=catalog, gateway=changing))
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def tokens() -> dict[str, str]:
    return dict(TOKENS)


@pytest.fixture(scope="session")
def auth() -> Auth:
    """Request headers for one of the demonstration identities, with an idempotency key when one is given."""

    def headers(who: str, key: str | None = None) -> Headers:
        found = {"Authorization": f"Bearer {TOKENS[who]}"}
        return found if key is None else {**found, "Idempotency-Key": key}

    return headers


@pytest.fixture(scope="session")
def scenario_1() -> dict[str, Any]:
    return SCENARIO_1


@pytest.fixture(scope="session")
def scenario_2() -> dict[str, Any]:
    return SCENARIO_2


@pytest.fixture(scope="session")
def hotel_approver_by_role() -> dict[str, str]:
    return dict(HOTEL_APPROVER_BY_ROLE)


@pytest.fixture(scope="session")
def make_offer(auth: Auth) -> Flow:
    def post(client: TestClient, who: str, body: dict[str, Any]) -> dict[str, Any]:
        response = client.post("/v1/offers", json=body, headers=auth(who))
        assert response.status_code == 201, response.text
        return response.json()

    return post


@pytest.fixture(scope="session")
def place_order(auth: Auth) -> Flow:
    def post(client: TestClient, who: str, offer: dict[str, Any], key: str, option: int = 0) -> dict[str, Any]:
        body = {"offer_id": offer["offer_id"], "option_id": offer["options"][option]["option_id"]}
        response = client.post("/v1/orders", json=body, headers=auth(who, key))
        assert response.status_code == 201, response.text
        return response.json()

    return post


@pytest.fixture(scope="session")
def assert_problem() -> Callable[..., dict[str, Any]]:
    """Check that a response is an RFC 9457 problem of one type and status, and hand back its body."""

    def check(response: Any, slug: str, status: int) -> dict[str, Any]:
        assert response.status_code == status, response.text
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        body = response.json()
        assert body["type"] == PROBLEM_TYPE_BASE + slug
        assert body["status"] == status
        assert body["title"]
        assert "Traceback" not in response.text
        return body

    return check
