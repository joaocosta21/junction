"""The composition root: the real implementations behind the ports (task T09, wiring notes of waves 1 and 2).

Scores on the 30% "one continuous flow": every package was built against ports; this is where they meet.
`TTA_MODE=replay` answers from the capture with the clock pinned to it; `TTA_MODE=live` asks the mock API
and falls back to the capture when it cannot answer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from tta.api import hooks
from tta.api.fallback import FallbackGateway
from tta.api.identity import TokenRegistry, load_tokens
from tta.api.limits import RateLimit, RateLimiter, default_rate_limit
from tta.api.service import Gateway, GatewayDeps
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
from tta.store import open_store
from tta.valio import ReplayGateway, ValioClient

logger = logging.getLogger(__name__)


class UtcClock:
    """The real time, for audit events: an event is stamped when it is written, never with the pinned
    replay clock (decision T06-2)."""

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class Parts:
    """Everything `create_app` serves, built once per process."""

    settings: Settings
    catalog: Catalog
    gateway: ValioGateway  # the capture, or the live client with its fall-back
    replay: ReplayGateway  # the capture itself: the examples of /openapi.json are built from it in every mode
    clock: Clock  # the data clock: pinned to the capture after a replayed answer, the server's time otherwise
    policy: PolicyEngine
    store: Store
    audit: AuditSink
    service: Gateway
    tokens: TokenRegistry

    def close(self) -> None:
        """Release what `build_parts` opened: the database and, in live mode, the HTTP client."""
        for part in (self.store, self.gateway):
            close = getattr(part, "close", None)
            if callable(close):
                close()


def _gateway(settings: Settings, replay: ReplayGateway) -> ValioGateway:
    if settings.tta_mode is not DataSource.LIVE:
        return replay
    try:
        return FallbackGateway(ValioClient(settings), replay)
    except SupplierUnavailable as error:
        # The live client refuses an address that would carry the key in clear text (tta.valio.client).
        logger.warning("The live supplier client cannot be used (%s). Answering from the replay capture.", error.detail)
        return replay


def wire(
    *,
    catalog: Catalog,
    policy: PolicyEngine,
    gateway: ValioGateway,
    clock: Clock,
    store: Store,
    limiter: RateLimiter,
    request_parser: RequestParser | None = None,
    agent_runner: AgentRunner | None = None,
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
        request_parser=request_parser, agent_runner=agent_runner,
    ))
    return service, audit


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

    Raises `TokenConfigurationError` outside dev and demo when the environment holds no usable tokens, and
    `SupplierUnavailable` when the replay capture cannot be read.
    """
    policy = RulePolicyEngine.from_files()
    tokens = load_tokens(settings, policy.profile_ids())  # first: without tokens nothing else is worth building
    catalog = catalog or ProductCatalog.from_settings(settings)
    replay = ReplayGateway(settings.replay_capture_dir)
    gateway = gateway or _gateway(settings, replay)
    clock: Clock = gateway.clock if hasattr(gateway, "clock") else replay.clock
    keys = catalog.product_type_keys()
    store = open_store(settings)
    service, audit = wire(
        catalog=catalog, policy=policy, gateway=gateway, clock=clock, store=store,
        limiter=RateLimiter(rate_limit or default_rate_limit(settings.is_demo_environment)),
        request_parser=request_parser or hooks.request_parser(settings, clock, keys),
        agent_runner=agent_runner or hooks.agent_runner(settings, clock, keys),
    )
    return Parts(
        settings=settings, catalog=catalog, gateway=gateway, replay=replay, clock=clock, policy=policy,
        store=store, audit=audit, service=service, tokens=tokens,
    )
