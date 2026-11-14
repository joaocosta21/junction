"""The composition root: the real implementations behind the ports (task T09, wiring notes of waves 1 and 2).

Scores on the 30% "one continuous flow": every package was built against ports; this is where they meet.
`TTA_MODE=replay` answers from the capture with the clock pinned to it; `TTA_MODE=live` asks the mock API
and falls back to the capture when it cannot answer. A configuration that cannot work stops the start; only
an outage, a spent budget or a full minute falls back. What a failed start had opened, it closes.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from tta.api import hooks
from tta.api.fallback import FallbackGateway
from tta.api.identity import TokenRegistry, load_tokens
from tta.api.limits import CallLimits, RateLimit, call_limits
from tta.api.sandbox import Sandbox, Sandboxes
from tta.api.service import MAX_DEMO_REQUEST_LINES, Gateway, GatewayDeps
from tta.audit import AuditTrail
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import DataSource
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import (
    AgentRunner,
    AuditSink,
    Catalog,
    Clock,
    PolicyEngine,
    RequestParser,
    Store,
    ValioGateway,
)
from tta.offers import OfferDeps, OfferService
from tta.orders import OrderBookService, day_committed_net_eur
from tta.policy import RulePolicyEngine
from tta.store import SqliteStore, open_store
from tta.store.postgres import open_postgres_store
from tta.valio import ReplayGateway, ValioClient

logger = logging.getLogger(__name__)


# A reason of `/healthz`: no path, no address, no secret.
STORE_FALLBACK = (
    "the PostgreSQL database could not be reached at start-up, so orders and the audit trail are kept in the local "
    "database of this process"
)
LIVE_CLIENT_NOT_BUILT = (
    "TTA_MODE=live was asked for, but the live supplier client cannot be built: {why} "
    "Correct VALIO_AIMO_BASE_URL, or start with TTA_MODE=replay."
)


class GatewayConfigurationError(RuntimeError):
    """Live mode was asked for with settings the live client refuses. The gateway does not start: serving
    the capture instead would look like live mode until someone read an offer's source."""


class UtcClock:
    """The real time, for audit events: an event is stamped when it is written, never with the pinned
    replay clock (decision T06-2)."""

    def now(self) -> datetime:
        return datetime.now(UTC)


def close_each(parts: Iterable[object]) -> list[Exception]:
    """Close every part that can be closed, also after one of them fails. Each failure is logged and returned."""
    failures: list[Exception] = []
    for part in parts:
        close = getattr(part, "close", None)
        if not callable(close):
            continue
        try:
            close()
        except Exception as error:  # every part gets its turn; the caller decides what to raise
            logger.error("%s could not be closed: %s", type(part).__name__, error, exc_info=error)
            failures.append(error)
    return failures


@dataclass(frozen=True)
class Parts:
    """Everything `create_app` serves, built once per process."""

    settings: Settings
    catalog: Catalog
    gateway: ValioGateway  # the capture, or the live client with its fall-back
    replay: ReplayGateway  # the capture itself: the examples of /openapi.json are built from it in every mode
    clock: Clock  # the data clock: pinned to the capture in replay mode, the live clock in live mode
    policy: PolicyEngine
    store: Store
    audit: AuditSink
    service: Gateway
    tokens: TokenRegistry
    sandboxes: Sandboxes | None = None  # the pages' private order books: in dev and demo only
    start_reasons: tuple[str, ...] = ()  # what the start had to do without, until a restart: for `/healthz`

    @property
    def opened(self) -> tuple[object, ...]:
        """What is to be closed, in that order: the sandboxes, the database and, in live mode, the gateway's
        HTTP client."""
        return (self.sandboxes, self.store, self.gateway)

    def close(self) -> None:
        """Release what is open. Each part is closed even when the one before it fails; the first failure is
        raised when all have had their turn."""
        failures = close_each(self.opened)
        if failures:
            raise failures[0]


def _order_book(settings: Settings) -> tuple[Store, tuple[str, ...]]:
    """The store of the shared order book and what to report about it: PostgreSQL when `DATABASE_URL` is set
    (task S1), the SQLite file otherwise. A database that cannot be reached or prepared at start-up does not stop
    the gateway: it starts on SQLite and says why. The URL is not repeated."""
    if not settings.has_database_url:
        return open_store(settings), ()
    try:
        return open_postgres_store(settings), ()
    except SupplierUnavailable:
        logger.warning("DATABASE_URL is set, but the database could not be reached at start-up: using SQLite.")
        return open_store(settings), (STORE_FALLBACK,)


def _gateway(settings: Settings, replay: ReplayGateway) -> ValioGateway:
    """The capture in replay mode; in live mode the live client with its fall-back to the capture.

    Raises `GatewayConfigurationError` when the live client refuses its settings (an address that would
    carry the key in clear text, `tta.valio.client`). The address is not repeated.
    """
    if settings.tta_mode is not DataSource.LIVE:
        return replay
    try:
        live = ValioClient(settings)
    except SupplierUnavailable as error:
        raise GatewayConfigurationError(LIVE_CLIENT_NOT_BUILT.format(why=error.detail)) from error
    return FallbackGateway(live, replay)


def wire(
    *,
    catalog: Catalog,
    policy: PolicyEngine,
    gateway: ValioGateway,
    clock: Clock,
    store: Store,
    limiter: CallLimits,
    request_parser: RequestParser | None = None,
    agent_runner: AgentRunner | None = None,
    max_request_lines: int | None = None,
) -> tuple[Gateway, AuditSink]:
    """The services over one store: one audit trail, the offer service, the order book, the gateway service."""
    audit = AuditTrail(store, UtcClock(), policy=policy)  # one per store and process
    offers = OfferService(OfferDeps(
        catalog=catalog, gateway=gateway, policy=policy, clock=clock,
        day_spend=lambda profile_id: day_committed_net_eur(store, clock, profile_id),
    ))
    orders = OrderBookService(store=store, policy=policy, revalidator=offers, audit=audit, clock=clock)
    service = Gateway(GatewayDeps(
        catalog=catalog, policy=policy, store=store, audit=audit, offers=offers, orders=orders, limiter=limiter,
        request_parser=request_parser, agent_runner=agent_runner, max_request_lines=max_request_lines,
    ))
    return service, audit


@dataclass(frozen=True)
class _Shared:
    """What every order book of the process shares: everything but the store and what writes to it."""

    catalog: Catalog
    policy: PolicyEngine
    gateway: ValioGateway
    clock: Clock
    limiter: CallLimits
    request_parser: RequestParser | None
    agent_runner: AgentRunner | None
    max_request_lines: int | None

    def sandbox(self) -> Sandbox:
        """A new, empty order book in memory, over the shared parts."""
        store = SqliteStore()
        service, audit = wire(
            catalog=self.catalog, policy=self.policy, gateway=self.gateway, clock=self.clock, store=store,
            limiter=self.limiter, request_parser=self.request_parser, agent_runner=self.agent_runner,
            max_request_lines=self.max_request_lines,
        )
        return Sandbox(service=service, store=store, audit=audit)


def build_parts(
    settings: Settings,
    *,
    catalog: Catalog | None = None,
    gateway: ValioGateway | None = None,
    request_parser: RequestParser | None = None,
    agent_runner: AgentRunner | None = None,
    rate_limit: RateLimit | None = None,
) -> Parts:
    """Wire the gateway for these settings. The keyword arguments replace one part each, for a test or a
    caller that already holds it (the catalog takes about 1.3 seconds to build).

    Raises `TokenConfigurationError` outside dev and demo when the environment holds no usable tokens,
    `GatewayConfigurationError` when live mode is asked for with an address the live client refuses,
    `HookError` when an optional package is there without what the gateway calls, and `SupplierUnavailable`
    when the replay capture cannot be read. Whatever this function had opened by then is closed again.
    """
    policy = RulePolicyEngine.from_files()
    tokens = load_tokens(settings, policy.profile_ids())  # first: without tokens nothing else is worth building
    catalog = catalog or ProductCatalog.from_settings(settings)
    replay = ReplayGateway(settings.replay_capture_dir)
    opened: list[object] = []  # what this call opened itself, newest first: a gateway handed in is the caller's
    try:
        if gateway is None:
            gateway = _gateway(settings, replay)
            opened.insert(0, gateway)
        clock: Clock = gateway.clock if hasattr(gateway, "clock") else replay.clock
        keys = catalog.product_type_keys()
        request_parser = request_parser or hooks.request_parser(settings, clock, keys)
        agent_runner = agent_runner or hooks.agent_runner(settings, clock, keys)
        demo = settings.is_demo_environment
        shared = _Shared(
            catalog=catalog, policy=policy, gateway=gateway, clock=clock,
            # The demonstration tokens are public and shared: there a caller is counted per visitor.
            limiter=call_limits(demo, rate_limit), request_parser=request_parser, agent_runner=agent_runner,
            max_request_lines=MAX_DEMO_REQUEST_LINES if demo else None,
        )
        store, start_reasons = _order_book(settings)
        opened.insert(0, store)
        service, audit = wire(
            catalog=catalog, policy=policy, gateway=gateway, clock=clock, store=store, limiter=shared.limiter,
            request_parser=request_parser, agent_runner=agent_runner, max_request_lines=shared.max_request_lines,
        )
    except BaseException:
        close_each(opened)  # a close that fails here is logged; the error that stopped the start is raised
        raise
    return Parts(
        settings=settings, catalog=catalog, gateway=gateway, replay=replay, clock=clock, policy=policy,
        store=store, audit=audit, service=service, tokens=tokens,
        sandboxes=Sandboxes(shared.sandbox) if demo else None, start_reasons=start_reasons,
    )
