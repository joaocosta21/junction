"""The composition root: the real implementations behind the ports (task T09, wiring notes of waves 1 and 2).

Scores on the 30% "one continuous flow": every package was built against ports; this is where they meet.
`TTA_MODE=replay` answers from the capture with the clock pinned to it; `TTA_MODE=live` asks the mock API
and falls back to the capture when it cannot answer. A configuration that cannot work stops the start; only
an outage, a spent budget or a full minute falls back. What a failed start had opened, it closes.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from tta.api import hooks
from tta.api.budget import MeteredAudit, StorageBudget
from tta.api.fallback import FallbackGateway
from tta.api.identity import TokenRegistry, load_tokens
from tta.api.limits import CallLimits, RateLimit, call_limits
from tta.api.sandbox import BookCustomer, Sandbox, Sandboxes
from tta.api.service import (
    MAX_DEMO_NAME_TERMS,
    MAX_DEMO_REQUEST_CHARACTERS,
    MAX_DEMO_REQUEST_LINES,
    Gateway,
    GatewayDeps,
)
from tta.api.signing import Signer
from tta.api.suggesting import CustomerOf, OfferSuggestions, customer_on_file
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
from tta.evidence import EvidenceFinder, build_evidence_finder
from tta.offers import OfferDeps, OfferService
from tta.orders import OrderBookService
from tta.orders.spend import day_spend
from tta.policy import RulePolicyEngine
from tta.standing import history_lookup
from tta.store import SqliteStore, open_store
from tta.store.postgres import open_postgres_store
from tta.suggestions import SuggestionPorts
from tta.valio import ReplayGateway, ValioClient

logger = logging.getLogger(__name__)


# The store of the shared order book, as `/healthz` names it: no path, no address, no secret.
POSTGRESQL, SQLITE = "postgresql", "sqlite"
STORE_IS_POSTGRESQL = "DATABASE_URL is set and the database answered at start-up"
STORE_IS_SQLITE = (
    "DATABASE_URL is not set, so orders and the audit trail are kept in the local database of this process"
)
STORE_FALLBACK = (
    "the PostgreSQL database could not be reached at start-up, so orders and the audit trail are kept in the local "
    "database of this process"
)
STORE_SCHEMA_REFUSED = (
    "TTA_DB_SCHEMA holds a name the PostgreSQL store refuses, so the database was not opened and orders and the "
    "audit trail are kept in the local database of this process"
)
STORE_FALLBACKS = (STORE_FALLBACK, STORE_SCHEMA_REFUSED)
STORE_REQUIRED_IN_PROD = (
    "DATABASE_URL is set, but the PostgreSQL store could not be opened ({why}). Outside dev and demo the gateway "
    "does not fall back to the local database of the process, where orders and the audit trail would be lost at "
    "the next restart: correct the database settings, or unset DATABASE_URL to choose the local database."
)
LIVE_CLIENT_NOT_BUILT = (
    "TTA_MODE=live was asked for, but the live supplier client cannot be built: {why} "
    "Correct VALIO_AIMO_BASE_URL, or start with TTA_MODE=replay."
)
DEMO_CLOCK_OUTSIDE_DEMO = (
    "TTA_DEMO_CLOCK is set, but TTA_ENV is neither dev nor demo. A clock somebody chose belongs to a "
    "demonstration only: unset TTA_DEMO_CLOCK, or start with TTA_ENV=demo and TTA_MODE=replay."
)
DEMO_CLOCK_NOT_HONOURED = (
    "TTA_DEMO_CLOCK is set and TTA_MODE is live: the demo clock is honoured in replay only, so the supplier's "
    "server time is the clock."
)


class GatewayConfigurationError(RuntimeError):
    """The gateway does not start on these settings. Live mode was asked for with settings the live client
    refuses (serving the capture instead would look like live mode until someone read an offer's source), a
    demo clock is set outside a demonstration, or outside dev and demo the PostgreSQL store that was asked for
    cannot be opened."""


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
    store_kind: str = SQLITE  # the database of the shared order book: `POSTGRESQL` or `SQLITE`
    # The key every answered offer and order record is signed with (`tta.api.signing`): the setting's, or a demo key.
    signer: Signer = field(default_factory=lambda: Signer.from_setting(None))
    evidence: EvidenceFinder | None = None  # held so that its HTTP client is closed with the rest

    @property
    def store_reason(self) -> str:
        """Why that store is in use, for `/healthz`: the fall-back's reason when the start had to fall back."""
        if self.store_kind == POSTGRESQL:
            return STORE_IS_POSTGRESQL
        return next((reason for reason in STORE_FALLBACKS if reason in self.start_reasons), STORE_IS_SQLITE)

    @property
    def opened(self) -> tuple[object, ...]:
        """What is to be closed, in that order: the sandboxes, the database, the evidence finder's HTTP client
        and, in live mode, the gateway's."""
        return (self.sandboxes, self.store, self.evidence, self.gateway)

    def close(self) -> None:
        """Release what is open. Each part is closed even when the one before it fails; the first failure is
        raised when all have had their turn."""
        failures = close_each(self.opened)
        if failures:
            raise failures[0]


def _order_book(settings: Settings) -> tuple[Store, tuple[str, ...], str]:
    """The store of the shared order book, what to report about it and its kind: PostgreSQL when `DATABASE_URL` is set
    (task S1), the SQLite file otherwise. In dev and demo a database that cannot be reached or prepared at start-up
    does not stop the gateway: it starts on SQLite and says why, with a reason of its own for a schema name the
    store refuses. Anywhere else it raises `GatewayConfigurationError`: a production order book is not moved to a
    file that a restart may lose. The cause is logged by its type only: the URL and the driver's message, which
    can hold the host, are not repeated."""
    if not settings.has_database_url:
        return open_store(settings), (), SQLITE
    try:
        return open_postgres_store(settings), (), POSTGRESQL
    except SupplierUnavailable as error:
        cause = error.__cause__
        reason = STORE_SCHEMA_REFUSED if isinstance(cause, ValueError) else STORE_FALLBACK
        why = f"{type(error).__name__}, caused by {type(cause).__name__}" if cause else type(error).__name__
        if not settings.is_demo_environment:
            logger.error("DATABASE_URL is set, but the PostgreSQL store was not opened (%s): not starting.", why)
            raise GatewayConfigurationError(STORE_REQUIRED_IN_PROD.format(why=why)) from error
        logger.warning("DATABASE_URL is set, but the PostgreSQL store was not opened (%s): using SQLite.", why)
        return open_store(settings), (reason,), SQLITE


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


def suggestions_in(settings: Settings) -> bool:
    """Whether offers carry suggestions: in replay only. A suggestion's price and confirmed stock are looked up
    like an offer's, up to three more looks per offer; in live mode those would be spent from the supplier's call
    budget and from the visitor's live looks a minute, and an offer that began live would be answered from the
    capture. So a live offer has no suggestions, and `/openapi.json` says so."""
    return settings.tta_mode is not DataSource.LIVE


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
    evidence: EvidenceFinder | None = None,
    supplier_suggestions: bool = True,
    customer_of: CustomerOf = customer_on_file,
    suggestions: bool = True,
    demo_limits: bool = False,
) -> tuple[Gateway, AuditSink]:
    """The services over one store: one audit trail, the offer service, the order book, the gateway service.
    `supplier_suggestions`: Valio Aimo's own suggestion on an offer (`TTA_SUPPLIER_SUGGESTIONS`). `customer_of`: whose
    customer file an offer's suggestions are computed from; by default the file of the caller's buyer profile.
    `suggestions`: False leaves every offer without suggestions (`suggestions_in`: live mode). `demo_limits`: the
    limits of dev and demo on a request's words and a search's name terms (review H2 and M3). When the limiter
    holds a day's budget of stored bytes, every event the trail writes is counted against it."""
    # One trail per store and process. In dev and demo it counts what it writes against the day's budget.
    if limiter.storage is not None:
        audit: AuditTrail = MeteredAudit(store, UtcClock(), limiter.storage, policy=policy)
    else:
        audit = AuditTrail(store, UtcClock(), policy=policy)
    offers = OfferService(OfferDeps(
        catalog=catalog, gateway=gateway, policy=policy, clock=clock,
        # Both parts of the day's spend, so rule P-02's sentence says what is ordered and what waits for a person.
        day_spend=lambda profile_id: day_spend(store, clock, profile_id),
        standing_history=history_lookup(store),  # rule P-08 (task STAND-1)
    ))
    orders = OrderBookService(
        store=store, policy=policy, revalidator=offers, audit=audit, clock=clock, evidence=evidence
    )
    service = Gateway(GatewayDeps(
        catalog=catalog, policy=policy, store=store, audit=audit, offers=offers, orders=orders, limiter=limiter,
        request_parser=request_parser, agent_runner=agent_runner, max_request_lines=max_request_lines,
        max_request_characters=MAX_DEMO_REQUEST_CHARACTERS if demo_limits else None,
        max_name_terms=MAX_DEMO_NAME_TERMS if demo_limits else None,
        suggestions=OfferSuggestions(
            ports=SuggestionPorts(catalog=catalog, gateway=gateway, clock=clock), policy=policy, store=store,
            audit=audit, supplier_suggestions=supplier_suggestions, customer_of=customer_of,
        ) if suggestions else None,
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
    demo_limits: bool = False  # dev and demo: the limits on a request's words and a search's name terms
    evidence: EvidenceFinder | None = None  # web evidence on a dietitian's approval card (task S2)
    supplier_suggestions: bool = True
    suggestions: bool = True

    def sandbox(self) -> Sandbox:
        """A new, empty order book in memory, over the shared parts."""
        store = SqliteStore()
        customer = BookCustomer()  # the shop names it; until then "My kitchen" has no customer file
        service, audit = wire(
            catalog=self.catalog, policy=self.policy, gateway=self.gateway, clock=self.clock, store=store,
            limiter=self.limiter, request_parser=self.request_parser, agent_runner=self.agent_runner,
            max_request_lines=self.max_request_lines, evidence=self.evidence,
            supplier_suggestions=self.supplier_suggestions, customer_of=customer.of, suggestions=self.suggestions,
            demo_limits=self.demo_limits,
        )
        return Sandbox(service=service, store=store, audit=audit, customer=customer)


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
    `GatewayConfigurationError` when live mode is asked for with an address the live client refuses, or when a
    demo clock is set outside dev and demo,
    `SigningKeyError` when `TTA_SIGNING_KEY` is set to something that is not an Ed25519 seed,
    `HookError` when an optional package is there without what the gateway calls, and `SupplierUnavailable`
    when the replay capture cannot be read. Whatever this function had opened by then is closed again.
    """
    if settings.tta_demo_clock is not None and not settings.is_demo_environment:
        raise GatewayConfigurationError(DEMO_CLOCK_OUTSIDE_DEMO)
    if settings.tta_demo_clock is not None and settings.demo_clock is None:
        logger.warning(DEMO_CLOCK_NOT_HONOURED)
    signer = Signer.from_setting(settings.tta_signing_key)  # a key that was set and cannot be used stops the start
    policy = RulePolicyEngine.from_files()
    tokens = load_tokens(settings, policy.profile_ids())  # first: without tokens nothing else is worth building
    catalog = catalog or ProductCatalog.from_settings(settings)
    replay = ReplayGateway.from_settings(settings)
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
        evidence = build_evidence_finder(settings, settings.tta_data_dir, catalog)
        opened.insert(0, evidence)
        shared = _Shared(
            catalog=catalog, policy=policy, gateway=gateway, clock=clock,
            # The demonstration tokens are public and shared: there a caller is counted per visitor.
            # In dev and demo an address and a token also have a day's budget of stored bytes (review H2).
            limiter=call_limits(demo, rate_limit, storage=StorageBudget() if demo else None),
            request_parser=request_parser, agent_runner=agent_runner,
            max_request_lines=MAX_DEMO_REQUEST_LINES if demo else None, demo_limits=demo, evidence=evidence,
            supplier_suggestions=settings.tta_supplier_suggestions, suggestions=suggestions_in(settings),
        )
        store, start_reasons, store_kind = _order_book(settings)
        opened.insert(0, store)
        service, audit = wire(
            catalog=catalog, policy=policy, gateway=gateway, clock=clock, store=store, limiter=shared.limiter,
            request_parser=request_parser, agent_runner=agent_runner, max_request_lines=shared.max_request_lines,
            evidence=evidence, supplier_suggestions=settings.tta_supplier_suggestions,
            suggestions=suggestions_in(settings), demo_limits=demo,
        )
    except BaseException:
        close_each(opened)  # a close that fails here is logged; the error that stopped the start is raised
        raise
    return Parts(
        settings=settings, catalog=catalog, gateway=gateway, replay=replay, clock=clock, policy=policy,
        store=store, audit=audit, service=service, tokens=tokens,
        sandboxes=Sandboxes(shared.sandbox) if demo else None, start_reasons=start_reasons,
        store_kind=store_kind, signer=signer, evidence=evidence,
    )
