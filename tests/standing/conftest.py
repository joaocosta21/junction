"""Fixtures for the standing-order tests: the gateway in replay over tonight's capture, wired as `tta.api.wiring.wire`
is, plus the one thing STAND-1 adds to it: `OfferDeps.standing_history` over the same store. No live service.

Every helper is a fixture, because test modules cannot import from one another (`--import-mode=importlib`).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tta.api.limits import call_limits
from tta.api.service import Gateway, GatewayDeps
from tta.api.wiring import UtcClock
from tta.audit import AuditTrail
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import Identity
from tta.offers import OfferDeps, OfferService
from tta.orders import OrderBookService, day_committed_net_eur
from tta.policy import RulePolicyEngine
from tta.standing import StandingOrders, history_lookup
from tta.store import SqliteStore
from tta.valio import ReplayGateway

CAPTURE = "2026-11-14-demo"


@dataclass(frozen=True)
class Book:
    """One order book in replay with standing orders: what the orchestrator wires for the shared book and each page
    sandbox."""

    store: SqliteStore
    audit: AuditTrail
    service: Gateway
    standing: StandingOrders
    replay: ReplayGateway


@pytest.fixture(scope="session")
def catalog() -> ProductCatalog:
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture(scope="session")
def replay() -> ReplayGateway:
    return ReplayGateway(Settings.for_tests(tta_replay_capture=CAPTURE).replay_capture_dir)


@pytest.fixture(scope="session")
def policy() -> RulePolicyEngine:
    return RulePolicyEngine.from_files()


def build_book(catalog: ProductCatalog, replay: ReplayGateway, policy: RulePolicyEngine) -> Book:
    store, clock = SqliteStore(), replay.clock
    audit = AuditTrail(store, UtcClock(), policy=policy)
    offers = OfferService(OfferDeps(
        catalog=catalog, gateway=replay, policy=policy, clock=clock,
        day_spend=lambda profile_id: day_committed_net_eur(store, clock, profile_id),
        standing_history=history_lookup(store),
    ))
    orders = OrderBookService(store=store, policy=policy, revalidator=offers, audit=audit, clock=clock)
    service = Gateway(GatewayDeps(
        catalog=catalog, policy=policy, store=store, audit=audit, offers=offers, orders=orders,
        limiter=call_limits(False),
    ))
    standing = StandingOrders(store=store, audit=audit, gateway=service, clock=clock)
    return Book(store=store, audit=audit, service=service, standing=standing, replay=replay)


@pytest.fixture
def book(catalog: ProductCatalog, replay: ReplayGateway, policy: RulePolicyEngine) -> Iterator[Book]:
    built = build_book(catalog, replay, policy)
    yield built
    built.store.close()


@pytest.fixture(scope="session")
def capture_dir() -> Path:
    return Settings.for_tests(tta_replay_capture=CAPTURE).replay_capture_dir


@pytest.fixture(scope="session")
def hotel_agent(agent_hotel: Identity) -> Identity:
    return agent_hotel
