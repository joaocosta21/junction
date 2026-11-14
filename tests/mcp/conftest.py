"""Fixtures for the MCP tests: the gateway in replay over tonight's capture, reached the way an agent's host
reaches it: the official MCP SDK client over Streamable HTTP, with a bearer token.

Nothing here opens a socket (the client talks to the application in memory), calls a live service or reads
`.env`. Every helper is a fixture, because test modules cannot import from one another.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx
import httpx2  # the MCP SDK's own HTTP client: its transport takes no other
import pytest
from fastapi import FastAPI
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

from tta.api import create_app
from tta.api.limits import RateLimit
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.availability import AvailabilityResponse, PriceResponse
from tta.contracts.common import DataSource
from tta.valio import ReplayGateway

BASE_URL = "http://gateway.test"
MCP_URL = f"{BASE_URL}/mcp/"  # the surface is mounted at /mcp; its endpoint is the mount's root
MONDAY = "2026-11-16"  # the Monday after tonight's capture (Saturday 14 Nov 2026)
# The demonstration tokens of src/tta/api/demo_tokens.yaml. They are public by design.
TOKENS = {
    "agent_hotel": "demo-agent-hotel-kitchen",
    "agent_ward": "demo-agent-allergy-ward",
    "hotel_purchasing": "demo-approver-hotel-purchasing",
    "ward_purchasing": "demo-approver-ward-purchasing",
    "supplier": "demo-supplier-valio-aimo",
    "nobody": "a-token-nobody-issued",
}
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

DEFAULT_PEER, PEER_PORT = "127.0.0.1", 123  # what the SDK's in-memory transport reports by default
OTHER_OPTIONAL_MODULES = ("tta.agent", "tta.ui.routes")  # what other tasks add to the gateway (`tta.api.hooks`)

Headers = dict[str, str]
Connect = Callable[..., AbstractAsyncContextManager[Client]]


class ChangingGateway:
    """The replay capture behind the `ValioGateway` port, with two faults a test can switch on: `price_rise`
    is added to every net price, and `broken` raises an error no code expects."""

    def __init__(self, replay: ReplayGateway) -> None:
        self._replay = replay
        self.price_rise = Decimal(0)
        self.broken = False

    @property
    def source(self) -> DataSource:
        return DataSource.REPLAY

    @property
    def clock(self) -> ChangingGateway:
        return self

    def now(self) -> datetime:
        return self._replay.time_now

    def _check(self) -> None:
        if self.broken:
            raise RuntimeError("a fault with the text do-not-show-this-to-a-caller")

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
        return self._replay.availability(product_ids, fresh=fresh)


@pytest.fixture(scope="module", autouse=True)
def without_the_other_optional_modules() -> Iterator[None]:
    """The MCP surface is tested on the gateway alone: the buyer agent (T10) and the pages (T12) read as not
    installed, whatever their tasks have landed. No MCP tool reaches either. Module scope, so that the other
    test folders of the same run see the real modules again."""
    with pytest.MonkeyPatch.context() as patch:
        for name in OTHER_OPTIONAL_MODULES:
            patch.setitem(sys.modules, name, None)
        yield


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def catalog() -> ProductCatalog:
    """The real catalog (17,546 products), built once per test session."""
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture
def changing(settings: Settings) -> ChangingGateway:
    return ChangingGateway(ReplayGateway(settings.replay_capture_dir))


@pytest.fixture
def rate_limit() -> RateLimit | None:
    """The gateway's own limit, unless a test module sets another."""
    return None


@pytest.fixture
def parts(
    settings: Settings, catalog: ProductCatalog, changing: ChangingGateway, rate_limit: RateLimit | None
) -> Iterator[Parts]:
    built = build_parts(settings, catalog=catalog, gateway=changing, rate_limit=rate_limit)
    yield built
    built.close()


@pytest.fixture
def app(settings: Settings, parts: Parts) -> FastAPI:
    return create_app(settings, parts=parts)


@pytest.fixture
async def running_app(app: FastAPI) -> AsyncIterator[FastAPI]:
    """The application with its lifespan running: the MCP session manager lives in it."""
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture(scope="session")
def auth() -> Callable[[str], Headers]:
    def headers(who: str) -> Headers:
        return {"Authorization": f"Bearer {TOKENS[who]}"}

    return headers


@pytest.fixture
async def rest(running_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """A plain HTTP client on the same application: the REST routes, and raw requests to the MCP endpoint."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=running_app), base_url=BASE_URL) as client:
        yield client


@pytest.fixture
def connect(running_app: FastAPI, auth: Callable[[str], Headers]) -> Connect:
    """An MCP client session as one of the demonstration identities, or with no token when `who` is `None`.
    `mode` is the SDK client's: "auto" speaks the newest protocol version, "legacy" the handshake one.
    `visitor` is the caller's address, as the gateway sees its peer (no forwarded header is trusted)."""

    @asynccontextmanager
    async def session(who: str | None, mode: str = "auto", visitor: str | None = None) -> AsyncIterator[Client]:
        headers = {} if who is None else auth(who)
        transport = httpx2.ASGITransport(app=running_app, client=(visitor or DEFAULT_PEER, PEER_PORT))
        async with (
            httpx2.AsyncClient(transport=transport, headers=headers) as http,
            Client(streamable_http_client(MCP_URL, http_client=http), mode=mode) as client,
        ):
            yield client

    return session


@pytest.fixture(scope="session")
def mcp_path() -> str:
    return "/mcp/"


@pytest.fixture(scope="session")
def scenario_1() -> dict[str, Any]:
    return SCENARIO_1


@pytest.fixture(scope="session")
def scenario_2() -> dict[str, Any]:
    return SCENARIO_2


@pytest.fixture(scope="session")
def rpc() -> Callable[..., dict[str, Any]]:
    """The body of one JSON-RPC request, for a raw call to the MCP endpoint."""

    def body(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
        return request if params is None else {**request, "params": params}

    return body
