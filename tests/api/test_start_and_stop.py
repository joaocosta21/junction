"""What is opened is closed: when the gateway stops, and when its start fails half-way (task FIX-8, finding 8).

Scores on the 15% "credible path toward production": a start that fails leaves no database handle and no
HTTP client behind, and a close that fails does not keep the others from closing.
"""

from __future__ import annotations

import dataclasses
import sys
import types
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app, wiring
from tta.api.fallback import FallbackGateway
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.availability import AvailabilityResponse, PriceResponse
from tta.contracts.common import DataSource
from tta.contracts.errors import SupplierUnavailable
from tta.valio import ReplayGateway, ValioClient


class Closable:
    """A gateway that remembers being closed, and can fail at it."""

    def __init__(self, replay: ReplayGateway, *, fails: bool = False) -> None:
        self._replay = replay
        self._fails = fails
        self.closed = 0

    @property
    def source(self) -> DataSource:
        return DataSource.REPLAY

    @property
    def clock(self) -> Any:
        return self._replay.clock

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        return self._replay.price(product_ids, fresh=fresh)

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:
        return self._replay.availability(product_ids, fresh=fresh)

    def close(self) -> None:
        self.closed += 1
        if self._fails:
            raise OSError("the connection could not be closed")


@pytest.fixture
def closable(settings: Settings) -> Closable:
    return Closable(ReplayGateway(settings.replay_capture_dir))


@pytest.fixture
def opened_stores(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Every store `build_parts` opens during the test."""
    stores: list[Any] = []
    genuine = wiring.open_store

    def remembering(settings: Settings) -> Any:
        stores.append(genuine(settings))
        return stores[-1]

    monkeypatch.setattr(wiring, "open_store", remembering)
    return stores


@pytest.fixture
def closed_clients(monkeypatch: pytest.MonkeyPatch) -> list[ValioClient]:
    """Every live client that was closed during the test."""
    closed: list[ValioClient] = []
    genuine = ValioClient.close

    def remembering(client: ValioClient) -> None:
        closed.append(client)
        genuine(client)

    monkeypatch.setattr(ValioClient, "close", remembering)
    return closed


def _is_closed(store: Any) -> bool:
    try:
        store.list_orders()
    except SupplierUnavailable:  # the store reports a closed database as its typed error
        return True
    return False


def _agent_that_cannot_be_built(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails after the gateway is built and before the store is opened."""

    def build_request_parser(**given: Any) -> Any:
        raise RuntimeError("the model client could not be built")

    module = types.ModuleType("tta.agent")
    module.build_request_parser = build_request_parser  # type: ignore[attr-defined]
    module.build_agent_runner = build_request_parser  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tta.agent", module)


def _services_that_cannot_be_wired(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails at the last step, after the gateway is built and the store is opened."""

    def wire(**given: Any) -> Any:
        raise RuntimeError("the services could not be wired")

    monkeypatch.setattr(wiring, "wire", wire)


# --- a start that fails ---------------------------------------------------------------------------------


def test_a_step_that_fails_after_the_store_is_opened_closes_the_store(
    settings: Settings, catalog: ProductCatalog, opened_stores: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _services_that_cannot_be_wired(monkeypatch)

    with pytest.raises(RuntimeError, match="could not be wired"):
        build_parts(settings, catalog=catalog)

    assert len(opened_stores) == 1
    assert _is_closed(opened_stores[0])


def test_a_step_that_fails_closes_the_live_client_it_built_too(
    tmp_path: Any, catalog: ProductCatalog, opened_stores: list[Any], closed_clients: list[ValioClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _services_that_cannot_be_wired(monkeypatch)
    settings = Settings.for_tests(tta_mode="live", tta_data_dir=tmp_path / "var")  # no key: no call is sent

    with pytest.raises(RuntimeError, match="could not be wired"):
        build_parts(settings, catalog=catalog)

    assert _is_closed(opened_stores[0])
    assert len(closed_clients) == 1


def test_a_hook_that_fails_closes_the_live_client_and_no_store_was_opened_yet(
    tmp_path: Any, catalog: ProductCatalog, opened_stores: list[Any], closed_clients: list[ValioClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _agent_that_cannot_be_built(monkeypatch)
    settings = Settings.for_tests(tta_mode="live", tta_data_dir=tmp_path / "var")

    with pytest.raises(RuntimeError, match="model client"):
        build_parts(settings, catalog=catalog)

    assert opened_stores == []
    assert not settings.db_path.exists()
    assert len(closed_clients) == 1


def test_a_failed_start_does_not_close_a_gateway_the_caller_handed_in(
    settings: Settings, catalog: ProductCatalog, closable: Closable, opened_stores: list[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _services_that_cannot_be_wired(monkeypatch)

    with pytest.raises(RuntimeError, match="could not be wired"):
        build_parts(settings, catalog=catalog, gateway=closable)

    assert _is_closed(opened_stores[0])
    assert closable.closed == 0  # the caller built it and still holds it


def test_a_failed_close_during_a_failed_start_is_logged_and_the_first_error_is_the_one_raised(
    tmp_path: Any, catalog: ProductCatalog, opened_stores: list[Any], monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _services_that_cannot_be_wired(monkeypatch)
    settings = Settings.for_tests(tta_mode="live", tta_data_dir=tmp_path / "var")

    def cannot_close(client: ValioClient) -> None:
        raise OSError("the connection could not be closed")

    monkeypatch.setattr(ValioClient, "close", cannot_close)

    with caplog.at_level("ERROR", logger="tta.api.wiring"), pytest.raises(RuntimeError, match="could not be wired"):
        build_parts(settings, catalog=catalog)

    assert _is_closed(opened_stores[0])
    assert "could not be closed" in caplog.text


def test_create_app_closes_the_parts_when_a_surface_cannot_be_mounted(
    settings: Settings, catalog: ProductCatalog, closable: Closable, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "tta.ui.routes", types.ModuleType("tta.ui.routes"))  # no create_surface
    parts = build_parts(settings, catalog=catalog, gateway=closable)

    with pytest.raises(RuntimeError, match="create_surface"):
        create_app(settings, parts=parts)

    # The application owns the parts it was given, also when it cannot be built.
    assert _is_closed(parts.store)
    assert closable.closed == 1


def test_create_app_alone_closes_what_it_built_when_a_surface_cannot_be_mounted(
    settings: Settings, opened_stores: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "tta.api.mcp_surface", types.ModuleType("tta.api.mcp_surface"))

    with pytest.raises(RuntimeError, match="create_surface"):
        create_app(settings)

    assert len(opened_stores) == 1
    assert _is_closed(opened_stores[0])


# --- stopping -------------------------------------------------------------------------------------------


def test_the_app_closes_the_live_client_when_it_stops(
    tmp_path: Any, catalog: ProductCatalog, closed_clients: list[ValioClient]
) -> None:
    settings = Settings.for_tests(tta_mode="live", tta_data_dir=tmp_path / "var")  # no key: no call is sent
    parts = build_parts(settings, catalog=catalog)
    assert isinstance(parts.gateway, FallbackGateway)

    with TestClient(create_app(settings, parts=parts)) as client:
        assert client.get("/healthz").status_code == 200
        assert closed_clients == []

    assert len(closed_clients) == 1
    assert _is_closed(parts.store)


def test_closing_goes_on_after_a_close_that_fails_and_the_failure_is_raised(
    settings: Settings, catalog: ProductCatalog, closable: Closable
) -> None:
    class StoreThatCannotClose:
        def close(self) -> None:
            raise OSError("the database could not be closed")

    built = build_parts(settings, catalog=catalog, gateway=closable)
    parts = dataclasses.replace(built, store=StoreThatCannotClose())  # type: ignore[arg-type]

    with pytest.raises(OSError, match="database could not be closed"):
        parts.close()

    assert closable.closed == 1  # the store is closed first, and its failure did not stop the gateway's close
    built.close()


def test_when_every_close_fails_each_was_tried_and_the_first_failure_is_raised(
    settings: Settings, catalog: ProductCatalog, caplog: pytest.LogCaptureFixture
) -> None:
    class StoreThatCannotClose:
        def close(self) -> None:
            raise OSError("the database could not be closed")

    failing = Closable(ReplayGateway(settings.replay_capture_dir), fails=True)
    built = build_parts(settings, catalog=catalog)
    parts: Parts = dataclasses.replace(built, store=StoreThatCannotClose(), gateway=failing)  # type: ignore[arg-type]

    with caplog.at_level("ERROR", logger="tta.api.wiring"), pytest.raises(OSError, match="database"):
        parts.close()

    assert failing.closed == 1
    assert "database could not be closed" in caplog.text and "connection could not be closed" in caplog.text
    built.close()
